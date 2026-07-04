#!/usr/bin/env python3
"""Power / robustness round for the H=20 momentum REVIEW (multiday_search.py found
WF 3/3 + PBO 0.48 + DSR 0.94 for liquid_50m+calm_vol). Pre-registered follow-on:
multiday_search_spec.md §run-matrix.

HONEST SCOPE (stated up front): overlapping / multi-phase sampling improves estimate
STABILITY but cannot create independent degrees of freedom — 3 years holds only
~38 independent 20-day periods, so the effective n for significance stays ~38. This
round therefore does NOT try to push DSR over 0.95 via more "periods" (that would be
the autocorrelation trap). It answers two honest questions:

  1. PHASE ROBUSTNESS — run the full non-overlapping search at ALL H rebalance-phase
     offsets (phase p uses days p, p+H, p+2H, …). Report, across phases: how often the
     WF passes, the DSR distribution, and which combo wins. If REVIEW only appears in
     a few phases it was phase-luck; if it holds across most, it's trustworthy.
  2. HAC SIGNIFICANCE — for the pre-specified winner, build the daily-formation
     OVERLAPPING cohort-return series (every day forms a top-N book held H days) and
     report the Newey-West (HAC, lag=H) t-stat with effective n ≈ n_days / H. This is
     the rigorous "is the Sharpe real on the full data" number, overlap-corrected.

Usage:
    python3 -m trading.lab.experiments.harness.multiday_power \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025.parquet \
        --horizon 20 --top-n 50 --cost-bps 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.experiments.harness import multiday_search as ms
from trading.lab.validation.cscv import pbo_from_matrix
from trading.lab.validation.deflated_sharpe import (
    deflated_sharpe_ratio, effective_n_trials,
)

WINNER = ("liquid_50m", "calm_vol")   # the H=20 REVIEW combo (pre-specified target)


def _newey_west_tstat(r: np.ndarray, lag: int) -> tuple[float, float, float]:
    """Newey-West HAC t-stat of the mean of an overlapping return series.
    Returns (mean, hac_se, tstat). lag = H-1 (Bartlett kernel)."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < lag + 2:
        return float("nan"), float("nan"), float("nan")
    mu = r.mean()
    e = r - mu
    gamma0 = float((e * e).mean())
    s = gamma0
    for k in range(1, lag + 1):
        w = 1.0 - k / (lag + 1.0)            # Bartlett weight
        cov = float((e[k:] * e[:-k]).mean())
        s += 2.0 * w * cov
    hac_se = np.sqrt(max(s, 1e-18) / n)       # se of the mean
    return mu, hac_se, (mu / hac_se if hac_se > 0 else float("nan"))


def _phase_search(df_all: pd.DataFrame, all_days, phase: int, H: int, top_n: int,
                  combos, pred, blocks: int) -> dict:
    """Full non-overlapping search on one rebalance phase."""
    rebal = set(all_days[phase::H])
    df = df_all[df_all["trade_date"].isin(rebal)].copy()
    if (df["year"] == fs.OOS_YEAR).any():
        df = df[df["year"] != fs.OOS_YEAR].copy()
    search = df[df["year"].isin(fs.SEARCH_YEARS)].copy()
    pooled = sorted(((c, fs.daily_portfolio(search, c, pred, top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    winner = pooled[0][0]
    wf = fs.walk_forward(df, combos, pred, top_n)
    perf = fs.build_perf_matrix(df, combos, pred, top_n)
    pbo = pbo_from_matrix(perf, n_blocks=blocks, higher_is_better=True)
    daily_sr = [perf[:, j].mean() / perf[:, j].std(ddof=1)
                for j in range(perf.shape[1]) if perf[:, j].std(ddof=1) > 0]
    sr_var = float(np.var(daily_sr, ddof=1)) if len(daily_sr) > 1 else 0.0
    n_eff = effective_n_trials(perf)
    dsr = deflated_sharpe_ratio(perf[:, combos.index(winner)], sr_var, n_eff)
    return {"phase": phase, "winner": winner, "wf_pass": wf["wf_pass"],
            "pos_folds": wf["positive_folds"], "pbo": pbo["pbo"],
            "dsr": dsr["dsr"], "winner_is_review_combo": winner == WINNER}


def main() -> None:
    p = argparse.ArgumentParser(description="Power/robustness round for the H=20 momentum REVIEW")
    p.add_argument("--ledger", required=True)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--cost-bps", type=float, default=10.0)
    p.add_argument("--blocks", type=int, default=12)
    args = p.parse_args()
    H = args.horizon

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    fwd = f"fwd_{H}"
    df = df[df["eligible"] & df[fwd].notna()].copy()
    df["realized_r"] = df[fwd].astype(float) - args.cost_bps / 10000.0
    df["score"] = df["mom_12_1"]
    df["year"] = df["trade_date"].dt.year
    df["filled"] = True
    all_days = sorted(df["trade_date"].unique())
    combos = ms.enumerate_combos(2)
    pred = {n: ms._predicate_mask(df, n) for n in ms.GRID}

    print(f"Power round: {path.name}, H={H}d, top_n={args.top_n}, cost={args.cost_bps:.0f}bps")
    print(f"Pre-specified REVIEW combo: {ms._fmt(WINNER)}\n")

    # ── 1. PHASE ROBUSTNESS ──────────────────────────────────────────────────
    print(f"=== 1. PHASE ROBUSTNESS — full search at all {H} rebalance offsets ===")
    res = [_phase_search(df, all_days, ph, H, args.top_n, combos, pred, args.blocks)
           for ph in range(H)]
    wf_pass = sum(r["wf_pass"] for r in res)
    review_win = sum(r["winner_is_review_combo"] for r in res)
    dsrs = np.array([r["dsr"] for r in res if np.isfinite(r["dsr"])])
    pbos = np.array([r["pbo"] for r in res if np.isfinite(r["pbo"])])
    print(f"  phases evaluated: {len(res)}")
    print(f"  WF PASS in {wf_pass}/{len(res)} phases")
    print(f"  winner == {ms._fmt(WINNER)} in {review_win}/{len(res)} phases")
    print(f"  DSR across phases: min {dsrs.min():.2f}  median {np.median(dsrs):.2f}  "
          f"max {dsrs.max():.2f}  (#≥0.95: {(dsrs>=0.95).sum()})")
    print(f"  PBO across phases: min {pbos.min():.2f}  median {np.median(pbos):.2f}  "
          f"max {pbos.max():.2f}  (#<0.5: {(pbos<0.5).sum()})")
    print("  per-phase: " + " ".join(
        f"{'P' if r['wf_pass'] else '.'}" for r in res) + "  (P=WF pass)")

    # ── 2. HAC SIGNIFICANCE of the pre-specified winner (overlapping daily) ───
    print(f"\n=== 2. HAC SIGNIFICANCE — daily-formation overlapping cohorts, {ms._fmt(WINNER)} ===")
    srch = df[df["year"].isin(fs.SEARCH_YEARS)].copy()
    mask = pd.Series(True, index=srch.index)
    for nm in WINNER:
        mask &= pred[nm].reindex(srch.index).fillna(False)
    book = srch[mask]
    # each day forms top-N by score; cohort return = mean net fwd_H of that book
    cohort = (book.sort_values("score", ascending=False)
                  .groupby("trade_date").head(args.top_n)
                  .groupby("trade_date")["realized_r"].mean().sort_index())
    r = cohort.values
    n = len(r)
    mean, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    ann = float(np.sqrt(252.0 / H))
    sharpe_ann = mean / sd * ann if sd > 0 else float("nan")
    mu, hac_se, t_hac = _newey_west_tstat(r, lag=H - 1)
    n_eff = n / H
    print(f"  daily cohorts: {n}  (effective independent periods ≈ n/H = {n_eff:.0f})")
    print(f"  per-cohort mean net R = {mean*100:+.3f}%   std = {sd*100:.3f}%   "
          f"annualized Sharpe = {sharpe_ann:+.2f}")
    print(f"  Newey-West (lag {H-1}) t-stat of the mean = {t_hac:+.2f}  "
          f"(naive t = {mean/(sd/np.sqrt(n)):+.2f}; HAC corrects the H-day overlap)")
    print(f"  → significant at |t|>1.96? {'YES' if abs(t_hac) > 1.96 else 'NO'}")

    # ── verdict ──────────────────────────────────────────────────────────────
    print("\n>>> POWER-ROUND READOUT")
    phase_robust = wf_pass >= 0.6 * len(res) and review_win >= 0.4 * len(res)
    print(f"  phase-robust (WF passes in ≥60% of phases AND review combo wins ≥40%): "
          f"{'YES' if phase_robust else 'NO'} ({wf_pass}/{len(res)} WF, {review_win}/{len(res)} combo)")
    print(f"  HAC-significant: {'YES' if abs(t_hac) > 1.96 else 'NO'} (t={t_hac:+.2f})")
    print(f"  DSR ceiling: median {np.median(dsrs):.2f} on n_eff≈{n_eff:.0f} — "
          f"{'clears' if np.median(dsrs)>=0.95 else 'does NOT clear'} 0.95 on 3yr of monthly data.")
    print("  Interpretation: if phase-robust + HAC-significant but DSR<0.95, the edge "
          "is REAL but the 3-year sample is too short to clear the demanding selection-"
          "bias gate. Honest path to PROMOTE = MORE history (pre-2022) or the higher-"
          "Sharpe long/short version — NOT finer slicing of these 3 years.")


if __name__ == "__main__":
    main()
