"""Tests for the no-trigger-leak 5-minute replay contract."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO

import pandas as pd

from trading.llm_trader import replay
from trading.llm_trader.replay import Setup


def test_neutral_open_stream_hides_scanner_trigger_and_emits_completed_bar5(monkeypatch):
    idx = pd.date_range("2025-03-10 09:30", periods=10, freq="min", tz="America/New_York")
    df = pd.DataFrame({
        "open": [10.0] * 10,
        "high": [10.1 + i * 0.01 for i in range(10)],
        "low": [9.9] * 10,
        "close": [10.05 + i * 0.01 for i in range(10)],
        "volume": [100] * 10,
        "cum_vol": [100 * (i + 1) for i in range(10)],
        "vwap": [10.0] * 10,
        "ema9": [10.0] * 10,
        "ema20": [10.0] * 10,
        "macd": [0.1] * 10,
        "macd_signal": [0.05] * 10,
        "macd_hist": [0.05] * 10,
        "session_high": [10.1 + i * 0.01 for i in range(10)],
        "new_high": [True] * 10,
        "rvol_bar": [None] * 10,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": 9.5, "prior_high": 9.8, "prior_low": 9.0,
        "pm_high": 10.0, "pm_low": 9.7, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "10:20", 12.34, 20.0, 9.9, 1e6, "scanner reason")

    out = StringIO()
    replay.replay(setup, from_open=True, neutral_meta=True, five_minute_context=True,
                  fmt="jsonl", out=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks, end = rows[0], rows[1:-1], rows[-1]

    assert meta["session_start"] == "09:30"
    for hidden in ("entry_time", "entry_px", "anchor_px", "rvol", "reason"):
        assert hidden not in meta
    assert [t["time"] for t in ticks[:2]] == ["09:30", "09:31"]
    assert all("vs_anchor_pct" not in t and "is_entry_bar" not in t for t in ticks)
    assert ticks[3]["bar5_complete"] is None
    first = ticks[4]["bar5_complete"]
    assert first == {
        "time": "09:30", "o": 10.0, "h": 10.14, "l": 9.9, "c": 10.09, "v": 500,
        "prior_3_high": None, "prior_3_low": None, "prior_3_avg_volume": None,
        "volume_ratio": None,
    }
    second = ticks[9]["bar5_complete"]
    assert second["time"] == "09:35" and second["prior_3_high"] == 10.14
    assert second["prior_3_low"] == 9.9 and second["volume_ratio"] == 1.0
    assert "run_vs_anchor_pct" not in end


def test_causal_cup_plan_is_hidden_in_meta_and_revealed_on_plan_bar(monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=330, tz="America/New_York")
    close = pd.Series(range(100, 430), index=idx, dtype=float)
    daily = pd.DataFrame({
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.7,
        "close": close,
        "volume": 3_000_000,
    }, index=idx)
    setup_day = idx[250].date()
    setup = Setup(
        "TEST", setup_day, "16:00", 351.0, None, None, None,
        "causal plan", strategy="cup_handle", pattern="cup_handle",
        features={
            "signal_kind": "prebreak_arm",
            "signal_as_of": setup_day.isoformat(),
            "entry_trigger": 351.0,
            "stop_px": 345.0,
            "target1_px": 360.0,
            "target2_px": 370.0,
            "atr": 4.0,
            "cup_depth_px": 18.0,
            "arm_expiry_bars": 5,
            "max_entry_gap_atr": 0.5,
        },
    )
    monkeypatch.setattr(replay, "fetch_daily_bars", lambda *_args, **_kwargs: daily)
    out = StringIO()
    replay.replay_daily(setup, neutral_meta=True, fmt="jsonl", out=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta = rows[0]
    setup_tick = next(row for row in rows if row.get("is_setup_day"))

    assert "entry_px" not in meta and "handle_high" not in meta
    assert setup_tick["scanner_plan"] == {
        "signal_as_of": setup_day.isoformat(),
        "trigger": 351.0,
        "stop": 345.0,
        "target1": 360.0,
        "target2": 370.0,
        "atr": 4.0,
        "cup_depth_px": 18.0,
        "arm_expiry_bars": 5,
        "max_entry_gap_atr": 0.5,
    }


def test_daily_replay_fails_closed_when_sma200_warmup_is_unavailable(monkeypatch):
    # The requested setup is deliberately too early in this frame for a 200-day
    # SMA.  Replay must refuse the whole session rather than reveal null values
    # and allow an agent to trade around them.
    idx = pd.bdate_range("2025-01-02", periods=160, tz="America/New_York")
    close = pd.Series(range(100, 260), index=idx, dtype=float)
    daily = pd.DataFrame({
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.7,
        "close": close,
        "volume": 3_000_000,
    }, index=idx)
    setup = Setup(
        "TEST", idx[100].date(), "16:00", 200.0, None, None, None,
        "must have all indicators", strategy="cup_handle", pattern="cup_handle",
    )
    monkeypatch.setattr(replay, "fetch_daily_bars", lambda *_args, **_kwargs: daily)
    out = StringIO()

    rc = replay.replay_daily(setup, fmt="jsonl", out=out)

    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    assert rc == 3
    assert rows == [{
        "type": "error",
        "message": rows[0]["message"],
    }]
    assert "sma200" in rows[0]["message"]
    assert "Refusing to emit a tradable stream" in rows[0]["message"]
