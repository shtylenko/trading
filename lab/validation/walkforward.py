"""Walk-forward signal construction with periodic re-optimization."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

OptimizeFn = Callable[[pd.DataFrame], Any]
SignalFn = Callable[[pd.DataFrame, Any], pd.Series]


def walk_forward_signal(
    ohlc: pd.DataFrame,
    optimize_fn: OptimizeFn,
    signal_fn: SignalFn,
    train_lookback: int,
    train_step: int,
) -> pd.Series:
    """Build an out-of-sample position signal by walking forward.

    Every ``train_step`` bars, ``optimize_fn`` is fitted on the trailing
    ``train_lookback`` bars and the resulting parameters drive the signal
    until the next refit. Bars before the first training fold get no
    position (NaN -> 0 contribution).

    Parameters
    ----------
    optimize_fn : (train_ohlc) -> params
        Fits/optimizes on training data, returns opaque params.
    signal_fn : (ohlc_so_far, params) -> Series
        Computes the position signal; only its tail past the previous
        refit point is used, so indicators may warm up on history.
    """
    n = len(ohlc)
    if train_lookback >= n:
        raise ValueError("train_lookback >= data length — nothing to walk forward")

    out = pd.Series(np.nan, index=ohlc.index)
    next_train = train_lookback
    params = None
    for i in range(train_lookback, n, train_step):
        if i >= next_train:
            params = optimize_fn(ohlc.iloc[i - train_lookback:i])
            next_train = i + train_step
        seg_end = min(i + train_step, n)
        # Signal computed on all data up to seg_end; indicators look back
        # as far as they need, but only out-of-sample bars are taken.
        sig = signal_fn(ohlc.iloc[:seg_end], params)
        out.iloc[i:seg_end] = sig.iloc[i:seg_end]
    return out.fillna(0.0)
