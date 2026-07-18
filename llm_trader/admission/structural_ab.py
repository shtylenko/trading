"""Structural A/B: No Man's Land + portfolio limits on existing short-hold entries.

Does **not** retune family detectors. Reuses sealed multi-year entry DBs, applies
pre-registered gates, re-sims path, writes comparison under batch/admission/.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from trading.llm_trader.admission.no_mans_land import (
    NmlConfig,
    evaluate_long_edge,
    find_signal_index,
)
from trading.llm_trader.admission.portfolio import PortfolioLimits, TimedTrade, apply_portfolio_limits
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore

log = logging.getLogger("llm_trader.admission.ab")


def _agg(rs: list[float], pnls: list[float] | None = None) -> dict:
    if not rs:
        return {"n": 0, "win_pct": 0.0, "eff_r": 0.0, "pnl": 0.0}
    return {
        "n": len(rs),
        "win_pct": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1),
        "eff_r": round(sum(rs) / len(rs), 4),
        "pnl": round(sum(pnls or [0.0] * len(rs)), 2),
    }


def _gates(years: dict[str, dict], pooled: dict) -> dict:
    pos = sum(1 for a in years.values() if a.get("eff_r", 0) > 0)
    return {
        "pooled_eff_r_gt_0": pooled["eff_r"] > 0,
        "years_positive": pos,
        "years_total": len(years),
        "pass": pooled["eff_r"] > 0 and pos >= 2,
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


def run_family_ab(
    *,
    strategy_id: str,
    db_path: Path,
    load_5m: Callable,
    simulate: Callable,
    cfg: Any,
    nml: NmlConfig,
    port: PortfolioLimits,
) -> dict:
    """Return baseline / nml / nml+portfolio / portfolio-only metrics."""
    rows = _load_rows(db_path, strategy_id)
    log.info("%s: %d sealed entries", strategy_id, len(rows))

    # Simulate all baseline trades first
    baseline_trades: list[dict] = []
    for r in rows:
        entry = _entry_from_row(r, strategy_id)
        try:
            tr = simulate(entry, cfg)
        except Exception:
            log.exception("sim %s %s", entry.ticker, entry.day)
            continue
        if tr is None:
            continue
        # Attach frame info for NML
        try:
            df = load_5m(entry.ticker, entry.day)
        except Exception:
            df = None
        sig_i = find_signal_index(df, entry.time_et) if df is not None else -1
        nml_dec = None
        if df is not None and sig_i >= 0:
            nml_dec = evaluate_long_edge(df, sig_i, float(entry.entry_px), nml)
        baseline_trades.append(
            {
                "ticker": tr.ticker,
                "day": tr.day,
                "entry_time": tr.entry_time,
                "exit_time": tr.exit_time,
                "r": tr.r_multiple,
                "pnl": tr.pnl_usd,
                "rvol": float(entry.rvol or 0),
                "gap_pct": float(entry.gap_pct or 0),
                "nml_admit": bool(nml_dec.admit) if nml_dec else False,
                "nml_reason": nml_dec.reason if nml_dec else "no_frame",
                "nml_position": nml_dec.position if nml_dec else None,
            }
        )

    def pack(subset: list[dict], label: str) -> dict:
        by_y: dict[str, list[float]] = defaultdict(list)
        by_y_pnl: dict[str, list[float]] = defaultdict(list)
        rs, pnls = [], []
        nml_reasons: dict[str, int] = defaultdict(int)
        for t in subset:
            rs.append(t["r"])
            pnls.append(t["pnl"])
            y = str(t["day"].year)
            by_y[y].append(t["r"])
            by_y_pnl[y].append(t["pnl"])
            nml_reasons[t.get("nml_reason") or "?"] += 1
        years = {
            y: _agg(by_y[y], by_y_pnl[y]) for y in sorted(by_y)
        }
        pooled = _agg(rs, pnls)
        return {
            "label": label,
            "pooled": pooled,
            "years": years,
            "gates": _gates(years, pooled),
            "nml_reason_counts": dict(sorted(nml_reasons.items(), key=lambda kv: -kv[1])),
        }

    baseline = pack(baseline_trades, "baseline")

    nml_kept = [t for t in baseline_trades if t["nml_admit"]]
    nml_only = pack(nml_kept, "nml_only")

    def port_filter(src: list[dict]) -> list[dict]:
        timed = [
            TimedTrade(
                ticker=t["ticker"],
                day=t["day"],
                entry_time=t["entry_time"],
                exit_time=t["exit_time"],
                r_multiple=t["r"],
                rvol=t["rvol"],
                gap_pct=t["gap_pct"],
                meta=t,
            )
            for t in src
        ]
        kept, _ = apply_portfolio_limits(timed, port)
        return [k.meta for k in kept if k.meta is not None]

    port_only = pack(port_filter(baseline_trades), "portfolio_only")
    nml_port = pack(port_filter(nml_kept), "nml_plus_portfolio")

    # Rejection stats
    rejected_nml = len(baseline_trades) - len(nml_kept)
    return {
        "strategy": strategy_id,
        "n_entries_sim": len(baseline_trades),
        "nml_config": nml.__dict__,
        "portfolio_config": port.__dict__,
        "variants": {
            "baseline": baseline,
            "nml_only": nml_only,
            "portfolio_only": port_only,
            "nml_plus_portfolio": nml_port,
        },
        "nml_rejected": rejected_nml,
        "nml_keep_rate": round(len(nml_kept) / len(baseline_trades), 4) if baseline_trades else 0.0,
    }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Structural NML + portfolio A/B on short-holds")
    p.add_argument(
        "--families",
        nargs="+",
        default=["micro_pullback", "vwap_pullback"],
        choices=["micro_pullback", "vwap_pullback"],
    )
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir) if args.out_dir else root / "batch" / "admission" / "structural_ab"
    out_dir.mkdir(parents=True, exist_ok=True)

    nml = NmlConfig()
    port = PortfolioLimits()
    results: dict[str, Any] = {
        "nml": nml.__dict__,
        "portfolio": port.__dict__,
        "families": {},
        "completed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    loaders = {}
    if "micro_pullback" in args.families:
        from trading.llm_trader.strategies.micro_pullback.config import MicroPullbackConfig
        from trading.llm_trader.strategies.micro_pullback.patterns import _rth_5m, simulate_trade

        loaders["micro_pullback"] = {
            "db": root / "data" / "micro_pullback" / "entries.db",
            "cfg": MicroPullbackConfig(),
            "load_5m": _rth_5m,
            "simulate": simulate_trade,
        }
    if "vwap_pullback" in args.families:
        from trading.llm_trader.strategies.vwap_pullback.config import VwapPullbackConfig
        from trading.llm_trader.strategies.vwap_pullback.patterns import _rth_5m, simulate_trade

        loaders["vwap_pullback"] = {
            "db": root / "data" / "vwap_pullback" / "entries.db",
            "cfg": VwapPullbackConfig(),
            "load_5m": _rth_5m,
            "simulate": simulate_trade,
        }

    for sid, pack in loaders.items():
        if not pack["db"].exists():
            log.warning("missing db %s — skip", pack["db"])
            continue
        ab = run_family_ab(
            strategy_id=sid,
            db_path=pack["db"],
            load_5m=pack["load_5m"],
            simulate=pack["simulate"],
            cfg=pack["cfg"],
            nml=nml,
            port=port,
        )
        results["families"][sid] = ab
        # print summary
        print(f"\n=== {sid} ===")
        for name, v in ab["variants"].items():
            g = v["gates"]
            print(
                f"  {name:20} n={v['pooled']['n']:4d} effR={v['pooled']['eff_r']:+.4f} "
                f"win%={v['pooled']['win_pct']:5.1f} pass={g['pass']} "
                f"years+={g['years_positive']}/{g['years_total']}"
            )

    out_json = out_dir / "RESULTS.json"
    atomic_write_json(out_json, results, indent=2)

    # Markdown
    lines = [
        "# Structural A/B — No Man's Land + portfolio limits",
        "",
        f"**NML:** `{nml.version}` lookback={nml.lookback_bars} mid=({nml.mid_lo},{nml.mid_hi}) "
        f"upper≥{nml.upper_edge_frac} breakout_close≥{nml.breakout_close_frac}",
        f"**Portfolio:** `{port.version}` max_concurrent={port.max_concurrent} max_per_day={port.max_per_day}",
        "",
        "Gates unchanged: pooled effR>0 and ≥2/4 years>0.",
        "",
    ]
    for sid, ab in results["families"].items():
        lines += [
            f"## {sid}",
            "",
            f"Sealed sims: {ab['n_entries_sim']} · NML keep rate: {ab['nml_keep_rate']:.1%} "
            f"(rejected {ab['nml_rejected']})",
            "",
            "| Variant | n | win% | effR | years+ | pass |",
            "|---|---:|---:|---:|---:|:---:|",
        ]
        for name, v in ab["variants"].items():
            g = v["gates"]
            lines.append(
                f"| `{name}` | {v['pooled']['n']} | {v['pooled']['win_pct']} | "
                f"{v['pooled']['eff_r']:+.4f} | {g['years_positive']}/{g['years_total']} | "
                f"{'Y' if g['pass'] else 'N'} |"
            )
        lines += ["", "Year detail (baseline vs nml_only):", ""]
        bl, nm = ab["variants"]["baseline"], ab["variants"]["nml_only"]
        lines += [
            "| Year | base n | base effR | nml n | nml effR |",
            "|---|---:|---:|---:|---:|",
        ]
        years = sorted(set(bl["years"]) | set(nm["years"]))
        for y in years:
            b, n = bl["years"].get(y, {}), nm["years"].get(y, {})
            lines.append(
                f"| {y} | {b.get('n', 0)} | {b.get('eff_r', 0):+.4f} | "
                f"{n.get('n', 0)} | {n.get('eff_r', 0):+.4f} |"
            )
        lines.append("")
        # top reject reasons
        reasons = ab["variants"]["baseline"].get("nml_reason_counts") or {}
        # Actually reason counts on baseline include admits — better from full set
        # We stored per-variant from subset only. Skip or recompute from first pack.
        lines.append("")

    lines += [
        "## Verdict rules (pre-registered)",
        "",
        "1. **NML helps** if `nml_only` effR > baseline and still passes gates (or converts fail→pass).",
        "2. **NML hurts** if effR drops or years+ collapses.",
        "3. **Portfolio** is risk packaging — judge on whether pass holds with lower n, not max effR.",
        "4. Do not retune mid_lo/mid_hi after seeing these numbers without a new pre-reg version.",
        "",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out_json, out_dir / "RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
