"""Warrior policy v14: causal scanner watch with sealed 3.0 entry checklist."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ...execution import EXECUTION_MODEL, ExecutionConfig
from . import policy as v1


POLICY_ID = "warrior_pattern_score_v14"
DECISION_SOURCE = "deterministic_policy"
USES_SESSION_EXECUTION_CONFIG = True
SETTINGS = v1.PolicySettings(
    entry_threshold=65.0,
    entry_cutoff="11:00",
    exit_threshold=50.0,
    scanner_event_required=True,
    scanner_event_checklist_watch=True,
    entry_action="ENTER_CLOSE",
)
POLICY_SPEC = {
    **v1.POLICY_SPEC,
    "entry_threshold": 65.0,
    "entry_cutoff": "11:00",
    "exit_threshold": 50.0,
    "scanner_event_required": True,
    "scanner_event_checklist_watch": True,
    "entry_action": "ENTER_CLOSE",
    "complete_five_minute_bars_required": True,
    "scanner_event_release_delay_minutes": 4,
    "policy_generation": 14,
}
PolicyError = v1.PolicyError


def _identity(value: dict[str, Any]) -> dict[str, Any]:
    out = dict(value)
    out["policy_id"] = POLICY_ID
    if isinstance(out.get("thought"), str):
        out["thought"] = out["thought"].replace(v1.POLICY_ID, POLICY_ID)
    return out


def decisions_for_ticks(
    ticks: Iterable[dict[str, Any]],
    execution_config: ExecutionConfig | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        _identity(value)
        for value in v1.decisions_for_ticks(ticks, execution_config, settings=SETTINGS)
    ]


def apply_to_session(session_dir: str | Path) -> list[dict[str, Any]]:
    from ... import recorder
    from ...fsutils import atomic_write_json

    directory = Path(session_dir)
    session_path = directory / "session.json"
    session = recorder._load_json(session_path, {}) or {}
    skill = session.get("skill") or {}
    if session.get("status") == "complete":
        raise PolicyError(f"session {directory.name} is finalized")
    if session.get("strategy") != "warrior" or session.get("config", {}).get(
        "execution_model"
    ) != EXECUTION_MODEL:
        raise PolicyError("Warrior policy requires warrior deterministic_ohlc_v1")
    if (
        str(skill.get("decision_source") or "").strip().lower() != DECISION_SOURCE
        or skill.get("decision_policy") != POLICY_ID
    ):
        raise PolicyError("Warrior policy skill provenance is invalid")
    for field in (
        "session_from_open", "five_minute_context", "candlebar_context",
        "strict_prior_three_context", "require_complete_five_minute_bars",
        "scanner_event_context", "scanner_event_start", "entry_bracket_required",
        "scanner_event_checklist_watch",
    ):
        if not v1._is_true(skill.get(field)):
            raise PolicyError(f"Warrior policy requires {field}: true")
    if int(skill.get("scanner_event_release_delay_minutes") or 0) != 4:
        raise PolicyError("Warrior policy requires a four-minute scanner-event release delay")
    if v1._is_true(skill.get("scanner_event_include_reason")):
        raise PolicyError("Warrior policy requires scanner_event_include_reason: false")
    if recorder._last_logged_i(directory / "decisions.jsonl") >= 0:
        raise PolicyError("Warrior policy refuses a session with existing decisions")
    meta, ticks, _ = recorder._parse_stream(directory / "stream.jsonl")
    if meta is None or not ticks or not v1._is_true(meta.get("scanner_event_context")):
        raise PolicyError("published stream lacks causal scanner-event context")
    errors = recorder.stream_integrity_errors(directory, session)
    if errors:
        raise PolicyError(
            "Warrior policy refuses stream data-integrity failure — " + "; ".join(errors)
        )
    records = decisions_for_ticks(ticks, session.get("config", {}))
    session["decision_policy"] = {"source": DECISION_SOURCE, "id": POLICY_ID}
    atomic_write_json(session_path, session, indent=2)
    for record in records:
        recorder.log(directory, record)
    return records


POLICY_CONTRACT_SUBJECTS = (
    *v1.POLICY_CONTRACT_SUBJECTS,
    _identity,
    decisions_for_ticks,
    apply_to_session,
)
