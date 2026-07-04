from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from zoneinfo import ZoneInfo

from trading.lab.core.execution import simulate_pullback_limit_long
from trading.lab.core.models import Candidate, ExecutionConfig, Signal, StrategyContext
from trading.lab.strategies import get_release_class

from .conftest import make_5m_bars

NY = ZoneInfo("America/New_York")


def make_1m_bars(rows: list[dict], start: str = "2024-04-01 09:35") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq="1min", tz=NY)
    return pd.DataFrame(rows, index=idx)


def _signal(trigger=101.0, stop=100.6, limit=100.92, ttl=30) -> Signal:
    return Signal(
        ticker="AAPL",
        setup_type="orb_pullback_limit_v2",
        signal_time=pd.Timestamp("2024-04-01 09:30", tz=NY).to_pydatetime(),
        entry_trigger=trigger,
        stop_price=stop,
        target_price=None,
        metadata={"pullback_limit": limit, "pullback_ttl_min": ttl},
    )


NO_COST = ExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fees_bps_per_side=0)


def test_pullback_fill_only_after_breach_bar():
    # bar0 breaches trigger AND dips below the limit; strict rule: no fill on
    # the breach bar itself. bar1 pulls back through the limit -> fill there.
    bars = make_1m_bars(
        [
            {"open": 100.9, "high": 101.2, "low": 100.8, "close": 101.1, "volume": 1000},
            {"open": 101.1, "high": 101.3, "low": 100.9, "close": 101.0, "volume": 1000},
            {"open": 101.0, "high": 102.0, "low": 101.0, "close": 102.0, "volume": 1000},
        ]
    )
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), NO_COST)
    assert trade is not None
    assert trade.entry_time == bars.index[1].to_pydatetime()
    assert trade.entry_price == pytest.approx(100.92)
    assert trade.exit_reason == "TIME_EXIT"
    assert trade.exit_price == pytest.approx(102.0)


def test_pullback_touch_does_not_fill():
    # low exactly equal to the limit price must not fill (queue priority)
    bars = make_1m_bars(
        [
            {"open": 100.9, "high": 101.2, "low": 100.85, "close": 101.1, "volume": 1000},
            {"open": 101.1, "high": 101.3, "low": 100.92, "close": 101.2, "volume": 1000},
            {"open": 101.2, "high": 101.5, "low": 101.0, "close": 101.4, "volume": 1000},
        ]
    )
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), NO_COST)
    assert trade is not None
    assert trade.exit_reason == "NO_FILL"
    assert trade.entry_time is None


def test_pullback_collapse_through_stop_fills_and_stops_same_bar():
    bars = make_1m_bars(
        [
            {"open": 100.9, "high": 101.2, "low": 100.85, "close": 101.1, "volume": 1000},
            {"open": 101.0, "high": 101.1, "low": 100.3, "close": 100.4, "volume": 1000},
        ]
    )
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), NO_COST)
    assert trade is not None
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.entry_price == pytest.approx(100.92)
    assert trade.exit_price == pytest.approx(100.6)
    assert trade.entry_time == trade.exit_time


def test_pullback_order_expires_after_ttl():
    rows = [{"open": 100.9, "high": 101.2, "low": 100.95, "close": 101.1, "volume": 1000}]
    # 31 bars that never pull back below the limit
    rows += [{"open": 101.1, "high": 101.4, "low": 101.0, "close": 101.2, "volume": 1000}] * 31
    # dip below the limit only AFTER the 30-minute TTL has expired
    rows += [{"open": 101.0, "high": 101.1, "low": 100.5, "close": 100.7, "volume": 1000}]
    bars = make_1m_bars(rows)
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), NO_COST)
    assert trade is not None
    assert trade.exit_reason == "NO_FILL"


def test_pullback_no_breach_no_fill():
    bars = make_1m_bars(
        [
            {"open": 100.0, "high": 100.9, "low": 99.8, "close": 100.5, "volume": 1000},
            {"open": 100.5, "high": 100.8, "low": 100.0, "close": 100.2, "volume": 1000},
        ]
    )
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), NO_COST)
    assert trade is not None
    assert trade.exit_reason == "NO_FILL"
    assert trade.context.get("breached") is False


def test_pullback_entry_has_no_entry_slippage():
    bars = make_1m_bars(
        [
            {"open": 100.9, "high": 101.2, "low": 100.8, "close": 101.1, "volume": 1000},
            {"open": 101.1, "high": 101.3, "low": 100.9, "close": 101.0, "volume": 1000},
            {"open": 101.0, "high": 102.0, "low": 101.0, "close": 102.0, "volume": 1000},
        ]
    )
    cfg = ExecutionConfig(entry_slippage_bps=10, exit_slippage_bps=0, fees_bps_per_side=0)
    trade = simulate_pullback_limit_long(bars, _signal(), bars.index[-1].to_pydatetime(), cfg)
    assert trade is not None
    assert trade.entry_price == pytest.approx(100.92)  # maker fill at the limit


def _o03_context(trade_date=date(2024, 4, 1)) -> StrategyContext:
    daily_idx = pd.bdate_range(end="2024-03-29", periods=30, tz=NY)
    daily = pd.DataFrame(
        {
            "open": [100.0] * 30,
            "high": [102.0] * 30,
            "low": [99.0] * 30,
            "close": [101.0] * 30,
            "volume": [2_000_000] * 30,
        },
        index=daily_idx,
    )
    hist_idx = pd.bdate_range(end="2024-03-29", periods=14, tz=NY).map(
        lambda ts: ts.replace(hour=9, minute=30)
    )
    historical_5m = pd.DataFrame(
        {
            "open": [100.0] * 14,
            "high": [101.0] * 14,
            "low": [99.0] * 14,
            "close": [100.5] * 14,
            "volume": [100_000] * 14,
        },
        index=pd.DatetimeIndex(hist_idx),
    )
    trade_bars = make_5m_bars()
    trade_bars.iloc[0, trade_bars.columns.get_loc("volume")] = 300_000
    return StrategyContext(
        trade_date=trade_date,
        release_id="o03",
        testset="unit",
        bars_5m={"AAPL": trade_bars},
        daily={"AAPL": daily},
        historical_5m={"AAPL": historical_5m},
        spy_5m=make_5m_bars(),
        spy_daily=daily,
    )


def test_o03_candidate_features_and_signal():
    release = get_release_class("o03")()
    context = _o03_context()
    candidates = release.build_candidates(context)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.features["rv"] == pytest.approx(3.0)
    assert "range_width_atr" in cand.features
    assert "spy_vr" in cand.features

    signal = release.build_signal(context, cand)
    assert signal is not None
    atr = cand.features["daily_atr_14"]
    assert signal.entry_trigger == pytest.approx(101.0)
    assert signal.stop_price == pytest.approx(101.0 - 0.10 * atr)
    assert signal.metadata["pullback_limit"] == pytest.approx(101.0 - 0.02 * atr)
    assert signal.metadata["pullback_ttl_min"] == 30
    assert signal.metadata["leverage"] <= 4.0 + 1e-6
    assert signal.target_price is None


def test_o03_is_registered_with_pullback_entry_style():
    release = get_release_class("o03")()
    assert release.entry_style == "pullback_limit"
    assert release.requires_rth_1m is True


def test_o03_disable_ml_env_forces_rv_ranking(monkeypatch):
    from trading.lab.strategies.stocks_in_play_orb.o03 import Release

    monkeypatch.setenv("O03_DISABLE_ML", "1")
    assert Release.model_payload() is None
