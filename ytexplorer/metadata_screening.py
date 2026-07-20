"""Auditable Hermes screening of video metadata before transcript download."""
from __future__ import annotations

import hashlib
import json
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


def parse_screen_response(raw: str, expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"metadata screener returned invalid JSON: {exc.msg}") from exc
    decisions = value.get("decisions") if isinstance(value, dict) else None
    if not isinstance(decisions, list):
        raise ValueError("metadata screener result needs a decisions list")
    parsed: dict[str, dict[str, Any]] = {}
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("metadata screener decision is not an object")
        video_id = item.get("video_id")
        verdict = item.get("verdict")
        score = item.get("score")
        reason = item.get("reason")
        if video_id not in expected_ids or video_id in parsed:
            raise ValueError("metadata screener returned an unknown or duplicate video_id")
        if verdict not in VERDICTS or not isinstance(score, (int, float)) or not 0 <= float(score) <= 100:
            raise ValueError("metadata screener returned an invalid verdict or score")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("metadata screener reason is missing")
        parsed[video_id] = {"verdict": verdict, "score": float(score), "reason": reason.strip()[:500]}
    if set(parsed) != expected_ids:
        raise ValueError("metadata screener did not decide every supplied video")
    return parsed


class MetadataScreener:
    def __init__(self, store, *, runner=subprocess.run):
        self.store = store
        self.runner = runner

    def screen(self, videos: list[dict[str, Any]], *, model: str | None = None, timeout: int = 45) -> dict[str, dict[str, Any]]:
        if not videos:
            return {}
        prompt = build_screen_prompt(videos)
        command = ["hermes", "-z", prompt, "--safe-mode"]
        if model:
            command.extend(["-m", model])
        proc = self.runner(command, text=True, capture_output=True, timeout=timeout, check=False)
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout or "metadata screener failed")[:1000])
        decisions = parse_screen_response(proc.stdout or "", {video["video_id"] for video in videos})
        self.store.record_metadata_screenings(
            decisions,
            model=model,
            prompt_hash=_digest(prompt),
            screen_version=SCREEN_VERSION,
        )
        return decisions
