"""#22 TTM Squeeze breakout — John Carter (daily).

Squeeze on (BB inside Keltner) for >=3 bars, then FIRES (BB exits Keltner) with
positive & rising momentum, price above the squeeze high, volume confirming.
Enter next open; stop = 10-bar squeeze low; target = 2R.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "ttm_squeeze"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    c = df["close"].to_numpy(float); h = df["high"].to_numpy(float)
    sq = df["ttm_squeeze_on"].to_numpy(bool)
    mom = df["ttm_mom"].to_numpy(float)
    relvol = df["relvol"].to_numpy(float)
    hh_prior = df["high"].rolling(6, min_periods=6).max().shift(1).to_numpy(float)
    ll10 = df["low"].rolling(10, min_periods=10).min().to_numpy(float)
    ds = dates(df)

    out = []
    for i in range(6, n - 1):
        fired = (not sq[i]) and sq[i - 1] and sq[i - 2] and sq[i - 3]
        if not fired:
            continue
        if not (mom[i] > 0 and mom[i] > mom[i - 1]):
            continue
        if not (relvol[i] > 1.0 and np.isfinite(hh_prior[i]) and c[i] > hh_prior[i]):
            continue
        stop = ll10[i]
        if not np.isfinite(stop) or stop >= c[i]:
            continue
        target = c[i] + 2.0 * (c[i] - stop)
        out.append(Signal(ticker, ds[i], stop=stop, target=target, entry="next_open"))
    return out
