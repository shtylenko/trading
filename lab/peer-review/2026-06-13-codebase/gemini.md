# Comprehensive Codebase Analysis: Strategy Lab Engine

This document outlines the findings of a comprehensive peer review of the `strategy_lab` engine. The analysis focuses on identifying issues and opportunities for improvement in accuracy, logic, and stability.

## 1. Accuracy & Logic Issues

### 1.1 Inaccurate Intraday VWAP Calculation
**Location:** `core/execution.py` (`simulate_long_breakout`)
**Issue:** The session VWAP gate uses a simple cumulative sum over the provided `bars_5m` DataFrame:
```python
typ = (bars_5m["high"] + bars_5m["low"] + bars_5m["close"]) / 3.0
cum_vol = bars_5m["volume"].cumsum()
vwap = (typ * bars_5m["volume"]).cumsum() / cum_vol.where(cum_vol > 0)
```
Because the `bars_5m` DataFrame passed to the simulator typically contains historical context (e.g., prior days fetched for indicators via lookback windows), `cumsum()` fails to reset at midnight. It erroneously accumulates volume and typical price across multiple trading sessions.
**Impact:** VWAP calculations are mathematically corrupted, making the `require_above_vwap` signal metadata gate logically invalid and causing false positives/negatives in trade entries.
**Recommendation:** Filter the DataFrame to isolate only the current trading day before calculating the session VWAP, or use a `groupby(bars_5m.index.date).cumsum()` to reset the VWAP at the start of each session.

### 1.2 "Same-Bar" Target vs. Stop Logic Constraints
**Location:** `core/execution.py`
**Issue:** The execution simulators check `if low <= stop:` before evaluating `if target is not None and high >= target:`. If both levels are hit within the same bar, the simulator assumes the stop loss triggered first.
**Impact:** While documented as a conservative feature, this systematically penalizes strategies with tight stops or targets on high-volatility setups, logging maximum losses for what might have been profitable trades. 
**Opportunity:** Since 1-minute data is often prefetched alongside 5-minute data (and prioritized in some paths), the engine could selectively drop down to 1-minute bars to resolve the exact intrabar sequence of the high/low when a 5-minute bar touches both levels, significantly improving backtest accuracy.

### 1.3 `position_returns` on Intraday Walk-Forwards
**Location:** `validation/gates.py` (`walkforward_permutation_test`)
**Issue:** The walk-forward permutation test calculates objectives via `position_returns(bars["close"], sig)`.
**Impact:** If an intraday strategy relies on explicit time-based exits (which the simulator supports), `position_returns` on raw close prices may mistakenly calculate overnight gap PnL if the signal array isn't forced to 0 at the session close.
**Recommendation:** Implement an automated intraday flattening pass in `position_returns` or the signal function for strategies that do not hold overnight, ensuring permutation tests reflect true intraday behavior.

---

## 2. Stability & Performance Issues

### 2.1 DuckDB Write Lock Contention During Simulations
**Location:** `runner/pipeline.py` (`run_backtest_for_date`)
**Issue:** The runner initiates a transaction (`db_conn.execute("BEGIN TRANSACTION")`) and then loops over all candidates. Inside this loop, it evaluates `release.build_signal(...)` and runs CPU-intensive pandas logic (`simulate_long_breakout`, etc.).
**Impact:** DuckDB supports only a single concurrent write transaction. By holding the write lock for the duration of the entire date's simulation, parallel execution of `run_backtest_for_testset` across multiple workers will stall. The database lock retries (capped at 10 minutes) will eventually trigger widespread timeout failures.
**Recommendation:** Refactor the loop to generate all signals and simulate all trades in memory first. Open the DuckDB connection and transaction only when it's time to bulk-insert the fully computed session results.

### 2.2 Unbounded Memory Consumption in Cache Sidecar Updates
**Location:** `marketdata/fetcher.py` (`_update_sidecar_coverage`)
**Issue:** To update metadata coverage statistics, the engine reads the entire requested date range into a DataFrame:
```python
all_bars = read_bars(ticker, timeframe, start=range_start, end=range_end, ...)
```
**Impact:** If a prefetch covers 5 years of 1-minute bars, this function loads the entire 5-year Parquet dataset into RAM simply to count the number of rows per day. In a parallel prefetching environment (`ThreadPoolExecutor`), this will rapidly cause Out of Memory (OOM) crashes.
**Recommendation:** Avoid loading data into memory just for row counts. Use `pyarrow.parquet` or DuckDB to directly query the row counts grouped by date against the Parquet dataset metadata, or maintain the daily count during the initial write.

### 2.3 `iterrows()` Iteration Bottleneck
**Location:** `core/execution.py`
**Issue:** All trade simulators loop through active price data using `for ts, bar in active.iterrows():`.
**Impact:** `iterrows()` creates a new Series object for every row, making it notoriously slow. When testing thousands of candidates across multi-year data, the simulator becomes the primary performance bottleneck.
**Recommendation:** Transition from `iterrows()` to `itertuples()` (which is significantly faster) or refactor the loop using vectorized NumPy operations / Numba for near-instant execution simulation.

### 2.4 Network Request TOCTOU (Time-of-Check to Time-of-Use)
**Location:** `marketdata/fetcher.py` (`fetch_bars`)
**Issue:** The cache is checked inside a `dataset_lock`, but the lock is released while fetching from providers to avoid blocking. It is re-acquired during the write phase.
**Impact:** Two concurrent threads requesting the same missing ticker data will both miss the cache, both dispatch identical requests to external APIs, and both attempt to write. This duplicates network latency and risks hitting provider API rate limits.
**Recommendation:** Implement a "request collapsing" or Future-flight tracking mechanism. If a fetch for `(ticker, timeframe, date)` is already in-flight, subsequent requests should await its completion rather than launching redundant API calls.

---

## 3. General Code Quality Improvements

### 3.1 Hardcoded Connectivity Checks
**Location:** `runner/pipeline.py` (`_wait_for_connectivity`)
**Issue:** The wait loop hardcodes the host to `data.alpaca.markets`. If the user limits the provider chain via `MARKETDATA_PROVIDERS=yfinance`, the engine will still ping Alpaca during an outage.
**Recommendation:** Dynamically derive the host from the prioritized provider in use, or use a neutral, high-availability host (e.g., `8.8.8.8`) to verify broad internet connectivity.

### 3.2 Suboptimal Database Insert Patterns
**Location:** `runner/pipeline.py`
**Issue:** Candidates, signals, orders, and trades are inserted via individual `INSERT` statements inside loops.
**Recommendation:** Transition to bulk inserts (`executemany()` or DuckDB's efficient DataFrame ingestion) to dramatically speed up data persistence and reduce I/O context switching overhead.
