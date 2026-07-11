"""Focused tests for the deterministic v3 OHLC execution contract."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from trading.llm_trader import recorder
from trading.llm_trader.execution import EXECUTION_MODEL, ExecutionConfig, ExecutionEngine


def _bar(i, o, h, l, c, v=10_000):
    return {"i": i, "time": f"10:{20 + i:02d}", "o": o, "h": h, "l": l, "c": c, "v": v}


def _config(**overrides):
    values = {
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "entry_slippage_bps": 0.0,
        "exit_slippage_bps": 0.0,
        "commission_per_share": 0.0,
        "max_participation_rate": 1.0,
        "tick_size": 0.01,
    }
    values.update(overrides)
    return ExecutionConfig(**values)


def test_stop_gap_uses_open_and_can_exceed_planned_risk():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 10, 10.2, 9.8, 10), _bar(1, 8, 8.5, 7.5, 8)],
        [{"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0}],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 8.0, 100)
    ]
    assert pnl["initial_risk"] == 100.0
    assert pnl["realized_pnl"] == -200.0  # $2 gap through a planned $1 stop


def test_armed_entry_and_stop_same_bar_use_adverse_path():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 9.5, 10.5, 8.0, 9.2)],
        [{"i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0}],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 9.0, 100)
    ]
    assert pnl["realized_pnl"] == -100.0


def test_stop_wins_when_ohlc_hits_target_and_stop():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            _bar(1, 10, 10.5, 9.5, 10),
            _bar(2, 10, 12, 8, 9),
        ],
        [
            {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0},
            {"i": 1, "time": "10:21", "action": "SCALE_LIMIT", "target": 11.0, "fraction": 0.5},
        ],
        force_close=False,
    )
    assert [a["action"] for a in actions] == ["ENTER", "EXIT"]
    assert actions[-1]["price"] == 9.0


def test_entry_bracket_derives_fixed_r_targets_from_actual_fill():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            _bar(1, 10, 10.8, 9.7, 10.5),
            _bar(2, 10.5, 11.1, 10.2, 11.0),
            _bar(3, 11.0, 12.1, 10.8, 12.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [
                {"r_multiple": 1.0, "fraction": 0.333},
                {"r_multiple": 2.0, "fraction": 0.333},
            ]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("SCALE", 11.0, 33), ("SCALE", 12.0, 33),
    ]
    assert "+1.00R" in actions[1]["reason"]
    assert "+2.00R" in actions[2]["reason"]


def test_entry_bracket_never_retroactively_fills_or_beats_stop_first():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            # The +1R target is touched only after the entry, so the next bar
            # is eligible; its stop touch remains the adverse OHLC outcome.
            _bar(1, 10, 11.2, 8.5, 9.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.333}]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 9.0, 100),
    ]


def test_armed_entry_bracket_waits_until_the_bar_after_its_fill():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            # This bar triggers the entry and touches +1R, but an entry-attached
            # bracket is deliberately ineligible until the following bar.
            _bar(1, 9.8, 11.2, 9.5, 10.7),
            _bar(2, 10.7, 11.2, 10.4, 11.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0,
            "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.5}]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 100), ("SCALE", 2, 50),
    ]


def test_sizing_enforces_buying_power_and_volume_cap():
    engine = ExecutionEngine(_config(buying_power=50.0, max_participation_rate=0.2))
    actions, _, pnl = engine.run(
        [_bar(0, 10, 10.2, 9.8, 10, v=50)],
        [{"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0}],
        force_close=False,
    )
    # Risk permits 100 shares; 20% of volume permits 10; $50 buying power permits 5.
    assert actions[0]["shares"] == 5
    assert pnl["initial_risk"] == 5.0


def _stream(path):
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 10.4, "l": 9.7, "c": 10.2, "v": 10_000},
        {"type": "end", "bars": 2, "close": 10.2},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_recorder_requires_revealed_intents_and_derives_fills(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["config"]["risk_budget"] = 100.0
    session["config"]["buying_power"] = 10_000.0
    session["config"]["execution"] = {
        "entry_slippage_bps": 0.0, "exit_slippage_bps": 0.0,
        "commission_per_share": 0.0, "max_participation_rate": 1.0,
    }
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    with pytest.raises(ValueError, match="derives fills"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "fill_px": 10.0,
        })
    with pytest.raises(ValueError, match="does not match"):
        recorder.log(sdir, {"i": 0, "time": "10:21", "action": "ENTER_CLOSE", "stop": 9.0})

    assert recorder.resolve(sdir, 0)["position_shares"] == 0
    recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0})
    resolved = recorder.resolve(sdir, 1)
    assert resolved["position_shares"] == 100
    assert resolved["avg_entry"] == 10.0

    finalized = recorder.finalize(sdir, full_day=False)
    assert finalized["result"]["execution_model"] == EXECUTION_MODEL
    actions = json.loads((sdir / "actions.json").read_text())
    assert [(a["side"], a["shares"]) for a in actions] == [("buy", 100), ("sell", 100)]


def test_recorder_validates_entry_bracket_shape(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"]["entry_bracket_required"] = "true"
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    with pytest.raises(ValueError, match="requires an entry bracket"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
        })
    with pytest.raises(ValueError, match="strictly increasing"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [
                {"r_multiple": 1.0, "fraction": 0.5},
                {"r_multiple": 1.0, "fraction": 0.5},
            ]},
        })


def test_recorder_replays_a_valid_entry_bracket(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"].update({
        "execution_model": EXECUTION_MODEL,
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "execution": {
            "risk_budget": 100.0, "buying_power": 10_000.0,
            "entry_slippage_bps": 0.0, "exit_slippage_bps": 0.0,
            "commission_per_share": 0.0, "max_participation_rate": 1.0,
            "tick_size": 0.01,
        },
    })
    session["skill"]["entry_bracket_required"] = "true"
    session_path.write_text(json.dumps(session))
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 11.1, "l": 10.0, "c": 11.0, "v": 10_000},
        {"type": "end", "bars": 2, "close": 11.0},
    ]
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    recorder.log(sdir, {
        "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
        "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.333}]},
    })

    resolved = recorder.resolve(sdir, 1)
    assert resolved["position_shares"] == 67
    assert [(fill["action"], fill["shares"]) for fill in resolved["fills"]] == [("SCALE", 33)]


def test_init_freezes_deterministic_execution_assumptions(tmp_path):
    skill = tmp_path / "candidate.md"
    skill.write_text(
        "---\nname: trade-simulator\nversion: 3.0.0\n"
        "execution_model: deterministic_ohlc_v1\nentry_bracket_required: true\n---\n# candidate\n"
    )
    runner_contract = {"harness_version": "test", "prompt_hash": "sha256:p"}
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, skill=skill,
                         risk_budget=75.0, buying_power=5_000.0,
                         runner_contract=runner_contract,
                         now=datetime(2026, 7, 10, 10, 0, 0))
    runner_contract["prompt_hash"] = "mutated-after-init"
    config = json.loads((sdir / "session.json").read_text())["config"]
    assert config["execution_model"] == EXECUTION_MODEL
    assert config["execution"]["risk_budget"] == 75.0
    assert config["execution"]["buying_power"] == 5_000.0
    assert config["execution"]["max_participation_rate"] == 0.10
    session = json.loads((sdir / "session.json").read_text())
    assert session["runner_contract"]["prompt_hash"] == "sha256:p"
    assert session["skill"]["entry_bracket_required"] == "true"


def _attribution_stream(path):
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.1, "l": 9.9, "c": 10.0, "v": 100},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 12.1, "l": 10.0, "c": 12.0, "v": 100},
        {"type": "end", "bars": 2, "close": 12.0},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def _attribution_session(tmp_path, *, batch, ticker, trade):
    sdir = recorder.init(
        ticker, "2025-03-10", root=tmp_path, batch=batch,
        now=datetime(2026, 7, 10, 10, 0, 0),
    )
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"].update({
        "execution_model": EXECUTION_MODEL,
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "execution": {
            "risk_budget": 100.0,
            "buying_power": 10_000.0,
            "entry_slippage_bps": 100.0,
            "exit_slippage_bps": 100.0,
            "commission_per_share": 0.01,
            "max_participation_rate": 0.10,
            "tick_size": 0.01,
        },
    })
    session_path.write_text(json.dumps(session))
    _attribution_stream(sdir / "stream.jsonl")
    if trade:
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0})
        recorder.log(sdir, {"i": 1, "time": "10:21", "action": "EXIT_CLOSE"})
    else:
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "STAND_DOWN"})
    recorder.finalize(sdir, full_day=False)
    return sdir


def test_execution_attribution_replays_intents_without_writing(tmp_path, monkeypatch):
    batch = "attribution-test"
    traded = _attribution_session(tmp_path, batch=batch, ticker="TRADE", trade=True)
    _attribution_session(tmp_path, batch=batch, ticker="PASS", trade=False)
    original_actions = (traded / "actions.json").read_text()

    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    report = recorder.execution_attribution(batch)

    assert report["n_eligible"] == 2
    assert report["n_skipped"] == 0
    assert report["verification"]["recorded_mismatches"] == []
    rows = {row["profile"]: row for row in report["profiles"]}
    assert rows["recorded"]["n"] == 2
    assert rows["recorded"]["trades"] == 1
    assert rows["recorded"]["stood_down"] == 1
    assert rows["no_commission"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["no_slippage"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["no_participation_cap"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["frictionless"]["pnl"] > rows["no_participation_cap"]["pnl"]
    assert rows["frictionless"]["fees"] == 0.0
    # Attribution only replays raw inputs in memory; it never rewrites sealed artifacts.
    assert (traded / "actions.json").read_text() == original_actions


def test_execution_attribution_rejects_legacy_only_batch(tmp_path, monkeypatch):
    sdir = tmp_path / "legacy"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "status": "complete", "batch": "legacy-batch", "ticker": "OLD",
        "historical_date": "2025-03-10", "config": {"execution_model": "reported_fill_v1"},
    }))
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)

    with pytest.raises(ValueError, match="no completed deterministic_ohlc_v1 sessions"):
        recorder.execution_attribution("legacy-batch")
