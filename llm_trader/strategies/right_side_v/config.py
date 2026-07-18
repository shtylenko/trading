"""Config for right-side-of-V confirmed reversal (long only)."""

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
class RightSideVConfig:
    """Sharp selloff → confirmed turn → long (not knife-catch)."""

    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    price_min: float = 10.0
    price_max: float = 10_000.0
    avg_vol_min: float = 1_000_000.0
    rvol_lookback: int = 20

    # Left side of V: selloff geometry
    drop_lookback_max: int = 20       # max bars for the down leg
    drop_lookback_min: int = 3
    drop_min_pct: float = 8.0         # min % drop from local high to pivot
    drop_max_pct: float = 35.0

    # Right side confirmation (not left-side catch)
    # Setup close must reclaim SMA20 and be above a fraction of the drop retrace
    require_close_above_sma20: bool = True
    min_retrace_frac: float = 0.35    # close >= pivot + frac*(high-pivot)
    # Higher low vs an intermediate trough optional — use reclaim of prior bar high
    require_close_above_prior_high: bool = True  # close > prior day high (turn)
    max_extension_above_sma20_pct: float = 8.0   # don't chase already extended

    # Regime: allow mean-reversion recoveries even if SPY soft, but require
    # name not in free-fall vs 200 (optional soft filter)
    require_above_sma200: bool = False
    require_spy_above_sma50: bool = False  # V's often after risk-off; off by default
    sma50_rising_lookback: int = 20

    # Plan
    signal_mode: Literal["prebreak_arm"] = "prebreak_arm"
    arm_expiry_bars: int = 5
    max_entry_gap_atr: float = 0.5
    atr_period: int = 14
    stop_buffer_atr: float = 0.20
    # Trigger = setup high (continuation of right side)
    entry_trigger_mode: Literal["setup_high", "reclaim_close"] = "setup_high"
    # T1 = 50% retrace of drop (from pivot); T2 = full retrace to swing high
    target1_retrace_frac: float = 0.50
    target2_retrace_frac: float = 1.00

    max_scan_failure_rate: float = 0.0
    min_bars_between_arms: int = 10

    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")
    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("right_side_v") / "entries.db"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RightSideVConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict in YAML file {path}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "RightSideVConfig":
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
            raise ValueError(f"unknown RightSideVConfig key(s): {sorted(unknown)}")
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
        if not 2 <= self.drop_lookback_min <= self.drop_lookback_max:
            raise ValueError("drop lookback bounds invalid")
        if not 0 < self.drop_min_pct <= self.drop_max_pct:
            raise ValueError("drop pct bounds invalid")
        if not 0 < self.min_retrace_frac <= 1:
            raise ValueError("min_retrace_frac must be in (0,1]")
        if not 0 < self.target1_retrace_frac < self.target2_retrace_frac:
            raise ValueError("target retrace fractions invalid")
        if self.signal_mode != "prebreak_arm":
            raise ValueError("signal_mode must be prebreak_arm")
        if self.atr_period < 2 or self.arm_expiry_bars < 1:
            raise ValueError("atr/arm_expiry invalid")
