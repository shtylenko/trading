"""Pattern registry and single-pass public detection API."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .detectors import builtin_detectors
from .features import candle_features
from .types import CandlePattern, PatternEvent


class PatternRegistry:
    """Named detector collection that makes adding future patterns explicit."""

    def __init__(self, detectors: Iterable[CandlePattern] = ()) -> None:
        self._detectors: dict[str, CandlePattern] = {}
        for detector in detectors:
            self.register(detector)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._detectors)

    def register(self, detector: CandlePattern, *, replace: bool = False) -> None:
        name = getattr(detector, "name", "")
        if not isinstance(name, str) or not name:
            raise ValueError("detector must have a non-empty string name")
        if name in self._detectors and not replace:
            raise ValueError(f"detector already registered: {name}")
        self._detectors[name] = detector

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        """Run every registered detector over one OHLCV frame.

        Candle features are calculated once.  Sorting includes detector name so
        a replay result remains stable when multiple patterns fire on one bar.
        """
        enriched = candle_features(bars)
        events = [event for detector in self._detectors.values() for event in detector.detect(enriched)]
        return sorted(events, key=lambda event: (event.index, event.pattern))


def default_registry() -> PatternRegistry:
    """Return a fresh registry containing the supported seed patterns."""
    return PatternRegistry(builtin_detectors())


def detect_patterns(bars: pd.DataFrame) -> list[PatternEvent]:
    """Convenience API for callers that need the default detector set."""
    return default_registry().detect(bars)

