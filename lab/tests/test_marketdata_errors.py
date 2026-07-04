"""Unit tests for trading.marketdata.errors."""

from trading.marketdata.errors import (
    AuthError,
    CalendarError,
    CorruptDataError,
    EmptyDataError,
    ProviderError,
    RateLimitError,
    StockMarketDataError,
    StorageError,
)


def test_inheritance():
    """All exceptions inherit from StockMarketDataError."""
    assert issubclass(ProviderError, StockMarketDataError)
    assert issubclass(EmptyDataError, StockMarketDataError)
    assert issubclass(AuthError, ProviderError)
    assert issubclass(RateLimitError, ProviderError)
    assert issubclass(CalendarError, StockMarketDataError)
    assert issubclass(StorageError, StockMarketDataError)
    assert issubclass(CorruptDataError, StorageError)


def test_can_raise_and_catch():
    try:
        raise AuthError("bad key")
    except ProviderError:
        pass  # Caught by parent

    try:
        raise CorruptDataError("parquet broken")
    except StorageError:
        pass  # Caught by parent
