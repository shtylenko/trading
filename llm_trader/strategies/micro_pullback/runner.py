"""Scan + multi-year short-hold backtest for micro-pullback."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore
from trading.llm_trader.universe import fetch_symbols

from .config import MicroPullbackConfig
from .patterns import SimTrade, detect_entry, screen_ticker, simulate_trade

log = logging.getLogger("llm_trader.micro_pullback")


@dataclass
class ScanStats:
    symbols_scanned: int = 0
    day_candidates: int = 0
    entries_found: int = 0
    symbols_failed: int = 0


def run_scan(
    cfg: MicroPullbackConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 20,
    strategy_id: str = "micro_pullback",
) -> ScanStats:
    if symbols is None:
        symbols = fetch_symbols(cfg.exchanges)
    symbols = list(dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip()))
    if max_symbols is not None:
        symbols = symbols[:max_symbols]

    stats = ScanStats()
    store = EntryStore(cfg.db_path)
    log.info(
        "micro_pullback scan %s→%s | %d symbols | gap≥%.1f rvol≥%.1f",
        cfg.start, cfg.end, len(symbols), cfg.gap_min_pct, cfg.rvol_min,
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
                    entry.strategy = strategy_id
                    store.upsert(entry)
                    stats.entries_found += 1
        store.dump_text(cfg.db_path.with_suffix(".txt"), strategy=strategy_id)
        store.dump_csv(cfg.db_path.with_suffix(".csv"), strategy=strategy_id)
        total = store.count(strategy=strategy_id)
    finally:
        store.close()
    log.info("done entries=%d table=%d", stats.entries_found, total)
    return stats


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


def _rows_to_trades(rows: list[dict], cfg: MicroPullbackConfig, strategy_id: str) -> list[SimTrade]:
    trades: list[SimTrade] = []
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
            pattern=r.get("pattern") or "micro_pullback",
            entry_px=float(r.get("entry_px") or 0),
            bar_close=float(r.get("bar_close") or r.get("entry_px") or 0),
            reason=r.get("reason") or "",
            strategy=strategy_id,
            gap_pct=r.get("gap_pct"),
            rvol=r.get("rvol"),
            features=feats or {},
        )
        try:
            tr = simulate_trade(entry, cfg)
        except Exception:
            log.exception("sim %s %s", entry.ticker, entry.day)
            continue
        if tr is not None:
            trades.append(tr)
    return trades


def run_backtest(
    cfg: MicroPullbackConfig,
    *,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
    progress_every: int = 20,
    strategy_id: str = "micro_pullback",
) -> dict:
    run_scan(
        cfg,
        symbols=symbols,
        max_symbols=max_symbols,
        progress_every=progress_every,
        strategy_id=strategy_id,
    )
    store = EntryStore(cfg.db_path)
    try:
        rows = [dict(r) for r in store.all_rows(strategy=strategy_id)]
    finally:
        store.close()

    trades = _rows_to_trades(rows, cfg, strategy_id)
    by_year: dict[str, list[SimTrade]] = defaultdict(list)
    for t in trades:
        by_year[str(t.day.year)].append(t)
    years = {y: _agg(ts) for y, ts in sorted(by_year.items())}
    pooled = _agg(trades)
    pos_years = sum(1 for a in years.values() if a.get("eff_r", 0) > 0)
    return {
        "strategy": strategy_id,
        "config": cfg.to_dict(),
        "entries": len(rows),
        "trades": len(trades),
        "years": years,
        "pooled": pooled,
        "gates": {
            "pooled_eff_r_gt_0": pooled["eff_r"] > 0,
            "years_positive": pos_years,
            "years_total": len(years),
            "pass": pooled["eff_r"] > 0 and pos_years >= 2,
        },
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_cost_stress(cfg: MicroPullbackConfig, rows: list[dict]) -> dict:
    grid = [
        (1.0, 2.0, "baseline_1f_2s"),
        (1.0, 4.0, "slip_2x"),
        (1.0, 6.0, "slip_3x"),
        (2.0, 4.0, "fee2_slip4"),
        (2.0, 6.0, "fee2_slip6"),
        (5.0, 5.0, "fee5_slip5"),
    ]
    out = {}
    for fee, slip, label in grid:
        c = deepcopy(cfg)
        c.fee_bps_one_way = fee
        c.slippage_bps_one_way = slip
        trades = _rows_to_trades(rows, c, "micro_pullback")
        a = _agg(trades)
        by_y: dict[str, list[SimTrade]] = defaultdict(list)
        for t in trades:
            by_y[str(t.day.year)].append(t)
        years_pos = sum(1 for ts in by_y.values() if _agg(ts)["eff_r"] > 0)
        a["fee_bps"] = fee
        a["slip_bps"] = slip
        a["years_pos"] = years_pos
        a["years_total"] = len(by_y)
        a["pass"] = a["eff_r"] > 0 and years_pos >= 2
        out[label] = a
    return out


def main_backtest(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Micro-pullback multi-year short-hold backtest")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--max-symbols", type=int, default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    cfg = MicroPullbackConfig(
        start=datetime.fromisoformat(args.start).date(),
        end=datetime.fromisoformat(args.end).date(),
    )
    result = run_backtest(cfg, symbols=args.symbols, max_symbols=args.max_symbols)

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[2]
        / "batch"
        / "micro_pullback"
        / "multiyear"
        / "RESULTS.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    store = EntryStore(cfg.db_path)
    rows = [dict(r) for r in store.all_rows(strategy="micro_pullback")]
    store.close()
    stress = run_cost_stress(cfg, rows)
    result["cost_stress"] = stress

    atomic_write_json(out, result, indent=2)
    md = out.with_suffix(".md")
    lines = [
        "# Micro-pullback — multi-year short-hold",
        "",
        f"**Pooled:** n={result['pooled']['n']} win%={result['pooled']['win_pct']} "
        f"effR={result['pooled']['eff_r']} pnl=${result['pooled']['pnl']}",
        f"**Gates pass:** {result['gates']['pass']}",
        "",
        "| Year | n | win% | effR | pnl |",
        "|---|---:|---:|---:|---:|",
    ]
    for y, a in result.get("years", {}).items():
        lines.append(f"| {y} | {a['n']} | {a['win_pct']} | {a['eff_r']} | {a['pnl']} |")
    lines += [
        "",
        "## Cost stress",
        "",
        "| Scenario | fee | slip | n | win% | effR | pass |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for label, a in stress.items():
        lines.append(
            f"| `{label}` | {a['fee_bps']} | {a['slip_bps']} | {a['n']} | "
            f"{a['win_pct']} | {a['eff_r']:+.4f} | {'Y' if a['pass'] else 'N'} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result["pooled"], indent=2))
    print("gates", result["gates"])
    for k, a in stress.items():
        print(
            f"{k:16} effR={a['eff_r']:+.4f} pass={a['pass']} years+={a['years_pos']}/{a['years_total']}"
        )
    print("wrote", out, md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_backtest())
