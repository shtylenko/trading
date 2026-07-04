# Peer Review: Feature-Capture & Combinatorial-Search Evaluation Pipeline

I've gone through this with the most adversarial lens I can bring. Below are my findings, organized by your explicit asks, with concrete failure modes and scenarios.

---

## 1. The 10 Toughest Questions (Before Trusting the Verdict)

1. **Why is the selection criterion "best on train" rather than "most stable across bootstrap samples of train"?** On single-year training windows (especially 2022, a bear market), the max-mean-R selector is a high-variance estimator. A stability-based selector (e.g., the combo that ranks in the top-3 most often across 1,000 block-bootstrap resamples of the training window) would favor combos that are robust to data perturbations rather than over-optimized to a specific regime. This alone could flip the fold-1 result.

2. **What would the walk-forward look like if you pooled selection across 2022–2023 and tested on 2024, then validated on the sealed 2025?** The current 2-fold design confounds selection noise with regime shifts. A pooled-selection WF would answer a different (and arguably more relevant) question: "Is there ONE filter combo that works across multiple regimes, when selected using multiple regimes of data?"

3. **If you ran the CSCV PBO separately for each year (2022 vs 2023+2024, etc.), does the overfitting probability spike in the bear-market year?** PBO=0.32 across the full window might mask that selection is severely overfit in some regimes and genuinely informative in others. Regime-conditional PBO would tell you whether the IS ranking is regime-stable or regime-fragile.

4. **Why is the top-10 cap applied AFTER the filter rather than scored on the unfiltered top-10 as a control?** A filter that removes high-gap names changes which candidates enter the top 10. The "performance" of filter F is really the joint effect of (a) removing candidates that F targets, and (b) promoting replacement candidates that may have different characteristics. You can't disentangle these without a control that scores the SAME top-10 candidates with and without the filter.

5. **What happens to the fold-1 result if you drop the `all-folds-positive` rule and instead require positive AGGREGATE OOS with a stability penalty (e.g., negative variance of fold-level mean R)?** The current rule is binary and fragile to 2 folds. A continuous stability penalty (penalize variance of OOS fold returns) would capture the same intuition without the cliff edge.

6. **Have you computed the expected distribution of the IS-best mean R under a global null (all 46 combos have true mean R = baseline's −0.014)?** With 46 correlated noise processes, the expected maximum is substantially above the baseline. If the observed IS-best (+0.027) falls within the null distribution of the maximum, the entire search is noise. If it's outside, there's something worth investigating.

7. **Would the verdict change qualitatively under a different risk:reward ratio (e.g., 1:1.5 or 1:2)?** The 1:1 structure is baked into the entire pipeline. If the real edge in gap-and-go requires letting winners run (trailing stop rather than fixed 1R target), this pipeline would never find it.

8. **Is the `first_close_pos` contamination contained, or does it propagate through the combinatorial structure?** That feature appears in one predicate (`close_pos_max_0_9`), but any combo that pairs that predicate with another one inherits the contamination. How many of the 46 combos involve this feature, and how does excluding all of them change the search landscape?

9. **What's the correlation matrix of the 9 predicate masks (the binary vectors of which candidates each predicate keeps)?** If several predicates are highly correlated (keep largely the same candidates), your effective degrees of freedom are less than 9, and the 46 combos are partially redundant. If predicates are orthogonal, you're genuinely searching a 9-dimensional space.

10. **How many of the 4,549 unfilled candidates would have been filled if they'd been in the top 10?** The 80% fill rate is on ALL admitted candidates, but the evaluation only scores filled trades. If filters systematically change the fill rate of the candidates they keep (e.g., a filter selects more volatile names that are more likely to trigger), the per-combo fill rate becomes a hidden confound.

---

## 2. Hidden Assumptions (Not Stated or Examined)

### Statistical
- **The PBO logit-transform assumes OOS ranks are symmetrically distributed around 0.5 under the null.** If the rank distribution is skewed (e.g., many combos cluster at similar performance, making ranks unreliable), the logit mapping distorts the overfitting signal.
- **Days are treated as exchangeable within CSCV blocks.** Even with contiguous blocking, the block-level ordering is randomized. If there are strong calendar effects (e.g., January vs August behavior), randomizing block order destroys this structure and may overstate the effective sample size.
- **The subset invariant treats each candidate's realized R as a fixed property.** But realized R is a random variable with noise — the same candidate on the same day with the same features could have produced a different realized R due to execution path randomness (did the breakout trigger before the stop? which happened first?). Treating it as fixed understates the noise in the IS ranking.

### Structural
- **The pipeline assumes the edge (if it exists) manifests within the 09:35–11:30 window.** If gap-and-go candidates that look good at 09:35 tend to work AFTER 11:30 (e.g., afternoon continuation), the hard time-exit kills the signal.
- **The "admission rule" itself is taken as given and not searched over.** If the real filtering should happen at the admission stage (e.g., gap > 2% instead of >1%), the combinatorial search over post-admission filters starts from a suboptimal base set.
- **The 87 features span many categories, but the 9 pre-registered predicates only use a subset.** The choice of WHICH features to use as predicates embeds implicit model selection. If the real edge requires a feature NOT in the 9-predicate set, it won't be found.

### Market
- **The pipeline assumes gap-and-go should work in all regimes (bear, chop, trend).** Gap-and-go is inherently a momentum strategy. Requiring it to work in 2022 (a bear market where gap-ups often fail intraday) may be asking the strategy to overcome a structural headwind. A regime-conditional verdict ("no edge in bear markets, possible edge in trend years") might be more accurate than a blanket "no edge."
- **The fixed 1%-risk model assumes constant volatility scaling.** On high-VIX days, a 1% stop is much closer to noise than on low-VIX days. The strategy's economics change with volatility, but the pipeline doesn't adjust for this.

---

## 3. Specific Failure Modes (Severity-Ranked)

### FALSE NEGATIVE (Killing a Real Edge)

| Severity | Failure Mode | Scenario |
|----------|-------------|----------|
| **CRITICAL** | **Regime confounding × small folds** | 2022 (bear) is fundamentally different from 2023 (chop). A real edge that requires regime-specific filtering would be killed because the 2022-optimized combo is optimized for a bear market and fails in a chop market. Training on 1 year of a specific regime to predict a different regime is a recipe for false negatives. The `gap_floor_3 + rvol_min_1_5` combo is positive across ALL of 2022–2024 IS and in the fold-2 OOS — it was only "beaten" in fold-1 selection by a bear-market-specific combo that then failed OOS. This is a selection-procedure failure, not necessarily a strategy failure. |
| **HIGH** | **All-folds-positive with 2 folds** | With only 2 test folds, a strategy with a genuine but small edge (mean R ~0.02) has a non-trivial chance of being negative in one fold by noise alone. If each fold has a ~40% chance of being negative despite a positive true mean (plausible with ~300 trades/year and σ_mean ≈ 0.057/√300 ≈ 0.0033, so mean R of 0.02 is only ~6 SE from zero — actually quite significant, so this is less of an issue than I first thought. But the folds have different regimes, so the true mean may not be constant across folds). |
| **HIGH** | **Top-10-after-filter interaction** | Consider `gap_ceiling_12`: it removes the highest-gap candidates (the ones most likely to be in the top 10). Its "performance" reflects the quality of replacement candidates (lower-gap names promoted into the top 10), not the quality of what was removed. If ALL gap-and-go candidates are mediocre (the baseline finding), then removing high-gap names and promoting low-gap names won't improve performance — but that doesn't mean the filter logic is wrong, it means the replacement pool is also mediocre. The filter is being scored on the wrong counterfactual. |
| **MEDIUM** | **Coarse grid misses optimal thresholds** | The REAL filter might be `gap > 2.3% AND rvol > 1.8`. The grid only has `gap > 3%` and `rvol > 1.5`. If the signal exists but at different cut points, the grid-based search produces a false negative. This is an accepted limitation (degrees-of-freedom control), but it's a real false-negative path. |
| **MEDIUM** | **Trade-count floor kills sparse edges** | A filter combo that produces 15 trades/quarter but wins 70% of them (mean R ~0.4) would be ineligible. The pipeline is structurally blind to low-frequency but high-conviction edges. This is conservative design but worth acknowledging. |

### FALSE POSITIVE (Blessing an Overfit Combo)

| Severity | Failure Mode | Scenario |
|----------|-------------|----------|
| **HIGH** | **9-predicate grid embeds researcher degrees of freedom** | The 9 predicates were chosen because they "make sense." But "makes sense" is a euphemism for "fits the researchers' mental model, which was formed by looking at data." Even if pre-registered, the feature selection embeds implicit overfitting. A combo that passes might just be validating the researchers' intuitions, not discovering a robust edge. |
| **MEDIUM** | **2022–2024 share a structural artifact** | All three years are post-COVID, zero-commission, retail-option-boom era. If there's a microstructure artifact (e.g., payment for order flow dynamics that changed in 2025), a combo that works in 2022–2024 might fail in any truly new regime. The sealed 2025 OOS helps, but one OOS year isn't proof of robustness. |
| **MEDIUM** | **PBO=0.32 is below 0.5 but not stringent** | With 12,870 splits, PBO=0.32 means ~4,120 splits have the IS-best in the OOS bottom half. This is better than random but far from clean. A threshold of 0.5 for "overfitting" is lenient — many researchers argue for 0.05 or 0.01. A combo with PBO=0.32 still has a 32% chance of being worse than median OOS. |
| **LOW** | **`first_close_pos` contamination propagation** | Any combo involving `close_pos_max_0_9` inherits the mild contamination from the feature reverse-engineered on in-sample losses. This is acknowledged but the quantitative impact isn't measured. |

---

## 4. Statistical-Validity Critique of WF + PBO

### Walk-Forward

**Selection variance is the dominant concern.** With single-year training windows:
- Fold 1 trains on ~250 days (2022), selects 1 combo from 46. The variance of the max over 46 correlated alternatives on 250 observations is high. The probability that the TRUE best combo is selected is well below 1.
- Fold 2 trains on ~500 days, which is better but still modest for 46-way selection.

**The "all folds positive" rule with per-fold re-selection tests a compound hypothesis:**
- H₁: There exists a stable filter combo that works across all sub-periods AND can be reliably identified from each sub-period's data.
- This is a much stronger hypothesis than: "There exists a filter combo that works across the full period."
- The pipeline rejects H₁ but does not distinguish between: (a) no combo exists, and (b) a combo exists but the selection procedure failed to identify it from limited training data.

**Suggested diagnostic:** For fold 1, report the OOS performance of ALL 46 combos, not just the train-selected one. If `gap_floor_3 + rvol_min_1_5` would have been positive in 2023 (+X R) but wasn't selected because `spy_weak_regime + adv_min_1m` had a slightly higher IS mean in 2022, that's direct evidence of a selection-procedure failure, not a strategy failure.

### PBO via CSCV

**Several issues with the CSCV construction:**

1. **Pseudo-replication of splits.** With 16 blocks and 12,870 enumerated splits, many splits differ by only 1 block. These are not independent estimates of overfitting. The effective sample size for the PBO estimate is much lower than 12,870. A bootstrap confidence interval for PBO would reveal how fragile the 0.32 estimate is.

2. **The logit transform λ = ln(w/(1−w)) is sensitive near 0 and 1.** If the IS-best is OOS-best (w ≈ 1), λ → +∞. If it's OOS-worst (w ≈ 0), λ → −∞. These extremes can dominate the PBO estimate. Winsorizing ranks or using a different transform might change PBO materially.

3. **PBO uses per-day summed R, not per-trade mean R.** A day with 10 trades of +0.1R each contributes +1.0 to the matrix cell. A day with 1 trade of +1.0R contributes the same. But the statistical reliability of these two days is very different — the 10-trade day has a much tighter standard error. The matrix M treats them as equally informative.

4. **PBO only flags λ < 0 (IS-best in OOS bottom half).** An IS-best that consistently lands at OOS rank 0.51 (barely above median) contributes λ ≈ +0.04 per split and produces PBO ≈ 0. But "barely above median OOS" is NOT evidence of a real edge — it's evidence that selection adds almost no value. PBO should arguably be supplemented with the mean OOS rank or the mean λ, not just the fraction below zero.

5. **Contiguous blocks and regime structure.** The intentional preservation of autocorrelation is good, but it means PBO is sensitive to how regimes align with block boundaries. If a bear-market regime spans blocks 3–5, then splits that put blocks 3–5 entirely in IS vs split across IS/OOS will produce very different λ values. The PBO estimate is partly measuring how "lumpy" the regimes are relative to the block size.

### Combining WF and PBO

**PBO=0.32 with WF-fail is coherent but reveals a tension in what each gate measures:**

- **PBO asks:** "Across random regime mixtures, does the IS ranking have OOS predictive power?" The answer is weakly yes (68% of splits have IS-best in OOS top half).
- **WF asks:** "In a strict time-ordered split with single-year training, does the selected combo work?" The answer is no (fold 1 failed).

The tension is that CSCV randomizes over which blocks are IS vs OOS, creating mixtures of 2022, 2023, and 2024 data in both IS and OOS. But the WF split (2022 IS → 2023 OOS) is a PARTICULARLY hard split because 2022 and 2023 are different regimes. CSCV's randomization averages over easy and hard splits; WF exposes the hardest one.

**What PBO<0.5 + WF-fail actually tells us:** The IS ranking has SOME signal, but it's not strong enough to survive the hardest regime transition (bear→chop). This is genuinely useful information — it suggests the edge might be regime-conditional rather than universally absent.

---

## 5. Leakage Vectors (Beyond Those You Listed)

1. **Sector ETF point-in-time mapping.** If sector classifications use current (2026) GICS codes rather than historical codes, a stock that changed sectors in 2023 would have its 2022 data labeled with its 2026 sector. This contaminates the `sector_weak_regime` predicate and any sector-relative features.

2. **Split/glitch guard dropping ENTIRE trade dates.** If the guard drops a date because ONE ticker had a split, it removes ALL candidates on that date. If split days correlate with high volatility (which they often do — stocks split after big runs), you're systematically dropping volatile-regime days from the dataset. This biases the remaining sample toward lower-volatility regimes.

3. **The 09:35 cutoff for features that use "prior session" data.** On days following early closes (Black Friday, July 3, Christmas Eve), the "prior 5-minute session" is shorter than normal. Features computed from the prior session's intraday structure would use different effective lookbacks on these days. This is minor but systematic.

4. **Unfilled candidates and the fill-rate confound.** The 4,549 unfilled candidates have `realized_r = null` and are excluded from scoring. But if a filter combo changes the fill rate (e.g., `rvol_min_1_5` selects higher-volume names that might fill MORE often), the combo's mean R is computed over a different (and non-random) subset of its kept candidates. A combo that keeps candidates with systematically different fill characteristics will have its mean R estimated over a biased sample.

5. **The `score` (gap %) used for top-10 ranking is itself a feature being filtered on.** The `gap_floor_3` and `gap_ceiling_12` predicates directly filter on the ranking variable. This creates a structural dependency: filtering on the ranking variable changes the ranking distribution of the remaining candidates, which changes who makes the top 10. This is the most acute case of the top-10-after-filter interaction.

6. **Survivorship in the "liquid names that existed then" universe.** If the universe is constructed from a database that includes delisted stocks but with data only up to the delisting date, the delisting date might be the LAST trading date rather than the announcement date. A stock that announced delisting on June 15 might have its last data point on June 30, creating a window where you're "trading" a known-to-be-delisted stock with distorted behavior.

---

## 6. The Single Highest-Leverage Change

**Replace per-fold re-selection with a single pooled selection across the full search window, tested on the sealed 2025 OOS.**

Specifically:
1. **Train** on 2022–2024 combined (the full search window) — select ONE combo maximizing the objective. This uses 3× the data for selection that fold 1 had, dramatically reducing selection variance.
2. **Validate** on 2025 (the untouched sealed OOS year). This is the cleanest possible test.
3. **Within the training window**, use bootstrap-based stability analysis to quantify how often the selected combo would have been chosen under data perturbations — report this as a "selection stability" metric alongside PBO.
4. **Drop the all-folds-positive rule** in favor of: (a) positive aggregate OOS mean R, (b) positive OOS mean R in each calendar quarter of 2025, and (c) selection stability > some threshold.

This addresses the core problem: the current WF design has high selection variance on single-year windows and a brittle binary pass rule. Pooling selection across the full window and spending the sealed OOS is a cleaner test of whether a stable filter combo exists. And if `gap_floor_3 + rvol_min_1_5` — the most consistent signal — is selected and works in 2025, you have a real candidate.

If you're unwilling to spend the sealed OOS on a single pooled selection, the next-best alternative is to keep the 2-fold WF but **report the OOS performance of the top-3 IS combos per fold, not just the top-1**. If the same combo appears in the top-3 across both folds, that's stability evidence even if the #1 pick changes.

---

## 7. Bottom Line

This pipeline is well-designed for its stated purpose (avoiding the overfitting that fooled you before), but it overcorrects in one critical way: the **per-fold re-selection with single-year training windows** makes the walk-forward a test of selection-procedure stability rather than strategy existence. A real but regime-sensitive edge would be structurally likely to fail this test.

The `gap_floor_3 + rvol_min_1_5` combo is the thread worth pulling: positive across all 3 IS years, positive in fold-2 OOS, IS-best overall, with a tail-share of 0.12 (broad, not driven by outliers). It was only the fold-1 selection procedure — optimizing on 2022 alone — that picked a different combo, which then failed. If you had trained on 2022–2023 pooled and selected `gap_floor_3 + rvol_min_1_5`, you'd be looking at a very different verdict.

**My recommendation:** Before retiring the family, run the pooled-selection test on 2025. If it fails there too, retire it with confidence. If it passes, you've caught a false negative and the pipeline needs the selection-procedure fix.