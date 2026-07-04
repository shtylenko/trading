"""o05 — Extreme-gapper specialization.

Hypothesis: the edge lives in catalyst-driven movers and is diluted
across liquid large caps. Tightens the in-play definition: overnight
|gap| >= 3%, RV >= 3, open price $5-$100 (excludes mega caps where
"in play" is meaningless). Long only, same mechanics as o04.
"""

from __future__ import annotations

from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant


class Release(SipOrbVariant):
    release_id = "o05"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — extreme gappers"
    description = (
        "o04 mechanics restricted to extreme movers: |gap| >= 3%, RV >= 3, "
        "open $5-$100, long only, RV-ranked, no ML."
    )

    top_n = None
    min_rv = 3.0
    min_gap_abs = 0.03
    max_open_price = 100.0
