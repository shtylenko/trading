"""Portfolio concurrency overlay for short-hold research sims.

Structural risk control: even if each single-name trade has a thin edge, unlimited
same-day concurrency is not how a desk would size. Pre-registered limits for A/B.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class PortfolioLimits:
    max_concurrent: int = 3          # open positions at once (by entry clock)
    max_per_day: int = 5             # new entries per calendar day
    # When oversubscribed at the same timestamp, keep higher rvol then gap
    version: str = "port_v0.1.0"


@dataclass
class TimedTrade:
    """Minimal trade handle for portfolio filtering."""

    ticker: str
    day: date
    entry_time: str                  # HH:MM
    exit_time: str                   # HH:MM
    r_multiple: float
    rvol: float = 0.0
    gap_pct: float = 0.0
    meta: Optional[dict[str, Any]] = None


def _tmin(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def apply_portfolio_limits(
    trades: Sequence[TimedTrade],
    limits: Optional[PortfolioLimits] = None,
) -> tuple[list[TimedTrade], list[TimedTrade]]:
    """Greedy chronological admission under concurrency + daily caps.

    Returns ``(kept, rejected)``. Sort key: day, entry_time, then -rvol, -gap.
    A position occupies capacity from entry_time until exit_time (inclusive start,
    exclusive end for concurrency checks at the next fill).
    """
    limits = limits or PortfolioLimits()
    ordered = sorted(
        trades,
        key=lambda t: (t.day, _tmin(t.entry_time), -float(t.rvol or 0), -float(t.gap_pct or 0)),
    )
    kept: list[TimedTrade] = []
    rejected: list[TimedTrade] = []
    # open: list of (exit_minute, trade) — same calendar day only
    open_pos: list[tuple[int, TimedTrade]] = []
    day_counts: dict[date, int] = {}
    cur_day: date | None = None

    for tr in ordered:
        # Overnight flat: short-hold book does not carry positions across days
        if cur_day is None or tr.day != cur_day:
            open_pos = []
            cur_day = tr.day
        et = _tmin(tr.entry_time)
        open_pos = [(x, t) for x, t in open_pos if x > et]
        dcount = day_counts.get(tr.day, 0)
        if dcount >= limits.max_per_day:
            rejected.append(tr)
            continue
        if len(open_pos) >= limits.max_concurrent:
            rejected.append(tr)
            continue
        kept.append(tr)
        day_counts[tr.day] = dcount + 1
        open_pos.append((_tmin(tr.exit_time), tr))

    return kept, rejected
