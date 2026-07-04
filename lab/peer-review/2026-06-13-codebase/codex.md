# Strategy Lab Comprehensive Codebase Review

**Reviewer:** Codex  
**Date:** 2026-06-13  
**Scope:** `/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab`

## Executive verdict

The codebase has a sound high-level separation between strategy definitions,
execution, orchestration, storage, validation, and market-data providers. The
market-data subsystem is substantially more defensive than a typical research
harness, and the non-network test suite is healthy.

However, several defects directly invalidate or weaken decision-grade results:

1. Every current `o03` production backtest can trade before the opening range is
   known.
2. `o03`'s local model artifact is ignored by git, omitted from the run
   signature, fitted on all 2024 labels, and used under a production policy that
   differs materially from the policy that produced the reported research
   metrics.
3. `d06` uses the completed breakout bar to decide whether an intrabar fill was
   above VWAP.
4. Headline realized-R and "account return" metrics are not net of fees and do
   not enforce portfolio-level leverage or concurrent-risk constraints.
5. Historical universes are built from today's active assets and therefore have
   known survivorship bias.
6. The pooled run validator is wrong when runs contain overlapping dates.
7. The run signature and resume logic are insufficient to guarantee that a run
   was completed under one immutable code, data, universe, model, and execution
   configuration.

Until the critical items below are fixed, the following should not be treated as
decision-grade:

- All stored `o03` results.
- All stored `d06` results.
- Any pre-2025 `o03` result produced with ML enabled.
- Dashboard "Model Equity @1% Risk" and
  `account_return_pct_at_1pct_risk`.
- Pooled validation results for runs whose calendars overlap.
- Historical performance interpreted as point-in-time, survivorship-free
  evidence.

## Review method

- Read repository guidance, specifications, roadmaps, strategy releases,
  shared variants, execution, metrics, runner, storage, dashboard, validation,
  universe builders, provider routing, and tests.
- Traced data from provider/cache through `StrategyContext`, candidate ranking,
  signal construction, execution, persistence, metrics, and reporting.
- Inspected 119 Python files and 29 test modules. The working tree is about 33 GB,
  primarily market data and DuckDB history.
- Ran:
  - `python3 -m compileall -q trading/lab`: passed.
  - `python3 -m pytest trading/lab/tests -q -m 'not network'`:
    **222 passed, 31 deselected**.
  - Ruff was unavailable in the environment.
- Built deterministic reproductions for the `o03` lookahead, `d06` VWAP
  lookahead, pooled-validation distortion, cutoff timing, and non-standard JSON.

The passing tests indicate that the main problems are missing assertions and
contract coverage, not obvious red tests.

## Critical findings

### C1. `o03` can enter before the five-minute opening range exists

**Files:** `runner/pipeline.py:622-634`,
`core/execution.py:318-367`, `strategies/stocks_in_play_orb/o03.py:222-269`

The breakout branch removes 1-minute bars inside the setup's opening five-minute
bar:

```python
sim_bars = sim_bars[
    sim_bars.index >= signal.signal_time + timedelta(minutes=5)
]
```

The pullback branch does not. `simulate_pullback_limit_long()` only filters
`bars.index > signal.signal_time`, so a signal timestamped 09:30 can detect a
breach at 09:31 and fill a pullback at 09:32 against a 09:30-09:35 high that is
not known until 09:35.

A deterministic reproduction produced:

```text
entry_time = 2024-01-02T09:32:00-05:00
breach_before_or_close = True
```

This is direct lookahead and invalidates all current `o03` production results.

The implementation also contradicts the release contract. The `o03` docstring
says the breach is the first **1-minute close** above the opening-range high
(`o03.py:24`), while the simulator uses `high > trigger`
(`execution.py:340-343`). This changes breach timing and trade eligibility.

**Required fix:**

- Represent setup availability explicitly, ideally as `signal_available_at`.
- For a left-labeled 09:30 five-minute bar, do not inspect bars before 09:35.
- Detect breach using the 1-minute close if that remains the release rule.
- Add a regression test that no `o03` breach or entry can occur before 09:35.
- Invalidate and rerun prior `o03` backtests.

### C2. `o03`'s model identity is neither versioned nor reproducible

**Files:** `.gitignore:8-11`, `o03.py:51-100`,
`runner/pipeline.py:64-100`

The model used by `o03` is:

```text
strategies/stocks_in_play_orb/research/artifacts/lgbm_orb_v2.pkl
```

The file is explicitly ignored by git. The tracked repository therefore does
not contain the production model. A fresh clone silently changes `o03` from ML
ranking to RV ranking because `_load_model()` catches absence/load errors and
returns `None`.

The run's `code_signature` does not hash the artifact, its SHA, its feature
schema, LightGBM version, or `O03_DISABLE_ML`. The current artifact contains only
`model` and `features`; it has no training cutoff, dataset hash, package
versions, hyperparameters, or provenance metadata.

Thus two runs with the same release ID and code signature can execute different
strategies:

- ML ranking using one local pickle.
- ML ranking using a different local pickle.
- RV fallback because the pickle or LightGBM is unavailable.
- RV fallback because `O03_DISABLE_ML=1`.

**Required fix:**

- Store the artifact in a versioned artifact registry or content-addressed
  release bundle.
- Persist artifact SHA-256, training cutoff, feature schema, package versions,
  and execution mode on every run.
- Fail closed when the model required by an ML release is unavailable. A
  fallback is a separate release identity, not the same release.

### C3. The `o03` artifact and reported v2 research metrics do not validate the
production release

**Files:** `research/train_and_simulate.py:64-136,169-252`,
`research/build_dataset.py:126-232`, `o03.py:53-56,146-270`

The research policy that produced `oos_metrics.json` is materially different
from production:

| Dimension | Research v2 | Production `o03` |
|---|---|---|
| Selection | top 5 | top 10 |
| OR window | adaptive 3/5/10m | fixed 5m |
| Entry | confidence chooses stop, pb02, or pb05 | always strict pb02 |
| Pullback latency | main v2 uses optimistic "loose" fill | strict next-bar fill |
| Sizing | probability-scaled 0.25x-2x then portfolio leverage scaling | flat 1% per trade, independent cap |
| Portfolio cap | shared 4x across selected positions | 4x independently per position |
| Label | hit +2R before stop under stop-entry geometry | production has no target and uses pullback PnL |

The script reports walk-forward OOS metrics, then fits the serialized final model
on **all** rows, including the rows previously treated as OOS:

```python
final_model.fit(df[FEATURES], df["label"])
```

That artifact cannot be used to reproduce the walk-forward OOS predictions. It
also creates lookahead if applied to any 2024 date and obvious future leakage
when applied to 2022-2023 dates. The code merely comments that users must set
`O03_DISABLE_ML`; it does not enforce a training cutoff.

**Required fix:**

- Treat the published production policy as the unit of validation.
- Produce date-versioned, expanding-window model artifacts, or use one artifact
  only after its training cutoff.
- Never fit the artifact used to claim OOS performance on its OOS labels.
- Rerun research using exact production selection, entry, latency, sizing,
  cost, and portfolio rules.

### C4. Run signatures and resume behavior can mix incompatible experiments

**Files:** `runner/pipeline.py:64-100,317-399,808-875`,
`scripts/backtest.py:60-102`

`compute_code_signature()` hashes the leaf release, a few engine modules, and a
sibling `common.py`. It omits important behavior:

- `strategies/*/variants.py`, which defines d02-d10, o04-o09, and f02-f05.
- `research/signal_helpers.py`.
- Market-data normalization, provider, calendar, storage, and cache semantics.
- Model artifacts and model mode.
- Universe YAML content.
- Testset YAML file content as an immutable file hash.
- Dependency versions.

For example, changing `post_gap_opening_drive/variants.py` changes d02-d10
semantics without changing those releases' code signatures.

Resume validation checks only `release_id` and testset name. It then uses the
current:

- `ExecutionConfig()`.
- CLI candidate limit.
- testset and universe file contents.
- code signature and release implementation.
- model artifact/environment mode.
- provider/cache contents.

The stored `execution_config_json`, `testset_config_json`, and code signature are
not reloaded or compared. A resumed run can therefore contain sessions produced
by different experiments while retaining one run ID.

**Required fix:**

- Create a canonical run manifest containing hashes of all imported strategy
  modules, engine modules, artifact, universe, testset, dependency lock, and
  execution parameters.
- Persist candidate-limit and data-refresh/provider settings.
- On resume, load the stored manifest and reject any mismatch.
- Prefer immutable run snapshots over mutable file references.

### C5. `d06` VWAP uses information printed after the simulated fill

**Files:** `core/execution.py:72-115`,
`strategies/post_gap_opening_drive/d06.py`

At a breakout, the simulator computes the cumulative VWAP using the complete
OHLCV row for the breakout bar, then compares the prospective intrabar entry to
that VWAP. The completed bar's close, low, high, and total volume are not known
at fill time.

A deterministic reproduction held open/high/low/volume constant and changed only
the breakout bar's final close:

```text
close 99.0  -> trade filled
close 102.0 -> NO_FILL
```

The entry decision therefore depends on future information inside the same bar.
Because d06 uses 5-minute execution, the lookahead window can be almost five
minutes.

The zero-volume behavior also fails open: NaN VWAP means no gate.

**Required fix:**

- Evaluate against VWAP known immediately before the triggering bar, or use
  1-minute/tick sequencing and update VWAP only with information available at
  each decision point.
- Fail closed when a mandatory VWAP cannot be computed.
- Invalidate and rerun all d06 results.

### C6. Headline R/account metrics overstate economic performance

**Files:** `core/execution.py:404-442`, `core/metrics.py:6-36`,
`scripts/dashboard.py:314-350,1011-1021`

`pnl_pct` subtracts fees, but `realized_r` does not:

```python
realized_r = (exit_price - entry_price) / planned_risk
```

Slippage is reflected in fill prices, but round-trip fees are absent from R.
`total_realized_r`, `avg_realized_r`, the sign-flip validation series, and
`account_return_pct_at_1pct_risk` are therefore systematically optimistic.

The dashboard then compounds each day's sum R as if every trade took exactly 1%
account risk. It explicitly ignores:

- Per-trade leverage clipping.
- Shared capital and margin.
- Concurrent positions.
- Aggregate risk exposure.
- Strategy releases that do not calculate quantity at all.
- Fees in R units.

Ten simultaneous "1% risk" trades can represent 10% account risk. A testset
candidate limit of 25 can imply much more. Independent per-position 4x caps do
not create a portfolio 4x cap.

Calling these values "decision-grade" and "Model Equity @1% Risk" is too strong.

**Required fix:**

- Compute net R after fees.
- Persist quantity and dollar PnL for every release.
- Add a chronological portfolio simulator with shared cash, buying power,
  leverage, concurrency, and max-risk limits.
- Keep unsized trade-quality metrics separate from executable account returns.

### C7. The historical "point-in-time" universe has known survivorship bias

**Files:** `scripts/build_universe.py:2-12,61-85`,
`universes/liquid_pit.yaml`

Historical snapshots are screened from Alpaca's **current active asset list**.
Stocks delisted before the universe was built are absent from old snapshots.
This tends to remove failures and flatter historical results, especially early
years.

The limitation is documented, which is good, but `universe_policy:
point_in_time` and filenames such as `liquid_pit` can still be interpreted more
strongly than the data supports.

**Required fix:**

- Source historical security-master membership including delistings, symbol
  changes, mergers, bankruptcies, and listing dates.
- Version the security master and snapshot source.
- Until then, label results as current-survivor-screened historical tests and
  treat early-period results as upper bounds.

## High-severity findings

### H1. d01-d10 use coarse 5-minute execution despite known tight-stop bias

**Files:** `post_gap_opening_drive/variants.py`, `runner/pipeline.py:636-652`

The pipeline comment states that 5-minute same-bar stop-first ordering overstated
losses by about 40% for tight ORB stops, which is why o04-o09 require 1-minute
bars. The d-family also uses opening-candle stops and explicitly investigates
"noise clip-outs," yet no d release declares `requires_rth_1m`.

This can make the engine's conservative OHLC ordering drive the conclusion being
studied. d09/d10 are especially sensitive because their hypothesis is stop
width.

**Recommendation:** Require 1-minute simulation for the d-family or report
1-minute results plus explicit optimistic/conservative same-bar bounds.

### H2. Time cutoffs use the close of a bar that ends after the stated cutoff

**Files:** `core/execution.py:57,175-178`,
`post_gap_opening_drive/d01.py:131-132`

Bars are left-labeled. Including a 5-minute bar with label 11:30 and then exiting
at its close uses the price at approximately 11:35 while recording the exit time
as 11:30. A reproduction confirmed that a cutoff of 11:30 consumes the 11:30
bar's close.

This directly contradicts d01/d03's "flatten at 11:30" contract. The same
label/close ambiguity affects 15:55 and 15:59 exits, though 15:55 on a 5-minute
bar may intentionally approximate the 16:00 close.

**Recommendation:** Define times as bar-open or bar-close timestamps and expose
`exit_at` semantics. For an exact wall-clock cutoff, use the last bar whose end
is no later than the cutoff or an explicit cutoff quote.

### H3. Pooled validation is mathematically wrong for overlapping run dates

**Files:** `scripts/validate_run.py:69-89`,
`validation/run_stats.py:23-35`

Pooling sums `n_days` across runs, but `daily_r_series()` groups trades only by
calendar date. If two runs both include January 2, their R is merged into one
observation and an artificial zero day is appended to reach the summed day
count.

Reproduction:

```text
two overlapping run-days: +1.00R and -0.25R
constructed series: [0.75, 0.0]
```

This distorts variance, bootstrap intervals, annualized pace, and sign-flip
p-values.

**Recommendation:** Key pooled observations by `(run_id, trade_date)`, or merge
calendars intentionally and set `n_days` to the union size. Reject ambiguous
pooling modes.

### H4. Walk-forward permutation logic preserves one real OOS bar

**Files:** `validation/gates.py:99-128`,
`validation/permutation.py:33-75`

`walkforward_permutation_test()` passes
`start_index=train_lookback`. `permute_bars()` preserves rows through
`start_index` inclusive and permutes only `start_index + 1:`. The first OOS bar,
at index `train_lookback`, is therefore never permuted.

**Recommendation:** Pass `train_lookback - 1`, clarify inclusive/exclusive
semantics, and add an assertion that every OOS row is eligible for permutation.

### H5. Intraday OOS years are miscomputed in the permutation CLI

**File:** `scripts/permutation_gate.py:136-140`

All intraday timeframes use `252 * 390` bars/year. Correct approximate values are
390 for 1-minute, 78 for 5-minute, and 26 for 15-minute RTH bars. A multi-year
5-minute test can be classified as roughly one-fifth of its real duration and
receive the weaker one-year p-value threshold.

**Recommendation:** Use timeframe-specific bars/session and the actual calendar
span.

### H6. Monte Carlo p-values can report impossible certainty

**Files:** `validation/gates.py:50-54`,
`validation/run_stats.py:48-52,103-108`

P-values use `better / n`, so zero exceedances produces `p=0`. For finite Monte
Carlo tests, use an add-one correction such as `(better + 1) / (n + 1)`.

The module documentation says 100 or 1,000 permutations are minimums, but the
functions do not enforce them. The screen's `p > 0.5` kill threshold is also a
very weak evidence threshold and should not be presented as statistical
validation.

**Recommendation:** Apply finite-sample correction, enforce minimum iteration
counts, report Monte Carlo uncertainty, and separate screening heuristics from
confirmatory significance.

### H7. The 1-minute completeness tolerance is too permissive for execution

**Files:** `marketdata/config.py:118-120`,
`marketdata/fetcher.py:440-488,650-692`,
`marketdata/storage.py:540-565`

`COMPLETENESS_TOLERANCE_1MIN_RTH = 0.13` allows roughly 50 of 390 RTH minutes to
be missing while a date is marked complete. The fast path then trusts the
sidecar and does not check exact labels.

Sidecar completeness is based on row counts by date, not exact expected
timestamps. Off-grid or duplicate-quality bars can inflate the count. Missing
entry, stop, target, or closing minutes can materially change a strategy while
the dataset remains "complete."

**Recommendation:** Use exact expected-label coverage for research-grade data,
lower the threshold substantially, and separately classify no-trade minutes
from provider/data holes.

### H8. Historical provider-empty results become permanent after seven days

**Files:** `marketdata/ttl.py:132-180`,
`marketdata/fetcher.py:323-360`

An authoritative provider response below coverage can cause unresolved dates to
be negative-cached as `provider_empty`. Once the date is more than seven
calendar days old, that absence never expires. A provider truncation,
misclassification, temporary entitlement issue, or symbol mapping problem can
therefore become permanent without `force=True`.

**Recommendation:** Preserve provenance for why a date is empty, periodically
audit permanent negatives, and require stronger confirmation before making an
absence immutable.

### H9. Runs do not capture market-data lineage

**Files:** `marketdata/fetcher.py`, `marketdata/storage.py`,
`runner/pipeline.py:808-875`

Cached partitions can be updated, merged from multiple providers, or refreshed
after a run. The run records no:

- Data snapshot ID or partition hashes.
- Provider contribution map.
- Retrieval timestamps.
- Coverage quality summary.
- Force-refresh setting.
- Negative-cache state.

The same code and config can therefore produce different results later with no
way to reconstruct the original input bars.

**Recommendation:** Create a data manifest per run/session with content hashes
or immutable snapshot references and provider/coverage metadata.

### H10. `build_universe` can leak stale, no-longer-candidate symbols

**Files:** `scripts/build_universe.py:88-100,141-171`

When the cache covers the requested symbols, `fetch_daily_history()` returns the
entire cached DataFrame, including symbols not in the current candidate list.
`screen_snapshot()` does not filter it back to the current symbols. A rebuilt
universe can therefore retain symbols removed by the current asset/name screen.

The cache also has no source-date, criteria, provider, or candidate-list
provenance.

**Recommendation:** Filter cached rows to the requested symbol set and store a
cache manifest. Handle the all-empty fetch case before `pd.concat`.

### H11. Strategy releases bypass the declared data-requirement contract

**Files:** `stocks_in_play_orb/variants.py:179-207`,
`stocks_in_play_orb/o07.py:32-37`,
`dominance_flip_reversal/variants.py:37-53`

`o07` and `f02` call `fetch_daily_context()` directly from strategy logic.
This bypasses `StrategyContext`, `force_data`, run-level lineage, and the
release-data contract. It also makes strategy evaluation depend on mutable
external state during candidate construction.

`f02` does not declare `requires_spy_daily`; `o07` declares it but ignores the
hydrated context because the context lookback is too short.

**Recommendation:** Add declarative per-dataset lookback requirements and hydrate
all data in the runner. Strategy code should be pure over `StrategyContext`.

### H12. Stored order/fill records do not faithfully describe execution

**Files:** `runner/pipeline.py:1038-1125`,
`core/models.py:60-72`

- `_insert_order()` always records `order_type="stop"`, including `o03`
  pullback-limit orders.
- Pullback limit price and expiry are stored as null.
- Slippage is split equally across entry and exit fills even when the maker
  entry has zero slippage and all configured slippage is on the exit.
- `Signal.risk_per_share` returns zero for short signals because it assumes
  `entry - stop`.
- Quantity is null for d/f releases, preventing account reconstruction.
- Fill `fees` and `slippage` columns contain percentages, not dollar amounts;
  the schema names do not express the unit.

**Recommendation:** Persist actual order type, limit, trigger, expiry, leg-level
costs, directional risk, quantity, notional, and dollar PnL.

### H13. No uniqueness guard prevents duplicate run-days

**Files:** `storage/duckdb.py:76-94`,
`runner/pipeline.py:376-381,556-577`

There is no unique constraint on `(run_id, trade_date)`. Overlapping testset
ranges or repeated execution can create multiple sessions for one run/date and
double-count results. The current checked-in testsets have no overlaps, but the
loader does not enforce that invariant.

**Recommendation:** Validate and deduplicate date ranges, and add a uniqueness
constraint or explicit attempt/version model.

## Medium-severity findings

### M1. Same-bar OHLC ordering can dominate results

**File:** `core/execution.py:139-153,245-255`

The simulator assumes the stop occurs before the target whenever both are
reachable in one bar. This is a defensible conservative bound, not a unique
historical outcome. It is especially material for tight stops and 5-minute
bars.

Report both stop-first and target-first bounds, use finer data where available,
and measure how many trades are ambiguous.

### M2. MFE/MAE use portions of the entry bar that may precede the fill

**File:** `core/execution.py:120-123,232-235,356-366`

Pullback entry MFE/MAE uses the entire fill bar. Breakout MAE uses the whole bar
low/high while MFE starts at zero. These are inconsistent and cannot distinguish
pre-fill from post-fill movement.

Use lower-resolution sequencing or mark entry-bar excursion as interval-censored.

### M3. `realized_r` uses planned trigger risk rather than actual fill risk

**File:** `core/execution.py:421-425`

This is documented, but pullback fills below the trigger and gap fills above it.
Planned-risk R is useful for comparing sizing plans; actual-risk R is useful for
execution quality. Persist both rather than overloading one value.

### M4. First-opening-bar stamping is ambiguous

**Files:** `research/filters.py:50-58`,
`stocks_in_play_orb/common.py:90-100`,
`runner/pipeline.py:641-650`

`first_regular_5m_bar()` first accepts 09:30-09:34, then falls back through
09:35. A close-stamped 09:35 bar is accepted, but the breakout 1-minute filter
then adds another five minutes and begins at 09:40, skipping valid post-range
minutes.

`or_start_minute` records the discrepancy but no release rejects or adjusts it.

Normalize providers to one bar-label convention at ingestion and assert the
expected opening timestamp.

### M5. Testset and universe loaders accept invalid configurations silently

**Files:** `data/testsets.py`, `data/universes.py`

There is no validation for:

- `start <= end`.
- Overlapping ranges.
- Positive candidate limit.
- Exactly one of `universe` or `tickers`.
- Requested `universe_policy` matching the universe file's policy.
- Duplicate snapshot dates.
- Non-empty snapshots.
- A universe snapshot existing before the first test date.
- Testset file name matching its internal name.

An absent eligible universe snapshot returns `[]`; the runner can complete a
zero-trade session without distinguishing configuration failure from no setups.

### M6. Calendar fallback can create fake weekday sessions

**File:** `runner/pipeline.py:40-61`

If the exchange calendar fails, `_trading_days()` falls back to weekdays and
treats holidays as trading days. Those dates can become completed zero-trade
sessions and alter validation denominators.

For decision-grade runs, fail closed when the exchange calendar is unavailable.

### M7. Input models lack validation

**Files:** `core/models.py`, `marketdata/storage.py:51-96`

The engine accepts negative fees/slippage, negative stop-limit offsets,
non-finite prices, invalid long/short stop geometry, naive times, and malformed
metadata. Storage drops NaN OHLC rows but does not validate:

- Positive prices.
- `high >= max(open, close)`.
- `low <= min(open, close)`.
- Non-negative volume.
- Expected timestamp grid/session.

Add validation at strategy, execution, and storage boundaries.

### M8. Cache corruption is converted to "no data"

**File:** `marketdata/storage.py:240-309`

Broad read exceptions log an error and return an empty DataFrame. Callers cannot
distinguish an empty dataset, an OS/resource problem, and corrupt Parquet.
`CorruptDataError` exists but is not raised here.

Raise typed errors or return a structured result so the runner can fail a
session instead of silently treating corruption as absence.

### M9. Public datetime semantics are inconsistent

**Files:** `marketdata/fetcher.py:178-185`,
`marketdata/calendar.py:110-150`,
`marketdata/storage.py:223-231`

- `fetch_bars()` treats naive start/end as UTC.
- `expected_bars()` documents and treats naive start/end as New York time.
- `read_bars()` passes naive values into filters without localization.

A direct caller can shift a request by four or five hours depending on which
layer it uses. Require aware datetimes, or choose and enforce one naive
convention.

### M10. YFinance does not implement the claimed split-only semantics

**File:** `marketdata/providers/yfinance_provider.py:27-116`

For `adjustment="split"`, the provider uses `auto_adjust=False` and returns the
raw OHLC columns. That does not by itself split-adjust historical OHLC. The
capability declaration therefore overstates what the provider supplies.

Either implement split-only adjustment from split events or remove that
capability.

### M11. Dependency manifests are incomplete and unpinned

**Files:** `strategy_lab/requirements.txt`, `engine/requirements.txt`

The lab requirements omit imports used at runtime, including `pyyaml`,
`python-dotenv`, `filelock`, and `requests`. The engine requirements omit core
lab dependencies such as DuckDB and exchange calendars. ML dependencies are
commented out even though `o03` can use them.

Versions are broadly unbounded despite API-sensitive code and Python 3.9
compatibility comments. Reproducible research needs one locked environment and
recorded package versions.

### M12. Database schema has no migration/versioning mechanism

**File:** `storage/duckdb.py:53-238`

`CREATE TABLE IF NOT EXISTS` does not evolve existing databases when columns,
constraints, or semantics change. There are no foreign keys, schema version,
or indexes for common run/session/trade lookups.

Introduce explicit migrations and integrity constraints.

### M13. Timezone-aware values are stored in timezone-naive DuckDB columns

**Files:** `storage/duckdb.py:56-190`,
`scripts/dashboard.py:452-481`

All time columns are `TIMESTAMP`, not `TIMESTAMPTZ`. The dashboard then assumes
DuckDB's naive datetimes are in the machine timezone and calls `.timestamp()`.
Moving the DB or dashboard to a machine with another timezone can shift chart
markers.

Store UTC instants explicitly with `TIMESTAMPTZ` or integer epoch values.

### M14. Long DuckDB transactions include strategy computation

**File:** `runner/pipeline.py:603-686`

The runner begins a write transaction before candidate signal construction and
simulation and holds it for the entire loop. This increases lock contention
between concurrent runs and makes a slow strategy or data operation hold the
writer unnecessarily.

Compute immutable rows in memory, then open a short bulk-write transaction.

### M15. Cache metadata updates can use large amounts of memory

**Files:** `marketdata/fetcher.py:650-692`,
`marketdata/storage.py:433-470`

Coverage updates load the full affected range into pandas just to count rows.
Parallel multi-year 1-minute prefetches can create large simultaneous frames.
The parsed `_META_CACHE` is also unbounded by count or bytes.

Use Parquet/DuckDB aggregation and a bounded metadata cache.

### M16. Provider registry and client lifecycle are fragile

**Files:** `marketdata/provider.py:92-130`,
`marketdata/providers/alpaca_provider.py:169-230`

- Provider registration has no deduplication.
- `max_lookback_days` is declared but not enforced.
- One lazily initialized `requests.Session` is shared across parallel workers
  without synchronization; Requests does not promise that arbitrary concurrent
  mutation/use of a Session is safe.
- Tickers are interpolated into URLs and filesystem paths without a central
  validation policy.

Use per-thread sessions or a thread-safe client pool, deduplicate registry
entries, enforce capabilities, and validate canonical symbols.

### M17. `o03` feature extraction can crash on artifact skew

**File:** `stocks_in_play_orb/o03.py:201-210`

Every artifact feature is indexed directly from every candidate dict. A missing,
renamed, non-finite, or null feature crashes the session. Validate the artifact
schema once and fail with an explicit release/artifact incompatibility error.

### M18. `o05` admits large gap-down stocks into a long-only strategy

**Files:** `stocks_in_play_orb/variants.py:73-83`,
`stocks_in_play_orb/o05.py`

`o05` filters `abs(gap_pct) >= 3%`, but directional gap checks run only when
`allow_short=True`. In long-only mode a stock gapping down 3% can qualify if its
first candle is green. That may be intentional reversal behavior, but it
conflicts with the "extreme-gapper continuation" framing.

Use a signed long-gap condition or rename/document the setup.

### M19. d01 remains exposed to raw-price split/glitch days

**Files:** `post_gap_opening_drive/d01.py`, `d05.py`

Only d05 applies `has_split_like_jump`. Raw daily and intraday scale consistency
avoids one class of adjusted/raw mismatch, but an actual split day can still
create a false historical gap and distorted prior high. d05 being a diagnostic
does not protect baseline d01 conclusions.

Apply data-integrity guards below the release layer so every strategy receives
valid bars without changing strategy identity.

### M20. Indicator implementations differ from canonical Wilder seeding

**File:** `dominance_flip_reversal/common.py:48-65`

RSI and ATR use pandas `ewm(adjust=False, min_periods=period)`, which does not
explicitly seed with the initial period's simple average as the daily ATR helper
does. Early same-day values, where f-family signals are most sensitive, can
differ from canonical Wilder values.

Add reference-vector tests against the intended formula and document the chosen
definition.

### M21. f03 can carry stretch/divergence state across overnight gaps

**Files:** `dominance_flip_reversal/variants.py:71-93`,
`dominance_flip_reversal/common.py:88-148`

Warm-starting by concatenating prior sessions is useful for indicator seeding,
but the setup's consecutive stretch and divergence search can also span the
overnight/session boundary. That is a stronger semantic change than merely
warming indicators.

Seed indicator state from history, but reset intraday setup-state machines at the
session boundary unless overnight continuity is explicitly part of the release.

### M22. The report/dashboard can select incomplete or failed latest runs

**Files:** `scripts/report.py:36-60`,
`scripts/dashboard.py:55-84,152-183`

Latest metric selection does not require a completed status. The testset detail
intentionally chooses the newest run even if it is running or failed, hiding the
most recent completed result. `completed_with_errors` runs are summarized from
successful dates and remain available for comparison.

Expose "latest attempt" and "latest completed valid result" separately. Never
promote partial-run metrics without an explicit missing-session warning.

### M23. Infinite profit factor produces invalid JSON for browsers

**Files:** `core/metrics.py:22`, `scripts/dashboard.py:588-595`

No-loss results use `float("inf")`. Python's `json.dumps` emits `Infinity`,
which is not valid JSON and is rejected by browser `JSON.parse`/`response.json`.
A no-loss run can therefore break an API response.

Serialize non-finite values as null or a tagged string and set
`allow_nan=False` to catch violations.

### M24. Candidate selection is not fully auditable

**File:** `runner/pipeline.py:581-610`

`candidate_limit` is applied before persistence, so eligible candidates beyond
the limit disappear from the database. A candidate whose signal is rejected
does not carry a structured rejection reason. A signal is persisted only after
the simulator returns a trade/no-fill object.

Persist the full ranked candidate set, selection flag, rejection stage, and
reason.

### M25. Dashboard trade detail can block all requests and database access

**Files:** `scripts/dashboard.py:398-529,532-576,1584-1595`

The server is single-threaded. `/api/trade` holds a read-only DB connection while
it may fetch market data over the network. One slow provider call blocks the
entire dashboard. `kill_process_on_port()` can also terminate an unrelated
process occupying the configured port without confirmation.

Use `ThreadingHTTPServer`, release DB access before network work, add timeouts,
and never kill an arbitrary port owner automatically.

### M26. Dashboard/testset totals mix incomparable experiments

**Files:** `scripts/dashboard.py:87-149,897-963`

Overview totals sum the latest metric for every release and testset. Those rows
can have different code signatures, configs, universes, date ranges, and
strategy families. The aggregate is not a portfolio or a statistically
meaningful total.

Restrict aggregation to compatible manifests or label the values as simple
row summaries rather than performance.

### M27. Position sizing conventions are inconsistent

**Files:** `stocks_in_play_orb/o02.py:113-124`,
`stocks_in_play_orb/variants.py:146-150`

`o02` rounds quantity, while later variants floor it. Rounding can exceed the
computed leverage cap. All implementations force at least one share, which can
also violate a cap for an extreme price.

Centralize portfolio sizing and always floor after all constraints, allowing
zero shares when the trade is not affordable.

### M28. The screen methodology is vulnerable to repeated-use overfitting

**Files:** `scripts/build_screen_testset.py`,
`testsets/screen_2022_2026_sampled.yaml`, strategy backlogs

The same 108 sampled dates are repeatedly used to kill, retain, diagnose, and
design follow-up variants. Even when each local batch is called
"pre-registered," repeated human feedback from the same screen turns it into
training data.

The claim that the sample is "unbiased" is also too strong given survivorship,
candidate caps, regime clustering, and event concentration.

Maintain a sealed holdout never used for ideation, rotate exploration screens,
track the number of tried hypotheses, and use multiple-testing-aware promotion
criteria.

### M29. Sign-flip validation assumes exchangeable symmetric daily outcomes

**File:** `validation/run_stats.py:38-52`

Randomly flipping individual daily signs ignores volatility clustering, regime
dependence, day-of-week/event structure, and serial correlation. The
permutation package itself notes that destroying volatility clustering can
favor a strategy.

Add block/bootstrap or regime-stratified robustness checks and do not use one
sign-flip p-value as the sole promotion gate.

### M30. Public documentation and behavior have drifted

Examples:

- `fetch_bars()` docs say daily defaults to split-adjusted, but code defaults to
  raw (`marketdata/fetcher.py:143-175`).
- `DriveVariant` says d02-d04 while it now powers d02-d10.
- Several release "next intended" sections no longer match actual numbering.
- The base strategy contract says long-only while short simulation and
  directional metadata exist.

Documentation drift is a correctness risk in a research system because release
identity depends on exact semantics.

## Lower-severity opportunities

1. Use `itertuples()` or arrays instead of `iterrows()` in hot execution loops.
2. Bulk-insert candidates/signals/orders/trades after simulation.
3. Add indexes for run/session/trade dashboard queries.
4. Replace hardcoded connectivity probing of `data.alpaca.markets` with the
   active provider or remove the external probe.
5. Record failed prefetch tickers as session data-quality failures rather than
   allowing a later empty context to look like "no setup."
6. Add a bounded lifecycle for `_thread_locks`; it grows by dataset key.
7. Add provider request collapsing so concurrent identical misses do not issue
   duplicate network calls.
8. Add checksums and schema validation to universe/testset YAML caches.
9. Store run-start environment details: Python, OS, timezone, package lock,
   git commit, dirty-tree state, and relevant environment variables.
10. Separate immutable release code from mutable research scripts and artifacts
    with an explicit release packaging command.

## Missing regression tests

The following tests should be added before trusting reruns:

1. `o03` cannot breach or fill before the OR close.
2. `o03` breach requires close, not high, if that remains the documented rule.
3. Model artifact hash/mode is part of run identity; missing artifact fails
   closed.
4. Resume rejects changed code, config, testset, universe, artifact, or
   candidate limit.
5. d06's entry decision is invariant to post-fill breakout-bar close/volume.
6. Exact cutoff semantics for 1-minute and 5-minute bars.
7. Fee-net R and portfolio-level capital/leverage constraints.
8. Pooled validation with overlapping and disjoint calendars.
9. Every OOS bar is permuted in walk-forward tests.
10. Timeframe-specific OOS-year calculations.
11. Browser-valid JSON for infinite/NaN metrics.
12. Exact timestamp coverage for missing first, entry, stop, and final bars.
13. Permanent negative-cache audit and recovery.
14. Universe cache rebuild after the candidate list shrinks.
15. Close-stamped versus open-stamped provider bars.
16. Canonical Wilder RSI/ATR vectors.
17. f03 indicator warm start without overnight setup-state continuation.
18. Database uniqueness for one canonical session per run/date.
19. Corrupt Parquet produces an explicit failed session, not a no-data result.
20. All runtime imports are represented in a locked dependency manifest.

## Prioritized remediation plan

### Phase 0: invalidate and stop promotion

1. Mark existing `o03` and `d06` results non-comparable/invalid.
2. Stop presenting current R-compounded equity as executable account equity.
3. Prevent pre-training-cutoff ML inference automatically.

### Phase 1: fix execution accuracy

1. Introduce explicit signal availability and bar-label semantics.
2. Fix `o03` breach sequencing and close rule.
3. Fix d06 VWAP timing.
4. Move tight-stop d-family execution to 1-minute data or bounded intrabar
   outcomes.
5. Define exact cutoff execution.
6. Compute fee-net R and actual-risk R.

### Phase 2: make runs reproducible

1. Build a canonical immutable run manifest.
2. Version/hash model artifacts, universes, testsets, data partitions, and
   dependencies.
3. Make resume strict against the manifest.
4. Record provider/data lineage.

### Phase 3: repair statistical validation

1. Fix overlapping-run pooling.
2. Fix walk-forward permutation indexing and intraday-year calculations.
3. Apply finite Monte Carlo correction and minimum counts.
4. Add block/regime robustness and sealed holdouts.

### Phase 4: harden storage and operations

1. Tighten exact data completeness.
2. Audit permanent negative cache.
3. Add schema migrations, uniqueness, timezone-safe columns, and short write
   transactions.
4. Complete and lock dependencies.
5. Make dashboard/network behavior non-blocking and non-destructive.

## Final assessment

The engine is a capable research harness, but its current auditability is
stronger at the code-organization level than at the experiment-identity level.
The most important next step is not adding more strategy variants. It is making
one backtest a fully reproducible object: exact code, model, universe, testset,
bars, costs, portfolio constraints, and validation method.

After C1-C7 and H1-H13 are addressed, rerun affected strategies from clean,
content-addressed data/model manifests before using the backlog conclusions for
promotion or rejection decisions.
