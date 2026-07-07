"""Tests for the sealed-source / incremental-reveal stepper (no-look-ahead core).

The stepper is what the TRADE_SIMULATOR skill uses to guarantee no look-ahead
*physically*: the whole day is sealed into a private file and the visible stream
only ever grows one bar at a time. These tests stub the data provider (replay) so
they run offline.
"""

from __future__ import annotations

import json
from datetime import date
from io import StringIO
from pathlib import Path

from trading.llm_trader import replay, step
from trading.llm_trader.replay import Setup
from trading.llm_trader.streamio import parse_stream

_SEALED = [
    {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20",
     "entry_px": 3.9, "anchor_px": 3.9, "session_end": "16:00", "reason": "demo"},
    {"type": "tick", "i": 0, "time": "10:20", "o": 3.6, "h": 3.8, "l": 3.5, "c": 3.75, "v": 100},
    {"type": "tick", "i": 1, "time": "10:21", "o": 3.75, "h": 3.9, "l": 3.7, "c": 3.85, "v": 90},
    {"type": "end", "bars": 2, "session_high": 3.9, "close": 3.85},
]


def _install_fake_provider(monkeypatch):
    """Make step.start seal a fixed 2-bar day without touching a real provider."""
    setup = Setup(ticker="TEST", day=date(2025, 3, 10), time_et="10:20",
                  entry_px=3.9, gap_pct=1.0, rvol=2.0, float_shares=1e6, reason="demo")
    monkeypatch.setattr(replay, "pick_setup", lambda *a, **k: setup)

    def fake_replay(_setup, **kw):
        Path(kw["out_file"]).write_text(
            "\n".join(json.dumps(x) for x in _SEALED) + "\n"
        )
        return 2

    monkeypatch.setattr(replay, "replay", fake_replay)


def test_start_reveals_meta_only(tmp_path, monkeypatch):
    _install_fake_provider(monkeypatch)
    sdir = tmp_path / "sess"
    rc = step.start(sdir, seed=1, out=StringIO())
    assert rc == 0

    # sealed file holds the WHOLE day...
    smeta, sticks, send = parse_stream(sdir / "_sealed.jsonl")
    assert smeta is not None and len(sticks) == 2 and send is not None

    # ...but the visible stream reveals only meta — no bars, no end line
    vmeta, vticks, vend = parse_stream(sdir / "stream.jsonl")
    assert vmeta is not None and vticks == [] and vend is None


def test_next_reveals_one_bar_at_a_time(tmp_path, monkeypatch):
    _install_fake_provider(monkeypatch)
    sdir = tmp_path / "sess"
    step.start(sdir, seed=1, out=StringIO())

    # reveal bar 0
    out = StringIO()
    assert step.next_(sdir, out=out) == 0
    _, ticks, end = parse_stream(sdir / "stream.jsonl")
    assert [t["i"] for t in ticks] == [0] and end is None
    assert "STATUS ok next=1 ended=false" in out.getvalue()

    # reveal bar 1 (the last) — ended=true
    out = StringIO()
    step.next_(sdir, out=out)
    _, ticks, end = parse_stream(sdir / "stream.jsonl")
    assert [t["i"] for t in ticks] == [0, 1]
    assert "ended=true" in out.getvalue()

    # past the last tick: end line is revealed exactly once
    out = StringIO()
    step.next_(sdir, out=out)
    _, ticks, end = parse_stream(sdir / "stream.jsonl")
    assert end is not None
    assert "STATUS end" in out.getvalue()

    # idempotent: another next stays at end, doesn't duplicate the end line
    step.next_(sdir, out=StringIO())
    text = (sdir / "stream.jsonl").read_text()
    assert text.count('"type": "end"') == 1


def test_status_does_not_reveal(tmp_path, monkeypatch):
    _install_fake_provider(monkeypatch)
    sdir = tmp_path / "sess"
    step.start(sdir, seed=1, out=StringIO())
    out = StringIO()
    step.status(sdir, out=out)
    # status reports progress but never appends a bar to the visible stream
    _, ticks, _ = parse_stream(sdir / "stream.jsonl")
    assert ticks == []
    assert "cursor=0" in out.getvalue()


def test_start_refuses_to_reseal_started_session(tmp_path, monkeypatch):
    """A re-run of `step start` on a started, UNREVEALED session is a no-op (harmless
    restart-recovery for an agent that lost $SDIR); --force re-seals it. But once a bar has
    been revealed, re-sealing is forbidden even with --force — reveal→reset→re-trade is
    look-ahead."""
    _install_fake_provider(monkeypatch)
    sdir = tmp_path / "sess"
    step.start(sdir, seed=1, out=StringIO())

    # started but nothing revealed yet (cursor == 0): a plain re-run is a no-op…
    out = StringIO()
    assert step.start(sdir, seed=1, out=out) == 0
    assert "already-started" in out.getvalue()
    # …and --force is permitted (a fresh restart is harmless before any reveal)
    assert step.start(sdir, seed=1, force=True, out=StringIO()) == 0

    # reveal bar 0, then BOTH a plain re-run AND --force must be refused (progress kept)
    step.next_(sdir, out=StringIO())
    _, ticks, _ = parse_stream(sdir / "stream.jsonl")
    assert [t["i"] for t in ticks] == [0]
    for forced in (False, True):
        out = StringIO()
        assert step.start(sdir, seed=1, force=forced, out=out) == 0
        assert "already-started" in out.getvalue()
        _, ticks, _ = parse_stream(sdir / "stream.jsonl")
        assert [t["i"] for t in ticks] == [0]    # never reset to meta-only
