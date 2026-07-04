#!/usr/bin/env python3
"""Build a ticker -> sector-ETF map for the liquid_pit universe.

Mirrors the universes/ philosophy: a static YAML artifact, built once, read
deterministically at backtest time. Each liquid_pit ticker is resolved to its
GICS sector via yfinance and mapped to the matching SPDR sector ETF, which a
release (d12) uses as a per-sector trend proxy.

CAVEATS (documented for honesty, baked into the map header):
  - yfinance returns the ticker's CURRENT sector classification, not a
    point-in-time one. Sectors are stable enough that this is low look-ahead
    risk, but it is a current-snapshot dependency, not strictly PIT.
  - Tickers yfinance cannot classify are left unmapped; the consuming release
    must fall back gracefully (d12 falls back to the SPY market gate).

Resumable: re-running skips tickers already in the output file. Saves
incrementally so an interrupted run loses nothing.

Usage:
    python3 -m trading.lab.scripts.build_sector_map
"""

from __future__ import annotations

from pathlib import Path

import yaml

UNIVERSES_DIR = Path(__file__).resolve().parent.parent / "universes"
SRC_UNIVERSE = UNIVERSES_DIR / "liquid_pit.yaml"
OUT_PATH = UNIVERSES_DIR / "sector_map.yaml"

# yfinance GICS-ish sector string -> SPDR select-sector ETF.
SECTOR_TO_ETF = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financial": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

SAVE_EVERY = 25


def _load_universe_union() -> list[str]:
    data = yaml.safe_load(SRC_UNIVERSE.read_text())
    union: set[str] = set()
    for snap in data.get("snapshots", []):
        union.update(snap.get("tickers", []))
    return sorted(union)


def _load_existing() -> dict:
    if not OUT_PATH.exists():
        return {}
    data = yaml.safe_load(OUT_PATH.read_text()) or {}
    return data.get("map", {})


def _save(mapping: dict, total: int, resolved: int) -> None:
    header = {
        "name": "sector_map",
        "description": (
            "Ticker -> SPDR sector ETF for the liquid_pit universe, built from "
            "yfinance CURRENT sector classification (not point-in-time; sectors "
            "are stable so look-ahead risk is low). Unmapped tickers fall back "
            "to the SPY market gate in the consuming release."
        ),
        "source": "yfinance .info['sector']",
        "etfs": sorted(set(SECTOR_TO_ETF.values())),
        "ticker_count": total,
        "resolved_count": resolved,
        "map": dict(sorted(mapping.items())),
    }
    OUT_PATH.write_text(yaml.safe_dump(header, sort_keys=False, default_flow_style=False))


def main() -> None:
    import yfinance as yf

    tickers = _load_universe_union()
    mapping = _load_existing()
    todo = [t for t in tickers if t not in mapping]
    print(f"liquid_pit union: {len(tickers)} | already mapped: {len(mapping)} | to do: {len(todo)}")

    for i, ticker in enumerate(todo, start=1):
        etf = None
        try:
            info = yf.Ticker(ticker).info
            sector = (info or {}).get("sector")
            if sector:
                etf = SECTOR_TO_ETF.get(sector.strip())
        except Exception as exc:  # network / parse / delisted
            print(f"  {ticker}: lookup failed ({type(exc).__name__})")
        # Record even a None so a resume does not retry the unmappable forever;
        # None is written as an explicit miss the release treats as "fallback".
        mapping[ticker] = etf
        if i % SAVE_EVERY == 0:
            resolved = sum(1 for v in mapping.values() if v)
            _save(mapping, len(tickers), resolved)
            print(f"  [{i}/{len(todo)}] saved · resolved {resolved}/{len(mapping)}")

    resolved = sum(1 for v in mapping.values() if v)
    _save(mapping, len(tickers), resolved)
    print(f"DONE · mapped {resolved}/{len(mapping)} tickers to a sector ETF -> {OUT_PATH}")


if __name__ == "__main__":
    main()
