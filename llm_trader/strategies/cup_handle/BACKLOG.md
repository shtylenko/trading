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

**Operational blocker (not a code defect):** no source-controlled historical
constituent file currently exists in this repository. Do not relabel
`universe_sp500.json` as PIT: it is explicitly a 2026-07-16 current snapshot.
Before any profitability/geometry conclusion, acquire or export an immutable
historical membership source, write the interval manifest, run `research_scan`,
and create a new provenance-sealed development/holdout pair from that corpus.

### Deterministic geometry selection

**Problem:** `_find_cup_and_handle` returns the first valid geometry. Iteration currently favors short handles and short cups, despite comments suggesting a different selection policy. Changing any boundary can therefore silently choose a different formation rather than merely tighten a filter.

**Plan:** enumerate all valid cup/handle candidates for a plan date, compute a fixed, explainable quality score, select the highest-scoring candidate with stable tie-breaking, and persist both chosen geometry and score components.

**Acceptance:** unit tests prove candidate order does not affect the selected formation; historical replays remain causal and reproducible.

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
