"""Tests for C1 chart-structure filters."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.indicators import enrich_daily
from trading.swing_screener.c1_pullback.rules import C1Config, load_config, shared_mask
from trading.swing_screener.c1_pullback.structure import (
    StructureConfig,
    add_structure_columns,
    structure_mask,
)


def _uptrend_with_orderly_pullback(n: int = 260) -> pd.DataFrame:
    """Synthetic leader: grind up, then 3 quiet down days into SMA20 zone."""
    rng = np.random.default_rng(7)
    close = np.cumsum(np.maximum(rng.normal(0.15, 0.05, n), 0.02)) + 40.0
    # last 3 days: orderly pullback
    close[-3] = close[-4] * 0.995
    close[-2] = close[-3] * 0.994
    close[-1] = close[-2] * 0.993
    high = close + 0.3
    high[-4] = close[-4] + 0.8  # local high before pullback
    low = close - 0.3
    vol = np.full(n, 1_500_000.0)
    vol[-10:-3] = 1_800_000.0  # advance volume
    vol[-3:] = 900_000.0  # dry-up
    df = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        },
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    return enrich_daily(df)


def test_structure_columns_present():
    df = _uptrend_with_orderly_pullback()
    for col in (
        "struct_rising_sma50",
        "struct_higher_high",
        "struct_pullback_len",
        "struct_not_collapse",
        "struct_vol_contract",
        "struct_near_support",
        "struct_above_swing_low",
        "struct_ok",
        "ema20",
        "days_since_high",
    ):
        assert col in df.columns


def test_collapse_day_fails_not_collapse():
    df = _uptrend_with_orderly_pullback()
    # Smash last day -15%
    df = df.copy()
    df.iloc[-1, df.columns.get_loc("close")] = float(df["close"].iloc[-2]) * 0.85
    df.iloc[-1, df.columns.get_loc("low")] = float(df["close"].iloc[-1]) - 0.1
    # re-enrich from OHLCV only
    raw = df[["open", "high", "low", "close", "volume"]].copy()
    raw.iloc[-1, raw.columns.get_loc("close")] = float(df["close"].iloc[-2]) * 0.85
    raw.iloc[-1, raw.columns.get_loc("low")] = raw["close"].iloc[-1] - 0.1
    raw.iloc[-1, raw.columns.get_loc("high")] = raw["close"].iloc[-1] + 0.1
    en = enrich_daily(raw)
    assert not bool(en["struct_not_collapse"].iloc[-1])


def test_structure_disabled_passes():
    df = _uptrend_with_orderly_pullback()
    m = structure_mask(df, StructureConfig(enabled=False))
    assert m.all()


def test_load_config_structure_enabled():
    cfg = load_config()
    assert cfg.structure.enabled is True
    assert cfg.rules_version.startswith("c1_pullback_v2")
    assert cfg.structure.pullback_bars_min == 2
    assert cfg.structure.pullback_bars_max == 5


def test_shared_mask_uses_structure():
    df = _uptrend_with_orderly_pullback()
    cfg = C1Config()
    m = shared_mask(df, cfg)
    # mask should be subset of struct_ok when structure enabled
    if m.any():
        assert df.loc[m, "struct_ok"].all()
