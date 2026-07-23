"""Deterministic Warrior pattern-confluence policy.

The candlebar library supplies causal geometry observations.  This module turns
those observations plus completed five-minute structure, volume, VWAP, EMA, and
MACD into reproducible entry/exit intents.  It never predicts from future bars
and never computes fills or share size; :mod:`llm_trader.execution` remains the
sole execution authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from ...execution import EXECUTION_MODEL, ExecutionConfig, ExecutionEngine


POLICY_ID = "warrior_pattern_score_v1"
DECISION_SOURCE = "deterministic_policy"
ENTRY_THRESHOLD = 75.0
EXIT_THRESHOLD = 50.0
ENTRY_CUTOFF = "11:00"
MANDATORY_FLAT_TIME = "15:55"
PATTERN_WEIGHTS = {
    "bull_flag_break": 30.0,
    "micro_pullback_break": 27.0,
    "candle_over_candle": 22.0,
}
BEARISH_PATTERNS = {
    "bearish_topping_tail",
    "bearish_breakout_failure",
}
ENTRY_BRACKET = {
    "scales": [
        {"r_multiple": 1.0, "fraction": 1.0 / 3.0},
        {"r_multiple": 2.0, "fraction": 1.0 / 3.0},
    ]
}
POLICY_SPEC = {
    "entry_threshold": ENTRY_THRESHOLD,
    "exit_threshold": EXIT_THRESHOLD,
    "entry_cutoff": ENTRY_CUTOFF,
    "mandatory_flat_time": MANDATORY_FLAT_TIME,
    "pattern_weights": PATTERN_WEIGHTS,
    "bearish_patterns": sorted(BEARISH_PATTERNS),
    "entry_bracket": ENTRY_BRACKET,
}
USES_SESSION_EXECUTION_CONFIG = True

_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


class PolicyError(ValueError):
    """The sealed stream or session cannot support this policy."""


@dataclass(frozen=True)
class PolicySettings:
    """Versioned, explicit tuning knobs for the common policy state machine.

    The default preserves the sealed v1 decision rules exactly.  New policy
    modules must pass their own immutable settings rather than mutating module
    globals, so a batch always carries an auditable parameter set.
    """

    entry_threshold: float = ENTRY_THRESHOLD
    exit_threshold: float = EXIT_THRESHOLD
    entry_cutoff: str = ENTRY_CUTOFF
    mandatory_flat_time: str = MANDATORY_FLAT_TIME
    policy_id: str = POLICY_ID
    scanner_event_required: bool = False
    scanner_event_immediate_confirmation: bool = False
    scanner_event_confirmation_bars: int = 5


DEFAULT_SETTINGS = PolicySettings()


def _number(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise PolicyError(f"{label} must be a finite number")
    return float(value)


def _optional_number(value: Any, label: str) -> float | None:
    return None if value is None else _number(value, label)


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _events(tick: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return validated current 1m + completed-5m pattern observations."""
    groups: list[Any] = [tick.get("candlebar_patterns", [])]
    bar5 = tick.get("bar5_complete")
    if isinstance(bar5, dict):
        groups.append(bar5.get("candlebar_patterns", []))

    events: list[dict[str, Any]] = []
    for group in groups:
        if group is None:
            continue
        if not isinstance(group, list):
            raise PolicyError("candlebar_patterns must be a list")
        for event in group:
            if not isinstance(event, dict):
                raise PolicyError("candlebar pattern event must be an object")
            pattern = event.get("pattern")
            direction = event.get("direction")
            score = _number(event.get("score"), "candlebar pattern score")
            if not isinstance(pattern, str) or not pattern:
                raise PolicyError("candlebar pattern name must be non-empty")
            if direction not in {"bullish", "bearish", "neutral"}:
                raise PolicyError("candlebar pattern direction is invalid")
            if not 0.0 <= score <= 1.0:
                raise PolicyError("candlebar pattern score must be in [0, 1]")
            events.append({**event, "score": score})
    return events


def _entry_assessment(
    tick: Mapping[str, Any], *, settings: PolicySettings = DEFAULT_SETTINGS,
    scanner_event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the 5.0 entry gates and score on one revealed tick."""
    hhmm = str(tick["time"])
    bar5 = tick.get("bar5_complete")
    failures: list[str] = []
    if hhmm >= settings.entry_cutoff:
        failures.append("entry_cutoff")
    if settings.scanner_event_required:
        if not isinstance(scanner_event, Mapping):
            failures.append("scanner_event_not_received")
        else:
            trigger = _optional_number(scanner_event.get("trigger"), "scanner_event.trigger")
            if trigger is None:
                failures.append("scanner_trigger_missing")
            elif _number(tick.get("c"), "tick.c") < trigger:
                failures.append("below_scanner_trigger")
    if not isinstance(bar5, dict):
        return {
            "eligible": False,
            "score": None,
            "components": {},
            "failures": failures + ["no_completed_5m"],
            "stop": None,
            "break_level": None,
        }

    count = bar5.get("prior_3_count")
    if count != 3:
        failures.append("prior_3_not_ready")

    required = {
        name: _optional_number(bar5.get(name), f"bar5_complete.{name}")
        for name in (
            "o", "h", "l", "c", "prior_3_high", "prior_3_low", "volume_ratio"
        )
    }
    if any(required[name] is None for name in ("prior_3_high", "prior_3_low", "volume_ratio")):
        failures.append("prior_3_fields_missing")
    if any(required[name] is None for name in ("o", "h", "l", "c")):
        failures.append("bar5_ohlc_missing")
        return {
            "eligible": False,
            "score": None,
            "components": {},
            "failures": failures,
            "stop": None,
            "break_level": None,
        }

    o, h, low, close = (required[name] for name in ("o", "h", "l", "c"))
    assert o is not None and h is not None and low is not None and close is not None
    vwap = _optional_number(tick.get("vwap"), "tick.vwap")
    ema9 = _optional_number(tick.get("ema9"), "tick.ema9")
    ema20 = _optional_number(tick.get("ema20"), "tick.ema20")
    macd_hist = _optional_number(tick.get("macd_hist"), "tick.macd_hist")
    rvol_bar = _optional_number(tick.get("rvol_bar"), "tick.rvol_bar")
    prior_high = required["prior_3_high"]
    prior_low = required["prior_3_low"]
    volume_ratio = required["volume_ratio"]
    bar_range = h - low
    green_upper_third = (
        close >= o and bar_range > 0 and h - close < bar_range / 3.0
    )

    if not green_upper_third:
        failures.append("not_green_upper_third")
    if vwap is None or close <= vwap:
        failures.append("not_above_vwap")
    if prior_high is None or h <= prior_high or close <= prior_high:
        failures.append("not_five_minute_break")
    if volume_ratio is None or volume_ratio < 1.5:
        failures.append("volume_ratio_below_1_5")
    if macd_hist is None or macd_hist < 0:
        failures.append("negative_macd")

    events = _events(tick)
    best_pattern = max(
        (
            PATTERN_WEIGHTS[event["pattern"]] * event["score"]
            for event in events
            if event["direction"] == "bullish" and event["pattern"] in PATTERN_WEIGHTS
        ),
        default=0.0,
    )
    bearish = any(
        event["direction"] == "bearish" or event["pattern"] in BEARISH_PATTERNS
        for event in events
    )
    if bearish:
        failures.append("bearish_pattern_veto")

    volume_score = 0.0
    if volume_ratio is not None and volume_ratio >= 1.5:
        volume_score += 15.0
    if volume_ratio is not None and volume_ratio >= 2.0:
        volume_score += 5.0
    if rvol_bar is not None and rvol_bar >= 1.5:
        volume_score += 5.0

    trend_score = 0.0
    if vwap is not None and close > vwap:
        trend_score += 8.0
    if ema9 is not None and ema20 is not None and ema9 >= ema20:
        trend_score += 6.0
    if macd_hist is not None and macd_hist >= 0:
        trend_score += 6.0

    quality_score = (10.0 if green_upper_third else 0.0) + (0.0 if bearish else 5.0)
    timing_score = 10.0 if hhmm < "10:30" else (5.0 if hhmm < settings.entry_cutoff else 0.0)
    components = {
        "pattern": round(best_pattern, 4),
        "volume": volume_score,
        "trend": trend_score,
        "quality": quality_score,
        "timing": timing_score,
    }
    score = round(sum(components.values()), 4)
    if score < settings.entry_threshold:
        failures.append(f"score_below_{settings.entry_threshold:g}")

    stop = (
        round(min(low, prior_low) - 0.01, 4)
        if prior_low is not None else None
    )
    if stop is None or stop >= close:
        failures.append("invalid_structural_stop")
    return {
        "eligible": not failures,
        "score": score,
        "components": components,
        "failures": failures,
        "stop": stop,
        "break_level": prior_high,
    }


def _scanner_event_entry_assessment(
    tick: Mapping[str, Any],
    *,
    scanner_event: Mapping[str, Any] | None,
    bars_since_event: int | None,
    settings: PolicySettings,
) -> dict[str, Any]:
    """Causal one-minute confirmation after an already-released scanner event."""
    failures: list[str] = []
    hhmm = str(tick["time"])
    if hhmm >= settings.entry_cutoff:
        failures.append("entry_cutoff")
    if not isinstance(scanner_event, Mapping):
        failures.append("scanner_event_not_received")
        return {"eligible": False, "score": None, "components": {}, "failures": failures, "stop": None, "break_level": None}
    trigger = _optional_number(scanner_event.get("trigger"), "scanner_event.trigger")
    scanner_rvol = _optional_number(scanner_event.get("rvol"), "scanner_event.rvol")
    if trigger is None:
        failures.append("scanner_trigger_missing")
    if bars_since_event is None or bars_since_event > settings.scanner_event_confirmation_bars:
        failures.append("scanner_confirmation_window_expired")
    close = _number(tick.get("c"), "tick.c")
    low = _number(tick.get("l"), "tick.l")
    open_ = _number(tick.get("o"), "tick.o")
    vwap = _optional_number(tick.get("vwap"), "tick.vwap")
    macd = _optional_number(tick.get("macd_hist"), "tick.macd_hist")
    rvol_bar = _optional_number(tick.get("rvol_bar"), "tick.rvol_bar")
    if trigger is not None and close < trigger * 0.99:
        failures.append("below_scanner_trigger_tolerance")
    if vwap is None or close <= vwap:
        failures.append("not_above_vwap")
    if macd is None or macd < 0:
        failures.append("negative_macd")
    if not bool(tick.get("new_high")):
        failures.append("not_new_high")
    events = _events(tick)
    best_pattern = max((PATTERN_WEIGHTS[e["pattern"]] * e["score"] for e in events if e["direction"] == "bullish" and e["pattern"] in PATTERN_WEIGHTS), default=0.0)
    bearish = any(e["direction"] == "bearish" or e["pattern"] in BEARISH_PATTERNS for e in events)
    if bearish:
        failures.append("bearish_pattern_veto")
    components = {
        "scanner": 25.0 if scanner_rvol is not None and scanner_rvol >= 1.5 else 15.0,
        "pattern": round(best_pattern, 4),
        "trend": 20.0 if vwap is not None and close > vwap and macd is not None and macd >= 0 else 0.0,
        "quality": 15.0 if close >= open_ and not bearish else 0.0,
        "timing": 10.0 if hhmm < "10:30" else 5.0,
        "bar_volume": 10.0 if rvol_bar is not None and rvol_bar >= 1.5 else 0.0,
    }
    score = round(sum(components.values()), 4)
    if score < settings.entry_threshold:
        failures.append(f"score_below_{settings.entry_threshold:g}")
    stop = round(low - 0.01, 4)
    if stop >= close:
        failures.append("invalid_structural_stop")
    return {"eligible": not failures, "score": score, "components": components, "failures": failures, "stop": stop, "break_level": trigger}


def _exit_assessment(
    tick: Mapping[str, Any],
    *,
    negative_macd_bars: int,
    bars_since_entry: int,
    made_post_entry_high: bool,
    avg_entry: float,
    initial_stop_distance: float,
) -> dict[str, Any]:
    """Compute the experimental 4.1/5.0 exit-pressure card."""
    close = _number(tick.get("c"), "tick.c")
    vwap = _optional_number(tick.get("vwap"), "tick.vwap")
    macd_score = 10.0 if negative_macd_bars >= 2 else 0.0
    events = _events(tick)
    best_bearish = max(
        (
            event["score"]
            for event in events
            if event["direction"] == "bearish" or event["pattern"] in BEARISH_PATTERNS
        ),
        default=0.0,
    )
    bar5 = tick.get("bar5_complete")
    red_volume_score = 0.0
    if isinstance(bar5, dict):
        o = _optional_number(bar5.get("o"), "bar5_complete.o")
        c = _optional_number(bar5.get("c"), "bar5_complete.c")
        ratio = _optional_number(bar5.get("volume_ratio"), "bar5_complete.volume_ratio")
        if o is not None and c is not None and ratio is not None and c < o and ratio >= 1.5:
            red_volume_score = 20.0
    stalled = (
        bars_since_entry >= 5
        and not made_post_entry_high
        and close < avg_entry + 0.25 * initial_stop_distance
    )
    components = {
        "below_vwap": 35.0 if vwap is not None and close < vwap else 0.0,
        "bearish_pattern": round(25.0 * best_bearish, 4),
        "red_5m_volume": red_volume_score,
        "negative_macd": macd_score,
        "stalled": 10.0 if stalled else 0.0,
    }
    return {
        "score": round(min(100.0, sum(components.values())), 4),
        "components": components,
    }


def _execution_config(value: ExecutionConfig | Mapping[str, Any] | None) -> ExecutionConfig:
    if isinstance(value, ExecutionConfig):
        return value
    if value is None:
        value = {
            "profile": "small",
            "risk_budget": 40.0,
            "buying_power": 12_000.0,
            "same_day_only": True,
        }
    return ExecutionConfig.from_session_config(dict(value))


def _validate_tick(tick: Mapping[str, Any], previous_i: int) -> tuple[int, str]:
    i = tick.get("i")
    hhmm = tick.get("time")
    if not isinstance(i, int) or isinstance(i, bool) or i < 0:
        raise PolicyError("stream tick i must be a non-negative integer")
    if i <= previous_i:
        raise PolicyError("stream ticks must have strictly increasing i")
    if not isinstance(hhmm, str) or not _HHMM_RE.fullmatch(hhmm):
        raise PolicyError(f"stream tick i={i} time must be HH:MM")
    hour, minute = (int(part) for part in hhmm.split(":"))
    if hour > 23 or minute > 59:
        raise PolicyError(f"stream tick i={i} time must be valid")
    for field in ("o", "h", "l", "c", "v"):
        _number(tick.get(field), f"tick.{field}")
    return i, hhmm


def _base_record(i: int, hhmm: str) -> dict[str, Any]:
    return {
        "i": i,
        "time": hhmm,
        "action": "OBSERVE",
        "thought": f"deterministic policy {POLICY_ID}",
        "policy_id": POLICY_ID,
        "decision_source": DECISION_SOURCE,
    }


class WarriorPatternPolicy:
    """Causal, single-trade Warrior state machine."""

    def __init__(
        self,
        execution_config: ExecutionConfig,
        *,
        settings: PolicySettings = DEFAULT_SETTINGS,
    ) -> None:
        self.engine = ExecutionEngine(execution_config)
        self.settings = settings
        self.previous_i = -1
        self.entry_attempted = False
        self.ever_long = False
        self.trade_complete = False
        self.exit_latched = False
        self.entry_i: int | None = None
        self.entry_bar_high: float | None = None
        self.break_level: float | None = None
        self.initial_stop: float | None = None
        self.high_water: float | None = None
        self.made_post_entry_high = False
        self.negative_macd_bars = 0
        self.last_green_5m_low: float | None = None
        self.scanner_event: Mapping[str, Any] | None = None
        self.scanner_event_i: int | None = None

    def _runner_exit(self, tick: Mapping[str, Any]) -> bool:
        bar5 = tick.get("bar5_complete")
        if not isinstance(bar5, dict) or self.last_green_5m_low is None:
            return False
        o = _optional_number(bar5.get("o"), "bar5_complete.o")
        close = _optional_number(bar5.get("c"), "bar5_complete.c")
        return (
            o is not None
            and close is not None
            and close < o
            and close < self.last_green_5m_low
        )

    def _update_green_5m(self, tick: Mapping[str, Any]) -> None:
        bar5 = tick.get("bar5_complete")
        if not isinstance(bar5, dict):
            return
        o = _optional_number(bar5.get("o"), "bar5_complete.o")
        close = _optional_number(bar5.get("c"), "bar5_complete.c")
        low = _optional_number(bar5.get("l"), "bar5_complete.l")
        if o is not None and close is not None and low is not None and close >= o:
            self.last_green_5m_low = low

    def decide(self, tick: Mapping[str, Any]) -> dict[str, Any]:
        i, hhmm = _validate_tick(tick, self.previous_i)
        self.previous_i = i
        event = tick.get("scanner_event")
        if event is not None:
            if not isinstance(event, Mapping):
                raise PolicyError("scanner_event must be an object")
            event_time = event.get("time")
            if event_time != hhmm:
                raise PolicyError("scanner_event must be released on its timestamp")
            _optional_number(event.get("trigger"), "scanner_event.trigger")
            self.scanner_event = dict(event)
            self.scanner_event_i = i
        bar = {
            key: tick.get(key)
            for key in ("i", "time", "o", "h", "l", "c", "v", "rvol_bar", "new_high", "macd_hist")
        }

        # Resolve protection and active targets before making this bar-close
        # decision, matching ExecutionEngine.run exactly.
        self.engine._last_bar = bar
        self.engine._resolve_open_orders(bar)
        self.engine._mark_mae(bar)
        snapshot = self.engine.snapshot(i)
        record = _base_record(i, hhmm)

        if self.ever_long and self.engine.shares == 0:
            self.trade_complete = True

        if self.engine.shares <= 0:
            if self.trade_complete or self.entry_attempted:
                record.update({
                    "action": "STAND_DOWN",
                    "thought": (
                        f"deterministic policy {POLICY_ID}: one-trade lifecycle complete"
                    ),
                    "reason_codes": ["one_trade_complete"],
                })
            else:
                assessment = (
                    _scanner_event_entry_assessment(
                        tick, scanner_event=self.scanner_event,
                        bars_since_event=(i - self.scanner_event_i) if self.scanner_event_i is not None else None,
                        settings=self.settings,
                    )
                    if self.settings.scanner_event_immediate_confirmation
                    else _entry_assessment(tick, settings=self.settings, scanner_event=self.scanner_event)
                )
                record.update({
                    "entry_score": assessment["score"],
                    "score_components": assessment["components"],
                    "reason_codes": assessment["failures"],
                    "thought": (
                        f"entry score={assessment['score']} "
                        f"components={assessment['components']} "
                        f"gates={assessment['failures'] or ['pass']}"
                    ),
                })
                if assessment["eligible"]:
                    record.update({
                        "action": "ENTER_CLOSE",
                        "stop": assessment["stop"],
                        "bracket": ENTRY_BRACKET,
                    })
                    self.entry_attempted = True
                    self.entry_i = i
                    self.entry_bar_high = _number(tick.get("h"), "tick.h")
                    self.break_level = assessment["break_level"]
                    self.initial_stop = assessment["stop"]
        else:
            self.ever_long = True
            assert self.entry_i is not None
            avg_entry = _number(snapshot.get("avg_entry"), "execution avg_entry")
            stop = _number(snapshot.get("stop"), "execution stop")
            high = _number(tick.get("h"), "tick.h")
            close = _number(tick.get("c"), "tick.c")
            self.high_water = max(self.high_water or high, high)
            if i > self.entry_i and self.entry_bar_high is not None and high > self.entry_bar_high:
                self.made_post_entry_high = True
            macd_hist = _optional_number(tick.get("macd_hist"), "tick.macd_hist")
            self.negative_macd_bars = (
                self.negative_macd_bars + 1
                if macd_hist is not None and macd_hist < 0 else 0
            )
            initial_distance = max(0.0, avg_entry - _number(self.initial_stop, "initial stop"))
            bars_since_entry = i - self.entry_i
            exit_assessment = _exit_assessment(
                tick,
                negative_macd_bars=self.negative_macd_bars,
                bars_since_entry=bars_since_entry,
                made_post_entry_high=self.made_post_entry_high,
                avg_entry=avg_entry,
                initial_stop_distance=initial_distance,
            )
            failed_break = (
                bars_since_entry <= 2
                and self.break_level is not None
                and close < self.break_level
            )
            mandatory_flat = hhmm >= self.settings.mandatory_flat_time
            runner_exit = self._runner_exit(tick)
            scale_fill = any(fill.get("action") == "SCALE" for fill in snapshot["fills"])

            reason: str | None = None
            if self.exit_latched:
                reason = "complete_latched_exit"
            elif mandatory_flat:
                reason = "mandatory_15_55_flat"
            elif failed_break:
                reason = "immediate_failed_break"
            elif exit_assessment["score"] >= self.settings.exit_threshold:
                reason = "exit_pressure"

            if reason is not None:
                self.exit_latched = True
                record.update({
                    "action": "EXIT_CLOSE",
                    "exit_score": exit_assessment["score"],
                    "score_components": exit_assessment["components"],
                    "reason_codes": [reason],
                    "thought": (
                        f"{reason}; exit score={exit_assessment['score']} "
                        f"components={exit_assessment['components']}"
                    ),
                })
            elif scale_fill and stop < avg_entry:
                record.update({
                    "action": "SET_STOP",
                    "stop": avg_entry,
                    "exit_score": exit_assessment["score"],
                    "score_components": exit_assessment["components"],
                    "reason_codes": ["first_scale_to_breakeven"],
                    "thought": "engine scale filled; protect runner at average entry",
                })
            elif (
                bars_since_entry in {1, 2}
                and initial_distance > 0
                and self.high_water >= avg_entry + min(0.10, initial_distance / 3.0)
                and close >= avg_entry
                and stop < avg_entry
            ):
                record.update({
                    "action": "SET_STOP",
                    "stop": avg_entry,
                    "exit_score": exit_assessment["score"],
                    "score_components": exit_assessment["components"],
                    "reason_codes": ["early_free_trade"],
                    "thought": "early momentum held; raise protective stop to average entry",
                })
            elif runner_exit:
                self.exit_latched = True
                record.update({
                    "action": "EXIT_CLOSE",
                    "exit_score": exit_assessment["score"],
                    "score_components": exit_assessment["components"],
                    "reason_codes": ["five_minute_runner_exit"],
                    "thought": "completed red 5m candle closed below prior green 5m low",
                })
            else:
                record.update({
                    "exit_score": exit_assessment["score"],
                    "score_components": exit_assessment["components"],
                    "reason_codes": ["manage_hold"],
                    "thought": (
                        f"hold; exit score={exit_assessment['score']} "
                        f"components={exit_assessment['components']}"
                    ),
                })

        self.engine._apply_decision(bar, record)
        if record["action"] == "ENTER_CLOSE":
            self.ever_long = self.engine.shares > 0
            self.trade_complete = self.engine.shares <= 0
            if self.engine.shares > 0:
                self.high_water = _number(tick.get("h"), "tick.h")
        self.engine._queue_pyramid_add(bar)
        self._update_green_5m(tick)
        return record


def decisions_for_ticks(
    ticks: Iterable[dict[str, Any]],
    execution_config: ExecutionConfig | Mapping[str, Any] | None = None,
    *,
    settings: PolicySettings = DEFAULT_SETTINGS,
) -> list[dict[str, Any]]:
    """Return one deterministic intent for every causally ordered stream tick."""
    policy = WarriorPatternPolicy(_execution_config(execution_config), settings=settings)
    return [policy.decide(tick) for tick in ticks]


def apply_to_session(session_dir: str | Path) -> list[dict[str, Any]]:
    """Materialize the deterministic policy in a fully published Warrior leaf."""
    from ... import recorder
    from ...fsutils import atomic_write_json

    sdir = Path(session_dir)
    session_path = sdir / "session.json"
    session = recorder._load_json(session_path, {}) or {}
    if session.get("status") == "complete":
        raise PolicyError(f"session {sdir.name} is finalized")
    if session.get("strategy") != "warrior":
        raise PolicyError("Warrior pattern policy is available only to warrior sessions")
    if session.get("config", {}).get("execution_model") != EXECUTION_MODEL:
        raise PolicyError("Warrior pattern policy requires deterministic_ohlc_v1 execution")
    skill = session.get("skill") or {}
    if str(skill.get("decision_source") or "").strip().lower() != DECISION_SOURCE:
        raise PolicyError("Warrior pattern policy requires decision_source: deterministic_policy")
    if skill.get("decision_policy") != POLICY_ID:
        raise PolicyError(f"Warrior pattern policy requires decision_policy: {POLICY_ID}")
    for flag in (
        "session_from_open",
        "five_minute_context",
        "candlebar_context",
        "strict_prior_three_context",
        "completed_five_minute_entry_required",
        "entry_bracket_required",
    ):
        if not _is_true(skill.get(flag)):
            raise PolicyError(f"Warrior pattern policy requires {flag}: true")
    if recorder._last_logged_i(sdir / "decisions.jsonl") >= 0:
        raise PolicyError("Warrior pattern policy refuses a session with existing decisions")

    meta, ticks, _end = recorder._parse_stream(sdir / "stream.jsonl")
    if meta is None or not ticks:
        raise PolicyError("Warrior pattern policy requires a published stream with ticks")
    if not _is_true(meta.get("strict_prior_three_context")):
        raise PolicyError("published stream is missing strict prior-three context")
    integrity_errors = recorder.stream_integrity_errors(sdir, session)
    if integrity_errors:
        raise PolicyError(
            "Warrior pattern policy refuses stream data-integrity failure — "
            + "; ".join(integrity_errors)
        )
    records = decisions_for_ticks(ticks, session.get("config", {}))

    session["decision_policy"] = {"source": DECISION_SOURCE, "id": POLICY_ID}
    atomic_write_json(session_path, session, indent=2)
    for record in records:
        recorder.log(sdir, record)
    return records


POLICY_CONTRACT_SUBJECTS = (
    _events,
    _entry_assessment,
    _exit_assessment,
    WarriorPatternPolicy,
    decisions_for_ticks,
    apply_to_session,
)
