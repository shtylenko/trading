"""Tests for WeBull research cost model."""

from trading.llm_trader.costs.webull import (
    LiquidityTier,
    apply_buy_fill,
    apply_sell_fill,
    round_trip_friction_bps,
    tier_for_price_adv,
    webull_long_equity,
)


def test_webull_zero_commission():
    m = webull_long_equity(tier=LiquidityTier.SMALL)
    assert m.commission_bps_buy == 0.0
    assert m.commission_bps_sell == 0.0
    assert m.regulatory_bps_sell > 0
    assert m.slippage_bps_one_way == 15.0


def test_buy_sell_fills_worsen_price():
    m = webull_long_equity(tier=LiquidityTier.SMALL, slip_bps_one_way=10.0)
    assert apply_buy_fill(100.0, m) > 100.0
    assert apply_sell_fill(100.0, m) < 100.0


def test_rt_friction_includes_slip_twice():
    m = webull_long_equity(tier=LiquidityTier.MEGA)  # 2 bps slip
    rt = round_trip_friction_bps(m)
    assert rt >= 4.0  # 2+2 slip at least
    assert rt < 10.0


def test_tier_heuristic():
    assert tier_for_price_adv(150.0, 5e7) == LiquidityTier.MEGA
    assert tier_for_price_adv(5.0, 1e6) == LiquidityTier.SMALL
