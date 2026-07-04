"""Structural hygiene guards — keep lab/ from re-bloating as research iterates.

Background: `lab/scripts/` and `lab/validation/` had accreted ~40 one-off experiment
scripts + 1.5 GB of capture parquet mixed in with the evergreen engine. After the 2026-06
reorg, one-off research lives in `lab/experiments/<bucket>/`, data in
`experiments/_data/` (gitignored), and the per-experiment audit trail in
`validation/research_log/`. These tests fail the moment that separation erodes, so the
"just drop it next to the others" path of least resistance is blocked at CI time rather
than discovered months later. See `lab/CLAUDE.md` ("Anti-bloat conventions") for the rules
these enforce.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[1]  # monorepo root (parent of the `trading/` package)

# Evergreen engine CLI entry points. Adding to this set is a DELIBERATE act: a new file in
# scripts/ must be a real cross-family CLI/engine tool, not a one-off research script (those
# go in experiments/<bucket>/). If this list needs updating for a genuine new tool, update it
# in the same change that adds the tool — that review friction is the point.
EVERGREEN_SCRIPTS = {
    "__init__.py",
    "backtest.py",
    "build_screen_testset.py",
    "build_sector_map.py",
    "build_universe.py",
    "dashboard.py",
    "disk_usage.py",
    "lifecycle.py",
    "permutation_gate.py",
    "report.py",
    "retry_sector_map.py",
    "validate_run.py",
}


def test_scripts_dir_holds_only_evergreen_cli() -> None:
    """`lab/scripts/` is for evergreen engine CLI only. One-off research scripts belong in
    `lab/experiments/<bucket>/`. A new file here that isn't a real CLI tool is the classic
    re-bloat — add it to experiments/ instead (or, if it truly is engine CLI, add it to
    EVERGREEN_SCRIPTS in the same change)."""
    present = {p.name for p in (LAB / "scripts").glob("*.py")}
    unexpected = present - EVERGREEN_SCRIPTS
    assert not unexpected, (
        f"Unexpected files in lab/scripts/: {sorted(unexpected)}. "
        "One-off research scripts go in lab/experiments/<bucket>/. "
        "If this really is an evergreen engine CLI tool, add it to EVERGREEN_SCRIPTS here."
    )


def test_no_parquet_or_data_committed() -> None:
    """Capture data (*.parquet) is gitignored and lives in experiments/_data/, regenerated
    on demand. Committing it bloats the repo permanently. This catches an accidental
    `git add` of a ledger anywhere under trading/."""
    tracked = subprocess.run(
        ["git", "ls-files", "*.parquet"], cwd=REPO, capture_output=True, text=True
    ).stdout.split()
    assert not tracked, (
        f"Data files tracked by git: {tracked}. Captures belong in "
        "lab/experiments/_data/ (gitignored) and are regenerated, never committed."
    )


def test_experiments_scripts_live_in_buckets() -> None:
    """`lab/experiments/` groups scripts by direction (multiday/, overnight/, harness/, …).
    A loose .py at the top level is an ungrouped one-off — put it in a bucket (make a new one
    for a new direction; don't pile into misc/)."""
    loose = {p.name for p in (LAB / "experiments").glob("*.py")} - {"__init__.py"}
    assert not loose, (
        f"Loose scripts at lab/experiments/ top level: {sorted(loose)}. "
        "Move each into a direction bucket (experiments/<bucket>/)."
    )
