"""Example strategy for the validation gauntlet: Donchian channel breakout.

The same strategy used in the neurotrader video. Long when the close is
the highest of the trailing lookback, short when it is the lowest; the
position is held until the opposite breakout. Serves as a reference
implementation of the (optimize_fn, signal_fn) interface and as the demo
strategy for scripts/permutation_gate.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import position_returns, profit_factor

DEFAULT_LOOKBACKS = tuple(range(12, 169, 4))


def donchian_signal(ohlc: pd.DataFrame, lookback: int) -> pd.Series:
    close = ohlc["close"]
    upper = close.rolling(lookback - 1).max().shift(1)
    lower = close.rolling(lookback - 1).min().shift(1)
    sig = pd.Series(np.nan, index=ohlc.index)
    sig[close > upper] = 1.0
    sig[close < lower] = -1.0
    return sig.ffill().fillna(0.0)


def donchian_objective(ohlc: pd.DataFrame, lookback: int) -> float:
    return profit_factor(position_returns(ohlc["close"], donchian_signal(ohlc, lookback)))


def optimize_donchian(ohlc: pd.DataFrame, lookbacks=DEFAULT_LOOKBACKS) -> int:
    """Grid-search the lookback; returns the best one (params for signal_fn)."""
    best_lb, best_obj = lookbacks[0], -np.inf
    for lb in lookbacks:
        obj = donchian_objective(ohlc, lb)
        if obj > best_obj:
            best_lb, best_obj = lb, obj
    return best_lb


def optimize_donchian_objective(ohlc: pd.DataFrame, lookbacks=DEFAULT_LOOKBACKS) -> float:
    """In-sample gate interface: run the full optimization, return best objective."""
    return donchian_objective(ohlc, optimize_donchian(ohlc, lookbacks))
