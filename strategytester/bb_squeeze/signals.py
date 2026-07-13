"""#18 Bollinger Band Squeeze breakout (daily).

Bandwidth at/near a 6-month low (squeeze) + close above the upper band + RSI>50
+ above-average volume in an uptrend. Enter next open; stop = 6-bar squeeze low;
target = close + 2*ATR (spec's 2xATR target).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "bb_squeeze"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    c = df["close"].to_numpy(float)
    atr = df["atr14"].to_numpy(float)
    bb_up = df["bb_up"].to_numpy(float)
    bb_w = df["bb_width"].to_numpy(float)
    bb_w_min = df["bb_width_min126"].to_numpy(float)
    rsi14 = df["rsi14"].to_numpy(float)
    relvol = df["relvol"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float)
    ll6 = df["low"].rolling(6, min_periods=6).min().to_numpy(float)
    ds = dates(df)

    squeeze = bb_w <= bb_w_min * 1.05
    breakout = c > bb_up
    mask = squeeze & breakout & (rsi14 > 50) & (relvol > 1.0) & (c > sma50) & np.isfinite(atr)

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        stop = min(ll6[i], c[i] * 0.97) if np.isfinite(ll6[i]) else c[i] * 0.97
        if stop >= c[i]:
            continue
        target = c[i] + 2.0 * atr[i]
        out.append(Signal(ticker, ds[i], stop=stop, target=target, entry="next_open"))
    return out
