"""Structured JSONL event logging with daily rotation (DESIGN §14).

One event per line, stable enriched schema, daily-rotated directories, so an
external agent can analyze a day's operational health without guessing. The DB is
the state source of truth; this is the event/audit/analysis stream.

    log = EventLogger(env_config)
    log.emit("run.start", component="engine", portfolio_id="x03-pf1",
             release_id="x03", run_id=rid, data={"asof": "2026-06-19"})

Files per UTC day under ``<log_dir>/<YYYY-MM-DD>/``:
    events.jsonl   — full stream      errors.jsonl — WARN/ERROR subset
    summary.json   — end-of-day rollup (written by write_summary)
    manifest.json  — schema version + file list
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
_REDACT_KEYS = ("api_key", "secret", "secret_key", "key_id", "account_number", "token", "password")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ulid_like() -> str:
    """Monotonic-ish, sortable event id (ms timestamp + random suffix)."""
    return f"{int(time.time()*1000):013d}-{uuid.uuid4().hex[:12]}"


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("***" if any(s in k.lower() for s in _REDACT_KEYS) else _redact(v))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


class EventLogger:
    """Append-only JSONL emitter, daily-rotated by UTC date."""

    def __init__(self, env_config, *, echo: bool = False):
        self._log_dir = Path(env_config.log_dir)
        self._env = env_config.env
        self._echo = echo

    def _day_dir(self, ts: datetime) -> Path:
        d = self._log_dir / ts.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def emit(self, event: str, *, level: str = "INFO", component: str = "",
             portfolio_id: str | None = None, mode: str | None = None,
             release_id: str | None = None, run_id: str | None = None,
             correlation_id: str | None = None, causation_id: str | None = None,
             actor_type: str = "system", actor_id: str | None = None,
             attempt: int = 1, message: str = "", data: dict | None = None,
             latency_ms: float | None = None, error: dict | None = None) -> dict:
        now = datetime.now(timezone.utc)
        rec = {
            "schema_version": SCHEMA_VERSION,
            "event_id": _ulid_like(),
            "ts": now.isoformat(),
            "env": self._env,
            "level": level,
            "event": event,
            "component": component,
            "portfolio_id": portfolio_id,
            "mode": mode,
            "release_id": release_id,
            "run_id": run_id,
            "correlation_id": correlation_id or run_id,
            "causation_id": causation_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "attempt": attempt,
            "message": message,
            "data": _redact(data or {}),
        }
        if latency_ms is not None:
            rec["latency_ms"] = latency_ms
        if error is not None:
            rec["error"] = _redact(error)

        line = json.dumps(rec, default=str)
        day = self._day_dir(now)
        self._append(day / "events.jsonl", line)
        if level in ("WARN", "ERROR"):
            self._append(day / "errors.jsonl", line)
        self._write_manifest(day)
        if self._echo:
            print(line)
        return rec

    @staticmethod
    def _append(path: Path, line: str) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _write_manifest(self, day: Path) -> None:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "date": day.name,
            "files": sorted(p.name for p in day.glob("*.jsonl")) +
                     sorted(p.name for p in day.glob("*.json") if p.name != "manifest.json"),
        }
        (day / "manifest.json").write_text(json.dumps(manifest, indent=2))

    def write_summary(self, summary: dict, *, day: str | None = None) -> Path:
        """Write/overwrite the end-of-day rollup for the given (default: today) day."""
        now = datetime.now(timezone.utc)
        d = self._log_dir / (day or now.strftime("%Y-%m-%d"))
        d.mkdir(parents=True, exist_ok=True)
        out = d / "summary.json"
        out.write_text(json.dumps({"schema_version": SCHEMA_VERSION,
                                   "generated_at": _utc_now_iso(), **summary}, indent=2))
        self._write_manifest(d)
        return out
