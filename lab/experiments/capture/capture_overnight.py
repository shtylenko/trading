#!/usr/bin/env python3
"""Overnight capture: annotate each name-night with LEAK-FREE features known AT
THE CLOSE, joined to its close→open return. The research ledger for the overnight
cross-sectional search (validation/overnight_premium_findings.md, EXPLORATION_PLAYBOOK).

Each row = one (date, ticker) name-night:
  - realized_r  : the close→open overnight return (the FUTURE outcome; from the
                  Stage-0 ledger written by overnight_premium_baseline.py),
  - features    : everything below, computed from data THROUGH that date's close
                  (strictly leak-safe — the only future quantity is realized_r),
  - score       : default ranking signal for the deployment top-N (short-term
                  reversal: most-oversold first); the search can re-rank.

All features are DAILY-derived (no intraday needed), so this is fast. Leak-safety
is enforced by construction: every feature uses close/open/high/low/volume up to
and including date d; the outcome is open(d+1)/close(d) − 1.

Usage:
    python3 -m trading.lab.experiments.capture.capture_overnight \
        --in trading/lab/experiments/_data/_overnight_stocks_2022_2025.parquet \
        --universe liquid_pit --start 2022-01-01 --end 2025-12-31 \
        --out trading/lab/experiments/_data/_overnight_capture_stocks_2022_2025.parquet
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

# Feature columns produced (documented; the search grid references these by name).
FEATURE_NAMES = (
    "log_close", "ret_1d", "ret_intraday", "ret_5d", "ret_10d", "ret_20d",
    "rsi_2", "vol_20d", "dollar_vol_20d", "gap_today", "range_pos_today",
    "dist_20d_high", "dist_52w_high",
    "dow", "dom", "is_turn_of_month",
    "spy_above_200d", "spy_above_50d", "spy_5d_ret", "spy_ret_1d",
)


def _rsi(series: pd.Series, period: int) -> pd.Series:
    """Wilder RSI over `period` on a close series (leak-safe: uses only past closes)."""
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_down = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def _ticker_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-date leak-safe feature panel for one ticker's daily bars (date-indexed,
    sorted). Every value uses data through that date's close."""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    prev_c = c.shift(1)
    out = pd.DataFrame(index=df.index)
    out["log_close"] = np.log(c.where(c > 0))
    out["ret_1d"] = c / prev_c - 1.0
    out["ret_intraday"] = c / o.where(o > 0) - 1.0
    out["ret_5d"] = c / c.shift(5) - 1.0
    out["ret_10d"] = c / c.shift(10) - 1.0
    out["ret_20d"] = c / c.shift(20) - 1.0
    out["rsi_2"] = _rsi(c, 2)
    daily_ret = c.pct_change()
    out["vol_20d"] = daily_ret.rolling(20).std()
    out["dollar_vol_20d"] = (c * v).rolling(20).mean()
    out["gap_today"] = o / prev_c - 1.0
    rng = (h - l).replace(0.0, np.nan)
    out["range_pos_today"] = (c - l) / rng
    out["dist_20d_high"] = c / h.rolling(20).max() - 1.0
    out["dist_52w_high"] = c / h.rolling(252).max() - 1.0
    return out


def _spy_regime(start: date, end: date) -> pd.DataFrame:
    spy = fetch_daily_range("SPY", start - timedelta(days=420), end)
    if spy is None or spy.empty:
        raise SystemExit("could not fetch SPY for regime features")
    spy = spy[["close"]].copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    c = spy["close"]
    out = pd.DataFrame(index=spy.index)
    out["spy_above_200d"] = (c > c.rolling(200).mean()).astype(float)
    out["spy_above_50d"] = (c > c.rolling(50).mean()).astype(float)
    out["spy_5d_ret"] = c.pct_change(5)
    out["spy_ret_1d"] = c.pct_change(1)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Overnight feature capture (leak-safe, daily)")
    p.add_argument("--in", dest="inp", required=True, help="Stage-0 per-name-night ledger")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    inp = Path(args.inp)
    if not inp.is_absolute():
        inp = PROJECT_ROOT / inp
    led = pd.read_parquet(inp)
    led["date"] = pd.to_datetime(led["date"]).dt.normalize()
    led = led.rename(columns={"overnight_return": "realized_r"})
    tickers = sorted(led["ticker"].unique())
    print(f"Ledger {inp.name}: {len(led):,} name-nights, {len(tickers)} tickers.")

    # Per-ticker feature panels (vectorized rolling; leak-safe by construction).
    parts = []
    for i, t in enumerate(tickers, 1):
        df = fetch_daily_range(t, start - timedelta(days=400), end)
        if df is None or df.empty:
            continue
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.DatetimeIndex(df.index).normalize().tz_localize(None)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        feats = _ticker_features(df)
        feats["ticker"] = t
        feats = feats.reset_index().rename(columns={"index": "date", "timestamp": "date"})
        parts.append(feats)
        if i % 100 == 0 or i == len(tickers):
            print(f"  features {i}/{len(tickers)} tickers", flush=True)
    feat = pd.concat(parts, ignore_index=True)
    feat["date"] = pd.to_datetime(feat["date"]).dt.normalize()

    # Join features → ledger on (date, ticker). Inner: keep name-nights with features.
    merged = led.merge(feat, on=["date", "ticker"], how="inner")

    # Calendar features.
    merged["dow"] = merged["date"].dt.dayofweek.astype(float)
    merged["dom"] = merged["date"].dt.day.astype(float)
    # turn-of-month: last 1 or first 3 trading days/month proxied by day-of-month.
    merged["is_turn_of_month"] = ((merged["dom"] <= 3) | (merged["dom"] >= 28)).astype(float)

    # SPY regime (join on date).
    reg = _spy_regime(start, end).reset_index().rename(columns={"index": "date", "timestamp": "date"})
    reg["date"] = pd.to_datetime(reg["date"]).dt.normalize()
    merged = merged.merge(reg, on="date", how="left")

    # Default deployment ranking: most-oversold first (short-term reversal thesis).
    merged["score"] = -merged["ret_5d"]
    merged["filled"] = True
    merged["year"] = merged["date"].dt.year
    merged = merged.rename(columns={"date": "trade_date"})

    # Drop rows missing core features (early history without full rolling windows).
    core = ["ret_5d", "vol_20d", "dollar_vol_20d", "rsi_2", "realized_r"]
    before = len(merged)
    merged = merged.dropna(subset=core)
    print(f"Captured {len(merged):,} name-nights (dropped {before-len(merged):,} "
          f"missing core features). Columns: {len(merged.columns)}")

    out = Path(args.out)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    merged.to_parquet(out)
    print(f"Wrote overnight capture → {out}")
    # quick sanity
    yr = merged.groupby("year")["realized_r"].agg(["count", "mean"])
    print("\nper-year (count, mean overnight R):")
    print(yr.to_string())


if __name__ == "__main__":
    main()
