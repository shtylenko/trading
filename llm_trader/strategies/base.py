"""Strategy family contract.

Implementations are thin adapters: they own config construction, the scan
pipeline entry points, skill-path resolution, and risk/horizon defaults.
Detection math lives in family modules (or top-level Warrior modules for
backward compatibility).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

# llm_trader/data/ — defined here to avoid circular imports with top-level config.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class HorizonSpec:
    """How a family replays and holds risk over time."""

    kind: str  # "intraday" | "multi_day"
    bar_resolution: str  # "1min" | "1day"
    same_day_only: bool
    max_hold_bars: Optional[int] = None  # bars after entry; None = no hard cap
    default_from_open: bool = True


@dataclass(frozen=True)
class RiskDefaults:
    """Per-trade risk and buying power defaults for recorder init."""

    profile: str  # "small" | "main" | "swing"
    risk_budget: float
    buying_power: float


@runtime_checkable
class StrategySpec(Protocol):
    id: str
    name: str
    description: str
    horizon: HorizonSpec
    risk: RiskDefaults

    def skills_dir(self) -> Path:
        """Directory holding ``trade_skills/`` + ``skill_versions.json``."""
        ...

    def registry_path(self) -> Path:
        ...

    def trade_skills_dir(self) -> Path:
        ...

    def default_db_path(self) -> Path:
        ...

    def default_scan_config(self) -> Any:
        ...

    def config_from_dict(self, raw: dict) -> Any:
        ...

    def run_scan(
        self,
        cfg: Any,
        *,
        symbols: list[str] | None = None,
        max_symbols: int | None = None,
        progress_every: int = 100,
    ) -> Any:
        ...


def strategy_data_dir(strategy_id: str) -> Path:
    """Per-strategy data root under ``llm_trader/data/<strategy_id>/``."""
    return DATA_DIR / strategy_id
