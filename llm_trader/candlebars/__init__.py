"""Extensible deterministic detection of OHLCV candlebar patterns.

The package is intentionally observation-only.  It returns pattern events and
geometry quality so Warrior can later decide how, or whether, to use them.
"""

from .detectors import (
    BearishBreakoutFailure,
    BearishToppingTail,
    BullFlagBreak,
    CandleOverCandle,
    MicroPullbackBreak,
)
from .registry import PatternRegistry, default_registry, detect_patterns
from .types import CandlePattern, PatternEvent

__all__ = [
    "BearishBreakoutFailure",
    "BearishToppingTail",
    "BullFlagBreak",
    "CandleOverCandle",
    "CandlePattern",
    "MicroPullbackBreak",
    "PatternEvent",
    "PatternRegistry",
    "default_registry",
    "detect_patterns",
]
