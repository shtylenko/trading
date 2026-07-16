#!/usr/bin/env python3
"""
Minimal local receiver for Webull chart candles + screener daily sessions.

Chart (POST /push):
  Closed candlebar data → local JSON files under data/captures/.

Screener (POST /screener):
  Rows from Webull screener tab → SQLite daily session membership + raw snapshots.
  Session day rolls on America/New_York calendar date.

Run:  python3 receiver.py   (or ./run.sh)
"""

from __future__ import annotations
import json
import math
import os
import re
import shutil
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qs, urlparse

import db as session_db
import screener_config
import session_log
import webull_watchlist

# Config
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "captures"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_LOG_DIR = BASE_DIR / "data" / "sessions"
SESSIONS_LOG_DIR.mkdir(parents=True, exist_ok=True)
session_log.set_base_dir(SESSIONS_LOG_DIR)

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "data" / "stock_monitor.db")))

NDJSON_PATH = DATA_DIR / "candles.ndjson"
STATIC_DIR = BASE_DIR / "static"
lock = RLock()  # reentrant to allow append inside update lock

MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(5 * 1024 * 1024)))
MAX_DEBUG_FILES = int(os.environ.get("MAX_DEBUG_FILES", "500"))
MIN_TS_MS = 946684800000      # 2000-01-01
MAX_TS_MS = 4102444800000     # 2100-01-01
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def init_session_db(path: Path | None = None) -> None:
    """Initialize SQLite path (callable from tests with a temp path)."""
    db_path = path or DB_PATH
    session_db.set_db_path(db_path)
    # Share the same SQLite file for watchlist sync tracking
    webull_watchlist.set_db_path(db_path)


# Default init at import so the server is ready; tests re-point via init_session_db.
init_session_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_tf(raw: str) -> str:
    if not raw:
        return "unknown"
    s = raw.lower().strip().replace(" ", "").replace("min", "m")
    m = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1h", "m1": "1m", "m5": "5m", "h1": "1h", "d": "1d", "day": "1d",
    }
    return m.get(s, s)


def safe_name(value: str, fallback: str = "UNKNOWN") -> str:
    cleaned = SAFE_NAME_RE.sub("_", str(value or fallback).strip())
    cleaned = cleaned.strip("._-")
    return (cleaned or fallback)[:80]


def per_symbol_path(symbol: str, tf: str) -> Path:
    safe_sym = safe_name(symbol.upper())
    safe_tf = safe_name(normalize_tf(tf), "unknown")
    return DATA_DIR / f"{safe_sym}_{safe_tf}.json"


def append_ndjson(record: dict) -> None:
    with lock:
        with NDJSON_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def coerce_number(value, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric")
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def normalize_ts_ms(value) -> int:
    number = coerce_number(value, "t")
    if number < 10_000_000_000:
        number *= 1000
    while number > MAX_TS_MS:
        number /= 1000
    ts = int(number)
    if ts < MIN_TS_MS or ts > MAX_TS_MS:
        raise ValueError("t outside supported epoch-ms range")
    return ts


def validate_candle(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("candle must be an object")
    t = normalize_ts_ms(raw.get("t"))
    o = coerce_number(raw.get("o"), "o")
    h = coerce_number(raw.get("h"), "h")
    l = coerce_number(raw.get("l"), "l")
    c = coerce_number(raw.get("c"), "c")
    v = coerce_number(raw.get("v", 0), "v")
    if v < 0:
        raise ValueError("v must be non-negative")
    if h < max(o, l, c) or l > min(o, h, c):
        raise ValueError("OHLC values are inconsistent")
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def validate_candles(raw_candles: list) -> tuple[list[dict], list[dict]]:
    valid: list[dict] = []
    rejected: list[dict] = []
    for idx, raw in enumerate(raw_candles):
        try:
            valid.append(validate_candle(raw))
        except ValueError as e:
            rejected.append({"index": idx, "error": str(e)})
    return valid, rejected


def read_existing_candles(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        candles = doc.get("candles", [])
        return candles if isinstance(candles, list) else []
    except Exception:
        corrupt_path = path.with_suffix(path.suffix + f".corrupt-{int(time.time())}")
        try:
            shutil.copy2(path, corrupt_path)
            print(f"[receiver] preserved corrupt JSON as {corrupt_path.name}")
        except Exception as e:
            print(f"[receiver] failed to preserve corrupt JSON {path.name}: {e}")
        return []


def atomic_write_json(path: Path, doc: dict) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def prune_debug_files() -> None:
    if MAX_DEBUG_FILES <= 0:
        return
    files = [p for p in DEBUG_DIR.glob("*.json") if p.is_file()]
    extra = len(files) - MAX_DEBUG_FILES
    if extra <= 0:
        return
    for path in sorted(files, key=lambda p: p.stat().st_mtime)[:extra]:
        try:
            path.unlink()
        except OSError as e:
            print(f"[receiver] failed to prune debug file {path.name}: {e}")


def update_per_symbol_json(symbol: str, tf: str, new_candles: list[dict], tab_id: str = "unknown", received_at: str = None) -> tuple[int, int]:
    """
    Merge by timestamp and rewrite the per-symbol JSON.
    Only appends *new* candles to NDJSON (with tab_id) to avoid duplicates from multiple tabs.
    Returns (number of candles in the resulting file, number of newly appended records).
    """
    if received_at is None:
        received_at = now_iso()
    path = per_symbol_path(symbol, tf)
    with lock:
        existing = read_existing_candles(path)
        by_t = {int(c["t"]): c for c in existing if isinstance(c, dict) and "t" in c}
        appended = 0

        for c in new_candles:
            t = int(c["t"])
            prev = by_t.get(t)
            if prev:
                # defensive merge (the extension only sends fully closed candles)
                by_t[t] = {
                    "t": t,
                    "o": prev.get("o", c.get("o")),
                    "h": max(prev.get("h", c.get("h", 0)), c.get("h", 0)),
                    "l": min(prev.get("l", c.get("l", 1e9)), c.get("l", 1e9)),
                    "c": c.get("c", prev.get("c")),
                    "v": c.get("v", prev.get("v")),
                    "tab_id": prev.get("tab_id", tab_id),  # keep the first one that recorded it
                }
            else:
                rec = {
                    "symbol": symbol,
                    "tf": tf,
                    "ts": t,
                    "o": c.get("o"),
                    "h": c.get("h"),
                    "l": c.get("l"),
                    "c": c.get("c"),
                    "v": c.get("v", 0),
                    "tab_id": tab_id,
                    "received_at": received_at,
                }
                append_ndjson(rec)
                appended += 1
                by_t[t] = {
                    "t": t,
                    "o": c.get("o"),
                    "h": c.get("h"),
                    "l": c.get("l"),
                    "c": c.get("c"),
                    "v": c.get("v", 0),
                    "tab_id": tab_id,
                }

        merged = sorted(by_t.values(), key=lambda x: x["t"])

        doc = {
            "symbol": symbol.upper(),
            "timeframe": normalize_tf(tf),
            "updated_at": now_iso(),
            "count": len(merged),
            "candles": merged,
        }
        atomic_write_json(path, doc)
        return len(merged), appended


class Handler(BaseHTTPRequestHandler):
    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        allowed = (
            origin.startswith("chrome-extension://") or
            origin in {"http://localhost", "http://127.0.0.1"} or
            origin.startswith("http://localhost:") or
            origin.startswith("http://127.0.0.1:")
        )
        return origin if allowed else None

    def _send_json(self, obj: dict, status=200):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        cors_origin = self._cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _safe_static_path(self, url_path: str) -> Path | None:
        """Resolve /static/... under STATIC_DIR; reject path traversal."""
        rel = url_path[len("/static/"):] if url_path.startswith("/static/") else url_path.lstrip("/")
        if not rel or ".." in rel.split("/"):
            return None
        candidate = (STATIC_DIR / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        return candidate

    def _serve_static(self, url_path: str) -> bool:
        path = self._safe_static_path(url_path)
        if path is None:
            return False
        data = path.read_bytes()
        ctype = STATIC_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self._send_bytes(data, ctype)
        return True

    def do_OPTIONS(self):
        self.send_response(204)
        cors_origin = self._cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return None, ({"error": "bad content length"}, 400)
        if length <= 0:
            return None, ({"error": "empty body"}, 400)
        if length > MAX_BODY_BYTES:
            return None, ({"error": "body too large", "max_bytes": MAX_BODY_BYTES}, 413)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception as e:
            return None, ({"error": "bad json", "detail": str(e)}, 400)
        if not isinstance(payload, dict):
            return None, ({"error": "payload must be an object"}, 400)
        return payload, None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query or "")

        if path in ("/health", "/api/health"):
            db_info = session_db.health_check()
            self._send_json({
                "status": "ok",
                "version": "0.2.1-named-screeners",
                "ndjson": str(NDJSON_PATH),
                "data_dir": str(DATA_DIR),
                "db": db_info,
            })
            return

        if path in ("/config/screeners", "/api/config/screeners"):
            self._send_json(screener_config.public_config())
            return

        if path == "/session/today":
            sess = session_db.get_session(None, include_tickers=True)
            if sess is None:
                self._send_json({
                    "ok": True,
                    "session_date": session_db.session_date_today(),
                    "tickers": [],
                    "ticker_count": 0,
                    "exists": False,
                })
            else:
                self._send_json({"ok": True, "exists": True, **sess})
            return

        if path == "/session":
            date = (qs.get("date") or [None])[0]
            if not date:
                self._send_json({"error": "date query param required (YYYY-MM-DD)"}, 400)
                return
            sess = session_db.get_session(date, include_tickers=True)
            if sess is None:
                self._send_json({"ok": True, "exists": False, "session_date": date, "tickers": [], "ticker_count": 0})
            else:
                self._send_json({"ok": True, "exists": True, **sess})
            return

        if path == "/sessions":
            try:
                limit = int((qs.get("limit") or ["30"])[0])
            except ValueError:
                limit = 30
            limit = max(1, min(limit, 365))
            self._send_json({"ok": True, "sessions": session_db.list_sessions(limit=limit)})
            return

        if path in ("/session/events", "/api/session/events"):
            date = (qs.get("date") or [None])[0] or session_db.session_date_today()
            event_filter = (qs.get("event") or [None])[0]
            try:
                limit = int((qs.get("limit") or ["0"])[0]) or None
            except ValueError:
                limit = None
            events = session_log.read_events(date, event=event_filter, limit=limit)
            self._send_json({
                "ok": True,
                "session_date": date,
                "count": len(events),
                "log_path": str(session_log.log_path(date)),
                "events": events,
            })
            return

        if path in ("/watchlist/status", "/api/watchlist/status"):
            cfg = webull_watchlist.load_config()
            date = (qs.get("date") or [None])[0] or session_db.session_date_today()
            try:
                rows = webull_watchlist.list_sync_for_session(date)
            except Exception as e:
                rows = []
                err = str(e)
            else:
                err = None

            # Live membership from Webull (MCP OAuth / OpenAPI)
            live = webull_watchlist.fetch_live_watchlist_symbols(cfg)
            live_set = set(live.get("symbols") or [])

            # Session tickers for this date (for per-row lights)
            sess = session_db.get_session(date, include_tickers=True)
            session_tickers = [
                t.get("ticker") for t in (sess or {}).get("tickers") or [] if t.get("ticker")
            ]
            membership = webull_watchlist.membership_for_tickers(
                session_tickers,
                live_symbols=live_set,
                sync_rows=rows,
            )

            # MCP OAuth logged-in if tokens exist
            has_mcp = False
            try:
                from pathlib import Path as _P
                has_mcp = (_P(__file__).parent / "conf" / "webull_mcp_tokens.json").is_file()
            except Exception:
                pass

            self._send_json({
                "ok": err is None and live.get("ok", False),
                "session_date": date,
                "config": {
                    "enabled": cfg.get("enabled"),
                    "dry_run": cfg.get("dry_run"),
                    "auth_mode": cfg.get("auth_mode"),
                    "watchlist_name": cfg.get("watchlist_name"),
                    "screener_keys": cfg.get("screener_keys"),
                    "has_credentials": bool(
                        os.environ.get("WEBULL_APP_KEY") and os.environ.get("WEBULL_APP_SECRET")
                    ),
                    "has_mcp_tokens": has_mcp,
                },
                "sync": rows,
                "live": {
                    "ok": live.get("ok"),
                    "watchlist_id": live.get("watchlist_id"),
                    "watchlist_name": live.get("watchlist_name"),
                    "symbols": live.get("symbols") or [],
                    "count": len(live.get("symbols") or []),
                    "error": live.get("error"),
                },
                "membership": membership,
                "error": err or live.get("error"),
            })
            return

        # Web UI
        if path in ("/", "/ui", "/ui/"):
            index = STATIC_DIR / "index.html"
            if index.is_file():
                self._send_bytes(index.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send_json({"error": "UI not found — missing static/index.html"}, 404)
            return

        if path.startswith("/static/"):
            if self._serve_static(path):
                return
            self._send_json({"error": "static file not found"}, 404)
            return

        if path in ("/api", "/api/"):
            self._send_json({
                "name": "webull-stock-monitor receiver",
                "version": "0.2.1-named-screeners",
                "ui": "http://127.0.0.1:8787/",
                "endpoints": [
                    "GET / — session UI",
                    "POST /push — closed candles → JSON files",
                    "POST /screener — screener rows → daily session SQLite",
                    "POST /session/event — lifecycle events (screener_open/close, …)",
                    "GET /config/screeners — enabled named screeners (Gap'n'Go, …)",
                    "GET /session/today",
                    "GET /session?date=YYYY-MM-DD",
                    "GET /session/events?date=YYYY-MM-DD",
                    "GET /sessions",
                    "GET /health",
                    "POST /debug/dom",
                ],
                "output": {
                    "candles": str(DATA_DIR),
                    "db": str(session_db.get_db_path()),
                    "session_events": str(SESSIONS_LOG_DIR),
                },
            })
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/debug/dom":
            self.handle_debug_dom()
            return

        if path in ("/screener", "/api/screener"):
            self.handle_screener()
            return

        if path in ("/session/event", "/api/session/event"):
            self.handle_session_event()
            return

        if path not in ("/push", "/api/candles"):
            self._send_json({"error": "use /push or /screener"}, 404)
            return

        payload, err = self._read_json_body()
        if err:
            body, status = err
            self._send_json(body, status)
            return

        symbol = safe_name((payload.get("symbol") or "UNKNOWN").upper())
        tf = normalize_tf(payload.get("timeframe") or "unknown")
        candles = payload.get("candles") or []
        tab_id = safe_name(payload.get("tab_id") or "unknown", "unknown")

        print(f"[receiver] received {len(candles)} candles for {symbol} {tf} from {tab_id}")

        if not isinstance(candles, list) or not candles:
            self._send_json({"error": "no candles"}, 400)
            return

        valid_candles, rejected = validate_candles(candles)
        if not valid_candles:
            self._send_json({
                "error": "no valid candles",
                "received": len(candles),
                "rejected": rejected[:20],
                "rejected_count": len(rejected),
            }, 400)
            return

        received_at = payload.get("captured_at") or now_iso()

        # Update the per-symbol JSON (dedup by ts inside; only new ones are appended to NDJSON with tab_id)
        total, appended = update_per_symbol_json(symbol, tf, valid_candles, tab_id=tab_id, received_at=received_at)

        self._send_json({
            "ok": True,
            "symbol": symbol,
            "timeframe": tf,
            "received": len(candles),
            "accepted": len(valid_candles),
            "rejected": len(rejected),
            "appended": appended,
            "total_in_file": total,
            "ndjson": str(NDJSON_PATH),
            "json_file": str(per_symbol_path(symbol, tf)),
        })

    def handle_screener(self):
        payload, err = self._read_json_body()
        if err:
            body, status = err
            self._send_json(body, status)
            return

        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            self._send_json({"error": "rows must be an array"}, 400)
            return

        source_url = payload.get("source_url") or payload.get("url")
        captured_at = payload.get("captured_at") or now_iso()
        tab_id = payload.get("tab_id") or "unknown"
        session_date = payload.get("session_date")  # optional override (tests)
        screener_key = payload.get("screener_key")
        screener_name = payload.get("screener_name")

        # Extension must arm on a configured My Screener (e.g. Gap'n'Go)
        if not screener_key:
            print(f"[receiver] REJECTED screener push from {tab_id}: missing screener_key (not armed)")
            self._send_json({
                "ok": False,
                "error": "screener_key required — open My Screeners and select a configured screener",
            }, 400)
            return

        cfg = screener_config.load_config()
        enabled_keys = {s["key"] for s in screener_config.enabled_screeners(cfg)}
        if screener_key not in enabled_keys:
            print(f"[receiver] REJECTED screener push: key={screener_key!r} not in enabled config")
            self._send_json({
                "ok": False,
                "error": f"screener_key {screener_key!r} is not an enabled configured screener",
                "enabled": sorted(enabled_keys),
            }, 400)
            return

        # Prefer canonical name + limits from config
        max_rows = screener_config.max_rows_per_push(screener_key, cfg)
        max_session = screener_config.max_session_tickers(screener_key, cfg)
        for s in screener_config.enabled_screeners(cfg):
            if s["key"] == screener_key:
                screener_name = s["name"]
                break

        # Hard abort: oversized batch = almost certainly the wrong screener / bulk quotes
        if len(rows) > max_rows:
            print(
                f"[receiver] REJECTED screener push from {tab_id}: "
                f"{len(rows)} rows > max_rows_per_push={max_rows} for {screener_key!r} "
                f"(likely wrong screener or quote dump)"
            )
            session_log.log_event(
                "push_rejected",
                session_date=session_date or session_db.session_date_today(),
                reason="batch_too_large",
                screener_key=screener_key,
                screener_name=screener_name,
                row_count=len(rows),
                max_rows_per_push=max_rows,
                tab_id=tab_id,
                source_url=source_url,
            )
            self._send_json({
                "ok": False,
                "error": "batch_too_large",
                "message": (
                    f"Rejected {len(rows)} rows for {screener_name or screener_key}: "
                    f"max_rows_per_push={max_rows}. Wrong screener or bulk quote traffic."
                ),
                "received": len(rows),
                "max_rows_per_push": max_rows,
                "screener_key": screener_key,
            }, 400)
            return

        # Optional session cap (unique tickers for the day under this screener)
        try:
            date = session_date or session_db.session_date_today()
            existing = session_db.get_session(date, include_tickers=True)
            existing_count = (existing or {}).get("ticker_count") or 0
            # Count how many of this batch are new symbols
            existing_set = {
                (t.get("ticker") or "").upper()
                for t in (existing or {}).get("tickers") or []
            }
            batch_syms = set()
            for r in rows:
                if isinstance(r, dict):
                    sym = (r.get("ticker") or r.get("symbol") or "").upper().strip()
                    if sym:
                        batch_syms.add(sym)
            new_count = len(batch_syms - existing_set)
            if existing_count + new_count > max_session and new_count > 0:
                # If already over or would blow past max with many new names, reject
                if existing_count >= max_session or new_count > max_rows:
                    print(
                        f"[receiver] REJECTED screener push: session would exceed "
                        f"max_session_tickers={max_session} "
                        f"(have={existing_count}, new_in_batch={new_count})"
                    )
                    session_log.log_event(
                        "push_rejected",
                        session_date=date,
                        reason="session_too_large",
                        screener_key=screener_key,
                        screener_name=screener_name,
                        existing_count=existing_count,
                        new_in_batch=new_count,
                        max_session_tickers=max_session,
                        tab_id=tab_id,
                    )
                    self._send_json({
                        "ok": False,
                        "error": "session_too_large",
                        "message": (
                            f"Session already has {existing_count} tickers; "
                            f"batch adds ~{new_count} new. max_session_tickers={max_session}."
                        ),
                        "existing_count": existing_count,
                        "new_in_batch": new_count,
                        "max_session_tickers": max_session,
                        "screener_key": screener_key,
                    }, 400)
                    return
        except Exception as e:
            print(f"[receiver] session size check skipped: {e}")

        print(
            f"[receiver] screener push: {len(rows)} rows from {tab_id} "
            f"screener={screener_name!r} ({screener_key})"
        )

        result = session_db.upsert_screener_rows(
            rows,
            source_url=source_url,
            captured_at=captured_at,
            session_date=session_date,
            screener_key=screener_key,
            screener_name=screener_name,
        )
        sess_date = result.get("session_date") or session_date or session_db.session_date_today()

        if result.get("session_created"):
            session_log.log_event(
                "session_start",
                session_date=sess_date,
                session_id=result.get("session_id"),
                screener_key=screener_key,
                screener_name=screener_name,
                tab_id=tab_id,
            )

        session_log.log_event(
            "screener_push",
            session_date=sess_date,
            screener_key=screener_key,
            screener_name=screener_name,
            row_count=len(rows),
            new_count=len(result.get("new_tickers") or []),
            updated_count=result.get("updated_tickers") or 0,
            tab_id=tab_id,
            source_url=source_url,
        )

        if result.get("new_tickers"):
            print(f"[receiver] new session tickers ({screener_key}): {result['new_tickers']}")
            for t in result["new_tickers"]:
                session_log.log_event(
                    "ticker_added",
                    session_date=sess_date,
                    ticker=t,
                    screener_key=screener_key,
                    screener_name=screener_name,
                    tab_id=tab_id,
                )
            # Auto-add brand-new Gap'n'Go names to Webull watchlist
            try:
                wl = webull_watchlist.sync_new_tickers(
                    result["new_tickers"],
                    session_date=sess_date,
                    screener_key=screener_key,
                )
                result["watchlist"] = wl
                if wl.get("added"):
                    mode = "dry-run " if wl.get("dry_run") else ""
                    print(
                        f"[receiver] watchlist {mode}sync → {wl.get('watchlist_name')}: "
                        f"added {wl['added']}"
                    )
                    for t in wl["added"]:
                        session_log.log_event(
                            "watchlist_added",
                            session_date=sess_date,
                            ticker=t,
                            watchlist_name=wl.get("watchlist_name"),
                            dry_run=wl.get("dry_run"),
                        )
                if wl.get("errors"):
                    print(f"[receiver] watchlist sync errors: {wl['errors']}")
                    session_log.log_event(
                        "watchlist_error",
                        session_date=sess_date,
                        errors=wl.get("errors"),
                        tickers=result["new_tickers"],
                    )
            except Exception as e:
                print(f"[receiver] watchlist sync failed: {e}")
                result["watchlist"] = {"ok": False, "errors": [str(e)]}
                session_log.log_event(
                    "watchlist_error",
                    session_date=sess_date,
                    errors=[str(e)],
                    tickers=result["new_tickers"],
                )

        self._send_json(result)

    def handle_session_event(self):
        """POST /session/event — lifecycle events from extension (screener open/close, etc.)."""
        payload, err = self._read_json_body()
        if err:
            body, status = err
            self._send_json(body, status)
            return

        event = (payload.get("event") or "").strip()
        if not event:
            self._send_json({"error": "event required"}, 400)
            return

        allowed = {
            "screener_open", "screener_close", "session_end",
            "session_start",  # rare: client-initiated
        }
        if event not in allowed and event not in session_log.EVENTS:
            # still accept unknown for forward-compat, but prefer known
            pass

        date = payload.get("session_date") or session_db.session_date_today()
        fields = {
            k: payload.get(k)
            for k in (
                "screener_key", "screener_name", "tab_id", "url",
                "reason", "ui_region", "manual",
            )
            if payload.get(k) is not None
        }
        rec = session_log.log_event(event, session_date=date, **fields)
        print(f"[receiver] session event: {event} date={date} {fields}")
        self._send_json({"ok": True, "logged": rec})

    def handle_debug_dom(self):
        payload, err = self._read_json_body()
        if err:
            body, status = err
            self._send_json(body, status)
            return

        ts = int(payload.get("timestamp", time.time() * 1000))
        reason = safe_name(payload.get("reason", "dom"), "dom")
        fname = f"{reason}-{ts}.json"
        path = DEBUG_DIR / fname
        raw_size = len(json.dumps(payload).encode("utf-8"))

        with lock:
            atomic_write_json(path, payload)
            prune_debug_files()

        print(f"[receiver] wrote debug: {path.name} (reason: {reason})")

        # Helpful prints for debugging
        if payload.get("raw_from_inject") or payload.get("raw_json"):
            r = payload.get("raw_from_inject") or payload.get("raw_json", {})
            url = r.get("url", "") if isinstance(r, dict) else ""
            if "kline" in url.lower() or "bar" in url.lower() or "candle" in url.lower():
                print(f"  >>> LOOKS LIKE KLINE URL: {url[:120]}")
            if isinstance(url, str) and any(x in url.lower() for x in ("screener", "scanner", "rank")):
                print(f"  >>> LOOKS LIKE SCREENER URL: {url[:120]}")
            print(f"  raw keys sample: {list(r.keys())[:6] if isinstance(r, dict) else 'array'}")

        self._send_json({
            "ok": True,
            "written": str(path),
            "size": raw_size,
        })


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    session_log.set_base_dir(SESSIONS_LOG_DIR)
    init_session_db()
    print(f"Webull Stock Monitor — candles + screener sessions")
    print(f"Listening on http://{HOST}:{PORT}")
    webull_watchlist.load_dotenv()
    wl_cfg = webull_watchlist.load_config()
    has_creds = bool(os.environ.get("WEBULL_APP_KEY") and os.environ.get("WEBULL_APP_SECRET"))
    print(f"UI        → http://{HOST}:{PORT}/")
    print(f"Candles   → {DATA_DIR}")
    print(f"Sessions  → {session_db.get_db_path()}")
    print(f"Event log → {SESSIONS_LOG_DIR}/YYYY-MM-DD/events.ndjson")
    print(
        f"Watchlist → {wl_cfg.get('watchlist_name')!r} "
        f"enabled={wl_cfg.get('enabled')} dry_run={wl_cfg.get('dry_run') or not has_creds} "
        f"creds={'yes' if has_creds else 'NO (set WEBULL_APP_KEY/SECRET)'}"
    )
    print("POST /push          — closed candles (chart tabs)")
    print("POST /screener      — screener rows → daily session (America/New_York)")
    print("POST /session/event — lifecycle events (screener open/close, …)")
    print("GET  /session/today | /session?date= | /sessions | /session/events | /watchlist/status")
    print("POST /debug/dom")
    print("Ctrl-C to stop.\n")

    session_log.log_event(
        "receiver_start",
        host=HOST,
        port=PORT,
        db=str(session_db.get_db_path()),
    )

    server = HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        session_log.log_event("receiver_stop", reason="shutdown")
        server.server_close()


if __name__ == "__main__":
    main()
