"""Tests for d07-d10: the candidate-time filter gates (gap ceiling,
relative-SPY gap, and the ATR-fraction band on the opening candle)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.lab.core.models import StrategyContext
from trading.lab.strategies import get_release_class, list_releases

from .conftest import make_daily_bars

NY = ZoneInfo("America/New_York")
TRADE_DATE = date(2024, 4, 1)


def _gap_day_bars(open_px=104.0, candle_hi=104.6, candle_lo=103.9):
    """A gap-up day (prior daily high = 102.0) with a green first candle."""
    idx = pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=24, freq="5min", tz=NY)
    closes = np.concatenate([[candle_hi - 0.05], (candle_hi - 0.05) + np.cumsum(np.full(23, 0.15))])
    opens = np.empty_like(closes); opens[0] = open_px; opens[1:] = closes[:-1]
    highs = np.maximum(opens, closes) + 0.10; highs[0] = candle_hi
    lows = np.minimum(opens, closes) - 0.10; lows[0] = candle_lo
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "volume": 5e5}, index=idx)


def _spy_bars(open_px, prior_high):
    idx = pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=2, freq="5min", tz=NY)
    return pd.DataFrame({"open": [open_px, open_px], "high": [open_px + 1, open_px + 1],
                         "low": [open_px - 1, open_px - 1], "close": [open_px, open_px],
                         "volume": 1e6}, index=idx), prior_high


def _ctx(release_id, bars=None, spy5=None, spy_daily=None):
    return StrategyContext(
        trade_date=TRADE_DATE, release_id=release_id, testset="unit",
        bars_5m={"AAPL": bars if bars is not None else _gap_day_bars()},
        daily={"AAPL": make_daily_bars()},
        spy_5m=spy5, spy_daily=spy_daily,
    )


def test_registered():
    assert {"d07", "d08", "d09", "d10"} <= set(list_releases())


class TestD07GapCeiling:
    def test_keeps_moderate_gap(self):
        # open 104 vs prior high 102 = ~2% gap, under the 8% ceiling
        assert len(get_release_class("d07")().build_candidates(_ctx("d07"))) == 1

    def test_drops_exhaustion_gap(self):
        # open 114 vs 102 = ~11.8% gap > 8% ceiling
        bars = _gap_day_bars(open_px=114.0, candle_hi=114.6, candle_lo=113.9)
        assert get_release_class("d07")().build_candidates(_ctx("d07", bars=bars)) == []


class TestD08RelativeSpy:
    def _daily(self):  # SPY daily with a prior-day row (high used for SPY gap)
        d = make_daily_bars(); return d

    def test_keeps_when_stock_outgaps_spy(self):
        # stock ~2% gap; SPY flat (open=prior high) -> spy_gap≈0 -> passes
        spy5, _ = _spy_bars(100.0, 100.0)
        spyd = make_daily_bars()  # last high = 102; SPY first open 100 -> negative gap
        assert len(get_release_class("d08")().build_candidates(
            _ctx("d08", spy5=spy5, spy_daily=spyd))) == 1

    def test_drops_when_macro_beta(self):
        # SPY gaps hugely (open 130 vs prior high 102 ≈ +27%); stock's ~2% < 2×27%
        spy5, _ = _spy_bars(130.0, 0)
        spyd = make_daily_bars()
        assert get_release_class("d08")().build_candidates(
            _ctx("d08", spy5=spy5, spy_daily=spyd)) == []

    def test_skips_when_no_spy_data(self):
        assert get_release_class("d08")().build_candidates(_ctx("d08")) == []


class TestD09D10CandleBand:
    # make_daily_bars ATR14 is ~ a few dollars; pick candle ranges around it.
    def test_d09_drops_wide_candle(self):
        wide = _gap_day_bars(open_px=104.0, candle_hi=112.0, candle_lo=103.0)  # range 9
        assert get_release_class("d09")().build_candidates(_ctx("d09", bars=wide)) == []

    def test_d09_keeps_normal_candle(self):
        assert len(get_release_class("d09")().build_candidates(_ctx("d09"))) == 1

    def test_d10_drops_tight_candle(self):
        tight = _gap_day_bars(open_px=104.0, candle_hi=104.10, candle_lo=104.0)  # range 0.10
        assert get_release_class("d10")().build_candidates(_ctx("d10", bars=tight)) == []
