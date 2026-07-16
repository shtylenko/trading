"""Skill versioning — one immutable file per version, no separate "live" copy.

Every recorded run is stamped (at ``recorder init``) with the *version* of the
skill that drove it, so profitability can be attributed per version
(``recorder report --by-version``). A version has two parts:

- **semver** — a ``version:`` in the skill's YAML frontmatter, matching the
  file's own name (``trade_skills/2.4.1.md`` declares ``version: 2.4.1``).
- **content hash** — an automatic sha256 of the file bytes, the source of truth
  for "did the rules actually change".

All versions for a family live as sibling files in that family's
``strategies/<id>/skills/trade_skills/``. There is no separate editable "live"
file: the small committed registry (``skills/skill_versions.json`` next to
``trade_skills/``) records a ``base`` pointer plus each version's content hash.

Default paths below point at the **warrior** family (historical default).

**Files are sealed (chmod read-only) the moment they're registered.** This is
what keeps the registry a source of truth: editing a version's rules in place,
after it's been used for even one run, would silently invalidate every past
result recorded against its hash with no way to recover the original bytes (no
separate archive copy exists to revert from — the version file *is* the only
copy). So the workflow for a new candidate is always an explicit copy-forward,
never an in-place edit:

    python3 -m trading.llm_trader.batchsim new-version --strategy warrior --from 2.4.1 --to 2.9.0
    # edit strategies/warrior/skills/trade_skills/2.9.0.md freely (unsealed until first run)
    python3 -m trading.llm_trader.batchsim run --version 2.9.0 ...
    python3 -m trading.llm_trader.batchsim promote --version 2.9.0   # once accepted

``resolve_version`` (used by interactive/unpinned ``recorder init`` runs, never
by a pinned batch) still auto-registers a version's first use and still
auto-assigns a version to a versionless skill — it just no longer auto-bumps a
sealed file's content in place, because that content can no longer be mutated
at the filesystem level.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

from .fsutils import atomic_write_bytes, atomic_write_json, file_lock

# Default = warrior family (symmetric layout under strategies/<id>/skills/).
_WARRIOR_SKILLS_DIR = Path(__file__).parent / "strategies" / "warrior" / "skills"
DEFAULT_TRADE_SKILLS_DIR = _WARRIOR_SKILLS_DIR / "trade_skills"
DEFAULT_REGISTRY_PATH = _WARRIOR_SKILLS_DIR / "skill_versions.json"
_SKILLS_DIR = _WARRIOR_SKILLS_DIR  # alias used by older helpers

# how many hex chars of the sha256 we keep as the short content hash
_HASH_LEN = 8

_SEALED_MODE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH          # 0o444
_UNSEALED_MODE = _SEALED_MODE | stat.S_IWUSR                        # 0o644


def trade_skills_dir_for(registry_path: str | Path) -> Path:
    """Where per-version skill files live, next to their registry."""
    return Path(registry_path).resolve().parent / "trade_skills"


def registry_for(trade_skills_dir: str | Path) -> Path:
    """The version registry next to a ``trade_skills`` dir (mirrors the old
    per-skill layout so a custom/test dir tracks into its own registry)."""
    return Path(trade_skills_dir).resolve().parent / "skill_versions.json"


def skill_path_for(version: str, trade_skills_dir: str | Path = DEFAULT_TRADE_SKILLS_DIR) -> Path:
    """The canonical path for one version's file: ``<dir>/<version>.md``."""
    return Path(trade_skills_dir) / f"{version}.md"


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


def read_skill_meta(path: str | Path) -> dict:
    """Return version/provenance metadata declared by a skill file.

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
        # Optional execution contract.  Older skills omit it and therefore use
        # the legacy reported-fill recorder; a major skill can opt into a new
        # deterministic execution model without changing historical sessions.
        "execution_model": fm.get("execution_model"),
        # Optional behavior contract for a deterministic skill. Kept in the
        # immutable session stamp so recorder validation does not infer rules
        # from a mutable "current version" pointer.
        "entry_bracket_required": fm.get("entry_bracket_required"),
        "entry_pyramid_required": fm.get("entry_pyramid_required"),
        # Optional market-data contract. A major version can begin at the open,
        # hide the scanner's already-known trigger, and receive completed 5-minute
        # candles without changing historical replay contracts.
        "session_from_open": fm.get("session_from_open"),
        "five_minute_context": fm.get("five_minute_context"),
        "completed_five_minute_entry_required": fm.get("completed_five_minute_entry_required"),
        # Multi-strategy / multi-horizon contracts
        "strategy": fm.get("strategy"),
        "horizon": fm.get("horizon"),  # intraday | multi_day
        "bar_resolution": fm.get("bar_resolution"),  # 1min | 1day
        "same_day_only": fm.get("same_day_only"),
        "max_hold_bars": fm.get("max_hold_bars"),
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
        return {"base": None, "versions": {}}
    try:
        reg = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"base": None, "versions": {}}
    reg.setdefault("base", None)
    reg.setdefault("versions", {})
    return reg


def _save_registry(registry_path: Path, reg: dict) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(registry_path, reg, indent=2, sort_keys=True)


def _registry_lock_path(registry_path: Path) -> Path:
    return registry_path.with_suffix(registry_path.suffix + ".lock")


def base_version(registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> Optional[str]:
    """The version an unpinned (no ``--version``) run currently uses. None if
    never set (a fresh checkout with no accepted baseline yet)."""
    return _load_registry(Path(registry_path)).get("base")


def base_skill_path(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    trade_skills_dir: Optional[str | Path] = None,
) -> Path:
    """The file path for the current base version. Raises if no base is set."""
    registry_path = Path(registry_path)
    trade_skills_dir = Path(trade_skills_dir) if trade_skills_dir else trade_skills_dir_for(registry_path)
    v = base_version(registry_path)
    if not v:
        raise FileNotFoundError(
            f"no base version set in {registry_path} — run `batchsim promote --version "
            "<X>` once a version exists, or `new-version` to create the first one."
        )
    return skill_path_for(v, trade_skills_dir)


def set_base(version: str, registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
    """Point unpinned runs at ``version``. It must already be registered
    (sealed by a first run/``resolve_version`` call) — you can't promote a
    version nobody has ever actually run."""
    registry_path = Path(registry_path)
    with file_lock(_registry_lock_path(registry_path)):
        reg = _load_registry(registry_path)
        if version not in reg["versions"]:
            raise ValueError(
                f"version {version} is not registered in {registry_path} — run it "
                "once (e.g. `batchsim run --version "
                f"{version} --dry-run`) before promoting it."
            )
        reg["base"] = version
        _save_registry(registry_path, reg)


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


def _rewrite_version_bytes(raw: bytes, new_version: str) -> Optional[bytes]:
    """Replace (or insert) the frontmatter ``version:`` line. Returns the new
    bytes, or None if there is no frontmatter block to edit."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    end_idx = ver_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
        if lines[idx].lstrip().startswith("version:"):
            ver_idx = idx
    if end_idx is None:
        return None
    newline = f"version: {new_version}\n"
    if ver_idx is not None:
        lines[ver_idx] = newline
    else:
        lines.insert(1, newline)  # just under the opening ---
    return "".join(lines).encode("utf-8")


def new_version(
    from_version: str,
    to_version: Optional[str] = None,
    *,
    trade_skills_dir: str | Path = DEFAULT_TRADE_SKILLS_DIR,
) -> Path:
    """Fork a new, unsealed candidate file from an existing (sealed) version.

    This is the ONLY sanctioned way to start editing toward a new version —
    editing a sealed file in place is blocked at the filesystem level (it's
    chmod read-only). Returns the new file's path, writable, frontmatter
    already rewritten to ``to_version`` (auto-picked as the next patch if
    omitted). The new file is NOT registered/sealed until it's actually run.
    """
    trade_skills_dir = Path(trade_skills_dir)
    src = skill_path_for(from_version, trade_skills_dir)
    if not src.exists():
        raise FileNotFoundError(f"source version {from_version} not found at {src}")
    if to_version is None:
        existing = {p.stem for p in trade_skills_dir.glob("*.md")}
        to_version = _next_version(from_version, existing)
    dest = skill_path_for(to_version, trade_skills_dir)
    if dest.exists():
        raise FileExistsError(f"{dest} already exists — pick a different --to version")
    raw = src.read_bytes()
    new_bytes = _rewrite_version_bytes(raw, to_version)
    if new_bytes is None:
        raise ValueError(f"{src} has no frontmatter block to rewrite the version in")
    atomic_write_bytes(dest, new_bytes)
    os.chmod(dest, _UNSEALED_MODE)
    return dest


def _seal(path: Path) -> None:
    """Make a version file read-only — it is now part of the permanent record
    and must never be edited in place again."""
    os.chmod(path, _SEALED_MODE)


def resolve_version(
    skill_path: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
    *,
    now: Optional[datetime] = None,
) -> tuple[dict, Optional[str]]:
    """Return ``(stamp-ready meta, note)``, registering+sealing a version on
    first use. ``skill_path`` defaults to the current base version's file.

    Unlike the old live-file design, this never rewrites a version's content
    in place — a version file is either brand new (unregistered, writable,
    gets sealed here) or already sealed (any content drift raises instead of
    silently bumping, since sealing means the filesystem itself should have
    prevented the edit; this is the loud fallback for a bypassed chmod).
    """
    # Registry resolution order: explicit registry_path wins; else, if an explicit
    # skill_path was given, colocate the registry next to it (this is what makes a
    # test's/ad-hoc skill file fully self-contained — resolve_version never touches
    # the real project's registry unless skill_path is also left at its default);
    # else fall back to the real project's registry for the real base skill.
    if registry_path is not None:
        registry_path = Path(registry_path)
    elif skill_path is not None:
        registry_path = Path(skill_path).parent / "skill_versions.json"
    else:
        registry_path = DEFAULT_REGISTRY_PATH
    trade_skills_dir = trade_skills_dir_for(registry_path)
    skill_path = Path(skill_path) if skill_path else base_skill_path(registry_path, trade_skills_dir)
    now = now or datetime.now()

    # Lock a sibling `.lock` file, never `skill_path` itself — a sealed (chmod
    # read-only) version file can't be opened in append mode, which is how
    # file_lock acquires its advisory lock.
    skill_lock_path = skill_path.with_name(skill_path.name + ".lock")
    with file_lock(_registry_lock_path(registry_path)), file_lock(skill_lock_path):
        meta = read_skill_meta(skill_path)
        reg = _load_registry(registry_path)
        versions = reg["versions"]
        version = meta.get("version")

        # versionless skill: assign an initial version so the run is trackable
        if not version:
            version = _next_version("0.0.0", set(versions.keys()))  # → 0.0.1
            new_bytes = _rewrite_version_bytes(skill_path.read_bytes(), version)
            if new_bytes is None:
                return meta, (
                    f"skill {meta.get('name')!r} has no `version:` and no frontmatter "
                    "to write one into — recorded as unversioned."
                )
            atomic_write_bytes(skill_path, new_bytes)
            meta = read_skill_meta(skill_path)  # re-hash after writing the version
            note_suffix = f"skill had no version — created {version}."
        else:
            note_suffix = None

        entry = versions.get(version)
        current = meta["content_hash"]

        if entry is None:  # first sighting (new candidate, or a hand-set bump)
            canonical = skill_path_for(version, trade_skills_dir)
            if skill_path.resolve() != canonical.resolve():
                atomic_write_bytes(canonical, skill_path.read_bytes())
                skill_path = canonical
            versions[version] = {
                "content_hash": current, "first_seen": now.isoformat(timespec="seconds"),
            }
            _save_registry(registry_path, reg)
            _seal(skill_path)
            return meta, note_suffix or f"registered new version {version}."

        if entry.get("content_hash") == current:  # unchanged
            return meta, None

        # entry exists but bytes differ — a sealed file was mutated in place
        # (chmod bypassed, or a repeat use of an unsealed race). Refuse rather
        # than guess: there is no separate archive copy left to revert from.
        raise ValueError(
            f"{skill_path} no longer matches the sealed hash registered for version "
            f"{version} — an already-registered version must never be edited in "
            f"place. Fork a new candidate instead: `batchsim new-version --from "
            f"{version} --to <next>`."
        )
