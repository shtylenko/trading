# Strategy Lab — Code Review Report

**Scope**: `trading/lab` (full package: core, runner, strategies, data, storage, marketdata, research, scripts, tests)  
**Reviewer**: Grok (orchestrated multi-pass review)  
**Date**: 2026-06-10  
**Status**: Findings only — no fixes applied  
**Prior reviews**: `peer-review/2026-06-09-sonnet46/feedback.md` (B-01…B-18), `peer-review/2026-06-09-fable5/feedback.md` (F-01…F-28)  
**Test run**: `149 passed` (offline subset; network tests excluded)

Severity key: 🔴 silently wrong results / data loss · 🟡 incorrect analytics or operational hazard · 🟢 quality / hygiene / efficiency

---

## Executive summary

`strategy_lab` is a well-structured research harness with clear layering (`core` → `runner` → `strategies`), deliberate conservative simulation semantics, and unusually deep coverage of the `marketdata/` subsystem. Since the 2026-06-09 peer reviews, several high-severity issues have been addressed: raw daily context by default, expanded `code_signature`, resume/per-session error isolation, pullback gap-through-stop handling in production simulation, negative-cache `provider_error` vs `provider_empty` distinction, Alpaca chunk-boundary fix, and scoped sidecar coverage reads.

The dominant remaining risks fall into four buckets:

1. **Marketdata cache semantics** — stale-but-`complete` partitions, expired negative-cache entries still masking gaps in Phase 1, and empty responses from misconfigured providers treated as confirmed empties.
2. **Research ↔ production drift (o03)** — the deployed ML artifact and headline OOS metrics describe a different policy than `o03.py` actually runs.
3. **Breakout simulator edge cases** — entry-bar gap-through-stop in `simulate_long_breakout` is inconsistent with pullback (which was fixed; note that the research dataset has the phantom profit issue on pullback entries).
4. **Agent-facing contract gaps** — stale `cli.txt`, duplicated metrics logic, and thin integration tests that mock away `_load_context`, giving false confidence on the paths agents are most likely to edit.

The engine is **usable for P0 baseline comparison** when run with raw daily data, split guards, and R-based metrics — but promotion decisions on o03 or broad-universe runs should treat current OOS numbers and `total_pnl_pct` with skepticism until the items in §C are addressed.

---

## 1. Architecture & design strengths

| Area | Assessment |
|------|------------|
| Package layout | Matches `spec.md`; responsibilities are separated cleanly. |
| Strategy contract | `StrategyRelease` + immutable release modules (`o01`, `o02`, `o03`, `d01`) are easy to reason about. |
| Simulation discipline | OR-bar exclusion (`execution.py:27-29`), stop-before-target ordering, strict pullback fills, maker/taker slippage split. |
| Data adapter | `data/market_data.py` documents and defaults to raw daily + pre-trade-date end — correct contract. |
| Shared filters | `strategies/stocks_in_play_orb/common.py` centralizes SIP gauntlet; `or_start_minute` records shifted OR bars. |
| Reproducibility | `compute_code_signature()` now hashes engine modules + per-strategy `common.py` (`pipeline.py:64-95`). |
| Resilience | Resume (`--resume`), per-session failure isolation, `max_failed_sessions`, progress derived from `sessions` table. |

---

## 2. Data correctness

### 🔴 R-01: Stale mutable-window data skipped when meta marks `complete=True`

**Files**: `marketdata/fetcher.py:340-343`, `fetcher.py:434-435`, `fetcher.py:170-175`

Phase 1 rejects cache when `is_stale()` is true for any partition. Phase 2 `_find_missing_dates()` then skips dates where `coverage[date].complete == True`. A Friday 1min RTH session fetched mid-day (~360/390 bars, within 13% tolerance → `complete=True`) becomes stale Monday (mtime > 2h), Phase 1 misses, Phase 2 skips Friday, Phase 3 returns the **stale partial day** with no refetch.

**Impact**: EOD/MOC exits simulated on truncated tails; o03 pullback fills degrade on incomplete 1m data. Silent, run-dependent.

**Recommendation**: When Phase 1 fails due to staleness, pass `ignore_complete=True` into `_find_missing_dates`, or derive refetch dates from per-partition `is_stale()` rather than the `complete` flag alone.

---

### 🔴 R-02: Expired negative-cache entries still suppress gap detection in Phase 1

**Files**: `marketdata/fetcher.py:353-357`, `marketdata/calendar.py:240-243`, `marketdata/spec.md:853+`

`_find_missing_dates()` correctly filters expired entries via `is_negative_cache_expired()` (`fetcher.py:422`). `_get_cached_data()` passes raw `neg_cache` into `coverage_gaps()`, which skips any date **present in the dict** regardless of expiry (`calendar.py:242-243`). An expired `provider_empty` entry causes Phase 1 to accept incomplete cached data as a HIT.

**Impact**: After a 24h TTL expires, gaps may never trigger refetch until `force=True`. Spec and implementation diverge — high agentic-coding risk.

**Recommendation**: Add `active_negative_cache()` helper that filters expired entries; use it in both `_get_cached_data` and `_find_missing_dates`.

---

### 🟡 R-03: Empty provider response (missing credentials) → 24h `provider_empty`

**Files**: `marketdata/fetcher.py:246-247`, `marketdata/providers/alpaca_provider.py:219-222`, `marketdata/providers/marketdata_provider.py:94-96`

`any_provider_responded = True` is set on **every non-exception return**, including empty `DataFrame` from missing Alpaca credentials. Those dates are negative-cached as `provider_empty` (24h), not `provider_error` (15m).

**Impact**: Misconfigured environments silently black out tickers for a day. Agents adding new providers may copy this pattern.

**Recommendation**: Only set `any_provider_responded` when the provider actually executed an authenticated request. Treat config-skip empties as errors or no-ops.

---

### 🟡 R-04: `fetch_bars` default adjustment asymmetry

**File**: `marketdata/fetcher.py:150-151`

```python
adjustment = "raw" if timeframe != "1day" else "split"
```

Direct `fetch_bars("X", "1day")` without explicit `adjustment` still defaults to split-adjusted daily. `data/market_data.py` correctly passes `adjustment="raw"`, but any new caller bypassing the adapter reintroduces F-01-scale bugs.

**Recommendation**: Default `1day` to `raw` everywhere, or require explicit `adjustment` (no silent default).

---

### 🟡 R-05: Opening-range bar fallback silently shifts setup by 5 minutes

**File**: `research/filters.py:53-57`

When the 09:30 bar is absent, fallback `between_time("09:30", "09:35")` returns the **09:35** bar. `or_start_minute` is recorded (`common.py:124`) but **not used to reject** candidates. Historical RV in `common.py:90-91` still groups `09:30–09:35` with `first()`, mixing stamp conventions.

**Impact**: Breakout triggers and RV denominators misaligned on provider holes. Rare but silent.

**Recommendation**: Fail closed when `or_start_minute != 0` for SSRN-parity releases, or align historical opening-bar selection with the same rule.

---

### ✅ F-01 (prior): Split-adjusted daily vs raw intraday — **largely fixed**

**File**: `data/market_data.py:104-127`

`fetch_daily_context` now defaults to `adjustment="raw"`, ends at `trade_date - 1`, and documents the mixing hazard. Strategies using `has_split_like_jump` (`filters.py:102-131`) provide a second guard. Residual risk: any caller overriding `adjustment="split"` or using `fetch_bars` directly without the adapter.

---

## 3. Backtest semantics & simulation

### 🟡 R-06: Breakout entry-bar gap-through-stop logic inconsistency

**File**: `core/execution.py:79-81`

On the entry bar, when `low <= stop` and `was_flat_at_open`, exit uses `stop` unconditionally. Unlike the pullback simulator, this does not book a phantom profit because the breakout entry price (`entry_price >= trigger`) is mathematically guaranteed to be greater than the stop-loss price (`stop_price < trigger` is enforced). Thus exit is always less than entry, booking a loss. However, exiting at `stop` when the bar opens below the stop is conceptually inconsistent with the pullback path and assumes the stop order fills at the stop price rather than the open of the gap.

The pullback simulator was fixed (`execution.py:192-193` uses `min(bar_open, stop)`). Breakout path (`o01`, `d01`, `o02` stop-order semantics) still uses the unadjusted stop.

**Recommendation**: Mirror pullback logic: `exit_base = min(bar_open, stop)` on entry bar for consistency. Add unit tests.

---

### 🟡 R-07: Pullback fill bar skips same-bar stop after normal limit fill

**File**: `core/execution.py:196-201`

After `low < limit` fill, the loop `continue`s without checking stop on that bar. Collapse path (`low <= stop` at 183) handles the overlap case; a fill with `stop < low < limit` may miss same-bar stop-out on coarse bars (5m fallback).

**Impact**: Minor on 1m; material when o03 degrades to 5m (`pipeline.py:548-549`).

---

### 🟡 R-08: Orphan signal/order rows when simulator returns `None`

**File**: `runner/pipeline.py:526-564`

`simulate_*` returns `None` for empty bars or `risk <= 0` (`execution.py:17-25`). Pipeline inserts candidate, signal, and order, then `if trade is None: continue` — ledger rows with no trade/fills.

**Impact**: Audit trail pollution; agents querying `signals` without joining `trades` overstate activity.

---

### 🟡 R-09: `realized_r` uses planned risk distance, not fill-to-stop

**File**: `core/execution.py:256`, `core/models.py:71-72`

Denominator is always `entry_trigger - stop_price`. Pullback fills below trigger produce R multiples that don't match actual fill risk. Documented in `mlspec.md` as conservative; sizing still uses full R (`o03.py:230-237`).

---

### 🟡 R-10: `gross_pnl_pct` naming / `slippage_pct` double-count trap

**Files**: `core/models.py:14-17`, `core/execution.py:252-267`

Slippage is baked into fill prices; `slippage_pct` is informational only. No docstring on `SimulatedTrade` fields warns downstream analytics. B-02 from prior review remains open.

---

### 🟢 R-11: Entry-bar MFE still includes pre-fill range (pullback only)

**File**: `core/execution.py:199-200`

Pullback sets full-bar MFE on fill bar; breakout correctly starts MFE at 0 (`execution.py:67`). Analytics-only.

---

### 🟢 R-12: `profit_factor` can be `inf`

**Files**: `core/metrics.py:22`, `runner/pipeline.py:662`

Zero-loss win streaks produce `float("inf")` in `metrics_json` — may break JSON consumers.

---

## 4. Metrics & reporting

### 🟡 R-13: Duplicated metrics logic — `compute_trade_metrics` is dead code

**Files**: `core/metrics.py:6-36`, `runner/pipeline.py:641-678`

`summarize_run` inlines metric computation from SQL rows (B-12 **fixed** for stored runs). `compute_trade_metrics` is **never imported** anywhere in the package. Two copies will diverge the moment an agent adds a metric to only one path.

**Recommendation**: Make `summarize_run` call `compute_trade_metrics` on reconstructed minimal objects, or delete the unused function.

---

### 🟡 R-14: `total_pnl_pct` remains a first-class column despite warnings

**Files**: `runner/pipeline.py:663-669`, `scripts/dashboard.py`, `scripts/report.py`

R-based fields (`total_realized_r`, `account_return_pct_at_1pct_risk`) are now computed and stored. `total_pnl_pct` is still the primary DuckDB column and dashboard sparkline input. F-06 partially mitigated but not resolved for agents reading `release_metrics.total_pnl_pct` first.

---

### 🟡 R-15: No portfolio-level risk budget across same-day signals

**Files**: `o02.py:113-124`, `o03.py:234-244`, `runner/pipeline.py`

Each selected name risks 1% independently. Top-10 o03 days can deploy ~10% theoretical risk before the 4× leverage cap per name. Metrics don't surface this concentration.

---

### 🟢 R-16: Dashboard cross-testset aggregation still sums unsized percent

**File**: `scripts/dashboard.py` (testset overview)

Compounds R-14 for multi-release views.

---

## 5. Marketdata performance & stability

### 🟡 R-17: `update_meta_summary` scans all partitions on every write

**File**: `marketdata/storage.py:569-643`

Footer statistics help, but fallback still reads full `timestamp` columns (`storage.py:617-623`). F-12 sidecar read is **fixed** (scoped to date range, `fetcher.py:504-513); summary scan remains O(partitions) per write.

---

### 🟡 R-18: 15-minute blocking retry per provider call

**Files**: `marketdata/retry.py`, `runner/pipeline.py:210-248`

Prefetch blocks up to 15 minutes per failing call; 330-ticker outage can stall for hours before `max_failed_sessions` abort. `CircuitBreaker` is exported (`marketdata/__init__.py`) but **not wired**.

---

### 🟡 R-19: 13% intraday completeness tolerance

**File**: `marketdata/config.py:119` (`COMPLETENESS_TOLERANCE_1MIN_RTH = 0.13`)

Up to ~51 missing 1min RTH bars/day accepted as complete. Comments in `fetcher.py:351-352` still say "5%". Agents "fixing" comments without reading config will reintroduce inconsistency.

---

### 🟡 R-20: Corrupt Parquet swallowed, never quarantined

**File**: `marketdata/storage.py:294-296`

`read_bars` catches all exceptions → empty DataFrame. `quarantine_corrupt` is imported in `fetcher.py:43` but unused.

---

### 🟡 R-21: DuckDB single-writer contention

**Files**: `storage/duckdb.py`, `scripts/dashboard.py:436`

Dashboard uses `read_only=True` (F-25 partially fixed). Pipeline and concurrent ad-hoc writers can still block. No schema version / migration table.

---

### 🟢 R-22: TTL uses calendar days for "today/yesterday" predicates

**File**: `marketdata/ttl.py`

Friday data can be treated immutable on Monday (3 calendar days). Interacts with R-01 for partial Friday sessions.

---

### ✅ Prior fixes confirmed in current code

| Prior ID | Fix |
|----------|-----|
| F-02 / B-07 | `provider_error` (15m) vs `provider_empty` (24h) (`fetcher.py:276-283`) |
| F-12 | Scoped `_update_sidecar_coverage` read (`fetcher.py:504-513`) |
| F-14 | Alpaca half-open chunk cursor (`alpaca_provider.py:249-252`) |
| F-05 | Providers filter `15:59` (verified in provider modules) |
| F-09 | Resume + per-session isolation (`pipeline.py:270-447`) |
| F-10 | Candidate dedup (`pipeline.py:500-515`) |
| F-16 | `_contiguous_date_runs` (`fetcher.py:376-391`) |
| F-18 | OHLC `dropna(how="any")` in storage |
| B-06 | Wilder's ATR in `filters.py` |
| B-10 | `db_conn` naming in insert helpers |
| B-11 | UTC `run_id` timestamps |
| B-12 | `summarize_run` computes from SQL rows directly |
| F-08 | Expanded `code_signature` module list |

---

## 6. Strategy releases & ML research pipeline

### 🔴 R-23: Deployed o03 model is in-sample; research sim ≠ production policy

**Files**: `research/train_and_simulate.py:243-246`, `o03.py:50-69`, `research/ablations.py`

- Final `lgbm_orb_v2.pkl` is fit on **full** dataset including OOS months.
- Walk-forward **scoring** is sound (`train_and_simulate.py:187-199`), but portfolio sim uses `pb02_loose` fills and `TOP_K=5` vs production `TOP_N=10` + `pb02_strict`.
- `artifacts/oos_metrics.json` describes `simulate_v2`, not `o03.Release`.

**Impact**: Headline +183%/yr (`mlspec.md`) and artifact probabilities are not what production o03 runs. Same `release_id`, different ranking if ML deps missing (RV fallback, `o03.py:67-68`).

---

### 🟡 R-24: Research dataset collapse exit still wrong-signed

**File**: `strategies/stocks_in_play_orb/research/build_dataset.py:224-225`

```python
f_exit = stop  # should be min(o[fill_i], stop) when open gaps below stop
```

Production `execution.py` fixed; training labels still optimistic on rare adverse gaps. Regenerating parquet without fixing this skews model training.

---

### 🟡 R-25: o03 docstring vs simulator trigger semantics

**Files**: `o03.py:24` ("1-minute **close** above H") vs `core/execution.py:175` (`high > trigger`)

Doc implies close confirmation; simulator fires on intrabar high touch. Biases toward **more** trades than documented.

---

### 🟡 R-26: `*_loose` columns retained without guardrails

**Files**: `build_dataset.py:196-230`, `ablations.py:44-45`

Look-ahead-inflated `realized_r_pb02_loose` (~4× per `mlspec.md`) coexist with `*_strict` columns. Nothing prevents a future script from using the wrong column.

**Recommendation**: Rename to `*_lookahead` or drop loose columns from published parquet.

---

### 🟡 R-27: ML dependencies commented out in requirements

**File**: `requirements.txt:12-15`

`lightgbm` and `scikit-learn` are commented optional installs. Fresh env → silent RV fallback with no signature change.

---

### 🟡 R-28: Pickle artifact + committed binaries

**Files**: `o03.py:64-65`, `strategies/stocks_in_play_orb/research/artifacts/`, `research/data/`

Pickle loading risks version skew; artifacts not in `.gitignore`. `code_signature` does not hash the model file.

---

### 🟢 R-29: SPY VWAP train/serve skew

**Files**: `o03.py` (`_spy_features`), `build_dataset.py`

Training used 1m cumulative VWAP; release approximates from 5m typical price. Mild distribution shift.

---

### 🟢 R-30: `o01` has no top-N cap

**File**: `o01.py`

Every passing ticker gets a signal — unlike o02 top-20 / o03 top-10. Intentional P0 baseline, but surprises agents comparing releases.

---

## 7. Tests & agent-facing contracts

### Test suite snapshot

| Layer | Files | Depth |
|-------|-------|-------|
| `marketdata/` | 13 test modules | **Deep** — cache, TTL, calendar, locks, roundtrip |
| `core/execution` | `test_execution.py` + o03 pullback tests | **Shallow** for breakout TARGET/STOP/TIME_EXIT |
| `runner/pipeline` | `test_pipeline.py` (3 tests) | **Critical gap** — mocks `_load_context` |
| `strategies` | o02/o03 unit tests | Partial happy paths |
| `scripts/` | report/dashboard helpers only | **No CLI tests** |

**Offline run**: 149 passed, 2 warnings (urllib3/OpenSSL, websockets deprecation).

### 🔴 R-31: `test_marketdata_meta_march2026.py` hits live APIs by default

Pinned golden OHLCV from 2026-06-05; not gated with `@pytest.mark.network`. Other live tests correctly require `--run-network` via `conftest.py`. This file will flake offline and masquerade as regressions.

---

### 🟡 R-32: `cli.txt` stale vs `backtest.py`

**File**: `cli.txt`

Documents `--list-releases` and `--list-testsets`; actual flag is `--list` only (`backtest.py:50`). References nonexistent testset `smoke_q2_2024_sp500` in `backtest.py` docstring (`backtest.py:6`). Omits `--resume`, `--no-prefetch`, `--prefetch-workers`, `--max-failed-sessions`, `--force-data`.

**Impact**: Primary agent onboarding doc will cause copy-paste failures.

---

### 🟡 R-33: Pipeline integration test mocks away real hydration

**File**: `tests/test_pipeline.py`

Only E2E test replaces `_load_context` with synthetic bars. Does not verify:
- `historical_5m`, `bars_1m`, `spy_*` population per release flags
- `entry_style` → 1m simulation dispatch
- Missing-bar skip behavior

---

### 🟡 R-34: `conftest.py` `make_5m_bars` kwargs footgun

**File**: `tests/conftest.py:72-76`

Documents `**kwargs` overrides via `locals()[...]` — **does not work in Python**. Agents copying the pattern get silent wrong fixtures.

---

### 🟡 R-35: `spec.md` lags implementation

Lists P0 releases only; registry includes o02/o03. Does not document `entry_style`, `requires_rth_1m`, `requires_spy_daily`, resume semantics. Agents treating spec as sole contract will miss critical flags.

---

### 🟢 R-36: Dashboard test uses wrong `exit_reason` enum

**File**: `tests/test_dashboard.py` (~297)

Fixture uses `"EXIT_TARGET"`; execution emits `"TARGET"`. Tests pass but document wrong enum.

---

## 8. Agentic coding risks (summary)

Patterns that have already caused or will cause silent regressions when AI tools edit this codebase:

| Risk | Why it bites agents |
|------|---------------------|
| **Dual metrics paths** | `compute_trade_metrics` vs `summarize_run` inline SQL |
| **`entry_style` magic string** | `getattr(release, "entry_style", "breakout_stop")` — typos silently change simulator |
| **`code_signature` gaps** | Does not include `research/signal_helpers.py`, model artifacts, or `data/market_data.py` |
| **Three data entry points** | `fetch_bars`, `data/market_data`, pipeline `_load_context` — different defaults |
| **Magic strings** | `"Connection timeout"`, `"provider_empty"`, `"provider_error"` — no enum |
| **Comments ≠ constants** | 5%/95%/340-bar comments vs `0.13` tolerance |
| **Spec vs code** | Negative-cache filtering in `spec.md` not implemented in `_get_cached_data` |
| **Research column names** | `realized_r_pb02` vs `realized_r_pb02_strict` |
| **Doc contradictions** | `o03.py` header vs `mlspec.md` vs `execution.py` on trigger semantics |
| **Import-time `DATA_DIR`** | `storage.py` binds at import; tests reload, production scripts may not |
| **Broad `except Exception`** | `fetcher.py`, `read_bars`, provider registration hide real bugs |
| **Peer-review drift** | 2026-06-09 findings partially fixed; agents may re-apply obsolete patches |

### Safe-edit zones (relatively)

- `marketdata/tests/*` — well-isolated, high coverage
- `strategies/*/common.py` — centralized, affects signature
- `research/filters.py` — in signature; test before promoting

### High-blast-radius zones (read surrounding code + tests first)

- `marketdata/fetcher.py` (three-phase pipeline, negative cache, TTL interaction)
- `core/execution.py` (PnL semantics)
- `runner/pipeline.py` (orchestration, DB transactions)
- `strategies/stocks_in_play_orb/research/*` (does not affect runtime unless artifact regenerated)
- `o03.py` (production ML path)

---

## 9. Status of prior review findings

### Sonnet 4.6 (B-01…B-18)

| ID | Status |
|----|--------|
| B-01 `planned_r` misnamed | ✅ Renamed `realized_r`; semantics documented |
| B-02 slippage double-count | ⚠️ Open — naming trap remains |
| B-03 `assert` in hot path | ✅ Restructured |
| B-04 MAE on entry-bar stop | ✅ MAE floored at stop in `_trade` |
| B-05 dead `prior_days` in o02 | ✅ Removed |
| B-06 SMA-TR vs Wilder ATR | ✅ Fixed |
| B-07 premature negative cache | ✅ Superseded by `provider_error` distinction; see R-03 |
| B-08 tolerance mismatch | ✅ Shared constants; comments stale (R-19) |
| B-09 Phase-1→2 TOCTOU | ✅ Documented |
| B-10 `conn` shadowing | ✅ `db_conn` |
| B-11 naive `run_id` time | ✅ UTC |
| B-12 placeholder trades in summarize | ✅ Fixed — SQL path |
| B-13 `rows_written` logging | ✅ Accepted |
| B-14 unbounded `_thread_locks` | ✅ Documented |
| B-15 `between_time` inclusive | ✅ Explicit `inclusive="both"` |
| B-16 `_fresh_env` storage reload | ✅ Fixed |
| B-17 no-op TTL test | ✅ Fixed |
| B-18 partial today daily bar | ⚠️ Mitigated by `index.date < trade_date` filters |

### Fable 5 (F-01…F-28)

| ID | Status |
|----|--------|
| F-01 split daily vs raw intraday | ✅ Default raw in adapter; guard with `has_split_like_jump` |
| F-02 error-as-empty negative cache | ✅ `provider_error` TTL; see R-03 for credential edge case |
| F-03 gap-down positive PnL pullback | ✅ Fixed in `execution.py`; open in `build_dataset.py` (R-24) |
| F-04 missing 09:30 bar | ⚠️ `or_start_minute` recorded, not rejected (R-05) |
| F-05 16:00 bar | ✅ Fixed in providers |
| F-06 no account metrics | ⚠️ R-based fields added; `total_pnl_pct` still headline (R-14) |
| F-07 summarize placeholder | ✅ Fixed |
| F-08 code_signature narrow | ✅ Expanded; still gaps (signal_helpers, model) |
| F-09 abort whole run / no resume | ✅ Resume + session isolation |
| F-10 duplicate candidates | ✅ Dedup in pipeline |
| F-11 entry-bar MFE | ⚠️ Open for pullback (R-11) |
| F-12 quadratic sidecar I/O | ✅ Scoped read; summary scan remains (R-17) |
| F-13 15m retry | ⚠️ Open (R-18) |
| F-14 Alpaca chunk skip | ✅ Fixed |
| F-15 calendar-day TTL | ⚠️ Open (R-22) |
| F-16 contiguous fetch window | ✅ `_contiguous_date_runs` |
| F-17 dead `is_trading_day` branch | ✅ Removed |
| F-18 partial NaN OHLC | ✅ Fixed |
| F-19 calendar fallback holidays | ⚠️ Open — log WARNING when fallback engages |
| F-20 o02/o03 filter duplication | ✅ `common.build_sip_base` extracted |
| F-21 ML deps / pickle / gitignore | ⚠️ Partial — requirements commented (R-27) |
| F-22 loose fill columns | ⚠️ Open (R-26) |
| F-23 SPY VWAP skew | ⚠️ Open (R-29) |
| F-24 `stop_limit_offset_cents` | ✅ Renamed `stop_limit_offset_dollars` |
| F-25 DuckDB contention | ⚠️ Partial — dashboard read-only |
| F-26 network tests unmarked | ⚠️ `meta_march2026` still live by default (R-31) |
| F-27 dashboard combined equity | ⚠️ Open (R-16) |
| F-28 `completed_days` non-transactional | ✅ Derived from `sessions` count |

---

## 10. Priority recommendations (no implementation)

### P0 — correctness / silent wrong results

1. **R-01 + R-02** — Fix stale-complete and expired-negative-cache interactions in the fetch pipeline.
2. **R-23 + R-24** — Align o03 artifact/training with production policy; fix dataset collapse exit; regenerate or version parquet.
3. **R-06** — Align breakout entry-bar gap-through-stop logic with pullback limit; add symmetric tests.
4. **R-03** — Don't treat credential-skip empties as confirmed `provider_empty`.

### P1 — operational / agent safety

5. **R-32 + R-35** — Sync `cli.txt` and `spec.md` with `backtest.py` and current releases.
6. **R-13** — Unify metrics into single code path.
7. **R-31** — Gate `test_marketdata_meta_march2026.py` behind `@pytest.mark.network`.
8. **R-33** — Add pipeline integration test without `_load_context` mock (seeded parquet).
9. **R-08** — Skip signal/order insert when simulation returns `None`.

### P2 — performance / hygiene

10. **R-17** — Incremental `update_meta_summary`.
11. **R-18** — Wire circuit breaker; configurable retry budget for batch prefetch.
12. **R-26** — Rename or drop lookahead columns in research artifacts.
13. **R-28** — Model hash in run metadata; `.gitignore` for artifacts; pin ML deps.

---

## 11. Summary table (new / remaining findings)

| ID | Sev | Area | One-liner |
|----|-----|------|-----------|
| R-01 | 🔴 | marketdata | Stale partition + `complete=True` → partial day never refetched |
| R-02 | 🔴 | marketdata | Expired negative cache still masks gaps in Phase 1 |
| R-03 | 🟡 | marketdata | Missing-credential empty → 24h `provider_empty` |
| R-04 | 🟡 | marketdata | `fetch_bars` defaults 1day to split, adapter uses raw |
| R-05 | 🟡 | filters | Missing 09:30 bar shifts OR; not rejected |
| R-06 | 🟡 | execution | Breakout entry-bar gap-through-stop is inconsistent with pullback |
| R-07 | 🟡 | execution | Pullback same-bar stop skipped after limit fill |
| R-08 | 🟡 | runner | Orphan signals when sim returns `None` |
| R-09 | 🟡 | execution | `realized_r` uses planned risk, not fill risk |
| R-10 | 🟡 | models | `gross_pnl_pct` / `slippage_pct` naming trap |
| R-11 | 🟢 | execution | Pullback entry-bar MFE overstated |
| R-12 | 🟢 | metrics | `profit_factor` can be `inf` |
| R-13 | 🟡 | metrics | `compute_trade_metrics` dead code; duplicated logic |
| R-14 | 🟡 | metrics | `total_pnl_pct` still headline despite R fields |
| R-15 | 🟡 | strategies | No portfolio-level risk cap across same-day picks |
| R-16 | 🟢 | dashboard | Cross-testset unsized percent sum |
| R-17 | 🟡 | marketdata | Full partition scan on every `update_meta_summary` |
| R-18 | 🟡 | marketdata | 15m blocking retry; circuit breaker unwired |
| R-19 | 🟡 | marketdata | 13% completeness; stale comments say 5% |
| R-20 | 🟡 | storage | Corrupt parquet swallowed; quarantine unused |
| R-21 | 🟡 | storage | DuckDB writer contention; no migrations |
| R-22 | 🟢 | marketdata | TTL calendar-day vs trading-day |
| R-23 | 🔴 | ml | In-sample model; research sim ≠ o03 production |
| R-24 | 🟡 | research | Dataset collapse exit wrong-signed |
| R-25 | 🟡 | o03 | Doc says close trigger; sim uses high touch |
| R-26 | 🟡 | research | `*_loose` lookahead columns unguarded |
| R-27 | 🟡 | deps | ML packages commented optional in requirements |
| R-28 | 🟡 | ml | Pickle artifact; binaries in tree; no model hash |
| R-29 | 🟢 | ml | SPY VWAP train/serve approximation |
| R-30 | 🟢 | o01 | No top-N cap on candidates |
| R-31 | 🔴 | tests | Live golden test runs offline by default |
| R-32 | 🟡 | docs | `cli.txt` stale vs `backtest.py` |
| R-33 | 🟡 | tests | Pipeline E2E mocks `_load_context` |
| R-34 | 🟡 | tests | `make_5m_bars` kwargs pattern broken |
| R-35 | 🟡 | docs | `spec.md` lags o02/o03 flags |
| R-36 | 🟢 | tests | Dashboard fixture wrong exit_reason enum |

---

## 12. Verdict by subsystem

| Subsystem | Grade | Notes |
|-----------|-------|-------|
| `marketdata/` | B | Strong tests; cache/TTL interaction bugs remain |
| `core/execution` | B+ | Conservative design; breakout gap edge case open |
| `runner/pipeline` | B | Resume/isolation improved; integration tests thin |
| SIP strategies (`common`, o02) | B | Shared filters; OR stamp edge cases |
| o03 ML integration | C+ | Production path OK with fallback; research claims overstated |
| Research pipeline | C | Good walk-forward scoring; loose fills + in-sample export |
| Metrics/reporting | B− | R fields exist; unsized `%` still prominent |
| Tests | B− (marketdata A−) | Deep infra tests; shallow engine contract tests |
| Agent docs (`cli.txt`, `spec.md`) | C | Stale; high risk for autonomous edits |

**Bottom line**: The simulation core is thoughtfully conservative and several critical 2026-06-09 findings are fixed. The highest remaining risks are **cache-layer silent staleness**, **o03 research/production divergence**, and **contract/test gaps that will mislead agentic refactors**. Address R-01/R-02/R-23 before using this lab for promotion decisions on ML-ranked strategies or long broad-universe backtests.