"""#12 Support/Resistance Bounce — Rayner Teo (daily).

Buy a bounce off rising SMA50 support in an uptrend: price tests the SMA50
(low within 1%) and closes back above it on a green, strong-close candle.
Enter next open; stop below support; target = 2R.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "sr_bounce"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    o = df["open"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    close_pos = df["close_pos"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float); sma200 = df["sma200"].to_numpy(float)
    ds = dates(df)

    sma50_rise = np.zeros(n, bool)
    sma50_rise[5:] = sma50[5:] > sma50[:-5]
    uptrend = (sma50 > sma200) & sma50_rise
    test = (l <= sma50 * 1.01) & (c > sma50)
    green = (c > o) & (close_pos >= 0.5)
    mask = uptrend & test & green

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        stop = min(l[i], sma50[i]) * 0.98
        if stop >= c[i]:
            continue
        target = c[i] + 2.0 * (c[i] - stop)
        out.append(Signal(ticker, ds[i], stop=stop, target=target, entry="next_open"))
    return out
