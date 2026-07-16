"""Orchestrate cup-and-handle scan → EntryStore."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import CupHandleConfig
from .patterns import detect_ticker

log = logging.getLogger("llm_trader.cup_handle")


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    entries_found: int = 0


def run_scan(
    cfg: CupHandleConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 50,
    strategy_id: str = "cup_handle",
) -> ScanStats:
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]

    store = EntryStore(cfg.db_path)
    stats = ScanStats()
    log.info(
        "cup_handle scan %s → %s | %d symbols | price≥$%.0f avgvol≥%.0fK",
        cfg.start, cfg.end, len(symbols), cfg.price_min, cfg.avg_vol_min / 1000,
    )
    try:
        for i, sym in enumerate(symbols, 1):
            stats.symbols_scanned += 1
            if i % progress_every == 0:
                log.info(
                    "  [%d/%d] %s — entries=%d",
                    i, len(symbols), sym, stats.entries_found,
                )
            try:
                entries = detect_ticker(sym, cfg, strategy_id=strategy_id)
            except Exception:
                log.exception("cup_handle detect failed for %s", sym)
                continue
            for e in entries:
                store.upsert(e)
                stats.entries_found += 1
        txt = store.dump_text(cfg.db_path.with_suffix(".txt"))
        csv = store.dump_csv(cfg.db_path.with_suffix(".csv"))
        total = store.count()
    finally:
        store.close()

    log.info(
        "done. entries(new/updated)=%d table_total=%d wrote %s and %s",
        stats.entries_found, total, txt, csv,
    )
    return stats
