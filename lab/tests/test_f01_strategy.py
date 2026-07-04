"""Unit tests for f01 — Dominance Flip Reversal P0 baseline.

The synthetic day is engineered to walk through all four phases:
seeded mean (bars 0-19), steep first leg down (20-29), weak bounce that
stays below the falling SMA (30-33), slow grind to a lower low (34-39),
climactic flush on huge volume (bar 40, z < -2), and a green flip bar
(41) that pulls the z-score back inside the extreme threshold.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.lab.core.execution import simulate_long_breakout
from trading.lab.core.models import ExecutionConfig, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.strategies import get_release_class
from trading.lab.strategies.dominance_flip_reversal.common import detect_dominance_flip

from .conftest import make_daily_bars

NY = ZoneInfo("America/New_York")

TRADE_DATE = date(2024, 4, 1)


def make_reversal_day_bars(
    flush_close: float = 93.5,
    flush_volume: float = 2_000_000.0,
) -> pd.DataFrame:
    """Full 78-bar RTH day with a capitulation flush and dominance flip.

    ``flush_close`` controls the bar-40 capitulation depth (the default
    drives the z-score through -2 and a lower low versus bar 29);
    ``flush_volume`` controls the liq-flow climax on that bar.
    """
    idx = pd.date_range(
        start=datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=78, freq="5min", tz=NY
    )
    closes: list[float] = []
    # bars 0-19: oscillate around 100 to seed the SMA
    for i in range(20):
        closes.append(100.0 + (0.2 if i % 2 == 0 else -0.2))
    # bars 20-29: steep first leg down (99.5 -> 95.18)
    for i in range(10):
        closes.append(99.5 - 0.48 * i)
    # bars 30-33: weak bounce that stays below the falling SMA
    closes += [95.6, 96.0, 96.2, 96.1]
    # bars 34-39: slow grind back down toward the first-leg low
    closes += [95.9, 95.8, 95.7, 95.6, 95.3, 94.8]
    # bar 40: capitulation flush — lower low, z extreme, climax volume
    closes.append(flush_close)
    # bar 41: flip bar — strong green reclaim of the extreme zone
    closes.append(95.0)
    # bars 42+: drift back up through the mean so the breakout entry
    # fills and the mean-touch target is reachable
    last = closes[-1]
    while len(closes) < 78:
        last += 0.18
        closes.append(min(last, 99.5))
    closes_arr = np.array(closes)

    opens = np.empty_like(closes_arr)
    opens[0] = 100.0
    opens[1:] = closes_arr[:-1]
    highs = np.maximum(opens, closes_arr) + 0.10
    lows = np.minimum(opens, closes_arr) - 0.10
    volume = np.full(78, 500_000.0)
    volume[:20] += np.where(np.arange(20) % 2 == 0, 30_000, -30_000)
    volume[40] = flush_volume
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_arr, "volume": volume},
        index=idx,
    )


def _context(bars=None, daily=None) -> StrategyContext:
    return StrategyContext(
        trade_date=TRADE_DATE,
        release_id="f01",
        testset="unit",
        bars_5m={"AAPL": bars if bars is not None else make_reversal_day_bars()},
        daily={"AAPL": daily if daily is not None else make_daily_bars()},
    )


def test_detect_dominance_flip_finds_engineered_setup():
    setup = detect_dominance_flip(make_reversal_day_bars())

    assert setup is not None
    assert setup["flip_time"] == pd.Timestamp("2024-04-01 12:55:00", tz=NY)
    assert setup["extreme_time"] == pd.Timestamp("2024-04-01 12:50:00", tz=NY)
    assert setup["stretch_bars"] >= 12
    assert setup["z_prev"] <= -2.0
    assert setup["z_at_flip"] > -2.0
    assert setup["vol_z_extreme"] >= 1.0
    # bullish divergence: lower price low, higher RSI low
    assert setup["extreme_low"] < setup["prior_low"]
    assert setup["rsi_extreme"] > setup["rsi_prior_low"]
    # levels: stop = flush low - 0.5*ATR, target = mean at the flip bar
    assert setup["entry_trigger"] == 95.1
    assert setup["stop_price"] == setup["extreme_low"] - 0.5 * setup["atr_5m"]
    assert setup["target_price"] == setup["sma_at_flip"]
    assert setup["stop_price"] < setup["entry_trigger"] < setup["target_price"]


def test_f01_builds_candidate_and_signal():
    release = get_release_class("f01")()
    context = _context()

    candidates = release.build_candidates(context)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.ticker == "AAPL"
    assert candidate.rank == 1
    assert candidate.score == abs(candidate.features["z_min"])

    signal = release.build_signal(context, candidate)
    assert signal is not None
    assert signal.setup_type == "dominance_flip_reversal"
    assert signal.signal_time == datetime(2024, 4, 1, 12, 55, tzinfo=NY)
    assert signal.entry_trigger == candidate.features["entry_trigger"]
    assert signal.stop_price == candidate.features["stop_price"]
    assert signal.target_price == candidate.features["target_price"]
    assert signal.metadata["release"] == "f01"
    assert signal.risk_per_share > 0


def test_f01_trade_simulates_to_mean_touch_target():
    release = get_release_class("f01")()
    context = _context()
    signal = release.build_signal(context, release.build_candidates(context)[0])

    trade = simulate_long_breakout(
        context.bars_5m["AAPL"],
        signal,
        release.exit_cutoff(context),
        ExecutionConfig(entry_slippage_bps=0.0, exit_slippage_bps=0.0, fees_bps_per_side=0.0),
    )

    assert trade is not None
    assert trade.exit_reason == "TARGET"
    assert trade.entry_time > signal.signal_time
    assert trade.pnl_pct > 0


def test_f01_rejects_flush_without_volume_climax():
    release = get_release_class("f01")()
    context = _context(bars=make_reversal_day_bars(flush_volume=500_000.0))

    assert release.build_candidates(context) == []


def test_f01_rejects_when_flush_is_not_a_lower_low():
    # flush stays above the first-leg low (95.08): no lower low, no divergence
    release = get_release_class("f01")()
    context = _context(bars=make_reversal_day_bars(flush_close=95.3))

    assert release.build_candidates(context) == []


def test_f01_rejects_illiquid_names():
    release = get_release_class("f01")()
    cheap = _context(daily=make_daily_bars(latest_close=4.0))
    assert release.build_candidates(cheap) == []

    thin_daily = make_daily_bars()
    thin_daily["volume"] = 200_000
    thin = _context(daily=thin_daily)
    assert release.build_candidates(thin) == []


def test_f01_exit_cutoff_is_1555_ny():
    release = get_release_class("f01")()
    assert release.exit_cutoff(_context()) == ny_dt(TRADE_DATE, 15, 55)
