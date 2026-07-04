#!/usr/bin/env python3
"""x03 residual (idiosyncratic) momentum — pre-registered test
(`multiday_x03_residmom_preregistration.md`). Ranks on CAPM-residual momentum (strips
the market beta IN the ranking) vs base 12-1 total-return momentum (x01), on the SAME
non-overlapping periods. Headline metric = BETA-ADJUSTED ALPHA (intercept + t of the
book's per-period returns regressed on SPY), because raw Sharpe/premium can be beta.

Computed entirely from the existing split-adjusted capture parquet (per-ticker daily
closes) + SPY — no re-fetch. Signal per rebalance d, per eligible name with ≥126 daily
returns in the 11-month formation [d-252, d-21]: regress r_i on r_SPY, resid ε; signal =
mean(ε)/std(ε). 2025 hard-sealed out. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet
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

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
FORM_LB = 252          # formation lookback (trading days)
SKIP = 21              # skip-month
MIN_OBS = 126


def _beta_adj_alpha(r, m):
    """OLS intercept (alpha) + t-stat of book returns r on market m."""
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    a, b = bhat[0], bhat[1]
    return a, a / np.sqrt(cov[0, 0]), b


def _metrics(r, m, H):
    r = np.asarray(r); m = np.asarray(m)
    n = len(r); ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    return {"n": n, "mean": r.mean(), "sharpe": r.mean() / sd * ann if sd > 0 else np.nan,
            "beta": beta, "alpha": a, "t_alpha": t_a,
            "maxdd": float((eq / peak - 1).min())}


def main() -> None:
    p = argparse.ArgumentParser(description="x03 residual momentum test")
    p.add_argument("--ledger", required=True)
    args = p.parse_args()
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()    # hard seal 2025

    # daily close matrix (dates × tickers) → daily returns
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dates = list(close.index)
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    # eligibility / fwd / base signal lookups
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")
    mom = df.pivot_table(index="trade_date", columns="ticker", values="mom_12_1", aggfunc="last")

    rebal = dates[::H]
    base_r, resid_r, mkt, kept = [], [], [], []
    for d in rebal:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi]                          # formation daily returns
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        ok_fwd = np.isfinite(fwd_row)
        Rw = win.values                                  # (Twin × Ntick)
        obs = np.isfinite(Rw).sum(axis=0)
        cand = elig_row & ok_fwd & (obs >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        # CAPM residual momentum, vectorized across candidate tickers
        Rc = Rw[:, cand]
        mask = np.isfinite(Rc)
        Rc0 = np.where(mask, Rc, 0.0)
        beta = (Rc0 * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        rm_mean = np.nanmean(resid, axis=0)
        rm_std = np.nanstd(resid, axis=0, ddof=1)
        resid_mom = np.where(rm_std > 0, rm_mean / rm_std, np.nan)
        fwd_c = fwd_row[cand]
        mom_c = mom.loc[d].values[cand]
        # base top-50 by mom_12_1, residual top-50 by resid_mom
        def topmean(score):
            order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
            return float(np.mean(fwd_c[order])) - COST
        if np.isfinite(mom_c).sum() < TOP_N or np.isfinite(resid_mom).sum() < TOP_N:
            continue
        base_r.append(topmean(mom_c)); resid_r.append(topmean(resid_mom))
        mkt.append(float(spy_fwd.loc[d])); kept.append(d)

    base_r, resid_r, mkt = map(np.array, (base_r, resid_r, mkt))
    fin = np.isfinite(base_r) & np.isfinite(resid_r) & np.isfinite(mkt)
    base_r, resid_r, mkt = base_r[fin], resid_r[fin], mkt[fin]
    n = len(base_r)
    print(f"Residual momentum test: {path.name}  ({n} non-overlapping periods, 2025 sealed)")
    if n < 10:
        print("too few periods"); return
    bm, rmet = _metrics(base_r, mkt, H), _metrics(resid_r, mkt, H)
    corr = np.corrcoef(base_r, resid_r)[0, 1]
    # DSR across the 2 pre-registered schemes
    srs = [s.mean() / s.std(ddof=1) for s in (base_r, resid_r)]
    sr_var = float(np.var(srs, ddof=1))
    dsr_b = deflated_sharpe_ratio(base_r, sr_var, 2.0)["dsr"]
    dsr_r = deflated_sharpe_ratio(resid_r, sr_var, 2.0)["dsr"]
    print(f"{'scheme':14}{'perPer%':>9}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'DSR':>7}")
    print(f"{'base 12-1':14}{bm['mean']*100:>+9.2f}{bm['sharpe']:>+7.2f}{bm['beta']:>+7.2f}"
          f"{bm['alpha']*100:>+8.2f}{bm['t_alpha']:>+7.2f}{bm['maxdd']*100:>+8.1f}{dsr_b:>7.3f}")
    print(f"{'residual':14}{rmet['mean']*100:>+9.2f}{rmet['sharpe']:>+7.2f}{rmet['beta']:>+7.2f}"
          f"{rmet['alpha']*100:>+8.2f}{rmet['t_alpha']:>+7.2f}{rmet['maxdd']*100:>+8.1f}{dsr_r:>7.3f}")
    print(f"\ncorr(base, residual) per-period returns = {corr:+.2f}")
    print(">>> x03 BAR: residual α-t materially > base α-t (base≈+0.31; want |t|>2), "
          "Sharpe ≥ base, DSR ≥ 0.95.")
    better = (rmet["t_alpha"] > bm["t_alpha"] and rmet["sharpe"] >= bm["sharpe"] and dsr_r >= 0.95
              and rmet["alpha"] > 0)
    print(f"    → {'PROMOTE-CANDIDATE' if better else 'does NOT clear the bar (residualization did not surface significant alpha)'}")


if __name__ == "__main__":
    main()
