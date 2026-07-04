from __future__ import annotations

from datetime import date

from trading.lab.core.models import StrategyContext
from trading.lab.storage import duckdb

from .conftest import make_5m_bars, make_daily_bars


def test_adhoc_backtest_persists_strategy_identity_and_metrics(monkeypatch, tmp_path):
    from trading.lab.runner import pipeline

    db_path = tmp_path / "strategy_lab_pipeline.duckdb"

    monkeypatch.setattr(pipeline, "connect", lambda: duckdb.connect(db_path))
    monkeypatch.setattr(pipeline, "init_db", lambda: duckdb.init_db(db_path))

    def fake_load_context(release_id, trade_date, testset_name, tickers, force_data):
        assert tickers == ["AAPL"]
        return StrategyContext(
            trade_date=trade_date,
            release_id=release_id,
            testset=testset_name,
            bars_5m={"AAPL": make_5m_bars()},
            daily={"AAPL": make_daily_bars()},
        )

    monkeypatch.setattr(pipeline, "_load_context", fake_load_context)

    session_id = pipeline.run_backtest_for_date(
        release_id="o01",
        trade_date=date(2024, 4, 1),
        tickers=["AAPL"],
    )

    with duckdb.connect(db_path) as conn:
        session = conn.execute(
            "SELECT status, strategy_alias, strategy_letter, candidate_count, signal_count, trade_count FROM sessions WHERE session_id = ?",
            [session_id],
        ).fetchone()
        metrics = conn.execute(
            "SELECT strategy_alias, strategy_letter, trade_count, total_pnl_pct FROM release_metrics"
        ).fetchone()
        order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        fill_count = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]

    assert session == ("completed", "stocks_in_play_orb", "o", 1, 1, 1)
    assert metrics[0] == "stocks_in_play_orb"
    assert metrics[1] == "o"
    assert metrics[2] == 1
    assert metrics[3] > 0
    assert order_count == 1
    assert fill_count == 2


def test_prefetch_testset_data_issues_ranged_fetches(monkeypatch):
    """One ranged request per ticker per timeframe; per-ticker failures don't raise."""
    import threading

    from trading.lab.runner import pipeline

    calls = []
    calls_lock = threading.Lock()

    def fake_intraday_range(ticker, start, end, timeframe="5min", session="rth", force=False):
        with calls_lock:
            calls.append((ticker, timeframe, session, start, end))
        if ticker == "BAD":
            raise RuntimeError("provider down")
        return None

    def fake_daily_range(ticker, start, end, force=False, adjustment="raw"):
        with calls_lock:
            calls.append((ticker, "1day", "rth", start, end))
        return None

    monkeypatch.setattr(pipeline, "fetch_intraday_range", fake_intraday_range)
    monkeypatch.setattr(pipeline, "fetch_daily_range", fake_daily_range)
    monkeypatch.setattr(
        pipeline, "_resolve_tickers", lambda testset, d, override: ["AAPL", "BAD", "MSFT"]
    )

    class FakeRelease:
        historical_5m_lookback_days = 14
        requires_rth_1m = True
        requires_extended_1m = False

    days = [date(2024, 7, 1), date(2024, 7, 2)]
    pipeline._prefetch_testset_data(FakeRelease(), None, days, max_workers=2)

    by_ticker = {}
    for ticker, timeframe, session, start, end in calls:
        by_ticker.setdefault(ticker, []).append((timeframe, session))

    # SPY warm-up plus each universe ticker, including the failing one
    assert set(by_ticker) == {"SPY", "AAPL", "BAD", "MSFT"}
    for t in ("AAPL", "MSFT"):
        assert sorted(by_ticker[t]) == [("1day", "rth"), ("1min", "rth"), ("5min", "rth")]

    # ranged, not per-day: every 5min fetch spans the whole range (plus history)
    five_min = [(s, e) for tk, tf, _, s, e in calls if tf == "5min" and tk == "AAPL"]
    assert five_min == [(date(2024, 7, 1) - pipeline.timedelta(days=42), date(2024, 7, 2))]

    # daily prefetch covers the fetch_daily_context lookback window
    daily = [(s, e) for tk, tf, _, s, e in calls if tf == "1day" and tk == "AAPL"]
    assert daily == [(date(2024, 7, 1) - pipeline.timedelta(days=41), date(2024, 7, 2))]


def test_prefetch_retries_connection_failures_until_success(monkeypatch):
    """Connection outages re-queue the ticker for another round — never skipped."""
    import threading

    from trading.marketdata.errors import ConnectionTimeoutError
    from trading.lab.runner import pipeline

    attempts = {}
    lock = threading.Lock()
    waits = []

    def fake_intraday_range(ticker, start, end, timeframe="5min", session="rth", force=False):
        with lock:
            attempts[ticker] = attempts.get(ticker, 0) + 1
            # FLAKY fails its first two rounds with a connection-shaped error
            if ticker == "FLAKY" and attempts[ticker] <= 2:
                raise ConnectionTimeoutError("unable to connect to provider for 15+ minutes.")
        return None

    monkeypatch.setattr(pipeline, "fetch_intraday_range", fake_intraday_range)
    monkeypatch.setattr(pipeline, "fetch_daily_range", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "_resolve_tickers", lambda testset, d, override: ["AAPL", "FLAKY"])
    monkeypatch.setattr(pipeline, "_wait_for_connectivity", lambda log, **k: waits.append(1))

    class FakeRelease:
        historical_5m_lookback_days = 0
        requires_rth_1m = False
        requires_extended_1m = False

    pipeline._prefetch_testset_data(FakeRelease(), None, [date(2024, 7, 1)], max_workers=2)

    assert attempts["FLAKY"] == 3  # two failed rounds + the successful one
    assert len(waits) == 2  # waited for connectivity before each retry round


def test_pipeline_real_hydration_and_execution(monkeypatch, tmp_path):
    import os
    import importlib
    from datetime import date, datetime
    import pandas as pd
    from trading.lab.runner import pipeline
    from trading.lab.storage import duckdb
    from .conftest import make_5m_bars, make_daily_bars

    # Set up temp database and environment
    db_path = tmp_path / "strategy_lab_pipeline_real.duckdb"
    monkeypatch.setattr(pipeline, "connect", lambda: duckdb.connect(db_path))
    monkeypatch.setattr(pipeline, "init_db", lambda: duckdb.init_db(db_path))

    # Set up isolated data directory for marketdata
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    data_dir = tmp_path / "smd_data"
    os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = str(data_dir)

    import trading.marketdata.config
    importlib.reload(trading.marketdata.config)
    import trading.marketdata.storage
    importlib.reload(trading.marketdata.storage)

    from trading.marketdata.storage import write_bars, update_meta_summary, update_meta_coverage
    from trading.marketdata.provider import _PROVIDER_REGISTRY
    import trading.marketdata.fetcher as fetcher_mod

    # Clear registry so it doesn't try to auto-register or contact live providers.
    # We will only use cached data.
    _PROVIDER_REGISTRY.clear()
    fetcher_mod._REGISTERED = True

    # Seed mock data
    trade_date = date(2024, 4, 1)

    # AAPL 5m bars (78 bars for a full RTH day)
    from .conftest import _make_5m_index
    aapl_idx = _make_5m_index(periods=78)
    aapl_5m = pd.DataFrame({
        "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8, "volume": 500000
    }, index=aapl_idx)
    aapl_5m.index.name = "timestamp"
    write_bars("AAPL", "5min", aapl_5m, session="rth", adjustment="raw", provider_name="seed")
    update_meta_summary("AAPL", "5min", "rth", "raw")
    # Coverage entries
    for d in aapl_5m.index.normalize().unique():
        date_str = d.strftime("%Y-%m-%d")
        cnt = len(aapl_5m[aapl_5m.index.normalize() == d])
        update_meta_coverage("AAPL", "5min", "rth", "raw", date_str, expected=cnt, actual=cnt)

    # AAPL daily context (covering the default lookback window of 40 days)
    aapl_daily = make_daily_bars(periods=45)
    aapl_daily.index.name = "timestamp"
    write_bars("AAPL", "1day", aapl_daily, session="rth", adjustment="raw", provider_name="seed")
    update_meta_summary("AAPL", "1day", "rth", "raw")

    # SPY 5m bars (78 bars for a full RTH day)
    spy_idx = _make_5m_index(periods=78)
    spy_5m = pd.DataFrame({
        "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8, "volume": 500000
    }, index=spy_idx)
    spy_5m.index.name = "timestamp"
    write_bars("SPY", "5min", spy_5m, session="rth", adjustment="raw", provider_name="seed")
    update_meta_summary("SPY", "5min", "rth", "raw")
    for d in spy_5m.index.normalize().unique():
        date_str = d.strftime("%Y-%m-%d")
        cnt = len(spy_5m[spy_5m.index.normalize() == d])
        update_meta_coverage("SPY", "5min", "rth", "raw", date_str, expected=cnt, actual=cnt)

    # Run the backtest (which does not mock _load_context!)
    try:
        session_id = pipeline.run_backtest_for_date(
            release_id="o01",
            trade_date=trade_date,
            tickers=["AAPL"],
        )
        
        # Verify the database has the session and metrics populated
        with duckdb.connect(db_path) as conn:
            session = conn.execute(
                "SELECT status, candidate_count, signal_count, trade_count FROM sessions WHERE session_id = ?",
                [session_id],
            ).fetchone()
            metrics_row = conn.execute(
                "SELECT trade_count, total_pnl_pct, metrics_json FROM release_metrics"
            ).fetchone()
            
        assert session == ("completed", 1, 1, 1)
        assert metrics_row[0] == 1
        assert metrics_row[1] is not None
        
        import json
        metrics_json = json.loads(metrics_row[2])
        assert metrics_json["total_realized_r"] is not None
    finally:
        # Cleanup env
        if old_env is None:
            os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
        else:
            os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old_env
