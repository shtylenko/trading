"""f03 — Dominance flip with warm-started indicators (morning flushes).

One-lever change from f01: seed SMA / RSI / z / ATR from the prior two 5m
sessions so the indicators are warm at the open. f01's same-day-only seeding
means the earliest possible flip is ~bar 32 (~12:10 NY), so the most common
capitulations — morning gap-down flushes — are invisible. The flip itself is
still required to land on the trade day (no overnight look-ahead); only the
stretch/divergence context may reach back into the seed.

Hypothesis: f01's edge (if any) is mostly unobserved because it only sees
afternoon setups. Warming the indicators should multiply the trade count and
reveal whether real signal exists across the day.
"""

from __future__ import annotations

from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant


class Release(FlipVariant):
    release_id = "f03"
    strategy_name = "Dominance Flip Reversal — warm-start (morning flushes)"
    description = (
        "f01 spec with indicators seeded from the prior two 5m sessions so flips "
        "are tradable from the open; flip must still occur on the trade day."
    )

    warm_start = True
    warm_start_lookback_days = 2
    historical_5m_lookback_days = 2  # tells the pipeline to load the seed days
