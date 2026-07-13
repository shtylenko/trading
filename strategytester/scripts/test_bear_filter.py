"""Test stronger bear-market regime filters for Momentum Burst @5d.

Goal: a filter that (a) removes the 2022 bear loss, (b) preserves the 2023-25
edge, (c) improves the $10k account outcome. Reports per-year expectancy per
regime, then a $10k Monte-Carlo (over trade selection) for baseline vs winner.

    python3 -m trading.strategytester.scripts.test_bear_filter
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.strategytester.common.engine import run_strategy
from trading.strategytester.common.metrics import trade_metrics
from trading.strategytester.common.panel import build_panel, CACHE_DIR
from trading.strategytester.common.universe import union_tickers
from trading.strategytester.momentum_burst.signals import make_signals

START, END = date(2022, 1, 1), date(2025, 12, 31)
HOLD = 5


def _exp(t, y0=None, y1=None):
    if y0:
        t = t[(pd.to_datetime(t["entry_date"]).dt.year >= y0) & (pd.to_datetime(t["entry_date"]).dt.year <= y1)]
    if t.empty:
        return (0, np.nan, np.nan)
    m = trade_metrics(t)
    return (m["n_trades"], round(m["avg_ret_net"] * 1e4, 1), m["t_stat_day"])


def mc10k(t, N=10, trials=200, start=10000.0, seed=1):
    rng = np.random.default_rng(seed)
    t = t.copy(); t["entry_date"] = pd.to_datetime(t["entry_date"]); t["exit_date"] = pd.to_datetime(t["exit_date"])
    dates = sorted(set(t["entry_date"]).union(t["exit_date"]))
    grp = {d: list(zip(g["exit_date"], g["pnl_pct"])) for d, g in t.groupby("entry_date")}
    fins = []; y22 = []; dds = []
    for _ in range(trials):
        free = start; op = []; yp = {}; peak = start; mdd = 0.0
        for d in dates:
            keep = []
            for p in op:
                if p[0] == d:
                    free += p[1] * (1 + p[2]); yp[d.year] = yp.get(d.year, 0) + p[1] * p[2]
                else:
                    keep.append(p)
            op = keep
            if d in grp:
                sig = grp[d][:]; rng.shuffle(sig)
                for ex, pnl in sig:
                    if len(op) >= N:
                        break
                    eq = free + sum(p[1] for p in op); alloc = min(eq / N, free)
                    if alloc <= 1e-9:
                        break
                    free -= alloc
                    if ex == d:
                        free += alloc * (1 + pnl); yp[d.year] = yp.get(d.year, 0) + alloc * pnl
                    else:
                        op.append((ex, alloc, pnl))
            eq = free + sum(p[1] for p in op); peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
        fins.append(free + sum(p[1] for p in op)); y22.append(yp.get(2022, 0)); dds.append(mdd)
    fins = np.array(fins)
    return dict(med=np.median(fins), p10=np.percentile(fins, 10), p90=np.percentile(fins, 90),
                y22=np.median(y22), mdd=np.median(dds))


def main() -> None:
    uni = union_tickers("liquid_pit", START, END)
    panel = build_panel(uni, START, END, cache_key="liquid_2022_2025", warmup_days=500)
    ctx = pd.read_parquet(CACHE_DIR / "market_context.parquet")

    # breadth from the cached panel: fraction of names with close>sma50 each day
    long = pd.read_parquet(CACHE_DIR / "liquid_2022_2025.parquet")
    br = long.assign(above=(long["close"] > long["sma50"])).groupby("date")["above"].mean()
    ctx["breadth_ok"] = (br.reindex(ctx.index) > 0.5).fillna(False)
    ctx["reg_bull_breadth"] = ctx["spy_bull"] & ctx["breadth_ok"]

    regimes = [
        ("none (no filter)", dict(require_regime=False)),
        ("spy_bull (baseline)", dict(regime_col="spy_bull")),
        ("spy>200sma", dict(regime_col="spy_above_200")),
        ("bull & spy>200", dict(regime_col="reg_bull_200")),
        ("bull & 50>200", dict(regime_col="reg_50_200")),
        ("bull & not-deep-dd", dict(regime_col="reg_dd_bull")),
        ("bull & vix<25", dict(regime_col="reg_bull_vix25")),
        ("bull & breadth>50%", dict(regime_col="reg_bull_breadth")),
    ]

    print("=" * 96)
    print("MOMENTUM BURST @5d — regime filter comparison (exp bps/trade, day-t) @10bps/side")
    print(f"{'regime':22s} {'n':>6s} {'full':>7s} {'day-t':>6s} | {'2022':>7s} {'2023':>7s} {'2024':>7s} {'2025':>7s}")
    results = {}
    for name, ov in regimes:
        tr = run_strategy(panel, make_signals(**ov), max_hold=HOLD, cost_bps=10.0, ctx=ctx)
        tr = tr[(pd.to_datetime(tr["entry_date"]).dt.date >= START) & (pd.to_datetime(tr["entry_date"]).dt.date <= END)]
        results[name] = tr
        n, fe, ft = _exp(tr)
        y = {yr: _exp(tr, yr, yr)[1] for yr in (2022, 2023, 2024, 2025)}
        print(f"{name:22s} {n:6d} {fe:+7.1f} {ft:+6.2f} | {y[2022]:+7.1f} {y[2023]:+7.1f} {y[2024]:+7.1f} {y[2025]:+7.1f}")

    print("\n" + "=" * 96)
    print("$10k ACCOUNT (10 positions, 200 random paths, 10bps): baseline vs best bear filters")
    for name in ["spy_bull (baseline)", "spy>200sma", "bull & spy>200", "bull & vix<25", "bull & breadth>50%"]:
        m = mc10k(results[name])
        print(f"  {name:22s} end-2025 median ${m['med']:,.0f} [{m['p10']:,.0f}..{m['p90']:,.0f}]  "
              f"2022 median ${m['y22']:+,.0f}  med maxDD {m['mdd']*100:+.0f}%")


if __name__ == "__main__":
    main()
