#!/usr/bin/env python3
"""Stage-0 triage for PIT-fundamentals signals (backlog #7 quality, #16 earnings momentum).

The cheap go/no-go gate before investing in a full capture + pipeline: is there ANY
cross-sectional signal in point-in-time fundamentals on our universe? Uses the SEC EDGAR
adapter (`data/sec_fundamentals.py`, true PIT — filed <= rebalance date, survivorship-free)
joined onto the existing price ledger's forward returns.

Two signals, both as-known-at the rebalance date:
  - gp_assets : Novy-Marx gross profitability = (TTM revenue − TTM COGS) / total assets
  - ni_yoy    : earnings momentum = YoY growth of TTM net income (split-safe)

Reports decile monotonicity (Spearman of decile index vs mean fwd_20) per year + pooled —
the same gate the price-momentum Stage-0 used. PASS = monotone, same-signed across years.

Usage (cap tickers by liquidity for a fast first read; raise/remove to scale):
    python3 -m trading.lab.experiments.multiday.multiday_fundamentals_triage \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet \
        --max-tickers 500
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data import sec_fundamentals as sf

H = 20
START_YEAR, END_YEAR = 2022, 2024     # clean PIT window (2025 sealed)


def _signals_for_ticker(facts: dict, asofs: list[pd.Timestamp]) -> dict[pd.Timestamp, tuple]:
    """(gp_assets, ni_yoy) as known at each asof for one company."""
    assets = sf.concept_union(facts, sf.ASSETS)
    rev = sf.concept_union(facts, sf.REVENUES)
    cogs = sf.concept_union(facts, sf.COGS)
    ni = sf.concept_union(facts, sf.NET_INCOME)
    out = {}
    for d in asofs:
        A = sf.asof_instant(assets, d)
        R = sf.asof_ttm(rev, d)
        C = sf.asof_ttm(cogs, d)
        gp = (R - C) / A if (A and R is not None and C is not None and A != 0) else np.nan
        em = sf.asof_ttm_growth(ni, d)
        out[d] = (gp if gp is not None else np.nan, em if em is not None else np.nan)
    return out


def _decile_report(df: pd.DataFrame, col: str) -> None:
    """Per-year + pooled decile monotonicity of fwd_20 across signal `col`."""
    print(f"\n=== {col} — decile monotonicity (mean fwd_20 % by signal decile) ===")
    print(f"  {'year':6}{'n':>7}{'D1(lo)':>9}{'D10(hi)':>9}{'D10-D1':>9}{'spearman':>10}")
    for yr in list(range(START_YEAR, END_YEAR + 1)) + ["pooled"]:
        sub = df if yr == "pooled" else df[df["year"] == yr]
        sub = sub.dropna(subset=[col, "fwd_20"])
        if len(sub) < 200:
            print(f"  {str(yr):6}{len(sub):>7}  (too few)"); continue
        # cross-sectional deciles within each rebalance date, then pool
        sub = sub.copy()
        sub["dec"] = sub.groupby("trade_date")[col].transform(
            lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
        g = sub.dropna(subset=["dec"]).groupby("dec")["fwd_20"].mean() * 100
        if len(g) < 10:
            print(f"  {str(yr):6}{len(sub):>7}  (insufficient breadth)"); continue
        sp = np.corrcoef(g.index.astype(float), g.values)[0, 1]
        print(f"  {str(yr):6}{len(sub):>7}{g.iloc[0]:>+9.2f}{g.iloc[-1]:>+9.2f}"
              f"{g.iloc[-1]-g.iloc[0]:>+9.2f}{sp:>+10.2f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Stage-0 PIT-fundamentals triage")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet")
    p.add_argument("--max-tickers", type=int, default=500, help="cap by liquidity for a fast first read")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    led = pd.read_parquet(path, columns=["trade_date", "ticker", "fwd_20", "eligible", "dollar_vol_20d"])
    led["trade_date"] = pd.to_datetime(led["trade_date"]).dt.normalize()
    led["year"] = led["trade_date"].dt.year
    led = led[(led["year"] >= START_YEAR) & (led["year"] <= END_YEAR) & led["eligible"] & led["fwd_20"].notna()]

    # rebalance grid (every H trading days) and the ticker set (cap by median liquidity)
    all_days = sorted(led["trade_date"].unique())
    rebal = set(all_days[::H])
    led = led[led["trade_date"].isin(rebal)]
    liq = led.groupby("ticker")["dollar_vol_20d"].median().sort_values(ascending=False)
    tickers = list(liq.head(args.max_tickers).index)
    led = led[led["ticker"].isin(tickers)]
    asofs = sorted(led["trade_date"].unique())
    print(f"Stage-0 fundamentals triage: {path.name}  {START_YEAR}-{END_YEAR}, "
          f"{len(tickers)} tickers (top by liquidity), {len(asofs)} rebalances.")

    cmap = sf.cik_map()
    sig_rows = []
    miss_cik = miss_facts = 0
    for i, t in enumerate(tickers):
        cik = cmap.get(t.upper())
        if not cik:
            miss_cik += 1; continue
        facts = sf.fetch_company_facts(cik)
        if facts is None:
            miss_facts += 1; continue
        sigs = _signals_for_ticker(facts, asofs)
        for d, (gp, em) in sigs.items():
            sig_rows.append((d, t, gp, em))
        if (i + 1) % 100 == 0:
            print(f"  ...fetched {i+1}/{len(tickers)} (no-CIK {miss_cik}, no-facts {miss_facts})")

    sig = pd.DataFrame(sig_rows, columns=["trade_date", "ticker", "gp_assets", "ni_yoy"])
    df = led.merge(sig, on=["trade_date", "ticker"], how="inner")
    cov_gp = df["gp_assets"].notna().mean()
    cov_em = df["ni_yoy"].notna().mean()
    print(f"\njoined name-rebalances: {len(df)}  (CIK-matched {len(tickers)-miss_cik}/{len(tickers)}, "
          f"no-facts {miss_facts})")
    print(f"signal coverage: gp_assets {cov_gp:.0%}, ni_yoy {cov_em:.0%} of rows")

    _decile_report(df, "gp_assets")
    _decile_report(df, "ni_yoy")
    print("\nReadout: a monotone, consistently-signed D10−D1 across years = a real PIT signal worth "
          "a full capture + pre-registered pipeline. Flat/sign-flipping = fundamentals add nothing "
          "orthogonal on this universe (bank x03). Quality (gp_assets) and earnings momentum (ni_yoy) "
          "judged independently — either passing justifies the build.")


if __name__ == "__main__":
    main()
