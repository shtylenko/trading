"""Unit tests for trend_pullback family (no live provider calls)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import get_strategy, list_strategies
from trading.llm_trader.strategies.trend_pullback.config import TrendPullbackConfig
from trading.llm_trader.strategies.trend_pullback.patterns import detect_from_frame
from trading.llm_trader.strategies.trend_pullback.policy import (
    POLICY_ID,
    decisions_for_ticks,
)


def _daily_index(n: int, start: str = "2023-01-02"):
    return pd.bdate_range(start=start, periods=n, tz="America/New_York")


def _synthetic_pullback_ema20(n: int = 320):
    """Uptrend → mild pullback under EMA20 → reclaim (0.2.0 geometry)."""
    idx = _daily_index(n)
    px = 80.0
    pull_bars = 7
    phase1 = n - pull_bars - 20
    closes = []
    for i in range(n):
        if i < phase1:
            px *= 1.004
        elif i < phase1 + pull_bars:
            px *= 0.996
        else:
            px *= 1.006
        closes.append(px)
    closes = np.array(closes, dtype=float)
    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.008,
            "low": closes * 0.992,
            "close": closes,
            "volume": np.full(n, 3_000_000.0),
        },
        index=idx,
    )
    for i in range(phase1, phase1 + pull_bars):
        df.iloc[i, df.columns.get_loc("low")] = closes[i] * 0.985
    return df


def _synthetic_pullback_sma50(n: int = 360):
    """Deeper pullback that tags SMA50 while staying recoverable above SMA200."""
    idx = _daily_index(n)
    px = 80.0
    pull_bars = 12
    phase1 = n - pull_bars - 25
    closes = []
    for i in range(n):
        if i < phase1:
            px *= 1.0045
        elif i < phase1 + pull_bars:
            px *= 0.993  # deeper so SMA50 is tagged
        else:
            px *= 1.007
        closes.append(px)
    closes = np.array(closes, dtype=float)
    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(n, 3_000_000.0),
        },
        index=idx,
    )
    for i in range(phase1, phase1 + pull_bars):
        df.iloc[i, df.columns.get_loc("low")] = closes[i] * 0.97
    return df


def test_strategy_registered():
    assert "trend_pullback" in list_strategies()
    s = get_strategy("trend_pullback")
    assert s.horizon.kind == "multi_day"
    assert s.horizon.bar_resolution == "1day"


def test_detect_ema20_reproduces_02_construction():
    df = _synthetic_pullback_ema20()
    cfg = TrendPullbackConfig(
        start=date(2023, 6, 1),
        end=date(2024, 6, 1),
        avg_vol_min=100_000.0,
        require_spy_above_sma50=False,
        pullback_ma="ema20",
        max_pullback_bars=10,
        entry_trigger_mode="setup_high",
        target1_mode="prior_high",
    )
    entries = detect_from_frame(df, "TEST", cfg)
    assert entries, "expected at least one EMA20 pullback plan"
    e = entries[0]
    assert e.features["pullback_ma"] == "ema20"
    assert e.features["entry_trigger_mode"] == "setup_high"
    assert e.features["target1_mode"] == "prior_high"
    assert e.features["stop_px"] < e.features["entry_trigger"]
    assert e.features["target2_px"] > e.features["target1_px"]


def test_detect_sma50_default_040():
    df = _synthetic_pullback_sma50()
    cfg = TrendPullbackConfig(
        start=date(2023, 6, 1),
        end=date(2024, 12, 1),
        avg_vol_min=100_000.0,
        require_spy_above_sma50=False,
        # defaults are 0.4.0 sma50 + setup_high + prior_high
    )
    assert cfg.pullback_ma == "sma50"
    entries = detect_from_frame(df, "TEST", cfg)
    assert entries, "expected at least one SMA50 pullback plan on synthetic series"
    e = entries[0]
    assert e.strategy == "trend_pullback"
    assert e.features["signal_kind"] == "prebreak_arm"
    assert e.features["pullback_ma"] == "sma50"
    assert e.features["entry_trigger_mode"] == "setup_high"
    assert e.features["target1_mode"] == "prior_high"
    for key in (
        "entry_trigger",
        "stop_px",
        "target1_px",
        "target2_px",
        "atr",
        "measured_move_px",
        "arm_expiry_bars",
        "max_entry_gap_atr",
        "signal_as_of",
    ):
        assert e.features.get(key) is not None, key


def test_policy_arms_on_setup_tick():
    ticks = [
        {"i": 0, "time": "16:00", "is_setup_day": False},
        {
            "i": 1,
            "time": "16:00",
            "is_setup_day": True,
            "scanner_plan": {
                "signal_as_of": "2024-06-03",
                "trigger": 100.0,
                "stop": 95.0,
                "target1": 105.0,
                "target2": 110.0,
                "atr": 2.0,
                "measured_move_px": 5.0,
                "arm_expiry_bars": 5,
                "max_entry_gap_atr": 0.5,
            },
        },
        {"i": 2, "time": "16:00", "is_setup_day": False},
    ]
    records = decisions_for_ticks(ticks)
    assert [r["action"] for r in records] == ["OBSERVE", "ARM_BUY_STOP", "OBSERVE"]
    assert records[1]["trigger"] == 100.0
    assert records[1]["policy_id"] == POLICY_ID
