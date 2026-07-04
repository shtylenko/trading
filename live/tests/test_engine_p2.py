from datetime import date

import pytest

from trading.live import ledger
from trading.live.broker import FakeBroker, Position
from trading.live.engine import RebalanceBlocked, rebalance_portfolio
from trading.live.notifications import FakeChannel, Notifier, Severity
from trading.live.policy import ApprovalPolicy
from trading.live.risk import RiskPolicy
from trading.live.tests.conftest import FakeCandidate, FakeRelease

ASOF = date(2024, 6, 3)
PF = "pf1"


def _release():
    return FakeRelease([FakeCandidate("AAA", 0.9, 100.0), FakeCandidate("BBB", 0.8, 50.0),
                        FakeCandidate("CCC", 0.7, 25.0)])


def _broker():
    return FakeBroker(equity=100_000, prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0})


def test_risk_halt_blocks_and_notifies(env):
    ledger.init_db(env)
    ch = FakeChannel()
    notifier = Notifier(channels=[ch], min_severity=Severity.WARN)
    with pytest.raises(RebalanceBlocked):
        rebalance_portfolio(PF, _release(), _broker(), context=None, asof=ASOF, env=env,
                            risk_policy=RiskPolicy(max_daily_loss_pct=0.03), day_pnl_pct=-0.10,
                            notifier=notifier)
    assert any(m.severity == Severity.CRITICAL for m in ch.sent)


def test_pending_approval_notifies(env):
    ledger.init_db(env)
    ch = FakeChannel()
    notifier = Notifier(channels=[ch], min_severity=Severity.WARN)
    res = rebalance_portfolio(PF, _release(), _broker(), context=None, asof=ASOF, env=env,
                              notifier=notifier)
    assert len(res.pending_approval) == 3
    assert any(m.severity == Severity.ACTION_REQUIRED for m in ch.sent)


def test_parity_drift_blocks_rebalance(env):
    """Active drift halts the whole rebalance (DESIGN §7: any order during drift → block)."""
    ledger.init_db(env)
    # two consecutive drift results → drift active
    ledger.record_parity("r1", PF, signal_match_pct=0.2, slippage_bps=0, drift=True, env=env)
    ledger.record_parity("r2", PF, signal_match_pct=0.2, slippage_bps=0, drift=True, env=env)
    assert ledger.parity_drift_active(PF, env=env)
    with pytest.raises(RebalanceBlocked):
        rebalance_portfolio(PF, _release(), _broker(), context=None, asof=ASOF, env=env)


def test_no_drift_when_fewer_than_two(env):
    ledger.init_db(env)
    ledger.record_parity("r1", PF, signal_match_pct=0.2, slippage_bps=0, drift=True, env=env)
    assert ledger.parity_drift_active(PF, env=env) is False    # needs 2 consecutive


def test_account_identity_mismatch_blocks(env):
    """A registered portfolio bound to account A must refuse broker account B."""
    from trading.live import portfolios as P
    from trading.live.secrets import account_id_hash
    ledger.init_db(env)
    P.onboard(PF, "x03", env=env, account_id_hash=account_id_hash("ACCT-A"))
    broker = FakeBroker(prices={"AAA": 100.0}, account_id="ACCT-B")   # wrong account
    with pytest.raises(RebalanceBlocked):
        rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)


def test_account_identity_binds_on_first_connect(env):
    from trading.live import portfolios as P
    from trading.live.secrets import account_id_hash
    ledger.init_db(env)
    P.onboard(PF, "x03", env=env)                       # no account bound yet
    broker = FakeBroker(prices={"AAA": 100.0, "BBB": 50.0, "CCC": 25.0}, account_id="ACCT-A")
    rebalance_portfolio(PF, _release(), broker, context=None, asof=ASOF, env=env)
    assert P.get(PF, env=env).account_id_hash == account_id_hash("ACCT-A")   # bound
