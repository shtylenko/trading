"""Tests for the d02-d04 post-gap-opening-drive variants: registry/config,
the RV filter (d02), uncapped target (d03), and hold-window (d04)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.lab.core.models import StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.strategies import get_release_class, list_releases

from .conftest import make_daily_bars

NY = ZoneInfo("America/New_York")
TRADE_DATE = date(2024, 4, 1)


def _gap_day_bars(first_volume: float = 1_000_000.0) -> pd.DataFrame:
    """A 1%+ gap-up day with a green first candle that breaks out and runs."""
    idx = pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=24, freq="5min", tz=NY)
    # prior daily high (make_daily_bars) = 102.0; open at 104 = ~2% gap up
    closes = np.concatenate([[104.5], 104.5 + np.cumsum(np.full(23, 0.15))])
    opens = np.empty_like(closes); opens[0] = 104.0; opens[1:] = closes[:-1]
    highs = np.maximum(opens, closes) + 0.20
    lows = np.minimum(opens, closes) - 0.20
    vol = np.full(24, 200_000.0); vol[0] = first_volume
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "volume": vol}, index=idx)


def _hist_5m(mean_open_vol: float) -> pd.DataFrame:
    """14 prior sessions, each with one 09:30 opening bar of the given volume."""
    days = pd.bdate_range(end=datetime(2024, 3, 29), periods=14)
    rows, idx = [], []
    for d in days:
        idx.append(pd.Timestamp(d.year, d.month, d.day, 9, 30, tz=NY))
        rows.append({"open": 100, "high": 100.5, "low": 99.5, "close": 100, "volume": mean_open_vol})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def _context(release_id, first_volume=1_000_000.0, hist_open_vol=None):
    hist = {}
    if hist_open_vol is not None:
        hist["AAPL"] = _hist_5m(hist_open_vol)
    return StrategyContext(
        trade_date=TRADE_DATE, release_id=release_id, testset="unit",
        bars_5m={"AAPL": _gap_day_bars(first_volume)},
        daily={"AAPL": make_daily_bars()},
        historical_5m=hist,
    )


def test_all_three_registered_and_configured():
    assert {"d02", "d03", "d04"} <= set(list_releases())
    assert get_release_class("d02")().min_rv == 2.0
    assert get_release_class("d02")().historical_5m_lookback_days == 14
    assert get_release_class("d03")().uncapped is True
    assert (get_release_class("d04")().exit_hour, get_release_class("d04")().exit_minute) == (15, 55)


class TestD02RelativeVolume:
    def test_keeps_high_rv_gap(self):
        # first bar 1M vs mean opening 200k -> RV 5 >= 2 : kept
        rel = get_release_class("d02")()
        cands = rel.build_candidates(_context("d02", first_volume=1_000_000, hist_open_vol=200_000))
        assert len(cands) == 1
        assert cands[0].features["rv"] >= 2.0

    def test_rejects_low_rv_gap(self):
        # first bar 250k vs mean opening 1M -> RV 0.25 < 2 : dropped
        rel = get_release_class("d02")()
        cands = rel.build_candidates(_context("d02", first_volume=250_000, hist_open_vol=1_000_000))
        assert cands == []

    def test_rejects_when_no_history(self):
        rel = get_release_class("d02")()
        assert rel.build_candidates(_context("d02", hist_open_vol=None)) == []


class TestD03Uncapped:
    def test_target_dropped(self):
        d01 = get_release_class("d01")()
        d03 = get_release_class("d03")()
        ctx1, ctx3 = _context("d01"), _context("d03")
        s1 = d01.build_signal(ctx1, d01.build_candidates(ctx1)[0])
        s3 = d03.build_signal(ctx3, d03.build_candidates(ctx3)[0])
        assert s1.target_price is not None  # d01 caps at 1R
        assert s3.target_price is None       # d03 uncapped


class TestD04HoldWindow:
    def test_cutoff_extended_to_1555(self):
        assert get_release_class("d01")().exit_cutoff(_context("d01")) == ny_dt(TRADE_DATE, 11, 30)
        assert get_release_class("d04")().exit_cutoff(_context("d04")) == ny_dt(TRADE_DATE, 15, 55)
