"""Opp B: pre-registered selection A/B on sealed inplay_continuation entries."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from trading.llm_trader.admission.portfolio import PortfolioLimits, TimedTrade, apply_portfolio_limits
from trading.llm_trader.costs.webull import webull_long_equity, LiquidityTier
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore

from .config import InplayContinuationConfig
from .patterns import SimTrade, simulate_trade

log = logging.getLogger("llm_trader.inplay_continuation.selection_b")
STRATEGY_ID = "inplay_continuation"


def _tmin(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _agg(ts: list[SimTrade]) -> dict:
    if not ts:
        return {"n": 0, "win_pct": 0.0, "eff_r": 0.0, "pnl": 0.0}
    rs = [t.r_multiple for t in ts]
    return {
        "n": len(ts),
        "win_pct": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1),
        "eff_r": round(sum(rs) / len(rs), 4),
        "pnl": round(sum(t.pnl_usd for t in ts), 2),
    }


def _metrics(trades: list[SimTrade]) -> dict:
    by_y: dict[str, list[SimTrade]] = defaultdict(list)
    for t in trades:
        by_y[str(t.day.year)].append(t)
    years = {y: _agg(ts) for y, ts in sorted(by_y.items())}
    pooled = _agg(trades)
    pos = sum(1 for a in years.values() if a.get("eff_r", 0) > 0)
    both = all(years.get(y, {}).get("eff_r", -1) > 0 for y in ("2025", "2026")) if years else False
    # if a year missing, both_years only if present years all > 0 and we have 2
    if set(years.keys()) == {"2025", "2026"}:
        both = years["2025"]["eff_r"] > 0 and years["2026"]["eff_r"] > 0
    else:
        both = pos >= 2 and pooled["eff_r"] > 0
    return {
        "pooled": pooled,
        "years": years,
        "years_positive": pos,
        "both_years_positive": both,
        "pass_primary": pooled["eff_r"] > 0 and both,
    }


def _entry_from_row(r: dict) -> Entry:
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
        pattern=r.get("pattern") or STRATEGY_ID,
        entry_px=float(r.get("entry_px") or 0),
        bar_close=float(r.get("bar_close") or r.get("entry_px") or 0),
        reason=r.get("reason") or "",
        strategy=STRATEGY_ID,
        gap_pct=r.get("gap_pct"),
        rvol=r.get("rvol"),
        features=feats or {},
    )


def _passes_filter(entry: Entry, name: str) -> bool:
    feats = entry.features or {}
    gap = float(entry.gap_pct if entry.gap_pct is not None else feats.get("gap_pct") or 0)
    rvol = float(entry.rvol if entry.rvol is not None else feats.get("rvol") or 0)
    depth = float(feats.get("depth_frac") or 1.0)
    t = entry.time_et or "99:99"

    if name == "baseline":
        return True
    if name == "morning_only":
        return _tmin(t) < _tmin("11:00")
    if name == "gap_band":
        return 5.0 <= gap <= 15.0
    if name == "rvol_strict":
        return rvol >= 3.0
    if name == "shallow_pb":
        return depth <= 0.40
    if name == "select_A":
        return (
            _tmin(t) < _tmin("11:00")
            and 5.0 <= gap <= 15.0
            and rvol >= 3.0
        )
    if name == "select_A_shallow":
        return (
            _tmin(t) < _tmin("11:00")
            and 5.0 <= gap <= 15.0
            and rvol >= 3.0
            and depth <= 0.40
        )
    raise ValueError(name)


def _first_per_day(entries: list[Entry]) -> list[Entry]:
    by_day: dict = defaultdict(list)
    for e in entries:
        by_day[e.day].append(e)
    out = []
    for d in sorted(by_day):
        best = min(by_day[d], key=lambda e: _tmin(e.time_et or "99:99"))
        out.append(best)
    return out


def _sim_all(entries: list[Entry], cfg: InplayContinuationConfig) -> list[tuple[Entry, SimTrade]]:
    pairs = []
    for e in entries:
        tr = simulate_trade(e, cfg)
        if tr is not None:
            pairs.append((e, tr))
    return pairs


def _portfolio_pack(pairs: list[tuple[Entry, SimTrade]], cfg: InplayContinuationConfig) -> list[SimTrade]:
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
    kept, _ = apply_portfolio_limits(
        timed, PortfolioLimits(cfg.paper_max_concurrent, cfg.paper_max_per_day)
    )
    idx = {t.meta["i"] for t in kept if t.meta}
    return [pairs[i][1] for i in sorted(idx)]


def run_selection_ab(
    cfg: InplayContinuationConfig,
    *,
    db_path: Optional[Path] = None,
) -> dict[str, Any]:
    db = Path(db_path or cfg.db_path)
    store = EntryStore(db)
    try:
        rows = [dict(r) for r in store.all_rows(strategy=STRATEGY_ID)]
    finally:
        store.close()
    all_entries = [_entry_from_row(r) for r in rows]
    log.info("sealed entries %d from %s", len(all_entries), db)

    variants = [
        "baseline",
        "morning_only",
        "gap_band",
        "rvol_strict",
        "shallow_pb",
        "first_per_day",
        "select_A",
        "select_A_shallow",
        "select_A_first",
    ]

    out_variants: dict[str, Any] = {}
    for name in variants:
        if name == "first_per_day":
            filtered = _first_per_day(all_entries)
        elif name == "select_A_first":
            filtered = _first_per_day([e for e in all_entries if _passes_filter(e, "select_A")])
        else:
            filtered = [e for e in all_entries if _passes_filter(e, name)]

        # slip 15
        c15 = deepcopy(cfg)
        c15.apply_cost_model(webull_long_equity(tier=LiquidityTier.SMALL, slip_bps_one_way=15.0))
        pairs15 = _sim_all(filtered, c15)
        trades15 = [t for _, t in pairs15]
        paper15 = _portfolio_pack(pairs15, c15)
        m15 = _metrics(trades15)
        m15_paper = _metrics(paper15)

        # slip 30
        c30 = deepcopy(cfg)
        c30.apply_cost_model(webull_long_equity(tier=LiquidityTier.SMALL, slip_bps_one_way=30.0))
        pairs30 = _sim_all(filtered, c30)
        m30 = _metrics([t for _, t in pairs30])

        out_variants[name] = {
            "n_entries": len(filtered),
            "n_trades_slip15": m15["pooled"]["n"],
            "slip15": m15,
            "slip15_paper": m15_paper,
            "slip30": m30,
            "slip30_not_catastrophe": m30["pooled"]["eff_r"] > -0.05,
            "primary_keep": m15["pass_primary"],
        }

    # decisions
    select_a = out_variants["select_A"]
    soft_winners = [
        n for n, v in out_variants.items()
        if v["slip15"]["both_years_positive"] and v["slip15"]["pooled"]["eff_r"] > 0
    ]
    result = {
        "experiment": "opp_b_selection",
        "prereg": "batch/inplay_continuation/PREREG_OPPB_SELECTION.md",
        "base_n": len(all_entries),
        "variants": out_variants,
        "gates": {
            "select_A_primary_keep": select_a["primary_keep"],
            "soft_winners": soft_winners,
            "any_both_years": len(soft_winners) > 0,
            "select_A_slip30_ok": select_a["slip30_not_catastrophe"],
            "pass": select_a["primary_keep"] and select_a["slip30_not_catastrophe"],
        },
        "completed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    return result


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Opp B selection A/B on inplay_continuation")
    p.add_argument("--db", default=None)
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    cfg = InplayContinuationConfig()
    if args.db:
        cfg.db_path = Path(args.db)
    result = run_selection_ab(cfg, db_path=cfg.db_path)

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[2]
        / "batch"
        / "inplay_continuation"
        / "selection_b"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "RESULTS.json", result, indent=2)

    lines = [
        "# Opp B selection A/B — inplay_continuation",
        "",
        f"**Pre-reg:** `{result['prereg']}`",
        f"**Base sealed n:** {result['base_n']}",
        f"**WeBull:** slip 15 baseline / 30 stress; no detector retune",
        "",
        "## Gates",
        "",
        f"| Gate | Result |",
        f"|---|---|",
        f"| `select_A` both years > 0 & pooled > 0 @15 | "
        f"{'**PASS**' if result['gates']['select_A_primary_keep'] else '**FAIL**'} |",
        f"| Any soft winner (both years) | "
        f"{'**YES** ' + str(result['gates']['soft_winners']) if result['gates']['any_both_years'] else '**NO**'} |",
        f"| `select_A` slip30 not catastrophe | "
        f"{'**PASS**' if result['gates']['select_A_slip30_ok'] else '**FAIL**'} |",
        f"| **Primary pass** | **{'PASS' if result['gates']['pass'] else 'FAIL'}** |",
        "",
        "## Variants @ slip 15",
        "",
        "| Variant | n | win% | effR | 2025 | 2026 | both+ | primary |",
        "|---|---:|---:|---:|---:|---:|:---:|:---:|",
    ]
    for name, v in result["variants"].items():
        s = v["slip15"]
        y25 = s["years"].get("2025", {}).get("eff_r", float("nan"))
        y26 = s["years"].get("2026", {}).get("eff_r", float("nan"))
        y25s = f"{y25:+.3f}" if y25 == y25 else "—"
        y26s = f"{y26:+.3f}" if y26 == y26 else "—"
        lines.append(
            f"| `{name}` | {s['pooled']['n']} | {s['pooled']['win_pct']} | "
            f"{s['pooled']['eff_r']:+.4f} | {y25s} | {y26s} | "
            f"{'Y' if s['both_years_positive'] else 'N'} | "
            f"{'Y' if v['primary_keep'] else 'N'} |"
        )
    lines += [
        "",
        "## Slip 30 (catastrophe check)",
        "",
        "| Variant | n | effR | > −0.05 |",
        "|---|---:|---:|:---:|",
    ]
    for name, v in result["variants"].items():
        s = v["slip30"]
        lines.append(
            f"| `{name}` | {s['pooled']['n']} | {s['pooled']['eff_r']:+.4f} | "
            f"{'Y' if v['slip30_not_catastrophe'] else 'N'} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
    ]
    if result["gates"]["pass"]:
        lines.append(
            "**KEEP `select_A`** as v0.1.1 admission for further work (still no live capital). "
            "Next: forward shadow / real fill calibration only."
        )
    elif result["gates"]["any_both_years"]:
        lines.append(
            f"**Soft keep** variants {result['gates']['soft_winners']} — promote only the "
            f"pre-registered soft path with a **new** version id; primary `select_A` failed."
        )
    else:
        lines.append(
            "**KILL Opp C + Opp B on this sample:** no pre-registered selection achieves "
            "both years positive. Park `inplay_continuation` v0.1; do **not** invent more "
            "filters on these 87 trades. Next: Opp E boring baseline or new structural thesis."
        )
    lines.append("")
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result["gates"], indent=2))
    for name, v in result["variants"].items():
        s = v["slip15"]
        print(
            f"{name:18} n={s['pooled']['n']:3d} effR={s['pooled']['eff_r']:+.4f} "
            f"both={s['both_years_positive']}"
        )
    print("wrote", out_dir / "RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
