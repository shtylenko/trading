# Strategy Lab — Peer Review Report

**Scope**: `trading/lab` (core, runner, strategies, data, storage, marketdata, research scripts, scripts, tests)
**Reviewer**: Claude (Fable 5)
**Date**: 2026-06-09
**Status**: Findings only — no fixes applied
**Prior review**: `peer-review/2026-06-09-sonnet46/feedback.md` (B-01…B-18); status of those findings is in §A.

Severity key: 🔴 silently wrong results / data loss · 🟡 incorrect analytics or operational hazard · 🟢 quality / hygiene / efficiency

Several findings below were *observed live* during today's o03 work; those are flagged **[observed]**.

---

## 1. Data correctness

### 🔴 F-01: Split-adjusted daily context vs. raw intraday prices — backtests are run-date dependent **[observed]**

**Files**: `data/market_data.py` (`fetch_daily_context`, hardcoded `adjustment="split"`), all strategy releases, `research/filters.py`

Daily context is fetched split-adjusted while all intraday bars are raw. Providers adjust historical prices to the **scale of the present day (the day the fetch runs)**, not the as-of backtest date. Consequence: for any ticker that split between the backtest's `trade_date` and *today*, every daily-derived quantity is in the wrong price scale relative to the intraday bars the simulator trades on.

Observed concretely: NVDA May 2024 sessions backtested in June 2026 — split-adjusted daily showed ≈ $103 while intraday raw traded ≈ $1,035. `o02`/`o03` (pre-fix) placed ATR stops 10× too tight (`stop = trigger − 0.10 × $3.2` instead of `− 0.10 × $32`), producing `realized_r = −1.43` on what should be ≈ −0.9R trades.

Affected surfaces:
- `o01`/`o02`: `min_price`, `min_avg_daily_volume` (split-adjusted *volume* is also rescaled), `daily_atr_14` → stop distance and position sizing.
- `d01`: `gap_pct = (raw open − adjusted prior high) / adjusted prior high` → wildly false gaps around splits (a 10:1 split manufactures a ~+900% "gap").
- `o03` (post-fix): ATR/prior-close now derived from raw `historical_5m`, but `min_avg_daily_volume`, `log_dollar_vol`, and `vol_concentration` still mix adjusted volume with raw prices.

A subtle second-order effect: **re-running the same backtest after a future split changes the results**, because the provider re-adjusts history. Run reproducibility is broken for any universe with splits.

**Recommendation**: pick one consistent convention. Options, best first:
1. Derive all trailing daily aggregates from the raw intraday cache (the approach `o03` now uses for ATR), with a split-window guard.
2. Fetch raw daily bars for level/scale computations and split-adjusted only for long-horizon return features.
3. Store point-in-time split factors and rescale explicitly.
Also add a regression test with a synthetic 10:1 split inside the lookback window.

---

### 🔴 F-02: Negative cache poisons availability after provider *errors* (not just genuine empties) **[observed]**

**File**: `marketdata/fetcher.py` (post-loop `write_negative_cache(..., "provider_empty")`)

The prior review's B-07 (premature write before exhausting the chain) was fixed, but the deeper issue remains: the code cannot distinguish *"providers confirmed there is no data"* from *"providers errored / were unreachable"*. Any date left in `remaining_dates` is negative-cached as `provider_empty` for 24 hours — including when:
- the network is fully down and every provider raised (exceptions are caught and `continue`d, then the dates are negative-cached);
- Alpaca returns an auth/subscription error (caught inside `AlpacaProvider.fetch_bars`, surfaces as an *empty* DataFrame);
- a single provider chain exists for the request (e.g., `extended` 1min) and it failed transiently.

Observed today: during a network outage, an o03 run requested extended-session 1-minute data; the failures were negative-cached, so a retry run within 24h would silently get no 1-minute data and quietly degrade fill simulation to 5-minute bars — **with no error and materially different backtest results**.

**Recommendation**: only write `provider_empty` when at least one provider *successfully responded* with no data for that date. Introduce a distinct `provider_error` reason with a short TTL (minutes) or none at all. Consider logging a WARNING when a backtest proceeds with degraded data resolution.

---

### 🟡 F-03: Gap-down-through-stop produces a *positive PnL* artifact in the pullback simulator

**Files**: `core/execution.py::simulate_pullback_limit_long` (collapse branch), `strategies/stocks_in_play_orb/research/build_dataset.py::simulate_outcomes` (same pattern)

In the collapse-through-stop branch, entry is `min(limit, bar_open)` and exit is the stop price. If the bar **opens below the stop** (gap down through both the limit and the stop while the order is working), `entry = bar_open < stop` and `exit = stop > entry` — the simulator books a *profit* on a catastrophic adverse gap. Reality: the limit fills at the open and the stop order exits at/below the open; PnL should be ≈ 0 or negative.

Rare (requires an intraminute/intrabar gap through two levels within the 30-minute TTL window) but wrong-signed, and it flatters exactly the worst trades. The research dataset shares the bug, so the +183%/yr OOS figure includes it; given the rarity, the effect is likely small, but it is biased in the optimistic direction.

**Recommendation**: in both implementations, exit at `min(bar_open, stop)` (and arguably skip the fill entirely when `bar_open < stop`, since a marketable gap-down would fill at the open and stop out at essentially the same price). Add unit tests for: open < stop, open between stop and limit, open above limit.

---

### 🟡 F-04: `first_regular_5m_bar` can silently return the 09:35 bar as "the first candle"

**File**: `research/filters.py`

When the 09:30 bar is absent (provider hole), the fallback `between_time("09:30", "09:35")` returns the 09:35 bar, which is then treated as the opening-range candle: its high becomes the breakout trigger and RV compares its volume against *09:30* opening bars from history (`o02`/`o03` use `between_time("09:30","09:35").groupby(...).first()` for the historical mean, mixing 09:30 and 09:35 bars). The setup quietly shifts 5 minutes with no flag in the candidate features.

**Recommendation**: either skip the day when the 09:30 bar is missing, or record `or_start_minute` in features so shifted setups are filterable. Make the historical opening-bar selection consistent with whichever rule is chosen.

---

### 🟡 F-05: 16:00-labeled bar inconsistency between providers and the calendar

**Files**: `marketdata/providers/alpaca_provider.py`, `marketdata/providers/marketdata_provider.py` vs. `marketdata/calendar.py`

Provider RTH session filters use `between_time("09:30", "16:00")` (inclusive of both endpoints), so a 16:00-labeled bar (the closing auction print on some feeds) is cached. `expected_bars` uses `inclusive="left"` (09:30…15:59). Consequences: cached data can contain a bar the calendar never expects (harmless for coverage math but a trap for consumers that slice with `<= 16:00`), and the two layers disagree about what a "complete day" contains.

**Recommendation**: standardize on left-closed [09:30, 16:00) everywhere; filter with `between_time("09:30", "15:59")` or explicit `< 16:00` in providers.

---

## 2. Backtest semantics & reporting

### 🔴 F-06: No account-level metrics — `total_pnl_pct` is a sum of per-trade price moves, presented as the headline **[observed]**

**Files**: `core/metrics.py`, `runner/pipeline.py::summarize_run`, `scripts/dashboard.py`, `scripts/report.py`

`total_pnl_pct` sums each trade's percentage *price* move with no position sizing, no risk normalization, and no compounding. The dashboard labels the cumulative sum an "Equity Curve". This is actively misleading for promotion decisions:

Observed today: the o03 Q2-2024 eval showed `total_pnl_pct = +0.52%`, which reads as "flat", while the size-aware view (Σ realized_r = +4.48R at 1% risk/trade ≈ +4.5% on account per quarter) tells the opposite story. The strategies in this lab size positions by R (`shares = risk_budget / risk_per_share`), so summing unsized price-percent moves systematically misweights expensive-vs-cheap and tight-vs-wide-stop trades.

**Recommendation**: add R-based aggregates to `release_metrics` (Σ realized_r, avg R, win rate by R) and a proper sized equity simulation (risk budget × realized_r, leverage cap, daily compounding) either in `summarize_run` or a dedicated analytics module. Rename the dashboard series until then.

### 🟡 F-07: `release_metrics` keeps only one scope row per run and `summarize_run` rebuilds trades with placeholder fields

**File**: `runner/pipeline.py::summarize_run`

Carried over from prior review (B-12), still open: reconstructed `SimulatedTrade`s use `entry_price=1.0`, `gross_pnl_pct = pnl_pct + slippage`, fees folded oddly. Any new metric added to `compute_trade_metrics` that touches prices, fees, or gross/net distinctions will silently compute nonsense for stored runs. Prefer computing metrics directly from the SQL rows.

### 🟡 F-08: `code_signature` covers only the release module — core engine changes are invisible to reproducibility tracking

**File**: `runner/pipeline.py::compute_code_signature`, `__init__.py::ENGINE_VERSION`

The signature hashes the release file + the constant `ENGINE_VERSION` (`"strategy_lab_p0"`, never bumped). Today's changes to `core/execution.py` (new fill simulator) and `runner/pipeline.py` (bar-resolution dispatch) materially changed simulation semantics for *existing* releases without changing any signature. Two runs with identical signatures are not comparable.

**Recommendation**: hash the closure of files that affect simulation (`core/*.py`, `runner/pipeline.py`, `research/filters.py`, the release file), or bump `ENGINE_VERSION` on any engine-semantics change as a disciplined convention (the former is robust, the latter is honor-system).

### 🟡 F-09: One failed session aborts the whole multi-day run; no resume capability **[observed]**

**File**: `runner/pipeline.py::run_backtest_for_testset`

A single exception (e.g., one ticker's `ProviderError` after the 15-minute retry budget, see F-13) marks the run failed and stops the loop; completed days are kept but there is no `--resume <run_id>`. For a 128-day broad-universe run that costs hours of fetching, this is expensive. Killing the process externally leaves the run row in `status='running'` forever (observed today; required manual SQL to tidy).

**Recommendation**: per-session error isolation with a `failed_sessions` counter and configurable threshold; a resume mode that skips already-completed `(run_id, trade_date)` sessions; mark `running` runs stale on startup.

### 🟢 F-10: Duplicate candidate tickers would violate the `candidates` PK and kill the session

**Files**: `runner/pipeline.py::_insert_candidate`, `storage/duckdb.py` (PK `(session_id, ticker)`)

Releases return a list; nothing deduplicates by ticker before insert. A future release bug (e.g., the same ticker passing two filter paths) becomes a hard session failure rather than a logged warning. Cheap guard: dedupe in the pipeline and log.

### 🟢 F-11: MFE on the entry bar includes pre-fill price action

**File**: `core/execution.py::simulate_long_breakout`

`mfe`/`mae` on the bar where entry occurs use the full bar high/low, part of which printed before the fill. MAE is later floored at the stop level (B-04 fix), but MFE remains overstated on entry bars with large post-trigger wicks. Affects `mfe_pct` analytics only, not PnL.

---

## 3. Market data layer

### 🔴 F-12: Coverage/summary sidecar updates re-read the entire dataset on every write — quadratic backtest data phase **[observed]**

**File**: `marketdata/fetcher.py::_update_sidecar_coverage`, `marketdata/storage.py::update_meta_summary`

After *every* `fetch_bars` that stored anything:
1. `_update_sidecar_coverage` calls `read_bars(...)` with **no start/end** — loads the ticker's *entire cached history* (for 1min data, potentially years) just to count bars per day;
2. `update_meta_summary` then re-reads the `timestamp` column of **every partition file** to recompute earliest/latest/total_rows.

In a day-by-day backtest, each new day triggers a full-history read per ticker: O(days²) I/O growth over a long run. This is a major contributor to the slow per-day pacing observed in today's 330-ticker run (beyond network fetches).

**Recommendation**: restrict the coverage read to `[min(trading_dates), max(trading_dates)]`; update summary incrementally (compare the new data's min/max against stored values; increment `total_rows` by genuinely-new rows). Both are local changes with large payoff.

### 🟡 F-13: 15-minute blocking retry per provider call interacts badly with batch backtests

**Files**: `marketdata/retry.py`, `marketdata/providers/*.py`, `runner/pipeline.py`

During an outage, each affected call blocks up to 15 minutes (observed: 4+ minutes of retries per ticker for extended 1min fetches), and the eventual `ProviderError("Connection timeout")` propagates through the session into a full run abort (F-09). For a 330-ticker day, worst case is hours of sequential retry stalls before dying anyway.

**Recommendation**: make the retry budget configurable per call-site (backtests want fail-fast + skip; interactive fetches may want patience); share an "outage detected" circuit breaker across calls so 330 tickers don't each independently rediscover the outage.

### 🟡 F-14: Alpaca chunking skips one calendar day at every 365-day chunk boundary (latent)

**File**: `marketdata/providers/alpaca_provider.py::fetch_bars`

`cursor = chunk_end + timedelta(days=1)` — the window `(chunk_end, chunk_end + 1 day)` is never requested, so for ranges > 365 days, bars on each boundary day are silently dropped (then likely negative-cached as `provider_empty` by the fetcher). Currently dormant because `fetch_daily_context` uses a 40-day lookback, but `Timeframe("1day").lookback_days_default = 1000` means any `fetch_bars("X", "1day")` call without an explicit `start` crosses two boundaries.

**Recommendation**: `cursor = chunk_end` (ranges half-open) or `chunk_end + smallest_bar_increment`; add a multi-chunk unit test.

### 🟡 F-15: Mutable-window TTL counts calendar days; docstring claims trading days

**File**: `marketdata/ttl.py::is_within_last_3_days`, `is_today_or_yesterday`

`(ny_today - data_date).days <= 1` makes Friday's data "immutable" on Monday (3 calendar days), even though only one trading day has elapsed. For intraday data fetched *mid-session* Friday, the partial day is then never refreshed by TTL — only the coverage-gap path can rescue it, and only if the gap exceeds the 5%/13% tolerance. A Friday fetched at 15:30 (≈ 2% of bars missing) stays incomplete forever and silently truncates EOD exits simulated on it.

**Recommendation**: compute the distance in trading days (the calendar module is right there), and/or treat "last session not fully covered through close" as mutable regardless of age.

### 🟢 F-16: Phase-2 fetch window spans first-to-last missing date, refetching the cached middle

**File**: `marketdata/fetcher.py`

`miss_start/miss_end` form one contiguous window. Missing Jan 2 + Dec 30 → the provider is asked for the whole year. Wasteful of rate limits and bandwidth (Alpaca SIP requests are paid). Group missing dates into runs and fetch per run.

### 🟢 F-17: Dead `is_trading_day` branch in `_find_missing_dates`

**File**: `marketdata/fetcher.py`

`trading_dates` is produced by `trading_days_in_range`, so the `if not is_trading_day(d)` branch (which writes `non_trading_day` negative-cache entries) is unreachable — same calendar on both sides. Dead code that implies a safety net that doesn't exist.

### 🟢 F-18: `_normalize_for_storage` keeps partially-NaN OHLC rows

**File**: `marketdata/storage.py`

Rows are dropped only when *all* of open/high/low/close/volume are NaN (`how="all"`). A row with a NaN close but valid high/low survives into the cache and propagates NaN into ATR/feature math downstream. Tighten to `how="any"` on OHLC (volume 0-fill is already handled).

### 🟢 F-19: `_trading_days` fallback silently includes holidays

**File**: `runner/pipeline.py`

If the calendar import fails, the fallback enumerates weekdays. Holiday "sessions" then run against empty data (wasted fetch attempts, `provider_empty` negative-cache writes for legitimate non-trading days with the wrong reason/TTL). At minimum log a WARNING when the fallback engages.

---

## 4. Strategy releases & research pipeline

### 🟡 F-20: `o03` duplicates the entire o02 SIP filter block — divergence risk

**Files**: `strategies/stocks_in_play_orb/o02.py`, `o03.py`

The price/volume/ATR/green-candle/RV gauntlet is copy-pasted with subtle differences (o03's raw-ATR fix, F-01). The next filter tweak will be applied to one and not the other, and comparisons between releases will quietly measure code drift instead of design intent. Extract the shared candidate-filter into `research/filters.py` (parameterized), keeping releases as thin configuration.

### 🟡 F-21: ML model artifact: unpinned dependencies, pickle loading, artifacts not git-ignored

**Files**: `strategies/stocks_in_play_orb/o03.py`, `research/artifacts/`, `research/data/`

- `lightgbm`/`scikit-learn` are runtime dependencies of o03's primary ranking path but appear in no requirements manifest; they were installed ad hoc into the user-site of a CommandLineTools Python 3.9. A fresh environment silently degrades o03 to RV ranking (logged once, easy to miss) → **same release id, different candidate ranking, no signature change** (compounds F-08).
- The artifact is a pickle — version-skew across sklearn/lightgbm upgrades will either crash (caught, degrades silently) or, worse, deserialize with changed semantics.
- `research/data/orb_ml_dataset.parquet` (multi-MB) and `research/artifacts/*.parquet|pkl` are not git-ignored; they'll bloat the repo on the next `git add -A`.

**Recommendation**: requirements pinning; record `ml_model_version` + model file hash in run metadata (it's in signal metadata already — promote to `runs`); prefer lightgbm's native `Booster.save_model` text format over pickle; add `.gitignore` entries.

### 🟡 F-22: Research dataset retains the optimistic "loose fill" columns alongside strict ones

**File**: `strategies/stocks_in_play_orb/research/build_dataset.py`, `ablations.py`

`realized_r_pb02`/`pb05` (fills allowed in the breach minute — demonstrated look-ahead, ~4× return inflation) coexist with `*_strict` columns. Nothing in the schema marks the loose columns as invalid for headline use; a future analysis that grabs the unsuffixed column reproduces the look-ahead silently. Rename to `*_loose`/`*_lookahead` or drop them.

### 🟢 F-23: `o03` SPY VWAP feature is a coarser proxy than the training-time feature

**File**: `strategies/stocks_in_play_orb/o03.py::_spy_features`

Training computed `spy_vwap_dist` from 1-minute cumulative VWAP over the first five minutes; the release approximates it with the first 5-minute bar's typical price. Same name, shifted distribution — mild train/serve skew. Either compute from `bars_1m` (now available in context) or document the approximation.

### 🟢 F-24: `ExecutionConfig.stop_limit_offset_cents` is added as **dollars**

**File**: `core/models.py`, `core/execution.py` (`limit = trigger + config.stop_limit_offset_cents`)

The field name says cents; the math treats it as dollars. Anyone passing `5` for "5 cents" gets a $5 offset. Dormant (defaults to `None`, no current caller) but a unit bug waiting for its first user. Rename to `_dollars` or divide by 100.

---

## 5. Operations, storage & tests

### 🟡 F-25: DuckDB single-writer contention between backtests, dashboard, and ad-hoc readers **[observed]**

**Files**: `storage/duckdb.py`, `scripts/dashboard.py`, `runner/pipeline.py`

Everything opens read-write connections against one DuckDB file. DuckDB allows a single writer process; concurrent dashboard reads / monitor polls during a long backtest intermittently fail to connect (observed during today's run monitoring; required `|| echo db-locked` handling). The per-insert pattern in the pipeline (a fresh `connect()` per helper when no conn passed) magnifies the window.

**Recommendation**: dashboard and report scripts should connect with `read_only=True` (DuckDB supports concurrent readers with one writer in that mode); pipeline should hold one connection per session (it mostly does via the transaction block — keep it that way for new code).

### 🟡 F-26: Live-network tests are not marked; suite is red offline **[observed]**

**Files**: `tests/test_marketdata_alpaca_vs_marketdata.py`, `tests/test_marketdata_integration_live.py`

4 provider-comparison tests fail hard without internet/API access (observed today). They are indistinguishable from real regressions in CI output. Mark with `@pytest.mark.network` (and skip by default) or auto-skip on connectivity failure.

### 🟢 F-27: Dashboard "combined equity" sums unsized per-trade percent across different testsets/releases

**File**: `scripts/dashboard.py`

Compounds F-06: cross-testset aggregation of unsized percent moves has no financial interpretation. Fine as a sparkline; should not inform decisions. Label accordingly or compute from R-based metrics once F-06 lands.

### 🟢 F-28: `runs.completed_days` updated outside the session transaction

**File**: `runner/pipeline.py::run_backtest_for_testset`

Crash between session commit and the `completed_days` update undercounts progress (cosmetic; relevant once a resume feature exists — resume should derive progress from `sessions`, not `completed_days`).

---

## A. Status of prior review (2026-06-09-sonnet46)

| ID | Finding | Status |
|----|---------|--------|
| B-01 | `planned_r` misnamed | ✅ Fixed (now `realized_r`) |
| B-02 | slippage double-count risk in `gross_pnl_pct` | ⚠️ Open (semantics unchanged; no warning comment) |
| B-03 | `assert` in hot path | ✅ Fixed (restructured) |
| B-04 | MAE overstated on entry-bar stop | ✅ Fixed (MAE floored at stop in `_trade`) |
| B-05 | dead `prior_days` in o02 | ✅ Fixed (removed) |
| B-06 | SMA-TR vs Wilder ATR | ✅ Fixed (`daily_atr_14` now Wilder) — but see F-01 for the bigger ATR problem |
| B-07 | premature negative-cache write | ✅ Fixed (write moved post-chain) — successor issue F-02 |
| B-08 | tolerance constant mismatch | ✅ Fixed (shared constants in config) |
| B-09 | Phase-1→2 TOCTOU | ✅ Accepted & documented in comment |
| B-10 | `conn` shadowing | ✅ Fixed (`db_conn`) |
| B-11 | naive `datetime.now()` in run_id | ✅ Fixed (UTC) |
| B-12 | `summarize_run` placeholder trades | ⚠️ Open — see F-07 |
| B-13 | `rows_written` overstated | ✅ Accepted & documented |
| B-14 | unbounded `_thread_locks` | ✅ Accepted & documented |
| B-15 | `between_time` inclusive unspecified | ✅ Fixed (`inclusive="both"`) |
| B-16 | `_fresh_env` not reloading storage | ✅ Fixed (storage reloaded) |
| B-17 | no-op TTL test | ✅ Fixed (no `pass`-body test remains) |
| B-18 | partial today-bar cached in daily | ⚠️ Open (mitigated by strategy-side `index.date < trade_date` filters) |

---

## B. Summary table (new findings)

| ID | Sev | Area | One-liner |
|----|-----|------|-----------|
| F-01 | 🔴 | data | Split-adjusted daily vs raw intraday: stops/gaps/filters wrong-scale around splits; results depend on run date |
| F-02 | 🔴 | marketdata | Provider *errors* negative-cached as `provider_empty` → 24h silent data blackouts, silent resolution degradation |
| F-03 | 🟡 | execution | Gap-down-through-stop books positive PnL in pullback simulator (release + research) |
| F-04 | 🟡 | filters | Missing 09:30 bar silently shifts the opening range to 09:35 |
| F-05 | 🟡 | marketdata | 16:00 bar cached by providers but never expected by calendar |
| F-06 | 🔴 | metrics | No account-level metrics; unsized `total_pnl_pct` presented as headline/equity |
| F-07 | 🟡 | metrics | `summarize_run` placeholder-trade reconstruction (B-12 carryover) |
| F-08 | 🟡 | reproducibility | `code_signature` blind to core-engine changes; `ENGINE_VERSION` never bumped |
| F-09 | 🟡 | runner | One session failure aborts run; no resume; killed runs stay `running` |
| F-10 | 🟢 | runner | Duplicate candidate ticker → PK violation kills session |
| F-11 | 🟢 | execution | Entry-bar MFE includes pre-fill range |
| F-12 | 🔴 | marketdata | Full-history re-read per cache write → quadratic backtest I/O |
| F-13 | 🟡 | marketdata | 15-min blocking retry per call; outage stalls then aborts batch runs |
| F-14 | 🟡 | marketdata | Alpaca 365-day chunking skips boundary days (latent) |
| F-15 | 🟡 | marketdata | TTL counts calendar days, not trading days; Friday partial days can freeze incomplete |
| F-16 | 🟢 | marketdata | Contiguous fetch window refetches cached middle |
| F-17 | 🟢 | marketdata | Dead `is_trading_day` branch in `_find_missing_dates` |
| F-18 | 🟢 | storage | Partially-NaN OHLC rows survive into cache |
| F-19 | 🟢 | runner | Calendar-fallback includes holidays silently |
| F-20 | 🟡 | strategies | o02/o03 filter duplication → divergence risk |
| F-21 | 🟡 | ml | Unpinned ML deps, silent RV fallback, pickle artifact, artifacts not git-ignored |
| F-22 | 🟡 | research | Look-ahead "loose fill" columns retained without warning labels |
| F-23 | 🟢 | ml | SPY VWAP feature train/serve skew |
| F-24 | 🟢 | execution | `stop_limit_offset_cents` is actually dollars |
| F-25 | 🟡 | storage | DuckDB writer/reader contention; dashboard should use read-only connections |
| F-26 | 🟡 | tests | Network tests unmarked; suite red offline |
| F-27 | 🟢 | dashboard | Cross-testset sum of unsized percent has no financial meaning |
| F-28 | 🟢 | runner | `completed_days` non-transactional (matters once resume exists) |

---

## C. Top priorities

1. **F-01** — the split-scale mismatch silently corrupts every level-based computation for split tickers and makes runs non-reproducible over time. It already distorted recorded o02/o03 results (NVDA Q2-2024).
2. **F-02** — error-as-empty negative caching causes silent 24h data blackouts and, worse, *silent simulation-resolution degradation* in o03. Today's outage planted exactly these entries.
3. **F-12** — the per-write full-history sidecar re-read is the dominant self-inflicted cost in long backtests; fixing it makes the broad-universe workflow practical.
4. **F-06** — until account-level metrics exist, promotion decisions are being made on a number (`total_pnl_pct`) that does not represent returns.
5. **F-03** — wrong-signed PnL on adverse gaps in the new pullback path; small but optimistic bias in the headline research result; cheap to fix and test.
