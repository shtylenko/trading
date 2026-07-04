#!/usr/bin/env python3
"""Stage-0.5 probe: is the overnight premium TRADEABLE once you (a) condition on
market regime and (b) pay realistic costs? Runs offline on the per-name-night
ledger written by overnight_premium_baseline.py — NO new feature capture.

Motivation: the unconditional overnight premium is real but thin (~1.6 bp/night
gross) and strongly regime-dependent (deeply negative in the 2022 bear, positive
2023–2025). The thesis is that the EDGE is regime conditioning — hold the overnight
book only when the market is risk-ON — and the question is whether that survives
round-trip costs. This triages whether a full leak-free overnight capture is worth
building, before spending it.

Regime flags (ALL known at today's close → deciding to hold tonight is leak-safe):
  - spy_above_200d : SPY close > its 200-day SMA (classic risk-on trend filter)
  - spy_above_50d  : SPY close > its 50-day SMA (faster)
  - spy_5d_up      : SPY 5-day return > 0 (short-term momentum)

Costs: --cost-bps is the ROUND-TRIP cost (buy at close + sell at next open) in basis
points, charged per name-night held. Swept over a few levels so you see the cost
the edge can bear. (Liquid ETFs ~2–4 bp round trip; liquid stocks ~6–12 bp.)

Usage:
    python3 -m trading.lab.experiments.overnight.overnight_regime_probe \
        --ledger trading/lab/experiments/_data/_overnight_etf_2022_2025.parquet
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

ANN = float(np.sqrt(252))


def _spy_regime(start: date, end: date) -> pd.DataFrame:
    """Per-date SPY regime flags, each computed from data through THAT date's close
    (leak-safe for a hold-tonight decision). Fetches extra history for the 200d SMA."""
    spy = fetch_daily_range("SPY", start - timedelta(days=420), end)
    if spy is None or spy.empty:
        raise SystemExit("could not fetch SPY")
    spy = spy[["close"]].copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    c = spy["close"]
    out = pd.DataFrame(index=spy.index)
    out["spy_above_200d"] = (c > c.rolling(200).mean()).astype(float)
    out["spy_above_50d"] = (c > c.rolling(50).mean()).astype(float)
    out["spy_5d_up"] = (c.pct_change(5) > 0).astype(float)
    return out


def _stats(nightly: pd.Series) -> dict:
    nightly = nightly.dropna()
    n = len(nightly)
    if n < 2:
        return {"nights": n, "sum": 0.0, "sharpe": float("nan"), "hit": float("nan")}
    mean, sd = float(nightly.mean()), float(nightly.std(ddof=1))
    return {
        "nights": n, "sum": float(nightly.sum()) * 100,
        "sharpe": (mean / sd * ANN) if sd > 0 else float("nan"),
        "hit": float((nightly > 0).mean() * 100),
        "by_year": {int(y): float(v) * 100 for y, v in nightly.groupby(nightly.index.year).sum().items()},
    }


def _nightly_net(led: pd.DataFrame, hold_mask: pd.Series, cost_bps: float) -> pd.Series:
    """Equal-weight nightly return after charging round-trip cost on held nights.
    hold_mask is per-date (the regime gate); nights gated off contribute 0 (flat)."""
    held = led[led["date"].map(hold_mask).fillna(False).astype(bool)].copy()
    held["net"] = held["overnight_return"] - cost_bps / 10000.0
    by_night = held.groupby("date")["net"].mean()
    all_nights = pd.Index(sorted(led["date"].unique()))
    return by_night.reindex(all_nights, fill_value=0.0)  # flat (0) when gated off


def main() -> None:
    p = argparse.ArgumentParser(description="Overnight regime + cost probe (offline)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--cost-bps", type=float, nargs="+", default=[0.0, 2.0, 5.0, 10.0],
                   help="round-trip cost(s) in bps to sweep")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    led = pd.read_parquet(path)
    led["date"] = pd.to_datetime(led["date"])
    d0, d1 = led["date"].min().date(), led["date"].max().date()
    print(f"Ledger {path.name}: {len(led):,} name-nights, {d0}..{d1}")

    reg = _spy_regime(d0, d1)
    gates = {
        "ALWAYS (unconditional)": pd.Series(True, index=reg.index),
        "spy_above_200d": reg["spy_above_200d"] == 1,
        "spy_above_50d": reg["spy_above_50d"] == 1,
        "spy_5d_up": reg["spy_5d_up"] == 1,
        "above_200d AND 5d_up": (reg["spy_above_200d"] == 1) & (reg["spy_5d_up"] == 1),
    }

    for cost in args.cost_bps:
        print(f"\n=== round-trip cost = {cost:.0f} bps ===")
        print(f"  {'regime gate':24} {'nights':>6} {'sum%':>8} {'Sharpe':>7} {'hit%':>6}  by-year sum%")
        for name, mask in gates.items():
            nightly = _nightly_net(led, mask, cost)
            # restrict the stats to nights the gate was ON (flat nights are 0 but
            # we report the active book's risk-adjusted quality + the calendar sum)
            active = nightly[nightly != 0.0]
            s_active = _stats(active)
            s_cal = _stats(nightly)  # calendar Sharpe incl. flat nights (deployable)
            by = "  ".join(f"{y}:{v:+.1f}" for y, v in s_cal.get("by_year", {}).items())
            print(f"  {name:24} {s_active['nights']:6d} {s_cal['sum']:+8.1f} "
                  f"{s_cal['sharpe']:+7.2f} {s_active['hit']:6.1f}  {by}")
    print("\n  sum%/Sharpe/by-year are CALENDAR (gated-off nights = flat/0, i.e. deployable "
          "as a capital overlay); hit% is over active nights. Gross close→open minus the "
          "stated round-trip cost. Stage-0.5 triage only.")


if __name__ == "__main__":
    main()
