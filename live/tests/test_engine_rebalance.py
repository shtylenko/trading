from datetime import date, datetime, timezone

import pytest

from trading.live import ledger
from trading.live.broker import FakeBroker, Position
from trading.live.engine import (RebalanceBlocked, execute_pending, rebalance_portfolio)
from trading.live.policy import ApprovalPolicy
from trading.live.tests.conftest import FakeCandidate, FakeRelease

ASOF = date(2024, 6, 3)
PF = "pf1"


def _release():
    return FakeRelease([FakeCandidate("AAA", 0.9, 100.0), FakeCandidate("BBB", 0.8, 50.0),
                        FakeCandidate("CCC", 0.7, 25.0)])


def test_new_buys_park_for_approval_by_default(env):
    """Default policy (auto_max_pct=0): all new buys need approval, none auto-execute."""
    ledger.init_db(env)
    broker = FakeBroker(equity=100_000, prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)
    assert set(res.target) == {"AAA", "BBB", "CCC"}
    assert res.auto_executed == []
    assert {p["ticker"] for p in res.pending_approval} == {"AAA", "BBB", "CCC"}
    assert ledger.get_positions(PF, env=env) == {}        # nothing executed


def test_approve_then_execute(env):
    ledger.init_db(env)
    broker = FakeBroker(equity=100_000, prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)
    # approve AAA only
    aaa = next(p for p in res.pending_approval if p["ticker"] == "AAA")
    ledger.decide_approval(aaa["approval_id"], "approved", env=env)
    rep = execute_pending(res.proposal_id, broker, asof=ASOF, portfolio_id=PF, env=env)
    assert rep["filled"] == 1
    pos = ledger.get_positions(PF, env=env)
    assert "AAA" in pos and "BBB" not in pos                # only approved one executed


def test_expired_approval_not_executed(env):
    ledger.init_db(env)
    broker = FakeBroker(equity=100_000, prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    # zero-ttl policy → approvals are already expired by execute time
    pol = ApprovalPolicy(approval_ttl_minutes=0)
    res = rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env, policy=pol)
    aaa = next(p for p in res.pending_approval if p["ticker"] == "AAA")
    ledger.decide_approval(aaa["approval_id"], "approved", env=env)   # approve, but it's stale
    rep = execute_pending(res.proposal_id, broker, asof=ASOF, portfolio_id=PF, env=env)
    assert rep["submitted"] == 0                            # expired → skipped
    assert ledger.get_positions(PF, env=env) == {}


def test_matured_exit_auto_executes(env):
    """A matured held name that fell off-book → SELL auto-executes (risk-reducing).

    (Equal-weight reconcile does not top up held names that stay in target, so the
    engine's auto path is reached via exits, not adds.)
    """
    ledger.init_db(env)
    # hold OLD (matured, off-book) + AAA (in target); ledger matches broker (no mismatch)
    broker = FakeBroker(equity=100_000,
                        prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0, "OLD": 30.0},
                        positions={"OLD": Position("OLD", 4, 25.0, 30.0, "2024-05-01"),
                                   "AAA": Position("AAA", 1, 100.0, 100.0, "2024-05-01")})
    ledger.record_fill("seedO", portfolio_id=PF, ticker="OLD", side="buy", qty=4, price=25.0, env=env)
    ledger.record_fill("seedA", portfolio_id=PF, ticker="AAA", side="buy", qty=1, price=100.0, env=env)
    res = rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)
    assert "OLD" in res.auto_executed                        # matured exit auto-sold
    assert "OLD" not in ledger.get_positions(PF, env=env)    # position closed
    assert "AAA" not in res.auto_executed                    # held & in target → untouched
    assert {p["ticker"] for p in res.pending_approval} == {"BBB", "CCC"}  # new buys parked


def test_kill_switch_blocks_rebalance(env):
    ledger.init_db(env)
    ledger.set_kill_switch(True, env=env)
    broker = FakeBroker(prices={"AAA": 100.0})
    with pytest.raises(RebalanceBlocked):
        rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)


def test_reconcile_mismatch_blocks(env):
    """Broker shows a position the ledger doesn't know → block before trading."""
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0},
                        positions={"ZZZ": Position("ZZZ", 5, 10.0, 10.0, "2024-01-01")})
    with pytest.raises(RebalanceBlocked):
        rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)


def test_live_mode_forbidden_in_dev(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0}, mode="live")
    with pytest.raises(PermissionError):
        rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)
