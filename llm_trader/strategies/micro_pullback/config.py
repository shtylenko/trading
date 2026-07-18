"""Config for same-day micro-pullback continuation (Ross / warrior phase-2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from trading.llm_trader.strategies.base import strategy_data_dir


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class MicroPullbackConfig:
    start: date = field(default_factory=lambda: date(2024, 1, 1))
    end: date = field(default_factory=lambda: date(2025, 12, 31))

    # Daily pre-screen (liquid strength day — not warrior penny gappers)
    price_min: float = 10.0
    price_max: float = 1_000.0
    gap_min_pct: float = 0.5
    gap_max_pct: float = 25.0
    avg_vol_min: float = 1_000_000.0
    rvol_min: float = 1.2
    rvol_lookback: int = 20

    # Impulse (morning leg up before the micro-pullback)
    impulse_min_bars: int = 2          # green/up bars to establish the runner
    impulse_min_pct: float = 0.35      # open→impulse high min %
    require_above_vwap: bool = True

    # Micro-pullback structure
    pb_min_bars: int = 1
    pb_max_bars: int = 3               # Ross: 1–2; allow 3 on 5m
    pb_max_depth_frac: float = 0.55    # pullback depth ≤ 55% of impulse range
    pb_must_hold_vwap: bool = True     # pullback lows stay ≥ VWAP

    # Entry
    entry_window_start: str = "09:45"
    entry_window_end: str = "14:00"
    require_green_break: bool = True   # signal bar green + close > pb high

    # Risk
    stop_buffer_pct: float = 0.05      # extra % under pullback low
    target1_r_mult: float = 1.0
    target2_r_mult: float = 2.0
    eod_exit_et: str = "15:55"
    fee_bps_one_way: float = 1.0
    slippage_bps_one_way: float = 2.0
    risk_budget: float = 100.0

    # Structural gate (Lance No Man's Land) — off by default; multi-year A/B
    # showed NML hurts this family. Do not enable on paper path.
    nml_gate: bool = False

    # Paper-book portfolio packaging (A/B-validated; port_v0.1.0)
    paper_portfolio: bool = True
    paper_max_concurrent: int = 3
    paper_max_per_day: int = 5

    # Universe profile: "liquid" (default multi-year gate) or "warrior"
    # (Ross small-cap gappers; current-snapshot float only — window ≤ ~2025–2026H1)
    universe_profile: str = "liquid"
    float_max: Optional[float] = None  # set by apply_warrior_profile; None = no float gate

    max_scan_failure_rate: float = 1.0
    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")
    db_path: Path = field(
        default_factory=lambda: strategy_data_dir("micro_pullback") / "entries.db"
    )

    def apply_warrior_profile(self) -> "MicroPullbackConfig":
        """Ross small-account gap screen + current-snapshot float caveat.

        Matches warrior ScanConfig defaults. Not multi-year-valid without PIT float.
        """
        self.universe_profile = "warrior"
        self.price_min = 2.0
        self.price_max = 20.0
        self.gap_min_pct = 5.0
        self.gap_max_pct = 100.0
        self.avg_vol_min = 500_000.0
        self.rvol_min = 2.0
        self.float_max = 20_000_000.0
        # Prefer separate DB so liquid multi-year seal stays intact
        self.db_path = strategy_data_dir("micro_pullback") / "entries_warrior.db"
        return self

    @classmethod
    def from_dict(cls, raw: dict) -> "MicroPullbackConfig":
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
