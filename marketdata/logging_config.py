"""Daily rotating log file for the strategy_lab.marketdata package.

Every day at 00:00 ET a new log file is created at::

    logs/2026-03-02.log
    logs/2026-03-03.log
    ...

All INFO+ messages from the ``strategy_lab.marketdata`` package tree are
written to the daily file — every provider request, cache write,
warning, and error.  INFO+ messages also go to the console so
interactive users see progress without tailing the log.

The daily files are NOT rotated away — they accumulate indefinitely.
If disk space becomes a concern add a retention policy or cron job::

    find logs/ -name '*.log' -mtime +90 -delete
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import typing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_TZ_NY = ZoneInfo("America/New_York")

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


class _DailyFileHandler(logging.Handler):
    """Writes to ``logs/<YYYY-MM-DD>.log``, keeping the file handle open
    across emits.  Re-opens on the first write of a new day so processes
    that run across midnight switch files seamlessly.

    Keeping the handle open avoids ``OSError: [Errno 24] Too many open
    files`` during tight backtest sweeps that write thousands of log
    lines through rapid open/close cycles.
    """

    def __init__(self, level: int = logging.WARNING):
        super().__init__(level)
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._fh: typing.IO | None = None
        self._current_date: str | None = None

    def _ensure_open(self) -> typing.IO | None:
        # Day boundary in ET, matching the market-day semantics documented
        # in the module docstring (not the machine's local timezone).
        today = datetime.now(_TZ_NY).strftime("%Y-%m-%d")
        if self._current_date != today:
            # Close previous day's file
            self._close()
            path = _LOG_DIR / f"{today}.log"
            try:
                self._fh = open(path, "a")
                self._current_date = today
            except OSError:
                return None
        return self._fh

    def _close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
            self._current_date = None

    def emit(self, record: logging.LogRecord) -> None:
        fh = self._ensure_open()
        if fh is None:
            return
        try:
            fh.write(self.format(record) + "\n")
            fh.flush()
        except OSError:
            self.handleError(record)


# ── Install once at import time ───────────────────────────────────────────────

_installed = False


def install_logging() -> None:
    """Install the daily-file handler on the root strategy_lab.marketdata logger.

    Safe to call multiple times — only installs once.
    """
    global _installed
    if _installed:
        return

    logger = logging.getLogger("strategy_lab.marketdata")
    logger.setLevel(logging.DEBUG)  # Let handlers decide their level

    # Remove any pre-existing strategy_lab.marketdata handlers to avoid duplicates
    # on re-import.
    for h in list(logger.handlers):
        if isinstance(h, (_DailyFileHandler, logging.StreamHandler)):
            logger.removeHandler(h)

    # Daily file: INFO+
    file_handler = _DailyFileHandler(level=logging.INFO)
    logger.addHandler(file_handler)

    # Console: WARNING+ only (INFO goes to daily log file)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter(
        "%(levelname)s: %(message)s",
    ))
    logger.addHandler(console)

    # This logger has its own console handler — don't also propagate to the
    # root logger, or applications that configure root logging see every
    # warning twice.
    logger.propagate = False

    _installed = True


# Auto-install on import so any code that imports ``strategy_lab.marketdata``
# automatically gets the daily log without explicit setup.
install_logging()
