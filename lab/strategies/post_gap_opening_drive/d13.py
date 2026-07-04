"""d13 — Post-Gap Opening Drive, first-bar close-position gate (standalone).

One-lever change from the d01 gap-and-go baseline. Pre-registered together with
d14 (2026-06-14) BEFORE either was run, from a diagnostic on the d11 screen
ledger (run_d11_screen_2022_2026_sampled_...): slicing every filled trade by
WHERE the first 5-minute candle closed within its own range produced a clean,
monotonic gradient in mean R:

    close in lower half (<0.5) :  +0.30R / trade, 66% win   (n=59)
    middle (0.5-0.9)           :  +0.11R / trade, 58% win   (n=221)
    closed at the high (>=0.9)  :  -0.03R / trade, 47% win   (n=96)

i.e. the top decile of close-position is the toxic bucket. Dropping it lifted
d11's screen mean R +0.106 -> +0.153 on 96 fewer trades, and the gain held
ex-2026H1 (+32.5R -> +34.9R), so it is not a recent-window mirage.

Thesis (why the direction is what it is):
    A first 5m candle that closes AT its high is exhaustion — the breakout
    entry above that high is chasing an already-extended move with little room
    before the 1R target, so it stalls and reverses. A candle that closes
    LOWER in its range but still climbs back through its high to trigger the
    breakout has demonstrated real demand reclaiming the level; that follow-
    through is what the gap-and-go is supposed to capture. d13 keeps only
    breakouts whose first bar closed below the top decile of its range.

    d13 is the STANDALONE test: it applies the close-position gate to the plain
    d01 baseline with NO market-regime gate, to establish whether the first-bar
    geometry edge stands on its own (vs being redundant with d11's SPY<50d
    gate). d14 stacks the same gate on top of d11's regime gate.

Data requirements:
    - Exactly d01's (current-day 5m RTH + raw daily context). The gate reads
      only the first-candle high/low/close already present in candidate
      features — no extra series, no look-ahead (all known at 09:35).

Entry rules:
    - All of d01's gap-and-go rules (gap > 1% above prior high, green first 5m
      candle, >= $5, breakout of the first-candle high).
    - ADDITIONALLY: the first candle's close position within its range,
      (close - low) / (high - low), must be <= 0.9 (i.e. not in the top decile).

Exit and risk rules:
    - Unchanged from d01: stop at first-candle low (=1R), 1R target, flatten
      11:30 NY.

Known limitations:
    - Single fixed threshold (0.9), chosen as the screen's toxic decile;
      tightening to 0.75 over-filtered (cut winners, sum R fell). The broad
      eval, not this screen sample, is the real arbiter of the threshold.
    - No regime gate, so it inherits d01's family-wide weakness (the ungated
      gap-and-go was largely 2026H1-carried). d13's job is to isolate the
      geometry lever's marginal contribution, not to be a finished strategy.

Next intended releases:
    - d14: this gate stacked on d11's SPY<50d regime gate (regime + geometry).
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d13"
    strategy_name = "Post-Gap Opening Drive — first-bar close-position gate"
    description = (
        "d01 gap-and-go, but reject breakouts whose first 5m candle closed in "
        "the top decile of its range (exhaustion); keep bars that closed lower "
        "but reclaimed the high to trigger. Standalone, no regime gate."
    )

    max_first_close_pos = 0.9
