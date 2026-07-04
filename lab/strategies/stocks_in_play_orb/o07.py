"""o07 — Volatility-regime-gated o04.

Hypothesis: the SIP-ORB edge is real but dormant outside high-volatility
tape (the paper's sample is dominated by 2020-2021). Trades the o04 spec
only on days where the FROZEN rule passes: SPY 14-day ATR% above its
~1-year median (computed strictly on data before the trade date;
pre-registered 2026-06-12 — never refit this rule to results).

Judgment criterion beyond sum R: were the gated-off days actually
negative for o04? (The gate must predict the bleed, not just delete data.)
"""

from __future__ import annotations

from trading.lab.core.models import StrategyContext
from trading.lab.strategies.stocks_in_play_orb.variants import (
    SipOrbVariant,
    spy_atr_regime_hot,
)


class Release(SipOrbVariant):
    release_id = "o07"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — volatility-regime gated"
    description = (
        "o04 spec gated by a frozen regime rule: trade only when SPY 14d ATR% "
        "is above its 1-year median (long only, RV-ranked, no ML)."
    )

    top_n = None
    min_rv = 2.0
    requires_spy_daily = True

    def regime_ok(self, context: StrategyContext) -> bool:
        return spy_atr_regime_hot(context.trade_date)
