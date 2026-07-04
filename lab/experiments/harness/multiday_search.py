#!/usr/bin/env python3
"""Multi-day cross-sectional momentum search — does conditioning the top-N 12-1
momentum book produce a robust net edge? Consumes the capture (capture_multiday.py)
and reuses the TRUSTED scoring machinery from feature_search.py verbatim (daily-
portfolio IR objective, leave-one-year-out walk-forward, PBO, Deflated Sharpe); only
the grid is momentum-specific. Pre-registered: validation/multiday_search_spec.md.

Structure: rank eligible names each rebalance by mom_12_1, hold top-N equal-weight H
trading days, NON-OVERLAPPING (independent periods). Cost charged per held name per
rebalance. Regime overlay (SPY>200d) optional as a fixed capital overlay. 2025 SEALED.

Usage:
    python3 -m trading.lab.experiments.harness.multiday_search \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025.parquet \
        --horizon 5 --top-n 50 --cost-bps 10
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

# ── PRE-REGISTERED grid (LOCKED) — see multiday_search_spec.md ────────────────
GRID: dict[str, tuple[str, float]] = {
    "liquid_50m":       ("ge", 50_000_000.0),   # dollar_vol_20d >= $50M
    "price_min_10":     ("ge", float(np.log(10.0))),  # log_close >= ln(10)
    "calm_vol":         ("le", 0.04),            # vol_20d <= 4%/day
    "confirm_6_1":      ("ge", 0.0),             # mom_6_1 >= 0
    "confirm_3_1":      ("ge", 0.0),             # mom_3_1 >= 0
    "not_overextended": ("le", 0.20),            # rev_1m <= +20%
    "mom_floor":        ("ge", 0.0),             # mom_12_1 >= 0
}
PREDICATE_FEATURE = {
    "liquid_50m": "dollar_vol_20d", "price_min_10": "log_close", "calm_vol": "vol_20d",
    "confirm_6_1": "mom_6_1", "confirm_3_1": "mom_3_1", "not_overextended": "rev_1m",
    "mom_floor": "mom_12_1",
}


def _predicate_mask(df: pd.DataFrame, name: str) -> pd.Series:
    op, thr = GRID[name]
    col = df[PREDICATE_FEATURE[name]]
    return {"ge": col >= thr, "le": col <= thr, "eq": col == thr}[op]


def enumerate_combos(k: int) -> list[tuple[str, ...]]:
    names = list(GRID)
    combos: list[tuple[str, ...]] = [()]
    for size in range(1, k + 1):
        for c in itertools.combinations(names, size):
            feats = [PREDICATE_FEATURE[n] for n in c]
            if len(set(feats)) < len(feats):   # no two predicates on the same feature
                continue
            combos.append(c)
    return combos


def _fmt(combo) -> str:
    return "+".join(combo) or "(top-N momentum, unconditioned)"


def main() -> None:
    p = argparse.ArgumentParser(description="Multi-day momentum search (cost-aware)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--horizon", type=int, default=5, help="hold/rebalance horizon (trading days)")
    p.add_argument("--top-n", type=int, default=50, help="names held per rebalance")
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--cost-bps", type=float, default=10.0, help="round-trip cost per held name per rebalance")
    p.add_argument("--regime-overlay", action="store_true")
    p.add_argument("--blocks", type=int, default=12)
    p.add_argument("--all-pre-oos-years", action="store_true",
                   help="set SEARCH_YEARS to ALL years < OOS_YEAR in the ledger (for the "
                        "extended-history decisive test → N-fold leave-one-year-out).")
    args = p.parse_args()

    H = args.horizon
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    if args.all_pre_oos_years:
        yrs = sorted(int(y) for y in df["trade_date"].dt.year.unique() if int(y) < fs.OOS_YEAR)
        fs.SEARCH_YEARS = yrs
        print(f"[extended] SEARCH_YEARS set to {yrs} ({len(yrs)}-fold LOO walk-forward).")
    fwd = f"fwd_{H}"
    if fwd not in df.columns:
        raise SystemExit(f"ledger has no {fwd} column (captured horizons: "
                         f"{[c for c in df.columns if c.startswith('fwd_')]})")

    df = df[df["eligible"] & df[fwd].notna()].copy()

    # NON-OVERLAPPING rebalance dates: every H trading days across the eligible grid.
    all_days = sorted(df["trade_date"].unique())
    rebal = set(all_days[::H])
    df = df[df["trade_date"].isin(rebal)].copy()

    # outcome = forward-H return minus round-trip cost (per held name per rebalance)
    df["realized_r"] = df[fwd].astype(float) - args.cost_bps / 10000.0
    df["score"] = df["mom_12_1"]   # rank by 12-1 momentum
    df["year"] = df["trade_date"].dt.year
    df["filled"] = True

    overlay = ""
    if args.regime_overlay:
        before = len(df)
        df = df[df["spy_above_200d"] == 1.0].copy()
        overlay = f" | regime overlay ON (SPY>200d): {len(df):,}/{before:,} name-periods"

    if (df["year"] == fs.OOS_YEAR).any():
        df = df[df["year"] != fs.OOS_YEAR].copy()
    search = df[df["year"].isin(fs.SEARCH_YEARS)].copy()
    n_rebal = search["trade_date"].nunique()

    combos = enumerate_combos(args.k)
    pred = {n: _predicate_mask(df, n) for n in GRID}
    ann = float(np.sqrt(252.0 / H))   # honest per-period annualization for display
    print(f"Multi-day ledger {path.name}: H={H}d, {n_rebal} non-overlapping rebalances "
          f"(2022–2024; 2025 sealed), top_n={args.top_n}, cost={args.cost_bps:.0f}bps"
          f"{overlay}")
    print(f"{len(combos)} combos. Ranking score=mom_12_1. (display annualization "
          f"√(252/{H})={ann:.2f}; gates are annualization-invariant.)\n")

    base = fs.daily_portfolio(search, (), pred, args.top_n)
    print(f"Baseline (top-{args.top_n} momentum, NET): {base['trades']:,} name-periods, "
          f"sumR={base['sum_r']*100:+.1f}% perPeriod tstat={base['tstat']:+.2f}")

    pooled = sorted(((c, fs.daily_portfolio(search, c, pred, args.top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    print("\nTop combos by pooled 2022–2024 info ratio (NET, descriptive):")
    for c, m in pooled[:8]:
        print(f"  {_fmt(c):46} sumR={m['sum_r']*100:+6.1f}% n={m['trades']:5d} "
              f"tstat={m['tstat']:+.2f} worstQ={m['worst_qtr_r']*100:+.1f}%")

    wf = fs.walk_forward(df, combos, pred, args.top_n)
    print("\n=== LEAVE-ONE-YEAR-OUT WALK-FORWARD (arbiter, NET) ===")
    for fo in wf["folds"]:
        t = fo["test"]
        print(f"  hold {fo['held_year']}: pick [{_fmt(tuple(fo['selected']))}] → "
              f"sumR={t['sum_r']*100:+.1f}% n={t['trades']} tstat={t['tstat']:+.2f}")
    print(f"  aggregate OOS sumR(net)={wf['agg_oos_sum_r']*100:+.1f}%  positive folds="
          f"{wf['positive_folds']}/{wf['n_folds']}  pick-stable={wf['pick_stable']}")
    print(f"  WF verdict: {'PASS' if wf['wf_pass'] else 'FAIL'}")

    perf = fs.build_perf_matrix(df, combos, pred, args.top_n)
    pbo = pbo_from_matrix(perf, n_blocks=args.blocks, higher_is_better=True)
    print(f"\n=== PBO (CSCV + embargo) ===  PBO={pbo['pbo']:.3f} over {pbo['n_splits']} splits")

    daily_sr = [perf[:, j].mean() / perf[:, j].std(ddof=1)
                for j in range(perf.shape[1]) if perf[:, j].std(ddof=1) > 0]
    sr_var = float(np.var(daily_sr, ddof=1)) if len(daily_sr) > 1 else 0.0
    n_eff = effective_n_trials(perf)
    dsr = deflated_sharpe_ratio(perf[:, combos.index(pooled[0][0])], sr_var, n_eff)
    print(f"\n=== Deflated Sharpe (selection-bias gate) ===")
    print(f"  winner [{_fmt(pooled[0][0])}]: DSR={dsr['dsr']:.3f}  "
          f"(per-period SR={dsr['sr_observed']:+.3f}, ann {dsr['sr_observed']*ann:+.2f}; "
          f"hurdle {dsr['sr_hurdle']:+.3f}; eff trials={n_eff:.1f}/{len(combos)}; n={dsr['n_obs']})")

    wf_ok, pbo_ok = wf["wf_pass"], pbo["pbo"] < 0.5
    dsr_ok = (dsr["dsr"] is not None) and (dsr["dsr"] >= fs.DSR_GATE)
    if wf_ok and pbo_ok and dsr_ok:
        verdict = "PROMOTE-CANDIDATE → sealed-OOS test (+ multi-day engine cross-check)"
    elif wf_ok and pbo_ok:
        verdict = f"REVIEW — path-robust but DSR {dsr['dsr']:.2f} < {fs.DSR_GATE}"
    else:
        verdict = "NO ROBUST EDGE (net of cost)"
    print(f"\n>>> MULTI-DAY SEARCH VERDICT: {verdict}")
    print(f"    gates: WF={'pass' if wf_ok else 'fail'}  PBO={pbo['pbo']:.2f}"
          f"{'<0.5' if pbo_ok else '≥0.5'}  DSR={dsr['dsr']:.2f}{'≥' if dsr_ok else '<'}{fs.DSR_GATE}"
          f"  @ H={H}d cost={args.cost_bps:.0f}bps")


if __name__ == "__main__":
    main()
