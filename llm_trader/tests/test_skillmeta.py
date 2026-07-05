"""Tests for skill versioning — reader, hash, drift detection, and the
recorder's version stamping + per-version report."""

from __future__ import annotations

import json
from datetime import datetime

from trading.llm_trader import recorder, skillmeta

_SKILL = """---
name: trade-simulator
version: 1.4.2
description: a test skill
---

# body
rules go here
"""


def _write_skill(tmp_path, text=_SKILL):
    p = tmp_path / "SKILL.md"
    p.write_text(text)
    return p


def test_read_skill_meta_parses_version_and_hashes(tmp_path):
    p = _write_skill(tmp_path)
    m = skillmeta.read_skill_meta(p)
    assert m["name"] == "trade-simulator"
    assert m["version"] == "1.4.2"
    assert m["content_hash"].startswith("sha256:")
    # hash is stable for identical bytes, changes when content changes
    assert skillmeta.read_skill_meta(p)["content_hash"] == m["content_hash"]
    p.write_text(_SKILL + "\nextra line\n")
    assert skillmeta.read_skill_meta(p)["content_hash"] != m["content_hash"]


def test_versionless_skill_reads_as_none(tmp_path):
    p = _write_skill(tmp_path, "---\nname: x\n---\nbody\n")
    assert skillmeta.read_skill_meta(p)["version"] is None


def test_drift_first_seen_records_then_matches(tmp_path):
    reg = tmp_path / "registry.json"
    meta = skillmeta.read_skill_meta(_write_skill(tmp_path))
    # first sighting: recorded, no warning
    assert skillmeta.check_drift(meta, reg) is None
    assert "1.4.2" in json.loads(reg.read_text())
    # same content, same version: still no warning
    assert skillmeta.check_drift(meta, reg) is None


def test_drift_same_version_changed_content_warns(tmp_path):
    reg = tmp_path / "registry.json"
    meta = skillmeta.read_skill_meta(_write_skill(tmp_path))
    skillmeta.check_drift(meta, reg)  # record 1.4.2
    drifted = dict(meta, content_hash="sha256:ffffffff")
    w = skillmeta.check_drift(drifted, reg)
    assert w is not None and "1.4.2" in w
    # registry is NOT overwritten, so the nag persists
    assert json.loads(reg.read_text())["1.4.2"]["content_hash"] == meta["content_hash"]
    assert skillmeta.check_drift(drifted, reg) is not None


def test_versionless_skill_warns(tmp_path):
    reg = tmp_path / "registry.json"
    meta = {"name": "x", "version": None, "content_hash": "sha256:1", "path": "x"}
    assert skillmeta.check_drift(meta, reg) is not None


def test_init_stamps_skill_block(tmp_path):
    p = _write_skill(tmp_path)
    sdir = recorder.init("TEST", "2025-03-10", seed=1, root=tmp_path, skill=p,
                         mode="live", now=datetime(2026, 6, 30, 18, 23, 10))
    s = json.loads((sdir / "session.json").read_text())
    assert s["skill"]["version"] == "1.4.2"
    assert s["skill"]["content_hash"].startswith("sha256:")
    assert s["mode"] == "live"


def test_report_by_version_groups_and_buckets_unversioned(tmp_path):
    # two finalized sessions under different versions + one unversioned
    def _mk(ver, realized, win):
        sdir = tmp_path / f"s-{ver}-{realized}"
        sdir.mkdir()
        (sdir / "session.json").write_text(json.dumps(
            {"status": "complete", "mode": "simulated",
             "skill": {"version": ver}}))
        (sdir / "pnl.json").write_text(json.dumps(
            {"traded": True, "win": win, "realized_pnl": realized,
             "r_multiple": realized / 40.0, "skill_version": ver,
             "skill_hash": "sha256:aaaa"}))

    _mk("2.0.0", 40.0, True)
    _mk("2.0.0", -20.0, False)
    _mk(None, 10.0, True)

    # point SIM_ROOT at tmp so report scans our fixtures
    orig = recorder.SIM_ROOT
    try:
        recorder.SIM_ROOT = tmp_path
        out = {r["version"]: r for r in recorder.report_by_version()}
    finally:
        recorder.SIM_ROOT = orig

    assert out["2.0.0"]["n"] == 2
    assert out["2.0.0"]["win_pct"] == 50
    assert out["2.0.0"]["pnl"] == 20.0
    assert out["unversioned"]["n"] == 1
