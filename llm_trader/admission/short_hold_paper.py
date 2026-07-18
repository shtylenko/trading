"""Shared deterministic paper-book builder for short-hold families.

Portfolio packaging ON by default; NML always forced OFF (structural A/B).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Sequence

from trading.llm_trader.admission.portfolio import PortfolioLimits, TimedTrade, apply_portfolio_limits
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore

log = logging.getLogger("llm_trader.admission.short_hold_paper")


class _SimTradeLike(Protocol):
    ticker: str
    day: Any
    entry_time: str
    exit_time: str
    entry_px: float
    exit_px: float
    stop_px: float
    target1_px: float
    target2_px: float
    exit_reason: str
    r_multiple: float
    pnl_usd: float
    shares: int


def _agg_trades(trades: Sequence[_SimTradeLike]) -> dict:
    if not trades:
        return {"n": 0, "win_pct": 0.0, "eff_r": 0.0, "pnl": 0.0, "exits": {}}
    rs = [t.r_multiple for t in trades]
    return {
        "n": len(trades),
        "win_pct": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1),
        "eff_r": round(sum(rs) / len(rs), 4),
        "pnl": round(sum(t.pnl_usd for t in trades), 2),
        "exits": {
            k: sum(1 for t in trades if t.exit_reason == k)
            for k in ("STOP", "TARGET1", "TARGET2", "EOD")
        },
    }


def _metrics(trades: Sequence[_SimTradeLike]) -> dict:
    by_year: dict[str, list] = defaultdict(list)
    for t in trades:
        by_year[str(t.day.year)].append(t)
    years = {y: _agg_trades(ts) for y, ts in sorted(by_year.items())}
    pooled = _agg_trades(trades)
    pos = sum(1 for a in years.values() if a.get("eff_r", 0) > 0)
    return {
        "pooled": pooled,
        "years": years,
        "gates": {
            "pooled_eff_r_gt_0": pooled["eff_r"] > 0,
            "years_positive": pos,
            "years_total": len(years),
            "pass": pooled["eff_r"] > 0 and pos >= 2,
        },
    }


def _load_rows(db_path: Path, strategy_id: str) -> list[dict]:
    store = EntryStore(db_path)
    try:
        return [dict(r) for r in store.all_rows(strategy=strategy_id)]
    finally:
        store.close()


def _entry_from_row(r: dict, strategy_id: str) -> Entry:
    feats = r.get("features_json")
    if isinstance(feats, str):
        try:
            feats = json.loads(feats)
        except json.JSONDecodeError:
            feats = {}
    return Entry(
        ticker=r["ticker"],
        day=datetime.fromisoformat(str(r["date"])).date(),
        time_et=r.get("time_et") or "10:00",
        pattern=r.get("pattern") or strategy_id,
        entry_px=float(r.get("entry_px") or 0),
        bar_close=float(r.get("bar_close") or r.get("entry_px") or 0),
        reason=r.get("reason") or "",
        strategy=strategy_id,
        gap_pct=r.get("gap_pct"),
        rvol=r.get("rvol"),
        features=feats or {},
    )


def _trade_record(entry: Entry, tr: _SimTradeLike, *, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "ticker": tr.ticker,
        "day": tr.day.isoformat() if hasattr(tr.day, "isoformat") else str(tr.day),
        "signal_time_et": entry.time_et,
        "entry_time": tr.entry_time,
        "exit_time": tr.exit_time,
        "entry_px": tr.entry_px,
        "exit_px": tr.exit_px,
        "stop_px": tr.stop_px,
        "target1_px": tr.target1_px,
        "target2_px": tr.target2_px,
        "exit_reason": tr.exit_reason,
        "r_multiple": tr.r_multiple,
        "pnl_usd": tr.pnl_usd,
        "shares": tr.shares,
        "gap_pct": entry.gap_pct,
        "rvol": entry.rvol,
        "reason": entry.reason,
    }


def apply_portfolio_to_pairs(
    pairs: list[tuple[Entry, Any]],
    limits: PortfolioLimits,
) -> tuple[list[tuple[Entry, Any]], list[tuple[Entry, Any]]]:
    timed = []
    for i, (entry, tr) in enumerate(pairs):
        timed.append(
            TimedTrade(
                ticker=tr.ticker,
                day=tr.day,
                entry_time=tr.entry_time,
                exit_time=tr.exit_time,
                r_multiple=tr.r_multiple,
                rvol=float(entry.rvol or 0),
                gap_pct=float(entry.gap_pct or 0),
                meta={"i": i},
            )
        )
    kept_t, rej_t = apply_portfolio_limits(timed, limits)
    kept_idx = {t.meta["i"] for t in kept_t if t.meta}
    rej_idx = {t.meta["i"] for t in rej_t if t.meta}
    return (
        [pairs[i] for i in sorted(kept_idx)],
        [pairs[i] for i in sorted(rej_idx)],
    )


def build_short_hold_paper_book(
    *,
    strategy_id: str,
    contract: str,
    cfg: Any,
    simulate: Callable[[Entry, Any], Optional[Any]],
    run_cost_stress: Optional[Callable[[Any, list[dict]], dict]] = None,
    limits: Optional[PortfolioLimits] = None,
    include_rejected: bool = True,
    run_stress: bool = True,
    promotion_notes: str = (
        "Thin multi-year edge under portfolio packaging; cost-fragile. "
        "Do not live-size. NML gate remains OFF."
    ),
) -> dict[str, Any]:
    """Build paper book from sealed entries under ``cfg.db_path``."""
    if getattr(cfg, "nml_gate", False):
        log.warning(
            "nml_gate=True on paper path is discouraged (structural A/B reject); forcing OFF"
        )
        cfg = deepcopy(cfg)
        cfg.nml_gate = False

    rows = _load_rows(Path(cfg.db_path), strategy_id)
    pairs: list[tuple[Entry, Any]] = []
    for r in rows:
        entry = _entry_from_row(r, strategy_id)
        if entry.day < cfg.start or entry.day > cfg.end:
            continue
        try:
            tr = simulate(entry, cfg)
        except Exception:
            log.exception("sim %s %s", entry.ticker, entry.day)
            continue
        if tr is not None:
            pairs.append((entry, tr))

    raw_metrics = _metrics([tr for _, tr in pairs])

    if limits is None:
        if getattr(cfg, "paper_portfolio", True):
            limits = PortfolioLimits(
                max_concurrent=int(getattr(cfg, "paper_max_concurrent", 3)),
                max_per_day=int(getattr(cfg, "paper_max_per_day", 5)),
            )
        else:
            limits = PortfolioLimits(max_concurrent=10_000, max_per_day=10_000)

    kept_pairs, rej_pairs = apply_portfolio_to_pairs(pairs, limits)
    kept_trades = [tr for _, tr in kept_pairs]
    paper_metrics = _metrics(kept_trades)

    stress = None
    if run_stress and kept_pairs and run_cost_stress is not None:
        stress_rows = []
        for entry, _tr in kept_pairs:
            stress_rows.append(
                {
                    "ticker": entry.ticker,
                    "date": entry.day.isoformat(),
                    "time_et": entry.time_et,
                    "pattern": entry.pattern,
                    "entry_px": entry.entry_px,
                    "bar_close": entry.bar_close,
                    "reason": entry.reason,
                    "gap_pct": entry.gap_pct,
                    "rvol": entry.rvol,
                    "features_json": json.dumps(entry.features or {}),
                }
            )
        stress = run_cost_stress(cfg, stress_rows)

    return {
        "contract": contract,
        "strategy": strategy_id,
        "nml_gate": False,
        "portfolio": asdict(limits),
        "config": cfg.to_dict() if hasattr(cfg, "to_dict") else {},
        "raw": {
            "n_entries": len(rows),
            "n_sim": len(pairs),
            **raw_metrics,
        },
        "paper": {
            "n_taken": len(kept_trades),
            "n_skipped_portfolio": len(rej_pairs),
            **paper_metrics,
        },
        "cost_stress_on_taken": stress,
        "trades": [_trade_record(e, t, status="taken") for e, t in kept_pairs],
        "rejected_sample": (
            [_trade_record(e, t, status="portfolio_skip") for e, t in rej_pairs[:50]]
            if include_rejected
            else []
        ),
        "rejected_total": len(rej_pairs),
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "promotion": {
            "status": "research_paper_optional",
            "notes": promotion_notes,
        },
    }


def write_short_hold_paper_book(
    result: dict,
    out_dir: Path,
    *,
    title: str,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jpath = out_dir / "PAPER_BOOK.json"
    mpath = out_dir / "PAPER_BOOK.md"
    atomic_write_json(jpath, result, indent=2)

    p = result["paper"]
    raw = result["raw"]
    lines = [
        f"# {title} (`{result['contract']}`)",
        "",
        f"**Status:** {result['promotion']['status']}",
        f"**Completed:** {result['completed_at']}",
        "",
        "## Packaging",
        "",
        "- NML gate: **OFF** (structural A/B reject)",
        f"- Portfolio: `{result['portfolio']}`",
        f"- Costs: fee={result['config'].get('fee_bps_one_way')} bps + "
        f"slip={result['config'].get('slippage_bps_one_way')} bps each way",
        f"- Risk budget / trade: ${result['config'].get('risk_budget')}",
        "",
        "## Gates (paper book)",
        "",
        "| | Raw (ungated sim) | Paper (portfolio) |",
        "|---|---:|---:|",
        f"| n | {raw['pooled']['n']} | {p['pooled']['n']} |",
        f"| win% | {raw['pooled']['win_pct']} | {p['pooled']['win_pct']} |",
        f"| effR | {raw['pooled']['eff_r']:+.4f} | **{p['pooled']['eff_r']:+.4f}** |",
        f"| pnl | ${raw['pooled']['pnl']:+,.0f} | **${p['pooled']['pnl']:+,.0f}** |",
        f"| years+ | {raw['gates']['years_positive']}/{raw['gates']['years_total']} | "
        f"**{p['gates']['years_positive']}/{p['gates']['years_total']}** |",
        f"| pass | {raw['gates']['pass']} | **{p['gates']['pass']}** |",
        "",
        f"Portfolio skipped: **{result['paper']['n_skipped_portfolio']}** candidates",
        "",
        "### By year (paper)",
        "",
        "| Year | n | win% | effR | pnl |",
        "|---|---:|---:|---:|---:|",
    ]
    for y, a in p.get("years", {}).items():
        lines.append(
            f"| {y} | {a['n']} | {a['win_pct']} | {a['eff_r']:+.4f} | ${a['pnl']:+,.0f} |"
        )

    if result.get("cost_stress_on_taken"):
        lines += [
            "",
            "## Cost stress (re-sim taken set; no re-portfolio)",
            "",
            "| Scenario | fee | slip | n | win% | effR | pass |",
            "|---|---:|---:|---:|---:|---:|:---:|",
        ]
        for label, a in result["cost_stress_on_taken"].items():
            lines.append(
                f"| `{label}` | {a['fee_bps']} | {a['slip_bps']} | {a['n']} | "
                f"{a['win_pct']} | {a['eff_r']:+.4f} | {'Y' if a['pass'] else 'N'} |"
            )

    lines += [
        "",
        "## Promotion bar",
        "",
        result["promotion"]["notes"],
        "",
        "- Live size: **no**",
        "- Paper / tiny size: optional if operator accepts cost fragility",
        "- Detector retune: **no** (edge is structural packaging only)",
        "",
        f"Full trade list: `{jpath.name}` (`trades` array, n={len(result['trades'])}).",
        "",
    ]
    mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jpath, mpath
