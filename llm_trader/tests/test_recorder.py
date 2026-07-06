"""Tests for the session recorder — the deterministic P&L/position engine."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from trading.llm_trader import recorder


def _stream(path, ticks, end_close):
    lines = [{"type": "meta", "ticker": "TEST", "date": "2025-03-10",
              "entry_time": "10:20", "entry_px": 3.97, "anchor_px": 3.97,
              "gap_pct": 32.0, "rvol": 4.7, "float_shares": 12e6,
              "pm_high": 3.97, "pm_low": 2.9, "prior_close": 2.5,
              "session_end": "16:00", "reason": "demo"}]
    for i, (hm, o, h, l, c, v) in enumerate(ticks):
        lines.append({"type": "tick", "i": i, "time": hm, "o": o, "h": h,
                      "l": l, "c": c, "v": v, "vwap": l, "ema9": c,
                      "session_high": h, "new_high": True, "rvol_bar": 2.0})
    lines.append({"type": "end", "bars": len(ticks), "close": end_close})
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def _session(tmp_path, ticks, end_close=3.5, decisions=()):
    sdir = recorder.init("TEST", "2025-03-10", seed=1, profile="small",
                         root=tmp_path, now=datetime(2026, 6, 30, 18, 23, 10))
    _stream(sdir / "stream.jsonl", ticks, end_close)
    # Write decisions.jsonl directly (not via recorder.log) so engine-validation
    # cases can hand-build malformed sequences — e.g. two fills at the same bar i
    # — that log()'s strict-ordering guard would (correctly) reject at write time.
    with open(sdir / "decisions.jsonl", "w") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")
    return sdir


def test_init_creates_folder_and_manifest(tmp_path):
    sdir = recorder.init("EVTV", "2026-01-13", seed=7, root=tmp_path,
                         now=datetime(2026, 6, 30, 18, 23, 10))
    # id is {ts}-{ticker}-{random}; the random suffix makes it collision-proof
    assert sdir.name.startswith("20260630182310-EVTV-")
    s = json.loads((sdir / "session.json").read_text())
    assert s["status"] == "running"
    assert s["config"]["risk_budget"] == 40.0
    assert (sdir / "decisions.jsonl").exists()


def test_init_ids_are_unique_for_same_ticker_and_time(tmp_path):
    """Two runs with the SAME ticker + wall-clock second must not collide (batch parallelism)."""
    now = datetime(2026, 6, 30, 18, 23, 10)
    a = recorder.init("EVTV", "2026-01-13", root=tmp_path, now=now)
    b = recorder.init("EVTV", "2026-01-13", root=tmp_path, now=now)
    assert a.name != b.name and a != b


def test_mfe_capture_uses_peak_size_not_initial_tranche(tmp_path):
    """A trade that ADDs near the high and sells all at the high = full capture (~1.0),
    not >1 — the denominator must scale on peak size, not the first tranche."""
    ticks = [("10:20", 5.0, 5.05, 4.95, 5.00, 9000),
             ("10:21", 5.0, 5.42, 5.00, 5.40, 9000),
             ("10:22", 5.4, 5.45, 5.40, 5.45, 9000)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 5.00, "shares_delta": 100, "stop": 4.80},
        {"i": 1, "time": "10:21", "action": "ADD", "fill_px": 5.40, "shares_delta": 100, "stop": 4.80},
        {"i": 2, "time": "10:22", "action": "EXIT", "fill_px": 5.45, "shares_delta": -200, "stop": 4.80},
    ]
    sdir = _session(tmp_path, ticks, end_close=5.45, decisions=decisions)
    recorder.finalize(sdir, full_day=False)
    pnl = json.loads((sdir / "pnl.json").read_text())
    assert pnl["entry_shares"] == 100 and pnl["max_shares"] == 200
    # blended entry 5.20, peak high 5.45, peak size 200 → best-case $50, realized $50
    assert pnl["realized_pnl"] == 50.0
    assert pnl["mfe_capture"] == 1.0     # would be >1 if scaled on the 100-share entry


def test_log_rejects_bad_action(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path)
    with pytest.raises(ValueError):
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "YOLO"})


def test_log_rejects_duplicate_or_out_of_order_i(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path)
    recorder.log(sdir, {"i": 0, "time": "10:20", "action": "OBSERVE", "thought": "a"})
    recorder.log(sdir, {"i": 1, "time": "10:21", "action": "OBSERVE", "thought": "b"})
    # re-logging the same bar (a retried turn) must be rejected
    with pytest.raises(ValueError, match="not ahead"):
        recorder.log(sdir, {"i": 1, "time": "10:21", "action": "OBSERVE", "thought": "dup"})
    # going backwards must be rejected too
    with pytest.raises(ValueError, match="not ahead"):
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "OBSERVE", "thought": "back"})


def test_log_rejects_after_finalize(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100)]
    sdir = _session(tmp_path, ticks, decisions=[
        {"i": 0, "time": "10:20", "action": "STAND_DOWN", "thought": "pass"},
    ])
    recorder.finalize(sdir)
    with pytest.raises(ValueError, match="finalized"):
        recorder.log(sdir, {"i": 1, "time": "10:21", "action": "OBSERVE", "thought": "late"})


def test_enter_scale_exit_pnl(tmp_path):
    ticks = [
        ("10:20", 3.6, 3.8, 3.5, 3.75, 100),   # i0 entry bar
        ("10:21", 3.75, 3.9, 3.7, 3.85, 90),   # i1
        ("10:23", 3.85, 3.99, 3.8, 3.96, 80),  # i2 scale
        ("10:27", 3.9, 3.95, 3.6, 3.66, 70),   # i3 exit
    ]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 300, "stop": 3.60, "thought": "in"},
        {"i": 2, "time": "10:23", "action": "SCALE", "fill_px": 3.90, "shares_delta": -150, "stop": 3.75, "thought": "half off"},
        {"i": 3, "time": "10:27", "action": "EXIT", "fill_px": 3.66, "shares_delta": -150, "stop": 3.75, "thought": "out"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    sess = recorder.finalize(sdir)

    pnl = json.loads((sdir / "pnl.json").read_text())
    # 150*(3.90-3.75) + 150*(3.66-3.75) = 22.5 - 13.5 = 9.0
    assert pnl["realized_pnl"] == pytest.approx(9.0)
    assert pnl["r_multiple"] == pytest.approx(9.0 / 40.0, abs=0.01)
    assert pnl["win"] is True
    assert pnl["forced_exit"] is False
    # MFE vs entry 3.75: session high 3.99 -> 0.24/sh
    assert pnl["mfe_per_share"] == pytest.approx(0.24, abs=1e-6)

    actions = json.loads((sdir / "actions.json").read_text())
    assert [a["side"] for a in actions] == ["buy", "sell", "sell"]
    assert actions[0]["position_after"] == 300

    bars = json.loads((sdir / "bars.json").read_text())
    assert len(bars) == 4 and "t" in bars[0] and bars[0]["vwap"] is not None

    assert sess["status"] == "complete"
    assert sess["result"]["realized_pnl"] == pytest.approx(9.0)
    assert (sdir / "journal.md").exists()


def test_blended_entry_and_actual_r(tmp_path):
    # ENTER 100@3.75 (stop 3.55 → risk 100*0.20 = $20), ADD 100@3.95, EXIT 200@4.15
    ticks = [
        ("10:20", 3.6, 3.8, 3.5, 3.75, 100),
        ("10:21", 3.75, 4.0, 3.7, 3.95, 90),
        ("10:22", 3.95, 4.2, 3.9, 4.15, 80),
    ]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 100, "stop": 3.55, "thought": "in"},
        {"i": 1, "time": "10:21", "action": "ADD", "fill_px": 3.95, "shares_delta": 100, "stop": 3.55, "thought": "add"},
        {"i": 2, "time": "10:22", "action": "EXIT", "fill_px": 4.15, "shares_delta": -200, "stop": 3.55, "thought": "out"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    recorder.finalize(sdir)
    pnl = json.loads((sdir / "pnl.json").read_text())
    # blended entry = (3.75+3.95)/2 = 3.85, not the first fill 3.75
    assert pnl["entry_avg"] == pytest.approx(3.85)
    # realized = 200*(4.15-3.85) = 60.0
    assert pnl["realized_pnl"] == pytest.approx(60.0)
    # actual R vs the $20 risked at entry = 3.0 (planned R vs $40 budget = 1.5)
    assert pnl["initial_risk"] == pytest.approx(20.0)
    assert pnl["r_multiple_actual"] == pytest.approx(3.0)
    assert pnl["r_multiple"] == pytest.approx(1.5)


def test_open_position_is_force_closed_at_end(tmp_path):
    ticks = [
        ("10:20", 3.6, 3.8, 3.5, 3.75, 100),
        ("10:21", 3.75, 3.9, 3.7, 3.85, 90),
    ]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 200, "thought": "in, forgot to exit"},
    ]
    sdir = _session(tmp_path, ticks, end_close=4.00, decisions=decisions)
    recorder.finalize(sdir)
    pnl = json.loads((sdir / "pnl.json").read_text())
    assert pnl["forced_exit"] is True
    # force-closed 200 @ 4.00 vs 3.75 entry = 50.0
    assert pnl["realized_pnl"] == pytest.approx(50.0)
    actions = json.loads((sdir / "actions.json").read_text())
    assert actions[-1]["reason"].startswith("auto-flat")


def test_oversell_raises(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 100, "thought": "in"},
        {"i": 0, "time": "10:20", "action": "EXIT", "fill_px": 3.7, "shares_delta": -200, "thought": "oversell"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    with pytest.raises(ValueError):
        recorder.finalize(sdir)


def test_enter_while_long_raises(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100), ("10:21", 3.75, 3.9, 3.7, 3.85, 90)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 100, "thought": "in"},
        {"i": 1, "time": "10:21", "action": "ENTER", "fill_px": 3.85, "shares_delta": 100, "thought": "double-enter"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    with pytest.raises(ValueError, match="ENTER while already long"):
        recorder.finalize(sdir)


def test_fill_action_without_fill_raises(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100)]
    decisions = [{"i": 0, "time": "10:20", "action": "ENTER", "thought": "forgot the fill"}]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    with pytest.raises(ValueError, match="requires fill_px"):
        recorder.finalize(sdir)


def test_wrong_sign_raises(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100), ("10:21", 3.75, 3.9, 3.7, 3.85, 90)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 100, "thought": "in"},
        {"i": 1, "time": "10:21", "action": "SCALE", "fill_px": 3.85, "shares_delta": 50, "thought": "scale but positive"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    with pytest.raises(ValueError, match="must be a sell"):
        recorder.finalize(sdir)


def test_stray_fill_on_observe_raises(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100)]
    decisions = [{"i": 0, "time": "10:20", "action": "OBSERVE", "fill_px": 3.7, "shares_delta": 100, "thought": "oops"}]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    with pytest.raises(ValueError, match="must not carry a fill"):
        recorder.finalize(sdir)


def _partial_stream(sdir, ticks):
    """Write meta + ticks with NO end line (a session still in progress)."""
    lines = [{"type": "meta", "ticker": "TEST", "date": "2025-03-10",
              "anchor_px": 3.97, "gap_pct": 32.0, "rvol": 4.7, "reason": "demo"}]
    for i, (hm, o, h, l, c, v) in enumerate(ticks):
        lines.append({"type": "tick", "i": i, "time": hm, "o": o, "h": h,
                      "l": l, "c": c, "v": v, "vwap": l, "ema9": c,
                      "session_high": h, "new_high": True, "rvol_bar": 2.0})
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")


# ── PositionEngine (extracted deterministic engine) ──────────────────────────

def test_position_engine_scale_out_math():
    e = recorder.PositionEngine()
    e.step(0, "10:20", "ENTER", 3.75, 300, 3.60, 3.75)
    assert e.shares == 300 and e.avg_entry == pytest.approx(3.75)
    e.step(3, "10:23", "SCALE", 3.90, -150, 3.75, 3.96)
    assert e.shares == 150 and e.realized == pytest.approx(150 * 0.15)
    e.step(7, "10:27", "EXIT", 3.66, -150, 3.75, 3.66)
    assert e.shares == 0
    assert e.realized_pnl == pytest.approx(9.0)


def test_position_engine_enter_while_long_raises():
    e = recorder.PositionEngine()
    e.step(0, "10:20", "ENTER", 3.75, 100, None, 3.75)
    with pytest.raises(ValueError, match="ENTER while already long"):
        e.step(1, "10:21", "ENTER", 3.80, 100, None, 3.80)


# ── get_session_view: live must reveal ONLY *processed* bars (no look-ahead) ──

def test_live_view_reveals_only_processed_bars(tmp_path):
    # The stream file may physically hold more bars than the agent has processed
    # (with `replay --delay 0` it holds the whole day). The live view must clamp
    # to the furthest bar the agent has logged a decision for — never what's merely
    # on disk. Here 3 ticks are on disk but only bars 0 and 1 have been logged.
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path)
    _partial_stream(sdir, [                      # 3 ticks on disk (i=0,1,2)
        ("10:20", 3.6, 3.8, 3.5, 3.75, 100),
        ("10:21", 3.75, 3.9, 3.7, 3.85, 90),
        ("10:22", 3.85, 3.95, 3.8, 3.90, 80),
    ])
    recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER",
                        "fill_px": 3.75, "shares_delta": 300, "stop": 3.6, "thought": "in"})
    recorder.log(sdir, {"i": 1, "time": "10:21", "action": "OBSERVE", "thought": "holding"})

    view = recorder.get_session_view(sdir)
    assert view["is_live"] is True
    assert len(view["bars"]) == 2            # clamped to processed frontier (i<=1)
    assert view["last_tick_i"] == 1          # bar i=2 is on disk but NOT shown
    assert len(view["decisions"]) == 2
    assert view["pnl"]["traded"] is True     # computed live from processed data
    assert view["pnl"]["forced_exit"] is False   # open position left open, not force-closed


def test_complete_view_reads_finalized_artifacts(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100), ("10:21", 3.75, 3.9, 3.7, 3.66, 90)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 100, "thought": "in"},
        {"i": 1, "time": "10:21", "action": "EXIT", "fill_px": 3.66, "shares_delta": -100, "thought": "out"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    recorder.finalize(sdir, full_day=False)     # clamp → no provider/network
    view = recorder.get_session_view(sdir)
    assert view["is_live"] is False
    assert view["pnl"]["realized_pnl"] == pytest.approx(-9.0)
    assert len(view["bars"]) == 2


def test_finalize_full_day_false_clamps_to_revealed(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.75, 100), ("10:21", 3.75, 3.9, 3.7, 3.85, 90),
             ("10:22", 3.85, 3.95, 3.8, 3.90, 80)]
    decisions = [{"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75,
                  "shares_delta": 100, "thought": "in"}]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    recorder.finalize(sdir, full_day=False)
    bars = json.loads((sdir / "bars.json").read_text())
    assert len(bars) == 3                        # revealed only, not the full RTH day


# ── list_sessions ────────────────────────────────────────────────────────────

def test_list_sessions_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    a = recorder.init("AAA", "2025-03-10", root=tmp_path, now=datetime(2026, 6, 30, 10, 0, 0))
    b = recorder.init("BBB", "2025-03-11", root=tmp_path, now=datetime(2026, 6, 30, 11, 0, 0))
    lst = recorder.list_sessions()
    ids = [e["id"] for e in lst]
    assert ids == [b.name, a.name]               # newest first (each ungrouped leaf is its own top session)
    # grouped list_sessions items describe aggregates (no per-leaf 'status'/'ticker' here)
    assert all(e.get("n_tickers") == 1 for e in lst)
    assert all("pnl" in e and "type" in e for e in lst)


def test_stand_down_no_trade(tmp_path):
    ticks = [("10:20", 3.6, 3.8, 3.5, 3.4, 100)]
    decisions = [
        {"i": 0, "time": "10:20", "action": "STAND_DOWN", "thought": "breakout bar red, below VWAP — pass"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    recorder.finalize(sdir)
    pnl = json.loads((sdir / "pnl.json").read_text())
    assert pnl["traded"] is False
    assert pnl["realized_pnl"] == 0.0


def test_get_session_view_and_list(tmp_path):
    ticks = [
        ("10:20", 3.6, 3.8, 3.5, 3.75, 100),
        ("10:21", 3.75, 3.9, 3.7, 3.85, 90),
    ]
    decisions = [
        {"i": 0, "time": "10:20", "action": "ENTER", "fill_px": 3.75, "shares_delta": 200, "thought": "in"},
    ]
    sdir = _session(tmp_path, ticks, decisions=decisions)
    # before finalize → should be treated as live / running. Only bar i=0 has a
    # logged decision, so the live view clamps to it (bar i=1 is on disk, unshown).
    view = recorder.get_session_view(sdir)
    assert view["is_live"] is True
    assert len(view["bars"]) == 1            # clamped to processed frontier (i<=0)
    assert view["pnl"]["traded"] is True

    # finalize it
    recorder.finalize(sdir)
    view2 = recorder.get_session_view(sdir)
    assert view2["is_live"] is False
    assert len(view2["bars"]) >= 2

    # list_sessions uses global SIM_ROOT; we just verify the function runs and returns a list
    lst = recorder.list_sessions()
    assert isinstance(lst, list)


# ───────────────────── PositionEngine direct tests (new reliability) ─────────

def test_position_engine_basic_flow():
    eng = recorder.PositionEngine()
    # ENTER
    a, t = eng.step(0, "10:00", "ENTER", 3.75, 200, 3.50, 3.80)
    assert a is not None and a["action"] == "ENTER"
    assert eng.shares == 200
    assert eng.avg_entry == pytest.approx(3.75)

    # SCALE out half
    a2, t2 = eng.step(2, "10:10", "SCALE", 3.90, -100, None, 3.95)
    assert a2["realized_delta"] == pytest.approx(15.0)
    assert eng.shares == 100
    assert eng.realized == pytest.approx(15.0)

    # EXIT rest
    a3, _ = eng.step(5, "10:20", "EXIT", 4.10, -100, None, 4.05)
    assert eng.shares == 0
    assert eng.realized == pytest.approx(15.0 + 35.0)


def test_position_engine_rejects_oversell_and_bad_actions():
    eng = recorder.PositionEngine()
    eng.step(0, "10:00", "ENTER", 5.0, 50, 4.5, 5.1)
    with pytest.raises(ValueError, match="selling .* but only"):
        eng.step(1, "10:01", "EXIT", 5.2, -100, None, 5.3)
    with pytest.raises(ValueError, match="must be a sell"):
        eng.step(2, "10:02", "SCALE", 5.1, 10, None, 5.2)


def test_mfe_and_force_close():
    eng = recorder.PositionEngine()
    eng.step(0, "10:00", "ENTER", 10.0, 100, 9.0, 10.5)
    bars = [{"i": 0, "h": 10.5}, {"i": 1, "h": 11.2}, {"i": 2, "h": 10.8}]
    mfe = eng.mfe_per_share(bars)
    assert mfe == pytest.approx(1.2)

    forced = eng.force_close_if_needed({"i": 2, "c": 10.8, "time": "10:30"}, None)
    assert forced is not None
    assert forced["action"] == "EXIT"
    assert forced["reason"].startswith("auto-flat")
    assert eng.shares == 0


def _finalized_session(root, sid, ticker, n_fills, win, realized, sess_id="grp"):
    """A minimal finalized session.json on disk (no artifacts) for list/aggregate tests."""
    d = root / sid
    d.mkdir()
    (d / "session.json").write_text(json.dumps({
        "id": sid, "status": "complete", "mode": "simulated",
        "ticker": ticker, "historical_date": "2025-03-10", "session": sess_id,
        "real_run_ts": "2026-06-30T18:23:10", "finalized_ts": "2026-06-30T18:25:00",
        "result": {"traded": True, "realized_pnl": realized, "win": win,
                   "n_fills": n_fills},
    }))
    return d


def test_win_rate_is_per_session_not_per_fill(tmp_path, monkeypatch):
    """A single winning trade with several fills must read 100%, not 1/n_fills.

    Regression for the win-rate denominator bug: win% is winning *sessions* over
    traded *sessions*, never over blotter fills."""
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    # one winner with 3 fills (ENTER+SCALE+EXIT) → 100%, not 33%
    _finalized_session(tmp_path, "a-TK-111111", "TK", n_fills=3, win=True, realized=50.0)

    top = next(s for s in recorder.list_sessions() if s["id"] == "grp")
    assert top["n_trades"] == 1          # traded sessions, not fills
    assert top["n_fills"] == 3
    assert top["win_rate"] == 100.0

    view = recorder.get_top_session_view("grp")
    row = next(t for t in view["tickers"] if t["ticker"] == "TK")
    assert row["n_trades"] == 1 and row["n_fills"] == 3 and row["win_rate"] == 100.0


def test_win_rate_counts_winning_sessions(tmp_path, monkeypatch):
    """Two runs on the same ticker, one win one loss → 50%."""
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    _finalized_session(tmp_path, "a-TK-111111", "TK", n_fills=2, win=True, realized=30.0)
    _finalized_session(tmp_path, "b-TK-222222", "TK", n_fills=4, win=False, realized=-20.0)

    view = recorder.get_top_session_view("grp")
    row = next(t for t in view["tickers"] if t["ticker"] == "TK")
    assert row["n_trades"] == 2 and row["win_rate"] == 50.0
