# trading

Research + execution monorepo for systematic trading. Three subsystems, one clean
dependency direction (`marketdata ← lab ← live`):

| Package | Role | Depends on |
|---|---|---|
| `trading.marketdata` | the finance **data layer** — the only market-data source (providers, cache, calendar, storage). Local caches (`marketdata/data/`, ~28GB) are gitignored, regenerated on demand. | — |
| `trading.lab` | strategy **research/discovery** harness (was `strategy_lab`): families, immutable releases, point-in-time universes, DuckDB ledger, the evaluation funnel. See `lab/CLAUDE.md`. | marketdata |
| `trading.live` | **live (paper-first) execution** of funnel-validated releases. Target-portfolio reconciliation against a broker; its own ledger (separate from lab's research DB). See `live/DESIGN.md`. | marketdata, lab |

`lab` and `live` read the **same** `marketdata` layer — that shared foundation is what
enforces backtest/live parity (the live signal is computed by the same `Release` code on the
same data the backtest used; never a re-implementation).

## Commands

Run from the **monorepo root** — the directory that contains `trading/`
(`/Users/shtylenko/Projects`) — so `trading` imports:

```bash
python3 -m pytest trading/lab/tests -q                       # lab test suite
python3 -m trading.lab.scripts.backtest --list               # research harness CLI
python3 -m trading.live.runner --release x03 --dry-run       # live (dry-run: prints plan, no orders)
```

## History

This grew out of `trading_strategy_finder`, which accreted many abandoned systems. In the
2026-06 refactor the three live pieces above were lifted into this `trading/` package and the
rest archived to `projects/_archive/trading_strategy_finder/` (history preserved via git
rename). Only `lab`, `marketdata`, and `live` are active; the archive is reference only.
