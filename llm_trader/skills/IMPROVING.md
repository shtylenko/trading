# Improving TRADE_SIMULATOR performance — the methodology playbook

> **This file is for whoever *improves* the trading rules.** `MAINTAINING.md` covers
> version mechanics (auto-bump, archive, registry). This file covers **how to make a
> rule change that actually raises trading performance and how to prove it did.**
> Versioning alone does not improve expectancy. Read this before any behavioral edit.

This playbook is the distillation of the 2.0→2.4 iteration and a three-way external
review (`peer_reviews/2026-07-08-skill/`). Follow it or you will keep shipping better
*archives* of the same tribal guesswork.

---

## 0. Objective (the thing we maximize)

**Primary:** raise **paired effective expectancy in R** on a fixed setup list, under a
flat per-trade risk budget, **while remaining a faithful operationalization of the Ross
Cameron canon** (`library/ross_cameron/all_content_structured.md`).

**Explicit non-goals:**
- Maximizing **max-R lottery tickets** (a +30R print from a noise-tight stop is size
  leverage, not edge — see §7).
- Gaming **clean-only** stats by standing down on marginal-but-profitable trades or by
  voiding hard setups. This is why the metric of record is *effective* R, not clean R.
- Beating one specific holdout. A change that lifts a metric but drifts from the canon
  is a **regression**, not a win.

---

## 1. Sources of truth

| Source | Role |
|---|---|
| `library/ross_cameron/all_content_structured.md` | **The single canon.** Every behavioral rule must trace to it. |
| `skills/TRADE_SIMULATOR.md` | The rule-set being optimized. |
| `skills/RULE_TRACE.md` | rule → canon citation table. **Mandatory update on every behavioral bump.** |
| `skills/CHANGELOG.md` | experiment log: version, hypothesis, batch, ΔR, decision. |
| `BACKLOG.md` | the open improvement queue. |

---

## 2. Design philosophy — the working heuristic that produced v2.3/v2.4

**Replace subjective feel-calls with formulas over revealed bars, at the decisions that
multiply R.** The biggest performance variable is LLM non-determinism on *judgment*
calls: two runs of the same version on the same setup diverged from +30R to −0.27R
because "is this *the* breakout bar?" and "where exactly is the stop?" were feel-calls.

- **v2.3.0** made the trigger bar objective ("first revealed bar where every entry box
  is true") and fixed a null-`rvol` trap.
- **v2.4.0** made stop placement a formula (`min(trigger low, prior low) − $0.01`).
- Result: paired mean ΔR **+0.25**, sign-test **p ≈ 0.007**, broad (not tail-driven).

Rules for applying it:
1. Prefer decisions that drive **fill price → share count → R** (entry timing, stop
   distance, free-trade BE, bailout).
2. Only objectify **corpus-grounded ambiguity**. A formula is acceptable when it is a
   *declared operationalization of a cited rule*, not the best-performing threshold on
   the known 100-set. If it narrows Cameron's discretion, say **why** in RULE_TRACE
   (e.g. "LLM reproducibility") so nobody later "fixes fidelity" by reintroducing noise.
3. **One hypothesis per minor bump.** Bundle only if inseparable — else you can't tell
   which change moved the metric.

---

## 3. How to choose the next change (don't start from "what prose can we add?")

Start from **which repeated-state decision is unstable and expensive**:

1. Run the candidate/current version with `--repeats 3-5` on a **dev** subset.
2. Align `decisions.json` across repeats by bar index; flag bars where `action`,
   `stop`, `fill_px`, or ENTER/EXIT timing differ.
3. Cluster disagreements by rule family (entry trigger, initial stop, free-trade BE,
   soft-bailout clause, scale level, re-entry, runner exit).
4. Rank by `within-setup std(R) × disagreement frequency × avg |ΔR| after divergence`.
5. Read the top cluster's losing/high-Δ leaves in the viewer. Classify: ambiguity /
   missing rule / misapplied rule / infra void / luck.
6. **Then** check the canon and write a thesis. Invent the rule from the top
   disagreement cluster, not from intuition about Cameron.

Known remaining feel-calls (as of v2.6): **scale "or first clear resistance"** (which
level counts as the first resistance is still a judgment call); pyramiding "conviction" /
"healthy rvol_bar" (§B.6); "still near the trigger" in the not-extended box. (The v2.4-era
list — soft-bailout OR-chain, free-trade BE timing, grade-B "decisively", "A+ bar" —
was objectified in 2.5.0/2.6.0; see CHANGELOG.)

---

## 4. Edit protocol (before you touch the skill)

Write a short thesis (into `CHANGELOG.md`) with: the decision instability or canon gap;
the skill lines and canon lines it touches; the change **type** (direct-corpus /
operationalization / sim-constraint / empirical-guardrail); the expected behavioral
delta and expected metric movement; the dev setups you'll inspect. Then:

- Patch `TRADE_SIMULATOR.md`; **hand-set a minor version** for a behavioral change.
- Update `RULE_TRACE.md`.
- `diff` against the previous `archive/TRADE_SIMULATOR@<prev>.md` snapshot.
- Batch-harness prompt changes in `batchsim.py` that affect agent behavior count as
  skill changes — bump too (see `MAINTAINING.md`).

### 4.1 Pre-batch clarity review (mandatory before any PAID batch)

Before a candidate goes to a paid validation batch, run an **executing-model clarity
review** of the full skill text: give a fresh LLM (ideally the same model that runs the
batches) the prompt at `peer_reviews/skill_clarity_review_prompt.md` and have it read
the candidate `TRADE_SIMULATOR.md` cold.

Why this is a gate, not a nicety: the 2.5.0 candidate shipped with a structural bug —
`break_level` defined as the breakout bar's high made the failed-break predicate fire
on the fill bar of every confirmed-close entry — that the author (who "knew what was
meant") could not see. The review caught it *before* a batch was paid for; without it,
the comparison would have measured the bug, not the hypothesis. Author blindness to
own drafts is exactly what a cold reader is for.

Protocol:
1. Run the review on the **candidate** text (post-edit, pre-batch).
2. Triage findings the way 2.6.0 did: accept / accept-the-problem-change-the-fix /
   reject — and **hold the reviewer to the same constraints** (no new tuned
   thresholds, no strategy redesign, prefer predicates over revealed fields). A
   reviewer suggestion is a *finding*, not a patch to apply verbatim.
3. Fold accepted fixes into the same candidate version **before** it batches (a
   clarity fix to an un-batched candidate is a rewrite of that candidate, not a new
   hypothesis — bundle freely; §2's one-hypothesis rule applies to *behavioral*
   theses, not to de-ambiguification of their wording).
4. Log in `CHANGELOG.md` which findings were accepted and which rejected (and why) —
   rejected findings are precedent for the next reviewer pass.
5. Only then spend on the batch.

---

## 5. Test protocol — the promotion gate (run `batchsim compare`)

**Never rank versions from a mixed `recorder report --by-version` table.** That table
aggregates every leaf of a version across batches/models and is flagged `MIXED` for
exactly this reason. Rank a *pair* with one batch each:

```bash
# baseline A (accepted) vs candidate B, same testset, same model, pinned versions
python3 -m trading.llm_trader.batchsim compare --a <tagA> --b <tagB>
```

**Unit of observation:** one `(ticker, date)` key. `compare` dedups resume/retry leaves
to one representative per key (prefers a completed non-void non-ooc leaf).

**Effective R per key:** traded → `r_multiple`; stood-down → **0R**; void/out-of-credits
→ **excluded from the pair** but reported as a guardrail.

**Promotion bar (all must hold):**
- [ ] Candidate passed the **pre-batch clarity review** (§4.1) before its batch ran.
- [ ] Same model, same testset file, pinned archived versions, **≥ 80 paired keys**
      (use the 100-set; the 30-set is smoke only).
- [ ] Paired **mean ΔR > 0** and **median ΔR ≥ 0**.
- [ ] **Sign-test p < 0.05** (two-sided, ties excluded) — or a paired-bootstrap 95% CI
      on mean ΔR that excludes 0.
- [ ] **Not tail-driven:** top-3 winners ≤ ½ of total positive ΔR (`compare` prints this).
- [ ] **Guardrails not worse:** void rate, out-of-credits, stood-down rate, avg loser,
      p10 R. A stricter version that stands down more can look good on *clean* R —
      effective R and the stood-down guardrail catch it.

`compare` prints an `ACCEPT / INVESTIGATE / REJECT` verdict against these. Record the
result (batch IDs, model, testset, ΔR, p, decision) in `CHANGELOG.md`.

**Repeats:** one run over the full set is the floor when cost is tight — but then accept
only if the effect is **broad** (sign test), never if ≤3 leaves explain >½ of ΔR. For a
rule touching entry/stop/bailout/re-entry, add `--repeats 2-3` (on the full set, or on
the top-20 highest-variance keys) so one lucky sampling can't masquerade as a rule win.

---

## 6. Holdout discipline (we are currently semi-contaminated — don't launder it)

The 100-set (`batch/testset_100.json`) was **inspected to design v2.3/v2.4**, so its
reported edge is an **upper bound** for live generalization (the paired sign-test is
still valid evidence of a within-sample effect — it just isn't out-of-sample).

Policy:
- The 100-set is the **dev** set: inspect leaves freely, mine disagreements, design rules.
- A **locked holdout** must be built from `(ticker, date)` keys **disjoint** from the
  dev set. Right now the setup pool (`entries.db`, 414 unique but all 2025-01…2026-06) has
  the dev 100 drawn from inside it, so **expanding the pool with earlier-period data is the
  enabling task** (BACKLOG `DX`). Build the holdout with a new seed via
  `batchsim build-set --exclude batch/testset_100.json` on the grown pool.
- **Quarantine rule:** if you opened a setup's chart/decisions to form a hypothesis,
  that setup is dev forever and cannot count as holdout evidence for that rule.
- Label every published table with the set used, version, batch tag, and model.

---

## 7. Reproducibility vs upside (settled: variance-reduction is conditional, not a goal)

Killing the +30R tail by objectifying the stop was **correct** because that tail came
from a stop *inside normal bar noise* — `shares = risk_budget / stop_distance`, so a
10× tighter stop is a 10× size bet that the path won't wick, which is accidental
optionality, not Cameron's "stop at the pullback low."

But **do not make variance-reduction unconditional.** The strategy is *supposed* to have
right-tail runners (scale-outs + 5-min runner management still allow multi-R winners).
The acceptance question is: **does the change cut *invalid path variance* while
preserving *valid strategy convexity*?** If a formula clips legitimate runners just to
make the distribution prettier — watch **median R** and **MFE-capture on wins** as
guardrails — reject it. Maximize paired effective mean R subject to (void low, p10 R not
worse, MFE-capture not collapsing). Never maximize max(R).

---

## 8. Tooling reference

```bash
# run a batch on a pinned version (see MAINTAINING for versioning)
python3 -m trading.llm_trader.batchsim run --version <v> --model <m> --set batch/testset_100.json
# resume (recovers version/model/set from batch.json)
python3 -m trading.llm_trader.batchsim run --resume --session <…-BATCH-…>
# audit look-ahead / mark out-of-credits
python3 -m trading.llm_trader.batchsim audit --tag <tag>
# THE GATE: paired candidate-vs-baseline
python3 -m trading.llm_trader.batchsim compare --a <tagA> --b <tagB>
# per-batch report (effective + clean R). Bare --by-version MIXES batches — do not rank from it.
python3 -m trading.llm_trader.recorder report --by-version
```

---

## 9. When to stop / when to major-bump

- **Diminishing returns:** if `|mean ΔR| < 0.05` and non-significant for two consecutive
  iterations on the same set, stop tweaking — the remaining variance is model/sampling,
  not rules. Invest in data (more setups) or a different lever.
- **Major bump (X.0.0):** a strategy rethink — changing the fill model (slippage /
  liquidity cap / latency), the 1-min→5-min entry timeframe, or the small-account
  profile. These invalidate cross-version comparisons, so re-baseline everything.

---

## 10. Known failure modes (lessons 2.0→2.4 — do not repeat)

1. **30-set + one outlier.** A single CPSH +30R swung a version's avg R from 0.4 to 2.1;
   re-run gave −0.27R. 30-set rankings are noise. Use the 100-set + sign test.
2. **Mixed `report --by-version`.** v2.2.1 reads 0.79R over 114 mixed leaves vs 0.39R on
   its clean 100-set batch. Rank only within one batch via `compare`.
3. **Feel-call stop/size.** The single largest source of run-to-run R variance. Objectify.
4. **Holdout contamination.** We tuned on the 100-set; it is now dev, not a holdout.
5. **Duplicate leaves.** Resume creates a new leaf without deleting the old stub; the
   v2.2.1 batch has 27 dup/void/ooc leaves. Always dedup to one key per setup (`compare`
   does this; hand analysis must too).
