"""Unit tests for inplay_continuation."""

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import list_strategies
from trading.llm_trader.strategies.inplay_continuation.config import InplayContinuationConfig
from trading.llm_trader.strategies.inplay_continuation.patterns import (
    DayCandidate,
    detect_from_frame,
)


def test_registered():
    assert "inplay_continuation" in list_strategies()


def test_config_webull_defaults():
    c = InplayContinuationConfig()
    assert c.gap_min_pct == 5.0
    assert c.slippage_bps_one_way == 15.0
    m = c.cost_model()
    assert m.commission_bps_buy == 0.0


def test_detect_fires_synthetic():
    n = 78
    idx = pd.date_range("2025-08-04 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.empty(n)
    close[:8] = np.linspace(10.0, 10.25, 8)  # impulse ~2.5%
    close[8:11] = [10.20, 10.15, 10.18]
    close[11] = 10.30
    close[12:] = np.linspace(10.30, 10.5, n - 12)
    open_ = close.copy()
    open_[:8] = close[:8] - 0.02
    open_[8:11] = close[8:11] + 0.01
    open_[11] = 10.16
    open_[12:] = close[12:] - 0.01
    high = np.maximum(open_, close) + 0.02
    high[:8] = close[:8] + 0.03
    high[8:11] = 10.22
    high[11] = 10.32
    low = np.minimum(open_, close) - 0.02
    low[8:11] = 10.12
    typical = (high + low + close) / 3.0
    vwap = np.cumsum(typical * 1e5) / np.cumsum(np.full(n, 1e5))
    vwap = np.minimum(vwap, low - 0.05)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(n, 1e5), "vwap": vwap},
        index=idx,
    )
    cand = DayCandidate("TEST", date(2025, 8, 4), 10.0, 9.0, 11.0, 3.0, 2e6)
    cfg = InplayContinuationConfig(impulse_min_pct=0.5, pb_max_depth_frac=0.8)
    e = detect_from_frame(df, cand, cfg)
    assert e is not None
    assert e.pattern == "inplay_continuation"
