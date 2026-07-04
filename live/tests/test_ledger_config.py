from datetime import date

import pytest

from trading.live import ledger


# ── config / mode lock ──

def test_live_forbidden_outside_prod(env):
    assert env.live_allowed is False
    env.require_mode_allowed("paper")            # ok
    with pytest.raises(PermissionError):
        env.require_mode_allowed("live")


def test_live_allowed_in_prod(prod_env):
    assert prod_env.live_allowed is True
    prod_env.require_mode_allowed("live")         # no raise


# ── kill switch (DB + disk) ──

def test_kill_switch_db_and_disk(env):
    ledger.init_db(env)
    assert ledger.is_kill_switch_active(env) is False
    ledger.set_kill_switch(True, env=env)
    assert ledger.is_kill_switch_active(env) is True
    assert (env.state_dir / "KILL_SWITCH").exists()   # disk mirror present
    ledger.set_kill_switch(False, env=env)
    assert ledger.is_kill_switch_active(env) is False
    assert not (env.state_dir / "KILL_SWITCH").exists()


def test_kill_disk_file_alone_trips(env):
    ledger.init_db(env)
    # simulate DB-clean but a stray disk trip → fail-safe blocks
    (env.state_dir).mkdir(parents=True, exist_ok=True)
    (env.state_dir / "KILL_SWITCH").write_text("manual\n")
    assert ledger.is_kill_switch_active(env) is True


# ── run persistence ──

def test_record_and_fetch_run(env):
    ledger.init_db(env)
    ledger.record_run("run1", release_id="x03", asof=date(2024, 6, 3), mode="paper",
                      state="proposal_created", code_hash="sha256:abc",
                      target_book=[{"ticker": "AAA", "rank": 1}],
                      blocked=[{"ticker": "BBB", "reason": "denylist"}], env=env)
    last = ledger.latest_run(env)
    assert last["run_id"] == "run1" and last["state"] == "proposal_created"
    import json
    assert json.loads(last["target_book"])[0]["ticker"] == "AAA"
