"""Tests for d13/d14: the first-bar close-position gate, standalone (d13) and
stacked on d11's SPY<50d regime gate (d14)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.lab.core.models import StrategyContext
from trading.lab.strategies import get_release_class, list_releases

from .conftest import make_daily_bars

NY = ZoneInfo("America/New_York")
TRADE_DATE = date(2024, 4, 1)


def _gap_day_bars(open_px=104.0, candle_hi=104.6, candle_lo=103.9, first_close=None):
    """Gap-up day (prior daily high = 102.0) with a green first candle.

    ``first_close`` controls where the FIRST 5m candle closes within its range,
    i.e. the close-position lever d13/d14 gate on. Defaults to near the high
    (matching the other drive-variant fixtures).
    """
    idx = pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=24, freq="5min", tz=NY)
    fc = candle_hi - 0.05 if first_close is None else first_close
    closes = np.concatenate([[fc], (candle_hi - 0.05) + np.cumsum(np.full(23, 0.15))])
    opens = np.empty_like(closes); opens[0] = open_px; opens[1:] = closes[:-1]
    highs = np.maximum(opens, closes) + 0.10; highs[0] = candle_hi
    lows = np.minimum(opens, closes) - 0.10; lows[0] = candle_lo
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "volume": 5e5}, index=idx)


def _spy_daily(below: bool):
    """60 daily SPY closes whose last value is below (or above) its 50d SMA."""
    idx = pd.date_range(end=TRADE_DATE - timedelta(days=1), periods=60, freq="D", tz=NY)
    closes = np.linspace(120, 100, 60) if below else np.linspace(100, 120, 60)
    return pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1,
                         "close": closes, "volume": 1e6}, index=idx)


def _ctx(release_id, bars=None, spy_daily=None):
    return StrategyContext(
        trade_date=TRADE_DATE, release_id=release_id, testset="unit",
        bars_5m={"AAPL": bars if bars is not None else _gap_day_bars()},
        daily={"AAPL": make_daily_bars()},
        spy_5m=None, spy_daily=spy_daily,
    )


def test_registered():
    assert {"d13", "d14"} <= set(list_releases())


class TestD13ClosePositionStandalone:
    def test_keeps_close_in_lower_range(self):
        # first candle closes at (104.2-103.9)/(104.6-103.9) = 0.43 <= 0.9
        bars = _gap_day_bars(first_close=104.2)
        cands = get_release_class("d13")().build_candidates(_ctx("d13", bars=bars))
        assert len(cands) == 1
        assert cands[0].features["first_close_pos"] < 0.9

    def test_drops_close_at_high(self):
        # default first close 104.55 -> pos 0.93 > 0.9 (top-decile exhaustion)
        assert get_release_class("d13")().build_candidates(_ctx("d13")) == []


class TestD14RegimePlusClosePosition:
    def test_keeps_when_weak_tape_and_room(self):
        bars = _gap_day_bars(first_close=104.2)
        cands = get_release_class("d14")().build_candidates(
            _ctx("d14", bars=bars, spy_daily=_spy_daily(below=True)))
        assert len(cands) == 1
        assert cands[0].features["spy_below_50d_sma"] is True
        assert cands[0].features["first_close_pos"] < 0.9

    def test_drops_close_at_high_even_when_weak_tape(self):
        # regime passes (SPY below 50d) but first bar closed at its high
        assert get_release_class("d14")().build_candidates(
            _ctx("d14", spy_daily=_spy_daily(below=True))) == []

    def test_drops_when_strong_tape(self):
        # geometry fine (room in the bar) but SPY above its 50d SMA -> no day
        bars = _gap_day_bars(first_close=104.2)
        assert get_release_class("d14")().build_candidates(
            _ctx("d14", bars=bars, spy_daily=_spy_daily(below=False))) == []

    def test_drops_when_no_spy_data(self):
        bars = _gap_day_bars(first_close=104.2)
        assert get_release_class("d14")().build_candidates(_ctx("d14", bars=bars)) == []
