#!/usr/bin/env python3
"""Retry the unmapped (None) entries in sector_map.yaml, gently throttled.

The bulk build hits yfinance rate limits in its back half; this re-fetches only
the misses at 2s/call so the burst limit stays clear, and only overwrites an
entry on success (a still-rate-limited or genuinely-missing ticker is left as
None for a later pass). Saves incrementally.
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from trading.lab.scripts.build_sector_map import SECTOR_TO_ETF, _save

OUT = Path(__file__).resolve().parent.parent / "universes" / "sector_map.yaml"
THROTTLE_S = 2.0


def main() -> None:
    import yfinance as yf

    data = yaml.safe_load(OUT.read_text())
    m = data["map"]
    misses = [t for t, v in m.items() if not v]
    print(f"retrying {len(misses)} unmapped at {THROTTLE_S}s/call")

    fixed = rate = miss = 0
    for i, t in enumerate(misses, 1):
        try:
            info = yf.Ticker(t).info or {}
            sec = info.get("sector")
            etf = SECTOR_TO_ETF.get(sec.strip()) if sec else None
            if etf:
                m[t] = etf
                fixed += 1
            else:
                miss += 1
        except Exception as exc:
            if "RateLimit" in type(exc).__name__:
                rate += 1
            else:
                miss += 1
        time.sleep(THROTTLE_S)
        if i % 25 == 0:
            _save(m, len(m), sum(1 for v in m.values() if v))
            print(f"  {i}/{len(misses)} · fixed {fixed} · rate-limited {rate} · real-miss {miss}")

    resolved = sum(1 for v in m.values() if v)
    _save(m, len(m), resolved)
    print(f"DONE · fixed {fixed} · still rate-limited {rate} · real-miss {miss} "
          f"· resolved {resolved}/{len(m)} ({100*resolved/len(m):.1f}%)")


if __name__ == "__main__":
    main()
