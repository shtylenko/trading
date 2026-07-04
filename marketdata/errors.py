"""Domain exceptions for the strategy_lab.marketdata package."""


class StockMarketDataError(Exception):
    """Base exception for all strategy_lab.marketdata errors."""


class ProviderError(StockMarketDataError):
    """A provider failed to return data (auth, rate limit, server error)."""


class ConnectionTimeoutError(ProviderError):
    """Connection retries exhausted — the network/provider is unreachable.

    Raised by ``retry.retry_on_connection_error`` after its retry budget is
    spent.  Callers abort the current fetch instead of falling through to
    other providers (the network is down for them too).
    """


class PartialDataError(ProviderError):
    """A provider returned data for part of the range and errored on the rest.

    ``df`` carries the successfully fetched bars so the caller can store
    them, while still treating the provider as errored — the missing dates
    must not be negative-cached as "confirmed empty".
    """

    def __init__(self, message: str, df=None):
        super().__init__(message)
        self.df = df


class EmptyDataError(StockMarketDataError):
    """A provider returned no data for the requested range."""


class AuthError(ProviderError):
    """Missing or invalid API credentials for a provider."""


class RateLimitError(ProviderError):
    """Provider rate limit exceeded."""


class CalendarError(StockMarketDataError):
    """Trading calendar look-up or computation error."""


class StorageError(StockMarketDataError):
    """Parquet read/write or filesystem error."""


class CorruptDataError(StorageError):
    """Cached data is corrupt and needs re-fetch."""
