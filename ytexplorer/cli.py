"""Bot-friendly commands for the YT Explorer evidence queue.

Run from the monorepo root, for example::

    python3 -m trading.ytexplorer.cli init
    python3 -m trading.ytexplorer.cli discover --query "anchored VWAP trading rules"
    python3 -m trading.ytexplorer.cli audit-channel CHANNEL_ID --transcripts --auto-promote
    python3 -m trading.ytexplorer.cli serve
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from .channel_audit import audit_samples, recommend_status
from .store import CANDIDATE_STATUSES, ExplorerStore, default_db_path


def _store(args: argparse.Namespace) -> ExplorerStore:
    return ExplorerStore(args.db) if getattr(args, "db", None) else ExplorerStore()


def _print(data: Any, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return
    if isinstance(data, list):
        for row in data:
            print(" | ".join(f"{k}={v}" for k, v in row.items()))
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


def cmd_init(args: argparse.Namespace) -> None:
    store = _store(args)
    store.init()
    _print({"ok": True, "database": str(store.path)}, as_json=args.json)


def cmd_discover(args: argparse.Namespace) -> None:
    from .ytmcp_client import search, transcript
    from .scope import long_only_scope

    store = _store(args)
    rows = search(
        args.query,
        max_results=args.max_results,
        upload_date=args.upload_date,
        sort_by=args.sort_by,
    )
    new = 0
    transcript_ok = 0
    out_of_scope = 0
    eligible_ids: set[str] = set()
    progress = _BatchProgress("Discover", len(rows), enabled=not args.no_progress)
    try:
        for row in rows:
            new += store.upsert_video(row, discovered_by=f"query:{args.query}")
            in_scope, _ = long_only_scope(row)
            if not in_scope:
                store.mark_video_out_of_scope(row["video_id"])
                out_of_scope += 1
                progress.update()
                continue
            eligible_ids.add(row["video_id"])
            if args.transcripts:
                result = transcript(row["video_id"])
                if "error" in result:
                    store.mark_transcript_error(row["video_id"], str(result["error"]))
                else:
                    store.set_transcript(row["video_id"], result.get("raw_text", ""), result.get("language_code", "en"))
                    transcript_ok += 1
            progress.update()
    finally:
        progress.close()
    extracted = []
    if args.extract:
        from .llm_engine import HermesExtractor
        extractor = HermesExtractor(store)
        progress = _BatchProgress("Extract discovered", len(rows), enabled=not args.no_progress)
        try:
            for row in rows:
                if row["video_id"] not in eligible_ids:
                    progress.update()
                    continue
                video = store.get_video(row["video_id"])
                if video is None or video.get("transcript_status") != "ready":
                    progress.update()
                    continue
                try:
                    result = extractor.extract(row["video_id"], model=args.model, timeout=args.timeout)
                    extracted.append({"video_id": result.video_id, "status": result.status, "disposition": result.disposition})
                except Exception as exc:  # One bad model response must not stop the discovery batch.
                    extracted.append({"video_id": row["video_id"], "status": "error", "detail": str(exc)})
                progress.update()
        finally:
            progress.close()
    outcome = {"query": args.query, "returned": len(rows), "new": new, "out_of_scope": out_of_scope,
               "transcripts": transcript_ok, "extractions": extracted}
    store.record_job("discover", args.query, json.dumps(outcome, sort_keys=True))
    _print(outcome, as_json=args.json)


def cmd_backfill(args: argparse.Namespace) -> None:
    """Ingest a historical, date-sorted result set for every configured query.

    This deliberately stores metadata only by default.  A large backfill must
    not immediately create thousands of transcript or Hermes jobs; the normal
    ranked pipeline can evaluate the expanded Inbox over time.
    """
    from .pipeline import load_plan
    from .scope import long_only_scope
    from .ytmcp_client import search, transcript

    store = _store(args)
    plan = load_plan(args.plan)
    queries = plan["queries"]
    progress = _BatchProgress(
        "Historical backfill",
        len(queries) * args.max_results,
        enabled=not args.no_progress,
    )
    outcomes = []
    total_new = 0
    total_transcripts = 0
    total_out_of_scope = 0
    try:
        for item in queries:
            result = {"id": item.id, "query": item.query, "returned": 0, "new": 0, "out_of_scope": 0, "transcripts": 0, "errors": []}
            try:
                rows = search(item.query, max_results=args.max_results, sort_by="date")
                result["returned"] = len(rows)
                for row in rows:
                    result["new"] += store.upsert_video(row, discovered_by=f"backfill:{item.id}")
                    in_scope, _ = long_only_scope(row)
                    if not in_scope:
                        store.mark_video_out_of_scope(row["video_id"])
                        result["out_of_scope"] += 1
                        progress.update()
                        continue
                    if args.transcripts:
                        tx = transcript(row["video_id"])
                        if "error" in tx:
                            store.mark_transcript_error(row["video_id"], str(tx["error"]))
                            result["errors"].append(f"{row['video_id']}: transcript {tx['error']}")
                        else:
                            store.set_transcript(row["video_id"], tx.get("raw_text", ""), tx.get("language_code", "en"))
                            result["transcripts"] += 1
                    progress.update()
            except Exception as exc:
                result["errors"].append(str(exc))
            total_new += result["new"]
            total_transcripts += result["transcripts"]
            total_out_of_scope += result["out_of_scope"]
            outcomes.append(result)
    finally:
        progress.close()
    outcome = {
        "mode": "historical-backfill",
        "sort_by": "date",
        "upload_date": None,
        "max_results_per_query": args.max_results,
        "queries": outcomes,
        "new": total_new,
        "out_of_scope": total_out_of_scope,
        "transcripts": total_transcripts,
    }
    store.record_job("historical-backfill", "configured-plan", json.dumps(outcome, sort_keys=True))
    _print(outcome, as_json=args.json)


def cmd_process_backfill(args: argparse.Namespace) -> None:
    """Process a bounded batch from the metadata-only historical Inbox."""
    from .pipeline import load_plan, process_historical_backfill

    store = _store(args)
    limits = load_plan()["daily_limits"]
    run_id = store.start_pipeline_run("historical-backfill")
    progress = _ScheduledProgress(enabled=not args.no_progress)
    try:
        outcome = process_historical_backfill(
            store,
            limit=args.limit,
            model=args.model,
            timeout=args.timeout,
            metadata_screen_limit=int(limits.get("max_metadata_screen_videos_per_backfill", 40)),
            metadata_screen_batch_size=int(limits.get("metadata_screen_batch_size", 20)),
            run_id=run_id,
            progress=progress,
        )
        outcome["run_id"] = run_id
        outcome["parameters"] = {
            "queries": [],
            "limits": {
                "max_backfill_videos_per_run": args.limit,
                "hermes_timeout_seconds": args.timeout,
                "metadata_screen_batch_size": int(limits.get("metadata_screen_batch_size", 20)),
                "max_metadata_screen_videos_per_backfill": int(limits.get("max_metadata_screen_videos_per_backfill", 40)),
            },
        }
        store.finish_pipeline_run(run_id, status="ok", summary=outcome)
        store.record_job("historical-process", str(args.limit), json.dumps(outcome, sort_keys=True))
    except Exception as exc:
        store.finish_pipeline_run(run_id, status="error", error=str(exc))
        raise
    finally:
        progress.close()
    _print(outcome, as_json=args.json)


def cmd_audit_channel(args: argparse.Namespace) -> None:
    from .ytmcp_client import channel_videos, transcript

    store = _store(args)
    channel = store.get_channel(args.channel_id)
    if channel is None:
        raise ValueError("unknown channel; discover or ingest one of its videos first")
    source_rows = channel_videos(args.channel_id, sort_by="newest")[:args.sample_size]
    progress = _BatchProgress("Audit channel", len(source_rows), enabled=not args.no_progress)
    try:
        for row in source_rows:
            # ytmcp channel records already include the channel identifier.
            store.upsert_video(row, discovered_by=f"channel:{args.channel_id}")
            if args.transcripts:
                result = transcript(row["video_id"])
                if "error" in result:
                    store.mark_transcript_error(row["video_id"], str(result["error"]))
                else:
                    store.set_transcript(row["video_id"], result.get("raw_text", ""), result.get("language_code", "en"))
            progress.update()
    finally:
        progress.close()
    samples = [v for v in store.list_videos(limit=1000) if v["channel_id"] == args.channel_id][:args.sample_size]
    audit = audit_samples(samples)
    recommended, reason = recommend_status(
        audit,
        min_sample=args.min_sample,
        min_trading_ratio=args.min_trading_ratio,
        min_strategy_ratio=args.min_strategy_ratio,
    )
    status = recommended if args.auto_promote else channel["status"]
    store.update_channel_audit(
        args.channel_id, sample_size=audit["sample_size"], trading_ratio=audit["trading_ratio"],
        strategy_ratio=audit["strategy_ratio"], status=status,
        reason=reason + ("; auto-promoted" if status == "approved" and args.auto_promote else ""),
    )
    outcome = {"channel_id": args.channel_id, "recommended_status": recommended, "applied_status": status,
               "reason": reason, **audit}
    store.record_job("channel-audit", args.channel_id, json.dumps(outcome, sort_keys=True))
    _print(outcome, as_json=args.json)


def cmd_list(args: argparse.Namespace) -> None:
    store = _store(args)
    if args.kind == "videos":
        data = store.list_videos(status=args.status, limit=args.limit)
    elif args.kind == "channels":
        data = store.list_channels(status=args.status)
    elif args.kind == "claims":
        data = store.list_claims(limit=args.limit)
    else:
        data = store.list_candidates(status=args.status)
    _print(data, as_json=args.json)


def cmd_add_claim(args: argparse.Namespace) -> None:
    store = _store(args)
    cid = store.add_claim(
        video_id=args.video_id, claim_type=args.claim_type, summary=args.summary,
        evidence_quote=args.evidence_quote, evidence_start=args.evidence_start,
        evidence_end=args.evidence_end, horizon=args.horizon, trigger_rule=args.trigger,
        invalidation_rule=args.invalidation, required_data=args.required_data,
        missing_fields=args.missing_field, extract_confidence=args.confidence,
    )
    _print({"claim_id": cid}, as_json=args.json)


def cmd_add_candidate(args: argparse.Namespace) -> None:
    cid = _store(args).add_candidate(
        title=args.title, summary=args.summary, claim_id=args.claim_id, priority=args.priority,
        feasibility=args.feasibility, data_requirements=args.data_requirements, prior_art=args.prior_art,
        structural_difference=args.structural_difference, assumption_register=args.assumption_register,
    )
    _print({"candidate_id": cid, "status": "triage"}, as_json=args.json)


def cmd_transition(args: argparse.Namespace) -> None:
    store = _store(args)
    store.transition_candidate(args.candidate_id, args.status, actor=args.actor, rationale=args.rationale)
    _print({"candidate_id": args.candidate_id, "status": args.status}, as_json=args.json)


def cmd_link_experiment(args: argparse.Namespace) -> None:
    _store(args).add_experiment_link(args.candidate_id, args.system, args.run_ref, state=args.state, note=args.note)
    _print({"candidate_id": args.candidate_id, "system": args.system, "run_ref": args.run_ref}, as_json=args.json)


def cmd_extract(args: argparse.Namespace) -> None:
    from .llm_engine import HermesExtractor, ExtractionError

    store = _store(args)
    if args.video_id:
        result = HermesExtractor(store).extract(args.video_id, model=args.model, timeout=args.timeout,
                                                force=args.force, dry_run=args.dry_run)
        payload: Any = result.__dict__
    else:
        videos = [v for v in store.list_videos(limit=10000) if v.get("transcript_status") == "ready"][:args.limit]
        progress = _BatchProgress("Extract", len(videos), enabled=not args.no_progress)
        results = []
        try:
            extractor = HermesExtractor(store)
            for video in videos:
                try:
                    result = extractor.extract(video["video_id"], model=args.model, timeout=args.timeout,
                                               force=args.force, dry_run=args.dry_run)
                    results.append(result.__dict__)
                except ExtractionError as exc:
                    results.append({"video_id": video["video_id"], "status": "error", "detail": str(exc)})
                progress.update()
        finally:
            progress.close()
        payload = results
    _print(payload, as_json=args.json)


def cmd_recover(args: argparse.Namespace) -> None:
    """Retry prior invalid output and surface existing incomplete evidence."""
    from .llm_engine import HermesExtractor, ExtractionError, promote_needs_detail

    store = _store(args)
    video_ids = store.invalid_extraction_video_ids(limit=args.limit)
    retried = []
    progress = _BatchProgress("Recover invalid extractions", len(video_ids), enabled=not args.no_progress)
    try:
        for video_id in video_ids:
            try:
                result = HermesExtractor(store).extract(video_id, model=args.model, timeout=args.timeout, force=True)
                retried.append({"video_id": video_id, "status": result.status, "disposition": result.disposition})
            except ExtractionError as exc:
                retried.append({"video_id": video_id, "status": "error", "detail": str(exc)})
            progress.update()
    finally:
        progress.close()
    promoted = promote_needs_detail(store, limit=args.promote_limit)
    _print({"retried": retried, "promoted_needs_detail": promoted}, as_json=args.json)


def cmd_run_scheduled(args: argparse.Namespace) -> None:
    from .pipeline import run_scheduled

    progress = _ScheduledProgress(enabled=not args.no_progress and not args.dry_run)
    try:
        payload = run_scheduled(_store(args), plan_path=args.plan, cadence=args.cadence,
                                model=args.model, dry_run=args.dry_run, progress=progress)
    finally:
        progress.close()
    _print(payload, as_json=args.json)


class _ScheduledProgress:
    """Interactive stderr-only progress for scheduled discovery.

    Keeping it on stderr means stdout remains a valid JSON document when the
    caller uses ``--json`` for bot automation or log processing.
    """

    def __init__(self, *, enabled: bool) -> None:
        self._bar: Any = None
        if not enabled or not sys.stderr.isatty():
            return
        try:
            from tqdm import tqdm
        except ImportError:
            return
        self._bar = tqdm(total=0, desc="YT Explorer", unit="video", dynamic_ncols=True, file=sys.stderr)

    def __call__(self, update: dict[str, Any]) -> None:
        if self._bar is None:
            return
        event = update["event"]
        if event == "query_started":
            self._bar.set_description(f"Search {update['index']}/{update['total_queries']}: {update['query_id']}")
        elif event == "videos_queued":
            self._bar.total += int(update["count"])
            self._bar.refresh()
        elif event == "backfill_queued":
            self._bar.set_description(f"Historical Inbox: {update['count']}/{update['pending']} selected")
            self._bar.total += int(update["count"])
            self._bar.refresh()
        elif event == "recovery_queued":
            self._bar.set_description(f"Recovery: {update['count']} invalid extractions")
            self._bar.total += int(update["count"])
            self._bar.refresh()
        elif event == "video_finished":
            self._bar.update(1)
        elif event == "run_finished":
            self._bar.set_description("YT Explorer complete")
            self._bar.refresh()

    def close(self) -> None:
        if self._bar is not None:
            self._bar.close()


class _BatchProgress:
    """A stderr-only tqdm bar for bounded batch commands."""

    def __init__(self, desc: str, total: int, *, enabled: bool) -> None:
        self._bar: Any = None
        if not enabled or not sys.stderr.isatty():
            return
        try:
            from tqdm import tqdm
        except ImportError:
            return
        self._bar = tqdm(total=total, desc=desc, unit="item", dynamic_ncols=True, file=sys.stderr)

    def update(self, count: int = 1) -> None:
        if self._bar is not None:
            self._bar.update(count)

    def close(self) -> None:
        if self._bar is not None:
            self._bar.close()


def _launch_agent_payload(wrapper: Path, log_dir: Path, hour: int, minute: int) -> dict[str, Any]:
    return {
        "Label": "com.trading.ytexplorer.daily",
        "ProgramArguments": [str(wrapper)],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(log_dir / "launchd.out.log"),
        "StandardErrorPath": str(log_dir / "launchd.err.log"),
    }


def _web_launch_agent_payload(wrapper: Path, log_dir: Path) -> dict[str, Any]:
    return {
        "Label": "com.trading.ytexplorer.web",
        "ProgramArguments": [str(wrapper)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(log_dir / "web.out.log"),
        "StandardErrorPath": str(log_dir / "web.err.log"),
    }


def cmd_install_schedule(args: argparse.Namespace) -> None:
    """Install and load a macOS LaunchAgent; this is the one-time scheduler setup."""
    package = Path(__file__).resolve().parent
    wrapper = package / "deploy" / "run_daily.sh"
    web_wrapper = package / "deploy" / "run_web.sh"
    log_dir = package / "data" / "logs"
    target_dir = Path.home() / "Library" / "LaunchAgents"
    target = target_dir / "com.trading.ytexplorer.daily.plist"
    web_target = target_dir / "com.trading.ytexplorer.web.plist"
    target.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = _launch_agent_payload(wrapper, log_dir, args.hour, args.minute)
    target.write_bytes(plistlib.dumps(payload, sort_keys=False))
    web_target.write_bytes(plistlib.dumps(_web_launch_agent_payload(web_wrapper, log_dir), sort_keys=False))
    wrapper.chmod(0o755)
    web_wrapper.chmod(0o755)
    if args.no_load:
        _print({"daily_agent": str(target), "web_agent": str(web_target), "loaded": False,
                "schedule": f"{args.hour:02d}:{args.minute:02d}"}, as_json=args.json)
        return
    uid = str(os.getuid())
    service = f"gui/{uid}/com.trading.ytexplorer.daily"
    web_service = f"gui/{uid}/com.trading.ytexplorer.web"
    # A prior version may or may not be loaded; ignore that particular outcome.
    subprocess.run(["launchctl", "bootout", service], capture_output=True, text=True, check=False)
    proc = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(target)], capture_output=True, text=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"launchctl bootstrap failed: {proc.stderr.strip() or proc.stdout.strip()}")
    subprocess.run(["launchctl", "bootout", web_service], capture_output=True, text=True, check=False)
    web_proc = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(web_target)], capture_output=True, text=True, check=False)
    if web_proc.returncode:
        raise RuntimeError(f"web LaunchAgent bootstrap failed: {web_proc.stderr.strip() or web_proc.stdout.strip()}")
    _print({"daily_agent": str(target), "web_agent": str(web_target), "loaded": True,
            "schedule": f"{args.hour:02d}:{args.minute:02d}", "monitor": "http://127.0.0.1:8791/operations",
            "log": str(log_dir / "daily.log")}, as_json=args.json)


def cmd_seed_demo(args: argparse.Namespace) -> None:
    """Create clearly-labelled local sample data so the web UI is explorable offline."""
    store = _store(args)
    video = {
        "video_id": "demo_vwap_001", "channel_identifier": "demo_channel", "channel": "Example Trading Lab",
        "title": "Anchored VWAP pullback: a rules-based walkthrough", "url": "https://www.youtube.com/watch?v=demo_vwap_001",
        "published_date": "2026-07-01", "duration": "18:24", "view_count": 0,
        "description": "Demo record for the local YT Explorer interface.",
    }
    store.upsert_video(video, discovered_by="demo")
    store.set_transcript(video["video_id"], "At 05:20, wait for a pullback to anchored VWAP after an earnings gap. Enter only after the reclaim. Stop below the pullback low.")
    store.update_channel_audit("demo_channel", sample_size=12, trading_ratio=0.92, strategy_ratio=0.75,
                               status="approved", reason="demo source; content audit passed")
    claim_id = store.add_claim(
        video_id=video["video_id"], claim_type="setup", summary="Earnings-anchored VWAP reclaim after a pullback",
        evidence_start=320, evidence_end=342,
        evidence_quote="wait for a pullback to anchored VWAP after an earnings gap. Enter only after the reclaim. Stop below the pullback low.",
        horizon="swing", trigger_rule="close reclaims earnings-anchored VWAP after a pullback",
        invalidation_rule="stop below pullback low", required_data=["daily OHLCV", "point-in-time earnings dates"],
        missing_fields=["universe", "exit"], extract_confidence=0.84,
    )
    candidate_id = store.add_candidate(
        claim_id=claim_id, title="Earnings-anchored VWAP reclaim", priority=61,
        summary="A source-backed swing hypothesis; not runnable until earnings-event data and explicit exits are frozen.",
        feasibility="data-blocked", data_requirements="Point-in-time earnings calendar; split-aware daily bars.",
        prior_art="Related to the parked anchored_vwap roadmap concept; no test without a structural difference.",
        structural_difference="Not yet established", assumption_register="Exit and eligible universe must be decided before any data is inspected.",
    )
    store.transition_candidate(candidate_id, "data-blocked", actor="demo", rationale="Required earnings-event store is not available")
    _print({"ok": True, "video_id": video["video_id"], "candidate_id": candidate_id}, as_json=args.json)


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn
    from .web.app import create_app

    uvicorn.run(create_app(_store(args).path), host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YT Explorer evidence-first research intake")
    parser.add_argument("--db", type=Path, help=f"SQLite path (default: {default_db_path()})")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--no-progress", action="store_true", help="suppress interactive tqdm progress bars")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)

    discover = sub.add_parser("discover", help="search YouTube via ytmcp and store new videos")
    discover.add_argument("--query", required=True)
    discover.add_argument("--max-results", type=int, default=20)
    discover.add_argument("--upload-date", choices=["hour", "today", "day", "week", "month", "year"])
    discover.add_argument("--sort-by", choices=["relevance", "rating", "date", "views", "popularity"], default="relevance")
    discover.add_argument("--transcripts", action="store_true", help="also fetch transcripts (uses API quota)")
    discover.add_argument("--extract", action="store_true", help="run Hermes extraction for downloaded transcripts")
    discover.add_argument("--model", help="Hermes model override used with --extract")
    discover.add_argument("--timeout", type=int, default=90, help="Hermes timeout seconds with --extract")
    discover.set_defaults(func=cmd_discover)

    backfill = sub.add_parser("backfill", help="date-sorted all-time discovery for every configured query")
    backfill.add_argument("--plan", type=Path, help="query-plan YAML (default: ytexplorer/config/queries.yaml)")
    backfill.add_argument("--max-results", type=int, default=200, help="maximum results to ingest per query (default: 200)")
    backfill.add_argument("--transcripts", action="store_true", help="also download transcripts; off by default for a safe large backfill")
    backfill.set_defaults(func=cmd_backfill)

    process_backfill = sub.add_parser("process-backfill", help="rank and process a bounded batch from the historical Inbox")
    process_backfill.add_argument("--limit", type=int, default=10, help="historical videos to attempt (default: 10)")
    process_backfill.add_argument("--model", help="Hermes model override")
    process_backfill.add_argument("--timeout", type=int, default=90, help="Hermes timeout seconds per video")
    process_backfill.set_defaults(func=cmd_process_backfill)

    audit = sub.add_parser("audit-channel", help="sample a channel and recommend/promote its source status")
    audit.add_argument("channel_id")
    audit.add_argument("--sample-size", type=int, default=12)
    audit.add_argument("--min-sample", type=int, default=12)
    audit.add_argument("--min-trading-ratio", type=float, default=0.70)
    audit.add_argument("--min-strategy-ratio", type=float, default=0.40)
    audit.add_argument("--transcripts", action="store_true", help="use transcripts as well as metadata")
    audit.add_argument("--auto-promote", action="store_true", help="apply an approved/rejected recommendation")
    audit.set_defaults(func=cmd_audit_channel)

    listing = sub.add_parser("list", help="list stored records")
    listing.add_argument("kind", choices=["videos", "channels", "claims", "candidates"])
    listing.add_argument("--status")
    listing.add_argument("--limit", type=int, default=100)
    listing.set_defaults(func=cmd_list)

    claim = sub.add_parser("add-claim", help="add a cited, structured claim")
    claim.add_argument("--video-id", required=True)
    claim.add_argument("--claim-type", default="setup")
    claim.add_argument("--summary", required=True)
    claim.add_argument("--evidence-quote", required=True)
    claim.add_argument("--evidence-start", type=int)
    claim.add_argument("--evidence-end", type=int)
    claim.add_argument("--horizon")
    claim.add_argument("--trigger")
    claim.add_argument("--invalidation")
    claim.add_argument("--required-data", action="append", default=[])
    claim.add_argument("--missing-field", action="append", default=[])
    claim.add_argument("--confidence", type=float)
    claim.set_defaults(func=cmd_add_claim)

    candidate = sub.add_parser("add-candidate", help="add a triage candidate from a claim")
    candidate.add_argument("--title", required=True)
    candidate.add_argument("--summary", required=True)
    candidate.add_argument("--claim-id")
    candidate.add_argument("--priority", type=float, default=0)
    candidate.add_argument("--feasibility", default="unassessed")
    candidate.add_argument("--data-requirements", default="")
    candidate.add_argument("--prior-art", default="")
    candidate.add_argument("--structural-difference", default="")
    candidate.add_argument("--assumption-register", default="")
    candidate.set_defaults(func=cmd_add_candidate)

    transition = sub.add_parser("transition", help="record a human/governance status change")
    transition.add_argument("candidate_id")
    transition.add_argument("status", choices=sorted(CANDIDATE_STATUSES))
    transition.add_argument("--actor", default="bot")
    transition.add_argument("--rationale", default="")
    transition.set_defaults(func=cmd_transition)

    link = sub.add_parser("link-experiment", help="attach a lab or llm_trader result reference")
    link.add_argument("candidate_id")
    link.add_argument("--system", required=True, choices=["lab", "llm_trader"])
    link.add_argument("--run-ref", required=True)
    link.add_argument("--state", default="planned")
    link.add_argument("--note", default="")
    link.set_defaults(func=cmd_link_experiment)

    extract = sub.add_parser("extract", help="automatically extract cited claims and queue dispositions with Hermes")
    extract.add_argument("--video-id", help="one downloaded transcript to process")
    extract.add_argument("--limit", type=int, default=20, help="ready transcripts to process when --video-id is omitted")
    extract.add_argument("--model", help="Hermes model override")
    extract.add_argument("--timeout", type=int, default=90)
    extract.add_argument("--force", action="store_true", help="reprocess even if the same transcript + skill already succeeded")
    extract.add_argument("--dry-run", action="store_true", help="show the Hermes command without invoking it")
    extract.set_defaults(func=cmd_extract)

    recover = sub.add_parser("recover", help="retry invalid Hermes output and queue existing needs-detail evidence")
    recover.add_argument("--limit", type=int, default=8, help="invalid videos to retry (default: 8)")
    recover.add_argument("--promote-limit", type=int, default=20, help="needs-detail bundles to queue (default: 20)")
    recover.add_argument("--model", help="Hermes model override")
    recover.add_argument("--timeout", type=int, default=90)
    recover.set_defaults(func=cmd_recover)

    scheduled = sub.add_parser("run-scheduled", help="run the configured autonomous discovery plan")
    scheduled.add_argument("--plan", type=Path, help="query-plan YAML (default: ytexplorer/config/queries.yaml)")
    scheduled.add_argument("--cadence", choices=["due", "daily", "weekly", "monthly"], default="due")
    scheduled.add_argument("--model", help="Hermes model override")
    scheduled.add_argument("--dry-run", action="store_true", help="show queries due without provider or Hermes calls")
    scheduled.set_defaults(func=cmd_run_scheduled)

    install = sub.add_parser("install-schedule", help="install the macOS daily LaunchAgent")
    install.add_argument("--hour", type=int, default=6, choices=range(24))
    install.add_argument("--minute", type=int, default=5, choices=range(60))
    install.add_argument("--no-load", action="store_true", help="write the LaunchAgent but do not enable it yet")
    install.set_defaults(func=cmd_install_schedule)

    sub.add_parser("seed-demo", help="add a local demo record for the web UI").set_defaults(func=cmd_seed_demo)
    serve = sub.add_parser("serve", help="run the local web interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8791)
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> None:
    # Users naturally place output-format flags after a subcommand. argparse only
    # accepts global options before it, so normalize this harmless convenience flag.
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    for flag in ("--json", "--no-progress"):
        if flag in raw_argv:
            raw_argv.remove(flag)
            raw_argv.insert(0, flag)
    args = build_parser().parse_args(raw_argv)
    try:
        args.func(args)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
