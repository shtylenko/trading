**Findings**

- **High: 2025 boundary is not enforced.** `rebal_days = tdays[::cadence]` includes `2025-12-17`, while `_load_daily_bars` fetches beyond `dr.end`; `simulate_daily_hold` will exit that rebalance on `2026-01-16` if bars exist. That contaminates a sealed 2025-only comparison. Fix before verdict: prefilter rebalances whose `d+H <= dr.end`, or explicitly match the offline harness if it also crosses into 2026. See [swing_pipeline.py](/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab/runner/swing_pipeline.py:84) and [swing_pipeline.py](/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab/runner/swing_pipeline.py:89).

- **Medium: liquidity eligibility fails open if volume is missing/NaN.** Offline requires 20d dollar volume >= $10M. Here, no `volume` column skips the filter entirely, and NaN dollar volume will not fail `dvol < min`. Require finite volume/dvol or reject. See [x01.py](/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab/strategies/xsec_momentum/x01.py:78).

- **Medium: generic metrics are not portfolio returns.** The engine stores 50 per-name trades; `total_pnl_pct` sums those, not the equal-weight rebalance return. For the offline comparison, aggregate as `mean(pnl_pct)` by rebalance date, then compute period total/Sharpe from those period means. See [metrics.py](/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab/core/metrics.py:23).

- **Medium operational: swing runner does not call `summarize_run()`.** Trades persist, but `release_metrics` may not be populated before lifecycle/dashboard use. Add summary before auto-eval or keep this test out of funnel automation. See [swing_pipeline.py](/Users/shtylenko/Hermes/projects/trading_strategy_finder/trading/lab/runner/swing_pipeline.py:98).

**No Leak Found**

Ranking data is sliced through rebalance close only, and `c.iloc[-22] / c.iloc[-253] - 1` correctly maps to `close[d-21] / close[d-252] - 1`. Entry at the same close is an MOC/offline-reproduction assumption, not live-realistic unless you can submit the close auction order before knowing the final close. Exit indexing at `i+H` is consistent.

**Run Verdict**

I would fix/report the end-boundary behavior and volume fail-open before treating the 2025 cross-check as verdict-grade. After that, I’d expect direction and magnitude to reproduce, assuming the rebalance phase, PIT universe, and adjusted/unadjusted close convention match.

For apples-to-apples 10 bps round-trip cost, use:

```python
ExecutionConfig(entry_slippage_bps=0.0, exit_slippage_bps=0.0, fees_bps_per_side=5.0)
```

Default engine costs are about 5 bps round-trip, so default net should be higher than offline by roughly 5 bps per held-name round trip. Daily-hold unit tests pass: `5 passed`.