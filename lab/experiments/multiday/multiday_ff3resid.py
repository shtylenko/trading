#!/usr/bin/env python3
"""x04 FF3 / size-factor residual momentum — pre-registered test
(`multiday_x04_ff3resid_preregistration.md`).

Extends x03 (CAPM/market-only residual momentum) to a 3-factor residual: market (SPY) + size
(SMB-proxy = IWM−SPY) + value (HML-proxy = IWD−IWF). Ranks on mean(ε)/std(ε) of the multi-factor
residual; everything else identical to x03. Question: does stripping size+value beta from the
ranking HOLD Sharpe while cutting beta (adopt), or trade Sharpe for beta (lower-beta variant only)?
2025 sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_ff3resid \
        --price-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --start-year 2022 --end-year 2024
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

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.validation.deflated_sharpe import deflated_sharpe_ratio

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
FORM_LB = 252
SKIP = 21
MIN_OBS = 126


def _beta_adj(r, m):
    r = np.asarray(r); m = np.asarray(m); n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat; s2 = (e @ e) / (n - 2); cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _metrics(r, m):
    r = np.asarray(r); m = np.asarray(m); ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t, b = _beta_adj(r, m)
    return {"sharpe": r.mean() / sd * ann if sd > 0 else np.nan, "beta": b, "alpha": a,
            "t_alpha": t, "maxdd": float((eq / peak - 1).min())}


def _capm_resid(R0, mask, spy):
    """x03 CAPM residual momentum (market only), per column."""
    spd = spy - np.nanmean(spy); var_sp = float(np.nansum(spd * spd))
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, R0 - beta[None, :] * spy[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def _multifactor_resid(R0, mask, factors):
    """3-factor residual momentum via shared residual-maker M = I − X(XᵀX)⁻¹Xᵀ.

    factors: (T×F) matrix of [SPY, SMB, HML] (no intercept col — add it). R0: (T×N) zero-filled
    returns. Residual ε = M @ R0; signal = mean(ε)/std(ε) over masked (real-data) positions.
    """
    T = R0.shape[0]
    X = np.column_stack([np.ones(T), factors])              # T×(F+1)
    XtX_inv = np.linalg.inv(X.T @ X)
    M = np.eye(T) - X @ XtX_inv @ X.T                        # T×T residual maker
    eps = M @ R0                                            # T×N residuals
    eps = np.where(mask, eps, np.nan)
    mu = np.nanmean(eps, axis=0); sd = np.nanstd(eps, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def main() -> None:
    p = argparse.ArgumentParser(description="x04 FF3/size residual momentum")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    df = pd.read_parquet(_abs(args.price_ledger))
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values="fwd_20", aggfunc="last")
    mom = df.pivot_table(index="trade_date", columns="ticker", values="mom_12_1", aggfunc="last")
    dates = list(close.index)

    def etf_ret(sym):
        s = fetch_daily_range(sym, dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
        s.index = pd.DatetimeIndex(s.index).normalize().tz_localize(None)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        return s["close"].pct_change().reindex(close.index)

    spy_r = etf_ret("SPY"); iwm_r = etf_ret("IWM"); iwd_r = etf_ret("IWD"); iwf_r = etf_ret("IWF")
    smb = (iwm_r - spy_r).values; hml = (iwd_r - iwf_r).values; spyv = spy_r.values
    spy_fwd = (fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10),
               adjustment="split")["close"])
    spy_fwd.index = pd.DatetimeIndex(spy_fwd.index).normalize().tz_localize(None)
    spy_fwd = spy_fwd[~spy_fwd.index.duplicated(keep="last")].sort_index()
    spy_fwd = (spy_fwd.shift(-H) / spy_fwd - 1.0).reindex(close.index)

    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal = [j for j in range(len(dates)) if j % H == 0 and in_window[j]]

    x01_r, x03_r, ff3_r, mkt = [], [], [], []
    for j in rebal:
        d = dates[j]; lo, hi = j - FORM_LB, j - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi].values
        sp = spyv[lo:hi]; fc = np.column_stack([spyv[lo:hi], smb[lo:hi], hml[lo:hi]])
        if not (np.isfinite(sp).all() and np.isfinite(fc).all()):
            continue
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values; mom_row = mom.loc[d].values
        obs = np.isfinite(win).sum(axis=0)
        cand = elig_row & np.isfinite(fwd_row) & (obs >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        Rc = win[:, cand]; mask = np.isfinite(Rc); R0 = np.where(mask, Rc, 0.0)
        capm = _capm_resid(R0, mask, sp)
        ff3 = _multifactor_resid(R0, mask, fc)
        mom_c = mom_row[cand]; fwd_c = fwd_row[cand]

        def topmean(score):
            if np.isfinite(score).sum() < TOP_N:
                return None
            order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
            return float(np.mean(fwd_c[order])) - COST

        a, b, c = topmean(mom_c), topmean(capm), topmean(ff3)
        if None in (a, b, c):
            continue
        x01_r.append(a); x03_r.append(b); ff3_r.append(c); mkt.append(float(spy_fwd.loc[d]))

    x01_r, x03_r, ff3_r, mkt = map(np.array, (x01_r, x03_r, ff3_r, mkt))
    n = len(mkt)
    print(f"FF3/size residual momentum: {args.start_year}-{args.end_year} ({n} periods, 2025 sealed)")
    if n < 10:
        print("too few periods"); return
    schemes = {"x01 mom": x01_r, "x03 CAPM resid": x03_r, "x04 FF3 resid": ff3_r}
    srs = [s.mean() / s.std(ddof=1) for s in schemes.values()]
    sr_var = float(np.var(srs, ddof=1))
    print(f"\n{'scheme':18}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'DSR':>7}")
    M = {}
    for name, s in schemes.items():
        m = _metrics(s, mkt); d_ = deflated_sharpe_ratio(s, sr_var, 3.0)["dsr"]; M[name] = m
        print(f"{name:18}{m['sharpe']:>+7.2f}{m['beta']:>+7.2f}{m['alpha']*100:>+8.2f}"
              f"{m['t_alpha']:>+7.2f}{m['maxdd']*100:>+8.1f}{d_:>7.3f}")
    corr = float(np.corrcoef(ff3_r, x03_r)[0, 1])
    x3, f3 = M["x03 CAPM resid"], M["x04 FF3 resid"]
    print(f"\ncorr(FF3, x03) = {corr:+.2f}")
    print(f"FF3 vs x03: Sharpe {x3['sharpe']:+.2f}→{f3['sharpe']:+.2f}, "
          f"beta {x3['beta']:+.2f}→{f3['beta']:+.2f}, alpha {x3['alpha']*100:+.2f}%→{f3['alpha']*100:+.2f}%")
    print(">>> BAR: Sharpe ≥ x03 AND beta materially lower AND alpha ≥ x03")
    if f3["sharpe"] >= x3["sharpe"] and f3["beta"] < x3["beta"] - 0.05 and f3["alpha"] >= x3["alpha"]:
        v = "ADOPT FF3-residual"
    elif f3["beta"] < x3["beta"] - 0.05:
        v = "LOWER-BETA VARIANT (Sharpe-for-beta; keep x03 default)"
    else:
        v = "REJECT (no meaningful improvement; x03 CAPM optimal)"
    print(f">>> VERDICT: {v}")


if __name__ == "__main__":
    main()
