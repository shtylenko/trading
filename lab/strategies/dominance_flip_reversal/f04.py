"""f04 — Dominance flip with N-bar time-decay abort (spec §8.3).

One-lever change from f01: flatten the position at the open of the 6th bar
(~30 min on 5m) after entry if it has not already hit the stop or the mean
target. Spec §8.3 argues a lack of immediate follow-through means the asset
has accepted the new level and the mean-reversion edge has decayed.

Hypothesis: f01's flip-bar entry into a near-mean target gives an inverted
R:R, and dead "time-correction" trades that drift to the 15:55 exit are pure
drag. Cutting them fast while letting real snap-backs hit target should lift
expectancy.
"""

from __future__ import annotations

from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant


class Release(FlipVariant):
    release_id = "f04"
    strategy_name = "Dominance Flip Reversal — N-bar time-decay abort"
    description = (
        "f01 spec with a 6-bar (~30 min) time-decay abort (spec §8.3): exit at "
        "the open once held 6 bars without resolving to stop or mean target."
    )

    max_hold_bars = 6
