"""Seed detectors for the extensible candlebar library.

These are geometry-only observations.  They do not inspect future bars and do
not use VWAP, volume, or account state; those belong to Warrior's later decision
layer.  This prevents a chart shape from accidentally becoming a trade by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .types import CandlePattern, Direction, PatternEvent


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _event(
    bars: pd.DataFrame,
    *,
    pattern: str,
    direction: Direction,
    index: int,
    score: float,
    evidence: dict,
) -> PatternEvent:
    return PatternEvent(
        pattern=pattern,
        direction=direction,
        index=index,
        timestamp=pd.Timestamp(bars.index[index]),
        score=round(_clamp(score), 6),
        evidence=evidence,
    )


@dataclass(frozen=True)
class CandleOverCandle(CandlePattern):
    """Bullish bar that closes through the prior bar's high."""

    min_close_location: float = 0.65
    min_body_ratio: float = 0.25
    name: str = "candle_over_candle"

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        events: list[PatternEvent] = []
        for i in range(1, len(bars)):
            prior = bars.iloc[i - 1]
            row = bars.iloc[i]
            prior_high = float(prior["high"])
            close = float(row["close"])
            if not (
                bool(row["cb_green"])
                and float(row["high"]) > prior_high
                and close >= prior_high
                and float(row["cb_close_location"]) >= self.min_close_location
                and float(row["cb_body_ratio"]) >= self.min_body_ratio
            ):
                continue
            break_distance = max(0.0, close - prior_high)
            score = 0.45 + 0.30 * float(row["cb_close_location"]) + 0.25 * min(
                1.0, break_distance / max(float(row["cb_range"]), 1e-12)
            )
            events.append(
                _event(
                    bars,
                    pattern=self.name,
                    direction="bullish",
                    index=i,
                    score=score,
                    evidence={
                        "prior_high": round(prior_high, 6),
                        "break_distance": round(break_distance, 6),
                        "close_location": round(float(row["cb_close_location"]), 4),
                        "body_ratio": round(float(row["cb_body_ratio"]), 4),
                    },
                )
            )
        return events


@dataclass(frozen=True)
class MicroPullbackBreak(CandlePattern):
    """One-to-three bar pullback followed by a green break of its high."""

    min_pullback_bars: int = 1
    max_pullback_bars: int = 3
    max_retrace_of_impulse: float = 0.65
    name: str = "micro_pullback_break"

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        events: list[PatternEvent] = []
        for i in range(2, len(bars)):
            current = bars.iloc[i]
            if not bool(current["cb_green"]):
                continue
            # Prefer the longer, more mature pause if multiple definitions fit
            # the same breakout bar; emit one event per bar/pattern.
            for pullback_bars in range(self.max_pullback_bars, self.min_pullback_bars - 1, -1):
                impulse_i = i - pullback_bars - 1
                if impulse_i < 0:
                    continue
                impulse = bars.iloc[impulse_i]
                pullback = bars.iloc[impulse_i + 1 : i]
                if len(pullback) != pullback_bars or not bool(impulse["cb_green"]):
                    continue

                impulse_high = float(impulse["high"])
                impulse_low = float(impulse["low"])
                pullback_high = float(pullback["high"].max())
                pullback_low = float(pullback["low"].min())
                impulse_range = max(impulse_high - impulse_low, 1e-12)
                retrace = max(0.0, impulse_high - pullback_low) / impulse_range
                if (
                    pullback_high > impulse_high
                    or retrace > self.max_retrace_of_impulse
                    or float(current["high"]) <= pullback_high
                    or float(current["close"]) < pullback_high
                ):
                    continue

                score = (
                    0.40
                    + 0.25 * (1.0 - retrace / self.max_retrace_of_impulse)
                    + 0.20 * float(current["cb_close_location"])
                    + 0.15 * float(current["cb_body_ratio"])
                )
                events.append(
                    _event(
                        bars,
                        pattern=self.name,
                        direction="bullish",
                        index=i,
                        score=score,
                        evidence={
                            "pullback_bars": pullback_bars,
                            "impulse_high": round(impulse_high, 6),
                            "pullback_high": round(pullback_high, 6),
                            "pullback_low": round(pullback_low, 6),
                            "retrace_of_impulse": round(retrace, 4),
                        },
                    )
                )
                break
        return events


@dataclass(frozen=True)
class BullFlagBreak(CandlePattern):
    """Short bullish impulse, contracting flag, then a green flag-high break."""

    impulse_bars: int = 3
    pullback_bars: int = 2
    min_green_fraction: float = 2 / 3
    max_retrace_of_impulse: float = 0.70
    name: str = "bull_flag_break"

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        events: list[PatternEvent] = []
        need = self.impulse_bars + self.pullback_bars + 1
        for i in range(need - 1, len(bars)):
            impulse_start = i - self.pullback_bars - self.impulse_bars
            impulse = bars.iloc[impulse_start : impulse_start + self.impulse_bars]
            pullback = bars.iloc[impulse_start + self.impulse_bars : i]
            current = bars.iloc[i]

            impulse_high = float(impulse["high"].max())
            impulse_low = float(impulse["low"].min())
            impulse_range = max(impulse_high - impulse_low, 1e-12)
            impulse_gain = float(impulse["close"].iloc[-1] - impulse["open"].iloc[0])
            avg_impulse_range = max(float(impulse["cb_range"].mean()), 1e-12)
            pullback_high = float(pullback["high"].max())
            pullback_low = float(pullback["low"].min())
            retrace = max(0.0, impulse_high - pullback_low) / impulse_range
            green_fraction = float(impulse["cb_green"].mean())

            if (
                green_fraction < self.min_green_fraction
                or impulse_gain < 1.5 * avg_impulse_range
                or pullback_high > impulse_high
                or retrace > self.max_retrace_of_impulse
                or not bool(current["cb_green"])
                or float(current["high"]) <= pullback_high
                or float(current["close"]) < pullback_high
            ):
                continue

            volume_ratio = None
            if "volume" in bars.columns:
                impulse_volume = float(impulse["volume"].mean())
                pullback_volume = float(pullback["volume"].mean())
                if impulse_volume > 0:
                    volume_ratio = pullback_volume / impulse_volume

            score = (
                0.35
                + 0.20 * green_fraction
                + 0.20 * min(1.0, impulse_gain / (3.0 * avg_impulse_range))
                + 0.15 * (1.0 - retrace / self.max_retrace_of_impulse)
                + 0.10 * float(current["cb_close_location"])
            )
            if volume_ratio is not None and volume_ratio <= 1.0:
                score += 0.05 * (1.0 - volume_ratio)

            events.append(
                _event(
                    bars,
                    pattern=self.name,
                    direction="bullish",
                    index=i,
                    score=score,
                    evidence={
                        "impulse_bars": self.impulse_bars,
                        "pullback_bars": self.pullback_bars,
                        "impulse_gain": round(impulse_gain, 6),
                        "pullback_high": round(pullback_high, 6),
                        "retrace_of_impulse": round(retrace, 4),
                        "pullback_to_impulse_volume": (
                            round(volume_ratio, 4) if volume_ratio is not None else None
                        ),
                    },
                )
            )
        return events


@dataclass(frozen=True)
class BearishToppingTail(CandlePattern):
    """Upper-wick rejection at or above a recent high."""

    lookback_bars: int = 3
    min_upper_wick_ratio: float = 0.45
    max_close_location: float = 0.55
    name: str = "bearish_topping_tail"

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        events: list[PatternEvent] = []
        for i in range(self.lookback_bars, len(bars)):
            row = bars.iloc[i]
            prior_high = float(bars["high"].iloc[i - self.lookback_bars : i].max())
            wick_ratio = float(row["cb_upper_wick_ratio"])
            close_location = float(row["cb_close_location"])
            if (
                float(row["high"]) < prior_high
                or wick_ratio < self.min_upper_wick_ratio
                or close_location > self.max_close_location
            ):
                continue
            score = 0.40 + 0.40 * wick_ratio + 0.20 * (1.0 - close_location)
            events.append(
                _event(
                    bars,
                    pattern=self.name,
                    direction="bearish",
                    index=i,
                    score=score,
                    evidence={
                        "prior_high": round(prior_high, 6),
                        "upper_wick_ratio": round(wick_ratio, 4),
                        "close_location": round(close_location, 4),
                    },
                )
            )
        return events


@dataclass(frozen=True)
class BearishBreakoutFailure(CandlePattern):
    """Pierces a recent high but closes back below that breakout level."""

    lookback_bars: int = 3
    name: str = "bearish_breakout_failure"

    def detect(self, bars: pd.DataFrame) -> list[PatternEvent]:
        events: list[PatternEvent] = []
        for i in range(self.lookback_bars, len(bars)):
            row = bars.iloc[i]
            prior_high = float(bars["high"].iloc[i - self.lookback_bars : i].max())
            high = float(row["high"])
            close = float(row["close"])
            if high <= prior_high or close >= prior_high:
                continue
            failure_depth = (prior_high - close) / max(float(row["cb_range"]), 1e-12)
            score = 0.55 + 0.25 * min(1.0, failure_depth) + 0.20 * float(
                row["cb_upper_wick_ratio"]
            )
            events.append(
                _event(
                    bars,
                    pattern=self.name,
                    direction="bearish",
                    index=i,
                    score=score,
                    evidence={
                        "prior_high": round(prior_high, 6),
                        "failure_depth_of_bar": round(failure_depth, 4),
                        "upper_wick_ratio": round(float(row["cb_upper_wick_ratio"]), 4),
                    },
                )
            )
        return events


def builtin_detectors() -> Iterable[CandlePattern]:
    """Return the small, deliberately conservative seed detector set."""
    return (
        CandleOverCandle(),
        MicroPullbackBreak(),
        BullFlagBreak(),
        BearishToppingTail(),
        BearishBreakoutFailure(),
    )

