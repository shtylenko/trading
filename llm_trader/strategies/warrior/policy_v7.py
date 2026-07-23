"""Warrior policy v7: v6 entry selection with an 80-point exit-pressure test."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable, Mapping
from ...execution import EXECUTION_MODEL, ExecutionConfig
from . import policy as v1

POLICY_ID = "warrior_pattern_score_v7"
DECISION_SOURCE = "deterministic_policy"
USES_SESSION_EXECUTION_CONFIG = True
SETTINGS = v1.PolicySettings(entry_threshold=90.0, entry_cutoff="10:00", exit_threshold=80.0)
POLICY_SPEC = {**v1.POLICY_SPEC, "entry_threshold": 90.0, "entry_cutoff": "10:00", "exit_threshold": 80.0, "complete_five_minute_bars_required": True, "policy_generation": 7}
PolicyError = v1.PolicyError
def _identity(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record); out["policy_id"] = POLICY_ID; thought = out.get("thought")
    if isinstance(thought, str): out["thought"] = thought.replace(v1.POLICY_ID, POLICY_ID)
    return out
def decisions_for_ticks(ticks: Iterable[dict[str, Any]], execution_config: ExecutionConfig | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    return [_identity(record) for record in v1.decisions_for_ticks(ticks, execution_config, settings=SETTINGS)]
def apply_to_session(session_dir: str | Path) -> list[dict[str, Any]]:
    from ... import recorder
    from ...fsutils import atomic_write_json
    sdir=Path(session_dir); session_path=sdir/"session.json"; session=recorder._load_json(session_path,{}) or {}; skill=session.get("skill") or {}
    if session.get("status")=="complete": raise PolicyError(f"session {sdir.name} is finalized")
    if session.get("strategy")!="warrior" or session.get("config",{}).get("execution_model")!=EXECUTION_MODEL: raise PolicyError("Warrior pattern policy requires warrior deterministic_ohlc_v1")
    if str(skill.get("decision_source") or "").strip().lower()!=DECISION_SOURCE or skill.get("decision_policy")!=POLICY_ID: raise PolicyError("Warrior pattern policy skill provenance is invalid")
    for flag in ("session_from_open","five_minute_context","candlebar_context","strict_prior_three_context","require_complete_five_minute_bars","completed_five_minute_entry_required","entry_bracket_required"):
        if not v1._is_true(skill.get(flag)): raise PolicyError(f"Warrior pattern policy requires {flag}: true")
    if recorder._last_logged_i(sdir/"decisions.jsonl")>=0: raise PolicyError("Warrior pattern policy refuses a session with existing decisions")
    meta,ticks,_=recorder._parse_stream(sdir/"stream.jsonl")
    if meta is None or not ticks or not v1._is_true(meta.get("strict_prior_three_context")) or not v1._is_true(meta.get("require_complete_five_minute_bars")): raise PolicyError("published stream lacks required causal context")
    errors=recorder.stream_integrity_errors(sdir,session)
    if errors: raise PolicyError("Warrior pattern policy refuses stream data-integrity failure — "+"; ".join(errors))
    records=decisions_for_ticks(ticks,session.get("config",{})); session["decision_policy"]={"source":DECISION_SOURCE,"id":POLICY_ID}; atomic_write_json(session_path,session,indent=2)
    for record in records: recorder.log(sdir,record)
    return records
POLICY_CONTRACT_SUBJECTS=(*v1.POLICY_CONTRACT_SUBJECTS,_identity,decisions_for_ticks,apply_to_session)
