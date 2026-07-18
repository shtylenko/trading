"""Same-day Bollinger squeeze → long expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trading.llm_trader.strategies.base import DATA_DIR, HorizonSpec, RiskDefaults

_PKG = Path(__file__).resolve().parent


class BbSqueezeLongStrategy:
    id = "bb_squeeze_long"
    name = "BB squeeze long (same-day)"
    description = (
        "Short-hold long: Bollinger bandwidth contracts (squeeze), then long on "
        "expansion with green reclaim of mid-band; stop under structure; flat EOD."
    )
    horizon = HorizonSpec(
        kind="intraday",
        bar_resolution="5min",
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
        return DATA_DIR / "bb_squeeze_long" / "entries.db"

    def default_scan_config(self):
        from .config import BbSqueezeLongConfig

        return BbSqueezeLongConfig(db_path=self.default_db_path())

    def config_from_dict(self, raw: dict):
        from .config import BbSqueezeLongConfig

        return BbSqueezeLongConfig.from_dict(raw)

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
