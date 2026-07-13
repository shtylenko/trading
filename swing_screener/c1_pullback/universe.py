"""Point-in-time universe helpers for C1 screens."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

from trading.lab.data.universes import UNIVERSES_DIR, load_universe_tickers


def universe_path(name: str) -> Path:
    path = UNIVERSES_DIR / f"{name}.yaml"
    if not path.exists():
        path = UNIVERSES_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Universe '{name}' not found in {UNIVERSES_DIR}")
    return path


@lru_cache(maxsize=8)
def _snapshot_table(name: str) -> list[tuple[date, frozenset[str]]]:
    path = universe_path(name)
    data = yaml.safe_load(path.read_text()) or {}
    snaps: list[tuple[date, frozenset[str]]] = []
    for snap in data.get("snapshots", []):
        ed = date.fromisoformat(str(snap["effective_date"]))
        tickers = frozenset(str(t).upper() for t in snap.get("tickers", []))
        snaps.append((ed, tickers))
    snaps.sort(key=lambda x: x[0])
    return snaps


def tickers_on(name: str, trade_date: date) -> list[str]:
    """PIT members on trade_date (latest snapshot with effective_date <= d)."""
    return load_universe_tickers(name, trade_date)


def ticker_union(
    name: str,
    start: date,
    end: date,
    *,
    pad_before: timedelta = timedelta(days=0),
) -> list[str]:
    """All tickers that appear in any snapshot active during [start, end].

    A snapshot is active from its effective_date until the day before the next
    snapshot (or forever for the last). We include any snapshot whose active
    window intersects [start - pad, end].
    """
    snaps = _snapshot_table(name)
    if not snaps:
        return []
    lo = start - pad_before
    hi = end
    members: set[str] = set()
    for i, (ed, tickers) in enumerate(snaps):
        next_ed = snaps[i + 1][0] if i + 1 < len(snaps) else date(9999, 12, 31)
        # active on [ed, next_ed)
        if next_ed <= lo or ed > hi:
            continue
        members |= set(tickers)
    return sorted(members)


def membership_asof(name: str, trade_date: date) -> frozenset[str]:
    snaps = _snapshot_table(name)
    eligible = [s for s in snaps if s[0] <= trade_date]
    if not eligible:
        return frozenset()
    return eligible[-1][1]
