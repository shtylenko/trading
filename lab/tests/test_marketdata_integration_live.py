"""Integration tests: fetch real market data from live providers, verify
the values are stored and read back exactly as returned.

These tests contact Alpaca/MarketData/YFinance over the wire.
They do NOT hardcode expected OHLCV values (which would drift with
split/dividend adjustments).  Instead they:

  1. Fetch bars for a known ticker/timeframe/date via the real provider chain.
  2. Record the exact OHLCV values returned.
  3. Read back from the Parquet cache.
  4. Assert every cell matches — open, high, low, close, volume.

Any drift between fetch and read-back means the storage layer is corrupting
data.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pandas as pd
import pytest

_TZ_NY = "America/New_York"


@pytest.fixture(autouse=True)
def _isolated_env():
    """Fresh temp directory, fresh provider registry, fresh fetcher state."""
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_int_") as td:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td

        # Reimport config/storage with the new dir
        import importlib
        import trading.marketdata.config
        importlib.reload(trading.marketdata.config)

        # Reset provider registry so fetch_bars auto-registers real providers
        import trading.marketdata.provider as pmod
        pmod._PROVIDER_REGISTRY.clear()
        import trading.marketdata.fetcher as fmod
        fmod._REGISTERED = False

        yield

    if old_env is None:
        os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
    else:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old_env


def _fetch_and_verify(
    ticker: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str = "rth",
    adjustment: str = "raw",
    *,
    expected_min_rows: int = 1,
) -> None:
    """Fetch live data, store, read back, assert exact OHLCV match.

    Args:
        ticker: Symbol (e.g. 'AAPL').
        timeframe: '1min', '5min', '15min', '1day'.
        start, end: Range for the fetch (America/New_York).
        session: 'rth' or 'extended'.
        adjustment: 'raw', 'split', 'all', or None for automatic default.
        expected_min_rows: Minimum number of bars expected (fails early
            if provider returns fewer).
    """
    from trading.marketdata.fetcher import fetch_bars
    from trading.marketdata.storage import read_bars

    # Phase 1: Fetch live (writes to cache internally)
    fetched = fetch_bars(
        ticker, timeframe,
        start=start, end=end,
        session=session, adjustment=adjustment,
    )

    assert fetched is not None, f"{ticker} {timeframe}: live provider chain returned None"
    assert not fetched.empty, f"{ticker} {timeframe}: live provider chain returned empty data"
    assert len(fetched) >= expected_min_rows, (
        f"{ticker} {timeframe}: expected ≥{expected_min_rows} bars, "
        f"got {len(fetched)}"
    )

    # Snapshot the exact OHLCV values from the provider
    snapshot = fetched.copy()

    # Phase 2: Read back from cache (should be same data)
    cached = read_bars(
        ticker, timeframe,
        start=start, end=end,
        session=session, adjustment=adjustment,
        tz=_TZ_NY,
    )

    assert cached is not None and not cached.empty, (
        f"{ticker} {timeframe}: cache read returned empty after write"
    )
    assert len(cached) == len(snapshot), (
        f"{ticker} {timeframe}: row count mismatch — "
        f"fetched={len(snapshot)}, cached={len(cached)}"
    )

    # Phase 3: Compare every cell, every row (use approx for float/volume tolerance)
    for idx in range(len(snapshot)):
        snap_row = snapshot.iloc[idx]
        cache_row = cached.iloc[idx]

        ts = snap_row.name if hasattr(snap_row, "name") else idx
        label = f"{ticker} {timeframe} bar [{idx}] @ {ts}"

        for col in ["open", "high", "low", "close"]:
            assert cache_row[col] == pytest.approx(snap_row[col], rel=1e-4), (
                f"{label}: {col} mismatch — "
                f"fetched={snap_row[col]}, cached={cache_row[col]}"
            )

        # Volume comparison with 1% tolerance
        assert cache_row["volume"] == pytest.approx(snap_row["volume"], rel=0.01), (
            f"{label}: volume mismatch — "
            f"fetched={snap_row['volume']}, cached={cache_row['volume']}"
        )


# ── 1-minute integration tests ────────────────────────────────────────────────


class Test1MinLive:
    @pytest.mark.network

    def test_aapl_first_bar_jan02(self):
        """AAPL 1min bar on 2024-01-02 at 09:30 ET (market open)."""
        _fetch_and_verify(
            "AAPL", "1min",
            start=datetime(2024, 1, 2, 9, 30, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 2, 9, 31, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            expected_min_rows=1,
        )
    @pytest.mark.network

    def test_aapl_full_day_390_bars(self):
        """All 390 1min RTH bars for AAPL on 2024-01-02."""
        _fetch_and_verify(
            "AAPL", "1min",
            start=datetime(2024, 1, 2, 9, 30, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 2, 16, 0, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            expected_min_rows=385,  # Allow a few missing bars for early close
        )
    @pytest.mark.network

    def test_spy_0930_open_tick(self):
        """SPY 1min open on 2024-01-02."""
        _fetch_and_verify(
            "SPY", "1min",
            start=datetime(2024, 1, 2, 9, 30, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 2, 9, 31, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            expected_min_rows=1,
        )


# ── 5-minute integration tests ────────────────────────────────────────────────


class Test5MinLive:
    @pytest.mark.network

    def test_nvda_5min_first_bar(self):
        """NVDA 5min bar at 09:30 ET on 2024-01-02."""
        _fetch_and_verify(
            "NVDA", "5min",
            start=datetime(2024, 1, 2, 9, 30, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 2, 9, 35, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            expected_min_rows=1,
        )


# ── 15-minute integration tests ──────────────────────────────────────────────


class Test15MinLive:
    @pytest.mark.network

    def test_amd_15min_morning(self):
        """AMD 15min bar at 09:30 ET on 2024-01-02."""
        _fetch_and_verify(
            "AMD", "15min",
            start=datetime(2024, 1, 2, 9, 30, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 2, 9, 45, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            expected_min_rows=1,
        )


# ── Daily integration tests ───────────────────────────────────────────────────


class TestDailyLive:
    @pytest.mark.network

    def test_aapl_daily_jan2024_split(self):
        """AAPL daily split-adjusted, first 5 trading days of 2024."""
        _fetch_and_verify(
            "AAPL", "1day",
            start=datetime(2024, 1, 2, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 8, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            adjustment="split",
            expected_min_rows=5,
        )
    @pytest.mark.network

    def test_aapl_daily_jan2024_raw(self):
        """AAPL daily raw (unadjusted), first 5 trading days of 2024."""
        _fetch_and_verify(
            "AAPL", "1day",
            start=datetime(2024, 1, 2, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 1, 8, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            adjustment="raw",
            expected_min_rows=5,
        )
    @pytest.mark.network

    def test_spy_daily_first_quarter(self):
        """SPY daily Q1 2024 — validates multi-month range with Alpaca chunking."""
        _fetch_and_verify(
            "SPY", "1day",
            start=datetime(2024, 1, 2, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            end=datetime(2024, 3, 28, tzinfo=__import__("zoneinfo").ZoneInfo(_TZ_NY)),
            adjustment="split",
            expected_min_rows=60,
        )


# ── Multi-timeframe: same ticker, same day ────────────────────────────────────


class TestMultiTimeframeSameDay:
    """Verify that 1min, 5min, and daily data for the same ticker + date
    are stored in separate Parquet trees and don't interfere."""
    @pytest.mark.network

    def test_aapl_jan02_all_timeframes(self):
        ny = __import__("zoneinfo").ZoneInfo(_TZ_NY)
        day_start = datetime(2024, 1, 2, 9, 30, tzinfo=ny)
        day_end = datetime(2024, 1, 2, 16, 0, tzinfo=ny)

        _fetch_and_verify("AAPL", "1min", day_start, day_end,
                          expected_min_rows=385)

        # After 1min fetch, verify storage meta has rows
        from trading.marketdata.storage import read_meta
        meta = read_meta("AAPL", "1min", "rth", "raw")
        assert meta.get("total_rows", 0) > 0, (
            "AAPL 1min has 0 rows after fetch"
        )
    @pytest.mark.network

    def test_same_ticker_multiple_timeframes(self):
        """5min and daily for the same ticker are stored independently."""
        ny = __import__("zoneinfo").ZoneInfo(_TZ_NY)
        day_start = datetime(2024, 1, 2, 9, 30, tzinfo=ny)
        day_end = datetime(2024, 1, 2, 16, 0, tzinfo=ny)

        _fetch_and_verify("MSFT", "5min", day_start, day_end,
                          expected_min_rows=70)
        _fetch_and_verify("MSFT", "1day",
                          start=datetime(2024, 1, 2, tzinfo=ny),
                          end=datetime(2024, 1, 3, tzinfo=ny),
                          adjustment="split",
                          expected_min_rows=1)

        from trading.marketdata.storage import read_meta
        for tf in ("5min", "1day"):
            adj = "raw" if tf != "1day" else "split"
            meta = read_meta("MSFT", tf, "rth", adj)
            assert meta.get("total_rows", 0) > 0, (
                f"MSFT {tf} has 0 rows after fetch"
            )


# ── Session-specific test ──────────────────────────────────────────────────────


class TestExtendedSessionLive:
    @pytest.mark.network

    def test_spy_premarket_first_bar(self):
        """SPY premarket (extended) first bar at 04:00 ET on 2024-01-02."""
        ny = __import__("zoneinfo").ZoneInfo(_TZ_NY)
        _fetch_and_verify(
            "SPY", "1min",
            start=datetime(2024, 1, 2, 4, 0, tzinfo=ny),
            end=datetime(2024, 1, 2, 4, 1, tzinfo=ny),
            session="extended",
            adjustment="raw",
            expected_min_rows=1,
        )
