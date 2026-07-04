from __future__ import annotations

from datetime import datetime

from trading.lab.scripts.report import fetch_report_rows
from trading.lab.storage.duckdb import connect, init_db


def _insert_run(conn, run_id: str, release_id: str, testset: str, started_at: str) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            run_id, run_type, testset, release_id, strategy_letter, strategy_alias,
            status, started_at, engine_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            "backtest",
            testset,
            release_id,
            release_id[0],
            "stocks_in_play_orb" if release_id.startswith("o") else "post_gap_opening_drive",
            "completed",
            datetime.fromisoformat(started_at),
            "test",
        ],
    )


def _insert_metrics(conn, run_id: str, release_id: str, testset: str, total_pnl_pct: float) -> None:
    conn.execute(
        """
        INSERT INTO release_metrics (
            run_id, testset, release_id, strategy_letter, strategy_alias, metric_scope,
            trade_count, wins, losses, win_rate, gross_win_pct, gross_loss_pct,
            profit_factor, total_pnl_pct, avg_pnl_pct, best_trade_pct,
            worst_trade_pct, metrics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            testset,
            release_id,
            release_id[0],
            "stocks_in_play_orb" if release_id.startswith("o") else "post_gap_opening_drive",
            "overall",
            10,
            6,
            4,
            60.0,
            5.0,
            -3.0,
            1.5,
            total_pnl_pct,
            total_pnl_pct / 10.0,
            3.0,
            -2.0,
            "{}",
        ],
    )


def test_report_rows_keep_latest_run_per_release_testset(tmp_path):
    db_path = tmp_path / "strategy_lab_report.duckdb"
    init_db(db_path)

    with connect(db_path) as conn:
        _insert_run(conn, "run_old_o01", "o01", "smoke", "2024-04-01T09:30:00")
        _insert_metrics(conn, "run_old_o01", "o01", "smoke", 100.0)
        _insert_run(conn, "run_new_o01", "o01", "smoke", "2024-04-02T09:30:00")
        _insert_metrics(conn, "run_new_o01", "o01", "smoke", -5.0)
        _insert_run(conn, "run_d01", "d01", "smoke", "2024-04-01T09:30:00")
        _insert_metrics(conn, "run_d01", "d01", "smoke", 7.0)

        rows = fetch_report_rows(conn, testset="smoke", limit=10)

    by_release = {row[2]: row for row in rows}
    assert set(by_release) == {"d01", "o01"}
    assert by_release["o01"][0] == "run_new_o01"
    assert by_release["o01"][11] == -5.0
    assert by_release["d01"][0] == "run_d01"
