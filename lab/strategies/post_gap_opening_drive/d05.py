"""d05 — Post-gap opening drive with a raw-price split / data-glitch guard.

One-lever change from d01: discard any candidate whose trailing daily window or
open-vs-prior-close shows a >40% jump (`has_split_like_jump`), the guard the ORB
family already uses but the d-family lacked.

Pre-registered CONTROL. The 2026-06-13 read-only diagnostic on d01 found zero
trades with gaps >40% (max 33%) and that the worst losers are ordinary small-%
noise stop-outs, not split blow-ups — so we expect this to be ~identical to d01.
Running it confirms that empirically (and closes out the reviewer's data-
contamination hypothesis) rather than relying on inference.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d05"
    strategy_name = "Post-Gap Opening Drive — split/glitch guard (control)"
    description = (
        "d01 gap-and-go with has_split_like_jump applied: drop raw-price split / "
        "data-glitch days. Pre-registered no-op control for the contamination test."
    )

    split_guard = True
