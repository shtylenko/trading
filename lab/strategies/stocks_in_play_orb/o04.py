"""o04 — Paper-faithful SIP ORB baseline.

Hypothesis: o03's failure came from its 2024-tuned variant (pullback
limit entry, top-10 cap), not from the SIP-ORB concept. This is the
closest engine expression of the published spec: RV >= 2 in-play filter,
no top-N cap (testset candidate_limit still applies), 5-minute OR, stop
entry on the break, 0.10 x ATR14 stop, EOD exit, long only.
"""

from __future__ import annotations

from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant


class Release(SipOrbVariant):
    release_id = "o04"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — paper-faithful baseline"
    description = (
        "Paper-faithful spec: SIP filters (RV>=2), 5m OR, stop entry at ORH, "
        "0.10 ATR stop, EOD 15:59, long only, RV-ranked, no top-N cap, no ML."
    )

    top_n = None
    min_rv = 2.0
