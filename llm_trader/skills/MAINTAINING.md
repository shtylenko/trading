# Maintaining TRADE_SIMULATOR — versioning & archive

> **This file is for whoever *edits* the skill, not for the agent *executing* a
> trade.** If you are running a simulation, ignore this — versioning is fully
> automatic and requires nothing from you. Go back to `TRADE_SIMULATOR.md`.

> ## ⚠ Improving performance ≠ versioning
>
> This file only covers **version mechanics**. Versioning a change does not make it
> an improvement. **Before any behavioral rule change, follow [`IMPROVING.md`](IMPROVING.md)**
> (hypothesis → objectify the feel-call → paired batch gate → RULE_TRACE citation).
>
> **Never rank skill versions from a mixed `recorder report --by-version` table** — it
> aggregates leaves across batches/models (rows flagged `MIXED`) and will manufacture
> false regressions. Rank a pair with `batchsim compare --a <tagA> --b <tagB>` on one
> batch each. See `IMPROVING.md` §5 (the promotion gate).

## For AI assistants and automated code editors (IMPORTANT)

**Any modification to the content of `TRADE_SIMULATOR.md` (including examples,
hygiene instructions, command blocks, or explanatory text that the agent will
read or be told to follow) changes the skill.**

You **MUST** ensure a version bump happens:

- Preferred: edit the file, then run a normal `python -m trading.llm_trader.recorder init ...` (without `--pin-version`) so `resolve_version` auto-bumps the patch and updates the registry + archive.
- Or: manually set a new `version:` in the frontmatter in the same edit (use the next patch unless you intend a larger jump).
- Never edit the text of an archived `archive/TRADE_SIMULATOR@X.Y.Z.md` file.
- Changes to the *injected prompt* in `batchsim.py` that affect agent behavior on a pinned version should also be accompanied by a version bump (or documented as only affecting new versions).

Failing to bump mixes different agent instructions under the same version number, making `report --by-version` and batch comparisons meaningless.

Log new rules or incidents in this file under "AI / Tooling Rules".

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
