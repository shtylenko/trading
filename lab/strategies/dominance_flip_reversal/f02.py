"""f02 — Dominance flip + macro trend filter (spec §10.1).

One-lever change from f01: only take the long capitulation reversal when
SPY closed above its 200-day SMA the day before. Tests the audit's #1
concern — f01 is a long-only knife-catcher with no regime alignment, so it
should bleed in 2022 / 2024-H1 bears. If gating to broad uptrends removes
the structurally-doomed losers, this lifts the family's worst buckets.
"""

from __future__ import annotations

from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant


class Release(FlipVariant):
    release_id = "f02"
    strategy_name = "Dominance Flip Reversal — macro trend filter"
    description = (
        "f01 spec gated to SPY-above-200-day-SMA days only (spec §10.1): trade "
        "capitulation reversals only when aligned with the broad uptrend."
    )

    require_spy_uptrend = True
