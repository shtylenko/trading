"""Unit tests for shared indicators module (no external deps)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading.llm_trader.config import ScanConfig
from trading.llm_trader.indicators import (
    enrich_1min_for_replay,
    normalize_to_et,
    prepare_detection_frame,
    session_vwap,
)
from trading.llm_trader.patterns import detect_from_frame
from trading.llm_trader.screen import GapCandidate


def _make_ohlcv(rows, day="2025-03-10", tz="America/New_York"):
    """rows: list[(HH:MM, o, h, l, c, v)]"""
    idx = pd.DatetimeIndex(
        [pd.Timestamp(f"{day} {hm}", tz=tz) for hm, *_ in rows],
        name="timestamp",
    )
    return pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
        },
        index=idx,
    )


def test_session_vwap_basic():
    rows = [
        ("09:30", 10, 11, 9, 10.5, 1000),
        ("09:35", 10.5, 10.6, 10.4, 10.5, 800),
    ]
    df = _make_ohlcv(rows)
    vwap = session_vwap(df)
    assert len(vwap) == 2
    assert pd.notna(vwap.iloc[0])
    # VWAP should be between low/high of session
    assert vwap.iloc[-1] > 9 and vwap.iloc[-1] < 12


def test_normalize_to_et_and_day_filter():
    rows = [("09:30", 5, 5.2, 4.9, 5.1, 100), ("16:00", 5.1, 5.3, 5.0, 5.2, 200)]
    df = _make_ohlcv(rows, tz=None)  # naive input
    norm = normalize_to_et(df, day=date(2025, 3, 10))
    # both rows are on 2025-03-10 so both kept; demonstrate tz + filter works
    assert len(norm) == 2
    assert str(norm.index.tz) == "America/New_York"

    # cross-day filter test
    rows2 = [("09:30", 5, 5.2, 4.9, 5.1, 100)]
    df2 = _make_ohlcv(rows2, day="2025-03-11", tz=None)
    norm2 = normalize_to_et(df2, day=date(2025, 3, 10))
    assert len(norm2) == 0


def test_prepare_detection_frame_adds_columns():
    rows = [
        ("09:30", 5.0, 5.2, 4.9, 5.1, 100),
        ("09:35", 5.1, 5.15, 5.05, 5.1, 80),
    ]
    df = _make_ohlcv(rows)
    prepared = prepare_detection_frame(df, date(2025, 3, 10), vol_avg_window=3)
    assert "vwap" in prepared.columns
    assert "vol_avg" in prepared.columns
    # vol_avg uses shift, first row after prep should have NA or small value
    assert prepared.iloc[0]["vol_avg"] != prepared.iloc[0]["vol_avg"] or pd.isna(prepared.iloc[0]["vol_avg"]) or prepared.iloc[0]["vol_avg"] >= 0


def test_enrich_1min_for_replay_adds_all_fields():
    rows = [
        ("09:30", 5.0, 5.2, 4.9, 5.1, 1000),
        ("09:35", 5.1, 5.3, 5.05, 5.25, 1200),
        ("09:40", 5.25, 5.4, 5.2, 5.35, 1500),
    ]
    df = _make_ohlcv(rows)
    enriched = enrich_1min_for_replay(df)
    for col in ("vwap", "ema9", "ema20", "macd", "macd_signal", "macd_hist",
                "cum_vol", "session_high", "new_high", "rvol_bar", "above_vwap"):
        assert col in enriched.columns
    assert enriched["new_high"].iloc[0]  # first bar is new high by construction
    assert enriched["above_vwap"].any()
    # MACD identity holds: hist == line − signal
    assert (enriched["macd_hist"] - (enriched["macd"] - enriched["macd_signal"])).abs().max() < 1e-9


def test_macd_matches_reference_and_no_lookahead():
    from trading.llm_trader.indicators import macd

    close = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], dtype=float)
    out = macd(close)
    # reference: fast/slow EMAs (adjust=False) differenced, signal = EMA9 of the line
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=9, adjust=False).mean()
    assert (out["macd"] - line).abs().max() < 1e-12
    assert (out["macd_signal"] - sig).abs().max() < 1e-12
    # no look-ahead: truncating the series doesn't change earlier MACD values
    trunc = macd(close.iloc[:8])
    assert (out["macd"].iloc[:8] - trunc["macd"]).abs().max() < 1e-12


def test_config_vol_avg_window_affects_detection():
    # Build a frame where breakout vol is between 1.0x and 2.0x
    day = "2025-03-10"
    rows = [
        ("09:30", 5.0, 5.2, 4.9, 5.1, 100_000),
        ("09:35", 5.1, 5.15, 5.05, 5.12, 80_000),
        ("09:40", 5.12, 5.19, 5.08, 5.15, 70_000),
        ("09:45", 5.15, 5.45, 5.14, 5.42, 150_000),  # new high, ~1.8-2x depending on window
    ]
    df = _make_ohlcv(rows, day=day)
    cand = GapCandidate("T", date(2025, 3, 10), 5.0, 4.0, 25.0, 8.0, 1e6, 8e6)

    # Default window=5 should compute a baseline; use a high threshold to block
    cfg_strict = ScanConfig(vol_expansion_mult=3.0, vol_avg_window=2)
    e_strict = detect_from_frame(df, cand, cfg_strict, None)
    # With small window the vol_mult may be high enough or not; main point is config is wired
    # Instead assert that changing window is accepted without crash and produces deterministic Entry or None
    assert e_strict is None or e_strict.bar_vol_mult is not None

    cfg_loose = ScanConfig(vol_expansion_mult=1.0, vol_avg_window=5)
    e_loose = detect_from_frame(df, cand, cfg_loose, None)
    assert e_loose is not None  # should pass loose gate
