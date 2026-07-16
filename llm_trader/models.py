"""Shared domain models for llm_trader scanners and stores.

Both Warrior (intraday momentum) and multi-day families emit the same
:class:`Entry` shape. Family-specific fields go in ``features`` so the store
schema stays stable across strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional


@dataclass
class Entry:
    """One primary setup the scanner would have flagged.

    Uniqueness is ``(strategy, ticker, date, pattern)`` — see ``store.setup_id``.
    """

    ticker: str
    day: date
    time_et: str  # "HH:MM" (for daily strategies, often "09:30" or "16:00")
    pattern: str
    entry_px: float
    bar_close: float
    reason: str
    strategy: str = "warrior"
    # Warrior-centric optional fields (nullable for other families)
    gap_pct: Optional[float] = None
    rvol: Optional[float] = None
    float_shares: Optional[float] = None
    bar_vol_mult: Optional[float] = None
    # Family-specific structured payload (ATR, targets, SMAs, cup metrics, …)
    features: dict[str, Any] = field(default_factory=dict)
