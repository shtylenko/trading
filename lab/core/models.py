from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd


@dataclass
class ExecutionConfig:
    """Execution-cost model for trade simulation.

    Slippage semantics: ``entry_slippage_bps`` / ``exit_slippage_bps`` are
    baked into the simulated fill prices, so ``gross_pnl_pct`` is already
    net of slippage. ``slippage_pct`` on a SimulatedTrade is informational
    only — do NOT subtract it again (``pnl_pct = gross_pnl_pct − fees_pct``).

    ``stop_limit_offset_dollars`` is an absolute price offset in dollars
    added to the trigger for stop-limit entries.
    """

    entry_slippage_bps: float = 2.0
    exit_slippage_bps: float = 2.0
    fees_bps_per_side: float = 0.5
    stop_limit_offset_dollars: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "entry_slippage_bps": self.entry_slippage_bps,
            "exit_slippage_bps": self.exit_slippage_bps,
            "fees_bps_per_side": self.fees_bps_per_side,
            "stop_limit_offset_dollars": self.stop_limit_offset_dollars,
        }


@dataclass
class StrategyContext:
    trade_date: date
    release_id: str
    testset: str | None
    bars_5m: dict[str, pd.DataFrame]
    daily: dict[str, pd.DataFrame]
    extended_1m: dict[str, pd.DataFrame] = field(default_factory=dict)
    bars_1m: dict[str, pd.DataFrame] = field(default_factory=dict)
    historical_5m: dict[str, pd.DataFrame] = field(default_factory=dict)
    spy_5m: pd.DataFrame | None = None
    spy_daily: pd.DataFrame | None = None
    # Extra non-traded daily series (sector ETFs, breadth proxies) hydrated by
    # the runner when a release declares extra_daily_symbols. Keyed by symbol.
    extra_daily: dict[str, pd.DataFrame] = field(default_factory=dict)


@dataclass
class Candidate:
    ticker: str
    rank: int | None = None
    score: float | None = None
    reason: str = ""
    features: dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    ticker: str
    setup_type: str
    signal_time: datetime
    entry_trigger: float
    stop_price: float
    target_price: float | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def risk_per_share(self) -> float:
        return max(0.0, self.entry_trigger - self.stop_price)


@dataclass
class SimulatedTrade:
    ticker: str
    setup_type: str
    direction: str
    entry_time: datetime | None
    entry_price: float | None
    exit_time: datetime | None
    exit_price: float | None
    exit_reason: str
    pnl_pct: float
    gross_pnl_pct: float
    realized_r: float | None
    mfe_pct: float | None
    mae_pct: float | None
    fees_pct: float
    slippage_pct: float
    context: dict[str, Any] = field(default_factory=dict)
