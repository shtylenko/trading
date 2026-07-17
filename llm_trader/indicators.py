"""Shared indicator calculations.

Central place for common technical computations used by the scanner (patterns)
and replay tooling. This eliminates duplication of VWAP, time-zone handling,
and session enrichment logic.

All functions are pure where possible and work on pandas DataFrames with
OHLCV data (any tz on index; functions normalize to ET internally when needed).
"""

from __future__ import annotations

from datetime import date
import math
from typing import Optional

import numpy as np
import pandas as pd


# A daily swing stream is actionable only when every one of these fields was
# computed from sufficient prior history.  Keep the contract here so replay,
# recorder, and batch audit use the same definition.
DAILY_REPLAY_REQUIRED_INDICATORS = (
    "sma20",
    "sma50",
    "sma200",
    "atr14",
    "rvol",
    "above_sma20",
    "above_sma50",
    "above_sma200",
    "sma50_rising",
)

# Replay presents this many completed bars before the setup bar. The scanner
# must prove this window is fully indicator-complete before publishing a plan.
DAILY_REPLAY_PLAN_LOOKBACK_BARS = 40


def daily_replay_indicators_available(df: pd.DataFrame) -> bool:
    """Return whether every required daily-replay field is finite over ``df``.

    A valid setup-day SMA200 is insufficient when earlier visible planning bars
    lack it. Missing values are a data-integrity failure, never a permission to
    emit a partial-context plan.
    """
    if df is None or df.empty:
        return False
    for field in DAILY_REPLAY_REQUIRED_INDICATORS:
        if field not in df:
            return False
        values = df[field]
        unavailable = values.isna()
        if not pd.api.types.is_bool_dtype(values):
            numeric = pd.to_numeric(values, errors="coerce")
            unavailable = unavailable | ~numeric.map(math.isfinite)
        if bool(unavailable.any()):
            return False
    return True


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Typical-price volume-weighted average price over the whole frame.

    Uses (H+L+C)/3 * volume, cumulative. Handles zero-volume bars gracefully.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_pv = (typical * df["volume"]).cumsum()
    cum_v = df["volume"].cumsum().replace(0, np.nan)
    return cum_pv / cum_v


def normalize_to_et(df: pd.DataFrame, day: Optional[date] = None) -> pd.DataFrame:
    """Return a copy with DatetimeIndex localized/converted to America/New_York.

    If ``day`` is provided, filter to rows whose .date() == day (after tz conversion).
    The input may have tz-naive or any tz.
    """
    out = df.sort_index().copy() if not df.index.is_monotonic_increasing else df.copy()
    if out.index.tz is None:
        out.index = out.index.tz_localize("America/New_York")
    else:
        out.index = out.index.tz_convert("America/New_York")
    if day is not None:
        out = out[out.index.date == day]
    return out


def add_volume_average(
    df: pd.DataFrame,
    window: int = 5,
    min_periods: int = 1,
    out_col: str = "vol_avg",
) -> pd.DataFrame:
    """Add a column with rolling mean of prior volume (shifted to avoid lookahead)."""
    out = df.copy()
    out[out_col] = out["volume"].shift(1).rolling(window, min_periods=min_periods).mean()
    return out


def macd(
    close: pd.Series,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Standard MACD on a close series (all backward-looking EMAs, no look-ahead).

    Returns a frame with columns ``macd`` (fast EMA − slow EMA), ``macd_signal``
    (EMA of the MACD line), and ``macd_hist`` (macd − signal). Cameron uses this as
    a trend-confirmation filter (§4.6): MACD line above signal + expanding histogram
    = momentum intact; never enter against it.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def enrich_1min_for_replay(
    df: pd.DataFrame,
    *,
    rvol_bar_window: int = 20,
    rvol_min_periods: int = 5,
) -> pd.DataFrame:
    """Enrich a 1-minute RTH (or session) frame with the indicators the replay
    and simulator use:

    - vwap (session)
    - ema9, ema20 (on close)
    - macd, macd_signal, macd_hist (12/26/9 trend-confirmation filter)
    - cum_vol
    - session_high (running high)
    - new_high (True when high > all prior highs)
    - rvol_bar (current vol / trailing N-bar avg, shifted)
    - above_vwap (bool)

    Returns a new DataFrame. Expects df to already be filtered/sorted for the day
    in ET if desired by caller.
    """
    out = df.copy()
    out["vwap"] = session_vwap(out)
    out["ema9"] = out["close"].ewm(span=9, adjust=False).mean()
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    macd_df = macd(out["close"])
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["macd_signal"]
    out["macd_hist"] = macd_df["macd_hist"]
    out["cum_vol"] = out["volume"].cumsum()
    session_high = out["high"].cummax()
    out["session_high"] = session_high
    prev_max = session_high.shift(1)
    out["new_high"] = out["high"] > prev_max.fillna(float("-inf"))
    vol_base = out["volume"].shift(1).rolling(
        rvol_bar_window, min_periods=rvol_min_periods
    ).mean()
    out["rvol_bar"] = out["volume"] / vol_base
    out["above_vwap"] = out["close"] >= out["vwap"]
    return out


def prepare_detection_frame(
    df: pd.DataFrame, day: date, vol_avg_window: int = 5
) -> pd.DataFrame:
    """Prepare a day's frame for detect_from_frame style logic.

    - Normalizes to ET and filters to the day
    - Adds 'vwap' and 'vol_avg' (using the window for breakout volume baseline)
    Returns the enriched frame (or empty).
    """
    day_df = normalize_to_et(df, day=day)
    if day_df.empty:
        return day_df
    day_df = day_df.assign(vwap=session_vwap(day_df))
    day_df = add_volume_average(day_df, window=vol_avg_window, out_col="vol_avg")
    return day_df


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average (min_periods=window — undefined until fully warm)."""
    return series.rolling(window, min_periods=window).mean()


def atr(
    df: pd.DataFrame,
    period: int = 14,
    *,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> pd.Series:
    """Average True Range (Wilder-style smoothing via EWM alpha=1/period).

    True range = max(high-low, |high-prev_close|, |low-prev_close|).
    Uses ``ewm(alpha=1/period, adjust=False)`` which matches Wilder's recursive
    ATR closely enough for stop placement. Pure and look-ahead-safe (uses only
    past closes via shift).
    """
    high = df[high_col].astype(float)
    low = df[low_col].astype(float)
    close = df[close_col].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def enrich_daily_for_replay(
    df: pd.DataFrame,
    *,
    volume_lookback: int = 20,
    sma50_rising_lookback: int = 20,
) -> pd.DataFrame:
    """Enrich a daily OHLCV frame for multi-day swing replay.

    Adds SMA20/50/200, ATR(14), and simple volume averages used by cup-handle
    and other swing families. No look-ahead: rolling/EWM only.
    """
    out = df.copy()
    out["sma20"] = sma(out["close"], 20)
    out["sma50"] = sma(out["close"], 50)
    out["sma200"] = sma(out["close"], 200)
    out["atr14"] = atr(out, 14)
    if volume_lookback < 2:
        raise ValueError("volume_lookback must be at least 2")
    if sma50_rising_lookback < 1:
        raise ValueError("sma50_rising_lookback must be positive")
    out["vol_avg20"] = out["volume"].shift(1).rolling(
        volume_lookback, min_periods=min(5, volume_lookback)
    ).mean()
    out["rvol"] = out["volume"] / out["vol_avg20"]
    # rising 50 SMA: current > value 20 bars ago
    out["sma50_rising"] = out["sma50"] > out["sma50"].shift(
        sma50_rising_lookback
    )
    out["above_sma20"] = out["close"] > out["sma20"]
    out["above_sma50"] = out["close"] > out["sma50"]
    out["above_sma200"] = out["close"] > out["sma200"]
    return out
