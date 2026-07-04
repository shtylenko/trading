#!/usr/bin/env python3
"""PIT value-signal capture (book-to-market + earnings yield). FAST — no network.

Reuses the EDGAR companyfacts already cached by `scripts/capture_fundamentals.py` plus the RAW
(unadjusted) price parquet, so it makes ZERO new requests. Market cap is split-safe:
`shares_outstanding(as-reported, filed ≤ d) × raw_close(d)` (as-reported shares pair with the
UNADJUSTED price — using the split-adjusted price would be wrong by each name's split factor).

Signals at each H-day rebalance, as KNOWN at the date (filed ≤ d):
  - book_to_market = StockholdersEquity / market_cap   (high = cheap = value; primary)
  - earnings_yield = TTM net income / market_cap        (secondary, descriptive)
Negative-book-equity names (buyback-heavy) are dropped from book_to_market (meaningless ratio).

Usage:
    python3 -m trading.lab.experiments.capture.capture_value \
        --raw-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet \
        --out trading/lab/experiments/_data/_capture_value_2017_2024.parquet \
        --start-year 2017 --end-year 2024
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data import sec_fundamentals as sf

H = 20


def main() -> None:
    p = argparse.ArgumentParser(description="PIT value capture (cached EDGAR + raw price; no network)")
    p.add_argument("--raw-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet")
    p.add_argument("--out", default="trading/lab/experiments/_data/_capture_value_2017_2024.parquet")
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2024)
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    raw = pd.read_parquet(_abs(args.raw_ledger), columns=["trade_date", "ticker", "close", "eligible", "dollar_vol_20d"])
    raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.normalize()
    yr = raw["trade_date"].dt.year
    raw = raw[(yr >= args.start_year) & (yr <= args.end_year) & raw["eligible"]]
    all_days = sorted(raw["trade_date"].unique())
    rebal = set(all_days[::H])
    raw = raw[raw["trade_date"].isin(rebal)]
    # raw close lookup (ticker, date) -> raw price
    rawclose = raw.set_index(["ticker", "trade_date"])["close"].to_dict()
    asofs_by_tk = raw.groupby("ticker")["trade_date"].apply(lambda s: sorted(s.unique())).to_dict()
    tickers = sorted(asofs_by_tk)
    print(f"Value capture: {len(tickers)} eligible tickers, {len(rebal)} rebalances "
          f"({args.start_year}-{args.end_year}). Reading CACHED facts (no network)...")

    cmap = sf.cik_map()
    rows = []
    t0 = time.time()
    miss = 0
    for i, t in enumerate(tickers):
        cik = cmap.get(t.upper())
        if not cik:
            miss += 1; continue
        facts = sf.fetch_company_facts(cik)     # cached → instant
        if facts is None:
            miss += 1; continue
        eq = sf.concept_union(facts, sf.EQUITY)
        sh = sf.shares_union(facts)
        ni = sf.concept_union(facts, sf.NET_INCOME)
        for d in asofs_by_tk[t]:
            E = sf.asof_instant(eq, d)
            S = sf.asof_instant(sh, d)
            px = rawclose.get((t, d))
            if not S or not px or S <= 0 or px <= 0:
                continue
            mc = S * px
            bm = (E / mc) if (E is not None and E > 0) else np.nan
            ni_ttm = sf.asof_ttm(ni, d)
            ey = (ni_ttm / mc) if ni_ttm is not None else np.nan
            rows.append((d, t, bm, ey, mc))
        if (i + 1) % 300 == 0:
            print(f"  {i+1}/{len(tickers)} ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows, columns=["trade_date", "ticker", "book_to_market", "earnings_yield", "market_cap"])
    out.to_parquet(_abs(args.out), index=False)
    cov_bm = out["book_to_market"].notna().mean() if len(out) else 0
    cov_ey = out["earnings_yield"].notna().mean() if len(out) else 0
    print(f"\nWrote {_abs(args.out)}  ({len(out)} rows, {out['ticker'].nunique()} tickers, "
          f"facts-miss {miss}, {time.time()-t0:.0f}s)")
    print(f"coverage: book_to_market {cov_bm:.0%}, earnings_yield {cov_ey:.0%}")
    print("Next: python3 -m trading.lab.experiments.multiday.multiday_value")


if __name__ == "__main__":
    main()
