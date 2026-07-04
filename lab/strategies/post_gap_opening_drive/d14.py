"""d14 — Post-Gap Opening Drive, SPY<50d regime gate + first-bar close-position.

Two-lever combination, pre-registered together with d13 (2026-06-14) BEFORE
either was run. d14 = d11 (SPY-below-50d-SMA market-regime gate) PLUS the
first-bar close-position gate that d13 tests standalone. The question d14
answers: do the two edges stack, or is the geometry filter redundant with the
regime gate?

Both levers came from the same d11 screen diagnostic. d11 already keeps only
days when the broad tape is weak (gap-up = relative strength). Within those
days, the surviving losers still cluster in breakouts whose first 5m candle
closed AT its high (exhaustion). On the d11 screen ledger, additionally
dropping the top close-position decile moved the gated family:

    d11 (regime only)              :  +39.9R / 376 trades, meanR +0.106
    d11 + close_pos < 0.9 (= d14)  :  +42.8R / 280 trades, meanR +0.153
                                       ex-2026H1 +32.5R -> +34.9R, 6/8 H buckets +

so the geometry lever adds mean-R quality on top of the regime gate without
collapsing trade count, and the improvement is not 2026H1-carried.

Thesis:
    Regime gate (from d11): a gap above the prior high is informative relative
    strength only when the broad market is weak (SPY < 50d SMA); in a ripping
    tape the same gap is just beta and fades. Geometry gate (from d13): even on
    a weak-tape day, a first candle that closed at its high is exhaustion and
    the breakout above it chases an extended move. d14 arms the gap-and-go only
    when BOTH are satisfied: weak market AND a first bar that left room.

Data requirements:
    - Everything d11 needs: d01's 5m RTH + raw daily, PLUS SPY daily history
      deep enough for a 50-day SMA (spy_daily_lookback_days = 90). The close-
      position gate reads only first-candle high/low/close already in candidate
      features — no extra series, no look-ahead.

Entry rules:
    - All of d11's rules: d01 gap-and-go AND SPY's prior-day close below its
      trailing 50-day SMA (else the day produces no candidates).
    - ADDITIONALLY: first-candle close position (close - low)/(high - low) <= 0.9.

Exit and risk rules:
    - Unchanged from d01/d11: stop at first-candle low (=1R), 1R target,
      flatten 11:30 NY.

Known limitations:
    - Stacks two sparsifying gates. d11 already zeroes out sustained bull
      stretches; the close-position decile drop removes ~25% more candidates
      (376 -> 280 on the screen). Watch the >20-trades/quarter floor on the
      broad eval — some half-years are already thin (2022H2, 2024H2).
    - Two fixed thresholds (SPY 50d, close-pos 0.9). Both inherited unchanged
      from d11/d13 rather than re-tuned, to keep the combination honest.
    - If d13 (standalone) is strong and d14 only marginally beats d11, the
      geometry lever is the real edge and the regime gate is secondary; if d14
      clearly beats both, they are complementary. That comparison is the point.

Next intended releases:
    - d15+: per-ticker relative-strength gate (stock vs its own 50d trend, or
      stock gap vs sector/SPY gap) as the cross-sectional refinement (also noted
      by d12's sector-trend gate).
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.d11 import Release as D11Release


class Release(D11Release):
    release_id = "d14"
    strategy_name = "Post-Gap Opening Drive — SPY<50d regime + first-bar close-position"
    description = (
        "d11's SPY-below-50d-SMA regime gate PLUS d13's first-bar close-position "
        "gate: arm the gap-and-go only when the broad tape is weak AND the first "
        "5m candle did not close in the top decile of its range (exhaustion)."
    )

    max_first_close_pos = 0.9
