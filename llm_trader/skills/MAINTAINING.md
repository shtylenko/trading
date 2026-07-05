# Maintaining TRADE_SIMULATOR — versioning & archive

> **This file is for whoever *edits* the skill, not for the agent *executing* a
> trade.** If you are running a simulation, ignore this — versioning is fully
> automatic and requires nothing from you. Go back to `TRADE_SIMULATOR.md`.

## Versioning is automatic

Each run is stamped with the skill's `version:` (frontmatter) so profitability is
tracked per rule-set: `python3 -m trading.llm_trader.recorder report --by-version`.

You do **not** bump the version by hand. Whenever `TRADE_SIMULATOR.md`'s content
changes, the next `recorder init` notices (its content hash no longer matches the
one recorded for `version:` in `skill_versions.json`) and **auto-bumps the patch**
(`2.0.1 → 2.0.2`), writing the new number into the frontmatter *and* the registry
before stamping the run. It prints `• auto-bumped skill version …` to stderr.

- **Any byte change bumps** — including pure prose edits. Auto-detection can't tell
  a rule change from a typo fix.
- **Want a larger, semantic jump?** Set `version:` by hand in the same edit —
  **minor** (`2.0.1 → 2.1.0`) for a real behavioural rule change, **major**
  (`2.0.1 → 3.0.0`) for a strategy rethink. A hand-set version is honoured as-is
  (no auto-bump on top of it), recorded as a first sighting.

## Archive

Every time a version is recorded, an immutable snapshot of the skill is written to
`skills/archive/TRADE_SIMULATOR@<version>.md`. Its bytes hash to exactly what the
registry records for that version, so you can read — or `diff` — the precise
rule-set behind any past run.

## Files (all committed, git-tracked)

| File | Role |
|---|---|
| `skill_versions.json` | registry: `version → content_hash` (source of truth) |
| `archive/TRADE_SIMULATOR@<v>.md` | immutable per-version snapshots |

Implementation lives in `llm_trader/skillmeta.py` (`resolve_version`), called from
`recorder.init`. Tests: `llm_trader/tests/test_skillmeta.py`.
