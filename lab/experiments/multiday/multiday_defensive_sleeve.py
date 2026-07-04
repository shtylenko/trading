#!/usr/bin/env python3
"""Long-only DEFENSIVE-SLEEVE rotation on the momentum book — the no-shorting route to
a smoother portfolio (multiday_momentum_findings.md: no long-only equity factor
diversifies momentum; smoothing must come from a non-equity sleeve or a regime
overlay). Rule: at each rebalance, if SPY > its 200-day SMA hold the top-50 momentum
book; otherwise hold a defensive sleeve (cash / TLT / GLD / TLT+GLD). Compare the
combined series to ALWAYS-momentum on annualized Sharpe AND max drawdown (the point is
tail reduction, not extra return).

Offline on the existing capture (momentum book + leak-safe SPY>200d regime) plus
fetched TLT/GLD daily bars. H=20 non-overlapping, 10 bps cost on whatever is held.
2017–2024 (2025 sealed); pre-2022 survivorship-optimistic (flag).

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_defensive_sleeve \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range

OOS_YEAR = 2025
H = 20
TOP_N = 50
COST = 10.0 / 10000.0
ANN = float(np.sqrt(252.0 / H))


def _fwd_h(sym: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Forward H-trading-day return of `sym` at each date (from fetched daily closes)."""
    df = fetch_daily_range(sym, date(2016, 1, 1), date(2025, 2, 1))
    df = df[["close"]].copy()
    df.index = pd.DatetimeIndex(df.index).normalize().tz_localize(None)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    c = df["close"]
    out = {}
    for d in dates:
        if d not in df.index:
            continue
        i = df.index.get_loc(d)
        if i + H < len(c):
            out[d] = c.iloc[i + H] / c.iloc[i] - 1.0
    return pd.Series(out)


def _curve_stats(r: pd.Series) -> dict:
    r = r.dropna()
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    eq = (1.0 + r).cumprod()
    dd = float((eq / eq.cummax() - 1.0).min())   # max drawdown
    return {"sharpe": (mean / sd * ANN) if sd > 0 else float("nan"),
            "total": float(eq.iloc[-1] - 1.0), "maxdd": dd,
            "by_year": {int(y): float(v) for y, v in r.groupby(r.index.year).mean().items()}}


def main() -> None:
    p = argparse.ArgumentParser(description="Defensive-sleeve rotation on the momentum book")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet")
    args = p.parse_args()
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df[df["eligible"] & (df["trade_date"].dt.year < OOS_YEAR) & df["fwd_20"].notna()].copy()

    all_days = sorted(df["trade_date"].unique())
    rebal = pd.DatetimeIndex(all_days[::H])

    # momentum book net return per rebalance + regime (SPY>200d) at that date
    sub = df[df["trade_date"].isin(rebal)]
    mom = (sub.sort_values("mom_12_1", ascending=False).groupby("trade_date").head(TOP_N)
              .groupby("trade_date")["fwd_20"].mean() - COST)
    regime = sub.groupby("trade_date")["spy_above_200d"].first()  # 1 = risk-on
    mom, regime = mom.sort_index(), regime.reindex(mom.index)
    risk_off = (regime != 1.0)
    print(f"Defensive-sleeve rotation: {len(mom)} rebalances 2017–2024, "
          f"{int(risk_off.sum())} risk-off (SPY<200d). Pre-2022 survivorship-optimistic.\n")

    tlt = _fwd_h("TLT", mom.index).reindex(mom.index) - COST
    gld = _fwd_h("GLD", mom.index).reindex(mom.index) - COST
    sleeves = {
        "cash":      pd.Series(0.0, index=mom.index),
        "TLT":       tlt,
        "GLD":       gld,
        "TLT+GLD":   (tlt + gld) / 2.0,
    }

    base = _curve_stats(mom)
    print(f"  {'strategy':22} {'Sharpe':>7} {'maxDD':>8} {'total':>8}  by-year mean%")
    print("  " + "-" * 70)
    print(f"  {'ALWAYS momentum':22} {base['sharpe']:+7.2f} {base['maxdd']*100:+7.1f}% "
          f"{base['total']*100:+7.0f}%  " + " ".join(f"{y}:{v*100:+.1f}" for y, v in base['by_year'].items()))
    for name, sl in sleeves.items():
        r = mom.where(~risk_off, sl)   # risk-on → momentum; risk-off → sleeve
        st = _curve_stats(r)
        print(f"  {'mom⇄'+name:22} {st['sharpe']:+7.2f} {st['maxdd']*100:+7.1f}% "
              f"{st['total']*100:+7.0f}%  " + " ".join(f"{y}:{v*100:+.1f}" for y, v in st['by_year'].items()))

    print("\n  Goal = SMOOTHER: higher Sharpe and/or shallower maxDD than always-momentum "
          f"(Sharpe {base['sharpe']:+.2f}, maxDD {base['maxdd']*100:+.1f}%). Risk-off periods "
          "swap the momentum book for the sleeve. Gross−10bps; pre-2022 survivorship-optimistic "
          "(treat levels as upper bounds; the drawdown-reduction structure is the takeaway).")


if __name__ == "__main__":
    main()
