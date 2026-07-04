"""Retry logic for handling internet connection timeouts and failures."""

from __future__ import annotations

import logging
import socket
import time
import urllib.error
from typing import Callable, TypeVar

from .errors import ConnectionTimeoutError, ProviderError

logger = logging.getLogger("strategy_lab.marketdata.retry")

T = TypeVar("T")


def is_connection_error(e: Exception) -> bool:
    """Return True if the exception is due to network connection/timeout issues."""
    if isinstance(e, urllib.error.HTTPError):
        return False
    if isinstance(e, (ConnectionError, TimeoutError, socket.timeout, socket.gaierror)):
        return True
    if isinstance(e, urllib.error.URLError):
        return True

    cls_name = e.__class__.__name__
    cls_module = e.__class__.__module__ or ""

    connection_keywords = {"connection", "timeout", "nameresolution", "gaierror", "host", "dns", "unreachable"}

    if any(kw in cls_name.lower() or kw in cls_module.lower() for kw in connection_keywords):
        return True

    err_str = str(e).lower()
    if "nodename nor servname provided" in err_str:
        return True
    if "failed to resolve" in err_str:
        return True
    if "name resolution" in err_str:
        return True
    if "connection timed out" in err_str:
        return True

    return False


def retry_on_connection_error(
    func: Callable[[], T],
    timeout_minutes: float | None = None,
    initial_backoff: float = 5.0,
    max_backoff: float = 60.0,
    circuit_breaker: "CircuitBreaker | None" = None,
) -> T:
    """Execute func, retrying connection-related errors.

    Parameters
    ----------
    timeout_minutes : float or None
        Max minutes to retry before raising ProviderError.
        None -> defaults to 15 min. Pass 0 for no retries (fail-fast).
    initial_backoff : float
        Seconds to wait before first retry.
    max_backoff : float
        Maximum seconds between retries (exponential backoff caps here).
    circuit_breaker : CircuitBreaker or None
        Shared per-provider breaker; short-circuits when open.
    """
    if timeout_minutes is None:
        timeout_minutes = 15.0
    if timeout_minutes <= 0:
        return func()

    if circuit_breaker is not None and not circuit_breaker.allow():
        # ConnectionTimeoutError (str contains "Connection timeout") so the
        # caller chain classifies this as a connection failure — the
        # pipeline re-queues the ticker for a retry round instead of
        # recording it as a permanent data failure.
        raise ConnectionTimeoutError(
            f"Connection timeout: circuit breaker open for {circuit_breaker.name} "
            f"({circuit_breaker.failure_count} failures in {circuit_breaker.window_seconds:.0f}s)"
        )

    start_time = time.time()
    backoff = initial_backoff
    attempt = 1

    while True:
        try:
            result = func()
            if circuit_breaker is not None:
                circuit_breaker.record_success()
            return result
        except Exception as e:
            if is_connection_error(e):
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                elapsed = (time.time() - start_time) / 60.0
                if elapsed >= timeout_minutes:
                    logger.error(
                        "Failed to connect to the internet after retrying for %.1f minutes. Error: %s",
                        elapsed,
                        e,
                    )
                    raise ConnectionTimeoutError(
                        f"Connection timeout: unable to connect to provider "
                        f"for {timeout_minutes:.0f}+ minutes. Error: {e}"
                    ) from e

                logger.warning(
                    "Network connection issue detected (%s). Retrying in %.1fs... (elapsed: %.1f minutes, attempt %d)",
                    e,
                    backoff,
                    elapsed,
                    attempt,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                attempt += 1
            else:
                raise e


# --- Circuit breaker ---------------------------------------------------------


class CircuitBreaker:
    """Simple count-based circuit breaker shared across provider calls.

    After *failure_threshold* failures within *window_seconds*, the breaker
    opens and ``allow()`` returns False until the window rolls forward.
    A single success resets all failures.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: float = 300.0,
    ):
        import threading

        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self._failures: list[float] = []
        self._lock = threading.Lock()

    def record_failure(self) -> None:
        now = time.time()
        with self._lock:
            self._failures.append(now)
            self._prune(now)

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()

    def allow(self) -> bool:
        with self._lock:
            self._prune(time.time())
            return len(self._failures) < self.failure_threshold

    @property
    def failure_count(self) -> int:
        with self._lock:
            self._prune(time.time())
            return len(self._failures)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self._failures = [t for t in self._failures if t > cutoff]
