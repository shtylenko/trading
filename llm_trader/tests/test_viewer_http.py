"""HTTP-level regression tests for the viewer server's no-look-ahead / hardening
guards. Spins up the real server on an ephemeral port and makes live requests."""

from __future__ import annotations

import threading
import urllib.request
import urllib.error

import pytest

from trading.llm_trader import viewer


def _get(port, path, headers=None, method="GET"):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


@pytest.fixture()
def server():
    httpd = viewer._Server(("127.0.0.1", 0), viewer._Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_raw_session_files_are_404(server):
    # the full-day stream.jsonl (and any raw session file) must never be fetchable
    status, _ = _get(server, "/simulations/anything/stream.jsonl")
    assert status == 404
    status, _ = _get(server, "/simulations/x/_sealed.jsonl")
    assert status == 404


def test_private_underscore_paths_are_404(server):
    status, _ = _get(server, "/viewer/_secret")
    assert status == 404


def test_static_spa_is_served(server):
    status, body = _get(server, "/viewer/app.js")
    assert status == 200 and b"renderChart" in body
    # multi-strategy UI hooks must ship with the SPA
    assert b"strategy" in body
    assert b"isMultiDaySession" in body
    assert b"sma50" in body
    assert b"setSidebarStrategy" in body
    assert b"sidebarStrategy" in body
    # multi-day blotter/timeline must receive multiDay (date in when column)
    assert b"fmtWhen" in body
    assert b"renderBlotter(view.actions || [], multiDay" in body
    assert b"renderTimeline(view.decisions || [], chart, multiDay)" in body


def test_bad_session_id_rejected(server):
    # a path-traversal-ish id never reaches the filesystem as a real session
    status, _ = _get(server, "/api/session/..%2Fetc/state")
    assert status != 200


def test_cross_origin_finalize_forbidden(server):
    # a POST carrying a foreign Origin (localhost CSRF) must be refused
    status, _ = _get(
        server, "/api/session/whatever/finalize",
        headers={"Origin": "http://evil.example.com"}, method="POST",
    )
    assert status == 403
