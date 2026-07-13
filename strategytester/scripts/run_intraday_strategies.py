"""Run intraday strategies (VWAP Bounce, Gap and Go) on 1-min bars.

Universe: cached_1min_2024_pit (liquid names with cached 1-min); window 2024.

    python3 -m trading.strategytester.scripts.run_intraday_strategies [--only NAME] [--limit N]
"""

from __future__ import annotations

import argparse
import importlib
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from trading.strategytester.common.intraday import run_intraday
from trading.strategytester.common.metrics import summarize
from trading.strategytester.common.universe import latest_tickers

logger = logging.getLogger("strategytester.run_intraday")

START = date(2024, 1, 1)
END = date(2024, 12, 31)
MODULES = ["vwap_bounce", "gap_and_go"]
OUT = Path(__file__).resolve().parent.parent / "outputs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cost-bps", type=float, default=5.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    tickers = latest_tickers("cached_1min_2024_pit")
    if args.limit:
        tickers = tickers[: args.limit]
    print(f"intraday universe: {len(tickers)} tickers, {START}..{END}, cost={args.cost_bps}bps/side")

    mods = [m for m in MODULES if (args.only is None or m == args.only)]
    rows = []
    for name in mods:
        mod = importlib.import_module(f"trading.strategytester.{name}.signals")
        all_trades = []
        for j, tk in enumerate(tickers, 1):
            try:
                tr = run_intraday(tk, mod.day_fn, START, END,
                                  cost_bps=args.cost_bps, need_prevclose=mod.NEED_PREVCLOSE)
            except Exception as e:  # noqa: BLE001
                logger.warning("intraday fail %s %s: %s", name, tk, e)
                tr = []
            all_trades.extend(tr)
            if j % 100 == 0:
                print(f"    {name}: {j}/{len(tickers)} ({len(all_trades)} trades)")
        trades = pd.DataFrame(all_trades)
        if not trades.empty:
            trades = trades.sort_values(["entry_date", "ticker"]).reset_index(drop=True)
        (OUT / name).mkdir(parents=True, exist_ok=True)
        trades.to_parquet(OUT / name / f"trades_{name}.parquet", index=False)
        m = summarize(name, trades, horizon="intraday")
        m["module"] = name
        rows.append(m)
        print(f"  {name:14s} n={m.get('n_trades',0):6d} win={m.get('win_rate',0):.2f} "
              f"exp%={m.get('avg_ret_net',0)*100:+.3f} PF={m.get('profit_factor',0):.3f} "
              f"t={m.get('t_stat','na')} shpe={m.get('ann_sharpe','na')} "
              f"CAGR={m.get('cagr','na')} DD={m.get('max_dd','na')}")

    summ = pd.DataFrame(rows)
    outdir = OUT / "_summary"
    outdir.mkdir(parents=True, exist_ok=True)
    summ.to_parquet(outdir / "intraday_metrics.parquet", index=False)
    summ.to_csv(outdir / "intraday_metrics.csv", index=False)
    print(f"\nwrote {outdir/'intraday_metrics.csv'}")


if __name__ == "__main__":
    main()
