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
from trading.llm_trader.strategies.cup_handle import patterns as cup_patterns


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


def _geometry_candidate(
    *,
    left_lip_i: int,
    cup_window_bars: int = 60,
    handle_bars: int = 6,
    handle_depth_px: float = 2.0,
    lip_diff_pct: float = 1.0,
    handle_volume_fraction: float = 0.4,
    trough_centrality: float = 0.5,
) -> cup_patterns.CupGeometry:
    """A valid-looking candidate for order-independent selection tests."""
    return cup_patterns.CupGeometry(
        left_lip_i=left_lip_i,
        cup_low_i=left_lip_i + 20,
        right_lip_i=left_lip_i + 40,
        handle_start_i=left_lip_i + 41,
        handle_end_i=left_lip_i + 46,
        left_lip_px=100.0,
        cup_low_px=80.0,
        right_lip_px=99.5,
        handle_high=99.0,
        handle_low=99.0 - handle_depth_px,
        cup_depth_pct=20.0,
        cup_depth_px=20.0,
        handle_depth_px=handle_depth_px,
        cup_window_bars=cup_window_bars,
        lip_to_lip_bars=40,
        handle_bars=handle_bars,
        lip_diff_pct=lip_diff_pct,
        handle_volume_fraction=handle_volume_fraction,
        trough_centrality=trough_centrality,
    )


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
    selection = e.features["geometry_selection"]
    assert selection["definition"] == "geometry_selection_v1"
    assert selection["candidate_count"] >= 1
    assert 0.0 <= selection["score"] <= 1.0


def test_geometry_selection_is_order_independent_and_uses_stable_ties():
    cfg = CupHandleConfig()
    weak = _geometry_candidate(
        left_lip_i=10,
        handle_depth_px=7.0,
        lip_diff_pct=4.5,
        handle_volume_fraction=0.8,
        trough_centrality=0.85,
    )
    strong = _geometry_candidate(left_lip_i=20)

    selected = cup_patterns._select_cup_and_handle([weak, strong], cfg)
    reversed_selected = cup_patterns._select_cup_and_handle([strong, weak], cfg)
    assert selected.left_lip_i == reversed_selected.left_lip_i == strong.left_lip_i
    assert selected.selection_candidate_count == reversed_selected.selection_candidate_count == 2
    assert selected.selection_score == reversed_selected.selection_score
    assert selected.selection_components == reversed_selected.selection_components

    # Equal structural score resolves by the declared longer-cup tie-breaker,
    # not whichever candidate happened to be enumerated first.
    short = _geometry_candidate(left_lip_i=30, cup_window_bars=40)
    long = _geometry_candidate(left_lip_i=40, cup_window_bars=80)
    tied = cup_patterns._select_cup_and_handle([short, long], cfg)
    assert tied.left_lip_i == long.left_lip_i
    assert tied.selection_candidate_count == 2


def test_scanner_attaches_causal_market_and_quality_diagnostics_without_gating():
    """Diagnostics enrich evidence only; they cannot alter the v0.7 plan."""
    df, _breakout_day, _handle_high = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        handle_min_bars=3,
        handle_max_bars=15,
        require_sma50_rising=False,
    )
    baseline = detect_from_frame(df, "TEST", cfg)
    assert baseline
    regime = {
        ts.date(): {
            "schema_version": 1,
            "as_of": ts.date().isoformat(),
            "close": 600.0,
            "sma50": 590.0,
            "sma200": 550.0,
            "above_sma50": True,
            "above_sma200": True,
            "sma50_rising": True,
            "regime": "above_sma50_and_sma200",
        }
        for ts in df.index
    }
    enriched = detect_from_frame(df, "TEST", cfg, market_regime_features=regime)

    assert _plan_keys(enriched) == _plan_keys(baseline)
    features = enriched[0].features
    assert features["market_regime"] == regime[enriched[0].day]
    quality = features["formation_quality"]
    assert quality["definition"] == "formation_quality_v1_diagnostics_only"
    assert 0.0 <= quality["score"] <= 1.0
    assert set(quality["components"]) == {
        "handle_high_position", "handle_shallowness", "lip_alignment",
        "trough_centrality", "volume_dryup",
    }


def test_scanner_fails_closed_when_candidate_lacks_market_diagnostic():
    df, _breakout_day, _handle_high = _synthetic_cup_breakout()
    cfg = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        handle_min_bars=3,
        handle_max_bars=15,
        require_sma50_rising=False,
    )
    candidate_day = detect_from_frame(df, "TEST", cfg)[0].day
    incomplete_regime = {
        ts.date(): {"as_of": ts.date().isoformat()}
        for ts in df.index
        if ts.date() != candidate_day
    }
    with pytest.raises(RuntimeError, match="SPY regime diagnostics are unavailable"):
        detect_from_frame(df, "TEST", cfg, market_regime_features=incomplete_regime)


def test_pit_membership_dates_do_not_reset_or_poison_arm_cooldown():
    """Only sessions where the ticker was eligible can create scanner state."""
    df, _breakout_day, _handle_high = _synthetic_cup_breakout(post=20)
    base = CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        handle_min_bars=3,
        handle_max_bars=15,
        require_sma50_rising=False,
        arm_expiry_bars=5,
    )
    baseline = detect_from_frame(df, "TEST", base)
    assert len(baseline) >= 2
    first, later = baseline[:2]

    # With a long cooldown, a continuous eligible history retains only
    # the first arm. If the first session was outside this ticker's PIT
    # membership, it was never actionable and must not suppress the later arm.
    cooldown_cfg = CupHandleConfig.from_dict({**base.to_dict(), "arm_expiry_bars": 20})
    continuous = detect_from_frame(df, "TEST", cooldown_cfg)
    assert [entry.day for entry in continuous] == [first.day]
    eligible_later = detect_from_frame(
        df, "TEST", cooldown_cfg, eligible_plan_dates={later.day},
    )
    assert [entry.day for entry in eligible_later] == [later.day]


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


def test_runner_aborts_immediately_on_missing_shared_market_diagnostic(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import runner as cup_runner
    from trading.llm_trader.strategies.cup_handle.patterns import MarketRegimeDataError

    calls = []

    def missing_market(ticker, *_args, **_kwargs):
        calls.append(ticker)
        raise MarketRegimeDataError("SPY regime diagnostics are unavailable for candidate setup date 2026-06-26")

    monkeypatch.setattr(cup_runner, "detect_ticker", missing_market)
    with pytest.raises(RuntimeError, match="failed closed: SPY regime diagnostics"):
        cup_runner.scan_scope(CupHandleConfig(), symbols=["AAA", "BBB"])
    assert calls == ["AAA"], "shared-indicator breach must not be counted-and-continued"


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


def test_market_regime_features_use_sma200_complete_history(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import patterns as cup_patterns

    idx = _daily_index(280)
    closes = np.linspace(400.0, 680.0, len(idx))
    spy = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(len(idx), 100_000_000.0),
        },
        index=idx,
    )
    start, end = idx[220].date(), idx[260].date()
    cfg = CupHandleConfig(start=start, end=end)

    requested = {}

    def fake_fetch(ticker, resolution, *, start, end, adjustment="raw", **_kwargs):
        requested.update(ticker=ticker, resolution=resolution, start=start, end=end)
        return spy

    monkeypatch.setattr(cup_patterns, "fetch_bars", fake_fetch)
    records = cup_patterns.fetch_market_regime_features(cfg)

    assert requested["ticker"] == "SPY"
    assert (cfg.start - requested["start"].date()).days >= 420
    assert set(records) == {ts.date() for ts in idx[220:261]}
    first = records[start]
    assert first["as_of"] == start.isoformat()
    assert first["above_sma50"] is True
    assert first["above_sma200"] is True
    assert first["sma50_rising"] is True

    # A missing SPY bar for an expected market session is a scope-wide data
    # integrity error. It must fail before the scanner reaches any ticker.
    from trading.marketdata.calendar import trading_days_in_range

    missing_day = trading_days_in_range(start, end)[2]
    incomplete = spy[spy.index.date != missing_day]
    monkeypatch.setattr(cup_patterns, "fetch_bars", lambda *_args, **_kwargs: incomplete)
    with pytest.raises(cup_patterns.MarketRegimeDataError, match="incomplete"):
        cup_patterns.fetch_market_regime_features(cfg)


# --------------------------------------------------------------------------- #
# As-of (single-date) entry scan
# --------------------------------------------------------------------------- #
def _asof_base_cfg() -> CupHandleConfig:
    return CupHandleConfig(
        start=date(2024, 1, 1),
        end=date(2026, 12, 31),
        price_min=10.0,
        avg_vol_min=500_000,
        cup_min_bars=15,
        cup_max_bars=80,
        handle_min_bars=3,
        handle_max_bars=15,
        require_sma50_rising=False,
        require_spy_above_sma50=False,
    )


def _plan_keys(arms):
    """Comparable identity of each arm's published plan."""
    return sorted(
        (
            a.ticker,
            a.day.isoformat(),
            a.features["formation_key"],
            a.features["entry_trigger"],
            a.features["stop_px"],
            a.features["target1_px"],
            a.features["target2_px"],
        )
        for a in arms
    )


def test_detector_asof_is_invariant_to_future_bars():
    """The plan for day D must not change when bars after D exist (no look-ahead)."""
    from dataclasses import replace

    from trading.llm_trader.strategies.cup_handle.patterns import detect_from_frame

    df, _breakout, _hh = _synthetic_cup_breakout()
    base = _asof_base_cfg()
    discovered = detect_from_frame(df, "T", base)
    assert discovered, "fixture should arm at least once"
    d = discovered[0].day

    cfg_d = replace(base, start=d, end=d)
    with_future = detect_from_frame(df, "T", cfg_d)
    truncated = df[df.index.date <= d]
    without_future = detect_from_frame(truncated, "T", cfg_d)

    assert with_future, "expected an arm on the as-of day"
    assert _plan_keys(with_future) == _plan_keys(without_future)
    # The truncated frame really did drop the post-D breakout/continuation bars.
    assert truncated.index.date.max() == d
    assert len(truncated) < len(df)


def test_scan_asof_matches_detector_and_never_requests_future_bars(monkeypatch):
    """scan_asof reuses the shared detector and only ever fetches bars <= D."""
    import pandas as pd
    from dataclasses import replace

    from trading.llm_trader.strategies.cup_handle import entry_scan
    from trading.llm_trader.strategies.cup_handle import patterns as cup_patterns
    from trading.llm_trader.strategies.cup_handle.patterns import detect_from_frame

    df, _breakout, _hh = _synthetic_cup_breakout()
    base = _asof_base_cfg()
    d = detect_from_frame(df, "T", base)[0].day

    requested_ends = []

    def fake_fetch(ticker, resolution, *, start, end, adjustment="raw", **kwargs):
        requested_ends.append(end)
        # A faithful provider never reveals a bar dated after the requested end.
        return df[df.index <= pd.Timestamp(end)]

    monkeypatch.setattr(cup_patterns, "fetch_bars", fake_fetch)

    result = entry_scan.scan_asof(d, ["t"], base)  # lower-case exercises normalization

    assert result.symbols_scanned == ["T"]
    assert result.symbols_failed == []
    assert result.arms, "expected at least one arm on the as-of day"

    # Parity: identical to the shared detector run over <= D bars.
    cfg_d = replace(base, start=d, end=d)
    ref = detect_from_frame(df[df.index.date <= d], "T", cfg_d)
    assert _plan_keys(result.arms) == _plan_keys(ref)

    # No look-ahead: every provider request ended on or before D.
    assert requested_ends, "detector should have fetched bars"
    assert all(pd.Timestamp(e).date() <= d for e in requested_ends)


def test_detect_ticker_fails_closed_when_provider_returns_no_bars(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import patterns as cup_patterns

    monkeypatch.setattr(cup_patterns, "fetch_bars", lambda *_args, **_kwargs: pd.DataFrame())
    with pytest.raises(RuntimeError, match="no daily market-data bars available for MISSING"):
        cup_patterns.detect_ticker("MISSING", CupHandleConfig())


def test_scanner_rejects_plan_when_visible_replay_history_lacks_an_indicator():
    from trading.llm_trader.indicators import DAILY_REPLAY_REQUIRED_INDICATORS
    from trading.llm_trader.strategies.cup_handle.patterns import (
        _replay_window_indicators_available,
    )

    frame = pd.DataFrame(index=range(241))
    for field in DAILY_REPLAY_REQUIRED_INDICATORS:
        frame[field] = True if field.startswith("above_") or field == "sma50_rising" else 1.0
    # The setup bar has SMA200, but the first twenty visible planning bars do
    # not. This must be rejected by the scanner rather than fail later in replay.
    frame.loc[180:199, "sma200"] = np.nan

    assert not _replay_window_indicators_available(frame, 220)
    frame["sma200"] = 1.0
    assert _replay_window_indicators_available(frame, 220)


def test_scan_asof_fails_closed_on_provider_error(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import entry_scan

    base = _asof_base_cfg()

    def boom(*_args, **_kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(entry_scan, "detect_ticker", boom)
    with pytest.raises(RuntimeError, match="failed closed"):
        entry_scan.scan_asof(date(2025, 6, 2), ["AAA", "BBB"], base)


def test_scan_asof_tolerates_failures_within_the_configured_rate(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import entry_scan

    base = _asof_base_cfg()
    base.max_scan_failure_rate = 0.5  # allow up to half the names to fail

    def flaky(sym, *_args, **_kwargs):
        if sym == "BAD":
            raise RuntimeError("provider hiccup")
        return []

    monkeypatch.setattr(entry_scan, "detect_ticker", flaky)
    result = entry_scan.scan_asof(date(2025, 6, 2), ["GOOD", "BAD"], base)
    assert result.symbols_failed == ["BAD"]
    assert result.symbols_scanned == ["GOOD"]
    assert result.arms == []


def test_sp500_universe_file_is_loadable_and_deduped():
    import json
    from pathlib import Path

    from trading.llm_trader.strategies.cup_handle import entry_scan

    path = Path(__file__).resolve().parents[1] / "batch" / "cup_handle" / "universe_sp500.json"
    assert path.exists(), "S&P 500 universe file should be checked in"
    syms = entry_scan._load_universe_file(path)
    assert len(syms) == len(set(syms)), "no duplicate tickers"
    assert 490 <= len(syms) <= 510, f"expected ~503 S&P 500 tickers, got {len(syms)}"
    # class shares are kept in dot form (the provider serves BRK.B / BF.B)
    assert "BRK.B" in syms and "BF.B" in syms
    # the stored count matches the symbols list
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["count"] == len(syms)


def test_scan_report_builds_chart_payload_from_arms(monkeypatch):
    import pandas as pd

    from trading.llm_trader.strategies.cup_handle import entry_scan, scan_report
    from trading.llm_trader.strategies.cup_handle import patterns as cup_patterns
    from trading.llm_trader.strategies.cup_handle.patterns import detect_from_frame

    df, _breakout, _hh = _synthetic_cup_breakout()
    base = _asof_base_cfg()
    d = detect_from_frame(df, "T", base)[0].day

    # the report re-fetches per ticker; serve the same synthetic frame, honoring `end`
    def fake_fetch(ticker, resolution, *, start, end, adjustment="raw", **kwargs):
        return df[df.index <= pd.Timestamp(end)]

    monkeypatch.setattr(cup_patterns, "fetch_bars", fake_fetch)
    monkeypatch.setattr(scan_report, "fetch_bars", fake_fetch)

    result = entry_scan.scan_asof(d, ["T"], base)
    report = scan_report.build_report(result, base)

    assert report["as_of"] == d.isoformat()
    assert len(report["tickers"]) == 1
    t = report["tickers"][0]
    assert t["ticker"] == "T"
    # the labels the user asked for are present
    assert t["cup_depth_pct"] is not None
    assert t["arm_expiry_bars"] == base.arm_expiry_bars
    # chart series and overlays are populated
    assert len(t["bars"]) > 20
    assert t["sma50"], "SMA overlay should be present"
    assert {pl["title"] for pl in t["priceLines"]} >= {"trigger", "stop", "T1", "T2"}
    # cup-geometry markers plus the ARM marker
    assert any(m["text"] == "ARM" for m in t["markers"])
    assert sum(1 for m in t["markers"] if "lip" in m["text"] or "cup low" in m["text"]) == 3
    # markers land on real bar dates in the window
    bar_times = {b["time"] for b in t["bars"]}
    assert all(m["time"] in bar_times for m in t["markers"])

    # self-contained HTML: library + data inlined, no external resource loads
    # (an SVG xmlns="http://www.w3.org/..." inside the inlined lib is not a fetch)
    page = scan_report.render_html(report)
    assert "LightweightCharts" in page and "createChart" in page
    assert "unpkg" not in page
    assert 'src="http' not in page and "href=\"http" not in page
    assert '"ticker":"T"' in page


def test_scan_asof_progress_bar_does_not_change_results(monkeypatch):
    from trading.llm_trader.strategies.cup_handle import entry_scan

    base = _asof_base_cfg()
    monkeypatch.setattr(entry_scan, "detect_ticker", lambda *_a, **_k: [])
    result = entry_scan.scan_asof(date(2025, 6, 2), ["AAA", "BBB"], base, progress=True)
    assert result.symbols_scanned == ["AAA", "BBB"]
    assert result.symbols_failed == []
    assert result.arms == []


def test_load_universe_file_missing_path_is_a_clean_error(tmp_path):
    from trading.llm_trader.strategies.cup_handle import entry_scan

    with pytest.raises(ValueError, match="not found"):
        entry_scan._load_universe_file(tmp_path / "typo_universe.json")


def test_resolve_universe_refuses_live_listings_for_historical_date():
    from trading.llm_trader.strategies.cup_handle import entry_scan

    with pytest.raises(ValueError, match="point-in-time"):
        entry_scan.resolve_universe(
            date(2020, 1, 2),
            symbols=None,
            universe_file=None,
            exchanges=("XNAS",),
            today=date(2026, 7, 16),
        )


def test_resolve_universe_rejects_unverified_explicit_historical_symbols():
    from trading.llm_trader.strategies.cup_handle import entry_scan

    with pytest.raises(ValueError, match="unverified explicit symbols"):
        entry_scan.resolve_universe(
            date(2020, 1, 2),
            symbols=["aaa", "bbb"],
            universe_file=None,
            exchanges=("XNAS",),
            today=date(2026, 7, 16),
        )


def test_resolve_universe_allows_explicit_historical_symbols_only_with_exploratory_opt_in():
    from trading.llm_trader.strategies.cup_handle import entry_scan

    syms = entry_scan.resolve_universe(
        date(2020, 1, 2),
        symbols=["aaa", "bbb"],
        universe_file=None,
        exchanges=("XNAS",),
        today=date(2026, 7, 16),
        allow_unverified_historical=True,
    )
    assert syms == ["aaa", "bbb"]


def test_load_universe_file_parses_text_and_json(tmp_path):
    from trading.llm_trader.strategies.cup_handle import entry_scan

    txt = tmp_path / "u.txt"
    txt.write_text("AAA, BBB  # inline comment\nCCC\n# whole-line comment\n", encoding="utf-8")
    assert entry_scan._load_universe_file(txt) == ["AAA", "BBB", "CCC"]

    arr = tmp_path / "u.json"
    arr.write_text('["DDD", "EEE"]', encoding="utf-8")
    assert entry_scan._load_universe_file(arr) == ["DDD", "EEE"]

    obj = tmp_path / "u_obj.json"
    obj.write_text('{"symbols": ["FFF"]}', encoding="utf-8")
    assert entry_scan._load_universe_file(obj) == ["FFF"]
