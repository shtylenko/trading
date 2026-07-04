"""Unit tests for trading.marketdata.calendar."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest
import zoneinfo

from trading.marketdata.calendar import (
    coverage_gaps,
    expected_bars,
    is_early_close,
    is_trading_day,
    session_close_utc,
    session_open_utc,
    trading_days_in_range,
)

_NY = zoneinfo.ZoneInfo("America/New_York")


class TestTradingCalendar:
    def test_is_trading_day_true(self):
        assert is_trading_day(date(2024, 1, 2)) is True  # Tuesday

    def test_is_trading_day_weekend(self):
        # Saturday
        assert is_trading_day(date(2024, 1, 6)) is False
        # Sunday
        assert is_trading_day(date(2024, 1, 7)) is False

    def test_is_trading_day_holiday(self):
        # New Year's Day
        assert is_trading_day(date(2024, 1, 1)) is False
        # Christmas
        assert is_trading_day(date(2024, 12, 25)) is False

    def test_session_open_close_utc(self):
        open_dt = session_open_utc(date(2024, 1, 2))
        close_dt = session_close_utc(date(2024, 1, 2))
        # 09:30 ET = 14:30 UTC
        assert open_dt.hour == 14
        assert open_dt.minute == 30
        # 16:00 ET = 21:00 UTC
        assert close_dt.hour == 21
        assert close_dt.minute == 0

    def test_trading_days_in_range_jan2024(self):
        days = trading_days_in_range(date(2024, 1, 1), date(2024, 1, 31))
        assert len(days) == 21
        assert date(2024, 1, 1) not in days  # holiday
        assert date(2024, 1, 15) not in days  # MLK day

    def test_is_early_close(self):
        # Normal day
        assert is_early_close(date(2024, 1, 2)) is False
        # Normal summer day closes at 20:00 UTC / 16:00 ET, not an early close
        assert is_early_close(date(2024, 7, 1)) is False
        # Black Friday 2024 (early close at 13:00 ET)
        assert is_early_close(date(2024, 11, 29)) is True
        # Christmas Eve 2024 (early close)
        assert is_early_close(date(2024, 12, 24)) is True

    def test_non_trading_day_raises(self):
        from trading.marketdata.errors import CalendarError

        with pytest.raises(CalendarError):
            session_open_utc(date(2024, 1, 1))  # Holiday


class TestExpectedBars:
    def test_daily_bars_jan2024(self):
        bars = expected_bars(
            "1day",
            datetime(2024, 1, 1, tzinfo=_NY),
            datetime(2024, 1, 31, tzinfo=_NY),
            session="rth",
        )
        assert len(bars) == 21
        # Works for both pytz (.zone) and zoneinfo (.key) tzinfo objects.
        assert str(bars[0].tz) == "America/New_York"

    def test_1min_bars_one_day(self):
        bars = expected_bars(
            "1min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        # 390 minutes in RTH (09:30 to 16:00)
        assert len(bars) == 390
        assert bars[0].hour == 9
        assert bars[0].minute == 30
        assert bars[-1].hour == 15
        assert bars[-1].minute == 59

    def test_5min_bars_one_day(self):
        bars = expected_bars(
            "5min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        # 390 / 5 = 78 bars
        assert len(bars) == 78

    def test_1min_partial_window(self):
        bars = expected_bars(
            "1min",
            datetime(2024, 1, 2, 11, 0, tzinfo=_NY),
            datetime(2024, 1, 2, 12, 59, tzinfo=_NY),
            session="rth",
        )
        assert len(bars) == 120
        assert bars[0].hour == 11
        assert bars[0].minute == 0
        assert bars[-1].hour == 12
        assert bars[-1].minute == 59

    def test_1min_extended_session(self):
        bars = expected_bars(
            "1min",
            datetime(2024, 6, 3, 4, 0, tzinfo=_NY),  # Summer — 04:00 ET = 08:00 UTC
            datetime(2024, 6, 3, 16, 0, tzinfo=_NY),
            session="extended",
        )
        # Extended: 04:00-16:00 ET = 720 bars (summer)
        assert 715 <= len(bars) <= 725
        assert bars[0].hour == 4
        assert bars[0].minute == 0

    def test_empty_range_no_trading_days(self):
        bars = expected_bars(
            "1day",
            datetime(2024, 1, 6, tzinfo=_NY),  # Saturday
            datetime(2024, 1, 7, tzinfo=_NY),  # Sunday
            session="rth",
        )
        assert len(bars) == 0

    def test_out_of_calendar_range(self):
        """Before exchange_calendars earliest session — returns empty."""
        from trading.marketdata.errors import CalendarError

        with pytest.raises(CalendarError):
            expected_bars(
                "1day",
                datetime(1999, 1, 1, tzinfo=_NY),
                datetime(1999, 1, 5, tzinfo=_NY),
                session="rth",
            )


class TestCoverageGaps:
    def test_no_gaps(self):
        bars = expected_bars(
            "1min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        gaps = coverage_gaps(
            bars,
            "1min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        assert len(gaps) == 0

    def test_first_100_bars_only(self):
        all_bars = expected_bars(
            "1min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        partial = all_bars[:100]
        gaps = coverage_gaps(
            partial,
            "1min",
            datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
            session="rth",
        )
        assert len(gaps) == 290  # 390 - 100

    def test_negative_cache_skips_date(self):
        """Expected bars for a non-trading date are suppressed by negative cache."""
        # 2024-01-01 is New Year's Day — no expected bars
        bars = expected_bars(
            "1min",
            datetime(2024, 1, 1, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 1, 16, 0, tzinfo=_NY),
            session="rth",
        )
        actual = pd.DatetimeIndex([])  # No actual data
        gaps = coverage_gaps(
            actual,
            "1min",
            datetime(2024, 1, 1, 9, 30, tzinfo=_NY),
            datetime(2024, 1, 1, 16, 0, tzinfo=_NY),
            session="rth",
            negative_cache={"2024-01-01": {"reason": "non_trading_day"}},
        )
        assert len(gaps) == 0  # Not a trading day, no expected bars generated

    def test_daily_gaps(self):
        bars = expected_bars(
            "1day",
            datetime(2024, 1, 1, tzinfo=_NY),
            datetime(2024, 1, 31, tzinfo=_NY),
            session="rth",
        )
        # Only first 10 days
        partial = bars[:10]
        gaps = coverage_gaps(
            partial,
            "1day",
            datetime(2024, 1, 1, tzinfo=_NY),
            datetime(2024, 1, 31, tzinfo=_NY),
            session="rth",
        )
        assert len(gaps) == 11  # 21 - 10
