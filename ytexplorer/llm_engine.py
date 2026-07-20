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
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .store import ExplorerStore, PACKAGE_DIR
from .scope import long_only_scope


SKILL_PATH = PACKAGE_DIR / "skills" / "video_hypothesis_extractor"
REPO_ROOT = PACKAGE_DIR.parent.parent
DISPOSITIONS = {"candidate", "needs-detail", "reference", "duplicate", "data-blocked", "rejected"}
CLAIM_TYPES = {"setup", "filter", "entry", "exit", "risk", "market_context"}
EVIDENCE_FRAGMENT_CHARS = 420


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


def build_evidence_fragments(text: str, *, max_chars: int = EVIDENCE_FRAGMENT_CHARS) -> list[dict[str, str]]:
    """Split an excerpt into stable, exact source fragments for model citation.

    The model selects an ID rather than copying text character-for-character.
    The application resolves that ID back to the original transcript text, so
    provenance stays strict without fragile quote copying.
    """
    fragments: list[dict[str, str]] = []
    start = 0
    while start < len(text):
        while start < len(text) and text[start].isspace():
            start += 1
        if start >= len(text):
            break
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(text.rfind(" ", start + max_chars // 2, end), text.rfind("\n", start + max_chars // 2, end))
            if boundary > start:
                end = boundary
        fragment = text[start:end].strip()
        if fragment:
            fragments.append({"id": f"F{len(fragments) + 1:03d}", "text": fragment})
        start = max(end, start + 1)
    return fragments


def validate_result(
    value: dict[str, Any],
    transcript: str,
    *,
    evidence_fragments: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Validate LLM output and prove each cited quote came from this transcript."""
    disposition = value.get("disposition")
    if disposition not in DISPOSITIONS:
        raise ExtractionError(f"invalid disposition: {disposition!r}")
    rationale = _require_string(value.get("rationale"), "rationale")
    raw_claims = value.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) > 3:
        raise ExtractionError("claims must be a list with at most three items")
    transcript_normal = _normal(transcript)
    fragment_text = {fragment["id"]: fragment["text"] for fragment in evidence_fragments or []}
    claims: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_claims):
        if not isinstance(raw, dict):
            raise ExtractionError(f"claim {i} is not an object")
        claim_type = raw.get("claim_type")
        if claim_type not in CLAIM_TYPES:
            raise ExtractionError(f"claim {i} has invalid claim_type")
        fragment_id = raw.get("evidence_fragment_id")
        if fragment_text and isinstance(fragment_id, str) and fragment_id in fragment_text:
            quote = fragment_text[fragment_id]
        else:
            # Legacy/recovery compatibility. New prompts require fragment IDs;
            # strict literal validation remains for historical output.
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
        assumption_register = candidate.get("assumption_register")
        missing_assumption_register = not isinstance(assumption_register, str) or not assumption_register.strip()
        candidate = {
            "claim_index": index,
            "title": _require_string(candidate.get("title"), "candidate.title"),
            "summary": _require_string(candidate.get("summary"), "candidate.summary"),
            "priority": float(priority),
            "feasibility": _require_string(candidate.get("feasibility"), "candidate.feasibility"),
            "data_requirements": _require_string(candidate.get("data_requirements"), "candidate.data_requirements", allow_empty=True),
            "prior_art": _require_string(candidate.get("prior_art"), "candidate.prior_art", allow_empty=True),
            "structural_difference": _require_string(candidate.get("structural_difference"), "candidate.structural_difference", allow_empty=True),
            "assumption_register": assumption_register.strip() if isinstance(assumption_register, str) else "",
            "missing_assumption_register": missing_assumption_register,
        }
    elif disposition in {"candidate", "duplicate", "data-blocked"}:
        raise ExtractionError(f"{disposition} disposition requires a candidate object")
    return {"disposition": disposition, "rationale": rationale, "claims": claims, "candidate": candidate}


def _bundle_gaps(claims: list[dict[str, Any]], candidate: dict[str, Any]) -> list[str]:
    """Return research requirements missing from the cited evidence bundle."""
    has_entry = any(c["claim_type"] in {"setup", "entry"} and c.get("trigger_rule") for c in claims)
    has_protection = any(c.get("invalidation_rule") for c in claims) or any(
        c["claim_type"] == "exit" and c.get("trigger_rule") for c in claims
    )
    has_data = bool(candidate.get("data_requirements", "").strip()) or any(c.get("required_data") for c in claims)
    gaps = []
    if not has_entry:
        gaps.append("an observable entry trigger")
    if not has_protection:
        gaps.append("an exit or invalidation rule")
    if not has_data:
        gaps.append("named data requirements")
    return gaps


def _fallback_assumption_register(claims: list[dict[str, Any]], gaps: list[str]) -> str:
    missing = sorted({item.strip() for claim in claims for item in claim.get("missing_fields", []) if item.strip()})
    items = [f"Freeze before testing: {item}." for item in missing + gaps]
    return "\n".join(items) or "Freeze all unstated execution assumptions before testing."


def select_relevant_excerpt(transcript: str, *, max_chars: int = 9000) -> str:
    """Choose one bounded, strategy-dense passage without asking an LLM to read a whole video."""
    if len(transcript) <= max_chars:
        return transcript
    terms = ("entry", "exit", "stop", "risk", "strategy", "setup", "trigger", "breakout", "pullback", "vwap", "volume")
    step, overlap = max_chars - 1500, 1500
    best = transcript[:max_chars]
    best_score = -1
    for start in range(0, len(transcript), step):
        window = transcript[start:start + max_chars]
        if not window:
            break
        lower = window.casefold()
        score = sum(lower.count(term) for term in terms)
        if score > best_score:
            best, best_score = window, score
        if start + max_chars >= len(transcript):
            break
    return best


def build_prompt(video: dict[str, Any], excerpt: str, evidence_fragments: list[dict[str, str]]) -> str:
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

Analyze only this bounded transcript excerpt (it may not represent the whole video).
For every claim, return one `evidence_fragment_id` from the numbered source
fragments below. Do not return `evidence_quote`; the application resolves the
fragment ID to exact source text. If no fragment supports a claim, omit it.
--- BEGIN NUMBERED SOURCE FRAGMENTS ---
{chr(10).join(f"[{fragment['id']}] {fragment['text']}" for fragment in evidence_fragments)}
--- END NUMBERED SOURCE FRAGMENTS ---

Research scope: this system only investigates long-only equity strategies. If
the source is primarily about futures, options, or short selling, return the
`rejected` disposition with an empty claims list and explain that it is out of
scope. Do not convert a short, options, or futures rule into a long-only rule.

Return only the strict JSON object required by the skill. Do not write files, run code,
search the web, inspect other repository files, or give advice. The transcript excerpt has no reliable
subtitle timestamps: use null timing fields and quote exact contiguous transcript passages."""


def build_quote_repair_prompt(raw_json: str, excerpt: str) -> str:
    return f"""Repair the JSON below. Return JSON only, preserving every field and value except
claims[*].evidence_quote. Each evidence_quote must be copied verbatim as one contiguous passage
from the transcript excerpt. Do not paraphrase, translate, shorten with ellipses, or add commentary.

Transcript excerpt:
--- BEGIN TRANSCRIPT ---
{excerpt}
--- END TRANSCRIPT ---

JSON to repair:
{raw_json}
"""


def build_assumption_repair_prompt(candidate: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    compact_claims = [{"summary": c["summary"], "missing_fields": c["missing_fields"]} for c in claims]
    return f"""Return only a JSON object with one key, assumption_register, whose value is a list of
concise assumptions that must be frozen before testing this source-backed trading idea. Do not claim
they came from the video; label them as research assumptions. Include every missing field.

Candidate: {json.dumps(candidate, ensure_ascii=False)}
Claims: {json.dumps(compact_claims, ensure_ascii=False)}
"""


class HermesExtractor:
    def __init__(self, store: ExplorerStore, *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self.store = store
        self.runner = runner

    @property
    def skill_hash(self) -> str:
        return _digest_text((SKILL_PATH / "SKILL.md").read_text(encoding="utf-8"))

    def _invoke(self, cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        """Terminate the whole Hermes process group when the hard budget expires."""
        if self.runner is not subprocess.run:  # deterministic seam for unit tests
            return self.runner(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=timeout, check=False)
        with subprocess.Popen(cmd, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    proc.kill()
                proc.communicate()
                raise exc
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout=stdout, stderr=stderr)

    def _repair_quotes(self, raw: str, excerpt: str, *, model: str | None, timeout: int) -> str:
        cmd = ["hermes", "-z", build_quote_repair_prompt(raw, excerpt), "--safe-mode"]
        if model:
            cmd.extend(["-m", model])
        proc = self._invoke(cmd, timeout=min(timeout, 30))
        if proc.returncode:
            raise ExtractionError("Hermes quote-repair failed")
        return (proc.stdout or "").strip()

    def _repair_assumptions(self, candidate: dict[str, Any], claims: list[dict[str, Any]], *, model: str | None, timeout: int) -> str:
        cmd = ["hermes", "-z", build_assumption_repair_prompt(candidate, claims), "--safe-mode"]
        if model:
            cmd.extend(["-m", model])
        try:
            proc = self._invoke(cmd, timeout=min(timeout, 30))
            value = _parse_json((proc.stdout or "").strip()) if proc.returncode == 0 else {}
            items = value.get("assumption_register") if isinstance(value, dict) else None
            if isinstance(items, list) and all(isinstance(item, str) and item.strip() for item in items):
                return "\n".join(f"Research assumption: {item.strip()}" for item in items)
        except (ExtractionError, subprocess.TimeoutExpired):
            pass
        return ""

    def extract(self, video_id: str, *, model: str | None = None, timeout: int = 90,
                force: bool = False, dry_run: bool = False) -> ExtractionResult:
        video = self.store.get_video(video_id)
        if video is None:
            raise ExtractionError(f"unknown video: {video_id}")
        transcript = video.get("transcript_text") or ""
        if not transcript or not video.get("transcript_hash"):
            raise ExtractionError(f"video {video_id} has no downloaded transcript")
        excerpt = select_relevant_excerpt(transcript)
        evidence_fragments = build_evidence_fragments(excerpt)
        excerpt_hash = _digest_text(excerpt)
        skill_hash = self.skill_hash
        if not force and self.store.extraction_exists(video_id, excerpt_hash, skill_hash):
            return ExtractionResult(video_id=video_id, status="skipped", skipped=True, detail="same bounded excerpt and skill already extracted")

        prompt = build_prompt(video, excerpt, evidence_fragments)
        prompt_hash = _digest_text(prompt)
        cmd = ["hermes", "-z", prompt, "--safe-mode"]
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
            proc = self._invoke(cmd, timeout=timeout)
        except FileNotFoundError as exc:
            self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", error="hermes CLI not found")
            raise ExtractionError("hermes CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", error=f"Hermes timed out after {timeout}s")
            raise ExtractionError(f"Hermes timed out after {timeout}s") from exc
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0:
            error = (proc.stderr or raw or f"Hermes exited {proc.returncode}")[:2000]
            self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                         prompt_hash=prompt_hash, status="error", raw_response=raw, error=error)
            raise ExtractionError(f"Hermes extraction failed: {error}")
        try:
            parsed = validate_result(_parse_json(raw), excerpt, evidence_fragments=evidence_fragments)
        except ExtractionError as exc:
            # The most common failure is a useful extraction with a paraphrased
            # citation. Repair only the quotes, then validate strictly again.
            if "evidence_quote is not an exact transcript excerpt" not in str(exc):
                self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                             prompt_hash=prompt_hash, status="invalid", raw_response=raw, error=str(exc))
                raise
            try:
                repaired_raw = self._repair_quotes(raw, excerpt, model=model, timeout=timeout)
                parsed = validate_result(_parse_json(repaired_raw), excerpt, evidence_fragments=evidence_fragments)
                raw = raw + "\n\n--- QUOTE REPAIR ---\n" + repaired_raw
            except (ExtractionError, subprocess.TimeoutExpired) as repair_exc:
                self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                             prompt_hash=prompt_hash, status="invalid", raw_response=raw,
                                             error=f"{exc}; quote repair failed: {repair_exc}")
                raise exc
        claim_ids = [self.store.add_claim(video_id=video_id, **claim) for claim in parsed["claims"]]
        candidate_id: str | None = None
        candidate = parsed["candidate"]
        if candidate is not None:
            candidate_in_scope, exclusions = long_only_scope({
                "title": candidate.get("title", ""),
                "description": candidate.get("summary", ""),
            })
            if not candidate_in_scope:
                # Retain any source-backed claims, but do not let a short-side
                # rule enter the long-only research queue merely because the
                # source title/description failed to expose its direction.
                candidate = None
                parsed["candidate"] = None
                parsed["disposition"] = "rejected"
                parsed["rationale"] += "; rejected by long-only scope: " + ", ".join(exclusions)
        if candidate is not None:
            candidate_args = dict(candidate)
            claim_id = claim_ids[candidate_args.pop("claim_index")]
            missing_assumptions = candidate_args.pop("missing_assumption_register")
            gaps = _bundle_gaps(parsed["claims"], candidate_args)
            if missing_assumptions:
                candidate_args["assumption_register"] = self._repair_assumptions(
                    candidate_args, parsed["claims"], model=model, timeout=timeout
                ) or _fallback_assumption_register(parsed["claims"], gaps)
            candidate_id = self.store.add_candidate(claim_id=claim_id, **candidate_args)
            target_status = "needs-detail" if missing_assumptions or gaps or parsed["disposition"] == "needs-detail" else {
                "candidate": "triage", "duplicate": "duplicate", "data-blocked": "data-blocked",
            }.get(parsed["disposition"])
            if target_status and target_status != "triage":
                rationale = parsed["rationale"]
                if gaps:
                    rationale += "; evidence bundle still needs " + ", ".join(gaps)
                self.store.transition_candidate(candidate_id, target_status, actor="hermes", rationale=rationale)
        self.store.record_extraction(video_id=video_id, transcript_hash=excerpt_hash, model=model, skill_hash=skill_hash,
                                     prompt_hash=prompt_hash, status="ok", raw_response=raw, parsed=parsed)
        return ExtractionResult(video_id=video_id, status="ok", disposition=parsed["disposition"], claim_ids=claim_ids,
                                candidate_id=candidate_id, detail=parsed["rationale"])


def extract_ready(store: ExplorerStore, *, limit: int = 20, model: str | None = None, timeout: int = 90,
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


def promote_needs_detail(store: ExplorerStore, *, limit: int = 20) -> list[str]:
    """Create transparent ``needs-detail`` queue cards from existing evidence.

    This is deliberately deterministic: it reuses stored claims and the
    extractor rationale, labels every unstated rule as an assumption, and does
    not ask an LLM to fabricate a complete strategy.
    """
    candidate_ids: list[str] = []
    for extraction in store.needs_detail_extractions(limit=limit):
        try:
            parsed = json.loads(extraction["parsed_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        claims = store.claims_for_video(extraction["video_id"])
        if not claims:
            continue
        best = max(claims, key=lambda claim: claim.get("extract_confidence") or 0)
        required_data = sorted({item for claim in claims for item in json.loads(claim["required_data_json"] or "[]")})
        missing = sorted({item for claim in claims for item in json.loads(claim["missing_fields_json"] or "[]")})
        claim_bundle = [{"claim_type": claim["claim_type"], "trigger_rule": claim.get("trigger_rule"),
                         "invalidation_rule": claim.get("invalidation_rule"), "required_data": required_data}
                        for claim in claims]
        gaps = _bundle_gaps(claim_bundle, {"data_requirements": ", ".join(required_data)})
        assumption_register = _fallback_assumption_register(
            [{"missing_fields": missing}], gaps
        )
        title = f"{extraction['video_title']} — evidence bundle"
        summary = " ".join(claim["summary"] for claim in claims[:3])
        candidate_id = store.add_candidate(
            claim_id=best["claim_id"], title=title, summary=summary, priority=20,
            feasibility="needs-detail", data_requirements=", ".join(required_data),
            prior_art="Not assessed; source-backed evidence bundle.",
            structural_difference="Not established until missing rules are frozen.",
            assumption_register=assumption_register,
        )
        store.transition_candidate(candidate_id, "needs-detail", actor="recovery", rationale=parsed.get("rationale", "incomplete evidence bundle"))
        candidate_ids.append(candidate_id)
    return candidate_ids
