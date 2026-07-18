"""Scan configuration for the trend-pullback swing family."""

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
class TrendPullbackConfig:
    """Knobs for Lance-style trending pullback (long only).

    v0.4.0 default: pullback to **SMA50** (orthogonal last try vs EMA20 0.1–0.3),
    with 0.2.0-style construction (setup_high + prior-high targets).
    """

    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    # Universe / liquidity
    price_min: float = 10.0
    price_max: float = 10_000.0
    avg_vol_min: float = 1_000_000.0
    rvol_lookback: int = 20

    # Trend filters (evaluated on the setup / plan bar close)
    require_above_sma50: bool = True
    require_above_sma200: bool = True
    require_sma50_rising: bool = True
    sma50_rising_lookback: int = 20
    # Max extension of setup close above the *pullback MA* (not always EMA20)
    max_extension_above_ema_pct: float = 4.0

    # Pullback geometry
    # v0.4.0 default = sma50 (last orthogonal try). Use ema20 to reproduce 0.2.0.
    pullback_ma: Literal["ema20", "sma50"] = "sma50"
    touch_tol_pct: float = 0.0
    # Require ≥1 close ≤ pullback MA in the window (body dip)
    require_close_below_ema: bool = True
    # SMA50 pullbacks tend to take longer than EMA20 — slightly wider window
    max_pullback_bars: int = 15
    min_pullback_bars: int = 3
    prior_high_lookback: int = 40
    pullback_depth_min_pct: float = 4.0
    pullback_depth_max_pct: float = 18.0

    # Plan / risk — restore 0.2.0 construction (best n30 so far)
    signal_mode: Literal["prebreak_arm"] = "prebreak_arm"
    arm_expiry_bars: int = 5
    max_entry_gap_atr: float = 0.5
    atr_period: int = 14
    stop_buffer_atr: float = 0.15
    entry_trigger_mode: Literal["reclaim_close", "setup_high"] = "setup_high"
    target1_mode: Literal["risk_r", "prior_high"] = "prior_high"
    target1_r_mult: float = 1.0
    target2_r_mult: float = 2.0
    measured_move_frac: float = 1.0

    require_spy_above_sma50: bool = True

    max_scan_failure_rate: float = 0.0
    min_bars_between_arms: int = 12

    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")

    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("trend_pullback") / "entries.db"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TrendPullbackConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict in YAML file {path}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "TrendPullbackConfig":
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
                f"unknown TrendPullbackConfig key(s): {sorted(unknown)}; "
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
            raise ValueError("TrendPullbackConfig.start must be on or before end")
        if self.price_min <= 0 or self.price_max < self.price_min:
            raise ValueError("price bounds must be positive and price_max >= price_min")
        if self.avg_vol_min < 0:
            raise ValueError("avg_vol_min must be non-negative")
        if self.rvol_lookback < 2:
            raise ValueError("rvol_lookback must be at least 2")
        if self.sma50_rising_lookback < 1:
            raise ValueError("sma50_rising_lookback must be positive")
        if not 1 <= self.min_pullback_bars <= self.max_pullback_bars:
            raise ValueError("pullback bar bounds must be ordered and positive")
        if self.prior_high_lookback < 5:
            raise ValueError("prior_high_lookback must be at least 5")
        if not 0 < self.pullback_depth_min_pct <= self.pullback_depth_max_pct:
            raise ValueError("pullback depth bounds must be positive and ordered")
        if self.atr_period < 2:
            raise ValueError("atr_period must be >= 2")
        if self.arm_expiry_bars < 1:
            raise ValueError("arm_expiry_bars must be positive")
        if self.max_entry_gap_atr < 0:
            raise ValueError("max_entry_gap_atr must be non-negative")
        if self.stop_buffer_atr < 0:
            raise ValueError("stop_buffer_atr must be non-negative")
        if self.measured_move_frac <= 0:
            raise ValueError("measured_move_frac must be positive")
        if self.entry_trigger_mode not in {"reclaim_close", "setup_high"}:
            raise ValueError("entry_trigger_mode must be reclaim_close or setup_high")
        if self.target1_mode not in {"risk_r", "prior_high"}:
            raise ValueError("target1_mode must be risk_r or prior_high")
        if self.target1_r_mult <= 0 or self.target2_r_mult <= self.target1_r_mult:
            raise ValueError("target R multiples must be positive and target2 > target1")
        if not 0 <= self.max_scan_failure_rate <= 1:
            raise ValueError("max_scan_failure_rate must be in [0, 1]")
        if self.signal_mode != "prebreak_arm":
            raise ValueError("signal_mode must be 'prebreak_arm' for v0")
        if self.pullback_ma not in {"ema20", "sma50"}:
            raise ValueError("pullback_ma must be 'ema20' or 'sma50'")
