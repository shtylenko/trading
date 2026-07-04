"""Unit tests for trading.marketdata.locks."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from trading.marketdata.locks import dataset_lock, _get_thread_lock


class TestDatasetLock:
    def test_acquire_release(self):
        """Lock can be acquired and released."""
        with dataset_lock("AAPL", "1min", "rth", "raw"):
            pass  # Should not block

    def test_multiple_keys_in_parallel(self):
        """Different dataset keys can be locked concurrently."""
        results: list[str] = []

        def worker(key_suffix: str):
            with dataset_lock("TICK", "1min", "rth", key_suffix):
                results.append(key_suffix)
                time.sleep(0.05)

        t1 = threading.Thread(target=worker, args=("raw",))
        t2 = threading.Thread(target=worker, args=("split",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(results) == 2
        assert "raw" in results
        assert "split" in results

    def test_same_key_serializes(self):
        """Same dataset key blocks — only one worker at a time."""
        order: list[int] = []

        def worker(idx: int):
            with dataset_lock("AAPL", "1min", "rth", "raw"):
                order.append(idx)
                time.sleep(0.1)

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        time.sleep(0.02)  # ensure t1 acquires first
        t2.start()
        t1.join()
        t2.join()
        assert order == [1, 2]  # t1 entered before t2

    def test_lock_file_created(self):
        """FileLock creates a lock file in data/.locks/."""
        # Reimport locks so it picks up the current DATA_DIR
        import importlib
        import trading.marketdata.locks as locks_mod
        importlib.reload(locks_mod)

        lock_dir = locks_mod._locks_dir()
        # Ensure cleared
        import shutil
        if lock_dir.exists():
            shutil.rmtree(lock_dir)

        with locks_mod.dataset_lock("TEST", "1day", "rth", "split"):
            lock_files = list(lock_dir.glob("*.lock"))
            assert len(lock_files) >= 1

    def test_thread_lock_reuse(self):
        """Same key returns same threading.Lock."""
        lock1 = _get_thread_lock("MSFT:1day:rth:split")
        lock2 = _get_thread_lock("MSFT:1day:rth:split")
        assert lock1 is lock2  # Same object (singleton per key)
