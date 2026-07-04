"""d04 — Post-gap opening drive, full-session hold.

One-lever change from d01: flatten at 15:55 instead of 11:30. A gap-and-go
drive can keep trending well past late morning; d01's 11:30 exit cuts any
runner that hasn't resolved by then. Keeps the 1R target and first-candle
stop — this isolates the hold-window effect alone.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d04"
    strategy_name = "Post-Gap Opening Drive — full-session hold"
    description = (
        "d01 gap-and-go held to 15:55 instead of 11:30, so a drive that keeps "
        "trending past late morning is not flattened early (1R target retained)."
    )

    exit_hour = 15
    exit_minute = 55
