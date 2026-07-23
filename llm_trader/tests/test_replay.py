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


def test_scanner_event_is_hidden_until_its_exact_trigger_minute(monkeypatch):
    idx = pd.date_range("2025-03-10 09:30", periods=10, freq="min", tz="America/New_York")
    df = pd.DataFrame({
        "open": [10.0] * 10, "high": [10.2] * 10, "low": [9.9] * 10,
        "close": [10.1] * 10, "volume": [100] * 10,
        "cum_vol": [100 * (i + 1) for i in range(10)], "vwap": [10.0] * 10,
        "ema9": [10.0] * 10, "ema20": [10.0] * 10, "macd": [0.1] * 10,
        "macd_signal": [0.05] * 10, "macd_hist": [0.05] * 10,
        "session_high": [10.2] * 10, "new_high": [True] * 10, "rvol_bar": [1.5] * 10,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": 9.5, "prior_high": 9.8, "prior_low": 9.0,
        "pm_high": 10.0, "pm_low": 9.7, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "09:35", 10.15, 20.0, 3.2, 1e6, "point-in-time signal")
    out = StringIO()
    replay.replay(setup, from_open=True, neutral_meta=True, scanner_event_context=True, fmt="jsonl", out=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks = rows[0], rows[1:-1]
    assert meta["scanner_event_context"] is True
    assert all("scanner_event" not in tick for tick in ticks[:5])
    assert ticks[5]["scanner_event"] == {
        "time": "09:35", "trigger": 10.15, "rvol": 3.2,
        "reason": "point-in-time signal", "signal": "historical_scanner_trigger",
    }
    assert all("scanner_event" not in tick for tick in ticks[6:])


def test_scanner_event_start_warms_privately_and_exposes_event_as_tick_zero(monkeypatch):
    idx = pd.date_range("2025-03-10 09:30", periods=10, freq="min", tz="America/New_York")
    df = pd.DataFrame({
        "open": [10.0] * 10, "high": [10.2] * 10, "low": [9.9] * 10,
        "close": [10.1] * 10, "volume": [100] * 10,
        "cum_vol": [100 * (i + 1) for i in range(10)], "vwap": [10.0] * 10,
        "ema9": [10.0] * 10, "ema20": [10.0] * 10, "macd": [0.1] * 10,
        "macd_signal": [0.05] * 10, "macd_hist": [0.05] * 10,
        "session_high": [10.2] * 10, "new_high": [True] * 10, "rvol_bar": [1.5] * 10,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": 9.5, "prior_high": 9.8, "prior_low": 9.0,
        "pm_high": 10.0, "pm_low": 9.7, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "09:35", 10.15, 20.0, 3.2, 1e6, "event")
    out = StringIO()
    replay.replay(setup, from_open=True, neutral_meta=True, scanner_event_context=True,
                  scanner_event_start=True, fmt="jsonl", out=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks = rows[0], rows[1:-1]
    assert meta["session_start"] == "scanner_event"
    assert ticks[0]["i"] == 0 and ticks[0]["time"] == "09:35"
    assert ticks[0]["scanner_event"]["trigger"] == 10.15
    assert [tick["time"] for tick in ticks] == ["09:35", "09:36", "09:37", "09:38", "09:39"]


def test_scanner_event_release_delay_waits_for_left_label_bar_close(monkeypatch):
    idx = pd.date_range("2025-03-10 09:30", periods=10, freq="min", tz="America/New_York")
    df = pd.DataFrame({
        "open": [10.0] * 10, "high": [10.2] * 10, "low": [9.9] * 10,
        "close": [10.1] * 10, "volume": [100] * 10,
        "cum_vol": [100 * (i + 1) for i in range(10)], "vwap": [10.0] * 10,
        "ema9": [10.0] * 10, "ema20": [10.0] * 10, "macd": [0.1] * 10,
        "macd_signal": [0.05] * 10, "macd_hist": [0.05] * 10,
        "session_high": [10.2] * 10, "new_high": [True] * 10, "rvol_bar": [1.5] * 10,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": 9.5, "prior_high": 9.8, "prior_low": 9.0,
        "pm_high": 10.0, "pm_low": 9.7, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "09:35", 10.15, 20.0, 3.2, 1e6, "reason")
    out = StringIO()
    replay.replay(
        setup, from_open=True, neutral_meta=True, scanner_event_context=True,
        scanner_event_start=True, scanner_event_release_delay_minutes=4,
        scanner_event_include_reason=False, fmt="jsonl", out=out,
    )
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    ticks = rows[1:-1]
    assert ticks[0]["i"] == 0 and ticks[0]["time"] == "09:39"
    assert ticks[0]["scanner_event"] == {
        "time": "09:39", "source_time": "09:35", "trigger": 10.15,
        "rvol": 3.2, "signal": "historical_scanner_trigger",
    }


def test_candlebar_context_is_opt_in_and_emits_completed_1m_and_5m_events(monkeypatch):
    idx = pd.date_range("2025-03-10 09:30", periods=10, freq="min", tz="America/New_York")
    opens = [10.00, 10.08, 10.16, 10.24, 10.32, 10.40, 10.50, 10.60, 10.70, 10.80]
    closes = [10.08, 10.16, 10.24, 10.32, 10.40, 10.50, 10.60, 10.70, 10.80, 10.90]
    highs = [close + 0.02 for close in closes]
    lows = [open_ - 0.02 for open_ in opens]
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [100] * 5 + [200] * 5,
        "cum_vol": [100, 200, 300, 400, 500, 700, 900, 1100, 1300, 1500],
        "vwap": [10.0] * 10, "ema9": closes, "ema20": opens,
        "macd": [0.1] * 10, "macd_signal": [0.05] * 10,
        "macd_hist": [0.05] * 10, "session_high": highs,
        "new_high": [True] * 10, "rvol_bar": [1.0] * 10,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": None, "prior_high": None, "prior_low": None,
        "pm_high": None, "pm_low": None, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "10:20", 12.34, None, None, None, "hidden")

    out = StringIO()
    replay.replay(
        setup, from_open=True, neutral_meta=True, five_minute_context=True,
        candlebar_context=True, fmt="jsonl", out=out,
    )
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks = rows[0], rows[1:-1]

    assert meta["candlebar_context"] is True
    assert "not a probability" in meta["candlebar_score_note"]
    assert "candle_over_candle" in {p["pattern"] for p in ticks[1]["candlebar_patterns"]}
    complete5 = ticks[9]["bar5_complete"]
    assert "candle_over_candle" in {p["pattern"] for p in complete5["candlebar_patterns"]}
    assert all(p["resolution"] == "5min" for p in complete5["candlebar_patterns"])


def test_strict_prior_three_context_withholds_aggregates_until_three_completed_bars(
    monkeypatch,
):
    idx = pd.date_range("2025-03-10 09:30", periods=20, freq="min", tz="America/New_York")
    closes = [10.0 + i * 0.01 for i in range(20)]
    df = pd.DataFrame({
        "open": [close - 0.02 for close in closes],
        "high": [close + 0.03 for close in closes],
        "low": [close - 0.04 for close in closes],
        "close": closes,
        "volume": [100] * 5 + [200] * 5 + [300] * 5 + [600] * 5,
        "cum_vol": list(pd.Series(
            [100] * 5 + [200] * 5 + [300] * 5 + [600] * 5
        ).cumsum()),
        "vwap": [9.9] * 20,
        "ema9": closes,
        "ema20": [close - 0.01 for close in closes],
        "macd": [0.1] * 20,
        "macd_signal": [0.05] * 20,
        "macd_hist": [0.05] * 20,
        "session_high": [close + 0.03 for close in closes],
        "new_high": [True] * 20,
        "rvol_bar": [1.5] * 20,
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": None, "prior_high": None, "prior_low": None,
        "pm_high": None, "pm_low": None, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "10:20", 12.34, None, None, None, "hidden")

    out = StringIO()
    replay.replay(
        setup,
        from_open=True,
        neutral_meta=True,
        five_minute_context=True,
        strict_prior_three_context=True,
        fmt="jsonl",
        out=out,
    )
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks = rows[0], rows[1:-1]
    complete = [tick["bar5_complete"] for tick in ticks if tick["bar5_complete"]]

    assert meta["strict_prior_three_context"] is True
    assert [bar["prior_3_count"] for bar in complete] == [0, 1, 2, 3]
    for bar in complete[:3]:
        assert bar["prior_3_high"] is None
        assert bar["prior_3_low"] is None
        assert bar["prior_3_avg_volume"] is None
        assert bar["volume_ratio"] is None
    assert complete[3]["prior_3_high"] is not None
    assert complete[3]["prior_3_low"] is not None
    assert complete[3]["prior_3_avg_volume"] == 1000.0
    assert complete[3]["volume_ratio"] == 3.0


def test_complete_five_minute_contract_skips_gapped_buckets(monkeypatch):
    # 09:33 is absent: the 09:30 bucket must not become a made-up 5m candle.
    idx = pd.DatetimeIndex([
        pd.Timestamp("2025-03-10 09:30", tz="America/New_York"),
        pd.Timestamp("2025-03-10 09:31", tz="America/New_York"),
        pd.Timestamp("2025-03-10 09:32", tz="America/New_York"),
        pd.Timestamp("2025-03-10 09:34", tz="America/New_York"),
        *pd.date_range("2025-03-10 09:35", periods=5, freq="min", tz="America/New_York"),
    ])
    closes = [10.0 + i * 0.01 for i in range(len(idx))]
    df = pd.DataFrame({
        "open": [close - 0.01 for close in closes],
        "high": [close + 0.02 for close in closes],
        "low": [close - 0.03 for close in closes],
        "close": closes,
        "volume": [100] * len(idx),
        "cum_vol": [100 * (i + 1) for i in range(len(idx))],
        "vwap": [9.9] * len(idx),
        "ema9": closes,
        "ema20": [close - 0.01 for close in closes],
        "macd": [0.1] * len(idx),
        "macd_signal": [0.05] * len(idx),
        "macd_hist": [0.05] * len(idx),
        "session_high": [close + 0.02 for close in closes],
        "new_high": [True] * len(idx),
        "rvol_bar": [1.5] * len(idx),
    }, index=idx)
    monkeypatch.setattr(replay, "fetch_minute_bars", lambda *args, **kwargs: df)
    monkeypatch.setattr(replay, "_enrich", lambda frame: frame)
    monkeypatch.setattr(replay, "_context", lambda *args, **kwargs: {
        "prior_close": None, "prior_high": None, "prior_low": None,
        "pm_high": None, "pm_low": None, "context_warnings": [],
    })
    setup = Setup("TEST", date(2025, 3, 10), "10:20", 12.34, None, None, None, "hidden")
    out = StringIO()
    replay.replay(
        setup, from_open=True, neutral_meta=True, five_minute_context=True,
        strict_prior_three_context=True, require_complete_five_minute_bars=True,
        fmt="jsonl", out=out,
    )
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    meta, ticks = rows[0], rows[1:-1]
    by_time = {tick["time"]: tick for tick in ticks}

    assert meta["require_complete_five_minute_bars"] is True
    assert by_time["09:34"]["bar5_complete"] is None
    first = by_time["09:39"]["bar5_complete"]
    assert first["time"] == "09:35"
    assert first["observed_minute_count"] == 5
    assert first["prior_3_count"] == 0


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
