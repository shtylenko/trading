**Bottom Line**

Your verdict is trustworthy only in a narrow sense: “this exact k≤2 grid, selected by this exact objective, using this exact yearly WF rule, did not produce a promotable strategy.” It is not strong enough to retire the broader gap-and-go family. The biggest risk is a false negative caused by an unstable selection procedure, not by the absence of signal.

The dangerous thing is that `gap_floor_3 + rvol_min_1_5` may be a real but regime-dependent edge, and your WF design can reject it because 2022 alone selected a different combo. Fold 1 does not actually test that combo. It tests the winner of a one-year bear-market selection contest.

**Toughest Questions**

1. Is the question “does any fixed filter have durable edge?” or “does this yearly refit-selection procedure have edge?” Your WF tests the second more than the first.

2. Why should 2022 alone be trusted to select a stable rule for 2023? One regime-year is too little for model selection.

3. Did `gap_floor_3 + rvol_min_1_5` fail materially in 2022 or 2023, or was it merely not the selected winner in fold 1?

4. Are daily clustered losses modeled? Ten same-direction gap longs can share one market beta shock; per-trade mean R may understate drawdown and overstate deployability.

5. Does the top-10-after-filter mechanic turn filters into implicit rankers? A filter can win by changing which names enter the capped portfolio, not because its predicate isolates better trades.

6. Are thresholds economically motivated or retrospectively plausible? Fixed thresholds reduce degrees of freedom, but judgment-call thresholds are still researcher degrees of freedom.

7. Is the point-in-time universe truly point-in-time at 09:35, including delistings, symbol changes, sector classifications, ETF mappings, and liquidity eligibility?

8. What is the minimum economically meaningful edge after realistic capacity, missed fills, queue priority, gap slippage, and same-day correlation?

9. Does PBO use the same objective, constraints, top-10 cap, and eligibility rules as WF? If not, it guards a different selection process.

**False Negative Risks**

Severity high: the WF has only two test folds, and each fold is a different market regime. “Positive in every fold” is strict, but more importantly the train windows are too small for selection. A real filter that needs many regimes to dominate can be missed because 2022 alone picks a noisy bear-market-specific combo.

Severity high: you may be evaluating an adaptive selection rule when the real candidate is a fixed economic thesis. `gap_floor_3 + rvol_min_1_5` being best over 2022-2024 and positive in 2024 OOS is not proof, but it is enough to say the family is not fully killed.

Severity medium: mean R ignores timing, clustering, and quarter-level consistency. A combo can have modest positive expectancy but lose under your objective if its edge appears in fewer high-opportunity regimes.

Severity medium: top-10 cap can hide edge outside the largest-gap names. If the true edge is “moderate gap plus strong RVOL,” ranking by raw gap after filtering may still select the wrong ten.

**False Positive Risks**

Severity high: 46 combos is not the real search space if predicates, thresholds, feature definitions, and prior failed rounds informed the grid. PBO only sees the final locked menu, not the researcher path that produced it.

Severity high: serial dependence and clustered event days reduce effective sample size. A strategy with 1,500 trades may have far fewer independent observations if many trades come from the same news/liquidity regimes.

Severity medium: PBO=0.32 is not “low”; it says the IS-best lands in the OOS bottom half in nearly one-third of splits. That is not catastrophic, but it is not strong comfort.

Severity medium: the top-5 tail penalty is too small to protect against regime/tail dependence. A strategy can be broad by top-5 share and still depend on a handful of high-opportunity weeks.

Severity medium: a pass could still be a universe artifact, especially if liquid-universe membership, sector maps, and split/glitch exclusions are not reconstructible exactly as of each historical morning.

**PBO + WF Critique**

`PBO=0.32 with WF-fail` is coherent. It means the selection procedure is not pure “best of noise,” but it also does not produce a temporally stable winner under your WF design. In plain English: there may be some signal in the grid, but not enough stable signal to trust the refit procedure.

The tension is interpretive, not mathematical. PBO asks, “Does the IS winner usually rank badly OOS across many symmetric block splits?” WF asks, “Does the expanding real-time process produce positive year-by-year results?” PBO can look acceptable while WF fails because CSCV averages many mixed-regime splits, while yearly WF exposes regime sequence risk.

I would not call PBO<0.5 a green light. I would call PBO=0.32 “not obviously data-mined, still fragile.”

**Objective Function**

Mean R over-selects for raw expectancy and under-selects for path quality, regime consistency, drawdown, and correlation. The hard trade floor prevents tiny-sample nonsense, but it does not ensure enough independent days, sectors, or event clusters.

A better objective would penalize instability directly: daily mean / daily volatility, positive-quarter rate, worst-quarter R, or a shrinkage score like:

`score = mean_daily_R - c * std_daily_R - d * max(0, -worst_quarter_R)`

Use daily portfolio R after top-10, not per-trade mean, because deployment is daily capital allocation.

**Top-10 Mechanic**

Top-10-after-filter is deployment-faithful, so it is sound if live trading really ranks by gap after filters. But it creates nonlinear interactions: a filter can remove high-gap names and promote lower-gap names into the traded set. That means the predicate is not merely “selecting a subset”; it is changing the portfolio construction rule.

This is not invalid, but you should analyze it as a filter-plus-ranker system. If gap rank is weak or negatively related after some threshold, the cap may dominate the result.

**Subset Invariant**

The subset invariant is useful for fast research, but not sufficient for strategy validity. Independent trade simulation is acceptable for estimating individual candidate R; it is not acceptable as the final portfolio model for a strategy that may hold 10 correlated longs simultaneously.

The fatal simplification would be treating 1,500 trades as 1,500 independent bets. The deployable unit is closer to trading days or event clusters.

**Leakage Vectors**

Watch sector ETF mapping and sector membership as-of-date. Modern sector labels backfilled onto old dates can leak.

Universe liquidity rules can leak if they use future average volume, current constituents, or surviving symbols.

Split/glitch exclusion can leak if the decision to drop a date depends on future-confirmed corporate-action data unavailable at 09:35.

Prior-session intraday features can leak through bad session boundaries, early closes, halts, extended-hours inclusion, or timezone/calendar mistakes.

The capture-to-ledger join can leak if outcomes are joined after ticker changes without strict date/symbol identity.

RVOL can leak if “average volume” includes the current day or if opening volume normalization accidentally uses full-day volume.

**One Defensible Additional Experiment**

Pre-register a fixed-candidate validation of `gap_floor_3 + rvol_min_1_5` as an economic thesis, not as the searched winner. Do not spend 2025 casually. First define the rule, portfolio construction, objective, minimum effect size, and failure criteria. Then evaluate it on the sealed 2025 year exactly once.

This is not goalpost-moving if you explicitly reframe it as: “The grid-search selection procedure failed, but one economically interpretable candidate emerged strongly enough to merit one alpha-spent confirmatory test.”

**Highest-Leverage Change**

Switch the arbiter from two yearly WF folds to a pre-registered portfolio-level, day-based validation framework with more folds and regime-aware blocking. Score daily top-10 portfolio R, include correlation/drawdown penalties, and require stability across blocks, not just positive annual sums.

The current pipeline is good at avoiding the old small-sample screen mistake. Its weakest point is that the final decision rests on two regime-confounded WF tests and a selection rule that may reject a real fixed edge because one early regime chose the wrong filter.