"""Configuration constants, enums, and path resolution."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

# ── Data directory ────────────────────────────────────────────────────────────
# Default: sibling directory named "data"
# Override via env STRATEGY_LAB_MARKETDATA_DIR.
# STOCKMARKETDATA_DIR is accepted as a legacy fallback for existing shells.
_DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR = Path(
    os.getenv("STRATEGY_LAB_MARKETDATA_DIR")
    or os.getenv("STOCKMARKETDATA_DIR")
    or str(_DATA_DIR)
)

# ── Timeframes ────────────────────────────────────────────────────────────────


class Timeframe(Enum):
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    DAY = "1day"

    @property
    def partition_granularity(self) -> str:
        mapping = {
            "1min": "month",
            "5min": "month",
            "15min": "year",
            "1day": "year",
        }
        return mapping[self.value]

    @property
    def lookback_days_default(self) -> int:
        mapping = {
            "1min": 5,
            "5min": 30,
            "15min": 60,
            "1day": 1000,
        }
        return mapping[self.value]

    def __str__(self) -> str:
        return self.value


# ── Session ───────────────────────────────────────────────────────────────────


class Session(Enum):
    RTH = "rth"
    EXTENDED = "extended"


# ── Adjustment ────────────────────────────────────────────────────────────────


class Adjustment(Enum):
    RAW = "raw"
    SPLIT = "split"
    ALL = "all"


# ── Supported values ──────────────────────────────────────────────────────────

SUPPORTED_TIMEFRAMES = {t.value for t in Timeframe}
SUPPORTED_SESSIONS = {s.value for s in Session}
SUPPORTED_ADJUSTMENTS = {a.value for a in Adjustment}

# ── Internal helper ───────────────────────────────────────────────────────────


def resolve_dataset_dir(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
) -> Path:
    """Return the dataset directory for a (ticker, timeframe, session, adjustment).

    e.g. data/1min/AAPL/session=rth/adjustment=raw/
    """
    return (
        DATA_DIR
        / timeframe
        / ticker.upper()
        / f"session={session}"
        / f"adjustment={adjustment}"
    )


def resolve_meta_path(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
) -> Path:
    """Return the path to the meta.json sidecar for a dataset key."""
    return resolve_dataset_dir(ticker, timeframe, session, adjustment) / "meta.json"


def dataset_key(ticker: str, timeframe: str, session: str, adjustment: str) -> str:
    """Canonical string key for lock / metadata indexing."""
    return f"{ticker.upper()}:{timeframe}:{session}:{adjustment}"


def safe_filename_key(key: str) -> str:
    """Filesystem-safe version of a dataset key (for lock files)."""
    return key.replace(":", "_").replace("/", "_")


# ── Cache & Coverage Completeness Tolerances ──────────────────────────────────
COMPLETENESS_TOLERANCE_1MIN_RTH = 0.13
COMPLETENESS_TOLERANCE_DEFAULT = 0.05

