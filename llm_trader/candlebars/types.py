"""Common types for deterministic candlestick-pattern detection.

The library deliberately operates on completed OHLCV bars only.  A pattern event
is therefore reproducible from the frame prefix that ends at its timestamp, which
makes it safe to reuse in replay, shadow trading, and later decision scoring.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

import pandas as pd


Direction = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True)
class PatternEvent:
    """One pattern detected on the current completed bar.

    ``score`` is pattern geometry quality in the unit interval, **not** a trade
    probability or a trading instruction.  The future Warrior decision engine
    can combine this evidence with VWAP, volume, risk, and market-context rules.
    """

    pattern: str
    direction: Direction
    index: int
    timestamp: pd.Timestamp
    score: float
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pattern:
            raise ValueError("pattern must be non-empty")
        if self.index < 0:
            raise ValueError("index must be non-negative")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be in [0, 1]")
        # Do not allow a caller to mutate the evidence after an event has been
        # recorded; persisted evidence must remain an audit artifact.
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


class CandlePattern(ABC):
    """Extension point for one causal candlebar detector.

    ``bars`` has the original OHLCV columns plus the ``cb_*`` feature columns
    produced by :func:`trading.llm_trader.candlebars.features.candle_features`.
    Implementations must only inspect rows up to an emitted event's ``index``.
    """

    name: str

    @abstractmethod
    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        """Return every event found in chronological order."""

