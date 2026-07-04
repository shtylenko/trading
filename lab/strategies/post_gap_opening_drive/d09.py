"""d09 — Post-gap opening drive, reject hyper-extended opening candles.

One-lever change from d01: require the first 5-minute candle's range to be
≤ 0.5 × the stock's 14-day ATR. Hypothesis: when the opening candle is huge,
(a) the stop (= candle range) is so wide that the symmetric 1R target sits an
unreachable distance away, and (b) the asset has already expanded violently and
exhausted immediate buying. Capping the candle/ATR ratio keeps the 1R target
achievable within normal intraday volatility.

Paired with d10 (a minimum on the same ratio) to isolate whether candle size —
i.e. stop width — is what drives the family's death-by-1R-clip.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d09"
    strategy_name = "Post-Gap Opening Drive — ATR-capped opening candle"
    description = (
        "d01 gap-and-go restricted to first-candle range ≤ 0.5×ATR14: drop "
        "hyper-extended opens where the 1R target is unreachable."
    )

    max_candle_atr_frac = 0.5
