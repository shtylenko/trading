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
