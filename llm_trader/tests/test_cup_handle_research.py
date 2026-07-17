"""Point-in-time universe and transactional research-scan contracts."""

from __future__ import annotations

import json
from datetime import date

import pytest

from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.strategies.cup_handle.config import CupHandleConfig
from trading.llm_trader.strategies.cup_handle.research_universe import (
    SOURCE_QUALITY_PUBLIC,
    UniverseManifestError,
    build_lagged_daily_csv_manifest,
    build_lagged_monthly_snapshot_manifest,
    load_research_universe,
)
from trading.llm_trader.strategies.cup_handle.runner import ScanStats, ScopeScan


def _manifest(path, *, basis="point_in_time", intervals=None):
    intervals = intervals or [
        {
            "start": "2025-01-01", "end": "2025-01-31", "as_of": "2024-12-31",
            "source": "fixture-v1", "source_sha256": "sha256:one", "symbols": ["AAA"],
        },
        {
            "start": "2025-02-01", "end": "2025-02-28", "as_of": "2025-01-31",
            "source": "fixture-v1", "source_sha256": "sha256:two", "symbols": ["BBB"],
        },
    ]
    path.write_text(json.dumps({
        "schema_version": 1,
        "name": "fixture-pit",
        "membership_basis": basis,
        "intervals": intervals,
    }), encoding="utf-8")
    return path


def _scope(ticker: str, day: date) -> ScopeScan:
    entry = Entry(
        ticker=ticker, day=day, time_et="16:00", pattern="cup_handle",
        entry_px=11.0, bar_close=10.9, reason="fresh causal plan", strategy="cup_handle",
        features={"signal_kind": "prebreak_arm"},
    )
    return ScopeScan(
        stats=ScanStats(symbols_scanned=1, entries_found=1),
        symbols_requested=[ticker], symbols_scanned=[ticker], symbols_failed=[], entries=[entry],
    )


def test_manifest_requires_complete_pit_coverage_and_rejects_current_snapshot(tmp_path):
    current = load_research_universe(_manifest(tmp_path / "current.json", basis="current_snapshot"))
    with pytest.raises(UniverseManifestError, match="current snapshot"):
        current.slices_for(date(2025, 1, 1), date(2025, 1, 2))

    gapped = load_research_universe(_manifest(
        tmp_path / "gapped.json",
        intervals=[
            {
                "start": "2025-01-01", "end": "2025-01-10", "as_of": "2024-12-31",
                "source": "fixture", "symbols": ["AAA"],
            },
            {
                "start": "2025-01-12", "end": "2025-01-31", "as_of": "2025-01-11",
                "source": "fixture", "symbols": ["BBB"],
            },
        ],
    ))
    with pytest.raises(UniverseManifestError, match="2025-01-11"):
        gapped.slices_for(date(2025, 1, 1), date(2025, 1, 31))


def test_lagged_monthly_manifest_uses_prior_month_and_hashes_archived_bytes(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    december = b'[{"Symbol":"AAA"},{"Symbol":"BBB"}]'
    january = b'[{"Symbol":"BBB"},{"Symbol":"CCC"}]'
    (source_dir / "2024-12.json").write_bytes(december)
    (source_dir / "2025-01.json").write_bytes(january)

    manifest = build_lagged_monthly_snapshot_manifest(
        source_dir, start=date(2025, 1, 1), end=date(2025, 2, 28),
        name="public-pit", url_template="https://example.test/{year}/{month:02d}.json",
    )

    assert manifest["source_quality"] == SOURCE_QUALITY_PUBLIC
    assert [(row["start"], row["end"], row["as_of"], row["symbols"]) for row in manifest["intervals"]] == [
        ("2025-01-01", "2025-01-31", "2024-12-01", ["AAA", "BBB"]),
        ("2025-02-01", "2025-02-28", "2025-01-01", ["BBB", "CCC"]),
    ]
    assert manifest["intervals"][0]["source_sha256"].startswith("sha256:")


def test_lagged_daily_csv_manifest_never_uses_same_day_membership(tmp_path):
    source = tmp_path / "members.csv"
    source.write_text(
        "date,tickers\n"
        "2024-12-31,AAA\n"
        "2025-01-02,\"AAA,BBB\"\n"
        "2025-01-06,BBB\n",
        encoding="utf-8",
    )

    manifest = build_lagged_daily_csv_manifest(
        source, start=date(2025, 1, 1), end=date(2025, 1, 7), name="daily-pit",
        source_url="https://example.test/members.csv",
    )

    assert [(row["start"], row["end"], row["as_of"], row["symbols"]) for row in manifest["intervals"]] == [
        ("2025-01-01", "2025-01-02", "2024-12-31", ["AAA"]),
        ("2025-01-03", "2025-01-06", "2025-01-02", ["AAA", "BBB"]),
        ("2025-01-07", "2025-01-07", "2025-01-06", ["BBB"]),
    ]


def test_research_scan_preserves_detector_state_across_intervals_and_stamps_entries(tmp_path, monkeypatch):
    from trading.llm_trader.strategies.cup_handle import research_scan

    db = tmp_path / "entries.db"
    with EntryStore(db) as store:
        for ticker, day in (("AAA", date(2025, 1, 2)), ("BBB", date(2025, 2, 2))):
            store.upsert(Entry(
                ticker=ticker, day=day, time_et="16:00", pattern="cup_handle",
                entry_px=9.0, bar_close=8.9, reason="stale", strategy="cup_handle",
            ))
    manifest_path = _manifest(tmp_path / "pit.json")
    universe = load_research_universe(manifest_path)
    cfg = CupHandleConfig(start=date(2025, 1, 1), end=date(2025, 2, 28), db_path=db)

    calls = []

    def fake_scan(cfg, *, symbols, eligible_plan_dates_by_symbol, **_kwargs):
        calls.append((cfg.start, cfg.end, tuple(symbols), eligible_plan_dates_by_symbol))
        entries = [
            _scope("AAA", date(2025, 1, 3)).entries[0],
            _scope("BBB", date(2025, 2, 3)).entries[0],
        ]
        return ScopeScan(
            stats=ScanStats(symbols_scanned=2, entries_found=2),
            symbols_requested=list(symbols), symbols_scanned=list(symbols),
            symbols_failed=[], entries=entries,
        )

    monkeypatch.setattr(
        research_scan,
        "fetch_market_regime_features",
        lambda _cfg: {date(2025, 1, 3): {"as_of": "2025-01-03"}},
    )
    monkeypatch.setattr(research_scan, "scan_scope", fake_scan)
    stats = research_scan.run_research_scan(cfg, universe=universe)

    assert stats.intervals_scanned == 2
    assert stats.stale_entries_removed == 2
    assert len(calls) == 1
    scanned_start, scanned_end, symbols, eligible = calls[0]
    assert (scanned_start, scanned_end, symbols) == (
        date(2025, 1, 1), date(2025, 2, 28), ("AAA", "BBB"),
    )
    assert date(2025, 1, 3) in eligible["AAA"]
    assert date(2025, 2, 3) in eligible["BBB"]
    with EntryStore(db) as store:
        rows = store.all_rows(strategy="cup_handle")
    assert [(r["ticker"], r["date"]) for r in rows] == [
        ("AAA", "2025-01-03"), ("BBB", "2025-02-03"),
    ]
    for row in rows:
        features = json.loads(row["features_json"])
        assert features["research_universe"]["manifest_sha256"] == universe.manifest_sha256
        assert features["research_universe"]["membership_basis"] == "point_in_time"
        assert features["research_universe"]["source_quality"] == "unqualified"
    artifact = json.loads(db.with_suffix(".research_scan.json").read_text())
    assert artifact["research_universe"]["manifest_sha256"] == universe.manifest_sha256
    assert len(artifact["interval_results"]) == 2


def test_research_scan_provider_failure_in_later_interval_leaves_database_unchanged(tmp_path, monkeypatch):
    from trading.llm_trader.strategies.cup_handle import research_scan

    db = tmp_path / "entries.db"
    original = Entry(
        ticker="AAA", day=date(2025, 1, 2), time_et="16:00", pattern="cup_handle",
        entry_px=9.0, bar_close=8.9, reason="must survive", strategy="cup_handle",
    )
    with EntryStore(db) as store:
        store.upsert(original)
    universe = load_research_universe(_manifest(tmp_path / "pit.json"))
    cfg = CupHandleConfig(start=date(2025, 1, 1), end=date(2025, 2, 28), db_path=db)
    calls = []

    def fake_scan(cfg, *, symbols, **_kwargs):
        calls.append((cfg.start, cfg.end, tuple(symbols)))
        raise RuntimeError("provider coverage failed")

    monkeypatch.setattr(
        research_scan,
        "fetch_market_regime_features",
        lambda _cfg: {date(2025, 1, 3): {"as_of": "2025-01-03"}},
    )
    monkeypatch.setattr(research_scan, "scan_scope", fake_scan)
    with pytest.raises(RuntimeError, match="provider coverage failed"):
        research_scan.run_research_scan(cfg, universe=universe)

    assert calls == [(date(2025, 1, 1), date(2025, 2, 28), ("AAA", "BBB"))]
    with EntryStore(db) as store:
        rows = store.all_rows(strategy="cup_handle")
    assert [(r["ticker"], r["date"], r["reason"]) for r in rows] == [
        ("AAA", "2025-01-02", "must survive"),
    ]
    assert not db.with_suffix(".research_scan.json").exists()
