"""Backward-compatible re-export of the Warrior scan config.

Canonical location: ``strategies/warrior/config.py``.
Platform code that only needs ``DATA_DIR`` may import from here.
"""

from pathlib import Path

# Defined first (before warrior imports) so importers of DATA_DIR never hit a cycle.
DATA_DIR = Path(__file__).resolve().parent / "data"

from trading.llm_trader.strategies.warrior.config import ScanConfig  # noqa: E402, F401

__all__ = ["DATA_DIR", "ScanConfig"]
