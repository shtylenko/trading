"""Local web server for the simulation viewer (SPA + live API).

Serves the SPA (``viewer/index.html``) plus a small JSON API over the session
folders under ``simulations/``:

    GET  /api/sessions                     list (newest first)
    GET  /api/session/<id>/state           UI view (finalized files, or a live
                                           view computed from revealed data only)
    GET  /api/session/<id>/events          Server-Sent Events (fs-mtime notifications)
    POST /api/session/<id>/finalize        finalize (force-closes any open position)

Running sessions update live via SSE; the server is threaded so a parked SSE
connection doesn't block other requests. Private step internals (``_sealed.jsonl``,
``_step.json``) are never served, to preserve no-look-ahead.

    python3 -m trading.llm_trader.viewer                       # open the SPA (session list)
    python3 -m trading.llm_trader.viewer --session <id>        # deep-link a session
    python3 -m trading.llm_trader.viewer --list                # CLI list, no server
    python3 -m trading.llm_trader.viewer --port 8765 --no-browser
"""

from __future__ import annotations

import argparse
import http.server
import json
import queue
import socketserver
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import re

PKG_DIR = Path(__file__).resolve().parent
SIM_ROOT = PKG_DIR / "simulations"

# session ids are ``{YYYYMMDDHHMMSS}-{TICKER}`` — restrict to that character set so
# a crafted id can never escape SIM_ROOT (e.g. ``../../etc``).
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_session_id(sid: str) -> Optional[str]:
    if sid and ".." not in sid and _SESSION_ID_RE.match(sid):
        return sid
    return None

# --- SSE pub/sub for live updates ---
# Keyed by session id → a list of per-client queues. The monitor thread only
# *enqueues*; each request-handler thread is the sole writer to its own socket
# (draining its queue), so there is no concurrent write to one connection.
_sse_clients: dict[str, list[queue.Queue]] = {}
_sse_lock = threading.Lock()
_monitor_thread_started = False


def _sse_broadcast(session_id: str, event: dict):
    """Enqueue an event for every client subscribed to this session."""
    data = f"data: {json.dumps(event)}\n\n".encode("utf-8")
    with _sse_lock:
        clients = list(_sse_clients.get(session_id, []))
    for q in clients:
        try:
            q.put_nowait(data)
        except queue.Full:
            pass  # slow client; drop this update, it'll refetch state on the next


def _register_sse_client(session_id: str) -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=100)
    with _sse_lock:
        _sse_clients.setdefault(session_id, []).append(q)
    _start_monitor()
    return q


def _unregister_sse_client(session_id: str, q: queue.Queue):
    with _sse_lock:
        lst = _sse_clients.get(session_id, [])
        if q in lst:
            lst.remove(q)


def _start_monitor():
    """Background thread that polls mtimes of key files and notifies SSE clients."""
    global _monitor_thread_started
    with _sse_lock:
        if _monitor_thread_started:
            return
        _monitor_thread_started = True

    def monitor():
        last_mtime: dict[str, float] = {}
        while True:
            try:
                # Nothing is listening → don't stat every session folder on a
                # 0.8s loop. Idle cheaply until a browser opens an SSE stream.
                with _sse_lock:
                    has_clients = any(_sse_clients.values())
                if not has_clients:
                    time.sleep(1.0)
                    continue
                if not SIM_ROOT.exists():
                    time.sleep(1.0)
                    continue
                for sdir in SIM_ROOT.iterdir():
                    if not (sdir / "session.json").exists():
                        continue
                    sid = sdir.name
                    key_files = [sdir / "stream.jsonl", sdir / "decisions.jsonl", sdir / "session.json"]
                    current = 0.0
                    for f in key_files:
                        if f.exists():
                            current = max(current, f.stat().st_mtime)
                    prev = last_mtime.get(sid, 0.0)
                    if current > prev + 0.001:
                        last_mtime[sid] = current
                        _sse_broadcast(sid, {"type": "update", "session": sid, "ts": current})
            except Exception:
                pass
            time.sleep(0.8)  # poll ~1.25 times/sec is plenty for local use

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the package dir + dynamic API + SSE. Quiet logging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PKG_DIR), **kwargs)

    def log_message(self, *args, **kwargs):  # noqa: D401 - silence access log
        pass

    # ---------------- API + SSE support ----------------

    def _send_json(self, obj, status=200):
        data = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _send_sse_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        # No Access-Control-Allow-Origin: this is a localhost tool; the SPA is
        # served same-origin, so nothing legitimate is cross-origin, and a wildcard
        # would let any web page you visit subscribe to your session stream.
        self.end_headers()

    def _get_session_id(self, path: str) -> Optional[str]:
        # /api/session/<id>/...
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[1] == "session":
            return _safe_session_id(parts[2])
        return None

    def _is_local_request(self) -> bool:
        """True unless the request looks cross-origin. A browser attaches an
        ``Origin`` header to state-changing cross-site POSTs; if one is present it
        must point back at this same localhost server. This blocks a random web
        page from POSTing to our localhost API (a classic localhost CSRF)."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # non-browser client (curl) or same-origin GET-style POST
        parsed = urlparse(origin)
        return parsed.hostname in ("127.0.0.1", "localhost")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API routes
        if path == "/api/sessions":
            try:
                from . import recorder
                sessions = recorder.list_sessions()
                self._send_json({"sessions": sessions})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/session/"):
            sid = self._get_session_id(path)
            if not sid:
                self._send_json({"error": "bad session id"}, 400)
                return

            if path.endswith("/state") or path.endswith("/state/"):
                try:
                    from . import recorder
                    view = recorder.get_session_view(SIM_ROOT / sid)
                    self._send_json(view)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
                return

            if path.endswith("/events") or path.endswith("/events/"):
                # Server-Sent Events. This handler thread is the SOLE writer to the
                # socket: it drains this client's queue (fed by the monitor thread)
                # and emits a heartbeat when idle.
                self._send_sse_headers()
                self.wfile.write(b"event: connected\ndata: {}\n\n")
                self.wfile.flush()
                q = _register_sse_client(sid)
                try:
                    while True:
                        try:
                            data = q.get(timeout=25)
                        except queue.Empty:
                            data = b": keep-alive\n\n"
                        self.wfile.write(data)
                        self.wfile.flush()
                except Exception:
                    pass  # client disconnected
                finally:
                    _unregister_sse_client(sid, q)
                return

        # Never serve private simulator internals over HTTP (the sealed full-day
        # stream + step cursor). Exposing them would break no-look-ahead.
        if any(seg.startswith("_") or seg.startswith(".") for seg in path.split("/") if seg):
            self.send_error(404, "Not Found")
            return

        # Session data goes through the API only (which clamps live sessions to
        # revealed bars). The raw files — notably the full-day stream.jsonl — must
        # never be fetched directly; that would leak future bars into a live view.
        if "simulations" in [seg for seg in path.split("/") if seg]:
            self.send_error(404, "Not Found")
            return

        # Default: static file serving
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/session/") and path.endswith("/finalize"):
            if not self._is_local_request():
                self.send_error(403, "Forbidden")
                return
            sid = self._get_session_id(path)
            if sid:
                return self._do_finalize(sid)
        self.send_response(404)
        self.end_headers()

    def _do_finalize(self, sid: str):
        try:
            from . import recorder
            # Force-close any still-open position at the last known price. This is a
            # LIVE session snapshot, so clamp the chart to revealed bars (full_day
            # =False) — never reveal price action past where trading stopped.
            session = recorder.finalize(SIM_ROOT / sid, full_day=False)
            self._send_json({"ok": True, "session": session})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


class _Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # Threaded: an SSE /events connection parks in a long-lived handler, so a
    # single-threaded server would freeze every other request while one is open.
    allow_reuse_address = True
    daemon_threads = True


def _sessions() -> list[str]:
    if not SIM_ROOT.exists():
        return []
    return sorted(d.name for d in SIM_ROOT.iterdir() if (d / "session.json").exists())


def _resolve_session(arg: Optional[str]) -> Optional[str]:
    if arg:
        name = Path(arg).name
        if not (SIM_ROOT / name / "session.json").exists():
            raise SystemExit(
                f"session '{name}' not found under {SIM_ROOT}.\n"
                f"available: {', '.join(_sessions()) or '(none)'}"
            )
        return name
    sess = _sessions()
    return sess[-1] if sess else None


def serve(session: Optional[str], port: int = 8765, open_browser: bool = True) -> None:
    # Start the FS monitor early so SSE works immediately
    _start_monitor()

    with _Server(("127.0.0.1", port), _Handler) as httpd:
        url = f"http://127.0.0.1:{port}/viewer/index.html"
        if session:
            url += f"?session={session}"
        print(f"serving {PKG_DIR} at {url}")
        print("Ctrl-C to stop.  Default view = session list (newest first).")
        if open_browser:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.viewer",
        description="Web UI server for day trading simulations (list + live detail view).",
    )
    p.add_argument("--session", help="session id to open directly (optional)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    p.add_argument("--list", action="store_true", help="list sessions on CLI and exit (no server)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        try:
            from . import recorder
            for s in recorder.list_sessions():
                print(f"{s['id']}  {s['ticker']} {s['historical_date']}  {s.get('mode','simulated')} {s['status']}")
            if not recorder.list_sessions():
                print("(no sessions yet)")
        except Exception as e:
            print(f"(error listing: {e})")
        return 0

    # If no explicit session, we still start the server; the SPA will show the list by default.
    session = _resolve_session(args.session) if args.session else None
    serve(session, port=args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
