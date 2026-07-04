# m01 — SMA Mean Reversion

**Status:** Proposed. Top-priority new strategy.

**Why this exists:** All current strategies are momentum/breakout — ORB buys
breakouts, dominance flip buys capitulation reversals, post-gap buys gap
continuation. None profits from mean-reverting tape. The stocks_in_play_orb
backlog's own B4 analysis shows September 2024 (−38.4R) was a mean-reverting
month where ORB bled. m01 would profit in the exact regime that hurts ORB.
Combined = smoother equity curve.

**Research thesis (Moon Dev):**
Buy when price deviates X% below SMA(N), sell when price reverts back to or
above SMA. Moon Dev showed a 192,726% ROI backtest (clearly overfit, but the
concept is sound) tested across multiple in/out-of-sample datasets. He described
it as "just a moving average reversal — mean revention" using SMA(14) with no
hard stop, relying on the mean-reversion property.

**Data requirements:**
- Daily OHLCV for SMA and universe filtering (already in the pipeline).
- 5-min bars for intraday signal/execution (already in the pipeline).

**Entry rules:**
- Universe gauntlet: price > $5, ADV >= 1M, ATR > $0.50 (same SIP filters).
- Entry when current price < SMA(N) × (1 − deviation_threshold).
- Entry style: limit order at or below the trigger price.

**Exit rules:**
- Target: price reaches SMA(N) (mean reversion completes) or SMA(N) × (1 + deviation_threshold).
- Time exit: 15:55 (existing convention).
- Optional stop: none in Moon Dev's version (pure mean reversion property handles it).
  Consider adding a volatility-adaptive stop (e.g., 2× ATR14 below entry) as a later variant.

**Parameters to sweep:**
- SMA period: 10–50 (Moon Dev settled on 14)
- Deviation threshold: 1%–5%
- Entry window: intraday (first cross of threshold) vs daily close

**Impact: high.** Fills an orthogonal strategy regime. Directly addresses the
"ORB bleeds in mean-reverting tape" problem documented in the ORB backlog B4.

**Cost: low.** All data already in the pipeline. ~200 LOC total (common.py + m01.py).

**Pitfalls:**
- Mean reversion is well-known; the edge may be eroded by market efficiency.
- No stop means gap risk on overnight news — consider a volatility-adaptive stop.
- Must backtest on multi-year data (2022 bear, 2023 chop, 2024 trend) to verify
  the edge survives different regimes.
