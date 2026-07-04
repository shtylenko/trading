from datetime import date

from trading.live.broker import OrderRequest, Position
from trading.live.policy import ApprovalPolicy, classify
from trading.live.reconcile import reconcile_positions

ASOF = date(2024, 6, 3)


# ── reconcile ──

def test_reconcile_ok_when_matching():
    broker = {"AAA": Position("AAA", 10, 100, 100)}
    led = {"AAA": {"qty": 10}}
    assert reconcile_positions(broker, led).ok


def test_reconcile_flags_qty_mismatch():
    broker = {"AAA": Position("AAA", 10, 100, 100)}
    led = {"AAA": {"qty": 8}}
    rep = reconcile_positions(broker, led)
    assert not rep.ok and rep.diffs[0].delta == 2


def test_reconcile_flags_missing_side():
    rep = reconcile_positions({"AAA": Position("AAA", 5, 1, 1)}, {})
    assert not rep.ok and rep.diffs[0].ticker == "AAA"


# ── policy ──

def test_exits_auto_buys_need_approval():
    orders = [OrderRequest("OLD", "sell", 5), OrderRequest("NEW", "buy", 10)]
    decs = classify(orders, equity=100_000, held={"OLD"}, policy=ApprovalPolicy(),
                    prices={"NEW": 100.0})
    by = {d.order.ticker: d for d in decs}
    assert by["OLD"].auto is True            # risk-reducing exit auto
    assert by["NEW"].auto is False           # new buy needs approval


def test_add_within_band_auto():
    orders = [OrderRequest("HELD", "buy", 1)]
    decs = classify(orders, equity=100_000, held={"HELD"},
                    policy=ApprovalPolicy(auto_max_pct=0.5, auto_max_names=5),
                    prices={"HELD": 100.0})
    assert decs[0].auto is True              # 0.1% of equity, already held


def test_oversized_add_needs_approval():
    orders = [OrderRequest("HELD", "buy", 1000)]   # 100% of equity
    decs = classify(orders, equity=100_000, held={"HELD"},
                    policy=ApprovalPolicy(auto_max_pct=0.05, auto_max_names=5),
                    prices={"HELD": 100.0})
    assert decs[0].auto is False


def test_anomaly_forces_approval():
    orders = [OrderRequest("OLD", "sell", 5)]
    decs = classify(orders, equity=100_000, held={"OLD"}, policy=ApprovalPolicy(),
                    prices={}, anomalies={"OLD"})
    assert decs[0].auto is False            # even an exit waits under an anomaly flag
