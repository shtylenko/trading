"""Backward-compatible re-export of the Warrior gap screen.

Canonical location: ``strategies/warrior/screen.py``.
"""

from trading.llm_trader.strategies.warrior.screen import (  # noqa: F401
    GapCandidate,
    screen_ticker,
)

__all__ = ["GapCandidate", "screen_ticker"]
