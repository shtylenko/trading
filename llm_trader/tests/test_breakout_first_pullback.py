"""Unit tests for breakout_first_pullback (no live provider)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import get_strategy, list_strategies
from trading.llm_trader.strategies.breakout_first_pullback.config import (
    BreakoutFirstPullbackConfig,
)
from trading.llm_trader.strategies.breakout_first_pullback.patterns import (
    detect_from_frame,
)
from trading.llm_trader.strategies.breakout_first_pullback.policy import (
    POLICY_ID,
    decisions_for_ticks,
)


def _idx(n: int, start: str = "2023-01-02"):
    return pd.bdate_range(start=start, periods=n, tz="America/New_York")


def _synthetic_base_breakout_pullback(n: int = 320):
    """Uptrend → flat base → breakout → pullback to base high → reclaim."""
    idx = _idx(n)
    px = 80.0
    # phases by bar index
    base_start = 230
    base_end = 255
    bo = 256
    pull_end = 262
    closes = []
    for i in range(n):
        if i < base_start:
            px *= 1.0035
        elif i <= base_end:
            # tight base around ~level
            px = px * 0.9995 + 0.0005 * (100 if i % 2 == 0 else -50)
            # keep roughly flat
            if i == base_start:
                base_px = px
            px = base_px * (1.0 + 0.02 * np.sin((i - base_start) / 5.0))
        elif i == bo:
            px = base_px * 1.04  # clear breakout
        elif i <= pull_end:
            # pull back toward base high
            t = (i - bo) / max(pull_end - bo, 1)
            px = base_px * 1.04 * (1 - 0.035 * t)
        else:
            px *= 1.004
        closes.append(float(px))
    closes = np.array(closes)
    # recompute base_px from series
    base_high = float(np.max(closes[base_start : base_end + 1]))
    # force breakout and pullback geometry on OHLC
    high = closes * 1.008
    low = closes * 0.992
    open_ = closes.copy()
    # base highs flat-ish
    for i in range(base_start, base_end + 1):
        high[i] = base_high * 1.001
        low[i] = base_high * 0.92
        closes[i] = base_high * (0.96 + 0.02 * (i % 3) / 3)
        open_[i] = closes[i] * 0.999
    # breakout day
    open_[bo] = base_high * 0.999
    closes[bo] = base_high * 1.025
    high[bo] = base_high * 1.03
    low[bo] = base_high * 0.995
    # pullback tags base high
    for i in range(bo + 1, pull_end + 1):
        high[i] = base_high * 1.02
        low[i] = base_high * 0.995  # tag
        closes[i] = base_high * 1.01
        open_[i] = base_high * 1.005
    # setup reclaim day
    plan = pull_end
    open_[plan] = base_high * 1.005
    closes[plan] = base_high * 1.015
    high[plan] = base_high * 1.022
    low[plan] = base_high * 0.998

    vol = np.full(n, 3_000_000.0)
    vol[bo] = 9_000_000.0
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": closes, "volume": vol},
        index=idx,
    )
    return df


def test_registered():
    assert "breakout_first_pullback" in list_strategies()
    s = get_strategy("breakout_first_pullback")
    assert s.horizon.kind == "multi_day"


def test_detect_emits_causal_plan():
    df = _synthetic_base_breakout_pullback()
    cfg = BreakoutFirstPullbackConfig(
        start=date(2023, 6, 1),
        end=date(2024, 12, 1),
        avg_vol_min=100_000.0,
        require_spy_above_sma50=False,
        require_spy_above_sma200=False,
        require_above_sma200=False,
        require_pullback_vol_below_breakout=False,
        breakout_vol_mult=1.2,
        breakout_clear_pct=0.1,
        base_range_min_pct=2.0,
        base_range_max_pct=25.0,
        entry_trigger_mode="setup_high",  # synthetic geometry easier with high trigger
    )
    entries = detect_from_frame(df, "TEST", cfg)
    assert entries, "expected at least one first-pullback plan"
    e = entries[0]
    assert e.strategy == "breakout_first_pullback"
    assert e.features["signal_kind"] == "prebreak_arm"
    for key in (
        "entry_trigger",
        "stop_px",
        "target1_px",
        "target2_px",
        "atr",
        "measured_move_px",
        "arm_expiry_bars",
        "max_entry_gap_atr",
        "breakout_level",
    ):
        assert e.features.get(key) is not None, key
    assert e.features["stop_px"] < e.features["entry_trigger"]
    assert e.features["target2_px"] > e.features["target1_px"]


def test_policy_arm():
    ticks = [
        {"i": 0, "time": "16:00", "is_setup_day": False},
        {
            "i": 1,
            "time": "16:00",
            "is_setup_day": True,
            "scanner_plan": {
                "signal_as_of": "2024-06-03",
                "trigger": 100.0,
                "stop": 94.0,
                "target1": 108.0,
                "target2": 115.0,
                "atr": 2.0,
                "measured_move_px": 7.0,
                "arm_expiry_bars": 5,
                "max_entry_gap_atr": 0.5,
            },
        },
        {"i": 2, "time": "16:00", "is_setup_day": False},
    ]
    rec = decisions_for_ticks(ticks)
    assert [r["action"] for r in rec] == ["OBSERVE", "ARM_BUY_STOP", "OBSERVE"]
    assert rec[1]["policy_id"] == POLICY_ID
