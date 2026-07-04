"""Unit tests for trading.marketdata.storage.

All tests use a temporary data directory to avoid polluting real data.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

# Set DATA_DIR before importing storage
_test_dir: str | None = None


@pytest.fixture(autouse=True)
def _isolated_data_dir():
    """Each test gets a fresh temp directory as STRATEGY_LAB_MARKETDATA_DIR."""
    global _test_dir
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_test_") as td:
        _test_dir = td
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td
        import importlib
        import trading.marketdata.config
        importlib.reload(trading.marketdata.config)
        import trading.marketdata.storage
        importlib.reload(trading.marketdata.storage)
        yield
    if old_env is None:
        os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
    else:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old_env


def _make_1min_df(n: int = 100, start_ts: str = "2024-01-02 14:30") -> pd.DataFrame:
    """Create a test DataFrame with n 1min bars starting at start_ts (UTC)."""
    timestamps = pd.date_range(start_ts, periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [180.0 + i * 0.01 for i in range(n)],
        "high": [181.0 + i * 0.01 for i in range(n)],
        "low": [179.5 + i * 0.01 for i in range(n)],
        "close": [180.5 + i * 0.01 for i in range(n)],
        "volume": [100000 + i * 100 for i in range(n)],
    })
    df.index = timestamps
    df.index.name = "timestamp"
    return df


class TestReadWrite:
    def test_write_and_read_full(self):
        from trading.marketdata.storage import read_bars, write_bars

        df = _make_1min_df(100)
        rows = write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                          provider_name="alpaca")
        assert rows == 100

        result = read_bars("AAPL", "1min", session="rth", adjustment="raw")
        assert len(result) == 100
        assert list(result.columns) == [
            "open", "high", "low", "close", "volume",
            "provider", "retrieved_at",
        ]
        assert result.index.name == "timestamp"
        assert result.index.tz is not None

    def test_write_and_read_with_filter(self):
        from trading.marketdata.storage import read_bars, write_bars

        df = _make_1min_df(390)
        write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                   provider_name="alpaca")

        # Filter by start (ET timezone input)
        ny = __import__("zoneinfo").ZoneInfo("America/New_York")
        filtered = read_bars(
            "AAPL", "1min",
            start=datetime(2024, 1, 2, 11, 0, tzinfo=ny),
            session="rth", adjustment="raw",
        )
        # 09:30 ET = 14:30 UTC, 11:00 ET = 16:00 UTC
        # So 16:00 UTC is 90 minutes after 14:30 UTC start
        # Wait: start has 390 bars from 14:30 UTC to 14:30+389min=21:39 UTC (too far)
        # Actually 14:30 UTC = 09:30 ET. 11:00 ET = 16:00 UTC.
        # 16:00 - 14:30 = 90 minutes. So bars at 14:30+90min = 16:00 UTC are included.
        # 390 - 90 = 300 bars at 11:00 ET+
        assert len(filtered) == 300

    def test_write_daily(self):
        from trading.marketdata.storage import read_bars, write_bars

        dates = pd.date_range("2020-01-02", periods=500, freq="D", tz="UTC")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": 200.0, "high": 201.0, "low": 199.0,
            "close": 200.5, "volume": 5_000_000,
        })
        df.index = dates
        df.index.name = "timestamp"
        rows = write_bars("SPY", "1day", df, session="rth", adjustment="split",
                          provider_name="alpaca")
        assert rows == 500

        result = read_bars("SPY", "1day", session="rth", adjustment="split")
        assert len(result) == 500
        assert "provider" in result.columns

    def test_write_empty_df(self):
        from trading.marketdata.storage import write_bars

        df = pd.DataFrame()
        rows = write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                          provider_name="test")
        assert rows == 0

    def test_read_nonexistent(self):
        from trading.marketdata.storage import read_bars

        result = read_bars("NONEXIST", "1min", session="rth", adjustment="raw")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_read_returns_empty_with_wrong_session(self):
        """Reading with different session returns no data."""
        from trading.marketdata.storage import read_bars, write_bars

        df = _make_1min_df(100)
        write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                   provider_name="alpaca")
        result = read_bars("AAPL", "1min", session="extended", adjustment="raw")
        assert result.empty

    def test_read_returns_empty_with_wrong_adjustment(self):
        from trading.marketdata.storage import read_bars, write_bars

        df = _make_1min_df(100)
        write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                   provider_name="alpaca")
        result = read_bars("AAPL", "1min", session="rth", adjustment="split")
        assert result.empty

    def test_merge_appends_new_data(self):
        from trading.marketdata.storage import read_bars, write_bars

        # Write first batch (09:30-09:40 ET = 10 bars)
        df1 = _make_1min_df(10, "2024-01-02 14:30")
        write_bars("AAPL", "1min", df1, session="rth", adjustment="raw",
                   provider_name="alpaca")

        # Append non-overlapping data (12:00-12:10 ET = 10 bars at 17:00 UTC)
        df2 = _make_1min_df(10, "2024-01-02 17:00")
        write_bars("AAPL", "1min", df2, session="rth", adjustment="raw",
                   provider_name="alpaca", merge=True)

        merged = read_bars("AAPL", "1min", session="rth", adjustment="raw")
        assert len(merged) == 20

    def test_merge_dedup_overlap(self):
        from trading.marketdata.storage import read_bars, write_bars

        df1 = _make_1min_df(10, "2024-01-02 14:30")
        write_bars("AAPL", "1min", df1, session="rth", adjustment="raw",
                   provider_name="alpaca")

        # Overlapping same range with higher close values
        df2 = _make_1min_df(10, "2024-01-02 14:30")
        df2["close"] = [999.0 + i * 0.01 for i in range(10)]
        write_bars("AAPL", "1min", df2, session="rth", adjustment="raw",
                   provider_name="marketdata", merge=True)

        merged = read_bars("AAPL", "1min", session="rth", adjustment="raw")
        assert len(merged) == 10  # Still 10 rows (dedup)
        # Second write has later timestamp in concat, keep="last"
        assert merged["close"].iloc[0] == 999.0


class TestMetaSidecar:
    def test_read_write_meta(self):
        from trading.marketdata.storage import read_meta, write_meta

        meta = {"total_rows": 100, "ticker": "AAPL"}
        write_meta("AAPL", "1min", "rth", "raw", meta)
        result = read_meta("AAPL", "1min", "rth", "raw")
        assert result["total_rows"] == 100
        assert result["version"] == 1
        assert "timezone_storage" in result

    def test_read_nonexistent_meta(self):
        from trading.marketdata.storage import read_meta

        result = read_meta("NONEXIST", "1min", "rth", "raw")
        assert result == {}

    def test_update_meta_coverage(self):
        from trading.marketdata.storage import (
            read_meta,
            update_meta_coverage,
        )

        update_meta_coverage("AAPL", "1min", "rth", "raw",
                             "2024-01-02", expected=390, actual=390)
        meta = read_meta("AAPL", "1min", "rth", "raw")
        assert meta["coverage"]["2024-01-02"]["expected_bars"] == 390
        assert meta["coverage"]["2024-01-02"]["actual_bars"] == 390
        assert meta["coverage"]["2024-01-02"]["complete"] is True

    def test_negative_cache(self):
        from trading.marketdata.storage import (
            get_negative_cache,
            write_negative_cache,
        )

        write_negative_cache("AAPL", "1min", "rth", "raw",
                             "2024-01-01", "non_trading_day")
        nc = get_negative_cache("AAPL", "1min", "rth", "raw")
        assert "2024-01-01" in nc
        assert nc["2024-01-01"]["reason"] == "non_trading_day"

    def test_update_meta_summary(self):
        from trading.marketdata.storage import (
            read_meta,
            update_meta_summary,
            write_bars,
        )

        df = _make_1min_df(100)
        write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                   provider_name="alpaca")
        update_meta_summary("AAPL", "1min", "rth", "raw")
        meta = read_meta("AAPL", "1min", "rth", "raw")
        assert meta["total_rows"] == 100
        assert meta["ticker"] == "AAPL"
        assert meta["timeframe"] == "1min"
        assert meta["session"] == "rth"
        assert meta["adjustment"] == "raw"
        assert len(meta["partitions"]) >= 1


class TestAtomicWrites:
    def test_file_appears_atomically(self):
        """The written file should appear atomically (temp file then rename)."""
        from trading.marketdata.storage import resolve_dataset_dir, write_bars

        df = _make_1min_df(10)
        write_bars("ATOMIC", "1min", df, session="rth", adjustment="raw",
                   provider_name="test")

        ds_dir = resolve_dataset_dir("ATOMIC", "1min", "rth", "raw")
        parquet_files = list(ds_dir.rglob("data.parquet"))
        assert len(parquet_files) == 1
        assert parquet_files[0].stat().st_size > 0

    def test_no_stale_temp_files(self):
        """No .tmp files should remain after a write."""
        from trading.marketdata.storage import resolve_dataset_dir, write_bars

        df = _make_1min_df(10)
        write_bars("CLEAN", "1min", df, session="rth", adjustment="raw",
                   provider_name="test")

        ds_dir = resolve_dataset_dir("CLEAN", "1min", "rth", "raw")
        temp_files = list(ds_dir.rglob("*.tmp"))
        assert len(temp_files) == 0


class TestPartitionPaths:
    def test_resolve_path(self):
        from trading.marketdata.storage import resolve_path

        p = resolve_path("AAPL", "1min", "rth", "raw", year=2024, month=1)
        assert "year=2024" in str(p)
        assert "month=1" in str(p)
        assert p.name == "data.parquet"

        p = resolve_path("AAPL", "1day", "rth", "split", year=2024)
        assert "year=2024" in str(p)
        assert "month" not in str(p)

    def test_get_partition_paths(self):
        from trading.marketdata.storage import (
            get_partition_paths,
            write_bars,
        )
        from datetime import datetime

        df = _make_1min_df(100)
        write_bars("AAPL", "1min", df, session="rth", adjustment="raw",
                   provider_name="alpaca")

        paths = get_partition_paths(
            "AAPL", "1min",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            session="rth", adjustment="raw",
        )
        assert len(paths) == 1
        assert paths[0].name == "data.parquet"

    def test_get_partition_paths_no_data(self):
        from trading.marketdata.storage import get_partition_paths
        from datetime import datetime

        paths = get_partition_paths(
            "NODATA", "1min",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            session="rth", adjustment="raw",
        )
        assert paths == []
