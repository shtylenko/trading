"""Unit tests for micro_pullback."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import list_strategies
from trading.llm_trader.strategies.micro_pullback.config import MicroPullbackConfig
from trading.llm_trader.strategies.micro_pullback.patterns import (
    DayCandidate,
    detect_from_frame,
)


def test_registered():
    assert "micro_pullback" in list_strategies()


def test_warrior_profile_defaults():
    from trading.llm_trader.strategies.micro_pullback.config import MicroPullbackConfig

    c = MicroPullbackConfig().apply_warrior_profile()
    assert c.universe_profile == "warrior"
    assert c.gap_min_pct == 5.0
    assert c.price_min == 2.0
    assert c.float_max == 20_000_000.0
    assert "entries_warrior" in str(c.db_path)


def test_detect_fires_on_synthetic_impulse_pb_break():
    n = 78
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.empty(n)
    # Impulse: climb 100 → 102 over first 8 bars
    close[:8] = np.linspace(100.0, 102.0, 8)
    # Micro-pullback 3 bars: shallow dip, no new high
    close[8:11] = [101.7, 101.5, 101.6]
    # Break bar: green through pb high (~101.7)
    close[11] = 102.3
    # rest drift
    close[12:] = np.linspace(102.3, 103.0, n - 12)

    open_ = np.empty(n)
    open_[:8] = close[:8] - 0.15
    open_[8:11] = close[8:11] + 0.05  # slightly red/flat pullback
    open_[11] = 101.55  # green break
    open_[12:] = close[12:] - 0.05

    high = np.maximum(open_, close) + 0.05
    # impulse highs climb; pb highs stay under 102
    high[:8] = close[:8] + 0.1
    high[8:11] = 101.75
    high[11] = 102.4
    high[12:] = close[12:] + 0.1

    low = np.minimum(open_, close) - 0.05
    low[8:11] = 101.4  # shallow vs impulse from 100

    # Fake VWAP rising under price
    typical = (high + low + close) / 3.0
    vwap = np.cumsum(typical * 1e5) / np.cumsum(np.full(n, 1e5))
    # keep vwap under lows during pullback
    vwap = np.minimum(vwap, low - 0.1)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1e5),
            "vwap": vwap,
        },
        index=idx,
    )
    cand = DayCandidate("TEST", date(2024, 6, 3), 100.0, 99.0, 1.0, 1.5, 2e6)
    cfg = MicroPullbackConfig(
        impulse_min_pct=0.3,
        impulse_min_bars=2,
        pb_max_bars=3,
        pb_max_depth_frac=0.7,
    )
    e = detect_from_frame(df, cand, cfg)
    assert e is not None, "synthetic impulse→pb→break should fire"
    assert e.pattern == "micro_pullback"
    assert e.features["stop_px"] < e.entry_px
    assert e.features["pb_bars"] >= 1
    hh, mm = map(int, e.time_et.split(":"))
    assert (hh, mm) < (14, 0)


def test_detect_no_crash_flat():
    n = 60
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.full(n, 100.0) + np.random.default_rng(0).normal(0, 0.02, n)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.05,
            "low": close - 0.05,
            "close": close,
            "volume": np.full(n, 1e5),
            "vwap": close - 0.01,
        },
        index=idx,
    )
    cand = DayCandidate("TEST", date(2024, 6, 3), 100.0, 99.5, 0.5, 1.3, 2e6)
    e = detect_from_frame(df, cand, MicroPullbackConfig())
    # flat day: either None or a valid structured trade
    if e is not None:
        assert e.features["stop_px"] < e.entry_px
