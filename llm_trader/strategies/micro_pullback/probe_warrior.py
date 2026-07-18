"""Warrior-universe probe for micro_pullback (Ross small-cap gappers).

**Not multi-year sealed research.** Float is yfinance *current snapshot* (same
caveat as warrior SPEC): only valid for a recent window (~2025–2026H1).

Pipeline:
1. Optional symbol universe: float < 20M from cache + exchange list
2. Daily warrior-style gap/price/RVOL screen
3. Same micro_pullback 5m detector (impulse → micro-pb → green break)
4. Path sim + portfolio packaging (NML OFF)
5. Write batch/micro_pullback/warrior_probe/

Does not overwrite liquid multi-year entries.db.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from trading.llm_trader.admission.portfolio import PortfolioLimits
from trading.llm_trader.admission.short_hold_paper import (
    apply_portfolio_to_pairs,
    build_short_hold_paper_book,
    write_short_hold_paper_book,
)
from trading.llm_trader.floats import FloatCache
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import MicroPullbackConfig
from .patterns import DayCandidate, SimTrade, detect_entry, screen_ticker, simulate_trade
from .runner import ScanStats, _agg, run_cost_stress

log = logging.getLogger("llm_trader.micro_pullback.probe_warrior")

PROBE_CONTRACT = "micro_pullback_warrior_probe_v0.1.0"
STRATEGY_ID = "micro_pullback"


def _low_float_symbols(
    exchanges: tuple[str, ...],
    float_max: float,
    *,
    max_symbols: Optional[int] = None,
    prefer_cached_only: bool = False,
) -> list[str]:
    """Return tickers that pass float_max (current snapshot)."""
    fc = FloatCache()
    try:
        if prefer_cached_only:
            # Only use names already in cache to avoid massive yfinance pulls
            syms = []
            for t, entry in fc._data.items():
                val = entry.get("value") if isinstance(entry, dict) else None
                if val is not None and val < float_max:
                    syms.append(t.upper())
            syms = sorted(set(syms))
        else:
            universe = fetch_symbols(exchanges)
            syms = []
            for i, t in enumerate(universe, 1):
                if i % 200 == 0:
                    log.info("  float gate [%d/%d] kept=%d", i, len(universe), len(syms))
                if fc.passes(t, float_max):
                    syms.append(t.upper())
            fc.flush()
        if max_symbols is not None:
            syms = syms[:max_symbols]
        return syms
    finally:
        try:
            fc.flush()
        except Exception:
            pass


def run_warrior_scan(
    cfg: MicroPullbackConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 25,
    prefer_cached_float: bool = True,
) -> ScanStats:
    """Scan warrior-profile universe into cfg.db_path (entries_warrior.db)."""
    cfg = cfg.apply_warrior_profile() if cfg.universe_profile != "warrior" else cfg
    if cfg.float_max is None:
        cfg.float_max = 20_000_000.0

    if symbols is None:
        symbols = _low_float_symbols(
            cfg.exchanges,
            float(cfg.float_max),
            max_symbols=max_symbols,
            prefer_cached_only=prefer_cached_float,
        )
    else:
        symbols = list(dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip()))
        if max_symbols is not None:
            symbols = symbols[:max_symbols]
        # Still enforce float when gate active
        fc = FloatCache()
        try:
            symbols = [s for s in symbols if fc.passes(s, cfg.float_max)]
        finally:
            fc.flush()

    stats = ScanStats()
    store = EntryStore(cfg.db_path)
    log.info(
        "warrior micro probe scan %s→%s | %d symbols | gap≥%.0f rvol≥%.1f float<%.0fM",
        cfg.start,
        cfg.end,
        len(symbols),
        cfg.gap_min_pct,
        cfg.rvol_min,
        (cfg.float_max or 0) / 1e6,
    )
    try:
        for i, sym in enumerate(symbols, 1):
            stats.symbols_scanned += 1
            if i % progress_every == 0:
                log.info(
                    "  [%d/%d] %s cands=%d entries=%d",
                    i,
                    len(symbols),
                    sym,
                    stats.day_candidates,
                    stats.entries_found,
                )
            try:
                cands = screen_ticker(sym, cfg)
            except Exception:
                stats.symbols_failed += 1
                log.exception("screen %s", sym)
                continue
            stats.day_candidates += len(cands)
            for cand in cands:
                try:
                    entry = detect_entry(cand, cfg)
                except Exception:
                    log.exception("detect %s %s", sym, cand.day)
                    continue
                if entry is not None:
                    entry.strategy = STRATEGY_ID
                    feats = dict(entry.features or {})
                    feats["universe_profile"] = "warrior"
                    feats["construction"] = "v0.1.0_micro_pullback_warrior_probe"
                    entry.features = feats
                    store.upsert(entry)
                    stats.entries_found += 1
        store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=STRATEGY_ID)
        store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=STRATEGY_ID)
        total = store.count(strategy=STRATEGY_ID)
    finally:
        store.close()
    log.info("done entries=%d table=%d failed=%d", stats.entries_found, total, stats.symbols_failed)
    return stats


def run_warrior_probe(
    cfg: MicroPullbackConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    prefer_cached_float: bool = True,
    skip_scan: bool = False,
) -> dict:
    """Scan (unless skip) + paper-packaged metrics for warrior window."""
    cfg = cfg.apply_warrior_profile()
    cfg.nml_gate = False
    if not skip_scan:
        run_warrior_scan(
            cfg,
            symbols=symbols,
            max_symbols=max_symbols,
            prefer_cached_float=prefer_cached_float,
        )

    limits = PortfolioLimits(
        max_concurrent=cfg.paper_max_concurrent,
        max_per_day=cfg.paper_max_per_day,
    )
    book = build_short_hold_paper_book(
        strategy_id=STRATEGY_ID,
        contract=PROBE_CONTRACT,
        cfg=cfg,
        simulate=simulate_trade,
        run_cost_stress=run_cost_stress,
        limits=limits,
        promotion_notes=(
            "Warrior-universe probe only (current-snapshot float). "
            "Not multi-year sealed. Do not promote to liquid multi-year bar."
        ),
    )
    book["probe"] = {
        "contract": PROBE_CONTRACT,
        "float_source": "yfinance_current_snapshot",
        "window_note": "Valid only while current float ≈ historical (warrior SPEC: 2025–2026H1)",
        "universe_profile": "warrior",
        "prefer_cached_float": prefer_cached_float,
    }
    return book


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="micro_pullback warrior-universe probe")
    p.add_argument("--start", default="2025-01-01")
    p.add_argument("--end", default="2026-06-30")
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--max-symbols", type=int, default=None)
    p.add_argument(
        "--full-float-scan",
        action="store_true",
        help="Query yfinance float for full exchange universe (slow). Default: cached floats only.",
    )
    p.add_argument("--skip-scan", action="store_true")
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    cfg = MicroPullbackConfig(
        start=datetime.fromisoformat(args.start).date(),
        end=datetime.fromisoformat(args.end).date(),
        nml_gate=False,
        paper_portfolio=True,
    ).apply_warrior_profile()

    result = run_warrior_probe(
        cfg,
        symbols=args.symbols,
        max_symbols=args.max_symbols,
        prefer_cached_float=not args.full_float_scan,
        skip_scan=args.skip_scan,
    )

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[2]
        / "batch"
        / "micro_pullback"
        / "warrior_probe"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    jpath, mpath = write_short_hold_paper_book(
        result,
        out_dir,
        title="Micro-pullback warrior-universe probe",
    )
    # Prepend probe caveats to markdown
    extra = [
        "",
        "## Probe caveats (read first)",
        "",
        f"- Contract: `{PROBE_CONTRACT}`",
        "- **Float is current snapshot, not PIT** — same limit as warrior SPEC",
        f"- Window: {cfg.start} → {cfg.end}",
        f"- Screen: price ${cfg.price_min}–{cfg.price_max}, gap≥{cfg.gap_min_pct}%, "
        f"rvol≥{cfg.rvol_min}, float<{cfg.float_max/1e6:.0f}M",
        "- Detector: same micro_pullback 5m rules as liquid book",
        "- This does **not** replace liquid multi-year PASS; separate universe",
        "",
    ]
    text = mpath.read_text(encoding="utf-8")
    # insert after title block
    parts = text.split("\n", 3)
    if len(parts) >= 4:
        mpath.write_text(parts[0] + "\n" + parts[1] + "\n" + parts[2] + "\n" + "\n".join(extra) + parts[3], encoding="utf-8")
    else:
        mpath.write_text(text + "\n".join(extra), encoding="utf-8")

    atomic_write_json(out_dir / "PROBE.json", result, indent=2)
    print(json.dumps(result["paper"]["pooled"], indent=2))
    print("gates", result["paper"]["gates"])
    print("raw n", result["raw"]["pooled"]["n"], "paper n", result["paper"]["pooled"]["n"])
    print("wrote", jpath, mpath, out_dir / "PROBE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
