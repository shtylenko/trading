"""Tests for the f02–f05 dominance-flip variants and the two engine
additions behind them (N-bar time-decay abort, warm-start flip gating)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from trading.lab.core.execution import simulate_long_breakout
from trading.lab.core.models import ExecutionConfig, Signal, StrategyContext
from trading.lab.strategies import get_release_class, list_releases
from trading.lab.strategies.dominance_flip_reversal.common import detect_dominance_flip

from .conftest import make_daily_bars
from .test_f01_strategy import make_reversal_day_bars

NY = ZoneInfo("America/New_York")
TRADE_DATE = date(2024, 4, 1)
_NOSLIP = ExecutionConfig(entry_slippage_bps=0.0, exit_slippage_bps=0.0, fees_bps_per_side=0.0)


def _context(release_id, bars=None, daily=None, historical_5m=None):
    return StrategyContext(
        trade_date=TRADE_DATE,
        release_id=release_id,
        testset="unit",
        bars_5m={"AAPL": bars if bars is not None else make_reversal_day_bars()},
        daily={"AAPL": daily if daily is not None else make_daily_bars()},
        historical_5m=historical_5m or {},
    )


def test_all_four_registered_and_configured():
    assert {"f02", "f03", "f04", "f05"} <= set(list_releases())
    assert get_release_class("f02")().require_spy_uptrend is True
    assert get_release_class("f03")().warm_start is True
    assert get_release_class("f03")().historical_5m_lookback_days == 2
    assert get_release_class("f04")().max_hold_bars == 6
    assert get_release_class("f05")().target_atr_mult == 0.5


class TestF02TrendFilter:
    def test_blocks_when_spy_below_200sma(self, monkeypatch):
        import trading.lab.strategies.dominance_flip_reversal.variants as v
        monkeypatch.setattr(v, "spy_above_200sma", lambda *_a, **_k: False)
        rel = get_release_class("f02")()
        assert rel.build_candidates(_context("f02")) == []

    def test_trades_when_spy_above_200sma(self, monkeypatch):
        import trading.lab.strategies.dominance_flip_reversal.variants as v
        monkeypatch.setattr(v, "spy_above_200sma", lambda *_a, **_k: True)
        rel = get_release_class("f02")()
        assert len(rel.build_candidates(_context("f02"))) == 1


class TestF05TargetOvershoot:
    def test_target_pushed_past_mean(self):
        f01 = get_release_class("f01")()
        f05 = get_release_class("f05")()
        ctx1, ctx5 = _context("f01"), _context("f05")
        s1 = f01.build_signal(ctx1, f01.build_candidates(ctx1)[0])
        c5 = f05.build_candidates(ctx5)[0]
        s5 = f05.build_signal(ctx5, c5)
        expected = c5.features["sma_at_flip"] + 0.5 * c5.features["atr_5m"]
        assert s5.target_price == pytest.approx(expected)
        assert s5.target_price > s1.target_price  # strictly past the mean
        assert s5.stop_price < s5.entry_trigger < s5.target_price


class TestF04TimeDecayAbort:
    def _bars(self, rows):
        idx = [datetime(2024, 4, 2, hh, mm, tzinfo=NY) for hh, mm, *_ in rows]
        return pd.DataFrame(
            {"open": [r[2] for r in rows], "high": [r[3] for r in rows],
             "low": [r[4] for r in rows], "close": [r[5] for r in rows], "volume": 1e4},
            index=pd.DatetimeIndex(idx),
        )

    def _sig(self, max_hold=None):
        meta = {"direction": "long"}
        if max_hold is not None:
            meta["max_hold_bars"] = max_hold
        return Signal(ticker="T", setup_type="t",
                      signal_time=datetime(2024, 4, 2, 9, 35, tzinfo=NY),
                      entry_trigger=100.5, stop_price=99.0, target_price=103.0,
                      metadata=meta)

    def test_aborts_after_n_bars(self):
        # fill on bar 1 (100.5 taken out), then drift sideways, never hitting
        # stop (99) or target (103). With max_hold=3 it exits at the open of
        # the 3rd bar after entry.
        rows = [
            (9, 40, 100.0, 100.7, 100.0, 100.4),  # bar0 entry: high>=100.5
            (9, 45, 100.4, 100.6, 100.2, 100.5),  # +1
            (9, 50, 100.5, 100.7, 100.3, 100.6),  # +2
            (9, 55, 100.6, 100.8, 100.4, 100.7),  # +3 -> abort at open 100.6
            (15, 55, 100.7, 100.9, 100.5, 100.8),
        ]
        t = simulate_long_breakout(self._bars(rows), self._sig(max_hold=3),
                                   datetime(2024, 4, 2, 15, 59, tzinfo=NY), _NOSLIP)
        assert t.exit_reason == "TIME_DECAY"
        assert t.exit_time.hour == 9 and t.exit_time.minute == 55
        assert t.exit_price == pytest.approx(100.6)

    def test_no_abort_without_metadata(self):
        rows = [
            (9, 40, 100.0, 100.7, 100.0, 100.4),
            (9, 45, 100.4, 100.6, 100.2, 100.5),
            (9, 50, 100.5, 100.7, 100.3, 100.6),
            (9, 55, 100.6, 100.8, 100.4, 100.7),
            (15, 55, 100.7, 100.9, 100.5, 100.8),
        ]
        t = simulate_long_breakout(self._bars(rows), self._sig(max_hold=None),
                                   datetime(2024, 4, 2, 15, 59, tzinfo=NY), _NOSLIP)
        assert t.exit_reason == "TIME_EXIT"


class TestWarmStartFlipGating:
    def test_flip_after_rejects_pre_trade_day_flip(self):
        # Same engineered day; a flip_after past the only flip bar => None.
        bars = make_reversal_day_bars()
        base = detect_dominance_flip(bars)
        assert base is not None
        after = base["flip_time"]  # exclude the flip bar itself
        assert detect_dominance_flip(bars, flip_after=after) is None
        # a flip_after before it keeps the setup
        earlier = bars.index[0]
        assert detect_dominance_flip(bars, flip_after=earlier) is not None
