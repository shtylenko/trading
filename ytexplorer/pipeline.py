"""Autonomous daily discovery pipeline driven by ``config/queries.yaml``."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml

from .channel_audit import audit_samples, recommend_status
from .llm_engine import HermesExtractor
from .scope import long_only_scope
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


_RULE_TERMS = {
    "entry": 4, "exit": 4, "stop loss": 4, "invalidation": 4, "risk reward": 3,
    "strategy": 2, "setup": 2, "rules": 2, "breakout": 2, "pullback": 2,
    "vwap": 2, "backtest": 2, "position sizing": 2,
}
_NOISE_TERMS = {"guaranteed": 5, "100%": 4, "90% win": 4, "signal": 2, "prediction": 2}


def rank_video_for_research(video: dict[str, Any]) -> tuple[int, list[str]]:
    """Rank metadata for explicit, testable trading-rule language.

    This deliberately ranks only the *extraction budget*; every result is
    still stored in the inbox for human exploration and later re-ranking.
    """
    in_scope, exclusions = long_only_scope(video)
    if not in_scope:
        return -1_000, [f"out-of-scope:{reason}" for reason in exclusions]
    text = f"{video.get('title', '')} {video.get('description', '')}".casefold()
    score, reasons = 0, []
    for term, weight in _RULE_TERMS.items():
        if term in text:
            score += weight
            reasons.append(term)
    for term, penalty in _NOISE_TERMS.items():
        if term in text:
            score -= penalty
    if video.get("channel_status") == "approved":
        score += 3
        reasons.append("approved-channel")
    return score, reasons


def screen_and_rank_videos(
    store: ExplorerStore,
    videos: list[dict[str, Any]],
    *,
    screen_limit: int,
    batch_size: int,
    model: str | None,
    timeout: int,
    run_id: str | None = None,
    stage: str = "metadata-screen",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use the metadata LLM screen as an auditable override of keyword ranking.

    A screen failure is safe: the existing deterministic order remains the
    fallback. The screener only sees metadata and never creates claims.
    """
    baseline = sorted(
        videos,
        key=lambda video: (rank_video_for_research(video)[0], video.get("published_at") or "", video.get("view_count") or 0),
        reverse=True,
    )
    to_screen = baseline[:max(0, screen_limit)]
    decisions: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []
    if to_screen:
        from .metadata_screening import MetadataScreener

        screener = MetadataScreener(store)
        for start in range(0, len(to_screen), max(1, batch_size)):
            batch = to_screen[start:start + max(1, batch_size)]
            try:
                batch_decisions, diagnostics = screener.screen(batch, model=model, timeout=min(timeout, 45))
                decisions.update(batch_decisions)
                warnings.extend(diagnostics)
            except Exception as exc:
                errors.append(str(exc))
                if run_id:
                    store.append_pipeline_event(run_id, stage, f"screen fallback: {exc}", "error")
    screened_out = 0
    eligible: list[dict[str, Any]] = []
    for video in baseline:
        decision = decisions.get(video["video_id"])
        if decision and decision["verdict"] == "out-of-scope":
            store.mark_video_out_of_scope(video["video_id"])
            screened_out += 1
            continue
        if decision:
            video["metadata_screen"] = decision
        eligible.append(video)
    def key(video: dict[str, Any]) -> tuple[float, float, int, str, int]:
        decision = video.get("metadata_screen") or {}
        verdict_weight = {"process": 2.0, "defer": 1.0}.get(decision.get("verdict"), 0.5)
        return (
            verdict_weight,
            float(decision.get("score", 0)),
            rank_video_for_research(video)[0],
            video.get("published_at") or "",
            video.get("view_count") or 0,
        )
    ranked = sorted(eligible, key=key, reverse=True)
    summary = {
        "screened": len(decisions),
        "screened_out_of_scope": screened_out,
        "screen_errors": errors,
        "screen_warnings": warnings,
    }
    if run_id:
        store.append_pipeline_event(
            run_id, stage,
            f"screened {len(decisions)}/{len(to_screen)} metadata records; {screened_out} out of scope; {len(errors)} fallback batches; {len(warnings)} partial-output warnings",
            "ok" if not errors else "error",
        )
    return ranked, summary


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


def process_historical_backfill(
    store: ExplorerStore,
    *,
    limit: int,
    model: str | None = None,
    timeout: int = 90,
    metadata_screen_limit: int = 40,
    metadata_screen_batch_size: int = 20,
    run_id: str | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Spend a bounded daily Hermes budget on the historical Inbox.

    Historical discovery is intentionally metadata-only. This worker gradually
    turns it into cited evidence without allowing a large one-off backfill to
    overload transcript or model capacity. Metadata rule density decides which
    items are attempted first; all remaining records stay in the Inbox.
    """
    from .ytmcp_client import transcript

    pending = store.historical_backfill_pending_videos()
    eligible = []
    out_of_scope = 0
    for video in pending:
        in_scope, _ = long_only_scope(video)
        if in_scope:
            eligible.append(video)
        else:
            store.mark_video_out_of_scope(video["video_id"])
            out_of_scope += 1
    ranked, screen_summary = screen_and_rank_videos(
        store,
        eligible,
        screen_limit=max(0, metadata_screen_limit) if limit > 0 else 0,
        batch_size=max(1, metadata_screen_batch_size),
        model=model,
        timeout=timeout,
        run_id=run_id,
        stage="historical-metadata-screen",
    )
    candidates = ranked[:max(0, limit)]
    reserved_ids = set(store.reserve_transcript_downloads([video["video_id"] for video in candidates]))
    selected = [video for video in candidates if video["video_id"] in reserved_ids]
    result: dict[str, Any] = {
        "pending": len(pending),
        "out_of_scope": out_of_scope,
        **screen_summary,
        "selected": len(selected),
        "transcripts": 0,
        "extracted": 0,
        "skipped": 0,
        "errors": [],
    }
    if progress is not None:
        progress({"event": "backfill_queued", "count": len(selected), "pending": len(pending)})
    if run_id:
        store.append_pipeline_event(
            run_id,
            "historical-backfill",
            f"selected {len(selected)}/{len(eligible)} in-scope historical videos by rule-language score; {out_of_scope} out of scope",
        )
    extractor = HermesExtractor(store)
    for video in selected:
        video_id = video["video_id"]
        try:
            tx = transcript(video_id)
            if "error" in tx:
                message = str(tx["error"])
                store.mark_transcript_error(video_id, message)
                result["errors"].append(f"{video_id}: transcript {message}")
                if run_id:
                    store.append_pipeline_event(run_id, "historical-transcript", f"{video_id}: {message}", "error")
                continue
            store.set_transcript(video_id, tx.get("raw_text", ""), tx.get("language_code", "en"))
            result["transcripts"] += 1
            if run_id:
                store.append_pipeline_event(run_id, "historical-transcript", f"{video_id}: downloaded")
            extraction = extractor.extract(video_id, model=model, timeout=timeout)
            if extraction.skipped:
                result["skipped"] += 1
            elif extraction.status == "ok":
                result["extracted"] += 1
            if run_id:
                store.append_pipeline_event(
                    run_id,
                    "historical-extract",
                    f"{video_id}: {extraction.status} {extraction.disposition or ''}".strip(),
                    "ok" if extraction.status == "ok" else extraction.status,
                )
        except Exception as exc:
            store.release_transcript_reservation(video_id)
            result["errors"].append(f"{video_id}: {exc}")
            if run_id:
                store.append_pipeline_event(run_id, "historical-video", f"{video_id}: {exc}", "error")
        finally:
            if progress is not None:
                progress({"event": "video_finished", "video_id": video_id, "source": "backfill"})
    return result


def recover_invalid_extractions(
    store: ExplorerStore,
    *,
    limit: int,
    model: str | None = None,
    timeout: int = 90,
    run_id: str | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Retry a small, automatic lane of invalid historical model output.

    New extractor versions use evidence-fragment IDs, so a forced retry can
    recover prior quote-copy failures without weakening evidence validation.
    """
    video_ids = store.invalid_extraction_video_ids(limit=max(0, limit))
    result: dict[str, Any] = {"selected": len(video_ids), "recovered": 0, "skipped_scope": 0, "errors": []}
    if progress is not None:
        progress({"event": "recovery_queued", "count": len(video_ids)})
    if run_id:
        store.append_pipeline_event(run_id, "recovery", f"selected {len(video_ids)} invalid extractions for retry")
    extractor = HermesExtractor(store)
    for video_id in video_ids:
        video = store.get_video(video_id)
        if video is None:
            continue
        in_scope, exclusions = long_only_scope(video)
        if not in_scope:
            store.mark_video_out_of_scope(video_id)
            result["skipped_scope"] += 1
            continue
        try:
            extraction = extractor.extract(video_id, model=model, timeout=timeout, force=True)
            if extraction.status == "ok":
                result["recovered"] += 1
            if run_id:
                store.append_pipeline_event(run_id, "recovery", f"{video_id}: {extraction.status}", extraction.status)
        except Exception as exc:
            result["errors"].append(f"{video_id}: {exc}")
            if run_id:
                store.append_pipeline_event(run_id, "recovery", f"{video_id}: {exc}", "error")
        finally:
            if progress is not None:
                progress({"event": "video_finished", "video_id": video_id, "source": "recovery"})
    return result


def synthesize_candidate_backlog(
    store: ExplorerStore,
    *,
    limit: int,
    batch_size: int,
    model: str | None = None,
    timeout: int = 90,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Incrementally organize active hypotheses after extraction.

    The output is advisory only: it records family labels and suggested next
    review action, never changes a candidate state or starts a backtest.
    """
    from .candidate_synthesis import CandidateSynthesizer, SYNTHESIS_VERSION

    completed = store.synthesized_candidate_ids(SYNTHESIS_VERSION)
    available = [row for row in store.active_candidates_for_synthesis() if row["candidate_id"] not in completed]
    selected = available[:max(0, limit)]
    result: dict[str, Any] = {"pending": len(available), "selected": len(selected), "decisions": 0, "warnings": [], "errors": []}
    if not selected:
        return result
    if run_id:
        store.append_pipeline_event(run_id, "candidate-synthesis", f"selected {len(selected)}/{len(available)} unsynthesized candidates")
    synthesizer = CandidateSynthesizer(store)
    size = max(1, batch_size)
    for index in range(0, len(selected), size):
        batch = selected[index:index + size]
        try:
            decisions, diagnostics = synthesizer.synthesize(batch, model=model, timeout=timeout)
            result["decisions"] += len(decisions)
            result["warnings"].extend(diagnostics)
            store.record_job(
                "candidate-synthesis-batch", f"{SYNTHESIS_VERSION}:{index // size + 1}",
                json.dumps({"selected": len(batch), "decisions": len(decisions), "warnings": diagnostics}, sort_keys=True),
            )
            if run_id:
                store.append_pipeline_event(run_id, "candidate-synthesis", f"{len(decisions)}/{len(batch)} classified", "ok")
        except Exception as exc:
            result["errors"].append(str(exc))
            store.record_job(
                "candidate-synthesis-batch", f"{SYNTHESIS_VERSION}:{index // size + 1}",
                json.dumps({"selected": len(batch), "error": str(exc)}, sort_keys=True),
            )
            if run_id:
                store.append_pipeline_event(run_id, "candidate-synthesis", str(exc), "error")
    return result


def run_scheduled(
    store: ExplorerStore, *, plan_path: Path | str | None = None, cadence: str = "daily",
    model: str | None = None, dry_run: bool = False, as_of: date | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
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

    def report(event: str, **details: Any) -> None:
        if progress is not None:
            progress({"event": event, **details})

    run_id = store.start_pipeline_run(cadence)
    limits = plan["daily_limits"]
    hermes_timeout = int(limits.get("hermes_timeout_seconds", 90))
    extractor = HermesExtractor(store)
    newly_discovered_channels: set[str] = set()
    outcomes: list[dict[str, Any]] = []
    report("run_started", query_count=len(selected))
    extraction_budget = max(1, int(limits.get("max_hermes_per_query", 4)))
    for query_index, item in enumerate(selected, start=1):
        result: dict[str, Any] = {
            "id": item.id, "query": item.query, "new": 0, "transcripts": 0, "extracted": 0,
            "ranked_for_extraction": 0, "deferred": 0, "out_of_scope": 0, "metadata_screened": 0, "errors": [],
        }
        report("query_started", index=query_index, total_queries=len(selected), query_id=item.id, query=item.query)
        store.append_pipeline_event(run_id, "search", f"searching {item.id}: {item.query}")
        try:
            rows = search(item.query, max_results=item.max_results, upload_date=item.upload_date)
        except Exception as exc:  # provider error belongs in the run report, not a crashed scheduler
            result["errors"].append(f"search: {exc}")
            store.append_pipeline_event(run_id, "search", f"{item.id}: {exc}", "error")
            outcomes.append(result)
            continue
        store.append_pipeline_event(run_id, "search", f"{item.id}: {len(rows)} videos returned")
        # Retain every discovery result, then spend transcript/Hermes capacity
        # only on the rule-dense subset.  Deferred records remain in the inbox.
        new_channel_ids: dict[str, bool] = {}
        for row in rows:
            is_new = store.upsert_video(row, discovered_by=f"scheduled:{item.id}")
            if is_new:
                result["new"] += 1
                new_channel_ids[row["video_id"]] = True
            stored = store.get_video(row["video_id"])
            if stored:
                row["channel_status"] = stored.get("channel_status")
        eligible_rows = []
        for row in rows:
            in_scope, _ = long_only_scope(row)
            if in_scope:
                eligible_rows.append(row)
            else:
                store.mark_video_out_of_scope(row["video_id"])
                result["out_of_scope"] += 1
        ranked, screen_summary = screen_and_rank_videos(
            store,
            eligible_rows,
            screen_limit=int(limits.get("max_metadata_screen_videos_per_query", 20)),
            batch_size=int(limits.get("metadata_screen_batch_size", 20)),
            model=model,
            timeout=hermes_timeout,
            run_id=run_id,
            stage=f"metadata-screen:{item.id}",
        )
        result["metadata_screened"] = screen_summary["screened"]
        result["out_of_scope"] += screen_summary["screened_out_of_scope"]
        result["errors"].extend(f"metadata screen: {error}" for error in screen_summary["screen_errors"])
        work_rows = ranked[:extraction_budget]
        result["ranked_for_extraction"] = len(work_rows)
        result["deferred"] = max(0, len(eligible_rows) - len(work_rows))
        store.append_pipeline_event(
            run_id, "rank", f"{item.id}: selected {len(work_rows)}/{len(eligible_rows)} in-scope videos; {result['deferred']} deferred; {result['out_of_scope']} out of scope"
        )
        report("videos_queued", query_id=item.id, count=len(work_rows))
        for row in work_rows:
            try:
                if new_channel_ids.get(row["video_id"]):
                    newly_discovered_channels.add(row["channel_identifier"])
                video = store.get_video(row["video_id"])
                if video and video.get("transcript_status") != "ready":
                    tx = transcript(row["video_id"])
                    if "error" in tx:
                        store.mark_transcript_error(row["video_id"], str(tx["error"]))
                        result["errors"].append(f"{row['video_id']}: transcript {tx['error']}")
                        store.append_pipeline_event(run_id, "transcript", f"{row['video_id']}: {tx['error']}", "error")
                        continue
                    store.set_transcript(row["video_id"], tx.get("raw_text", ""), tx.get("language_code", "en"))
                    result["transcripts"] += 1
                    store.append_pipeline_event(run_id, "transcript", f"{row['video_id']}: downloaded")
                store.append_pipeline_event(run_id, "extract", f"{row['video_id']}: Hermes extraction")
                extraction = extractor.extract(row["video_id"], model=model, timeout=hermes_timeout)
                if extraction.status == "ok":
                    result["extracted"] += 1
                store.append_pipeline_event(run_id, "extract", f"{row['video_id']}: {extraction.status} {extraction.disposition or ''}".strip(),
                                            "ok" if extraction.status == "ok" else extraction.status)
            except Exception as exc:
                result["errors"].append(f"{row.get('video_id', '?')}: {exc}")
                store.append_pipeline_event(run_id, "video", f"{row.get('video_id', '?')}: {exc}", "error")
            finally:
                report("video_finished", query_id=item.id, video_id=row.get("video_id", "?"))
        outcomes.append(result)

    backfill_limit = max(0, int(limits.get("max_backfill_videos_per_run", 0)))
    historical_backfill = process_historical_backfill(
        store,
        limit=backfill_limit,
        model=model,
        timeout=hermes_timeout,
        metadata_screen_limit=int(limits.get("max_metadata_screen_videos_per_backfill", 40)),
        metadata_screen_batch_size=int(limits.get("metadata_screen_batch_size", 20)),
        run_id=run_id,
        progress=progress,
    )
    recovery = recover_invalid_extractions(
        store,
        limit=max(0, int(limits.get("max_recovery_videos_per_run", 0))),
        model=model,
        timeout=hermes_timeout,
        run_id=run_id,
        progress=progress,
    )
    candidate_synthesis = synthesize_candidate_backlog(
        store,
        limit=max(0, int(limits.get("max_candidate_synthesis_per_run", 0))),
        batch_size=max(1, int(limits.get("candidate_synthesis_batch_size", 4))),
        model=model,
        timeout=hermes_timeout,
        run_id=run_id,
    )

    audit_outcomes = []
    for channel_id in sorted(newly_discovered_channels)[:int(limits.get("max_new_channels_to_audit", 3))]:
        try:
            store.append_pipeline_event(run_id, "channel-audit", f"{channel_id}: auditing")
            audit_outcomes.append(_audit_new_channel(
                store, channel_id, sample_size=int(limits.get("channel_sample_size", 12)),
                fetch_transcripts=bool(limits.get("fetch_channel_transcripts", True)),
            ))
            store.append_pipeline_event(run_id, "channel-audit", f"{channel_id}: {audit_outcomes[-1]['status']}",
                                        audit_outcomes[-1]["status"])
        except Exception as exc:
            audit_outcomes.append({"channel_id": channel_id, "status": "error", "error": str(exc)})
            store.append_pipeline_event(run_id, "channel-audit", f"{channel_id}: {exc}", "error")
    outcome = {
        "run_id": run_id, "mode": "run", "cadence": cadence, "run_date": run_date.isoformat(),
        "timezone": plan["timezone"], "queries": outcomes, "historical_backfill": historical_backfill,
        "recovery": recovery,
        "candidate_synthesis": candidate_synthesis,
        "channel_audits": audit_outcomes,
        "parameters": {
            "queries": [item.__dict__ for item in selected],
            "limits": {
                "hermes_timeout_seconds": hermes_timeout,
                "max_hermes_per_query": extraction_budget,
                "max_backfill_videos_per_run": backfill_limit,
                "max_recovery_videos_per_run": max(0, int(limits.get("max_recovery_videos_per_run", 0))),
                "metadata_screen_batch_size": int(limits.get("metadata_screen_batch_size", 20)),
                "max_metadata_screen_videos_per_query": int(limits.get("max_metadata_screen_videos_per_query", 20)),
                "max_metadata_screen_videos_per_backfill": int(limits.get("max_metadata_screen_videos_per_backfill", 40)),
                "max_candidate_synthesis_per_run": max(0, int(limits.get("max_candidate_synthesis_per_run", 0))),
                "candidate_synthesis_batch_size": max(1, int(limits.get("candidate_synthesis_batch_size", 4))),
                "max_new_channels_to_audit": int(limits.get("max_new_channels_to_audit", 3)),
                "channel_sample_size": int(limits.get("channel_sample_size", 12)),
            },
        },
    }
    store.finish_pipeline_run(run_id, status="ok", summary=outcome)
    store.record_job("scheduled-run", cadence, json.dumps(outcome, sort_keys=True))
    report("run_finished")
    return outcome
