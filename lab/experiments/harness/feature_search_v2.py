#!/usr/bin/env python3
"""Deeper feature-search DIAGNOSTICS — the companion to the canonical
`feature_search.py`. Runs ONLY on the search window 2022–2024; the sealed 2025
OOS is never read here.

The canonical search (`feature_search.py`) now uses the corrected daily-portfolio
info-ratio objective + leave-one-year-out arbiter + consistent PBO, and imports
its scoring helpers (`daily_portfolio`, `_apply_roster`) — this script reuses them
so there is ONE implementation. What this script adds beyond the canonical run:

  1. FOLD-1 ALL-COMBOS table — show EVERY combo's 2023 result when training on
     2022 alone, to demonstrate the round-1 selection artifact (was the thesis
     combo positive but merely not selected?).
  2. SUBSTITUTION (roster) comparison for the thesis combo — 'replace' (filter
     then top-N, promotes bench names) vs 'remove' (top-N then filter, can only
     subtract). A large gap = the edge is substitution luck, not the predicate.

Usage:
    python3 -m trading.lab.experiments.harness.feature_search_v2 \
        --ledger trading/lab/experiments/_data/_capture_2022_2025.parquet \
        --top-n 10
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

from trading.lab.experiments.harness.feature_search import (
    GRID, OOS_YEAR, SEARCH_YEARS, _combo_mask, _predicate_mask, _fmt, apply_top_n,
    daily_portfolio, enumerate_combos, objective,
)
from trading.lab.validation.cscv import pbo_from_matrix

THESIS_COMBO = ("gap_floor_3", "rvol_min_1_5")  # the live thread from round 1


def main() -> None:
    p = argparse.ArgumentParser(description="Phase-A search diagnostics (2022–2024 only)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--blocks", type=int, default=16)
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["year"] = df["trade_date"].dt.year
    if (df["year"] == OOS_YEAR).any():
        df = df[df["year"] != OOS_YEAR].copy()  # HARD guard: never touch OOS here
    search = df[df["year"].isin(SEARCH_YEARS)].copy()

    combos = enumerate_combos(2)
    pred = {n: _predicate_mask(df, n) for n in GRID}
    print(f"Ledger {path.name}: {len(search)} rows, search years {SEARCH_YEARS} "
          f"(OOS {OOS_YEAR} excluded). {len(combos)} combos, top_n={args.top_n}")
    print("Objective: annualized daily-portfolio info ratio (mean/std of daily R).\n")

    # ── DIAGNOSTIC 1: fold-1 all-combos OOS (train 2022 → look at ALL on 2023) ──
    print("=" * 78)
    print("DIAGNOSTIC 1 — Fold 1: train 2022, ALL 46 combos' 2023 OOS (not just the pick)")
    print("=" * 78)
    tr22 = search[search.year == 2022]; te23 = search[search.year == 2023]
    rows = []
    for c in combos:
        m_tr = daily_portfolio(tr22, c, pred, args.top_n)
        m_te = daily_portfolio(te23, c, pred, args.top_n)
        rows.append((c, m_tr, m_te))
    # what 2022 (old mean-R) and 2022 (new IR) each select:
    elig22 = [(c, tr, te) for c, tr, te in rows if tr["eligible"]]
    pick_ir = max(elig22, key=lambda x: x[1]["ir"])
    print(f"2022-selected by NEW IR objective: [{_fmt(pick_ir[0])}] "
          f"→ 2023 OOS sumR={pick_ir[2]['sum_r']:+.1f} IR={pick_ir[2]['ir_raw']:+.2f}")
    # rank all combos by their 2023 OOS sum_r, mark the thesis combo
    by_oos = sorted(rows, key=lambda x: x[2]["sum_r"], reverse=True)
    print("\nTop 8 combos by 2023 OOS sumR:")
    for c, tr, te in by_oos[:8]:
        tag = "  <<< THESIS" if c == THESIS_COMBO else ""
        print(f"  {_fmt(c):40} 2023 sumR={te['sum_r']:+7.1f} IR={te['ir_raw']:+.2f} "
              f"n={te['trades']}{tag}")
    thesis_rank = next(i for i, (c, _, _) in enumerate(by_oos, 1) if c == THESIS_COMBO)
    tc = next((c, tr, te) for c, tr, te in rows if c == THESIS_COMBO)
    print(f"\nTHESIS combo [{_fmt(THESIS_COMBO)}]: 2022 train IR={tc[1]['ir_raw']:+.2f}, "
          f"2023 OOS sumR={tc[2]['sum_r']:+.1f} IR={tc[2]['ir_raw']:+.2f} "
          f"→ ranked #{thesis_rank}/{len(by_oos)} on 2023 OOS")
    print("INTERPRETATION: if the thesis combo is POSITIVE in 2023 but ranked below the\n"
          "2022-pick, the round-1 FAIL was a selection-procedure artifact, not absence of edge.")

    # ── DIAGNOSTIC 2: per-year fixed thesis combo + substitution effect ──
    print("\n" + "=" * 78)
    print("DIAGNOSTIC 2 — Fixed thesis combo per year + substitution (roster modes)")
    print("=" * 78)
    print(f"{'year':6} {'mode':8} {'trades':>7} {'sumR':>8} {'IR':>7} {'tstat':>7} "
          f"{'win%':>6} {'worstQ':>8} {'tail':>6}")
    for yr in SEARCH_YEARS + ["ALL"]:
        win = search if yr == "ALL" else search[search.year == yr]
        for mode in ("replace", "remove"):
            m = daily_portfolio(win, THESIS_COMBO, pred, args.top_n, mode=mode)
            ts = m['top_k_share']
            print(f"{str(yr):6} {mode:8} {m['trades']:>7} {m['sum_r']:>+8.1f} "
                  f"{m['ir_raw']:>+7.2f} {m['tstat']:>+7.2f} {m['win_rate']:>6.1f} "
                  f"{m['worst_qtr_r']:>+8.1f} {('-' if ts is None else f'{ts:.2f}'):>6}")
    print("'replace' = deployment (filter then top-N); 'remove' = isolate filter (top-N then filter).\n"
          "Large replace-vs-remove gap ⇒ the combo's edge is substitution (bench luck), not the predicate.")

    # ── DIAGNOSTIC 3: pooled + leave-one-year-out selection ──
    print("=" * 78)
    print("DIAGNOSTIC 3 — Pooled & leave-one-year-out selection (IR objective)")
    print("=" * 78)
    pooled = sorted(((c, daily_portfolio(search, c, pred, args.top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    print("Pooled 2022–2024 selection (in-sample identity of the global winner):")
    for c, m in pooled[:5]:
        print(f"  {_fmt(c):40} IR={m['ir_raw']:+.2f} sumR={m['sum_r']:+.1f} "
              f"n={m['trades']} worstQ={m['worst_qtr_r']:+.1f}")
    print(f"\nLeave-one-year-out (train on the other two, test on the held-out year):")
    loo_sumr = 0.0; loo_pos = 0
    for held in SEARCH_YEARS:
        train = search[search.year != held]; test = search[search.year == held]
        elig = [(c, daily_portfolio(train, c, pred, args.top_n)) for c in combos]
        elig = [(c, m) for c, m in elig if m["eligible"]]
        pick = max(elig, key=lambda x: x[1]["ir"])[0]
        tm = daily_portfolio(test, pick, pred, args.top_n)
        loo_sumr += tm["sum_r"]; loo_pos += int(tm["sum_r"] > 0)
        print(f"  hold {held}: pick [{_fmt(pick)}] → test sumR={tm['sum_r']:+.1f} "
              f"IR={tm['ir_raw']:+.2f} n={tm['trades']}")
    print(f"  LOO aggregate sumR={loo_sumr:+.1f}, positive folds={loo_pos}/{len(SEARCH_YEARS)}")

    # ── DIAGNOSTIC 4: PBO on the daily-portfolio metric (consistent with selection) ──
    print("\n" + "=" * 78)
    print("DIAGNOSTIC 4 — PBO via CSCV on the DAILY-PORTFOLIO metric (matches objective)")
    print("=" * 78)
    all_days = sorted(search["trade_date"].dt.normalize().unique())
    day_ix = {d: i for i, d in enumerate(all_days)}
    perf = np.zeros((len(all_days), len(combos)))
    for j, c in enumerate(combos):
        book = apply_top_n(search[_combo_mask(search, c, pred)], args.top_n)
        book = book[book["filled"] == True]  # noqa: E712
        if book.empty:
            continue
        for d, v in book.groupby(book["trade_date"].dt.normalize())["realized_r"].sum().items():
            perf[day_ix[d], j] = float(v)
    pbo = pbo_from_matrix(perf, n_blocks=args.blocks, higher_is_better=True)
    print(f"  PBO={pbo['pbo']:.3f} over {pbo['n_splits']} splits (S={args.blocks}); "
          f"IS-best also OOS-best rate={pbo['is_best_also_oos_best_rate']:.2f}")
    print("  (Same daily-R matrix the IR objective uses — removes the round-1 metric mismatch.)")

    print("\n" + "=" * 78)
    print("PHASE-A READOUT (no 2025 spent). Decision inputs:")
    print(f"  • thesis combo 2023-OOS rank #{thesis_rank}, "
          f"{'POSITIVE' if tc[2]['sum_r'] > 0 else 'NEGATIVE'} ({tc[2]['sum_r']:+.1f}R)")
    print(f"  • LOO aggregate {loo_sumr:+.1f}R, {loo_pos}/3 folds positive")
    print(f"  • PBO (consistent metric) {pbo['pbo']:.3f}")
    print("=" * 78)


if __name__ == "__main__":
    main()
