"""f05 — Dominance flip with mean-overshoot target.

One-lever change from f01: set the target to the mean plus 0.5·ATR(5m)
instead of the mean itself. f01 enters on the flip bar (already partway back
toward the mean, the safe entry per spec §7.1) but targets only the mean, so
the reward leg is short while the ATR-buffered stop sits far below the flush
low — an inverted, often sub-1:1 R:R.

Hypothesis: extending the target past the mean restores a worthwhile reward
and lifts per-trade R. Counter-thesis (spec §8.1): holding past the mean
degrades the win rate toward 50/50. The screen settles which dominates.
"""

from __future__ import annotations

from trading.lab.strategies.dominance_flip_reversal.variants import FlipVariant


class Release(FlipVariant):
    release_id = "f05"
    strategy_name = "Dominance Flip Reversal — mean-overshoot target"
    description = (
        "f01 spec with the target pushed to mean + 0.5·ATR(5m) past the SMA, "
        "restoring reward on the flip-bar entry's otherwise inverted R:R."
    )

    target_atr_mult = 0.5
