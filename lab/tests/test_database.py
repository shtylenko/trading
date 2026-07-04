from __future__ import annotations

from trading.lab.storage.duckdb import connect, init_db


def test_duckdb_schema_has_strategy_identity_columns(tmp_path):
    db_path = tmp_path / "strategy_lab_test.duckdb"

    init_db(db_path)

    with connect(db_path) as conn:
        for table in ["runs", "sessions", "candidates", "signals", "trades", "release_metrics"]:
            cols = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
            assert "strategy_letter" in cols
            assert "strategy_alias" in cols


def test_duckdb_schema_has_core_tables(tmp_path):
    db_path = tmp_path / "strategy_lab_test.duckdb"

    init_db(db_path)

    with connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}

    assert {
        "runs",
        "sessions",
        "candidates",
        "signals",
        "orders",
        "fills",
        "trades",
        "release_metrics",
        "search_runs",
        "search_results",
    }.issubset(tables)
