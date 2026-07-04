#!/usr/bin/env python3
"""Multi-factor residual momentum — extends x03 (CAPM-residual) to a SIZE and FF3
residual, to test whether x01's "beta" is partly a small-cap tilt that a size factor
strips further. Factors are buyable-ETF proxies (no external FF data needed):
    market = SPY return;  size (SMB) = IWM − SPY;  value (HML) = IWD − IWF.
Per name at rebalance d, regress daily r_i on the chosen factors (NO intercept, so the
residual mean = factor-adjusted mean return = alpha) over [d-252,d-21]; signal =
mean(ε)/std(ε). Compares base 12-1, CAPM (x03), CAPM+size, FF3 — Sharpe, beta-to-SPY,
beta-adjusted alpha, maxDD, DSR. 2025 sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom_ff3 \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.data.market_data import fetch_daily_range
from trading.lab.validation.deflated_sharpe import deflated_sharpe_ratio

H, TOP_N, COST, FORM, SKIP, MIN_OBS = 20, 50, 10.0 / 10000.0, 252, 21, 126
SCHEMES = ("base", "capm", "capm_size", "ff3")


def _etf_ret(sym, lo, hi):
    d = fetch_daily_range(sym, lo - timedelta(days=10), hi + timedelta(days=10), adjustment="split")
    d.index = pd.DatetimeIndex(d.index).normalize().tz_localize(None)
    return d[~d.index.duplicated(keep="last")].sort_index()["close"].pct_change()


def _alpha(r, m):
    n = len(r); X = np.column_stack([np.ones(n), m])
    bhat = np.linalg.lstsq(X, r, rcond=None)[0]
    e = r - X @ bhat; s2 = (e @ e) / (n - 2); cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _stats(r, m):
    r = np.asarray(r); m = np.asarray(m); ann = np.sqrt(252.0 / H)
    eq = np.cumprod(1 + r); a, ta, beta = _alpha(r, m)
    return {"mean": r.mean(), "sharpe": r.mean() / r.std(ddof=1) * ann, "beta": beta,
            "alpha": a, "t": ta, "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    a = ap.parse_args()
    path = Path(a.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change(fill_method=None)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")
    mom = df.pivot_table(index="trade_date", columns="ticker", values="mom_12_1", aggfunc="last")
    lo, hi = close.index[0], close.index[-1]
    spy, iwm, iwd, iwf = (_etf_ret(s, lo, hi).reindex(close.index) for s in ("SPY", "IWM", "IWD", "IWF"))
    spy_fwd = (fetch_daily_range("SPY", lo - timedelta(days=10), hi + timedelta(days=30), adjustment="split")
               .assign(c=lambda x: x["close"]))
    spy_fwd.index = pd.DatetimeIndex(spy_fwd.index).normalize().tz_localize(None)
    spy_fwd = spy_fwd[~spy_fwd.index.duplicated(keep="last")].sort_index()["close"]
    spf = (spy_fwd.shift(-H) / spy_fwd - 1.0).reindex(close.index)
    # factor matrices (returns), columns market/size/value
    F = {"capm": np.column_stack([spy.values]),
         "capm_size": np.column_stack([spy.values, (iwm - spy).values]),
         "ff3": np.column_stack([spy.values, (iwm - spy).values, (iwd - iwf).values])}

    dates = list(close.index); rebal = dates[::H]
    out = {s: [] for s in SCHEMES}; mkt = []
    for d in rebal:
        di = close.index.get_loc(d); a0, b0 = di - FORM, di - SKIP
        if a0 < 1 or b0 <= a0 + MIN_OBS or not np.isfinite(spf.loc[d]):
            continue
        Rw = rets.iloc[a0:b0].values
        obs = np.isfinite(Rw).sum(0)
        el = elig.loc[d].fillna(False).values.astype(bool); fw = fwd.loc[d].values; mo = mom.loc[d].values
        cand = el & np.isfinite(fw) & (obs >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        Rc = Rw[:, cand]; mask = np.isfinite(Rc); Rc0 = np.where(mask, Rc, 0.0)
        fwc = fw[cand]; moc = mo[cand]
        def topmean(score):
            return float(np.mean(fwc[np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]])) - COST
        scores = {"base": moc}
        for fac in ("capm", "capm_size", "ff3"):
            Xf = F[fac][a0:b0]
            good = np.isfinite(Xf).all(1)
            Xg = Xf[good]; Rg = Rc0[good]
            coef = np.linalg.lstsq(Xg, Rg, rcond=None)[0]      # (K × Ncand), no intercept
            resid = np.where(mask[good], Rg - Xg @ coef, np.nan)
            with np.errstate(invalid="ignore"):
                sd = np.nanstd(resid, axis=0, ddof=1)
                scores[fac] = np.where(sd > 0, np.nanmean(resid, axis=0) / sd, np.nan)
        if any(np.isfinite(scores[s]).sum() < TOP_N for s in scores):
            continue
        for s in SCHEMES:
            out[s].append(topmean(scores[s]))
        mkt.append(float(spf.loc[d]))
    mkt = np.array(mkt); n = len(mkt)
    arr = {s: np.array(out[s]) for s in SCHEMES}
    fin = np.isfinite(mkt) & np.all([np.isfinite(arr[s]) for s in SCHEMES], axis=0)
    mkt = mkt[fin]; arr = {s: arr[s][fin] for s in SCHEMES}; n = len(mkt)
    srs = [arr[s].mean() / arr[s].std(ddof=1) for s in SCHEMES]; sr_var = float(np.var(srs, ddof=1))
    print(f"Multi-factor residual momentum: {path.name}  ({n} periods, 2025 sealed)")
    print(f"{'scheme':11}{'perPer%':>9}{'annSh':>7}{'betaSPY':>9}{'alpha%':>8}{'t(a)':>7}{'maxDD':>8}{'DSR':>7}")
    for s in SCHEMES:
        m = _stats(arr[s], mkt); dsr = deflated_sharpe_ratio(arr[s], sr_var, len(SCHEMES))["dsr"]
        print(f"{s:11}{m['mean']*100:>+9.2f}{m['sharpe']:>+7.2f}{m['beta']:>+9.2f}"
              f"{m['alpha']*100:>+8.2f}{m['t']:>+7.2f}{m['maxdd']*100:>+8.1f}{dsr:>7.3f}")
    print("\n(alpha/beta are vs SPY only, for comparability. ff3 should show the lowest SPY beta if size/value strip more.)")


if __name__ == "__main__":
    main()
