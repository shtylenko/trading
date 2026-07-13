"""C2 daily features: base pivot/depth + 52w distance + optional SPY RS."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.indicators import enrich_daily, performance


def _base_features(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    atr: np.ndarray,
    lookback: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Causal base stats using bars [i-lookback, i) — excludes today.

    Returns pivot, base_low, depth_atr, range_pct, vol_dryup (1/0/nan).
    """
    n = len(high)
    pivot = np.full(n, np.nan)
    base_low = np.full(n, np.nan)
    depth_atr = np.full(n, np.nan)
    range_pct = np.full(n, np.nan)
    vol_dry = np.full(n, np.nan)
    for i in range(lookback, n):
        # prior window only
        hseg = high[i - lookback : i]
        lseg = low[i - lookback : i]
        vseg = volume[i - lookback : i]
        piv = float(np.nanmax(hseg))
        blo = float(np.nanmin(lseg))
        pivot[i] = piv
        base_low[i] = blo
        a = atr[i - 1] if np.isfinite(atr[i - 1]) else atr[i]
        if not np.isfinite(a) or a <= 0 or piv <= 0:
            continue
        depth_atr[i] = (piv - blo) / a
        range_pct[i] = (piv - blo) / piv
        mid = lookback // 2
        left = np.nanmean(vseg[:mid]) if mid > 0 else np.nan
        right = np.nanmean(vseg[mid:]) if lookback - mid > 0 else np.nan
        if np.isfinite(left) and np.isfinite(right) and left > 0:
            vol_dry[i] = 1.0 if right <= left else 0.0
    return pivot, base_low, depth_atr, range_pct, vol_dry


def enrich_c2(
    df: pd.DataFrame,
    *,
    base_lookback: int = 15,
    spy_perf_21d: pd.Series | None = None,
) -> pd.DataFrame:
    """Enrich OHLCV with C1 indicators plus C2 base/52w/RS columns.

    ``spy_perf_21d`` should be indexed like the stock's session dates
    (normalized, tz-naive preferred) for alignment.
    """
    out = enrich_daily(df)
    if out is None or out.empty:
        return out

    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)

    out["perf_63d"] = performance(close, 63)
    out["high_252"] = high.rolling(252, min_periods=200).max()
    out["dist_52w"] = 1.0 - close / out["high_252"].replace(0.0, np.nan)

    piv, blo, d_atr, r_pct, vdry = _base_features(
        high.to_numpy(),
        low.to_numpy(),
        volume.to_numpy(),
        out["atr14"].to_numpy(dtype=float),
        base_lookback,
    )
    out["pivot"] = piv
    out["base_low"] = blo
    out["base_depth_atr"] = d_atr
    out["base_range_pct"] = r_pct
    out["base_vol_dryup"] = pd.Series(vdry == 1.0, index=out.index)

    # RS vs SPY
    if spy_perf_21d is not None and not spy_perf_21d.empty:
        spy = spy_perf_21d.copy()
        spy.index = pd.to_datetime(spy.index)
        if getattr(spy.index, "tz", None) is not None:
            spy.index = spy.index.tz_convert("America/New_York").tz_localize(None)
        spy.index = spy.index.normalize()
        stock_idx = pd.to_datetime(out.index)
        if getattr(stock_idx, "tz", None) is not None:
            stock_idx = stock_idx.tz_convert("America/New_York").tz_localize(None)
        stock_idx = stock_idx.normalize()
        spy_aligned = spy.reindex(stock_idx)
        # reindex may fail if index types differ — use map by date
        if spy_aligned.isna().all():
            spy_map = {pd.Timestamp(i).normalize(): float(v) for i, v in spy.items()}
            spy_aligned = pd.Series(
                [spy_map.get(pd.Timestamp(i).normalize(), np.nan) for i in stock_idx],
                index=out.index,
            )
        else:
            spy_aligned.index = out.index
        out["rs_spy_21d"] = out["perf_21d"].astype(float) - spy_aligned.astype(float)
    else:
        out["rs_spy_21d"] = np.nan

    return out
