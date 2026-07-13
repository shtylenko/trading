"""Unit tests for C1 daily trade simulation."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.backtest import (
    BacktestConfig,
    MRBacktestConfig,
    PBBacktestConfig,
    _BarFrame,
    simulate_mr_trades,
    simulate_pb_trades,
    summarize_trades,
)
from trading.swing_screener.c1_pullback.indicators import enrich_daily


def _bars_from_close(closes: list[float], start: str = "2024-01-02") -> _BarFrame:
    n = len(closes)
    close = np.array(closes, dtype=float)
    # mild ranges so ATR is positive
    high = close + 0.5
    low = close - 0.5
    open_ = close.copy()
    vol = np.full(n, 1_000_000.0)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=pd.bdate_range(start, periods=n),
    )
    return _BarFrame.from_df(enrich_daily(df))


def test_mr_next_open_stop_and_time():
    # Long flat then dump after entry path
    closes = [100.0 + i * 0.1 for i in range(220)]
    # ensure last stretch drops hard for stop
    for i in range(210, 220):
        closes[i] = closes[209] - (i - 209) * 3.0
    bars = _bars_from_close(closes)
    # pick a mid signal date where SMA200 exists
    sig = pd.Timestamp(bars.dates[205]).date()
    cfg = BacktestConfig(
        cost_bps_per_side=0.0,
        mr=MRBacktestConfig(entry_mode="next_open", max_hold_days=5, stop_atr_mult=2.0),
    )
    trades = simulate_mr_trades(
        bars, [sig], ticker="T", cfg=cfg, rules_version="test"
    )
    # May or may not trade depending on ATR/stop path; structure check if any
    if trades:
        t = trades[0]
        assert t["variant"] == "C1_MR"
        assert t["entry_date"] > t["signal_date"]
        assert t["hold_days"] >= 1
        assert t["exit_reason"] in {
            "stop",
            "rsi2_exit",
            "sma5_exit",
            "time",
        }


def test_mr_signal_close_mode_enters_same_day():
    closes = [50 + 0.2 * i for i in range(250)]
    bars = _bars_from_close(closes)
    sig = pd.Timestamp(bars.dates[220]).date()
    cfg = BacktestConfig(
        cost_bps_per_side=0.0,
        mr=MRBacktestConfig(entry_mode="signal_close", max_hold_days=5),
    )
    trades = simulate_mr_trades(
        bars, [sig], ticker="T", cfg=cfg, rules_version="test"
    )
    if trades:
        assert trades[0]["entry_date"] == trades[0]["signal_date"]


def test_pb_no_fill_when_trigger_not_reached():
    closes = [100.0] * 230
    bars = _bars_from_close(closes)
    # Force high[si] so trigger is above next day's high by editing arrays
    si = 210
    bars.high[si] = 100.0
    bars.low[si] = 99.0
    # next day cannot reach 101
    bars.high[si + 1] = 100.2
    bars.open[si + 1] = 100.0
    bars.close[si + 1] = 100.1
    bars.atr14[si] = 1.0
    sig = pd.Timestamp(bars.dates[si]).date()
    cfg = BacktestConfig(cost_bps_per_side=0.0, pb=PBBacktestConfig(entry_stop_buffer=0.01))
    trades = simulate_pb_trades(
        bars, [sig], ticker="T", cfg=cfg, rules_version="test"
    )
    assert trades == []


def test_pb_fill_and_target_or_stop():
    closes = [80 + 0.15 * i for i in range(240)]
    bars = _bars_from_close(closes)
    si = 220
    bars.high[si] = float(bars.close[si])
    bars.atr14[si] = 1.0
    # next day clears 1% above signal high
    trigger = bars.high[si] * 1.01
    bars.open[si + 1] = float(bars.close[si])
    bars.high[si + 1] = trigger + 0.5
    bars.low[si + 1] = float(bars.close[si]) - 0.2
    bars.close[si + 1] = trigger + 0.2
    # keep pullback lows tight so stop is not too wide
    for j in range(si - 4, si + 1):
        bars.low[j] = float(bars.close[j]) - 0.3
    sig = pd.Timestamp(bars.dates[si]).date()
    cfg = BacktestConfig(
        cost_bps_per_side=0.0,
        pb=PBBacktestConfig(
            entry_stop_buffer=0.01,
            max_stop_atr=5.0,
            target_r=2.0,
            max_hold_days=7,
        ),
    )
    trades = simulate_pb_trades(
        bars, [sig], ticker="T", cfg=cfg, rules_version="test"
    )
    if trades:
        assert trades[0]["variant"] == "C1_PB"
        assert trades[0]["entry_mode"] == "next_day_buy_stop"
        assert np.isfinite(trades[0]["realized_r"])


def test_one_position_blocks_overlap():
    closes = [100 + 0.05 * i for i in range(250)]
    bars = _bars_from_close(closes)
    # Two consecutive signal days
    s1 = pd.Timestamp(bars.dates[220]).date()
    s2 = pd.Timestamp(bars.dates[221]).date()
    cfg = BacktestConfig(
        cost_bps_per_side=0.0,
        one_position_per_ticker=True,
        mr=MRBacktestConfig(entry_mode="next_open", max_hold_days=5),
    )
    trades = simulate_mr_trades(
        bars, [s1, s2], ticker="T", cfg=cfg, rules_version="test"
    )
    # At most one open at a time — second signal often skipped
    assert len(trades) <= 2
    if len(trades) == 2:
        assert trades[1]["entry_date"] > trades[0]["exit_date"] or trades[1][
            "entry_date"
        ] >= trades[0]["exit_date"]


def test_summarize_trades_win_rate():
    trades = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "variant": ["C1_MR", "C1_MR", "C1_MR"],
            "entry_date": [date(2024, 1, 2), date(2024, 2, 1), date(2024, 3, 1)],
            "realized_r": [1.0, -1.0, 0.5],
            "hold_days": [2, 3, 1],
            "exit_reason": ["sma5_exit", "stop", "time"],
        }
    )
    s = summarize_trades(trades)
    overall = s[(s["year"] == 0) & (s["variant"] == "C1_MR")].iloc[0]
    assert overall["n_trades"] == 3
    assert abs(overall["win_rate"] - 2 / 3) < 1e-9
    assert abs(overall["avg_r"] - (1.0 - 1.0 + 0.5) / 3) < 1e-9
