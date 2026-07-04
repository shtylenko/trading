import socket
import urllib.error
import pytest
from unittest.mock import Mock

from trading.marketdata.errors import ProviderError
from trading.marketdata.retry import is_connection_error, retry_on_connection_error


def test_is_connection_error():
    assert is_connection_error(socket.timeout("timeout")) is True
    assert is_connection_error(ConnectionAbortedError("aborted")) is True
    assert is_connection_error(urllib.error.URLError("url error")) is True
    
    # HTTPError should NOT be recognized as connection error
    http_err = urllib.error.HTTPError("http://example.com", 403, "Forbidden", {}, None)
    assert is_connection_error(http_err) is False

    # Check requests/urllib3 mock exception names
    class MockConnectionError(Exception):
        pass
    assert is_connection_error(MockConnectionError("connection issue")) is True

    class MockNameResolutionError(Exception):
        pass
    assert is_connection_error(MockNameResolutionError("resolution failed")) is True

    # String check
    assert is_connection_error(Exception("Failed to resolve host")) is True
    assert is_connection_error(Exception("nodename nor servname provided")) is True
    
    # Standard ValueError should not be connection error
    assert is_connection_error(ValueError("Invalid argument")) is False


def test_retry_success_immediately():
    func = Mock(return_value="success")
    result = retry_on_connection_error(func)
    assert result == "success"
    assert func.call_count == 1


def test_retry_recovery():
    # Fails twice with socket.timeout, then succeeds on the 3rd attempt
    func = Mock(side_effect=[socket.timeout("timed out"), socket.timeout("timed out"), "success"])
    
    result = retry_on_connection_error(
        func,
        timeout_minutes=1.0,
        initial_backoff=0.01,
        max_backoff=0.1,
    )
    assert result == "success"
    assert func.call_count == 3


def test_retry_timeout_exceeded():
    # Keep failing with connection errors until timeout is reached
    func = Mock(side_effect=lambda: raise_error(socket.timeout("timed out")))
    
    def raise_error(err):
        raise err

    with pytest.raises(ProviderError) as exc_info:
        # Use a tiny timeout of 0.0001 minutes (~6 milliseconds) to fail fast
        retry_on_connection_error(
            func,
            timeout_minutes=0.0001,
            initial_backoff=0.001,
            max_backoff=0.005,
        )
    
    assert "Connection timeout" in str(exc_info.value)
    assert func.call_count >= 1


def test_no_retry_for_non_connection_error():
    # Immediate failure on ValueError
    func = Mock(side_effect=ValueError("bad data"))
    
    with pytest.raises(ValueError) as exc_info:
        retry_on_connection_error(func, timeout_minutes=1.0, initial_backoff=0.01)
        
    assert "bad data" in str(exc_info.value)
    assert func.call_count == 1


def test_circuit_breaker_open_raises_connection_timeout():
    from trading.marketdata.errors import ConnectionTimeoutError
    from trading.marketdata.retry import CircuitBreaker, retry_on_connection_error

    br = CircuitBreaker("test", failure_threshold=2, window_seconds=300.0)
    br.record_failure()
    br.record_failure()
    assert not br.allow()

    import pytest
    with pytest.raises(ConnectionTimeoutError, match="Connection timeout"):
        retry_on_connection_error(lambda: 1, circuit_breaker=br)
