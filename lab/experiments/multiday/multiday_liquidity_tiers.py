#!/usr/bin/env python3
"""Liquidity-tier gradient test — does factor strength increase toward smaller/less-liquid names?

The cheap go/no-go for the "switch to a small-cap universe" idea (option 1) BEFORE buying a
survivorship-free small-cap data source. Splits our existing eligible universe into liquidity
tiers by 20-day dollar volume and measures each factor's BETA-ADJUSTED top-50 book (alpha + t +
Sharpe) per tier. Three signals: momentum (mom_12_1, positive control), quality (gp_assets),
value (book_to_market).

Key asymmetry that makes a NEGATIVE result trustworthy: survivorship bias INFLATES the
lower-liquidity tier (more of those names since delisted are missing), so a factor that is still
flat/beta in our small tier — with that tailwind — will not be rescued by clean small-cap data.
A monotone strengthening toward the illiquid tier is what would justify the data buy.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_liquidity_tiers \
        --price-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --fundamentals trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet \
        --value trading/lab/experiments/_data/_capture_value_2017_2024.parquet \
        --start-year 2022 --end-year 2024 --n-tiers 3
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
MIN_TIER = 150          # need enough names in a tier to take a top-50


def _beta_adj(r, m):
    r = np.asarray(r); m = np.asarray(m); n = len(r)
    if n < 5:
        return np.nan, np.nan, np.nan, np.nan
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat; s2 = (e @ e) / (n - 2); cov = s2 * np.linalg.inv(X.T @ X)
    sd = r.std(ddof=1); sharpe = r.mean() / sd * np.sqrt(252.0 / H) if sd > 0 else np.nan
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1], sharpe


def main() -> None:
    p = argparse.ArgumentParser(description="liquidity-tier factor-strength gradient")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--fundamentals", default="trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet")
    p.add_argument("--value", default="trading/lab/experiments/_data/_capture_value_2017_2024.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument("--n-tiers", type=int, default=3)
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    df = pd.read_parquet(_abs(args.price_ledger),
                         columns=["trade_date", "ticker", "mom_12_1", "fwd_20", "dollar_vol_20d", "eligible"])
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    fund = pd.read_parquet(_abs(args.fundamentals))[["trade_date", "ticker", "gp_assets"]]
    fund["trade_date"] = pd.to_datetime(fund["trade_date"]).dt.normalize()
    val = pd.read_parquet(_abs(args.value))[["trade_date", "ticker", "book_to_market"]]
    val["trade_date"] = pd.to_datetime(val["trade_date"]).dt.normalize()
    df = df.merge(fund, on=["trade_date", "ticker"], how="left").merge(val, on=["trade_date", "ticker"], how="left")

    yr = df["trade_date"].dt.year
    df = df[(yr >= args.start_year) & (yr <= args.end_year) & df["eligible"] & df["fwd_20"].notna()]
    # Use the captures' OWN rebalance grid (they strided from 2017) so the fundamentals/value
    # columns are populated at these dates — building a fresh 2022-strided grid would misalign.
    cap_dates = set(fund["trade_date"]) | set(val["trade_date"])
    rebal = sorted(d for d in df["trade_date"].unique() if d in cap_dates)
    df = df[df["trade_date"].isin(rebal)]

    dates = sorted(df["trade_date"].unique())
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0)

    nt = args.n_tiers
    signals = ["mom_12_1", "gp_assets", "book_to_market"]
    # books[signal][tier] = list of per-period book returns; mkt aligned per (signal,tier)
    books = {s: {k: [] for k in range(nt)} for s in signals}
    mkts = {s: {k: [] for k in range(nt)} for s in signals}
    tvol = {k: [] for k in range(nt)}

    for d in rebal:
        day = df[df["trade_date"] == d]
        if len(day) < MIN_TIER * nt // 2:
            continue
        m = spy_fwd.get(d, np.nan)
        if not np.isfinite(m):
            continue
        # liquidity tiers: 0 = most liquid ... nt-1 = least liquid
        day = day.sort_values("dollar_vol_20d", ascending=False).reset_index(drop=True)
        edges = np.linspace(0, len(day), nt + 1).astype(int)
        for k in range(nt):
            tier = day.iloc[edges[k]:edges[k + 1]]
            if len(tier) < MIN_TIER:
                continue
            tvol[k].append(float(tier["dollar_vol_20d"].median()))
            for s in signals:
                sub = tier.dropna(subset=[s])
                if len(sub) < TOP_N:
                    continue
                top = sub.nlargest(TOP_N, s)
                books[s][k].append(float(top["fwd_20"].mean()) - COST)
                mkts[s][k].append(m)

    print(f"Liquidity-tier gradient: {args.start_year}-{args.end_year}, {nt} tiers, top-{TOP_N}/tier, "
          f"beta-adjusted. Tier 0 = most liquid.\n")
    print(f"{'signal':16}{'tier':>5}{'med$vol':>10}{'annSh':>7}{'alpha%':>8}{'t(α)':>7}{'beta':>7}{'nPer':>6}")
    for s in signals:
        for k in range(nt):
            r = books[s][k]
            if len(r) < 5:
                print(f"{s:16}{k:>5}{'—':>10}{'(thin)':>7}"); continue
            a, t, b, sh = _beta_adj(r, mkts[s][k])
            mv = np.median(tvol[k]) / 1e6 if tvol[k] else float("nan")
            print(f"{s:16}{k:>5}{mv:>9.0f}M{sh:>+7.2f}{a*100:>+8.2f}{t:>+7.2f}{b:>+7.2f}{len(r):>6}")
        print()
    print("Read: does alpha/t-stat STRENGTHEN from tier 0 (liquid) → tier", nt-1, "(small)? "
          "If value/quality alpha rises toward the small tier, a survivorship-free small-cap source is "
          "justified. If flat/negative even here (where survivorship INFLATES the small tier), option 1 "
          "is a dead end — the factor isn't there, clean data won't conjure it.")


if __name__ == "__main__":
    main()
