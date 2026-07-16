"""trading.llm_trader — multi-strategy entry scanner + sealed replay/sim tooling.

Default family is Warrior (Ross Cameron) momentum. Cup-and-handle swing and
future families register under ``strategies/``. See README.md, MULTI_STRATEGY.md,
SPEC.md, and SIMULATION_VIEWER_SPEC.md.
"""

from .config import ScanConfig
from .indicators import (
    atr,
    enrich_1min_for_replay,
    enrich_daily_for_replay,
    normalize_to_et,
    prepare_detection_frame,
    session_vwap,
    sma,
)
from .models import Entry
from .patterns import detect_entry, detect_from_frame

__all__ = [
    "ScanConfig",
    "Entry",
    "detect_entry",
    "detect_from_frame",
    "PositionEngine",
    "get_session_view",
    "list_sessions",
    "session_vwap",
    "normalize_to_et",
    "prepare_detection_frame",
    "enrich_1min_for_replay",
    "enrich_daily_for_replay",
    "sma",
    "atr",
]


def __getattr__(name: str):
    if name in {"PositionEngine", "get_session_view", "list_sessions"}:
        from . import recorder

        val = getattr(recorder, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
