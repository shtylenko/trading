"""Scan + probe runner for inplay_continuation (Opp C)."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from trading.llm_trader.admission.portfolio import PortfolioLimits, TimedTrade, apply_portfolio_limits
from trading.llm_trader.costs.webull import stress_grid_webull_small
from trading.llm_trader.floats import FloatCache
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import InplayContinuationConfig
from .patterns import SimTrade, detect_entry, screen_ticker, simulate_trade

log = logging.getLogger("llm_trader.inplay_continuation")
STRATEGY_ID = "inplay_continuation"


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    day_candidates: int = 0
    entries_found: int = 0
    symbols_failed: int = 0


def _agg(ts: list[SimTrade]) -> dict:
    if not ts:
        return {"n": 0, "win_pct": 0.0, "eff_r": 0.0, "pnl": 0.0, "exits": {}}
    rs = [t.r_multiple for t in ts]
    return {
        "n": len(ts),
        "win_pct": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1),
        "eff_r": round(sum(rs) / len(rs), 4),
        "pnl": round(sum(t.pnl_usd for t in ts), 2),
        "exits": {
            k: sum(1 for t in ts if t.exit_reason == k)
            for k in ("STOP", "TARGET1", "TARGET2", "EOD")
        },
    }


def _symbols(cfg: InplayContinuationConfig, symbols: list[str] | None, max_symbols: int | None,
             prefer_cached_float: bool) -> list[str]:
    if symbols is not None:
        syms = list(dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip()))
    elif prefer_cached_float and cfg.float_max is not None:
        fc = FloatCache()
        syms = []
        for t, entry in fc._data.items():
            val = entry.get("value") if isinstance(entry, dict) else None
            if val is not None and val < cfg.float_max:
                syms.append(t.upper())
        syms = sorted(set(syms))
    else:
        syms = fetch_symbols(cfg.exchanges)
        if cfg.float_max is not None:
            fc = FloatCache()
            try:
                syms = [s for s in syms if fc.passes(s, cfg.float_max)]
            finally:
                fc.flush()
    if max_symbols is not None:
        syms = syms[:max_symbols]
    return syms


def run_scan(
    cfg: InplayContinuationConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 25,
    prefer_cached_float: bool = True,
) -> ScanStats:
    symbols = _symbols(cfg, symbols, max_symbols, prefer_cached_float)
    stats = ScanStats()
    store = EntryStore(cfg.db_path)
    log.info(
        "inplay_continuation scan %s→%s | %d syms | gap≥%.0f rvol≥%.1f slip=%.0fbps",
        cfg.start, cfg.end, len(symbols), cfg.gap_min_pct, cfg.rvol_min, cfg.slippage_bps_one_way,
    )
    try:
        for i, sym in enumerate(symbols, 1):
            stats.symbols_scanned += 1
            if i % progress_every == 0:
                log.info(
                    "  [%d/%d] %s cands=%d entries=%d",
                    i, len(symbols), sym, stats.day_candidates, stats.entries_found,
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
                    store.upsert(entry)
                    stats.entries_found += 1
        store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=STRATEGY_ID)
        total = store.count(strategy=STRATEGY_ID)
    finally:
        store.close()
    log.info("done entries=%d table=%d failed=%d", stats.entries_found, total, stats.symbols_failed)
    return stats


def _load_rows(cfg: InplayContinuationConfig) -> list[dict]:
    store = EntryStore(cfg.db_path)
    try:
        return [dict(r) for r in store.all_rows(strategy=STRATEGY_ID)]
    finally:
        store.close()


def _sim_rows(rows: list[dict], cfg: InplayContinuationConfig) -> list[tuple[Entry, SimTrade]]:
    out = []
    for r in rows:
        feats = r.get("features_json")
        if isinstance(feats, str):
            try:
                feats = json.loads(feats)
            except json.JSONDecodeError:
                feats = {}
        entry = Entry(
            ticker=r["ticker"],
            day=datetime.fromisoformat(str(r["date"])).date(),
            time_et=r.get("time_et") or "10:00",
            pattern=r.get("pattern") or STRATEGY_ID,
            entry_px=float(r.get("entry_px") or 0),
            bar_close=float(r.get("bar_close") or r.get("entry_px") or 0),
            reason=r.get("reason") or "",
            strategy=STRATEGY_ID,
            gap_pct=r.get("gap_pct"),
            rvol=r.get("rvol"),
            features=feats or {},
        )
        if entry.day < cfg.start or entry.day > cfg.end:
            continue
        tr = simulate_trade(entry, cfg)
        if tr is not None:
            out.append((entry, tr))
    return out


def _metrics(trades: list[SimTrade]) -> dict:
    by_y: dict[str, list[SimTrade]] = defaultdict(list)
    for t in trades:
        by_y[str(t.day.year)].append(t)
    years = {y: _agg(ts) for y, ts in sorted(by_y.items())}
    pooled = _agg(trades)
    pos = sum(1 for a in years.values() if a.get("eff_r", 0) > 0)
    return {
        "pooled": pooled,
        "years": years,
        "gates": {
            "pooled_eff_r_gt_0": pooled["eff_r"] > 0,
            "years_positive": pos,
            "years_total": len(years),
            # PREREG: pooled > 0 and at least one calendar year > 0 in window
            "pass": pooled["eff_r"] > 0 and pos >= 1,
        },
    }


def run_cost_stress(cfg: InplayContinuationConfig, pairs: list[tuple[Entry, SimTrade]]) -> dict:
    """Re-sim under WeBull slip grid (entries fixed)."""
    # Rebuild minimal rows from entries
    out = {}
    for label, model in stress_grid_webull_small():
        c = deepcopy(cfg)
        c.apply_cost_model(model)
        trades = []
        for entry, _ in pairs:
            tr = simulate_trade(entry, c)
            if tr:
                trades.append(tr)
        m = _metrics(trades)
        a = m["pooled"]
        a["slip_bps"] = model.slippage_bps_one_way
        a["tier"] = model.tier.value
        a["years_pos"] = m["gates"]["years_positive"]
        a["years_total"] = m["gates"]["years_total"]
        a["pass"] = m["gates"]["pass"]
        # PREREG gate 3 at slip 30
        if abs(model.slippage_bps_one_way - 30.0) < 1e-6:
            a["prereg_slip30_not_catastrophe"] = a["eff_r"] > -0.05
        out[label] = a
    return out


def run_probe(
    cfg: InplayContinuationConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    prefer_cached_float: bool = True,
    skip_scan: bool = False,
) -> dict:
    if not skip_scan:
        run_scan(
            cfg,
            symbols=symbols,
            max_symbols=max_symbols,
            prefer_cached_float=prefer_cached_float,
        )
    rows = _load_rows(cfg)
    pairs = _sim_rows(rows, cfg)
    trades = [t for _, t in pairs]
    raw = _metrics(trades)

    # portfolio
    timed = [
        TimedTrade(
            ticker=t.ticker,
            day=t.day,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            r_multiple=t.r_multiple,
            rvol=float(e.rvol or 0),
            gap_pct=float(e.gap_pct or 0),
            meta={"i": i},
        )
        for i, (e, t) in enumerate(pairs)
    ]
    kept_t, rej_t = apply_portfolio_limits(
        timed, PortfolioLimits(cfg.paper_max_concurrent, cfg.paper_max_per_day)
    )
    kept_idx = {t.meta["i"] for t in kept_t if t.meta}
    paper_trades = [pairs[i][1] for i in sorted(kept_idx)]
    paper = _metrics(paper_trades)

    stress = run_cost_stress(cfg, pairs)
    slip30 = stress.get("slip_30", {})
    result = {
        "strategy": STRATEGY_ID,
        "experiment": "opp_c_inplay_v010",
        "prereg": "batch/inplay_continuation/PREREG_v010.md",
        "config": cfg.to_dict(),
        "scan_entries": len(rows),
        "raw": raw,
        "paper": {
            **paper,
            "n_skipped_portfolio": len(rej_t),
        },
        "cost_stress": stress,
        "gates": {
            "pooled_eff_r_gt_0": raw["gates"]["pooled_eff_r_gt_0"],
            "years_ok": raw["gates"]["years_positive"] >= 1,
            "slip30_not_catastrophe": bool(slip30.get("prereg_slip30_not_catastrophe", False)),
            "pass": bool(
                raw["gates"]["pooled_eff_r_gt_0"]
                and raw["gates"]["years_positive"] >= 1
                and slip30.get("prereg_slip30_not_catastrophe", False)
            ),
        },
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return result


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="inplay_continuation Opp C probe")
    p.add_argument("--start", default="2025-07-01")
    p.add_argument("--end", default="2026-06-30")
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--max-symbols", type=int, default=None)
    p.add_argument("--full-float-scan", action="store_true")
    p.add_argument("--skip-scan", action="store_true")
    p.add_argument("--slip", type=float, default=15.0)
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    cfg = InplayContinuationConfig(
        start=datetime.fromisoformat(args.start).date(),
        end=datetime.fromisoformat(args.end).date(),
        slippage_bps_one_way=args.slip,
    )
    cfg.apply_cost_model(cfg.cost_model().with_slip(args.slip))

    result = run_probe(
        cfg,
        symbols=args.symbols,
        max_symbols=args.max_symbols,
        prefer_cached_float=not args.full_float_scan,
        skip_scan=args.skip_scan,
    )
    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[2] / "batch" / "inplay_continuation" / "probe_12m"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "RESULTS.json", result, indent=2)

    raw, paper, gates = result["raw"], result["paper"], result["gates"]
    lines = [
        "# In-play continuation — 12m probe v0.1.0 (Opp C)",
        "",
        f"**Pre-reg:** `{result['prereg']}`",
        f"**WeBull costs:** commission 0; baseline slip **{cfg.slippage_bps_one_way} bps** one-way (SMALL).",
        f"**Window:** {cfg.start} → {cfg.end}",
        f"**Construction:** `v0.1.0_inplay_continuation`",
        "",
        "## Gates",
        "",
        f"| Gate | Result |",
        f"|---|---|",
        f"| Pooled effR > 0 @ slip15 | {'**PASS**' if gates['pooled_eff_r_gt_0'] else '**FAIL**'} "
        f"({raw['pooled']['eff_r']:+.4f}) |",
        f"| ≥1 year > 0 | {'**PASS**' if gates['years_ok'] else '**FAIL**'} "
        f"({raw['gates']['years_positive']}/{raw['gates']['years_total']}) |",
        f"| Slip30 not catastrophe (effR > −0.05) | "
        f"{'**PASS**' if gates['slip30_not_catastrophe'] else '**FAIL**'} |",
        f"| **Overall** | **{'PASS' if gates['pass'] else 'FAIL'}** |",
        "",
        f"**Raw:** n={raw['pooled']['n']} win%={raw['pooled']['win_pct']} "
        f"effR={raw['pooled']['eff_r']:+.4f} pnl=${raw['pooled']['pnl']:+,.0f}",
        f"**Paper portfolio:** n={paper['pooled']['n']} skipped={paper['n_skipped_portfolio']} "
        f"effR={paper['pooled']['eff_r']:+.4f}",
        "",
        "| Year | n | win% | effR | pnl |",
        "|---|---:|---:|---:|---:|",
    ]
    for y, a in raw.get("years", {}).items():
        lines.append(
            f"| {y} | {a['n']} | {a['win_pct']} | {a['eff_r']:+.4f} | ${a['pnl']:+,.0f} |"
        )
    lines += [
        "",
        "## Cost stress (WeBull slip grid)",
        "",
        "| Scenario | slip | n | win% | effR | pass |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for label, a in result["cost_stress"].items():
        lines.append(
            f"| `{label}` | {a.get('slip_bps', '?')} | {a['n']} | {a['win_pct']} | "
            f"{a['eff_r']:+.4f} | {'Y' if a.get('pass') else 'N'} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
        (
            "PASS — candidate for Opp B selection layer; still no live capital."
            if gates["pass"]
            else "FAIL — park inplay_continuation v0.1.0; no threshold nibble. "
            "Next: different structural thesis or selection-first design with new pre-reg."
        ),
        "",
        "Caveat: current-snapshot float / cached universe; not multi-year PIT.",
        "",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(raw["pooled"], indent=2))
    print("gates", gates)
    for k, a in result["cost_stress"].items():
        print(f"{k:16} slip={a.get('slip_bps')} effR={a['eff_r']:+.4f}")
    print("wrote", out_dir / "RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
