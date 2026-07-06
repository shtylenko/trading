"""A0 — symbol universe.

Enumerates US exchange-listed common stocks from the Finnhub symbol list and
caches them to ``data/universe_symbols.json``. Cameron trades exchange-listed
US equities (NASDAQ/NYSE/AMEX), explicitly avoiding OTC/foreign listings, so
OTC (mic ``OOTC``) and non-common types are excluded.

The Finnhub ``/stock/symbol`` endpoint returns a 302 redirect to a signed file
URL; ``requests`` follows it by default.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .config import DATA_DIR
from .fsutils import atomic_write_json

_FINNHUB_URL = "https://finnhub.io/api/v1/stock/symbol"
_CACHE = DATA_DIR / "universe_symbols.json"
_CACHE_TTL_S = 7 * 24 * 3600  # refresh weekly


def _finnhub_key() -> str:
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        raise RuntimeError(
            "FINNHUB_API_KEY not set. Export it (it lives in the repo-root .env)."
        )
    return key


def fetch_symbols(
    exchanges: tuple[str, ...] = ("XNAS", "XNYS", "XASE"),
    *,
    force: bool = False,
) -> list[str]:
    """Return sorted US exchange-listed common-stock tickers.

    Cached to ``data/universe_symbols.json`` (refreshed weekly or on ``force``).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cached = _read_cache(exchanges)
    if cached is not None and not force:
        return cached

    resp = requests.get(
        _FINNHUB_URL,
        params={"exchange": "US", "token": _finnhub_key()},
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json()

    keep = []
    wanted = set(exchanges)
    for r in rows:
        if r.get("type") != "Common Stock":
            continue
        if r.get("mic") not in wanted:
            continue
        sym = str(r.get("symbol", "")).strip().upper()
        # exclude symbols with class/warrant suffixes finnhub encodes with '.'
        if not sym or "." in sym:
            continue
        keep.append(sym)

    symbols = sorted(set(keep))
    _write_cache(exchanges, symbols)
    return symbols


def _read_cache(exchanges: tuple[str, ...]) -> list[str] | None:
    if not _CACHE.exists():
        return None
    try:
        blob = json.loads(_CACHE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if blob.get("exchanges") != list(exchanges):
        return None
    if time.time() - blob.get("fetched_at", 0) > _CACHE_TTL_S:
        return None
    return blob.get("symbols")


def _write_cache(exchanges: tuple[str, ...], symbols: list[str]) -> None:
    atomic_write_json(
        _CACHE,
        {
            "exchanges": list(exchanges),
            "fetched_at": time.time(),
            "symbols": symbols,
        },
    )
