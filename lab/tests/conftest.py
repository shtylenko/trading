"""Shared pytest configuration for strategy_lab tests.

Register custom markers, provide common fixtures, and define helper
functions for constructing test DataFrames.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta

import pandas as pd
import pytest
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


# ── pytest configuration ─────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: tests that require live network/API access (skip with -m 'not network')",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip network tests unless --run-network is passed."""
    if config.getoption("--run-network", default=False):
        return
    skip_network = pytest.mark.skip(reason="network test (use --run-network to enable)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_network)


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="Run network-dependent tests that contact live APIs",
    )


# ── Test data factories ──────────────────────────────────────────────────────


def _make_5m_index(start_hour: int = 9, start_min: int = 30, periods: int = 10):
    """Generate a DatetimeIndex of 5-minute bars in America/New_York."""
    start = datetime(2024, 4, 1, start_hour, start_min, tzinfo=NY)
    return pd.date_range(start=start, periods=periods, freq="5min", tz=NY)


def make_5m_bars(
    first_open: float = 100.0,
    first_high: float = 101.0,
    first_low: float = 99.5,
    first_close: float = 100.8,
    **kwargs,
) -> pd.DataFrame:
    """Return a DataFrame of 5-minute OHLCV bars for testing.

    The first bar is the "opening range" bar with configurable OHLC.
    Subsequent bars trend gently upward with modest volatility so that
    breakout, stop-loss, and time-exit scenarios all exercise normally.

    Any keyword argument matching ``first_<col>`` overrides the first
    bar's value for that column.
    """
    if "first_open" in kwargs:
        first_open = kwargs["first_open"]
    if "first_high" in kwargs:
        first_high = kwargs["first_high"]
    if "first_low" in kwargs:
        first_low = kwargs["first_low"]
    if "first_close" in kwargs:
        first_close = kwargs["first_close"]

    idx = _make_5m_index(periods=10)
    n = len(idx)
    data = {
        "open": [first_open] + [100.9 + i * 0.1 for i in range(1, n)],
        "high": [first_high] + [101.2 + i * 0.2 for i in range(1, n)],
        "low": [first_low] + [100.5 + i * 0.05 for i in range(1, n)],
        "close": [first_close] + [101.0 + i * 0.15 for i in range(1, n)],
        "volume": [500_000] * n,
    }
    return pd.DataFrame(data, index=idx)


def make_daily_bars(
    prior_high: float = 102.0,
    latest_close: float = 101.0,
    periods: int = 16,
    **kwargs,
) -> pd.DataFrame:
    """Return a DataFrame of daily OHLCV bars for testing.

    The index covers *periods* prior business days ending on 2024-03-29
    (the day before the default test trade_date of 2024-04-01). Values
    are chosen to pass the Stocks-in-Play v1 filter gauntlet (price > $5,
    14-day avg vol >= 1M, ATR > $0.50, green first candle, RV >= 2.0).

    Keyword arguments:
        prior_high: The 'high' value for all rows (default 102.0).
        latest_close: The 'close' value for all rows (default 101.0).
    """
    idx = pd.bdate_range(end="2024-03-29", periods=periods, tz=NY)
    n = len(idx)
    data = {
        "open": [100.0] * n,
        "high": [prior_high] * n,
        "low": [99.0] * n,
        "close": [latest_close] * n,
        "volume": [2_000_000] * n,
    }
    return pd.DataFrame(data, index=idx)
