"""Tests for the multi-day swing simulator (core/execution.simulate_daily_hold)."""
from __future__ import annotations

import pandas as pd
import pytest

from trading.lab.core.execution import simulate_daily_hold
from trading.lab.core.models import ExecutionConfig, Signal


def _bars(closes, start="2024-01-02"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": closes, "high": [c * 1.01 for c in closes],
                         "low": [c * 0.99 for c in closes]}, index=idx)


def _sig(stop=90.0):
    return Signal(ticker="X", setup_type="xsec_momentum",
                  signal_time=pd.Timestamp("2024-01-02"), entry_trigger=100.0,
                  stop_price=stop, target_price=None, metadata={})


def test_time_exit_after_hold_days():
    bars = _bars([100, 101, 102, 103, 104, 105, 106])  # +1/day
    cfg = ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0)
    t = simulate_daily_hold(bars, _sig(), entry_date=bars.index[0], hold_days=5, config=cfg)
    assert t is not None and t.exit_reason == "TIME_EXIT"
    # entered close[0]=100, exit close[5]=105 → +5% gross, no cost
    assert t.entry_price == pytest.approx(100.0)
    assert t.exit_price == pytest.approx(105.0)
    assert t.gross_pnl_pct == pytest.approx(5.0)
    # exit timestamp is exactly 5 trading days after entry
    assert pd.Timestamp(t.exit_time).normalize() == bars.index[5]


def test_slippage_and_fees_baked_in():
    bars = _bars([100, 100, 100, 100, 100, 100])
    cfg = ExecutionConfig(entry_slippage_bps=10, exit_slippage_bps=10, fees_bps_per_side=5)
    t = simulate_daily_hold(bars, _sig(), entry_date=bars.index[0], hold_days=5, config=cfg)
    # flat price but slippage: pay 100*(1.001)=100.1, receive 100*(0.999)=99.9
    # gross = (99.9-100.1)/100.1*100 ≈ -0.1998%
    assert t.entry_price == pytest.approx(100.1)
    assert t.exit_price == pytest.approx(99.9)
    assert t.gross_pnl_pct == pytest.approx((99.9 - 100.1) / 100.1 * 100.0)
    assert t.fees_pct == pytest.approx(0.1)  # 5bps*2 sides /100
    assert t.pnl_pct == pytest.approx(t.gross_pnl_pct - t.fees_pct)


def test_close_stop_exits_early():
    bars = _bars([100, 99, 95, 88, 92, 96, 100])  # dips below stop=90 on day 3
    cfg = ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0)
    t = simulate_daily_hold(bars, _sig(stop=90.0), entry_date=bars.index[0], hold_days=6,
                            config=cfg, use_close_stop=True)
    assert t.exit_reason == "STOP_CLOSE"
    assert t.exit_price == pytest.approx(88.0)  # first close <= 90


def test_none_when_insufficient_forward_bars():
    bars = _bars([100, 101, 102])
    cfg = ExecutionConfig()
    assert simulate_daily_hold(bars, _sig(), entry_date=bars.index[0], hold_days=5, config=cfg) is None


def test_none_when_entry_date_absent():
    bars = _bars([100, 101, 102, 103, 104, 105])
    cfg = ExecutionConfig()
    assert simulate_daily_hold(bars, _sig(), entry_date=pd.Timestamp("2020-05-05"),
                               hold_days=2, config=cfg) is None
