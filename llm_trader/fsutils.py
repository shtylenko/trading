"""Small filesystem primitives used by the local trading tools.

These helpers keep state-file writes atomic and provide advisory locks for the
session folders. They deliberately stay dependency-free so CLI tools can use
them in fresh subprocesses.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fcntl

_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def file_lock(path: str | Path) -> Iterator[None]:
    """Exclusive advisory lock on ``path``.

    The lock file is created if needed. All cooperating processes must acquire
    the same lock around read-modify-write sequences.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    thread_lock = _thread_lock_for(p)
    with thread_lock:
        with open(p, "a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: str | Path, text: str) -> None:
    """Write text via a same-directory temp file and atomic replace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write bytes via a same-directory temp file and atomic replace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(
    path: str | Path,
    obj,
    *,
    indent: int | None = None,
    sort_keys: bool = False,
) -> None:
    text = json.dumps(obj, indent=indent, sort_keys=sort_keys)
    if indent is not None:
        text += "\n"
    atomic_write_text(path, text)
