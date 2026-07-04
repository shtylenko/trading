"""d06 — Post-gap opening drive with a VWAP confluence gate.

One-lever change from d01: only take the breakout if it FILLS above the
session VWAP (the day's volume-weighted institutional cost basis). A "gap-up"
whose first-candle-high breakout triggers below VWAP means the opening volume
was net distribution — buying it is buying into trapped supply, which tends to
fade.

Why this needed an engine change (unlike d07–d10): the gate must be evaluated
at the *breakout fill*, not at signal-build time (at the first candle, VWAP is
just that candle's own typical price — degenerate). The check is implemented in
``simulate_long_breakout`` via the ``require_above_vwap`` signal-metadata flag:
session VWAP is computed from the open, and a breakout that triggers at/below
VWAP is rejected (NO_FILL). The flag is a no-op for every other strategy.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d06"
    strategy_name = "Post-Gap Opening Drive — VWAP confluence"
    description = (
        "d01 gap-and-go that only fills the breakout when it clears session VWAP "
        "(institutional cost basis): skip breakouts triggering into trapped supply."
    )

    require_above_vwap = True
