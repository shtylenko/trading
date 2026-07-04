"""Thread-level and cross-process file locks for dataset-level concurrency.

Uses per-dataset-key threading.Lock for in-process threads, and
``filelock.FileLock`` for cross-process safety when multiple Python
processes access the same Parquet partition sidecar.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock as _FileLock

from . import config
from .config import dataset_key, safe_filename_key

# ── Thread locks (in-process) ─────────────────────────────────────────────────

# WARNING: _thread_locks grows unboundedly as new (ticker, timeframe, session, adjustment)
# combinations are queried, because locks are never removed once created.
# While safe and negligible in memory footprint for typical backtests (e.g. thousands of
# combinations consume less than a few megabytes), this could act as a slow memory leak
# in a long-running production service processing millions of dynamic keys.
_thread_locks: dict[str, threading.Lock] = {}
_thread_locks_lock = threading.Lock()



def _get_thread_lock(key: str) -> threading.Lock:
    with _thread_locks_lock:
        if key not in _thread_locks:
            _thread_locks[key] = threading.Lock()
        return _thread_locks[key]


def _locks_dir() -> Path:
    """Return the lock directory, creating it if needed.

    Uses DATA_DIR dynamically so it picks up the env-var override
    even after module import.
    """
    d = config.DATA_DIR / ".locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def dataset_lock(ticker: str, timeframe: str, session: str, adjustment: str):
    """Acquire both an in-process threading.Lock and a cross-process FileLock.

    Lock scope: the entire fetch → cache-check → write cycle for a
    (ticker, timeframe, session, adjustment) dataset.  Multiple workers
    requesting the same dataset block; different datasets run in parallel.

    Marker files are intentionally left in place after release: deleting
    them races with concurrent acquirers (filelock opens/stats the path it
    locked, and a vanished file raises FileNotFoundError mid-acquire).
    They are zero-byte and bounded by the number of dataset keys.
    """
    key = dataset_key(ticker, timeframe, session, adjustment)
    safe = safe_filename_key(key)
    lock_file = _locks_dir() / f"{safe}.lock"

    thread_lock = _get_thread_lock(key)
    # 5 minute acquire timeout. NOTE: this is shorter than the retry
    # wrapper's 15-minute connection-retry budget — safe only because
    # provider HTTP fetches happen OUTSIDE this lock (the fetcher locks
    # around cache reads/writes, not around network calls). Don't move
    # network requests under dataset_lock.
    file_lock = _FileLock(str(lock_file), timeout=300)

    thread_lock.acquire()
    try:
        with file_lock:
            yield
    finally:
        thread_lock.release()
