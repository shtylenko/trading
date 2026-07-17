"""Fail-closed historical cup-handle scans over a point-in-time universe.

Use this instead of the convenience scanner when generating a research corpus
or a promotion-eligible holdout.  It refuses current-membership snapshots,
requires complete interval coverage, detects every interval before touching the
database, then publishes all replacements in one SQLite transaction.

Example (from the monorepo root)::

    python3 -m trading.llm_trader.strategies.cup_handle.research_scan \
      --universe-manifest path/to/sp500_pit.json \
      --start 2025-01-01 --end 2026-06-30 \
      --db trading/llm_trader/data/cup_handle/entries.db
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.store import EntryStore

from .config import CupHandleConfig
from .research_universe import ResearchUniverse, UniverseInterval, UniverseManifestError, load_research_universe
from .runner import ScanStats, ScopeScan, scan_scope

log = logging.getLogger("llm_trader.cup_handle.research_scan")


@dataclass
class ResearchScanStats:
    intervals_scanned: int = 0
    symbols_requested: int = 0
    symbols_succeeded: int = 0
    symbols_failed: int = 0
    entries_found: int = 0
    stale_entries_removed: int = 0


def _entry_universe_provenance(
    universe: ResearchUniverse,
    interval: UniverseInterval,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "membership_basis": universe.membership_basis,
        "manifest_name": universe.name,
        "manifest_sha256": universe.manifest_sha256,
        "interval": interval.provenance(),
    }


def _stamp_scope_entries(
    scope: ScopeScan,
    universe: ResearchUniverse,
    interval: UniverseInterval,
) -> None:
    """Attach immutable membership provenance before an Entry reaches storage."""
    provenance = _entry_universe_provenance(universe, interval)
    for entry in scope.entries:
        # Entry.features belongs to the detector result and is not shared across
        # entries.  Copy defensively anyway, because it is evidence, not a mutable
        # runtime scratchpad.
        entry.features = dict(entry.features or {})
        entry.features["research_universe"] = provenance


def run_research_scan(
    cfg: CupHandleConfig,
    *,
    universe: ResearchUniverse,
    strategy_id: str = "cup_handle",
    progress_every: int = 50,
) -> ResearchScanStats:
    """Scan ``cfg.start..cfg.end`` with complete PIT membership provenance.

    Detection and provider checks for every interval happen before ``EntryStore``
    is opened.  If one interval cannot meet the configured failure policy, no
    new row is published and no stale row is deleted.
    """
    cfg.validate()
    intervals = universe.slices_for(cfg.start, cfg.end)
    scope_results: list[tuple[UniverseInterval, ScopeScan]] = []
    stats = ResearchScanStats(intervals_scanned=len(intervals))
    for interval in intervals:
        interval_cfg = replace(cfg, start=interval.start, end=interval.end)
        log.info(
            "PIT interval %s → %s (as_of=%s; %d symbols; source=%s)",
            interval.start, interval.end, interval.as_of, len(interval.symbols), interval.source,
        )
        scope = scan_scope(
            interval_cfg,
            symbols=list(interval.symbols),
            progress_every=progress_every,
            strategy_id=strategy_id,
        )
        _stamp_scope_entries(scope, universe, interval)
        scope_results.append((interval, scope))
        stats.symbols_requested += len(scope.symbols_requested)
        stats.symbols_succeeded += len(scope.symbols_scanned)
        stats.symbols_failed += len(scope.symbols_failed)
        stats.entries_found += len(scope.entries)

    # All expensive/fallible work above has succeeded.  One transaction now
    # replaces every permitted scope, preserving prior output on any DB error.
    store = EntryStore(cfg.db_path)
    try:
        stats.stale_entries_removed = store.sync_scopes(
            [entry for _interval, scope in scope_results for entry in scope.entries],
            strategy=strategy_id,
            scopes=[
                (scope.symbols_scanned, interval.start.isoformat(), interval.end.isoformat())
                for interval, scope in scope_results
            ],
        )
        txt = store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=strategy_id)
        csv = store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=strategy_id)
        total = store.count(strategy=strategy_id)
    finally:
        store.close()

    manifest = {
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strategy": strategy_id,
        "config": cfg.to_dict(),
        "research_universe": universe.provenance(cfg.start, cfg.end),
        "interval_results": [
            {
                **interval.provenance(),
                "symbols_requested": len(scope.symbols_requested),
                "symbols_succeeded": len(scope.symbols_scanned),
                "symbols_failed": scope.symbols_failed,
                "entries_found": len(scope.entries),
            }
            for interval, scope in scope_results
        ],
        "entries_found": stats.entries_found,
        "stale_entries_removed": stats.stale_entries_removed,
        "database_entries_total": total,
    }
    artifact = cfg.db_path.with_suffix(".research_scan.json")
    atomic_write_json(artifact, manifest, indent=2, sort_keys=True)
    log.info(
        "PIT research scan complete: intervals=%d entries=%d stale_removed=%d "
        "database_total=%d wrote %s, %s, and %s",
        stats.intervals_scanned, stats.entries_found, stats.stale_entries_removed,
        total, txt, csv, artifact,
    )
    return stats


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cup_handle.research_scan",
        description=(
            "Historical cup-handle scan over a versioned point-in-time universe. "
            "Fails before writing if membership coverage or data integrity is incomplete."
        ),
    )
    p.add_argument("--universe-manifest", required=True, help="PIT universe manifest JSON (schema v1).")
    p.add_argument("--start", required=True, help="inclusive scan start YYYY-MM-DD")
    p.add_argument("--end", required=True, help="inclusive scan end YYYY-MM-DD")
    p.add_argument("--config", help="CupHandleConfig YAML; start/end are overridden by CLI")
    p.add_argument("--db", help="output EntryStore SQLite path")
    p.add_argument("--progress-every", type=int, default=50)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    try:
        cfg = CupHandleConfig.from_yaml(args.config) if args.config else CupHandleConfig()
        cfg.start = date.fromisoformat(args.start)
        cfg.end = date.fromisoformat(args.end)
        if args.db:
            cfg.db_path = Path(args.db)
        universe = load_research_universe(args.universe_manifest)
        stats = run_research_scan(
            cfg, universe=universe, progress_every=args.progress_every,
        )
    except (UniverseManifestError, ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"PIT scan complete: {stats.intervals_scanned} interval(s), "
        f"{stats.entries_found} entries, {stats.symbols_failed} provider failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
