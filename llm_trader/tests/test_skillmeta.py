"""Tests for skill versioning — reader, hash, one-file-per-version registration/
sealing, base-version pointer, and the recorder's version stamping + per-version
report."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime

import pytest

from trading.llm_trader import recorder, skillmeta

_SKILL = """---
name: trade-simulator
version: 1.4.2
candlebar_context: true
description: a test skill
---

# body
rules go here
"""


def _write_skill(tmp_path, text=_SKILL, name="SKILL.md"):
    p = tmp_path / name
    p.write_text(text)
    return p


def _is_writable(p) -> bool:
    return bool(os.stat(p).st_mode & stat.S_IWUSR)


def test_read_skill_meta_parses_version_and_hashes(tmp_path):
    p = _write_skill(tmp_path)
    m = skillmeta.read_skill_meta(p)
    assert m["name"] == "trade-simulator"
    assert m["version"] == "1.4.2"
    assert m["candlebar_context"] == "true"
    assert m["content_hash"].startswith("sha256:")
    # hash is stable for identical bytes, changes when content changes
    assert skillmeta.read_skill_meta(p)["content_hash"] == m["content_hash"]
    p.write_text(_SKILL + "\nextra line\n")
    assert skillmeta.read_skill_meta(p)["content_hash"] != m["content_hash"]


def test_versionless_skill_reads_as_none(tmp_path):
    p = _write_skill(tmp_path, "---\nname: x\n---\nbody\n")
    assert skillmeta.read_skill_meta(p)["version"] is None


def test_resolve_first_sighting_registers_seals_and_is_idempotent(tmp_path):
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    # first sighting: registered under skills_dir/1.4.2.md, sealed; source `p`
    # untouched and still writable (only the canonical copy is immutable)
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "1.4.2" and note == "registered new version 1.4.2."
    canonical = tmp_path / "trade_skills" / "1.4.2.md"
    assert canonical.exists()
    assert not _is_writable(canonical)
    assert _is_writable(p)
    r = json.loads(reg.read_text())
    assert "1.4.2" in r["versions"]

    # same content, same version, re-resolved from the ORIGINAL (non-canonical)
    # path: still a no-op — nothing gets re-registered or re-sealed
    meta2, note2 = skillmeta.resolve_version(p, reg)
    assert meta2["version"] == "1.4.2" and note2 is None


def test_resolve_raises_when_a_registered_version_drifts(tmp_path):
    """Editing content under an ALREADY-registered version number (no version
    bump) is refused — there's no separate archive to silently bump/revert
    from anymore, so this must fail loudly instead of corrupting history."""
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    skillmeta.resolve_version(p, reg)  # registers 1.4.2

    p.write_text(_SKILL.replace("rules go here", "different rules"))  # same version!
    with pytest.raises(ValueError, match="must never be edited in place"):
        skillmeta.resolve_version(p, reg)

    # the sealed canonical copy is untouched by the failed attempt
    canonical = tmp_path / "trade_skills" / "1.4.2.md"
    assert "different rules" not in canonical.read_text()


def test_resolve_hand_set_bump_is_first_sighting(tmp_path):
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    skillmeta.resolve_version(p, reg)  # registers 1.4.2

    # a human sets a semantic minor bump AND changes a rule
    p.write_text(_SKILL.replace("version: 1.4.2", "version: 1.5.0")
                       .replace("rules go here", "new rules"))
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "1.5.0"
    assert note == "registered new version 1.5.0."
    r = json.loads(reg.read_text())
    assert "1.5.0" in r["versions"]
    # both versions now have their own sealed, immutable file
    v142 = tmp_path / "trade_skills" / "1.4.2.md"
    v150 = tmp_path / "trade_skills" / "1.5.0.md"
    assert v142.exists() and v150.exists()
    assert not _is_writable(v142) and not _is_writable(v150)
    assert "version: 1.4.2" in v142.read_text()
    assert "version: 1.5.0" in v150.read_text()


def test_resolve_creates_version_when_missing(tmp_path):
    p = _write_skill(tmp_path, "---\nname: x\n---\nbody\n")
    reg = tmp_path / "skill_versions.json"
    meta, note = skillmeta.resolve_version(p, reg)
    assert meta["version"] == "0.0.1"
    assert note and "created" in note
    assert "version: 0.0.1" in p.read_text()
    canonical = tmp_path / "trade_skills" / "0.0.1.md"
    assert canonical.exists() and not _is_writable(canonical)


def test_resolve_raises_if_seal_is_bypassed(tmp_path):
    """A chmod'd-back-writable sealed file whose bytes then drift is still
    caught (by hash, not just permissions) — the loud fallback the docstring
    promises for a bypassed seal."""
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    skillmeta.resolve_version(p, reg)  # registers + seals 1.4.2
    canonical = tmp_path / "trade_skills" / "1.4.2.md"
    os.chmod(canonical, 0o644)  # simulate a bypassed seal
    canonical.write_text(_SKILL.replace("rules go here", "tampered"))
    with pytest.raises(ValueError, match="must never be edited in place"):
        skillmeta.resolve_version(canonical, reg)


def test_new_version_forks_unsealed_copy(tmp_path):
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    skillmeta.resolve_version(p, reg)  # registers + seals 1.4.2
    skills_dir = tmp_path / "trade_skills"

    dest = skillmeta.new_version("1.4.2", "1.9.0", trade_skills_dir=skills_dir)
    assert dest == skills_dir / "1.9.0.md"
    assert _is_writable(dest)
    assert "version: 1.9.0" in dest.read_text()
    # source untouched
    assert "version: 1.4.2" in (skills_dir / "1.4.2.md").read_text()

    # omitting --to picks the next free patch
    dest2 = skillmeta.new_version("1.4.2", trade_skills_dir=skills_dir)
    assert dest2 == skills_dir / "1.4.3.md"

    # forking from a nonexistent version fails clearly
    with pytest.raises(FileNotFoundError):
        skillmeta.new_version("9.9.9", "9.9.10", trade_skills_dir=skills_dir)

    # forking onto an existing filename fails clearly (never silently overwrites)
    with pytest.raises(FileExistsError):
        skillmeta.new_version("1.4.2", "1.9.0", trade_skills_dir=skills_dir)


def test_base_version_promotion(tmp_path):
    p = _write_skill(tmp_path)
    reg = tmp_path / "skill_versions.json"
    skillmeta.resolve_version(p, reg)  # registers 1.4.2

    assert skillmeta.base_version(reg) is None
    with pytest.raises(FileNotFoundError):
        skillmeta.base_skill_path(reg)

    # promoting an unregistered version is refused
    with pytest.raises(ValueError, match="not registered"):
        skillmeta.set_base("9.9.9", registry_path=reg)

    skillmeta.set_base("1.4.2", registry_path=reg)
    assert skillmeta.base_version(reg) == "1.4.2"
    assert skillmeta.base_skill_path(reg) == tmp_path / "trade_skills" / "1.4.2.md"


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
