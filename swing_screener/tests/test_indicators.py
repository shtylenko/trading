"""Unit tests for C1 indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.indicators import (
    enrich_daily,
    performance,
    sma,
    wilder_rsi,
)


def test_sma_min_periods():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert np.isnan(out.iloc[0])
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[4] == 4.0


def test_performance_lookback():
    s = pd.Series([100.0, 110.0, 121.0])
    p = performance(s, 2)
    assert np.isnan(p.iloc[0])
    assert np.isnan(p.iloc[1])
    assert abs(p.iloc[2] - 0.21) < 1e-9


def test_wilder_rsi_bounds_and_warmup():
    # Monotone up → RSI near 100 after warmup
    close = pd.Series(np.linspace(100, 150, 40))
    rsi = wilder_rsi(close, 14)
    assert rsi.isna().sum() >= 14  # warmup
    assert rsi.dropna().iloc[-1] > 70

    # Flat → RSI around 50
    flat = pd.Series([10.0] * 30)
    rsi_flat = wilder_rsi(flat, 2)
    assert abs(rsi_flat.dropna().iloc[-1] - 50.0) < 1e-6


def test_enrich_daily_columns():
    n = 250
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": rng.integers(1_000_000, 2_000_000, n),
        },
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
    )
    out = enrich_daily(df)
    for col in (
        "sma5",
        "sma20",
        "sma50",
        "sma200",
        "rsi2",
        "rsi14",
        "atr14",
        "avg_vol_20",
        "relvol",
        "perf_5d",
        "perf_21d",
        "perf_126d",
        "sma20_ext",
    ):
        assert col in out.columns
    # SMA200 needs 200 bars
    assert out["sma200"].isna().sum() == 199
    assert out["sma200"].notna().sum() == n - 199
