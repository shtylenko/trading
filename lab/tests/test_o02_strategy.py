from __future__ import annotations

from datetime import date, datetime
import pandas as pd
from zoneinfo import ZoneInfo

from trading.lab.core.models import Candidate, StrategyContext
from trading.lab.strategies import get_release_class
from trading.lab.research.filters import daily_atr_14

from .conftest import make_5m_bars, make_daily_bars

NY = ZoneInfo("America/New_York")


def _context(
    bars=None,
    daily=None,
) -> StrategyContext:
    return StrategyContext(
        trade_date=date(2024, 4, 1),
        release_id="o02",
        testset="unit",
        bars_5m={"AAPL": bars if bars is not None else make_5m_bars()},
        daily={"AAPL": daily if daily is not None else make_daily_bars()},
    )


def test_daily_atr_14():
    # Make daily bars with a clean volatility profile
    # Day TR ranges should be high - low
    # Let's construct a daily df manually
    idx = pd.date_range("2024-03-01", periods=16, freq="D", tz="America/New_York")
    daily = pd.DataFrame(
        {
            "open": [10.0] * 16,
            "high": [12.0] * 16,
            "low": [7.0] * 16,
            "close": [10.0] * 16,
            "volume": [1_500_000] * 16,
        },
        index=idx,
    )
    
    # Calculate ATR over 14 days before 2024-03-16
    atr = daily_atr_14(daily, period=14, trade_date=date(2024, 3, 16))
    assert atr == 5.0 # (12 - 7) = 5.0, mean over 14 days is 5.0


def test_o02_signal_position_sizing_and_leverage():
    release = get_release_class("o02")()
    candidate = Candidate(
        ticker="AAPL",
        score=2.5,
        features={"daily_atr_14": 4.0}, # ATR of 4.0
    )
    
    context = _context()
    # first 5m bar high is 101.0, low is 99.5
    signal = release.build_signal(context, candidate)
    
    assert signal is not None
    assert signal.entry_trigger == 101.0
    # stop loss: entry - 0.10 * atr = 101.0 - 0.40 = 100.60
    assert signal.stop_price == 100.60
    
    # risk per share = 101.0 - 100.60 = 0.40
    # risk budget = 100,000 * 0.01 = 1,000
    # shares = 1,000 / 0.40 = 2500 shares
    # required capital = 2500 * 101.0 = 252,500
    # leverage constraint: 252,500 / 100,000 = 2.525x (no cap needed)
    assert signal.metadata["shares"] == 2500
    assert signal.metadata["leverage"] == 2.525


def test_o02_signal_leverage_cap():
    release = get_release_class("o02")()
    candidate = Candidate(
        ticker="AAPL",
        score=2.5,
        # Set daily ATR to be small, making risk_per_share tiny, and leverage high
        features={"daily_atr_14": 0.51}, # ATR is 0.51
    )
    
    context = _context()
    # first bar: high 101.0, low 99.5
    # entry_trigger = 101.0
    # stop = 101.0 - 0.051 = 100.949
    # risk_per_share = 0.051
    # risk budget = 1000
    # shares = 1000 / 0.051 = 19607 shares
    # required capital = 19607 * 101.0 = 1,980,307 (exceeds 4x leverage limit of 400,000!)
    # capped shares = 400,000 / 101.0 = 3960 shares
    signal = release.build_signal(context, candidate)
    
    assert signal is not None
    assert signal.metadata["leverage"] <= 4.0
    assert signal.metadata["shares"] == 3960


def test_o02_candidate_rv_accepts_close_stamped_opening_bars():
    release = get_release_class("o02")()
    trade_date = date(2024, 4, 1)

    daily_idx = pd.bdate_range(end="2024-03-29", periods=16, tz=NY)
    daily = pd.DataFrame(
        {
            "open": [100.0] * 16,
            "high": [102.0] * 16,
            "low": [99.0] * 16,
            "close": [101.0] * 16,
            "volume": [2_000_000] * 16,
        },
        index=daily_idx,
    )

    hist_idx = pd.bdate_range(end="2024-03-29", periods=14, tz=NY).map(
        lambda ts: ts.replace(hour=9, minute=35)
    )
    historical_5m = pd.DataFrame(
        {
            "open": [100.0] * 14,
            "high": [101.0] * 14,
            "low": [99.0] * 14,
            "close": [100.5] * 14,
            "volume": [100_000] * 14,
        },
        index=pd.DatetimeIndex(hist_idx),
    )

    trade_bars = make_5m_bars(first_close=100.8)
    trade_bars.iloc[0, trade_bars.columns.get_loc("volume")] = 300_000

    context = StrategyContext(
        trade_date=trade_date,
        release_id="o02",
        testset="unit",
        bars_5m={"AAPL": trade_bars},
        daily={"AAPL": daily},
        historical_5m={"AAPL": historical_5m},
    )

    candidates = release.build_candidates(context)

    assert len(candidates) == 1
    assert candidates[0].ticker == "AAPL"
    assert candidates[0].features["rv"] == 3.0
