"""Daily technical indicators for C1 screens (vectorized, no look-ahead)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder RSI using RMA (alpha = 1/period) on close-to-close changes.

    First non-null value requires ``period`` completed change observations
    (i.e. ``period + 1`` closes). NaN until then.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder RMA ≡ ewm(alpha=1/period, adjust=False) after seed;
    # ewm with min_periods=period matches common platform behavior.
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss == 0 and avg_gain > 0, RSI = 100
    both_zero = (avg_gain == 0.0) & (avg_loss == 0.0)
    only_gain = (avg_loss == 0.0) & (avg_gain > 0.0)
    rsi = rsi.mask(only_gain, 100.0)
    rsi = rsi.mask(both_zero, 50.0)
    return rsi


def avg_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    return volume.astype(float).rolling(window=window, min_periods=window).mean()


def relative_volume(volume: pd.Series, avg_vol: pd.Series) -> pd.Series:
    return volume.astype(float) / avg_vol.replace(0.0, np.nan)


def performance(close: pd.Series, lookback: int) -> pd.Series:
    """Simple return over ``lookback`` sessions: close/close.shift(n) - 1."""
    prior = close.shift(lookback)
    return close.astype(float) / prior.replace(0.0, np.nan) - 1.0


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder ATR (RMA of true range)."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def enrich_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Add C1 indicator columns to a daily OHLCV frame.

    Expects columns: open, high, low, close, volume.
    Index should be chronological (tz-aware or naive dates ok).
    Returns a copy with indicator columns appended.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    cols = {c.lower(): c for c in out.columns}
    for need in ("close", "volume"):
        if need not in cols and need not in out.columns:
            raise ValueError(f"enrich_daily requires '{need}' column")
    close = out["close"] if "close" in out.columns else out[cols["close"]]
    volume = out["volume"] if "volume" in out.columns else out[cols["volume"]]
    high = out["high"] if "high" in out.columns else out.get(cols.get("high", "high"))
    low = out["low"] if "low" in out.columns else out.get(cols.get("low", "low"))
    close = close.astype(float)
    volume = volume.astype(float)
    if high is None or low is None:
        raise ValueError("enrich_daily requires high/low columns for ATR")
    high = high.astype(float)
    low = low.astype(float)

    out["sma5"] = sma(close, 5)
    out["sma20"] = sma(close, 20)
    out["sma50"] = sma(close, 50)
    out["sma200"] = sma(close, 200)
    out["rsi2"] = wilder_rsi(close, 2)
    out["rsi14"] = wilder_rsi(close, 14)
    out["atr14"] = atr(high, low, close, 14)
    out["avg_vol_20"] = avg_volume(volume, 20)
    out["relvol"] = relative_volume(volume, out["avg_vol_20"])
    out["perf_5d"] = performance(close, 5)
    out["perf_21d"] = performance(close, 21)
    out["perf_126d"] = performance(close, 126)
    out["sma20_ext"] = close / out["sma20"].replace(0.0, np.nan) - 1.0
    return out
