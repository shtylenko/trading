from __future__ import annotations

import logging
import random
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "strategy_lab.duckdb"

logger = logging.getLogger("strategy_lab.storage")

# DuckDB allows a single read-write connection per database file. The
# pipeline only holds connections for short bursts (run-row creation,
# per-day session writes), so concurrent backtests work fine as long as
# a lock collision waits instead of crashing.
_LOCK_WAIT_TOTAL = 600.0  # give up after 10 minutes
_LOCK_WAIT_STEP = 2.0


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "strategy_lab requires DuckDB. Install it with: python3 -m pip install duckdb"
        ) from exc
    return duckdb


def connect(db_path: Path | str | None = None, *, read_only: bool = False):
    duckdb = _duckdb()
    path = str(db_path or DB_PATH)
    deadline = time.monotonic() + _LOCK_WAIT_TOTAL
    waited = False
    while True:
        try:
            conn = duckdb.connect(path, read_only=read_only)
            if waited:
                logger.info("DB lock released; connected to %s", path)
            return conn
        except duckdb.IOException as exc:
            if "lock" not in str(exc).lower() or time.monotonic() >= deadline:
                raise
            if not waited:
                logger.warning(
                    "Database %s is locked by another process; waiting up "
                    "to %.0f s for it to release...", path, _LOCK_WAIT_TOTAL,
                )
                waited = True
            time.sleep(_LOCK_WAIT_STEP + random.uniform(0, 0.5))


def init_db(db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id VARCHAR PRIMARY KEY,
                run_type VARCHAR NOT NULL,
                testset VARCHAR,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                engine_version VARCHAR NOT NULL,
                execution_config_json VARCHAR,
                testset_config_json VARCHAR,
                code_signature VARCHAR,
                completed_days INTEGER DEFAULT 0,
                total_days INTEGER DEFAULT 0,
                notes VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                testset VARCHAR,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                universe_name VARCHAR,
                ticker_count INTEGER DEFAULT 0,
                candidate_count INTEGER DEFAULT 0,
                signal_count INTEGER DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                error VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                session_id VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                ticker VARCHAR NOT NULL,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                rank INTEGER,
                score DOUBLE,
                reason VARCHAR,
                features_json VARCHAR,
                PRIMARY KEY (session_id, ticker)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                ticker VARCHAR NOT NULL,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                setup_type VARCHAR NOT NULL,
                signal_time TIMESTAMP,
                entry_trigger DOUBLE NOT NULL,
                stop_price DOUBLE NOT NULL,
                target_price DOUBLE,
                risk_per_share DOUBLE,
                metadata_json VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id VARCHAR PRIMARY KEY,
                signal_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                side VARCHAR NOT NULL,
                order_type VARCHAR NOT NULL,
                trigger_price DOUBLE,
                limit_price DOUBLE,
                stop_price DOUBLE,
                target_price DOUBLE,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                status VARCHAR NOT NULL,
                metadata_json VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                fill_id VARCHAR PRIMARY KEY,
                order_id VARCHAR NOT NULL,
                signal_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                side VARCHAR NOT NULL,
                fill_time TIMESTAMP NOT NULL,
                fill_price DOUBLE NOT NULL,
                quantity DOUBLE,
                fees DOUBLE DEFAULT 0,
                slippage DOUBLE DEFAULT 0,
                metadata_json VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id VARCHAR PRIMARY KEY,
                signal_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                testset VARCHAR,
                ticker VARCHAR NOT NULL,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                setup_type VARCHAR NOT NULL,
                direction VARCHAR NOT NULL,
                entry_time TIMESTAMP,
                entry_price DOUBLE,
                exit_time TIMESTAMP,
                exit_price DOUBLE,
                exit_reason VARCHAR,
                pnl_pct DOUBLE,
                gross_pnl_pct DOUBLE,
                realized_r DOUBLE,
                mfe_pct DOUBLE,
                mae_pct DOUBLE,
                fees_pct DOUBLE DEFAULT 0,
                slippage_pct DOUBLE DEFAULT 0,
                context_json VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS release_metrics (
                run_id VARCHAR NOT NULL,
                testset VARCHAR,
                release_id VARCHAR NOT NULL,
                strategy_letter VARCHAR NOT NULL,
                strategy_alias VARCHAR NOT NULL,
                metric_scope VARCHAR NOT NULL,
                trade_count INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate DOUBLE,
                gross_win_pct DOUBLE,
                gross_loss_pct DOUBLE,
                profit_factor DOUBLE,
                total_pnl_pct DOUBLE,
                avg_pnl_pct DOUBLE,
                best_trade_pct DOUBLE,
                worst_trade_pct DOUBLE,
                metrics_json VARCHAR,
                PRIMARY KEY (run_id, metric_scope)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS release_lifecycle (
                release_id VARCHAR PRIMARY KEY,
                stage INTEGER NOT NULL,
                disposition VARCHAR NOT NULL,
                killed_stage INTEGER,
                reason VARCHAR,
                decided_by_run VARCHAR,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_runs (
                search_id VARCHAR PRIMARY KEY,
                release_id VARCHAR NOT NULL,
                testset VARCHAR,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                objective VARCHAR NOT NULL,
                config_json VARCHAR,
                status VARCHAR NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_results (
                search_id VARCHAR NOT NULL,
                result_rank INTEGER NOT NULL,
                filters_json VARCHAR NOT NULL,
                trade_count INTEGER,
                total_pnl_pct DOUBLE,
                profit_factor DOUBLE,
                win_rate DOUBLE,
                metrics_json VARCHAR,
                PRIMARY KEY (search_id, result_rank)
            )
        """)
