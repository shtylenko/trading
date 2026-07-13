# swing_screener

Historical / research screens for long-only swing strategies, using
`trading.marketdata` as the only OHLCV source.

## C2_BREAKOUT

52-week-high base breakout (Finviz-free). Spec: `library/strategies/C2_BREAKOUT/spec.md`.

```bash
# 2025 screen → backtest → portfolio
python3 -m trading.swing_screener.scripts.run_c2_screen \
  --start 2025-01-01 --end 2025-12-31
python3 -m trading.swing_screener.scripts.run_c2_backtest \
  --candidates trading/swing_screener/outputs/c2_breakout/candidates_2025-01-01_2025-12-31.parquet
python3 -m trading.swing_screener.scripts.run_c2_portfolio \
  --trades trading/swing_screener/outputs/c2_breakout/trades_2025-01-01_2025-12-31.parquet \
  --candidates trading/swing_screener/outputs/c2_breakout/candidates_2025-01-01_2025-12-31.parquet
```

## C1_PULLBACK

Leader pullback candidate screen (RSI(2) mean-reversion + RSI(14) pullback zone).

- Spec: [`library/strategies/C1_PULLBACK/spec.md`](library/strategies/C1_PULLBACK/spec.md)
- Strategy thesis: [`library/strategies/consolidated.md`](library/strategies/consolidated.md)

### Run

From monorepo root (`/Users/shtylenko/Projects`):

```bash
python3 -m trading.swing_screener.scripts.run_c1_screen \
  --start 2022-01-01 --end 2026-06-30 \
  --variant both \
  -v
```

Smoke (few tickers):

```bash
python3 -m trading.swing_screener.scripts.run_c1_screen \
  --start 2024-01-01 --end 2024-03-31 \
  --tickers AAPL,MSFT,NVDA,META,AMZN \
  --variant both -v
```

### Chart structure (v2)

Shared gates now include rising SMA50, 20d higher-high, 2–5 bar orderly
pullback, volume dry-up, support proximity (SMA20/EMA20/SMA50), and prior
swing-low hold. **Not** included: sector map, news headlines.

Toggle in `config/c1_pullback.yaml` → `structure.enabled`.

### Portfolio layer (capacity)

After backtest, select a tradable subset (max concurrent positions, sector cap, rank):

```bash
python3 -m trading.swing_screener.scripts.run_c1_portfolio \
  --trades trading/swing_screener/outputs/c1_pullback/trades_2025_v2.parquet \
  --candidates trading/swing_screener/outputs/c1_pullback/candidates_2025_v2.parquet \
  --max-positions 4 --max-per-sector 2
```

### Backtest (win rate / expectancy)

Simulates entries/exits from the candidate list (daily rules; C1_PB is a
buy-stop proxy, not full 15m reclaim):

```bash
python3 -m trading.swing_screener.scripts.run_c1_backtest \
  --candidates trading/swing_screener/outputs/c1_pullback/candidates_2022-01-01_2026-06-30.parquet \
  -v
```

Defaults (see `config/c1_pullback.yaml` → `backtest`):

- **C1_MR:** next-day open entry, disaster stop `min(2×ATR, 8%)`, exit RSI(2)>65 or close>SMA5 or day 5
- **C1_PB:** next-day buy stop at signal high +1%, stop under 5d pullback low, +2R target or day 7
- **Costs:** 5 bps/side; one open position per ticker

### Tests

```bash
python3 -m pytest trading/swing_screener/tests -q
```

### Outputs

Written under `outputs/c1_pullback/` (gitignored):

- `candidates_{start}_{end}.parquet`
- `summary_by_year_{start}_{end}.parquet`
- `trades_*.parquet` / `metrics_trades_*.parquet` (from backtest)
