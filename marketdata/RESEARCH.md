# Research Findings (Effort 5)

## Storage Format Candidates

### Parquet — RECOMMENDED ✅
- **Compression:** 10-15x vs CSV/SQLite (50GB SQLite → ~3GB Parquet zstd — PBieda blog)
- **Read speed:** Columnar projection (read only needed columns), predicate pushdown (skip irrelevant row groups)
- **Ecosystem:** Native pandas, pyarrow, DuckDB, Polars, Spark
- **Git-friendly:** Small individual files, easy to exclude per-ticker
- **Proven in:** quant-pipeline, ml4t-data, market-data-warehouse, ArcticDB (underlying format), tidy-finance migration
- **Verdict:** Industry standard for analytical time-series data

### Feather — NOT RECOMMENDED ❌
- Good speed (Arrow IPC format) but no compression for string columns
- Known memory issues with large DataFrames (Sheftel benchmarks)
- Less ecosystem support than Parquet

### DuckDB Native — OPTIONAL QUERY LAYER
- Excellent for ad-hoc SQL across multi-ticker datasets
- Can query Parquet files directly — no need to import into DuckDB format
- Benchmark: 0.42s vs 21.4s for SQLite on same tick data query (PBieda blog)
- DuckDB vs Parquet: Parquet format query is 2-3x slower than DuckDB native, but native format is 4x larger on disk (DuckDB issue #10161)
- Recommendation: Use DuckDB as optional query layer over Parquet, not primary storage

### ArcticDB — OVERKILL ❌
- Requires LMDB or S3 backend (not local-only file-friendly)
- Pipeline from Man Group designed for petabyte-scale S3 workflows
- Not pip-installable without C++ compilation issues on some systems
- Overkill for a single-machine stock data pipeline with ~500 tickers

### HDF5 — LEGACY ❌
- Single file per dataset (can't do per-ticker granulation)
- Complex API, limited ecosystem
- No git-friendly structure

## Directory Structure Patterns

| Project | Pattern | Partitioning |
|---------|---------|-------------|
| **quant-pipeline** | `bars/{timeframe}/{ticker}/year={year}/bars.parquet` | Year per day/hourly, plus DuckDB views |
| **ml4t-data** (Hive) | `{ticker}/year={y}/month={m}/data.parquet` | Granularity configurable per timeframe |
| **market-data-warehouse** | `bronze/asset_class=equity/symbol={ticker}/data.parquet` | Asset class + symbol |
| **PBieda blog** | `ticks/{symbol}/{date}.parquet` | Per-symbol, per-day files |

**Chosen:** quant-pipeline + ml4t-data hybrid — `{timeframe}/{ticker}/year={y}/month={m}/data.parquet` with granularity tuned to timeframe.

## Provider Routing Patterns

| Project | Provider | Fallback | Cache |
|---------|----------|----------|-------|
| **stockfeed** | Tiingo, Finnhub, Alpaca, YFinance, etc. | Transparent failover, yfinance is final | DuckDB embedded |
| **quant-pipeline** | Alpaca only | None | Parquet files |
| **current (quick_flip_monitor)** | Alpaca → MarketData → YFinance | Env-flag gated, with batch yfinance | SQLite + full-series accumulator |
| **current (midday_vwap)** | Alpaca → MarketData | Env-flag gated | SQLite |

**Chosen:** stockfeed's ordered-try pattern. All providers implement the same `fetch_bars()` interface. Priority list per timeframe. YFinance always last.

## Cache Freshness Research

Article: "Fresh Enough to Render" (Daniel Romitelli, 2026) — key design principle:
> *"Expiration stored with the value — not in a separate metadata table."*

| Source | Intraday TTL | Daily TTL | Historical |
|--------|-------------|-----------|------------|
| Romitelli dashboard | 5 min | 60 min | Not specified |
| Current quick_flip | 2 hours | End of day | Infinite |
| Current midday_vwap | 2 hours | End of day | Infinite |

**Chosen:** Current system already has sensible TTLs. The spec formalizes them into an explicit `FreshnessRule` table instead of hardcoded `if` checks.

## Concurrency

The per-ticker `threading.Lock` pattern from `backtesting/data.py` was the most expensive fix in the project's history (29s → 1s run time, as documented in strategy-finder-conventions). This pattern is carried forward as-is.

## Sources Consulted

- [Parquet vs SQLite for tick data — PBieda Blog](https://pbieda.com/blog/optimizing-tick-data-storage-from-sqlite-to-parquet)
- [ml4t-data Hive Storage — ML4T Docs](https://ml4trading.io/docs/data/user-guide/storage/)
- [quant-pipeline — GitHub (nktkt)](https://github.com/nktkt/quant-pipeline)
- [DuckDB File Formats Guide](https://duckdb.org/docs/lts/guides/performance/file_formats.html)
- [DuckDB vs SQLite Discussion #10161](https://github.com/duckdb/duckdb/discussions/10161)
- [Cache Freshness for Market Data — Crafted by Daniel](https://craftedbydaniel.com/blog/fresh-enough-to-render-how-i-encode-market-data-trust-in-the-cache-layer)
- [stockfeed library — GitHub (fuzzyalej)](https://github.com/fuzzyalej/stockfeed)
- [market-data-warehouse — GitHub (joemccann)](https://github.com/joemccann/market-data-warehouse)
- [DuckDB vs SQLite — MotherDuck](https://motherduck.com/learn/duckdb-vs-sqlite-databases/)
- [Data Store Speed Comparisons — Sheftel Financial](https://blog.sheftel.net/2023/11/18/data-store-speed-comparisons/)
- [Storing Market Data — timestored.com](https://www.timestored.com/data/store-market-tick-data)
- [Working with Parquet and DuckDB — Low Hanging Data](https://lowhangingdata.com/article/working-with-parquet-and-duckdb/)
- [Parquet vs Row for Tick Data — WorldData](https://worlddata.cloud/cloud-cost-and-performance-trade-offs-for-storing-tick-level)
- [Tidy Finance SQLite to Parquet Migration Discussion](https://github.com/tidy-finance/website/issues/122)
- [Personal Market Database with DuckDB and Parquet — Jacob Ingle](https://medium.com/data-science-collective/how-i-built-a-personal-market-database-with-duckdb-and-parquet-step-by-step-27b0d1bb7e2e)
