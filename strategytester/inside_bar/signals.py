"""#15 Inside Bar Breakout (daily). Buy-stop above an inside bar in an uptrend.

Faithful-minimal: inside bar (H<prevH, L>prevL) whose range <= ATR (compression),
in an uptrend (SMA50>SMA200, close>SMA50). Entry = buy-stop above the inside-bar
high next session; stop = inside-bar low; target = 2R (measured-move proxy).
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "inside_bar"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    atr = df["atr14"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float); sma200 = df["sma200"].to_numpy(float)
    ds = dates(df)

    inside = np.zeros(n, bool)
    inside[1:] = (h[1:] < h[:-1]) & (l[1:] > l[:-1])
    compression = (h - l) <= atr
    low_vol = np.zeros(n, bool)
    low_vol[1:] = v[1:] <= v[:-1]           # consolidation (not a distribution bar)
    uptrend = (sma50 > sma200) & (c > sma50)
    mask = inside & compression & low_vol & uptrend & np.isfinite(atr)

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        trig = h[i] + max(0.05, 0.001 * h[i])
        stop = l[i]
        if trig <= stop:
            continue
        target = trig + 2.0 * (trig - stop)
        out.append(Signal(ticker, ds[i], stop=stop, target=target, trigger=trig, entry="buy_stop"))
    return out
