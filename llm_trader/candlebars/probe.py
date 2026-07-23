"""Read-only probe of the candlebar library against cached Warrior 1-minute bars.

This intentionally reads the parquet cache directly through ``read_bars``.  It
does not call ``fetch_bars`` and therefore cannot download, refresh, or mutate
market data.  Results are exploratory pattern counts, not performance claims.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from trading.marketdata.storage import read_bars

from .registry import detect_patterns
from .types import PatternEvent


ET = ZoneInfo("America/New_York")


def _cached_rth_bars(ticker: str, day: date):
    start = datetime.combine(day, time(9, 30), tzinfo=ET)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=ET)
    bars = read_bars(ticker, "1min", start=start, end=end, session="rth", adjustment="raw")
    if bars.empty:
        return bars
    bars = bars[bars.index.date == day]
    return bars.between_time("09:30", "16:00", inclusive="left")


def _event_record(event: PatternEvent, *, ticker: str, day: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "date": day,
        "time_et": event.timestamp.strftime("%H:%M"),
        "score": round(event.score, 4),
        "evidence": dict(event.evidence),
    }


def probe_testset(path: str | Path, *, limit: int | None = None, samples_per_pattern: int = 3) -> dict:
    """Return pattern counts and small event samples for cached test-set sessions."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    setups = payload.get("setups")
    if not isinstance(setups, list):
        raise ValueError(f"test set {path} lacks a setups list")
    if limit is not None:
        setups = setups[:limit]

    counts: Counter[str] = Counter()
    sessions_by_pattern: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    loaded = 0
    missing: list[dict[str, str]] = []
    total_bars = 0

    for setup in setups:
        ticker = str(setup["ticker"]).upper()
        day_text = str(setup["date"])
        bars = _cached_rth_bars(ticker, date.fromisoformat(day_text))
        if bars.empty:
            missing.append({"ticker": ticker, "date": day_text})
            continue
        loaded += 1
        total_bars += len(bars)
        seen: set[str] = set()
        for event in detect_patterns(bars):
            counts[event.pattern] += 1
            seen.add(event.pattern)
            if len(samples[event.pattern]) < samples_per_pattern:
                samples[event.pattern].append(_event_record(event, ticker=ticker, day=day_text))
        for name in seen:
            sessions_by_pattern[name] += 1

    return {
        "source": "cached marketdata 1min/rth/raw parquet only",
        "testset": str(path),
        "requested_sessions": len(setups),
        "loaded_sessions": loaded,
        "missing_sessions": len(missing),
        "total_bars": total_bars,
        "patterns": {
            name: {
                "events": counts[name],
                "sessions": sessions_by_pattern[name],
                "samples": samples[name],
            }
            for name in sorted(counts)
        },
        "missing_sample": missing[:10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testset", type=Path, required=True, help="Warrior test-set JSON")
    parser.add_argument("--limit", type=int, default=None, help="cap sessions (default: all)")
    parser.add_argument("--samples", type=int, default=3, help="sample events per pattern")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.samples < 1:
        parser.error("--samples must be positive")
    print(json.dumps(probe_testset(args.testset, limit=args.limit, samples_per_pattern=args.samples), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

