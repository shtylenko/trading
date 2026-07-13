"""#17 Fibonacci Retracement Pullback (daily).

In an uptrend (close>SMA50, ADX>20), price pulls back into the 38.2-61.8% zone
of the last confirmed swing-low -> swing-high impulse and prints a bullish
reversal candle. Enter next open; stop = swing low; target = impulse high.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "fib_pullback"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    o = df["open"].to_numpy(float); c = df["close"].to_numpy(float)
    close_pos = df["close_pos"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float); adx = df["adx14"].to_numpy(float)
    sw_lo = df["swing_low"].to_numpy(float); sw_hi = df["swing_high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    ds = dates(df)

    out = []
    for i in range(1, n - 1):
        H, L = sw_hi[i], sw_lo[i]
        if not (np.isfinite(H) and np.isfinite(L)) or H <= L or c[i] >= H:
            continue
        retr = (H - c[i]) / (H - L)
        if not (0.382 <= retr <= 0.618):
            continue
        if not (c[i] > sma50[i] and adx[i] > 20):
            continue
        if not (c[i] > o[i] and c[i] > c[i - 1] and close_pos[i] >= 0.5):
            continue
        stop = min(l[i], L)
        if stop >= c[i] or H <= c[i]:
            continue
        out.append(Signal(ticker, ds[i], stop=stop, target=H, entry="next_open"))
    return out
