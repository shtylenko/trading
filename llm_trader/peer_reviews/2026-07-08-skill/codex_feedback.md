# Codex feedback: skill improvement methodology

**Date:** 2026-07-08  
**Reviewer:** Codex  
**Target:** `llm_trader/skills/MAINTAINING.md` and the skill-improvement loop

## Executive view

The highest-leverage change is to turn `MAINTAINING.md` into the owner manual for **both** version integrity and experimental method. Keeping it as a pure versioning note would preserve the current failure mode: the only document every editor is told to read explains auto-bumps and archives, but not how to make or accept a trading-rule change. Today it explicitly covers byte-change bumps, archive immutability, and registry mechanics, and stops there (`llm_trader/skills/MAINTAINING.md:7`, `llm_trader/skills/MAINTAINING.md:24`, `llm_trader/skills/MAINTAINING.md:42`, `llm_trader/skills/MAINTAINING.md:49`).

The doc should add three things before any future rule iteration:

1. **A rule-change thesis template:** every change must name the ambiguous/high-variance decision it is fixing, cite the Cameron corpus, and define the expected behavioral delta before editing the skill.
2. **A minimum acceptance protocol:** paired, fixed-setup evaluation; 100-set as the floor for a promoted version; repeats on a targeted disagreement subset; primary statistic is paired effective expectancy in R with confidence interval/sign test, not a lone avg-R table.
3. **A contamination policy:** split development and locked validation sets. The current `testset_100.json` is useful, but once maintainers inspect runs and tune against it, it is no longer a real holdout.

## 1. Structure and scope

Use one file: `MAINTAINING.md`. Rename the title to something like **Maintaining and Improving TRADE_SIMULATOR**. A sibling `IMPROVING.md` would be cleaner academically, but it is worse operationally: the current simulator warns editors to see `MAINTAINING.md` when changing rules (`llm_trader/skills/TRADE_SIMULATOR.md:8`), and the versioning doc is already the mandatory stop for AI/code editors (`llm_trader/skills/MAINTAINING.md:7`). Put the methodology where editors cannot miss it.

Suggested outline:

1. **Purpose:** this file governs edits to the trading skill and the evidence needed to accept them.
2. **Versioning and archive mechanics:** keep the current content, but move it after the methodology summary.
3. **Change thesis required before editing:** hypothesis, affected skill section, corpus citations, expected behavior, expected failure mode, and success metric.
4. **Alignment gate:** rule-to-corpus trace table and required citations for every behavioral rule.
5. **Design principle:** remove subjective degrees of freedom only when the formula is a faithful operationalization of Cameron, not a fitted parameter.
6. **Evaluation protocol:** dev set, locked validation set, repeats, paired comparison, bootstrap/sign-test, required report fields.
7. **Decision rules:** accept, reject, or investigate; how to handle metric improvement with alignment drift.
8. **Post-run review:** disagreement mining, variance hotspots, next-change backlog.
9. **Version bump/archive mechanics:** current auto-bump/hash/archive rules.

## 2. What to change next

Systematize the process that produced v2.3/v2.4. The skill now defines the trigger bar as the first revealed bar where every entry checklist box is true (`llm_trader/skills/TRADE_SIMULATOR.md:373`, `llm_trader/skills/TRADE_SIMULATOR.md:382`) and defines stop placement with a mechanical two-bar formula (`llm_trader/skills/TRADE_SIMULATOR.md:466`, `llm_trader/skills/TRADE_SIMULATOR.md:472`). That is the right class of improvement because those rules reduce LLM interpretation variance at high-impact decision points: entry timing and stop distance drive fill price, share count, and R.

Make that repeatable:

- Run 3-5 repeats on a smaller **diagnostic set** of setups where prior versions diverged.
- Mine each repeated setup for first divergence: first `ENTER`, first `EXIT`, initial stop, stand-down/trade choice, re-entry choice, and runner exit.
- Rank candidate changes by `variance contribution = within-setup std(R) + frequency of decision disagreement + average absolute R swing after disagreement`.
- Only then write a rule thesis. Do not start from “what prose can we add?” Start from “which repeated-state decision is unstable and expensive?”

This belongs in `MAINTAINING.md`; tooling can come later. The existing harness already supports repeats (`llm_trader/batchsim.py:516`, `llm_trader/batchsim.py:599`, `llm_trader/batchsim.py:616`), exact setup pinning (`llm_trader/batchsim.py:590`), and pinned archived versions (`llm_trader/batchsim.py:562`, `llm_trader/batchsim.py:567`). The doc should tell maintainers when to use those capabilities.

## 3. Minimum defensible acceptance protocol

For a behavioral rule change:

1. **Pre-register the hypothesis** in a short note before running the acceptance batch.
2. **Run paired batches:** old accepted version vs candidate version on the same setup list, same model, same repeat count, pinned archived skill versions.
3. **Use the 100-set as the minimum acceptance set**, not the 30-set. The committed 30-set has `n: 30` (`llm_trader/batch/testset.json:4`); the larger set has `n: 100` (`llm_trader/batch/testset_100.json:4`). The 30-set is only for smoke tests and diagnostics.
4. **Use paired per-setup deltas** as the main comparison: `delta_R = candidate_effective_R - baseline_effective_R` on matching `(ticker,date,repeat)`.
5. **Require robustness, not just mean lift:** median delta non-negative, sign test or paired bootstrap supports improvement, and the lift is not explained by one tail trade. A practical bar: paired mean effective delta `> +0.15R`, bootstrap 95% CI lower bound `> 0` or two-sided sign-test `p < 0.05`, and no single setup contributes more than one third of total delta.
6. **Repeat policy:** one repeat over all 100 is a floor when cost is tight. Add 3-5 repeats on the top disagreement/variance subset before accepting a rule that touches entry, stop, bailout, or re-entry.
7. **Report clean and effective metrics:** clean traded-only results are diagnostic; effective results are the acceptance metric.

The current `report_by_version` excludes stood-down and voided runs from win/P&L/R (`llm_trader/recorder.py:1425`, `llm_trader/recorder.py:1459`, `llm_trader/recorder.py:1462`, `llm_trader/recorder.py:1486`). That is fine for “how did trades perform?” but not enough for “is this version better on presented setups?” A stricter version that stands down more often can look better on clean avg-R while producing less opportunity. `MAINTAINING.md` should require an “effective R per planned setup” view: traded runs use final R, stood-down runs are `0R`, audit voids are excluded from statistical inference but counted as a reliability failure or penalized in deployment scoring.

## 4. Metric of record

Primary metric: **paired effective expectancy in budget R per planned setup**.

Why budget R: the simulator uses a flat risk budget (`llm_trader/skills/TRADE_SIMULATOR.md:696`) and records final R as realized dollars divided by that budget (`llm_trader/skills/TRADE_SIMULATOR.md:709`). With no compounding portfolio and one setup at a time, expectancy in R is the cleanest objective. P&L is useful because buying power constraints matter, but P&L is not as portable across price/stop regimes.

Guardrails:

- Clean expectancy R over traded non-void runs.
- Win rate, average winner, average loser, and profit factor.
- Median R and p10/p90 R so a single right-tail run cannot hide a weak center.
- Stood-down rate and void/out-of-credit rate.
- MFE capture on winners as a management diagnostic, not a ranking metric. The current report already averages capture only over winners because loser capture is misleading (`llm_trader/recorder.py:1469`, `llm_trader/recorder.py:1472`, `llm_trader/recorder.py:1489`).

Do not make raw win rate the primary metric. Cameron's corpus says the edge is tight losses, selection, and enough win rate, not win rate alone (`library/ross_cameron/all_content_structured.md:78`, `library/ross_cameron/all_content_structured.md:79`, `library/ross_cameron/all_content_structured.md:427`).

## 5. Alignment enforcement

Add a lightweight `Rule Traceability` section or table in `MAINTAINING.md`, and require every new behavioral change to update it. Columns:

- Skill section/rule.
- Rule type: direct corpus rule, operationalization, simulator constraint, or empirical guardrail.
- Corpus citation(s).
- Implementation notes.
- Known tradeoff.
- Last version changed.

Examples from current rules:

| Skill rule | Type | Corpus support | Review note |
|---|---|---|---|
| 5-pillars grade gate | direct + operationalized | 5 pillars and thresholds (`library/ross_cameron/all_content_structured.md:106`, `library/ross_cameron/all_content_structured.md:110`, `library/ross_cameron/all_content_structured.md:120`, `library/ross_cameron/all_content_structured.md:124`, `library/ross_cameron/all_content_structured.md:132`) | Current skill measures four available pillars and uses C hard gates (`llm_trader/skills/TRADE_SIMULATOR.md:202`, `llm_trader/skills/TRADE_SIMULATOR.md:221`). Document catalyst/rate-of-change as unavailable or inferred. |
| ACD/first-new-high entry | direct + operationalized | first candle new high, immediate trigger (`library/ross_cameron/all_content_structured.md:176`, `library/ross_cameron/all_content_structured.md:180`) | v2.4's “first checklist-valid bar” is an operationalization; keep it only if it reduces ambiguity without contradicting immediate entry. |
| Stop formula | operationalization | low of pullback/structure (`library/ross_cameron/all_content_structured.md:182`, `library/ross_cameron/all_content_structured.md:186`, `library/ross_cameron/all_content_structured.md:1193`) | The exact `min(trigger low, prior low)-0.01` formula is not directly in the corpus; it should be marked as a 1-min-feed translation, not a Cameron quote. |
| Breakout-or-bailout | direct | immediate resolution and 1-2 bar bailout (`library/ross_cameron/all_content_structured.md:256`, `library/ross_cameron/all_content_structured.md:258`, `library/ross_cameron/all_content_structured.md:263`, `library/ross_cameron/all_content_structured.md:271`) | Strongly aligned with current manage sequence (`llm_trader/skills/TRADE_SIMULATOR.md:534`, `llm_trader/skills/TRADE_SIMULATOR.md:551`). |
| Scale in/out | direct | scaling into winners and thirds exits (`library/ross_cameron/all_content_structured.md:80`, `library/ross_cameron/all_content_structured.md:286`, `library/ross_cameron/all_content_structured.md:609`) | Current thirds plan is aligned (`llm_trader/skills/TRADE_SIMULATOR.md:581`). |
| Sub-VWAP trap re-entry | direct | favorite intraday setup and reclaim/stop rules (`library/ross_cameron/all_content_structured.md:248`, `library/ross_cameron/all_content_structured.md:512`, `library/ross_cameron/all_content_structured.md:519`, `library/ross_cameron/all_content_structured.md:520`) | Current §C is aligned (`llm_trader/skills/TRADE_SIMULATOR.md:639`, `llm_trader/skills/TRADE_SIMULATOR.md:661`). |

This is the line between “removing ambiguity” and “encoding our judgment”: a formula is acceptable when it is a declared operationalization of a cited rule and is tested for generalization. It is not acceptable when it is just the best-performing threshold on the known 100-set.

## 6. Overfitting and holdout discipline

The 100-set should now be treated as contaminated for model/skill selection if maintainers have inspected its winners/losers and edited rules from them. `batchsim.build_set` creates deterministic stratified samples from `entries.db` (`llm_trader/batchsim.py:156`, `llm_trader/batchsim.py:161`, `llm_trader/batchsim.py:188`), and the committed sets use the same seed 13 (`llm_trader/batch/testset.json:3`, `llm_trader/batch/testset_100.json:3`). That makes comparisons repeatable, but it also makes overfitting easy.

Practical policy:

- **Dev set:** one or more known sets that maintainers may inspect in the viewer, mine for disagreements, and use for rule design.
- **Locked validation set:** a separate committed set, different seed and preferably non-overlapping `(ticker,date)`, used only after the rule thesis is frozen. Do not inspect leaf decisions on this set until after accept/reject.
- **Fresh-forward set:** when new recorded setups arrive, reserve the newest dates for a validation refresh. Prefer date-forward validation where feasible.
- **Quarantine rule:** if a setup is cited in a rule thesis or manually inspected to design the rule, it cannot be counted as locked validation evidence for that rule.

This is more important than adding more metrics. Richer reports make it easier to tune to noise unless the doc defines which set is allowed for discovery and which set is allowed for evidence.

## 7. Reproducibility versus upside

Removing the +30R lottery tail by objectifying the stop is directionally right **if** the removed tail came from an invalid or non-reproducible interpretation. Cameron's own framing supports speed, scaling, and runners, but also tight risk control and losing less (`library/ross_cameron/all_content_structured.md:78`, `library/ross_cameron/all_content_structured.md:79`, `library/ross_cameron/all_content_structured.md:1215`, `library/ross_cameron/all_content_structured.md:1223`). A tail that depends on a stop inside normal bar noise is not an edge; it is an artifact of share inflation.

But do not encode “variance reduction” as an unconditional goal. The strategy is supposed to have right-tail runners. v2.4 still allows runners through scale-outs and 5-minute runner management (`llm_trader/skills/TRADE_SIMULATOR.md:589`, `llm_trader/skills/TRADE_SIMULATOR.md:593`), and real batch examples show the rules can still print multi-R outcomes after bailouts/re-entries. For example, the current batch had RNAZ at +4.89R and BQ at +3.89R in `pnl.json` on batch `20260708181528-BATCH-023823` (read from `llm_trader/simulations/20260708181530-RNAZ-84cf12/pnl.json` and `llm_trader/simulations/20260708181528-BQ-272065/pnl.json`).

The acceptance question should be: does the change reduce **invalid path variance** while preserving **valid strategy convexity**? If yes, take it. If it clips valid runners just to make the distribution prettier, reject it.

## 8. Biggest blind spots

First blind spot: the current primary report does not distinguish clean expectancy from deployment expectancy. Because stood-down sessions are counted as notes but excluded from avg-R/P&L/win% (`llm_trader/recorder.py:1462`, `llm_trader/recorder.py:1507`), a future rule could improve clean avg-R by refusing marginal but profitable trades. The doc should require both clean and effective metrics in every acceptance report.

Second blind spot: exact formulas are being added inside the trading skill faster than the corpus-trace machinery. The stop formula is plausible and useful, but it is more specific than Cameron's text. That is okay only if the trace table explicitly labels it as an operationalization of the low-of-pullback rule, not as a direct teaching.

Third blind spot: model stochasticity is the actual experimental unit problem. One run per setup cannot separate “rule is better” from “agent sampled better reasoning.” The harness already has `repeats`; `MAINTAINING.md` should make repeats mandatory for high-variance rule areas and should define disagreement mining as the normal way to choose the next change.

## Acceptance checklist to paste into `MAINTAINING.md`

Before editing:

- [ ] Name the decision instability or corpus gap.
- [ ] Cite the relevant skill lines and Cameron corpus lines.
- [ ] State whether the change is direct corpus, operationalization, simulator constraint, or empirical guardrail.
- [ ] Define expected behavioral delta and expected metric movement.
- [ ] Pick dev setups for inspection; do not use locked validation for discovery.

Before accepting:

- [ ] Candidate and baseline are pinned archived versions.
- [ ] Same model, same setup set, same repeats, same batch protocol.
- [ ] 100 planned setups minimum for promotion, unless this is only a patch/hygiene fix.
- [ ] Paired effective expectancy R improves; clean expectancy does not mask worse deployment expectancy.
- [ ] Median delta and sign count support the mean; no single tail explains the result.
- [ ] Guardrails are not worse: avg loser, void rate, stood-down rate, and MFE capture reviewed.
- [ ] Rule trace table updated with corpus citations and operationalization notes.
- [ ] Result recorded with batch IDs, model, testset path, repeats, and accept/reject decision.

Bottom line: keep the recent objectification pattern, but discipline it. The doc should teach maintainers to find high-variance subjective decisions, convert only corpus-grounded ambiguity into explicit rules, and accept versions only through paired, contamination-aware, effective-R evidence.
