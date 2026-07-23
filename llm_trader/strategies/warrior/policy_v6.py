"""Warrior policy v6: test a less hair-trigger exit-pressure threshold."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable, Mapping
from ...execution import EXECUTION_MODEL, ExecutionConfig
from . import policy as v1

POLICY_ID="warrior_pattern_score_v6"; DECISION_SOURCE="deterministic_policy"; USES_SESSION_EXECUTION_CONFIG=True
SETTINGS=v1.PolicySettings(entry_threshold=90.0, entry_cutoff="10:00", exit_threshold=70.0)
POLICY_SPEC={**v1.POLICY_SPEC,"entry_threshold":90.0,"entry_cutoff":"10:00","exit_threshold":70.0,"complete_five_minute_bars_required":True,"policy_generation":6}
PolicyError=v1.PolicyError
def _identity(r:dict[str,Any])->dict[str,Any]:
    o=dict(r);o["policy_id"]=POLICY_ID;t=o.get("thought")
    if isinstance(t,str): o["thought"]=t.replace(v1.POLICY_ID,POLICY_ID) if POLICY_ID in t.replace(v1.POLICY_ID,POLICY_ID) else f"deterministic policy {POLICY_ID}: {t}"
    return o
def decisions_for_ticks(ticks:Iterable[dict[str,Any]],execution_config:ExecutionConfig|Mapping[str,Any]|None=None)->list[dict[str,Any]]:
    return [_identity(r) for r in v1.decisions_for_ticks(ticks,execution_config,settings=SETTINGS)]
def apply_to_session(session_dir:str|Path)->list[dict[str,Any]]:
    from ... import recorder
    from ...fsutils import atomic_write_json
    d=Path(session_dir); sp=d/"session.json"; s=recorder._load_json(sp,{}) or {}; skill=s.get("skill") or {}
    if s.get("status")=="complete": raise PolicyError(f"session {d.name} is finalized")
    if s.get("strategy")!="warrior" or s.get("config",{}).get("execution_model")!=EXECUTION_MODEL: raise PolicyError("Warrior pattern policy requires warrior deterministic_ohlc_v1")
    if str(skill.get("decision_source") or "").strip().lower()!=DECISION_SOURCE or skill.get("decision_policy")!=POLICY_ID: raise PolicyError("Warrior pattern policy skill provenance is invalid")
    for f in ("session_from_open","five_minute_context","candlebar_context","strict_prior_three_context","require_complete_five_minute_bars","completed_five_minute_entry_required","entry_bracket_required"):
        if not v1._is_true(skill.get(f)): raise PolicyError(f"Warrior pattern policy requires {f}: true")
    if recorder._last_logged_i(d/"decisions.jsonl")>=0: raise PolicyError("Warrior pattern policy refuses a session with existing decisions")
    meta,ticks,_=recorder._parse_stream(d/"stream.jsonl")
    if meta is None or not ticks or not v1._is_true(meta.get("strict_prior_three_context")) or not v1._is_true(meta.get("require_complete_five_minute_bars")): raise PolicyError("published stream lacks required causal context")
    errors=recorder.stream_integrity_errors(d,s)
    if errors: raise PolicyError("Warrior pattern policy refuses stream data-integrity failure — "+"; ".join(errors))
    rs=decisions_for_ticks(ticks,s.get("config",{}));s["decision_policy"]={"source":DECISION_SOURCE,"id":POLICY_ID};atomic_write_json(sp,s,indent=2)
    for r in rs: recorder.log(d,r)
    return rs
POLICY_CONTRACT_SUBJECTS=(*v1.POLICY_CONTRACT_SUBJECTS,_identity,decisions_for_ticks,apply_to_session)
