"""o09 — Wide, noise-clearing stop (last pre-registered SIP-ORB hypothesis).

Hypothesis: the concept fails because the stop is mis-sized, not because
breakouts don't work. Diagnosis from the o04-o08 screens (2026-06-12):

  1. The 0.10 x ATR14 stop (~32 bps of price) sits INSIDE normal
     opening-hour turbulence -> ~90% of entries are clipped by noise
     (e.g. ENVX 2022-01-11: +1.3R four minutes after entry, then stopped
     on a routine wiggle).
  2. Costs are fixed in price terms but R is measured against the stop
     width: at 32 bps risk, slippage + fees cost ~0.34R per trade —
     larger than the whole measured deficit (-0.32R/trade).

o09: stop = the WIDER of (entry - 0.30 x ATR14) and the opening range
low — at least ~3x the old distance (cost drag falls to ~0.11R) and
always clear of the morning's demonstrated noise band. Position size
shrinks proportionally (1% risk on the wider stop), winners still run
to EOD uncapped. Same screen, same kill rule. If this dies too, the
family is exhausted: every distinct hypothesis tested and explained.
"""

from __future__ import annotations

from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant


class Release(SipOrbVariant):
    release_id = "o09"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — wide noise-clearing stop"
    description = (
        "o04 spec with the stop widened to max(0.30 ATR, opening-range low): "
        "clears opening-hour noise and amortizes costs over ~3x the risk "
        "distance (long only, RV-ranked, no ML)."
    )

    top_n = None
    min_rv = 2.0
    stop_offset_atr = 0.30
    stop_beyond_or = True
