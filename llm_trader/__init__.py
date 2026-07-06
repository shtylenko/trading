"""trading.llm_trader — Warrior Trading momentum *entry scanner* + replay/sim tooling.

See README.md, SPEC.md, and SIMULATION_VIEWER_SPEC.md.
"""

from .config import ScanConfig
from .indicators import (
    enrich_1min_for_replay,
    normalize_to_et,
    prepare_detection_frame,
    session_vwap,
)
from .patterns import Entry, detect_entry, detect_from_frame

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
]


def __getattr__(name: str):
    if name in {"PositionEngine", "get_session_view", "list_sessions"}:
        from . import recorder

        val = getattr(recorder, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
