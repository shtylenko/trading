"""Small helpers shared by strategy signal modules."""

from __future__ import annotations

import numpy as np
import pandas as pd


def aligned(ctx: pd.DataFrame | None, df: pd.DataFrame, col: str, default=False) -> np.ndarray:
    """Return ctx[col] reindexed to df.index as a numpy array (default-filled)."""
    n = len(df)
    if ctx is None or col not in ctx.columns:
        return np.full(n, default)
    s = ctx[col].reindex(df.index)
    if s.dtype == bool or default is False or default is True:
        return s.fillna(default).to_numpy()
    return s.to_numpy(dtype=float)


def rolling_vwap(df: pd.DataFrame, n: int = 20) -> np.ndarray:
    """n-day rolling VWAP (proxy for AVWAP anchored ~n sessions back)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    v = df["volume"].astype(float)
    num = (tp * v).rolling(n, min_periods=n).sum()
    den = v.rolling(n, min_periods=n).sum().replace(0.0, np.nan)
    return (num / den).to_numpy(dtype=float)


def dates(df: pd.DataFrame) -> list:
    return [pd.Timestamp(x).date() for x in df.index]
