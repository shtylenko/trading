"""d03 — Post-gap opening drive, uncapped winners.

One-lever change from d01: remove the 1R target and let the position ride
to the 11:30 cutoff (or the stop). The gap-and-go thesis is tail-driven —
a few big runners pay for many small losers — but d01's symmetric 1R cap
against a 1R stop structurally clips exactly that right tail. This tests
whether the cap, not the concept, is the drag.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d03"
    strategy_name = "Post-Gap Opening Drive — uncapped winners"
    description = (
        "d01 gap-and-go with the 1R target removed: winners run to the 11:30 "
        "cutoff so the right tail is uncapped (stop still at the first-candle low)."
    )

    uncapped = True
