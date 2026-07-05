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


def test_resolve_first_sighting_records_then_matches(tmp_path):
    p = _write_skill(tmp_path)
    reg = skillmeta.registry_for(p)
    # first sighting: recorded, no note, version unchanged
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "1.4.2" and note is None
    assert "1.4.2" in json.loads(reg.read_text())
    # same content, same version: still a no-op
    meta2, note2 = skillmeta.resolve_version(p, reg)
    assert meta2["version"] == "1.4.2" and note2 is None


def test_resolve_autobumps_on_changed_content(tmp_path):
    p = _write_skill(tmp_path)
    reg = skillmeta.registry_for(p)
    skillmeta.resolve_version(p, reg)  # record 1.4.2

    # change a RULE (hash changes) but leave version:1.4.2 in the file
    p.write_text(_SKILL.replace("rules go here", "different rules"))
    meta, note = skillmeta.resolve_version(p, reg)

    assert meta["version"] == "1.4.3"          # auto-bumped patch
    assert note and "auto-bumped" in note
    # the bump was persisted into the skill file itself
    assert skillmeta.read_skill_meta(p)["version"] == "1.4.3"
    # registry records the POST-write hash (so it round-trips)
    r = json.loads(reg.read_text())
    assert r["1.4.3"]["content_hash"] == skillmeta.read_skill_meta(p)["content_hash"]
    assert r["1.4.3"]["bumped_from"] == "1.4.2"


def test_resolve_autobump_terminates(tmp_path):
    """The run right after an auto-bump must NOT bump again (hash round-trips)."""
    p = _write_skill(tmp_path)
    reg = skillmeta.registry_for(p)
    skillmeta.resolve_version(p, reg)
    p.write_text(_SKILL.replace("rules go here", "different rules"))
    skillmeta.resolve_version(p, reg)                      # 1.4.2 → 1.4.3
    meta, note = skillmeta.resolve_version(p, reg)         # should be a no-op
    assert meta["version"] == "1.4.3" and note is None


def test_resolve_creates_version_when_missing(tmp_path):
    p = _write_skill(tmp_path, "---\nname: x\n---\nbody\n")
    reg = skillmeta.registry_for(p)
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "0.0.1"
    assert note and "created" in note
    assert "version: 0.0.1" in p.read_text()


def test_resolve_hand_set_bump_is_first_sighting(tmp_path):
    p = _write_skill(tmp_path)
    reg = skillmeta.registry_for(p)
    skillmeta.resolve_version(p, reg)  # record 1.4.2
    # a human sets a semantic minor bump AND changes a rule
    p.write_text(_SKILL.replace("version: 1.4.2", "version: 1.5.0")
                       .replace("rules go here", "new rules"))
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "1.5.0" and note is None      # honoured as-is, no bump
    assert "1.5.0" in json.loads(reg.read_text())


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
