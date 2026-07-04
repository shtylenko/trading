# Strategy Lab Roadmap

## P0 — Essential Functionality

- Create standalone `strategy_lab` package.
- Use DuckDB for run, session, candidate, signal, order, fill, trade, and metrics storage.
- Use `strategy_lab.marketdata` for regular-hours and extended-hours data requests.
- Add standalone testsets and point-in-time universe files.
- Implement Python release registry.
- Implement `o01`: Stocks-in-Play ORB baseline.
- Implement `d01`: Post-Gap Opening Drive baseline.
- Add a backtest CLI.
- Add a report CLI focused on total PnL.
- Add a lightweight local dashboard.
- Add shared common-filter hooks without requiring filter search yet.

## P1 — Incremental Improvements

- Add richer execution modeling: spread, slippage, stop-limit caps, order expiry.
- Refine ORB relative-volume ranking and harden it across provider timestamp conventions.
- Add additional ORB ATR stop and no-target EOD exit release variants.
- Add gap-drive premarket volume, gap-hold, 2R target, scale-out, and EMA trailing releases.
- Add common filter library with reusable masks across strategies.
- Add combinatorial filter search with min-trade, outlier, and holdout controls.
- Add CAGR, max drawdown, daily return, and portfolio-level metrics.
- Add walk-forward test runner.
- Add outlier robustness reports and ex-best-N gates.
- Add release promotion checklist markdown templates.

## P2 — Advanced

- Add Neurotrader-style in-sample permutation tests.
- Add walk-forward permutation tests.
- Add daily dollar-return portfolio simulator.
- Add paper-trading bridge.
- Add broker/execution audit schema.
- Add live/paper dashboard states.
- Add model-based meta-labeling support for release families that need ML gates.
- Add market-regime and event-day overlays.
