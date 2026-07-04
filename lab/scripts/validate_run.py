#!/usr/bin/env python3
"""Statistical validation of a backtest run's R series.

Reports, per run_id:
  - permutation test: sign-flip the daily R series N times; p-value of the
    realized total R against the null of "no directional edge"
  - bootstrap CI for annualized R pace and daily R std
  - tail dependence: share of total R carried by the top-k trades, and
    total R with the top-k trades removed

Usage:
    python3 -m trading.lab.scripts.validate_run --run <run_id> [--iters 10000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.storage.duckdb import connect
from trading.lab.validation.run_stats import (
    TRADING_DAYS_PER_YEAR,
    bootstrap_ci,
    daily_r_series,
    permutation_pvalue,
    tail_stats,
)


def load_run(conn, run_id: str):
    row = conn.execute(
        "SELECT testset, release_id, completed_days, total_days FROM runs WHERE run_id = ?",
        [run_id],
    ).fetchone()
    if row is None:
        raise SystemExit(f"Run '{run_id}' not found")
    trades = conn.execute(
        """
        SELECT trade_date, realized_r FROM trades
        WHERE run_id = ? AND realized_r IS NOT NULL
        ORDER BY trade_date
        """,
        [run_id],
    ).fetchall()
    n_days = conn.execute(
        "SELECT COUNT(DISTINCT trade_date) FROM sessions WHERE run_id = ? AND status = 'completed'",
        [run_id],
    ).fetchone()[0]
    return row, trades, n_days


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a backtest run statistically")
    parser.add_argument("--run", required=True, action="append",
                        help="run_id to validate; repeat to pool several runs "
                             "into one combined daily-R series")
    parser.add_argument("--iters", type=int, default=10_000)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    metas, trades, n_days = [], [], 0
    per_run_daily = []
    with connect(read_only=True) as conn:
        for run_id in args.run:
            meta, run_trades, run_days = load_run(conn, run_id)
            metas.append((run_id, meta))
            trades.extend(run_trades)
            n_days += run_days
            # Build each run's daily-R series independently and concatenate.
            # Keying the pooled series on calendar date alone would merge two
            # runs that share a trade_date into one observation (and fabricate
            # zero-pad days to reach the summed day count), distorting the
            # variance, bootstrap CIs, and sign-flip p-value. Per-run series
            # keep overlapping dates as the distinct observations they are.
            per_run_daily.append(daily_r_series(run_trades, run_days))

    if not trades:
        raise SystemExit("Run has no trades with realized_r")
    (testset, release_id, completed, total) = metas[0][1]
    if len(metas) > 1:
        testset = f"pooled[{len(metas)} runs]"
        completed = total = n_days

    daily = np.concatenate(per_run_daily) if per_run_daily else daily_r_series(trades, n_days)
    sum_r = daily.sum()
    pace = daily.mean() * TRADING_DAYS_PER_YEAR
    sd = daily.std(ddof=1)
    pval = permutation_pvalue(daily, args.iters, rng)
    (pace_lo, pace_hi), (sd_lo, sd_hi) = bootstrap_ci(daily, args.iters, rng)
    _, top_sum, share, without = tail_stats(trades, args.top_k)

    print(f"Run:        {', '.join(args.run)}")
    print(f"Release:    {release_id}   Testset: {testset}   Days: {completed}/{total}")
    print(f"Trades:     {len(trades)}")
    print()
    print(f"Total R:            {sum_r:+.1f}R over {daily.size} days")
    print(f"Annualized pace:    {pace:+.1f}R/yr   (95% CI {pace_lo:+.1f} .. {pace_hi:+.1f})")
    print(f"Daily R std:        {sd:.2f}R        (95% CI {sd_lo:.2f} .. {sd_hi:.2f})")
    print(f"Permutation p:      {pval:.4f}   (sign-flip null, {args.iters} iters, one-sided)")
    print()
    print(f"Top-{args.top_k} trades:       {top_sum:+.1f}R = {share * 100:.0f}% of total")
    print(f"Total w/o top-{args.top_k}:    {without:+.1f}R")


if __name__ == "__main__":
    main()
