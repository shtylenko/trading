"""Breakout first-pullback swing family (Lance swing #2)."""

from __future__ import annotations

from pathlib import Path

from trading.llm_trader.strategies.base import HorizonSpec, RiskDefaults, strategy_data_dir

_PKG = Path(__file__).resolve().parent


class BreakoutFirstPullbackStrategy:
    id = "breakout_first_pullback"
    name = "Breakout first pullback"
    description = (
        "Multi-day long-only: multi-week base breakout on volume, then buy the "
        "first pullback that holds the breakout level as support (Lance swing #2)."
    )
    horizon = HorizonSpec(
        kind="multi_day",
        bar_resolution="1day",
        same_day_only=False,
        max_hold_bars=25,
        default_from_open=True,
    )
    risk = RiskDefaults(profile="swing", risk_budget=500.0, buying_power=50_000.0)

    def skills_dir(self) -> Path:
        return _PKG / "skills"

    def registry_path(self) -> Path:
        return self.skills_dir() / "skill_versions.json"

    def trade_skills_dir(self) -> Path:
        return self.skills_dir() / "trade_skills"

    def default_db_path(self) -> Path:
        return strategy_data_dir(self.id) / "entries.db"

    def default_scan_config(self):
        from .config import BreakoutFirstPullbackConfig

        return BreakoutFirstPullbackConfig(db_path=self.default_db_path())

    def config_from_dict(self, raw: dict):
        from .config import BreakoutFirstPullbackConfig

        return BreakoutFirstPullbackConfig.from_dict(raw)

    def run_scan(
        self,
        cfg,
        *,
        symbols: list[str] | None = None,
        max_symbols: int | None = None,
        progress_every: int = 100,
    ):
        from .runner import run_scan as _run_scan

        return _run_scan(
            cfg,
            symbols=symbols,
            max_symbols=max_symbols,
            progress_every=progress_every,
            strategy_id=self.id,
        )
