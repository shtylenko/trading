#!/usr/bin/env python3
"""x05 Arm B (issuance) capture — split-adjusted 12-month net share issuance, PIT.

Spec: `validation/research_log/multiday_x05_residual_purification_preregistration.md` (Arm B
addendum). For each eligible ticker at each H-day rebalance d:
    NSI = shares(d) / ( shares(d−~12m) × split_ratio_over_interval ) − 1
where shares = raw cover-page count (SEC DEI, PIT via filed ≤ d) and split_ratio is the product
of yfinance split events with ex-date in (d−12m, d]. The split adjustment is NOT optional: the
momentum winners (NVDA 10:1, AAPL 4:1, TSLA, …) are exactly the names that split, and a raw
share-count delta would book a split as huge "issuance". Splits come from yfinance directly
(deep history, no creds) — avoids the Alpaca/MarketData history gating on raw prices.

Shares are already in the local companyfacts cache from the fundamentals capture, so the SEC
side is a re-extract. The per-ticker yfinance split fetch is the slow part. RUN MANUALLY. Usage:
    python3 -m trading.lab.experiments.capture.capture_issuance \
        --price-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --out trading/lab/experiments/_data/_capture_issuance_2017_2025.parquet \
        --start-year 2017 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yfinance as yf

from trading.lab.data import sec_fundamentals as sf

H = 20
LOOKBACK_DAYS = 365      # ~12 months calendar for the share-count comparison


def _split_events(ticker: str) -> pd.Series:
    """yfinance split events: ex-date (tz-naive) -> ratio (4.0 for 4:1, 0.1 for 1:10 reverse).
    Retried — batch throttling can return an empty Series for a name that DID split, which would
    leave a 20:1 booked as +1900% issuance. An empty result after retries is the genuine-no-split
    case; the NSI winsorization in main() is the safety net for any that still slip through."""
    for attempt in range(3):
        try:
            s = yf.Ticker(ticker).splits
            if s is not None and len(s) > 0:
                s = s.copy()
                s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                return s[s > 0]
        except Exception:
            pass
        time.sleep(0.4 * (attempt + 1))
    return pd.Series(dtype=float)


def main() -> None:
    p = argparse.ArgumentParser(description="x05 Arm B issuance capture (split-adjusted NSI, PIT)")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--out", default="trading/lab/experiments/_data/_capture_issuance_2017_2025.parquet")
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--max-tickers", type=int, default=0)
    args = p.parse_args()

    lp = Path(args.price_ledger)
    if not lp.is_absolute():
        lp = PROJECT_ROOT / lp
    led = pd.read_parquet(lp, columns=["trade_date", "ticker", "eligible", "dollar_vol_20d"])
    led["trade_date"] = pd.to_datetime(led["trade_date"]).dt.normalize()
    yr = led["trade_date"].dt.year
    win = led[(yr >= args.start_year) & (yr <= args.end_year) & led["eligible"]]
    all_days = sorted(win["trade_date"].unique())
    rebal = all_days[::H]
    elig_rebal = win[win["trade_date"].isin(rebal)]
    asofs = sorted(pd.to_datetime(elig_rebal["trade_date"].unique()))
    liq = elig_rebal.groupby("ticker")["dollar_vol_20d"].median().sort_values(ascending=False)
    tickers = list(liq.index if args.max_tickers <= 0 else liq.head(args.max_tickers).index)
    print(f"Issuance capture: {len(tickers)} eligible tickers, {len(asofs)} rebalances "
          f"({args.start_year}-{args.end_year}). Shares from SEC cache + yfinance splits...")

    cmap = sf.cik_map()
    rows = []
    t0 = time.time()
    miss_cik = miss_facts = 0
    for i, t in enumerate(tickers):
        cik = cmap.get(t.upper())
        if not cik:
            miss_cik += 1; continue
        facts = sf.fetch_company_facts(cik)
        if facts is None:
            miss_facts += 1; continue
        sh = sf.shares_union(facts)
        # DEI cover-page count ONLY: it is stated "as of" the filing/cover date (post any split that
        # already occurred), so its (end,val) basis is unambiguous — unlike the us-gaap balance-sheet
        # count, which filers restate inconsistently (a post-split value tagged with a pre-split
        # period-end date double-counts under to_current). Fall back to the union only if DEI is absent.
        dei = sh[sh["concept"] == "EntityCommonStockSharesOutstanding"]
        sh = (dei if not dei.empty else sh)
        if sh.empty:
            miss_facts += 1; continue
        sh = sh.copy()
        sh["filed"] = pd.to_datetime(sh["filed"]); sh["end"] = pd.to_datetime(sh["end"])
        splits = _split_events(t.replace(".", "-"))     # yfinance symbology (BRK.B -> BRK-B)

        def asof_shares(asof):
            """(end-date, value) of the latest share figure KNOWN at asof (filed ≤ asof, max end)."""
            k = sh[sh["filed"] <= asof]
            if k.empty:
                return None
            r = k.sort_values(["end", "filed"]).iloc[-1]
            return r["end"], float(r["val"])

        def to_current(end, val):
            """Restate a share figure (valid as of its end-date) into current post-all-splits terms,
            so two figures from different dates are comparable: multiply by splits with ex-date > end."""
            if len(splits) and end is not None:
                sr = float(splits[splits.index > end].prod())
                if np.isfinite(sr) and sr > 0:
                    return val * sr
            return val

        for d in asofs:
            d0 = d - timedelta(days=LOOKBACK_DAYS)
            a_now, a_prev = asof_shares(d), asof_shares(d0)
            if a_now and a_prev and a_prev[1] != 0:
                adj_now = to_current(*a_now); adj_prev = to_current(*a_prev)
                nsi = adj_now / adj_prev - 1.0 if adj_prev else np.nan
                # Safety net: the yfinance split correction is imperfect because SEC's DEI share
                # fact tags the count with the PERIOD-END date (often pre-split) while its VALUE is
                # the cover-page CURRENT (post-split) count — an irreducible basis ambiguity around
                # splits that leaks artifacts BOTH ways (+19 for a missed 20:1, −0.95 for an
                # over-applied one). Real 12m net issuance ≈ never leaves (−0.45, +0.85); NaN outside
                # → that name is simply NOT vetoed. This makes the veto CONSERVATIVE (it can miss a
                # genuine heavy issuer that also split) but it never FALSELY vetoes a non-issuer on a
                # split artifact. (Pre-committed band, a data-cleaning rule — not a signal knob.)
                if np.isfinite(nsi) and not (-0.45 < nsi < 0.85):
                    nsi = np.nan
            else:
                nsi = np.nan
            rows.append((d, t, nsi))
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(tickers)}  ({time.time()-t0:.0f}s, no-CIK {miss_cik}, no-facts {miss_facts})")

    out = pd.DataFrame(rows, columns=["trade_date", "ticker", "nsi_12m"])
    op = Path(args.out)
    if not op.is_absolute():
        op = PROJECT_ROOT / op
    out.to_parquet(op, index=False)
    cov = out["nsi_12m"].notna().mean() if len(out) else 0
    print(f"\nWrote {op}  ({len(out)} rows, {out['ticker'].nunique()} tickers, nsi coverage {cov:.0%})")
    print(f"  (no-CIK {miss_cik}, no-facts {miss_facts}, {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
