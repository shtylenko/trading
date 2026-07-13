"""Chart-structure qualification for C1 (price/volume only).

Implements the consolidated chart checklist **except**:
  - Sector Map / Group (needs sector series — out of scope)
  - Adverse headlines (needs news feed — out of scope)

All functions are causal (no look-ahead): bar *t* uses only data ≤ *t*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructureConfig:
    enabled: bool = True
    # Rising SMA50: SMA50[t] > SMA50[t - slope_lookback]
    sma50_slope_lookback: int = 5
    # Higher high: max high over last hh_window > max high of prior hh_window
    hh_window: int = 20
    # Bars since local high (in lookback) must fall in [pb_min, pb_max]
    pullback_lookback: int = 15
    pullback_bars_min: int = 2
    pullback_bars_max: int = 5
    # Collapse guards
    max_1d_drop_pct: float = 0.06  # single-session close-to-close
    max_pullback_atr: float = 3.5  # depth from local high in ATR units
    min_pullback_atr: float = 0.15  # trivial dip filter
    # Volume dry-up: mean vol over last vol_pb_bars < ratio * mean vol of prior vol_adv_bars
    vol_pb_bars: int = 3
    vol_adv_bars: int = 5
    vol_contract_ratio: float = 1.0  # ≤ 1.0 means pullback vol ≤ advance vol
    # Support proximity (fraction of price)
    support_band: float = 0.03
    # Prior swing low: min low in [t - swing_lookback - pb_max, t - pb_min]
    swing_lookback: int = 15
    swing_low_buffer: float = 0.002  # allow 0.2% noise under swing low


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.astype(float).ewm(span=span, adjust=False, min_periods=span).mean()


def _days_since_rolling_high(high: np.ndarray, window: int) -> np.ndarray:
    """For each bar, bars since the max high in ``high[i-window+1 : i+1]`` (0 = today)."""
    n = len(high)
    out = np.full(n, np.nan, dtype=float)
    if n == 0:
        return out
    for i in range(window - 1, n):
        seg = high[i - window + 1 : i + 1]
        # last occurrence of max if ties (prefer more recent high)
        rev = seg[::-1]
        k_from_end = int(np.argmax(rev))
        out[i] = float(k_from_end)
    return out


def _prior_swing_low(
    low: np.ndarray,
    days_since_high: np.ndarray,
    *,
    swing_lookback: int,
    pb_min: int,
) -> np.ndarray:
    """Min low in the window *before* the current pullback started.

    For bar i with days_since_high d, use min(low[i-d-swing_lookback : i-d+1])
    i.e. structure lows ending at the local high bar.
    """
    n = len(low)
    out = np.full(n, np.nan, dtype=float)
    for i in range(n):
        d = days_since_high[i]
        if not np.isfinite(d):
            continue
        d = int(d)
        # local high index
        hi_i = i - d
        if hi_i < 0:
            continue
        left = hi_i - swing_lookback + 1
        if left < 0:
            left = 0
        if left > hi_i:
            continue
        out[i] = float(np.nanmin(low[left : hi_i + 1]))
    return out


def add_structure_columns(df: pd.DataFrame, cfg: StructureConfig | None = None) -> pd.DataFrame:
    """Append structure diagnostics used by ``structure_mask``."""
    cfg = cfg or StructureConfig()
    if df is None or df.empty:
        return df
    out = df.copy()
    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)

    if "sma50" not in out.columns:
        raise ValueError("add_structure_columns requires sma50 (run enrich_daily first)")
    if "sma20" not in out.columns:
        raise ValueError("add_structure_columns requires sma20")
    if "atr14" not in out.columns:
        raise ValueError("add_structure_columns requires atr14")

    out["ema20"] = ema(close, 20)

    # 1) Rising SMA50
    out["sma50_slope"] = out["sma50"] - out["sma50"].shift(cfg.sma50_slope_lookback)
    out["struct_rising_sma50"] = out["sma50_slope"] > 0

    # 2) Higher high vs prior window
    hh = high.rolling(cfg.hh_window, min_periods=cfg.hh_window).max()
    hh_prior = high.shift(cfg.hh_window).rolling(cfg.hh_window, min_periods=cfg.hh_window).max()
    out["struct_higher_high"] = hh > hh_prior

    # 3–4) Pullback length + depth from local high
    dsh = _days_since_rolling_high(high.to_numpy(), cfg.pullback_lookback)
    out["days_since_high"] = dsh
    out["struct_pullback_len"] = (
        (dsh >= cfg.pullback_bars_min) & (dsh <= cfg.pullback_bars_max)
    )

    # Local high price ≈ rolling max over lookback (consistent with days_since)
    local_high = high.rolling(cfg.pullback_lookback, min_periods=cfg.pullback_lookback).max()
    atr = out["atr14"].astype(float)
    depth_atr = (local_high - close) / atr.replace(0.0, np.nan)
    out["pullback_depth_atr"] = depth_atr

    ret_1d = close.pct_change()
    worst_1d = ret_1d.rolling(cfg.pullback_bars_max, min_periods=1).min()
    out["struct_not_collapse"] = (
        (worst_1d > -cfg.max_1d_drop_pct)
        & (depth_atr <= cfg.max_pullback_atr)
        & (depth_atr >= cfg.min_pullback_atr)
    )

    # 5) Volume contracts: recent pullback vol vs prior advance vol
    vol_pb = volume.rolling(cfg.vol_pb_bars, min_periods=cfg.vol_pb_bars).mean()
    vol_adv = (
        volume.shift(cfg.vol_pb_bars)
        .rolling(cfg.vol_adv_bars, min_periods=cfg.vol_adv_bars)
        .mean()
    )
    out["vol_pb"] = vol_pb
    out["vol_adv"] = vol_adv
    out["struct_vol_contract"] = vol_pb <= (cfg.vol_contract_ratio * vol_adv)

    # 6) Near support: SMA20 / EMA20 / SMA50 band
    band = cfg.support_band
    near_sma20 = ((close / out["sma20"] - 1.0).abs() <= band) | (
        (close >= out["sma20"]) & (close / out["sma20"] - 1.0 <= band)
    )
    # also allow slightly below MA (tagging support from above)
    near_sma20 = (close / out["sma20"] - 1.0).abs() <= band
    near_ema20 = (close / out["ema20"] - 1.0).abs() <= band
    near_sma50 = (close / out["sma50"] - 1.0).abs() <= band
    out["struct_near_support"] = near_sma20 | near_ema20 | near_sma50

    # 7) Not closed below prior structural swing low
    psl = _prior_swing_low(
        low.to_numpy(),
        dsh,
        swing_lookback=cfg.swing_lookback,
        pb_min=cfg.pullback_bars_min,
    )
    out["prior_swing_low"] = psl
    buf = 1.0 - cfg.swing_low_buffer
    # Pullback lows and close stay above prior swing low
    pb_low = low.rolling(cfg.pullback_bars_max, min_periods=1).min()
    out["struct_above_swing_low"] = (
        (close >= psl * buf) & (pb_low >= psl * buf) & np.isfinite(psl)
    )

    # Combined (all structure flags)
    out["struct_ok"] = (
        out["struct_rising_sma50"].fillna(False)
        & out["struct_higher_high"].fillna(False)
        & out["struct_pullback_len"].fillna(False)
        & out["struct_not_collapse"].fillna(False)
        & out["struct_vol_contract"].fillna(False)
        & out["struct_near_support"].fillna(False)
        & out["struct_above_swing_low"].fillna(False)
    )
    return out


def structure_mask(df: pd.DataFrame, cfg: StructureConfig | None = None) -> pd.Series:
    """Boolean mask: all structure checks pass."""
    cfg = cfg or StructureConfig()
    if not cfg.enabled:
        return pd.Series(True, index=df.index)
    if "struct_ok" not in df.columns:
        df = add_structure_columns(df, cfg)
        return df["struct_ok"].fillna(False)
    return df["struct_ok"].fillna(False)
