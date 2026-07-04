#!/usr/bin/env python3
"""x03 + vol-target sizing overlay — pre-registered
(`multiday_x03_voltarget_preregistration.md`). Builds the x03 residual-momentum book
per-period returns, then scales exposure by min(L_max, σ_target/σ̂_t) where σ̂_t is the
STRATEGY's OWN trailing realized vol over the prior K=6 non-overlapping periods (leak-safe;
σ_target = first-year mean, fixed forward). Variants L_max∈{1.0 defensive, 1.5 modest-lever,
6% APR financing}. Reports unscaled vs scaled: Sharpe, CAGR, maxDD, beta, beta-adj alpha,
avg/min exposure. 2025 sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_x03_voltarget \
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

H, TOP_N, COST, FORM, SKIP, MIN_OBS = 20, 50, 10.0 / 10000.0, 252, 21, 126
K = 6                       # trailing periods for the strategy's own realized vol
BORROW_APR = 0.06
ANN = np.sqrt(252.0 / H)


def _residual_book(path):
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change(fill_method=None)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")
    spy = fetch_daily_range("SPY", close.index[0] - timedelta(days=10), close.index[-1] + timedelta(days=30), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    sret = spy["close"].pct_change().reindex(close.index)
    sfwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)
    dates = list(close.index); rebal = dates[::H]
    r, m, ds = [], [], []
    for d in rebal:
        di = close.index.get_loc(d); a0, b0 = di - FORM, di - SKIP
        if a0 < 1 or b0 <= a0 + MIN_OBS or not np.isfinite(sfwd.loc[d]):
            continue
        sp = sret.iloc[a0:b0].values; spd = sp - np.nanmean(sp); var = float(np.nansum(spd * spd))
        if var <= 0:
            continue
        el = elig.loc[d].fillna(False).values.astype(bool); fw = fwd.loc[d].values
        Rw = rets.iloc[a0:b0].values; obs = np.isfinite(Rw).sum(0)
        cand = el & np.isfinite(fw) & (obs >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        Rc = Rw[:, cand]; mask = np.isfinite(Rc)
        beta = (np.where(mask, Rc, 0.0) * spd[:, None]).sum(0) / var
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        with np.errstate(invalid="ignore"):
            sd = np.nanstd(resid, 0, ddof=1)
            score = np.where(sd > 0, np.nanmean(resid, 0) / sd, np.nan)
        if np.isfinite(score).sum() < TOP_N:
            continue
        fwc = fw[cand]
        top = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
        r.append(float(np.mean(fwc[top])) - COST); m.append(float(sfwd.loc[d])); ds.append(d)
    return np.array(r), np.array(m), pd.DatetimeIndex(ds)


def _metrics(r, m):
    eq = np.cumprod(1 + r); n = len(r)
    X = np.column_stack([np.ones(n), m]); bh = np.linalg.lstsq(X, r, rcond=None)[0]
    e = r - X @ bh; cov = (e @ e) / (n - 2) * np.linalg.inv(X.T @ X)
    span = n * H / 252.0
    return {"sharpe": r.mean() / r.std(ddof=1) * ANN, "cagr": eq[-1] ** (1 / span) - 1,
            "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "beta": bh[1], "alpha": bh[0], "t": bh[0] / np.sqrt(cov[0, 0])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ledger", required=True)
    a = ap.parse_args()
    path = Path(a.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    r, m, ds = _residual_book(path)
    n = len(r)
    years = ds.year.values
    # trailing realized vol (annualized) of the strategy's own prior-K returns
    sig = np.full(n, np.nan)
    for t in range(n):
        if t >= K:
            sig[t] = r[t - K:t].std(ddof=1) * ANN
    first_year = years[np.isfinite(sig)][0] if np.isfinite(sig).any() else years[0]
    target = np.nanmean(sig[(years == first_year) & np.isfinite(sig)])

    print(f"x03 vol-target sizing: {path.name}  ({n} periods, 2025 sealed)")
    print(f"σ_target (Option B, {first_year}-only mean strategy vol, fixed) = {target*100:.1f}%/yr,  K={K} periods\n")
    print(f"{'variant':16}{'annSh':>7}{'CAGR':>8}{'maxDD':>8}{'beta':>7}{'alpha%':>8}{'t(a)':>6}{'avgExp':>8}{'minExp':>8}")
    base = _metrics(r, m)
    print(f"{'x03 unscaled':16}{base['sharpe']:>+7.2f}{base['cagr']*100:>+7.1f}%{base['maxdd']*100:>+7.1f}%"
          f"{base['beta']:>+7.2f}{base['alpha']*100:>+8.2f}{base['t']:>+6.2f}{1.0:>8.2f}{1.0:>8.2f}")
    for L in (1.0, 1.5):
        exp = np.where(np.isfinite(sig), np.minimum(L, target / sig), 1.0)
        fin = np.maximum(0.0, exp - 1.0) * BORROW_APR * H / 252.0
        rs = exp * r - fin
        mt = _metrics(rs, m)
        print(f"{'voltarget L=' + str(L):16}{mt['sharpe']:>+7.2f}{mt['cagr']*100:>+7.1f}%{mt['maxdd']*100:>+7.1f}%"
              f"{mt['beta']:>+7.2f}{mt['alpha']*100:>+8.2f}{mt['t']:>+6.2f}{exp.mean():>8.2f}{exp.min():>8.2f}")
    print("\nBar: Sharpe ≥ unscaled AND maxDD ≥15% shallower; L=1.5 must beat L=1.0 to justify leverage.")


if __name__ == "__main__":
    main()
