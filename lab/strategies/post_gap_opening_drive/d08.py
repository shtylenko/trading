"""d08 — Post-gap opening drive, relative-strength vs SPY (2026-H1 diagnostic).

One-lever change from d01: require the stock's gap to be at least 2× SPY's own
gap that morning (open vs prior daily high). A stock gapping +2% on a morning
SPY also gaps +2% is riding macro beta, not an idiosyncratic catalyst — and
macro gaps tend to mean-revert when the index fades.

This is also the key DIAGNOSTIC for the cross-family 2026-H1 anomaly: if every
family is positive only in 2026-H1 because that half-year was a broad melt-up,
gating to idiosyncratic (relative-strength) gaps should flatten the 2026-H1
bucket. If 2026-H1 survives this filter, the edge there is genuinely
stock-specific; if it collapses, it was beta in disguise.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d08"
    strategy_name = "Post-Gap Opening Drive — relative strength vs SPY"
    description = (
        "d01 gap-and-go requiring the stock's gap ≥ 2× SPY's gap that morning: "
        "isolate idiosyncratic catalysts from macro beta (2026-H1 diagnostic)."
    )

    requires_spy_daily = True  # need SPY prior daily high for its gap
    min_rel_spy_gap = 2.0
