"""A2 — float gate.

Cameron's central filter is a low share *float* (< 20M "hot", < 5M "cold").
marketdata has no float, so we read the current ``floatShares`` snapshot from
yfinance and cache it per ticker in ``data/float_cache.json``.

Caveat (see SPEC §2): this is a *current* snapshot, not point-in-time — valid as
an approximation only over the recent window (2025–2026H1) the scanner targets.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import DATA_DIR
from .fsutils import atomic_write_json, file_lock

_CACHE = DATA_DIR / "float_cache.json"
_CACHE_TTL_S = 30 * 24 * 3600  # floats drift slowly; refresh monthly
_MISS_TTL_S = 3 * 24 * 3600    # retry unknowns sooner


class FloatCache:
    """Lazy, persistent per-ticker float lookup."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        try:
            self._data = json.loads(_CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._data = {}
        self._dirty = False

    def get(self, ticker: str) -> Optional[float]:
        """Float shares for ``ticker`` (None if unknown). Cached."""
        return self.snapshot(ticker).get("value")

    def snapshot(self, ticker: str, *, force_refresh: bool = False) -> dict:
        """Return the retrieval provenance alongside the current float value.

        This data is deliberately labelled as a *retrieval-time snapshot*, not
        an as-of-date float.  Historical scanner rows must never be promoted as
        point-in-time research merely because a float threshold was applied.
        """
        ticker = ticker.upper()
        entry = self._data.get(ticker)
        now = time.time()
        if entry is not None and not force_refresh:
            fresh_ttl = _MISS_TTL_S if entry.get("value") is None else _CACHE_TTL_S
            if now - entry.get("ts", 0) < fresh_ttl:
                return self._snapshot_record(entry)

        value, source = _fetch_float(ticker)
        self._data[ticker] = {"value": value, "ts": now, "source": source}
        self._dirty = True
        return self._snapshot_record(self._data[ticker])

    @staticmethod
    def _snapshot_record(entry: dict) -> dict:
        """Normalize legacy cache rows into an explicit research record."""
        ts = entry.get("ts")
        fetched_at = None
        if isinstance(ts, (int, float)):
            fetched_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        source = entry.get("source") or "unknown"
        return {
            "value": entry.get("value"),
            "source": source,
            "fetched_at": fetched_at,
            "as_of": "retrieval_time_current_snapshot",
            "point_in_time": False,
            "fallback_used": source == "shares_outstanding",
        }

    def passes(self, ticker: str, float_max: Optional[float]) -> bool:
        """True if ``ticker`` is within ``float_max`` (None ⇒ no gate).

        Unknown float is treated as **fail** when a gate is active — Cameron
        will not trade a name he can't confirm is low-float.
        """
        if float_max is None:
            return True
        value = self.snapshot(ticker).get("value")
        if value is None:
            return False
        return value < float_max

    def flush(self) -> None:
        if not self._dirty:
            return
        with file_lock(_CACHE):
            disk_data = {}
            try:
                disk_data = json.loads(_CACHE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                disk_data = {}
            disk_data.update(self._data)
            self._data = disk_data
            atomic_write_json(_CACHE, self._data)
            self._dirty = False


def _fetch_float(ticker: str) -> tuple[Optional[float], Optional[str]]:
    """Return ``(value, source)`` where source records which yfinance field was
    used: ``"float"`` (true floatShares) or ``"shares_outstanding"`` (a fallback
    that overstates the tradeable float — the gate stays conservative, but the
    provenance is now recorded rather than lost)."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        fval = info.get("floatShares")
        if fval:
            return float(fval), "float"
        sval = info.get("sharesOutstanding")
        if sval:
            return float(sval), "shares_outstanding"
        return None, None
    except Exception:
        return None, None
