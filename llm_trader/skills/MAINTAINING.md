# Maintaining TRADE_SIMULATOR — versioning & the base pointer

> **This file is for whoever *edits* the skill, not for the agent *executing* a
> trade.** If you are running a simulation, ignore this — versioning is fully
> automatic and requires nothing from you. Go find your version under
> `skills/trade_skills/`.

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

## There is no "live" skill file

Every version — the currently-accepted one and every past/rejected candidate — is
its own file in `skills/trade_skills/<version>.md`. `skills/skill_versions.json`
tracks each version's content hash plus a `base` pointer: whichever version an
unpinned run (`recorder init` without `--pin-version`, or `batchsim run` without
`--version`) currently uses. Check it any time:

```
python3 -m trading.llm_trader.batchsim current
```

## Files are sealed — you cannot edit one in place

The moment a version file is registered (first run against it), it's chmod'd
read-only. This is deliberate, not a bug: there's no separate archive copy behind
it anymore — the version file **is** the only copy, so an in-place edit after
sealing would silently invalidate every past result recorded against its hash with
no way to recover the original bytes. Editing a sealed file fails with a
permission error at the OS level before any Python code even runs.

## Workflow for a new candidate

```
# 1. fork a new, unsealed candidate from an existing version
python3 -m trading.llm_trader.batchsim new-version --from 2.4.1 --to 2.9.0
#    (omit --to to auto-pick the next free patch)

# 2. edit skills/trade_skills/2.9.0.md freely — it's writable until first run

# 3. test it (this also registers + seals it, and does NOT move `base`)
python3 -m trading.llm_trader.batchsim run --version 2.9.0 --model <...> ...

# 4. only once it clears the promotion gate (IMPROVING.md §5), make it default
python3 -m trading.llm_trader.batchsim promote --version 2.9.0
```

`new-version` also rewrites the frontmatter `version:` line for you, so the file's
name and its own declared version always agree — don't hand-edit that line
yourself unless you also rename the file to match.

## For AI assistants and automated code editors (IMPORTANT)

**Any modification to a skill's rules (examples, hygiene instructions, command
blocks, or explanatory text the agent will read or be told to follow) requires a
new version file — never edit a file already under `skills/trade_skills/` in
place.** If you try, the filesystem will refuse the write; that error means fork
with `new-version` first, not "find a way around the permission."

Changes to the *injected prompt* in `batchsim.py` that affect agent behavior on a
pinned version should also be accompanied by a version bump (or documented as only
affecting new versions) — otherwise `report --by-version` and batch comparisons
mix different agent instructions under the same version number.

Log new rules or incidents in this file under "AI / Tooling Rules".

## Registering without promoting

`resolve_version` (used by an interactive/unpinned `recorder init`) registers +
seals a version's file on its first use, but never moves `base` — promotion is
always the separate, explicit `batchsim promote` step above. A `--version X`
batch run also registers+seals `X` on first use without touching `base`.

- **Any byte change is a new version.** There's no auto-bump-on-drift anymore
  (nothing to bump — a sealed file can't drift). A versionless skill file still
  gets an initial version (`0.0.1`) assigned automatically on first use.
- **Hand-set the version** in the frontmatter of a forked candidate to whatever
  jump you intend — patch for a small change, minor/major for a real behavioral
  or strategic shift. `new-version --to <X>` sets this for you; `new-version`
  with no `--to` defaults to the next patch.

## Files (all committed, git-tracked)

| File | Role |
|---|---|
| `skill_versions.json` | registry: `{"base": <version>, "versions": {version: {content_hash, first_seen}}}` |
| `trade_skills/<v>.md` | every version's full text — sealed (read-only) once registered |

Implementation lives in `llm_trader/skillmeta.py` (`resolve_version`, `new_version`,
`set_base`), called from `recorder.init` / `batchsim`. Tests:
`llm_trader/tests/test_skillmeta.py`.
