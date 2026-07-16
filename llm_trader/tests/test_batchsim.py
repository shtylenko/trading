"""Tests for the batch backtest harness — set building, pinned stamping, and audit."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

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


def test_build_set_exclude_carves_disjoint_holdout(tmp_path):
    db = tmp_path / "entries.db"
    _make_entries_db(db, _rows())
    dev = batchsim.build_set(n=100, db=db, seed=7)
    dev_keys = {(s["ticker"], s["date"]) for s in dev}
    holdout = batchsim.build_set(n=100, db=db, seed=7, exclude=dev_keys)
    hold_keys = {(s["ticker"], s["date"]) for s in holdout}
    # holdout shares no key with the excluded dev set
    assert dev_keys.isdisjoint(hold_keys)


def test_build_set_causal_only_excludes_legacy_cup_labels(tmp_path):
    db = tmp_path / "entries.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE entries (ticker TEXT, date TEXT, time_et TEXT, pattern TEXT, "
        "features_json TEXT, entry_px REAL, gap_pct REAL, rvol REAL, "
        "float_shares REAL, reason TEXT)"
    )
    complete_plan = {
        "signal_kind": "prebreak_arm", "signal_as_of": "2025-02-03",
        "entry_trigger": 11.0, "stop_px": 9.0, "target1_px": 12.0,
        "target2_px": 13.0, "atr": 1.0, "cup_depth_px": 3.0,
        "arm_expiry_bars": 5, "max_entry_gap_atr": 0.5,
    }
    conn.executemany(
        "INSERT INTO entries (ticker,date,time_et,pattern,features_json) VALUES (?,?,?,?,?)",
        [
            ("CAUSAL", "2025-02-03", "16:00", "cup_handle", json.dumps(complete_plan)),
            ("STALE", "2025-02-04", "09:30", "cup_handle", "{}"),
        ],
    )
    conn.commit()
    conn.close()

    setups = batchsim.build_set(n=10, db=db, causal_only=True)
    assert [(s["ticker"], s["date"], s["time_et"]) for s in setups] == [
        ("CAUSAL", "2025-02-03", "16:00"),
    ]


def test_causal_batch_preflight_rejects_a_stale_exact_setup(tmp_path):
    db = tmp_path / "entries.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE entries (ticker TEXT, date TEXT, time_et TEXT, pattern TEXT, "
        "strategy TEXT, features_json TEXT, entry_px REAL, gap_pct REAL, rvol REAL, "
        "float_shares REAL, reason TEXT)"
    )
    conn.execute(
        "INSERT INTO entries (ticker,date,time_et,pattern,strategy,features_json) "
        "VALUES (?,?,?,?,?,?)",
        ("STALE", "2025-02-04", "09:30", "cup_handle", "cup_handle", "{}"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="incompatible with the causal cup-handle skill"):
        batchsim._validate_causal_testset(
            [{"ticker": "STALE", "date": "2025-02-04", "time_et": "09:30"}],
            db=db, strategy_id="cup_handle",
        )


def test_load_keys_reads_setups_and_top_level_list(tmp_path):
    p = tmp_path / "ts.json"
    p.write_text(json.dumps({"setups": [
        {"ticker": "AAA", "date": "2025-01-02"},
        {"ticker": "BBB", "date": "2025-03-04"},
    ]}))
    assert batchsim._load_keys(p) == {("AAA", "2025-01-02"), ("BBB", "2025-03-04")}
    p2 = tmp_path / "ts2.json"
    p2.write_text(json.dumps([{"ticker": "CCC", "date": "2025-05-06"}]))
    assert batchsim._load_keys(p2) == {("CCC", "2025-05-06")}


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
    (d / "decisions.jsonl").write_text('{"i": 0, "action": "OBSERVE"}\n')
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
    # a plain re-run of step start is a harmless no-op (step.start guards it) — NOT a void
    assert batchsim._scan_commands("step start\nstep start") is None
    assert batchsim._scan_commands("step next\nrecorder log\nfinalize") is None  # clean


def test_parse_export_ignores_planning_tool_mentions():
    # the agent's todo/planning tool quotes the plan ("run step start", "don't read
    # _sealed.jsonl"). Scanning it was a LIVE false-positive void — must be ignored;
    # only the real terminal command counts.
    export = json.dumps({"messages": [
        {"role": "assistant", "tool_calls": [
            {"function": {"name": "todos", "arguments": json.dumps({"todos": [
                {"id": "1", "content": "run step start to seal the day"},
                {"id": "2", "content": "never open _sealed.jsonl"}]})}},
            {"function": {"name": "terminal",
                          "arguments": '{"command": "python3 -m trading.llm_trader.step start --session X"}'}},
        ]},
    ]})
    cmds = batchsim._parse_export(export)
    assert cmds.count("step start") == 1          # only the real command, not the todo
    assert "_sealed.jsonl" not in cmds            # planning mention excluded
    assert batchsim._scan_commands(cmds) is None  # not voided


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


def test_audit_voids_daily_indicator_integrity_before_transcript_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    d = _fake_session(tmp_path, "bad-daily")
    session_path = d / "session.json"
    session = json.loads(session_path.read_text())
    session.update({"strategy": "cup_handle", "config": {
        "horizon": "multi_day", "bar_resolution": "1day",
    }})
    session_path.write_text(json.dumps(session))
    (d / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"type": "meta", "ticker": "TK", "date": "2025-01-02",
         "horizon": "multi_day", "bar_resolution": "1day"},
        {"type": "tick", "i": 0, "date": "2025-01-02", "time": "16:00",
         "sma20": 10.0, "sma50": 10.0, "sma200": None, "atr14": 1.0,
         "rvol": 1.0, "above_sma20": True, "above_sma50": True,
         "above_sma200": None, "sma50_rising": True},
    ]) + "\n")
    calls = []
    monkeypatch.setattr(batchsim, "_resolve_batch_commands", lambda sids: calls.append(sids) or {})

    assert batchsim.audit("bad-daily") == 1
    assert calls == []
    assert "data-integrity" in json.loads(session_path.read_text())["void"]


def test_audit_voids_causal_session_missing_scanner_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    d = _fake_session(tmp_path, "stale-causal")
    session_path = d / "session.json"
    session = json.loads(session_path.read_text())
    session.update({
        "strategy": "cup_handle",
        "config": {"horizon": "multi_day", "bar_resolution": "1day"},
        "skill": {"arm_on_scanner_plan_required": "true"},
    })
    session_path.write_text(json.dumps(session))
    daily = {
        "sma20": 10.0, "sma50": 10.0, "sma200": 10.0, "atr14": 1.0,
        "rvol": 1.0, "above_sma20": True, "above_sma50": True,
        "above_sma200": True, "sma50_rising": True,
    }
    (d / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"type": "meta", "ticker": "TK", "date": "2025-01-02",
         "horizon": "multi_day", "bar_resolution": "1day"},
        {"type": "tick", "i": 0, "date": "2025-01-02", "time": "16:00",
         "is_setup_day": True, **daily},
    ]) + "\n")
    assert recorder.stream_integrity_errors(d, session)
    assert batchsim._sessions_for_batch("stale-causal") == [d]
    monkeypatch.setattr(
        batchsim, "_resolve_batch_commands",
        lambda _sids: (_ for _ in ()).throw(AssertionError("must not inspect transcripts")),
    )

    assert batchsim.audit("stale-causal") == 1
    assert "causal scanner_plan is missing" in json.loads(session_path.read_text())["void"]


def test_sessions_for_batch_includes_manifest_orphans(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "partial-manifest"
    listed = _fake_session(tmp_path, tag, sid="listed")
    orphan = _fake_session(tmp_path, tag, sid="orphan")
    manifest = tmp_path / "_batch" / tag / "manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"sid": listed.name}) + "\n")

    assert {p.name for p in batchsim._sessions_for_batch(tag)} == {listed.name, orphan.name}


# --- out-of-credits: an infra failure (HTTP 402), NOT a look-ahead void ---

def test_text_out_of_credits_detector():
    assert batchsim._text_out_of_credits("HTTP 402: Insufficient Balance")
    assert batchsim._text_out_of_credits("...\nInsufficient balance\n")
    assert batchsim._text_out_of_credits("error: insufficient credits")
    assert not batchsim._text_out_of_credits("step next\nrecorder log\nOBSERVE")
    assert not batchsim._text_out_of_credits("")
    assert not batchsim._text_out_of_credits(None)


def test_audit_marks_out_of_credits_not_void(tmp_path, monkeypatch):
    # No command log (agent never ran), BUT its captured log shows HTTP 402 → the run
    # is tagged out_of_credits and excluded from stats, not voided as unverifiable.
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag, sid, name = "b4", "20250102000000-TK-abc123", "batchsim-b4-TK-2025-01-02-r0"
    d = _fake_session(tmp_path, tag, sid=sid)
    logdir = tmp_path / "_batch" / tag
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / f"{name}.log").write_text("[exit 0]\n===== STDOUT =====\nHTTP 402: Insufficient Balance\n")
    (logdir / "manifest.jsonl").write_text(
        json.dumps({"sid": sid, "session_name": name, "status": "out-of-credits"}) + "\n")
    monkeypatch.setattr(batchsim, "_resolve_batch_commands", lambda sids: {sid: None})

    assert batchsim.audit(tag) == 0  # not counted as a void
    s = json.loads((d / "session.json").read_text())
    assert s.get("out_of_credits")   # tagged
    assert not s.get("void")         # and NOT voided

    # excluded from metrics: n_out_of_credits surfaced, run not in n_planned/n_traded
    view = recorder.get_top_session_view(tag)  # leaves group under the batch tag
    assert view["metrics"]["n_out_of_credits"] == 1
    assert view["metrics"]["n_planned"] == 0
    assert view["tickers"][0]["status"] == "out_of_credits"


def test_run_one_stamps_out_of_credits(tmp_path, monkeypatch):
    # _run_one detects the 402 in agent output and stamps the session out_of_credits.
    sdir = tmp_path / "20250102000000-TK-abc123"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps(
        {"id": sdir.name, "status": "complete", "ticker": "TK",
         "historical_date": "2025-01-02", "void": "stale-should-be-cleared"}))
    monkeypatch.setattr(recorder, "finalize", lambda p: None)
    batchsim._stamp_out_of_credits(sdir)
    s = json.loads((sdir / "session.json").read_text())
    assert s["out_of_credits"] and "void" not in s


def test_stamp_timeout(tmp_path, monkeypatch):
    # _stamp_timeout marks the session timed_out and clears any stale void.
    sdir = tmp_path / "20250102000000-TK-abc123"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps(
        {"id": sdir.name, "status": "complete", "ticker": "TK",
         "historical_date": "2025-01-02", "void": "stale-should-be-cleared"}))
    batchsim._stamp_timeout(sdir)
    s = json.loads((sdir / "session.json").read_text())
    assert s["timed_out"] and "void" not in s


def test_empty_intent_log_is_infra_failure_and_rerunnable(tmp_path, monkeypatch):
    # An empty decisions.jsonl is never a valid stand-down: the model/harness made
    # no decision at all. Audit backfills the stamp, reporting excludes the leaf,
    # and --resume sees the slot as unfinished.
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "no-intent"
    d = _fake_session(tmp_path, tag)
    (d / "decisions.jsonl").write_text("")
    monkeypatch.setattr(batchsim, "_resolve_batch_commands", lambda sids: {d.name: "step next"})

    assert batchsim.audit(tag) == 0
    session = json.loads((d / "session.json").read_text())
    assert session["no_decision_log"]
    assert "void" not in session
    assert batchsim._completed_counts(tag) == {}
    assert batchsim._effective_r({
        "void": False, "ooc": False, "timeout": False, "finalize_error": False,
        "no_decision_log": True, "status": "complete", "traded": False, "r": None,
    }) is None

    view = recorder.get_top_session_view(tag)
    assert view["metrics"]["n_no_decision_log"] == 1
    assert view["metrics"]["n_planned"] == 0
    assert view["tickers"][0]["status"] == "no_decision_log"


def test_agent_abandoned_armed_run_is_infra_failure_and_rerunnable(tmp_path, monkeypatch):
    """ARM then stop logging before exit fill → agent_abandoned (BNY v0.2.0 pilot)."""
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "abandon-arm"
    d = _fake_session(tmp_path, tag)
    # Agent armed at i=1, last log i=2; engine later filled and stopped without more logs.
    (d / "decisions.jsonl").write_text(
        json.dumps({"i": 0, "action": "OBSERVE"}) + "\n"
        + json.dumps({"i": 1, "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0}) + "\n"
        + json.dumps({"i": 2, "action": "OBSERVE"}) + "\n"
    )
    (d / "actions.json").write_text(json.dumps([
        {"i": 5, "side": "buy", "price": 10.1, "shares": 10},
        {"i": 8, "side": "sell", "price": 9.0, "shares": 10},
    ]))
    reason = batchsim._agent_abandoned_stream(d)
    assert reason and "before exit bar i=8" in reason
    batchsim._stamp_agent_abandoned(d, reason)
    session = json.loads((d / "session.json").read_text())
    assert session["agent_abandoned"]
    assert batchsim._completed_counts(tag) == {}
    assert batchsim._effective_r({
        "void": False, "ooc": False, "timeout": False, "finalize_error": False,
        "no_decision_log": False, "agent_abandoned": True,
        "status": "complete", "traded": True, "r": -1.0,
    }) is None

    # STAND_DOWN as last action is a clean early stop, not abandoned.
    d2 = _fake_session(tmp_path, tag + "2", sid="20250102000000-TK-stand")
    (d2 / "decisions.jsonl").write_text(
        json.dumps({"i": 0, "action": "OBSERVE"}) + "\n"
        + json.dumps({"i": 3, "action": "STAND_DOWN"}) + "\n"
    )
    (d2 / "actions.json").write_text("[]")
    assert batchsim._agent_abandoned_stream(d2) is None

    view = recorder.get_top_session_view(tag)
    assert view["metrics"]["n_agent_abandoned"] == 1
    assert view["metrics"]["n_planned"] == 0
    assert view["tickers"][0]["status"] == "agent_abandoned"


def test_timed_out_excluded_from_stats_and_rerun(tmp_path, monkeypatch):
    # A timed-out run must NOT be a clean "complete": excluded from metrics, shown as a
    # timeout, and re-run by --resume (never counted as done).
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "bt"
    d = _fake_session(tmp_path, tag, sid="20250102000000-TK-abc123")
    # stamp it timed_out (as _run_one would after exhausting retries)
    batchsim._stamp_timeout(d)

    # excluded from metrics: surfaced as n_timed_out, not counted as planned/traded
    view = recorder.get_top_session_view(tag)
    assert view["metrics"]["n_timed_out"] == 1
    assert view["metrics"]["n_planned"] == 0
    assert view["metrics"]["n_traded"] == 0
    assert view["tickers"][0]["status"] == "timeout"

    # resume must re-run it: a timed-out leaf does NOT count as a completed slot
    assert batchsim._completed_counts(tag) == {}


def test_stamp_finalize_error(tmp_path, monkeypatch):
    # _stamp_finalize_error marks the session broken (status="error", not "running")
    # and clears any stale void — finalize() never wrote session.json itself since it
    # raised, so this is the only place the leaf's terminal state gets recorded.
    sdir = tmp_path / "20250102000000-TK-abc123"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps(
        {"id": sdir.name, "status": "running", "ticker": "TK",
         "historical_date": "2025-01-02", "void": "stale-should-be-cleared"}))
    batchsim._stamp_finalize_error(sdir, "turn i=2: selling 114 but only 0 held")
    s = json.loads((sdir / "session.json").read_text())
    assert s["status"] == "error"
    assert "selling 114" in s["finalize_error"]
    assert "void" not in s


def test_finalize_error_excluded_from_stats_and_rerun(tmp_path, monkeypatch):
    # A finalize-error run must NOT be a clean "complete": excluded from metrics,
    # shown distinctly, and re-run by --resume (never counted as done) — same
    # treatment as timeout/out-of-credits, not an orphaned "running" leaf forever.
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "bt"
    d = _fake_session(tmp_path, tag, sid="20250102000000-TK-abc123")
    batchsim._stamp_finalize_error(d, "turn i=2: selling 114 but only 0 held")

    view = recorder.get_top_session_view(tag)
    assert view["tickers"][0]["status"] == "finalize_error"
    assert view["tickers"][0]["n_finalize_error"] == 1
    assert view["metrics"]["n_planned"] == 0
    assert view["metrics"]["n_traded"] == 0

    # resume must re-run it: a finalize-error leaf does NOT count as a completed slot
    assert batchsim._completed_counts(tag) == {}


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


def test_resolve_batch_commands_ignores_report_output_contamination(monkeypatch):
    """A later run that prints another leaf's SDIR in `recorder report` OUTPUT must not
    have its own commands attributed to that leaf. The owner is bound by its setup-block
    marker (CAPTURED_SDIR/BATCHSIM_SID) even when its commands only use $SDIR (never the
    literal) — so the compliant clean leaf is not falsely voided by the dirty mentioner."""
    sid_clean = "20250101090000-AQMS-111111"   # a clean, protocol-compliant run ($SDIR only)
    sid_dirty = "20250101093000-EVTV-222222"   # re-ran step start AND printed AQMS's path via report
    exports = {
        # AQMS owner: bound by CAPTURED_SDIR marker (echo output); commands use $SDIR, no literal
        "20250101_090005_aaa": json.dumps({"messages": [
            {"role": "tool", "content": f"CAPTURED_SDIR=/x/simulations/{sid_clean}"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal",
             "arguments": json.dumps({"command": 'python3 -m trading.llm_trader.step next --session "$SDIR"'})}}]},
            {"role": "assistant", "content": f"BATCHSIM_SID=/x/simulations/{sid_clean}"}]}),
        # EVTV run: force-re-sealed AFTER revealing bars (real look-ahead) AND its OUTPUT
        # prints AQMS's SDIR via a bare report path
        "20250101_093005_bbb": json.dumps({"messages": [
            {"role": "tool", "content": f"CAPTURED_SDIR=/x/simulations/{sid_dirty}"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal",
             "arguments": json.dumps({"command": f'python3 -m trading.llm_trader.step next --session {sid_dirty}'})}}]},
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal",
             "arguments": json.dumps({"command": f'python3 -m trading.llm_trader.step start --force --session {sid_dirty}'})}}]},
            {"role": "tool", "content": f"report listing ... {sid_clean} ... {sid_dirty} ..."}]}),
    }
    monkeypatch.setattr(batchsim, "_recent_session_ids", lambda limit: list(exports))
    monkeypatch.setattr(batchsim, "_export_session", lambda hid: exports.get(hid))
    got = batchsim._resolve_batch_commands([sid_clean, sid_dirty])
    # clean leaf resolves to its OWN commands (only `step next`) via the marker — NOT the
    # dirty session's commands pulled in through the report-output mention
    assert "step next" in got[sid_clean]
    assert "--force" not in got[sid_clean]
    assert batchsim._scan_commands(got[sid_clean]) is None
    # dirty leaf still resolves to its own commands and is correctly flagged
    assert batchsim._scan_commands(got[sid_dirty]) == "agent force-re-sealed after revealing bars (look-ahead)"


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


def test_resume_excludes_out_of_credits(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag = "b6"
    d = _fake_session(tmp_path, tag, sid="s1-TK-aaa111")
    s = json.loads((d / "session.json").read_text())
    s["out_of_credits"] = "out of credits (HTTP 402)"
    (d / "session.json").write_text(json.dumps(s))
    # an out-of-credits run never traded — it must NOT count as done, so --resume re-runs it
    assert batchsim._completed_counts(tag).get(("TK", "2025-01-02"), 0) == 0


def test_existing_session_id_recovers_top_level_for_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag = "b7"
    d = _fake_session(tmp_path, tag, sid="20250102000000-TK-aaa111")
    # tag the leaf with its top-level session id (what recorder.init stores)
    s = json.loads((d / "session.json").read_text())
    s["session"] = "20250102000000-BATCH-deadbe"
    (d / "session.json").write_text(json.dumps(s))
    # --resume must rejoin this exact top-level session, not fork a new one
    assert batchsim._existing_session_id(tag) == "20250102000000-BATCH-deadbe"
    assert batchsim._existing_session_id("no-such-tag") is None
    # and the reverse: `--resume --session <id>` (no --tag) recovers the tag from it
    assert batchsim._tag_for_session("20250102000000-BATCH-deadbe") == tag
    assert batchsim._tag_for_session("no-such-session") is None


def test_resume_recovers_config_from_batch_json(tmp_path, monkeypatch):
    # `--resume --session <id>` with NO version/model/set: all recovered from batch.json.
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "9.9.9-20250102"
    d = _fake_session(tmp_path, tag, sid="20250102000000-TK-aaa111")
    s = json.loads((d / "session.json").read_text())
    s["session"] = "20250102000000-BATCH-deadbe"
    (d / "session.json").write_text(json.dumps(s))
    ts = tmp_path / "myset.json"
    ts.write_text(json.dumps({"setups": [
        {"ticker": "TK", "date": "2025-01-02", "time_et": "09:35"}]}))
    batchsim._write_batch_meta(tag, version="9.9.9", model="rec-model",
                               testset=str(ts), repeats=1)
    # skill file for the recovered version must exist for run() to load it
    dummy_skill = tmp_path / "dummy_skill.md"
    dummy_skill.write_text("---\nname: x\nversion: 9.9.9\n---\nbody\n")
    monkeypatch.setattr(
        batchsim, "_archived_skill", lambda v, strategy_id="warrior": dummy_skill
    )
    dummy_hash = skillmeta.read_skill_meta(dummy_skill)["content_hash"]
    batchsim._write_batch_meta(
        tag,
        testset_hash=batchsim._file_hash(ts),
        skill_hash=dummy_hash,
        runner_contract=batchsim.runner_contract(),
    )

    # resume by session alone → recovers version/model/testset; dry-run so no agents spawn
    out = batchsim.run(resume=True, session="20250102000000-BATCH-deadbe", dry_run=True)
    assert out == tag  # rejoined the right batch


def test_resolve_testset_path_bare_name_under_strategy():
    p = batchsim.resolve_testset_path("testset_30", "cup_handle")
    assert p.is_file()
    assert p.parent.name == "cup_handle"
    assert p.name == "testset_30.json"
    # with or without .json
    p2 = batchsim.resolve_testset_path("testset_30.json", "cup_handle")
    assert p2 == p
    # default when None
    # warrior default exists as testset.json
    w = batchsim.resolve_testset_path(None, "warrior")
    assert w.name == "testset.json" and w.parent.name == "warrior"


def test_run_defaults_model_when_omitted(monkeypatch):
    # a fresh (non-resume) run uses DEFAULT_MODEL when --model is omitted
    assert batchsim.DEFAULT_MODEL == "deepseek-v4-flash"
    seen = {}

    def _fake_run_one(work):
        seen["model"] = work["model"]
        return {"item": work["item"], "status": "dry-run", "cmd": [], "sid": None}

    monkeypatch.setattr(batchsim, "_run_one", _fake_run_one)
    # dry-run path builds work items and calls _run_one without hermes
    batchsim.run(
        "2.0.2",
        model=None,
        testset=batchsim.TESTSET_DEFAULT,
        dry_run=True,
        parallel=1,
        repeats=1,
    )
    assert seen.get("model") == "deepseek-v4-flash"


def test_scan_commands_denylist_allows_benign_shell():
    """DENYLIST model: the audit voids only concrete look-ahead / determinism breaks. The
    benign shell agents actually run — cd, env-load, viewer kill, journal heredoc writes,
    literal-path trading commands, `python3 -c` step loops — must NOT void a run."""
    benign = "\n".join([
        'cd /Users/shtylenko/Projects && set -a && . trading/.env && set +a && python3 -c "import trading.llm_trader" && echo OK',
        'lsof -nP -tiTCP:8765 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null; sleep 1; echo killed',
        'pkill -f "trading.llm_trader.viewer" 2>/dev/null',
        'cd /Users/shtylenko/Projects && python3 -m trading.llm_trader.step next --session "/x/sim/20260706-KITT-abc"',
        'for i in $(seq 1 20); do python3 -m trading.llm_trader.step next --session "$SDIR"; done',
        "cat >> /x/sim/20260706-KITT-abc/journal.md << 'END'\nnice runner, watched the tape\nEND",
        'python3 -m trading.llm_trader.recorder finalize --session "/x/sim/20260706-KITT-abc"',
    ])
    assert batchsim._scan_commands(benign) is None
    # naming a private file in an EXISTENCE check (the setup block's leak-hygiene step) is
    # benign — only reading its content is a peek
    assert batchsim._scan_commands("ls -la /x/sim/s/_sealed.jsonl /x/sim/s/_step.json 2>&1") is None
    assert batchsim._scan_commands('test -f "$SDIR/_sealed.jsonl" && echo present') is None
    # a plain re-run of step start (guarded no-op), and a --force re-seal BEFORE any reveal,
    # are both harmless restarts — not look-ahead
    assert batchsim._scan_commands("step start\nstep start") is None
    assert batchsim._scan_commands("step start --force\nstep next\nstep next") is None


def test_scan_commands_denylist_still_voids_lookahead():
    """The concrete look-ahead / determinism vectors still void, however they're wrapped."""
    assert batchsim._scan_commands("cd /x && cat /x/_sealed.jsonl") \
        == "agent read forbidden `_sealed.jsonl`"
    assert batchsim._scan_commands('grep foo a/_step.json') == "agent read forbidden `_step.json`"
    assert batchsim._scan_commands("while read l; do :; done < /x/_sealed.jsonl") is not None
    # reconstructing bars from the raw data layer / cache is look-ahead
    assert batchsim._scan_commands('python3 -c "from trading.marketdata import bars"') is not None
    assert batchsim._scan_commands("cat /x/marketdata/data/AAPL.parquet") is not None
    assert batchsim._scan_commands("sqlite3 /x/entries.db 'select *'") is not None
    # re-seal AFTER revealing bars (reveal → reset → re-trade) and direct replay still void
    assert batchsim._scan_commands("step next\nstep next\nstep start --force") \
        == "agent force-re-sealed after revealing bars (look-ahead)"
    assert batchsim._scan_commands("python3 -m trading.llm_trader.replay AAPL") is not None


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
    """init --pin-version stamps the version without touching the registry."""
    archived = skillmeta.skill_path_for("2.0.1")
    before = skillmeta.DEFAULT_REGISTRY_PATH.read_text()
    sdir = recorder.init("BQ", "2026-01-13", root=tmp_path, skill=archived,
                         pin_version="2.0.1", batch="t",
                         now=datetime(2026, 7, 5, 10, 0, 0))
    s = json.loads((sdir / "session.json").read_text())
    assert s["skill"]["version"] == "2.0.1"
    assert s["batch"] == "t"
    assert skillmeta.DEFAULT_REGISTRY_PATH.read_text() == before  # registry untouched


def test_agent_env_sandboxes_marketdata(tmp_path, monkeypatch):
    """The env handed to the agent strips provider creds, redirects the marketdata cache
    to a fresh empty dir, and disables the provider chain — so `replay`/`fetch` can't
    reach the day's data. `step next`/`recorder log` don't need any of it."""
    monkeypatch.setenv("ALPACA_API_KEY_ID", "secret")
    monkeypatch.setenv("MARKETDATA_TOKEN", "secret")
    monkeypatch.setenv("STRATEGY_LAB_MARKETDATA_DIR", "/real/cache")
    cache = tmp_path / "nomd"
    env = batchsim._agent_env(cache)
    assert "ALPACA_API_KEY_ID" not in env and "MARKETDATA_TOKEN" not in env
    # cache redirected to our empty dir, NOT the real one (which would hold the future)
    assert env["STRATEGY_LAB_MARKETDATA_DIR"] == str(cache)
    assert env["STOCKMARKETDATA_DIR"] == str(cache)
    assert cache.is_dir()
    # a sentinel that matches no real provider — an empty string would mean "all"
    assert env["MARKETDATA_PROVIDERS"] and env["MARKETDATA_PROVIDERS"] != ""
    assert env["MARKETDATA_PROVIDERS"] not in ("alpaca", "marketdata", "yfinance")


def test_macos_sandbox_blocks_shared_simulation_tree_but_allows_staged_session(tmp_path, monkeypatch):
    sandbox = batchsim._sandbox_executable()
    if sandbox is None:
        pytest.skip("sandbox-exec is unavailable on this platform")

    durable = tmp_path / "durable-simulations"
    durable.mkdir()
    secret = durable / "future.jsonl"
    secret.write_text("future\n")
    staged = tmp_path / "staged" / "session"
    staged.mkdir(parents=True)
    visible = staged / "stream.jsonl"
    visible.write_text("revealed\n")
    monkeypatch.setattr(recorder, "SIM_ROOT", durable)
    profile = batchsim._write_agent_sandbox(tmp_path, staged)

    blocked = subprocess.run(
        [sandbox, "-f", str(profile), "/bin/cat", str(secret)],
        capture_output=True, text=True,
    )
    allowed = subprocess.run(
        [sandbox, "-f", str(profile), "/bin/cat", str(visible)],
        capture_output=True, text=True, check=True,
    )
    assert blocked.stdout == ""
    assert blocked.returncode != 0
    assert allowed.stdout == "revealed\n"


def test_promote_staged_session_moves_only_after_harness_finalization(tmp_path, monkeypatch):
    durable = tmp_path / "simulations"
    staged_root = tmp_path / "staging"
    staged = staged_root / "20260710120000-TEST-abcdef"
    staged.mkdir(parents=True)
    (staged / "session.json").write_text("{}")
    monkeypatch.setattr(recorder, "SIM_ROOT", durable)

    promoted = batchsim._promote_staged_session(staged)

    assert promoted == durable / staged.name
    assert (promoted / "session.json").exists()
    assert not staged.exists()


def test_prompt_is_preseal_step_next_only():
    """The agent prompt hands over an already-started literal SDIR and confines the
    agent to the step-next/log loop — no init/start/finalize, no data layer, fail-closed."""
    sdir = "/x/simulations/20260101120000-BQ-abc123"
    p = batchsim._prompt("2.0.5", "SKILL-TEXT", "tag", "SESSION-ID",
                         "BQ", "2026-01-01", "09:35", sdir)
    assert sdir in p                                          # literal path inlined
    # the agent is never told to RUN these (they appear only in the prohibition list,
    # as backticked prose — not as `python3 -m …` invocations it should execute)
    assert "trading.llm_trader.recorder init" not in p        # no setup
    assert "trading.llm_trader.step start" not in p           # no sealing
    assert "trading.llm_trader.recorder finalize" not in p    # harness finalizes
    assert "trading.llm_trader.step next" in p                # the one data command
    assert "fail closed" in p.lower()                         # explicit fail-closed rule
    assert f"BATCHSIM_SID={sdir}" in p                        # audit anchor marker


def test_prompt_uses_resolve_and_intents_for_deterministic_skill():
    sdir = "/x/simulations/20260101120000-BQ-abc123"
    p = batchsim._prompt("3.0.0", "SKILL-TEXT", "tag", "SESSION-ID",
                         "BQ", "2026-01-01", "09:35", sdir,
                         execution_model="deterministic_ohlc_v1")
    assert "trading.llm_trader.recorder resolve" in p
    assert "ENTER_CLOSE|ARM_BUY_STOP" in p
    assert '"fill_px":null' not in p


def test_from_open_prompt_hides_scanner_time_and_prevents_flat_early_stop():
    p = batchsim._prompt("4.0.0", "SKILL-TEXT", "tag", "SESSION-ID",
                         "BQ", "2026-01-01", "10:35", "/tmp/session",
                         execution_model="deterministic_ohlc_v1", session_from_open=True,
                         horizon="intraday", bar_resolution="1min")
    assert "ticker=BQ  date=2026-01-01" in p
    assert "time=10:35" not in p
    assert "keep revealing bars through 11:00 ET" in p


def test_multi_day_prompt_does_not_use_intraday_1100_stop():
    p = batchsim._prompt(
        "0.1.0", "SKILL-TEXT", "tag", "SESSION-ID",
        "BNY", "2025-06-18", "09:30", "/tmp/session",
        execution_model="deterministic_ohlc_v1", session_from_open=True,
        horizon="multi_day", bar_resolution="1day",
    )
    assert "MULTI-DAY swing run" in p
    assert "Do NOT stop because the clock says after 11:00" in p
    assert "scanner setup date" in p
    assert "keep revealing bars through 11:00 ET" not in p
    # BNY pilot: agents delayed arm until scanner date; prompt must forbid that.
    assert "NOT a wait-to-arm clock" in p
    assert "ENTER_CLOSE" in p
    assert "do not wait for that calendar day" in p
    # BNY v0.2.0: agent armed then abandoned loop while stop still pending.
    assert "live ARM_BUY_STOP" in p or "pending buy-stop" in p
    assert "FAILED run" in p
    assert "NEVER print BATCHSIM_SID while ARMED" in p
    assert "progress report" in p


def test_continue_prompt_forbids_early_batchsim_sid():
    p = batchsim._continue_prompt(
        "BASE PROMPT BODY", "/tmp/sdir", "pending ARM_BUY_STOP", 1, 5,
    )
    assert "HARNESS CONTINUE (1/5)" in p
    assert "pending ARM_BUY_STOP" in p
    assert "Do NOT print BATCHSIM_SID until you are truly done" in p
    assert "BASE PROMPT BODY" in p


def test_skill_text_for_batch_strips_init_and_finalize():
    skill = """# skill
## ENTRY checklist
- trade
## Shell / $SDIR discipline
```bash
init here
```
## Step 0 — Init + seal
do not show
## MANAGE checklist (IN position)
- manage
## Finalize
finalize cmd
"""
    out = batchsim._skill_text_for_batch_agent(skill)
    assert "ENTRY checklist" in out
    assert "MANAGE checklist" in out
    assert "Shell / $SDIR" not in out
    assert "Step 0" not in out
    assert "Finalize" not in out
    assert "init here" not in out


def test_multi_day_prompt_is_slim_runtime_contract():
    skill = Path(__file__).resolve().parents[1] / "strategies/cup_handle/skills/trade_skills/0.4.0.md"
    if not skill.exists():
        skill = Path(__file__).resolve().parents[1] / "strategies/cup_handle/skills/trade_skills/0.3.0.md"
    text = skill.read_text()
    p = batchsim._prompt(
        "0.4.0", text, "tag", "SID", "BNY", "2025-06-18", "09:30", "/tmp/s",
        execution_model="deterministic_ohlc_v1", session_from_open=True,
        horizon="multi_day", bar_resolution="1day",
        auto_lookback={"n_auto_observe": 20, "first_llm_i": 20, "setup_i": 40},
    )
    assert "runtime contract" in p or "already live" in p or "SESSION (already set up)" in p
    assert "recorder init" in p  # must say do NOT run it
    assert "Do NOT run recorder init" in p or "Do NOT run recorder init" in p.replace("\n", " ")
    # Operator shell tutorial should not appear after slim
    assert "CAPTURED_SDIR" not in p
    assert "Early lookback bars" in p
    assert "first_llm_i" in p or "i≈20" in p or "i≈20" in p or "i=20" in p or "20" in p


def test_agent_needs_continue_when_armed_and_bars_remain(tmp_path, monkeypatch):
    """Live arm + unrevealed ticks ⇒ harness should re-invoke hermes."""
    sdir = tmp_path / "sess"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "id": "s", "status": "running", "ticker": "BNY",
        "config": {"execution_model": "deterministic_ohlc_v1",
                   "risk_budget": 500.0, "buying_power": 50000.0},
    }))
    # Revealed stream: two daily bars; agent armed on i=0, observed i=1.
    lines = [
        {"type": "meta", "ticker": "BNY", "date": "2025-06-18", "horizon": "multi_day"},
        {"type": "tick", "i": 0, "date": "2025-05-27", "time": "16:00",
         "o": 90, "h": 90.2, "l": 89, "c": 90.1, "v": 1e6},
        {"type": "tick", "i": 1, "date": "2025-05-28", "time": "16:00",
         "o": 90, "h": 90.1, "l": 88.5, "c": 88.8, "v": 1e6},
    ]
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    (sdir / "decisions.jsonl").write_text(
        json.dumps({"i": 0, "time": "16:00", "action": "ARM_BUY_STOP",
                    "trigger": 90.63, "stop": 87.94}) + "\n"
        + json.dumps({"i": 1, "time": "16:00", "action": "OBSERVE"}) + "\n"
    )

    class _GW:
        def remaining_ticks(self):
            return 10  # sealed hold still ahead

    reason = batchsim._agent_needs_continue(sdir, _GW(), multi_day=True)
    assert reason and "ARM_BUY_STOP" in reason

    # STAND_DOWN ends continue even with bars left.
    (sdir / "decisions.jsonl").write_text(
        json.dumps({"i": 0, "action": "OBSERVE"}) + "\n"
        + json.dumps({"i": 1, "action": "STAND_DOWN"}) + "\n"
    )
    assert batchsim._agent_needs_continue(sdir, _GW(), multi_day=True) is None

    # No remaining ticks → no continue.
    class _Done:
        def remaining_ticks(self):
            return 0
    (sdir / "decisions.jsonl").write_text(
        json.dumps({"i": 0, "action": "ARM_BUY_STOP", "trigger": 90.63, "stop": 87.9}) + "\n"
    )
    assert batchsim._agent_needs_continue(sdir, _Done(), multi_day=True) is None


def test_auto_observe_multi_day_lookback_logs_early_bars(tmp_path):
    """Harness should OBSERVE deep lookback and leave setup-near bars for the LLM."""
    from trading.llm_trader.step import IsolatedStreamGateway

    sdir = tmp_path / "auto"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "id": "s", "status": "running", "ticker": "BNY", "strategy": "cup_handle",
        "config": {
            "execution_model": "deterministic_ohlc_v1",
            "risk_budget": 500.0, "buying_power": 50000.0,
            "horizon": "multi_day", "bar_resolution": "1day",
        },
        "skill": {"execution_model": "deterministic_ohlc_v1"},
    }))
    (sdir / "decisions.jsonl").write_text("")
    records = [{"type": "meta", "ticker": "BNY", "date": "2025-06-18",
                "plan_lookback_bars": 40, "horizon": "multi_day"}]
    # 5 lookback + setup at i=5 + 2 hold
    for i in range(8):
        day = f"2025-05-{20+i:02d}" if i < 5 else (
            "2025-06-18" if i == 5 else f"2025-06-{19+i-5:02d}")
        records.append({
            "type": "tick", "i": i, "date": day if i != 5 else "2025-06-18",
            "time": "16:00", "o": 90, "h": 91, "l": 89, "c": 90.5, "v": 1e6,
            "sma20": 89.5, "sma50": 88.0, "sma200": 80.0, "atr14": 1.2,
            "rvol": 1.1, "above_sma20": True, "above_sma50": True,
            "above_sma200": True, "sma50_rising": True,
            **({"is_setup_day": True} if i == 5 else {}),
        })
    records.append({"type": "end", "bars": 8, "close": 90.5})
    gw = IsolatedStreamGateway(sdir, records).start()
    try:
        info = batchsim._auto_observe_multi_day_lookback(
            sdir, gw, "2025-06-18", llm_lookback=2,
        )
        # setup_i=5, first_llm_i=3 → auto i=0,1,2
        assert info["setup_i"] == 5
        assert info["first_llm_i"] == 3
        assert info["n_auto_observe"] == 3
        assert gw.revealed_tick_count() == 3
        raw = [json.loads(l) for l in (sdir / "decisions.jsonl").read_text().splitlines() if l.strip()]
        assert len(raw) == 3
        assert all(d["action"] == "OBSERVE" for d in raw)
        assert [d["i"] for d in raw] == [0, 1, 2]
    finally:
        gw.close()


def test_prompt_reentry_budget_and_cutoff():
    """The §C re-entry budget + optional cutoff time drive the flat-stop rule (condition b)."""
    args = ("3.4.0", "SKILL-TEXT", "tag", "SESSION-ID", "BQ", "2026-01-01", "09:35", "/tmp/s")
    # default: budget 1, no cutoff — classic single re-entry, no time bound
    p1 = batchsim._prompt(*args, max_reentries=1)
    assert "BUDGET of 1" in p1
    assert "ET has passed" not in p1        # no cutoff clause
    # raised budget + cutoff: both bounds present, and it must NOT stop while flat with budget left
    p3 = batchsim._prompt(*args, max_reentries=3, trade_until="11:30")
    assert "BUDGET of 3" in p3
    assert "11:30 ET" in p3
    assert "do NOT stop" in p3
    # disabled: budget 0 means flat = done immediately
    p0 = batchsim._prompt(*args, max_reentries=0)
    assert "RE-ENTRY IS DISABLED" in p0
    assert "budget 0" in p0


# --- compare: the paired promotion gate ---

def test_sign_test_p_two_sided():
    # 42 up / 20 down (the real 2.4.0 vs 2.2.1 result) → p ≈ 0.007
    assert batchsim._sign_test_p(42, 20) == pytest.approx(0.0071, abs=5e-4)
    # symmetric split → not significant
    assert batchsim._sign_test_p(10, 10) > 0.5
    assert batchsim._sign_test_p(0, 0) is None


def test_effective_r_stood_down_is_zero_void_excluded():
    assert batchsim._effective_r({"void": False, "ooc": False, "timeout": False,
                                  "finalize_error": False,
                                  "status": "complete", "traded": True, "r": 1.5}) == 1.5
    # stood-down (completed, not traded) contributes 0R, not exclusion
    assert batchsim._effective_r({"void": False, "ooc": False, "timeout": False,
                                  "finalize_error": False,
                                  "status": "complete", "traded": False, "r": None}) == 0.0
    # void / out-of-credits / timed-out / finalize-error / unfinished are excluded
    assert batchsim._effective_r({"void": True, "ooc": False, "timeout": False,
                                  "finalize_error": False,
                                  "status": "complete", "traded": True, "r": 1.0}) is None
    assert batchsim._effective_r({"void": False, "ooc": True, "timeout": False,
                                  "finalize_error": False,
                                  "status": "complete", "traded": False, "r": None}) is None
    assert batchsim._effective_r({"void": False, "ooc": False, "timeout": True,
                                  "finalize_error": False,
                                  "status": "complete", "traded": True, "r": 1.0}) is None
    assert batchsim._effective_r({"void": False, "ooc": False, "timeout": False,
                                  "finalize_error": True,
                                  "status": "error", "traded": True, "r": 1.0}) is None


def test_compare_pairs_and_verdicts(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")

    contract = {
        "harness_version": "test-v1",
        "prompt_hash": "sha256:prompt",
        "harness_hash": "sha256:harness",
    }

    def mk(tag, ticker, date, r, sid, traded=True):
        skill_hash = f"sha256:{tag}-skill"
        d = tmp_path / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "session.json").write_text(json.dumps(
            {"id": sid, "status": "complete", "ticker": ticker,
             "historical_date": date, "batch": tag, "real_run_ts": sid,
             "config": {"execution_model": "reported_fill_v1"},
             "skill": {"content_hash": skill_hash},
             "runner_contract": contract}))
        (d / "pnl.json").write_text(json.dumps(
            {"traded": traded, "win": (r or 0) > 0, "realized_pnl": (r or 0) * 40,
             "r_multiple": r, "skill_hash": skill_hash}))

    # baseline A all 0R; candidate B all +1R on the same 3 setups → B clearly better
    for i, (tk, dt) in enumerate([("AA", "2025-01-01"), ("BB", "2025-01-02"), ("CC", "2025-01-03")]):
        mk("baseA", tk, dt, 0.0, f"a{i}-{tk}-x", traded=True)
        mk("candB", tk, dt, 1.0, f"b{i}-{tk}-x", traded=True)
    for tag in ("baseA", "candB"):
        batchsim._write_batch_meta(
            tag, model="test-model", testset_hash="sha256:testset",
            skill_hash=f"sha256:{tag}-skill", runner_contract=contract, reentry=False,
        )
    r = batchsim.compare("baseA", "candB")
    assert r["n_pairs"] == 3
    assert r["mean_dR"] == pytest.approx(1.0)
    assert r["better"] == 3 and r["worse"] == 0


def test_compare_refuses_runner_contract_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")

    def mk(tag, contract):
        d = tmp_path / f"{tag}-run"
        d.mkdir()
        (d / "session.json").write_text(json.dumps({
            "status": "complete", "ticker": "AA", "historical_date": "2025-01-01",
            "batch": tag, "config": {"execution_model": "deterministic_ohlc_v1", "execution": {}},
            "skill": {"content_hash": "sha256:skill"}, "runner_contract": contract,
        }))
        (d / "pnl.json").write_text(json.dumps({
            "traded": True, "win": True, "realized_pnl": 40.0, "r_multiple": 1.0,
            "execution_model": "deterministic_ohlc_v1", "skill_hash": "sha256:skill",
        }))
        batchsim._write_batch_meta(
            tag, model="test-model", testset_hash="sha256:testset", skill_hash="sha256:skill",
            runner_contract=contract, reentry=False,
        )

    base = {"harness_version": "v1", "prompt_hash": "sha256:a", "harness_hash": "sha256:b"}
    changed = {**base, "prompt_hash": "sha256:changed"}
    mk("base", base)
    mk("changed", changed)
    with pytest.raises(ValueError, match="runner contract"):
        batchsim.compare("base", "changed")


def test_compare_refuses_execution_model_rebaseline(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    for tag, model in (("legacy", "reported_fill_v1"), ("v3", "deterministic_ohlc_v1")):
        d = tmp_path / f"{tag}-run"
        d.mkdir()
        (d / "session.json").write_text(json.dumps({
            "status": "complete", "ticker": "AA", "historical_date": "2025-01-01",
            "batch": tag, "config": {"execution_model": model},
        }))
        (d / "pnl.json").write_text(json.dumps({
            "traded": True, "win": True, "realized_pnl": 40.0,
            "r_multiple": 1.0, "execution_model": model,
        }))
    with pytest.raises(ValueError, match="major rebaseline"):
        batchsim.compare("legacy", "v3")


def test_repeat_panels_average_runs_and_allow_candidate_skill_change(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    contract = {"harness_version": "v1", "prompt_hash": "sha256:p", "harness_hash": "sha256:h"}

    def write_batch(tag, skill_hash, rs):
        for i, r in enumerate(rs):
            ticker = f"T{i}"
            d = tmp_path / f"{tag}-{ticker}"
            d.mkdir()
            (d / "session.json").write_text(json.dumps({
                "status": "complete", "ticker": ticker, "historical_date": f"2025-01-0{i + 1}",
                "batch": tag, "real_run_ts": f"{tag}-{i}",
                "config": {"execution_model": "reported_fill_v1"},
                "skill": {"content_hash": skill_hash}, "runner_contract": contract,
            }))
            (d / "pnl.json").write_text(json.dumps({
                "traded": True, "win": r > 0, "realized_pnl": r * 40,
                "r_multiple": r, "skill_hash": skill_hash,
            }))
        batchsim._write_batch_meta(
            tag, model="test-model", testset_hash="sha256:set", skill_hash=skill_hash,
            runner_contract=contract, reentry=False,
        )

    write_batch("base1", "sha256:base", [0.0, 1.0])
    write_batch("base2", "sha256:base", [0.2, 1.2])
    write_batch("cand1", "sha256:candidate", [1.0, 2.0])
    write_batch("cand2", "sha256:candidate", [1.2, 2.2])

    panel = batchsim.repeat_panel(["base1", "base2"])
    assert panel["pnl"]["mean"] == pytest.approx(48.0)
    assert panel["effective_r"]["mean"] == pytest.approx(0.6)

    result = batchsim.compare_repeats(["base1", "base2"], ["cand1", "cand2"])
    assert result["n_pairs"] == 2
    assert result["mean_dR"] == pytest.approx(1.0)
    assert result["better"] == 2


def test_diagnostics_reports_grade_order_behavior_and_in_position_mfe(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    tag, sdir = "diagnostic", tmp_path / "run"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "status": "complete", "ticker": "TEST", "historical_date": "2025-01-02",
        "batch": tag, "real_run_ts": "2026-07-11T10:00:00",
        "setup": {"entry_px": 5.0, "rvol": 6.0, "float_shares": 1_000_000,
                  "gap_pct": 20.0, "entry_time": "09:35"},
    }))
    (sdir / "pnl.json").write_text(json.dumps({
        "traded": True, "win": True, "realized_pnl": 20.0, "r_multiple": 0.5,
    }))
    (sdir / "actions.json").write_text(json.dumps([
        {"i": 0, "action": "ENTER", "side": "buy", "price": 10.0, "position_after": 100,
         "reason": "close-confirmed entry"},
        {"i": 1, "action": "ADD", "side": "buy", "price": 11.0, "position_after": 150,
         "reason": "close-confirmed pyramid"},
        {"i": 2, "action": "EXIT", "side": "sell", "price": 9.0, "position_after": 0,
         "reason": "protective stop (gap-aware)"},
    ]))
    (sdir / "decisions.jsonl").write_text(json.dumps({"action": "ADD_CLOSE"}) + "\n")
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"type": "tick", "i": 0, "h": 10.5},
        {"type": "tick", "i": 1, "h": 12.0},
        # Final protective-stop bar is excluded from MFE under stop-first OHLC.
        {"type": "tick", "i": 2, "h": 20.0},
    ]) + "\n")

    result = batchsim.diagnostics(tag)
    assert result["by_grade"]["A"]["effective_r"] == pytest.approx(0.5)
    assert result["by_entry"]["confirmed close"]["trades"] == 1
    assert result["by_exit"]["protective stop"]["trades"] == 1
    assert result["adds"] == {"attempted": 1, "filled": 1}
    assert result["in_position_mfe_per_share"]["mean"] == pytest.approx(2.0)
