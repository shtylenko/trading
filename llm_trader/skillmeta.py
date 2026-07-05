"""Skill versioning — read/hash the TRADE_SIMULATOR skill and detect drift.

Every recorded run is stamped (at ``recorder init``) with the *version* of the
skill that drove it, so profitability can be attributed per version
(``recorder report --by-version``). A version has two parts:

- **semver** — a human-set ``version:`` in the skill's YAML frontmatter. This is
  what you group by and eyeball.
- **content hash** — an automatic sha256 of the file bytes. It guarantees two
  runs are distinguishable even if you forget to bump, and it powers the *drift
  warning*: if the file changes but the version tag doesn't, two different
  behaviours would otherwise blend under one tag.

A tiny committed registry (``skills/skill_versions.json``) remembers the first
hash seen for each version. ``init`` consults it and warns when the content has
drifted from that canonical hash without a bump. The registry lives in git
alongside the skill (NOT in the gitignored ``simulations/`` tree) because it is
the source of truth for "hash X *is* version 2.0.0".
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_SKILLS_DIR = Path(__file__).parent / "skills"
DEFAULT_SKILL_PATH = _SKILLS_DIR / "TRADE_SIMULATOR.md"
REGISTRY_PATH = _SKILLS_DIR / "skill_versions.json"

# how many hex chars of the sha256 we keep as the short content hash
_HASH_LEN = 8


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


def check_drift(
    meta: dict, registry_path: Path = REGISTRY_PATH, *, now: Optional[datetime] = None
) -> Optional[str]:
    """Record a first-seen version, or warn if a known version's content drifted.

    Returns a human-readable warning string when the skill content has changed
    but the version tag has not (the "you forgot to bump" case), else ``None``.

    On the first sighting of a version, its hash is written to the registry and
    no warning is produced. A drift does **not** overwrite the recorded hash, so
    the warning keeps firing every run until the version is actually bumped.
    """
    version = meta.get("version")
    if not version:
        return (
            f"skill {meta.get('name')!r} has no `version:` in its frontmatter — "
            "this run will be recorded as unversioned."
        )

    now = now or datetime.now()
    reg = _load_registry(registry_path)
    entry = reg.get(version)
    current = meta.get("content_hash")

    if entry is None:
        reg[version] = {
            "content_hash": current,
            "first_seen": now.isoformat(timespec="seconds"),
        }
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
        return None

    if entry.get("content_hash") != current:
        return (
            f"skill content changed but version is still {version} "
            f"(recorded {entry.get('content_hash')}, now {current}) — bump the "
            "`version:` in the frontmatter or two behaviours will blend under one "
            "tag."
        )
    return None
