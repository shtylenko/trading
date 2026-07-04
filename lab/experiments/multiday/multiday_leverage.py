#!/usr/bin/env python3
"""Leverage / position-sizing study for the validated equal-weight 12-1 momentum book.

NOT an alpha change — the signal is fixed (base x01 rule). This quantifies the pure
risk dial: for each gross exposure L, what CAGR do you gain and what max drawdown do
you take on, NET of a financing charge on the borrowed (L−1) fraction. Leverage does
not raise Sharpe (it slightly lowers it after financing); it buys return with risk.

Per non-overlapping rebalance: top-N by mom_12_1, equal weight, period return =
mean(fwd_H − cost). Leveraged period return = L·r − (L−1)·fin_per_period. Reports
CAGR, annualized vol, Sharpe, max drawdown, worst single period, and a crude
risk-of-ruin marker (the L at which the worst observed period breaches −50%).

2025 hard-sealed out. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_leverage \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet \
        --horizon 20 --top-n 50 --cost-bps 10 --borrow-apr 0.06
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

LEVELS = (1.0, 1.25, 1.5, 1.75, 2.0)


def _base_periods(df: pd.DataFrame, rebal_days, top_n: int) -> pd.Series:
    """Equal-weight top-N book return per rebalance day."""
    rows = {}
    for d in rebal_days:
        day = df[df["trade_date"] == d]
        b = day[day["eligible"] & day["mom_12_1"].notna()]
        if b.empty:
            continue
        book = b.sort_values("mom_12_1", ascending=False).head(top_n)
        rows[d] = float(book["realized_r"].astype(float).mean())
    return pd.Series(rows).sort_index()


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def _metrics(r: np.ndarray, H: int) -> dict:
    n = len(r)
    ann = float(np.sqrt(252.0 / H))
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    equity = np.cumprod(1.0 + r)
    span_years = n * H / 252.0
    cagr = equity[-1] ** (1.0 / span_years) - 1.0 if equity[-1] > 0 else -1.0
    return {"cagr": cagr, "ann_vol": sd * ann,
            "sharpe": (mean / sd * ann) if sd > 0 else float("nan"),
            "maxdd": _max_drawdown(equity), "worst": float(r.min()),
            "final_mult": float(equity[-1])}


def main() -> None:
    p = argparse.ArgumentParser(description="Leverage/sizing study for x01 momentum")
    p.add_argument("--ledger", required=True)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--cost-bps", type=float, default=10.0)
    p.add_argument("--borrow-apr", type=float, default=0.06,
                   help="annual financing rate charged on the borrowed (L−1) fraction")
    args = p.parse_args()
    H = args.horizon

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    fwd = f"fwd_{H}"
    df = df[df["eligible"] & df[fwd].notna()].copy()
    df["realized_r"] = df[fwd].astype(float) - args.cost_bps / 10000.0
    df["year"] = df["trade_date"].dt.year
    df = df[df["year"] != fs.OOS_YEAR].copy()             # hard seal 2025
    all_days = sorted(df["trade_date"].unique())
    years = sorted(df["year"].unique())
    base = _base_periods(df, all_days[0::H], args.top_n)
    r0 = base.to_numpy()
    fin_per_period = args.borrow_apr * H / 252.0          # financing per period per unit borrowed

    print(f"Leverage study: {path.name}, H={H}d, top_n={args.top_n}, cost={args.cost_bps:.0f}bps, "
          f"borrow={args.borrow_apr*100:.0f}% APR")
    print(f"years {years[0]}–{years[-1]} (2025 sealed), {len(r0)} non-overlapping periods\n")
    print(f"{'L':>5} {'CAGR':>8} {'annVol':>8} {'Sharpe':>7} {'maxDD':>8} {'worstPer':>9} {'×money':>8}")
    for L in LEVELS:
        rL = L * r0 - (L - 1.0) * fin_per_period
        m = _metrics(rL, H)
        print(f"{L:>5.2f} {m['cagr']*100:>+7.1f}% {m['ann_vol']*100:>7.1f}% {m['sharpe']:>+7.2f} "
              f"{m['maxdd']*100:>+7.1f}% {m['worst']*100:>+8.1f}% {m['final_mult']:>7.2f}x")
    # risk-of-ruin marker
    worst = float(r0.min())
    ruin_L = (-0.50 / worst) if worst < 0 else float("inf")
    print(f"\nWorst single period (L=1): {worst*100:+.1f}%  →  a single period breaches −50% at L ≈ {ruin_L:.2f}")
    print("Note: leverage does NOT raise Sharpe (financing lowers it slightly); it scales CAGR AND drawdown together. "
          "Sizing is a risk-tolerance choice, not an alpha improvement.")


if __name__ == "__main__":
    main()
