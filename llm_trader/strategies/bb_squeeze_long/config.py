"""Config for same-day Bollinger squeeze → long expansion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class BbSqueezeLongConfig:
    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    # Daily pre-screen (liquid in-play)
    price_min: float = 10.0
    price_max: float = 1_000.0
    avg_vol_min: float = 1_000_000.0
    rvol_min: float = 1.15
    rvol_lookback: int = 20
    # Prefer non-collapse days (optional mild gap floor)
    gap_min_pct: float = -2.0
    gap_max_pct: float = 20.0

    # Bollinger
    bb_period: int = 20
    bb_std: float = 2.0
    # Squeeze: bandwidth percentile rank over trailing lookback ≤ this.
    # Lookback 36 (~3h of 5m) keeps morning/midday in range after BB warm-up;
    # 48 + rigid bb+lb start previously pushed first candidate past 14:30 (n=0).
    squeeze_lookback: int = 36
    squeeze_pctile_max: float = 0.25    # bottom quartile width
    # Expansion entry window
    entry_window_start: str = "09:45"
    entry_window_end: str = "14:30"
    require_green: bool = True
    require_width_expanding: bool = True
    require_close_above_mid: bool = True
    # Optional: close above prior bar high
    require_close_above_prior_high: bool = True

    # Risk
    stop_lookback_bars: int = 6         # stop under min low of last N bars
    stop_buffer_pct: float = 0.05       # extra % under stop structure
    target1_r_mult: float = 1.0
    target2_r_mult: float = 2.0
    eod_exit_et: str = "15:55"
    fee_bps_one_way: float = 1.0
    slippage_bps_one_way: float = 2.0
    risk_budget: float = 100.0

    max_scan_failure_rate: float = 1.0
    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")
    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("bb_squeeze_long") / "entries.db"
    )

    @classmethod
    def from_dict(cls, raw: dict) -> "BbSqueezeLongConfig":
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
