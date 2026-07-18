"""Scan configuration for breakout-first-pullback (Lance swing #2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import yaml

from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class BreakoutFirstPullbackConfig:
    """Multi-week base → breakout → first pullback to breakout level as support."""

    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    # Universe
    price_min: float = 10.0
    price_max: float = 10_000.0
    avg_vol_min: float = 1_000_000.0
    rvol_lookback: int = 20

    # Base / consolidation (before breakout)
    base_min_bars: int = 15          # ~3 weeks
    base_max_bars: int = 60          # ~3 months
    base_range_max_pct: float = 18.0  # (base_high - base_low) / base_high
    base_range_min_pct: float = 4.0

    # Breakout (v0.2.0: stronger — fewer false breaks in weak regimes)
    breakout_vol_mult: float = 1.5   # was 1.3 in 0.1.0
    require_green_breakout: bool = True
    # Close must clear base high by at least this fraction of price
    breakout_clear_pct: float = 0.30  # was 0.15

    # First pullback after breakout
    max_bars_to_first_pullback: int = 12
    min_bars_after_breakout: int = 1
    # Tighter retest of breakout level (was 1.5)
    retest_tol_pct: float = 1.0
    require_close_above_breakout: bool = True
    # Less extension at arm (was 6)
    max_extension_above_breakout_pct: float = 4.0
    pullback_depth_min_pct: float = 2.5
    pullback_depth_max_pct: float = 12.0
    # Prefer quieter pullback vs breakout day volume
    require_pullback_vol_below_breakout: bool = True

    # Trend / regime (v0.2.0: hard trend filters — 2022 was the hole)
    require_above_sma50: bool = True
    require_above_sma200: bool = True   # was False
    require_sma50_rising: bool = True
    sma50_rising_lookback: int = 20
    require_spy_above_sma50: bool = True
    require_spy_above_sma200: bool = True  # new: bull-regime only

    # Plan / risk (v0.2.0 construction: buy the level, not the chase)
    signal_mode: Literal["prebreak_arm"] = "prebreak_arm"
    arm_expiry_bars: int = 5
    max_entry_gap_atr: float = 0.5
    atr_period: int = 14
    stop_buffer_atr: float = 0.15
    # breakout_level = ARM at the reclaimed support (Lance); setup_high = 0.1.0 chase
    entry_trigger_mode: Literal["setup_high", "breakout_level"] = "breakout_level"
    measured_move_frac: float = 1.0

    max_scan_failure_rate: float = 0.0
    min_bars_between_arms: int = 15

    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")

    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("breakout_first_pullback") / "entries.db"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BreakoutFirstPullbackConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict in YAML file {path}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "BreakoutFirstPullbackConfig":
        raw = dict(raw)
        if "start" in raw:
            raw["start"] = _as_date(raw["start"])
        if "end" in raw:
            raw["end"] = _as_date(raw["end"])
        if "exchanges" in raw and raw["exchanges"] is not None:
            raw["exchanges"] = tuple(raw["exchanges"])
        if "db_path" in raw and raw["db_path"] is not None:
            raw["db_path"] = Path(raw["db_path"])
        known = set(cls.__dataclass_fields__)
        unknown = set(raw) - known
        if unknown:
            raise ValueError(
                f"unknown BreakoutFirstPullbackConfig key(s): {sorted(unknown)}; "
                f"valid keys: {sorted(known)}"
            )
        cfg = cls(**raw)
        cfg.validate()
        return cfg

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        d["exchanges"] = list(self.exchanges)
        d["db_path"] = str(self.db_path)
        return d

    def validate(self) -> None:
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        if self.price_min <= 0 or self.price_max < self.price_min:
            raise ValueError("invalid price bounds")
        if self.avg_vol_min < 0:
            raise ValueError("avg_vol_min must be non-negative")
        if not 5 <= self.base_min_bars <= self.base_max_bars:
            raise ValueError("base bar bounds invalid")
        if not 0 < self.base_range_min_pct <= self.base_range_max_pct:
            raise ValueError("base range bounds invalid")
        if self.breakout_vol_mult <= 0:
            raise ValueError("breakout_vol_mult must be positive")
        if self.max_bars_to_first_pullback < self.min_bars_after_breakout:
            raise ValueError("pullback window bounds invalid")
        if self.atr_period < 2 or self.arm_expiry_bars < 1:
            raise ValueError("atr_period / arm_expiry_bars invalid")
        if self.signal_mode != "prebreak_arm":
            raise ValueError("signal_mode must be prebreak_arm")
        if self.entry_trigger_mode not in {"setup_high", "breakout_level"}:
            raise ValueError("invalid entry_trigger_mode")
        if not 0 <= self.max_scan_failure_rate <= 1:
            raise ValueError("max_scan_failure_rate must be in [0, 1]")
