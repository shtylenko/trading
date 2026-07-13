"""#05 Anchored VWAP Pullback — Martin Luk (daily approximation).

Buy weakness in strength: a strong stock (perf 63d>20% or 126d>30%) dips to
support (20d rolling-VWAP proxy / 21EMA) and RECLAIMS it (close back above the
VWAP proxy and 9EMA, turning positive). Enter next open; tight stop = day low;
big-R strategy so no fixed target — ride to the 3-session mandate stop.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates, rolling_vwap

NAME = "avwap_pullback"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    o = df["open"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ema9 = df["ema9"].to_numpy(float); ema21 = df["ema21"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float)
    perf63 = df["perf63"].to_numpy(float); perf126 = df["perf126"].to_numpy(float)
    avwap = rolling_vwap(df, 20)
    ds = dates(df)

    strong = (perf63 > 0.20) | (perf126 > 0.30)
    uptrend = (c > sma50) & (ema9 > ema21)
    support = np.maximum(avwap, ema21)
    dipped = l <= support
    reclaim = (c > avwap) & (c > ema9) & (c > o)
    mask = strong & uptrend & dipped & reclaim & np.isfinite(avwap)

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        stop = l[i]
        if stop >= c[i]:
            continue
        out.append(Signal(ticker, ds[i], stop=stop, target=None, entry="next_open"))
    return out
