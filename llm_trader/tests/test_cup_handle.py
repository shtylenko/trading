"""Unit tests for cup-and-handle family (no live provider calls)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from trading.llm_trader.store import EntryStore, setup_id
from trading.llm_trader.strategies import get_strategy, list_strategies
from trading.llm_trader.strategies.cup_handle.config import CupHandleConfig
from trading.llm_trader.strategies.cup_handle.patterns import detect_from_frame


def _daily_index(n: int, start: str = "2024-06-03"):
    # business days
    idx = pd.bdate_range(start=start, periods=n, tz="America/New_York")
    return idx


def _synthetic_cup_breakout(n_pre=100, cup=40, handle=8, post=5):
    """Build a synthetic daily series with a clear cup, tight handle, and breakout.

    Layout:
      strong multi-month uptrend → left lip → rounded ~15% cup → tight handle → breakout.
    """
    warmup = 250
    n = warmup + n_pre + cup + handle + post
    idx = _daily_index(n)
    closes = []
    px = 80.0
    # long warm-up uptrend (keeps SMA50 rising through a moderate cup)
    for _ in range(warmup + n_pre):
        px *= 1.0025
        closes.append(px)
    left_lip = px
    depth = 0.15 * left_lip  # 15% cup — inside 12–35% band
    for i in range(cup):
        t = i / max(cup - 1, 1)
        # rounded bottom via sine
        level = left_lip - depth * np.sin(np.pi * t)
        closes.append(float(level))
    # right lip near left
    closes[-1] = left_lip * 0.995
    handle_high = left_lip * 0.997
    for i in range(handle):
        # coil under handle high with small swings
        closes.append(handle_high * (0.988 + 0.004 * (0.5 + 0.5 * np.sin(i))))
    # breakout day
    closes.append(handle_high * 1.025)
    for i in range(post - 1):
        closes.append(handle_high * (1.025 + 0.01 * (i + 1)))

    closes = np.array(closes[: len(idx)], dtype=float)
    high = closes * 1.008
    low = closes * 0.992
    open_ = closes.copy()
    bi = warmup + n_pre + cup + handle
    if bi < len(closes):
        open_[bi] = handle_high * 0.995
        high[bi] = handle_high * 1.04
        low[bi] = handle_high * 0.99
        closes[bi] = handle_high * 1.025
    # cup lows need true troughs on the low series
    cup0 = warmup + n_pre
    for i in range(cup):
        t = i / max(cup - 1, 1)
        trough = left_lip - depth * np.sin(np.pi * t)
        low[cup0 + i] = trough * 0.995
        high[cup0 + i] = max(high[cup0 + i], trough * 1.01)

    vol = np.full(len(idx), 3_000_000.0)
    h0 = warmup + n_pre + cup
    vol[h0 : h0 + handle] = 1_400_000.0
    if bi < len(vol):
        vol[bi] = 9_000_000.0

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": closes, "volume": vol},
        index=idx,
    )
    breakout_day = idx[bi].date() if bi < len(idx) else idx[-1].date()
    return df, breakout_day, float(handle_high)


def test_registry_lists_cup_handle():
    ids = list_strategies()
    assert "warrior" in ids
    assert "cup_handle" in ids
    s = get_strategy("cup_handle")
    assert s.horizon.kind == "multi_day"
    assert s.risk.risk_budget == 500.0
    assert s.default_db_path().name == "entries.db"


def test_detect_synthetic_cup_breakout():
    df, breakout_day, handle_high = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        handle_min_bars=3,
        handle_max_bars=15,
        # The fixture's cup recovery leaves a flat SMA50; isolate the geometry
        # and causal timing contract in this unit test.
        require_sma50_rising=False,
        require_spy_above_sma50=False,
    )
    entries = detect_from_frame(df, "TEST", cfg)
    assert entries, "expected at least one cup_handle entry on synthetic series"
    e = entries[0]
    assert e.strategy == "cup_handle"
    assert e.pattern == "cup_handle"
    assert e.features.get("stop_px") is not None
    assert e.features.get("target1_px") is not None
    assert e.features.get("target2_px") is not None
    assert e.features["signal_kind"] == "prebreak_arm"
    assert e.time_et == "16:00"
    assert e.day < breakout_day
    assert e.features["stop_distance"] == pytest.approx(
        1.5 * e.features["atr"], rel=1e-3
    )
    assert e.entry_px > 0
    # entry should be near handle high
    assert abs(e.entry_px - handle_high) / handle_high < 0.05


def test_store_strategy_uniqueness(tmp_path):
    df, _, _ = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        require_sma50_rising=False,
    )
    entries = detect_from_frame(df, "TEST", cfg)
    if not entries:
        pytest.skip("synthetic detector found no entry — geometry thresholds")
    e = entries[0]
    store = EntryStore(tmp_path / "c.db")
    store.upsert(e)
    store.upsert(e)
    assert store.count(strategy="cup_handle") == 1
    assert store.count() == 1
    sid = setup_id(e.ticker, e.day, e.pattern, strategy="cup_handle")
    assert store.all_rows()[0]["setup_id"] == sid
    # warrior row same ticker/day/pattern is a different key
    from trading.llm_trader.models import Entry

    w = Entry(
        ticker=e.ticker,
        day=e.day,
        time_et="09:45",
        pattern="cup_handle",  # same pattern string — different strategy
        entry_px=1.0,
        bar_close=1.0,
        reason="warrior-style placeholder",
        strategy="warrior",
    )
    store.upsert(w)
    assert store.count() == 2
    store.close()


def test_store_sync_scope_removes_stale_rows_only_after_successful_replacement(tmp_path):
    from trading.llm_trader.models import Entry

    store = EntryStore(tmp_path / "c.db")
    old = Entry(
        ticker="TEST", day=date(2025, 1, 2), time_et="16:00", pattern="cup_handle",
        entry_px=10.0, bar_close=9.9, reason="old", strategy="cup_handle",
    )
    keep = Entry(
        ticker="OTHER", day=date(2025, 1, 2), time_et="16:00", pattern="cup_handle",
        entry_px=10.0, bar_close=9.9, reason="other", strategy="cup_handle",
    )
    store.upsert(old)
    store.upsert(keep)
    removed = store.sync_scope(
        [], strategy="cup_handle", tickers=["TEST"],
        start_day="2025-01-01", end_day="2025-01-31",
    )
    assert removed == 1
    assert store.count(strategy="cup_handle") == 1
    assert store.all_rows(strategy="cup_handle")[0]["ticker"] == "OTHER"
    store.close()


def test_runner_fails_closed_without_mutating_existing_entries(tmp_path, monkeypatch):
    from trading.llm_trader.models import Entry
    from trading.llm_trader.strategies.cup_handle import runner as cup_runner

    db = tmp_path / "entries.db"
    with EntryStore(db) as store:
        store.upsert(Entry(
            ticker="TEST", day=date(2025, 1, 2), time_et="16:00", pattern="cup_handle",
            entry_px=10.0, bar_close=9.9, reason="existing", strategy="cup_handle",
        ))
    cfg = CupHandleConfig(
        start=date(2025, 1, 1), end=date(2025, 1, 31), db_path=db,
    )

    def broken(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(cup_runner, "detect_ticker", broken)
    with pytest.raises(RuntimeError, match="failed closed"):
        cup_runner.run_scan(cfg, symbols=["TEST"])
    with EntryStore(db) as store:
        assert store.count(strategy="cup_handle") == 1


def test_runner_replaces_completed_scope_and_writes_manifest(tmp_path, monkeypatch):
    from trading.llm_trader.models import Entry
    from trading.llm_trader.strategies.cup_handle import runner as cup_runner

    db = tmp_path / "entries.db"
    cfg = CupHandleConfig(
        start=date(2025, 1, 1), end=date(2025, 1, 31), db_path=db,
    )
    with EntryStore(db) as store:
        store.upsert(Entry(
            ticker="TEST", day=date(2025, 1, 2), time_et="16:00", pattern="cup_handle",
            entry_px=10.0, bar_close=9.9, reason="stale", strategy="cup_handle",
        ))

    fresh = Entry(
        ticker="TEST", day=date(2025, 1, 3), time_et="16:00", pattern="cup_handle",
        entry_px=11.0, bar_close=10.9, reason="fresh", strategy="cup_handle",
    )
    monkeypatch.setattr(cup_runner, "detect_ticker", lambda *_args, **_kwargs: [fresh])
    stats = cup_runner.run_scan(cfg, symbols=["TEST"])
    assert stats.entries_found == 1
    assert stats.stale_entries_removed == 1
    with EntryStore(db) as store:
        rows = store.all_rows(strategy="cup_handle")
        assert [(r["ticker"], r["date"]) for r in rows] == [("TEST", "2025-01-03")]
    assert db.with_suffix(".last_scan.json").exists()


def test_fade_series_no_entry():
    idx = _daily_index(300)
    closes = np.linspace(200, 50, len(idx))  # relentless downtrend
    df = pd.DataFrame(
        {
            "open": closes * 1.01,
            "high": closes * 1.02,
            "low": closes * 0.98,
            "close": closes,
            "volume": np.full(len(idx), 3_000_000.0),
        },
        index=idx,
    )
    cfg = CupHandleConfig(start=date(2024, 1, 1), end=date(2026, 12, 31), price_min=10.0)
    assert detect_from_frame(df, "FADE", cfg) == []


def test_confirmed_breakout_is_labelled_after_close_not_as_open_fill():
    df, breakout_day, _ = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        require_sma50_rising=False,
        signal_mode="confirmed_breakout",
    )
    entries = detect_from_frame(df, "TEST", cfg)
    assert entries
    entry = entries[0]
    assert entry.day == breakout_day
    assert entry.time_et == "16:00"
    assert entry.features["signal_kind"] == "confirmed_breakout"
    assert entry.features["breakout_close_above_trigger"] is True


def test_regime_filter_requires_explicit_market_dates():
    df, _, _ = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        require_sma50_rising=False,
        require_spy_above_sma50=True,
    )
    with pytest.raises(ValueError, match="SPY regime dates"):
        detect_from_frame(df, "TEST", cfg)
