"""Orchestrate cup-and-handle scan → EntryStore."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import CupHandleConfig
from .patterns import detect_ticker, fetch_market_regime

log = logging.getLogger("llm_trader.cup_handle")


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    symbols_failed: int = 0
    entries_found: int = 0
    stale_entries_removed: int = 0


@dataclass
class ScopeScan:
    """A fully detected scope that has not yet been published to ``EntryStore``.

    Keeping detection separate from publication lets a point-in-time research
    scan validate *all* of its membership intervals before one transaction
    replaces any database rows.
    """

    stats: ScanStats
    symbols_requested: list[str]
    symbols_scanned: list[str]
    symbols_failed: list[str]
    entries: list[Entry]


def normalize_symbols(symbols: list[str]) -> list[str]:
    """Return a stable, uppercase, de-duplicated scan scope."""
    return list(dict.fromkeys(sym.strip().upper() for sym in symbols if sym and sym.strip()))


def scan_scope(
    cfg: CupHandleConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 50,
    strategy_id: str = "cup_handle",
) -> ScopeScan:
    """Detect one scanner scope without writing the database.

    Provider failures are checked before returning.  Callers therefore never
    receive a partially successful scope unless their explicitly configured
    failure budget permits it; in that case only successful symbols are safe to
    replace at publish time.
    """
    cfg.validate()
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    symbols = normalize_symbols(symbols)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    if not symbols:
        raise ValueError("cup_handle scan has no symbols")

    stats = ScanStats()
    log.info(
        "cup_handle scan %s → %s | %d symbols | price≥$%.0f avgvol≥%.0fK",
        cfg.start, cfg.end, len(symbols), cfg.price_min, cfg.avg_vol_min / 1000,
    )
    market_ok_dates = fetch_market_regime(cfg) if cfg.require_spy_above_sma50 else None
    scanned_symbols: list[str] = []
    detected: list[Entry] = []
    failures: list[str] = []
    for i, sym in enumerate(symbols, 1):
        stats.symbols_scanned += 1
        if i % progress_every == 0:
            log.info(
                "  [%d/%d] %s — entries=%d failures=%d",
                i, len(symbols), sym, len(detected), len(failures),
            )
        try:
            entries = detect_ticker(
                sym, cfg, strategy_id=strategy_id, market_ok_dates=market_ok_dates
            )
        except Exception:
            failures.append(sym)
            log.exception("cup_handle detect failed for %s", sym)
            continue
        scanned_symbols.append(sym)
        detected.extend(entries)

    stats.symbols_failed = len(failures)
    failure_rate = len(failures) / len(symbols)
    if failure_rate > cfg.max_scan_failure_rate:
        raise RuntimeError(
            f"cup_handle scan failed closed: {len(failures)}/{len(symbols)} symbols "
            f"({failure_rate:.2%}) failed, exceeding max_scan_failure_rate="
            f"{cfg.max_scan_failure_rate:.2%}; database was not changed"
        )
    stats.entries_found = len(detected)
    return ScopeScan(
        stats=stats,
        symbols_requested=symbols,
        symbols_scanned=scanned_symbols,
        symbols_failed=failures,
        entries=detected,
    )


def run_scan(
    cfg: CupHandleConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 50,
    strategy_id: str = "cup_handle",
) -> ScanStats:
    scope = scan_scope(
        cfg,
        symbols=symbols,
        max_symbols=max_symbols,
        progress_every=progress_every,
        strategy_id=strategy_id,
    )
    stats = scope.stats

    store = EntryStore(cfg.db_path)
    try:
        stats.stale_entries_removed = store.sync_scope(
            scope.entries,
            strategy=strategy_id,
            tickers=scope.symbols_scanned,
            start_day=cfg.start.isoformat(),
            end_day=cfg.end.isoformat(),
        )
        txt = store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=strategy_id)
        csv = store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=strategy_id)
        total = store.count(strategy=strategy_id)
    finally:
        store.close()

    atomic_write_json(
        cfg.db_path.with_suffix(".last_scan.json"),
        {
            "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "strategy": strategy_id,
            "config": cfg.to_dict(),
            "symbols_requested": len(scope.symbols_requested),
            "symbols_succeeded": len(scope.symbols_scanned),
            "symbols_failed": scope.symbols_failed,
            "entries_found": stats.entries_found,
            "stale_entries_removed": stats.stale_entries_removed,
        },
    )

    log.info(
        "done. entries(current)=%d stale_removed=%d table_total=%d wrote %s and %s",
        stats.entries_found, stats.stale_entries_removed, total, txt, csv,
    )
    return stats
