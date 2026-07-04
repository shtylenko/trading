"""o06 — Market-tailwind gate (long only).

Hypothesis: SIP-ORB longs only work when the broad market opens with a
tailwind; on weak opens the breakouts are fade-bait. Trades the o04 spec
only on days where SPY's first regular 5-minute candle closes green
(frozen rule, pre-registered 2026-06-12 — never refit to results).

Distinct from o07: this gates on same-morning market *direction*, o07 on
trailing market *volatility*.

(Originally specced two-sided; revised to long-only 2026-06-12 — the
account cannot short.)
"""

from __future__ import annotations

from trading.lab.core.models import StrategyContext
from trading.lab.research.filters import green_first_candle
from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant


class Release(SipOrbVariant):
    release_id = "o06"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — market-tailwind gated"
    description = (
        "o04 spec gated by market direction: trade longs only when SPY's "
        "first 5-minute candle closes green (long only, RV-ranked, no ML)."
    )

    top_n = None
    min_rv = 2.0

    def regime_ok(self, context: StrategyContext) -> bool:
        return green_first_candle(context.spy_5m)
