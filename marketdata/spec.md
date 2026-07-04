# Strategy Lab MarketData — Unified Data Processor Specification

## Current Ownership

This component now lives inside `trading/marketdata` and is owned by `strategy_lab`. It is no longer a top-level `engine.stockmarketdata` package. Strategy Lab code should import it as:

```python
from trading.marketdata import fetch_bars
```

The default cache directory is `trading/marketdata/data`. Override it with `STRATEGY_LAB_MARKETDATA_DIR`; the old `STOCKMARKETDATA_DIR` name remains as a legacy fallback only.

## 1. Motivation & Goals

### Current State (3 Fragmented Approaches)

| Component | Storage | Provider Logic | Cache Mechanism | Timeframes |
|-----------|---------|---------------|-----------------|------------|
| **backtesting/data.py** | Per-ticker CSVs (`engine/backtesting/data/AAPL.csv`) | Alpaca only, no fallback | CSV file per ticker, per-ticker threading.Lock | Daily only |
| **midday_vwap_pullback/data.py + cache.py** | SQLite blob cache (`midday_vwap_cache.db`) | Alpaca → MarketData fallback, env flag gated | SQLite table (provider, ticker, start, end, minute_size as PK) | 1m, daily |
| **quick_flip_monitor/cache.py** | SQLite blob cache (`cache.db`) + full-daily-series merge | Alpaca batch, MarketData primary, yfinance batch fallback | SQLite table + full-daily accumulator (daily:full: prefix hack) | 1m, 5m, 15m, daily |

**Problems:**
- 3 separate cache databases that grow unboundedly (SQLite JSON blobs expand file size, can't push to git)
- 3 independent implementations of Alpaca client setup, env loading, MarketData URL construction
- No common interface — each project imports fetch functions from its own module
- Daily data exists as both CSV (backtesting) and SQLite blobs (both strategies)
- Quick Flip's pipeline embeds yfinance batch logic + MarketData routing inline, not reusable

### Design Goals

1. **Single source of truth** for all OHLCV market data
2. **Granular per-stock, per-timeframe file storage** — no monolithic SQLite databases
3. **Automatic provider routing** — declare priority, the system tries providers in order and falls through
4. **Unified cache freshness rules** — intraday vs daily TTLs, no per-project ad-hoc staleness logic
5. **Explicit data contracts** — session scope, adjustment mode, timezone, and coverage semantics are part of every request
6. **Git-friendly** — small individual files, easy to `.gitignore` or selectively commit
7. **Strategy Lab ownership** — this package is colocated with Strategy Lab because it is the market-data layer for Strategy Lab research
8. **Thread/process-safe** — preserve per-ticker locking and add file locks for multi-process backtests

---

## 2. Research Findings (Effort 5)

### 2.1 Storage Format: Parquet

| Format | Compression vs CSV | Read Speed | Pandas Integration | Git-Friendly | Maturity |
|--------|-------------------|------------|-------------------|-------------|----------|
| **Parquet (zstd)** | 10-15x | Excellent (columnar, predicate pushdown) | Native via pyarrow | Small files, binary | Industry standard |
| **Feather** | 3-5x | Excellent (Arrow IPC) | Native via pyarrow | Medium | Good but no compression on strings |
| **CSV** | 1x (baseline) | Poor (row parse, no pushdown) | Native | Text, diffable | Universal |
| **HDF5** | 5-8x | Good (chunked) | Via tables/h5py | Single file per dataset | Legacy; complex |
| **ArcticDB** | 8-12x | Best for updates & SELECT_CUT | Native | LMDB/S3 only | Production (Man Group) |
| **DuckDB native** | 5-8x | Best for analytical SQL | Through DuckDB | Single .duckdb file | Mature v1.0+ |

**Recommendation: Parquet with zstd compression** as the canonical storage format.
- 10-15x compression turns 50 GB SQLite → ~3 GB Parquet (verified by PBieda blog)
- Column projection reads only needed columns (open/high/low/close/volume)
- Predicate pushdown skips row groups that don't match filter dates
- Native pandas read via `pd.read_parquet(path)` — zero migration cost for existing code
- DuckDB can query Parquet files directly with SQL (useful for ad-hoc analytics)
- Per-ticker Parquet files are small enough to push selectively to git (e.g. `.gitignore` except a reference subset)

**DuckDB Lite** is recommended as an *optional* query layer (not primary storage). If a project wants SQL access across many tickers, DuckDB can create views over the Parquet directory. But the canonical store remains per-file Parquet.

### 2.2 Directory Structure: Hive-Partitioned

Based on the proven patterns from `quant-pipeline`, `ml4t-data`, and the `market-data-warehouse` reference architecture:

```
trading/marketdata/
├── __init__.py
├── provider.py          # Provider interface + routing
├── storage.py           # Parquet read/write layer
├── config.py            # DataDirectory + Timeframe constants
├── ttl.py               # Freshness rules
├── errors.py            # Exceptions
│
└── data/                # Default data root (configurable)
    ├── .gitignore
    │
    ├── 1min/
    │   ├── AAPL/
    │   │   ├── session=rth/
    │   │   │   ├── adjustment=raw/
    │   │   │   │   ├── meta.json  # Dataset sidecar: last_updated, coverage, negative cache
    │   │   │   │   ├── year=2024/
    │   │   │   │   │   ├── month=1/
    │   │   │   │   │   │   └── data.parquet
    │   │   │   │   │   └── month=2/
    │   │   │   │   │       └── data.parquet
    │   │   │   │   └── year=2025/
    │   │   │   │       └── month=3/
    │   │   │   │           └── data.parquet
    │   │   │   └── adjustment=split/
    │   │   │       └── ...
    │   │   └── session=extended/
    │   │       └── adjustment=raw/
    │   │           └── ...
    │   └── SPY/
    │       ├── meta.json
    │       └── ...
    │
    ├── 5min/
    │   └── ...
    │
    └── 1day/
        └── AAPL/
            ├── meta.json
            └── year=2024/
                └── data.parquet
```

**Partition granularity rationale** (from ml4t-data Hive partitions table):
| Timeframe | Partition by | Rows/partition | Justification |
|-----------|-------------|----------------|---------------|
| 1min | month | ~1,440 × 21 ≈ 30,240 | Below 200K row group for efficient reads |
| 5min | month | ~288 × 21 ≈ 6,048 | Good balance of file count vs size |
| 15min | year | ~84 × 252 ≈ 21,168 | Low density, one file per year is fine |
| 1day | year | ~252 | Tiny files — year is enough |

**Dataset key:** every stored dataset is keyed by `(ticker, timeframe, session, adjustment)`.

- `session="rth"` means regular trading hours only (`09:30-16:00 America/New_York`) and is the default for both existing strategy harnesses.
- `session="extended"` means premarket + regular hours (`04:00-16:00 America/New_York`) for workflows such as premarket RVOL.
- `adjustment="raw"` means actual traded OHLC prices. This is the default for intraday execution research because adjusted intraday prices can distort stops, VWAP, and opening ranges.
- `adjustment="split"` means split-adjusted only. This is the default for daily context/ATR.
- `adjustment="all"` means split/dividend-adjusted and is available for long-horizon daily analytics, but not the default for intraday.

**Why not flat (one file per ticker per timeframe)?** For 1min data, a single AAPL file covering 5 years would have ~1.3M rows. Parquet reads are already efficient for this, but Hive partitioning enables:
- Time-range slice without reading the entire file
- Incremental appends per partition (write only the new month)
- Parallel reads across partitions (DuckDB parallelizes files)
- Smaller files = easier git exclusion per partition

### 2.3 Provider Routing: Tiered Fallthrough

Modeled after `stockfeed`'s provider abstraction with tiered priority:

```
Tier 1: Alpaca (primary — free tier, SIP feed, reliable for daily + intraday)
↓  (on rate limit / auth failure / empty response / not found on date)
Tier 2: MarketData (fallback — good for historical, needs token)
↓  (on auth failure / empty response)
Tier 3: YFinance (final fallback — free, always available, no API key)
```

**Routing rules:**
- Provider priority is **configured per timeframe** (not global)
- Default: Alpaca (1min, 5min, 15min, daily) → MarketData (all) → YFinance (daily only, not intraday)
- If a provider returns empty data for a requested trading-session range without error, the system falls through (don't trust empty results from a paid provider as authoritative)
- Non-trading dates are filtered before provider calls using the exchange calendar and written as negative cache entries; weekends/holidays should not trigger provider fallthrough.
- If all providers return empty, return `None` (don't fail — caller decides)
- Provider failure is tracked and logged but never raises (graceful degradation)

**Canonical provider model:**
```python
class Provider:
    name: str
    priority: int
    timeframes: set[Timeframe]
    sessions: set[Session]
    adjustments: set[Adjustment]
    max_lookback_days: int | None  # None = unlimited
    requires_auth: bool
    is_free: bool
```

### 2.4 Cache Freshness Rules

Based on the "encode trust in the cache" principle from the financial dashboard research:

| Data Type | Condition | TTL / Freshness Rule | Rationale |
|-----------|-----------|---------------------|-----------|
| **Intraday (today)** | Today's 1min/5min | 120 minutes since retrieval | Market moves intraday, but 5-min historical bars don't update after close |
| **Intraday (historical)** | Any past date | Infinite — never re-fetch | Historic intraday bars are immutable |
| **Daily (recent 3 days)** | Latest 3 trading days | 24 hours | Last 2 days may adjust (splits/dividends/provider corrections) |
| **Daily (historical)** | All older dates | Infinite — never re-fetch | Split/dividend-adjusted series are usually finalized after ~3 days |
| **Any (force refresh)** | Caller passes `force=True` | Bypass all TTL checks | For explicit re-fetch requests |
| **Negative cache** | Non-trading date or provider-confirmed empty trading date | Infinite for non-trading dates; 24 hours for trading-date provider empties | Avoid repeated holiday/weekend calls while allowing true provider misses to recover |

**Key insight:** These TTLs are assigned *at write time* and validated *at read time*. The cache stores `retrieved_at` per Parquet file (as metadata). On read, the system checks whether the file is within its freshness window. Expired files are not deleted — they're just skipped (the system fetches fresh data and writes a new partition; the old partition remains until explicitly pruned or overwritten via upsert).

### 2.5 Migration Path

The old top-level `engine/stockmarketdata` package has been moved under `trading/marketdata`.

**Current state**
- Strategy Lab imports from `trading.marketdata`.
- Existing local Parquet cache data moved with the package.
- `STRATEGY_LAB_MARKETDATA_DIR` is the preferred cache override.
- `STOCKMARKETDATA_DIR` is retained only as a compatibility fallback.

Historical migration notes from the former standalone package are intentionally omitted here. The active contract is that Strategy Lab owns this market-data layer and calls it through `trading.marketdata`.

---

## 3. Architecture

### 3.1 Package Structure

```
trading/marketdata/
├── __init__.py               # Public exports
├── spec.md                   # This file
│
├── config.py                 # DataDirectory, Timeframe enum, defaults
├── errors.py                 # ProviderError, EmptyDataError, AuthError
│
├── provider.py               # Abstract provider interface + registry
├── providers/
│   ├── __init__.py
│   ├── alpaca_provider.py    # Alpaca Market Data API
│   ├── marketdata_provider.py # MarketData.app API
│   └── yfinance_provider.py  # YFinance (daily only)
│
├── storage.py                # Parquet read/write, Hive partitioning
├── ttl.py                    # Freshness rules, TTL table
├── calendar.py               # Trading calendar + expected bar/session coverage
├── locks.py                  # Thread locks + cross-process file locks
│
├── fetcher.py                # fetch_bars() — orchestrates provider + storage
│
└── data/                     # Default data directory (configurable via env)
    └── ...
```

### 3.2 Core Interfaces

#### `Timeframe` (config.py)

```python
from enum import Enum

class Timeframe(Enum):
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    DAY = "1day"

    @property
    def partition_granularity(self) -> str:
        """Hive partition granularity per ml4t-data guidelines."""
        mapping = {
            "1min": "month",
            "5min": "month",
            "15min": "year",
            "1day": "year",
        }
        return mapping[self.value]

    @property
    def lookback_days_default(self) -> int:
        """Sensible default fetch windows by timeframe."""
        mapping = {
            "1min": 5,     # last 5 trading days for intraday
            "5min": 30,    # recent month for 5m
            "15min": 60,   # 2-3 months for 15m
            "1day": 1000,  # deep history for daily
        }
        return mapping[self.value]
```

#### `Session`, `Adjustment`, and Timezone Contract (config.py)

```python
class Session(Enum):
    RTH = "rth"              # 09:30-16:00 ET
    EXTENDED = "extended"    # 04:00-16:00 ET


class Adjustment(Enum):
    RAW = "raw"              # Actual traded prices
    SPLIT = "split"          # Split-adjusted only
    ALL = "all"              # Split + dividend adjusted
```

**Public timezone contract:**
- Storage is always UTC (`timestamp` column is `datetime64[ns, UTC]`).
- `fetch_bars()` returns a timezone-aware `DatetimeIndex` in `America/New_York` by default because current strategy code slices by ET session times (`between_time("09:30", "16:00")`, opening boxes, VWAP windows).
- Callers may pass `tz="UTC"` to receive UTC-indexed data.
- Provider implementations normalize to UTC before writing; only the public read path converts to the requested return timezone.

#### `Provider` (provider.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class ProviderCapabilities:
    name: str
    priority: int            # Lower = tried first
    timeframes: set[str]     # e.g. {"1min", "5min", "1day"}
    sessions: set[str]       # e.g. {"rth", "extended"}
    adjustments: set[str]    # e.g. {"raw", "split", "all"}
    max_lookback_days: Optional[int] = None
    requires_auth: bool = True
    is_free: bool = False


class Provider(ABC):
    """Abstract base for any data provider."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        session: str,
        adjustment: str,
    ) -> pd.DataFrame:
        """Return OHLCV DataFrame with DatetimeIndex. Empty DataFrame on no data."""
        ...
```

#### `fetch_bars` (fetcher.py) — The Main Entry Point

```python
def fetch_bars(
    ticker: str,
    timeframe: str | Timeframe,
    start: datetime | None = None,
    end: datetime | None = None,
    session: str | Session = Session.RTH,
    adjustment: str | Adjustment | None = None,
    tz: str = "America/New_York",
    force: bool = False,
) -> pd.DataFrame | None:
    """
    Main entry point.

    Default parameter values:
      - end=None   → datetime.now(timezone.utc)
      - start=None → end - timedelta(days=Timeframe(timeframe).lookback_days_default)
      - session    → "rth"
      - adjustment → "raw" for intraday, "split" for daily
      - tz         → "America/New_York"

    Three-phase:

    1. CHECK CACHE — normalize the request into expected trading sessions/bar labels,
       check TTL via ttl.is_stale() for relevant partition(s), and validate coverage
       with calendar.coverage_gaps(). If cache is fresh and covers the expected bars,
       return the requested slice. If cache is stale or coverage has gaps, proceed to fetch.

    2. FETCH — iterate providers by priority for this timeframe.
       Gap tracking uses expected missing sessions/bar labels, not min/max timestamp.
       Pass only missing date/session windows to subsequent providers. Overlapping
       data from multiple providers is resolved by dedup on timestamp (higher-priority
       provider's row wins). If all providers are exhausted and gaps remain, write
       provider-empty negative cache entries and log a warning.

    3. STORE + RETURN — merge new data into existing Parquet partitions
       (dedup by timestamp). Update per-ticker sidecar metadata. Return merged DataFrame.
    """
    ...
```

### 3.3 Provider Registry & Routing Table

Defined in `provider.py`:

```python
_PROVIDER_REGISTRY: list[Provider] = []  # Ordered by priority

def register_provider(provider: Provider) -> None:
    """Add a provider. Sorted by priority on first use."""
    _PROVIDER_REGISTRY.append(provider)
    _PROVIDER_REGISTRY.sort(key=lambda p: p.capabilities.priority)

def get_providers_for_timeframe(timeframe: str) -> list[Provider]:
    """Return providers that support this timeframe, in priority order."""
    return [p for p in _PROVIDER_REGISTRY if timeframe in p.capabilities.timeframes]
```

**Default routing table:**

| Priority | Provider | 1min | 5min | 15min | 1day | Sessions | Adjustments | Auth Required |
|----------|----------|------|------|-------|------|----------|-------------|---------------|
| 1 | Alpaca | ✓ | ✓ | ✓ | ✓ | rth, extended | raw, split, all | Yes (env) |
| 2 | MarketData | ✓ | ✓ | ✓ | ✓ | rth, extended | raw | Yes (token) |
| 3 | YFinance | ✗ | ✗ | ✗ | ✓ | rth | split, all | No |

### 3.4 Storage Layer (storage.py)

```python
def resolve_path(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    year: int,
    month: int | None = None,
) -> Path:
    """
    Hive-partitioned path:
      1min:  data/1min/AAPL/session=rth/adjustment=raw/year=2024/month=1/data.parquet
      1day:  data/1day/AAPL/session=rth/adjustment=split/year=2024/data.parquet
    """
    ...

def read_bars(
    ticker: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    session: str = "rth",
    adjustment: str = "raw",
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """
    Read OHLCV from Parquet.
    - `timestamp` is stored as a regular Parquet column, not a DataFrame index.
      pyarrow filter pushdown only works on columns — storing timestamp as index
      breaks predicate pushdown. After reading, set it as the index:
      `df = df.set_index("timestamp")`.
    - Uses pyarrow's ParquetDataset with filter pushdown for Hive partitions
    - Converts the returned index to `tz` after reading
    - Returns empty DataFrame if no data exists
    - Optionally projects columns (only open/close/volume if that's all you need)
    """
    ...

def write_bars(
    ticker: str,
    timeframe: str,
    df: pd.DataFrame,
    session: str,
    adjustment: str,
    partition_by: str = "auto",  # uses Timeframe.partition_granularity
    merge: bool = True,
) -> int:
    """
    Write OHLCV DataFrame to Parquet.
    - Partitions by timestamp (year or year/month depending on timeframe)
    - If merge=True, reads existing partition, deduplicates by timestamp,
      and rewrites the partition file
    - Atomic write: write to a `tempfile.NamedTemporaryFile` in the same directory,
      then `Path.rename()` — atomic on POSIX when source and destination are on the
      same filesystem. Not safe across mount points.
    - Returns row count written
    """
    ...
```

### 3.5 TTL / Freshness Layer (ttl.py)

```python
@dataclass
class FreshnessRule:
    timeframe: str
    staleness_threshold: timedelta
    applies_when: Callable[[datetime], bool]  # e.g. "is today" or "is within last 3 days"

FRESHNESS_RULES = [
    FreshnessRule("1min", timedelta(hours=2), is_today_or_yesterday),
    FreshnessRule("5min", timedelta(hours=2), is_today_or_yesterday),
    FreshnessRule("15min", timedelta(hours=4), is_today_or_yesterday),
    FreshnessRule("1day", timedelta(days=1), is_within_last_3_days),
]

def is_stale(ticker: str, timeframe: str, file_path: Path) -> bool:
    """
    Returns True if the cached partition file should be re-fetched.

    - retrieved_at: the file's mtime — when this partition was last written to disk.
      Do NOT use the data's latest timestamp as retrieved_at. A file written
      yesterday containing yesterday's bars would measure ~24h old by data age,
      but the mtime correctly reflects when it was actually cached.
    - applies_when: receives the data's latest timestamp (in America/New_York)
      to decide whether the data is in the mutable window (e.g. "is this today's
      data?"). Date boundary comparisons use ET to match market day boundaries,
      not UTC (UTC midnight ≠ ET market day boundary).
    """
    rule = _get_rule(timeframe)
    retrieved_at = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
    data_latest = _get_latest_data_timestamp(file_path)  # max(timestamp) from Parquet
    if data_latest is None:
        return True  # Unreadable partition; treat as stale
    data_latest_et = data_latest.astimezone(ZoneInfo("America/New_York"))
    if not rule.applies_when(data_latest_et):
        return False  # Historical data — immutable, never stale
    return (datetime.now(timezone.utc) - retrieved_at) > rule.staleness_threshold
```

### 3.6 Calendar & Coverage (calendar.py)

Coverage validation is calendar-aware and timeframe-aware. It never treats market data as a continuous timestamp interval.

```python
def expected_bars(
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
) -> pd.DatetimeIndex:
    """
    Return expected bar labels in America/New_York for valid trading sessions.

    Rules:
      - Weekends and exchange holidays produce no expected bars.
      - Early closes use the exchange calendar's actual close time.
      - RTH uses 09:30 through the final label before/session close according
        to the timeframe's bar labeling convention.
      - Extended uses 04:00 through the final label before/session close.
      - Returned labels match the storage convention after UTC normalization:
        left-labeled bars (`closed="left", label="left"`) for 1m/5m/15m.
    """
    ...

def coverage_gaps(
    actual_index: pd.DatetimeIndex,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
    negative_cache: dict[str, dict] | None = None,
) -> list[datetime]:
    """
    Compare actual timestamps against expected_bars().

    Missing bars on non-trading dates and known negative-cache dates are ignored.
    Missing bars inside an expected trading session are returned as gaps.
    """
    ...
```

**Why this matters:** a 5-minute RTH session may legitimately end at a `15:55` label, daily bars may be date/midnight labeled, and holidays/weekends should have no bars. Min/max timestamp comparisons misclassify these cases and miss internal gaps.

### 3.7 Configuration (config.py)

```python
from pathlib import Path

# Default data directory
DATA_DIR = Path(__file__).resolve().parent / "data"

# Override via environment variable
import os
DATA_DIR = Path(os.getenv("STRATEGY_LAB_MARKETDATA_DIR", str(DATA_DIR)))

# Supported timeframes
SUPPORTED_TIMEFRAMES = {"1min", "5min", "15min", "1day"}
SUPPORTED_SESSIONS = {"rth", "extended"}
SUPPORTED_ADJUSTMENTS = {"raw", "split", "all"}

# Metadata is stored as sidecar files alongside each dataset key:
#   data/{timeframe}/{TICKER}/session={session}/adjustment={adjustment}/meta.json
# No global metadata.json — avoids write contention and scales to large universes.
# The dataset lock (see section 7) protects sidecar reads/writes.
```

---

## 4. Provider Implementations

### 4.1 AlpacaProvider

- **SDK:** `alpaca-py` (`StockHistoricalDataClient`)
- **Feed:** Configurable via env `ALPACA_HISTORICAL_FEED` (default: `"sip"`, fallback `"iex"`)
- **Credentials:** `ALPACA_API_KEY_ID`, `ALPACA_SECRET_KEY` (loaded from `.env`)
- **Timeframes:** 1min, 5min, 15min, daily
- **Sessions:** `rth`, `extended` (provider fetches a broad range, storage filters to the requested session)
- **Adjustments:** `raw`, `split`, `all`
- **Chunked fetch:** Splits ranges into 365-day chunks (proven pattern from backtesting/data.py)
- **Max lookback:** Alpaca free tier: 15 years for daily, ~7 days for intraday from IEX, full history from SIP
- **Fallback on empty:** Returns empty DataFrame (caller falls through to next provider)

### 4.2 MarketDataProvider

- **API:** REST via `urllib.request` (no SDK needed)
- **URL pattern:** `https://api.marketdata.app/v1/stocks/candles/{minute_size}/{TICKER}/?from={date}&to={date}`
- **Response format:** JSON with keys `t` (timestamps), `o`, `h`, `l`, `c`, `v`
- **Credentials:** `MARKETDATA_TOKEN` (loaded from `.env`)
- **Timeframes:** 1min, 5min, 15min, daily
- **Sessions:** `rth`, `extended`
- **Adjustments:** `raw` only. If the caller requests adjusted data, MarketData is skipped unless an explicit future adjustment pipeline is implemented.
- **No chunking needed** — single request for any range
- **Timezone handling:** MarketData returns UTC timestamps; store UTC and convert only on public read

### 4.3 YFinanceProvider

- **SDK:** `yfinance`
- **No credentials needed**
- **Timeframes:** Daily only (also supports 1wk, 1mo — but we only use daily)
- **Sessions:** `rth` only
- **Adjustments:** `split`, `all`
- **Limitations:** Rate limits (~2 requests/second), no intraday history from free tier
- **Adjustment handling:** use `auto_adjust=True` for `all`; use explicit split-adjustment logic for `split` if required. YFinance is skipped for `raw`.
- **Always last resort** — no auth, always available, but slowest and least reliable for precision

---

## 5. Directory Layout & File Naming

### 5.1 Parquet Schema

All Parquet files use a consistent schema:

| Column | Type | Notes |
|--------|------|-------|
| `timestamp` | datetime64[ns, UTC] | Regular Parquet column (not index). Set as index via `df.set_index("timestamp")` after reading. Always tz-aware UTC. |
| `open` | float64 | |
| `high` | float64 | |
| `low` | float64 | |
| `close` | float64 | |
| `volume` | int64 | |
| `trade_count` | int64 (optional) | Only if provider supplies it (Alpaca does) |
| `vwap` | float64 (optional) | Only if provider supplies it |
| `provider` | string | Provider that supplied the winning row after deduplication |
| `retrieved_at` | datetime64[ns, UTC] | Row-level retrieval timestamp for diagnostics; partition TTL still uses file metadata/mtime |

### 5.2 Metadata Sidecar Files

Each ticker/timeframe/session/adjustment combination has a `meta.json` sidecar stored above its Parquet partitions:

`data/1min/AAPL/session=rth/adjustment=raw/meta.json`:

```json
{
  "version": 1,
  "ticker": "AAPL",
  "timeframe": "1min",
  "session": "rth",
  "adjustment": "raw",
  "timezone_storage": "UTC",
  "timezone_default_return": "America/New_York",
  "last_updated": "2025-06-05T18:30:00Z",
  "earliest": "2020-01-02T14:30:00Z",
  "latest": "2025-06-05T20:00:00Z",
  "total_rows": 152340,
  "partitions": ["year=2024/month=1", "year=2024/month=2", "..."],
  "coverage": {
    "2025-06-05": {
      "expected_bars": 390,
      "actual_bars": 390,
      "complete": true
    }
  },
  "negative_cache": {
    "2025-01-01": {
      "reason": "non_trading_day",
      "retrieved_at": "2025-06-05T18:30:00Z"
    }
  }
}
```

The dataset/process lock (section 7) protects sidecar reads and writes. One sidecar per dataset key scales to a full SP500 universe without the write contention or merge conflict risk of a single global `metadata.json`.

### 5.3 .gitignore

```
data/
!data/.gitkeep
```

The `data/` directory is git-ignored by default. Individual users can override per-ticker if they want to share a subset (e.g. daily SPY data as reference). This solves the original problem — monolithic SQLite DBs that can't be pushed to git.

---

## 6. Migration & Backward Compatibility

### 6.1 Compatibility Adapter

Each consuming project gets a thin adapter that maps its existing API calls to `strategy_lab.marketdata`:

**midday_vwap_pullback adapter:**
```python
# Old: from .data import fetch_daily_bars, fetch_intraday_bars
# New: from trading.marketdata import fetch_bars

def fetch_daily_bars(ticker, end_date, lookback_days=60, logger=None):
    """Drop-in replacement for midday_vwap_pullback.data.fetch_daily_bars."""
    start = (end_date - timedelta(days=lookback_days))
    return fetch_bars(
        ticker,
        "1day",
        start=start,
        end=end_date,
        session="rth",
        adjustment="split",
    )

def fetch_intraday_bars(ticker, trade_date, minute_size=1, logger=None):
    """Drop-in replacement for midday_vwap_pullback.data.fetch_intraday_bars."""
    start = market_open_time(trade_date)
    end = market_close_time(trade_date)
    return fetch_bars(
        ticker,
        f"{minute_size}min",
        start=start,
        end=end,
        session="rth",
        adjustment="raw",
    )
```

**quick_flip_monitor adapter:**
```python
# The inline Alpaca batch + yfinance chunk logic in pipeline.py
# is replaced by calling strategy_lab.marketdata.fetch_bars() which
# handles the same routing internally.
```

### 6.2 Data Migration Script

`scripts/migrate_to_parquet.py` will:
1. Scan all existing `engine/backtesting/data/*.csv` files → export to `strategy_lab.marketdata/data/1day/{TICKER}/`
2. Export SQLite cache from `midday_vwap_cache.db` → separate into 1min and daily Parquet
3. Export SQLite cache from `engine/quick_flip_monitor/cache.db` → merge with above
4. Validate: compare row counts, date ranges, timezone normalization, duplicate timestamps, first/last timestamp per session, OHLC equality tolerance, and volume sums before/after
5. Generate per-ticker sidecar files (`meta.json` alongside each ticker's Parquet directory)

Migration maps existing cache rows as follows:
- Existing regular-hours intraday rows become `session=rth`, `adjustment=raw`.
- Existing premarket/extended rows become `session=extended`, `adjustment=raw`.
- Existing Alpaca/backtesting daily rows become `session=rth`, `adjustment=split` unless source metadata proves a different adjustment.
- Existing yfinance `auto_adjust=True` rows become `session=rth`, `adjustment=all`.

### 6.3 What Stays Behind

- **Strategy DBs** (`strategy_finder.db`, `midday_vwap_pullback.db`, `quick_flip_monitor/*.db`) — these contain trade results, test results, strategy configs; they are NOT replaced by strategy_lab.marketdata
- **Dataset locks** — the existing per-ticker thread-lock idea from `backtesting/data.py` will be expanded into dataset-key thread locks plus cross-process file locks

---

## 7. Thread Safety & Concurrency

The proven per-ticker lock pattern from `backtesting/data.py` is carried forward for threads, and a file lock is added for separate Python processes:

```python
_ticker_locks: dict[str, threading.Lock] = {}
_ticker_locks_lock = threading.Lock()

def _get_thread_lock(dataset_key: str) -> threading.Lock:
    with _ticker_locks_lock:
        if dataset_key not in _ticker_locks:
            _ticker_locks[dataset_key] = threading.Lock()
        return _ticker_locks[dataset_key]

@contextmanager
def dataset_lock(ticker: str, timeframe: str, session: str, adjustment: str):
    """
    Acquire both:
      1. an in-process threading.Lock, and
      2. a filesystem lock file under data/.locks/

    The filesystem lock protects concurrent scripts/backtests running in separate
    Python processes from racing on the same Parquet partition or meta.json.
    """
    key = f"{ticker.upper()}:{timeframe}:{session}:{adjustment}"
    with _get_thread_lock(key):
        with file_lock(DATA_DIR / ".locks" / f"{safe_key(key)}.lock"):
            yield
```

**Lock scope:** Wraps the entire fetch → cache-check → write cycle for a given `(ticker, timeframe, session, adjustment)` dataset, including Parquet partition rewrites and the `meta.json` sidecar update. Multiple workers requesting the same dataset block, but different tickers or independent dataset keys run in parallel. This prevents redundant provider fetches and protects against partial writes when multiple backtests run at the same time.

**Atomicity rules:**
- Parquet partition updates write to a temporary file in the destination directory, `fsync`, then `Path.replace()` the final `data.parquet`.
- `meta.json` updates use the same temp-file + replace pattern.
- Corrupt or partially written files are moved to `*.corrupt.{timestamp}` before refetch; do not silently delete them unless an explicit prune command is used.

---

## 8. Error Handling

| Scenario | Behavior |
|----------|----------|
| Provider auth failure | Log warning, skip provider, fall through to next |
| Provider rate limited | Log warning, backoff 60s, retry once, then fall through |
| Non-trading date | Write negative cache entry, skip providers |
| Provider empty response on trading date | Log debug, write 24h negative cache entry, fall through |
| All providers fail | Return `None`, log error with details |
| Corrupt Parquet file | Log error, quarantine file, re-fetch from scratch |
| Partial range coverage | Fetch missing expected sessions/bar labels, then fall through for the remainder |

**No silent failures.** All errors are logged with provider name, ticker, timeframe, and range. The caller gets `None` (not an exception) so they can decide how to handle — skip the ticker, use fallback data, or raise.

---

## 9. TTL Implementation Details

### 9.1 Staleness Timeline

```
Intraday (1min):
  TODAY: write ─── 2hr fresh ─── stale → re-fetch on next read
  PAST:  write ─── forever fresh (immutable)

Daily (1day):
  LAST 3 DAYS: write ─── 24hr fresh ─── stale → re-fetch on next read
  OLDER:       write ─── forever fresh (immutable)
```

### 9.2 Implementation Note

All TTL / freshness logic lives in `ttl.py` (see section 3.5). `fetcher.py` calls `ttl.is_stale()` — do not duplicate freshness logic in `fetcher.py`.

The cache check in `fetcher.py` looks like:

```python
# In fetcher.py
def _get_cached_data(
    ticker: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
    adjustment: str,
    tz: str,
) -> pd.DataFrame | None:
    """
    Returns cached DataFrame if fresh and covering the expected market bars.
    Returns None if cache is stale, missing, or has internal coverage gaps.
    """
    # Identify partition files relevant to the requested date/session range.
    partition_paths = storage.get_partition_paths(
        ticker, timeframe, start, end, session=session, adjustment=adjustment
    )
    if not partition_paths:
        return None
    if any(ttl.is_stale(ticker, timeframe, p) for p in partition_paths):
        return None
    df = storage.read_bars(
        ticker,
        timeframe,
        start=start,
        end=end,
        session=session,
        adjustment=adjustment,
        tz=tz,
    )
    if df.empty:
        return None

    # Do not use min/max timestamp coverage. Market data is sparse by design:
    # weekends, holidays, early closes, and timeframe labels mean [start, end]
    # is not a continuous timestamp interval.
    gaps = calendar.coverage_gaps(
        df.index,
        timeframe=timeframe,
        start=start,
        end=end,
        session=session,
        negative_cache=metadata.get_negative_cache(ticker, timeframe, session, adjustment),
    )
    if gaps:
        return None
    return df
```

---

## 10. Dependencies

| Package | Required? | Use |
|---------|-----------|-----|
| `pandas` | Yes | DataFrame operations, existing project dependency |
| `pyarrow` | Yes | Parquet read/write via pandas |
| `pandas_market_calendars` or `exchange_calendars` | Yes | NYSE trading days, holidays, early closes |
| `filelock` | Yes | Cross-process dataset locks |
| `alpaca-py` | Optional | Alpaca provider (required for Tier 1) |
| `yfinance` | Optional | YFinance provider (required for Tier 3) |
| `numpy` | Yes | Existing project dependency |

DuckDB is **not** a required dependency. It's an optional companion for ad-hoc queries. The strategy_lab.marketdata package works with pure pandas + pyarrow + Parquet.

---

## 11. Performance Estimates

Based on published benchmarks (PBieda blog, quant-pipeline, ml4t-data):

| Operation | Current (SQLite/CSV) | Projected (Parquet) |
|-----------|---------------------|---------------------|
| Read 5yr daily AAPL | ~150ms (CSV) | ~50ms (Parquet) |
| Read 1yr 1min AAPL (250K rows) | ~2s (SQLite JSON blob) | ~200ms (Parquet w/partition pruning) |
| Fetch + cache 500 tickers daily | ~45s (Alpaca batch) | ~45s (same fetch, but Parquet write is faster than JSON blob insert) |
| Data directory size (135 CSVs) | 11 MB | ~1-2 MB (Parquet zstd) |
| Full 5yr SP500 daily universe | ~500 MB (CSV) | ~40-80 MB (Parquet) |

---

## 12. Open Questions / Future Work

1. **Corporate action metadata** — current decision is to preserve adjustment mode in the dataset key (`raw`, `split`, `all`). Future work: store split/dividend event metadata beside daily data so consumers can audit why adjusted series changed.
2. **Delisted tickers** — tickers that have been delisted or renamed. Parquet files remain on disk but the metadata manifest excludes them from listings. Cleanup via `strategy_lab.marketdata prune --delisted` command.
3. **Evening fetch cron** — a cron job at 6PM ET to update today's data for all watched tickers. This ensures morning reads are always cached.
4. **Delta vs full partition writes** — currently the spec writes full partition files on update. For large partitions (1min with months), incremental delta writes could be faster. Investigate Parquet row group appends.
5. **DuckDB auto-register** — optional: on first import, auto-create DuckDB views over the Parquet directory for SQL access.
