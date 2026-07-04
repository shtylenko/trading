# Comprehensive Codebase Analysis — `strategy_lab`

**Reviewer**: DeepSeek v4 Pro (multi-agent parallel review)  
**Date**: 2026-06-13  
**Scope**: All 53 Python files in `trading/lab/` — core, runner, strategies (o/d/f), marketdata, data, storage, research, validation, scripts  
**Prior reviews referenced**: `2026-06-09-sonnet46/feedback.md`, `2026-06-09-fable5/feedback.md`, `2026-06-10-code-review/composer.md`, `2026-06-13-codebase/gemini.md`  
**Test run**: 220 passed, 1 failed (ZoneInfo API compat in test assertion; 1 env-dependent data-provider test)  
**Methodology**: Core files read directly; strategy families and marketdata layer analyzed by parallel subagents; all findings cross-referenced against prior reviews to avoid stale duplication.

---

## Executive Summary

`strategy_lab` is a mature, well-layered research harness with strong isolation between `core` → `runner` → `strategies` and deliberate conservative simulation semantics. The marketdata subsystem has deep coverage of caching, staleness, and provider fallback logic. Since the 2026-06-10 review, most reported bugs have been fixed (raw daily default, expanded code signatures, per-session error isolation, negative-cache distinctions).

The remaining risk surface clusters into four areas:

1. **Marketdata correctness under degradation** — calendar-day fallbacks in staleness logic, unbounded memory in meta caches, and provider-error misclassification can silently corrupt data or exhaust resources.
2. **Strategy-level fragility** — ML feature crashes on model-artifact mismatch, architecture violations (direct provider calls in f02), timezone assumptions that only hold by convention, and brittle cross-module contracts.
3. **Simulation edge cases** — `_time_stop_triggered` parsing fragility, VWAP computation contract risk (multi-day data), and stop-loss abs() masking invalid stop placement.
4. **Operational risks** — DuckDB write-lock contention during long simulation loops, hardcoded connectivity host, and lock-file accumulation.

The engine is **production-usable for baseline backtest comparison** (o/d/f families). ML-based releases (o03) and broad-universe runs with 1-minute data carry the most remaining risk.

---

## 🔴 HIGH Severity

### H1 — o03 ML feature crash on model-artifact mismatch
**File**: `strategies/stocks_in_play_orb/o03.py:204–208`  
**Category**: stability  
**Cross-ref**: New finding (not in prior reviews)

`build_candidates` iterates `float(c.features[name])` for every `name` in the model artifact's feature list. If any candidate's `features` dict is missing a key (version skew, partial build) or has a `None` value, this raises `KeyError` or `TypeError` and crashes the entire backtest run. A `try/except` with fallback to RV ranking, or filling missing features with a sentinel (0.0), would make the release robust to model-artifact mismatches. Additionally, the feature `"window": 5.0` (line 179) is hardcoded as a constant — if the model was trained with a varying `window` feature, all predictions are silently degraded.

**Recommendation**: Wrap feature extraction in try/except with warning + fallback; verify the model's feature list doesn't include `"window"` as a signal-bearing column.

---

### H2 — f02 architecture violation: direct `fetch_daily_context` call
**File**: `strategies/dominance_flip_reversal/variants.py:37–53`  
**Category**: logic (architecture violation)  
**Cross-ref**: New finding

`spy_above_200sma()` — called from `regime_ok` when `require_spy_uptrend=True` — directly imports and invokes `fetch_daily_context` from `trading.lab.data.market_data`. This violates the core contract documented in `strategies/CLAUDE.md`: "Release logic must not call providers directly — declare data requirements via the class attributes and the runner hydrates StrategyContext." Consequences: (a) f02 fetches SPY daily through a separate code path, risking data inconsistencies with the runner's loading; (b) the runner's caching layer is bypassed, causing repeated network fetches; (c) f02 becomes untestable without a live provider; (d) the function silently returns `False` on missing data, collapsing to zero trades with no diagnostic.

**Recommendation**: Set `requires_spy_daily = True` on the release class and read `context.spy_daily` in `regime_ok`. This is exactly the pattern the contract was designed for.

---

### H3 — `is_connection_error` treats all `URLError` as transient
**File**: `marketdata/retry.py:24–25`  
**Category**: logic / stability  
**Cross-ref**: New finding

`is_connection_error()` returns `True` for ALL `urllib.error.URLError` instances, regardless of underlying reason. `URLError` wraps HTTP 403 (forbidden/auth), 429 (rate-limit), and 500 (server error) — none of which are transient connection failures. When the retry wrapper sees `True`, it triggers exponential-backoff retries for up to 15 minutes. A 403 (bad credentials) or 429 (rate limit) will never succeed on retry, wasting the retry budget and delaying the entire backtest. The explicit exclusion of `HTTPError` (line 20–21) doesn't fully mitigate this because `URLError` and `HTTPError` are siblings under `URLError`, and some HTTP responses are raised as `URLError` by the urllib stack.

**Recommendation**: Inspect the reason/reason-args inside `URLError` for HTTP status codes. Treat 4xx as non-retryable errors; only retry on socket-level and timeout errors.

---

### H4 — TTL fallback uses calendar days, corrupting weekend staleness
**File**: `marketdata/ttl.py:33–50`  
**Category**: accuracy  
**Cross-ref**: New finding (distinct from composer R-01/R-02 which concern `complete` flag and negative-cache expiry, not the trading-day fallback)

When `exchange_calendars` is unavailable, `_trading_days_since()` computes `(ny_today - data_date).days` — calendar days, not trading days. On a Monday morning, data from Friday is 3 calendar days old, so `is_today_or_yesterday()` (which checks `<= 1`) returns `False`. Friday's intraday data is misclassified as "historical/immutable" and not subjected to the mutable-window staleness check. The docstring on lines 37–39 explicitly warns: "Using trading days (not calendar days) keeps Friday's data in the mutable window through Monday." The fallback path silently violates this invariant.

**Recommendation**: Implement a weekday-only fallback (skip Saturday/Sunday in the calendar-day count) as a minimum guard. Better: cache the exchange-calendar import failure and surface it as a warning at startup so the user knows they're running with degraded staleness semantics.

---

### H5 — Naive datetime silently mismatches in pyarrow predicate filters
**File**: `marketdata/storage.py:226–231`  
**Category**: accuracy / logic  
**Cross-ref**: New finding

In `read_bars`, when `start` or `end` are naive datetime objects, they are passed directly into pyarrow filter tuples without UTC localization. The stored `timestamp` column is always UTC with timezone. pyarrow predicate pushdown between tz-aware and naive values produces undefined behavior — depending on pyarrow version, this may silently match zero rows or raise an obscure error. All internal callers currently pass tz-aware datetimes, so the bug is latent. But the function is a public API export (`__init__.py`), and external callers may pass naive datetimes expecting UTC or ET semantics.

**Recommendation**: Localize naive inputs to UTC (with a warning) before constructing pyarrow filters, or raise a clear error explaining the requirement.

---

### H6 — `cache_inspect` uses hardcoded `DATA_DIR`, ignores env var override
**File**: `marketdata/cache_inspect.py:36`  
**Category**: logic  
**Cross-ref**: New finding

The diagnostic script defines its own `DATA_DIR = Path(__file__).resolve().parent / "data"` instead of importing from `.config`, which reads `STRATEGY_LAB_MARKETDATA_DIR` and `STOCKMARKETDATA_DIR` environment variables. When a user has configured a different cache directory, `cache_inspect` silently inspects the default directory, producing misleading reports about what data exists.

**Recommendation**: Import `DATA_DIR` from `marketdata.config` so the diagnostic tool follows the same resolution path as the rest of the subsystem.

---

## 🟡 MEDIUM Severity

### M1 — o06 implicit `spy_5m` dependency with no guard
**File**: `strategies/stocks_in_play_orb/o06.py:35–36`  
**Category**: logic  
**Cross-ref**: New finding

`regime_ok` calls `green_first_candle(context.spy_5m)`, but the `StrategyRelease` base has no `requires_spy_5m` flag. The runner *currently* always fetches SPY 5m bars unconditionally (`pipeline.py:945`), so this works. If the runner's contract ever changes to conditional fetching, o06 silently receives `None`, `green_first_candle` returns `False`, and every trading day produces zero candidates with no error.

**Recommendation**: Add `requires_spy_5m = True` as a class attribute on o06 (or on the `StrategyRelease` base with a False default) and have the runner check it, mirroring the `requires_spy_daily` pattern.

---

### M2 — Historical 5m bars timezone-naive assumption
**File**: `strategies/stocks_in_play_orb/common.py:92`  
**Category**: accuracy  
**Cross-ref**: New finding

```python
hist_ny = hist_5m.tz_convert("America/New_York") if hist_5m.index.tz is not None else hist_5m
```

When historical 5m bars have a timezone-naive index, the code assumes they are already in America/New_York. If a data provider returns timezone-naive timestamps in UTC, `between_time("09:30", "09:35")` selects the wrong bars — potentially from overnight hours. This corrupts `mean_opening_volume` and all RV-based rankings across o02–o09. The same pattern appears in `post_gap_opening_drive/variants.py:44–49`.

**Recommendation**: Use `tz_localize("America/New_York")` for naive inputs or assert the timezone with a clear error message.

---

### M3 — DuckDB write lock held during entire simulation loop
**File**: `runner/pipeline.py:603–686`  
**Category**: stability  
**Cross-ref**: gemini §2.1

The runner opens a DuckDB transaction (`BEGIN TRANSACTION`), then loops over all candidates — running `release.build_signal()`, `simulate_long_breakout()`, and other CPU-intensive pandas logic — all while holding the database write lock. DuckDB supports only a single concurrent write transaction. In any parallel execution scenario (multiple workers, concurrent backtests), this causes lock contention and eventual timeout failures (capped at 10 minutes).

**Recommendation**: Generate all signals and simulate all trades in memory first. Open the DuckDB connection and transaction only when bulk-inserting the completed session results.

---

### M4 — Sidecar coverage update reads entire date range into RAM
**File**: `marketdata/fetcher.py:674–677`  
**Category**: stability  
**Cross-ref**: gemini §2.2

`_update_sidecar_coverage` calls `read_bars(ticker, timeframe, start=range_start, end=range_end, ...)` to load the entire requested date range into a DataFrame solely to count rows per day. For a 5-year prefetch of 1-minute bars, this loads ~2M rows per ticker into RAM. In a `ThreadPoolExecutor` with 8 workers, this causes rapid memory exhaustion.

**Recommendation**: Use `pyarrow.parquet.read_metadata()` to get row-group statistics, or use DuckDB to query row counts grouped by date directly against the Parquet files without loading data.

---

### M5 — `_META_CACHE` unbounded growth (~100 KB per entry)
**File**: `marketdata/storage.py:438–439`  
**Category**: stability  
**Cross-ref**: New finding

The `_META_CACHE` dictionary (parsed meta.json sidecars keyed by string path) has no eviction policy and no size cap. Each (ticker, timeframe, session, adjustment) combination adds a permanent entry. With multi-year coverage metadata, each entry can be ~100 KB. For 1,000 tickers × 4 timeframes, this grows to ~400 MB of cached JSON with no mechanism for cleanup. In long-running sessions or services, this becomes a meaningful memory leak.

**Recommendation**: Add an LRU eviction policy (e.g., `@functools.lru_cache(maxsize=512)`), or clear the cache after each run completes.

---

### M6 — R-01 / R-02: Stale partial data and expired negative-cache masking
**Files**: `marketdata/fetcher.py:340-357`, `calendar.py:240-243`  
**Category**: accuracy  
**Cross-ref**: composer R-01, R-02 — **UNRESOLVED**

These two issues from the 2026-06-10 composer review remain unresolved:

**R-01**: Phase 1 rejects cache when `is_stale()` is true, but Phase 2 `_find_missing_dates` skips dates where `coverage[date].complete == True`. A Friday session fetched mid-day (within tolerance → `complete=True`) becomes stale on Monday. Phase 1 misses, Phase 2 skips Friday, Phase 3 returns stale truncated data with no refetch.

**R-02**: `_get_cached_data` passes raw `neg_cache` into `coverage_gaps()`, which skips any date present in the dict regardless of TTL expiry. An expired `provider_empty` entry causes Phase 1 to accept incomplete cached data as a HIT.

**Recommendation**: For R-01, when Phase 1 fails due to staleness, pass `ignore_complete=True` to `_find_missing_dates`. For R-02, add an `active_negative_cache()` helper that filters expired entries and use it in both `_get_cached_data` and `_find_missing_dates`.

---

### M7 — `_time_stop_triggered` parsing fragility
**File**: `core/execution.py:26`  
**Category**: stability  
**Cross-ref**: New finding

```python
hh, mm = (int(x) for x in str(at).split(":"))
```

If a release sets `time_stop_at` to a malformed value like `"12:00:00"` (three components), the generator yields 3 values but `hh, mm = ...` expects exactly 2, raising `ValueError` and crashing the simulation mid-trade. While current releases use valid `"HH:MM"`, any future typo produces a hard crash with no clear error message.

**Recommendation**: Add input validation — check that `split(":")` yields exactly 2 components, or use `try/except` with a warning fallback.

---

### M8 — f01 tz-aware vs naive comparison risk
**File**: `strategies/dominance_flip_reversal/f01.py:128–139`, `variants.py:96–111`  
**Category**: stability  
**Cross-ref**: New finding

`build_candidates` constructs `latest_flip = ny_dt(context.trade_date, 15, 0)` (tz-aware) and compares `setup["flip_time"] > latest_flip`, where `setup["flip_time"]` comes from `bars_5m.index[t]`. If the DataFrame index hasn't been localized (data pipeline bug or provider change), this raises `TypeError: can't compare offset-naive and offset-aware datetimes`. The `post_gap_opening_drive` family avoids this because d01 never compares bar timestamps against `ny_dt()` output within strategy code.

**Recommendation**: Defensively call `ensure_ny_index()` on `bars_5m` inside f01's `build_candidates`, or add an assertion that the index is tz-aware.

---

### M9 — `_trading_days_since` fallback silently drops Friday-to-Monday window
**File**: `marketdata/ttl.py:160–168`  
**Category**: logic  
**Cross-ref**: New finding (related to H4)

The `_IMMUTABLE_AFTER_DAYS = 7` check for `provider_empty` entries uses `(ny_today - entry_date).days > 7` — calendar days, not trading days. The rest of the module goes to great lengths to use trading-day semantics for freshness, but immutability uses calendar days. Between day 2 and day 7 (calendar), the entry is re-checked every 24 hours. After 7 calendar days (which could be only 5 trading days over a weekend), it becomes permanently immutable. This inconsistency likely means the negative cache is locked in prematurely on entries that cross weekends.

**Recommendation**: Use `_trading_days_since()` (with the improved fallback from H4) instead of raw calendar-day arithmetic.

---

### M10 — 13% completeness tolerance masks significant data gaps
**File**: `marketdata/config.py:119–120`  
**Category**: accuracy  
**Cross-ref**: New finding

`COMPLETENESS_TOLERANCE_1MIN_RTH = 0.13` means up to 13% of expected 1-minute bars (~51 bars out of 390 in a full RTH session) can be missing before the cache is considered incomplete. A ticker missing 51 consecutive minutes of data is still served from cache without triggering a refetch. The `fetcher.py:475` comment says "tolerate up to 5% missing bars" which contradicts the actual 13% constant, suggesting the value was changed without updating documentation.

**Recommendation**: Reduce to 0.05 (matches the DEFAULT tolerance and the fetcher comment), or make it configurable per-timeframe with reasonable defaults.

---

### M11 — f05 NaN ATR silently falls back to f01 target
**File**: `strategies/dominance_flip_reversal/variants.py:134–138`  
**Category**: stability  
**Cross-ref**: New finding

`atr = float(f.get("atr_5m", 0.0))` returns 0.0 if key missing, but returns `nan` if the key exists with `NaN` value. Then `new_target = sma_at_flip + 0.5 * nan = nan`, and `new_target > signal.entry_trigger` evaluates to `False` (all NaN comparisons are `False`). The code silently falls back to f01's original mean-touch target with no warning. The trade isn't corrupted, but f05 silently degrades to f01 behavior — inflating f05's reported trade count while underreporting the filter's true selectivity.

**Recommendation**: Add `math.isfinite(atr)` check before using ATR in target computation; log a warning if ATR is unavailable so the researcher knows f05 isn't applying its filter.

---

### M12 — `stop_limit_offset_dollars` in short simulator: complex conditional with potential fill-price confusion
**File**: `core/execution.py:221–228`  
**Category**: logic  
**Cross-ref**: New finding

```python
if bar_open < trigger:
    fill_base = limit if bar_open < limit else bar_open
else:
    fill_base = trigger
```

When `stop_limit_offset_dollars` is set and `bar_open < limit` (the bar opens below the limit price), the fill is at `limit`. But if the bar opens between `limit` and `trigger`, the fill is at `bar_open`. This is the mirror of the long logic, but the conditional nesting (lines 221–228) is harder to reason about than the long version (lines 91–98). The short version has 3 nested conditions where the long version has 2. While it appears logically correct, the asymmetry makes maintenance riskier — a future change to one direction could miss updating the other.

**Recommendation**: Refactor both `stop_limit_offset_dollars` paths into a shared helper function with clear direction-switching to eliminate the code duplication and asymmetry.

---

### M13 — `execution.py:88,218` strict inequality for entry triggering
**File**: `core/execution.py:88, 218`  
**Category**: accuracy  
**Cross-ref**: New finding

Both `simulate_long_breakout` (`high < trigger`) and `simulate_short_breakout` (`low > trigger`) use strict inequality. A bar whose high exactly equals the trigger price does NOT trigger an entry. This is the documented conservative choice, but it systematically skips exact-touch breakouts — potentially reducing trade counts by a small percentage and affecting strategy comparisons if any variant relies on tighter thresholds.

**Recommendation**: Document this choice prominently in the docstring and consider making it configurable (e.g., `entry_policy: "strict" | "inclusive"`).

---

### M14 — o03 ML artifact trained on 2024 used for pre-2024 backtests
**File**: `strategies/stocks_in_play_orb/o03.py:93–94, 201–214`  
**Category**: accuracy (look-ahead risk)  
**Cross-ref**: composer §2 (research ↔ production drift) — **partially addressed**

The ML model artifact was trained on 2024 data. When backtesting on 2022–2023, using the model constitutes temporal look-ahead bias. The code acknowledges this (line 93–94 comment) but requires manual intervention (`O03_DISABLE_ML=1` env var) to disable. There is no automatic guard that checks `context.trade_date.year < 2024` and disables ML scoring. A researcher unaware of this produces inflated backtest results on pre-2024 data.

**Recommendation**: Add an automatic gate: if `context.trade_date < ARTIFACT_TRAIN_START_DATE`, fall back to RV ranking with a logged warning. Make the env var override explicit opt-in for "I know this is look-ahead."

---

### M15 — `o02` rounds position size, `o04–o09` truncate
**File**: `strategies/stocks_in_play_orb/o02.py:124` vs `variants.py:150`  
**Category**: logic (inconsistency)  
**Cross-ref**: New finding

`o02` rounds: `int(round(qty))`. `o04–o09` truncate: `int(qty)`. For a computed quantity of 2.5, o02 buys 3 shares while o04 buys 2 — a ~20% difference on small positions. Since o02 is the "SSRN replication" and o04+ are "paper-faithful" variants intended to be directly comparable, this subtle rounding difference means their position sizing is not strictly identical. The paper spec doesn't specify rounding, so either is defensible, but the inconsistency within the same family is a foot-gun for A/B comparison.

**Recommendation**: Pick one convention and apply it consistently across the family. Document the choice.

---

### M16 — `d09`/`d10` ATR filter adds undocumented data-availability gate
**File**: `strategies/post_gap_opening_drive/variants.py:119–128`  
**Category**: logic  
**Cross-ref**: New finding

When `max_candle_atr_frac` (d09) or `min_candle_atr_frac` (d10) is set, the code calls `daily_atr_14()` and skips the candidate entirely if ATR cannot be computed (fewer than 15 daily bars, ATR ≤ 0). This means d09/d10 silently drop tickers lacking sufficient daily history — an implicit filter layered on top of d01's baseline. Neither d09.py nor d10.py's docstrings mention this dependency.

**Recommendation**: Document the data-availability requirement in d09/d10 docstrings, or move the ATR check to `build_candidates` qualifiers so rejected tickers appear in the candidates table with a clear reason.

---

## 🟢 LOW Severity

### L1 — `_finalize_run` COALESCE preserves stale failure notes
**File**: `runner/pipeline.py:880–883`  
**Category**: logic  
**Cross-ref**: New finding

```python
"UPDATE runs SET status = ?, completed_at = ?, notes = COALESCE(?, notes) WHERE run_id = ?"
```

When a run completes successfully, the caller passes `notes=""`. `COALESCE("", notes)` returns `""` (empty string is not NULL in SQLite/DuckDB), which replaces existing notes instead of preserving them. This is actually the intended behavior (line 520–522 comment: "Pass '' … so a resumed run's stale failure traceback in notes is cleared"), but passing `None` would use the COALESCE fallback correctly. The code works as intended but uses SQL semantics in a confusing way — future readers may think passing `""` preserves old notes.

**Recommendation**: Use an explicit `CASE WHEN ? IS NOT NULL THEN ? ELSE notes END` pattern, or document the COALESCE behavior with a comment explaining that empty string ≠ NULL.

---

### L2 — `opening_relative_volume` (d variants) duplicates common.py's fragile timezone assumption
**File**: `strategies/post_gap_opening_drive/variants.py:44–49`  
**Category**: stability  
**Cross-ref**: New finding (same pattern as M2)

Same timezone-naive assumption pattern as `common.py:92`. The `else` branch passes the DataFrame through as-is and calls `between_time("09:30", "09:35")`, implicitly assuming a tz-naive index is NY local time.

**Recommendation**: Apply the same fix as M2 — use `tz_localize` or assert the timezone.

---

### L3 — `DriveVariant.build_candidates` mutates shared `Candidate.features` in place
**File**: `strategies/post_gap_opening_drive/variants.py:109, 117, 129`  
**Category**: stability  
**Cross-ref**: New finding

The variant directly mutates `c.features` (aliased as `f`) by inserting keys like `"rv"`, `"spy_gap_pct"`, and `"candle_atr_frac"`. Since `Candidate.features` is a mutable dict, these mutations persist on the original Candidate objects in the calling code's list. Currently safe because there's only one consumer, but if another consumer held a reference to the pre-filter candidate list, it would observe silently mutated objects.

**Recommendation**: Create a copy before mutation: `f = dict(c.features)`.

---

### L4 — `spy_atr_regime_hot` bypasses `StrategyContext` (same pattern as H2)
**File**: `strategies/stocks_in_play_orb/variants.py:179–207`  
**Category**: logic  
**Cross-ref**: New finding

Same architecture violation as H2 — calls `fetch_daily_context("SPY", ...)` directly instead of reading from `context.spy_daily`. Uses its own lookback (403 calendar days) and its own ATR calculation that could diverge from `daily_atr_14` in `research/filters.py`.

**Recommendation**: Refactor to use `context.spy_daily` with `requires_spy_daily = True`.

---

### L5 — `or_start_minute` feature recorded but never used for filtering
**File**: `strategies/stocks_in_play_orb/common.py:132`  
**Category**: logic (dead data)  
**Cross-ref**: composer R-05 — **UNRESOLVED**

The `or_start_minute` field is recorded in candidate features (indicating whether the opening-range bar is shifted from 09:30) but no variant actually filters on it. Composer R-05 noted this creates a silent 5-minute bar shift in fallback paths. The field exists to detect this shift but isn't used to reject candidates or adjust RV calculations.

**Recommendation**: Either add filtering logic that uses `or_start_minute`, or remove the field to avoid misleading future researchers.

---

### L6 — `historical_5m_lookback_days` declared on leaf classes, not variant base
**File**: `strategies/post_gap_opening_drive/d02.py:23`, `strategies/dominance_flip_reversal/f03.py:30`  
**Category**: opportunity  
**Cross-ref**: New finding

d02 and f03 set `historical_5m_lookback_days` directly on their leaf classes. The `DriveVariant` and `FlipVariant` base classes don't declare this attribute — they inherit the default `0` from `StrategyRelease`. A developer scanning the variant base class to understand all pipeline knobs would miss this attribute entirely.

**Recommendation**: Declare `historical_5m_lookback_days: int = 0` on `DriveVariant` and `FlipVariant` with the default value, so the full parameter surface is visible in one place.

---

### L7 — `FlipVariant.warm_start_lookback_days` dead attribute
**File**: `strategies/dominance_flip_reversal/variants.py:62`  
**Category**: stability (dead code)  
**Cross-ref**: New finding

`warm_start_lookback_days: int = 2` is declared on `FlipVariant` but never read by any code. The actual warm-start logic reads `context.historical_5m.get(ticker)` directly, and the lookback is controlled by `historical_5m_lookback_days = 2` on f03. Changing `warm_start_lookback_days` has zero effect.

**Recommendation**: Remove the dead attribute, or wire it into the historical data loading path if it was intended to be tunable.

---

### L8 — `compute_flip_indicators` uses population std (`ddof=0`) for z-scores
**File**: `strategies/dominance_flip_reversal/common.py:45, 56`  
**Category**: accuracy (statistical convention)  
**Cross-ref**: New finding

Both price and volume z-scores use `std(ddof=0)` (population standard deviation). Standard practice in trading indicator libraries (TA-Lib, pandas-ta, Tulipy) uses `ddof=1` (sample). For a 20-bar window, the difference is √(19/20) ≈ 0.975 — small but systematic. This means z-score thresholds (`z_extreme = 2.0`, `vol_climax_z = 1.0`) define slightly different extreme zones than reference implementations.

**Recommendation**: Either switch to `ddof=1` and adjust thresholds accordingly, or document the deviation with rationale.

---

### L9 — `has_split_like_jump` depends on `daily.index.date` which returns local date
**File**: `research/filters.py:13, 78, 120`  
**Category**: accuracy  
**Cross-ref**: New finding (related to composer R-04 / F-01)

`daily[daily.index.date < trade_date]` is used in `min_price`, `min_avg_daily_volume`, `daily_atr_14`, and `has_split_like_jump`. If daily bars have timezone-aware timestamps (e.g., `2024-06-13 00:00:00-04:00`), `.date` returns the local NY date — correct. But if daily bars are timezone-naive at midnight UTC, `.date` could return a different calendar date, causing the `< trade_date` filter to include the trade date's own bar (look-ahead) or exclude valid prior bars.

**Recommendation**: Add an assertion or defensive normalization in `_normalize_columns` (`data/market_data.py`) that daily bars are NY-localized, or use `pd.Timestamp(trade_date).tz_localize(NY)` for the comparison.

---

### L10 — `stop_loss` usage of `abs(risk)` masks invalid stop placement
**File**: `strategies/stocks_in_play_orb/variants.py:143`  
**Category**: logic  
**Cross-ref**: New finding

```python
risk_per_share = abs(entry_trigger - stop_price)
```

Using `abs()` masks a potential logic error: if `stop_price > entry_trigger` for a long trade (stop ABOVE entry — invalid), `abs()` makes `risk_per_share` positive and the trade proceeds with a nonsensical stop level. Using `entry_trigger - stop_price` directly and checking `< 0` would catch such errors during development.

**Recommendation**: Use directional risk: `entry_trigger - stop_price` for longs, `stop_price - entry_trigger` for shorts. Assert `> 0`.

---

### L11 — `execution.py` VWAP computation assumes single-day bars
**File**: `core/execution.py:78–80`  
**Category**: accuracy (latent contract risk)  
**Cross-ref**: gemini §1.1 — **partially rebutted**

Gemini claimed VWAP is "mathematically corrupted" because `cumsum()` doesn't reset across sessions. **Verified**: The standard pipeline path (`_load_context`) populates `bars_5m` with single-day RTH bars from `fetch_intraday_day()`, so `cumsum()` is correct for the current contract. However, the simulator itself has no guard against multi-day DataFrames. If a strategy-level override or future pipeline change passes multi-day bars, VWAP would silently compute across session boundaries.

**Recommendation**: Add a defensive `groupby(bars_5m.index.date)` or an assertion that the index spans exactly one date in the simulator. The contract is currently upheld, but a guard prevents silent corruption if it's ever broken.

---

### L12 — Lock file accumulation
**Files**: `marketdata/locks.py:57–60`, `marketdata/data/.locks/*.lock`  
**Category**: stability  
**Cross-ref**: Noted in strategy-backtesting skill pitfalls, **UNRESOLVED**

`filelock.FileLock` never cleans up its marker files. The `.locks/` directory has accumulated stale lock files (visible in the repository listing). While each lock file is zero bytes, on filesystems with limited inodes this can become a problem over years of operation.

**Recommendation**: Add `lock_file.unlink(missing_ok=True)` in a `finally` block, as was done for the `dataset_lock` in the midday_vwap_pullback harness.

---

### L13 — `first_regular_5m_candle` deprecated but still used by o01
**File**: `research/filters.py:38`, `strategies/stocks_in_play_orb/o01.py:65`  
**Category**: opportunity  
**Cross-ref**: composer (noted as C4 — marked DEPRECATED, but not migrated)

o01 still calls the deprecated `first_regular_5m_candle`. The deprecated function delegates to `first_regular_5m_bar` so there's no correctness issue, but continued use of deprecated APIs is technical debt.

**Recommendation**: Migrate o01 to `first_regular_5m_bar`, then remove `first_regular_5m_candle`.

---

### L14 — `VWAP_BREAK` exit type in execution.py `_trade` not meaningful for breakout sim
**File**: `core/execution.py:404–443`  
**Category**: opportunity  
**Cross-ref**: New finding

The `_trade()` helper is shared between breakout and pullback simulators, but the breakout simulator never uses `"VWAP_BREAK"` as an exit reason — that's a midday_vwap_pullback concept. The function signature and logic are clean; this is noted only for cross-engine consistency.

---

### L15 — `tests/conftest.py` `bars[0].tz.zone` uses old pytz API on zoneinfo
**File**: `tests/test_marketdata_calendar.py:82`  
**Category**: stability  
**Cross-ref**: New finding (discovered during test run)

```python
assert bars[0].tz.zone == "America/New_York"
```

`zoneinfo.ZoneInfo` objects use `.key`, not `.zone` (which is a `pytz` API). This test fails on Python 3.11+ with `AttributeError`. The failure doesn't affect production code but prevents the full test suite from passing.

**Recommendation**: Change to `bars[0].tz.key == "America/New_York"` for zoneinfo compatibility.

---

### L16 — `report.py` report SQL missing `r.started_at` + `r.completed_at` in column list
**File**: `scripts/report.py:39–64`  
**Category**: opportunity  
**Cross-ref**: New finding

The CTE selects `r.started_at, r.completed_at` (line 45) but the outer SELECT doesn't include them. The SQL still works (the CTE just has extra columns), but it suggests the report was intended to show timestamps and they were dropped without cleanup.

**Recommendation**: Either add started/completed to the report output, or remove them from the CTE to avoid confusion.

---

### L17 — `variants.py` docstrings stale (d, f families)
**File**: `strategies/post_gap_opening_drive/variants.py:1–20`, `strategies/dominance_flip_reversal/variants.py:1–5`  
**Category**: opportunity  
**Cross-ref**: New finding

The `DriveVariant` module docstring says "Parametrized base for the d02–d04 post-gap-opening-drive variants" but the file now supports d02 through d10. The `FlipVariant` module docstring similarly doesn't document the full parameter surface. A developer scanning the file header would miss that 9 variants exist.

**Recommendation**: Update docstrings to list all registered knobs with defaults.

---

### L18 — `log_dollar_vol` feature uses unreliable average when fewer than 14 daily bars
**File**: `strategies/stocks_in_play_orb/common.py:117`  
**Category**: logic  
**Cross-ref**: New finding

```python
avg_vol_14 = float(hist_daily["volume"].tail(14).mean())
```

If `hist_daily` has fewer than 14 rows, `tail(14)` returns all available rows and `.mean()` computes the average over whatever is available. The `min_hist_days=10` guard in `build_sip_base` only applies to 5m opening bars, not daily volume history. A ticker with 5 daily bars but 10+ historical 5m bars passes the gauntlet with a dubious volume average.

**Recommendation**: Add a minimum daily-bar count guard, or use `min(len(hist_daily), 14)` and flag the feature as incomplete.

---

### L19 — `build_candidates` double-calls `build_sip_base` for short-capable variants
**File**: `strategies/stocks_in_play_orb/variants.py:60–104`  
**Category**: opportunity (performance)  
**Cross-ref**: New finding

When `allow_short=True`, `build_candidates` calls `build_sip_base` twice per ticker — once for long (green candle), once for short (red candle). Since the candle color is determined by the first bar, at most one succeeds. The failed call still does all the expensive work: historical volume mean, ATR, split-like jump check, daily context filtering. For 500 tickers, this roughly doubles the work for negligible gain.

**Recommendation**: Determine candle color once per ticker, then apply direction filtering without re-running the full gauntlet.

---

### L20 — `_is_plausible` guard not yet ported from midday_vwap_pullback
**File**: `runner/pipeline.py` (absent)  
**Category**: opportunity  
**Cross-ref**: Noted in strategy-backtesting skill

The `midday_vwap_pullback` harness has a three-layer defense-in-depth chain for ghost exit prices (pipeline guard + release-level `MAX_STOP_RATIO` + exit-fill `_is_plausible()`). `strategy_lab` has none of these. While the strategy_lab simulators are simpler (single-bar entry, stop/target/time_exit only), and ghost exits haven't been observed, the absence of any fill-plausibility check means a computation bug that produces an impossible exit price would be silently persisted.

**Recommendation**: Port a simplified `_is_plausible` guard to the strategy_lab pipeline — validate that exit prices don't exceed known bar extreme by >5% and that the PnL is within a sane range (±50% intraday).

---

## Summary by Severity

| Severity | Count | Impact |
|----------|-------|--------|
| 🔴 HIGH | 6 | Silent data corruption, backtest crashes, resource exhaustion |
| 🟡 MEDIUM | 16 | Correctness under edge conditions, architecture violations, maintenance risk |
| 🟢 LOW | 20 | Documentation, dead code, fragile conventions, minor inefficiencies |

## Unresolved from Prior Reviews

| ID | Source | Issue | Status |
|----|--------|-------|--------|
| R-01 | composer | Stale partial data masked by `complete=True` | Still present |
| R-02 | composer | Expired negative-cache entries suppress gap detection | Still present |
| R-05 | composer | `or_start_minute` recorded but not used for filtering | Still present |
| L-12 | skill pitfalls | Lock file accumulation | Still present |
| H4/M9 | composer | `1day` default still `split` in direct `fetch_bars` calls (R-04) | Still present in `marketdata/fetcher.py:150-151` |

## Test Suite Status

- **220 passed**, 1 ZoneInfo API compat failure (test assertion, not production code)
- 1 env-dependent test failure (no Alpaca credentials configured — expected in dev)
- All strategy tests pass; marketdata integration tests all pass
- Test coverage is biased toward marketdata subsystem (12/32 test files); strategy family tests exist (o02, o03, f01, d variants) but core execution and pipeline have only integration-level coverage

---

## Recommendations by Effort/Impact

### Quick Wins (high impact, low effort)
1. **H1**: Add try/except around o03 feature extraction (1 line change)
2. **H2**: Wire f02 to use `context.spy_daily` (remove 15 lines, add 2)
3. **H3**: Check HTTP status in URLError reason (add ~10 lines in retry.py)
4. **M1**: Add `requires_spy_5m = True` on o06 (1 line)
5. **M7**: Validate `time_stop_at` format in `_time_stop_triggered` (3 lines)
6. **M11**: Add `math.isfinite(atr)` check in f05 (1 line)
7. **L15**: Fix `tz.zone` → `tz.key` in test (1 line)
8. **L12**: Add lock file cleanup in `finally` block (2 lines)

### Strategic Investments (medium effort, lasting impact)
1. **M3**: Refactor DuckDB transaction scope (restructure ~50 lines in pipeline.py)
2. **M4**: Replace DataFrame-load coverage counting with Parquet metadata queries
3. **M6**: Implement `active_negative_cache()` helper + `ignore_complete` flag (R-01/R-02 fix)
4. **M10**: Reduce 1-min completeness tolerance to 5% and verify against existing cache
5. **H4**: Improve `_trading_days_since` fallback to exclude weekends
6. **M2/M12/L2**: Add defensive timezone guards across strategy families
7. **M12**: Refactor `stop_limit_offset_dollars` into shared direction-switching helper
