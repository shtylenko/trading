#!/usr/bin/env python3
"""Validate the OVERNIGHT REGIME OVERLAY as a single, pre-specified rule:
equal-weight the universe overnight (close→open), held ONLY on nights with SPY
above its long SMA. This is the one robust remnant of the overnight thread — a
regime-conditioned BETA-TIMING overlay (NOT a cross-sectional alpha; that path was
killed, overnight_premium_findings.md). It has no searched/tuned parameters, so the
selection-bias gates (PBO/DSR) don't apply; the honest tests for a fixed rule are:

  1. per-year consistency NET of cost (not just one good year),
  2. threshold robustness (50d / 100d / 200d — is it a knife-edge on 200?),
  3. statistical significance (t-stat of nightly net returns on regime-ON nights),
  4. mechanism check (regime-OFF nights are genuinely the bad ones → the gate adds
     value, it isn't just discarding random nights),
  5. 2025 reported separately as the most out-of-sample year.

Usage:
    python3 -m trading.lab.experiments.overnight.overnight_overlay_validate \
        --ledger trading/lab/experiments/_data/_overnight_etf_2022_2025.parquet \
        --cost-bps 2 3
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

ANN = float(np.sqrt(252))


def _spy_smas(start: date, end: date) -> pd.DataFrame:
    spy = fetch_daily_range("SPY", start - timedelta(days=500), end)
    spy = spy[["close"]].copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    c = spy["close"]
    out = pd.DataFrame(index=spy.index)
    for w in (50, 100, 200):
        out[f"above_{w}d"] = (c > c.rolling(w).mean()).astype(float)
    return out


def _series_stats(nightly_net: pd.Series) -> dict:
    """nightly_net: net return per CALENDAR night (0 on gated-off nights)."""
    active = nightly_net[nightly_net != 0.0].dropna()
    n_act = len(active)
    mean, sd = float(nightly_net.mean()), float(nightly_net.std(ddof=1))
    sharpe = (mean / sd * ANN) if sd > 0 else float("nan")
    # t-stat on the ACTIVE nights (is the held-book mean return > 0?)
    am, asd = float(active.mean()), float(active.std(ddof=1)) if n_act > 1 else float("nan")
    tstat = (am / asd * np.sqrt(n_act)) if (n_act > 1 and asd > 0) else float("nan")
    return {"cal_sum": float(nightly_net.sum()) * 100, "cal_sharpe": sharpe,
            "active_nights": n_act, "active_mean_bps": am * 1e4, "tstat": tstat,
            "by_year": {int(y): float(v) * 100 for y, v in
                        nightly_net.groupby(nightly_net.index.year).sum().items()}}


def main() -> None:
    p = argparse.ArgumentParser(description="Validate the overnight regime overlay (fixed rule)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--cost-bps", type=float, nargs="+", default=[2.0, 3.0])
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    led = pd.read_parquet(path)
    led["date"] = pd.to_datetime(led["date"]).dt.normalize()
    d0, d1 = led["date"].min().date(), led["date"].max().date()
    nightly_gross = led.groupby("date")["overnight_return"].mean()
    nightly_gross.index = pd.DatetimeIndex(nightly_gross.index)
    print(f"Ledger {path.name}: {len(led):,} name-nights, {d0}..{d1}, "
          f"{len(nightly_gross)} nights (equal-weight).")

    smas = _spy_smas(d0, d1)

    for cost in args.cost_bps:
        c = cost / 1e4
        print(f"\n{'='*78}\nROUND-TRIP COST = {cost:.0f} bps\n{'='*78}")
        # baseline always-on
        always = (nightly_gross - c)
        s = _series_stats(always)
        by = "  ".join(f"{y}:{v:+.1f}" for y, v in s["by_year"].items())
        print(f"  {'ALWAYS-ON (no gate)':22} sum={s['cal_sum']:+6.1f}% Sharpe={s['cal_sharpe']:+.2f} "
              f"t={s['tstat']:+.2f} nights={s['active_nights']}  {by}")
        for w in (50, 100, 200):
            mask = smas[f"above_{w}d"].reindex(nightly_gross.index).fillna(0.0)
            on = (nightly_gross - c).where(mask == 1.0, 0.0)
            s = _series_stats(on)
            by = "  ".join(f"{y}:{v:+.1f}" for y, v in s["by_year"].items())
            print(f"  SPY>{w}d {'overlay':14} sum={s['cal_sum']:+6.1f}% Sharpe={s['cal_sharpe']:+.2f} "
                  f"t={s['tstat']:+.2f} nights={s['active_nights']}  {by}")
            if w == 200:
                # mechanism: the gated-OFF nights (SPY<200d) — should be worse
                off = (nightly_gross - c).where(mask == 0.0, 0.0)
                so = _series_stats(off)
                print(f"      └ regime-OFF nights (SPY<200d): active mean={so['active_mean_bps']:+.2f}bps "
                      f"t={so['tstat']:+.2f} over {so['active_nights']} nights "
                      f"(these are the nights the overlay AVOIDS)")

    print("\nNotes: cal_sum/Sharpe are CALENDAR (gated-off nights flat) — deployable as an "
          "overlay; t-stat is on the ACTIVE (held) nights. Gross close→open minus the stated "
          "round-trip cost. 2025 is the most out-of-sample year (read it as the holdout). This "
          "is a beta-timing overlay (no cross-sectional alpha) — a PASS still owes a real "
          "overnight-hold engine cross-check + a capacity/borrow/fill check before capital.")


if __name__ == "__main__":
    main()
