# Peer-review request: improving the trading-skill *improvement process*

**Date:** 2026-07-08
**Requested by:** the `llm_trader` maintainers
**Your role:** external reviewer AI with full read access to this repository.
**Deliverable:** save your response as `<yourname>_feedback.md` in this same
directory (`llm_trader/peer_reviews/2026-07-08-skill/`), e.g. `codex_feedback.md`,
`gemini_feedback.md`. Ground every claim in files/code you actually read — cite
`path:line`. Disagreement with the framing below is welcome and useful.

---

## 0. The one question we want answered

We iterate a trading **skill** (a natural-language rule-set an LLM executes) toward
better trading performance. The document that is *supposed* to govern how we do that
iteration — [`llm_trader/skills/MAINTAINING.md`](../../skills/MAINTAINING.md) —
currently only covers **versioning mechanics** (auto-bump, archive, registry). It says
nothing about **how to actually improve trading performance**: how to choose the next
rule change, how to test it, how to avoid fooling ourselves, or how to stay aligned
with the strategy we're trying to replicate.

> **We want your feedback on how to rewrite/expand `MAINTAINING.md` so it becomes the
> playbook for improving trading performance — not just a versioning note.**

Everything below is context to let you answer that well. If, after reading the code,
you think the bottleneck to better performance is somewhere *other* than
`MAINTAINING.md`, say so — but tell us what `MAINTAINING.md` should say to route future
maintainers toward that bottleneck.

---

## 1. What `llm_trader` is

`llm_trader` paper-trades **one recorded intraday setup at a time**, paced bar-by-bar,
and has an LLM agent make **Ross Cameron / Warrior Trading momentum long-side**
decisions (entry, scale, stop, exit) in real time, then journals the result. It exists
to (a) discover whether an LLM *can* trade this style profitably, and (b) find the
rule-set that makes it do so most reliably.

Core pieces (all under `llm_trader/`):

| File | Role |
|---|---|
| `skills/TRADE_SIMULATOR.md` | **the skill** — the full rule-set the agent follows. This is the artifact we are optimizing. Currently **v2.4.0**. |
| `skills/MAINTAINING.md` | **the subject of this review** — how the skill is maintained/versioned. |
| `skills/archive/TRADE_SIMULATOR@<v>.md` | immutable per-version snapshots (so any past run's exact rules are recoverable). |
| `skills/skill_versions.json` | registry: `version → content_hash`. |
| `batchsim.py` | runs headless agents over a fixed setup set (`testset*.json`), audits for look-ahead, aggregates results per batch. |
| `recorder.py` | records each run, derives P&L/R deterministically from fills, `report --by-version`. |
| `step.py` / `replay.py` / `feed.py` | the sealed, no-look-ahead bar-reveal machinery. |
| `viewer/` | web UI to inspect any run (chart + decision timeline). |

The **no-look-ahead guarantee is structural**: `step start` seals the whole day into a
private `_sealed.jsonl`; the agent only ever sees bars it has explicitly revealed via
`step next`. `batchsim` additionally strips market-data credentials from agents and
post-hoc audits every transcript, voiding any run that touched the future.

**How we measure:** `python3 -m trading.llm_trader.recorder report --by-version`
aggregates finalized runs per skill version (win%, P&L, avg R, MFE-capture). A "batch"
is a fixed, stratified holdout of `(ticker, date)` setups run against one pinned
version — see `batchsim.load_testset` and `batch/testset_100.json` (100 setups) /
`batch/testset.json` (30 setups).

---

## 2. The goal and the north star

**Goal:** maximize trading performance (expectancy in R, win rate, controlled losers,
reproducibility) of the skill.

**North star / alignment target:** the skill must faithfully implement Ross Cameron's
documented method. The authoritative corpus is
[`library/ross_cameron/all_content_structured.md`](../../../library/ross_cameron/all_content_structured.md)
(~1,270 lines distilled from 428 transcripts). Every rule in the skill is meant to trace
to it: the 5 pillars of stock selection, the ACD/first-new-high entry, "breakout or
bailout," scale-in-thirds, the 10-cent free-trade stop, the sub-VWAP-trap / washout
re-entry, the icebreaker sizing, "get good at losing," etc. **A change that improves a
metric but drifts from the corpus is a regression, not a win** — we do not want to
overfit an LLM to our particular holdout.

---

## 3. The improvement loop as it exists today (informal, undocumented)

1. Read the corpus + inspect losing runs in the viewer.
2. Form a hypothesis about a rule that's ambiguous, missing, or misapplied.
3. Edit `TRADE_SIMULATOR.md` (bump version — minor for behavioral change).
4. Run a batch on the pinned version; `report --by-version`; eyeball the delta.
5. Keep or revert.

This loop is **entirely tribal knowledge** — none of it is written down in
`MAINTAINING.md`. That is the gap.

---

## 4. What we've learned the hard way (please pressure-test these)

These lessons emerged over versions 2.0 → 2.4 and are the reason we now think
`MAINTAINING.md` needs to encode *methodology*, not just versioning:

- **Small samples lie.** On the 30-setup holdout, a *single* setup (CPSH) once printed
  +29.91R and single-handedly swung a version's avg R from ~0.4 to ~2.1. Re-running the
  same version on the same setup gave −0.27R. The strategy has **fat right tails**, so
  any 30-run comparison is dominated by whether one runner happened to fire. We now
  believe version ranking requires the **100-set** and ideally **repeats**.

- **The biggest performance variable is LLM non-determinism on *subjective* decisions.**
  Two runs of the *same version* on the *same setup* diverged wildly because one agent
  read a bar as "the breakout" and entered early with a tight stop (huge size, huge R),
  while the other called the same bar "extended," waited, and chased in later with a wide
  stop (tiny size, tiny R). Same rules, same data, opposite outcome — because "is this
  *the* breakout bar?" and "where exactly is the stop?" were *feel calls*.

- **The fix pattern that worked: replace feel calls with objective formulas.**
  - **v2.3.0** defined the trigger bar objectively ("the first revealed bar on which
    every entry-checklist box is simultaneously true") and fixed a `rvol_bar`-null trap
    that was blocking early entries.
  - **v2.4.0** defined stop placement objectively
    (`stop = min(trigger bar low, prior bar low) − $0.01`), banning the ad-hoc
    "tight stop under the breakout level" reading that only ever worked by luck.

- **This trades peak upside for reproducibility — deliberately.** v2.4.0 can no longer
  print a +30R lottery ticket (that only existed via a noise-tight stop), but its
  *mean* went up and its losers got tighter. We think that's the right trade, but we
  want challenge on it.

- **Measured result (the first comparison we actually trust):** v2.4.0 vs v2.2.1, both
  on the full 100-set, both 87 setups traded:

  | | v2.4.0 | v2.2.1 |
  |---|---|---|
  | avg R | **0.63** | 0.39 |
  | P&L | **$2,209** | $1,359 |
  | win % | 49% | 44% |
  | avg loser | −$15 | −$18 |

  Paired on 96 common setups: mean ΔR = **+0.25**, **42 better / 20 worse / 34 ≈equal**,
  sign-test **two-sided p ≈ 0.007** — broad-based, not tail-driven. (Contrast: our
  earlier 30-set comparisons were noise.)

**Open tensions we have NOT resolved (your input especially wanted):**
- Our 100-set **overlaps the tuning population** — we may be overfitting execution to
  known setups rather than generalizing. True out-of-sample needs more recorded setups.
- **One run per version** still leaves LLM per-run noise; repeats cost real money.
- Objectifying decisions reduces variance but risks **encoding our judgment instead of
  Cameron's** — where is the line between "removing ambiguity" and "deviating from the
  method"?

---

## 5. Reference material for grounding your review

**Last version tested — v2.4.0 — batch `20260708181528-BATCH-023823`.** Inspect it:

```bash
# per-leaf results for the batch
python3 - <<'PY'
import json, pathlib
base = pathlib.Path("trading/llm_trader/simulations")
for d in sorted(base.iterdir()):
    sj = d/"session.json"
    if not sj.exists(): continue
    s = json.loads(sj.read_text())
    if s.get("session") != "20260708181528-BATCH-023823": continue
    p = json.loads((d/"pnl.json").read_text()) if (d/"pnl.json").exists() else {}
    print(s["ticker"], s["historical_date"], "R=", p.get("r_multiple"), "traded=", p.get("traded"))
PY

# the whole version history, side by side
python3 -m trading.llm_trader.recorder report --by-version
```

Each leaf directory under `simulations/<id>/` holds `decisions.json` (the agent's
bar-by-bar reasoning — read these to see *why* it entered/exited), `pnl.json`,
`bars.json`, `journal.md`. The **comparison baseline** batch is
`20260707225900-BATCH-aca57c` (v2.2.1, same 100-set).

**Read at minimum:**
- `skills/MAINTAINING.md` — the target of this review.
- `skills/TRADE_SIMULATOR.md` — the current rule-set (esp. §A entry, §B manage, Step 0.5
  grading, Step 3 sizing). `diff` it against `archive/TRADE_SIMULATOR@2.2.1.md` to see
  exactly what 2.3.0+2.4.0 changed.
- `library/ross_cameron/all_content_structured.md` — the alignment target.
- `batchsim.py` (the test harness) and `recorder.py::report_by_version` (the metrics).
- A few `decisions.json` from winning and losing leaves in batch `023823`.

---

## 6. What `MAINTAINING.md` covers today (and doesn't)

**Covers:** version auto-bump on content-hash change; minor/major hand-bumps; the
immutable archive; the registry; "any byte change bumps."

**Does NOT cover (the gap we're asking you to help close):**
- How to decide *what* to change next (which rule is highest-value / highest-variance).
- How to test a change rigorously (sample size, repeats, which metric, tail-robustness).
- How to avoid false positives from small-sample tail luck.
- How to check a change still **aligns with the Cameron corpus** (not just "moves a metric").
- How to guard against **overfitting to the holdout** / holdout contamination.
- The objective-rule design philosophy (replace feel calls with formulas) as an
  explicit, reusable heuristic for future edits.
- When to stop (diminishing returns / when a version is "good enough to keep").

---

## 7. Specific questions for you

1. **Structure & scope.** Should `MAINTAINING.md` stay a pure versioning doc with a new
   sibling (e.g. `IMPROVING.md` / `METHODOLOGY.md`), or should it absorb the methodology?
   Propose the concrete section outline you'd write.

2. **Test rigor.** Given fat-tailed outcomes and LLM per-run noise, what is the *minimum
   defensible* protocol to accept a version as "better"? (Sample size, repeats,
   paired vs unpaired, which statistic, what significance bar, how to report it.) Be
   concrete enough to write into the doc as a checklist.

3. **Metric of record.** We rank on avg R / P&L / win%. Are we optimizing the right
   objective? What single primary metric (and guardrail metrics) would you enshrine, and
   why — given a flat per-trade risk budget and no compounding? (See the prior review
   `../2026-07-06-session-metrics/` for our metric discussion.)

4. **Overfitting / generalization.** How should the doc handle the fact that our 100-set
   overlaps the tuning setups? Prescribe a holdout discipline we can actually follow.

5. **Alignment enforcement.** How do we make "traceable to the Cameron corpus" a
   *checkable* gate on every rule change, not a vibe? Is there a lightweight artifact
   (rule → corpus §citation table?) worth maintaining?

6. **Finding the next change.** We found the last two wins by reading divergent runs and
   spotting a *subjective* decision. Is there a systematic way (variance decomposition
   across repeats? disagreement mining across runs of the same version?) to surface the
   next-highest-variance decision automatically? Would that belong in the doc/tooling?

7. **The reproducibility-vs-upside trade.** We deliberately removed the +30R tail by
   objectifying the stop. Right call? Under what objective should we (not) do that again?

8. **Anything we're blind to.** Having read the code, what's the biggest risk or missed
   opportunity in how we improve this skill that none of the above captures?

---

## 8. How to respond

Write `<yourname>_feedback.md` here. Prioritize: lead with the 2–3 changes to
`MAINTAINING.md` (or its replacement) that would most improve *trading performance per
iteration*, then the concrete section outline / checklist you'd have us adopt, then the
rest. Cite files. Push back where we're wrong.
