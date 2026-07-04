#!/usr/bin/env python3
"""Multi-day swing capture: one row per (date, ticker) with LEAK-FREE close-knowable
momentum/conditioning features and FORWARD H-day return labels. The research ledger
for the cross-sectional momentum search (validation/multiday_momentum_findings.md,
multiday_search_spec.md). Offline, daily bars, no engine change.

Each row (date d):
  - features : computed from data THROUGH close d (strictly leak-safe),
  - fwd_H    : close(d+H)/close(d) − 1 for each horizon H (the FUTURE labels),
  - eligible : in the PIT universe as of d AND close >= $5 AND 20d $vol >= $10M,
  - score    : default ranking = mom_12_1 (the Stage-0 winner; search may keep/replace).

Captures 2022–2025 INCLUDING the sealed 2025 (the search hard-seals it, like
feature_search). The label uses look-ahead by construction (that's the point) — every
FEATURE is leak-safe; only fwd_* are future.

Usage:
    python3 -m trading.lab.experiments.capture.capture_multiday \
        --universe liquid_pit --start 2022-01-01 --end 2025-12-31 --horizons 5 20 \
        --out trading/lab/experiments/_data/_capture_multiday_2022_2025.parquet
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
MIN_DOLLAR_VOL = 10_000_000.0

FEATURE_NAMES = (
    "mom_12_1", "mom_6_1", "mom_3_1", "prox_52w", "rev_1m",
    "log_close", "dollar_vol_20d", "vol_20d",
    "spy_above_200d",
)


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _spy_regime(start: date, end: date, adjustment: str = "split") -> pd.DataFrame:
    spy = fetch_daily_range("SPY", start - timedelta(days=500), end, adjustment=adjustment)
    spy = spy[["close"]].copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    c = spy["close"]
    out = pd.DataFrame(index=spy.index)
    out["spy_above_200d"] = (c > c.rolling(200).mean()).astype(float)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Multi-day momentum capture (leak-safe, daily)")
    p.add_argument("--universe", default="liquid_pit")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--horizons", type=int, nargs="+", default=[5, 20])
    p.add_argument("--adjustment", default="split",
                   help="bar adjustment for daily closes. SPLIT-adjusted by default: a "
                        "multi-day hold straddles splits and a split inside the 252d "
                        "lookback corrupts momentum — raw is correct only for intraday.")
    p.add_argument("--fixed-universe-asof", default=None,
                   help="resolve the universe ONCE at this date and apply that fixed "
                        "ticker set to every capture date (for pre-snapshot history; "
                        "SURVIVORSHIP-limited — flag results as optimistic for long).")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    start, end = _parse(args.start), _parse(args.end)
    horizons = args.horizons
    maxh = max(horizons)
    days = trading_days_in_range(start, end)
    if args.fixed_universe_asof:
        fixed = set(load_universe_tickers(args.universe, _parse(args.fixed_universe_asof)))
        by_day = {pd.Timestamp(d): fixed for d in days}
        print(f"Universe {args.universe} FIXED as-of {args.fixed_universe_asof}: "
              f"{len(fixed)} tickers applied to all dates (SURVIVORSHIP-limited proxy).")
    else:
        by_day = {pd.Timestamp(d): set(load_universe_tickers(args.universe, d)) for d in days}
    union = sorted(set().union(*by_day.values()))
    print(f"Universe {args.universe}: {len(days)} days {days[0]}..{days[-1]}, {len(union)} tickers.")

    parts = []
    for i, t in enumerate(union, 1):
        df = fetch_daily_range(t, start - timedelta(days=430), end + timedelta(days=int(maxh * 1.6) + 10),
                               adjustment=args.adjustment)
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
        out["mom_3_1"] = c.shift(21) / c.shift(63) - 1.0
        out["prox_52w"] = c / h.rolling(252).max()
        out["rev_1m"] = c / c.shift(21) - 1.0
        out["log_close"] = np.log(c.where(c > 0))
        out["dollar_vol_20d"] = (c * v).rolling(20).mean()
        out["vol_20d"] = c.pct_change().rolling(20).std()
        for H in horizons:
            out[f"fwd_{H}"] = c.shift(-H) / c - 1.0
        out["ticker"] = t
        parts.append(out.reset_index().rename(columns={"index": "date", "timestamp": "date"}))
        if i % 200 == 0 or i == len(union):
            print(f"  panel {i}/{len(union)} tickers", flush=True)

    panel = pd.concat(parts, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    # restrict to the actual trading-day grid (drop the extra forward-padding dates)
    panel = panel[panel["date"].isin([pd.Timestamp(d) for d in days])]

    # leak-safe eligibility at close d
    panel["in_univ"] = [t in by_day.get(d, ()) for d, t in zip(panel["date"], panel["ticker"])]
    panel["eligible"] = (panel["in_univ"] & (panel["close"] >= MIN_PRICE)
                         & (panel["dollar_vol_20d"] >= MIN_DOLLAR_VOL))

    reg = _spy_regime(start, end, args.adjustment).reset_index().rename(columns={"index": "date", "timestamp": "date"})
    reg["date"] = pd.to_datetime(reg["date"]).dt.normalize()
    panel = panel.merge(reg, on="date", how="left")

    panel["score"] = panel["mom_12_1"]
    panel["filled"] = True
    panel["year"] = panel["date"].dt.year
    panel = panel.rename(columns={"date": "trade_date"})

    # keep rows with the core signal + at least the shortest-horizon label present
    core = ["mom_12_1", "vol_20d", "dollar_vol_20d", f"fwd_{min(horizons)}"]
    before = len(panel)
    panel = panel.dropna(subset=core)
    print(f"Captured {len(panel):,} name-days (dropped {before-len(panel):,} missing core). "
          f"Eligible: {int(panel['eligible'].sum()):,}.")

    out = Path(args.out)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    panel.to_parquet(out)
    print(f"Wrote multi-day capture → {out}")
    print("\nper-year eligible name-days:")
    print(panel[panel["eligible"]].groupby("year").size().to_string())


if __name__ == "__main__":
    main()
