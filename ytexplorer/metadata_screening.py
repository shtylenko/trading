"""Auditable Hermes screening of video metadata before transcript download."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from typing import Any


SCREEN_VERSION = "metadata-long-only-v1"
VERDICTS = {"process", "defer", "out-of-scope"}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_screen_prompt(videos: list[dict[str, Any]]) -> str:
    records = [
        {
            "video_id": video["video_id"],
            "title": str(video.get("title") or ""),
            "description": str(video.get("description") or "")[:800],
            "channel": str(video.get("channel_title") or video.get("channel") or ""),
            "published_at": video.get("published_at") or video.get("published_date") or "",
        }
        for video in videos
    ]
    return f"""You are screening YouTube metadata for a long-only equity strategy research queue.
Do not infer rules that are not visible in the title/description. For each supplied video return:
- process: likely contains explicit, testable long-only equity rules worth downloading a transcript for;
- defer: potentially relevant but likely generic education, workflow, commentary, or insufficiently specific;
- out-of-scope: primarily futures, options, or short selling.

Return JSON only in this shape:
{{"decisions":[{{"video_id":"...","verdict":"process|defer|out-of-scope","score":0,"reason":"brief metadata-grounded reason"}}]}}

Return exactly one decision for every supplied video ID. `score` is 0 through 100 and ranks transcript value, not claimed profitability.

Videos:
{json.dumps(records, ensure_ascii=False)}"""


def parse_screen_response(
    raw: str,
    expected_ids: set[str],
    *,
    allow_partial: bool = False,
) -> dict[str, dict[str, Any]] | tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse a screen response, optionally retaining its valid subset.

    A batch contains independent decisions. One duplicated ID should not throw
    away the other nineteen valid decisions; missing/invalid rows simply use
    the deterministic fallback in the caller.
    """
    try:
        cleaned = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        start = cleaned.find("{")
        if start < 0:
            raise json.JSONDecodeError("No JSON object found", cleaned, 0)
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"metadata screener returned invalid JSON: {exc.msg}") from exc
    decisions = value.get("decisions") if isinstance(value, dict) else None
    if not isinstance(decisions, list):
        raise ValueError("metadata screener result needs a decisions list")
    parsed: dict[str, dict[str, Any]] = {}
    diagnostics: list[str] = []
    for position, item in enumerate(decisions, start=1):
        if not isinstance(item, dict):
            diagnostics.append(f"decision {position}: not an object")
            continue
        video_id = item.get("video_id")
        verdict = item.get("verdict")
        score = item.get("score")
        reason = item.get("reason")
        if video_id not in expected_ids:
            diagnostics.append(f"decision {position}: unknown video_id")
            continue
        if video_id in parsed:
            diagnostics.append(f"decision {position}: duplicate video_id {video_id}")
            continue
        if verdict not in VERDICTS or not isinstance(score, (int, float)) or not 0 <= float(score) <= 100:
            diagnostics.append(f"decision {position}: invalid verdict or score")
            continue
        if not isinstance(reason, str) or not reason.strip():
            diagnostics.append(f"decision {position}: missing reason")
            continue
        parsed[video_id] = {"verdict": verdict, "score": float(score), "reason": reason.strip()[:500]}
    missing = expected_ids - set(parsed)
    if missing:
        diagnostics.append(f"missing decisions for {len(missing)} video(s)")
    if not allow_partial and diagnostics:
        raise ValueError("metadata screener did not decide every supplied video")
    if allow_partial:
        if not parsed:
            raise ValueError("metadata screener returned no usable decisions")
        return parsed, diagnostics
    return parsed


class MetadataScreener:
    def __init__(self, store, *, runner=subprocess.run):
        self.store = store
        self.runner = runner

    def screen(
        self,
        videos: list[dict[str, Any]],
        *,
        model: str | None = None,
        timeout: int = 45,
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        if not videos:
            return {}, []
        prompt = build_screen_prompt(videos)
        command = ["hermes", "-z", prompt, "--safe-mode"]
        if model:
            command.extend(["-m", model])
        proc = self.runner(command, text=True, capture_output=True, timeout=timeout, check=False)
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout or "metadata screener failed")[:1000])
        decisions, diagnostics = parse_screen_response(
            proc.stdout or "",
            {video["video_id"] for video in videos},
            allow_partial=True,
        )
        self.store.record_metadata_screenings(
            decisions,
            model=model,
            prompt_hash=_digest(prompt),
            screen_version=SCREEN_VERSION,
        )
        return decisions, diagnostics
