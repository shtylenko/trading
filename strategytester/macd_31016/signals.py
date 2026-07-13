"""#06 MACD 3-10-16 (Linda Raschke 3/10 oscillator), daily swing entries.

Strong trend (ADX>25, trend line >0, close>20EMA) with the histogram crossing
back above zero — momentum re-accelerating after a pullback to the 20 EMA.
Enter next open; stop = 3-bar low; target = 2R.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "macd_31016"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    c = df["close"].to_numpy(float)
    ema20 = df["ema20"].to_numpy(float)
    adx = df["adx14"].to_numpy(float)
    sig = df["macd_sig"].to_numpy(float)
    hist = df["macd_hist"].to_numpy(float)
    ll3 = df["low"].rolling(3, min_periods=3).min().to_numpy(float)
    ds = dates(df)

    cross_up = np.zeros(n, bool)
    cross_up[1:] = (hist[1:] > 0) & (hist[:-1] <= 0)
    trend = (adx > 25) & (sig > 0) & (c > ema20)
    mask = cross_up & trend

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        stop = ll3[i]
        if not np.isfinite(stop) or stop >= c[i]:
            continue
        target = c[i] + 2.0 * (c[i] - stop)
        out.append(Signal(ticker, ds[i], stop=stop, target=target, entry="next_open"))
    return out
