#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.storage.duckdb import connect, init_db


def fetch_report_rows(
    conn,
    *,
    testset: str | None = None,
    release: str | None = None,
    run_id: str | None = None,
    limit: int = 20,
):
    where = []
    params = []
    if testset:
        where.append("rm.testset = ?")
        params.append(testset)
    if release:
        where.append("rm.release_id = ?")
        params.append(release)
    if run_id:
        where.append("rm.run_id = ?")
        params.append(run_id)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    return conn.execute(
        f"""
        WITH ranked AS (
            SELECT
                rm.run_id, rm.testset, rm.release_id, rm.strategy_alias,
                rm.strategy_letter, rm.metric_scope, rm.trade_count, rm.wins,
                rm.losses, rm.win_rate, rm.profit_factor, rm.total_pnl_pct,
                rm.avg_pnl_pct, rm.best_trade_pct, rm.worst_trade_pct,
                rm.metrics_json,
                r.started_at, r.completed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY rm.release_id, COALESCE(rm.testset, ''), rm.metric_scope
                    ORDER BY r.started_at DESC, r.completed_at DESC, rm.run_id DESC
                ) AS recency_rank
            FROM release_metrics rm
            LEFT JOIN runs r ON r.run_id = rm.run_id
            {clause}
        )
        SELECT run_id, testset, release_id, strategy_alias, strategy_letter,
               metric_scope, trade_count, wins, losses, win_rate, profit_factor,
               total_pnl_pct, avg_pnl_pct, best_trade_pct, worst_trade_pct,
               metrics_json
        FROM ranked
        WHERE recency_rank = 1
        ORDER BY COALESCE(testset, ''), release_id, metric_scope
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description="Report strategy_lab results")
    parser.add_argument("--testset")
    parser.add_argument("--release")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    init_db()

    with connect() as conn:
        rows = fetch_report_rows(
            conn,
            testset=args.testset,
            release=args.release,
            run_id=args.run_id,
            limit=args.limit,
        )

        if not rows:
            print("No release metrics found. Run a backtest first.")
            return

        print("Strategy Lab Release Metrics")
        print("-" * 148)
        print(
            f"{'release':8s} {'testset':28s} {'trades':>6s} {'wins':>5s} {'loss':>5s} "
            f"{'strategy':24s} {'WR':>7s} {'PF':>7s} {'total':>10s} {'avg':>9s} {'best':>9s} {'worst':>9s} {'sumR':>7s} {'avgR':>7s} run_id"
        )
        print("-" * 148)
        for r in rows:
            metrics_json = {}
            try:
                import json
                metrics_json = json.loads(r[15] or "{}")
            except Exception:
                pass
            total_r = float(metrics_json.get("total_realized_r") or 0.0)
            avg_r = float(metrics_json.get("avg_realized_r") or 0.0)
            print(
                f"{r[2]:8s} {str(r[1] or '-'):28s} {int(r[6] or 0):6d} {int(r[7] or 0):5d} {int(r[8] or 0):5d} "
                f"{str(r[3] or '-'):24s} {float(r[9] or 0):6.1f}% {float(r[10] or 0):7.2f} {float(r[11] or 0):+9.3f}% "
                f"{float(r[12] or 0):+8.3f}% {float(r[13] or 0):+8.3f}% {float(r[14] or 0):+8.3f}% "
                f"{total_r:+7.2f} {avg_r:+7.2f} {r[0]}"
            )


if __name__ == "__main__":
    main()
