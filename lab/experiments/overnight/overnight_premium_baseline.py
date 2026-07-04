#!/usr/bin/env python3
"""Stage-0 baseline for the OVERNIGHT-PREMIUM idea (relax flat-overnight).

The premise (decades of equity research): ~all of the long-run equity risk
premium accrues CLOSE-TO-OPEN (overnight), not intraday — the exact window the
strategy_lab mold currently skips. Before any engine work to support overnight
holds, measure the bare premium OFFLINE on daily bars: buy every universe name at
the close, sell at the next open, equal-weight. Honest baseline, no engine change.

This is Stage-0 triage per validation/EXPLORATION_PLAYBOOK.md §1b: is there a
there there? It does NOT decide promotion — that needs the full capture → search →
WF → PBO → DSR → sealed pipeline, and finally an overnight-hold engine cross-check.

Method:
  - overnight_return(t) = open(t+1) / close(t) − 1, raw (unadjusted) prices.
  - PIT membership: a name contributes night t only if it is in the universe as
    of day t (the night you decide to hold).
  - Split/glitch guard: drop |overnight_return| > --split-threshold (raw prices
    make an overnight split look like a huge phantom move). Count + report drops.
  - Equal-weight nightly portfolio: each night's return = mean over that night's
    names. Report sum, mean/night, annualized Sharpe, by year and quarter, plus
    the per-name-day mean and hit rate.

Survivorship note (direction matters): liquid_pit is built from currently-active
symbols, so pre-2024 it MISSES since-delisted names. For a LONG overnight strategy
that is OPTIMISTIC (skips names that went to zero) → a NEGATIVE baseline is safe,
a POSITIVE one must be re-checked on a delisting-inclusive universe. etf_liquid_pit
is ~unbiased (ETF closures in this liquid set are rare).

Usage:
    python3 -m trading.lab.experiments.overnight.overnight_premium_baseline \
        --universe liquid_pit --start 2022-01-01 --end 2025-12-31
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.data.universes import load_universe_tickers
from trading.marketdata.calendar import trading_days_in_range

ANN = float(np.sqrt(252))


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _membership(universe: str, days: list[date]) -> dict[date, set[str]]:
    """PIT ticker set per trading day, and the union to fetch."""
    by_day: dict[date, set[str]] = {}
    for d in days:
        by_day[d] = set(load_universe_tickers(universe, d))
    return by_day


def _daily_bars(tickers: set[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """One ranged daily fetch per ticker → {ticker: df indexed by date with open/close}."""
    out: dict[str, pd.DataFrame] = {}
    tickers = sorted(tickers)
    for i, t in enumerate(tickers, 1):
        try:
            df = fetch_daily_range(t, start, end)
        except Exception:
            df = None
        if df is not None and not df.empty:
            d = df[["open", "close"]].copy()
            d.index = pd.DatetimeIndex(d.index).normalize().date
            out[t] = d[~d.index.duplicated(keep="last")]
        if i % 50 == 0 or i == len(tickers):
            print(f"  fetched {i}/{len(tickers)} tickers", flush=True)
    return out


def build_overnight(universe: str, start: date, end: date, split_threshold: float):
    days = trading_days_in_range(start, end)
    if len(days) < 2:
        raise SystemExit("need >= 2 trading days")
    print(f"Universe {universe}: {len(days)} trading days {days[0]}..{days[-1]}")
    by_day = _membership(universe, days)
    union = set().union(*by_day.values())
    print(f"Fetching daily bars for {len(union)} tickers (union of PIT snapshots)…")
    bars = _daily_bars(union, start, end)

    rows = []
    dropped = 0
    for i in range(len(days) - 1):
        d, nxt = days[i], days[i + 1]
        for t in by_day[d]:
            df = bars.get(t)
            if df is None:
                continue
            try:
                close_t = df.at[d, "close"]
                open_n = df.at[nxt, "open"]
            except KeyError:
                continue
            if not (close_t and open_n and close_t > 0):
                continue
            ret = open_n / close_t - 1.0
            if abs(ret) > split_threshold:   # split / glitch / corporate action
                dropped += 1
                continue
            rows.append({"date": d, "ticker": t, "overnight_return": ret})
    led = pd.DataFrame(rows)
    led["date"] = pd.to_datetime(led["date"])
    print(f"Name-nights: {len(led):,} (dropped {dropped} as |ret|>{split_threshold:.0%} "
          f"split/glitch)")
    return led


def _report(led: pd.DataFrame, label: str) -> None:
    # equal-weight nightly portfolio
    nightly = led.groupby("date")["overnight_return"].mean()
    n = len(nightly)
    mean, sd = float(nightly.mean()), float(nightly.std(ddof=1))
    sharpe = (mean / sd * ANN) if sd > 0 else float("nan")
    sumret = float(nightly.sum())
    hit_namedays = float((led["overnight_return"] > 0).mean() * 100)
    hit_nights = float((nightly > 0).mean() * 100)
    print(f"\n=== {label} — equal-weight overnight portfolio ===")
    print(f"  nights={n}  name-nights={len(led):,}")
    print(f"  mean/night={mean*100:+.4f}%  (per name-night mean={led['overnight_return'].mean()*100:+.4f}%)")
    print(f"  sum of nightly returns={sumret*100:+.1f}%   annualized Sharpe={sharpe:+.2f}")
    print(f"  hit rate: nights {hit_nights:.1f}%  name-nights {hit_namedays:.1f}%")
    yr = nightly.groupby(nightly.index.year)
    print("  by year:   " + "  ".join(
        f"{y}: {v*100:+.1f}% (n={cnt})" for (y, v), cnt in
        zip(yr.sum().items(), yr.size())))
    q = nightly.groupby(nightly.index.to_period("Q"))
    print("  by quarter:")
    qs, qsh = q.sum(), q.apply(lambda s: s.mean()/s.std(ddof=1)*ANN if s.std(ddof=1) > 0 else float("nan"))
    for per in qs.index:
        print(f"    {per}: sum {qs[per]*100:+6.2f}%  Sharpe {qsh[per]:+.2f}  (n={q.size()[per]})")


def main() -> None:
    p = argparse.ArgumentParser(description="Stage-0 overnight-premium baseline (offline, daily bars)")
    p.add_argument("--universe", default="liquid_pit")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--split-threshold", type=float, default=0.35,
                   help="drop |overnight return| above this (split/glitch guard)")
    p.add_argument("--out", help="optional parquet path for the per-name-night ledger")
    args = p.parse_args()

    led = build_overnight(args.universe, _parse(args.start), _parse(args.end),
                          args.split_threshold)
    _report(led, args.universe)
    if args.out:
        path = Path(args.out)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        led.to_parquet(path)
        print(f"\nWrote per-name-night ledger → {path} ({len(led):,} rows)")
    print("\nNOTE: gross close→open returns, no costs/slippage. Stage-0 triage only "
          "(EXPLORATION_PLAYBOOK §1b) — a real verdict needs the capture→search→WF→"
          "PBO→DSR→sealed pipeline + an overnight-hold engine cross-check. Mind the "
          "survivorship direction (see module docstring).")


if __name__ == "__main__":
    main()
