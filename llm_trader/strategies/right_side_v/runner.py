"""Orchestrate right_side_v scan → EntryStore."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import RightSideVConfig
from .patterns import MarketRegimeDataError, detect_ticker, fetch_market_regime_features

log = logging.getLogger("llm_trader.right_side_v")


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    symbols_failed: int = 0
    entries_found: int = 0
    stale_entries_removed: int = 0


def normalize_symbols(symbols: list[str]) -> list[str]:
    return list(dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip()))


def run_scan(
    cfg: RightSideVConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 50,
    strategy_id: str = "right_side_v",
) -> ScanStats:
    cfg.validate()
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    symbols = normalize_symbols(symbols)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    if not symbols:
        raise ValueError("right_side_v scan has no symbols")

    stats = ScanStats()
    log.info("right_side_v scan %s → %s | %d symbols", cfg.start, cfg.end, len(symbols))

    market_regime_features = None
    market_ok_dates = None
    if cfg.require_spy_above_sma50:
        market_regime_features = fetch_market_regime_features(cfg)
        market_ok_dates = {
            d for d, r in market_regime_features.items() if r.get("above_sma50")
        }

    scanned: list[str] = []
    detected: list[Entry] = []
    failures: list[str] = []
    for i, sym in enumerate(symbols, 1):
        stats.symbols_scanned += 1
        if i % progress_every == 0:
            log.info("  [%d/%d] %s entries=%d", i, len(symbols), sym, len(detected))
        try:
            entries = detect_ticker(
                sym,
                cfg,
                strategy_id=strategy_id,
                market_ok_dates=market_ok_dates,
                market_regime_features=market_regime_features,
            )
        except MarketRegimeDataError as exc:
            raise RuntimeError(f"right_side_v failed closed: {exc}") from exc
        except Exception:
            failures.append(sym)
            log.exception("detect failed %s", sym)
            continue
        scanned.append(sym)
        detected.extend(entries)

    stats.symbols_failed = len(failures)
    rate = len(failures) / len(symbols)
    if rate > cfg.max_scan_failure_rate:
        raise RuntimeError(
            f"right_side_v scan failed: {len(failures)}/{len(symbols)} ({rate:.2%})"
        )
    stats.entries_found = len(detected)

    store = EntryStore(cfg.db_path)
    try:
        stats.stale_entries_removed = store.sync_scope(
            detected,
            strategy=strategy_id,
            tickers=scanned,
            start_day=cfg.start.isoformat(),
            end_day=cfg.end.isoformat(),
        )
        store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=strategy_id)
        store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=strategy_id)
        total = store.count(strategy=strategy_id)
    finally:
        store.close()

    atomic_write_json(
        cfg.db_path.with_suffix(".last_scan.json"),
        {
            "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "strategy": strategy_id,
            "config": cfg.to_dict(),
            "entries_found": stats.entries_found,
            "symbols_failed": failures,
            "stale_entries_removed": stats.stale_entries_removed,
        },
    )
    log.info("done entries=%d table_total=%d", stats.entries_found, total)
    return stats
