"""Autonomous daily discovery pipeline driven by ``config/queries.yaml``."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .channel_audit import audit_samples, recommend_status
from .llm_engine import HermesExtractor
from .store import ExplorerStore


DEFAULT_PLAN_PATH = Path(__file__).resolve().parent / "config" / "queries.yaml"


@dataclass(frozen=True)
class QueryPlan:
    id: str
    query: str
    cadence: str
    upload_date: str | None
    max_results: int
    intent: str


def load_plan(path: Path | str | None = None) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path or DEFAULT_PLAN_PATH).read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("queries"), list):
        raise ValueError("queries.yaml must contain a queries list")
    queries: list[QueryPlan] = []
    for item in raw["queries"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("id", "query", "cadence", "intent")):
            raise ValueError("each query needs id, query, cadence, and intent")
        if item["cadence"] not in {"daily", "weekly", "monthly"}:
            raise ValueError(f"invalid cadence for {item['id']}")
        queries.append(QueryPlan(
            id=str(item["id"]), query=str(item["query"]), cadence=str(item["cadence"]),
            upload_date=str(item["upload_date"]) if item.get("upload_date") else None,
            max_results=int(item.get("max_results", 20)), intent=str(item["intent"]),
        ))
    return {"timezone": raw.get("timezone", "America/Chicago"), "daily_limits": raw.get("daily_limits", {}), "queries": queries}


def _audit_new_channel(store: ExplorerStore, channel_id: str, *, sample_size: int, fetch_transcripts: bool) -> dict[str, Any]:
    from .ytmcp_client import channel_videos, transcript

    source_rows = channel_videos(channel_id, sort_by="newest")[:sample_size]
    for row in source_rows:
        store.upsert_video(row, discovered_by=f"channel:{channel_id}")
        existing = store.get_video(row["video_id"])
        if fetch_transcripts and existing and existing.get("transcript_status") != "ready":
            result = transcript(row["video_id"])
            if "error" in result:
                store.mark_transcript_error(row["video_id"], str(result["error"]))
            else:
                store.set_transcript(row["video_id"], result.get("raw_text", ""), result.get("language_code", "en"))
    samples = [v for v in store.list_videos(limit=10000) if v["channel_id"] == channel_id][:sample_size]
    audit = audit_samples(samples)
    status, reason = recommend_status(audit)
    store.update_channel_audit(channel_id, sample_size=audit["sample_size"], trading_ratio=audit["trading_ratio"],
                               strategy_ratio=audit["strategy_ratio"], status=status, reason=reason)
    return {"channel_id": channel_id, "status": status, "reason": reason, **audit}


def run_scheduled(
    store: ExplorerStore, *, plan_path: Path | str | None = None, cadence: str = "daily",
    model: str | None = None, dry_run: bool = False, as_of: date | None = None,
) -> dict[str, Any]:
    """Run discovery → transcript → Hermes extraction → new-channel audit.

    Each unit fails independently and is reported in the job ledger; one malformed
    video or unavailable transcript cannot kill the whole daily run.
    """
    if cadence not in {"due", "daily", "weekly", "monthly"}:
        raise ValueError("cadence must be due, daily, weekly, or monthly")
    plan = load_plan(plan_path)
    run_date = as_of or datetime.now(ZoneInfo(plan["timezone"])).date()
    if cadence == "due":
        selected = [q for q in plan["queries"] if (
            q.cadence == "daily"
            or (q.cadence == "weekly" and run_date.weekday() == 0)
            or (q.cadence == "monthly" and run_date.day == 1)
        )]
    else:
        selected = [q for q in plan["queries"] if q.cadence == cadence]
    if dry_run:
        return {"mode": "dry-run", "cadence": cadence, "run_date": run_date.isoformat(), "timezone": plan["timezone"],
                "queries": [q.__dict__ for q in selected], "limits": plan["daily_limits"]}

    from .ytmcp_client import search, transcript

    extractor = HermesExtractor(store)
    newly_discovered_channels: set[str] = set()
    outcomes: list[dict[str, Any]] = []
    for item in selected:
        result: dict[str, Any] = {"id": item.id, "query": item.query, "new": 0, "transcripts": 0, "extracted": 0, "errors": []}
        try:
            rows = search(item.query, max_results=item.max_results, upload_date=item.upload_date)
        except Exception as exc:  # provider error belongs in the run report, not a crashed scheduler
            result["errors"].append(f"search: {exc}")
            outcomes.append(result)
            continue
        for row in rows:
            try:
                is_new = store.upsert_video(row, discovered_by=f"scheduled:{item.id}")
                if is_new:
                    result["new"] += 1
                    newly_discovered_channels.add(row["channel_identifier"])
                video = store.get_video(row["video_id"])
                if video and video.get("transcript_status") != "ready":
                    tx = transcript(row["video_id"])
                    if "error" in tx:
                        store.mark_transcript_error(row["video_id"], str(tx["error"]))
                        result["errors"].append(f"{row['video_id']}: transcript {tx['error']}")
                        continue
                    store.set_transcript(row["video_id"], tx.get("raw_text", ""), tx.get("language_code", "en"))
                    result["transcripts"] += 1
                extraction = extractor.extract(row["video_id"], model=model)
                if extraction.status == "ok":
                    result["extracted"] += 1
            except Exception as exc:
                result["errors"].append(f"{row.get('video_id', '?')}: {exc}")
        outcomes.append(result)

    limits = plan["daily_limits"]
    audit_outcomes = []
    for channel_id in sorted(newly_discovered_channels)[:int(limits.get("max_new_channels_to_audit", 3))]:
        try:
            audit_outcomes.append(_audit_new_channel(
                store, channel_id, sample_size=int(limits.get("channel_sample_size", 12)),
                fetch_transcripts=bool(limits.get("fetch_channel_transcripts", True)),
            ))
        except Exception as exc:
            audit_outcomes.append({"channel_id": channel_id, "status": "error", "error": str(exc)})
    outcome = {"mode": "run", "cadence": cadence, "run_date": run_date.isoformat(), "timezone": plan["timezone"], "queries": outcomes, "channel_audits": audit_outcomes}
    store.record_job("scheduled-run", cadence, json.dumps(outcome, sort_keys=True))
    return outcome
