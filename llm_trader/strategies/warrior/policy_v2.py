"""Warrior policy v2: v1 scoring on a complete-five-minute data contract.

The decision rules intentionally remain identical to v1 in this release.  The
version boundary exists because a five-minute bar that lacks one or more of its
constituent minutes is no longer eligible evidence.  Keeping this adapter
separate freezes the v1 implementation used by sealed 5.0.0 sessions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ...execution import EXECUTION_MODEL, ExecutionConfig
from . import policy as v1


POLICY_ID = "warrior_pattern_score_v2"
DECISION_SOURCE = "deterministic_policy"
USES_SESSION_EXECUTION_CONFIG = True
POLICY_SPEC = {
    **v1.POLICY_SPEC,
    "complete_five_minute_bars_required": True,
    "policy_generation": 2,
}
PolicyError = v1.PolicyError


def _v2_identity(record: dict[str, Any]) -> dict[str, Any]:
    """Replace v1 provenance in an otherwise identical causal decision."""
    out = dict(record)
    out["policy_id"] = POLICY_ID
    thought = out.get("thought")
    if isinstance(thought, str):
        thought = thought.replace(v1.POLICY_ID, POLICY_ID)
        if POLICY_ID not in thought:
            thought = f"deterministic policy {POLICY_ID}: {thought}"
        out["thought"] = thought
    return out


def decisions_for_ticks(
    ticks: Iterable[dict[str, Any]],
    execution_config: ExecutionConfig | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the v1 decision logic under this version's feed contract."""
    return [_v2_identity(record) for record in v1.decisions_for_ticks(ticks, execution_config)]


def apply_to_session(session_dir: str | Path) -> list[dict[str, Any]]:
    """Materialize v2 only when the sealed stream proves complete 5m context."""
    from ... import recorder
    from ...fsutils import atomic_write_json

    sdir = Path(session_dir)
    session_path = sdir / "session.json"
    session = recorder._load_json(session_path, {}) or {}
    if session.get("status") == "complete":
        raise PolicyError(f"session {sdir.name} is finalized")
    if session.get("strategy") != "warrior":
        raise PolicyError("Warrior pattern policy is available only to warrior sessions")
    if session.get("config", {}).get("execution_model") != EXECUTION_MODEL:
        raise PolicyError("Warrior pattern policy requires deterministic_ohlc_v1 execution")
    skill = session.get("skill") or {}
    if str(skill.get("decision_source") or "").strip().lower() != DECISION_SOURCE:
        raise PolicyError("Warrior pattern policy requires decision_source: deterministic_policy")
    if skill.get("decision_policy") != POLICY_ID:
        raise PolicyError(f"Warrior pattern policy requires decision_policy: {POLICY_ID}")
    for flag in (
        "session_from_open",
        "five_minute_context",
        "candlebar_context",
        "strict_prior_three_context",
        "require_complete_five_minute_bars",
        "completed_five_minute_entry_required",
        "entry_bracket_required",
    ):
        if not v1._is_true(skill.get(flag)):
            raise PolicyError(f"Warrior pattern policy requires {flag}: true")
    if recorder._last_logged_i(sdir / "decisions.jsonl") >= 0:
        raise PolicyError("Warrior pattern policy refuses a session with existing decisions")

    meta, ticks, _end = recorder._parse_stream(sdir / "stream.jsonl")
    if meta is None or not ticks:
        raise PolicyError("Warrior pattern policy requires a published stream with ticks")
    if not v1._is_true(meta.get("strict_prior_three_context")):
        raise PolicyError("published stream is missing strict prior-three context")
    if not v1._is_true(meta.get("require_complete_five_minute_bars")):
        raise PolicyError("published stream is missing complete-five-minute context")
    integrity_errors = recorder.stream_integrity_errors(sdir, session)
    if integrity_errors:
        raise PolicyError(
            "Warrior pattern policy refuses stream data-integrity failure — "
            + "; ".join(integrity_errors)
        )
    records = decisions_for_ticks(ticks, session.get("config", {}))

    session["decision_policy"] = {"source": DECISION_SOURCE, "id": POLICY_ID}
    atomic_write_json(session_path, session, indent=2)
    for record in records:
        recorder.log(sdir, record)
    return records


POLICY_CONTRACT_SUBJECTS = (
    *v1.POLICY_CONTRACT_SUBJECTS,
    _v2_identity,
    decisions_for_ticks,
    apply_to_session,
)
