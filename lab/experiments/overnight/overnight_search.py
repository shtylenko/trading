#!/usr/bin/env python3
"""Overnight cross-sectional search — which subset of name-nights, held close→open,
has a robust multi-year edge AFTER costs? Consumes the overnight capture ledger
(scripts/capture_overnight.py) and reuses the TRUSTED scoring machinery from
scripts/feature_search.py verbatim (daily-portfolio info-ratio objective,
leave-one-year-out walk-forward, PBO via CSCV, Deflated Sharpe) — only the grid is
overnight-specific. Methodology: validation/EXPLORATION_PLAYBOOK.md.

Two overnight-specific elements, both pre-committed:
  - COST CHARGE: realized_r (the close→open return) has a round-trip cost
    subtracted on every held name-night (--cost-bps), so the entire pipeline —
    objective, WF, PBO, DSR — operates on NET return. The pre-registered minimum
    effect size is "survives a realistic cost", not "beats zero" (≥5 bps stocks).
  - REGIME OVERLAY (optional, --regime-overlay): hold the book ONLY on nights with
    SPY > its 200-day SMA, applied identically to ALL combos (a capital overlay,
    NOT a searched degree of freedom). The synthetic control showed day-level
    regime flags are best used this way, not as in-search admission predicates
    (they under-recover under the daily-IR objective). Gated-off nights = flat.

2025 is the SEALED OOS year (never read here — fs.OOS_YEAR). A search PASS only
nominates the combo for the pre-registered sealed-OOS test + an overnight-hold
engine cross-check; it is not a promotion.

Usage:
    python3 -m trading.lab.experiments.overnight.overnight_search \
        --ledger trading/lab/experiments/_data/_overnight_capture_stocks_2022_2025.parquet \
        --top-n 20 --cost-bps 5 --regime-overlay
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.validation.cscv import pbo_from_matrix
from trading.lab.validation.deflated_sharpe import (
    deflated_sharpe_ratio, effective_n_trials,
)

ANN = float(np.sqrt(252))

# ── PRE-REGISTERED overnight grid (LOCKED) — see overnight_search_spec.md ──────
# Thesis: short-term reversal (oversold names bounce overnight) on liquid, non-
# distressed names; turn-of-month calendar premium. One-sided cuts, coarse.
GRID: dict[str, tuple[str, float]] = {
    "rev_5d_oversold":   ("le", -0.03),       # ret_5d <= -3%  (5-day losers)
    "rev_rsi2_oversold": ("le", 10.0),        # rsi_2 <= 10    (Connors oversold)
    "weak_close_today":  ("le", -0.01),       # ret_intraday <= -1% (closed soft)
    "not_falling_knife": ("ge", -0.25),       # dist_52w_high >= -25% (not distressed)
    "liquid_20m":        ("ge", 20_000_000.),  # dollar_vol_20d >= $20M (cost-bearing)
    "price_min_10":      ("ge", np.log(10.0)),  # log_close >= ln(10)  (>= $10)
    "calm_vol":          ("le", 0.04),        # vol_20d <= 4% daily (avoid most volatile)
    "turn_of_month":     ("eq", 1.0),         # is_turn_of_month == 1
}
PREDICATE_FEATURE = {
    "rev_5d_oversold": "ret_5d", "rev_rsi2_oversold": "rsi_2",
    "weak_close_today": "ret_intraday", "not_falling_knife": "dist_52w_high",
    "liquid_20m": "dollar_vol_20d", "price_min_10": "log_close",
    "calm_vol": "vol_20d", "turn_of_month": "is_turn_of_month",
}
# Two reversal predicates target the same thesis on different features — allow them
# together (a confirmation pair), like the gap floor+ceiling band in feature_search.
ALLOWED_SAME_THESIS_PAIRS = {frozenset({"rev_5d_oversold", "rev_rsi2_oversold"})}


def _predicate_mask(df: pd.DataFrame, name: str) -> pd.Series:
    op, thr = GRID[name]
    col = df[PREDICATE_FEATURE[name]]
    if op == "ge":
        return col >= thr
    if op == "le":
        return col <= thr
    if op == "eq":
        return col == thr
    raise ValueError(op)


def enumerate_combos(k: int) -> list[tuple[str, ...]]:
    names = list(GRID)
    combos: list[tuple[str, ...]] = [()]
    for size in range(1, k + 1):
        for c in itertools.combinations(names, size):
            feats = [PREDICATE_FEATURE[n] for n in c]
            if len(set(feats)) < len(feats) and frozenset(c) not in ALLOWED_SAME_THESIS_PAIRS:
                continue
            combos.append(c)
    return combos


def _fmt(combo) -> str:
    return "+".join(combo) or "(all-names baseline)"


def main() -> None:
    p = argparse.ArgumentParser(description="Overnight cross-sectional search (cost-aware)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--top-n", type=int, default=20, help="names held per night")
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--cost-bps", type=float, default=5.0, help="round-trip cost per held name-night")
    p.add_argument("--regime-overlay", action="store_true",
                   help="hold only on SPY>200d nights (capital overlay, all combos)")
    p.add_argument("--blocks", type=int, default=16)
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["year"] = df["trade_date"].dt.year

    # cost charge → operate on NET return everywhere
    df["realized_r"] = df["realized_r"].astype(float) - args.cost_bps / 10000.0

    overlay = ""
    if args.regime_overlay:
        before = len(df)
        df = df[df["spy_above_200d"] == 1.0].copy()
        overlay = f" | regime overlay ON (SPY>200d): {len(df):,}/{before:,} name-nights held"

    if (df["year"] == fs.OOS_YEAR).any():
        df = df[df["year"] != fs.OOS_YEAR].copy()  # HARD seal
    search = df[df["year"].isin(fs.SEARCH_YEARS)].copy()

    combos = enumerate_combos(args.k)
    pred = {n: _predicate_mask(df, n) for n in GRID}
    print(f"Overnight ledger {path.name}: {len(search):,} search name-nights "
          f"(2025 sealed). {len(combos)} combos, top_n={args.top_n}, "
          f"cost={args.cost_bps:.0f}bps{overlay}")
    print("Objective: annualized daily-portfolio info ratio on NET close→open R. "
          "Arbiter: leave-one-year-out.\n")

    base = fs.daily_portfolio(search, (), pred, args.top_n)
    print(f"Baseline (all-names top-{args.top_n}, NET): {base['trades']:,} name-nights, "
          f"sumR(net)={base['sum_r']*100:+.1f}% IR={base['ir_raw']:+.2f}")

    pooled = sorted(((c, fs.daily_portfolio(search, c, pred, args.top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    print("\nTop combos by pooled 2022–2024 info ratio (NET, descriptive):")
    for c, m in pooled[:8]:
        print(f"  {_fmt(c):42} IR={m['ir_raw']:+.2f} sumR={m['sum_r']*100:+6.1f}% "
              f"n={m['trades']:5d} worstQ={m['worst_qtr_r']*100:+.1f}%")

    wf = fs.walk_forward(df, combos, pred, args.top_n)
    print("\n=== LEAVE-ONE-YEAR-OUT WALK-FORWARD (arbiter, NET) ===")
    for fo in wf["folds"]:
        t = fo["test"]
        print(f"  hold {fo['held_year']}: pick [{_fmt(tuple(fo['selected']))}] → "
              f"sumR={t['sum_r']*100:+.1f}% IR={t['ir_raw']:+.2f} n={t['trades']}")
    print(f"  aggregate OOS sumR(net)={wf['agg_oos_sum_r']*100:+.1f}%  positive folds="
          f"{wf['positive_folds']}/{wf['n_folds']}  pick-stable={wf['pick_stable']}")
    print(f"  WF verdict: {'PASS' if wf['wf_pass'] else 'FAIL'}")

    perf = fs.build_perf_matrix(df, combos, pred, args.top_n)
    pbo = pbo_from_matrix(perf, n_blocks=args.blocks, higher_is_better=True)
    print(f"\n=== PBO (CSCV + embargo) ===  PBO={pbo['pbo']:.3f} over {pbo['n_splits']} splits")

    daily_sr = []
    for j in range(perf.shape[1]):
        col = perf[:, j]
        sd = col.std(ddof=1)
        if sd > 0:
            daily_sr.append(col.mean() / sd)
    sr_var = float(np.var(daily_sr, ddof=1)) if len(daily_sr) > 1 else 0.0
    n_eff = effective_n_trials(perf)
    dsr = deflated_sharpe_ratio(perf[:, combos.index(pooled[0][0])], sr_var, n_eff)
    print(f"\n=== Deflated Sharpe (selection-bias gate) ===")
    print(f"  winner [{_fmt(pooled[0][0])}]: DSR={dsr['dsr']:.3f}  "
          f"(obs daily SR={dsr['sr_observed']:+.3f}, ann {dsr['sr_observed']*ANN:+.2f}; "
          f"hurdle {dsr['sr_hurdle']:+.3f}; eff trials={n_eff:.1f}/{len(combos)})")

    wf_ok, pbo_ok = wf["wf_pass"], pbo["pbo"] < 0.5
    dsr_ok = (dsr["dsr"] is not None) and (dsr["dsr"] >= fs.DSR_GATE)
    if wf_ok and pbo_ok and dsr_ok:
        verdict = "PROMOTE-CANDIDATE → sealed-OOS test (+ overnight engine cross-check)"
    elif wf_ok and pbo_ok:
        verdict = f"REVIEW — path-robust but DSR {dsr['dsr']:.2f} < {fs.DSR_GATE}"
    else:
        verdict = "NO ROBUST EDGE (net of cost)"
    print(f"\n>>> OVERNIGHT SEARCH VERDICT: {verdict}")
    print(f"    gates: WF={'pass' if wf_ok else 'fail'}  PBO={pbo['pbo']:.2f}"
          f"{'<0.5' if pbo_ok else '≥0.5'}  DSR={dsr['dsr']:.2f}{'≥' if dsr_ok else '<'}{fs.DSR_GATE}"
          f"  @ cost={args.cost_bps:.0f}bps")


if __name__ == "__main__":
    main()
