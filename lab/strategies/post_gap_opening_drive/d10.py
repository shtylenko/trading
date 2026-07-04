"""d10 — Post-gap opening drive, reject tight-stop opening candles.

One-lever change from d01, motivated by the 2026-06-13 diagnostic: d01's worst
losers are tiny price moves (−0.1% to −0.7%) that become a full −1R because the
stop = the first-candle range, which is often a sliver of price. A stop that
narrow sits inside normal opening noise and gets clipped before any trend
appears (the same microstructure failure that killed ORB).

This release requires the first 5-minute candle's range to be ≥ 0.3 × the
stock's 14-day ATR — i.e. only take setups whose stop is wide enough to clear
the morning's noise band. If R improves, the death-by-clip diagnosis is right
and the fix is to avoid (or widen) tight-stop opens; if not, candidate selection
can't fix the geometry and the entry/stop design itself must change.

Paired with d09 (a maximum on the same ratio) to bracket the candle-size effect.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d10"
    strategy_name = "Post-Gap Opening Drive — minimum stop width (anti-clip)"
    description = (
        "d01 gap-and-go restricted to first-candle range ≥ 0.3×ATR14: skip "
        "tight-stop opens that get clipped by opening noise before trending."
    )

    min_candle_atr_frac = 0.3
