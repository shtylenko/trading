# Grok peer review: skill-improvement playbook (`MAINTAINING.md`)

**Date:** 2026-07-08  
**Reviewer:** Grok (xAI)  
**Target question:** How should `llm_trader/skills/MAINTAINING.md` become the playbook for *improving trading performance*, not just versioning mechanics?  
**Grounding:** `skills/MAINTAINING.md`, `skills/TRADE_SIMULATOR.md` v2.4.0 vs archive `@2.2.1` / `@2.3.0`, `batchsim.py`, `recorder.py::report_by_version`, corpus under `library/ross_cameron/`, batch `20260708181528-BATCH-023823` (v2.4.0) vs `20260707225900-BATCH-aca57c` (v2.2.1), plus prior metrics review `peer_reviews/2026-07-06-session-metrics/`.

---

## TL;DR — the 3 changes that most improve performance *per iteration*

1. **Split the doc, don’t just lengthen it.** Keep `MAINTAINING.md` as the short *mechanics* page (auto-bump, archive, registry — what it already is at `skills/MAINTAINING.md:1-57`). Add a sibling **`IMPROVING.md`** as the *methodology* playbook: hypothesis → objectify feel-calls → batch protocol → promote/revert. Maintainers edit the skill weekly; they need a checklist they can follow without rereading versioning lore. Putting both in one file will make the versioning note unreadable and the methodology hard to find.

2. **Enshrine a promotion gate that the current tooling does not implement.** `recorder report --by-version` (`recorder.py:1420-1493`) is **not** a valid version ranker: it mixes every finalized leaf of a version across batches, models, and retries. Live numbers today: v2.2.1 reports avgR **0.79** over n=114 mixed sessions, while the apples-to-apples 100-set batch alone is avgR **0.39** on 87 traded leaves. Ranking from the mixed table is how you fool yourselves. The gate must require: **one pinned batch tag per version**, **one leaf per (ticker, date)** (or explicit repeat aggregation), **paired effective ΔR**, and a **pre-declared significance bar**. Write that as a checklist in `IMPROVING.md` *and* ship `batchsim compare` (already proposed in `2026-07-06-session-metrics/proposal.md:171`).

3. **Make “objectify the next highest-variance feel-call” the default edit policy — with a corpus citation gate.** v2.3.0 (trigger bar definition + null-`rvol_bar`) and v2.4.0 (formula stop) are the right pattern: they attacked **decision noise that multiplies R** (stop → shares → R), not cosmetic prose. Codify: (a) mine divergence before inventing rules; (b) only promote rules that are *formulas over revealed bars*; (c) every new formula must cite a corpus section; (d) reject “tight stop under the break” style luck even if one leaf prints +30R.

Everything else below is supporting structure for those three.

---

## Pushback on the framing (where you’re right / wrong)

### What’s solid

- **Small samples lie.** Confirmed. Fat right tails + LLM non-determinism dominate 30-set rankings. The CPSH anecdote matches the structure of this strategy (rare multi-R runners; mean sensitive to max).
- **Objectifying feel-calls raised mean and tightened losers.** Reproduced on the named batches (effective paired, stood-down = 0R): n=99 common setups, mean ΔR ≈ **+0.29**, better/worse/equalish ≈ **41 / 19 / 39**, sign-test two-sided **p ≈ 0.006** — consistent with your reported ~+0.25 / p≈0.007 when ties are treated similarly. Not tail-driven: max R on v2.4 is **4.89** (RNAZ), not 30; losers bottom near **−1.1R** on both.
- **The tribal loop** (viewer → hypothesis → edit → batch → eyeball) is exactly what the docs omit. `MAINTAINING.md` never mentions batchsim, holdouts, or Cameron alignment.

### What’s incomplete or slightly wrong

1. **Bottleneck is not only `MAINTAINING.md`.** The doc is empty of methodology, yes — but the **harness already half-knows the right design** (`batchsim.py:1-34`: fixed holdout, pin version, `--repeats`) and then **report/compare tooling under-delivers**. `report_by_version` has no batch isolation by default, no paired delta, no CI, no repeat aggregation. Writing a beautiful playbook without `batchsim compare` will produce disciplined humans running undisciplined numbers.

2. **Your v2.2.1 baseline batch is messier than the prompt implies.** Session `20260707225900-BATCH-aca57c` has **127 leaves / 100 unique (ticker,date)** — **27 duplicate setups**. v2.4 batch is clean (100/100). Any hand-paired analysis that doesn’t dedupe first is soft. The playbook must require: **one primary leaf per setup per version**, or mean-of-repeats if `--repeats>1`.

3. **“Alignment to Cameron” is currently multi-headed and path-broken.**  
   - Skill front matter points agents at `library/analyst_warrior_trading_strategy.md` (`TRADE_SIMULATOR.md:17-25`) — **that path does not exist**. Real files live under `library/ross_cameron/` (`analyst_warrior_trading_strategy.md`, `all_content_structured.md`, `ROSS_CAMERON_TRADING_CANON.md`).  
   - Prompt says the north star is `all_content_structured.md`; the skill cites a different doc with different § numbering.  
   - Until you pick **one** alignment artifact, “traceable to the corpus” cannot be a checkable gate.

4. **v2.4 stop formula is a deliberate 1-min *translation*, not a pure quote.** Corpus (`all_content_structured.md:182-186`): stop = **low of the pullback candle, NOT the entry candle**. Skill (`TRADE_SIMULATOR.md:472-476`): `stop = min(trigger low, prior low) − $0.01`. That is a reasonable micro-structure proxy when the “pullback” is 1 bar; it is **not** identical to multi-bar base lows (armed path partially handles that via named base bars — `TRADE_SIMULATOR.md:502-507`). Don’t pretend objectification is pure fidelity; label it **operationalization** and require the citation + “how this maps.”

5. **Reproducibility-over-lottery is the right trade for *this* research goal** (discover a reliable rule-set an LLM can execute). It would be the wrong trade if the goal were “maximize one-run show-me equity.” State the objective explicitly in the playbook so future maintainers don’t re-litigate every tail.

---

## Proposed structure

### Files

| File | Role |
|---|---|
| `skills/MAINTAINING.md` | Keep ~current content. Add one top link: “Improving performance → `IMPROVING.md`.” Add: “Injected prompt changes in `batchsim.py` count as skill changes.” |
| `skills/IMPROVING.md` | **New** methodology playbook (outline below). |
| `skills/RULE_TRACE.md` | **New, lightweight** rule → corpus citation table (versioned with the skill; bump when rules change). |
| `skills/archive/` + `skill_versions.json` | Unchanged mechanics. |

Do **not** dump methodology into `TRADE_SIMULATOR.md`. That file is already ~784 lines / ~46k chars and is inlined into every batch agent prompt (`batchsim.py:256-258`). Methodology text in the skill would (a) burn tokens and (b) confuse the trader agent.

### `IMPROVING.md` — concrete outline to write

```
# Improving TRADE_SIMULATOR performance

## 0. Objective (one paragraph)
  - Primary: raise **effective expectancy in R** on held-out setups,
    under flat $ risk budget, while remaining a faithful operationalization
    of the Cameron corpus.
  - Explicit non-goals: maximizing max-R lottery tickets; gaming clean-only
    stats by voiding/standing down losers.

## 1. North star & sources of truth
  - Single alignment corpus (pick ONE path; fix skill § refs).
  - RULE_TRACE.md is mandatory for every behavioral edit.
  - Divergence from corpus requires a written “operationalization note.”

## 2. What may be changed
  - Skill rules (versioned).
  - Batch harness prompt only with version bump (MAINTAINING already says this).
  - Not: post-hoc re-labeling of voids to change rankings.

## 3. Design philosophy (the working heuristic)
  - Prefer replacing subjective decisions with formulas over revealed bars.
  - Prioritize decisions that multiply R (entry timing, stop → size, free-trade).
  - Prefer tighter losers and higher median/mean over fatter right tail.
  - One hypothesis per version bump (minor). Bundle only if inseparable.

## 4. How to choose the next change
  - Mine disagreement (see §8 tooling).
  - Read losing leaves + high-Δ leaves in the viewer.
  - Classify: ambiguity / missing rule / misapplied rule / infra void / luck.
  - Rank by estimated impact on R variance × frequency.

## 5. Edit protocol
  - Write hypothesis (1–3 sentences) in CHANGELOG section of IMPROVING or RULE_TRACE.
  - Patch TRADE_SIMULATOR.md; hand-set minor version for behavioral changes.
  - Update RULE_TRACE citations.
  - Diff against previous archive snapshot before running batch.

## 6. Test protocol (promotion gate) — checklist
  [see next section]

## 7. Holdout discipline
  [see overfitting section]

## 8. Tooling commands (copy-paste)
  - batchsim run / audit / report
  - batchsim compare (to build)
  - recorder report --batch TAG (not bare --by-version for promotion)

## 9. When to stop / when to major-bump
  - Diminishing returns: |mean ΔR| < 0.05 and non-significant for two iterations.
  - Major bump: strategy rethink (e.g. abandon small-account profile, change fill model).

## 10. Known failure modes (lessons 2.0→2.4)
  - 30-set + single outlier
  - mixed --by-version table
  - feel-call stop/size
  - holdout contamination
```

Keep versioning details in `MAINTAINING.md` only.

---

## Answers to the eight questions

### 1. Structure & scope

**Sibling `IMPROVING.md` + thin `MAINTAINING.md`.** Absorbing methodology into `MAINTAINING.md` couples two audiences (versioning implementers vs. strategy researchers) and grows past scannability. A sibling also lets you link from `TRADE_SIMULATOR.md`’s tooling note without bloating the agent-facing skill.

Section outline: as above.

### 2. Test rigor — minimum defensible promotion protocol

Write this checklist into `IMPROVING.md` and refuse to promote without it:

**Unit of observation**

- One planned testset slot = one observation key: `(ticker, historical_date)`.
- If `--repeats > 1`, primary R for the key = **mean of non-void repeats**; also report **std across repeats** (LLM noise).
- If multiple leaves exist for the same key under one batch (retries), **do not** average silently in promotion — pick the first complete non-void or mean-of-repeats with an explicit rule. (v2.2.1 batch shows this is real: 27 dups.)

**Populations**

| Role | Set | Use |
|---|---|---|
| Dev | e.g. first 70 of `testset_100` **or** a dedicated `testset_dev.json` | Inspect freely, form hypotheses, iterate |
| Validation | locked 30 (or separate seed, non-overlapping keys) | **Report-only**; never open `decisions.json` while iterating |
| Smoke | `testset.json` (30) or `testset_mini.json` | Syntax/behavior sanity only — **never promote from this** |

Today both testsets share seed 13 (`testset.json` n=30, `testset_100.json` n=100) — the 30-set is almost certainly nested in the 100. Treat the 30-set as smoke only.

**Metrics for a candidate version V vs baseline B (same model, same testset file)**

1. **Primary (promotion):** paired **effective** ΔR  
   - effective R: traded → `pnl.r_multiple` (budget-R is fine as primary while risk budget is fixed at $40; also report `r_multiple_actual` as secondary per prior metrics review)  
   - stood-down → **0R**  
   - void / out-of-credits → **exclude from pair** *or* assign a fixed penalty (recommend **exclude from primary pair, but report void rate as hard guardrail**)
2. **Guardrails (any fail = no promote):**  
   - void rate ≤ baseline + 5pp (and absolute void rate < 5% preferred)  
   - avg loser (clean traded) not worse by > $3 (or > 0.1R)  
   - p10 effective R not worse by > 0.15R  
   - stood-down rate change is **noted**, not gamed: a version that stands down all losers can look great on clean avgR — effective R catches this
3. **Statistics:**  
   - n_pairs ≥ 80 non-void keys on the 100-set (or full planned set)  
   - report: mean ΔR, median ΔR, % better / worse / |ΔR|<0.05  
   - **two-sided sign test on non-ties** (or paired bootstrap CI on mean ΔR)  
   - **Promotion bar:** mean ΔR > 0 **and** (sign-test p < 0.05 **or** bootstrap 95% CI on mean ΔR excludes 0) **and** guardrails pass  
   - **Weak accept (optional label, not default promote):** mean ΔR > 0.1, p < 0.10, guardrails pass — flag as “provisional,” requires validation set confirm
4. **Repeats:**  
   - Ideal: `--repeats 2` on validation after a candidate wins on dev once. Costly; if budget-constrained, do repeats only on the **top 20 highest |R| or highest inter-run disagreement** setups, not the full 100×2.  
   - Minimum without repeats: accept only if effect is **broad** (sign test), not driven by ≤3 leaves (report top-5 ΔR contributors; if >50% of sum(ΔR₊) from ≤3 keys, reject as tail-driven).

**Hard ban**

- Promoting from bare `report --by-version` without `--batch`.
- Promoting from n≈30 alone.
- Promoting a pure prose / hygiene edit that didn’t intend behavior change without verifying hash + “no behavior expected.”

### 3. Metric of record

Given **flat per-trade risk, independent leaves, no compounding** (correct framing in `2026-07-06-session-metrics/proposal.md` and Claude’s review):

| Priority | Metric | Why |
|---|---|---|
| **Primary** | **Effective expectancy in budget-R** = mean R over all *planned non-void* leaves (stood-down = 0) | Matches deployment: skipping is neither free alpha nor free to ignore; prevents survivor bias from selective stand-downs |
| **Co-primary for diffs** | **Paired mean ΔR (effective)** on shared keys | Controls setup luck; this is what made v2.4 vs 2.2.1 trustworthy |
| Secondary | Clean expectancy (traded only), win%, profit factor (R), median R, p10/p90 | Distribution shape; PF for asymmetry |
| Secondary | `r_multiple_actual` expectancy | True R on risk taken; use when stop/size policy changes |
| Guardrail | avg loser $, void%, forced_exit%, MFE-capture on wins | Risk of “tighter stops that get wicked” vs “lottery stops” |
| Explicitly **not** primary | Raw P&L alone, max R, SQN as headline, portfolio MDD | P&L ≈ R when budget fixed but is less comparable if budget changes; max R is luck; SQN conflates N with edge; MDD is undefined without fake ordering |

**Enshrine:** *“A version is better iff paired effective mean ΔR clears the significance bar and guardrails hold.”* Win% and P&L are commentary.

Also fix reporting: `report_by_version` currently uses only clean traded R (`recorder.py:1462-1489`) and drops stood-downs from the mean — fine as a *secondary* line, fatal as the only line. The playbook should say: always print **effective** and **clean** side by side (as the metrics proposal already concluded).

### 4. Overfitting / generalization

Honest assessment: **the 100-set is already semi-contaminated.** You inspected leaves, tuned v2.3/v2.4 language against failure modes you saw, and re-ran the same keys. That does **not** invalidate the paired sign-test (still evidence of a real within-sample effect); it **does** mean reported edge is an upper bound for live generalization.

**Discipline you can actually follow (cheap → better):**

1. **Immediate (no new recordings needed):** Split `testset_100.json` deterministically into:
   - `dev` = keys with `hash(ticker|date) % 10 < 7` (≈70)
   - `val` = the rest (≈30), **locked**  
   Commit the split lists. Rule: while editing the skill, you may open `decisions.json` **only for dev keys**. Val is numbers-only until freeze.
2. **Promotion:** Candidate must pass the §2 gate on **dev** first; then run (or reuse) batch on **val** once. Promote only if val mean ΔR ≥ 0 and not catastrophic on guardrails. With n_val≈30, require **directionally positive** + no guardrail break, not p<0.05 alone.
3. **Next recordings:** `build-set` with a **new seed** and **exclude all keys ever used in testset_100** → `testset_oos.json`. That becomes the true OOS when entries.db grows.
4. **Process rule in the doc:** “If you looked at a leaf’s chart/decisions to form the hypothesis, that leaf is **dev**, never val.”
5. **Label all published tables:** `SELECTED_AGAINST=dev|full100|oos` and skill version + batch tag + model.

Do **not** pretend you still have a pure holdout on the full 100. Document the contamination; don’t launder it.

### 5. Alignment enforcement — make it checkable

**Pick one SOFT:**

Recommend **`library/ross_cameron/ROSS_CAMERON_TRADING_CANON.md`** as the short check surface (158 lines, deduped), with `all_content_structured.md` as the deep backup for ambiguous citations. Fix skill text to point at real paths (today’s `library/analyst_warrior_trading_strategy.md` is broken).

**Artifact: `skills/RULE_TRACE.md`**

Minimal table, updated on every minor bump:

| Skill rule (stable id) | Skill location | Corpus cite | Operationalization note | Since |
|---|---|---|---|---|
| `entry.trigger_bar` | §A “Which bar is the breakout?” | Canon / structured §3.1 first new high | 1-min closed-bar checklist proxy for 5-min ACD | 2.3.0 |
| `stop.initial_formula` | §A “Where the stop goes” | Structured §3.1 stop = pullback low | min(trigger, prior)−0.01; multi-bar base via arm path | 2.4.0 |
| `manage.free_trade` | §B.3 | Structured §4 “10 cents… free trade” | +$0.10 or +1/3 stop_distance | … |

**Gate on PR / edit:**

1. New/changed behavioral rule → new/updated RULE_TRACE row.  
2. Citation must be a real heading or quote, not “vibe.”  
3. If the formula **narrows** Cameron’s discretion (e.g. forbids tight stops under fill), the operationalization note must say **why** (LLM reproducibility / small-account structure) so future maintainers don’t “fix fidelity” by reintroducing noise.  
4. Optional lightweight check: grep skill for `§` refs and assert targets exist in the chosen doc (the current §4.6 / §9 / §18 map to `analyst_warrior…`, not `all_content_structured` TOC — another reason to unify).

This is cheap and high leverage. Full formal verification is overkill.

### 6. Finding the next change — systematic disagreement mining

Yes — and it belongs in **tooling first**, **doc second**.

v2.3/v2.4 wins came from noticing that **the same bars produced opposite narrative labels** (“breakout” vs “extended”; “structural stop” vs “tight under fill”). That is **inter-run disagreement**, not mean P&L.

**Practical pipeline (implement as `batchsim mine-disagreement` or a script):**

1. Run version V with `--repeats 2` (or compare two historical leaves of same version/setup when dups exist).  
2. For each setup, align by bar index `i` on `decisions.json`.  
3. Flag bars where `action` differs, or where `stop` / `fill_px` / ENTER timing differ.  
4. Cluster by **rule family** using note/thought keywords or structured fields:  
   - entry trigger bar index  
   - initial stop price  
   - free-trade BE move  
   - soft-bailout reason  
   - scale level choice  
   - §C re-entry yes/no  
5. Score cluster by **contribution to R variance** across repeats × frequency.  
6. Highest score → next objectification candidate.

**Where subjectivity still lives in v2.4.0** (read from skill + batch actions):

| Surface | Evidence | Priority |
|---|---|---|
| Soft bailout OR-chain (failed break / VWAP / topping tail / MACD / time) | `TRADE_SIMULATOR.md:538-573` multi-clause; EXIT notes vary | **High** — objectify order + predicates |
| Free-trade timing on armed fill bar | 5/87 first ENTERs logged BE stop equal to fill (BQ, YDKG, DXST, …) | **High** — formula: when may stop jump to BE on the fill bar? |
| “A+ bar” late morning | `~10:30–11:00` + “well clear of VWAP” (`:450-455`) | Medium |
| Grade B “decisively” / “borderline” | Step 0.5 (`:212-220`) | Medium |
| Scale “or first clear resistance” | (`:583-588`) | Medium |
| Optional pyramid “conviction” | (`:543`, `:618-629`) | Lower frequency (ADD rare) |
| Runner trail “major 5-min swing / ema20” | (`:612-617`) | Medium for MFE-capture |

Doc should say: **do not invent the next rule from intuition about Cameron; invent it from the top disagreement cluster, then check Cameron.**

### 7. Reproducibility vs upside — was killing the +30R tail right?

**Yes, under the stated research objective.**

- A +30R from a **noise-tight stop** is mostly **size leverage on a random non-stop**, not skill edge. Share count is `risk_budget / stop_distance` (`TRADE_SIMULATOR.md:696-700`); tightening stop 10× is a 10× size bet that the path won’t touch noise. That is not Cameron’s “stop at the pullback low” (`all_content_structured.md:182-186`); it is accidental optionality.
- Your measured v2.4 result: higher mean R, better paired sign test, **no need for the lottery** to win. Losers still ~−1R capped by budget. That’s what a small-account momentum system should look like (corpus: ~1:1 avg win/loss, edge from win rate — `all_content_structured.md:304-308`).
- **When not to objectify further:** if a formula **systematically** cuts the left tail **and** the right body of *legitimate* runners (e.g. free-trade to BE so early that normal 1-min noise scratches winners that Cameron would hold). Watch **MFE-capture** and **median R** as guardrails. If median falls while mean flat and max collapses, you over-smoothed.
- **Objective for future tradeoffs:** maximize **paired effective mean R** subject to (void low, p10 R not worse, MFE-capture not collapsing). Do **not** maximize max(R).

One nuance: corpus free-trade is “+10¢ in the first minute” (`all_content_structured.md:294`). Skill allows +$0.10 **or** +⅓ stop_distance on first bar or two (`TRADE_SIMULATOR.md:574-578`). On wide stops, ⅓ distance is larger than 10¢ → slower BE; on tight stops, 10¢ may be larger than the whole risk. That’s a reasonable operationalization — keep it cited, and verify with disagreement mining whether agents still freestyle BE on the fill bar (they do).

### 8. Blind spots / missed opportunities

These are the items the prompt’s framing underweights:

1. **Reporting contamination is a first-class bug.** Mixed `report --by-version` will keep causing false “regressions.” Fix code + doc together.

2. **Skill context bulk may now dominate residual error.** ~46k characters of rules inlined every run. LLMs miss mid-prompt constraints. After objectifying entry/stop, the next performance lever may be **compressing the skill** (move hygiene/shell novels out of the inlined body for batch mode — batch already strips setup duties in `batchsim._prompt`, but still pastes the entire skill including Step 0/1/4 viewer ops). Consider a **`TRADE_SIMULATOR.batch.md`** slim profile that is a *generated* projection of the same versioned rules (hash-linked), not a second hand-edited truth.

3. **Timeframe mismatch is unresolved strategy risk.** Cameron’s flagship ACD is **5-minute first new high** (`all_content_structured.md:177-180`); the sim is **1-minute** with 5-min only for runner exit (`TRADE_SIMULATOR.md:593-611`). Objectifying 1-min checklists can create a coherent **1-min dialect** of Cameron that is still not his primary chart. `IMPROVING.md` should either (a) accept “1-min operationalization of 5-min ACD” as explicit scope, or (b) prioritize experiments that gate entry on completed 5-min structure. This is a larger fork than another stop tweak.

4. **Soft bailout is the next variance dragon.** Entry/stop are now formulas; manage step 2 is still a prose OR-list. Many exits in the 023823 batch are soft bailouts one bar after entry (MTEN, MBRX first legs) — correct for “breakout or bailout,” but the *which clause fired* and *when* still looks narrative. Objectify with a strict priority list and boolean predicates (you already have a priority list at `:536-544` — make each predicate as crisp as the stop formula).

5. **§C re-entry is ~neutral on average in v2.4 batch** (17 multi-enter leaves, avg R ≈ 0.63 vs ≈ 0.63 for single-enter). That does **not** mean delete it (corpus favorite), but it means **don’t invest iteration budget there** until entry/manage variance is lower. Multi-enter also doubles fee/token cost and bailout noise.

6. **No model dimension in the skill playbook.** `batchsim` pins `--model`. A skill “improvement” that only works on one model is a model–prompt interaction. Require reporting model id next to version; don’t promote a skill change tested on a different model than production.

7. **Fill model vs Cameron tape.** Intra-bar hard stops / touch scales (`TRADE_SIMULATOR.md:336-351`) are reasonable, but they interact with objectified stops: wide structural stops get hit less often on noise, tight ones more. Keep fill assumptions fixed while skill-testing; changing fill model is a **major** version, not a minor rule tweak.

8. **Archive is good; experiment log is missing.** Immutable `TRADE_SIMULATOR@v.md` recovers *what* rules ran, not *why* you changed them or which batch proved it. Add a short `skills/CHANGELOG.md` (or section in IMPROVING) with: version, hypothesis, batch tag, paired ΔR, promote/revert. Without this, future AIs will re-try failed ideas.

---

## What `MAINTAINING.md` should say even if the bottleneck is elsewhere

If you only patch `MAINTAINING.md` and skip `IMPROVING.md`, still add this block at the top:

```markdown
## Improving trading performance

Versioning alone does not improve expectancy. Before editing TRADE_SIMULATOR.md
for a behavioral change, follow skills/IMPROVING.md (hypothesis → objectify →
paired batch gate → RULE_TRACE citation).

Never rank skill versions from a mixed `recorder report --by-version` table.
Rank only within one batch tag (or via `batchsim compare`) on a fixed testset,
using paired effective R. See IMPROVING.md §Test protocol.
```

That single redirect prevents the most expensive failure mode: **false confidence from the wrong report**.

---

## Suggested implementation order (performance per unit work)

1. **Docs:** `IMPROVING.md` + RULE_TRACE skeleton + fix broken corpus path in skill (path fix may warrant patch bump only if agents never open the file mid-run — still do it for maintainers).  
2. **Tooling:** `batchsim compare --a TAG --b TAG` (paired effective R, sign test, top Δ contributors, void rates).  
3. **Report fix:** `report --by-version` print effective vs clean; warn when multiple batches/models mixed.  
4. **Holdout split:** commit dev/val key lists from testset_100.  
5. **Next skill edit:** mine soft-bailout / free-trade disagreement; objectify one surface; run promotion gate.  
6. **Later:** slim batch skill projection; OOS `build-set`; optional 5-min entry experiment as major if 1-min dialect saturates.

---

## Verdict on the v2.4 philosophy

The v2.3→v2.4 arc is the correct research program: **reduce LLM degrees of freedom on R-critical decisions while staying inside Cameron’s skeleton.** The missing piece is not another narrative paragraph in the skill — it is a **written promotion science** plus **compare/disagreement tools** so the next objectification is chosen and accepted for the right reasons.

If `MAINTAINING.md` only grows versioning detail, you will keep shipping better archives of the same tribal process. Expand methodology in `IMPROVING.md`, keep versioning thin, and make the harness refuse to lie.
)
