"""Universe helpers (thin wrapper over lab point-in-time universes)."""

from __future__ import annotations

import os
from datetime import date

import yaml

from trading.lab.data.universes import UNIVERSES_DIR


def union_tickers(name: str, start: date | None = None, end: date | None = None) -> list[str]:
    """Union of all tickers appearing in any snapshot of `name` intersecting
    [start, end] (or all snapshots if unbounded)."""
    path = os.path.join(UNIVERSES_DIR, f"{name}.yaml")
    data = yaml.safe_load(open(path)) or {}
    members: set[str] = set()
    snaps = sorted(data.get("snapshots", []), key=lambda s: str(s["effective_date"]))
    for i, snap in enumerate(snaps):
        ed = date.fromisoformat(str(snap["effective_date"]))
        nxt = (
            date.fromisoformat(str(snaps[i + 1]["effective_date"]))
            if i + 1 < len(snaps)
            else date(9999, 12, 31)
        )
        if start and nxt <= start:
            continue
        if end and ed > end:
            continue
        members |= {str(t).upper() for t in snap.get("tickers", [])}
    return sorted(members)


def latest_tickers(name: str) -> list[str]:
    path = os.path.join(UNIVERSES_DIR, f"{name}.yaml")
    data = yaml.safe_load(open(path)) or {}
    snaps = sorted(data.get("snapshots", []), key=lambda s: str(s["effective_date"]))
    return sorted({str(t).upper() for t in snaps[-1].get("tickers", [])}) if snaps else []
