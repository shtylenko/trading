"""Regression tests for the 2026-06-20 peer-review findings."""
from datetime import date

import pytest

from trading.live import ledger
from trading.live.broker import Account, FakeBroker, Position
from trading.live.config import LiveConfig
from trading.live.engine import RebalanceBlocked, execute_pending, rebalance_portfolio
from trading.live.portfolio import reconcile as portfolio_reconcile
from trading.live.tests.conftest import FakeCandidate, FakeRelease

ASOF = date(2024, 6, 3)


def _release():
    return FakeRelease([FakeCandidate("AAA", 0.9, 100.0), FakeCandidate("BBB", 0.8, 50.0),
                        FakeCandidate("CCC", 0.7, 25.0)])


# ── Finding 1: execute_pending portfolio/proposal isolation ──
def test_execute_pending_rejects_wrong_portfolio(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio("pfA", _release(), broker, context=None, asof=ASOF, env=env)
    # caller tries to execute pfA's proposal under pfB → must be refused
    with pytest.raises(RebalanceBlocked):
        execute_pending(res.proposal_id, broker, asof=ASOF, portfolio_id="pfB", env=env)


def test_execute_pending_kill_blocks(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio("pfA", _release(), broker, context=None, asof=ASOF, env=env)
    ledger.set_kill_switch(True, portfolio_id="pfA", env=env)
    with pytest.raises(RebalanceBlocked):
        execute_pending(res.proposal_id, broker, asof=ASOF, portfolio_id="pfA", env=env)


# ── Finding 3: per-portfolio denylist is enforced ──
def test_per_portfolio_denylist_blocks_buy(env):
    ledger.init_db(env)
    ledger.add_denylist_entry("AAA", "emergency block", scope="pfA", env=env)
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio("pfA", _release(), broker, context=None, asof=ASOF, env=env)
    assert "AAA" not in res.target            # denylisted name dropped from the book
    assert {"BBB", "CCC"} <= set(res.target)


def test_platform_denylist_in_db_applies_to_all(env):
    ledger.init_db(env)
    ledger.add_denylist_entry("BBB", "platform block", scope="platform", env=env)
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})
    res = rebalance_portfolio("pfX", _release(), broker, context=None, asof=ASOF, env=env)
    assert "BBB" not in res.target


# ── Finding 4: new-entry sizing uses the whole-book equal weight ──
def test_new_entry_sizing_equal_weight_full_book():
    """5 new names in a 50-name book each get ~equity/50, not equity/5."""
    cfg = LiveConfig(release_id="x03", cash_reserve_pct=0.0)
    target = [f"T{i}" for i in range(50)]
    held = {t: Position(t, 10, 100.0, 100.0, "2024-05-01") for t in target[:45]}  # hold 45
    prices = {t: 100.0 for t in target}
    acct = Account(equity=100_000, buying_power=100_000)
    orders = portfolio_reconcile(target, held, acct, hold_days=20, asof=ASOF,
                                 config=cfg, prices=prices)
    buys = [o for o in orders if o.side == "buy"]
    assert len(buys) == 5
    # each new name ≈ equity/50 = $2000 → 20 sh, NOT equity/5 = $20k → 200 sh
    assert all(o.qty == 20 for o in buys)


def test_sizing_uses_configured_capital_not_broker_equity():
    """A $5k portfolio sizes to its capital even when the broker account holds $100k."""
    cfg = LiveConfig(release_id="x04", cash_reserve_pct=0.0, capital=5_000)
    target = [f"T{i}" for i in range(50)]
    prices = {t: 100.0 for t in target}
    acct = Account(equity=100_000, buying_power=100_000)   # broker far larger than allocation
    orders = portfolio_reconcile(target, {}, acct, hold_days=20, asof=ASOF,
                                 config=cfg, prices=prices)
    buys = [o for o in orders if o.side == "buy"]
    assert len(buys) == 50
    # each name ≈ capital/50 = $100 → 1 sh, NOT equity/50 = $2000 → 20 sh
    assert all(o.qty == 1 for o in buys)
    assert sum(o.qty * prices[o.ticker] for o in buys) <= 5_000


def test_sizing_budget_capped_by_buying_power():
    """Configured capital cannot exceed what the account can actually fund."""
    cfg = LiveConfig(release_id="x04", cash_reserve_pct=0.0, capital=100_000)
    target = ["A", "B", "C", "D"]
    prices = {t: 100.0 for t in target}
    acct = Account(equity=100_000, buying_power=400)        # only $400 cash to deploy
    orders = portfolio_reconcile(target, {}, acct, hold_days=20, asof=ASOF,
                                 config=cfg, prices=prices)
    buys = [o for o in orders if o.side == "buy"]
    # per-name slice is $25k but the $400 cash cap allows only 4 shares total
    assert sum(o.qty for o in buys) <= 4


def test_sizing_falls_back_to_equity_without_capital():
    """capital=0 preserves the legacy behaviour (size to broker equity)."""
    cfg = LiveConfig(release_id="x04", cash_reserve_pct=0.0)   # capital defaults to 0
    target = [f"T{i}" for i in range(50)]
    prices = {t: 100.0 for t in target}
    acct = Account(equity=100_000, buying_power=100_000)
    orders = portfolio_reconcile(target, {}, acct, hold_days=20, asof=ASOF,
                                 config=cfg, prices=prices)
    buys = [o for o in orders if o.side == "buy"]
    assert all(o.qty == 20 for o in buys)        # equity/50 = $2000 → 20 sh


# ── Alpaca follow-up: fill-sync poll (P1 stand-in for the trade stream) ──
class _PollBroker(FakeBroker):
    """A broker whose get_order returns a controllable cumulative fill (the real-world
    case: a market order accepted at submit, then filled afterwards)."""
    def __init__(self, fills):                    # fills: coid -> (status, filled_qty, price)
        super().__init__()
        self._fills = fills

    def get_order(self, client_order_id):
        from trading.live.broker import BrokerOrder
        f = self._fills.get(client_order_id)
        if not f:
            return None
        status, qty, px = f
        return BrokerOrder(client_order_id, "ZZZ", "buy", qty, status,
                           filled_qty=qty, filled_avg_price=px, broker_order_id="b1")


def test_sync_fills_books_delta_idempotently(env):
    from trading.live.engine import sync_fills
    ledger.init_db(env)
    coid = "co_test1"
    ledger.record_intent(coid, run_id="r1", portfolio_id="pf", ticker="ZZZ", side="buy",
                         qty=10.0, env=env)
    ledger.update_intent(coid, status="accepted", env=env)   # submitted, not yet filled

    broker = _PollBroker({coid: ("filled", 10.0, 50.0)})
    rep = sync_fills("pf", broker, env=env)
    assert rep["new_fills"] == 1 and rep["filled"] == 1
    pos = ledger.get_positions("pf", env=env)
    assert pos["ZZZ"]["qty"] == 10.0
    assert pos["ZZZ"]["entry_date"] is not None        # hold-timer authority set on first fill

    # second sync must be a no-op (delta already booked) — no double-counting
    rep2 = sync_fills("pf", broker, env=env)
    assert rep2["new_fills"] == 0
    assert ledger.get_positions("pf", env=env)["ZZZ"]["qty"] == 10.0


def test_sync_fills_partial_then_full(env):
    from trading.live.engine import sync_fills
    ledger.init_db(env)
    coid = "co_test2"
    ledger.record_intent(coid, run_id="r1", portfolio_id="pf", ticker="ZZZ", side="buy",
                         qty=10.0, env=env)
    ledger.update_intent(coid, status="accepted", env=env)

    # first poll: partial 4 sh
    sync_fills("pf", _PollBroker({coid: ("partially_filled", 4.0, 50.0)}), env=env)
    assert ledger.get_positions("pf", env=env)["ZZZ"]["qty"] == 4.0
    # second poll: now fully filled 10 sh → only the 6-sh delta is booked
    rep = sync_fills("pf", _PollBroker({coid: ("filled", 10.0, 50.0)}), env=env)
    assert rep["new_fills"] == 1
    assert ledger.get_positions("pf", env=env)["ZZZ"]["qty"] == 10.0


def test_latest_run_is_scoped_per_portfolio(env):
    """latest_run(portfolio_id=A) returns A's run even when B rebalanced more recently."""
    from datetime import date as _date
    ledger.init_db(env)
    ledger.record_run("runA", release_id="x03", asof=_date(2024, 6, 1), mode="paper",
                      state="proposal_created", portfolio_id="pfA",
                      target_book=[{"ticker": "AAA", "rank": 1, "score": 0.5, "close": 10.0}],
                      env=env)
    ledger.record_run("runB", release_id="x04", asof=_date(2024, 6, 2), mode="paper",
                      state="proposal_created", portfolio_id="pfB",
                      target_book=[{"ticker": "BBB", "rank": 1, "score": 0.4, "close": 20.0}],
                      env=env)
    assert ledger.latest_run(env=env)["run_id"] == "runB"                 # global = newest
    assert ledger.latest_run(env=env, portfolio_id="pfA")["run_id"] == "runA"
    assert ledger.latest_run(env=env, portfolio_id="pfB")["run_id"] == "runB"


def test_risk_limits_measured_against_capital_not_broker_equity():
    """A position over the per-name limit relative to CAPITAL is forced to approval even
    though it's tiny relative to the broker account's equity."""
    from trading.live.risk import RiskPolicy, assess
    from trading.live.broker import Account, OrderRequest
    policy = RiskPolicy(max_single_position_pct=0.12)         # 12% per-name cap
    # $1,000 buy: 20% of a $5k allocation (breach) but 1% of $100k broker equity (no breach)
    order = OrderRequest("AAA", "buy", 10, client_order_id="co_a")
    acct = Account(equity=100_000, buying_power=100_000)
    prices = {"AAA": 100.0}
    # against broker equity → no forced approval
    a_equity = assess([order], account=acct, positions={}, prices=prices, policy=policy)
    assert not a_equity.forced_approval
    # against configured capital → forced approval
    a_capital = assess([order], account=acct, positions={}, prices=prices, policy=policy,
                       equity_basis=5_000)
    assert "co_a" in a_capital.forced_approval


def test_hold_timer_uses_ledger_entry_date_when_broker_lacks_one():
    """A held name with no broker entry_date still time-exits using the ledger's date."""
    from datetime import date as _date
    cfg = LiveConfig(release_id="x04", cash_reserve_pct=0.0)
    # broker reports the position but with NO entry_date (the Alpaca case)
    held = {"OLD": Position("OLD", 5, 100.0, 100.0, entry_date=None)}
    # simulate the engine's merge: entry_date older than the hold window
    held["OLD"].entry_date = "2024-01-01"
    orders = portfolio_reconcile(["NEW"], held, Account(equity=10_000, buying_power=10_000),
                                 hold_days=20, asof=_date(2024, 6, 3), config=cfg,
                                 prices={"NEW": 100.0, "OLD": 100.0})
    sells = [o for o in orders if o.side == "sell"]
    assert any(o.ticker == "OLD" for o in sells)   # matured + off-book → time exit fires
