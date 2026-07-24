"""Scan configuration — parameters for the Warrior entry scanner.

Defaults encode Ross Cameron's documented thresholds for the small-account
profile (see ``library/ross_cameron/all_content_structured.md`` and ``SPEC.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

# Package data root (llm_trader/data/), shared caches + warrior entries.db.
# Not strategies/warrior/data — keep historical path for warrior entries.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class ScanConfig:
    """All knobs for one scan run."""

    # ── Date window (current-snapshot float ≈ historical over 2025–2026H1) ──
    start: date = field(default_factory=lambda: date(2025, 1, 1))
    end: date = field(default_factory=lambda: date(2026, 6, 30))

    # ── Stock selection (5 Pillars, small-account profile) ────────────────
    account_profile: str = "small"          # small | main
    price_min: float = 2.0
    price_max: float = 20.0
    gap_min_pct: float = 5.0                 # gap up vs prior close, percent
    gap_max_pct: float = 100.0               # guard: drop split/data-artifact gaps
    avg_vol_min: float = 500_000            # min 20d avg daily volume
    # Legacy field names retained for config compatibility. They represent a
    # *prior-day volume ratio*, not intraday relative volume.
    rvol_min: float = 2.0                    # min prior-day volume ratio
    rvol_lookback: int = 20                  # preceding sessions in the baseline
    float_max: Optional[float] = 20_000_000  # Cameron "hot"; None disables

    # ── Universe ──────────────────────────────────────────────────────────
    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE")

    # ── Intraday entry (ACD / ORB flat-top breakout) ──────────────────────
    entry_window_et: tuple[str, str] = ("07:00", "12:00")
    consolidation_min_bars: int = 2          # bars of pause before breakout
    vol_expansion_mult: float = 1.5          # breakout vol vs rolling avg
    require_above_vwap: bool = True
    vol_avg_window: int = 5                  # rolling window (prior bars) for vol expansion baseline in detection

    # ── Output ────────────────────────────────────────────────────────────
    db_path: Path = field(default_factory=lambda: DATA_DIR / "entries.db")
    # Optional append-only contemporaneous scanner-input capture. A ledger is
    # the required first artifact for a future frozen forward-shadow cohort.
    forward_shadow_ledger: Optional[Path] = None

    # ── Profiles ──────────────────────────────────────────────────────────
    def apply_profile(self, *, override_bounds: bool = True) -> "ScanConfig":
        """Adjust price band for the 'main' account profile."""
        if self.account_profile == "main" and override_bounds:
            self.price_min = 5.0
            self.price_max = 50.0
        return self

    # ── (de)serialization ─────────────────────────────────────────────────
    @classmethod
    def from_yaml(cls, path: str | Path) -> "ScanConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict in YAML file {path}, got {type(raw).__name__}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "ScanConfig":
        raw = dict(raw)
        if "start" in raw:
            raw["start"] = _as_date(raw["start"])
        if "end" in raw:
            raw["end"] = _as_date(raw["end"])
        if "exchanges" in raw and raw["exchanges"] is not None:
            raw["exchanges"] = tuple(raw["exchanges"])
        if "entry_window_et" in raw and raw["entry_window_et"] is not None:
            raw["entry_window_et"] = tuple(raw["entry_window_et"])
        if "db_path" in raw and raw["db_path"] is not None:
            raw["db_path"] = Path(raw["db_path"])
        if "forward_shadow_ledger" in raw and raw["forward_shadow_ledger"] is not None:
            raw["forward_shadow_ledger"] = Path(raw["forward_shadow_ledger"])
        known = set(cls.__dataclass_fields__)
        unknown = set(raw) - known
        if unknown:
            # a typo'd key would otherwise be silently dropped and the run would
            # quietly use the default for that threshold — fail loud instead.
            raise ValueError(
                f"unknown ScanConfig key(s): {sorted(unknown)}; "
                f"valid keys: {sorted(known)}"
            )
        cfg = cls(**raw)
        return cfg.apply_profile(override_bounds=not ("price_min" in raw or "price_max" in raw))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        d["exchanges"] = list(self.exchanges)
        d["entry_window_et"] = list(self.entry_window_et)
        d["db_path"] = str(self.db_path)
        if self.forward_shadow_ledger is not None:
            d["forward_shadow_ledger"] = str(self.forward_shadow_ledger)
        return d
