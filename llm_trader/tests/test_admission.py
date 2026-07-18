"""Unit tests for structural admission (NML + portfolio)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.admission.no_mans_land import NmlConfig, evaluate_long_edge
from trading.llm_trader.admission.portfolio import PortfolioLimits, TimedTrade, apply_portfolio_limits


def _frame_range(low: float, high: float, n: int = 20, close_at: float | None = None):
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    mid = 0.5 * (low + high)
    close = np.full(n, close_at if close_at is not None else mid)
    high_a = np.full(n, high)
    low_a = np.full(n, low)
    # last bar can break out
    return pd.DataFrame(
        {
            "open": close,
            "high": high_a,
            "low": low_a,
            "close": close,
            "volume": np.full(n, 1e5),
        },
        index=idx,
    )


def test_nml_rejects_mid_range_long():
    df = _frame_range(100.0, 110.0, n=20, close_at=105.0)
    d = evaluate_long_edge(df, signal_i=19, entry_px=105.0, cfg=NmlConfig())
    assert d.admit is False
    assert d.reason == "mid_range_nml"
    assert 0.4 < d.position < 0.6


def test_nml_admits_upper_edge():
    df = _frame_range(100.0, 110.0, n=20, close_at=108.5)
    d = evaluate_long_edge(df, signal_i=19, entry_px=108.5, cfg=NmlConfig())
    assert d.admit is True
    assert d.is_upper_edge
    assert d.reason in ("upper_edge", "breakout", "tight_upper_or_breakout")


def test_nml_admits_breakout():
    n = 20
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    high = np.full(n, 105.0)
    low = np.full(n, 100.0)
    close = np.full(n, 103.0)
    # last bar breaks prior high
    high[-1] = 106.5
    close[-1] = 106.0
    low[-1] = 104.0
    df = pd.DataFrame(
        {"open": close - 0.2, "high": high, "low": low, "close": close, "volume": np.full(n, 1e5)},
        index=idx,
    )
    d = evaluate_long_edge(df, signal_i=n - 1, entry_px=106.0, cfg=NmlConfig())
    assert d.admit is True
    assert d.is_breakout


def test_portfolio_caps_concurrent_and_daily():
    day = date(2024, 6, 3)
    trades = [
        TimedTrade("A", day, "10:00", "11:00", 0.1, rvol=2.0),
        TimedTrade("B", day, "10:05", "11:00", 0.1, rvol=1.5),
        TimedTrade("C", day, "10:10", "11:00", 0.1, rvol=1.2),
        TimedTrade("D", day, "10:15", "11:00", 0.1, rvol=1.0),  # 4th concurrent → reject
        TimedTrade("E", day, "12:00", "13:00", 0.1, rvol=3.0),  # after free slot
    ]
    kept, rej = apply_portfolio_limits(trades, PortfolioLimits(max_concurrent=3, max_per_day=10))
    assert len(kept) == 4
    assert any(t.ticker == "D" for t in rej)
    assert any(t.ticker == "E" for t in kept)


def test_portfolio_clears_overnight():
    d1, d2 = date(2024, 6, 3), date(2024, 6, 4)
    trades = [
        TimedTrade("A", d1, "10:00", "15:55", 0.1, rvol=1.0),
        TimedTrade("B", d1, "10:05", "15:55", 0.1, rvol=1.0),
        TimedTrade("C", d1, "10:10", "15:55", 0.1, rvol=1.0),
        # next day must not be blocked by prior-day open exits
        TimedTrade("D", d2, "10:00", "11:00", 0.2, rvol=1.0),
    ]
    kept, rej = apply_portfolio_limits(trades, PortfolioLimits(max_concurrent=3, max_per_day=5))
    assert any(t.ticker == "D" for t in kept)
    assert not any(t.ticker == "D" for t in rej)
