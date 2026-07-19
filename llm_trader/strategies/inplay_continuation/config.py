"""Config for in-play gap continuation (Opp C) — WeBull research economics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from trading.llm_trader.costs.webull import LiquidityTier, WebullLongEquityCosts, webull_long_equity
from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class InplayContinuationConfig:
    start: date = field(default_factory=lambda: date(2025, 7, 1))
    end: date = field(default_factory=lambda: date(2026, 6, 30))

    # In-play daily screen (PREREG v0.1.0)
    price_min: float = 2.0
    price_max: float = 50.0
    gap_min_pct: float = 5.0
    gap_max_pct: float = 80.0
    avg_vol_min: float = 500_000.0
    rvol_min: float = 2.0
    rvol_lookback: int = 20
    float_max: Optional[float] = 50_000_000.0  # None = no float gate

    # Impulse / micro-pb (stricter impulse % than liquid micro)
    impulse_min_bars: int = 2
    impulse_min_pct: float = 0.8
    require_above_vwap: bool = True
    pb_min_bars: int = 1
    pb_max_bars: int = 3
    pb_max_depth_frac: float = 0.55
    pb_must_hold_vwap: bool = True

    entry_window_start: str = "09:45"
    entry_window_end: str = "13:30"
    require_green_break: bool = True

    stop_buffer_pct: float = 0.05
    target1_r_mult: float = 1.0
    target2_r_mult: float = 2.0
    eod_exit_et: str = "15:55"
    risk_budget: float = 100.0

    # WeBull cost model (not legacy 1+2 mega)
    cost_tier: str = "small"
    slippage_bps_one_way: float = 15.0
    # Derived for sim: fee_one_way approximates sell regulatory/2
    fee_bps_one_way: float = 0.25

    paper_portfolio: bool = True
    paper_max_concurrent: int = 3
    paper_max_per_day: int = 5
    nml_gate: bool = False

    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")
    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("inplay_continuation") / "entries.db"
    )

    def cost_model(self) -> WebullLongEquityCosts:
        tier = LiquidityTier(self.cost_tier)
        return webull_long_equity(tier=tier, slip_bps_one_way=self.slippage_bps_one_way)

    def apply_cost_model(self, model: WebullLongEquityCosts) -> "InplayContinuationConfig":
        self.slippage_bps_one_way = model.slippage_bps_one_way
        self.fee_bps_one_way = model.fee_bps_sell / 2.0
        self.cost_tier = model.tier.value
        return self

    @classmethod
    def from_dict(cls, raw: dict) -> "InplayContinuationConfig":
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
        d["cost_model"] = self.cost_model().to_dict()
        return d
