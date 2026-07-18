"""Deterministic decision policy for causal trend-pullback plans.

Mirrors cup_handle auto-arm: on the setup tick, ARM_BUY_STOP with scanner plan
levels; OBSERVE all other ticks. Execution engine owns fills and exits.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Iterable


POLICY_ID = "trend_pullback_auto_arm_v1"
DECISION_SOURCE = "deterministic_policy"

_PLAN_FIELDS = (
    "signal_as_of",
    "trigger",
    "stop",
    "target1",
    "target2",
    "atr",
    "measured_move_px",
    "arm_expiry_bars",
    "max_entry_gap_atr",
)

_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


class PolicyError(ValueError):
    """The sealed stream cannot support this deterministic policy."""


def _policy_note() -> str:
    return (
        "deterministic policy " + POLICY_ID
        + ": arm the causal scanner plan; engine owns execution and exits"
    )


def _require_plan(tick: dict[str, Any]) -> dict[str, Any]:
    plan = tick.get("scanner_plan")
    if not isinstance(plan, dict):
        raise PolicyError("setup tick has no scanner_plan")
    missing = [field for field in _PLAN_FIELDS if plan.get(field) is None]
    if missing:
        raise PolicyError("scanner_plan missing field(s): " + ", ".join(missing))
    signal_as_of = plan["signal_as_of"]
    if not isinstance(signal_as_of, str) or not signal_as_of.strip():
        raise PolicyError("scanner_plan signal_as_of must be a non-empty string")

    def number(field: str, *, positive: bool = True) -> float:
        value = plan[field]
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(float(value))):
            raise PolicyError(f"scanner_plan {field} must be a finite number")
        value = float(value)
        if positive and value <= 0:
            raise PolicyError(f"scanner_plan {field} must be positive")
        if not positive and value < 0:
            raise PolicyError(f"scanner_plan {field} must be non-negative")
        return value

    trigger = number("trigger")
    stop = number("stop")
    target1 = number("target1")
    target2 = number("target2")
    number("atr")
    number("measured_move_px")
    number("max_entry_gap_atr", positive=False)
    expiry = plan["arm_expiry_bars"]
    if not isinstance(expiry, int) or isinstance(expiry, bool) or expiry < 1:
        raise PolicyError("scanner_plan arm_expiry_bars must be a positive integer")
    if stop >= trigger:
        raise PolicyError("scanner_plan stop must be below trigger")
    if target1 <= trigger or target2 <= target1:
        raise PolicyError("scanner_plan targets must be strictly above trigger")
    return plan


def decisions_for_ticks(ticks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(ticks)
    setup_rows = [tick for tick in rows if tick.get("is_setup_day")]
    if len(setup_rows) != 1:
        raise PolicyError(
            f"causal policy requires exactly one setup tick; found {len(setup_rows)}"
        )
    setup_i = setup_rows[0].get("i")
    if not isinstance(setup_i, int):
        raise PolicyError("setup tick has no integer i")

    records: list[dict[str, Any]] = []
    previous_i = -1
    for tick in rows:
        i = tick.get("i")
        hhmm = tick.get("time")
        if not isinstance(i, int) or i < 0:
            raise PolicyError("stream tick i must be a non-negative integer")
        if i <= previous_i:
            raise PolicyError("stream ticks must have strictly increasing i")
        if not isinstance(hhmm, str) or not _HHMM_RE.fullmatch(hhmm):
            raise PolicyError(f"stream tick i={i} time must be HH:MM")
        hour, minute = (int(part) for part in hhmm.split(":"))
        if hour > 23 or minute > 59:
            raise PolicyError(f"stream tick i={i} time must be a valid HH:MM")
        previous_i = i

        record: dict[str, Any] = {
            "i": i,
            "time": hhmm,
            "action": "OBSERVE",
            "thought": _policy_note(),
            "policy_id": POLICY_ID,
            "decision_source": DECISION_SOURCE,
        }
        if i == setup_i:
            plan = _require_plan(tick)
            record.update({
                "action": "ARM_BUY_STOP",
                "trigger": plan["trigger"],
                "stop": plan["stop"],
                "atr": plan["atr"],
                "max_entry_gap_atr": plan["max_entry_gap_atr"],
                "expiry_bars": plan["arm_expiry_bars"],
            })
        records.append(record)
    return records


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def apply_to_session(session_dir: str | Path) -> list[dict[str, Any]]:
    """Materialize the policy in an unfinalized, fully sealed trend_pullback session."""
    from ... import recorder
    from ...execution import EXECUTION_MODEL
    from ...fsutils import atomic_write_json

    sdir = Path(session_dir)
    session_path = sdir / "session.json"
    session = recorder._load_json(session_path, {}) or {}
    if session.get("status") == "complete":
        raise PolicyError(f"session {sdir.name} is finalized")
    if session.get("strategy") != "trend_pullback":
        raise PolicyError("auto-arm policy is available only to trend_pullback sessions")
    if session.get("config", {}).get("execution_model") != EXECUTION_MODEL:
        raise PolicyError("auto-arm policy requires deterministic_ohlc_v1 execution")
    skill = session.get("skill") or {}
    if str(skill.get("decision_source") or "").strip().lower() != DECISION_SOURCE:
        raise PolicyError("auto-arm policy requires decision_source: deterministic_policy")
    if skill.get("decision_policy") != POLICY_ID:
        raise PolicyError(f"auto-arm policy requires decision_policy: {POLICY_ID}")
    if not _is_true(skill.get("arm_on_scanner_plan_required")):
        raise PolicyError("auto-arm policy requires arm_on_scanner_plan_required")
    if not _is_true(skill.get("scanner_plan_targets_engine_owned")):
        raise PolicyError("auto-arm policy requires engine-owned scanner targets")
    if recorder._last_logged_i(sdir / "decisions.jsonl") >= 0:
        raise PolicyError("auto-arm policy refuses a session with existing decisions")

    meta, ticks, _end = recorder._parse_stream(sdir / "stream.jsonl")
    if meta is None or not ticks:
        raise PolicyError("auto-arm policy requires a published stream with ticks")
    integrity_errors = recorder.stream_integrity_errors(sdir, session)
    if integrity_errors:
        raise PolicyError(
            "auto-arm policy refuses stream data-integrity failure — "
            + "; ".join(integrity_errors)
        )
    records = decisions_for_ticks(ticks)

    session["decision_policy"] = {"source": DECISION_SOURCE, "id": POLICY_ID}
    atomic_write_json(session_path, session, indent=2)
    for record in records:
        recorder.log(sdir, record)
    return records
