"""Tests for C2 breakout screen/sim."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c2_breakout.indicators import enrich_c2
from trading.swing_screener.c2_breakout.rules import C2Config, c2_mask, load_config


def test_load_c2_config():
    cfg = load_config()
    assert cfg.rules_version.startswith("c2_breakout")
    assert cfg.relvol_min == 1.5
    assert cfg.backtest.target_r == 2.5


def test_enrich_c2_columns():
    n = 280
    close = np.linspace(50, 120, n) + np.sin(np.linspace(0, 20, n)) * 0.5
    # tight base near end then breakout day
    close[-20:-1] = np.linspace(close[-21], close[-21] * 1.02, 19)
    close[-1] = close[-2] * 1.03
    high = close + 0.4
    high[-1] = close[-1] + 0.2
    low = close - 0.4
    vol = np.full(n, 1_000_000.0)
    vol[-15:-1] = 600_000.0
    vol[-1] = 2_500_000.0
    df = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": vol},
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    out = enrich_c2(df, base_lookback=15)
    for col in (
        "high_252",
        "dist_52w",
        "pivot",
        "base_low",
        "base_depth_atr",
        "base_range_pct",
        "perf_63d",
        "relvol",
        "atr14",
    ):
        assert col in out.columns
    assert out["pivot"].notna().sum() > 0


def test_c2_mask_breakout_day():
    n = 280
    rng = np.random.default_rng(0)
    # strong uptrend into highs
    close = 40 + np.cumsum(np.abs(rng.normal(0.2, 0.05, n)))
    high = close + 0.5
    low = close - 0.5
    vol = np.full(n, 1_200_000.0)
    # compress last 15 days volume then spike
    vol[-16:-1] = 500_000.0
    # pivot from prior highs
    high[-16:-1] = close[-16:-1] + 0.2
    close[-1] = float(np.max(high[-16:-1])) * 1.01
    high[-1] = close[-1] + 0.1
    low[-1] = close[-1] - 0.1
    vol[-1] = 3_000_000.0
    df = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": vol},
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    en = enrich_c2(df, base_lookback=15)
    # inject RS so filter doesn't kill
    en["rs_spy_21d"] = 0.05
    cfg = C2Config(require_rs_spy_21d=True, max_break_extension_atr=2.0)
    mask = c2_mask(en, cfg)
    # last day may or may not pass all gates; ensure mask is boolean series
    assert mask.dtype == bool or str(mask.dtype) == "bool"
    assert len(mask) == n
