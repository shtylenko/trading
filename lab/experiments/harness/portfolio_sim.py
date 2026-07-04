#!/usr/bin/env python3
"""Portfolio simulation for a swing run — turn the per-name backtest trades into a
REAL $-denominated portfolio: start with --capital, equal-weight the top-N names each
rebalance with WHOLE shares, charge cost, compound equity sequentially (the strategy is
non-overlapping: deploy → hold 20d → liquidate → redeploy). Writes an HTML report
(equity curve + per-rebalance table + sample trade ledger) and prints a text summary.

Usage:
    python3 -m trading.lab.experiments.harness.portfolio_sim \
        --run run_x03_momentum_swing_2024_... --capital 100000 --cost-bps 10
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DB = PROJECT_ROOT / "engine/strategy_lab/storage/strategy_lab.duckdb"


def _svg_equity(points, w=900, h=300, pad=45):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    ylo, yhi = min(ys), max(ys)
    yr = (yhi - ylo) or 1.0
    def px(i): return pad + (w - 2 * pad) * i / (len(points) - 1)
    def py(v): return pad + (h - 2 * pad) * (1 - (v - ylo) / yr)
    poly = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, (_, v) in enumerate(points))
    grid = ""
    for f in (0, .25, .5, .75, 1):
        val = ylo + yr * f; yy = py(val)
        grid += (f'<line x1="{pad}" y1="{yy:.1f}" x2="{w-pad}" y2="{yy:.1f}" stroke="#eee"/>'
                 f'<text x="6" y="{yy+4:.1f}" font-size="11" fill="#888">${val:,.0f}</text>')
    base = py(points[0][1])
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px">'
            f'{grid}<line x1="{pad}" y1="{base:.1f}" x2="{w-pad}" y2="{base:.1f}" '
            f'stroke="#bbb" stroke-dasharray="4"/>'
            f'<polyline fill="none" stroke="#2b7" stroke-width="2" points="{poly}"/>'
            f'<text x="{pad}" y="{h-12}" font-size="11" fill="#888">{points[0][0]}</text>'
            f'<text x="{w-pad-70}" y="{h-12}" font-size="11" fill="#888">{points[-1][0]}</text></svg>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--capital", type=float, default=100_000.0)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--out", default=str(PROJECT_ROOT / "engine/strategy_lab/portfolio_sim.html"))
    a = ap.parse_args()
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute(
        """SELECT s.trade_date d, t.ticker, t.entry_price, t.exit_price, t.exit_time
           FROM trades t JOIN sessions s ON t.session_id=s.session_id
           WHERE t.run_id=? AND t.entry_price>0 ORDER BY s.trade_date, t.ticker""", [a.run]).fetchall()
    if not rows:
        print("no trades for run", a.run); return
    # group by rebalance date
    from itertools import groupby
    sessions = [(d, list(g)) for d, g in groupby(rows, key=lambda r: r[0])]
    def _ds(x):
        return x.date().isoformat() if hasattr(x, "date") else str(x)
    cost = a.cost_bps / 10000.0
    equity = a.capital
    curve = [(_ds(sessions[0][0]), equity)]
    reb_rows, all_trades, peak, maxdd = [], [], equity, 0.0
    for d, names in sessions:
        n = len(names)
        alloc = equity / n
        invested = pnl = 0.0
        for _, tk, ep, xp, xt in names:
            sh = int(alloc // ep)
            if sh <= 0:
                continue
            notional = sh * ep
            tcost = notional * cost + sh * xp * cost
            tpnl = sh * (xp - ep) - tcost
            invested += notional; pnl += tpnl
            all_trades.append((_ds(d), tk, sh, notional, tpnl, (xp / ep - 1) * 100))
        equity += pnl
        peak = max(peak, equity); maxdd = min(maxdd, equity / peak - 1)
        xdate = names[0][4]
        reb_rows.append((_ds(d), n, invested, equity - (curve[-1][1]), equity, pnl / (curve[-1][1]) * 100))
        curve.append((str(xdate.date()) if xdate else _ds(d), equity))
    tot = equity / a.capital - 1
    span_yrs = (sessions[-1][0] - sessions[0][0]).days / 365.25 + 20 / 252
    cagr = (equity / a.capital) ** (1 / max(span_yrs, 1e-9)) - 1
    # text summary
    print(f"\nPORTFOLIO SIM — {a.run}")
    print(f"  start ${a.capital:,.0f} → end ${equity:,.0f}  ({tot*100:+.1f}%, CAGR {cagr*100:+.1f}%/yr over {span_yrs:.2f}y)")
    print(f"  rebalances {len(sessions)}, ~{names and len(sessions[0][1])} names each, cost {a.cost_bps:.0f}bps, max drawdown {maxdd*100:.1f}%")
    print(f"  per-rebalance:")
    for d, n, inv, chg, eq, ret in reb_rows:
        print(f"    {d}  {n:>3} pos  invested ${inv:>9,.0f}  P&L ${chg:>+8,.0f} ({ret:>+5.1f}%)  equity ${eq:>10,.0f}")
    big = sorted(all_trades, key=lambda r: r[4])
    print("  biggest winners:", [(t[1], f"{t[2]}sh", f"${t[4]:+,.0f}") for t in big[-3:][::-1]])
    print("  biggest losers: ", [(t[1], f"{t[2]}sh", f"${t[4]:+,.0f}") for t in big[:3]])
    # html
    def tr_rows(ts):
        return "".join(f"<tr><td>{html.escape(t[0])}</td><td>{html.escape(t[1])}</td><td>{t[2]}</td>"
                       f"<td>${t[3]:,.0f}</td><td style='color:{'#0a0' if t[4]>=0 else '#c00'}'>${t[4]:+,.0f}</td>"
                       f"<td>{t[5]:+.1f}%</td></tr>" for t in ts)
    reb_html = "".join(f"<tr><td>{d}</td><td>{n}</td><td>${inv:,.0f}</td>"
                       f"<td style='color:{'#0a0' if chg>=0 else '#c00'}'>${chg:+,.0f}</td>"
                       f"<td>{ret:+.1f}%</td><td><b>${eq:,.0f}</b></td></tr>"
                       for d, n, inv, chg, eq, ret in reb_rows)
    out = Path(a.out)
    out.write_text(f"""<!doctype html><meta charset=utf8><title>Portfolio sim {a.run}</title>
<style>body{{font:14px system-ui;margin:24px;color:#222}}table{{border-collapse:collapse;margin:8px 0}}
td,th{{border:1px solid #ddd;padding:3px 8px;text-align:right}}td:first-child,td:nth-child(2){{text-align:left}}
h2{{margin-top:24px}}</style>
<h1>Portfolio simulation — {html.escape(a.run)}</h1>
<p><b>${a.capital:,.0f}</b> → <b>${equity:,.0f}</b> &nbsp; ({tot*100:+.1f}%, CAGR {cagr*100:+.1f}%/yr,
max drawdown {maxdd*100:.1f}%, {len(sessions)} rebalances, {a.cost_bps:.0f}bps cost, whole shares)</p>
{_svg_equity(curve)}
<h2>Per rebalance</h2><table><tr><th>date</th><th>positions</th><th>invested</th><th>P&amp;L</th><th>return</th><th>equity</th></tr>{reb_html}</table>
<h2>Biggest winners</h2><table><tr><th>date</th><th>ticker</th><th>shares</th><th>$ invested</th><th>$ P&amp;L</th><th>%</th></tr>{tr_rows(big[-10:][::-1])}</table>
<h2>Biggest losers</h2><table><tr><th>date</th><th>ticker</th><th>shares</th><th>$ invested</th><th>$ P&amp;L</th><th>%</th></tr>{tr_rows(big[:10])}</table>
""")
    print(f"\n  HTML report → {out}")


if __name__ == "__main__":
    main()
