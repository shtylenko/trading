#!/usr/bin/env python3
"""EXPLORATORY: absolute resid-mom score threshold vs relative top-50.

Question: x03 holds the relative top-50 by residual-momentum score
(mean(eps)/std(eps)). Some of those 50 have weak/low scores. Would requiring an
ABSOLUTE minimum score instead improve profitability?

This sweeps absolute cutoffs on the residual-momentum score. At each rebalance it
holds EW *all* candidates with score >= cutoff (no fixed count); if none qualify it
sits in CASH for that period (return 0, no cost). It reports, per cutoff:
  held   = avg # names held when invested
  %cash  = fraction of periods fully in cash (the regime/timing piece)
  alpha + t(alpha) = market-orthogonal edge (the thing we actually care about)

WARNING: this is a diagnostic, NOT a validated scheme. Sweeping cutoffs and reading
the best one back is selection bias. The honest questions are (a) does ANY cutoff
beat top-50 on ALPHA-t (not raw Sharpe, which can be 2022-cash beta-timing), and
(b) does the gain come from the cash-dodge (%cash high) or from quality (held~50,
low %cash). 2025 hard-sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom_absthresh \
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

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
FORM_LB = 252
SKIP = 21
MIN_OBS = 126


def _beta_adj_alpha(r, m):
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    a, b = bhat[0], bhat[1]
    return a, a / np.sqrt(cov[0, 0]), b


def _row(label, r, m, held, cash_frac):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    sh = r.mean() / sd * ann if sd > 0 else np.nan
    maxdd = float((eq / peak - 1).min())
    print(f"{label:>12}{held:>7.1f}{cash_frac*100:>7.0f}{r.mean()*100:>+9.2f}"
          f"{sh:>+7.2f}{beta:>+7.2f}{a*100:>+8.2f}{t_a:>+7.2f}{maxdd*100:>+8.1f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    args = p.parse_args()
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
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")

    rebal = dates[::H]
    # collect per-period: residual-mom score array + fwd array (candidates), market fwd
    periods = []
    for d in rebal:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi]
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        ok_fwd = np.isfinite(fwd_row)
        Rw = win.values
        obs = np.isfinite(Rw).sum(axis=0)
        cand = elig_row & ok_fwd & (obs >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        Rc = Rw[:, cand]
        mask = np.isfinite(Rc)
        Rc0 = np.where(mask, Rc, 0.0)
        beta = (Rc0 * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        rm = np.nanmean(resid, axis=0)
        rs = np.nanstd(resid, axis=0, ddof=1)
        score = np.where(rs > 0, rm / rs, np.nan)
        fwd_c = fwd_row[cand]
        good = np.isfinite(score) & np.isfinite(fwd_c)
        mk = float(spy_fwd.loc[d])
        if good.sum() < TOP_N or not np.isfinite(mk):
            continue
        periods.append((score[good], fwd_c[good], mk))

    n = len(periods)
    print(f"Absolute-threshold sweep: {path.name}  ({n} periods, 2025 sealed)\n")

    # distribution of scores actually selected by top-50 (to anchor thresholds)
    sel_scores = []
    for sc, fw, mk in periods:
        order = np.argsort(-sc)[:TOP_N]
        sel_scores.append(sc[order])
    sel_scores = np.concatenate(sel_scores)
    qs = [0, 10, 25, 50, 75, 90]
    print("residual score of top-50 picks (pooled) percentiles:")
    print("  " + "  ".join(f"p{q}={np.percentile(sel_scores, q):+.3f}" for q in qs))
    print()

    print(f"{'scheme':>12}{'held':>7}{'%cash':>7}{'perPer%':>9}{'annSh':>7}"
          f"{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}")

    # baselines: relative top-N (the control for "is it absolute, or just fewer names?")
    for tn in (50, 35, 25, 15, 10, 5):
        br, bm = [], []
        for sc, fw, mk in periods:
            order = np.argsort(-sc)[:tn]
            br.append(float(np.mean(fw[order])) - COST); bm.append(mk)
        _row(f"top{tn} (rel)", br, bm, float(tn), 0.0)
    print()

    # absolute cutoffs, anchored on the selected-score distribution
    cutoffs = [np.percentile(sel_scores, q) for q in (0, 10, 25, 50, 75, 90)]
    cut_lbls = [f"abs>={c:+.3f}" for c in cutoffs]
    for c, lbl in zip(cutoffs, cut_lbls):
        rr, mm, held_list, cash = [], [], [], 0
        for sc, fw, mk in periods:
            pick = sc >= c
            if pick.sum() == 0:
                rr.append(0.0); mm.append(mk); cash += 1; continue
            rr.append(float(np.mean(fw[pick])) - COST); mm.append(mk)
            held_list.append(int(pick.sum()))
        held = float(np.mean(held_list)) if held_list else 0.0
        _row(lbl, rr, mm, held, cash / n)

    print("\n>>> Read: does any abs cutoff beat top50 on t(α) (not just Sharpe)?")
    print("    If the winners have high %cash, the 'edge' is 2022 cash-timing (a beta")
    print("    overlay we've already killed), NOT stock quality. Quality would show as")
    print("    held~50 / low %cash with higher t(α). Selection bias: best cutoff is cherry-picked.")


if __name__ == "__main__":
    main()
