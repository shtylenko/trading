from datetime import date

from trading.live import ledger
from trading.live.broker import FakeBroker, OrderRequest, Position
from trading.live.executor import client_order_id, execute
from trading.live.logging import EventLogger

ASOF = date(2024, 6, 3)
PF = "pf1"


def _orders(*specs):
    return [OrderRequest(ticker=t, side=s, qty=q) for t, s, q in specs]


def test_full_fill_lifecycle(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0})
    rep = execute(_orders(("AAA", "buy", 10), ("BBB", "buy", 5)),
                  broker=broker, portfolio_id=PF, run_id="r1", asof=ASOF, env=env,
                  log=EventLogger(env))
    assert rep.submitted == 2 and rep.filled == 2 and rep.rejected == 0
    pos = ledger.get_positions(PF, env=env)
    assert pos["AAA"]["qty"] == 10 and pos["BBB"]["qty"] == 5


def test_partial_fill(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0}, partial={"AAA": 0.4})
    rep = execute(_orders(("AAA", "buy", 10)), broker=broker, portfolio_id=PF,
                  run_id="r1", asof=ASOF, env=env, log=EventLogger(env))
    assert rep.partial == 1 and rep.filled == 0
    assert ledger.get_positions(PF, env=env)["AAA"]["qty"] == 4.0


def test_rejected_order(env):
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0}, reject={"AAA"})
    rep = execute(_orders(("AAA", "buy", 10)), broker=broker, portfolio_id=PF,
                  run_id="r1", asof=ASOF, env=env, log=EventLogger(env))
    assert rep.rejected == 1 and rep.filled == 0
    assert "AAA" not in ledger.get_positions(PF, env=env)


def test_no_double_submit_on_rerun(env):
    """Re-running the same rebalance must not re-submit (idempotency, DESIGN §11)."""
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0})
    o = OrderRequest("AAA", "buy", 10, client_order_id=client_order_id(PF, "AAA", "buy", ASOF))
    r1 = execute([o], broker=broker, portfolio_id=PF, run_id="r1", asof=ASOF, env=env,
                 log=EventLogger(env))
    # second run, fresh order object, SAME deterministic coid
    o2 = OrderRequest("AAA", "buy", 10, client_order_id=client_order_id(PF, "AAA", "buy", ASOF))
    r2 = execute([o2], broker=broker, portfolio_id=PF, run_id="r2", asof=ASOF, env=env,
                 log=EventLogger(env))
    assert r1.filled == 1 and r2.skipped == 1 and r2.submitted == 0
    assert ledger.get_positions(PF, env=env)["AAA"]["qty"] == 10  # not doubled


def test_deterministic_client_order_id():
    a = client_order_id("pf1", "AAA", "buy", ASOF)
    assert a == client_order_id("pf1", "AAA", "buy", ASOF)
    assert a != client_order_id("pf1", "AAA", "sell", ASOF)


def test_ledger_positions_survive_restart(env, tmp_path):
    """Positions persisted to SQLite are readable by a fresh connection (restart)."""
    ledger.init_db(env)
    broker = FakeBroker(prices={"AAA": 100.0})
    execute(_orders(("AAA", "buy", 7)), broker=broker, portfolio_id=PF, run_id="r1",
            asof=ASOF, env=env, log=EventLogger(env))
    # simulate a process restart: brand-new env object pointing at the same db file
    from trading.live.config import load_env_config
    env2 = load_env_config()
    assert ledger.get_positions(PF, env=env2)["AAA"]["qty"] == 7
