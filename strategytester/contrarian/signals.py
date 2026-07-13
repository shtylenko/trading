"""#10 Contrarian Swing — Bob Desmond (daily approximation).

Buy stabilization after panic while market fear is elevated (VIX above its
10-day average): a big down day / RSI2 washout, then price closes back above
the panic-day high. Enter next open; wide structural stop (below the panic
low); target = 2R mean-revert.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import aligned, dates

NAME = "contrarian"
HORIZON = "daily"
MAX_HOLD = 3
COST_BPS = 5.0


def signals(ticker, df, ctx):
    n = len(df)
    if n < 210:
        return []
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ret1 = df["ret1"].to_numpy(float); rsi2 = df["rsi2"].to_numpy(float)
    vix = aligned(ctx, df, "vix", np.nan)
    vix_ma = aligned(ctx, df, "vix_ma10", np.nan)
    ds = dates(df)

    fear = vix > (vix_ma * 1.10)
    out = []
    for i in range(2, n - 1):
        if not (np.isfinite(vix[i]) and fear[i]):
            continue
        panic = (ret1[i - 1] < -0.04) or (rsi2[i - 1] < 5)
        if not panic:
            continue
        if not (c[i] > h[i - 1]):            # stabilization / reclaim of panic high
            continue
        stop = min(l[i - 1], l[i])
        if stop >= c[i]:
            continue
        target = c[i] + 2.0 * (c[i] - stop)
        out.append(Signal(ticker, ds[i], stop=stop, target=target, entry="next_open"))
    return out
