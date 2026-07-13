"""#24 Overnight Hold Swing — Ricky Gutierrez (daily-bar).

Buy at the close of a bullish day (uptrend, green candle, above SMA20, above
avg volume) to capture the overnight drift. Three variants: pure close->next
open (1 night), close->close (+1), and close->close (+3, mandate max).
Stop = 1.5% below the entry-day low as a gap-down guard.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import dates

NAME = "overnight_hold"
HORIZON = "daily"


def _core(ticker, df, ctx, *, exit_on_open):
    n = len(df)
    if n < 210:
        return []
    o = df["open"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    sma20 = df["sma20"].to_numpy(float); sma50 = df["sma50"].to_numpy(float)
    relvol = df["relvol"].to_numpy(float)
    ds = dates(df)

    mask = (c > sma50) & (c > sma20) & (c > o) & (relvol > 1.0)
    out = []
    for i in np.where(mask)[0]:
        if i >= n - 1:
            continue
        out.append(Signal(ticker, ds[i], stop=l[i] * 0.985, target=None,
                          entry="signal_close", exit_on_open=exit_on_open))
    return out


def _v_open(ticker, df, ctx):
    return _core(ticker, df, ctx, exit_on_open=True)


def _v_c2c(ticker, df, ctx):
    return _core(ticker, df, ctx, exit_on_open=False)


VARIANTS = [
    {"name": "overnight_1n_open", "signals": _v_open, "max_hold": 1, "cost_bps": 5.0},
    {"name": "overnight_c2c_1", "signals": _v_c2c, "max_hold": 1, "cost_bps": 5.0},
    {"name": "overnight_c2c_3", "signals": _v_c2c, "max_hold": 3, "cost_bps": 5.0},
]
