"""Unit tests for trading.marketdata.provider and providers.

Tests the provider interface, registry, and each provider's factory.
Provider implementations that need live API calls are integration tests
and are skipped unless RUN_INTEGRATION=1.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from trading.marketdata.provider import (
    Provider,
    ProviderCapabilities,
    _PROVIDER_REGISTRY,
    get_providers_for_timeframe,
    register_provider,
)


class TestProviderInterface:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Provider()  # type: ignore

    def test_minimal_provider(self):
        """A minimal concrete provider can be created and registered."""
        class TestProv(Provider):
            @property
            def capabilities(self):
                return ProviderCapabilities(
                    name="test", priority=50,
                    timeframes={"1day"}, sessions={"rth"},
                    adjustments={"raw"}, requires_auth=False, is_free=True,
                )

            def fetch_bars(self, ticker, timeframe, start, end,
                           session="rth", adjustment="raw"):
                return pd.DataFrame()

        p = TestProv()
        assert p.capabilities.name == "test"
        assert p.capabilities.priority == 50

    def test_provider_fetch_returns_dataframe(self):
        """fetch_bars must return DataFrame, never None."""
        class MyProv(Provider):
            @property
            def capabilities(self):
                return ProviderCapabilities(name="mine", priority=1)

            def fetch_bars(self, *args, **kwargs):
                return pd.DataFrame()

        p = MyProv()
        result = p.fetch_bars("AAPL", "1day", None, None)
        assert isinstance(result, pd.DataFrame)


class TestRegistry:
    def setup_method(self):
        # Clear registry
        _PROVIDER_REGISTRY.clear()

    def test_register_and_order(self):
        p1 = _make_provider("first", priority=1)
        p2 = _make_provider("second", priority=99)
        p3 = _make_provider("third", priority=50)

        register_provider(p1)
        register_provider(p2)
        register_provider(p3)

        assert _PROVIDER_REGISTRY[0].capabilities.name == "first"
        assert _PROVIDER_REGISTRY[1].capabilities.name == "third"
        assert _PROVIDER_REGISTRY[2].capabilities.name == "second"

    def test_get_providers_for_timeframe(self):
        p1 = _make_provider("daily_prov", priority=1, tfs={"1day"})
        p2 = _make_provider("all_prov", priority=2, tfs={"1min", "1day"})

        for p in (p1, p2):
            register_provider(p)

        daily = get_providers_for_timeframe("1day")
        assert len(daily) == 2
        assert daily[0].capabilities.name == "daily_prov"

        intraday = get_providers_for_timeframe("1min")
        assert len(intraday) == 1
        assert intraday[0].capabilities.name == "all_prov"

    def test_get_providers_filters_by_session(self):
        p1 = _make_provider("rth_only", priority=1, tfs={"1day"}, sessions={"rth"})
        p2 = _make_provider("extended_only", priority=2, tfs={"1day"}, sessions={"extended"})
        for p in (p1, p2):
            register_provider(p)

        rth_providers = get_providers_for_timeframe("1day", session="rth")
        names = [p.capabilities.name for p in rth_providers]
        assert "rth_only" in names
        assert "extended_only" not in names

    def test_get_providers_filters_by_adjustment(self):
        p1 = _make_provider("raw_only", priority=1, tfs={"1day"}, adjustments={"raw"})
        p2 = _make_provider("split_only", priority=2, tfs={"1day"}, adjustments={"split"})
        for p in (p1, p2):
            register_provider(p)

        split_providers = get_providers_for_timeframe("1day", adjustment="split")
        names = [p.capabilities.name for p in split_providers]
        assert "split_only" in names
        assert "raw_only" not in names


class TestAlpacaProviderInit:
    def test_instantiate(self):
        from trading.marketdata.providers.alpaca_provider import AlpacaProvider

        try:
            p = AlpacaProvider()
            assert p.capabilities.name == "alpaca"
            assert 1 in p.capabilities.timeframes or "1min" in p.capabilities.timeframes
            assert p.capabilities.priority == 1
        except RuntimeError as e:
            if "alpaca-py is not installed" in str(e):
                pytest.skip("alpaca-py not installed")

    def test_session_filter_excludes_premarket(self):
        from trading.marketdata.providers.alpaca_provider import AlpacaProvider

        idx = pd.DatetimeIndex([
            pd.Timestamp("2024-01-02 13:00", tz="UTC"),  # 08:00 ET
            pd.Timestamp("2024-01-02 14:30", tz="UTC"),  # 09:30 ET
            pd.Timestamp("2024-01-02 20:59", tz="UTC"),  # 15:59 ET
        ], name="timestamp")
        df = pd.DataFrame({"open": [1, 2, 3]}, index=idx)

        filtered = AlpacaProvider._filter_session(df, "rth")
        assert list(filtered.index) == [idx[1], idx[2]]


class TestMarketDataProviderInit:
    def test_instantiate(self):
        from trading.marketdata.providers.marketdata_provider import (
            MarketDataProvider,
        )

        p = MarketDataProvider()
        assert p.capabilities.name == "marketdata"
        assert p.capabilities.priority == 2
        assert p.capabilities.adjustments == {"raw"}


class TestYFinanceProviderInit:
    def test_instantiate(self):
        from trading.marketdata.providers.yfinance_provider import (
            YFinanceProvider,
        )

        try:
            p = YFinanceProvider()
            assert p.capabilities.name == "yfinance"
            assert p.capabilities.priority == 99
            assert p.capabilities.is_free
        except ImportError:
            pytest.skip("yfinance not installed")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_provider(name: str, priority: int,
                   tfs: set | None = None,
                   sessions: set | None = None,
                   adjustments: set | None = None) -> Provider:
    class _P(Provider):
        @property
        def capabilities(self):
            return ProviderCapabilities(
                name=name, priority=priority,
                timeframes=tfs or {"1day"},
                sessions=sessions or {"rth"},
                adjustments=adjustments or {"raw"},
            )

        def fetch_bars(self, *args, **kwargs):
            return pd.DataFrame()

    return _P()
