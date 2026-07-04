"""d07 — Post-gap opening drive with an exhaustion-gap ceiling.

One-lever change from d01: keep the 1% gap floor but ADD an 8% ceiling, so
only "Goldilocks" gaps (1% ≤ gap ≤ 8% above the prior day's high) qualify.
Hypothesis: very large overnight gaps are exhaustion moves — overnight holders
liquidate into retail opening demand and the drive immediately fades. (We lead
with the ceiling because the gap *floor* alone, ≥3%, was already tested and
killed as ORB o05; the ceiling is the novel part.)
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d07"
    strategy_name = "Post-Gap Opening Drive — exhaustion-gap ceiling"
    description = (
        "d01 gap-and-go restricted to 1% ≤ gap ≤ 8% above the prior daily high: "
        "drop large overnight gaps that tend to fade as exhaustion moves."
    )

    max_gap_pct = 8.0
