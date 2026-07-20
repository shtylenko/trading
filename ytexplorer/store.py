"""Local, auditable storage for the YT Explorer intake workflow.

The store deliberately stops at an experiment brief / result link.  It never
creates a strategy release, changes a scanner, or talks to broker code.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PACKAGE_DIR / "data" / "ytexplorer.sqlite3"

VIDEO_STATUSES = {"new", "extracted", "reference", "archived", "out-of-scope", "error"}
CHANNEL_STATUSES = {"candidate", "approved", "rejected", "demoted"}
CANDIDATE_STATUSES = {
    "triage",
    "needs-detail",
    "duplicate",
    "data-blocked",
    "parked",
    "rejected",
    "approved-for-brief",
    "preregistered",
    "development-run",
    "validation-run",
    "killed",
    "shadow-forward",
    "research-supported",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_db_path() -> Path:
    raw = os.getenv("YTEXPLORER_DB")
    return Path(raw).expanduser() if raw else DEFAULT_DB_PATH


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class ExplorerStore:
    """SQLite repository shared by bot commands and the local web UI."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_db_path()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    handle TEXT,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    discovery_source TEXT,
                    trading_ratio REAL,
                    strategy_ratio REAL,
                    audit_sample_size INTEGER NOT NULL DEFAULT 0,
                    audit_reason TEXT,
                    last_audited_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL REFERENCES channels(channel_id),
                    title TEXT NOT NULL,
                    url TEXT,
                    published_at TEXT,
                    duration TEXT,
                    view_count INTEGER,
                    description TEXT,
                    discovered_by TEXT,
                    transcript_text TEXT,
                    transcript_hash TEXT,
                    transcript_language TEXT,
                    transcript_status TEXT NOT NULL DEFAULT 'pending',
                    status TEXT NOT NULL DEFAULT 'new',
                    discovered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
                CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(video_id),
                    claim_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_start INTEGER,
                    evidence_end INTEGER,
                    evidence_quote TEXT NOT NULL,
                    horizon TEXT,
                    trigger_rule TEXT,
                    invalidation_rule TEXT,
                    required_data_json TEXT NOT NULL DEFAULT '[]',
                    missing_fields_json TEXT NOT NULL DEFAULT '[]',
                    extract_confidence REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_claims_video ON claims(video_id);
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    claim_id TEXT REFERENCES claims(claim_id),
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'triage',
                    priority REAL NOT NULL DEFAULT 0,
                    feasibility TEXT,
                    data_requirements TEXT,
                    prior_art TEXT,
                    structural_difference TEXT,
                    assumption_register TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
                CREATE TABLE IF NOT EXISTS queue_events (
                    event_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    rationale TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiment_links (
                    link_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                    system TEXT NOT NULL,
                    run_ref TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'planned',
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_extractions (
                    extraction_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(video_id),
                    transcript_hash TEXT NOT NULL,
                    model TEXT,
                    skill_hash TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    raw_response TEXT,
                    parsed_json TEXT,
                    error TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_llm_extractions_video ON llm_extractions(video_id, completed_at DESC);
                CREATE TABLE IF NOT EXISTS metadata_screenings (
                    screening_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(video_id),
                    screen_version TEXT NOT NULL,
                    model TEXT,
                    prompt_hash TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    score REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metadata_screenings_video ON metadata_screenings(video_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    cadence TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    summary_json TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS pipeline_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id),
                    stage TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pipeline_events_run ON pipeline_events(run_id, created_at DESC);
                """
            )

    @staticmethod
    def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def record_job(self, kind: str, detail: str, outcome: str) -> None:
        self.init()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO job_runs VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), kind, detail, outcome, now, now),
            )

    def start_pipeline_run(self, cadence: str) -> str:
        self.init()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute("INSERT INTO pipeline_runs (run_id,cadence,status,started_at) VALUES (?, ?, 'running', ?)",
                         (run_id, cadence, utc_now()))
        self.append_pipeline_event(run_id, "run", f"scheduled pipeline started ({cadence})", "running")
        return run_id

    def append_pipeline_event(self, run_id: str, stage: str, detail: str, status: str = "running") -> None:
        self.init()
        with self.connect() as conn:
            conn.execute("INSERT INTO pipeline_events VALUES (?, ?, ?, ?, ?, ?)",
                         (str(uuid.uuid4()), run_id, stage, detail[:2000], status, utc_now()))

    def finish_pipeline_run(self, run_id: str, *, status: str, summary: dict[str, Any] | None = None, error: str = "") -> None:
        self.init()
        with self.connect() as conn:
            conn.execute("UPDATE pipeline_runs SET status=?, completed_at=?, summary_json=?, error=? WHERE run_id=?",
                         (status, utc_now(), _json(summary) if summary is not None else None, error[:2000] or None, run_id))
        self.append_pipeline_event(run_id, "run", "pipeline completed" if status == "ok" else error or "pipeline failed", status)

    def latest_pipeline_run(self) -> Optional[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_pipeline_run(self, run_id: str) -> Optional[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_pipeline_runs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Recent scheduled/manual pipeline runs, newest launch first.

        Parse the non-sensitive persisted summary into template-friendly fields
        while retaining the raw run record for diagnostics.
        """
        self.init()
        with self.connect() as conn:
            rows = self._rows(conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall())
        for row in rows:
            try:
                summary = json.loads(row.get("summary_json") or "{}")
            except json.JSONDecodeError:
                summary = {}
            parameters = summary.get("parameters") or {}
            # Runs created before parameter persistence have outcome query data,
            # which is still useful context even though it lacks the full plan.
            query_specs = parameters.get("queries") or summary.get("queries") or []
            row["run_date"] = summary.get("run_date")
            row["timezone"] = summary.get("timezone")
            row["query_specs"] = query_specs
            row["limits"] = parameters.get("limits") or {}
            row["parameters_captured"] = bool(parameters)
        return rows

    def pipeline_events(self, run_id: str, *, limit: int = 80) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                "SELECT * FROM pipeline_events WHERE run_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (run_id, limit)
            ).fetchall())

    def upsert_video(self, video: dict[str, Any], discovered_by: str = "manual") -> bool:
        """Insert/update a video and create an unknown channel as a candidate.

        Returns True only when the video was new, so callers can safely run
        discovery repeatedly.
        """
        self.init()
        video_id = str(video.get("video_id") or "").strip()
        channel_id = str(video.get("channel_identifier") or video.get("channel_id") or "").strip()
        if not video_id or not channel_id:
            raise ValueError("video_id and channel_identifier are required")
        now = utc_now()
        title = str(video.get("title") or "Untitled video")
        channel_title = str(video.get("channel") or video.get("channel_title") or "Unknown channel")
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO channels (channel_id,title,handle,status,discovery_source,created_at,updated_at)
                   VALUES (?, ?, ?, 'candidate', ?, ?, ?)
                   ON CONFLICT(channel_id) DO UPDATE SET
                   title=excluded.title, updated_at=excluded.updated_at""",
                (channel_id, channel_title, video.get("handle"), discovered_by, now, now),
            )
            exists = conn.execute("SELECT 1 FROM videos WHERE video_id=?", (video_id,)).fetchone()
            conn.execute(
                """INSERT INTO videos
                   (video_id,channel_id,title,url,published_at,duration,view_count,description,discovered_by,discovered_at,updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(video_id) DO UPDATE SET
                     title=excluded.title, url=excluded.url, published_at=excluded.published_at,
                     duration=excluded.duration, view_count=excluded.view_count,
                     description=excluded.description, updated_at=excluded.updated_at""",
                (
                    video_id, channel_id, title, video.get("url"),
                    video.get("published_date_YYYYMMDD") or video.get("published_date"),
                    video.get("duration"), video.get("view_count"), video.get("description"),
                    discovered_by, now, now,
                ),
            )
        return exists is None

    def set_transcript(self, video_id: str, text: str, language: str = "en") -> None:
        import hashlib

        self.init()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self.connect() as conn:
            conn.execute(
                """UPDATE videos SET transcript_text=?, transcript_hash=?, transcript_language=?,
                   transcript_status='ready', status=CASE WHEN status='new' THEN 'extracted' ELSE status END,
                   updated_at=? WHERE video_id=?""",
                (text, digest, language, utc_now(), video_id),
            )

    def mark_transcript_error(self, video_id: str, message: str) -> None:
        self.init()
        with self.connect() as conn:
            conn.execute(
                "UPDATE videos SET transcript_status=?, updated_at=? WHERE video_id=?",
                (f"error: {message[:160]}", utc_now(), video_id),
            )

    def reserve_transcript_downloads(self, video_ids: list[str]) -> list[str]:
        """Atomically claim pending videos so overlapping workers cannot duplicate work."""
        if not video_ids:
            return []
        self.init()
        reserved: list[str] = []
        with self.connect() as conn:
            now = utc_now()
            for video_id in video_ids:
                result = conn.execute(
                    """UPDATE videos SET transcript_status='processing', updated_at=?
                       WHERE video_id=? AND transcript_status='pending' AND status='new'""",
                    (now, video_id),
                )
                if result.rowcount:
                    reserved.append(video_id)
        return reserved

    def release_transcript_reservation(self, video_id: str) -> None:
        """Return a video to the backlog after an unexpected transient worker failure."""
        self.init()
        with self.connect() as conn:
            conn.execute(
                """UPDATE videos SET transcript_status='pending', updated_at=?
                   WHERE video_id=? AND transcript_status='processing'""",
                (utc_now(), video_id),
            )

    def mark_video_out_of_scope(self, video_id: str) -> None:
        """Keep discovered metadata visible while preventing later evaluation."""
        self.init()
        with self.connect() as conn:
            conn.execute(
                "UPDATE videos SET status='out-of-scope', updated_at=? WHERE video_id=?",
                (utc_now(), video_id),
            )

    def get_video(self, video_id: str) -> Optional[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute(
                """SELECT v.*, c.title AS channel_title, c.status AS channel_status
                   FROM videos v JOIN channels c ON c.channel_id=v.channel_id WHERE v.video_id=?""",
                (video_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_videos(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.init()
        query = """SELECT v.*, c.title AS channel_title, c.status AS channel_status
                   FROM videos v JOIN channels c ON c.channel_id=v.channel_id"""
        args: list[Any] = []
        if status:
            query += " WHERE v.status=?"
            args.append(status)
        query += " ORDER BY v.discovered_at DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            return self._rows(conn.execute(query, args).fetchall())

    def historical_backfill_pending_videos(self, *, limit: int = 10_000) -> list[dict[str, Any]]:
        """Return metadata-only historical discoveries that have not been attempted.

        A transcript error is deliberately not selected again here; recovery is
        a separate, explicit policy so an unavailable caption track cannot
        consume every future daily backfill slot.
        """
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                """SELECT v.*, c.title AS channel_title, c.status AS channel_status
                   FROM videos v JOIN channels c ON c.channel_id=v.channel_id
                   WHERE v.discovered_by LIKE 'backfill:%' AND v.transcript_status='pending' AND v.status='new'
                   ORDER BY v.published_at DESC, v.discovered_at DESC LIMIT ?""",
                (limit,),
            ).fetchall())

    def list_channels(self, *, status: str | None = None) -> list[dict[str, Any]]:
        self.init()
        where, args = ("", []) if not status else (" WHERE c.status=?", [status])
        with self.connect() as conn:
            return self._rows(conn.execute(
                """SELECT c.*, COUNT(v.video_id) AS video_count
                   FROM channels c LEFT JOIN videos v ON v.channel_id=c.channel_id"""
                + where + " GROUP BY c.channel_id ORDER BY c.updated_at DESC", args
            ).fetchall())

    def get_channel(self, channel_id: str) -> Optional[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM channels WHERE channel_id=?", (channel_id,)).fetchone()
        return dict(row) if row else None

    def update_channel_audit(
        self, channel_id: str, *, sample_size: int, trading_ratio: float, strategy_ratio: float,
        status: str, reason: str,
    ) -> None:
        if status not in CHANNEL_STATUSES:
            raise ValueError(f"invalid channel status: {status}")
        self.init()
        with self.connect() as conn:
            conn.execute(
                """UPDATE channels SET status=?, trading_ratio=?, strategy_ratio=?, audit_sample_size=?,
                   audit_reason=?, last_audited_at=?, updated_at=? WHERE channel_id=?""",
                (status, trading_ratio, strategy_ratio, sample_size, reason, utc_now(), utc_now(), channel_id),
            )

    def add_claim(
        self, *, video_id: str, claim_type: str, summary: str, evidence_quote: str,
        evidence_start: int | None = None, evidence_end: int | None = None,
        horizon: str | None = None, trigger_rule: str | None = None,
        invalidation_rule: str | None = None, required_data: list[str] | None = None,
        missing_fields: list[str] | None = None, extract_confidence: float | None = None,
    ) -> str:
        if not summary.strip() or not evidence_quote.strip():
            raise ValueError("summary and timestamped evidence quote are required")
        self.init()
        claim_id = f"clm_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM videos WHERE video_id=?", (video_id,)).fetchone():
                raise ValueError(f"unknown video: {video_id}")
            conn.execute(
                """INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    claim_id, video_id, claim_type, summary.strip(), evidence_start, evidence_end,
                    evidence_quote.strip(), horizon, trigger_rule, invalidation_rule,
                    _json(required_data or []), _json(missing_fields or []), extract_confidence, utc_now(),
                ),
            )
            conn.execute("UPDATE videos SET status='extracted', updated_at=? WHERE video_id=?", (utc_now(), video_id))
        return claim_id

    def list_claims(self, *, limit: int = 200) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                """SELECT cl.*, v.title AS video_title, v.url, c.title AS channel_title
                   FROM claims cl JOIN videos v ON v.video_id=cl.video_id
                   JOIN channels c ON c.channel_id=v.channel_id
                   ORDER BY cl.created_at DESC LIMIT ?""", (limit,)
            ).fetchall())

    def claims_for_video(self, video_id: str) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute("SELECT * FROM claims WHERE video_id=? ORDER BY created_at", (video_id,)).fetchall())

    def extraction_exists(self, video_id: str, transcript_hash: str, skill_hash: str) -> bool:
        """Whether this exact evidence + skill combination was already processed."""
        self.init()
        with self.connect() as conn:
            return conn.execute(
                """SELECT 1 FROM llm_extractions WHERE video_id=? AND transcript_hash=? AND skill_hash=?
                   AND status='ok' LIMIT 1""", (video_id, transcript_hash, skill_hash)
            ).fetchone() is not None

    def record_extraction(
        self, *, video_id: str, transcript_hash: str, model: str | None, skill_hash: str,
        prompt_hash: str, status: str, raw_response: str = "", parsed: dict[str, Any] | None = None,
        error: str = "",
    ) -> str:
        self.init()
        now = utc_now()
        extraction_id = f"ext_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO llm_extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (extraction_id, video_id, transcript_hash, model, skill_hash, prompt_hash, status,
                 raw_response, _json(parsed) if parsed is not None else None, error, now, now),
            )
        return extraction_id

    def record_metadata_screenings(
        self,
        decisions: dict[str, dict[str, Any]],
        *,
        model: str | None,
        prompt_hash: str,
        screen_version: str,
    ) -> None:
        if not decisions:
            return
        self.init()
        now = utc_now()
        with self.connect() as conn:
            for video_id, decision in decisions.items():
                conn.execute(
                    """INSERT INTO metadata_screenings
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"scr_{uuid.uuid4().hex[:12]}", video_id, screen_version, model, prompt_hash,
                        decision["verdict"], float(decision["score"]), decision["reason"], now,
                    ),
                )

    def metadata_screenings_for_video(self, video_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                """SELECT screen_version, model, verdict, score, rationale, created_at
                   FROM metadata_screenings WHERE video_id=?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (video_id, limit),
            ).fetchall())

    def extractions_for_video(self, video_id: str) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                """SELECT extraction_id, model, skill_hash, status, error, started_at, completed_at
                   FROM llm_extractions WHERE video_id=? ORDER BY completed_at DESC, rowid DESC""", (video_id,)
            ).fetchall())

    def invalid_extraction_video_ids(self, *, limit: int) -> list[str]:
        """Latest-invalid videos with no later successful extraction."""
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT e.video_id
                   FROM llm_extractions e
                   WHERE e.status='invalid'
                     AND NOT EXISTS (
                       SELECT 1 FROM llm_extractions newer
                       WHERE newer.video_id=e.video_id AND newer.status='ok'
                         AND (newer.completed_at > e.completed_at OR
                              (newer.completed_at=e.completed_at AND newer.rowid > e.rowid))
                     )
                   GROUP BY e.video_id
                   ORDER BY MAX(e.completed_at) ASC
                   LIMIT ?""", (limit,)
            ).fetchall()
        return [row["video_id"] for row in rows]

    def needs_detail_extractions(self, *, limit: int) -> list[dict[str, Any]]:
        """Successful source bundles awaiting a research candidate."""
        self.init()
        with self.connect() as conn:
            rows = self._rows(conn.execute(
                """SELECT e.video_id, e.parsed_json, e.completed_at, v.title AS video_title
                   FROM llm_extractions e JOIN videos v ON v.video_id=e.video_id
                   WHERE e.status='ok' AND e.parsed_json LIKE '%\"disposition\": \"needs-detail\"%'
                     AND NOT EXISTS (
                       SELECT 1 FROM candidates ca JOIN claims cl ON cl.claim_id=ca.claim_id
                       WHERE cl.video_id=e.video_id
                     )
                   ORDER BY e.completed_at ASC LIMIT ?""", (limit,)
            ).fetchall())
        return rows

    def add_candidate(
        self, *, title: str, summary: str, claim_id: str | None = None, priority: float = 0,
        feasibility: str = "unassessed", data_requirements: str = "", prior_art: str = "",
        structural_difference: str = "", assumption_register: str = "",
    ) -> str:
        if not title.strip() or not summary.strip():
            raise ValueError("title and summary are required")
        self.init()
        cid = f"cand_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        with self.connect() as conn:
            if claim_id and not conn.execute("SELECT 1 FROM claims WHERE claim_id=?", (claim_id,)).fetchone():
                raise ValueError(f"unknown claim: {claim_id}")
            conn.execute(
                """INSERT INTO candidates VALUES (?, ?, ?, ?, 'triage', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cid, claim_id, title.strip(), summary.strip(), priority, feasibility, data_requirements,
                 prior_art, structural_difference, assumption_register, now, now),
            )
            conn.execute(
                "INSERT INTO queue_events VALUES (?, ?, NULL, 'triage', 'cli', 'candidate created', ?)",
                (str(uuid.uuid4()), cid, now),
            )
        return cid

    def list_candidates(self, *, status: str | None = None) -> list[dict[str, Any]]:
        self.init()
        query = """SELECT ca.*, cl.summary AS claim_summary, v.video_id, v.title AS video_title,
                          v.url, ch.title AS channel_title
                   FROM candidates ca
                   LEFT JOIN claims cl ON cl.claim_id=ca.claim_id
                   LEFT JOIN videos v ON v.video_id=cl.video_id
                   LEFT JOIN channels ch ON ch.channel_id=v.channel_id"""
        args: list[Any] = []
        if status:
            query += " WHERE ca.status=?"
            args.append(status)
        query += " ORDER BY ca.priority DESC, ca.updated_at DESC"
        with self.connect() as conn:
            return self._rows(conn.execute(query, args).fetchall())

    def get_candidate(self, candidate_id: str) -> Optional[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute(
                """SELECT ca.*, cl.summary AS claim_summary, cl.evidence_quote, cl.evidence_start,
                          cl.evidence_end, cl.horizon, cl.trigger_rule, cl.invalidation_rule,
                          v.video_id, v.title AS video_title, v.url, ch.title AS channel_title
                   FROM candidates ca
                   LEFT JOIN claims cl ON cl.claim_id=ca.claim_id
                   LEFT JOIN videos v ON v.video_id=cl.video_id
                   LEFT JOIN channels ch ON ch.channel_id=v.channel_id
                   WHERE ca.candidate_id=?""", (candidate_id,)
            ).fetchone()
        return dict(row) if row else None

    def transition_candidate(self, candidate_id: str, to_status: str, *, actor: str, rationale: str = "") -> None:
        if to_status not in CANDIDATE_STATUSES:
            raise ValueError(f"invalid candidate status: {to_status}")
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT status FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            if row is None:
                raise ValueError(f"unknown candidate: {candidate_id}")
            now = utc_now()
            conn.execute("UPDATE candidates SET status=?, updated_at=? WHERE candidate_id=?", (to_status, now, candidate_id))
            conn.execute(
                "INSERT INTO queue_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), candidate_id, row["status"], to_status, actor, rationale, now),
            )

    def candidate_events(self, candidate_id: str) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            return self._rows(conn.execute(
                "SELECT * FROM queue_events WHERE candidate_id=? ORDER BY created_at DESC, rowid DESC", (candidate_id,)
            ).fetchall())

    def add_experiment_link(self, candidate_id: str, system: str, run_ref: str, *, state: str = "planned", note: str = "") -> None:
        if system not in {"lab", "llm_trader"}:
            raise ValueError("system must be lab or llm_trader")
        self.init()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO experiment_links VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), candidate_id, system, run_ref, state, note, utc_now()),
            )

    def experiment_links(self, candidate_id: str | None = None) -> list[dict[str, Any]]:
        self.init()
        query = """SELECT e.*, c.title AS candidate_title, c.status AS candidate_status
                   FROM experiment_links e JOIN candidates c ON c.candidate_id=e.candidate_id"""
        args: list[Any] = []
        if candidate_id:
            query += " WHERE e.candidate_id=?"
            args.append(candidate_id)
        query += " ORDER BY e.created_at DESC"
        with self.connect() as conn:
            return self._rows(conn.execute(query, args).fetchall())

    def dashboard(self) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            def count(table: str, where: str = "", args: tuple[Any, ...] = ()) -> int:
                row = conn.execute(f"SELECT COUNT(*) AS c FROM {table} {where}", args).fetchone()
                return int(row["c"])
            return {
                "videos": count("videos"),
                "new_videos": count("videos", "WHERE status='new'"),
                "channels": count("channels"),
                "candidate_channels": count("channels", "WHERE status='candidate'"),
                "claims": count("claims"),
                "candidates": count("candidates"),
                "triage": count("candidates", "WHERE status='triage'"),
                "blocked": count("candidates", "WHERE status='data-blocked'"),
                "recent_jobs": self._rows(conn.execute("SELECT * FROM job_runs ORDER BY completed_at DESC LIMIT 10").fetchall()),
            }
