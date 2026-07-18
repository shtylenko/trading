"""Config for same-day VWAP pullback / reclaim."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class VwapPullbackConfig:
    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    # Daily pre-screen (liquid trend/gap day — not warrior penny gappers)
    price_min: float = 10.0
    price_max: float = 1_000.0
    gap_min_pct: float = 0.5          # mild gap or strength day
    gap_max_pct: float = 25.0
    avg_vol_min: float = 1_000_000.0
    rvol_min: float = 1.2
    rvol_lookback: int = 20
    # Also allow flat-gap days if prior close green? Keep simple: gap_min only

    # Intraday structure
    morning_confirm_end: str = "10:30"   # must have held above VWAP in open→this
    entry_window_start: str = "10:00"
    entry_window_end: str = "14:00"
    min_bars_above_vwap_before: int = 3  # bars strictly above VWAP before first touch
    require_green_reclaim: bool = True
    # Touch: low <= vwap <= high
    # Stop under VWAP by this fraction of price or ATR proxy from bar range
    stop_below_vwap_pct: float = 0.15     # 0.15% of price under VWAP
    target1_r_mult: float = 1.0
    target2_r_mult: float = 2.0
    # EOD flatten after this ET time
    eod_exit_et: str = "15:55"
    # Cost model (bps round-trip half applied each side)
    fee_bps_one_way: float = 1.0
    slippage_bps_one_way: float = 2.0

    # Risk $ for PnL reporting (fixed risk budget)
    risk_budget: float = 100.0

    # Structural gate (Lance No Man's Land) — OFF; A/B hard-fail on this family.
    nml_gate: bool = False

    # Paper-book portfolio packaging (A/B-validated; port_v0.1.0)
    paper_portfolio: bool = True
    paper_max_concurrent: int = 3
    paper_max_per_day: int = 5

    max_scan_failure_rate: float = 1.0  # 5m missing is common; don't fail closed
    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")
    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("vwap_pullback") / "entries.db"
    )

    @classmethod
    def from_dict(cls, raw: dict) -> "VwapPullbackConfig":
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
            raise ValueError(f"unknown keys: {sorted(unknown)}")
        return cls(**raw)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        d["exchanges"] = list(self.exchanges)
        d["db_path"] = str(self.db_path)
        return d
