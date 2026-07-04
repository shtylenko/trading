from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from trading.lab.storage.duckdb import connect, init_db
from trading.lab.storage.lifecycle import get_lifecycle, upsert_lifecycle
from trading.lab.validation.funnel_eval import evaluate_release


def _seed_run(conn, run_id, release_id, testset, daily_rs, *, status="completed",
              start_day=date(2023, 1, 2)):
    """Insert a run + its overall metrics + one trade per day.

    ``daily_rs`` is a list of per-day realized R; each becomes one trade on a
    distinct consecutive trading day, and one session row so the day count is
    real.
    """
    conn.execute(
        """
        INSERT INTO runs (run_id, run_type, testset, release_id, strategy_letter,
            strategy_alias, status, started_at, engine_version, completed_days, total_days)
        VALUES (?, 'backtest', ?, ?, 'o', 'stocks_in_play_orb', ?, ?, 'test', ?, ?)
        """,
        [run_id, testset, release_id, status, datetime(2024, 1, 1, 12), len(daily_rs), len(daily_rs)],
    )
    sum_r = sum(daily_rs)
    metrics = {"total_realized_r": sum_r, "trade_count": len(daily_rs)}
    conn.execute(
        """
        INSERT INTO release_metrics (run_id, testset, release_id, strategy_letter,
            strategy_alias, metric_scope, trade_count, wins, losses, win_rate,
            gross_win_pct, gross_loss_pct, profit_factor, total_pnl_pct, avg_pnl_pct,
            best_trade_pct, worst_trade_pct, metrics_json)
        VALUES (?, ?, ?, 'o', 'stocks_in_play_orb', 'overall', ?, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, ?)
        """,
        [run_id, testset, release_id, len(daily_rs), json.dumps(metrics)],
    )
    for i, r in enumerate(daily_rs):
        d = start_day + timedelta(days=i)
        conn.execute(
            """
            INSERT INTO sessions (session_id, run_id, trade_date, release_id,
                strategy_letter, strategy_alias, status, started_at)
            VALUES (?, ?, ?, ?, 'o', 'stocks_in_play_orb', 'completed', ?)
            """,
            [f"{run_id}_s{i}", run_id, d, release_id, datetime(2024, 1, 1, 12)],
        )
        conn.execute(
            """
            INSERT INTO trades (trade_id, signal_id, session_id, run_id, trade_date,
                testset, ticker, release_id, strategy_letter, strategy_alias,
                setup_type, direction, realized_r)
            VALUES (?, ?, ?, ?, ?, ?, 'AAA', ?, 'o', 'stocks_in_play_orb',
                'brk', 'long', ?)
            """,
            [f"{run_id}_t{i}", f"{run_id}_sig{i}", f"{run_id}_s{i}", run_id, d,
             testset, release_id, float(r)],
        )


def test_evaluate_promotes_through_full_funnel(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        # smoke: a couple of trades, ran clean
        _seed_run(conn, "r_smoke", "o20", "smoke_april_2024_sample", [1.0, -0.5, 2.0])
        # screen: strongly positive, >30 trades
        _seed_run(conn, "r_screen", "o20", "screen_2022_2026_sampled", [2.0] * 40)
        # broad in-sample: all 4 year buckets positive, lots of trades
        for ts in ("eval_2022_broad", "eval_2023_broad", "eval_2024_h1_broad", "eval_2024_h2_broad"):
            _seed_run(conn, f"r_{ts}", "o20", ts, [1.5] * 80)
        # OOS: positive, in line with in-sample
        for ts in ("eval_2025_broad", "eval_2026_h1_broad"):
            _seed_run(conn, f"r_{ts}", "o20", ts, [1.0] * 80)

        lc = evaluate_release(conn, "o20")
    assert lc["disposition"] == "promoted"
    assert lc["stage"] == 4  # cleared OOS rung
    assert lc["killed_stage"] is None


def test_evaluate_kills_at_screen_on_negative_sum_r(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        _seed_run(conn, "r_smoke", "o21", "smoke_april_2024_sample", [1.0, 1.0])
        _seed_run(conn, "r_screen", "o21", "screen_2022_2026_sampled", [-1.0] * 40)
        lc = evaluate_release(conn, "o21")
    assert lc["disposition"] == "killed"
    assert lc["killed_stage"] == 1  # screen rung
    assert lc["stage"] == 0         # only smoke cleared
    assert "screen" in lc["reason"]


def test_evaluate_smoke_zero_trades_passes_and_awaits_screen(tmp_path):
    # A clean smoke run with 0 trades is not a kill; it clears smoke and the
    # release simply awaits a screen run.
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        _seed_run(conn, "r_smoke", "o22", "smoke_april_2024_sample", [])
        lc = evaluate_release(conn, "o22")
    assert lc["disposition"] == "active"
    assert lc["killed_stage"] is None
    assert lc["stage"] == 0
    assert "awaiting screen" in lc["reason"]


def test_evaluate_kills_smoke_on_failed_run(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        _seed_run(conn, "r_smoke", "o25", "smoke_april_2024_sample", [1.0],
                  status="failed")
        lc = evaluate_release(conn, "o25")
    assert lc["disposition"] == "killed"
    assert lc["killed_stage"] == 0


def test_evaluate_oos_artifact_check_uses_broad_is_sum_r(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        _seed_run(conn, "r_smoke", "o26", "smoke_april_2024_sample", [1.0, 1.0])
        _seed_run(conn, "r_screen", "o26", "screen_2022_2026_sampled", [2.0] * 40)
        # Broad IS clears but totals only 40R across the four buckets.
        for ts in ("eval_2022_broad", "eval_2023_broad", "eval_2024_h1_broad", "eval_2024_h2_broad"):
            _seed_run(conn, f"r_{ts}", "o26", ts, [0.125] * 80)
        # OOS totals 160R, more than 3x broad IS; this should stop at REVIEW,
        # not auto-promote as if the artifact check were disabled.
        for ts in ("eval_2025_broad", "eval_2026_h1_broad"):
            _seed_run(conn, f"r_{ts}", "o26", ts, [1.0] * 80)

        lc = evaluate_release(conn, "o26")
    assert lc["disposition"] == "active"
    assert lc["stage"] == 2
    assert "review @ oos" in lc["reason"]
    assert "in-sample" in lc["reason"]


def test_evaluate_one_bucket_carry_goes_to_review(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        _seed_run(conn, "r_smoke", "o23", "smoke_april_2024_sample", [1.0, 1.0])
        _seed_run(conn, "r_screen", "o23", "screen_2022_2026_sampled", [2.0] * 40)
        # one bucket deeply negative, pooled still positive -> carry flag
        _seed_run(conn, "r1", "o23", "eval_2022_broad", [-0.2] * 80)   # ~ -16R bucket
        _seed_run(conn, "r2", "o23", "eval_2023_broad", [2.0] * 80)
        _seed_run(conn, "r3", "o23", "eval_2024_h1_broad", [2.0] * 80)
        _seed_run(conn, "r4", "o23", "eval_2024_h2_broad", [2.0] * 80)
        lc = evaluate_release(conn, "o23")
    assert lc["disposition"] == "active"   # not promoted, not killed
    assert lc["stage"] == 1                # stopped advancing at broad (review)
    assert "review" in lc["reason"]


def test_evaluate_respects_manual_archive(tmp_path):
    db = tmp_path / "fe.duckdb"
    init_db(db)
    with connect(db) as conn:
        upsert_lifecycle(conn, "o24", stage=2, disposition="archived",
                         reason="superseded by o25")
        # a fresh strong run should NOT un-archive it
        _seed_run(conn, "r_screen", "o24", "screen_2022_2026_sampled", [2.0] * 40)
        lc = evaluate_release(conn, "o24")
    assert lc["disposition"] == "archived"
    assert lc["reason"] == "superseded by o25"
