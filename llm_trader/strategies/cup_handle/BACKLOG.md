# Cup-handle research backlog

## Purpose and guardrails

This is a hypothesis backlog, not a list of parameters to optimize against the current small cohort. Keep the causal `prebreak_arm` contract and v0.6 engine-owned target/indicator fail-closed protections intact while researching.

For every change:

1. State a falsifiable hypothesis before implementation.
2. Compute and persist the feature first; do not immediately turn it into a gate.
3. Use only information available at the completed plan bar.
4. Evaluate one feature family at a time on a chronological development split.
5. Freeze a rule before evaluation on an untouched out-of-sample period.
6. Count every eligible signal, including no-trades, gaps, stops, and voids.

Do not choose target, stop, expiry, or threshold values from the current six-trade v0.6 cohort.

Source ideas: [`library/cup_handle/00_MASTER_LIBRARY.md`](../../../library/cup_handle/00_MASTER_LIBRARY.md). Treat its research and vendor claims as hypotheses requiring independent validation, not as sufficient evidence to change production defaults.

## P0 — research-engine stability first

### Deterministic decision-path migration

**Goal:** remove the LLM from cup-handle entry, cancellation, and exit decisions.
The scanner already produces a causal plan and the execution engine already owns
fills, sizing, gap/expiry guards, targets, breakeven, and forced exits.

**Phase 1 — versioned baseline — completed 2026-07-17:** create a shared `CupHandlePolicy` that emits
one `ARM_BUY_STOP` on every valid revealed scanner-plan bar and otherwise
`OBSERVE`. It must be driven only by the plan/tick stream, be fully replayable,
and stamp a deterministic policy version in each session. Do not attempt to
imitate vague LLM discretion.

**Phase 2 — deterministic batch path — completed 2026-07-17:** run the policy without an agent or
agent sandbox, but retain the same sealed stream, recorder validation, engine,
artifacts, and audit-grade provenance. Compare it with v0.6 as a new baseline,
not an equivalent replay.

**Phase 3 — explicit discretionary rules:** only add cancellation or early-exit
logic after specifying exact causal predicates and independently evaluating each
one. Candidate phrases such as “trend invalidates”, “expanding downside volume”,
or “throwbacks are normal” are not executable policy.

**Role of LLMs:** retain them for research, diagnostics, and operator summaries;
they must not alter the deterministic trading decision path. A future
news/fundamental discretionary strategy would be a separate strategy with its
own data contract and evaluation.

**Acceptance:** repeated runs over the same sealed plans produce byte-identical
decision records and identical execution artifacts; no trading run requires an
LLM process, prompt, or private-file audit.

**Completion evidence:** `0.7.0` is a versioned deterministic baseline. Its
policy materializes only plan-bound `ARM_BUY_STOP`/`OBSERVE` intents, its audit
re-derives the full decision log from the sealed stream, and it does not invoke
Hermes. The original nine-setup smoke cohort reproduced v0.6 exactly. On the
new ten-unique-ticker smoke cohort, v0.6 and v0.7 were economically near-equal
($839.04 versus $838.67); this is migration evidence, not a profitability or
promotion result.

### Scanner/replay indicator-window parity — completed 2026-07-17

- [x] Make the scanner require every daily replay indicator across the same
  40 completed planning bars that replay exposes before the setup bar. A valid
  indicator on the setup bar alone is insufficient: a plan with a late-starting
  SMA200 would otherwise be admitted by research and fail only during batch
  preseal.
- [x] Centralize the 40-bar planning-window constant and required-indicator
  completeness predicate. The scanner, replay, and step fallback now derive
  from the same contract.

**Regression evidence:** the first full 2025 run rejected `GEV_2025-02-10`
before any trade because its visible planning window lacked 24 SMA200 values.
The portfolio replayer then correctly refused to score the incomplete cohort.
After the scanner fix, an atomic PIT rescan removed that plan; the corrected
569-setup development batch completed with zero indicator preseal failures.

### Completed cohort-integrity remediation (2026-07-17)

- [x] Make exact testset size a CLI contract: `build-set --n N` now fails when
  fewer than `N` eligible rows (or unique tickers) are available; stratified
  allocation now sums exactly to `N` when the pool permits it.
- [x] Preserve the historical nine-name `testset_10.json` rather than rewrite
  its provenance; create `batch/cup_handle/testset_10_v2.json` with ten unique,
  causal ticker/date plans after a 100-symbol no-failure scan.
- [x] Re-run v0.5, v0.6, and v0.7 on the same v2 set. v0.5 produced five audit
  voids (agent-authored target-ladder violations / forbidden reads), v0.6
  required one fail-closed retry, and v0.7 completed all ten leaves with zero
  agent processes and zero voids.

**Limit:** `testset_10_v2` is a smoke/regression cohort, not a promotion
holdout. The 100-symbol scan takes the first sorted symbols and is therefore
alphabetically concentrated; it is not a point-in-time representative universe.

### Point-in-time universe and cohort provenance — infrastructure completed 2026-07-17

- [x] Add a versioned, hashable point-in-time universe-manifest contract with
  explicit effective intervals, source/as-of date, symbol list/hash, and
  continuous coverage validation. A `current_snapshot` is represented honestly
  but is rejected before historical research data is fetched.
- [x] Add the fail-closed `research_scan` path. It detects every membership
  interval before opening the `EntryStore`, then replaces all successful scopes
  in a single SQLite transaction; a later interval/provider failure leaves the
  previous corpus untouched.
- [x] Stamp every research-scanned setup with the exact universe-manifest hash
  and interval evidence. `build-set` now requires this evidence for a normal
  cup-handle holdout, embeds it in the testset, and `batchsim run` rejects a
  cup-handle batch without it. The existing `testset_10_v2` remains readable as
  historical smoke evidence but is deliberately no longer promotion-eligible.
- [x] Make historical `entry_scan` reject raw ticker lists/current snapshots by
  default. A raw historical list requires an explicit exploratory opt-in and
  cannot become a promotion batch.

**Public PIT validation corpus — completed 2026-07-17:** archive a dated public
S&P 500 membership CSV, hash the raw source, and apply every source-day
membership list only from the following calendar day. The resulting immutable
manifest, `batch/cup_handle/universe_sp500_public_pit_2025_2026.json`, covers
28 intervals from 2025-01-01 through 2026-06-30. Its fail-closed scan requested
and received data for all 14,088 interval-symbols and yielded 818 causal plans
across 247 tickers. `testset_sp500_public_pit_30.json` is a stratified,
provenance-sealed 30-plan validation cohort from that corpus.

**Source-quality gate — completed 2026-07-17:** every manifest, scanned setup,
testset, and batch now carries `source_quality`. `primary_or_licensed` is the
only promotion-eligible tier. The public dated archive is deliberately marked
`public_pit_unverified`, so its batches run as reproducible PIT validation but
are non-promotable and cannot be used in the final batch-comparison gate.
`universe_sp500.json` remains an explicitly non-historical current snapshot.

**Remaining operational blocker:** acquire/export an immutable primary or
licensed historical-constituent source, reproduce the multi-year corpus with
that source, and create chronological development and untouched holdout cohorts.
Do not draw a profitability or geometry conclusion from the public-validation
cohort alone.

### Continuous detector state across PIT boundaries — completed 2026-07-17

- [x] Replace interval-by-interval detector calls with one continuous scan per
  ticker across the complete requested research period. Point-in-time membership
  is now an eligible-plan-date map, applied before formation/cooldown state is
  updated. An absent ticker therefore cannot create a plan or suppress a later
  eligible arm, while an unrelated constituent-file boundary cannot reset the
  scanner's five-bar arm cooldown.
- [x] Stamp each emitted plan with the membership interval in effect on that
  plan date and fail if a detector output is outside its PIT membership scope.
  Tests cover both the continuous one-scope contract and the eligible-date
  cooldown semantics.

**Correction evidence:** the first 2023–2025 scan used 45 independent detector
calls and produced 1,535 plans. The corrected continuous scan completed 562
distinct symbols with zero provider failures and published 1,352 plans
(487/381/484 in 2023/2024/2025), removing 183 boundary-reset artifacts. The
prior 2025-only public-PIT result with 569 plans is **superseded** by the
484-plan continuous-history cohort and must not be used for strategy selection.
The 2026-H1 holdout remains unexecuted and unscored.

### Deterministic geometry selection — completed 2026-07-17

- [x] Enumerate every valid cup/handle geometry visible on a plan date. Select
  by the fixed `geometry_selection_v1` structural score (handle shallowness,
  lip alignment, trough centrality, and handle-volume dry-up); ties resolve by
  longer cup, shorter handle, then earlier geometry indices.
- [x] Persist selection score, components, candidate count, tie-break order,
  and selected indices in every plan. The causal-plan contract now rejects a
  legacy row that lacks this evidence, forcing an explicit rescan rather than
  silently replaying the prior first-match geometry.
- [x] Add adversarial tests proving candidate enumeration order cannot change
  the selected formation and that the stable longer-cup tie-breaker applies.

**Development correction:** after continuous-state scanning, the geometry-v1
rescan completed 562 symbols with zero provider failures and yielded 1,305
plans (473/363/469 in 2023/2024/2025), versus 1,352 under first-match geometry.
Its selection candidate count had a median of 29 (maximum 675), making the
previous implicit loop order materially consequential. The deterministic
execution batch completed 1,305/1,305 leaves with zero voids. This is an
outcome-independent scanner correctness change, not a feature threshold or
entry gate.

### Parallel workstreams and dependency boundary

P0 blocks experiments that change scanner candidate geometry or compare a newly
rescanned setup population. It does not block preparatory work: point-in-time
data adapters, deterministic feature calculation, skill/harness compliance
tests, and frozen-plan execution-veto tests can proceed in parallel.

Do not describe a scanner-level market-regime filter as merely dropping plan
dates. In the current prebreak scanner, the regime test happens before
`last_arm_i` is updated. Suppressing one plan can therefore allow a nearby later
plan that the baseline cooldown would have suppressed. Treat that as a distinct
scanner policy, with its own rescanned population, after P0. A frozen-plan
experiment may instead test a narrower, explicit execution veto: remove a
baseline plan when its plan-date regime fails and do not replace it with a later
arm.

## P1 — highest-value signal-quality experiments

### Skill-policy and harness workstream

**Scope:** skill versions can be compared on frozen, causal plans without
changing the scanner setup population. This measures decision-policy and agent
reliability, not detector alpha.

**Plan:** evaluate sealed skill candidates with identical test sets, execution
configuration, prompt contract, and multiple agent repeats. Report arm
compliance, late/invalid cancellation or exit rate, abandonment/void rate,
decision divergence, and R outcomes separately from scanner performance.

**Boundary:** do not let an LLM use an unvalidated feature to decide whether to
arm, cancel, or exit. That is an opaque informal gate. New scanner features may
be exposed only as labelled diagnostics until a pre-registered deterministic
policy has been evaluated. Do not add a narrative rule such as “throwbacks are
expected” unless it is translated into an objective, causal invalidation/exit
rule and tested on a materially larger frozen cohort.

### Market regime filter

**Hypothesis:** cup-handle plans have better expectancy when the broad market is in a confirmed uptrend.

**Current state:** `require_spy_above_sma50` exists but defaults to false.

**Experiment:** compare pre-declared variants: SPY > SMA50, SPY > SMA200, and both. Compute on the plan date only and retain the same universe/execution contract. Select at most one variant using development data; freeze it for the final holdout.

**Causal diagnostics — completed 2026-07-17:** the research scanner now
persists a strict, plan-date SPY close/SMA50/SMA200 record (schema v1) and a
diagnostic-only `formation_quality_v1` record with structural and volume
components for every causal plan. The 2025 PIT development refresh completed
all 17 intervals and all 569 baseline setups with zero provider failures; the
enriched setup identities exactly matched the frozen strict v0.7 batch. The
new feature report fails closed if a batch setup lacks either feature record or
if a trade is not classified by the auditable portfolio replay.

**Development evidence, not a selected rule:** the 31 plans made while SPY was
below both averages were poor independently (`-0.475` effective R), but the
current capacity-constrained portfolio had accepted several of them. The
pre-declared *frozen-plan* `SPY > SMA50 and SMA200` veto was therefore tested
without rescanning or allowing replacement arms: it stood down 51 of 569
setups, improved independent effective R from `+0.031` to `+0.054`, but made
the portfolio result worse (`-$10,585.13` / `-0.037` effective R versus the
baseline `-$10,033.02` / `-0.035`) and deepened realized drawdown. **Reject
this veto as a portfolio policy.** Do not convert the independent-only result
into a scanner gate. The 2026-H1 holdout remains unexecuted and unscored.

The calendar-quarter diagnostic reinforces that restraint: independent effective
R ranged from `-0.529` (2025-Q1) to `+0.251` (Q2), while constrained portfolio
effective R ranged from `-0.214` to `+0.006` before Q4 fell to `-0.109`. One
calendar year is not stable enough to infer an all-regime market rule or to
optimize a portfolio priority from these descriptive bands.

**Data-integrity enforcement — completed 2026-07-17:** any missing shared SPY
diagnostic now aborts the scanner immediately rather than being counted as an
isolated ticker failure. The SPY raw cache tail was repaired with actual
provider bars (no imputation or carry-forward), and the regime fetch now
preflights every expected market session in the complete requested scope
before scanning a single ticker.

### Single-name relative performance versus SPY

**Hypothesis:** a strong stock relative to the broad market improves breakout quality.

**Plan:** add a trailing single-name return versus SPY as a causal descriptive
feature now. Use consistent, split-adjusted return series and matching trading
dates; confirm the market-data adjustment contract before treating it as a
research feature or gate. This calculation does not require a historical
cross-sectional universe.

### Cross-sectional RS and sector regime

**Hypothesis:** a strong stock in a strong sector improves breakout quality and reduces correlated momentum failures.

**Plan:** add cross-sectional RS rank, sector ETF trend, and sector relative
strength as causal features. Require a point-in-time constituent universe and
point-in-time sector classification before using ranks as gates. Do not use
today’s universe or sector membership to rank historical signals.

For a live scan, current sector membership may be logged as operator-facing
diagnostic context, but it must not affect the automated/LLM decision until the
same feature has a point-in-time historical evaluation. Live-only context is not
research/live parity.

### Handle quality features

**Hypothesis:** high, gently downward/flat, low-volume handles have superior expectancy.

**Plan:** persist handle position within cup, handle low versus cup midpoint, normalized handle slope, volume-trend slope, and resistance-touch count. Test upper-half/upper-third location and depth/duration constraints only after feature analysis.

**First diagnostic slice — completed 2026-07-17:** `formation_quality_v1`
currently records handle height, shallowness, lip alignment, trough centrality,
and handle-volume dry-up along with the raw geometry. Its fixed score bands
were intentionally descriptive only: the small `>=0.70` group (28 setups) was
negative, while the broad middle band was positive independently but negative
after portfolio capacity. This is insufficiently stable to select a threshold
or use score as priority. Next, inspect chronological stability and individual
components before registering exactly one portfolio-priority hypothesis.

### Pre-break volume and accumulation features

**Hypothesis:** declining handle supply and net accumulation during the base improve the probability and quality of a later breakout.

**Plan:** add handle volume dry-up slope, cup-recovery up-volume versus down-volume, and a causal 20-bar net-distribution metric (top-volume days that are up versus down days).

### Prior-uptrend strength

**Hypothesis:** a meaningful advance before the cup distinguishes continuation bases from weak rebounds.

**Plan:** compute pre-cup return and trend strength over fixed causal windows (for example 40/60 sessions) as features. The existing SMA stack is not a substitute for this measurement.

## P2 — structural refinements and separate strategy variants

### Cup-shape quality score

Persist trough centrality, left/right duration balance, recovery symmetry, and normalized quadratic-fit diagnostics. Do not initially hard-gate on a polynomial R² threshold: fit quality is scale/window-sensitive and can overfit.

### Definitional-gate protocol

After P0, a semantic pattern constraint may have a lighter *implementation*
burden than a tuned numeric threshold, but never a lighter evidence burden for
strategy promotion. “Reject a rising handle” still requires a predeclared,
causal definition: price field, exact handle window, slope estimator,
normalization, and treatment of negligible slopes. It must have adversarial
fixtures and an impact report (signals removed, coverage, and outcomes across
walk-forward folds) before becoming a default gate. No definitional label is a
license to fast-track an unmeasured profitability claim.

### Volume-confirmed, next-session entry variant

`breakout_vol_mult` affects only the research-only `confirmed_breakout` path; it does **not** filter production `prebreak_arm` entries. Raising it is not a simple production threshold change.

Build a separate causal variant that observes a completed breakout close above the trigger with RVOL >= a pre-declared threshold, then enters no earlier than the following session with full gap modeling. Compare its coverage and expectancy with `prebreak_arm`; never merge the two result sets.

### Pullback/retest entry variant

As a separate strategy, test a finite post-breakout retest window with a predeclared entry and invalidation rule. It may raise hit rate while lowering coverage; report both and include missed breakouts.

### Earnings-event risk veto

With a point-in-time earnings calendar, test a no-new-entry window before earnings. Treat this primarily as tail-risk control, not assumed alpha.

## P3 — portfolio and execution extensions

### Portfolio risk controls

Independent session backtests do not model simultaneous positions. Add portfolio-level maximum open risk, sector concentration limits, and regime-adjusted portfolio heat before paper/live portfolio use.

**Priority escalation — observed 2026-07-17:** the deterministic 59-plan
exploratory panel contained 11 overlapping same-ticker position pairs (three
concurrent ABBV positions alone). A causal one-open-position-per-ticker control
removed eight entries and reduced the panel's effective R from `+0.288` to
`+0.142`; the independent sessions also reached seven concurrent positions / about
`$3,484` initial risk on a nominal `$500` per-trade budget. Before any geometry/filter experiment, complete a
portfolio replay that enforces at least one open position per ticker; do not
interpret independent-session P&L as portfolio P&L.

- [x] Add a reproducible ticker-exclusive shadow control to `batchsim
  diagnostics`: it identifies every overlap, reports the causal one-open-
  position-per-ticker result, and reports maximum independent concurrent risk.
- [x] Add the deterministic post-fill chronological portfolio replayer
  (`batchsim portfolio`): it consumes sealed action records only, fails closed
  when actions and persisted P&L disagree, applies stable same-timestamp
  priority, enforces one open position per ticker, maximum open positions,
  maximum initial risk, and gross-notional buying-power limits, and writes an
  auditable `portfolio.json` artifact. On `cup-59x-v070`, the predeclared
  3-position / $1,500-risk / $50,000-gross contract accepted 25 of 37 leaf
  trades, rejected eight same-ticker overlaps and four capacity conflicts, and
  produced `$3,624.62` / `+0.123` effective R (versus `$8,497.49` / `+0.288`
  independently). This cohort is still exploratory and non-promotable.
- [x] Correct same-bar ordering in the portfolio replay: an exit on the exact
  timestamp of its own opening fill is processed after that fill, while exits
  from already-open positions release capacity before new entries. This avoids
  silently discarding valid one-bar trades while retaining conservative,
  deterministic ordering where daily bars have no truthful intrabar sequence.

**Public-PIT contract check — completed 2026-07-17:** the deterministic v0.7
run on `testset_sp500_public_pit_30` completed 30/30 leaves with no audit voids;
25 trades yielded `$4,725.60` / `+0.315` independent effective R and five
no-trades. Under the predeclared 3-position / $1,500-risk / $50,000-gross
portfolio contract, 21 trades were accepted and four were rejected by capacity,
for `$7,231.14` / `+0.482` portfolio effective R and `-$1,521.19` realized-P&L
maximum drawdown. The higher constrained outcome is selection, not alpha: all
four mechanically rejected entries happened to be losers in this small cohort.
This is a validation-only safety check, not an optimization target or promotion
result. **It is additionally superseded as performance evidence by the
continuous-state correction:** its scanner population was built before PIT
boundary cooldown resets were removed. Retain it only as historical harness
smoke evidence.

**Superseded 2025 development baseline — 2026-07-17:** the formerly sealed
`testset_sp500_public_pit_dev_2025` contains every eligible causal plan from
2025 (569 setups); the sealed 249-setup 2026-H1 cohort remains untouched.
The strict deterministic run completed all 569 leaves with zero voids and zero
indicator preseal failures: 385 trades / 184 no-trades, `$8,727.06`, and
`+0.031` portfolio-normalized independent effective R. Under the predeclared
3-position / `$1,500`-risk / `$50,000`-gross contract, only 53 of 385 entries
were feasible, producing `$-10,033.02` / `-0.035` effective R and a
`$-10,791.14` realized-P&L maximum drawdown. Of 332 deterministic rejections,
306 were the position limit, 21 the ticker limit, and five gross-notional.
The ticker-exclusive control was also negative (`-0.011` effective R). Treat
the independent-session gain as non-investable; do not open the 2026-H1
holdout or tune thresholds until a predeclared development-only selection
hypothesis is implemented.

**Why superseded:** that scanner run reset formation and cooldown state at PIT
interval boundaries. Keep its artifacts for audit history only; do not compare a
candidate with this 569-plan baseline or treat its P&L as a valid development
result.

**Superseded first-match continuous multi-year baseline — 2026-07-17:** the
former replacement public-PIT cohort,
`testset_sp500_public_pit_dev_2023_2025_continuous`, seals all 1,352 causal
plans from 2023–2025 under continuous ticker state. Deterministic v0.7
completed 1,352/1,352 leaves with zero voids: 940 trades / 412 no-trades,
`$16,924.78`, and `+0.025` independent effective R. Under the unchanged
3-position / `$1,500`-risk / `$50,000`-gross contract, only 151 trades were
feasible (789 capacity/ticker/gross rejections), for `$-23,212.76`, `-0.034`
effective R, and `$-27,213.38` realized-P&L maximum drawdown. By year, portfolio
effective R was `+0.016` (2023), `-0.077` (2024), and `-0.057` (corrected 2025).
The strategy is not investable under this contract; do not promote v0.7 or
interpret its independent-session result as capacity-adjusted alpha. It is
superseded by the deterministic geometry-selection population below.

**Geometry-selection v1 multi-year development baseline — completed
2026-07-17:** the replacement 1,305-plan cohort completed with zero voids:
899 trades / 406 no-trades, `$18,041.91`, and `+0.028` independent effective R.
The unchanged 3-position / `$1,500`-risk / `$50,000`-gross replay accepted 147
trades and rejected 752, producing `$-11,822.88`, `-0.018` effective R, and a
`$-18,693.36` realized-P&L maximum drawdown. This is materially safer than the
first-match corpus but still loses under the declared portfolio contract. Do
not promote it or reinterpret the independent gain as investable alpha.

**Predeclared frozen-plan regime veto — still unselected:** on geometry v1,
standing down unless SPY was above both SMA50 and SMA200 vetoed 146 of 1,305
plans. It improved independent effective R to `+0.064` and constrained P&L to
`$-4,545.14` / `-0.007` effective R with `$-13,365.43` realized-P&L maximum
drawdown. This is an encouraging development-only counterfactual, but it still
loses, changes the scanner population indirectly if made a gate, and has no
untouched holdout result. It is not a selected portfolio or scanner rule.

- [ ] Extend the replay with point-in-time sector concentration and
  mark-to-market portfolio heat/drawdown. The current drawdown is realized-P&L
  only; it deliberately never invents intraday portfolio marks from leaf data.

### Exit-policy research

The v0.6 engine-owned half-at-T1/remainder-at-T2 plus breakeven stop is the baseline. Only on frozen scanner plans, compare a small pre-registered set of execution policies (for example current ladder versus a trailing remainder). Use the same conservative OHLC, gap, slippage, fee, and participation model.

Do not tune T1/T2 fractions, ATR stop distance, arm expiry, or gap budget from the current cohort. Current v0.6 P&L is concentrated in two T2 trades.

## Deferred

- ML/CNN/SVM pattern classification: defer until there are many independently labeled formations, a point-in-time universe, purged time-series validation, and a strict untouched test period.
- Earnings/fundamental/CAN SLIM filters: defer until a reliable point-in-time fundamental and event-data source is available.

## Evaluation protocol before promotion

1. Build a multi-year point-in-time universe spanning multiple market regimes.
2. Reserve the latest chronological period as a final untouched holdout.
3. On development data, use walk-forward folds and predeclare feature formulas, thresholds, and selection criteria.
4. Report signal count, fill rate, no-trade rate, void rate, win rate, expectancy in R, profit factor, drawdown, MAE/MFE, tail loss, and exposure.
5. Re-run the frozen version on the untouched holdout with unchanged execution assumptions and compare against the current v0.6 baseline.
6. Promote only if the improvement is stable across folds/regimes and remains economically meaningful after conservative costs and gap handling.
