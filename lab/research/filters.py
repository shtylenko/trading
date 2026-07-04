from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd


def min_price(daily: pd.DataFrame | None, threshold: float = 5.0, trade_date: date | None = None) -> bool:
    if daily is None or daily.empty or "close" not in daily:
        return False
    df = daily
    if trade_date is not None:
        df = daily[daily.index.date < trade_date]
    if df.empty:
        return False
    return float(df["close"].iloc[-1]) >= threshold


def min_avg_daily_volume(daily: pd.DataFrame | None, threshold: float = 1_000_000, lookback: int = 14, trade_date: date | None = None) -> bool:
    if daily is None or daily.empty or "volume" not in daily:
        return False
    df = daily
    if trade_date is not None:
        df = daily[daily.index.date < trade_date]
    sample = df.tail(lookback)
    if sample.empty:
        return False
    return float(sample["volume"].mean()) >= threshold


def green_first_candle(bars_5m: pd.DataFrame | None) -> bool:
    first = first_regular_5m_candle(bars_5m)
    if first is None:
        return False
    return float(first["close"]) > float(first["open"])


def first_regular_5m_candle(bars_5m: pd.DataFrame | None):
    """DEPRECATED: use first_regular_5m_bar() instead.

    Returns just the first bar's Series (without timestamp).
    Kept for backward compatibility with o01 and d01.
    """
    bar = first_regular_5m_bar(bars_5m)
    if bar is None:
        return None
    return bar[1]


def first_regular_5m_bar(bars_5m: pd.DataFrame | None):
    if bars_5m is None or bars_5m.empty:
        return None
    regular = bars_5m.between_time("09:30", "09:34", inclusive="both")
    if regular.empty:
        regular = bars_5m.between_time("09:30", "09:35", inclusive="both")
    if regular.empty:
        return None
    return regular.index[0], regular.iloc[0]


def opening_range_width_pct(bars_5m: pd.DataFrame | None) -> float | None:
    first = first_regular_5m_candle(bars_5m)
    if first is None:
        return None
    high = float(first["high"])
    low = float(first["low"])
    close = float(first["close"])
    if close <= 0:
        return None
    return (high - low) / close * 100.0


def daily_atr_14(daily: pd.DataFrame | None, period: int = 14, trade_date: date | None = None) -> float | None:
    if daily is None or daily.empty:
        return None
    df = daily
    if trade_date is not None:
        df = daily[daily.index.date < trade_date]
    if len(df) < period + 1:
        return None
    
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr_clean = tr.dropna()
    if len(tr_clean) < period:
        return None
    tr_vals = tr_clean.values
    atr = np.zeros_like(tr_vals)
    atr[period - 1] = np.mean(tr_vals[:period])
    for i in range(period, len(tr_vals)):
        atr[i] = (atr[i - 1] * (period - 1) + tr_vals[i]) / period
    return float(atr[-1])


def has_split_like_jump(
    daily: pd.DataFrame | None,
    trade_date: date | None = None,
    lookback: int = 15,
    threshold: float = 0.40,
    open_price: float | None = None,
) -> bool:
    """True when the trailing window likely spans a split or data glitch.

    With raw (unadjusted) daily bars, a split shows up as a >40% single-day
    close-to-close jump; any trailing statistic (ATR, average volume) that
    spans it is in mixed price scales and must not be traded on. Also flags
    a >40% gap between *open_price* (today's raw open) and the prior close.
    """
    if daily is None or daily.empty or "close" not in daily:
        return False
    df = daily
    if trade_date is not None:
        df = daily[daily.index.date < trade_date]
    closes = df["close"].astype(float).tail(lookback)
    if len(closes) < 2:
        return False
    rets = closes.pct_change().abs().dropna()
    if not rets.empty and float(rets.max()) > threshold:
        return True
    if open_price is not None:
        prior_close = float(closes.iloc[-1])
        if prior_close > 0 and abs(open_price - prior_close) / prior_close > threshold:
            return True
    return False


COMMON_FILTERS = {
    "min_price_5": min_price,
    "min_avg_daily_volume_1m": min_avg_daily_volume,
    "green_first_candle": green_first_candle,
    "daily_atr_14": daily_atr_14,
}
