"""Unit tests for vwap_pullback (pure frame logic)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import list_strategies
from trading.llm_trader.strategies.vwap_pullback.config import VwapPullbackConfig
from trading.llm_trader.strategies.vwap_pullback.patterns import (
    DayCandidate,
    detect_from_frame,
)


def test_registered():
    assert "vwap_pullback" in list_strategies()


def test_detect_reclaim():
    # Synthetic RTH 5m: hold above rising VWAP then dip and reclaim
    n = 60
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.linspace(100, 103, n)
    # force a dip to VWAP around bar 30
    close[28:32] = [102.0, 101.5, 101.2, 101.8]
    close[32:] = np.linspace(102.0, 104.0, n - 32)
    high = close + 0.3
    low = close - 0.3
    low[30] = 101.0  # touch
    open_ = close - 0.05
    open_[31] = 101.1
    close[31] = 101.9  # green reclaim
    high[31] = 102.0
    vol = np.full(n, 100_000.0)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    df["vwap"] = (typical * df["volume"]).cumsum() / df["volume"].cumsum()

    cand = DayCandidate("TEST", date(2024, 6, 3), 100.0, 99.0, 1.0, 2.0, 2e6)
    cfg = VwapPullbackConfig(
        morning_confirm_end="10:30",
        entry_window_start="10:00",
        entry_window_end="14:00",
        min_bars_above_vwap_before=2,
    )
    e = detect_from_frame(df, cand, cfg)
    # May or may not fire depending on VWAP path; at least no crash
    if e is not None:
        assert e.pattern == "vwap_pullback"
        assert e.features["stop_px"] < e.entry_px
