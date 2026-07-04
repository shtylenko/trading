"""Tests for d06's VWAP confluence gate (implemented in simulate_long_breakout
via the require_above_vwap metadata flag)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from trading.lab.core.execution import simulate_long_breakout
from trading.lab.core.models import ExecutionConfig, Signal
from trading.lab.strategies import get_release_class

NY = ZoneInfo("America/New_York")
_CUTOFF = datetime(2024, 4, 2, 15, 59, tzinfo=NY)
_NOSLIP = ExecutionConfig(entry_slippage_bps=0.0, exit_slippage_bps=0.0, fees_bps_per_side=0.0)


def _bars(rows):
    idx = [datetime(2024, 4, 2, hh, mm, tzinfo=NY) for hh, mm, *_ in rows]
    return pd.DataFrame(
        {"open": [r[2] for r in rows], "high": [r[3] for r in rows],
         "low": [r[4] for r in rows], "close": [r[5] for r in rows],
         "volume": [r[6] for r in rows]},
        index=pd.DatetimeIndex(idx),
    )


def _sig(require_vwap):
    md = {"direction": "long"}
    if require_vwap:
        md["require_above_vwap"] = True
    return Signal(ticker="T", setup_type="t",
                  signal_time=datetime(2024, 4, 2, 9, 30, tzinfo=NY),
                  entry_trigger=100.5, stop_price=99.5, target_price=101.5, metadata=md)


def test_registered_and_flagged():
    assert get_release_class("d06")().require_above_vwap is True


def test_fills_when_breakout_above_vwap():
    # Bar0 (signal bar 09:30) low, heavy volume far below -> drags VWAP down.
    # Breakout bar 09:35 fills at 100.5, comfortably above the low VWAP.
    bars = _bars([
        (9, 30, 90.0, 90.5, 89.5, 90.0, 100000),   # signal bar, VWAP≈90
        (9, 35, 100.0, 101.0, 100.0, 100.8, 1000),  # breakout >100.5, above VWAP
        (9, 40, 100.8, 101.6, 100.7, 101.5, 1000),  # hits target 101.5
    ])
    t = simulate_long_breakout(bars, _sig(True), _CUTOFF, _NOSLIP)
    assert t.exit_reason in ("TARGET", "TIME_EXIT")
    assert t.entry_price is not None


def test_rejects_when_breakout_below_vwap():
    # Bar0 prints very high on huge volume -> VWAP sits ~120, above the 100.5
    # breakout fill -> the gate must reject (NO_FILL).
    bars = _bars([
        (9, 30, 120.0, 121.0, 119.0, 120.0, 500000),  # huge volume high -> VWAP≈120
        (9, 35, 100.0, 101.0, 100.0, 100.8, 1000),    # breakout >100.5 but below VWAP
        (9, 40, 100.8, 101.6, 100.7, 101.5, 1000),
    ])
    t = simulate_long_breakout(bars, _sig(True), _CUTOFF, _NOSLIP)
    assert t.exit_reason == "NO_FILL"
    assert t.entry_price is None


def test_no_gate_without_flag_fills_normally():
    bars = _bars([
        (9, 30, 120.0, 121.0, 119.0, 120.0, 500000),
        (9, 35, 100.0, 101.0, 100.0, 100.8, 1000),
        (9, 40, 100.8, 101.6, 100.7, 101.5, 1000),
    ])
    t = simulate_long_breakout(bars, _sig(False), _CUTOFF, _NOSLIP)
    assert t.exit_reason in ("TARGET", "TIME_EXIT")  # no VWAP gate → fills


def test_vwap_gate_invariant_to_breakout_bar_close_and_volume():
    """Regression (C5): the VWAP gate at the breakout bar must use the VWAP
    through the PRIOR completed bar, never the breakout bar's own close/volume
    (which only print once that bar closes). Two scenarios that differ ONLY in
    the breakout bar's close and volume must produce the same fill decision.
    """
    # Prior (signal) bar fixes VWAP ≈ 95, well below the 100.5 trigger, so the
    # gate should admit the breakout regardless of the breakout bar itself.
    def scenario(bo_high, bo_close, bo_vol):
        bars = _bars([
            (9, 30, 95.0, 95.0, 95.0, 95.0, 10000),          # prior bar → VWAP≈95
            (9, 35, 100.6, bo_high, 100.4, bo_close, bo_vol),  # breakout fills ~100.6
            (9, 40, 100.8, 101.6, 100.7, 101.5, 1000),
        ])
        return simulate_long_breakout(bars, _sig(True), _CUTOFF, _NOSLIP)

    low = scenario(bo_high=101.0, bo_close=99.0, bo_vol=1_000)
    high = scenario(bo_high=131.0, bo_close=130.0, bo_vol=500_000)

    # Pre-fix, the heavy high-close breakout bar pulled the cumulative VWAP
    # above the fill and flipped this to NO_FILL. Both must now fill.
    assert low.entry_price is not None
    assert high.entry_price is not None
    assert low.exit_reason == high.exit_reason
