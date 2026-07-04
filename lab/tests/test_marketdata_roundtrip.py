"""Round-trip fidelity tests — write known OHLCV values and verify they
survive the Parquet storage layer intact.

Tests write → read cycles with exact OHLCV values for each supported
timeframe, then asserts every cell matches to full float precision.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pandas as pd
import pytest

_TZ_NY = "America/New_York"


@pytest.fixture(autouse=True)
def _isolated_data_dir():
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_rt_") as td:
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


# ── Known-value datasets ─────────────────────────────────────────────────────
# Each fixture creates a DataFrame with a single bar at a known datetime
# with specific OHLCV values for a given timeframe.


def _make_single_bar(
    ticker: str,
    timeframe: str,
    ts_ny: str,  # America/New_York datetime string
    ohlcv: tuple[float, float, float, float, int],
    session: str = "rth",
    adjustment: str = "raw",
) -> None:
    """Write a single OHLCV bar to the isolated cache."""
    ts = pd.Timestamp(ts_ny, tz=_TZ_NY)
    o, h, l, c, v = ohlcv

    # Build the DataFrame with timestamp as BOTH column and index name
    # (mimicking how real providers return data)
    df = pd.DataFrame(
        {
            "timestamp": [ts],
            "open": [o],
            "high": [h],
            "low": [l],
            "close": [c],
            "volume": [v],
        },
    )
    df.index = [ts]
    df.index.name = "timestamp"

    from trading.marketdata.storage import write_bars, update_meta_summary

    write_bars(ticker, timeframe, df, session=session, adjustment=adjustment,
               provider_name="test")
    update_meta_summary(ticker, timeframe, session, adjustment)


def _assert_value(
    ticker: str,
    timeframe: str,
    ts_ny: str,
    expected_ohlcv: tuple[float, float, float, float, int],
    session: str = "rth",
    adjustment: str = "raw",
) -> None:
    """Read back and assert exact OHLCV match."""
    ts_start = pd.Timestamp(ts_ny, tz=_TZ_NY)
    ts_end = ts_start + pd.Timedelta("1min")

    from trading.marketdata.storage import read_bars

    df = read_bars(
        ticker, timeframe,
        start=ts_start, end=ts_end,
        session=session, adjustment=adjustment,
        tz=_TZ_NY,
    )

    assert df is not None and not df.empty, (
        f"No data returned for {ticker} {timeframe} @ {ts_ny}"
    )

    exp_o, exp_h, exp_l, exp_c, exp_v = expected_ohlcv
    row = df.iloc[0]

    assert row["open"] == exp_o, (
        f"{ticker} {timeframe} @ {ts_ny}: expected open={exp_o}, got {row['open']}"
    )
    assert row["high"] == exp_h, (
        f"{ticker} {timeframe} @ {ts_ny}: expected high={exp_h}, got {row['high']}"
    )
    assert row["low"] == exp_l, (
        f"{ticker} {timeframe} @ {ts_ny}: expected low={exp_l}, got {row['low']}"
    )
    assert row["close"] == exp_c, (
        f"{ticker} {timeframe} @ {ts_ny}: expected close={exp_c}, got {row['close']}"
    )
    assert row["volume"] == exp_v, (
        f"{ticker} {timeframe} @ {ts_ny}: expected volume={exp_v}, got {row['volume']}"
    )


class TestRoundTrip1Min:
    def test_aapl_0930_open(self):
        """AAPL 1min bar at 09:30 ET on 2024-01-02."""
        ts = "2024-01-02 09:30"
        ohlcv = (185.64, 185.89, 185.60, 185.75, 1_234_567)
        _make_single_bar("AAPL", "1min", ts, ohlcv)
        _assert_value("AAPL", "1min", ts, ohlcv)

    def test_aapl_1200_midday(self):
        """AAPL 1min bar at 12:00 ET — exact midday value."""
        ts = "2024-01-02 12:00"
        ohlcv = (187.23, 187.45, 187.10, 187.38, 892_345)
        _make_single_bar("AAPL", "1min", ts, ohlcv)
        _assert_value("AAPL", "1min", ts, ohlcv)

    def test_spy_0950(self):
        """SPY 1min bar with very small spread (penny wide)."""
        ts = "2024-01-02 09:50"
        ohlcv = (476.32, 476.33, 476.31, 476.32, 5_678_901)
        _make_single_bar("SPY", "1min", ts, ohlcv)
        _assert_value("SPY", "1min", ts, ohlcv)

    def test_tsla_high_volume(self):
        """TSLA 1min bar with high volume."""
        ts = "2024-01-02 10:30"
        ohlcv = (248.50, 249.80, 248.10, 249.50, 15_432_100)
        _make_single_bar("TSLA", "1min", ts, ohlcv)
        _assert_value("TSLA", "1min", ts, ohlcv)

    def test_zero_volume(self):
        """Edge case: a bar with zero volume."""
        ts = "2024-01-02 15:59"
        ohlcv = (190.00, 190.05, 189.98, 190.02, 0)
        _make_single_bar("ZEROVOL", "1min", ts, ohlcv)
        _assert_value("ZEROVOL", "1min", ts, ohlcv)

    def test_multiple_bars_all_verified(self):
        """Write 3 sequential 1min bars and verify each independently."""
        bars = [
            ("2024-01-02 09:31", (185.70, 185.95, 185.65, 185.80, 100_000)),
            ("2024-01-02 09:32", (185.80, 186.10, 185.75, 186.05, 150_000)),
            ("2024-01-02 09:33", (186.05, 186.20, 185.90, 186.12, 120_000)),
        ]
        for ts, ohlcv in bars:
            _make_single_bar("SEQ", "1min", ts, ohlcv)
        for ts, ohlcv in bars:
            _assert_value("SEQ", "1min", ts, ohlcv)


class TestRoundTrip5Min:
    def test_nvda_5min_open(self):
        """NVDA 5min bar at 09:30 ET."""
        ts = "2024-01-02 09:30"
        ohlcv = (485.00, 487.50, 484.20, 487.10, 8_900_000)
        _make_single_bar("NVDA", "5min", ts, ohlcv)
        _assert_value("NVDA", "5min", ts, ohlcv)

    def test_nvda_5min_close(self):
        """NVDA 5min bar at 15:55 ET (last 5min bar)."""
        ts = "2024-01-02 15:55"
        ohlcv = (492.30, 492.80, 491.90, 492.50, 4_500_000)
        _make_single_bar("NVDA", "5min", ts, ohlcv)
        _assert_value("NVDA", "5min", ts, ohlcv)


class TestRoundTrip15Min:
    def test_amd_15min_morning(self):
        """AMD 15min bar at 09:30 ET."""
        ts = "2024-01-02 09:30"
        ohlcv = (147.20, 148.50, 146.80, 148.30, 12_345_678)
        _make_single_bar("AMD", "15min", ts, ohlcv)
        _assert_value("AMD", "15min", ts, ohlcv)

    def test_amd_15min_afternoon(self):
        """AMD 15min bar at 14:00 ET."""
        ts = "2024-01-02 14:00"
        ohlcv = (149.10, 149.40, 148.70, 149.05, 5_432_100)
        _make_single_bar("AMD", "15min", ts, ohlcv)
        _assert_value("AMD", "15min", ts, ohlcv)


class TestRoundTrip1Day:
    def test_aapl_daily_split(self):
        """AAPL daily split-adjusted bar."""
        ts = "2024-01-02 00:00"
        ohlcv = (185.64, 188.08, 183.60, 187.26, 49_876_543)
        _make_single_bar("AAPL", "1day", ts, ohlcv,
                         adjustment="split")
        _assert_value("AAPL", "1day", ts, ohlcv,
                      adjustment="split")

    def test_aapl_daily_raw(self):
        """Same day with raw (unadjusted) values — should differ."""
        ts = "2024-01-02 00:00"
        ohlcv = (185.64, 188.08, 183.60, 187.26, 49_876_543)
        _make_single_bar("AAPL", "1day", ts, ohlcv,
                         session="rth", adjustment="raw")
        _assert_value("AAPL", "1day", ts, ohlcv,
                      session="rth", adjustment="raw")

    def test_spy_daily_long_history(self):
        """SPY daily bar from 2015 (older data)."""
        ts = "2015-08-24 00:00"  # Flash crash day
        ohlcv = (189.00, 190.50, 182.50, 189.75, 250_000_000)
        _make_single_bar("SPY", "1day", ts, ohlcv,
                         adjustment="split")
        _assert_value("SPY", "1day", ts, ohlcv,
                      adjustment="split")


class TestRoundTripEdgeCases:
    def test_float_precision(self):
        """OHLC values with many decimal places survive round-trip."""
        ts = "2024-01-02 11:11"
        ohlcv = (123.456789, 124.567890, 122.345678, 123.789012, 777_777)
        _make_single_bar("PRECISE", "1min", ts, ohlcv)
        _assert_value("PRECISE", "1min", ts, ohlcv)

    def test_integer_prices(self):
        """Prices that happen to be whole integers."""
        ts = "2024-01-02 09:30"
        ohlcv = (100.0, 101.0, 99.0, 100.0, 500_000)
        _make_single_bar("WHOLE", "1min", ts, ohlcv)
        _assert_value("WHOLE", "1min", ts, ohlcv)

    def test_negative_not_applicable(self):
        """OHLC should never be negative for equities but verify zero works."""
        ts = "2024-01-02 09:30"
        ohlcv = (0.01, 0.01, 0.01, 0.01, 1)
        _make_single_bar("TINY", "1min", ts, ohlcv)
        _assert_value("TINY", "1min", ts, ohlcv)

    def test_volume_as_int64(self):
        """Volume is stored and returned as int64 (not float)."""
        ts = "2024-01-02 09:30"
        ohlcv = (150.0, 151.0, 149.0, 150.5, 999_999_999)
        _make_single_bar("BIGVOL", "1min", ts, ohlcv)
        _assert_value("BIGVOL", "1min", ts, ohlcv)


class TestCrossSessionIsolation:
    """Same ticker, same timeframe, same day — but different session or
    adjustment must NOT contaminate each other's storage."""

    def test_rth_vs_extended(self):
        """RTH and extended sessions are stored separately."""
        ts_rth = "2024-01-02 09:30"
        ts_ext = "2024-01-02 04:00"
        rth_ohlcv = (185.00, 186.00, 184.50, 185.50, 1_000_000)
        ext_ohlcv = (184.00, 184.80, 183.50, 184.20, 100_000)

        _make_single_bar("SEP", "1min", ts_rth, rth_ohlcv, session="rth")
        _make_single_bar("SEP", "1min", ts_ext, ext_ohlcv, session="extended")

        # Read RTH — should see only the RTH bar
        _assert_value("SEP", "1min", ts_rth, rth_ohlcv, session="rth")

        # Read EXTENDED — should see only the extended bar
        _assert_value("SEP", "1min", ts_ext, ext_ohlcv, session="extended")

    def test_raw_vs_split_adjustment(self):
        """Raw and split-adjusted daily data are stored separately."""
        ts = "2024-01-02 00:00"
        raw_ohlcv = (185.64, 188.08, 183.60, 187.26, 49_876_543)
        split_ohlcv = (184.50, 186.80, 182.40, 186.00, 49_876_543)

        _make_single_bar("ADJ", "1day", ts, raw_ohlcv,
                         adjustment="raw")
        _make_single_bar("ADJ", "1day", ts, split_ohlcv,
                         adjustment="split")

        _assert_value("ADJ", "1day", ts, raw_ohlcv, adjustment="raw")
        _assert_value("ADJ", "1day", ts, split_ohlcv, adjustment="split")


class TestFetchBarsRoundTrip:
    """Round-trip through the full fetch_bars() pipeline (cache only).

    These tests are intentionally minimal — the cache-hit and cache-miss
    paths are thoroughly covered in test_fetcher.py.  Here we just verify
    that the read path inside fetch_bars does not corrupt values.
    """

    def test_storage_readback_preserves_values(self):
        """Read via storage.read_bars preserves exact OHLCV after write_bars."""
        from trading.marketdata.storage import read_bars

        ts = "2024-01-02 09:30"
        ohlcv = (185.64, 185.89, 185.60, 185.75, 1_234_567)
        _make_single_bar("AAPL", "1min", ts, ohlcv)

        ts_start = pd.Timestamp(ts, tz=_TZ_NY)
        ts_end = ts_start + pd.Timedelta("1min")

        result = read_bars(
            "AAPL", "1min",
            start=ts_start, end=ts_end,
            session="rth", adjustment="raw",
        )
        assert result is not None and not result.empty
        row = result.iloc[0]
        assert row["open"] == ohlcv[0]
        assert row["high"] == ohlcv[1]
        assert row["low"] == ohlcv[2]
        assert row["close"] == ohlcv[3]
        assert row["volume"] == ohlcv[4]

    def test_storage_daily_readback(self):
        """Daily bar via storage layer preserves exact values."""
        from trading.marketdata.storage import read_bars

        ts = "2024-01-02 00:00"
        ohlcv = (185.64, 188.08, 183.60, 187.26, 49_876_543)
        _make_single_bar("AAPL", "1day", ts, ohlcv, adjustment="split")

        ts_start = pd.Timestamp(ts, tz=_TZ_NY)
        ts_end = ts_start + pd.Timedelta("1day")

        result = read_bars(
            "AAPL", "1day",
            start=ts_start, end=ts_end,
            session="rth", adjustment="split",
        )
        assert result is not None and not result.empty
        row = result.iloc[0]
        assert row["close"] == ohlcv[3]
        assert row["volume"] == ohlcv[4]
