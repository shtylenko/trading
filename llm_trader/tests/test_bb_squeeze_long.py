"""Unit tests for bb_squeeze_long."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.llm_trader.strategies import list_strategies
from trading.llm_trader.strategies.bb_squeeze_long.config import BbSqueezeLongConfig
from trading.llm_trader.strategies.bb_squeeze_long.patterns import (
    DayCandidate,
    _bb_width_pctile,
    add_bollinger,
    detect_from_frame,
)


def test_registered():
    assert "bb_squeeze_long" in list_strategies()


def test_add_bollinger():
    n = 80
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.concatenate([np.full(40, 100.0), np.linspace(100, 105, 40)])
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(n, 1e5),
        },
        index=idx,
    )
    out = add_bollinger(df)
    assert "bb_mid" in out.columns
    assert out["bb_mid"].notna().sum() > 0


def test_bb_width_pctile_causal_low_on_squeeze():
    # wide then narrow plateau: strict-`<` rank keeps plateau at ~0 (not mid)
    w = np.concatenate([np.full(30, 0.04), np.full(10, 0.01)])
    pct = _bb_width_pctile(w, lookback=24)
    assert np.isfinite(pct[-1])
    assert pct[-1] <= 0.05
    assert pct[30] <= 0.05  # first narrow bar


def test_detect_fires_on_synthetic_squeeze_expand():
    """Construct RTH day: near-flat compression then directional expand."""
    n = 78  # full RTH 5m session-ish
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    # Early: larger swings (wide BB); mid: flat (squeeze); late: green breakout
    close = np.empty(n)
    # 0-29: oscillating so BB width is elevated once period fills
    for i in range(30):
        close[i] = 100.0 + (1.2 if i % 2 == 0 else -1.2)
    # 30-54: flat squeeze
    close[30:55] = 100.0
    # 55+: expand up (green bars break prior high, above mid)
    close[55:] = np.linspace(100.05, 104.0, n - 55)
    open_ = np.empty(n)
    open_[:55] = close[:55]
    open_[55:] = close[55:] - 0.2
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1e5),
        },
        index=idx,
    )
    cand = DayCandidate("TEST", date(2024, 6, 3), 100.0, 99.5, 0.5, 1.5, 2e6)
    cfg = BbSqueezeLongConfig(
        squeeze_pctile_max=0.35,
        squeeze_lookback=24,
        require_close_above_prior_high=True,
    )
    e = detect_from_frame(df, cand, cfg)
    assert e is not None, "synthetic squeeze→expand should produce an entry"
    assert e.pattern == "bb_squeeze_long"
    assert e.features["stop_px"] < e.entry_px
    assert e.features["construction"].startswith("v0.1.1")
    # Must fire inside entry window, not after 14:30
    hh, mm = map(int, e.time_et.split(":"))
    assert (hh, mm) < (14, 30)


def test_detect_no_crash_random():
    n = 100
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    close = np.concatenate(
        [
            np.full(60, 100.0) + np.random.default_rng(0).normal(0, 0.05, 60),
            np.linspace(100.2, 103, 40),
        ]
    )
    df = pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(n, 1e5),
        },
        index=idx,
    )
    cand = DayCandidate("TEST", date(2024, 6, 3), 100.0, 99.5, 0.5, 1.5, 2e6)
    cfg = BbSqueezeLongConfig(squeeze_pctile_max=0.5, squeeze_lookback=30)
    e = detect_from_frame(df, cand, cfg)
    if e is not None:
        assert e.features["stop_px"] < e.entry_px
