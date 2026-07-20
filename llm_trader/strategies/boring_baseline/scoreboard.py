"""Opp E: boring session-long baselines vs clever select_A (WeBull costs)."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.costs.webull import (
    LiquidityTier,
    apply_buy_fill,
    apply_sell_fill,
    webull_long_equity,
)
from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.indicators import normalize_to_et
from trading.llm_trader.store import EntryStore
from trading.llm_trader.strategies.inplay_continuation.config import InplayContinuationConfig
from trading.llm_trader.strategies.inplay_continuation.patterns import simulate_trade
from trading.llm_trader.strategies.inplay_continuation.selection_b import (
    _entry_from_row,
    _passes_filter,
)

log = logging.getLogger("llm_trader.boring_baseline")

NOTIONAL = 5_000.0
STRATEGY_INPLAY = "inplay_continuation"


@dataclass
class DayTrade:
    ticker: str
    day: date
    entry_px: float
    exit_px: float
    shares: int
    pnl: float
    bps: float
    win: bool
    tag: str


def _rth_5m(ticker: str, day: date) -> Optional[pd.DataFrame]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    df = fetch_bars(ticker, "5min", start=start, end=end, session="rth", adjustment="raw")
    if df is None or df.empty:
        return None
    df = normalize_to_et(df, day=day)
    if df.empty:
        return None
    df = df.between_time(time(9, 30), time(16, 0), inclusive="left")
    return df if len(df) >= 10 else None


def _daily(ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
    s = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=40)
    e = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=s, end=e, adjustment="raw")
    if df is None or df.empty:
        return None
    return df.sort_index()


def _session_trade(
    ticker: str,
    day: date,
    *,
    model,
    tag: str,
    require_green_first: bool = False,
) -> Optional[DayTrade]:
    df = _rth_5m(ticker, day)
    if df is None:
        return None
    first, last = df.iloc[0], df.iloc[-1]
    if require_green_first and float(first["close"]) <= float(first["open"]):
        return None
    entry_mid = float(first["open"])
    exit_mid = float(last["close"])
    entry = apply_buy_fill(entry_mid, model)
    exit_ = apply_sell_fill(exit_mid, model)
    shares = max(1, int(NOTIONAL / entry))
    pnl = (exit_ - entry) * shares
    notional = entry * shares
    bps = (pnl / notional) * 10_000.0 if notional > 0 else 0.0
    return DayTrade(
        ticker=ticker,
        day=day,
        entry_px=round(entry, 4),
        exit_px=round(exit_, 4),
        shares=shares,
        pnl=round(pnl, 2),
        bps=round(bps, 3),
        win=pnl > 0,
        tag=tag,
    )


def _agg_day_trades(trades: list[DayTrade]) -> dict[str, Any]:
    if not trades:
        return {
            "n": 0,
            "win_pct": 0.0,
            "mean_bps": 0.0,
            "total_pnl": 0.0,
            "years": {},
        }
    by_y: dict[str, list[DayTrade]] = defaultdict(list)
    for t in trades:
        by_y[str(t.day.year)].append(t)
    years = {}
    for y, ts in sorted(by_y.items()):
        years[y] = {
            "n": len(ts),
            "win_pct": round(100.0 * sum(1 for t in ts if t.win) / len(ts), 1),
            "mean_bps": round(sum(t.bps for t in ts) / len(ts), 3),
            "total_pnl": round(sum(t.pnl for t in ts), 2),
        }
    return {
        "n": len(trades),
        "win_pct": round(100.0 * sum(1 for t in trades if t.win) / len(trades), 1),
        "mean_bps": round(sum(t.bps for t in trades) / len(trades), 3),
        "total_pnl": round(sum(t.pnl for t in trades), 2),
        "years": years,
    }


def run_baselines(start: date, end: date) -> dict[str, Any]:
    model = webull_long_equity(tier=LiquidityTier.MEGA)  # 2 bps slip
    # trading days from SPY daily
    ddf = _daily("SPY", start, end)
    if ddf is None or ddf.empty:
        raise RuntimeError("SPY daily unavailable")
    days = []
    gaps = {}
    ddf = ddf.copy()
    ddf["prior_close"] = ddf["close"].shift(1)
    for row in ddf.itertuples():
        d = row.Index.date() if hasattr(row.Index, "date") else pd.Timestamp(row.Index).date()
        if d < start or d > end:
            continue
        if pd.isna(row.prior_close) or row.prior_close <= 0:
            continue
        days.append(d)
        gaps[d] = (float(row.open) - float(row.prior_close)) / float(row.prior_close) * 100.0

    variants: dict[str, list[DayTrade]] = {
        "spy_oc": [],
        "qqq_oc": [],
        "spy_green_open": [],
        "spy_gap_nonneg": [],
    }
    for i, d in enumerate(days):
        if (i + 1) % 40 == 0:
            log.info("baseline days %d/%d", i + 1, len(days))
        t = _session_trade("SPY", d, model=model, tag="spy_oc")
        if t:
            variants["spy_oc"].append(t)
        t = _session_trade("QQQ", d, model=model, tag="qqq_oc")
        if t:
            variants["qqq_oc"].append(t)
        t = _session_trade("SPY", d, model=model, tag="spy_green_open", require_green_first=True)
        if t:
            variants["spy_green_open"].append(t)
        if gaps.get(d, -99) >= 0:
            t = _session_trade("SPY", d, model=model, tag="spy_gap_nonneg")
            if t:
                variants["spy_gap_nonneg"].append(t)

    return {
        name: _agg_day_trades(ts) for name, ts in variants.items()
    }, {name: len(ts) for name, ts in variants.items()}


def run_select_a_bps(
    start: date,
    end: date,
    *,
    db_path: Path,
) -> dict[str, Any]:
    """Re-sim select_A with $5k notional cap metrics (bps of actual entry notional)."""
    cfg = InplayContinuationConfig(start=start, end=end)
    cfg.apply_cost_model(webull_long_equity(tier=LiquidityTier.SMALL, slip_bps_one_way=15.0))
    # Force notional-like sizing: risk_budget large so 50x cap ~ binds differently
    # Use actual sim shares then bps = pnl/(entry*shares)*1e4
    store = EntryStore(db_path)
    try:
        rows = [dict(r) for r in store.all_rows(strategy=STRATEGY_INPLAY)]
    finally:
        store.close()
    entries = [
        e for e in (_entry_from_row(r) for r in rows)
        if start <= e.day <= end and _passes_filter(e, "select_A")
    ]
    trades_bps = []
    r_mults = []
    pnls = []
    by_y: dict[str, list] = defaultdict(list)
    for e in entries:
        tr = simulate_trade(e, cfg)
        if tr is None:
            continue
        notional = tr.entry_px * tr.shares
        bps = (tr.pnl_usd / notional) * 10_000.0 if notional > 0 else 0.0
        # rescale to $5k notional equivalent PnL for fair total comparison
        scale = NOTIONAL / notional if notional > 0 else 1.0
        pnl_5k = tr.pnl_usd * scale
        bps_5k = (pnl_5k / NOTIONAL) * 10_000.0
        rec = {
            "day": tr.day,
            "ticker": tr.ticker,
            "bps": bps_5k,
            "pnl": pnl_5k,
            "r": tr.r_multiple,
            "win": pnl_5k > 0,
        }
        trades_bps.append(rec)
        r_mults.append(tr.r_multiple)
        pnls.append(pnl_5k)
        by_y[str(tr.day.year)].append(rec)

    def pack(rows: list) -> dict:
        if not rows:
            return {"n": 0, "win_pct": 0.0, "mean_bps": 0.0, "total_pnl": 0.0, "mean_eff_r": 0.0}
        return {
            "n": len(rows),
            "win_pct": round(100.0 * sum(1 for r in rows if r["win"]) / len(rows), 1),
            "mean_bps": round(sum(r["bps"] for r in rows) / len(rows), 3),
            "total_pnl": round(sum(r["pnl"] for r in rows), 2),
            "mean_eff_r": round(sum(r["r"] for r in rows) / len(rows), 4),
        }

    years = {y: pack(rs) for y, rs in sorted(by_y.items())}
    pooled = pack(trades_bps)
    return {"pooled": pooled, "years": years, "trades": len(trades_bps)}


def run_scoreboard(
    *,
    start: date,
    end: date,
    inplay_db: Path,
) -> dict[str, Any]:
    import pandas as pd  # noqa: F401 — used in _daily path via Timestamp

    baselines, counts = run_baselines(start, end)
    clever = run_select_a_bps(start, end, db_path=inplay_db)

    best_name = max(baselines.keys(), key=lambda k: baselines[k]["mean_bps"])
    best = baselines[best_name]
    c = clever["pooled"]
    clever_wins = (
        c["n"] > 0
        and c["mean_bps"] > best["mean_bps"]
        and c["total_pnl"] > best["total_pnl"]
    )
    return {
        "experiment": "opp_e_boring_baseline_v010",
        "prereg": "batch/boring_baseline/PREREG_v010.md",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "notional_usd": NOTIONAL,
        "webull_mega_slip_bps": 2.0,
        "webull_select_a_slip_bps": 15.0,
        "baselines": baselines,
        "baseline_counts": counts,
        "select_a": clever,
        "scoreboard": {
            "best_baseline": best_name,
            "best_baseline_mean_bps": best["mean_bps"],
            "best_baseline_total_pnl": best["total_pnl"],
            "select_a_mean_bps": c["mean_bps"],
            "select_a_total_pnl": c["total_pnl"],
            "clever_wins": clever_wins,
        },
        "completed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Opp E boring baseline scoreboard")
    p.add_argument("--start", default="2025-07-01")
    p.add_argument("--end", default="2026-06-30")
    p.add_argument(
        "--inplay-db",
        default=str(
            Path(__file__).resolve().parents[2] / "data" / "inplay_continuation" / "entries.db"
        ),
    )
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)

    start = datetime.fromisoformat(args.start).date()
    end = datetime.fromisoformat(args.end).date()
    result = run_scoreboard(start=start, end=end, inplay_db=Path(args.inplay_db))

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[2]
        / "batch"
        / "boring_baseline"
        / "scoreboard_v010"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "RESULTS.json", result, indent=2)

    sb = result["scoreboard"]
    lines = [
        "# Opp E — boring baseline scoreboard v0.1.0",
        "",
        f"**Pre-reg:** `{result['prereg']}`",
        f"**Window:** {result['window']['start']} → {result['window']['end']}",
        f"**Sizing:** ${NOTIONAL:.0f} notional / trade (WeBull: mega 2 bps slip for beta; "
        f"select_A 15 bps small-tier)",
        "",
        "## Gates",
        "",
        f"| Gate | Result |",
        f"|---|---|",
        f"| Best boring baseline | `{sb['best_baseline']}` "
        f"mean **{sb['best_baseline_mean_bps']:+.2f} bps** / "
        f"pnl **${sb['best_baseline_total_pnl']:+,.0f}** |",
        f"| select_A mean bps | **{sb['select_a_mean_bps']:+.2f}** |",
        f"| select_A total pnl @$5k | **${sb['select_a_total_pnl']:+,.0f}** |",
        f"| **Clever wins scoreboard** | **{'YES' if sb['clever_wins'] else 'NO'}** |",
        "",
        "## Boring baselines (WeBull mega)",
        "",
        "| Variant | n | win% | mean bps | total pnl |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, a in result["baselines"].items():
        lines.append(
            f"| `{name}` | {a['n']} | {a['win_pct']} | {a['mean_bps']:+.2f} | ${a['total_pnl']:+,.0f} |"
        )
    lines += [
        "",
        "### Baseline by year (best + SPY OC)",
        "",
    ]
    for name in (sb["best_baseline"], "spy_oc"):
        a = result["baselines"][name]
        lines.append(f"**`{name}`**")
        lines.append("")
        lines.append("| Year | n | mean bps | pnl |")
        lines.append("|---|---:|---:|---:|")
        for y, ya in a.get("years", {}).items():
            lines.append(
                f"| {y} | {ya['n']} | {ya['mean_bps']:+.2f} | ${ya['total_pnl']:+,.0f} |"
            )
        lines.append("")

    ca = result["select_a"]["pooled"]
    lines += [
        "## select_A (Opp B) on same window",
        "",
        f"n={ca['n']} win%={ca['win_pct']} mean_bps={ca['mean_bps']:+.2f} "
        f"total_pnl=${ca['total_pnl']:+,.0f} mean_effR={ca['mean_eff_r']:+.4f}",
        "",
        "| Year | n | mean bps | pnl | effR |",
        "|---|---:|---:|---:|---:|",
    ]
    for y, ya in result["select_a"].get("years", {}).items():
        lines.append(
            f"| {y} | {ya['n']} | {ya['mean_bps']:+.2f} | ${ya['total_pnl']:+,.0f} | "
            f"{ya['mean_eff_r']:+.4f} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
    ]
    if sb["clever_wins"]:
        lines.append(
            f"**select_A beats** best boring (`{sb['best_baseline']}`) on mean bps and total PnL "
            "under stated costs. Still **no live capital** — n is tiny; use as license for "
            "**forward zero-capital shadow** only, not size."
        )
    else:
        lines.append(
            f"**select_A does not beat** best boring baseline (`{sb['best_baseline']}`). "
            "Deprioritize clever in-play until larger forward sample; prefer process/beta "
            "or a new thesis. Do not add more filters on the n=87 sample."
        )
    lines.append("")
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(sb, indent=2))
    print("wrote", out_dir / "RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
