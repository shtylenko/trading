"""Tests for the no-lookahead feed reader (core reliability contract)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading.llm_trader.feed import read


def _write_stream(path: Path, lines: list[dict]):
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def test_nostream_when_missing(tmp_path):
    p = tmp_path / "stream.jsonl"
    from io import StringIO
    out = StringIO()
    rc = read(p, 0, out=out, wait=False)
    assert rc == 3
    assert "nostream" in out.getvalue().lower()


def test_meta_then_tick_then_status_ok(tmp_path):
    p = tmp_path / "s.jsonl"
    lines = [
        {"type": "meta", "ticker": "T", "date": "2025-03-10"},
        {"type": "tick", "i": 0, "time": "09:30", "c": 5.0},
        {"type": "end", "bars": 1, "close": 5.1},
    ]
    _write_stream(p, lines)

    # cursor 0 should emit meta + tick + STATUS ok
    # We capture via a temp file? Use a list capture by overriding print is complex;
    # instead call and inspect side effects aren't written, so use StringIO.
    from io import StringIO

    out = StringIO()
    rc = read(str(p), 0, out=out, wait=False)
    text = out.getvalue()
    assert rc == 0
    assert '"type": "meta"' in text
    assert '"i": 0' in text
    assert "STATUS ok next_cursor=1" in text


def test_waiting_when_not_yet_written(tmp_path):
    p = tmp_path / "live.jsonl"
    # only meta, no tick 5 yet
    _write_stream(p, [{"type": "meta"}, {"type": "tick", "i": 0, "time": "09:30"}])
    from io import StringIO

    out = StringIO()
    rc = read(str(p), 5, out=out, wait=False, timeout=0.01)
    assert rc == 2
    assert "STATUS waiting" in out.getvalue()


def test_ended_flag_not_leaked_by_full_file(tmp_path):
    # With `replay --delay 0` the whole file (incl the end line) is on disk at once.
    # A non-final tick must still report ended=false — otherwise the flag would leak
    # that the stream is complete / how many bars remain.
    p = tmp_path / "full.jsonl"
    _write_stream(p, [
        {"type": "meta"},
        {"type": "tick", "i": 0, "time": "09:30"},
        {"type": "tick", "i": 1, "time": "09:31"},
        {"type": "end", "bars": 2},
    ])
    from io import StringIO

    out = StringIO()
    read(str(p), 0, out=out, wait=False)  # first (non-final) tick
    assert "ended=false" in out.getvalue()

    out = StringIO()
    read(str(p), 1, out=out, wait=False)  # last tick
    assert "ended=true" in out.getvalue()


def test_end_status_when_past_end(tmp_path):
    p = tmp_path / "e.jsonl"
    _write_stream(p, [
        {"type": "meta"},
        {"type": "tick", "i": 0},
        {"type": "end", "bars": 1},
    ])
    from io import StringIO
    out = StringIO()
    rc = read(str(p), 0, out=out, wait=False)
    assert rc == 0
    assert "STATUS end" in out.getvalue() or "STATUS ok" in out.getvalue()
