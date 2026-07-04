"""Unit tests for trading.marketdata.ttl."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _touch(path, mtime: datetime | None = None):
    """Create or update mtime of a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    if mtime is not None:
        os.utime(path, (mtime.timestamp(), mtime.timestamp()))


# ── Test is_stale ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_data_dir():
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_ttl_") as td:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td
        import importlib
        import trading.marketdata.config
        importlib.reload(trading.marketdata.config)
        import trading.marketdata.ttl
        importlib.reload(trading.marketdata.ttl)
        yield
    if old_env is None:
        os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
    else:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old_env


class TestFreshnessRules:
    def test_no_file_is_stale(self):
        from trading.marketdata.ttl import is_stale
        from pathlib import Path

        assert is_stale("AAPL", "1min", Path("/nonexistent/file.parquet"), "rth", "raw") is True

    def test_historical_1min_never_stale(self):
        """Historical 1min data (outside today/yesterday) should never be stale, even if the file mtime is old."""
        from trading.marketdata.ttl import is_stale
        from trading.marketdata.config import DATA_DIR
        import pandas as pd

        # Create a file path
        file_path = DATA_DIR / "1min" / "AAPL" / "session=rth" / "adjustment=raw" / "year=2024" / "month=1" / "data.parquet"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write a valid parquet file with a historical timestamp (e.g. 2024-01-02)
        df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2024-01-02 14:30:00", tz="UTC")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
        })
        df.to_parquet(file_path, index=False)

        # Set file mtime to 5 hours ago (older than the 2-hour 1min RTH staleness threshold)
        five_hours_ago = datetime.now(timezone.utc) - timedelta(hours=5)
        os.utime(file_path, (five_hours_ago.timestamp(), five_hours_ago.timestamp()))

        # Since the data is historical (2024), it should not be stale
        assert is_stale("AAPL", "1min", file_path, "rth", "raw") is False



class TestNegativeCacheTTL:
    def test_non_trading_day_never_expires(self):
        from trading.marketdata.ttl import is_negative_cache_expired

        entry = {"reason": "non_trading_day", "retrieved_at": "2020-01-01T00:00:00Z"}
        assert is_negative_cache_expired(entry) is False

    def test_provider_empty_expires_after_24h(self):
        from trading.marketdata.ttl import is_negative_cache_expired

        # Created 48 hours ago → expired
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        entry = {"reason": "provider_empty", "retrieved_at": old}
        assert is_negative_cache_expired(entry) is True

        # Created 1 hour ago → still fresh
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        entry2 = {"reason": "provider_empty", "retrieved_at": recent}
        assert is_negative_cache_expired(entry2) is False

    def test_unknown_reason_expires(self):
        from trading.marketdata.ttl import is_negative_cache_expired

        entry = {"reason": "something_else", "retrieved_at": "2024-01-01T00:00:00Z"}
        assert is_negative_cache_expired(entry) is True

    def test_malformed_retrieved_at_expires(self):
        from trading.marketdata.ttl import is_negative_cache_expired

        entry = {"reason": "provider_empty", "retrieved_at": "not_a_date"}
        assert is_negative_cache_expired(entry) is True


class TestDatePredicates:
    def test_is_today_or_yesterday(self):
        from trading.marketdata.ttl import is_today_or_yesterday
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        assert is_today_or_yesterday(now) is True
        # the predicate counts TRADING days (Fri stays fresh through Mon by design),
        # so 3 *calendar* days back is only ~1 session on a Mon/weekend and flaky.
        # Use a margin wide enough to be >1 session regardless of weekends/holidays.
        too_old = now - timedelta(days=10)
        assert is_today_or_yesterday(too_old) is False

    def test_is_within_last_3_days(self):
        from trading.marketdata.ttl import is_within_last_3_days
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        assert is_within_last_3_days(now) is True
        # the window counts TRADING days, so use a margin wide enough to
        # contain at most 3 sessions regardless of weekends/holidays
        old = now - timedelta(days=10)
        assert is_within_last_3_days(old) is False
