"""#23 VWAP Bounce / Trend Following — Brian Shannon (1-min intraday).

Price trending above session VWAP pulls back to touch VWAP and RECLAIMS it
(green bar closing back above VWAP). Enter next 1-min open; stop below the
bounce low / VWAP; target 2R; exit by the close (hours-hold, native short).
"""

from __future__ import annotations

import numpy as np

NAME = "vwap_bounce"
HORIZON = "intraday"
COST_BPS = 5.0
NEED_PREVCLOSE = False


def day_fn(o, h, l, c, vwap, prevclose):
    n = len(c)
    if n < 120:
        return None
    above = c > vwap
    for i in range(20, min(n - 2, 350)):
        if not np.isfinite(vwap[i]):
            continue
        recently_above = above[max(0, i - 10):i].mean() > 0.6
        touched = l[i] <= vwap[i] * 1.001
        reclaim = (c[i] > vwap[i]) and (c[i] > o[i])
        rising = c[i] > c[max(0, i - 15)]
        if recently_above and touched and reclaim and rising:
            entry_px = o[i + 1]
            stop = min(l[i], vwap[i] * 0.997)
            if stop >= entry_px:
                continue
            target = entry_px + 2.0 * (entry_px - stop)
            return (i + 1, entry_px, stop, target, n - 1)
    return None
