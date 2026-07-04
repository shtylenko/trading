"""Unit tests for trading.marketdata.config."""

from __future__ import annotations

import os
import tempfile

import pytest

from trading.marketdata.config import (
    DATA_DIR,
    Adjustment,
    Session,
    Timeframe,
    dataset_key,
    resolve_dataset_dir,
    resolve_meta_path,
    safe_filename_key,
)


class TestTimeframe:
    def test_values(self):
        assert Timeframe.MIN_1.value == "1min"
        assert Timeframe.MIN_5.value == "5min"
        assert Timeframe.MIN_15.value == "15min"
        assert Timeframe.DAY.value == "1day"

    def test_partition_granularity(self):
        assert Timeframe.MIN_1.partition_granularity == "month"
        assert Timeframe.MIN_5.partition_granularity == "month"
        assert Timeframe.MIN_15.partition_granularity == "year"
        assert Timeframe.DAY.partition_granularity == "year"

    def test_lookback_days_default(self):
        assert Timeframe.MIN_1.lookback_days_default == 5
        assert Timeframe.MIN_5.lookback_days_default == 30
        assert Timeframe.MIN_15.lookback_days_default == 60
        assert Timeframe.DAY.lookback_days_default == 1000

    def test_str(self):
        assert str(Timeframe.MIN_1) == "1min"


class TestSession:
    def test_values(self):
        assert Session.RTH.value == "rth"
        assert Session.EXTENDED.value == "extended"


class TestAdjustment:
    def test_values(self):
        assert Adjustment.RAW.value == "raw"
        assert Adjustment.SPLIT.value == "split"
        assert Adjustment.ALL.value == "all"


class TestPathHelpers:
    def test_resolve_dataset_dir(self):
        path = resolve_dataset_dir("AAPL", "1min", "rth", "raw")
        assert path.name == "adjustment=raw"
        assert path.parent.name == "session=rth"
        assert path.parent.parent.name == "AAPL"

    def test_resolve_meta_path(self):
        path = resolve_meta_path("SPY", "1day", "rth", "split")
        assert path.name == "meta.json"
        assert "SPY" in str(path)

    def test_dataset_key(self):
        assert dataset_key("AAPL", "1min", "rth", "raw") == "AAPL:1min:rth:raw"

    def test_safe_filename_key(self):
        assert safe_filename_key("AAPL:1min:rth:raw") == "AAPL_1min_rth_raw"

    def test_DATA_DIR_override(self):
        """DATA_DIR respects STRATEGY_LAB_MARKETDATA_DIR env var."""
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
            try:
                os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td
                # Reimport to pick up new env
                import importlib
                import trading.marketdata.config as cfg
                importlib.reload(cfg)
                assert str(cfg.DATA_DIR) == td
            finally:
                if old is None:
                    del os.environ["STRATEGY_LAB_MARKETDATA_DIR"]
                else:
                    os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old
                importlib.reload(__import__("trading.marketdata.config"))


def test_negative_cache_old_provider_empty_never_expires():
    from datetime import datetime, timedelta, timezone
    from trading.marketdata.ttl import is_negative_cache_expired

    stale_retrieved = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_date_entry = {"reason": "provider_empty", "retrieved_at": stale_retrieved}

    # Historical date: confirmed absence is final even past the 24h TTL
    assert is_negative_cache_expired(old_date_entry, date_key="2024-03-08") is False
    # Recent date: 24h TTL still applies
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    assert is_negative_cache_expired(old_date_entry, date_key=recent) is True
    # No date_key: legacy behavior (TTL applies)
    assert is_negative_cache_expired(old_date_entry) is True
    # provider_error short TTL unaffected
    err_entry = {"reason": "provider_error", "retrieved_at": stale_retrieved}
    assert is_negative_cache_expired(err_entry, date_key="2024-03-08") is True
