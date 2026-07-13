"""#02 Episodic Pivot — StockBee/Qullamaggie (daily, truncated to <=3 sessions).

Gap up 10%+ on >=2x volume that HOLDS (closes in the upper half of the day),
from a non-extended base (neglect), with the index bullish. Enter next open
(confirmation), stop = gap-day low, ride to the 3-session time stop.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import aligned, dates

NAME = "episodic_pivot"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    gap = df["gap"].to_numpy(float)
    relvol = df["relvol"].to_numpy(float)
    close_pos = df["close_pos"].to_numpy(float)
    perf126 = df["perf126"].to_numpy(float)
    sma50 = df["sma50"].to_numpy(float)
    bull = aligned(ctx, df, "spy_bull", False)
    ds = dates(df)

    neglect = ~(perf126 > 0.8)              # not already run 80%+ in 6 months
    mask = (gap >= 0.10) & (relvol >= 2.0) & (close_pos >= 0.5) & (c > sma50) & neglect & bull

    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        stop = l[i]
        if stop >= c[i]:
            continue
        out.append(Signal(ticker, ds[i], stop=stop, target=None, entry="next_open"))
    return out
