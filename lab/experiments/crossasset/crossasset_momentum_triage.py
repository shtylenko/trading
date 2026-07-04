#!/usr/bin/env python3
"""Cross-asset momentum (GTAA/dual-momentum) — Stage-0 triage.

Genuinely-unexplored long-only direction: rank a basket of asset-class ETFs (equity, bond,
real-asset) by 12-1 TOTAL-RETURN momentum, hold the top-N equal weight, with an ABSOLUTE-momentum
filter (only hold names with own 12-mo return > 0; empty slots → cash/BIL). Unlike every killed
intra-equity signal, this ESCAPES equity beta by rotating across uncorrelated asset classes — in a
2022-style equity bear it rotates to commodities/cash, not stocks. NOT the killed defensive sleeve
(that was a forced binary SPY<200d→TLT/GLD switch; this is momentum-RANKED, so it never holds a
negative-momentum asset).

Total return via adjustment="all" (dividends matter for bonds/REITs). Fixed ETF basket = NO
survivorship bias. In-sample 2017–2024; 2025+ reserved as a clean future sealed test. The key
metric is BETA TO SPY (should be low/time-varying) + the 2022 return (should survive the bear).

Usage:
    python3 -m trading.lab.experiments.crossasset.crossasset_momentum_triage --top-n 5
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

from trading.lab.data.market_data import fetch_daily_range

H = 21                       # ~monthly rebalance / hold (trading days)
FORM_LB = 252
SKIP = 21
EQUITY = ["SPY", "QQQ", "IWM", "EFA", "EEM"]      # equity
NONEQ = ["TLT", "IEF", "LQD", "HYG", "AGG",       # bonds
         "GLD", "DBC", "VNQ"]                     # real assets
RISK = EQUITY + NONEQ
CASH = "BIL"                 # absolute-momentum destination (t-bills, total return)


def _load(syms, start, end):
    out = {}
    for s in syms:
        df = fetch_daily_range(s, start, end, adjustment="all")
        if df is None or df.empty:
            print(f"  WARN: no data for {s}"); continue
        idx = pd.DatetimeIndex(df.index).normalize().tz_localize(None)
        out[s] = pd.Series(df["close"].values, index=idx).sort_index()
        out[s] = out[s][~out[s].index.duplicated(keep="last")]
    return pd.DataFrame(out)


def _stats(r, label, mkt=None):
    r = np.asarray(r); ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sharpe = r.mean() / sd * ann if sd > 0 else np.nan
    cagr = eq[-1] ** (252.0 / H / len(r)) - 1
    beta = np.nan
    if mkt is not None:
        m = np.asarray(mkt); X = np.column_stack([np.ones(len(m)), m])
        beta = float(np.linalg.lstsq(X, r, rcond=None)[0][1])
    return {"label": label, "sharpe": sharpe, "cagr": cagr, "maxdd": dd, "beta": beta, "n": len(r)}


def main() -> None:
    p = argparse.ArgumentParser(description="cross-asset momentum Stage-0")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2024, help="2025+ reserved as sealed")
    p.add_argument("--no-equity", action="store_true",
                   help="non-equity basket only (bonds/gold/commodities/REITs) — the diversifier sleeve")
    args = p.parse_args()
    N = args.top_n
    risk = NONEQ if args.no_equity else RISK
    globals()["RISK"] = risk        # the loops below reference RISK

    # always load SPY + AGG for benchmarks/beta even if not in the tradeable basket
    load_syms = list(dict.fromkeys(risk + [CASH, "SPY", "AGG"]))
    px = _load(load_syms, date(args.start_year - 1, 1, 1), date(args.end_year, 12, 31))
    px = px.dropna(how="all").ffill()
    dates = list(px.index)
    spy = px["SPY"]

    rebal = [j for j in range(len(dates)) if j % H == 0]
    book_r, spy_r, ew_r, sf_r, yrs = [], [], [], [], []
    holdings_log = []
    for j in rebal:
        if j - FORM_LB < 1 or j + H >= len(dates):
            continue
        d = dates[j]
        if not (args.start_year <= d.year <= args.end_year):
            continue
        # 12-1 total-return momentum for each risk ETF, as known at d
        mom = {}
        for s in RISK:
            p0 = px[s].iloc[j - FORM_LB]; p1 = px[s].iloc[j - SKIP]
            if np.isfinite(p0) and np.isfinite(p1) and p0 > 0:
                mom[s] = p1 / p0 - 1.0
        if len(mom) < N:
            continue
        # absolute filter: only positive-momentum names eligible; rank desc; top-N
        pos = {s: m for s, m in mom.items() if m > 0}
        ranked = sorted(pos, key=pos.get, reverse=True)[:N]
        n_risk = len(ranked)
        n_cash = N - n_risk                              # empty slots → cash
        # forward H-day total return of each held sleeve
        def fwd(s):
            return px[s].iloc[j + H] / px[s].iloc[j] - 1.0
        r = (sum(fwd(s) for s in ranked) + n_cash * fwd(CASH)) / N
        book_r.append(r)
        spy_r.append(fwd("SPY"))
        ew_r.append(np.mean([fwd(s) for s in RISK]))     # equal-weight-all-assets benchmark
        sf_r.append(0.6 * fwd("SPY") + 0.4 * fwd("AGG")) # 60/40 benchmark
        yrs.append(d.year)
        holdings_log.append((d, ranked, n_cash))

    book_r, spy_r, ew_r, sf_r, yrs = map(np.array, (book_r, spy_r, ew_r, sf_r, yrs))
    n = len(book_r)
    print(f"Cross-asset momentum: top-{N} of {len(RISK)} ETFs, 12-1 mom + abs filter→cash, "
          f"{args.start_year}-{args.end_year} ({n} monthly rebalances; 2025+ reserved sealed)\n")
    print(f"{'strategy':28}{'annSh':>7}{'CAGR':>8}{'maxDD':>8}{'βSPY':>7}")
    for r, lab, mk in [(book_r, f"cross-asset mom (top{N})", spy_r), (spy_r, "SPY buy&hold", spy_r),
                       (sf_r, "60/40 SPY/AGG", spy_r), (ew_r, "equal-weight all ETFs", spy_r)]:
        st = _stats(r, lab, mk)
        print(f"{st['label']:28}{st['sharpe']:>+7.2f}{st['cagr']*100:>+7.1f}%{st['maxdd']*100:>+7.1f}%{st['beta']:>+7.2f}")

    print("\n=== per-year return % (cross-asset mom vs SPY) — 2022 is the bear test ===")
    for y in sorted(set(yrs.tolist())):
        bm = book_r[yrs == y]; sm = spy_r[yrs == y]
        # compound within year
        bc = float(np.prod(1 + bm) - 1); sc = float(np.prod(1 + sm) - 1)
        print(f"  {y}: cross-asset {bc*100:+6.1f}%   SPY {sc*100:+6.1f}%")

    # sample recent holdings (shows the rotation)
    print("\n=== last 6 rebalance holdings (rotation evidence) ===")
    for d, held, nc in holdings_log[-6:]:
        cash_s = f" +{nc}×cash" if nc else ""
        print(f"  {d.date()}: {', '.join(held)}{cash_s}")

    bm = _stats(book_r, "x", spy_r)
    print(f"\nReadout: the prize is LOW βSPY ({bm['beta']:+.2f}) + a non-negative 2022 with a Sharpe "
          "competitive with SPY. If βSPY is low AND 2022 survived, this is a GENUINE diversifier to x03 "
          "(equity momentum) — worth the full pipeline + a sealed-2025 test. If it's just SPY-beta or "
          "dies in 2022, it's no better than what we have.")


if __name__ == "__main__":
    main()
