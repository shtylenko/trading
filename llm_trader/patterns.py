"""Backward-compatible re-export of the Warrior ACD/ORB detector.

Canonical location: ``strategies/warrior/patterns.py``.
"""

from trading.llm_trader.models import Entry  # noqa: F401
from trading.llm_trader.strategies.warrior.patterns import (  # noqa: F401
    detect_entry,
    detect_from_frame,
)

__all__ = ["Entry", "detect_entry", "detect_from_frame"]
