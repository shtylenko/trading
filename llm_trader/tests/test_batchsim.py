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


def _fake_session(root, tag, ticker="TK", date="2025-01-02", void=None):
    d = root / f"20250102-{ticker}"
    d.mkdir(parents=True, exist_ok=True)
    sess = {"id": d.name, "status": "complete", "ticker": ticker,
            "historical_date": date, "batch": tag, "skill": {"version": "9.9.9"}}
    if void:
        sess["void"] = void
    (d / "session.json").write_text(json.dumps(sess))
    (d / "pnl.json").write_text(json.dumps(
        {"traded": True, "win": True, "realized_pnl": 10.0, "r_multiple": 0.25,
         "skill_version": "9.9.9", "batch": tag}))
    return d


def _transcript(root, tag, ticker, date, text):
    log_dir = root / "_batch" / tag
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{ticker}_{date}_r0.log").write_text(text)


def test_audit_voids_peeking_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "b1"
    d = _fake_session(tmp_path, tag)
    _transcript(tmp_path, tag, "TK", "2025-01-02",
                "ran step next ... then cat _sealed.jsonl to peek\n")
    assert batchsim.audit(tag) == 1
    sess = json.loads((d / "session.json").read_text())
    assert "_sealed.jsonl" in sess["void"]


def test_audit_voids_missing_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "b2"
    d = _fake_session(tmp_path, tag)
    assert batchsim.audit(tag) == 1  # no transcript → unverifiable → void
    sess = json.loads((d / "session.json").read_text())
    assert "unverifiable" in sess["void"]


def test_audit_passes_clean_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "b3"
    d = _fake_session(tmp_path, tag)
    _transcript(tmp_path, tag, "TK", "2025-01-02",
                "recorder init ... step start ... step next ... recorder log ... finalize\n")
    assert batchsim.audit(tag) == 0
    sess = json.loads((d / "session.json").read_text())
    assert "void" not in sess
    # and the clean session is counted in the batch report
    rows = recorder.report_by_version(batch=tag)
    assert rows and rows[0]["n"] == 1 and rows[0]["n_void"] == 0


def test_audit_flags_double_step_start(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    monkeypatch.setattr(batchsim, "BATCH_LOGS", tmp_path / "_batch")
    tag = "b4"
    _fake_session(tmp_path, tag)
    _transcript(tmp_path, tag, "TK", "2025-01-02",
                "step start ...\n(some retry)\nstep start ... again\n")
    assert batchsim.audit(tag) == 1


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
