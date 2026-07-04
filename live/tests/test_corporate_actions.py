from trading.live import ledger
from trading.live.corporate_actions import CorporateAction, apply_actions

PF = "pf1"


def _seed(env, ticker, qty, price):
    ledger.record_fill(f"seed-{ticker}", portfolio_id=PF, ticker=ticker, side="buy",
                       qty=qty, price=price, env=env)


def test_split_adjusts_position(env):
    ledger.init_db(env)
    _seed(env, "AAA", 10, 100.0)
    rep = apply_actions(PF, [CorporateAction("AAA", "split", "2024-06-03", ratio=2.0)], env=env)
    assert rep.applied == ["AAA"]
    pos = ledger.get_positions(PF, env=env)["AAA"]
    assert pos["qty"] == 20 and abs(pos["avg_entry_price"] - 50.0) < 1e-9


def test_reverse_split(env):
    ledger.init_db(env)
    _seed(env, "AAA", 60, 10.0)
    apply_actions(PF, [CorporateAction("AAA", "split", "2024-06-03", ratio=0.1)], env=env)  # 1:10
    pos = ledger.get_positions(PF, env=env)["AAA"]
    assert pos["qty"] == 6 and abs(pos["avg_entry_price"] - 100.0) < 1e-9


def test_dividend_credits_cash(env):
    ledger.init_db(env)
    _seed(env, "AAA", 10, 100.0)
    apply_actions(PF, [CorporateAction("AAA", "dividend", "2024-06-03", cash_per_share=0.5)], env=env)
    assert abs(ledger.get_cash(PF, env=env) - 5.0) < 1e-9      # 10 * 0.5


def test_merger_flagged_not_applied(env):
    ledger.init_db(env)
    _seed(env, "AAA", 10, 100.0)
    rep = apply_actions(PF, [CorporateAction("AAA", "merger", "2024-06-03")], env=env)
    assert rep.flagged == ["AAA"] and rep.applied == []
    assert ledger.get_positions(PF, env=env)["AAA"]["qty"] == 10  # untouched


def test_unheld_symbol_skipped(env):
    ledger.init_db(env)
    rep = apply_actions(PF, [CorporateAction("ZZZ", "split", "2024-06-03", ratio=2.0)], env=env)
    assert rep.skipped == ["ZZZ"] and rep.applied == []


def test_split_keeps_reconcile_consistent(env):
    """After a 2:1 split applied to the ledger, ledger qty matches a split-adjusted broker."""
    from trading.live.broker import Position
    from trading.live.reconcile import reconcile_positions
    ledger.init_db(env)
    _seed(env, "AAA", 10, 100.0)
    apply_actions(PF, [CorporateAction("AAA", "split", "2024-06-03", ratio=2.0)], env=env)
    broker = {"AAA": Position("AAA", 20, 50.0, 50.0)}     # broker auto-adjusted to 20 sh
    assert reconcile_positions(broker, ledger.get_positions(PF, env=env)).ok
