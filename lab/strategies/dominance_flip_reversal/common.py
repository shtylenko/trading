"""Shared indicator and setup-detection helpers for dominance_flip_reversal.

The family trades long-only intraday capitulation reversals on 5-minute
bars. The detection pipeline mirrors the four phases in the family spec:

1. Price stretch  — consecutive bars trading entirely below the rolling
   mean (no "mean touch") for a minimum stretch length.
2. RSI divergence — price makes a lower low inside the stretch while the
   Wilder RSI makes a higher low (momentum decay into the flush).
3. Z-score extreme — the close-vs-mean z-score breaches the negative
   extreme threshold, with a volume-z climax on the extreme-low bar
   standing in for the "liq-flow" confirmation.
4. The flip back  — the z-score crosses back above the extreme threshold,
   which is the entry signal bar.

All functions operate on a single ticker's regular-hours 5-minute OHLCV
DataFrame (NY-indexed) and use only same-day data; the first usable flip
therefore cannot occur before roughly bar ``sma_period + min_stretch_bars``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_flip_indicators(
    bars_5m: pd.DataFrame,
    sma_period: int = 20,
    rsi_period: int = 14,
    vol_period: int = 20,
    atr_period: int = 14,
) -> pd.DataFrame:
    """Per-bar indicator frame: sma, z, rsi, vol_z, atr.

    Early bars carry NaN until each rolling window is seeded; callers must
    treat NaN as "indicator not yet available", never as zero.
    """
    close = bars_5m["close"].astype(float)
    high = bars_5m["high"].astype(float)
    low = bars_5m["low"].astype(float)
    volume = bars_5m["volume"].astype(float)

    sma = close.rolling(sma_period).mean()
    sd = close.rolling(sma_period).std(ddof=0)
    z = (close - sma) / sd.replace(0.0, np.nan)

    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    rs = gain / loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(loss > 0.0, 100.0).where(gain.notna() & loss.notna())

    vol_mean = volume.rolling(vol_period).mean()
    vol_sd = volume.rolling(vol_period).std(ddof=0)
    vol_z = (volume - vol_mean) / vol_sd.replace(0.0, np.nan)

    close_prev = close.shift(1)
    tr = pd.concat(
        [high - low, (high - close_prev).abs(), (low - close_prev).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / atr_period, adjust=False, min_periods=atr_period).mean()

    return pd.DataFrame({"sma": sma, "z": z, "rsi": rsi, "vol_z": vol_z, "atr": atr}, index=bars_5m.index)


def detect_dominance_flip(
    bars_5m: pd.DataFrame | None,
    *,
    z_extreme: float = 2.0,
    min_stretch_bars: int = 12,
    min_divergence_separation: int = 3,
    vol_climax_z: float = 1.0,
    stop_atr_mult: float = 0.5,
    sma_period: int = 20,
    rsi_period: int = 14,
    vol_period: int = 20,
    atr_period: int = 14,
    flip_after=None,
) -> dict | None:
    """Scan one ticker-day for the first long dominance-flip reversal setup.

    Returns None when no bar satisfies all four phases, otherwise a dict of
    setup levels and diagnostic features keyed for Candidate/Signal reuse.

    ``flip_after`` (optional timestamp): only accept a flip bar strictly
    after this time. Used for warm-started runs where ``bars_5m`` is the
    trade day prepended with seeding history — the stretch/divergence may
    reach back into the seed, but the flip (and hence the trade) must occur
    on the trade day. ``None`` keeps the same-day-only f01 behaviour.
    """
    if bars_5m is None or bars_5m.empty or len(bars_5m) <= sma_period:
        return None

    ind = compute_flip_indicators(bars_5m, sma_period, rsi_period, vol_period, atr_period)
    high = bars_5m["high"].astype(float).to_numpy()
    low = bars_5m["low"].astype(float).to_numpy()
    sma = ind["sma"].to_numpy()
    z = ind["z"].to_numpy()
    rsi = ind["rsi"].to_numpy()
    vol_z = ind["vol_z"].to_numpy()
    atr = ind["atr"].to_numpy()

    n = len(bars_5m)
    for t in range(1, n):
        if not (np.isfinite(z[t - 1]) and np.isfinite(z[t]) and np.isfinite(atr[t]) and np.isfinite(sma[t])):
            continue
        # Warm-start guard: the flip itself must land on the trade day.
        if flip_after is not None and bars_5m.index[t] <= flip_after:
            continue
        # Phase 4 gate first (cheapest): z crosses back up through -z_extreme.
        if not (z[t - 1] <= -z_extreme and z[t] > -z_extreme):
            continue

        # Phase 1: bars since the last mean touch (bar high tagged the SMA).
        # Bars without a seeded SMA count as a touch — the stretch must be
        # fully observable.
        touch = -1
        for i in range(t - 1, -1, -1):
            if not np.isfinite(sma[i]) or high[i] >= sma[i]:
                touch = i
                break
        stretch_start = touch + 1
        stretch_bars = t - stretch_start
        if stretch_bars < min_stretch_bars:
            continue

        window_low = low[stretch_start:t]
        ext = stretch_start + int(np.argmin(window_low))
        if not (np.isfinite(rsi[ext]) and np.isfinite(vol_z[ext])):
            continue

        # Phase 3: liq-flow confirmation — climactic volume on the extreme bar.
        if vol_z[ext] < vol_climax_z:
            continue

        # Phase 2: bullish RSI divergence — an earlier swing low inside the
        # stretch with a higher price low but a lower RSI than the extreme.
        prior_end = ext - min_divergence_separation
        if prior_end <= stretch_start:
            continue
        prior = stretch_start + int(np.argmin(low[stretch_start:prior_end]))
        if not np.isfinite(rsi[prior]):
            continue
        if not (low[ext] < low[prior] and rsi[ext] > rsi[prior]):
            continue

        entry_trigger = float(high[t])
        stop_price = float(low[ext]) - stop_atr_mult * float(atr[t])
        target_price = float(sma[t])  # mean-touch exit
        if not (stop_price < entry_trigger < target_price):
            continue

        window_z = z[stretch_start:t]
        finite_z = window_z[np.isfinite(window_z)]
        return {
            "flip_time": bars_5m.index[t],
            "entry_trigger": entry_trigger,
            "stop_price": stop_price,
            "target_price": target_price,
            "z_at_flip": float(z[t]),
            "z_prev": float(z[t - 1]),
            "z_min": float(finite_z.min()) if finite_z.size else float(z[t - 1]),
            "stretch_bars": int(stretch_bars),
            "extreme_low": float(low[ext]),
            "extreme_time": bars_5m.index[ext],
            "vol_z_extreme": float(vol_z[ext]),
            "rsi_extreme": float(rsi[ext]),
            "rsi_prior_low": float(rsi[prior]),
            "prior_low": float(low[prior]),
            "prior_low_time": bars_5m.index[prior],
            "atr_5m": float(atr[t]),
            "sma_at_flip": float(sma[t]),
        }
    return None
