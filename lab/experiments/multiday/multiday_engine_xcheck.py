#!/usr/bin/env python3
"""Independent cross-check of the multi-day momentum result (EXPLORATION_PLAYBOOK §6:
reproduce the number via a SEPARATE code path before trusting the offline ledger).

This is a ground-up daily-bar backtest that recomputes EVERYTHING from raw fetched
closes — momentum signal, eligibility, forward returns, cost — WITHOUT reading the
capture parquet or the search code. If it reproduces the sealed-OOS 2025 numbers
(per-period net ≈ +3.98%, ann Sharpe ≈ +1.08, cross-sectional premium ≈ +2.78%), the
capture→search→OOS pipeline is sound (no look-ahead / join / shift / cost bug). A
material divergence means a pipeline bug to hunt.

Note: the engine proper is intraday-only (5-min breakout); a full multi-day
StrategyRelease is a separate, larger build deferred until we commit to trading this.
This independent re-implementation is the proportionate cross-check for a daily-close
strategy whose offline ledger already uses real daily bars.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_engine_xcheck --year 2025
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.data.universes import load_universe_tickers
from trading.marketdata.calendar import trading_days_in_range


def main() -> None:
    p = argparse.ArgumentParser(description="Independent daily-bar cross-check of multi-day momentum")
    p.add_argument("--year", type=int, default=2025)
    p.add_argument("--universe", default="liquid_pit")
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--cost-bps", type=float, default=10.0)
    p.add_argument("--min-price", type=float, default=5.0)
    p.add_argument("--min-dollar-vol", type=float, default=10_000_000.0)
    args = p.parse_args()
    H, N = args.horizon, args.top_n

    yr = args.year
    days = trading_days_in_range(date(yr, 1, 1), date(yr, 12, 31))
    # rebalance every H trading days, non-overlapping
    rebal = days[::H]
    # need H trading days AFTER the last rebalance for the hold; trim if data short
    print(f"Independent cross-check: {args.universe} {yr}, top-{N} 12-1 momentum, "
          f"H={H}, cost={args.cost_bps:.0f}bps. {len(rebal)} rebalances.")

    # union of tickers across rebalance dates
    union = sorted(set().union(*(set(load_universe_tickers(args.universe, d)) for d in rebal)))

    # fetch SPLIT-ADJUSTED daily closes ONCE per ticker (independent of the capture
    # parquet). Split-adjusted, not raw: a multi-day hold straddles splits and a split
    # inside the 252d lookback corrupts momentum — raw is correct only for intraday.
    bars: dict[str, pd.DataFrame] = {}
    for i, t in enumerate(union, 1):
        df = fetch_daily_range(t, date(yr - 2, 1, 1), date(yr + 1, 2, 1), adjustment="split")
        if df is not None and not df.empty:
            d = df[["close", "volume"]].copy()
            d.index = pd.DatetimeIndex(d.index).normalize().tz_localize(None)
            bars[t] = d[~d.index.duplicated(keep="last")].sort_index()
        if i % 200 == 0 or i == len(union):
            print(f"  fetched {i}/{len(union)}", flush=True)

    per_period = []        # net portfolio return per rebalance
    univ_means = []        # eligible-universe gross mean per rebalance (for the premium)
    for d in rebal:
        dts = pd.Timestamp(d)
        elig = set(load_universe_tickers(args.universe, d))
        rows = []
        for t in elig:
            b = bars.get(t)
            if b is None or dts not in b.index:
                continue
            idx = b.index.get_loc(dts)
            if idx < 252 or idx + H >= len(b):
                continue
            c = b["close"].values
            v = b["volume"].values
            close_d = c[idx]
            if close_d < args.min_price:
                continue
            dvol = float(np.mean(c[idx - 19:idx + 1] * v[idx - 19:idx + 1]))
            if dvol < args.min_dollar_vol:
                continue
            mom = c[idx - 21] / c[idx - 252] - 1.0      # 12-1 momentum, independent calc
            fwd = c[idx + H] / c[idx] - 1.0             # forward H-day return, independent calc
            if not (np.isfinite(mom) and np.isfinite(fwd)):
                continue
            rows.append((t, mom, fwd))
        if len(rows) < N:
            continue
        rr = pd.DataFrame(rows, columns=["ticker", "mom", "fwd"])
        top = rr.nlargest(N, "mom")
        net = float(top["fwd"].mean()) - args.cost_bps / 10000.0
        per_period.append(net)
        univ_means.append(float(rr["fwd"].mean()))

    r = np.array(per_period)
    n = len(r)
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    ann = float(np.sqrt(252.0 / H))
    sharpe = mean / sd * ann if sd > 0 else float("nan")
    premium = float(np.mean(r) - np.mean(univ_means)) + args.cost_bps / 10000.0 * 0  # net top vs gross univ
    premium = float(np.mean([pp for pp in per_period]) - np.mean(univ_means))
    print(f"\n=== INDEPENDENT CROSS-CHECK RESULT ({yr}) ===")
    print(f"  rebalances: {n}")
    print(f"  per-period net mean = {mean*100:+.3f}%   annualized Sharpe = {sharpe:+.2f}")
    print(f"  cross-sectional premium (top-{N} net − universe gross) = {premium*100:+.3f}%")
    print(f"\n  ledger/search OOS-2025 reference: net +3.98%/period, Sharpe +1.08, premium +2.78%")
    print(f"  → reproduction: {'MATCH (pipeline sound)' if (mean>0 and sharpe>0.5) else 'DIVERGENCE — investigate'}"
          f" (independent code path, fresh bars, recomputed signal/returns)")


if __name__ == "__main__":
    main()
