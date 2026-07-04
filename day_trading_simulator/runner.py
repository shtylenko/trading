"""Orchestrate A0 → A1 → A2 → B and write the entry list.

Pipeline (see SPEC §3):
  A0  symbol universe          (universe.fetch_symbols)
  A1  daily gap screen         (screen.screen_ticker)        — per symbol
  A2  float gate               (floats.FloatCache)           — per gap ticker
  B   intraday ACD/ORB detect  (patterns.detect_entry)       — per gap day
  →   idempotent upsert to SQLite + text/CSV dump            (store.EntryStore)

Re-running over the same window is idempotent: setups upsert on
``(ticker, date, pattern)`` and are never duplicated.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from .config import ScanConfig
from .floats import FloatCache
from .patterns import detect_entry
from .screen import screen_ticker
from .store import EntryStore
from .universe import fetch_symbols

log = logging.getLogger("day_trading_simulator")


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
) -> ScanStats:
    cfg.apply_profile()
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]

    floats = FloatCache()
    store = EntryStore(cfg.db_path)
    stats = ScanStats()

    log.info(
        "scan %s → %s | %d symbols | profile=%s price $%.0f–$%.0f | gap≥%.0f%% rvol≥%.1f float<%s",
        cfg.start, cfg.end, len(symbols), cfg.account_profile,
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
                # one bad ticker must not kill the sweep; full context for debugging
                log.exception("screen failed for %s", sym)
                continue
            if not cands:
                continue
            stats.gap_candidates += len(cands)

            # Float gate once per ticker (cached); skip whole ticker if it fails.
            if not floats.passes(sym, cfg.float_max):
                continue
            fshares = floats.get(sym)
            stats.float_survivors += len(cands)

            for cand in cands:
                try:
                    entry = detect_entry(cand, cfg, fshares)
                except Exception:
                    log.exception("intraday detect failed for %s %s", sym, cand.day)
                    continue
                if entry is not None:
                    store.upsert(entry)
                    stats.entries_found += 1
    finally:
        floats.flush()

    txt = store.dump_text(cfg.db_path.with_suffix(".txt"))
    csv = store.dump_csv(cfg.db_path.with_suffix(".csv"))
    total = store.count()
    store.close()

    log.info(
        "done. gappers=%d float_ok=%d entries(new/updated)=%d table_total=%d",
        stats.gap_candidates, stats.float_survivors, stats.entries_found, total,
    )
    log.info("wrote %s and %s", txt, csv)
    return stats


def main(argv: list[str] | None = None) -> int:
    from .cli import build_parser, config_from_args

    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    cfg = config_from_args(args)
    run_scan(
        cfg,
        max_symbols=args.max_symbols,
        symbols=[s.upper() for s in args.symbols] if args.symbols else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
