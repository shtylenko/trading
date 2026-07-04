#!/usr/bin/env python3
"""Stage-0 triage for a long-only multi-day signal that COMPLEMENTS momentum — the
project goal is a portfolio smoother than any single strategy (CLAUDE.md). Momentum
(top-50 12-1) is real but modest with intrinsic crash risk (2021–22). We want a
long-only, daily-bar signal whose good periods are momentum's BAD periods → low/neg
correlation, positive in 2021–22, and an improved COMBINED (50/50) Sharpe.

Offline on the existing combined capture (`_capture_multiday_2017_2025.parquet`); no
new data, no engine, no shorting. H=20 non-overlapping, 10 bps cost. 2025 stays sealed
(uses 2017–2024 only here; pre-2022 is survivorship-optimistic — flagged).

For each candidate long book it reports: standalone ann Sharpe, per-year returns,
correlation of its period returns with the momentum book, and the 50/50-combined
ann Sharpe (the smoothness test). A good complement: decent standalone + LOW/NEG
corr with momentum + POSITIVE in 2021–22 + lifts the combined Sharpe.

Candidate long books (all from captured daily features):
  momentum   : top-50 by mom_12_1            (the reference)
  low_vol    : bottom-50 by vol_20d          (low-volatility anomaly, defensive)
  st_reversal: bottom-50 by rev_1m           (biggest 1-month losers — reversal)
  near_low   : bottom-50 by prox_52w         (furthest below 52w high — contrarian)
  short_mom  : top-50 by mom_3_1             (3-month momentum — faster)

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_complement_triage \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet
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

OOS_YEAR = 2025
H = 20
TOP_N = 50
COST = 10.0 / 10000.0
ANN = float(np.sqrt(252.0 / H))

# (column, ascending?) — ascending=True ⇒ take the SMALLEST (bottom) values.
BOOKS = {
    "momentum":    ("mom_12_1", False),
    "low_vol":     ("vol_20d", True),
    "st_reversal": ("rev_1m", True),
    "near_low":    ("prox_52w", True),
    "short_mom":   ("mom_3_1", False),
}


def _book_series(df: pd.DataFrame, col: str, ascending: bool, rebal: list) -> pd.Series:
    """Per-rebalance net return of a top/bottom-50 equal-weight long book."""
    sub = df[df["trade_date"].isin(rebal)].dropna(subset=[col, "fwd_20"])
    picks = sub.sort_values(col, ascending=ascending).groupby("trade_date").head(TOP_N)
    return picks.groupby("trade_date")["fwd_20"].mean().sort_index() - COST


def _stats(s: pd.Series) -> dict:
    n = len(s)
    mean, sd = float(s.mean()), float(s.std(ddof=1))
    return {"n": n, "mean": mean, "sharpe": (mean / sd * ANN) if sd > 0 else float("nan"),
            "by_year": {int(y): float(v) for y, v in (s.groupby(s.index.year).mean()).items()}}


def main() -> None:
    p = argparse.ArgumentParser(description="Stage-0 complement-to-momentum triage")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet")
    args = p.parse_args()
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df[df["eligible"] & (df["trade_date"].dt.year < OOS_YEAR) & df["fwd_20"].notna()].copy()
    all_days = sorted(df["trade_date"].unique())
    rebal = all_days[::H]
    print(f"Complement triage: {path.name}, 2017–2024 (2025 sealed), H={H}, top/bottom-{TOP_N}, "
          f"{len(rebal)} rebalances. Pre-2022 survivorship-optimistic.\n")

    series = {name: _book_series(df, col, asc, rebal) for name, (col, asc) in BOOKS.items()}
    mom = series["momentum"]
    mom_bad_years = [y for y, v in _stats(mom)["by_year"].items() if v <= 0]
    print(f"Momentum book bad years (mean ≤ 0): {mom_bad_years}\n")

    hdr = f"  {'book':12} {'Sharpe':>7} {'corr_mom':>9} {'combo50_Sharpe':>14}  by-year mean%"
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    rows = []
    for name, s in series.items():
        st = _stats(s)
        aligned = pd.concat([mom, s], axis=1, join="inner").dropna()
        corr = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])) if len(aligned) > 2 else float("nan")
        combo = (aligned.iloc[:, 0] + aligned.iloc[:, 1]) / 2.0
        cst = _stats(combo)
        by = " ".join(f"{y}:{v*100:+.1f}" for y, v in st["by_year"].items())
        flag = ""
        if name != "momentum":
            helps_bad = all(st["by_year"].get(y, 0) > 0 for y in mom_bad_years) if mom_bad_years else False
            flag = ("  <-- diversifies" if (corr < 0.5 and cst["sharpe"] > _stats(mom)["sharpe"])
                    else ("  (+in mom's bad yrs)" if helps_bad else ""))
        print(f"  {name:12} {st['sharpe']:+7.2f} {corr:+9.2f} {cst['sharpe']:+14.2f}  {by}{flag}")
        rows.append((name, st, corr, cst))

    print("\n  Read: a good long-only complement has LOW/NEG corr_mom, is POSITIVE in "
          f"momentum's bad years {mom_bad_years}, and lifts combo50_Sharpe above momentum's "
          f"standalone ({_stats(mom)['sharpe']:+.2f}). Standalone edge matters less than the "
          "diversification. Survivorship-optimistic pre-2022 → treat levels as upper bounds; "
          "the CORRELATION structure is the robust takeaway. Next: lock a search on the winner.")


if __name__ == "__main__":
    main()
