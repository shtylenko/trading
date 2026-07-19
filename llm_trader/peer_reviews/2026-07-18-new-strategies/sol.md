# Peer review — 2026-07-18 new strategies

## Executive verdict (10 lines max)

The multi-day releases and BB squeeze should remain parked; their negative evidence is sufficient to stop work on those exact constructions.
The claimed micro and VWAP passes are not valid promotion evidence: their daily screens select intraday trades using the completed day's volume.
VWAP has a second look-ahead: a 10:00–10:25 signal can use “morning confirmation” through 10:25; 254/506 signals occur before 10:30.
Accordingly, neither strategy should be paper-traded with capital yet; “paper book” currently means an in-sample historical repackage, not forward paper observation.
Micro is the better *candidate for repair*, not a validated strategy; VWAP should be behind it and may not merit repair.
The exact rolling-24-bar NML overlay should stay OFF, but this says little about Lance's post-leg consolidation-box concept.
Portfolio caps are sensible operational constraints, but their small historical uplift is not edge evidence and the two books have never been combined under one cap.
The warrior result is unusable for promotion because of current-float/cached-universe bias, noncausal RVOL, incomplete horizon, and unrealistic small-cap costs.
Freeze parameter tuning, fix causality and run integrity/null tests, then allow one pre-registered forward confirmation of micro; otherwise close the track.

## Gate / method scorecard

| Claim | Trust (H/M/L) | Why |
|---|:---:|---|
| Park the exact multi-day releases | **H** | All three fail pooled expectancy; two also fail year breadth. Recent/n30 selection was demonstrably misleading. Negative results are enough to stop these constructions, not to refute the source theses globally. |
| Park BB squeeze v0.1.1 | **H** | n=7,149, 0/4 positive years, baseline already negative. The RVOL leak makes it noncausal, but an apparently favorable activity selection still did not rescue it. v0.1.1 is not a clean test of v0.1.0 parameters. |
| Micro is a valid paper-optional pass | **L / invalid** | Full-day volume is used to decide an intraday candidate (`patterns.py:63-65`). The 2022–2025 data were also reused across family selection and packaging. Nominal significance does not cure leakage. |
| VWAP is a valid second book | **L / invalid** | Same full-day RVOL leak plus future morning bars can qualify early signals (`patterns.py:118-145`). Half the signals, 254/506, are before the 10:30 confirmation cutoff. |
| Prefer micro to VWAP | **M as triage; L as promotion** | Micro has broader nominal years and no second VWAP-specific look-ahead. That justifies repairing micro first, not allocating capital. |
| NML OFF for these books | **H for v0.1.0 overlay; L for Lance's thesis** | The frozen rolling-window overlay clearly damages these entries. It is not the post-leg, pullback, contraction, then consolidation box described by Lance. |
| Portfolio limits are validated packaging | **M** | Chronological caps are operationally sensible and tests cover basic concurrency. The uplift is measured on reused data, same-minute event order is coarse, and no shared micro+VWAP book was tested. |
| Warrior micro fails promotion | **H** | 1/2 periods, current float, cached survivors, only 18 months, full-day RVOL, and small-cap fill assumptions. Confidence is high in “do not promote,” low in “the thesis is dead.” |
| 2022–2023 5-minute coverage is adequate | **M/H for the chosen candidates** | I independently found all 3,254 micro/VWAP-screen candidate-days and all 12,812 BB candidate-days marked complete in marketdata metadata. That does not validate provider provenance, bar values, or the survivor universe. |
| Common gate controls research selection | **L** | `pooled > 0` plus `2/4 years > 0` has no minimum edge, uncertainty bound, dependence correction, or family-wise control. The same years serve discovery, selection, overlays, and “paper.” |

Trust ranking requested: multi-day FAIL park **high**; micro paper-optional **low/invalid**; VWAP second **low/invalid**; exact NML OFF **high**; warrior nonpromotion **high**.

## Answers to hard questions (§7)

### 7.1 Validity of the sim

1. **Yes, as a complete pipeline; insufficient evidence to isolate the fill-model bias.** Next-bar open is a defensible signal delay for liquid names, and stop-first OHLC ordering is conservative. Exact target-touch fills, stop fills near the stop rather than through it, absence of spread/queue/latency, and no auction/halt logic are optimistic. More importantly, the full-day RVOL screen is a direct look-ahead, so the current edge must be marked to **zero** for promotion. After a causal rebuild, I would require at least an extra 2–3 bps one-way execution haircut beyond baseline or, equivalently here, subtract roughly 0.02–0.03 effR. The observed 3×-slip failure says the whole claimed edge lies inside a plausible model-error band.

2. **Mostly no for bar-order optionality; yes for fill idealization.** The simulator checks the stop before T1/T2 on every bar, so a bar touching both is charged as a stop. If the low never touches the stop and the high crosses both targets, taking both within the bar is feasible in price-path terms. The optimism is exact fills on a touch and no queue/partial fill. Also, targets are frozen from the signal close but shares/risk are recomputed from the next open, so the exits are no longer actual 1R/2R from the fill. A next open at or below the stop is silently dropped rather than booked at the available loss; none were dropped in the liquid result, but this rule is unsafe.

3. **Yes, if presented as a contest between horizons.** Intraday and multi-day books have different opportunity sets, turnover, beta exposure, gap risk, capital occupation, and cost incidence. The result supports “these exact multi-day releases fail their own gate while these intraday simulations appeared positive,” not “short hold is economically superior” or “Lance swing ideas fail.” Avoid a cross-mold league table.

4. **Large caps: liquidity is realistic, risk labeling is not. Small caps: neither fills nor costs are reliable.** With a $5,000 notional cap, participation is immaterial in mega-caps. But the paper trades average only about $30 actual stop risk for micro and $21 for VWAP; 971/972 micro and 494/494 VWAP trades risk less than $90. The reported effR divides P&L by the intended $100, making these essentially fixed-$5k-notional trades, not $100-risk trades. Average baseline profit is only $3.15 and $2.56 per trade (about 6.5 and 5.3 bps of entry notional). In a $2 warrior name, $5,000 is 2,500 shares and can be meaningful participation in a 5-minute bar even if daily ADV is 500k shares; spread, halts, partial fills, and price impact dominate a 2-bps assumption.

### 7.2 Gates and multiple testing

5. **No.** The gate does not control family/version fishing. With 6–8 families, versions, source interpretations, and overlays, a merely positive point estimate is far too weak. I would designate one repaired family, freeze it, and require untouched forward data—preferably 2026-08-01 through at least 2027-01-31, extended until a predeclared minimum of 150 trades and 60 trading days. No other family may consume that confirmatory window. Require a positive lower confidence bound on day-clustered expectancy, positive net expectancy at calibrated p75 live-paper cost, and pass of preregistered nulls. Historical “holdout” years already inspected are not holdouts.

6. **Not convincingly after the research process.** On the packaged micro trade list, mean effR is 0.0315 across 972 trades. A day-clustered standard error is about 0.0124, giving a nominal 95% interval of roughly **[0.007, 0.056]** and t≈2.54. That looks marginally positive before accounting for family selection, nonstationarity, reused data, and leakage; it does not survive a simple eight-family Bonferroni bar. The 4/4 sign count is not four independent replications because names and market days share factors.

7. **Use both, but neither as currently defined.** Trade-weighted pooled expectancy measures realized opportunity; equal-year weighting prevents a dense regime from dominating. The primary unit should be daily portfolio return/P&L with day or week clustering, while equal-year results are a stability diagnostic. Four year signs are too coarse, and “greater than zero” needs an economically meaningful margin and uncertainty bound.

8. **It is a new version, not a pure bugfix.** Changing the start index is the bugfix. Changing percentile 0.20→0.25 and lookback 48→36 changes the hypothesis and signal population after observing n=0. Re-run 0.20/48 with only the start-index correction to close the original test, label 0.25/36 separately, and do not choose between them on 2022–2025. This does not change the practical park decision because the looser new version is uniformly negative.

### 7.3 NML A/B

9. **Evidence against this operationalization only.** Lance describes a directional leg, pullback, contraction, and identifiable consolidation box. `evaluate_long_edge` uses a generic rolling 24-bar high/low including the signal bar; it does not detect the leg, pullback, box start, contraction, or repeated edges. “NML hurts” should always be qualified as `nml_v0.1.0 hurts these detectors`.

10. **Yes, conceptually, though pre-registering and reporting the failed combination was honest.** A session-VWAP reclaim can naturally occur near the session range midpoint; rejecting it for being mid-range conflicts with the setup definition. The result falsifies the combination. It should not be used as evidence that either VWAP support/reclaim or a properly defined consolidation NML rule is false.

11. **Statistically unjustified and incomplete as a risk-filter criterion.** A −0.005 non-inferiority margin is smaller than sampling error and is harsh if the filter materially cuts drawdown/correlation, yet lenient if it preserves mean while providing no risk improvement. A risk filter should have frozen risk objectives—maximum drawdown, worst-day loss, expected shortfall, turnover—and a confidence-based non-inferiority test for expectancy. Here NML fails by enough that the ambiguity does not affect the OFF decision.

### 7.4 Universe and data

12. **Plausibly.** The list is a present-day mega-cap survivor cohort and even contains SPY and QQQ; there is no frozen PIT membership manifest or universe hash in the result. Controls should include: (a) within-symbol, same-day and time-of-day matched random entries with identical holding/stop machinery; (b) shuffle setup timestamps among eligible candidate-days; (c) regress trade/day P&L on contemporaneous SPY/QQQ intraday returns; and (d) report setup return minus a matched long beta/null return. The strategy must beat these nulls, not merely be long on active up days.

13. **Yes—unusable for promotion, even as a positive hint.** Current float creates membership leakage; a cached 420-name set omits delisted, renamed, newly listed, and failed-fetch names; 2026 is only H1; nine names had NA gaps; full-day RVOL is noncausal; and small-cap costs are implausible. Treat +0.158 in 2026 as a debugging observation, not Bayesian promotion evidence.

14. **No obvious silent missing-day problem in the selected liquid cohort, but the audit is not complete enough to certify the data.** I reconstructed the daily candidates and checked metadata: all 3,254 candidate ticker-days for micro/VWAP and all 12,812 for BB were marked complete at 5 minutes. That answers the narrow coverage question favorably. It does not test OHLCV correctness, provider mixing, corporate-action normalization, or excluded symbols. The runners also tolerate all symbol failures (`max_scan_failure_rate=1.0`) and do not persist candidate/failure counts in `RESULTS.json`, which is an integrity gap.

### 7.5 Promotion policy

15. **As written, it is a soft keep-alive.** The so-called paper books are historical simulations of the same entries with a post-processing cap. “Paper-optional” is coherent only if it means a zero-capital, forward shadow order log with a start date, sample target, cost/fill reconciliation, and automatic kill rule. “Tiny live size” is not justified before repairing causality.

16. **Only as a repair priority, not a capital choice.** Micro's nominal 4/4 and cost result are preferable, but the fee2+slip4 pass is +0.0022—economically zero—and occurs on a subset selected on the same historical data. The portfolio uplift from +0.0292 to +0.0315 is not an independent result. VWAP additionally has a future-morning look-ahead and a negative 2024.

17. **No, but stop strategy invention for now.** Cost fragility at 3× slip is a kill for deployment, not necessarily for all research. The only justified work is infrastructure/validation: causal screens, fill calibration, null models, PIT universe, immutable run manifests, and one forward confirmation. If a repaired micro book cannot clear calibrated p75 costs plus a safety margin, stop the short-hold track.

18. **Neither, with capital.** If “paper” means a forward zero-capital shadow book, choose repaired micro alone after rerunning the historical pipeline causally and freezing it. Do not choose a combined book yet: it can hide two weak signals and creates another selection degree of freedom. A combined shared-cap book is a later confirmatory risk experiment, not the next trade.

### 7.6 Multi-day FAIL interpretation

19. **Park the construction; do not declare the broad thesis dead.** High win rate with negative R can reflect target/stop geometry, selection, or genuine lack of payoff. Retargeting after seeing the result is outcome fitting. First preserve the release as negative evidence. Only a genuinely different, source-grounded construction with frozen exits and a new holdout could reopen it; “make winners larger” is not a thesis.

20. **Mandate chronological, all-opportunity sampling with a version budget.** Before any run: freeze the detector, universe manifest/hash, execution rules, cost model, development interval, one validation interval, and one untouched confirmation interval. Small n30 sets may be smoke tests only and must be stratified across regimes—not most-recent unique tickers. Evaluate every eligible setup in the interval, cluster by day, log every failure/missing bar, register every attempted version, and prohibit reusing a consumed confirmation window for promotion.

## Integrity findings

- **[Critical] Completed-day volume look-ahead.** Micro, VWAP, and BB screens compute current-day RVOL from the final daily volume (`strategies/*/patterns.py`, respectively lines 63–65 or 59–61) and apply it before intraday detection. At 09:45–14:30 that volume is unknown. This invalidates all positive short-hold promotion claims and the warrior probe. Use prior-day liquidity for a premarket screen or a causal cumulative-volume-to-time baseline.
- **[Critical] VWAP future-morning look-ahead and overlap.** `morning` spans 09:30–10:30, is fully evaluated, then `win` begins at 10:00. Thus early signals see later bars, and 10:00–10:25 is processed twice. The DB has 254/506 signals before 10:30, including 192 at 10:00. Fix by either starting entries at 10:30 or evaluating confirmation incrementally using `df.iloc[:i+1]`.
- **[High] “Sealed” entries are mutable.** The runners call `upsert` into persistent SQLite files and never call the available `sync_scope`; signals that disappear after a config change can remain. Backtests then read all rows for the strategy without date/config hash filtering. Current construction tags happen to be uniform, but there is no immutable run ID, config hash, universe manifest, source-data fingerprint, or stale-row proof.
- **[High] No real holdout remains.** The same 2022–2025 cohort is used for family selection, cost stress, NML, portfolio packaging, and the historical “paper” label. Pre-registering an overlay prevents threshold tuning but does not turn reused outcomes into independent confirmation.
- **[High] Universe provenance is missing.** Narrative alternates between 60 and 59 names; the DB has 59 distinct symbols, including two ETFs. There is no PIT membership or rationale frozen in the artifact. A current mega-cap survivor list can materially favor long-only results.
- **[High] Risk/effR description is misleading.** A $5,000 notional cap binds almost every liquid trade. Mean stop risk is about $30 micro/$21 VWAP, yet P&L is divided by $100. Report notional return, actual-risk R, intended-risk utilization, gross edge, and costs separately.
- **[Medium] Targets are not rebased to the actual fill.** Stops/T1/T2 derive from the signal close, while sizing derives from next-bar effective entry. Consequently “half at 1R/rest at 2R” is not true from the fill. The configured `max_entry_gap_atr=0.5` is stored in features but not enforced by these simulators.
- **[Medium] Stop/limit fill realism is incomplete.** Stop-first resolves OHLC ambiguity conservatively, but target touches always fill exactly and stops do not gap through. A next-open fill below the stop is dropped. Small-cap halts, spreads, partial fills, and queue priority are absent.
- **[Medium] Portfolio timing is only minute-granular.** A position whose exit and another entry share a 5-minute timestamp frees capacity without intrabar ordering evidence. Same-time selection also uses full-day RVOL. This is unlikely to explain the whole edge but must be made causal.
- **[Medium] Error policy can silently shrink the sample.** Scan/detect exceptions are logged and skipped, `max_scan_failure_rate=1.0` is effectively permissive, and final result artifacts omit day-candidate and failure counts. The present liquid candidate-day metadata are complete, but the pipeline contract remains unsafe.
- **[Medium] Detector/source mismatch.** Ross says enter immediately on the break and describes 1–2 bars in an in-play runner. Micro waits for a green bar close, allows three bars, requires a new impulse high in practice, and tests ordinary liquid mega-caps without a PIT catalyst. Lance's VWAP source is chiefly anchored VWAP as context, not this exact session-VWAP signal. Results should be named as implementations, not source validation.
- **[Low] Tests pass but validate mechanics, not research validity.** The focused suite passed 27 tests. No test asserts a signal is invariant to future daily volume/future morning bars, cleans a rerun scope, handles gap-through stops, or verifies a frozen universe/run manifest.

## Disagreements with implementer freeze

- I agree with parking all exact multi-day releases and BB, freezing detector nibbling, keeping exact NML v0.1.0 OFF, and refusing warrior promotion.
- I disagree with retaining micro or VWAP as “paper-optional” under the current wording. They should be **invalid pending causal rebuild**, not thin passes. No capital—even tiny size—should be attached to them.
- I disagree that the current artifacts are sealed paper books. They are mutable-entry historical simulations plus packaging. Reserve “paper” for forward orders and broker-reconciled fills.
- I would not characterize portfolio-only as A/B-validated edge. Keep 3 concurrent/5 per day as a conservative provisional exposure rule, but its parameters and apparent uplift remain unconfirmed.
- I would repair micro first and probably drop VWAP unless the future-morning bugfix plus causal screen still leaves adequate margin. That is narrower than “micro primary, VWAP second.”
- I would not spend another historical holdout on alternative NML now. It is intellectually defensible as a new construction but lower priority than causality, nulls, costs, and a real forward sample.

## Pre-registered next experiments (if any)

| ID | Hypothesis | Frozen design | Gates | Kill criteria | What is not success |
|---|---|---|---|---|---|
| **E0 — causal rebuild audit** | The apparent micro/VWAP edge survives removal of future information. | Freeze all detector/exit parameters. Replace daily RVOL with cumulative RTH volume through the signal divided by the median cumulative volume through the same 5-minute slot over prior 20 sessions; threshold stays 1.2. For VWAP, require confirmation using past bars only and do not double-process 10:00–10:25. Same 59-symbol diagnostic window 2022–2025; fresh DB/run hash. | Reproduce candidate counts/failures; pooled and each-year metrics; day-cluster CI; calibrated costs. This is an **audit**, not promotion. | Any future-data dependency; unexplained stale rows; micro pooled ≤0; fewer than 3/4 positive years; p75-cost expectancy ≤0. VWAP is killed if pooled ≤0 or fewer than 3/4 positive years after its second leak is removed. | A positive point estimate, recovery through threshold changes, or choosing between old and new RVOL definitions after seeing results. |
| **E1 — matched nulls** | Setup timing adds value beyond being long active large caps on selected days. | For every repaired signal, generate 1,000 within-symbol matched null sets from eligible bars in the same time bucket/day, using identical next-open fill, notional, stop-distance distribution, EOD rule, and costs. Also shuffle setup days within symbol/month. | Actual minus null mean >0 with day-cluster/randomization p<0.05; lower 95% bound >0; pass at p75 cost. | Actual is not above the 95th percentile of both null distributions, or edge is explained by SPY/QQQ contemporaneous return. | Beating zero while failing to beat the matched long null. |
| **E2 — broker fill calibration** | A conservative cost model can be estimated and the repaired micro gross edge exceeds it. | Zero-capital or minimum-share shadow orders for repaired micro only, 2026-08 onward. Record decision timestamp, NBBO/quote, intended order, simulated fill, broker fill, partials, reject, spread, and adverse excursion. Freeze order type before start. | At least 150 trades and 60 days; use p75 one-way implementation shortfall plus actual fees in the confirmatory backtest; net lower day-cluster 95% bound >0.01 intended-R/trade and no year/quarter negative after costs. | Median fill alone looks good; fewer than minimum observations; excluding rejects/partials; changing order type mid-sample. |
| **E3 — one forward micro confirmation** | The repaired, null-clearing micro release has positive forward net expectancy. | One immutable micro release; PIT eligible universe declared daily; 2026-08-01 onward, no parameter changes, zero capital initially; portfolio 3 concurrent/5 day. Continue to later of 2027-01-31 or 150 trades. | Net expectancy >0 at calibrated p75 costs; positive lower one-sided 95% day-cluster bound; max drawdown and worst day within preregistered $ limits; no severe data/fill audit exceptions. | A profitable month, pooled >0 without uncertainty, simulated rather than broker-reconciled fills, or extending the window only because it is losing. |
| **E4 — combined portfolio, only after E3** | Micro and VWAP (if independently confirmed) provide diversification under shared capital rather than duplicate beta. | Use raw chronological signals from both; one shared cap of 3 concurrent, 5 new/day, $15k gross notional, $300 intended stop risk/day; deterministic same-time priority frozen using causal features only. No per-family pre-caps. | Combined net expectancy and lower bound >0; max drawdown or expected shortfall improves ≥15% versus micro alone without expectancy falling by >0.01; report daily correlation. | Higher trade count/P&L from more exposure, choosing priority after outcomes, or combining a failed VWAP book with a winning micro book. |
| **E5 — PIT warrior feasibility** | A PIT small-cap universe and empirical fill model can test—not assume—the Ross-style opportunity. | Acquire PIT float/shares outstanding, delistings/symbol history, full exchange universe, catalysts if available, complete 1-minute quotes/trades, and halt data. Freeze 2024–2025 development; keep 2026+ untouched. Use actual cumulative RVOL and dollar-volume/participation caps. | Data completeness ≥99% of eligible sessions; all membership reproducible; shadow-fill p75 cost leaves predeclared gross margin; two full untouched periods positive. | Current float, cached survivors, bar-only 2-bps fills, pooled 2026 H1, or a full exchange rescan without PIT membership. |
| **E6 — post-leg NML v0.2 (optional, low priority)** | NML helps only when a true directional leg is followed by a contracted consolidation box; it should not gate generic VWAP touches. | Micro only. Freeze a causal leg definition, 3–8-bar pullback, 4–12-bar box, contraction ratio, and edge definition from source before data. Exclude VWAP. Evaluate on a future window not used by E3, or abandon if no holdout budget. | Expectancy non-inferior with lower confidence bound above −0.01 and ≥20% improvement in preregistered worst-day/expected-shortfall metric. | Searching box lengths/edges, applying it to VWAP again, or retaining it merely because pooled effR remains positive. |

Ordering matters: **E0 → E1 → E2 → E3**. E4–E6 are contingent and should not run in parallel on the same confirmatory outcomes.

## What the implementer should stop doing

- Stop calling historical repackaging “paper” or mutable SQLite rows “sealed.”
- Stop using completed-day fields for intraday admission; add a general future-column invariance test.
- Stop treating `>0` as an adequate economic or statistical margin.
- Stop counting calendar-year signs as independent replications or H1 2026 as equivalent to a full year.
- Stop bundling bug fixes with threshold changes under one version narrative.
- Stop using recent unique-ticker n30 samples for anything beyond smoke testing.
- Stop translating a source concept into a convenient rolling indicator and then generalizing the result back to the source.
- Stop reporting intended-risk effR without actual risk utilization and notional-return decomposition.
- Stop accepting scan failure rates up to 100% or omitting failure/candidate counts from immutable results.
- Stop adding families until the null, cost, universe, and forward-confirmation machinery exists.

## Recommendations to human operator

1. **Trade neither micro nor VWAP with money now.** The key positive evidence is contaminated by two kinds of look-ahead. The correct allocation is $0 live and $0 “tiny live.”
2. Permit one bounded repair project for **micro only**: causal time-of-day RVOL, immutable clean run, matched nulls, and a broker-fill calibration. Do not retune the detector while repairing it.
3. If the repaired historical micro result remains positive with margin, run a forward shadow book at the current exposure ceiling—maximum three concurrent, five entries/day, no more than $5,000 notional per position—but submit no capital-bearing orders until the fill study and forward gate pass.
4. Treat VWAP as parked pending the micro decision. It has a second look-ahead, a negative 2024, weaker cost margin, and only nominal day-cluster evidence. Do not spend a separate holdout on it unless micro clears the full process.
5. Keep the exact NML gate OFF. Do not infer that Lance's actual post-leg-box advice is disproved, and do not build v0.2 unless a fresh holdout budget remains after execution validation.
6. Keep the portfolio cap as a conservative provisional limit, not as proof of added edge. Do not run both families simultaneously until a shared chronological portfolio is pre-registered.
7. Keep multi-day TA, BB squeeze, and warrior micro parked. Ignore their attractive subperiods and high win rates. Reopen only for a structurally new thesis plus untouched data; for warrior, PIT float and empirical small-cap fills are prerequisites.
8. Make the next research milestone an **integrity release**, not another strategy: frozen universe manifest, clean-scope DB, run/config/data hashes, causal-feature checks, failure accounting, day-cluster uncertainty, null benchmarks, and broker-reconciled costs.

Bottom line: the implementer's instinct to freeze tuning is correct, but the proposed soft promotion is not. The evidence supports **park most; repair and shadow-test micro once; allocate no capital until it independently passes**.
