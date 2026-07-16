"""Warrior Trading (Ross Cameron) momentum day-trade family.

Layout (symmetric with ``strategies/cup_handle/``):

```
strategies/warrior/
  config.py / screen.py / patterns.py / runner.py
  SPEC.md
  skills/
    skill_versions.json
    trade_skills/<version>.md
    CHANGELOG.md  RULE_TRACE.md  MAINTAINING.md  IMPROVING.md
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from trading.llm_trader.strategies.base import DATA_DIR, HorizonSpec, RiskDefaults

_PKG = Path(__file__).resolve().parent


class WarriorStrategy:
    id = "warrior"
    name = "Warrior Trading momentum (Ross Cameron)"
    description = (
        "Gap-up low-float high-RVOL small-cap morning breakouts "
        "(ACD/ORB) with same-day management."
    )
    horizon = HorizonSpec(
        kind="intraday",
        bar_resolution="1min",
        same_day_only=True,
        max_hold_bars=None,
        default_from_open=True,
    )
    risk = RiskDefaults(profile="small", risk_budget=40.0, buying_power=12_000.0)

    def skills_dir(self) -> Path:
        return _PKG / "skills"

    def registry_path(self) -> Path:
        return self.skills_dir() / "skill_versions.json"

    def trade_skills_dir(self) -> Path:
        return self.skills_dir() / "trade_skills"

    def default_db_path(self) -> Path:
        return DATA_DIR / "entries.db"

    def default_scan_config(self):
        from .config import ScanConfig

        return ScanConfig()

    def config_from_dict(self, raw: dict):
        from .config import ScanConfig

        return ScanConfig.from_dict(raw)

    def run_scan(
        self,
        cfg: Any,
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


def risk_for_profile(profile: str) -> RiskDefaults:
    if profile == "main":
        return RiskDefaults(profile="main", risk_budget=1350.0, buying_power=100_000.0)
    return RiskDefaults(profile="small", risk_budget=40.0, buying_power=12_000.0)
