"""Tests for the extensible, causal candlebar detector library."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading.llm_trader.candlebars import PatternEvent, PatternRegistry, detect_patterns
from trading.llm_trader.candlebars.features import candle_features


def _frame(rows: list[tuple[float, float, float, float, int]]) -> pd.DataFrame:
    idx = pd.date_range("2025-03-10 09:30", periods=len(rows), freq="min", tz="America/New_York")
    return pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close", "volume"],
        index=idx,
    )


def test_candle_features_are_safe_for_zero_range_bars():
    bars = _frame([(10.0, 10.0, 10.0, 10.0, 100)])
    features = candle_features(bars)
    assert features.iloc[0]["cb_body_ratio"] == 0.0
    assert features.iloc[0]["cb_close_location"] == 0.5


def test_candle_over_candle_detects_clean_prior_high_break():
    bars = _frame(
        [
            (10.0, 10.20, 9.95, 10.10, 100),
            (10.08, 10.55, 10.05, 10.50, 200),
        ]
    )
    events = [event for event in detect_patterns(bars) if event.pattern == "candle_over_candle"]
    assert len(events) == 1
    assert events[0].index == 1
    assert events[0].direction == "bullish"
    assert events[0].evidence["prior_high"] == 10.2


def test_micro_pullback_break_uses_only_preceding_impulse_and_pullback():
    bars = _frame(
        [
            (10.00, 10.10, 9.95, 10.05, 100),
            (10.05, 10.70, 10.00, 10.62, 300),  # impulse
            (10.62, 10.64, 10.42, 10.48, 120),  # pullback
            (10.48, 10.50, 10.36, 10.42, 100),  # pullback
            (10.43, 10.82, 10.40, 10.78, 260),  # green break
        ]
    )
    events = [event for event in detect_patterns(bars) if event.pattern == "micro_pullback_break"]
    assert len(events) == 1
    assert events[0].index == 4
    assert events[0].evidence["pullback_bars"] == 2

    # The event must also be discoverable without future bars being present.
    prefix_events = [
        event for event in detect_patterns(bars.iloc[:5]) if event.pattern == "micro_pullback_break"
    ]
    assert prefix_events == events


def test_bull_flag_break_detects_impulse_pause_and_break():
    bars = _frame(
        [
            (10.00, 10.40, 9.95, 10.35, 100),
            (10.35, 10.80, 10.30, 10.75, 180),
            (10.75, 11.20, 10.70, 11.15, 220),
            (11.12, 11.16, 10.95, 11.00, 90),
            (11.00, 11.08, 10.88, 10.94, 80),
            (10.96, 11.38, 10.92, 11.32, 240),
        ]
    )
    events = [event for event in detect_patterns(bars) if event.pattern == "bull_flag_break"]
    assert len(events) == 1
    assert events[0].index == 5
    assert events[0].evidence["pullback_bars"] == 2


def test_bearish_rejection_patterns_detect_failed_high_break():
    bars = _frame(
        [
            (10.0, 10.2, 9.9, 10.1, 100),
            (10.1, 10.3, 10.0, 10.2, 100),
            (10.2, 10.4, 10.1, 10.3, 100),
            (10.3, 10.8, 10.2, 10.25, 200),
        ]
    )
    names = {event.pattern for event in detect_patterns(bars) if event.index == 3}
    assert "bearish_topping_tail" in names
    assert "bearish_breakout_failure" in names


def test_registry_accepts_future_custom_pattern():
    @dataclass(frozen=True)
    class AlwaysLast:
        name: str = "always_last"

        def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
            i = len(bars) - 1
            return [
                PatternEvent(
                    pattern=self.name,
                    direction="neutral",
                    index=i,
                    timestamp=pd.Timestamp(bars.index[i]),
                    score=0.5,
                    evidence={"custom": True},
                )
            ]

    registry = PatternRegistry()
    registry.register(AlwaysLast())
    events = registry.detect(_frame([(10.0, 10.1, 9.9, 10.0, 100)]))
    assert [event.pattern for event in events] == ["always_last"]
