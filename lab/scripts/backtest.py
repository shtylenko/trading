#!/usr/bin/env python3
"""Run a strategy_lab backtest from the command line.

Usage:
    PYTHONPATH=engine python3 -m trading.lab.scripts.backtest \\
        --release o02 --testset eval_q2_2024_sample

    # Single-date ad-hoc run:
    python3 -m trading.lab.scripts.backtest \\
        --release o01 --date 2024-04-01 --tickers AAPL,MSFT

    # Resume an interrupted run:
    python3 -m trading.lab.scripts.backtest \\
        --resume run_o02_smoke_q2_2024_sp500_20240601_120000_abc123
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.runner.pipeline import run_backtest_for_date, run_backtest_for_testset
from trading.lab.runner.swing_pipeline import run_swing_backtest_for_testset, is_swing_release
from trading.lab.core.models import ExecutionConfig
from trading.lab.storage.duckdb import init_db
from trading.lab.strategies import list_releases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a strategy_lab backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available releases: " + ", ".join(list_releases()),
    )
    parser.add_argument("--release", "-r", help="Release ID (e.g. o02, d01); not needed with --resume")
    parser.add_argument("--testset", "-t", help="Testset name (for multi-day backtest)")
    parser.add_argument("--date", "-d", help="Single trade date (YYYY-MM-DD)")
    parser.add_argument("--tickers", help="Comma-separated tickers for ad-hoc runs")
    parser.add_argument("--resume", help="Resume an interrupted run by run_id")
    parser.add_argument("--candidate-limit", type=int, default=None)
    parser.add_argument("--force-data", action="store_true", help="Bypass cache, re-fetch from providers")
    parser.add_argument("--max-failed-sessions", type=int, default=10)
    parser.add_argument("--no-prefetch", action="store_true", help="Skip the bulk data prefetch pass before the day loop")
    parser.add_argument("--prefetch-workers", type=int, default=8, help="Parallel fetch workers during prefetch (default 8)")
    parser.add_argument("--list", action="store_true", help="List available releases and exit")
    parser.add_argument("--allow-oos", action="store_true",
                        help="Override the out-of-sample guardrail (run an OOS testset "
                             "before the release has cleared in-sample). Use sparingly.")

    args = parser.parse_args()

    if args.list:
        print("Available releases:")
        for r in list_releases():
            print(f"  {r}")
        return

    init_db()

    ec = ExecutionConfig()

    def guard_oos(release_id: str, testset_name: str) -> None:
        if args.allow_oos:
            return
        from trading.lab.storage.duckdb import connect
        from trading.lab.validation.funnel_eval import check_oos_prerequisite

        with connect(read_only=True) as conn:
            allowed, message = check_oos_prerequisite(conn, release_id, testset_name)
        if not allowed:
            parser.error(message)

    if args.resume:
        release_id, testset_name = args.release, args.testset
        if not release_id or not testset_name:
            from trading.lab.storage.duckdb import connect

            with connect(read_only=True) as conn:
                row = conn.execute(
                    "SELECT release_id, testset FROM runs WHERE run_id = ?",
                    [args.resume],
                ).fetchone()
            if row is None:
                parser.error(f"Run '{args.resume}' not found")
            release_id = release_id or row[0]
            testset_name = testset_name or row[1]
        guard_oos(release_id, testset_name)
        run_id = run_backtest_for_testset(
            release_id=release_id,
            testset_name=testset_name,
            execution_config=ec,
            candidate_limit=args.candidate_limit,
            force_data=args.force_data,
            resume_run_id=args.resume,
            max_failed_sessions=args.max_failed_sessions,
            prefetch=not args.no_prefetch,
            prefetch_workers=args.prefetch_workers,
        )
        print(f"\nResumed run: {run_id}")
    elif args.testset:
        if not args.release:
            parser.error("--release is required with --testset")
        guard_oos(args.release, args.testset)
        if is_swing_release(args.release):
            # Multi-day (cross-session) releases use the additive swing runner;
            # the intraday per-session path doesn't apply.
            run_id = run_swing_backtest_for_testset(
                release_id=args.release,
                testset_name=args.testset,
                execution_config=ec,
                force_data=args.force_data,
            )
        else:
            run_id = run_backtest_for_testset(
                release_id=args.release,
                testset_name=args.testset,
                execution_config=ec,
                candidate_limit=args.candidate_limit,
                force_data=args.force_data,
                max_failed_sessions=args.max_failed_sessions,
                prefetch=not args.no_prefetch,
                prefetch_workers=args.prefetch_workers,
            )
        print(f"\nRun completed: {run_id}")
    elif args.date:
        if not args.release:
            parser.error("--release is required with --date")
        trade_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        tickers = [t.strip().upper() for t in (args.tickers or "").split(",") if t.strip()] or None
        session_id = run_backtest_for_date(
            release_id=args.release,
            trade_date=trade_date,
            tickers=tickers,
            execution_config=ec,
            candidate_limit=args.candidate_limit,
            force_data=args.force_data,
        )
        print(f"\nSession completed: {session_id}")
    else:
        parser.error("One of --testset, --date, or --resume is required")


if __name__ == "__main__":
    main()
