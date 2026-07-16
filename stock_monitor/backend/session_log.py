"""
Per-day session event log (append-only NDJSON).

Layout:
  backend/data/sessions/YYYY-MM-DD/events.ndjson

Each line:
  {
    "ts": "ISO-8601",
    "event": "session_start|session_end|screener_open|...",
    "session_date": "YYYY-MM-DD",
    ...event-specific fields
  }

Read later with:  jq . data/sessions/2026-07-15/events.ndjson
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
_lock = RLock()
_base_dir: Path | None = None

# Known event names (documentation / validation helpers)
EVENTS = {
    "session_start",       # first activity creating the daily session
    "session_end",         # explicit end, day roll, or receiver shutdown
    "screener_open",       # Gap'n'Go (or configured) armed / selected
    "screener_close",      # disarmed / left configured screener
    "ticker_added",        # first time ticker joins this session
    "screener_push",       # accepted batch of result rows
    "push_rejected",       # batch rejected (too large, wrong key, etc.)
    "watchlist_added",     # ticker pushed to Webull watchlist
    "watchlist_error",     # watchlist sync failure
    "receiver_start",      # backend process started
    "receiver_stop",       # backend process stopping
}


def set_base_dir(path: Path | str) -> None:
    """Root for session logs (usually backend/data/sessions)."""
    global _base_dir
    _base_dir = Path(path)
    _base_dir.mkdir(parents=True, exist_ok=True)


def get_base_dir() -> Path:
    if _base_dir is None:
        # default next to receiver data/
        default = Path(__file__).parent / "data" / "sessions"
        set_base_dir(default)
    return _base_dir  # type: ignore[return-value]


def session_date_today() -> str:
    return datetime.now(tz=NY).date().isoformat()


def now_iso() -> str:
    return datetime.now(tz=NY).astimezone().isoformat()


def log_path(session_date: str | None = None) -> Path:
    date = session_date or session_date_today()
    day_dir = get_base_dir() / date
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / "events.ndjson"


def log_event(
    event: str,
    *,
    session_date: str | None = None,
    ts: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """
    Append one event line to the day's log. Returns the written record.
    Unknown event names are still written (forward-compatible).
    """
    date = session_date or session_date_today()
    record: dict[str, Any] = {
        "ts": ts or now_iso(),
        "event": event,
        "session_date": date,
    }
    for k, v in fields.items():
        if v is not None:
            record[k] = v

    path = log_path(date)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return record


def read_events(
    session_date: str | None = None,
    *,
    event: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read events for a day (oldest first). Optional filter by event name."""
    path = log_path(session_date)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event and rec.get("event") != event:
                continue
            out.append(rec)
    if limit is not None and limit > 0:
        return out[-limit:]
    return out


def list_session_log_dates() -> list[str]:
    base = get_base_dir()
    if not base.is_dir():
        return []
    dates = []
    for p in base.iterdir():
        if p.is_dir() and (p / "events.ndjson").is_file():
            dates.append(p.name)
    return sorted(dates, reverse=True)
