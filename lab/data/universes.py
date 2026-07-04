from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml

UNIVERSES_DIR = Path(__file__).resolve().parent.parent / "universes"

# Parsed-YAML cache keyed by (path, mtime). Broad universes are ~300 KB of
# YAML; testset runs resolve the universe once per trading day, and without
# this cache a 250-day backtest spends minutes re-parsing the same file.
_SNAPSHOT_CACHE: dict[tuple[str, float], list[tuple[date, frozenset]]] = {}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_snapshots(path: Path) -> list[tuple[date, frozenset]]:
    key = (str(path), path.stat().st_mtime)
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None:
        return cached

    data = yaml.safe_load(path.read_text()) or {}
    snapshots = []
    for snap in data.get("snapshots", []):
        snapshots.append(
            (
                _parse_date(snap["effective_date"]),
                frozenset(str(t).upper() for t in snap.get("tickers", [])),
            )
        )
    snapshots.sort(key=lambda x: x[0])
    # drop stale mtimes for the same path
    for k in [k for k in _SNAPSHOT_CACHE if k[0] == str(path)]:
        del _SNAPSHOT_CACHE[k]
    _SNAPSHOT_CACHE[key] = snapshots
    return snapshots


def load_universe_tickers(name: str, trade_date: date) -> list[str]:
    path = UNIVERSES_DIR / f"{name}.yaml"
    if not path.exists():
        path = UNIVERSES_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Universe '{name}' not found in {UNIVERSES_DIR}")

    snapshots = _load_snapshots(path)
    eligible = [s for s in snapshots if s[0] <= trade_date]
    if not eligible:
        return []
    return sorted(eligible[-1][1])
