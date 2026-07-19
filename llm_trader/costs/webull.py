"""WeBull US long-equity research cost model.

Operator fact (2026-07): WeBull does **not** charge commissions on long US-listed
stocks/ETFs. Sell orders still incur **mandatory regulatory / exchange pass-through**
(SEC fee, FINRA TAF, etc.). Those are tiny vs spread/slippage for most names.

**Binding cost for research = slippage/spread**, tiered by liquidity — not commission.

This module is the **default research economics** for new opportunity-track families.
It does not resurrect E0-failed liquid take-all books (those failed on edge, not fees).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class LiquidityTier(str, Enum):
    MEGA = "mega"    # large-cap liquid
    MID = "mid"
    SMALL = "small"  # gap/in-play, wider books
    MICRO = "micro"  # very thin — research stress only


# Default one-way slippage assumptions (bps of price). Conservative for research.
_DEFAULT_SLIP_ONE_WAY_BPS: dict[LiquidityTier, float] = {
    LiquidityTier.MEGA: 2.0,
    LiquidityTier.MID: 5.0,
    LiquidityTier.SMALL: 15.0,
    LiquidityTier.MICRO: 40.0,
}


@dataclass(frozen=True)
class WebullLongEquityCosts:
    """All-in friction model for long stock/ETF round trips on WeBull."""

    name: str = "webull_long_equity_v0.1"
    # Commission: $0 each way (operator)
    commission_bps_buy: float = 0.0
    commission_bps_sell: float = 0.0
    # Bundle SEC + FINRA TAF + misc pass-through as a small sell-side bps proxy.
    # True SEC is ~$0.00–few cents per $1k; TAF is per-share capped. 0.5 bps sell
    # is a deliberate overestimate so we do not understate regulatory drag.
    regulatory_bps_sell: float = 0.5
    # Slippage one-way (buy and sell each apply this unless overridden)
    slippage_bps_one_way: float = 15.0
    tier: LiquidityTier = LiquidityTier.SMALL

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        return d

    @property
    def fee_bps_buy(self) -> float:
        return self.commission_bps_buy

    @property
    def fee_bps_sell(self) -> float:
        return self.commission_bps_sell + self.regulatory_bps_sell

    def with_slip(self, slip_bps_one_way: float) -> "WebullLongEquityCosts":
        return WebullLongEquityCosts(
            name=self.name,
            commission_bps_buy=self.commission_bps_buy,
            commission_bps_sell=self.commission_bps_sell,
            regulatory_bps_sell=self.regulatory_bps_sell,
            slippage_bps_one_way=float(slip_bps_one_way),
            tier=self.tier,
        )

    def with_tier(self, tier: LiquidityTier) -> "WebullLongEquityCosts":
        return WebullLongEquityCosts(
            name=self.name,
            commission_bps_buy=self.commission_bps_buy,
            commission_bps_sell=self.commission_bps_sell,
            regulatory_bps_sell=self.regulatory_bps_sell,
            slippage_bps_one_way=_DEFAULT_SLIP_ONE_WAY_BPS[tier],
            tier=tier,
        )


def webull_long_equity(
    *,
    tier: LiquidityTier = LiquidityTier.SMALL,
    slip_bps_one_way: Optional[float] = None,
) -> WebullLongEquityCosts:
    """Factory: WeBull long equity defaults for a liquidity tier."""
    base = WebullLongEquityCosts(tier=tier).with_tier(tier)
    if slip_bps_one_way is not None:
        return base.with_slip(slip_bps_one_way)
    return base


def tier_for_price_adv(
    price: float,
    avg_daily_volume: float,
    *,
    dollar_adv: Optional[float] = None,
) -> LiquidityTier:
    """Rough tier for research (not a broker classification)."""
    dadv = dollar_adv if dollar_adv is not None else price * avg_daily_volume
    if price >= 50 and dadv >= 5e8:
        return LiquidityTier.MEGA
    if price >= 10 and dadv >= 5e7:
        return LiquidityTier.MID
    if price >= 2 and dadv >= 2e6:
        return LiquidityTier.SMALL
    return LiquidityTier.MICRO


def apply_buy_fill(price: float, model: WebullLongEquityCosts) -> float:
    """Worse buy: pay slip + any buy commission bps."""
    bps = model.slippage_bps_one_way + model.fee_bps_buy
    return float(price) * (1.0 + bps / 10_000.0)


def apply_sell_fill(price: float, model: WebullLongEquityCosts) -> float:
    """Worse sell: lose slip + sell commission + regulatory bps."""
    bps = model.slippage_bps_one_way + model.fee_bps_sell
    return float(price) * (1.0 - bps / 10_000.0)


def round_trip_friction_bps(model: WebullLongEquityCosts) -> float:
    """Approximate all-in RT cost in bps of mid (buy friction + sell friction)."""
    return (
        model.slippage_bps_one_way
        + model.fee_bps_buy
        + model.slippage_bps_one_way
        + model.fee_bps_sell
    )


def legacy_fee_slip_pair(model: WebullLongEquityCosts) -> tuple[float, float]:
    """Map to old (fee_bps_one_way, slip_bps_one_way) for gradual migration.

    Old sims applied the same fee bps on buy and sell. WeBull has fee≈0 on buy and
    regulatory-only on sell. Approximate by averaging sell fee into a symmetric
    one-way fee so legacy simulators remain usable:
      fee_one_way ≈ regulatory_sell / 2
      slip_one_way = model.slippage
    """
    fee_one_way = model.fee_bps_sell / 2.0
    return fee_one_way, model.slippage_bps_one_way


def stress_grid_webull_small() -> list[tuple[str, WebullLongEquityCosts]]:
    """Pre-registered stress scenarios for in-play / small-cap research."""
    base = webull_long_equity(tier=LiquidityTier.SMALL)
    return [
        ("baseline_slip15", base.with_slip(15.0)),
        ("slip_10", base.with_slip(10.0)),
        ("slip_20", base.with_slip(20.0)),
        ("slip_30", base.with_slip(30.0)),
        ("slip_50", base.with_slip(50.0)),
        ("mega_slip2_ref", webull_long_equity(tier=LiquidityTier.MEGA)),
    ]
