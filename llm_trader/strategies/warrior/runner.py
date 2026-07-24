"""Orchestrate Warrior A0 → A1 → A2 → B and write the entry list."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from trading.llm_trader.floats import FloatCache
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import ScanConfig
from .patterns import detect_entry
from .screen import screen_ticker
from .forward_shadow import ForwardShadowLedger

log = logging.getLogger("llm_trader.warrior")


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    gap_candidates: int = 0
    float_survivors: int = 0
    entries_found: int = 0


def run_scan(
    cfg: ScanConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 100,
    strategy_id: str = "warrior",
) -> ScanStats:
    """Warrior gap → float → ACD/ORB pipeline (strategy_id stamped on entries)."""
    cfg.apply_profile()
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]

    floats = FloatCache()
    store = EntryStore(cfg.db_path)
    stats = ScanStats()
    shadow_ledger = (
        ForwardShadowLedger(cfg.forward_shadow_ledger)
        if cfg.forward_shadow_ledger is not None else None
    )
    scan_id = datetime.now(timezone.utc).strftime("warrior-shadow-%Y%m%dT%H%M%SZ")

    log.info(
        "scan [%s] %s → %s | %d symbols | profile=%s price $%.0f–$%.0f | gap≥%.0f%% rvol≥%.1f float<%s",
        strategy_id, cfg.start, cfg.end, len(symbols), cfg.account_profile,
        cfg.price_min, cfg.price_max, cfg.gap_min_pct, cfg.rvol_min,
        f"{cfg.float_max/1e6:.0f}M" if cfg.float_max else "off",
    )

    try:
        for i, sym in enumerate(symbols, 1):
            stats.symbols_scanned += 1
            if i % progress_every == 0:
                log.info(
                    "  [%d/%d] %s — gappers=%d float_ok=%d entries=%d",
                    i, len(symbols), sym, stats.gap_candidates,
                    stats.float_survivors, stats.entries_found,
                )
            try:
                cands = screen_ticker(sym, cfg)
            except Exception:
                log.exception("screen failed for %s", sym)
                continue
            if not cands:
                continue
            stats.gap_candidates += len(cands)

            # A frozen forward-shadow cohort must capture the float lookup at
            # this scan, rather than silently inheriting a month-old cache row.
            float_snapshot = floats.snapshot(
                sym, force_refresh=shadow_ledger is not None
            )
            fshares = float_snapshot.get("value")
            float_gate_passed = (
                cfg.float_max is None
                or (fshares is not None and float(fshares) < cfg.float_max)
            )
            if shadow_ledger is not None:
                for cand in cands:
                    shadow_ledger.record_candidate(
                        scan_id=scan_id,
                        candidate=cand,
                        float_snapshot=float_snapshot,
                        float_gate_passed=float_gate_passed,
                        config=cfg.to_dict(),
                    )
            if not float_gate_passed:
                continue
            stats.float_survivors += len(cands)

            for cand in cands:
                try:
                    entry = detect_entry(cand, cfg, fshares)
                except Exception:
                    log.exception("intraday detect failed for %s %s", sym, cand.day)
                    continue
                if entry is not None:
                    entry.strategy = strategy_id
                    entry.features.update({
                        "float_provenance": float_snapshot,
                        "research_quality": {
                            "historical_promotion_eligible": False,
                            "warning": "NON_PIT_FLOAT",
                        },
                    })
                    store.upsert(entry)
                    stats.entries_found += 1
        txt = store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=strategy_id)
        csv = store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=strategy_id)
        total = store.count(strategy=strategy_id)
    finally:
        floats.flush()
        store.close()

    log.info(
        "done. gappers=%d float_ok=%d entries(new/updated)=%d table_total=%d",
        stats.gap_candidates, stats.float_survivors, stats.entries_found, total,
    )
    log.info("wrote %s and %s", txt, csv)
    return stats
