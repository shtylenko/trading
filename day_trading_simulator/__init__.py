"""trading.day_trading_simulator — Warrior Trading momentum *entry scanner* + replay/sim tooling.

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
from .recorder import PositionEngine, get_session_view, list_sessions

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
