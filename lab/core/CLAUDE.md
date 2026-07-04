# core/

The engine contract. Domain dataclasses, the execution simulator, metrics, and time helpers. Strategy releases and the runner depend on these — **change with care**; a change to `models.py` or `execution.py` ripples across every family and the DuckDB persistence flow.

| File | Role |
|---|---|
| `models.py` | the dataclasses every layer passes around (below) |
| `execution.py` | trade simulator: turns a `Signal` + bars into a `SimulatedTrade` |
| `metrics.py` | trade/release metrics (R, PnL%, etc.) |
| `time_utils.py` | New-York-time session helpers |

## Dataclasses (`models.py`)

- **`StrategyContext`** — everything a release sees for one `trade_date`. Always populated: `bars_5m`, `daily` (per-ticker `dict[str, DataFrame]`). Optionally hydrated by the runner when a release declares it: `extended_1m`, `bars_1m`, `historical_5m`, `spy_5m`, `spy_daily`. Releases read from here; they never call providers.
- **`Candidate`** — a ticker that passed eligibility: `ticker`, `rank`, `score`, `reason`, `features`. Output of `build_candidates`.
- **`Signal`** — entry thesis + planned levels: `entry_trigger`, `stop_price`, `target_price`, `setup_type`, `signal_time`, `metadata`. `risk_per_share` = `entry_trigger − stop_price` (≥0). Output of `build_signal`.
- **`SimulatedTrade`** — final outcome: `pnl_pct`, `gross_pnl_pct`, `realized_r`, `mfe_pct`/`mae_pct`, `exit_reason`, `fees_pct`, `slippage_pct`, plus strategy-specific `context` (JSON'd into DuckDB).
- **`ExecutionConfig`** — cost model.

## Execution-cost semantics (easy to get wrong)

Slippage is **baked into the simulated fill prices**, so `gross_pnl_pct` is already net of slippage. `slippage_pct` on a `SimulatedTrade` is **informational only — do not subtract it again**:

```
pnl_pct = gross_pnl_pct − fees_pct
```

`stop_limit_offset_dollars` is an absolute dollar offset added to the trigger for stop-limit entries. Defaults: entry/exit slippage 2.0 bps, fees 0.5 bps/side.
