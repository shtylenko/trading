from trading.live.broker import Account, OrderRequest, Position
from trading.live.risk import RiskPolicy, assess

ACC = Account(equity=100_000, buying_power=100_000)


def test_no_limits_no_violations():
    a = assess([OrderRequest("AAA", "buy", 1000)], account=ACC, positions={},
               prices={"AAA": 100.0}, policy=RiskPolicy())
    assert not a.halt and a.forced_approval == {}


def test_daily_loss_halts():
    a = assess([], account=ACC, positions={}, prices={},
               policy=RiskPolicy(max_daily_loss_pct=0.03), day_pnl_pct=-0.05)
    assert a.halt and "daily loss" in a.halt_reason


def test_drawdown_halts():
    a = assess([], account=ACC, positions={}, prices={},
               policy=RiskPolicy(max_drawdown_pct=0.10), drawdown_pct=-0.15)
    assert a.halt


def test_oversized_buy_forces_approval():
    # buying 200 * $100 = $20k = 20% of equity, limit 12%
    a = assess([OrderRequest("AAA", "buy", 200, client_order_id="co1")], account=ACC,
               positions={}, prices={"AAA": 100.0}, policy=RiskPolicy(max_single_position_pct=0.12))
    assert not a.halt and "co1" in a.forced_approval


def test_existing_holding_counts_toward_limit():
    pos = {"AAA": Position("AAA", 100, 100.0, 100.0)}   # already $10k
    a = assess([OrderRequest("AAA", "buy", 50, client_order_id="co1")], account=ACC,
               positions=pos, prices={"AAA": 100.0}, policy=RiskPolicy(max_single_position_pct=0.12))
    # 10k + 5k = 15k = 15% > 12% → forced approval
    assert "co1" in a.forced_approval


def test_sell_never_forced():
    a = assess([OrderRequest("AAA", "sell", 1000, client_order_id="co1")], account=ACC,
               positions={"AAA": Position("AAA", 1000, 100, 100)}, prices={"AAA": 100.0},
               policy=RiskPolicy(max_single_position_pct=0.01))
    assert a.forced_approval == {}     # exits are risk-reducing
