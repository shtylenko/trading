"""Skill versioning — read/hash the TRADE_SIMULATOR skill and auto-version it.

Every recorded run is stamped (at ``recorder init``) with the *version* of the
skill that drove it, so profitability can be attributed per version
(``recorder report --by-version``). A version has two parts:

- **semver** — a ``version:`` in the skill's YAML frontmatter. This is what you
  group by and eyeball.
- **content hash** — an automatic sha256 of the file bytes, the source of truth
  for "did the rules actually change".

A tiny committed registry (``skills/skill_versions.json``) maps each version to
the content hash it was recorded with. On every run ``resolve_version`` compares
the skill's current hash to the hash recorded for its frontmatter version:

- version not yet in the registry → record it (first sighting), no change;
- recorded hash matches → unchanged;
- recorded hash **differs** (a rule changed under an already-recorded version) →
  **auto-bump**: pick the next free patch version, write it into the skill's
  frontmatter *and* the registry, and stamp the run with the new version.

So editing the rules and running a sim is enough — the version increments itself,
in the file and the registry, with no manual bump. (A human/agent may still set a
larger jump by hand — a minor/major bump — which is honoured as a first sighting.)

Termination note: the version is written into the frontmatter *before* the hash
is recorded, so the recorded hash reflects the post-write bytes — a subsequent run
sees a match and does not bump again.

Each time a version is recorded, an immutable snapshot of the skill is written to
``skills/archive/<stem>@<version>.md`` — a browsable history of every rule-set,
whose bytes hash to exactly what the registry records for that version.

The registry (and archive) live in git alongside the skill (NOT in the gitignored
``simulations/`` tree) because they are the source of truth for "hash X is v2.0.0".
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_SKILLS_DIR = Path(__file__).parent / "skills"
DEFAULT_SKILL_PATH = _SKILLS_DIR / "TRADE_SIMULATOR.md"

# how many hex chars of the sha256 we keep as the short content hash
_HASH_LEN = 8


def registry_for(skill_path: str | Path) -> Path:
    """The version registry lives next to its skill, so a custom ``--skill``
    (or a test's temp skill) tracks into its own file — never the bundled one."""
    return Path(skill_path).resolve().parent / "skill_versions.json"


def archive_dir_for(skill_path: str | Path) -> Path:
    """Where per-version snapshots of the skill are kept (next to the skill)."""
    return Path(skill_path).resolve().parent / "archive"


def _archive_path(skill_path: Path, version: str) -> Path:
    return archive_dir_for(skill_path) / f"{skill_path.stem}@{version}.md"


def _archive_snapshot(skill_path: Path, version: str) -> Path:
    """Save an immutable copy of the *current* skill bytes as
    ``archive/<stem>@<version>.md``. Called at the moment a version is recorded,
    so the snapshot's hash equals the hash the registry stores for that version."""
    dest = _archive_path(skill_path, version)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(skill_path.read_bytes())
    return dest


# the bundled skill's registry (the common case)
REGISTRY_PATH = registry_for(DEFAULT_SKILL_PATH)


def _parse_frontmatter(text: str) -> dict:
    """Minimal ``key: value`` reader for the leading ``---`` YAML block.

    Deliberately dependency-free (no pyyaml): the frontmatter we care about is
    flat scalars (``name``, ``version``). Anything fancier is ignored.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def read_skill_meta(path: str | Path = DEFAULT_SKILL_PATH) -> dict:
    """Return ``{name, version, content_hash, path}`` for a skill file.

    ``content_hash`` is ``sha256:<8 hex>`` over the raw file bytes. ``version``
    is ``None`` if the frontmatter has no ``version:`` — callers should treat a
    versionless skill as "unversioned" rather than fail.
    """
    p = Path(path)
    raw = p.read_bytes()
    fm = _parse_frontmatter(raw.decode("utf-8", errors="replace"))
    digest = hashlib.sha256(raw).hexdigest()[:_HASH_LEN]
    return {
        "name": fm.get("name"),
        "version": fm.get("version"),
        "content_hash": f"sha256:{digest}",
        # store a repo-relative-ish path for readability, falling back to name
        "path": _rel_path(p),
    }


def _rel_path(p: Path) -> str:
    """Best-effort ``trading/llm_trader/...``-style path for the manifest."""
    p = p.resolve()
    for parent in p.parents:
        if parent.name == "trading":
            return str(p.relative_to(parent.parent))
    return p.name


def _load_registry(registry_path: Path) -> dict:
    if not registry_path.exists():
        return {}
    try:
        return json.loads(registry_path.read_text())
    except Exception:
        return {}


def _save_registry(registry_path: Path, reg: dict) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")


def _parse_semver(v: str) -> Optional[list[int]]:
    """``"2.0.1"`` → ``[2, 0, 1]``; pads short forms; ``None`` if not numeric."""
    parts = v.strip().split(".")
    nums: list[int] = []
    for p in parts:
        if not p.isdigit():
            return None
        nums.append(int(p))
    while len(nums) < 3:
        nums.append(0)
    return nums[:3]


def _next_version(current: str, taken: set[str]) -> str:
    """Next free **patch** version after ``current``, skipping any already used.

    Falls back to a ``<current>-N`` suffix for non-semver version strings so we
    still produce a fresh, unique tag rather than crash.
    """
    nums = _parse_semver(current)
    if nums is None:
        i = 1
        while f"{current}-{i}" in taken:
            i += 1
        return f"{current}-{i}"
    nums[2] += 1
    while ".".join(map(str, nums)) in taken:
        nums[2] += 1
    return ".".join(map(str, nums))


def _write_version(skill_path: Path, new_version: str) -> bool:
    """Replace (or insert) the frontmatter ``version:`` line. Returns success.

    Rewrites only the version line inside the leading ``---`` block, leaving the
    rest of the file byte-for-byte intact. Returns ``False`` if there is no
    frontmatter block to edit (caller then falls back to a warning)."""
    lines = skill_path.read_text().splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return False
    end_idx = ver_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
        if lines[idx].lstrip().startswith("version:"):
            ver_idx = idx
    if end_idx is None:
        return False
    newline = f"version: {new_version}\n"
    if ver_idx is not None:
        lines[ver_idx] = newline
    else:
        lines.insert(1, newline)  # just under the opening ---
    skill_path.write_text("".join(lines))
    return True


def resolve_version(
    skill_path: str | Path = DEFAULT_SKILL_PATH,
    registry_path: Optional[str | Path] = None,
    *,
    now: Optional[datetime] = None,
) -> tuple[dict, Optional[str]]:
    """Return ``(stamp-ready meta, note)``, auto-creating a version on drift.

    See the module docstring for the three cases. ``note`` is a human-readable
    message describing a first-version creation or an auto-bump (for the caller to
    surface), or ``None`` when nothing changed.
    """
    skill_path = Path(skill_path)
    reg_path = Path(registry_path) if registry_path else registry_for(skill_path)
    now = now or datetime.now()

    meta = read_skill_meta(skill_path)
    reg = _load_registry(reg_path)
    version = meta.get("version")

    # versionless skill: create an initial version so the run is trackable
    if not version:
        new_version = _next_version("0.0.0", set(reg.keys()))  # → 0.0.1
        if not _write_version(skill_path, new_version):
            return meta, (
                f"skill {meta.get('name')!r} has no `version:` and no frontmatter "
                "to write one into — recorded as unversioned."
            )
        meta = read_skill_meta(skill_path)  # re-hash after writing the version
        reg[new_version] = {"content_hash": meta["content_hash"],
                            "first_seen": now.isoformat(timespec="seconds")}
        _save_registry(reg_path, reg)
        _archive_snapshot(skill_path, new_version)
        return meta, f"skill had no version — created {new_version}."

    entry = reg.get(version)
    current = meta.get("content_hash")

    if entry is None:  # first sighting (incl. a hand-set minor/major bump)
        reg[version] = {"content_hash": current,
                        "first_seen": now.isoformat(timespec="seconds")}
        _save_registry(reg_path, reg)
        _archive_snapshot(skill_path, version)
        return meta, None

    if entry.get("content_hash") == current:  # unchanged
        return meta, None

    # drift: content changed under an already-recorded version → auto-bump patch
    new_version = _next_version(version, set(reg.keys()))
    if not _write_version(skill_path, new_version):
        return meta, (
            f"skill content changed under {version} but the frontmatter could not "
            "be updated — bump `version:` manually."
        )
    meta = read_skill_meta(skill_path)  # re-hash AFTER writing the new version line
    reg[new_version] = {"content_hash": meta["content_hash"],
                        "first_seen": now.isoformat(timespec="seconds"),
                        "bumped_from": version}
    _save_registry(reg_path, reg)
    _archive_snapshot(skill_path, new_version)
    return meta, f"auto-bumped skill version {version} → {new_version} (rules changed)."
