# Evaluation-Pipeline Review

**Reviewer:** Claude (Opus 4.8) — one reviewer; run `prompt.md` through the others too.
**Date:** 2026-06-15
**Verdict on the verdict:** The "no robust edge" conclusion is *directionally*
defensible but **over-stated as currently framed**. The dominant risk in round 1 is
a **false negative from the 2-fold / 1-year-train walk-forward**, not overfitting.
PBO and WF are also measuring subtly different things, so citing them together as
one coherent verdict is shakier than it looks.

## Toughest questions (ranked by ability to change the conclusion)

1. **Is the walk-forward measuring "is there an edge?" or "is one-year-trained
   selection stable?" — because right now it's mostly the latter.** Fold 1 trains
   on **2022 alone** (a bear year) and selects `spy_weak_regime+adv_min_1m` — a
   combo tuned to bear conditions — then bleeds in 2023. The combo that's actually
   interesting (`gap_floor_3+rvol_min_1.5`) was *never selected* in fold 1, so it
   never got a fair OOS test in 2023. The "FAIL" is largely **selection variance
   from a 1-year training window**, conflated with "no edge." With 3 search years
   and expanding windows, fold 1 will always have a pathologically short train.
   **This is the single most likely false-negative mechanism.**

2. **The "positive in EVERY fold" rule + "each test year is a different regime" =
   you are demanding regime-invariance from a strategy whose own thesis is
   regime-conditional.** The gap-up thesis is literally "relative strength pays
   when the tape is weak." Requiring it to be positive in 2023 chop AND 2024 trend,
   selected from a model that can't see the test regime, may be the wrong bar. The
   pipeline cannot currently distinguish *no edge* from *regime-conditional edge
   tested in a regime-blind way*.

3. **PBO and the walk-forward rank combos on different metrics — so they don't
   form one coherent gate.** PBO's performance matrix uses **summed daily R**
   (volume-weighted, rewards high-trade-count combos); the WF selection uses
   **mean R per trade**. The "IS-best" in CSCV may not be the combo WF would pick.
   PBO=0.32 alongside WF-FAIL is presented as "not overfit, just unstable," but the
   two numbers are partly about different objects. Make PBO rank by the *same*
   objective the search uses, or stop presenting them as jointly conclusive.

4. **PBO is near-useless as a discriminator in the no-edge regime, and 0.32 may be
   mildly *contradicting* the WF fail.** When the true edge ≈ 0 everywhere,
   PBO → 0.5 by construction (IS-best is random OOS). Getting **0.32** — visibly
   below 0.5 — weakly implies the IS-best *does* tend to hold rank OOS, i.e. some
   persistent structure (plausibly the gap+rvol combo). So PBO is faintly arguing
   *against* "no edge," while WF says fail. That tension is unresolved and is
   currently being smoothed over.

5. **The objective is mean-R with only a trade-count floor — no consistency or
   risk term.** It will happily select a combo that is +0.3R one quarter and −0.1R
   for three over a steady +0.05R combo, as long as the mean wins and the count
   floor holds. For a strategy you want to be *reliable across regimes*, selecting
   on raw mean R almost guarantees the regime-fragile pick you then punish in WF.
   Self-inflicted instability.

6. **`top-10-after-filter` conflates two different effects.** A filter that drops
   high-gap names lets *lower-gap names that the top-10 cap would otherwise exclude*
   into the book. So a "filtered" combo is **not** "baseline minus bad trades" — it
   is a partially different basket (some removed, some newly promoted). The subset
   invariant on *realized R* still holds (independent sims), but the *interpretation*
   of why a combo helps is confounded by this promotion effect. Worth isolating:
   compare "filter with top-10" vs "filter without the cap" to see how much of the
   effect is the filter vs the reshuffled book.

## Hidden assumptions

- **That a single combo must work in all regimes.** Unstated; baked into "positive
  every fold." A regime-switching deployment (use the sector/SPY-weak combo only in
  weak tapes) is excluded by construction.
- **That independent per-trade simulation ≈ the real portfolio.** 10 same-morning
  gap-up longs are highly correlated (one tape). The 1%-risk/trade, no-concurrency-
  cap model **overstates return and understates drawdown**. *Important asymmetry:*
  this biases toward **false positives**, so a **negative** verdict is robust to it
  — if it can't win under the optimistic model, the realistic one is worse. State
  this explicitly; it's a point in the verdict's favor.
- **That 2022–2024 is "enough regimes."** Three years, two folds. The whole edifice
  rests on a tiny number of independent regime samples.
- **That the 9 fixed thresholds are representative.** The negative is "no edge in
  *this* 46-combo grid," not "no edge." gap_floor_2, rvol_2.0, or a feature not in
  the grid could differ. Framing is mostly right but should be louder.

## Failure modes, ranked

**False negative (kill a real edge) — the bigger risk here:**
1. 1-year fold-1 training → high-variance selection → spurious WF fail (Q1). HIGH.
2. All-folds-positive under regime-disjoint test years (Q2). HIGH.
3. mean-R objective selecting regime-fragile combos it then fails (Q5). MED.
4. Coarse grid misses the real threshold/feature. MED.

**False positive (bless an overfit combo) — if a future round "passes":**
1. 46 combos is modest, but k=3 (a planned round) explodes it; PBO must scale with
   the round, and the alpha-spending budget across rounds is the real exposure. MED.
2. PBO/WF metric mismatch (Q3) could let a volume-heavy combo look stable in PBO
   while being mean-R-fragile, or vice versa. MED.
3. `first_close_pos` contamination if it enters a passing combo. LOW.

## Leakage check (mostly clean)
No obvious leak in the described construction — point-in-time universe, strict
<09:35/prior-day slicing, split guards, independent labels. Two to verify:
- **Sector map provenance:** if ticker→sector ETF mapping is a *current* snapshot
  applied to 2022, that's a mild look-ahead (sector reclassifications). Confirm it's
  effective-dated.
- **Capture→ledger join** on `(session_id, ticker)` with `filled = entry_time
  not-null`: confirm no-fill candidates carry `realized_r = null` (not 0) so they
  don't dilute mean R as fake break-evens.

## The single highest-leverage change
**Add folds / get more independent regime samples, and separate "search" from
"confirm."** Concretely, two things:
1. Re-cast walk-forward as **leave-one-year-out** or **quarter-level expanding**
   folds so selection isn't hostage to a 1-year bear-only training window, and so a
   combo good in 2 of 3 years isn't auto-killed.
2. Treat `gap_floor_3+rvol_min_1.5` as a **specific pre-registered hypothesis** and
   run a **fixed-combo** (no per-fold re-selection) walk-forward on it across all
   windows + the sealed 2025. This is *confirmatory*, not goalpost-moving, **iff**
   you pre-register it as a distinct round and accept its OOS result as binding.
   The search said "no stable *selection*"; it did not cleanly test "does this one
   thesis-backed combo hold." Those are different questions and only the first was
   answered.

## Bottom line
The machinery is sound and the discipline (sealed OOS, locked grid, PBO, no
p-hacking) is genuinely better than what fooled this project before. But round 1's
"no robust edge" mostly demonstrates **"no robustly *auto-selectable* combo under a
2-fold, 1-year-train, regime-disjoint, mean-R protocol."** That is weaker than "the
family has no edge." Before retiring gap-and-go, run the confirmatory fixed-combo
test on gap+rvol against 2025, and report PBO computed on the same objective the
search optimizes. If *that* fails too, the kill is earned.
