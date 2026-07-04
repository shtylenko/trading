#!/usr/bin/env python3
"""SEALED 2026-H1 EARLY PARTIAL confirmation — multi-day momentum. ONE SHOT; criteria
pre-registered in validation/multiday_2026h1_preregistration.md (locked BEFORE this ran).
Mirrors multiday_oos_test.py (the 2025 first confirmation) but on the 2026-H1 window and
SPLIT-ADJUSTED data, with the pre-registered DISTRUST OVERLAY: in this suspected-artifact
window the cross-sectional premium GATES a PASS (a positive return without a momentum tilt
is downgraded to REVIEW). ~5 effective periods → weak by design; the verdict is binding.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_2026h1_test \
        --ledger trading/lab/experiments/_data/_capture_multiday_2026h1_split.parquet
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

YEAR = 2026
H = 20
TOP_N = 50
COST = 10.0 / 10000.0


def main() -> None:
    p = argparse.ArgumentParser(description="Sealed 2026-H1 early partial confirmation")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2026h1_split.parquet")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df[(df["trade_date"].dt.year == YEAR) & df["eligible"] & df[f"fwd_{H}"].notna()].copy()
    print(f"SEALED 2026-H1 read (ONE SHOT). {len(df):,} eligible name-days, "
          f"{df['trade_date'].nunique()} dates "
          f"({df['trade_date'].min().date()} → {df['trade_date'].max().date()}).")

    df["net"] = df[f"fwd_{H}"].astype(float) - COST
    book = (df.sort_values("mom_12_1", ascending=False)
              .groupby("trade_date").head(TOP_N))
    cohort = book.groupby("trade_date")["net"].mean().sort_index()
    univ = df.groupby("trade_date")["fwd_20"].mean().sort_index()

    r = cohort.values
    n = len(r)
    mean, sd = float(np.mean(r)), float(np.std(r, ddof=1)) if n > 1 else 0.0
    ann = float(np.sqrt(252.0 / H))
    sharpe = mean / sd * ann if sd > 0 else float("nan")
    _, _, t_hac = _newey_west_tstat(r, lag=H - 1)
    n_eff = n / H
    prem = float(cohort.mean() - univ.reindex(cohort.index).mean())
    d = df.copy()
    d["dec"] = d.groupby("trade_date")["mom_12_1"].transform(
        lambda s: pd.qcut(s, 10, labels=False, duplicates="drop") if s.nunique() >= 10 else np.nan)
    dec_mean = d.dropna(subset=["dec"]).groupby("dec")["fwd_20"].mean()
    mono = pd.Series(dec_mean.values).corr(pd.Series(dec_mean.index, dtype=float), method="spearman")

    print(f"\n--- PRIMARY (tradeability, net of cost) ---")
    print(f"  per-period net mean = {mean*100:+.3f}%   (positive? {'YES' if mean>0 else 'NO'})")
    print(f"  annualized Sharpe   = {sharpe:+.2f}   (>= 0.5? {'YES' if sharpe>=0.5 else 'NO'})")
    print(f"  daily cohorts n={n} (effective independent periods ≈ {n_eff:.0f} — VERY THIN)")
    print(f"\n--- DISTRUST OVERLAY (gating qualifier for 2026-H1) ---")
    print(f"  cross-sectional premium (top-50 net − universe gross) = {prem*100:+.3f}% "
          f"({'momentum tilt' if prem>0 else 'NO tilt → likely window artifact'})")
    print(f"\n--- COLOR (not gates) ---")
    print(f"  decile monotonicity (mom_12_1 vs fwd_20) = {mono:+.2f}")
    print(f"  Newey-West HAC t-stat (lag {H-1})         = {t_hac:+.2f} "
          f"(≈{n_eff:.0f} periods → expected weak, color only)")

    # pre-registered verdict mapping
    if mean <= 0:
        verdict = "FAIL (net return <= 0)"
    elif sharpe >= 0.5 and prem > 0:
        verdict = "CONFIRM (PASS-primary AND positive momentum premium)"
    elif sharpe >= 0.5 and prem <= 0:
        verdict = "REVIEW (PASS-primary but premium <= 0 → likely 2026-H1 artifact, downgraded)"
    else:
        verdict = "REVIEW (positive but Sharpe < 0.5)"
    print(f"\n>>> SEALED 2026-H1 VERDICT: {verdict}")
    print(f"    (binding per multiday_2026h1_preregistration.md; record in oos_spend_ledger.md)")
    print(f"    NOTE: ~{n_eff:.0f} effective periods → supportive/directional at most, NOT decisive.")


if __name__ == "__main__":
    main()
