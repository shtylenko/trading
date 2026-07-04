# Strategy Lab — Code Review Report

**Scope**: `trading/lab`
**Reviewer**: GitHub Copilot (Claude Sonnet 4.6)
**Date**: 2026-06-09
**Status**: Bugs / regressions found (no fixes applied)

---

## Severity Key

- 🔴 **High** — silently wrong results or data loss
- 🟡 **Moderate** — incorrect analytics / hard-to-debug behaviour
- 🟢 **Minor** — code quality, naming, minor inconsistency

---

## 1. `core/execution.py` — Simulator

### 🟡 B-01: `planned_r` is misnamed — computes realized R, not planned R

**File**: `core/execution.py`

```python
# line in _trade()
planned_r = (exit_price - entry_price) / (signal.entry_trigger - signal.stop_price)
```

`exit_price` is the *actual* slippage-adjusted fill price of the exit. This computes **realized R** relative to the original planned risk distance, not the pre-trade planned R ratio (which would always be `(target - trigger) / (trigger - stop)` = 1.0 for both o01 and d01). The denominator correctly uses `signal.entry_trigger - signal.stop_price`, but the numerator should be `signal.target_price - signal.entry_trigger`. The current formula is also misleading for `TIME_EXIT` trades (no target was set) and `STOP_LOSS` trades, where the ratio will be ≤ 0. Anyone reading this field assuming it means "planned reward/risk before entry" will draw wrong conclusions.

---

### 🟡 B-02: `slippage_pct` and `gross_pnl_pct` double-count slippage for consumers

**File**: `core/execution.py`

Slippage is already **baked into** `entry_price` and `exit_price` before `gross` is computed:

```python
entry_price = fill_base * (1 + config.entry_slippage_bps / 10_000)
exit_price  = target    * (1 - config.exit_slippage_bps / 10_000)
gross       = (exit_price - entry_price) / entry_price * 100.0
```

Then `slippage_pct` is separately reported as:

```python
slippage = (config.entry_slippage_bps + config.exit_slippage_bps) / 100.0
```

This field is **not subtracted from `pnl_pct`** (only `fees` is), which is technically correct — but any analytics code that computes `net = pnl_pct - slippage_pct - fees_pct` will **double-count slippage** and produce results more pessimistic than reality. There is no docstring or comment warning about this. The `SimulatedTrade` dataclass also stores `gross_pnl_pct` which already has slippage embedded, making the field name "gross" misleading.

---

### 🟢 B-03: `assert entry_price is not None` in hot-path loop

**File**: `core/execution.py`

```python
assert entry_price is not None
mfe = max(float(mfe or 0.0), ...)
```

`assert` is silently disabled when Python runs with `-O` or `-OO`. While the assertion is logically redundant (the preceding block guarantees `entry_price` is set), using an `assert` as a runtime guard in production simulation code is inappropriate.

---

### 🟢 B-04: MAE overstated when stop is hit on entry bar

On the same bar where entry occurs, the simulator computes MAE from `bar.low`, then checks whether `low <= stop`. If both happen on the same bar, `mae` will be `(bar.low - entry_price) / entry_price * 100`, which can be more negative than `(stop - entry_price) / entry_price * 100`. The true Maximum Adverse Excursion from the fill should be capped at the stop-out level. This causes MAE to look worse than the actual realized risk.

---

## 2. `strategies/stocks_in_play_orb/o02.py` — SSRN Replication Strategy

### 🟡 B-05: `prior_days` computed but never used — dead variable with latent confusion risk

**File**: `strategies/stocks_in_play_orb/o02.py`

```python
def build_candidates(self, context: StrategyContext) -> list[Candidate]:
    prior_days = get_prior_trading_days(context.trade_date, count=14)
    if len(prior_days) < 14:
        return []
    ...
    # `prior_days` is never referenced again
```

`prior_days` is computed and length-checked, then completely unused. The actual historical data slice used for RV computation comes from `context.historical_5m`, which is pre-loaded by the pipeline based on `historical_5m_lookback_days = 14`. The dead variable creates an impression that `prior_days` guards historical data availability, but if `context.historical_5m` was populated with a different window, `prior_days` would not catch that mismatch.

Additionally, the `get_prior_trading_days` guard (require exactly 14 days) and the later check (`if len(opening_bars) < 10: continue`) operate on **different quantities**, creating an inconsistency: `build_candidates` bails out entirely if there are fewer than 14 prior trading days in the calendar, but then tolerates up to 4 missing opening bars per individual ticker.

---

### 🟡 B-06: `daily_atr_14` uses SMA of True Range, not Wilder's ATR

**File**: `research/filters.py`

```python
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
return float(tr.tail(period).mean())
```

This is a **simple arithmetic mean of True Range** over the last 14 bars (SMA-TR), not Wilder's ATR (which uses exponential/recursive smoothing: `ATR_t = (ATR_{t-1} * 13 + TR_t) / 14`). The Zarattini, Barbon & Aziz 2024 SSRN paper uses Wilder's ATR. The stop-loss formula `stop = entry - 0.10 * atr` will produce different distances: SMA-TR is generally more reactive to recent volatility and produces larger ATR values than Wilder's during calm markets, resulting in **wider stops and smaller position sizes** than the paper intends. This directly affects the o02 backtested returns.

---

## 3. `marketdata/fetcher.py` — Three-Phase Fetch Pipeline

### 🟡 B-07: Negative cache written prematurely when a provider returns empty, before all providers are tried

**File**: `marketdata/fetcher.py`

```python
else:
    # Provider returned empty on a trading day — write negative cache under lock
    with dataset_lock(ticker, timeframe, session, adjustment):
        for d in remaining_dates:
            write_negative_cache(
                ticker, timeframe, session, adjustment,
                d.isoformat(), "provider_empty",
            )
```

This runs when **any** provider returns empty — even if there are still lower-priority providers in the chain that haven't been tried yet. On the *current* call this is harmless (the provider loop continues with `remaining_dates` unchanged). But the negative cache entries written with `reason="provider_empty"` and a current timestamp persist to disk. Any subsequent call to `fetch_bars` within 24 hours will see those entries in `_find_missing_dates` and skip those dates, preventing the remaining providers from being retried — even if the higher-priority provider had only a transient outage.

Example scenario: Alpaca is down for 30 minutes. `fetch_bars` is called, Alpaca returns empty, negative cache is written for all missing dates. The code continues to MarketData, which also returns empty (e.g., for an illiquid ticker). For the next 24 hours, both providers are blocked by the negative cache written from Alpaca's empty response, even if Alpaca recovers. Only the first provider to fail should write the negative cache after all providers are exhausted.

---

### 🟡 B-08: Cache "completeness" threshold inconsistency between `update_meta_coverage` and `_find_missing_dates`

**File**: `marketdata/storage.py` and `marketdata/fetcher.py`

`update_meta_coverage` marks a 1min RTH day as `complete=True` when `actual >= 340` (i.e., up to 50 missing bars = 12.8% tolerance):

```python
is_complete = (actual >= 340) if (timeframe == "1min" and expected == 390) else (actual >= expected)
```

But `_get_cached_data` (Phase 1) accepts the cache when gaps are < 13%:

```python
tolerance = 0.13 if (timeframe == "1min" and session == "rth") else 0.05
```

A day with 13.0% gaps (e.g., 340 actual bars, 50 missing) would be marked `complete=False` in metadata but *accepted as a cache hit* in Phase 1. However, `_find_missing_dates` (Phase 2) skips dates where `cov.get("complete", False)` is True. So a date at ~12.9% missing:
- Phase 1 returns the cached data ✓
- But if Phase 1 is bypassed (e.g., after TTL expiry), Phase 2 includes this date in `still_missing` because `complete=False`, triggering an unnecessary refetch.

The 13% cache-hit tolerance and the 12.8% coverage-complete threshold should be the same constant.

---

### 🟢 B-09: Phase 1 cache lock released before Phase 2 begins — TOCTOU window

**File**: `marketdata/fetcher.py`

Phase 1 acquires and releases the `dataset_lock`, then Phase 2 acquires it again. In a multi-threaded backtest, two threads fetching the same ticker could both miss the cache in Phase 1 and both proceed to fetch from providers. The final merge (`merge=True` in `write_bars`) handles the deduplication correctly, but it causes redundant provider API calls and double writes. A comment acknowledging this limitation would prevent future "optimizations" that break the merge safety net.

---

## 4. `runner/pipeline.py` — Orchestration

### 🔴 B-10: `_insert_*` helpers shadow outer `conn` parameter

**File**: `runner/pipeline.py`

```python
def _insert_candidate(session_id, trade_date, release, candidate, conn=None) -> None:
    def _run(db_conn):
        db_conn.execute(...)

    if conn is None:
        with connect() as conn:   # ← SHADOWS the 'conn' parameter
            _run(conn)
    else:
        _run(conn)
```

All five helpers (`_insert_candidate`, `_insert_signal`, `_insert_order`, `_insert_fills`, `_insert_trade`) have this pattern. Within the `with connect() as conn:` block, the name `conn` is rebound to the new connection, shadowing the function parameter. In Python this is valid (outer `conn` is `None` at this point), but it is a latent trap: if someone adds logic after the `with` block that references `conn` expecting the parameter, they'll silently get the closed connection. The inner binding should use a distinct name like `db_conn`.

---

### 🟡 B-11: `_create_run` uses naive `datetime.now()` in `run_id` string

**File**: `runner/pipeline.py`

```python
run_id = f"run_{release_id}_{testset.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
```

`datetime.now()` returns the local machine's naive datetime, while all timestamp fields in the DB use `_now()` which is `datetime.now(timezone.utc)`. On a machine in a non-UTC timezone, `run_id` timestamps will not sort chronologically against `started_at` timestamps. Should be `datetime.now(timezone.utc)`.

---

### 🟢 B-12: `summarize_run` reconstructs `SimulatedTrade` with wrong field values

**File**: `runner/pipeline.py`

```python
trades = [
    SimulatedTrade(
        ticker="",
        ...
        entry_price=1.0,   # ← placeholder
        exit_price=1.0,    # ← placeholder
        gross_pnl_pct=float(row[5] or 0.0),  # ← same as pnl_pct (fees ignored)
        ...
    )
    ...
]
```

The reconstructed `SimulatedTrade` objects passed to `compute_trade_metrics` use `pnl_pct` for both `pnl_pct` and `gross_pnl_pct`. The `fees_pct` and `slippage_pct` are set to `0.0`. This means `compute_trade_metrics` operates on the **net** PnL (post-fee) but treats it as both gross and net. The `profit_factor` and other metrics are therefore computed from net PnL, which is correct for the stored results. However, any future metric that computes gross P&F (e.g., `gross_win / gross_loss`) from the reconstructed objects would be wrong. This is a fragile but currently harmless design.

---

## 5. `marketdata/storage.py`

### 🟢 B-13: `write_bars` accumulates rows_written from merged data, not only new rows

**File**: `marketdata/storage.py`

```python
rows_written += len(write_df)
```

After merging with existing data, `write_df` contains **merged + new** rows, not just the newly added rows. The return value of `write_bars` (used in the `logger.info("[Cache WRITE] ... %d rows stored"`) overstates the number of new rows. Not a correctness bug but misleading logging.

---

## 6. `marketdata/locks.py`

### 🟢 B-14: `_thread_locks` dict grows unboundedly

**File**: `marketdata/locks.py`

```python
_thread_locks: dict[str, threading.Lock] = {}
```

A new `threading.Lock` is created for every distinct `(ticker, timeframe, session, adjustment)` key and stored permanently. In a long-running process with a large universe, this dict grows without bound. Locks are never removed. For a 500-ticker universe × 3 timeframes × 2 sessions × 2 adjustments = 6,000 entries minimum. Not a crash risk but a memory leak in long-running processes (e.g., live runners or repeated interactive sessions).

---

## 7. `research/filters.py`

### 🟢 B-15: `first_regular_5m_bar` uses `between_time` without explicit `inclusive` — version-dependent behaviour

**File**: `research/filters.py`

```python
regular = bars_5m.between_time("09:30", "09:34")
if regular.empty:
    regular = bars_5m.between_time("09:30", "09:35")
```

For a DataFrame with both 09:30 and 09:35 bars (which could happen if a provider returns higher-resolution data that wasn't properly filtered, or if `bars_5m` contains bars from a prior day due to a timezone issue), the fallback `between_time("09:30", "09:35")` selects **two** bars, and `regular.iloc[0]` returns the first. The 09:30 bar should always be preferred, but the condition `if regular.empty` would not trigger if 09:30 is present. The fallback path is only reachable when 09:30 is absent, making the `"09:35"` inclusion in the fallback technically correct — but the `inclusive` parameter is not specified, relying on pandas default which has changed across versions (`both` in older pandas, `left` in newer). This should be made explicit.

---

## 8. Tests

### 🟡 B-16: `test_marketdata_fetcher.py` — `_fresh_env` does not reload `storage` module, causing potential `DATA_DIR` isolation failure

**File**: `tests/test_marketdata_fetcher.py`

The `_fresh_env` fixture reloads `trading.marketdata.config` but does **not** reload `trading.marketdata.storage`. `storage.py` imports `DATA_DIR` at module load time:

```python
from .config import DATA_DIR, ...
```

Since `DATA_DIR` is a bound name in the `storage` module (not a late-binding attribute lookup on `config`), reloading `config` updates `config.DATA_DIR` but **not** `storage.DATA_DIR`. The `_seed_1min_data` and `_seed_daily_data` helpers call `storage.write_bars`, which resolves paths using the stale `storage.DATA_DIR`. If `storage` was imported before the fixture runs, seed data can silently be written to the default `marketdata/data/` directory instead of the test's temp directory, and subsequent reads in `fetch_bars` would look in the temp dir and find nothing.

By contrast, `test_marketdata_storage.py`'s `_isolated_data_dir` fixture correctly reloads both modules. The fetcher tests pass today likely because of import ordering — if `storage` is first imported during the test session *after* the env var is set, the bound `DATA_DIR` will be the temp dir. This is fragile and will silently fail if import order changes.

---

### 🟢 B-17: `TestFreshnessRules.test_historical_1min_never_stale` is a no-op test

**File**: `tests/test_marketdata_ttl.py`

```python
def test_historical_1min_never_stale(self):
    ...
    pass  # The test body ends with `pass`
```

The test creates a fake Parquet file (not a valid Parquet), sets an mtime, and then does nothing. The comment explains "we need to seed data properly" and then `pass`. This test provides no coverage; it should either be completed or deleted.

---

## 9. `data/market_data.py`

### 🟢 B-18: `fetch_daily_context` end date includes today — partial intraday daily bar may be cached

**File**: `data/market_data.py`

```python
end = ny_dt(trade_date, 23, 59)
```

For a same-day query, this fetches through 23:59 of the trade date. A daily-bar provider could return a partial intraday OHLCV bar for today (some providers do, reflecting the partial day). That bar would be written to the split-adjusted Parquet partition for the current year, potentially caching a stale OHLC for today's session. Strategy filters correctly exclude today's bar (`daily.index.date < trade_date`), so this doesn't affect signal generation — but it pollutes the cache for consumers that don't apply that filter.

---

## Summary Table

| ID | Severity | Module | Description |
|----|----------|--------|-------------|
| B-01 | 🟡 | `core/execution.py` | `planned_r` computes realized R, not planned pre-trade R |
| B-02 | 🟡 | `core/execution.py` | `slippage_pct` already embedded in `gross_pnl_pct` — double-counting risk |
| B-03 | 🟢 | `core/execution.py` | `assert` in simulation hot path — disabled by `-O` |
| B-04 | 🟢 | `core/execution.py` | MAE overstated on same-bar fill-and-stop scenario |
| B-05 | 🟡 | `o02.py` | `prior_days` is computed and checked but never used — dead guard |
| B-06 | 🟡 | `research/filters.py` | `daily_atr_14` uses SMA-TR, not Wilder's ATR — o02 stop distances differ from paper |
| B-07 | 🟡 | `marketdata/fetcher.py` | Negative cache written on first empty provider, blocks fallback providers for 24h |
| B-08 | 🟡 | `fetcher.py` + `storage.py` | Coverage `complete` threshold (12.8%) vs cache-hit tolerance (13%) inconsistency |
| B-09 | 🟢 | `marketdata/fetcher.py` | Phase 1 → Phase 2 lock gap allows redundant provider fetches under concurrency |
| B-10 | 🔴 | `runner/pipeline.py` | `_insert_*` helpers shadow `conn` parameter — latent trap for future edits |
| B-11 | 🟡 | `runner/pipeline.py` | `run_id` timestamp uses naive `datetime.now()`, inconsistent with UTC elsewhere |
| B-12 | 🟢 | `runner/pipeline.py` | `summarize_run` reconstructed `SimulatedTrade` uses pnl for both gross and net |
| B-13 | 🟢 | `marketdata/storage.py` | `write_bars` logs merged row count as "rows stored", overstates new rows |
| B-14 | 🟢 | `marketdata/locks.py` | `_thread_locks` dict grows unboundedly across ticker/timeframe combos |
| B-15 | 🟢 | `research/filters.py` | `between_time` `inclusive` default is version-dependent, not specified |
| B-16 | 🟡 | `tests/test_marketdata_fetcher.py` | `_fresh_env` doesn't reload `storage` — `DATA_DIR` isolation may break |
| B-17 | 🟢 | `tests/test_marketdata_ttl.py` | `test_historical_1min_never_stale` is a no-op (`pass`) |
| B-18 | 🟢 | `data/market_data.py` | `fetch_daily_context` end includes trade date — partial daily bar may be cached |

---

## Highest-Priority Items

1. **B-07** — The negative cache premature write is the most operationally dangerous issue: a single Alpaca outage (or an illiquid ticker returning empty from Alpaca) silently blocks all fallback providers for 24 hours on future calls.
2. **B-06** — SMA-TR vs Wilder's ATR affects o02 stop placement and position sizing, making the backtest non-comparable to the paper.
3. **B-01 + B-02** — `planned_r` and `slippage_pct` semantics will mislead any post-processing analytics code.
4. **B-10** — The `conn` variable shadow is safe today but is a sharp edge for the next person editing `pipeline.py`.
5. **B-16** — The test isolation bug in `test_marketdata_fetcher.py` could produce spurious passing/failing tests depending on import order.
