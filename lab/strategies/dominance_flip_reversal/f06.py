"""f06 — f02 macro-trend gate, sourced from the hydrated SPY context.

Strategy identity:
    Name: Dominance Flip Reversal
    Alias: dominance_flip_reversal
    Letter: f
    Release: f06

Why this release exists (audit H2, 2026-06-13):
    f02 gates capitulation reversals to days when SPY closed above its 200-day
    SMA — but its ``spy_above_200sma`` helper calls ``fetch_daily_context``
    DIRECTLY from strategy code. That violates the StrategyContext contract:
    it bypasses the runner's data hydration, ``--force-data``, and per-run data
    lineage, fetches SPY daily through a separate code path, and makes the
    release untestable without a live provider. f06 declares ``requires_spy_daily``
    with a 200-day-plus lookback so the runner hydrates SPY daily history, then
    reads ``context.spy_daily`` — no provider calls in release logic.

    The gate itself is identical to f02 (most recent SPY daily close strictly
    before the trade date is above its 200-day SMA; conservative on thin data),
    so f06 is "f02 done within the contract", not a new hypothesis.

Detection / entry / exit: inherited unchanged from f01 via FlipVariant.
"""

from __future__ import annotations

from trading.lab.core.models import StrategyContext
from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant

_SMA_PERIOD = 200


def _spy_above_sma_from_daily(daily, sma_period: int = _SMA_PERIOD) -> bool:
    """f02's gate, computed from an already-fetched SPY daily frame.

    True when SPY's most recent daily close (the runner hydrates only bars
    strictly before the trade date) is above its ``sma_period``-day SMA.
    Conservative on missing data: fewer than ``sma_period`` bars → do not trade.
    """
    if daily is None or len(daily) < sma_period:
        return False
    close = daily["close"].astype(float).to_numpy()
    sma = close[-sma_period:].mean()
    return bool(close[-1] > sma)


class Release(FlipVariant):
    release_id = "f06"
    strategy_name = "Dominance Flip Reversal — macro trend filter (context-sourced)"
    description = (
        "f02's gate (trade capitulation reversals only when SPY closed above its "
        "200-day SMA) computed from the runner-hydrated context.spy_daily instead "
        "of a direct provider call."
    )

    # Leave require_spy_uptrend at its False default so FlipVariant's direct-fetch
    # path stays inert; f06 supplies its own context-sourced gate below.
    requires_spy_daily = True
    spy_daily_lookback_days = int(_SMA_PERIOD * 1.6)

    def regime_ok(self, context: StrategyContext) -> bool:
        return _spy_above_sma_from_daily(context.spy_daily)
