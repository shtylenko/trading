"""Tests for the o04-o08 variant releases and the engine extensions
behind them (short simulator, time stop, candle gate)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from trading.lab.core.execution import (
    simulate_long_breakout,
    simulate_short_breakout,
)
from trading.lab.core.models import ExecutionConfig, Signal
from trading.lab.strategies import get_release_class, list_releases

NY = ZoneInfo("America/New_York")


def _bars(rows):
    """rows: list of (hh, mm, o, h, l, c)."""
    idx = [datetime(2024, 4, 2, hh, mm, tzinfo=NY) for hh, mm, *_ in rows]
    return pd.DataFrame(
        {
            "open": [r[2] for r in rows],
            "high": [r[3] for r in rows],
            "low": [r[4] for r in rows],
            "close": [r[5] for r in rows],
            "volume": 10_000,
        },
        index=pd.DatetimeIndex(idx),
    )


def _signal(trigger, stop, direction="long", metadata=None):
    return Signal(
        ticker="TEST",
        setup_type="t",
        signal_time=datetime(2024, 4, 2, 9, 35, tzinfo=NY),
        entry_trigger=trigger,
        stop_price=stop,
        target_price=None,
        metadata={"direction": direction, **(metadata or {})},
    )


_CFG = ExecutionConfig()
_CUTOFF = datetime(2024, 4, 2, 15, 59, tzinfo=NY)


class TestShortBreakout:
    def test_short_fill_and_eod_profit(self):
        bars = _bars([
            (9, 40, 100.0, 100.4, 99.4, 99.6),   # breaks below 99.5 trigger
            (9, 45, 99.5, 99.6, 98.0, 98.2),
            (15, 55, 98.2, 98.4, 97.8, 98.0),
        ])
        sig = _signal(trigger=99.5, stop=100.5, direction="short")
        t = simulate_short_breakout(bars, sig, _CUTOFF, _CFG)
        assert t.direction == "short"
        assert t.exit_reason == "TIME_EXIT"
        assert t.realized_r is not None and t.realized_r > 0
        assert t.pnl_pct > 0

    def test_short_stop_loss_and_gap_through(self):
        bars = _bars([
            (9, 40, 100.0, 100.4, 99.4, 99.6),   # fill short at 99.5
            (9, 45, 101.2, 101.5, 101.0, 101.3),  # gaps above the 100.5 stop
        ])
        sig = _signal(trigger=99.5, stop=100.5, direction="short")
        t = simulate_short_breakout(bars, sig, _CUTOFF, _CFG)
        assert t.exit_reason == "STOP_LOSS"
        # gap through: exit at the open (101.2), worse than the stop
        assert t.exit_price >= 101.2
        assert t.realized_r < -1.0

    def test_short_no_fill(self):
        bars = _bars([(9, 40, 100.0, 100.5, 99.8, 100.2)])
        sig = _signal(trigger=99.5, stop=100.5, direction="short")
        t = simulate_short_breakout(bars, sig, _CUTOFF, _CFG)
        assert t.exit_reason == "NO_FILL"
        assert t.realized_r is None


class TestTimeStop:
    def test_laggard_cut_at_noon_winner_kept(self):
        meta = {"time_stop_at": "12:00", "time_stop_min_r": 0.5}
        # Laggard: fills at 100.5, drifts sideways, noon bar opens at 100.6
        # (unrealized R = 0.1/1.0 < 0.5) -> TIME_STOP at the noon open.
        laggard = _bars([
            (9, 40, 100.0, 100.6, 99.9, 100.4),   # breaks 100.5 trigger
            (11, 55, 100.4, 100.7, 100.3, 100.6),
            (12, 0, 100.6, 100.9, 100.5, 100.8),
            (15, 55, 100.8, 100.9, 100.6, 100.7),
        ])
        sig = _signal(100.5, 99.5, metadata=meta)
        t = simulate_long_breakout(laggard, sig, _CUTOFF, _CFG)
        assert t.exit_reason == "TIME_STOP"
        assert t.exit_time.hour == 12

        # Winner: noon open already +1R above entry -> runs to EOD.
        winner = _bars([
            (9, 40, 100.0, 100.6, 99.9, 100.4),
            (12, 0, 101.6, 102.0, 101.5, 101.9),  # unrealized R = 1.1
            (15, 55, 102.0, 102.3, 101.9, 102.2),
        ])
        t2 = simulate_long_breakout(winner, _signal(100.5, 99.5, metadata=meta),
                                    _CUTOFF, _CFG)
        assert t2.exit_reason == "TIME_EXIT"

    def test_no_time_stop_without_metadata(self):
        laggard = _bars([
            (9, 40, 100.0, 100.6, 99.9, 100.4),
            (12, 0, 100.6, 100.9, 100.5, 100.8),
            (15, 55, 100.8, 100.9, 100.6, 100.7),
        ])
        t = simulate_long_breakout(laggard, _signal(100.5, 99.5), _CUTOFF, _CFG)
        assert t.exit_reason == "TIME_EXIT"


class TestVariantReleases:
    def test_all_registered_and_configured(self):
        assert {"o04", "o05", "o06", "o07", "o08"} <= set(list_releases())
        o04 = get_release_class("o04")()
        assert o04.entry_style == "breakout_stop"
        assert o04.requires_rth_1m is True  # 1m sim fidelity (tight stops)
        o05 = get_release_class("o05")()
        assert o05.min_rv == 3.0 and o05.min_gap_abs == 0.03
        o06 = get_release_class("o06")()
        assert o06.allow_short is False  # account is long-only
        o07 = get_release_class("o07")()
        assert o07.requires_spy_daily is True
        o08 = get_release_class("o08")()
        assert o08.time_stop_at == "12:00" and o08.time_stop_min_r == 0.5

    def test_short_signal_geometry_engine_capability(self):
        # No production release shorts (the account is long-only), but the
        # engine capability stays covered via an ad-hoc two-sided variant.
        from trading.lab.core.models import Candidate, StrategyContext
        from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant

        class TwoSided(SipOrbVariant):
            release_id = "test2s"
            strategy_letter = "o"
            strategy_alias = "stocks_in_play_orb"
            strategy_name = "test"
            description = "test"
            allow_short = True

        rel = TwoSided()
        bars = _bars([(9, 30, 100.0, 100.4, 99.0, 99.2)])  # red first candle
        ctx = StrategyContext(
            release_id="test2s",
            testset="unit",
            trade_date=datetime(2024, 4, 2).date(),
            bars_5m={"TEST": bars},
            daily={}, historical_5m={}, bars_1m={}, extended_1m={},
            spy_5m=None, spy_daily=None,
        )
        cand = Candidate(
            ticker="TEST", score=3.0, reason="x",
            features={"direction": "short", "daily_atr_14": 2.0, "rv": 3.0,
                      "gap_pct": -0.04},
        )
        sig = rel.build_signal(ctx, cand)
        assert sig is not None
        assert sig.metadata["direction"] == "short"
        assert sig.entry_trigger == pytest.approx(99.0)   # OR low
        assert sig.stop_price == pytest.approx(99.0 + 0.2)  # +0.10*ATR

    def test_o06_gates_on_spy_first_candle(self):
        from trading.lab.core.models import StrategyContext

        o06 = get_release_class("o06")()
        green_spy = _bars([(9, 30, 500.0, 502.0, 499.5, 501.5)])
        red_spy = _bars([(9, 30, 500.0, 500.5, 497.0, 498.0)])
        def ctx(spy):
            return StrategyContext(
                release_id="o06", testset="unit",
                trade_date=datetime(2024, 4, 2).date(),
                bars_5m={}, daily={}, historical_5m={}, bars_1m={},
                extended_1m={}, spy_5m=spy, spy_daily=None,
            )
        assert o06.regime_ok(ctx(green_spy)) is True
        assert o06.regime_ok(ctx(red_spy)) is False
        # red-SPY day produces no candidates at all
        assert o06.build_candidates(ctx(red_spy)) == []


def test_o09_wide_stop_geometry():
    from trading.lab.core.models import Candidate, StrategyContext

    o09 = get_release_class("o09")()
    assert o09.stop_offset_atr == 0.30 and o09.stop_beyond_or is True

    # ENVX-like setup: OR 18.58-19.00, ATR 2.54
    bars = _bars([(9, 30, 18.58, 19.00, 18.58, 18.93)])
    ctx = StrategyContext(
        release_id="o09", testset="unit",
        trade_date=datetime(2024, 4, 2).date(),
        bars_5m={"TEST": bars}, daily={}, historical_5m={},
        bars_1m={}, extended_1m={}, spy_5m=None, spy_daily=None,
    )
    cand = Candidate(ticker="TEST", score=3.0, reason="x",
                     features={"direction": "long", "daily_atr_14": 2.5434,
                               "rv": 3.5, "gap_pct": -0.04})
    sig = o09.build_signal(ctx, cand)
    # 0.30*ATR = 0.763 below trigger (18.237) is wider than OR low (18.58)
    # -> the 0.30 ATR stop wins (min of the two for longs)
    assert sig.entry_trigger == pytest.approx(19.00)
    assert sig.stop_price == pytest.approx(19.00 - 0.30 * 2.5434)

    # Wide OR: OR low further than 0.30 ATR -> OR low wins
    cand2 = Candidate(ticker="TEST", score=3.0, reason="x",
                      features={"direction": "long", "daily_atr_14": 1.0,
                                "rv": 3.5, "gap_pct": 0.0})
    bars2 = _bars([(9, 30, 18.50, 19.00, 18.50, 18.93)])  # OR span 0.50 > 0.30 ATR
    ctx.bars_5m["TEST"] = bars2
    sig2 = o09.build_signal(ctx, cand2)
    assert sig2.stop_price == pytest.approx(18.50)
