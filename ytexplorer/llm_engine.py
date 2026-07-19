"""Hermes-backed transcript-to-hypothesis extraction.

Hermes is asked to produce strict JSON under a local skill. This module treats
the LLM as an untrusted parser: it validates shape, checks every quote against
the stored transcript, records the complete result, and only then updates the
research queue. It never launches a backtest or writes strategy code.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .store import ExplorerStore, PACKAGE_DIR


SKILL_PATH = PACKAGE_DIR / "skills" / "video_hypothesis_extractor"
JOB_DIR = PACKAGE_DIR / "data" / "hermes_jobs"
REPO_ROOT = PACKAGE_DIR.parent.parent
DISPOSITIONS = {"candidate", "needs-detail", "reference", "duplicate", "data-blocked", "rejected"}
CLAIM_TYPES = {"setup", "filter", "entry", "exit", "risk", "market_context"}


class ExtractionError(RuntimeError):
    pass


@dataclass
class ExtractionResult:
    video_id: str
    status: str
    disposition: Optional[str] = None
    claim_ids: list[str] | None = None
    candidate_id: Optional[str] = None
    skipped: bool = False
    detail: str = ""


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Hermes did not return valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ExtractionError("Hermes result must be a JSON object")
    return value


def _require_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ExtractionError(f"invalid or missing {field}")
    return value.strip()


def validate_result(value: dict[str, Any], transcript: str) -> dict[str, Any]:
    """Validate LLM output and prove each cited quote came from this transcript."""
    disposition = value.get("disposition")
    if disposition not in DISPOSITIONS:
        raise ExtractionError(f"invalid disposition: {disposition!r}")
    rationale = _require_string(value.get("rationale"), "rationale")
    raw_claims = value.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) > 3:
        raise ExtractionError("claims must be a list with at most three items")
    transcript_normal = _normal(transcript)
    claims: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_claims):
        if not isinstance(raw, dict):
            raise ExtractionError(f"claim {i} is not an object")
        claim_type = raw.get("claim_type")
        if claim_type not in CLAIM_TYPES:
            raise ExtractionError(f"claim {i} has invalid claim_type")
        quote = _require_string(raw.get("evidence_quote"), f"claims[{i}].evidence_quote")
        if _normal(quote) not in transcript_normal:
            raise ExtractionError(f"claim {i} evidence_quote is not an exact transcript excerpt")
        confidence = raw.get("extract_confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise ExtractionError(f"claim {i} extract_confidence must be 0..1")
        required_data = raw.get("required_data", [])
        missing_fields = raw.get("missing_fields", [])
        if not all(isinstance(x, str) for x in required_data) or not all(isinstance(x, str) for x in missing_fields):
            raise ExtractionError(f"claim {i} data fields must be string lists")
        claims.append({
            "claim_type": claim_type,
            "summary": _require_string(raw.get("summary"), f"claims[{i}].summary"),
            # ytmcp returns timing-free cleaned transcript text. The skill must leave these null.
            "evidence_start": None,
            "evidence_end": None,
            "evidence_quote": quote,
            "horizon": raw.get("horizon") if raw.get("horizon") in {"intraday", "overnight", "swing", "unknown"} else "unknown",
            "trigger_rule": raw.get("trigger_rule") if isinstance(raw.get("trigger_rule"), str) else None,
            "invalidation_rule": raw.get("invalidation_rule") if isinstance(raw.get("invalidation_rule"), str) else None,
            "required_data": required_data,
            "missing_fields": missing_fields,
            "extract_confidence": float(confidence),
        })
    candidate = value.get("candidate")
    if candidate is not None:
        if not isinstance(candidate, dict) or not claims:
            raise ExtractionError("candidate requires at least one valid claim")
        index = candidate.get("claim_index")
        if not isinstance(index, int) or not 0 <= index < len(claims):
            raise ExtractionError("candidate.claim_index must reference a claim")
        priority = candidate.get("priority", 0)
        if not isinstance(priority, (int, float)) or not 0 <= float(priority) <= 100:
            raise ExtractionError("candidate.priority must be 0..100")
        candidate = {
            "claim_index": index,
            "title": _require_string(candidate.get("title"), "candidate.title"),
            "summary": _require_string(candidate.get("summary"), "candidate.summary"),
            "priority": float(priority),
            "feasibility": _require_string(candidate.get("feasibility"), "candidate.feasibility"),
            "data_requirements": _require_string(candidate.get("data_requirements"), "candidate.data_requirements", allow_empty=True),
            "prior_art": _require_string(candidate.get("prior_art"), "candidate.prior_art", allow_empty=True),
            "structural_difference": _require_string(candidate.get("structural_difference"), "candidate.structural_difference", allow_empty=True),
            "assumption_register": _require_string(candidate.get("assumption_register"), "candidate.assumption_register", allow_empty=True),
        }
    elif disposition in {"candidate", "duplicate", "data-blocked"}:
        raise ExtractionError(f"{disposition} disposition requires a candidate object")
    return {"disposition": disposition, "rationale": rationale, "claims": claims, "candidate": candidate}


def build_prompt(video: dict[str, Any], transcript_path: Path) -> str:
    skill = (SKILL_PATH / "SKILL.md").read_text(encoding="utf-8")
    return f"""Process exactly one YouTube transcript. The version-controlled skill below is part of this task;
follow it exactly even if no Hermes profile skill has that name.

--- BEGIN video-hypothesis-extractor skill ---
{skill}
--- END video-hypothesis-extractor skill ---

Video metadata:
- video_id: {video['video_id']}
- title: {video['title']}
- channel: {video['channel_title']}
- source URL: {video.get('url') or 'unknown'}

Read only this transcript file: {transcript_path}

Return only the strict JSON object required by the skill. Do not write files, run code,
search the web, inspect other repository files, or give advice. The transcript has no reliable
subtitle timestamps: use null timing fields and quote exact contiguous transcript passages."""


class HermesExtractor:
    def __init__(self, store: ExplorerStore, *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self.store = store
        self.runner = runner

    @property
    def skill_hash(self) -> str:
        return _digest_text((SKILL_PATH / "SKILL.md").read_text(encoding="utf-8"))

    def extract(self, video_id: str, *, model: str | None = None, timeout: int = 300,
                force: bool = False, dry_run: bool = False) -> ExtractionResult:
        video = self.store.get_video(video_id)
        if video is None:
            raise ExtractionError(f"unknown video: {video_id}")
        transcript = video.get("transcript_text") or ""
        transcript_hash = video.get("transcript_hash") or ""
        if not transcript or not transcript_hash:
            raise ExtractionError(f"video {video_id} has no downloaded transcript")
        skill_hash = self.skill_hash
        if not force and self.store.extraction_exists(video_id, transcript_hash, skill_hash):
            return ExtractionResult(video_id=video_id, status="skipped", skipped=True, detail="same transcript and skill already extracted")

        JOB_DIR.mkdir(parents=True, exist_ok=True)
        transcript_path = JOB_DIR / f"{video_id}-{transcript_hash[:12]}.txt"
        transcript_path.write_text(transcript, encoding="utf-8")
        prompt = build_prompt(video, transcript_path)
        prompt_hash = _digest_text(prompt)
        cmd = ["hermes", "-z", prompt, "--yolo"]
        # A deployed Hermes profile may register the same skill by name. The prompt
        # always embeds the checked-in source of truth, so this remains portable.
        runtime_skill = os.getenv("YTEXPLORER_HERMES_SKILL")
        if runtime_skill:
            cmd.extend(["--skills", runtime_skill])
        if model:
            cmd.extend(["-m", model])
        if dry_run:
            return ExtractionResult(video_id=video_id, status="dry-run", detail=json.dumps(cmd))
        try:
            proc = self.runner(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError as exc:
            self.store.record_extraction(video_id=video_id, transcript_hash=transcript_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", error="hermes CLI not found")
            raise ExtractionError("hermes CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            self.store.record_extraction(video_id=video_id, transcript_hash=transcript_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", error=f"Hermes timed out after {timeout}s")
            raise ExtractionError(f"Hermes timed out after {timeout}s") from exc
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0:
            error = (proc.stderr or raw or f"Hermes exited {proc.returncode}")[:2000]
            self.store.record_extraction(video_id=video_id, transcript_hash=transcript_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", raw_response=raw, error=error)
            raise ExtractionError(f"Hermes extraction failed: {error}")
        try:
            parsed = validate_result(_parse_json(raw), transcript)
        except ExtractionError as exc:
            self.store.record_extraction(video_id=video_id, transcript_hash=transcript_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="invalid", raw_response=raw, error=str(exc))
            raise
        claim_ids = [self.store.add_claim(video_id=video_id, **claim) for claim in parsed["claims"]]
        candidate_id: str | None = None
        candidate = parsed["candidate"]
        if candidate is not None:
            candidate_args = dict(candidate)
            claim_id = claim_ids[candidate_args.pop("claim_index")]
            candidate_id = self.store.add_candidate(claim_id=claim_id, **candidate_args)
            target_status = {"candidate": "triage", "duplicate": "duplicate", "data-blocked": "data-blocked"}.get(parsed["disposition"])
            if target_status and target_status != "triage":
                self.store.transition_candidate(candidate_id, target_status, actor="hermes", rationale=parsed["rationale"])
        self.store.record_extraction(video_id=video_id, transcript_hash=transcript_hash, model=model, skill_hash=skill_hash,
                                     prompt_hash=prompt_hash, status="ok", raw_response=raw, parsed=parsed)
        return ExtractionResult(video_id=video_id, status="ok", disposition=parsed["disposition"], claim_ids=claim_ids,
                                candidate_id=candidate_id, detail=parsed["rationale"])


def extract_ready(store: ExplorerStore, *, limit: int = 20, model: str | None = None, timeout: int = 300,
                  force: bool = False, dry_run: bool = False) -> list[ExtractionResult]:
    extractor = HermesExtractor(store)
    ready = [v for v in store.list_videos(limit=10000) if v.get("transcript_status") == "ready"][:limit]
    results: list[ExtractionResult] = []
    for video in ready:
        try:
            results.append(extractor.extract(video["video_id"], model=model, timeout=timeout, force=force, dry_run=dry_run))
        except ExtractionError as exc:
            results.append(ExtractionResult(video_id=video["video_id"], status="error", detail=str(exc)))
    return results
