#!/usr/bin/env python3
"""
Minimal local receiver for Webull candle data.

Primary goal (per spec answers 2026-07-02):
  Collect **closed** candlebar data into local JSON file(s).

Rules applied by the extension:
- Only fully closed candles (no forming/incomplete bars).
- Pushes happen when a candle closes (newer bar timestamp seen for that symbol+tf).
- The timeframe that is currently open/selected in the Webull chart is recorded.
- Multiple tabs can have monitoring enabled independently.

POST /push  (from extension)
  {
    "symbol": "AAPL",
    "timeframe": "5m",     // the active/open timeframe on that tab
    "captured_at": "...",
    "candles": [ {"t": ms_since_epoch, "o":, "h":, "l":, "c":, "v": }, ... ]   // closed bars only
  }

Outputs (backend/data/captures/):
  candles.ndjson                     (append-only log, one line per candle)
  {SYMBOL}_{TF}.json                 (current view, deduped by t)

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
from urllib.parse import urlparse

# Config
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "captures"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

NDJSON_PATH = DATA_DIR / "candles.ndjson"
lock = RLock()  # reentrant to allow append inside update lock

MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(5 * 1024 * 1024)))
MAX_DEBUG_FILES = int(os.environ.get("MAX_DEBUG_FILES", "500"))
MIN_TS_MS = 946684800000      # 2000-01-01
MAX_TS_MS = 4102444800000     # 2100-01-01
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


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

    def do_OPTIONS(self):
        self.send_response(204)
        cors_origin = self._cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/health", "/api/health"):
            self._send_json({
                "status": "ok",
                "version": "0.1.0-minimal-json",
                "ndjson": str(NDJSON_PATH),
                "data_dir": str(DATA_DIR),
            })
            return
        if parsed.path == "/":
            self._send_json({
                "name": "webull-stock-monitor minimal receiver",
                "endpoints": ["/push (POST)", "/health", "/api/health"],
                "output": "local JSON files under data/captures/",
            })
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/push", "/api/candles"):
            if parsed.path == "/debug/dom":
                self.handle_debug_dom()
                return
            self._send_json({"error": "use /push"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json({"error": "bad content length"}, 400)
            return
        if length <= 0:
            self._send_json({"error": "empty body"}, 400)
            return
        if length > MAX_BODY_BYTES:
            self._send_json({"error": "body too large", "max_bytes": MAX_BODY_BYTES}, 413)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception as e:
            self._send_json({"error": "bad json", "detail": str(e)}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "payload must be an object"}, 400)
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

    def handle_debug_dom(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json({"error": "bad content length"}, 400)
            return
        if length <= 0:
            self._send_json({"error": "empty body"}, 400)
            return
        if length > MAX_BODY_BYTES:
            self._send_json({"error": "body too large", "max_bytes": MAX_BODY_BYTES}, 413)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception as e:
            self._send_json({"error": "bad json", "detail": str(e)}, 400)
            return

        ts = int(payload.get("timestamp", time.time() * 1000))
        reason = safe_name(payload.get("reason", "dom"), "dom")
        fname = f"{reason}-{ts}.json"
        path = DEBUG_DIR / fname

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
            print(f"  raw keys sample: {list(r.keys())[:6] if isinstance(r, dict) else 'array'}")

        self._send_json({
            "ok": True,
            "written": str(path),
            "size": len(raw),
        })


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Webull Stock Monitor — minimal JSON receiver (closed candles only)")
    print(f"Listening on http://{HOST}:{PORT}")
    print(f"Writing to: {DATA_DIR}")
    print("Only closed bars (no forming candles) from the active/open timeframe per tab.")
    print("POST /push  — multiple tabs ok")
    print("POST /debug/dom — DOM + RAW JSON dumps (DEBUG_ALL_RESPONSES mode is ON in inject.js)")
    print("Ctrl-C to stop.\n")

    server = HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
