import pytest

from trading.live import ledger
from trading.live.secrets import (IdentityMismatch, account_id_hash,
                                  verify_account_identity)


# ── per-portfolio + global kill isolation ──

def test_per_portfolio_kill_isolated(env):
    ledger.init_db(env)
    ledger.set_kill_switch(True, portfolio_id="pf1", env=env)
    assert ledger.is_kill_switch_active("pf1", env=env) is True
    assert ledger.is_kill_switch_active("pf2", env=env) is False    # isolated


def test_global_kill_blocks_all(env):
    ledger.init_db(env)
    ledger.set_kill_switch(True, portfolio_id=None, env=env)
    assert ledger.is_kill_switch_active("pf1", env=env) is True
    assert ledger.is_kill_switch_active("pf2", env=env) is True
    assert (env.state_dir / "KILL_SWITCH").exists()                 # disk mirror (global only)


def test_reset_per_portfolio_leaves_global(env):
    ledger.init_db(env)
    ledger.set_kill_switch(True, portfolio_id="pf1", env=env)
    ledger.set_kill_switch(False, portfolio_id="pf1", env=env)
    assert ledger.is_kill_switch_active("pf1", env=env) is False


def test_kill_audited(env):
    ledger.init_db(env)
    ledger.set_kill_switch(True, portfolio_id="pf1", actor="tester", env=env)
    rows = ledger.recent_audit(env=env)
    assert any(r["action"] == "kill_switch" and "pf1" in r["detail"] for r in rows)


# ── broker account identity (invariant #3) ──

def test_identity_match_passes():
    h = account_id_hash("ACCT-123")
    verify_account_identity("ACCT-123", h)            # no raise


def test_identity_mismatch_raises():
    h = account_id_hash("ACCT-123")
    with pytest.raises(IdentityMismatch):
        verify_account_identity("ACCT-999", h)        # wrong account → block


def test_identity_unbound_is_noop():
    verify_account_identity("anything", None)         # first connect, not yet bound
