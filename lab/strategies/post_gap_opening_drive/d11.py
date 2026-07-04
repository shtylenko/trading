"""d11 — Post-Gap Opening Drive, SPY-below-50d-SMA market-regime gate.

One-lever change from d01, motivated by the 2026-06-14 regime diagnostic on the
d05 screen ledger. Splitting every filled d05 trade by the broad-market trend —
SPY's prior-day close vs its own 50-day SMA — cleanly separated the family's
P&L:

    SPY < 50d SMA :  +39.97R over 377 trades  (meanR +0.106)
    SPY > 50d SMA :  -33.57R over 671 trades  (meanR -0.050)

and, crucially, the SPY<50d edge GENERALIZES: ex-2026H1 it is still +32.6R,
positive in 6 of 7 half-year buckets (only 2023H2 dips, -2.5R). The ungated
strategy was entirely 2026H1-carried; this gate is not — its edge lives across
2022-2025, so it is not the recent-window mirage the rest of the family was.

Thesis (why the direction is what it is):
    A gap above the prior day's high is a RELATIVE-STRENGTH signal. Relative
    strength is informative when the broad tape is weak — a stock gapping up
    while the market is below its 50-day trend is a genuine standout on real,
    idiosyncratic demand, and it follows through. When the whole market is
    ripping (SPY above its 50d SMA), "gap above prior high" is just beta:
    everything floats up, the signal is not selective, and the crowded gap
    gets sold back intraday. So d11 only arms the gap-and-go when SPY closed
    BELOW its 50-day SMA the prior session.

Data requirements:
    - Everything d01 needs (5m RTH + raw daily), PLUS SPY daily history deep
      enough for a 50-day SMA. ``spy_daily_lookback_days = 90`` (~62 trading
      days) gives a safe margin over the 50 the SMA needs. The runner hydrates
      ``context.spy_daily`` (SPY daily bars strictly before the trade date), so
      its last row is the prior session — no look-ahead.

Entry rules:
    - All of d01's gap-and-go rules (gap > 1% above prior high, green first 5m
      candle, >= $5, breakout of the first-candle high).
    - ADDITIONALLY: SPY's prior-day close must be below its trailing 50-day SMA.
      If not, the day produces no candidates (and therefore no trades).

Exit and risk rules:
    - Unchanged from d01: stop at first-candle low (=1R), 1R target, flatten
      11:30 NY.

Known limitations:
    - The gated edge leans on 2023H1 (+16.3R) and 2025H1 (+10.6R); the full
      eval_*_broad sign-flip test is the real arbiter, not this screen sample.
    - "SPY < 50d SMA" is a market-correction filter, so it trades sparsely in
      sustained bull stretches (the screen's 2025H2 had ZERO qualifying days).
      Watch trade count on the broad eval — do not let it collapse below the
      >20-per-quarter floor before reading the verdict.
    - Single fixed threshold (50d, SPY only). No breadth, no VIX, no sector
      regime. Deliberately one lever so the screen stays honest.
    - Does NOT explain 2026H1's residual anomaly: that period's gain sat in the
      SPY>50d bucket (the one that bleeds elsewhere). d11 captures the robust,
      cross-year edge underneath it, not the 2026 outlier — by design.

Next intended releases:
    - d12: relax to SPY's 100d/200d SMA (longer regime) as a one-lever control.
    - d13: per-ticker relative-strength gate (stock vs its own 50d trend AND/OR
      stock gap vs SPY's gap) as the second-order, cross-sectional refinement.
"""

from __future__ import annotations

import pandas as pd

from trading.lab.core.models import Candidate, StrategyContext
from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d11"
    strategy_name = "Post-Gap Opening Drive — SPY<50d regime gate"
    description = (
        "d01 gap-and-go armed only when SPY closed below its 50-day SMA the "
        "prior session: gap-up = relative strength, which pays when the broad "
        "tape is weak and fades when the market is ripping on beta."
    )

    requires_spy_daily = True
    spy_daily_lookback_days = 90  # safe margin over the 50-day SMA window

    spy_sma_period = 50

    def _spy_below_sma(self, context: StrategyContext) -> bool | None:
        """True when SPY's prior-day close is below its trailing N-day SMA.

        Returns None when SPY history is missing or too short for the SMA, in
        which case d11 conservatively skips the day (no candidates).
        """
        spyd = context.spy_daily
        if spyd is None or spyd.empty or "close" not in spyd:
            return None
        closes = spyd["close"].astype(float)
        if len(closes) < self.spy_sma_period:
            return None
        sma = float(closes.tail(self.spy_sma_period).mean())
        last_close = float(closes.iloc[-1])
        if sma <= 0:
            return None
        return last_close < sma

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        # Regime gate first: if SPY is not below its 50d SMA (or we cannot tell),
        # the whole day is skipped — gap-and-go is only a relative-strength
        # signal worth taking when the broad tape is weak.
        below = self._spy_below_sma(context)
        if not below:
            return []
        cands = super().build_candidates(context)
        for c in cands:
            c.features = {**c.features, "spy_below_50d_sma": True}
        return cands
