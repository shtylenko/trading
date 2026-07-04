from __future__ import annotations

from datetime import date

import pytest

from trading.lab.core.execution import _time_stop_triggered, simulate_long_breakout
from trading.lab.core.models import ExecutionConfig, Signal

from .conftest import make_5m_bars


def test_time_stop_rejects_malformed_time(monkeypatch):
    """M7: a malformed time_stop_at must raise a clear error, not yield the
    wrong number of values and crash mid-trade with an opaque ValueError."""
    import pandas as pd

    sig = Signal(
        ticker="T", setup_type="t", signal_time=date(2024, 1, 2),
        entry_trigger=100.0, stop_price=99.0, target_price=None,
        metadata={"time_stop_at": "12:00:00"},  # three components → invalid
    )
    ts = pd.Timestamp("2024-01-02 12:05", tz="America/New_York")
    with pytest.raises(ValueError, match="HH:MM"):
        _time_stop_triggered(sig, entry_price=100.0, bar_open=99.5, ts=ts)


def test_time_stop_well_formed_time_ok():
    import pandas as pd

    sig = Signal(
        ticker="T", setup_type="t", signal_time=date(2024, 1, 2),
        entry_trigger=100.0, stop_price=99.0, target_price=None,
        metadata={"time_stop_at": "12:00", "time_stop_min_r": 0.0},
    )
    ts = pd.Timestamp("2024-01-02 12:05", tz="America/New_York")
    # Unrealized R at the open is negative (open below entry) → time stop fires.
    assert _time_stop_triggered(sig, entry_price=100.0, bar_open=99.5, ts=ts) is True


def test_breakout_cannot_fill_on_opening_range_bar():
    bars = make_5m_bars()
    first_ts = bars.index[0].to_pydatetime()
    signal = Signal(
        ticker="AAPL",
        setup_type="opening_range_breakout",
        signal_time=first_ts,
        entry_trigger=101.0,
        stop_price=99.5,
        target_price=102.5,
    )

    trade = simulate_long_breakout(
        bars,
        signal,
        cutoff=bars.index[-1].to_pydatetime(),
        config=ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0),
    )

    assert trade is not None
    assert trade.entry_time == bars.index[1].to_pydatetime()
    assert trade.entry_time > signal.signal_time


def test_no_fill_trade_is_recorded_when_trigger_never_breaks():
    bars = make_5m_bars(first_high=101.0)
    signal = Signal(
        ticker="AAPL",
        setup_type="opening_range_breakout",
        signal_time=bars.index[0].to_pydatetime(),
        entry_trigger=200.0,
        stop_price=198.0,
        target_price=202.0,
    )

    trade = simulate_long_breakout(
        bars,
        signal,
        cutoff=bars.index[-1].to_pydatetime(),
        config=ExecutionConfig(),
    )

    assert trade is not None
    assert trade.exit_reason == "NO_FILL"
    assert trade.entry_time is None
    assert trade.pnl_pct == 0.0


def test_breakout_same_bar_stop_out():
    # Bar 1 is the setup/signal bar (not active).
    # Bar 2 is the active bar where entry & stop occur.
    # Trigger = 101.0, Stop = 99.0.
    # Bar 2: Open = 100.0, High = 102.0, Low = 98.5, Close = 100.0.
    # Since open (100.0) > stop (99.0), exit_base = min(100.0, 99.0) = 99.0.
    bars = make_5m_bars()
    # Replace the second bar with our test values
    bars.iloc[1] = [100.0, 102.0, 98.5, 100.0, 500_000]
    
    signal = Signal(
        ticker="AAPL",
        setup_type="opening_range_breakout",
        signal_time=bars.index[0].to_pydatetime(),
        entry_trigger=101.0,
        stop_price=99.0,
        target_price=200.0,
    )

    trade = simulate_long_breakout(
        bars,
        signal,
        cutoff=bars.index[-1].to_pydatetime(),
        config=ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0),
    )

    assert trade is not None
    assert trade.entry_time == bars.index[1].to_pydatetime()
    assert trade.exit_time == bars.index[1].to_pydatetime()
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.entry_price == 101.0
    assert trade.exit_price == 99.0


def test_breakout_same_bar_stop_out_gap():
    # Bar 1 is setup.
    # Bar 2: Open = 98.0, High = 102.0, Low = 97.5, Close = 99.0.
    # Trigger = 101.0, Stop = 99.0.
    # The open (98.0) printed BEFORE the entry fill at 101, so the
    # gap-through rule does not apply on the entry bar: after the fill,
    # price fell back through the stop and the stop order fills at 99.0.
    bars = make_5m_bars()
    bars.iloc[1] = [98.0, 102.0, 97.5, 99.0, 500_000]
    
    signal = Signal(
        ticker="AAPL",
        setup_type="opening_range_breakout",
        signal_time=bars.index[0].to_pydatetime(),
        entry_trigger=101.0,
        stop_price=99.0,
        target_price=200.0,
    )

    trade = simulate_long_breakout(
        bars,
        signal,
        cutoff=bars.index[-1].to_pydatetime(),
        config=ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0),
    )

    assert trade is not None
    assert trade.entry_time == bars.index[1].to_pydatetime()
    assert trade.exit_time == bars.index[1].to_pydatetime()
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.entry_price == 101.0
    assert trade.exit_price == 99.0

