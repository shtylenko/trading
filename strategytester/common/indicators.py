"""Vectorized daily indicators for short-hold strategy research.

Self-contained (numpy/pandas only). All indicators are causal — value at bar
``i`` uses only bars ``<= i`` — so a signal read at close of bar ``i`` can be
acted on at the open of bar ``i+1`` without look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- moving avgs
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, min_periods=n, adjust=False).mean()


# ---------------------------------------------------------------- volatility
def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    pc = close.shift(1)
    return pd.concat(
        [(high - low).abs(), (high - pc).abs(), (low - pc).abs()], axis=1
    ).max(axis=1)


def atr(high, low, close, n: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


# ---------------------------------------------------------------- oscillators
def wilder_rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.astype(float).diff()
    gain = d.clip(lower=0.0)
    loss = (-d).clip(lower=0.0)
    ag = gain.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    al = loss.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    rs = ag / al.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.mask((al == 0) & (ag > 0), 100.0)
    rsi = rsi.mask((al == 0) & (ag == 0), 50.0)
    return rsi


def adx(high, low, close, n: int = 14) -> pd.Series:
    """Wilder ADX(n)."""
    up = high.diff()
    dn = -low.diff()
    plus_dm = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    tr = true_range(high, low, close)
    atr_n = tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean() / atr_n
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean() / atr_n
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


# ---------------------------------------------------------------- MACD 3-10-16
def macd_3_10_16(close: pd.Series):
    """Linda Raschke 3/10 oscillator (SMA-based). Returns (fast, signal, hist)."""
    fast = sma(close, 3) - sma(close, 10)
    signal = sma(fast, 16)
    return fast, signal, fast - signal


# ---------------------------------------------------------------- bands
def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper = mid + k * sd
    lower = mid - k * sd
    width = (upper - lower) / mid.replace(0.0, np.nan)
    return mid, upper, lower, width


def keltner(high, low, close, n: int = 20, k: float = 1.5):
    mid = ema(close, n)
    rng = atr(high, low, close, n)
    return mid, mid + k * rng, mid - k * rng


# ---------------------------------------------------------------- TTM momentum
def ttm_momentum(high, low, close, n: int = 20) -> pd.Series:
    """John Carter TTM momentum: linreg of (close - baseline) over n bars.

    baseline = avg( (donchian mid over n), sma(close,n) ).
    """
    donch_mid = (high.rolling(n, min_periods=n).max() + low.rolling(n, min_periods=n).min()) / 2.0
    base = (donch_mid + sma(close, n)) / 2.0
    delta = (close - base).to_numpy(dtype=float)
    out = np.full(len(delta), np.nan)
    x = np.arange(n, dtype=float)
    x = x - x.mean()
    denom = (x * x).sum()
    for i in range(n - 1, len(delta)):
        y = delta[i - n + 1 : i + 1]
        if np.isnan(y).any():
            continue
        slope = (x * (y - y.mean())).sum() / denom
        intercept = y.mean()
        out[i] = intercept + slope * x[-1]  # value at last bar of linreg
    return pd.Series(out, index=close.index)


# ---------------------------------------------------------------- swings
def rolling_swing_low(low: pd.Series, left: int = 3, right: int = 3) -> pd.Series:
    """Confirmed pivot low value carried forward (causal: known `right` bars later)."""
    n = len(low)
    lv = low.to_numpy(dtype=float)
    out = np.full(n, np.nan)
    last = np.nan
    for i in range(n):
        p = i - right
        if p - left >= 0 and p + right < n:
            win = lv[p - left : p + right + 1]
            if np.isfinite(win).all() and lv[p] == win.min():
                last = lv[p]
        out[i] = last
    return pd.Series(out, index=low.index)


def rolling_swing_high(high: pd.Series, left: int = 3, right: int = 3) -> pd.Series:
    n = len(high)
    hv = high.to_numpy(dtype=float)
    out = np.full(n, np.nan)
    last = np.nan
    for i in range(n):
        p = i - right
        if p - left >= 0 and p + right < n:
            win = hv[p - left : p + right + 1]
            if np.isfinite(win).all() and hv[p] == win.max():
                last = hv[p]
        out[i] = last
    return pd.Series(out, index=high.index)


def perf(close: pd.Series, n: int) -> pd.Series:
    return close / close.shift(n) - 1.0


# ---------------------------------------------------------------- enrich
def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Attach all indicators used across the 13 short-hold strategies.

    Expects lowercase columns open/high/low/close/volume, chronological index.
    """
    o, h, l, c, v = (df[x].astype(float) for x in ("open", "high", "low", "close", "volume"))
    out = df.copy()

    # trend / MAs
    out["ema9"] = ema(c, 9)
    out["ema21"] = ema(c, 21)
    out["ema20"] = ema(c, 20)
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)

    # vol / range
    out["atr14"] = atr(h, l, c, 14)
    out["avg_vol20"] = v.rolling(20, min_periods=20).mean()
    out["relvol"] = v / out["avg_vol20"].replace(0.0, np.nan)
    out["range"] = h - l
    out["ret1"] = c.pct_change()
    out["gap"] = o / c.shift(1) - 1.0
    out["close_pos"] = (c - l) / (h - l).replace(0.0, np.nan)  # 1=close at high

    # momentum
    out["rsi2"] = wilder_rsi(c, 2)
    out["rsi14"] = wilder_rsi(c, 14)
    out["adx14"] = adx(h, l, c, 14)
    out["perf21"] = perf(c, 21)
    out["perf63"] = perf(c, 63)
    out["perf126"] = perf(c, 126)

    # MACD 3-10-16
    out["macd_fast"], out["macd_sig"], out["macd_hist"] = macd_3_10_16(c)

    # Bollinger + bandwidth percentile
    out["bb_mid"], out["bb_up"], out["bb_lo"], out["bb_width"] = bollinger(c, 20, 2.0)
    out["bb_width_min126"] = out["bb_width"].rolling(126, min_periods=60).min()

    # Keltner + TTM squeeze flag
    kmid, kup, klo = keltner(h, l, c, 20, 1.5)
    out["kc_up"], out["kc_lo"] = kup, klo
    out["ttm_squeeze_on"] = (out["bb_up"] < kup) & (out["bb_lo"] > klo)
    out["ttm_mom"] = ttm_momentum(h, l, c, 20)

    # swings (3/3 pivots)
    out["swing_low"] = rolling_swing_low(l, 3, 3)
    out["swing_high"] = rolling_swing_high(h, 3, 3)
    # 20-day prior high/low for base/impulse detection
    out["hh20"] = h.rolling(20, min_periods=20).max()
    out["ll20"] = l.rolling(20, min_periods=20).min()
    out["hh252"] = h.rolling(252, min_periods=150).max()

    return out
