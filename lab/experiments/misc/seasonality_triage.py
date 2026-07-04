#!/usr/bin/env python3
"""Calendar / seasonality anomalies — Stage-0 triage (long-only exposure timing on SPY).

Tests documented calendar effects as long/cash overlays on SPY total return:
  - turn-of-month (TOM): long the last trading day + first 3 of each month, else cash
  - Halloween (sell-in-May): long Nov–Apr, cash May–Oct
  - TOM ∩ Halloween: TOM days only during the Nov–Apr window
Genuinely orthogonal to cross-sectional beta (calendar-based), long-only. But it's market-TIMING
(the fragile class that has failed here), so the bar is high: it must beat SPY buy&hold on
risk-adjusted terms with meaningfully less time at risk to be interesting. Total return via
adjustment="all"; 2016–2024 in-sample, 2025+ reserved.

Usage: python3 -m trading.lab.experiments.misc.seasonality_triage
"""
from __future__ import annotations

import sys
from datetime import date

import numpy as np
import pandas as pd

from trading.lab.data.market_data import fetch_daily_range


def _stats(daily_ret, in_mkt):
    r = daily_ret * in_mkt                       # cash = 0 on out days
    ann = np.sqrt(252.0); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sharpe = r.mean() / sd * ann if sd > 0 else np.nan
    cagr = eq[-1] ** (252.0 / len(r)) - 1
    return sharpe, cagr, dd, float(in_mkt.mean())


def main() -> None:
    spy = fetch_daily_range("SPY", date(2016, 1, 1), date(2024, 12, 31), adjustment="all")
    idx = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    s = pd.Series(spy["close"].values, index=idx).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    r = s.pct_change().dropna()
    dts = r.index

    # turn-of-month flag: last trading day of month or first 3 trading days
    month = dts.to_period("M")
    is_last = pd.Series(month, index=dts).shift(-1).ne(pd.Series(month, index=dts)).values
    # first-3: rank within month
    dom_rank = pd.Series(1, index=dts).groupby(month).cumsum().values
    is_first3 = dom_rank <= 3
    tom = (is_last | is_first3).astype(float)
    halloween = np.isin(dts.month, [11, 12, 1, 2, 3, 4]).astype(float)
    tom_hall = tom * halloween

    rv = r.values
    print("Seasonality overlays on SPY total return, 2016-2024 (daily):\n")
    print(f"{'strategy':26}{'annSh':>7}{'CAGR':>8}{'maxDD':>8}{'%inMkt':>8}")
    for flag, lab in [(np.ones(len(rv)), "SPY buy&hold"),
                      (tom, "turn-of-month"),
                      (halloween, "Halloween (Nov-Apr)"),
                      (tom_hall, "TOM ∩ Halloween")]:
        sh, cg, dd, frac = _stats(rv, flag)
        print(f"{lab:26}{sh:>+7.2f}{cg*100:>+7.1f}%{dd*100:>+7.1f}%{frac*100:>7.0f}%")
    print("\nReadout: a seasonality overlay is interesting only if Sharpe BEATS buy&hold with far less "
          "time at risk (capital-efficient / lower DD). Modest absolute return is expected (it sits in "
          "cash most days). As market-TIMING it's the fragile class — high bar to clear vs cross-asset.")


if __name__ == "__main__":
    main()
