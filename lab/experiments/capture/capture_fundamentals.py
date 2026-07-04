#!/usr/bin/env python3
"""Full PIT-fundamentals capture across the eligible universe (the LONG EDGAR fetch).

Builds the fundamentals ledger that `scripts/multiday_quality.py` scores: for every eligible
ticker, at every H-day rebalance date in the window, the as-known-at-date quality + earnings
signals from `data/sec_fundamentals.py` (true point-in-time, survivorship-free).

This is the slow step — it fetches one `companyfacts` JSON per ticker from SEC EDGAR (cached to
`data/_sec_cache/`, rate-limited ≤8/s, retried). RUN IT MANUALLY; reruns are cheap (cached).
Resumable: a transient skip just leaves that ticker out of this run; rerun to fill it.

Usage (full universe, powered window):
    python3 -m trading.lab.experiments.capture.capture_fundamentals \
        --price-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --out trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet \
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


def _signals(facts: dict, asofs: list[pd.Timestamp]) -> list[tuple]:
    assets = sf.concept_union(facts, sf.ASSETS)
    rev = sf.concept_union(facts, sf.REVENUES)
    cogs = sf.concept_union(facts, sf.COGS)
    ni = sf.concept_union(facts, sf.NET_INCOME)
    rows = []
    for d in asofs:
        A = sf.asof_instant(assets, d)
        R = sf.asof_ttm(rev, d)
        C = sf.asof_ttm(cogs, d)
        gp = (R - C) / A if (A and R is not None and C is not None and A != 0) else np.nan
        em = sf.asof_ttm_growth(ni, d)
        rows.append((d, gp if gp is not None else np.nan, em if em is not None else np.nan))
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Full PIT-fundamentals capture (long EDGAR fetch)")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--out", default="trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet")
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument("--max-tickers", type=int, default=0, help="0 = all eligible names")
    args = p.parse_args()

    lp = Path(args.price_ledger)
    if not lp.is_absolute():
        lp = PROJECT_ROOT / lp
    led = pd.read_parquet(lp, columns=["trade_date", "ticker", "eligible", "dollar_vol_20d"])
    led["trade_date"] = pd.to_datetime(led["trade_date"]).dt.normalize()
    yr = led["trade_date"].dt.year
    led = led[(yr >= args.start_year) & (yr <= args.end_year) & led["eligible"]]

    all_days = sorted(led["trade_date"].unique())
    rebal = all_days[::H]
    led = led[led["trade_date"].isin(rebal)]
    asofs = sorted(led["trade_date"].unique())
    liq = led.groupby("ticker")["dollar_vol_20d"].median().sort_values(ascending=False)
    tickers = list(liq.index if args.max_tickers <= 0 else liq.head(args.max_tickers).index)
    print(f"Fundamentals capture: {len(tickers)} eligible tickers, {len(asofs)} rebalances "
          f"({args.start_year}-{args.end_year}). Fetching companyfacts (cached, ~8/s)...")

    cmap = sf.cik_map()
    out_rows = []
    t0 = time.time()
    miss_cik = miss_facts = 0
    for i, t in enumerate(tickers):
        cik = cmap.get(t.upper())
        if not cik:
            miss_cik += 1; continue
        facts = sf.fetch_company_facts(cik)
        if facts is None:
            miss_facts += 1; continue
        for d, gp, em in _signals(facts, asofs):
            out_rows.append((d, t, gp, em))
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(tickers)}  ({el:.0f}s, no-CIK {miss_cik}, no-facts {miss_facts})")

    out = pd.DataFrame(out_rows, columns=["trade_date", "ticker", "gp_assets", "ni_yoy"])
    op = Path(args.out)
    if not op.is_absolute():
        op = PROJECT_ROOT / op
    out.to_parquet(op, index=False)
    cov_gp = out["gp_assets"].notna().mean() if len(out) else 0
    cov_em = out["ni_yoy"].notna().mean() if len(out) else 0
    print(f"\nWrote {op}  ({len(out)} rows, {out['ticker'].nunique()} tickers)")
    print(f"coverage: gp_assets {cov_gp:.0%}, ni_yoy {cov_em:.0%}  "
          f"(CIK-miss {miss_cik}, facts-miss {miss_facts}, {time.time()-t0:.0f}s total)")
    print("Next: python3 -m trading.lab.experiments.multiday.multiday_quality "
          f"--fundamentals {op.name}")


if __name__ == "__main__":
    main()
