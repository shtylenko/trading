"""Tests for the batch backtest harness — set building, pinned stamping, and audit."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from trading.llm_trader import batchsim, recorder, skillmeta


def _make_entries_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE entries (setup_id INTEGER, ticker TEXT, date TEXT, time_et TEXT, "
        "pattern TEXT, entry_px REAL, bar_close REAL, gap_pct REAL, rvol REAL, "
        "float_shares REAL, bar_vol_mult REAL, reason TEXT, updated_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO entries (ticker,date,time_et,pattern,float_shares,gap_pct) "
        "VALUES (?,?,?,?,?,?)", rows,
    )
    conn.commit()
    conn.close()


def _rows():
    # a mix of early/late and low/mid float across many tickers/dates
    out = []
    for i in range(40):
        tod = "09:35" if i % 2 else "11:20"
        flt = 2e6 if i % 3 else 9e6
        out.append((f"TK{i:02d}", f"2025-01-{(i % 27) + 1:02d}", tod, "acd_orb", flt, 20.0))
    return out


def test_build_set_deterministic_and_deduped(tmp_path):
    db = tmp_path / "entries.db"
    _make_entries_db(db, _rows())
    a = batchsim.build_set(n=15, db=db, seed=7)
    b = batchsim.build_set(n=15, db=db, seed=7)
    assert [(s["ticker"], s["date"]) for s in a] == [(s["ticker"], s["date"]) for s in b]
    # unique (ticker, date)
    keys = [(s["ticker"], s["date"]) for s in a]
    assert len(keys) == len(set(keys))
    assert 0 < len(a) <= 15


def test_build_set_different_seed_differs(tmp_path):
    db = tmp_path / "entries.db"
    _make_entries_db(db, _rows())
    a = {(s["ticker"], s["date"]) for s in batchsim.build_set(n=15, db=db, seed=1)}
    b = {(s["ticker"], s["date"]) for s in batchsim.build_set(n=15, db=db, seed=2)}
    assert a != b


def _fake_session(root, tag, sid="20250102000000-TK-abc123", ticker="TK",
                  date="2025-01-02", void=None):
    d = root / sid
    d.mkdir(parents=True, exist_ok=True)
    sess = {"id": sid, "status": "complete", "ticker": ticker,
            "historical_date": date, "batch": tag, "skill": {"version": "9.9.9"}}
    if void:
        sess["void"] = void
    (d / "session.json").write_text(json.dumps(sess))
    (d / "pnl.json").write_text(json.dumps(
        {"traded": True, "win": True, "realized_pnl": 10.0, "r_multiple": 0.25,
         "skill_version": "9.9.9", "batch": tag}))
    return d


# --- the false-positive fix: scan only executed commands, never prose ---

def test_parse_export_extracts_only_tool_call_commands():
    # prose that QUOTES the rules (names _sealed.jsonl) must be ignored; only the
    # tool-call arguments (actual commands) are returned.
    export = json.dumps({"messages": [
        {"role": "assistant",
         "content": "I will NOT open _sealed.jsonl or re-run step start.",
         "tool_calls": [{"function": {"name": "bash",
                                      "arguments": '{"cmd": "python3 -m trading.llm_trader.step next"}'}}]},
    ]})
    cmds = batchsim._parse_export(export)
    assert "step next" in cmds
    assert "_sealed.jsonl" not in cmds       # prose excluded → no false positive


def test_scan_commands_flags_real_peek_but_not_prose():
    assert batchsim._scan_commands('{"cmd": "cat _sealed.jsonl"}') is not None
    assert batchsim._scan_commands('{"cmd": "python3 -m trading.llm_trader.replay"}') is not None
    assert batchsim._scan_commands("step start\nstep start") is not None       # ran twice
    assert batchsim._scan_commands("step next\nrecorder log\nfinalize") is None  # clean


def _audit_with_commands(tmp_path, monkeypatch, tag, commands):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    sid = "20250102000000-TK-abc123"
    d = _fake_session(tmp_path, tag, sid=sid)
    # stub the hermes-export correlation with a canned command map for this sid
    monkeypatch.setattr(batchsim, "_resolve_batch_commands", lambda sids: {sid: commands})
    return d


def test_audit_voids_peeking_commands(tmp_path, monkeypatch):
    d = _audit_with_commands(tmp_path, monkeypatch, "b1", '{"cmd":"cat _sealed.jsonl"}')
    assert batchsim.audit("b1") == 1
    assert "_sealed.jsonl" in json.loads((d / "session.json").read_text())["void"]


def test_audit_voids_unverifiable(tmp_path, monkeypatch):
    d = _audit_with_commands(tmp_path, monkeypatch, "b2", None)  # no command log
    assert batchsim.audit("b2") == 1
    assert "unverifiable" in json.loads((d / "session.json").read_text())["void"]


def test_audit_passes_clean_commands(tmp_path, monkeypatch):
    d = _audit_with_commands(tmp_path, monkeypatch, "b3",
                             "step start\nstep next\nrecorder log\nfinalize")
    assert batchsim.audit("b3") == 0
    assert "void" not in json.loads((d / "session.json").read_text())
    rows = recorder.report_by_version(batch="b3")
    assert rows and rows[0]["n"] == 1 and rows[0]["n_void"] == 0


def test_resolve_batch_commands_matches_session_by_sid(monkeypatch):
    # two runs; each hermes session's export contains that run's unique SDIR
    sid_a, sid_b = "20250101090000-AAA-111111", "20250101090100-BBB-222222"
    exports = {
        "20250101_090005_aaa": json.dumps({"messages": [
            {"role": "tool", "content": f"session {sid_a} finalized"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal",
             "arguments": '{"command": "step next"}'}}]}]}),
        "20250101_090105_bbb": json.dumps({"messages": [
            {"role": "tool", "content": f"session {sid_b} finalized"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal",
             "arguments": '{"command": "cat _sealed.jsonl"}'}}]}]}),
    }
    monkeypatch.setattr(batchsim, "_recent_session_ids", lambda limit: list(exports))
    monkeypatch.setattr(batchsim, "_export_session", lambda hid: exports.get(hid))
    got = batchsim._resolve_batch_commands([sid_a, sid_b])
    assert "step next" in got[sid_a]
    assert batchsim._scan_commands(got[sid_a]) is None          # clean
    assert batchsim._scan_commands(got[sid_b]) is not None      # peeked


def test_resolve_batch_commands_unfound_is_none(monkeypatch):
    monkeypatch.setattr(batchsim, "_recent_session_ids", lambda limit: [])
    got = batchsim._resolve_batch_commands(["20250101090000-AAA-111111"])
    assert got["20250101090000-AAA-111111"] is None            # → audited as unverifiable


def test_extract_sid_prefers_anchor_over_stray_path():
    # a stray/earlier path must NOT win over the anchored final marker
    out = ("... init printed /x/simulations/20250101090000-OLD-000000 ...\n"
           "finalized ok\n"
           "BATCHSIM_SID=/x/simulations/20250102153000-BQ-9f3a1c\n")
    assert batchsim._extract_sid(out) == "20250102153000-BQ-9f3a1c"


def test_extract_sid_falls_back_to_bare_id():
    out = "no anchor here, just /x/simulations/20250102153000-BQ-9f3a1c/pnl.json"
    assert batchsim._extract_sid(out) == "20250102153000-BQ-9f3a1c"


def test_parse_export_handles_content_array_tool_use():
    # a schema where tool calls live in a content array (not top-level tool_calls)
    export = json.dumps({"messages": [
        {"role": "assistant", "content": [
            {"type": "text", "text": "I will not read _sealed.jsonl"},
            {"type": "tool_use", "name": "bash",
             "input": {"cmd": "python3 -m trading.llm_trader.step next"}},
        ]},
    ]})
    cmds = batchsim._parse_export(export)
    assert "step next" in cmds and "_sealed.jsonl" not in cmds


def test_parse_export_returns_none_when_no_tool_calls():
    # prose-only session (schema mismatch or truly no commands) → unverifiable, not clean
    export = json.dumps({"messages": [{"role": "assistant", "content": "just talking"}]})
    assert batchsim._parse_export(export) is None


def test_report_capture_averages_wins_only(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag = "capbatch"

    def _sess(sid, win, cap, realized):
        d = tmp_path / sid
        d.mkdir()
        (d / "session.json").write_text(json.dumps(
            {"id": sid, "status": "complete", "batch": tag, "skill": {"version": "1.0.0"}}))
        (d / "pnl.json").write_text(json.dumps(
            {"traded": True, "win": win, "realized_pnl": realized, "r_multiple": realized / 40,
             "mfe_capture": cap, "skill_version": "1.0.0", "batch": tag}))

    _sess("s1-TK-aaaaaa", True, 0.80, 40.0)     # winner
    _sess("s2-TK-bbbbbb", False, -1.50, -20.0)  # loser with negative capture
    rows = recorder.report_by_version(batch=tag)
    assert rows[0]["avg_capture"] == 0.80       # loser's -1.5 excluded


def test_run_rejects_testset_missing_time(tmp_path):
    import pytest
    ts = tmp_path / "ts.json"
    ts.write_text(json.dumps({"setups": [{"ticker": "TK", "date": "2025-01-02", "time_et": None}]}))
    with pytest.raises(ValueError, match="time_et"):
        batchsim.run("2.0.2", model="m", testset=ts, dry_run=True)


def test_void_stats_counts_unverifiable(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag = "vs"
    _fake_session(tmp_path, tag, sid="a-TK-111111", void="no agent command log (unverifiable)")
    _fake_session(tmp_path, tag, sid="b-TK-222222")   # clean
    assert batchsim._void_stats(tag) == (2, 1)


def test_resume_excludes_voided(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag = "b5"
    _fake_session(tmp_path, tag, sid="s1-TK-aaa111", void="unverifiable")
    # a voided attempt must NOT count as done, so resume will re-run this slot
    counts = batchsim._completed_counts(tag)
    assert counts.get(("TK", "2025-01-02"), 0) == 0


def test_at_time_pins_exact_setup(tmp_path):
    from trading.llm_trader import replay
    db = tmp_path / "entries.db"
    _make_entries_db(db, [
        ("DUP", "2025-05-01", "09:35", "acd_orb", 3e6, 20.0),
        ("DUP", "2025-05-01", "10:40", "acd_orb", 3e6, 20.0),
    ])
    # both rows share (ticker,date); --time disambiguates to exactly one
    from datetime import time as dtime
    s = replay.pick_setup(db, ticker="DUP", after=dtime(9, 30), at_time="10:40")
    assert s.time_et == "10:40"
    # a time with no matching row raises rather than silently picking another
    import pytest
    with pytest.raises(SystemExit):
        replay.pick_setup(db, ticker="DUP", after=dtime(9, 30), at_time="07:00")


def test_pin_version_is_read_only(tmp_path, monkeypatch):
    """init --pin-version stamps the version without touching the registry/archive."""
    archived = skillmeta.archive_dir_for(skillmeta.DEFAULT_SKILL_PATH) / "TRADE_SIMULATOR@2.0.1.md"
    before = skillmeta.REGISTRY_PATH.read_text()
    sdir = recorder.init("BQ", "2026-01-13", root=tmp_path, skill=archived,
                         pin_version="2.0.1", batch="t",
                         now=datetime(2026, 7, 5, 10, 0, 0))
    s = json.loads((sdir / "session.json").read_text())
    assert s["skill"]["version"] == "2.0.1"
    assert s["batch"] == "t"
    assert skillmeta.REGISTRY_PATH.read_text() == before  # registry untouched
