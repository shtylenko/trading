"""Smoke tests for C1 screen helpers (no full marketdata fetch required)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.indicators import enrich_daily
from trading.swing_screener.c1_pullback.rules import C1Config, load_config
from trading.swing_screener.c1_pullback.screen import _normalize_variants, screen_ticker


def test_load_default_config():
    cfg = load_config()
    assert cfg.rules_version.startswith("c1_pullback")
    assert cfg.mr.rsi2_max == 10.0
    assert cfg.pb.rsi14_min == 35.0


def test_normalize_variants():
    assert _normalize_variants("both") == ["C1_MR", "C1_PB"]
    assert _normalize_variants("C1_MR") == ["C1_MR"]
    assert _normalize_variants("mr") == ["C1_MR"]


def test_screen_ticker_on_synthetic():
    n = 260
    rng = np.random.default_rng(42)
    close = 80 + np.cumsum(rng.normal(0.05, 0.8, n))
    # ensure positive trend-ish
    close = np.maximum.accumulate(close * 0.2 + np.linspace(80, 120, n) * 0.8)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.full(n, 2_000_000.0),
        },
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    enriched = enrich_daily(df)
    cfg = C1Config()
    start = enriched.index[200].date()
    end = enriched.index[-1].date()
    out = screen_ticker(
        "FAKE",
        enriched,
        cfg,
        start=start,
        end=end,
        variants=["C1_MR", "C1_PB"],
        membership=None,
    )
    assert isinstance(out, pd.DataFrame)
    if not out.empty:
        assert set(out["variant"]).issubset({"C1_MR", "C1_PB"})
        assert (out["ticker"] == "FAKE").all()
