#!/usr/bin/env python3
"""EXPLORATORY: residual-momentum SIGNAL-DEFINITION robustness (+ cadence check).

Peer reviewer (2026-06-22) challenged the single choice we never stress-tested:
why score on mean(ε)/std(ε) — the "residual Sharpe / information ratio" — rather than
a plain cumulative residual return, a residual t-stat, or a compounded residual alpha?
The denominator rewards CONSISTENCY but (a) may discard the most violent genuine
winners and (b) adds a second layer of estimation noise (unstable std(ε) on thin
history). Conversely it is the form Blitz-Huij-Martens use.

This is the RIGHT kind of test: it runs entirely on the existing capture ledgers (no
new data) and the valuable outcome is the AGREEMENT VERDICT, not a new winner — if the
four definitions rank similarly and post similar beta-adjusted alpha, confidence in the
design choice goes UP; if they diverge sharply, the edge is sensitive to an arbitrary
knob and that is worth knowing before the 2027 seal.

Four scores over the formation window [d-252, d-21], ε = r_i - β_i·r_SPY:
  sharpe : mean(ε) / std(ε)              <- the live x03 score (information ratio)
  sum    : Σ ε                            <- cumulative residual return (obs-weighted)
  tstat  : mean(ε)/std(ε) · sqrt(n_obs)   <- residual t-stat
  cum    : Π(1+ε) − 1                     <- compounded residual alpha

For each score we form the top_n equal-weight book, hold H days, and report the
beta-adjusted alpha (OLS intercept of book vs SPY) + its t-stat + gross Sharpe + maxDD.
We also report the mean per-period Spearman rank-correlation of each alt score vs the
sharpe baseline (the "do they agree" number). Then we repeat the whole thing at H in
{20, 30, 40} as the cadence-fragility check (#4): an edge that survives only at exactly
20 days is fragile. Gross of cost (turnover ≈ equal across definitions; cost is already
established non-binding here). 2025 hard-sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom_scoredef \
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

TOP_N = 50
FORM_LB = 252
SKIP = 21
MIN_OBS = 126
SCORES = ("sharpe", "sum", "tstat", "cum")


def _beta_adj_alpha(r, m):
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _stats(r, m, H):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    sh = r.mean() / sd * ann if sd > 0 else np.nan
    return sh, beta, a, t_a, float((eq / peak - 1).min())


def _spearman(a, b):
    """Rank correlation of two finite vectors."""
    ra = pd.Series(a).rank().values
    rb = pd.Series(b).rank().values
    ra = ra - ra.mean(); rb = rb - rb.mean()
    d = np.sqrt((ra @ ra) * (rb @ rb))
    return float((ra @ rb) / d) if d > 0 else np.nan


def run(close, rets, spy_ret, spy_close, elig, cols, dates, H, top_n):
    spy_fwd = (spy_close.shift(-H) / spy_close - 1.0).reindex(close.index)
    books = {s: ([], []) for s in SCORES}   # score -> (book_returns, market_returns)
    rankcorr = {s: [] for s in SCORES}
    for d in dates[::H]:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS or di + H >= len(dates):
            continue
        mk = float(spy_fwd.loc[d])
        if not np.isfinite(mk):
            continue
        win = rets.iloc[lo:hi]
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        # forward return computed directly from the close pivot (cadence-agnostic)
        fwd_row = (close.iloc[di + H].values / close.iloc[di].values - 1.0)
        cand = elig_row & np.isfinite(fwd_row) & (np.isfinite(win.values).sum(axis=0) >= MIN_OBS)
        if cand.sum() < top_n:
            continue
        Rc = win.values[:, cand]; mask = np.isfinite(Rc)
        beta = (np.where(mask, Rc, 0.0) * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        nobs = mask.sum(axis=0)
        mean_e = np.nanmean(resid, axis=0)
        std_e = np.nanstd(resid, axis=0, ddof=1)
        sharpe = mean_e / std_e
        scores = {
            "sharpe": sharpe,
            "sum": np.nansum(resid, axis=0),
            "tstat": sharpe * np.sqrt(nobs),
            "cum": np.nanprod(np.where(mask, 1.0 + resid, 1.0), axis=0) - 1.0,
        }
        fwd_cand = fwd_row[cand]
        base = scores["sharpe"]
        for s in SCORES:
            sc = scores[s]
            good = np.isfinite(sc) & np.isfinite(fwd_cand)
            if good.sum() < top_n:
                continue
            sel = np.argsort(-sc[good])[:top_n]
            br, mr = books[s]
            br.append(float(np.mean(fwd_cand[good][sel])))
            mr.append(mk)
            if s != "sharpe":
                g2 = good & np.isfinite(base)
                rankcorr[s].append(_spearman(base[g2], sc[g2]))
    return books, rankcorr


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    p.add_argument("--top-n", type=int, default=TOP_N)
    args = p.parse_args()
    top_n = args.top_n
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()

    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dates = list(close.index)
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_close = spy["close"].reindex(close.index).ffill()
    spy_ret = spy_close.pct_change()
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    cols = np.array(close.columns)

    print(f"Residual-momentum score-definition robustness: {path.name}  (top_n={top_n}, 2025 sealed)\n")
    for H in (20, 30, 40):
        books, rankcorr = run(close, rets, spy_ret, spy_close, elig, cols, dates, H, top_n)
        n = len(books["sharpe"][0])
        cad = "  <- x03 live cadence" if H == 20 else ""
        print(f"H={H} ({n} periods){cad}")
        print(f"{'score':>8}{'Sharpe':>8}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'ρ_vs_sharpe':>13}")
        for s in SCORES:
            br, mr = books[s]
            if len(br) < 3:
                print(f"{s:>8}{'  (insufficient periods)':>20}")
                continue
            sh, beta, a, t_a, dd = _stats(br, mr, H)
            rho = "—" if s == "sharpe" else f"{np.nanmean(rankcorr[s]):+.2f}"
            print(f"{s:>8}{sh:>+8.2f}{beta:>+7.2f}{a*100:>+8.2f}{t_a:>+7.2f}{dd*100:>+8.1f}{rho:>13}")
        print()
    print(">>> Read: if the four scores post similar alpha/Sharpe AND ρ_vs_sharpe is high")
    print("    (~0.8+), the design choice is robust -> confidence UP. If 'sharpe' is a lone")
    print("    outlier, the edge leans on an arbitrary denominator. Cadence: an edge that")
    print("    survives only at H=20 (dies at 30/40) is fragile.")


if __name__ == "__main__":
    main()
