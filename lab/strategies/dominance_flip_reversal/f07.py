"""f07 — f05 mean-overshoot target, guarded against unavailable ATR.

Strategy identity:
    Name: Dominance Flip Reversal
    Alias: dominance_flip_reversal
    Letter: f
    Release: f07

Why this release exists (audit M11, 2026-06-13):
    f05 sets the target to mean + 0.5·ATR(5m). It reads the ATR with
    ``float(f.get("atr_5m", 0.0))``: a MISSING key yields 0.0, but a present
    NaN yields NaN, so ``new_target = sma + 0.5·NaN = NaN`` and the
    ``new_target > entry_trigger`` guard is False — f05 then silently falls
    back to f01's mean-touch target. The trade is still taken, so f05's reported
    trade count is inflated with disguised-f01 trades and its true selectivity
    is understated.

    f07 makes the ATR dependency explicit: when ATR(5m) is missing/non-finite
    /non-positive, the overshoot target — the release's entire reason to exist
    — cannot be honored, so the candidate is SKIPPED (with a warning) rather
    than quietly traded as f01. When ATR is valid the behaviour matches f05.

Detection / entry / stop: inherited unchanged from f01 via FlipVariant.
"""

from __future__ import annotations

import logging
import math

from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant

logger = logging.getLogger("strategy_lab.strategies.f07")


class Release(FlipVariant):
    release_id = "f07"
    strategy_name = "Dominance Flip Reversal — mean-overshoot target (ATR-guarded)"
    description = (
        "f05's mean + 0.5·ATR(5m) target, but candidates whose ATR(5m) is "
        "missing/non-finite are skipped instead of silently reverting to f01's "
        "mean-touch target."
    )

    # Apply the overshoot here (not via the inherited target_atr_mult knob,
    # which routes through FlipVariant's unguarded path) so the guard owns it.
    TARGET_ATR_MULT = 0.5

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        # target_atr_mult stays at its 0.0 default, so super() returns the f01
        # signal (mean-touch target) untouched; f07 then sets the guarded target.
        signal = super().build_signal(context, candidate)
        if signal is None:
            return None
        atr = float(candidate.features.get("atr_5m", float("nan")))
        if not math.isfinite(atr) or atr <= 0.0:
            logger.warning(
                "f07: ATR(5m) unavailable for %s on %s — skipping (cannot honor "
                "overshoot target)", candidate.ticker, context.trade_date,
            )
            return None
        new_target = float(candidate.features["sma_at_flip"]) + self.TARGET_ATR_MULT * atr
        if new_target > signal.entry_trigger:
            signal.target_price = new_target
            signal.metadata["target_price"] = new_target
            signal.metadata["target_atr_mult"] = self.TARGET_ATR_MULT
        return signal
