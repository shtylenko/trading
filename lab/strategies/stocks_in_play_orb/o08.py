"""o08 — Time-stop variant (cut the bleed, keep the tails).

Hypothesis: the tails are real but death-by-a-thousand-cuts kills the
sum (every validation period was −100R..−160R without its top-5 trades).
o04 spec plus: exit at the first bar at/after 12:00 NY whose OPEN shows
unrealized R below +0.5 — the morning momentum either showed up or it
didn't. Winners past +0.5R run to EOD untouched; winners are never capped.
"""

from __future__ import annotations

from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant


class Release(SipOrbVariant):
    release_id = "o08"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — noon time-stop"
    description = (
        "o04 spec + time stop: exit at 12:00 NY if unrealized R < +0.5; "
        "winners run to EOD (long only, RV-ranked, no ML)."
    )

    top_n = None
    min_rv = 2.0
    time_stop_at = "12:00"
    time_stop_min_r = 0.5
