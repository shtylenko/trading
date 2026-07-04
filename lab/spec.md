# Strategy Lab Specification

## Purpose

`strategy_lab` is a generic research harness for comparing long-only, same-day stock trading strategies. It starts from the engineering lessons in `midday_vwap_pullback`, but does not depend on that package.

The engine is designed around:

- independent strategy families, each with a stable alias and letter (`stocks_in_play_orb` / `o`, `post_gap_opening_drive` / `d`, etc.)
- immutable Python release modules (`o01`, `o02`, `d01`, ...)
- named standalone test sets
- point-in-time universe modeling
- shared execution, reporting, and dashboard tooling
- common filter libraries that can be reused across strategies
- DuckDB as the research ledger
- `trading.marketdata` as the only market-data source

P0 prioritizes total PnL. P1 adds CAGR-style portfolio metrics. P2 adds daily dollar-return evaluation and paper-trading support.

## Package Layout

Source code is intentionally grouped by responsibility:

```text
strategy_lab/
  core/       # domain models, execution simulator, metrics, time helpers
  data/       # strategy_lab.marketdata adapter, testset loader, universe loader
  storage/    # DuckDB schema and connection helpers
  research/   # common strategy filters and future search tooling
  runner/     # backtest orchestration and persistence flow
  strategies/ # strategy families and immutable release modules
  scripts/    # CLI and dashboard entry points
  tests/      # unit tests plus explicit live-provider marketdata checks
```

New code should import from the layered packages directly, such as `trading.lab.runner.pipeline` or `trading.lab.core.models`.

## P0 Strategies

### `o01` — Stocks-in-Play Opening Range Breakout Baseline

Long-only 5-minute opening range breakout:

- use regular-hours 5-minute bars
- first 5-minute candle must close green
- entry trigger is the first candle high
- stop is the first candle low
- target is 1R for P0
- time exit at 15:55 New York time

### `o02` — Stocks-in-Play Opening Range Breakout with Filters & Sizing

Added relative-volume ranking, ATR stop variants, top-20 stock-in-play selection, no-target exit at 15:59, and 1% risk-based position sizing.

### `o03` — Stocks-in-Play ORB v2 (ML + Pullback Entry)

Added LightGBM machine learning ranking and a passive pullback limit entry strategy:
- Declares `requires_rth_1m = True`, `requires_spy_daily = True`, and `entry_style = "pullback_limit"`.
- Ranked by ML classifier probability of hitting +2R before stop (fallback to RV).
- Trigger on 1-minute close above the opening 5-minute candle high.
- Entry via buy limit order at `H - 0.02 * ATR14` working for 30 minutes after trigger (maker execution).
- Stop-loss at `H - 0.10 * ATR14` (R distance).
- Exit at 15:59 New York time (no profit target).

This is a deliberately small baseline. Later releases should add more variations.

### `d01` — Post-Gap Opening Drive Baseline

Long-only gap-and-go baseline:

- use daily bars to detect a positive gap versus the prior day's high
- first 5-minute candle must close green
- entry trigger is the first candle high
- stop is the first candle low
- target is 1R for P0
- time exit at 11:30 New York time

Later `d02+` releases should add extended-hours volume filters, premarket gap-hold checks, stop-limit offsets, 2R/scale-out logic, and 9 EMA trailing exits.

### `f01` — Dominance Flip Reversal Baseline

Long-only intraday capitulation-reversal baseline (family spec in
`strategies/dominance_flip_reversal/spec.md`; letter `f` because `d` is owned
by `post_gap_opening_drive`):

- use same-day regular-hours 5-minute bars; eligibility requires last daily close ≥ $5 and 14-day average volume ≥ 1M
- price stretch: at least 12 consecutive bars with highs below the 20-period SMA (no mean touch)
- bullish RSI(14) divergence: lower price low inside the stretch with a higher RSI low
- z-score extreme: close z-score vs the 20-SMA reaches ≤ −2.0 with a volume z-score ≥ +1.0 on the extreme bar (liq-flow climax proxy)
- entry trigger is the high of the bar where the z-score flips back above −2.0 (flips after 15:00 are discarded)
- stop is the flush low minus 0.5 × intraday ATR(14); target is the 20-SMA at the flip bar (static mean-touch)
- time exit at 15:55 New York time

Later `f02+` releases should seed indicators from prior-day 5-minute history, add a signed-volume liq-flow delta, an N-bar time-decay abort, and market-regime filters.

## Database

All research results are written to `strategy_lab.duckdb`.

Core tables:

- `runs` — one row per backtest command execution.
- `sessions` — one row per release/date execution.
- `candidates` — per ticker/day eligibility and ranking context.
- `signals` — entry thesis and planned trade levels.
- `orders` — planned simulated orders.
- `fills` — simulated fills.
- `trades` — final trade outcomes and strategy-specific JSON context.
- `release_metrics` — summarized release/testset metrics.
- `search_runs` and `search_results` — future combinatorial filter-search ledger.

The schema keeps common fields normalized and stores strategy-specific details in JSON text. Each row carries `strategy_alias`, `strategy_letter`, and `release_id`, which keeps ORB, gap-drive, and future strategies comparable without forcing every strategy into one brittle table shape.

## Test Sets

Test sets live in `testsets/*.yaml`. They are intentionally owned by `strategy_lab` and do not import from `midday_vwap_pullback`.

Each testset may provide explicit `tickers`, or reference a point-in-time universe file in `universes/*.yaml`.

## Strategy Layout

Strategy releases live under:

```text
strategies/
  stocks_in_play_orb/
    o01.py
    o02.py
  post_gap_opening_drive/
    d01.py
  dominance_flip_reversal/
    f01.py
```

Each release file should start with a substantial header docstring covering identity, thesis, data requirements, entry rules, exit/risk rules, known limitations, and intended next releases.

Strategy releases declare non-default data requirements on the release class. The runner always loads current-day regular-hours 5-minute bars and daily context. Releases may additionally request `historical_5m_lookback_days` or `requires_extended_1m`; those datasets are hydrated into `StrategyContext` before candidate generation so release logic does not call providers directly.

## Universe Policy

Universe files model snapshots:

```yaml
name: sp500_sample_pit
policy: point_in_time
snapshots:
  - effective_date: "2024-01-01"
    tickers: ["AAPL", "MSFT", "NVDA"]
```

For a trade date, the engine uses the latest snapshot whose `effective_date` is less than or equal to that date. Static samples are allowed for smoke tests, but production validation should use real point-in-time constituents.

## Validation Discipline

P0 only needs runnable baselines, total PnL reporting, release/testset comparison, and clean run lineage.

P1 should add:

- outlier robustness
- walk-forward runs
- bootstrap daily confidence intervals
- CAGR and drawdown metrics
- common filter search
- release promotion checklists

P2 should add:

- Neurotrader-style permutation tests
- walk-forward permutation tests
- daily dollar-return portfolio simulation
- paper-trading bridge
- broker/execution audit tables
