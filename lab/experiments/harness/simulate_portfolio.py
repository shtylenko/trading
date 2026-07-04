#!/usr/bin/env python3
"""Simulate a $-denominated PORTFOLIO running a swing strategy over an arbitrary window.

Unlike `scripts.backtest` (which persists an engine run to DuckDB and drops incomplete
final holds), this is a stand-alone, ephemeral simulation: pick a release, a date range,
and a starting capital; it runs the release's own ranking each rebalance, buys the top-N
equal-weight in WHOLE shares, compounds equity, and **liquidates all positions on the end
date** (the final hold is truncated to end). Prints profitability metrics + the full trade
ledger, and writes an HTML report (equity curve + tables).

Works for any swing release (x01, x03, …) — it calls the release's build_candidates, so the
selection logic is exactly the strategy's.

Usage:
    python3 -m trading.lab.experiments.harness.simulate_portfolio \
        --release x03 --start 2022-01-01 --end 2024-12-31 --capital 100000 \
        [--universe liquid_pit] [--cost-bps 10] [--top-n 50] [--out report.html]
"""
from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.core.models import StrategyContext
from trading.lab.data.universes import load_universe_tickers
from trading.lab.runner.pipeline import _trading_days
from trading.lab.runner.swing_pipeline import _load_daily_bars
from trading.lab.strategies import get_release_class


def _asof(bars, ts):
    """close at or just before ts (handles missing exact day); (price, date) or None."""
    s = bars[bars.index <= ts]
    if s.empty:
        return None
    return float(s["close"].iloc[-1]), s.index[-1]


def _parse(d):
    return datetime.strptime(d, "%Y-%m-%d").date()


def main():
    ap = argparse.ArgumentParser(description="Simulate a $ portfolio running a swing strategy")
    ap.add_argument("--release", required=True)
    ap.add_argument("--start", required=True, type=_parse)
    ap.add_argument("--end", required=True, type=_parse)
    ap.add_argument("--capital", type=float, default=100_000.0)
    ap.add_argument("--universe", default=None, help="default: the release's, else liquid_pit")
    ap.add_argument("--cost-bps", type=float, default=10.0, help="round-trip cost per name (spread+fees)")
    ap.add_argument("--top-n", type=int, default=None, help="override the release's top_n")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "engine/strategy_lab/portfolio_sim.html"))
    a = ap.parse_args()

    rel = get_release_class(a.release)()
    if not getattr(rel, "is_swing", False):
        sys.exit(f"{a.release} is not a swing release (this simulates multi-day books).")
    H = int(rel.hold_days); cad = int(rel.rebalance_cadence_days)
    top_n = a.top_n or int(rel.top_n)
    universe = a.universe or "liquid_pit"
    adj = getattr(rel, "daily_adjustment", "split")

    tdays = [pd.Timestamp(d) for d in _trading_days(a.start, a.end)]
    if len(tdays) < 2:
        sys.exit("date range too short.")
    rebal = tdays[::cad]
    members = {rd: set(load_universe_tickers(universe, rd.date())) for rd in rebal}
    union = set().union(*members.values()) if members else set()
    print(f"Simulating {a.release} ({rel.strategy_name}) on {universe}: "
          f"{a.start}→{a.end}, {len(rebal)} rebalances, hold={H}d, top_n={top_n}, ${a.capital:,.0f}…")
    bars = _load_daily_bars(union, a.start - timedelta(days=600), a.end + timedelta(days=5), False, adjustment=adj)
    spy_full = None
    if getattr(rel, "requires_spy_daily", False):
        spy_full = _load_daily_bars(["SPY"], a.start - timedelta(days=600), a.end + timedelta(days=5), False, adjustment=adj).get("SPY")

    equity = a.capital
    curve = [(a.start.isoformat(), equity)]
    reb_rows, trades, peak, maxdd = [], [], equity, 0.0
    for i, rd in enumerate(rebal):
        # context THROUGH the rebalance close
        ctx_daily = {}
        for t in members[rd]:
            b = bars.get(t)
            if b is None or rd not in b.index:
                continue
            upto = b[b.index <= rd]
            if len(upto) >= 253:
                ctx_daily[t] = upto.tail(300)
        spy_daily = None
        if spy_full is not None:
            s = spy_full[spy_full.index <= rd]
            spy_daily = s.tail(300) if len(s) else None
        ctx = StrategyContext(trade_date=rd.date(), release_id=a.release, testset=None,
                              bars_5m={}, daily=ctx_daily, spy_daily=spy_daily)
        cands = rel.build_candidates(ctx)[:top_n]
        # exit date = H trading days later, capped at the end (liquidate-all on end)
        exit_ts = tdays[min(i * cad + H, len(tdays) - 1)]
        # build the book: entry = close at rd, exit = close at exit_ts
        book = []
        for cand in cands:
            b = bars.get(cand.ticker)
            if b is None or rd not in b.index:
                continue
            ep = float(b.loc[rd, "close"])
            ex = _asof(b, exit_ts)
            if ep <= 0 or ex is None or ex[1] <= rd:
                continue
            book.append((cand.ticker, ep, ex[0]))
        if not book:
            continue
        alloc = equity / len(book)
        cost = a.cost_bps / 10000.0
        invested = pnl = 0.0
        for tk, ep, xp in book:
            sh = int(alloc // ep)
            if sh <= 0:
                continue
            notional = sh * ep
            tpnl = sh * (xp - ep) - (notional + sh * xp) * cost
            invested += notional; pnl += tpnl
            trades.append((rd.date().isoformat(), exit_ts.date().isoformat(), tk, sh, notional, tpnl, (xp / ep - 1) * 100))
        prev = equity
        equity += pnl
        peak = max(peak, equity); maxdd = min(maxdd, equity / peak - 1)
        reb_rows.append((rd.date().isoformat(), len(book), invested, pnl, equity, pnl / prev * 100))
        curve.append((exit_ts.date().isoformat(), equity))

    if not reb_rows:
        sys.exit("no trades produced (check date range / data coverage).")
    _report(a, equity, curve, reb_rows, trades, maxdd, rebal, H)


def _report(a, equity, curve, reb_rows, trades, maxdd, rebal, H):
    tot = equity / a.capital - 1
    span = (a.end - a.start).days / 365.25
    cagr = (equity / a.capital) ** (1 / max(span, 1e-9)) - 1
    rets = np.array([r[5] for r in reb_rows]) / 100.0
    ann = np.sqrt(252.0 / H)
    sharpe = rets.mean() / rets.std(ddof=1) * ann if len(rets) > 1 and rets.std() > 0 else float("nan")
    tp = np.array([t[5] for t in trades])
    wins = tp[tp > 0]; losses = tp[tp < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() != 0 else float("inf")
    print(f"\n{'='*70}\nPORTFOLIO SIMULATION — {a.release}  {a.start} → {a.end}")
    print(f"{'='*70}")
    print(f"  Starting capital      ${a.capital:,.0f}")
    print(f"  Ending equity         ${equity:,.0f}   (all positions liquidated {a.end})")
    print(f"  Total return          {tot*100:+.1f}%      CAGR {cagr*100:+.1f}%/yr  ({span:.2f}y)")
    print(f"  Max drawdown          {maxdd*100:.1f}%      per-rebalance Sharpe(ann) {sharpe:+.2f}")
    print(f"  Rebalances            {len(reb_rows)}        Trades {len(trades)}")
    print(f"  Win rate              {len(wins)/len(tp)*100:.0f}%   profit factor {pf:.2f}   "
          f"avg win ${wins.mean() if len(wins) else 0:+,.0f} / avg loss ${losses.mean() if len(losses) else 0:+,.0f}")
    print(f"\n  Per rebalance:")
    print(f"  {'entry':>10} {'pos':>4} {'invested':>11} {'P&L':>10} {'ret':>7} {'equity':>12}")
    for d, n, inv, chg, eq, ret in reb_rows:
        print(f"  {d:>10} {n:>4} ${inv:>10,.0f} ${chg:>+9,.0f} {ret:>+6.1f}% ${eq:>11,.0f}")
    big = sorted(trades, key=lambda r: r[5])
    print(f"\n  Top winners: " + ", ".join(f"{t[2]}({t[3]}sh ${t[5]:+,.0f})" for t in big[-5:][::-1]))
    print(f"  Top losers:  " + ", ".join(f"{t[2]}({t[3]}sh ${t[5]:+,.0f})" for t in big[:5]))
    # HTML
    from trading.lab.experiments.harness.portfolio_sim import _svg_equity  # reuse the SVG drawer
    def trrows(ts):
        return "".join(f"<tr><td>{html.escape(t[0])}</td><td>{html.escape(t[1])}</td><td>{html.escape(t[2])}</td>"
                       f"<td>{t[3]}</td><td>${t[4]:,.0f}</td><td style='color:{'#0a0' if t[5]>=0 else '#c00'}'>"
                       f"${t[5]:+,.0f}</td><td>{t[6]:+.1f}%</td></tr>" for t in ts)
    rebhtml = "".join(f"<tr><td>{d}</td><td>{n}</td><td>${inv:,.0f}</td>"
                      f"<td style='color:{'#0a0' if chg>=0 else '#c00'}'>${chg:+,.0f}</td><td>{ret:+.1f}%</td>"
                      f"<td><b>${eq:,.0f}</b></td></tr>" for d, n, inv, chg, eq, ret in reb_rows)
    out = Path(a.out)
    out.write_text(f"""<!doctype html><meta charset=utf8><title>Portfolio sim {a.release}</title>
<style>body{{font:14px system-ui;margin:24px;color:#222}}table{{border-collapse:collapse;margin:8px 0;font-size:13px}}
td,th{{border:1px solid #ddd;padding:3px 8px;text-align:right}}td:first-child,td:nth-child(2),td:nth-child(3){{text-align:left}}h2{{margin-top:22px}}</style>
<h1>{html.escape(a.release)} — ${a.capital:,.0f} portfolio, {a.start}→{a.end}</h1>
<p><b>${a.capital:,.0f} → ${equity:,.0f}</b> ({tot*100:+.1f}%, CAGR {cagr*100:+.1f}%/yr, max DD {maxdd*100:.1f}%,
Sharpe {sharpe:+.2f}, {len(reb_rows)} rebalances, {len(trades)} trades, win {len(wins)/len(tp)*100:.0f}%, {a.cost_bps:.0f}bps)</p>
{_svg_equity(curve)}
<h2>Per rebalance</h2><table><tr><th>entry</th><th>pos</th><th>invested</th><th>P&amp;L</th><th>return</th><th>equity</th></tr>{rebhtml}</table>
<h2>Top winners</h2><table><tr><th>entry</th><th>exit</th><th>ticker</th><th>sh</th><th>$ in</th><th>$ P&amp;L</th><th>%</th></tr>{trrows(big[-15:][::-1])}</table>
<h2>Top losers</h2><table><tr><th>entry</th><th>exit</th><th>ticker</th><th>sh</th><th>$ in</th><th>$ P&amp;L</th><th>%</th></tr>{trrows(big[:15])}</table>
<h2>All trades</h2><table><tr><th>entry</th><th>exit</th><th>ticker</th><th>sh</th><th>$ in</th><th>$ P&amp;L</th><th>%</th></tr>{trrows(sorted(trades,key=lambda r:(r[0],r[2])))}</table>
""")
    print(f"\n  HTML report → {out}   (open it: open {out})")


if __name__ == "__main__":
    main()
