"""OHLC(V) bar permutation (Masters / neurotrader algorithm).

Decomposes each bar into log-space components that are shuffled
independently and restrung:

- the *gap*: open minus the prior bar's close
- the *intrabar* offsets: high/low/close minus the bar's own open

Gaps and intrabar offsets get separate shuffles, but high/low/close (and
volume) of one source bar always travel together, so bar geometry stays
valid (high >= max(open, close), low <= min(open, close)).

Properties preserved: the first bar, the last close (overall trend),
return moments (mean/std/skew/kurtosis), and — when permuting several
markets with the same shuffle — cross-market correlation. Properties
destroyed: temporal structure (autocorrelation, volatility clustering,
long memory). Strategies that monetize those destroyed properties get an
optimistic bias from these tests — a strategy that *still* fails is
definitely junk.
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np
import pandas as pd

_OHLC = ["open", "high", "low", "close"]

BarsLike = Union[pd.DataFrame, Sequence[pd.DataFrame]]


def permute_bars(
    data: BarsLike,
    start_index: int = 0,
    seed: int | np.random.Generator | None = None,
) -> BarsLike:
    """Return a random permutation of OHLC(V) bars.

    Parameters
    ----------
    data : DataFrame or sequence of DataFrames
        Bars with columns open/high/low/close (volume optional). A list
        permutes multiple markets with the *same* shuffle, preserving
        cross-market correlation. All frames must share one index.
    start_index : int
        Bars before this index are copied through unchanged. Used by the
        walk-forward permutation test to keep the first training fold
        real and permute only the evaluation data.
    seed : int or numpy Generator, optional
        For reproducible permutations.
    """
    rng = seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)
    single = isinstance(data, pd.DataFrame)
    markets = [data] if single else list(data)
    if not markets:
        raise ValueError("No data given")
    index = markets[0].index
    for m in markets[1:]:
        if not m.index.equals(index):
            raise ValueError("All markets must share an identical index")
    n = len(index)
    if not 0 <= start_index < n - 1:
        raise ValueError(f"start_index {start_index} out of range for {n} bars")

    n_perm = n - start_index - 1
    shuffle_intrabar = rng.permutation(n_perm)
    shuffle_gaps = rng.permutation(n_perm)

    out: list[pd.DataFrame] = []
    for m in markets:
        log_bars = np.log(m[_OHLC].to_numpy(dtype=float))
        opens, highs, lows, closes = (log_bars[:, i] for i in range(4))

        # Components of the bars after start_index
        rel_gap = opens[start_index + 1:] - closes[start_index:-1]
        rel_high = highs[start_index + 1:] - opens[start_index + 1:]
        rel_low = lows[start_index + 1:] - opens[start_index + 1:]
        rel_close = closes[start_index + 1:] - opens[start_index + 1:]

        g = rel_gap[shuffle_gaps]
        h = rel_high[shuffle_intrabar]
        l = rel_low[shuffle_intrabar]
        c = rel_close[shuffle_intrabar]

        # String the permuted bars together:
        #   close_j = close_{j-1} + gap_j + relclose_j   (cumulative)
        #   open_j  = close_{j-1} + gap_j
        perm_close = closes[start_index] + np.cumsum(g + c)
        perm_open = perm_close - c
        perm_high = perm_open + h
        perm_low = perm_open + l

        new_log = log_bars.copy()
        new_log[start_index + 1:, 0] = perm_open
        new_log[start_index + 1:, 1] = perm_high
        new_log[start_index + 1:, 2] = perm_low
        new_log[start_index + 1:, 3] = perm_close

        perm_df = pd.DataFrame(np.exp(new_log), index=index, columns=_OHLC)
        # Copy the unchanged prefix from the source verbatim — exp(log(x))
        # round-trips with float error and the prefix must stay bit-exact.
        perm_df.iloc[: start_index + 1] = m[_OHLC].iloc[: start_index + 1].to_numpy()
        if "volume" in m.columns:
            vol = m["volume"].to_numpy().copy()
            # volume travels with its source bar's intrabar components
            vol[start_index + 1:] = vol[start_index + 1:][shuffle_intrabar]
            perm_df["volume"] = vol
        out.append(perm_df)

    return out[0] if single else out
