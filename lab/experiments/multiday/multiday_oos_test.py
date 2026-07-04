#!/usr/bin/env python3
"""SEALED-OOS confirmatory test — multi-day momentum on 2025. ONE SHOT, criteria
pre-registered in validation/multiday_oos_preregistration.md (read BEFORE this ran).
Reads 2025 exactly once; the printed verdict is binding.

Rule (pre-registered, nothing tuned to 2025): long the top-50 eligible names by
mom_12_1, equal weight, monthly (H=20) non-overlapping hold, 10 bps round-trip cost.
Metrics use the daily-formation overlapping cohort series (PHASE-INDEPENDENT — no
rebalance-phase cherry-pick); significance via Newey-West HAC.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_oos_test \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025.parquet
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

from trading.lab.experiments.harness.multiday_power import _newey_west_tstat

OOS_YEAR = 2025
H = 20
TOP_N = 50
COST = 10.0 / 10000.0


def main() -> None:
    p = argparse.ArgumentParser(description="Sealed-OOS 2025 test for multi-day momentum")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2022_2025.parquet")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df[(df["trade_date"].dt.year == OOS_YEAR) & df["eligible"] & df[f"fwd_{H}"].notna()].copy()
    print(f"SEALED-OOS 2025 read (ONE SHOT). {len(df):,} eligible name-days, "
          f"{df['trade_date'].nunique()} dates.")

    # daily-formation overlapping cohorts (phase-independent): each day, top-50 by mom_12_1
    df["net"] = df[f"fwd_{H}"].astype(float) - COST
    book = (df.sort_values("mom_12_1", ascending=False)
              .groupby("trade_date").head(TOP_N))
    cohort = book.groupby("trade_date")["net"].mean().sort_index()
    univ = df.groupby("trade_date")["fwd_20"].mean().sort_index()  # eligible-universe mean (gross)

    r = cohort.values
    n = len(r)
    mean, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    ann = float(np.sqrt(252.0 / H))
    sharpe = mean / sd * ann if sd > 0 else float("nan")
    _, _, t_hac = _newey_west_tstat(r, lag=H - 1)
    n_eff = n / H
    # cross-sectional premium: top-50 net mean − eligible-universe gross mean
    prem = float(cohort.mean() - univ.reindex(cohort.index).mean())
    # decile monotonicity in 2025
    d = df.copy()
    d["dec"] = d.groupby("trade_date")["mom_12_1"].transform(
        lambda s: pd.qcut(s, 10, labels=False, duplicates="drop") if s.nunique() >= 10 else np.nan)
    dec_mean = d.dropna(subset=["dec"]).groupby("dec")["fwd_20"].mean()
    mono = pd.Series(dec_mean.values).corr(pd.Series(dec_mean.index, dtype=float), method="spearman")

    print(f"\n--- PRIMARY (tradeability, net of cost) ---")
    print(f"  per-period net mean = {mean*100:+.3f}%   (positive? {'YES' if mean>0 else 'NO'})")
    print(f"  annualized Sharpe   = {sharpe:+.2f}   (>= 0.5? {'YES' if sharpe>=0.5 else 'NO'})")
    print(f"  daily cohorts n={n} (effective independent periods ≈ {n_eff:.0f})")
    print(f"\n--- SECONDARY (alpha confirmation / color) ---")
    print(f"  cross-sectional premium (top-50 net − universe gross) = {prem*100:+.3f}% "
          f"({'momentum tilt' if prem>0 else 'no tilt / pure beta'})")
    print(f"  decile monotonicity (mom_12_1 vs fwd_20)              = {mono:+.2f}")
    print(f"  Newey-West HAC t-stat (lag {H-1})                      = {t_hac:+.2f} "
          f"(one year ≈ {n_eff:.0f} periods → weak by design, color only)")

    if mean > 0 and sharpe >= 0.5:
        verdict = "PASS"
    elif mean > 0:
        verdict = "REVIEW (positive but Sharpe < 0.5)"
    else:
        verdict = "FAIL (net return <= 0)"
    print(f"\n>>> SEALED-OOS 2025 VERDICT: {verdict}")
    print(f"    (binding per multiday_oos_preregistration.md; record in oos_spend_ledger.md)")
    print(f"    alpha qualifier: cross-sectional premium {'POSITIVE (genuine momentum)' if prem>0 else 'ZERO/NEG (beta-driven)'}.")


if __name__ == "__main__":
    main()
