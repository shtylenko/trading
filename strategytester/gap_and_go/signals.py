"""#11 Gap and Go Momentum — Ross Cameron (1-min intraday).

Stock gaps up (>=3%) and holds above VWAP; enter on an opening-range breakout
(close > first-5-min high, above VWAP) in the first ~25 min; stop below the
opening-range low / VWAP; target 2R; hard time exit ~11:00 (zombie rule).
"""

from __future__ import annotations

import numpy as np

NAME = "gap_and_go"
HORIZON = "intraday"
COST_BPS = 5.0
NEED_PREVCLOSE = True


def day_fn(o, h, l, c, vwap, prevclose):
    n = len(c)
    if n < 90 or prevclose is None or prevclose <= 0:
        return None
    gap = o[0] / prevclose - 1.0
    if not (0.03 <= gap <= 0.30):
        return None
    or_high = h[:5].max()
    or_low = l[:5].min()
    cutoff = min(n - 1, 90)                      # ~11:00 hard exit
    for i in range(5, min(n - 2, 25)):           # breakout window 09:35-09:55
        if not np.isfinite(vwap[i]):
            continue
        if c[i] > or_high and c[i] > vwap[i]:
            entry_px = o[i + 1]
            stop = min(or_low, vwap[i])
            if stop >= entry_px or i + 1 > cutoff:
                continue
            target = entry_px + 2.0 * (entry_px - stop)
            return (i + 1, entry_px, stop, target, cutoff)
    return None
