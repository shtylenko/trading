#!/usr/bin/env python3
"""Offline in-process validation of the o03 release on a real trading day.

Builds a StrategyContext for 2024-05-29 from the cached 1-minute data
(resampled to 5-minute bars where the release expects them), then runs
build_candidates -> build_signal -> simulate_pullback_limit_long exactly as
the runner pipeline would, and prints the resulting trades.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from trading.lab.core.execution import simulate_pullback_limit_long
from trading.lab.core.models import ExecutionConfig, StrategyContext
from trading.lab.strategies import get_release_class
from trading.lab.strategies.stocks_in_play_orb.research.build_dataset import load_ticker_year

TRADE_DATE = date(2024, 5, 29)
TICKERS = ["ANF", "CHWY", "GAP", "INTU", "AAPL", "NVDA", "DKS", "AAL", "M", "KSS"]


def to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    g = df_1m.set_index("timestamp")
    out = g.resample("5min", label="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["open"])


def daily_from_1m(df_1m: pd.DataFrame) -> pd.DataFrame:
    g = df_1m.groupby("day")
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "volume": g["volume"].sum(),
        }
    )
    out.index = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in out.index])
    return out


def main() -> None:
    bars_5m, daily, extended_1m, historical_5m = {}, {}, {}, {}
    hist_start = TRADE_DATE - timedelta(days=30)
    for t in TICKERS + ["SPY"]:
        raw = load_ticker_year(t)
        if raw is None:
            print(f"no 1m data for {t}")
            continue
        day_mask = raw["day"] == TRADE_DATE
        day_df = raw[day_mask]
        if day_df.empty:
            continue
        five = to_5m(day_df)
        d = daily_from_1m(raw[raw["day"] <= TRADE_DATE])
        if t == "SPY":
            spy_5m, spy_daily = five, d
            continue
        bars_5m[t] = five
        daily[t] = d
        one = day_df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        extended_1m[t] = one
        hist = raw[(raw["day"] >= hist_start) & (raw["day"] < TRADE_DATE)]
        historical_5m[t] = to_5m(hist)

    context = StrategyContext(
        trade_date=TRADE_DATE,
        release_id="o03",
        testset="offline_validation",
        bars_5m=bars_5m,
        daily=daily,
        extended_1m=extended_1m,
        historical_5m=historical_5m,
        spy_5m=spy_5m,
        spy_daily=spy_daily,
    )

    release = get_release_class("o03")()
    cfg = ExecutionConfig()
    candidates = release.build_candidates(context)
    print(f"{len(candidates)} candidates")
    for cand in candidates:
        prob = cand.features.get("probability_score")
        print(
            f"  #{cand.rank} {cand.ticker} score={cand.score:.3f} rv={cand.features['rv']:.2f} "
            f"prob={prob if prob is None else round(prob, 3)}"
        )
        signal = release.build_signal(context, cand)
        if signal is None:
            print("    no signal")
            continue
        trade = simulate_pullback_limit_long(
            extended_1m[cand.ticker], signal, release.exit_cutoff(context), cfg
        )
        if trade is None:
            print("    no trade")
            continue
        r = (
            (trade.exit_price - trade.entry_price) / signal.risk_per_share
            if trade.entry_price is not None
            else None
        )
        print(
            f"    trigger={signal.entry_trigger:.2f} limit={signal.metadata['pullback_limit']:.2f} "
            f"stop={signal.stop_price:.2f} -> {trade.exit_reason} "
            f"entry={trade.entry_price} exit={trade.exit_price} "
            f"pnl%={trade.pnl_pct:.2f} R={'n/a' if r is None else f'{r:+.2f}'}"
        )


if __name__ == "__main__":
    main()
