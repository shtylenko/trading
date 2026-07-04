"""strategy_lab.marketdata — unified market data processor.

Single source of truth for all OHLCV stock market data in the
trading_strategy_finder project.  Handles:

- Hive-partitioned Parquet storage (per ticker / timeframe / session / adjustment)
- Automatic provider routing (Alpaca → MarketData → YFinance)
- Calendar-aware coverage validation
- Thread- and process-safe dataset-level locking
- TTL-based cache freshness with negative cache for non-trading dates

Usage
-----
    from trading.marketdata import fetch_bars, Timeframe

    # Fetch daily split-adjusted bars for AAPL (caches to Parquet)
    df = fetch_bars("AAPL", "1day", start=..., end=..., adjustment="split")

    # Fetch 1-minute raw intraday bars
    df = fetch_bars("AAPL", "1min", start=..., end=..., session="rth", adjustment="raw")
"""

from .config import DATA_DIR, Adjustment, Session, Timeframe
from .fetcher import fetch_bars

# Activate daily file logging for the strategy_lab.marketdata package.
# All WARNING+ messages during market data operations are written to
# logs/<YYYY-MM-DD>.log — rate limits, provider failures, auth errors.
from . import logging_config  # noqa: F401  (side-effect: install handlers)

from .provider import register_provider, get_providers_for_timeframe
from .retry import CircuitBreaker
from .storage import (
    get_partition_paths,
    read_bars,
    read_meta,
    update_meta_summary,
    write_bars,
)

__all__ = [
    "CircuitBreaker",
    "DATA_DIR",
    "Adjustment",
    "Session",
    "Timeframe",
    "fetch_bars",
    "get_partition_paths",
    "get_providers_for_timeframe",
    "read_bars",
    "read_meta",
    "register_provider",
    "update_meta_summary",
    "write_bars",
]
