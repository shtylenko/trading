"""Tests for the deterministic cup-handle decision policy."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from trading.llm_trader import recorder
from trading.llm_trader.strategies.cup_handle.policy import (
    DECISION_SOURCE,
    POLICY_ID,
    PolicyError,
    apply_to_session,
    decisions_for_ticks,
)


def _plan() -> dict:
    return {
        "signal_as_of": "2025-03-10",
        "trigger": 10.10,
        "stop": 9.00,
        "target1": 11.20,
        "target2": 12.30,
        "atr": 1.0,
        "cup_depth_px": 2.0,
        "max_entry_gap_atr": 0.5,
        "arm_expiry_bars": 5,
    }


def _tick(i: int, date: str, *, setup: bool = False) -> dict:
    return {
        "type": "tick",
        "i": i,
        "date": date,
        "time": "16:00",
        "o": 10.0,
        "h": 10.2,
        "l": 9.8,
        "c": 10.0,
        "v": 10_000,
        "sma20": 9.0,
        "sma50": 8.0,
        "sma200": 7.0,
        "atr14": 1.0,
        "rvol": 1.2,
        "above_sma20": True,
        "above_sma50": True,
        "above_sma200": True,
        "sma50_rising": True,
        "is_setup_day": setup,
        **({"scanner_plan": _plan()} if setup else {}),
    }


def _stream_rows() -> list[dict]:
    return [_tick(0, "2025-03-10"), _tick(1, "2025-03-11", setup=True), _tick(2, "2025-03-12")]


def test_policy_arms_only_the_revealed_scanner_plan_and_is_replayable():
    ticks = _stream_rows()

    first = decisions_for_ticks(ticks)
    assert decisions_for_ticks(ticks) == first
    assert [record["action"] for record in first] == ["OBSERVE", "ARM_BUY_STOP", "OBSERVE"]
    assert all(record["policy_id"] == POLICY_ID for record in first)
    assert all(record["decision_source"] == DECISION_SOURCE for record in first)
    assert first[1] == {
        "i": 1,
        "time": "16:00",
        "action": "ARM_BUY_STOP",
        "thought": (
            "deterministic policy cup_handle_auto_arm_v1: arm the causal scanner "
            "plan; engine owns execution and exits"
        ),
        "policy_id": POLICY_ID,
        "decision_source": DECISION_SOURCE,
        "trigger": 10.10,
        "stop": 9.00,
        "atr": 1.0,
        "max_entry_gap_atr": 0.5,
        "expiry_bars": 5,
    }


@pytest.mark.parametrize(
    ("ticks", "message"),
    [
        ([_tick(0, "2025-03-10")], "exactly one setup tick; found 0"),
        ([_tick(0, "2025-03-10", setup=True), _tick(1, "2025-03-11", setup=True)], "found 2"),
    ],
)
def test_policy_requires_exactly_one_setup_tick(ticks, message):
    with pytest.raises(PolicyError, match=message):
        decisions_for_ticks(ticks)


def test_policy_rejects_malformed_plan_before_emitting_any_intent():
    ticks = _stream_rows()
    ticks[1]["scanner_plan"]["target2"] = "unknown"

    with pytest.raises(PolicyError, match="target2 must be a finite number"):
        decisions_for_ticks(ticks)


def test_apply_to_session_uses_recorder_and_stamps_provenance(tmp_path):
    skill = Path(__file__).parents[1] / "strategies/cup_handle/skills/trade_skills/0.7.0.md"
    sdir = recorder.init(
        "TEST",
        "2025-03-11",
        root=tmp_path,
        skill=skill,
        pin_version="0.7.0",
        strategy="cup_handle",
        now=datetime(2026, 7, 17, 10, 0, 0),
    )
    rows = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-11", "strategy": "cup_handle",
         "horizon": "multi_day", "bar_resolution": "1day"},
        *_stream_rows(),
        {"type": "end", "bars": 3, "close": 10.0},
    ]
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    records = apply_to_session(sdir)

    persisted = [json.loads(line) for line in (sdir / "decisions.jsonl").read_text().splitlines()]
    assert persisted == records
    assert persisted[1]["engine_targets"] == {"target1": 11.2, "target2": 12.3}
    session = json.loads((sdir / "session.json").read_text())
    assert session["skill"]["decision_source"] == DECISION_SOURCE
    assert session["skill"]["decision_policy"] == POLICY_ID
    assert session["decision_policy"] == {"source": DECISION_SOURCE, "id": POLICY_ID}
    with pytest.raises(PolicyError, match="existing decisions"):
        apply_to_session(sdir)


def test_apply_to_session_fails_closed_before_writing_on_invalid_plan(tmp_path):
    skill = Path(__file__).parents[1] / "strategies/cup_handle/skills/trade_skills/0.7.0.md"
    sdir = recorder.init(
        "TEST",
        "2025-03-11",
        root=tmp_path,
        skill=skill,
        pin_version="0.7.0",
        strategy="cup_handle",
        now=datetime(2026, 7, 17, 10, 0, 1),
    )
    rows = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-11", "strategy": "cup_handle",
         "horizon": "multi_day", "bar_resolution": "1day"},
        *_stream_rows(),
    ]
    rows[2]["scanner_plan"]["target1"] = "unknown"
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    with pytest.raises(PolicyError, match="target1 must be a finite number"):
        apply_to_session(sdir)

    assert (sdir / "decisions.jsonl").read_text() == ""
    session = json.loads((sdir / "session.json").read_text())
    assert "decision_policy" not in session
