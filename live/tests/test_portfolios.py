import pytest

from trading.live import ledger, portfolios as P


def test_onboard_and_get(env):
    cfg = P.onboard("pf1", "x03", capital=25000, secret_handle="ALPACA_PF1", env=env)
    assert cfg.portfolio_id == "pf1" and cfg.mode == "paper" and cfg.status == "active"
    assert cfg.manifest and cfg.manifest["release_id"] == "x03"   # release pinned
    got = P.get("pf1", env=env)
    assert got.release_id == "x03" and got.capital == 25000


def test_onboard_duplicate_rejected(env):
    P.onboard("pf1", "x03", env=env)
    with pytest.raises(ValueError):
        P.onboard("pf1", "x03", env=env)


def test_live_onboard_forbidden_in_dev(env):
    with pytest.raises(PermissionError):
        P.onboard("pf1", "x03", mode="live", env=env)


def test_live_onboard_allowed_in_prod(prod_env):
    cfg = P.onboard("pf1", "x03", mode="live", env=prod_env)
    assert cfg.mode == "live"


def test_list_excludes_retired(env):
    P.onboard("pf1", "x03", env=env)
    P.onboard("pf2", "x03", env=env)
    P.set_status("pf2", "retired", env=env)
    ids = {p.portfolio_id for p in P.list_portfolios(env=env)}
    assert ids == {"pf1"}
    assert {p.portfolio_id for p in P.list_portfolios(env=env, include_retired=True)} == {"pf1", "pf2"}


def test_onboard_writes_audit(env):
    P.onboard("pf1", "x03", env=env)
    actions = [a["action"] for a in ledger.recent_audit(env=env)]
    assert "portfolio.onboard" in actions
