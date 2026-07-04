"""Regression tests for the audit-driven new releases (2026-06-13):

    o10 (M14) — o03 ML auto-disabled before its 2024 training span.
    o11 (L4)  — o07 volatility-regime gate sourced from context.spy_daily.
    f06 (H2)  — f02 200-SMA gate sourced from context.spy_daily.
    f07 (M11) — f05 overshoot target, skips when ATR(5m) is unavailable
                instead of silently reverting to f01.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from trading.lab.strategies import get_release_class
from trading.lab.strategies.stocks_in_play_orb.o11 import (
    _spy_atr_regime_hot_from_daily,
)
from trading.lab.strategies.dominance_flip_reversal.f06 import (
    _spy_above_sma_from_daily,
)

NY = ZoneInfo("America/New_York")


def test_all_four_registered():
    for rid in ("o10", "o11", "f06", "f07"):
        assert get_release_class(rid)().release_id == rid


# ── o10 (M14): ML date gate ──────────────────────────────────────────────────

def test_o10_disables_ml_before_training_year():
    o10 = get_release_class("o10")
    o03 = get_release_class("o03")
    o10._gate_year = 2022
    assert o10.model_payload() is None  # look-ahead guard: no ML pre-2024
    o10._gate_year = 2024
    # On/after the cutoff o10 delegates to o03's loader (env/lgbm decide):
    # either both fall back to RV (None) or both load the same feature schema.
    p10, p03 = o10.model_payload(), o03.model_payload()
    assert (p10 is None) == (p03 is None)
    if p10 is not None:
        assert p10["features"] == p03["features"]


def test_o10_declares_long_enough_spy_history():
    # Inherits o03's requirement; the gate never needs more than o03 does.
    assert get_release_class("o10")().requires_spy_daily is True


# ── o11 (L4) / f06 (H2): context-sourced regime gates ────────────────────────

def _spy_frame(closes):
    idx = pd.date_range("2023-01-02", periods=len(closes), freq="D", tz=NY)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"high": c + 1, "low": c - 1, "close": c}, index=idx)


def test_f06_sma_gate_above_and_below():
    rising = _spy_frame(np.linspace(100, 200, 250))   # last close >> 200-SMA
    falling = _spy_frame(np.linspace(200, 100, 250))   # last close << 200-SMA
    assert _spy_above_sma_from_daily(rising) is True
    assert _spy_above_sma_from_daily(falling) is False


def test_f06_conservative_on_thin_data():
    # Fewer than 200 bars → do not trade (no provider fallback).
    assert _spy_above_sma_from_daily(_spy_frame(np.linspace(100, 110, 50))) is False
    assert _spy_above_sma_from_daily(None) is False


def test_o11_regime_hot_distinguishes_high_low_vol():
    rng = np.random.default_rng(3)
    base = 100 + np.cumsum(rng.normal(0, 0.2, 300))
    calm = _spy_frame(base)
    # Recent bars get a volatility burst → ATR% should sit above its median.
    spiked = base.copy()
    spiked[-20:] += rng.normal(0, 8.0, 20)
    hot = _spy_frame(spiked)
    assert _spy_atr_regime_hot_from_daily(hot) is True
    assert _spy_atr_regime_hot_from_daily(calm.tail(40)) is False  # thin → False


# ── f07 (M11): ATR guard ─────────────────────────────────────────────────────

class _Ctx:
    trade_date = date(2024, 4, 2)


def _flip_candidate(atr_5m):
    from trading.lab.core.models import Candidate

    feats = {
        "flip_time": datetime(2024, 4, 2, 13, 0, tzinfo=NY),
        "entry_trigger": 99.0,
        "stop_price": 95.0,
        "target_price": 100.0,   # f01 mean-touch target
        "sma_at_flip": 100.0,
        "atr_5m": atr_5m,
    }
    return Candidate(ticker="T", score=1.0, reason="t", features=feats)


def test_f07_applies_overshoot_target_when_atr_valid():
    f07 = get_release_class("f07")()
    sig = f07.build_signal(_Ctx(), _flip_candidate(atr_5m=2.0))
    assert sig is not None
    # mean 100 + 0.5 * 2.0 = 101, above the f01 target of 100.
    assert sig.target_price == pytest.approx(101.0)


def test_f07_skips_when_atr_missing_or_nan():
    f07 = get_release_class("f07")()
    assert f07.build_signal(_Ctx(), _flip_candidate(atr_5m=float("nan"))) is None
    bad = _flip_candidate(atr_5m=2.0)
    del bad.features["atr_5m"]
    assert f07.build_signal(_Ctx(), bad) is None


def test_f05_silently_reverts_on_nan_atr_the_bug_f07_fixes():
    # Documents the f05 behaviour f07 corrects: NaN ATR → f05 still trades,
    # silently keeping f01's mean-touch target.
    f05 = get_release_class("f05")()
    sig = f05.build_signal(_Ctx(), _flip_candidate(atr_5m=float("nan")))
    assert sig is not None
    assert sig.target_price == pytest.approx(100.0)  # unchanged f01 target
