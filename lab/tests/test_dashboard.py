from __future__ import annotations

from datetime import datetime

from trading.lab.scripts.dashboard import (
    get_run_detail,
    get_testset_detail,
    get_testsets,
)
from trading.lab.storage.duckdb import connect, init_db


def test_dashboard_testset_backtest_run_flow(tmp_path):
    db_path = tmp_path / "strategy_lab_dashboard.duckdb"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, testset, release_id, strategy_letter,
                strategy_alias, status, started_at, engine_version,
                completed_days, total_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "run_old",
                "backtest",
                "smoke",
                "o01",
                "o",
                "stocks_in_play_orb",
                "completed",
                datetime(2024, 4, 1, 12, 0),
                "test",
                1,
                1,
            ],
        )
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, testset, release_id, strategy_letter,
                strategy_alias, status, started_at, engine_version,
                completed_days, total_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "run_new",
                "backtest",
                "smoke",
                "o01",
                "o",
                "stocks_in_play_orb",
                "completed",
                datetime(2024, 4, 2, 12, 0),
                "test",
                1,
                1,
            ],
        )
        for run_id, pnl in [("run_old", 8.0), ("run_new", -1.5)]:
            conn.execute(
                """
                INSERT INTO release_metrics (
                    run_id, testset, release_id, strategy_letter, strategy_alias,
                    metric_scope, trade_count, wins, losses, win_rate,
                    gross_win_pct, gross_loss_pct, profit_factor, total_pnl_pct,
                    avg_pnl_pct, best_trade_pct, worst_trade_pct, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    "smoke",
                    "o01",
                    "o",
                    "stocks_in_play_orb",
                    "overall",
                    1,
                    1 if pnl > 0 else 0,
                    0 if pnl > 0 else 1,
                    100.0 if pnl > 0 else 0.0,
                    max(pnl, 0.0),
                    abs(min(pnl, 0.0)),
                    2.0,
                    pnl,
                    pnl,
                    pnl,
                    pnl,
                    "{}",
                ],
            )
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, run_id, trade_date, testset, release_id,
                strategy_letter, strategy_alias, status, started_at,
                ticker_count, candidate_count, signal_count, trade_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "s1",
                "run_new",
                "2024-04-02",
                "smoke",
                "o01",
                "o",
                "stocks_in_play_orb",
                "completed",
                datetime(2024, 4, 2, 12, 0),
                1,
                1,
                1,
                1,
            ],
        )
        conn.execute(
            """
            INSERT INTO trades (
                trade_id, signal_id, session_id, run_id, trade_date, testset,
                ticker, release_id, strategy_letter, strategy_alias, setup_type,
                direction, entry_time, entry_price, exit_time, exit_price,
                exit_reason, pnl_pct, gross_pnl_pct, realized_r, fees_pct,
                slippage_pct, context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "t1",
                "sig1",
                "s1",
                "run_new",
                "2024-04-02",
                "smoke",
                "AAPL",
                "o01",
                "o",
                "stocks_in_play_orb",
                "opening_range_breakout",
                "long",
                datetime(2024, 4, 2, 10, 0),
                100.0,
                datetime(2024, 4, 2, 11, 0),
                98.5,
                "STOP_LOSS",
                -1.5,
                -1.4,
                -1.0,
                0.1,
                0.04,
                "{}",
            ],
        )

        testsets = get_testsets(conn)
        detail = get_testset_detail(conn, "smoke")
        run = get_run_detail(conn, "run_new")

    assert testsets["testsets"][0]["name"] == "smoke"
    assert detail["backtests"][0]["run_id"] == "run_new"
    assert detail["backtests"][0]["total_pnl_pct"] == -1.5
    assert detail["backtests"][0]["equity_curve"] == [
        {"date": "2024-04-02", "pnl": -1.5, "cum_r": -1.0}
    ]
    assert run["run"]["run_id"] == "run_new"
    assert run["trades"][0]["ticker"] == "AAPL"
    assert run["equity_curve"] == [
        {
            "date": "2024-04-02",
            "daily_pnl": -1.5,
            "pnl": -1.5,
            "daily_r": -1.0,
            "cum_r": -1.0,
            "equity": 99.0,  # 100 * (1 + 0.01 * -1R)
            "trades": 1,
        }
    ]
    assert run["max_drawdown_pct"] == -1.0


def test_kill_process_on_port(monkeypatch):
    import signal
    from trading.lab.scripts.dashboard import kill_process_on_port

    called_pids = []
    
    def fake_kill(pid, sig):
        called_pids.append((pid, sig))
        if sig == 0:
            # Simulate process termination on the second check
            if len([x for x in called_pids if x[0] == pid and x[1] == 0]) > 1:
                raise OSError("No such process")

    monkeypatch.setattr("os.kill", fake_kill)
    monkeypatch.setattr("os.getpid", lambda: 9999)

    # Mock subprocess to return a target PID and our own PID (which should be ignored)
    def fake_check_output(args, **kwargs):
        assert "lsof" in args
        return "1234\n9999\n"

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    kill_process_on_port(8890)

    # PID 9999 is ourselves and should be ignored.
    # PID 1234 should be SIGTERM'd, then polled with sig=0 twice before simulated termination.
    assert (1234, signal.SIGTERM) in called_pids
    assert (1234, 0) in called_pids
    assert (9999, signal.SIGTERM) not in called_pids


def test_dashboard_trade_detail_endpoint(tmp_path, monkeypatch):
    import pandas as pd
    from datetime import datetime, date
    from trading.lab.scripts.dashboard import get_trade_detail
    from trading.lab.storage.duckdb import connect, init_db

    db_path = tmp_path / "strategy_lab_dashboard_trade.duckdb"
    init_db(db_path)

    with connect(db_path) as conn:
        # Insert a run
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, testset, release_id, strategy_letter,
                strategy_alias, status, started_at, engine_version,
                completed_days, total_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "run_test",
                "backtest",
                "smoke",
                "o01",
                "o",
                "stocks_in_play_orb",
                "completed",
                datetime(2024, 4, 2, 12, 0),
                "v1.0.0",
                1,
                1,
            ],
        )
        # Insert a signal
        conn.execute(
            """
            INSERT INTO signals (
                signal_id, session_id, trade_date, ticker, release_id,
                strategy_letter, strategy_alias, setup_type, signal_time,
                entry_trigger, stop_price, target_price, risk_per_share
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "sig_test",
                "s_test",
                date(2024, 4, 2),
                "AAPL",
                "o01",
                "o",
                "stocks_in_play_orb",
                "opening_range_breakout",
                datetime(2024, 4, 2, 9, 35),
                100.0,
                98.0,
                102.0,
                2.0,
            ],
        )
        # Insert a trade
        conn.execute(
            """
            INSERT INTO trades (
                trade_id, signal_id, session_id, run_id, trade_date, testset,
                ticker, release_id, strategy_letter, strategy_alias, setup_type,
                direction, entry_time, entry_price, exit_time, exit_price,
                exit_reason, pnl_pct, gross_pnl_pct, fees_pct, slippage_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "trd_test",
                "sig_test",
                "s_test",
                "run_test",
                date(2024, 4, 2),
                "smoke",
                "AAPL",
                "o01",
                "o",
                "stocks_in_play_orb",
                "opening_range_breakout",
                "long",
                datetime(2024, 4, 2, 9, 36),
                100.0,
                datetime(2024, 4, 2, 10, 0),
                101.5,
                "EXIT_TARGET",
                1.5,
                1.6,
                0.05,
                0.05,
            ],
        )

        # Mock fetch_bars to return a dummy DataFrame
        index = pd.date_range("2024-04-02 09:30:00", "2024-04-02 16:00:00", freq="1min", tz="America/New_York")
        df = pd.DataFrame({
            "open": [100.0] * len(index),
            "high": [101.0] * len(index),
            "low": [99.0] * len(index),
            "close": [100.0] * len(index),
            "volume": [1000] * len(index)
        }, index=index)

        monkeypatch.setattr("trading.marketdata.fetch_bars", lambda *args, **kwargs: df)

        trade_detail = get_trade_detail(conn, "trd_test")

    assert trade_detail["trade_id"] == "trd_test"
    assert trade_detail["ticker"] == "AAPL"
    assert trade_detail["engine_version"] == "v1.0.0"
    assert trade_detail["signal_stop_price"] == 98.0
    assert trade_detail["signal_target_price"] == 102.0
    assert len(trade_detail["bars"]) == len(index)
    assert trade_detail["bars"][0]["open"] == 100.0
    assert len(trade_detail["vwap"]) == len(index)




def test_annotate_freshness_matching_signature_is_fresh(monkeypatch):
    from trading.lab.scripts import dashboard

    monkeypatch.setattr(dashboard, "current_code_signature", lambda rid: "abc123")
    rows = [{"release_id": "o01", "code_signature": "abc123"}]
    dashboard._annotate_freshness(rows)
    assert rows[0]["code_fresh"] is True
    assert rows[0]["current_signature"] == "abc123"


def test_annotate_freshness_mismatch_is_stale(monkeypatch):
    from trading.lab.scripts import dashboard

    monkeypatch.setattr(dashboard, "current_code_signature", lambda rid: "newhash")
    rows = [{"release_id": "o01", "code_signature": "oldhash"}]
    dashboard._annotate_freshness(rows)
    assert rows[0]["code_fresh"] is False
    assert rows[0]["current_signature"] == "newhash"


def test_annotate_freshness_missing_signature_is_unknown(monkeypatch):
    from trading.lab.scripts import dashboard

    monkeypatch.setattr(dashboard, "current_code_signature", lambda rid: "abc123")
    rows = [{"release_id": "o01", "code_signature": None}]
    dashboard._annotate_freshness(rows)
    assert rows[0]["code_fresh"] is None
    assert rows[0]["current_signature"] is None


def test_annotate_freshness_unregistered_release_is_unknown(monkeypatch):
    from trading.lab.scripts import dashboard

    def boom(rid):
        raise KeyError(rid)

    monkeypatch.setattr(dashboard, "current_code_signature", boom)
    rows = [{"release_id": "zz99", "code_signature": "whatever"}]
    dashboard._annotate_freshness(rows)
    assert rows[0]["code_fresh"] is None


def test_annotate_freshness_cache_isolates_releases(monkeypatch):
    from trading.lab.scripts import dashboard

    calls = []

    def sig(rid):
        calls.append(rid)
        return {"o01": "sig_o01", "d01": "sig_d01"}[rid]

    monkeypatch.setattr(dashboard, "current_code_signature", sig)
    rows = [
        {"release_id": "o01", "code_signature": "sig_o01"},   # fresh
        {"release_id": "d01", "code_signature": "stale_d01"}, # stale
        {"release_id": "o01", "code_signature": "old_o01"},   # stale, reuses cache
    ]
    dashboard._annotate_freshness(rows)
    assert rows[0]["code_fresh"] is True
    assert rows[1]["code_fresh"] is False
    assert rows[2]["code_fresh"] is False
    # o01 hashed once despite two rows; d01 once -> 2 total calls
    assert calls == ["o01", "d01"]


def test_annotate_lifecycle_attaches_position_and_rank(tmp_path):
    from trading.lab.scripts.dashboard import _annotate_lifecycle
    from trading.lab.storage.lifecycle import upsert_lifecycle

    db = tmp_path / "lc_dash.duckdb"
    init_db(db)
    with connect(db) as conn:
        upsert_lifecycle(conn, "o03", stage=1, disposition="killed",
                         killed_stage=1, reason="screen neg")
        upsert_lifecycle(conn, "o20", stage=4, disposition="promoted",
                         reason="survived OOS")
        rows = [{"release_id": "o03"}, {"release_id": "o20"}, {"release_id": "o99"}]
        _annotate_lifecycle(conn, rows)

    by_id = {r["release_id"]: r for r in rows}
    assert by_id["o03"]["disposition"] == "killed"
    assert by_id["o03"]["stage_name"] == "screen"
    assert by_id["o03"]["disposition_rank"] == 2
    assert by_id["o20"]["disposition"] == "promoted"
    assert by_id["o20"]["disposition_rank"] == 0
    # no ledger row -> stage 0 / active default
    assert by_id["o99"]["disposition"] == "active"
    assert by_id["o99"]["stage"] == 0
    assert by_id["o99"]["disposition_rank"] == 1
