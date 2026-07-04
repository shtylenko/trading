#!/usr/bin/env python3
"""Stage-0 triage for the MULTI-DAY SWING (long-only) pivot — does a cross-sectional
momentum signal predict forward H-day returns on our universe? Offline, daily bars,
NO engine change (same approach as the overnight Stage-0). See
validation/STRATEGY_SYNTHESIS.md §4 for why this is the recommended next bet.

Method (leak-safe, honest about overlap):
  - Per name-day, compute close-knowable signals and FORWARD H-day labels
    fwd = close(d+H)/close(d) − 1.
  - Rebalance every H trading days (NON-OVERLAPPING) so the H-day return periods are
    independent → the annualized Sharpe isn't inflated by overlap.
  - Each rebalance date: rank the PIT universe cross-sectionally into deciles by the
    signal; report pooled mean forward return per decile, the tradeable TOP-decile
    long-only series, and the D10−D1 spread (the long/short potential, for later).
  - Search years 2022–2024 only; 2025 stays sealed for a future confirmatory test.

Signals (all from daily bars, known at close d):
  - mom_12_1 : close(d−21)/close(d−252)−1   (12-month return skipping last month;
               the classic cross-sectional momentum, avoids 1-month reversal)
  - mom_6_1  : close(d−21)/close(d−126)−1   (6-month, skip last month)
  - prox_52w : close(d)/max(high, 252d)     (George–Hwang 52-week-high proximity)
  - rev_1m   : close(d)/close(d−21)−1       (1-month return; expect NEGATIVE predictive
               = short-term reversal — a direction/sanity check)

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_momentum_triage \
        --universe liquid_pit --start 2022-01-01 --end 2024-12-31 --horizons 5 20
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.data.universes import load_universe_tickers
from trading.marketdata.calendar import trading_days_in_range

MIN_PRICE = 5.0
MIN_DOLLAR_VOL = 10_000_000.0   # liquidity floor (cost-bearing names)


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _panel(universe: str, start: date, end: date, horizons: list[int]) -> pd.DataFrame:
    """Long panel (date, ticker, signals, fwd_H, eligible) over the universe union."""
    days = trading_days_in_range(start, end)
    by_day = {d: set(load_universe_tickers(universe, d)) for d in days}
    union = sorted(set().union(*by_day.values()))
    print(f"Universe {universe}: {len(days)} days {days[0]}..{days[-1]}, "
          f"{len(union)} tickers (union).")

    parts = []
    maxh = max(horizons)
    for i, t in enumerate(union, 1):
        df = fetch_daily_range(t, start - timedelta(days=430), end + timedelta(days=int(maxh * 1.6) + 10))
        if df is None or df.empty:
            continue
        df = df[["high", "close", "volume"]].copy()
        df.index = pd.DatetimeIndex(df.index).normalize().tz_localize(None)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        c, h, v = df["close"], df["high"], df["volume"]
        out = pd.DataFrame(index=df.index)
        out["close"] = c
        out["mom_12_1"] = c.shift(21) / c.shift(252) - 1.0
        out["mom_6_1"] = c.shift(21) / c.shift(126) - 1.0
        out["prox_52w"] = c / h.rolling(252).max()
        out["rev_1m"] = c / c.shift(21) - 1.0
        out["dollar_vol_20d"] = (c * v).rolling(20).mean()
        for H in horizons:
            out[f"fwd_{H}"] = c.shift(-H) / c - 1.0
        out["ticker"] = t
        parts.append(out.reset_index().rename(columns={"index": "date", "timestamp": "date"}))
        if i % 200 == 0 or i == len(union):
            print(f"  panel {i}/{len(union)} tickers", flush=True)
    panel = pd.concat(parts, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    # eligibility (leak-safe, at close d): in PIT universe that day + price/liquidity
    day_index = {pd.Timestamp(d): s for d, s in by_day.items()}
    panel["in_univ"] = [t in day_index.get(d, ()) for d, t in zip(panel["date"], panel["ticker"])]
    panel["eligible"] = (panel["in_univ"] & (panel["close"] >= MIN_PRICE)
                         & (panel["dollar_vol_20d"] >= MIN_DOLLAR_VOL))
    return panel


def _decile_report(panel: pd.DataFrame, signal: str, H: int, rebal_days: list[pd.Timestamp]) -> None:
    fwd = f"fwd_{H}"
    sub = panel[panel["date"].isin(rebal_days) & panel["eligible"]].copy()
    sub = sub.dropna(subset=[signal, fwd])
    # cross-sectional deciles per rebalance date
    sub["dec"] = sub.groupby("date")[signal].transform(
        lambda s: pd.qcut(s, 10, labels=False, duplicates="drop") if s.nunique() >= 10 else np.nan)
    sub = sub.dropna(subset=["dec"])
    dec_mean = sub.groupby("dec")[fwd].mean() * 100  # mean H-day fwd return per decile (%)
    # top-decile long-only portfolio series (equal weight per rebalance) → honest Sharpe
    top = sub[sub["dec"] == 9].groupby("date")[fwd].mean()
    bot = sub[sub["dec"] == 0].groupby("date")[fwd].mean()
    ppy = 252.0 / H
    def sh(s):
        return (s.mean() / s.std(ddof=1) * np.sqrt(ppy)) if (len(s) > 1 and s.std(ddof=1) > 0) else float("nan")
    ls = (top - bot).dropna()
    # monotonicity: Spearman of decile index vs mean fwd
    mono = pd.Series(dec_mean.values).corr(pd.Series(dec_mean.index, dtype=float), method="spearman")
    print(f"\n  signal={signal}  H={H}d  ({len(top)} non-overlapping rebalances)")
    print("    decile mean fwd% : " + " ".join(f"{dec_mean.get(d, float('nan')):+.2f}" for d in range(10)))
    print(f"    monotonicity (decile rank vs fwd, Spearman) = {mono:+.2f}")
    print(f"    TOP decile (long-only): mean {top.mean()*100:+.2f}%/period  ann.Sharpe {sh(top):+.2f}  "
          f"hit {100*(top>0).mean():.0f}%")
    print(f"    D10-D1 spread (long/short potential): mean {ls.mean()*100:+.2f}%/period  ann.Sharpe {sh(ls):+.2f}")
    by = top.groupby(top.index.year).mean() * 100
    print(f"    TOP decile by year (%/period): " + "  ".join(f"{y}:{v:+.2f}" for y, v in by.items()))


def main() -> None:
    p = argparse.ArgumentParser(description="Stage-0 multi-day momentum triage (offline)")
    p.add_argument("--universe", default="liquid_pit")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2024-12-31", help="search years only; keep 2025 sealed")
    p.add_argument("--horizons", type=int, nargs="+", default=[5, 20])
    p.add_argument("--signals", nargs="+", default=["mom_12_1", "mom_6_1", "prox_52w", "rev_1m"])
    args = p.parse_args()

    panel = _panel(args.universe, _parse(args.start), _parse(args.end), args.horizons)
    all_days = sorted(panel.loc[panel["eligible"], "date"].unique())
    print(f"\nEligible name-days: {int(panel['eligible'].sum()):,} over {len(all_days)} dates.")
    print("Triage = cross-sectional decile of forward H-day return, NON-overlapping "
          "rebalance (honest Sharpe). Gross; multi-day turnover is low so cost is small "
          "vs H-day moves. 2025 sealed.")
    for H in args.horizons:
        rebal = [pd.Timestamp(d) for d in all_days[::H]]  # every H trading days
        print(f"\n{'='*70}\nHORIZON H={H} trading days — {len(rebal)} rebalances\n{'='*70}")
        for sig in args.signals:
            _decile_report(panel, sig, H, rebal)


if __name__ == "__main__":
    main()
