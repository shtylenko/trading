"""Tests for the deterministic Warrior pattern-confluence policy."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from trading.llm_trader import batchsim, recorder
from trading.llm_trader.execution import ExecutionConfig
from trading.llm_trader.strategies.warrior.policy import (
    DECISION_SOURCE,
    ENTRY_BRACKET,
    POLICY_ID,
    WarriorPatternPolicy,
    apply_to_session,
    decisions_for_ticks,
    PolicySettings,
)
from trading.llm_trader.strategies.warrior import policy_v2


def _event(
    pattern: str,
    *,
    direction: str = "bullish",
    score: float = 1.0,
) -> dict:
    return {
        "pattern": pattern,
        "direction": direction,
        "score": score,
        "resolution": "5min",
        "time": "09:49",
        "evidence": {},
    }


def _entry_tick(i: int = 0, time: str = "09:49") -> dict:
    return {
        "type": "tick",
        "i": i,
        "time": time,
        "o": 10.05,
        "h": 10.20,
        "l": 9.90,
        "c": 10.18,
        "v": 10_000,
        "vwap": 10.00,
        "ema9": 10.10,
        "ema20": 10.00,
        "macd_hist": 0.05,
        "rvol_bar": 1.6,
        "new_high": True,
        "candlebar_patterns": [],
        "bar5_complete": {
            "time": "09:45",
            "o": 9.90,
            "h": 10.20,
            "l": 9.70,
            "c": 10.18,
            "v": 4_000,
            "prior_3_count": 3,
            "prior_3_high": 10.00,
            "prior_3_low": 9.70,
            "prior_3_avg_volume": 2_000.0,
            "volume_ratio": 2.0,
            "candlebar_patterns": [_event("bull_flag_break")],
        },
    }


def _manage_tick(i: int, **overrides) -> dict:
    row = {
        "type": "tick",
        "i": i,
        "time": f"09:{49 + i:02d}",
        "o": 10.18,
        "h": 10.25,
        "l": 10.05,
        "c": 10.20,
        "v": 10_000,
        "vwap": 10.00,
        "ema9": 10.15,
        "ema20": 10.05,
        "macd_hist": 0.03,
        "rvol_bar": 1.2,
        "new_high": False,
        "candlebar_patterns": [],
        "bar5_complete": None,
    }
    row.update(overrides)
    return row


def test_scanner_event_required_policy_refuses_entry_until_event_arrives():
    settings = PolicySettings(scanner_event_required=True)
    without = deepcopy(_entry_tick())
    blocked = decisions_for_ticks([without], settings=settings)[0]
    assert blocked["action"] == "OBSERVE"
    assert "scanner_event_not_received" in blocked["reason_codes"]

    with_event = deepcopy(_entry_tick())
    with_event["scanner_event"] = {
        "time": "09:49", "trigger": 10.00, "rvol": 3.0,
        "reason": "point-in-time scanner event", "signal": "historical_scanner_trigger",
    }
    accepted = decisions_for_ticks([with_event], settings=settings)[0]
    assert accepted["action"] == "ENTER_CLOSE"
    assert accepted["reason_codes"] == []


def test_scanner_event_immediate_confirmation_can_enter_without_bar5():
    tick = _entry_tick(time="09:30")
    tick["bar5_complete"] = None
    tick["scanner_event"] = {
        "time": "09:30", "trigger": 10.00, "rvol": 3.0,
        "reason": "point-in-time scanner event", "signal": "historical_scanner_trigger",
    }
    settings = PolicySettings(
        entry_threshold=70.0, scanner_event_required=True,
        scanner_event_immediate_confirmation=True,
    )
    decision = decisions_for_ticks([tick], settings=settings)[0]
    assert decision["action"] == "ENTER_CLOSE"
    assert decision["stop"] == 9.89


def _config() -> ExecutionConfig:
    return ExecutionConfig(risk_budget=40.0, buying_power=12_000.0)


def test_entry_score_is_exact_auditable_and_attaches_engine_bracket():
    record = decisions_for_ticks([_entry_tick()], _config())[0]

    assert record["action"] == "ENTER_CLOSE"
    assert record["entry_score"] == 100.0
    assert record["score_components"] == {
        "pattern": 30.0,
        "volume": 25.0,
        "trend": 20.0,
        "quality": 15.0,
        "timing": 10.0,
    }
    assert record["stop"] == 9.69
    assert record["bracket"] == ENTRY_BRACKET
    assert record["policy_id"] == POLICY_ID
    assert record["decision_source"] == DECISION_SOURCE


def test_entry_requires_three_actual_prior_five_minute_bars():
    tick = _entry_tick()
    tick["bar5_complete"]["prior_3_count"] = 1

    record = decisions_for_ticks([tick], _config())[0]

    assert record["action"] == "OBSERVE"
    assert "prior_3_not_ready" in record["reason_codes"]


def test_current_bearish_pattern_vetoes_an_otherwise_full_score_entry():
    tick = _entry_tick()
    tick["candlebar_patterns"] = [
        _event("bearish_topping_tail", direction="bearish", score=0.8)
    ]

    record = decisions_for_ticks([tick], _config())[0]

    assert record["action"] == "OBSERVE"
    assert record["entry_score"] == 95.0
    assert "bearish_pattern_veto" in record["reason_codes"]


def test_exit_pressure_needs_confirmation_and_exits_at_50_or_more():
    entry = _entry_tick()
    bearish = _manage_tick(
        1,
        c=10.10,
        vwap=10.20,
        candlebar_patterns=[
            _event("bearish_topping_tail", direction="bearish", score=0.8)
        ],
    )

    records = decisions_for_ticks([entry, bearish], _config())

    assert records[1]["action"] == "EXIT_CLOSE"
    assert records[1]["exit_score"] == 55.0
    assert records[1]["reason_codes"] == ["exit_pressure"]


def test_bearish_pattern_alone_does_not_force_an_exit():
    records = decisions_for_ticks([
        _entry_tick(),
        _manage_tick(
            1,
            c=10.20,
            vwap=10.00,
            candlebar_patterns=[
                _event("bearish_breakout_failure", direction="bearish", score=1.0)
            ],
        ),
    ], _config())

    assert records[1]["exit_score"] == 25.0
    assert records[1]["action"] in {"OBSERVE", "SET_STOP"}


def test_early_momentum_promotes_the_stop_to_breakeven():
    records = decisions_for_ticks([
        _entry_tick(),
        _manage_tick(1, h=10.40, c=10.25),
    ], _config())

    assert records[1]["action"] == "SET_STOP"
    assert records[1]["stop"] == 10.2
    assert records[1]["reason_codes"] == ["early_free_trade"]


def test_first_engine_scale_fill_promotes_runner_stop_to_breakeven():
    records = decisions_for_ticks([
        _entry_tick(),
        _manage_tick(1, h=10.80, c=10.25),
    ], _config())

    assert records[1]["action"] == "SET_STOP"
    assert records[1]["reason_codes"] == ["first_scale_to_breakeven"]
    assert records[1]["stop"] == 10.2


def test_mandatory_flat_is_policy_authored_and_latched_until_position_is_flat():
    policy = WarriorPatternPolicy(_config())
    entry = policy.decide(_entry_tick())
    close = policy.decide(_manage_tick(1, time="15:55", h=10.30, c=10.20))

    assert entry["action"] == "ENTER_CLOSE"
    assert close["action"] == "EXIT_CLOSE"
    assert close["reason_codes"] == ["mandatory_15_55_flat"]
    assert policy.engine.shares == 0


def test_policy_replay_is_exactly_deterministic_and_runner_contract_names_warrior():
    ticks = [_entry_tick(), _manage_tick(1, h=10.40, c=10.25), _manage_tick(2)]
    first = decisions_for_ticks(deepcopy(ticks), _config())

    assert decisions_for_ticks(deepcopy(ticks), _config()) == first
    assert batchsim._policy_module_for("warrior").POLICY_ID == POLICY_ID
    contract = batchsim.deterministic_policy_runner_contract(
        POLICY_ID, strategy_id="warrior"
    )
    assert contract["decision_source"] == DECISION_SOURCE
    assert contract["policy_spec"]["entry_threshold"] == 75.0


def test_v2_policy_is_a_distinct_immutable_router_target():
    tick = _entry_tick()
    tick["bar5_complete"] = None
    records = policy_v2.decisions_for_ticks([tick], _config())

    assert records[0]["policy_id"] == policy_v2.POLICY_ID
    assert policy_v2.POLICY_ID in records[0]["thought"]
    assert batchsim._policy_module_for("warrior", policy_v2.POLICY_ID) is policy_v2
    assert batchsim.deterministic_policy_runner_contract(
        policy_v2.POLICY_ID, strategy_id="warrior"
    )["policy_spec"]["complete_five_minute_bars_required"] is True


def test_apply_finalize_and_audit_use_the_same_policy_and_leave_no_forced_exit(tmp_path):
    skill = (
        Path(__file__).parents[1]
        / "strategies/warrior/skills/trade_skills/5.0.0.md"
    )
    sdir = recorder.init(
        "TEST",
        "2025-03-10",
        root=tmp_path,
        skill=skill,
        pin_version="5.0.0",
        strategy="warrior",
        now=datetime(2026, 7, 22, 10, 0, 0),
    )
    rows = [
        {
            "type": "meta",
            "ticker": "TEST",
            "date": "2025-03-10",
            "session_end": "16:00",
            "strict_prior_three_context": True,
        },
        _entry_tick(),
        _manage_tick(1, time="15:55", h=10.30, c=10.20),
        {"type": "end", "bars": 2, "close": 10.20},
    ]
    (sdir / "stream.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n"
    )

    records = apply_to_session(sdir)
    recorder.finalize(sdir)
    session = json.loads((sdir / "session.json").read_text())
    pnl = json.loads((sdir / "pnl.json").read_text())

    assert [record["action"] for record in records] == ["ENTER_CLOSE", "EXIT_CLOSE"]
    assert session["decision_policy"] == {
        "source": DECISION_SOURCE,
        "id": POLICY_ID,
    }
    assert pnl["forced_exit"] is False
    assert batchsim._deterministic_policy_integrity_errors(sdir, session) == []
