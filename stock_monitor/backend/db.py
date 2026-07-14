"""
SQLite layer for daily sessions + screener membership/snapshots.

Session day rolls on America/New_York calendar date.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SNAPSHOT_THROTTLE_SEC = 30

_lock = RLock()
_db_path: Path | None = None


def now_iso() -> str:
    return datetime.now(tz=NY).astimezone().isoformat()


def session_date_today() -> str:
    """Return YYYY-MM-DD for current America/New_York calendar day."""
    return datetime.now(tz=NY).date().isoformat()


def set_db_path(path: Path | str) -> None:
    global _db_path
    _db_path = Path(path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db()


def get_db_path() -> Path:
    if _db_path is None:
        raise RuntimeError("db path not set; call set_db_path() first")
    return _db_path


def get_conn() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_sessions (
    id            INTEGER PRIMARY KEY,
    session_date  TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_tickers (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES daily_sessions(id),
    ticker        TEXT NOT NULL,
    ticker_id     TEXT,
    name          TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    first_source  TEXT DEFAULT 'webull-screener',
    screener_key  TEXT,
    screener_name TEXT,
    meta_json     TEXT,
    last_raw_hash TEXT,
    last_snapshot_at TEXT,
    UNIQUE(session_id, ticker)
);

CREATE TABLE IF NOT EXISTS screener_snapshots (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES daily_sessions(id),
    ticker        TEXT NOT NULL,
    seen_at       TEXT NOT NULL,
    raw_json      TEXT NOT NULL,
    source_url    TEXT,
    screener_key  TEXT,
    screener_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_session_tickers_session ON session_tickers(session_id);
CREATE INDEX IF NOT EXISTS idx_session_tickers_ticker ON session_tickers(ticker);
CREATE INDEX IF NOT EXISTS idx_snapshots_session_ticker ON screener_snapshots(session_id, ticker);
CREATE INDEX IF NOT EXISTS idx_snapshots_seen ON screener_snapshots(seen_at);
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db() -> None:
    with _lock:
        conn = get_conn()
        try:
            conn.executescript(SCHEMA)
            # Migrations for DBs created before named-screener tagging
            _ensure_column(conn, "session_tickers", "screener_key", "TEXT")
            _ensure_column(conn, "session_tickers", "screener_name", "TEXT")
            _ensure_column(conn, "screener_snapshots", "screener_key", "TEXT")
            _ensure_column(conn, "screener_snapshots", "screener_name", "TEXT")
            conn.commit()
        finally:
            conn.close()


def get_or_create_session(session_date: str | None = None) -> dict[str, Any]:
    date = session_date or session_date_today()
    now = now_iso()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, session_date, created_at, updated_at FROM daily_sessions WHERE session_date = ?",
                (date,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE daily_sessions SET updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                conn.commit()
                return {
                    "id": row["id"],
                    "session_date": row["session_date"],
                    "created_at": row["created_at"],
                    "updated_at": now,
                }
            cur.execute(
                "INSERT INTO daily_sessions(session_date, created_at, updated_at) VALUES (?, ?, ?)",
                (date, now, now),
            )
            conn.commit()
            return {
                "id": cur.lastrowid,
                "session_date": date,
                "created_at": now,
                "updated_at": now,
            }
        finally:
            conn.close()


def _row_hash(row: dict) -> str:
    """Stable hash of the full raw row for change detection."""
    payload = row.get("raw") if isinstance(row.get("raw"), (dict, list)) else row
    try:
        blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _parse_iso_to_epoch(iso: str) -> float:
    try:
        s = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def _normalize_ticker(raw: Any) -> str | None:
    if raw is None:
        return None
    t = str(raw).strip().upper()
    if not t or t == "UNKNOWN":
        return None
    # Basic symbol hygiene
    if not any(c.isalpha() for c in t):
        return None
    return t[:32]


def upsert_screener_rows(
    rows: list[dict],
    *,
    source_url: str | None = None,
    captured_at: str | None = None,
    session_date: str | None = None,
    throttle_sec: int = SNAPSHOT_THROTTLE_SEC,
    screener_key: str | None = None,
    screener_name: str | None = None,
) -> dict[str, Any]:
    """
    Upsert screener rows into today's (or given) session.

    - New ticker → insert session_tickers + snapshot
    - Existing → update last_seen_at / meta; snapshot if hash changed or throttle elapsed
    - screener_key/name tag which configured My Screener produced the rows
    """
    if not rows:
        session = get_or_create_session(session_date)
        return {
            "ok": True,
            "session_date": session["session_date"],
            "session_id": session["id"],
            "received": 0,
            "new_tickers": [],
            "updated_tickers": 0,
            "snapshots_written": 0,
            "screener_key": screener_key,
            "screener_name": screener_name,
        }

    session = get_or_create_session(session_date)
    sid = session["id"]
    seen_at = captured_at or now_iso()
    now_ts = _parse_iso_to_epoch(seen_at) or datetime.now(tz=NY).timestamp()
    first_source = f"webull-screener:{screener_key}" if screener_key else "webull-screener"

    new_tickers: list[str] = []
    updated = 0
    snapshots = 0
    skipped_invalid = 0

    # Dedupe by ticker within batch (last wins)
    by_ticker: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            skipped_invalid += 1
            continue
        ticker = _normalize_ticker(
            r.get("ticker") or r.get("symbol") or r.get("disSymbol")
        )
        if not ticker:
            skipped_invalid += 1
            continue
        by_ticker[ticker] = r

    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()

            for ticker, r in by_ticker.items():
                ticker_id = r.get("ticker_id") or r.get("tickerId")
                if ticker_id is not None:
                    ticker_id = str(ticker_id)
                name = r.get("name")
                if name is not None:
                    name = str(name)[:256]
                fields = r.get("fields") if isinstance(r.get("fields"), dict) else {}
                meta = {
                    "fields": fields,
                    "ticker_id": ticker_id,
                    "name": name,
                    "screener_key": screener_key,
                    "screener_name": screener_name,
                }
                meta_json = json.dumps(meta, ensure_ascii=False, default=str)
                raw_payload = {
                    "ticker": ticker,
                    "ticker_id": ticker_id,
                    "name": name,
                    "fields": fields,
                    "screener_key": screener_key,
                    "screener_name": screener_name,
                    "raw": r.get("raw", r),
                }
                raw_json = json.dumps(raw_payload, ensure_ascii=False, default=str)
                rh = _row_hash(r)

                cur.execute(
                    "SELECT id, last_raw_hash, last_snapshot_at FROM session_tickers "
                    "WHERE session_id = ? AND ticker = ?",
                    (sid, ticker),
                )
                existing = cur.fetchone()

                if existing is None:
                    cur.execute(
                        """
                        INSERT INTO session_tickers(
                            session_id, ticker, ticker_id, name,
                            first_seen_at, last_seen_at, first_source,
                            screener_key, screener_name,
                            meta_json, last_raw_hash, last_snapshot_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            sid, ticker, ticker_id, name, seen_at, seen_at, first_source,
                            screener_key, screener_name, meta_json, rh, seen_at,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO screener_snapshots(
                            session_id, ticker, seen_at, raw_json, source_url,
                            screener_key, screener_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (sid, ticker, seen_at, raw_json, source_url, screener_key, screener_name),
                    )
                    new_tickers.append(ticker)
                    snapshots += 1
                else:
                    cur.execute(
                        """
                        UPDATE session_tickers
                        SET last_seen_at = ?,
                            ticker_id = COALESCE(?, ticker_id),
                            name = COALESCE(?, name),
                            screener_key = COALESCE(?, screener_key),
                            screener_name = COALESCE(?, screener_name),
                            meta_json = ?
                        WHERE id = ?
                        """,
                        (seen_at, ticker_id, name, screener_key, screener_name, meta_json, existing["id"]),
                    )
                    updated += 1

                    prev_hash = existing["last_raw_hash"]
                    last_snap = existing["last_snapshot_at"]
                    last_snap_ts = _parse_iso_to_epoch(last_snap) if last_snap else 0.0
                    hash_changed = prev_hash != rh
                    throttle_ok = (now_ts - last_snap_ts) >= throttle_sec

                    if hash_changed or throttle_ok:
                        cur.execute(
                            """
                            INSERT INTO screener_snapshots(
                                session_id, ticker, seen_at, raw_json, source_url,
                                screener_key, screener_name
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (sid, ticker, seen_at, raw_json, source_url, screener_key, screener_name),
                        )
                        cur.execute(
                            """
                            UPDATE session_tickers
                            SET last_raw_hash = ?, last_snapshot_at = ?
                            WHERE id = ?
                            """,
                            (rh, seen_at, existing["id"]),
                        )
                        snapshots += 1

            cur.execute(
                "UPDATE daily_sessions SET updated_at = ? WHERE id = ?",
                (seen_at, sid),
            )
            conn.commit()
        finally:
            conn.close()

    return {
        "ok": True,
        "session_date": session["session_date"],
        "session_id": sid,
        "received": len(by_ticker),
        "new_tickers": new_tickers,
        "updated_tickers": updated,
        "snapshots_written": snapshots,
        "skipped_invalid": skipped_invalid,
        "screener_key": screener_key,
        "screener_name": screener_name,
    }


def get_session(session_date: str | None = None, include_tickers: bool = True) -> dict[str, Any] | None:
    date = session_date or session_date_today()
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, session_date, created_at, updated_at FROM daily_sessions WHERE session_date = ?",
                (date,),
            )
            row = cur.fetchone()
            if not row:
                return None
            result: dict[str, Any] = {
                "id": row["id"],
                "session_date": row["session_date"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            if include_tickers:
                cur.execute(
                    """
                    SELECT ticker, ticker_id, name, first_seen_at, last_seen_at, first_source,
                           screener_key, screener_name, meta_json
                    FROM session_tickers
                    WHERE session_id = ?
                    ORDER BY first_seen_at ASC
                    """,
                    (row["id"],),
                )
                tickers = []
                for t in cur.fetchall():
                    meta = None
                    if t["meta_json"]:
                        try:
                            meta = json.loads(t["meta_json"])
                        except json.JSONDecodeError:
                            meta = t["meta_json"]
                    tickers.append({
                        "ticker": t["ticker"],
                        "ticker_id": t["ticker_id"],
                        "name": t["name"],
                        "first_seen_at": t["first_seen_at"],
                        "last_seen_at": t["last_seen_at"],
                        "first_source": t["first_source"],
                        "screener_key": t["screener_key"],
                        "screener_name": t["screener_name"],
                        "meta": meta,
                    })
                result["tickers"] = tickers
                result["ticker_count"] = len(tickers)
            return result
        finally:
            conn.close()


def list_sessions(limit: int = 30) -> list[dict[str, Any]]:
    with _lock:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.id, s.session_date, s.created_at, s.updated_at,
                       COUNT(t.id) AS ticker_count
                FROM daily_sessions s
                LEFT JOIN session_tickers t ON t.session_id = s.id
                GROUP BY s.id
                ORDER BY s.session_date DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": r["id"],
                    "session_date": r["session_date"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "ticker_count": r["ticker_count"],
                }
                for r in cur.fetchall()
            ]
        finally:
            conn.close()


def health_check() -> dict[str, Any]:
    try:
        path = get_db_path()
        conn = get_conn()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return {"ok": False, "error": str(e), "path": str(_db_path) if _db_path else None}
