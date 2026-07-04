"""Shared Stocks-in-Play candidate filtering used by the `o` releases.

Both o02 (SSRN v1 replication) and o03 (Phase v2 ML + pullback entry) apply
the same candidate gauntlet; keeping it in one place prevents the filter
logic from silently diverging between releases. Each release configures its
own ranking, selection size, and signal construction on top.

All price-scale inputs are expected in RAW (unadjusted) prices, consistent
with the intraday bars (see ``data.market_data.fetch_daily_context``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trading.lab.research.filters import (
    daily_atr_14,
    first_regular_5m_bar,
    green_first_candle,
    has_split_like_jump,
    min_avg_daily_volume,
)


@dataclass
class SipBaseFeatures:
    rv: float
    daily_atr_14: float
    mean_opening_volume: float
    avg_vol_14: float
    prior_close: float
    prior_day_ret: float
    gap_pct: float
    first_open: float
    first_high: float
    first_low: float
    first_close: float
    first_volume: float
    or_start_minute: int  # 0 = the 09:30 bar; >0 = opening bar was shifted


def build_sip_base(
    ticker: str,
    bars_5m: pd.DataFrame | None,
    daily: pd.DataFrame | None,
    hist_5m: pd.DataFrame | None,
    trade_date: date,
    min_open_price: float = 5.0,
    min_avg_volume: float = 1_000_000,
    min_atr: float = 0.50,
    min_rv: float = 2.0,
    min_hist_days: int = 10,
    candle: str = "green",
) -> SipBaseFeatures | None:
    """Apply the Stocks-in-Play v1 filter gauntlet for one ticker.

    Returns the base feature set, or None if any filter rejects the ticker:
    opening price > $5, 14-day avg volume >= 1M, 14-day Wilder ATR > $0.50,
    first 5-minute candle direction per ``candle`` ("green" long bias /
    "red" short bias / "any"), RV >= 2.0, and no split-like jump inside
    the trailing window (raw-price consistency guard).
    """
    first_bar = first_regular_5m_bar(bars_5m)
    if first_bar is None or daily is None or daily.empty:
        return None
    first_ts, first = first_bar

    open_price = float(first["open"])
    if open_price <= min_open_price:
        return None
    if not min_avg_daily_volume(daily, min_avg_volume, lookback=14, trade_date=trade_date):
        return None
    if has_split_like_jump(daily, trade_date=trade_date, open_price=open_price):
        return None
    atr = daily_atr_14(daily, period=14, trade_date=trade_date)
    if atr is None or atr <= min_atr:
        return None
    if candle == "green":
        if not green_first_candle(bars_5m):
            return None
    elif candle == "red":
        if float(first["close"]) >= float(first["open"]):
            return None
    elif candle != "any":
        raise ValueError(f"Unknown candle gate: {candle!r}")

    if hist_5m is None or hist_5m.empty:
        return None
    hist_ny = hist_5m.tz_convert("America/New_York") if hist_5m.index.tz is not None else hist_5m
    # Use a broad window (09:30-09:35) to catch both open-stamped (09:30)
    # and close-stamped (09:35) bars. The or_start_minute field on the
    # returned features records which stamping was used for today's bar
    # so consumers can detect and filter setups with shifted opening ranges
    # (see peer review F-04).
    opening_bars = hist_ny.between_time("09:30", "09:35", inclusive="both")
    opening_bars = opening_bars.groupby(opening_bars.index.date).first()
    if len(opening_bars) < min_hist_days:
        return None
    mean_opening_volume = float(opening_bars["volume"].mean())
    if mean_opening_volume <= 0:
        return None

    first_vol = float(first.get("volume", 0.0))
    rv = first_vol / mean_opening_volume
    if rv < min_rv:
        return None

    hist_daily = daily[daily.index.date < trade_date]
    closes = hist_daily["close"].astype(float)
    if len(closes) < 2:
        return None
    prior_close = float(closes.iloc[-1])
    prior_day_ret = float(closes.iloc[-1] / closes.iloc[-2] - 1.0)
    avg_vol_14 = float(hist_daily["volume"].tail(14).mean())

    return SipBaseFeatures(
        rv=rv,
        daily_atr_14=float(atr),
        mean_opening_volume=mean_opening_volume,
        avg_vol_14=avg_vol_14,
        prior_close=prior_close,
        prior_day_ret=prior_day_ret,
        gap_pct=(open_price - prior_close) / prior_close,
        first_open=open_price,
        first_high=float(first["high"]),
        first_low=float(first["low"]),
        first_close=float(first["close"]),
        first_volume=first_vol,
        or_start_minute=int(first_ts.hour * 60 + first_ts.minute - (9 * 60 + 30)),
    )
