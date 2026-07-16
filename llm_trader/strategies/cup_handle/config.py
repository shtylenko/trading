"""Scan configuration for the cup-and-handle swing family."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class CupHandleConfig:
    """Knobs for the cup-and-handle scanner (Davidson-style operationalization)."""

    start: date = field(default_factory=lambda: date(2025, 1, 1))
    end: date = field(default_factory=lambda: date(2026, 6, 30))

    # Universe / liquidity (Finviz-like, reimplemented on marketdata)
    price_min: float = 20.0
    price_max: float = 10_000.0
    avg_vol_min: float = 2_000_000.0
    rvol_lookback: int = 20

    # Trend (5 key questions — strong uptrend)
    require_above_sma20: bool = True
    require_above_sma50: bool = True
    require_above_sma200: bool = True
    require_sma50_rising: bool = True
    sma50_rising_lookback: int = 20

    # Cup geometry (objectified)
    cup_min_bars: int = 20          # ~4 weeks
    cup_max_bars: int = 90          # ~4.5 months
    cup_depth_min_pct: float = 12.0
    cup_depth_max_pct: float = 35.0
    lip_tolerance_pct: float = 5.0  # right lip within this % of left lip high

    # Handle
    handle_min_bars: int = 3
    handle_max_bars: int = 15
    handle_depth_max_frac: float = 0.40  # handle depth ≤ 40% of cup depth
    handle_vol_frac_max: float = 0.85    # handle avg vol ≤ this × prior cup avg vol

    # Breakout confirmation
    require_breakout_volume: bool = True
    breakout_vol_mult: float = 1.3       # vs 20d avg
    require_green_breakout: bool = True

    # Risk plan (Baby Bear ATR stop + dual targets)
    atr_period: int = 14
    stop_atr_mult: float = 1.5
    target1_cup_frac: float = 0.50       # half position at 50% of measured move
    target2_cup_frac: float = 0.80       # remainder toward 80% of measured move

    # Market regime proxy ("trifecta" lite — overall market)
    require_spy_above_sma50: bool = False  # optional; needs SPY daily bars

    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")

    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("cup_handle") / "entries.db"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CupHandleConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict in YAML file {path}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "CupHandleConfig":
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
                f"unknown CupHandleConfig key(s): {sorted(unknown)}; "
                f"valid keys: {sorted(known)}"
            )
        return cls(**raw)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        d["exchanges"] = list(self.exchanges)
        d["db_path"] = str(self.db_path)
        return d
