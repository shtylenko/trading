"""Run all daily short-hold strategies over the shared cached panel.

Loads the panel + market context ONCE, evaluates each strategy (and variant),
truncates to the eval window, writes per-strategy trades and a combined metrics
table under outputs/_summary/.

    python3 -m trading.strategytester.scripts.run_daily_strategies [--only NAME]
"""

from __future__ import annotations

import argparse
import importlib
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from trading.strategytester.common.engine import run_strategy
from trading.strategytester.common.metrics import summarize
from trading.strategytester.common.panel import build_panel, CACHE_DIR
from trading.strategytester.common.universe import union_tickers

logger = logging.getLogger("strategytester.run_daily")

CACHE_KEY = "liquid_2022_2025"
START = date(2022, 1, 1)
END = date(2025, 12, 31)
EVAL_START = date(2022, 1, 1)

MODULES = [
    "inside_bar", "momentum_burst", "bb_squeeze", "macd_31016", "ttm_squeeze",
    "overnight_hold", "episodic_pivot", "sr_bounce", "fib_pullback",
    "avwap_pullback", "contrarian",
]

OUT = Path(__file__).resolve().parent.parent / "outputs"


def _variants(mod):
    if hasattr(mod, "VARIANTS"):
        return [(v["name"], v["signals"], v.get("max_hold", 3), v.get("cost_bps", 5.0)) for v in mod.VARIANTS]
    return [(mod.NAME, mod.signals, getattr(mod, "MAX_HOLD", 3), getattr(mod, "COST_BPS", 5.0))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="run a single module by name")
    ap.add_argument("--cost-bps", type=float, default=None, help="override per-side cost (bps)")
    ap.add_argument("--max-hold", type=int, default=None, help="override hold-session cap for all variants")
    ap.add_argument("--tag", default="", help="suffix for the summary output file")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    uni = union_tickers("liquid_pit", START, END)
    panel = build_panel(uni, START, END, cache_key=CACHE_KEY, warmup_days=500)
    ctx = pd.read_parquet(CACHE_DIR / "market_context.parquet")
    print(f"panel: {len(panel)} tickers | ctx: {len(ctx)} rows")

    mods = [m for m in MODULES if (args.only is None or m == args.only)]
    rows = []
    for name in mods:
        mod = importlib.import_module(f"trading.strategytester.{name}.signals")
        for vname, sfn, max_hold, cost_bps in _variants(mod):
            if args.cost_bps is not None:
                cost_bps = args.cost_bps
            if args.max_hold is not None:
                max_hold = args.max_hold
            trades = run_strategy(panel, sfn, max_hold=max_hold, cost_bps=cost_bps, ctx=ctx)
            if not trades.empty:
                trades = trades[(pd.to_datetime(trades["entry_date"]).dt.date >= EVAL_START)
                                & (pd.to_datetime(trades["entry_date"]).dt.date <= END)]
            (OUT / name).mkdir(parents=True, exist_ok=True)
            trades.to_parquet(OUT / name / f"trades_{vname}{args.tag}.parquet", index=False)
            m = summarize(vname, trades, horizon="daily")
            m["module"] = name
            rows.append(m)
            print(f"  {vname:22s} n={m.get('n_trades',0):6d} "
                  f"win={m.get('win_rate',0):.2f} exp%={m.get('avg_ret_net',0)*100:+.3f} "
                  f"PF={m.get('profit_factor',0):.3f} t={m.get('t_stat','na'):>6} "
                  f"shpe={m.get('ann_sharpe','na'):>6} CAGR={m.get('cagr','na'):>7} "
                  f"DD={m.get('max_dd','na'):>7} fill={m.get('fill_rate','na')}")

    summ = pd.DataFrame(rows)
    outdir = OUT / "_summary"
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"daily_metrics{args.tag}"
    summ.to_parquet(outdir / f"{stem}.parquet", index=False)
    summ.to_csv(outdir / f"{stem}.csv", index=False)
    print(f"\nwrote {outdir/(stem+'.csv')} ({len(summ)} rows)")


if __name__ == "__main__":
    main()
