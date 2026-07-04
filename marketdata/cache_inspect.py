#!/usr/bin/env python3
"""
Cache Inspector — comprehensive health and metrics report for the Hive-partitioned
Parquet market-data cache.

Usage:
    python3 -m trading.marketdata.cache_inspect          # full report
    python3 -m trading.marketdata.cache_inspect --ticker AAPL  # single ticker
    python3 -m trading.marketdata.cache_inspect --summary-only  # aggregate only
    python3 -m trading.marketdata.cache_inspect --holes          # gap report
    python3 -m trading.marketdata.cache_inspect --top 20         # top-N by bars

Output sections:
    1. AGGREGATE OVERVIEW      — per-timeframe totals
    2. TOP TICKERS             — biggest / sparsest tickers ranked
    3. YEAR COVERAGE MATRIX    — how many tickers have each year×timeframe
    4. PROVIDER DISTRIBUTION   — alpaca vs yfinance bars
    5. DATA FRESHNESS          — staleness distribution
    6. PER-TICKER DETAIL (if not --summary-only)
    7. CROSS-TIMEFRAME GAPS    — daily but no intraday, etc.
    8. HEALTH CHECKS           — lock files, meta mismatches, empty partitions
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Config ──────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "data"
TIMEFRAMES = ["1min", "5min", "1day"]  # 15min doesn't exist yet

# Intraday: data/{tf}/{TICKER}/session=rth/adjustment={raw|split}/year={Y}/month={M}/data.parquet
# Daily:    data/1day/{TICKER}/session=rth/adjustment={raw|split}/year={Y}/data.parquet
# Meta:     data/{tf}/{TICKER}/session=rth/adjustment={adj}/meta.json
# Locks:    data/.locks/{TICKER}_{tf}_{session}_{adj}.lock


# ── Helpers ─────────────────────────────────────────────────────────────────────

def format_bytes(n: int) -> str:
    f: float = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(f) < 1024.0:
            return f"{f:.1f} {unit}"
        f /= 1024.0
    return f"{f:.1f} PB"


def format_bars(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def parse_iso(ts_str: str | None) -> datetime | None:
    """Parse ISO timestamp string, handling various formats."""
    if not ts_str:
        return None
    try:
        # Handle '2026-06-11T19:23:07.110824+00:00'
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        pass
    try:
        # Handle '2026-06-05T19:59:00+00:00'
        ts_str_clean = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str_clean)
    except (ValueError, TypeError):
        return None


def get_disk_usage(path: Path) -> int:
    """Return total bytes for all data.parquet files under path (or single dir)."""
    total = 0
    try:
        for p in path.rglob("data.parquet"):
            try:
                total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


# ── Core data gathering ─────────────────────────────────────────────────────────

def gather_all_meta() -> Dict[str, Dict[str, Dict]]:
    """Walk DATA_DIR and collect every meta.json, keyed by (timeframe, ticker)."""
    result: Dict[str, Dict[str, Dict]] = {tf: {} for tf in TIMEFRAMES}

    for tf in TIMEFRAMES:
        tf_dir = DATA_DIR / tf
        if not tf_dir.is_dir():
            continue

        for ticker_dir in sorted(tf_dir.iterdir()):
            if not ticker_dir.is_dir() or ticker_dir.name.startswith("."):
                continue
            ticker = ticker_dir.name

            # Look for session=rth/adjustment=raw/meta.json
            for adj_dir in ticker_dir.glob("session=rth/adjustment=*/meta.json"):
                try:
                    with open(adj_dir) as f:
                        meta = json.load(f)
                    result[tf][ticker] = meta
                except (json.JSONDecodeError, OSError):
                    pass

    return result


def collect_ticker_stats(
    all_meta: dict,
) -> Dict[str, Dict[str, dict]]:
    """Build per-ticker stats from meta.json data."""
    # ticker -> {tf: {years, total_rows, earliest, latest, n_partitions, coverage_days, ...}}
    stats: Dict[str, Dict[str, dict]] = defaultdict(dict)

    for tf in TIMEFRAMES:
        for ticker, meta in all_meta.get(tf, {}).items():
            partitions_val = meta.get("partitions", [])
            n_partitions = len(partitions_val) if isinstance(partitions_val, list) else int(partitions_val)

            s = {
                "total_rows": meta.get("total_rows", 0),
                "partitions": n_partitions,
                "earliest": meta.get("earliest"),
                "latest": meta.get("latest"),
                "last_updated": meta.get("last_updated"),
                "coverage_days": len(meta.get("coverage", {})),
                "negative_cache": len(meta.get("negative_cache", {})),
            }

            # Figure out years covered from coverage dates or partitions list
            years = set()
            if "coverage" in meta:
                for date_str in meta["coverage"]:
                    years.add(date_str[:4])
            elif "partitions" in meta:
                for p in meta["partitions"]:
                    years.add(p.get("year", ""))
            s["years"] = sorted(years)
            s["year_count"] = len(years)

            stats[ticker][tf] = s

    return stats


def get_provider_distribution(
    tf: str, tickers: List[str], sample: int = 30
) -> Dict[str, int]:
    """Sample parquet files to estimate provider distribution."""
    import pandas as pd

    provider_counts: Dict[str, int] = defaultdict(int)
    tf_dir = DATA_DIR / tf
    tickers_sampled = tickers[:sample] if len(tickers) > sample else tickers

    for ticker in tickers_sampled:
        raw_dir = tf_dir / ticker / "session=rth" / "adjustment=raw"
        for parquet_file in list(raw_dir.rglob("data.parquet"))[:2]:  # first 2 partitions
            try:
                df = pd.read_parquet(parquet_file, columns=["provider"])
                for p in df["provider"].dropna().unique():
                    provider_counts[str(p)] += 1
            except Exception:
                pass

    return dict(provider_counts)


def get_freshness_distribution(all_meta: dict) -> Dict[str, int]:
    """Bucket tickers by data age (from meta.json last_updated)."""
    now = datetime.now(timezone.utc)
    buckets = {
        "< 0.5h": 0,
        "0.5–6h": 0,
        "6–24h": 0,
        "1–7 days": 0,
        "> 7 days": 0,
        "unknown": 0,
    }
    for tf in TIMEFRAMES:
        for ticker, meta in all_meta.get(tf, {}).items():
            ts = parse_iso(meta.get("last_updated"))
            if ts is None:
                buckets["unknown"] += 1
                continue
            age_h = (now - ts).total_seconds() / 3600
            if age_h < 0.5:
                buckets["< 0.5h"] += 1
            elif age_h < 6:
                buckets["0.5–6h"] += 1
            elif age_h < 24:
                buckets["6–24h"] += 1
            elif age_h < 168:
                buckets["1–7 days"] += 1
            else:
                buckets["> 7 days"] += 1
    return buckets


def find_cross_timeframe_gaps(
    ticker_stats: dict,
) -> Tuple[List[str], List[str], List[str]]:
    """Find tickers that have one timeframe but not another."""
    all_tickers = set(ticker_stats.keys())

    has_1min = {t for t in all_tickers if "1min" in ticker_stats[t]}
    has_5min = {t for t in all_tickers if "5min" in ticker_stats[t]}
    has_1day = {t for t in all_tickers if "1day" in ticker_stats[t]}

    daily_no_intraday = sorted(has_1day - has_1min - has_5min)
    intraday_no_daily = sorted((has_1min | has_5min) - has_1day)
    five_no_one = sorted(has_5min - has_1min)

    return daily_no_intraday, intraday_no_daily, five_no_one


def check_health(
    ticker_stats: dict, all_meta: dict
) -> list[tuple[str, str]]:
    """Run health checks, return list of (severity, message)."""
    issues: list[tuple[str, str]] = []

    # Lock files: warn if >100 stray locks
    locks_dir = DATA_DIR / ".locks"
    if locks_dir.is_dir():
        lock_count = len(list(locks_dir.iterdir()))
        if lock_count > 200:
            issues.append(("WARN", f"{lock_count} lock files — possible leak (clean with caution)"))

    # Tickers with 0 partitions in meta
    for tf in TIMEFRAMES:
        zero_part = [
            t for t, meta in all_meta.get(tf, {}).items()
            if meta.get("partitions", 0) == 0 and meta.get("total_rows", 0) > 0
        ]
        if zero_part:
            issues.append(("WARN", f"{tf}: {len(zero_part)} tickers with total_rows>0 but partitions=0 (meta corruption?)"))

    # Tickers with no data.parquet files but meta.json exists
    for tf in TIMEFRAMES:
        tf_dir = DATA_DIR / tf
        if not tf_dir.is_dir():
            continue
        empty = []
        for ticker in all_meta.get(tf, {}):
            ticker_dir = tf_dir / ticker
            parquets = list(ticker_dir.rglob("data.parquet"))
            if not parquets:
                empty.append(ticker)
        if empty:
            issues.append(("INFO", f"{tf}: {len(empty)} tickers have meta.json but no parquet files (not yet populated)"))

    return issues


# ── Display ─────────────────────────────────────────────────────────────────────

def print_divider(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_summary(all_meta: dict, ticker_stats: dict) -> None:
    """Print aggregate overview by timeframe."""
    print_divider("AGGREGATE OVERVIEW")

    header = f"{'Metric':<32} {'1min':>12} {'5min':>12} {'1day':>12}"
    print(header)
    print("-" * len(header))

    for label, fn in [
        ("Ticker count", lambda tf: len(all_meta.get(tf, {}))),
        ("Total bars", lambda tf: sum(m.get("total_rows", 0) for m in all_meta.get(tf, {}).values())),
        ("Total partitions", lambda tf: sum(
            len(m.get("partitions", [])) if isinstance(m.get("partitions"), list) else m.get("partitions", 0)
            for m in all_meta.get(tf, {}).values()
        )),
        ("Coverage days (sum)", lambda tf: sum(len(m.get("coverage", {})) for m in all_meta.get(tf, {}).values())),
        ("Negative cache entries", lambda tf: sum(len(m.get("negative_cache", {})) for m in all_meta.get(tf, {}).values())),
    ]:
        vals = [fn(tf) for tf in TIMEFRAMES]
        print(f"  {label:<30} {format_bars(vals[0]):>12} {format_bars(vals[1]):>12} {format_bars(vals[2]):>12}")

    # Disk usage
    disk_vals = []
    for tf in TIMEFRAMES:
        tf_dir = DATA_DIR / tf
        du = get_disk_usage(tf_dir) if tf_dir.is_dir() else 0
        disk_vals.append(du)
    print(f"  {'Disk usage':<30} {format_bytes(disk_vals[0]):>12} {format_bytes(disk_vals[1]):>12} {format_bytes(disk_vals[2]):>12}")
    print(f"  {'Disk total':<30} {format_bytes(sum(disk_vals)):>12}")

    # Date range
    for label, key, fn in [("Earliest bar", "earliest", min), ("Latest bar", "latest", max)]:
        vals = []
        for tf in TIMEFRAMES:
            dates = [
                m.get(key) for m in all_meta.get(tf, {}).values() if m.get(key)
            ]
            vals.append(fn(dates)[:10] if dates else "—")
        print(f"  {label:<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Lock files
    locks_dir = DATA_DIR / ".locks"
    lock_count = len(list(locks_dir.iterdir())) if locks_dir.is_dir() else 0
    print(f"  {'Lock files':<30} {lock_count:>12}")


def print_top_tickers(ticker_stats: dict, n: int = 20) -> None:
    """Show top-N tickers by 1min bar count and sparsest tickers."""
    print_divider(f"TOP {n} TICKERS BY 1min BARS")

    ranked = []
    for ticker, tfs in ticker_stats.items():
        bars_1m = tfs.get("1min", {}).get("total_rows", 0)
        bars_5m = tfs.get("5min", {}).get("total_rows", 0)
        bars_1d = tfs.get("1day", {}).get("total_rows", 0)
        ranked.append((ticker, bars_1m, bars_5m, bars_1d))

    ranked.sort(key=lambda x: x[1], reverse=True)

    print(f"  {'Ticker':<8} {'1min':>10} {'5min':>10} {'1day':>8}  {'Years (1m)'}")
    print("  " + "-" * 52)
    for ticker, b1, b5, bd in ranked[:n]:
        years = ticker_stats[ticker].get("1min", {}).get("year_count", 0)
        print(f"  {ticker:<8} {format_bars(b1):>10} {format_bars(b5):>10} {format_bars(bd):>8}  {years}")

    # Bottom N (tickers with least 1min data)
    print()
    print(f"  SPARSEST {n} TICKERS (by 1min bars, non-zero):")
    non_zero = [(t, b1, b5, bd) for t, b1, b5, bd in ranked if b1 > 0]
    for ticker, b1, b5, bd in non_zero[-n:]:
        years = ticker_stats[ticker].get("1min", {}).get("year_count", 0)
        print(f"  {ticker:<8} {format_bars(b1):>10} {format_bars(b5):>10} {format_bars(bd):>8}  {years}")


def print_year_coverage(ticker_stats: dict) -> None:
    """Matrix: how many tickers have each (year, timeframe)."""
    print_divider("YEAR COVERAGE MATRIX")
    years = sorted(set(
        y
        for tfs in ticker_stats.values()
        for tf_data in tfs.values()
        for y in tf_data.get("years", [])
    ))

    header = f"  {'Year':<6}"
    for tf in TIMEFRAMES:
        header += f" {tf:>8}"
    print(header)
    print("  " + "-" * 36)

    for year in years:
        row = f"  {year:<6}"
        for tf in TIMEFRAMES:
            count = sum(
                1 for tfs in ticker_stats.values()
                if year in tfs.get(tf, {}).get("years", [])
            )
            row += f" {count:>8}"
        print(row)

    # Total unique tickers with any data
    total = len(ticker_stats)
    print(f"\n  Total unique tickers across all timeframes: {total}")


def print_provider_distribution(all_meta: dict) -> None:
    """Show provider distribution (alpaca vs yfinance)."""
    print_divider("PROVIDER DISTRIBUTION")
    for tf in TIMEFRAMES:
        tickers = list(all_meta.get(tf, {}).keys())
        if not tickers:
            print(f"  {tf}: no data")
            continue
        dist = get_provider_distribution(tf, tickers, sample=min(50, len(tickers)))
        total = sum(dist.values()) or 1
        row = "  ".join(f"{k}={v} ({100*v/total:.0f}%)" for k, v in sorted(dist.items()))
        print(f"  {tf}: {row}  (sampled {min(50, len(tickers))} tickers)")


def print_freshness(all_meta: dict) -> None:
    """Show how stale the cache is."""
    print_divider("DATA FRESHNESS (last_updated bucket)")
    dist = get_freshness_distribution(all_meta)
    total = sum(dist.values()) or 1
    for bucket in ["< 0.5h", "0.5–6h", "6–24h", "1–7 days", "> 7 days", "unknown"]:
        count = dist[bucket]
        bar = "█" * max(1, int(40 * count / total))
        print(f"  {bucket:<12} {count:>6}  {bar}")


def print_cross_timeframe_gaps(ticker_stats: dict) -> None:
    """Tickers that are missing one timeframe."""
    print_divider("CROSS-TIMEFRAME GAPS")

    daily_no_intraday, intraday_no_daily, five_no_one = find_cross_timeframe_gaps(ticker_stats)

    print(f"  Daily-only (no 1min or 5min): {len(daily_no_intraday)} tickers")
    if daily_no_intraday:
        print(f"    {', '.join(daily_no_intraday[:30])}")
        if len(daily_no_intraday) > 30:
            print(f"    ... and {len(daily_no_intraday) - 30} more")

    print(f"  Intraday-only (no daily):     {len(intraday_no_daily)} tickers")
    if intraday_no_daily:
        print(f"    {', '.join(intraday_no_daily[:30])}")
        if len(intraday_no_daily) > 30:
            print(f"    ... and {len(intraday_no_daily) - 30} more")

    print(f"  5min-only (no 1min):          {len(five_no_one)} tickers")
    if five_no_one:
        print(f"    {', '.join(five_no_one[:30])}")
        if len(five_no_one) > 30:
            print(f"    ... and {len(five_no_one) - 30} more")


def print_health(issues: list[tuple[str, str]]) -> None:
    """Print health check results."""
    print_divider("HEALTH CHECKS")
    if not issues:
        print("  All checks passed.")
        return

    for severity, msg in issues:
        prefix = {"WARN": "⚠ ", "ERROR": "✗ ", "INFO": "  "}.get(severity, "  ")
        print(f"  {prefix}[{severity}] {msg}")


def print_ticker_detail(
    ticker: str,
    ticker_stats: dict,
    all_meta: dict,
    show_holes: bool = False,
) -> None:
    """Print detailed stats for one ticker."""
    print_divider(f"TICKER: {ticker}")
    stats = ticker_stats.get(ticker, {})

    for tf in TIMEFRAMES:
        s = stats.get(tf, {})
        if not s:
            print(f"  {tf}: NO DATA")
            continue

        print(f"  ── {tf} ──")
        print(f"    Bars:          {s.get('total_rows', 0):,}")
        print(f"    Partitions:    {s.get('partitions', 0)}")
        print(f"    Coverage days: {s.get('coverage_days', 0)}")
        print(f"    Years:         {', '.join(s.get('years', []))} ({s.get('year_count')})")
        print(f"    Date range:    {str(s.get('earliest', '?'))[:19]} → {str(s.get('latest', '?'))[:19]}")
        print(f"    Last updated:  {str(s.get('last_updated', '?'))[:26]}")
        print(f"    Missing dates:  {s.get('negative_cache', 0)}")

        # Monthly gap check (for intraday)
        if tf in ("1min", "5min") and show_holes:
            meta = all_meta.get(tf, {}).get(ticker, {})
            coverage_dates = set(meta.get("coverage", {}).keys())
            if coverage_dates and s.get("years"):
                now = datetime.now()
                current_year, current_month = now.year, now.month

                for year_str in s["years"]:
                    year_int = int(year_str)
                    months_present = set()
                    for d in coverage_dates:
                        if d.startswith(year_str):
                            months_present.add(int(d[5:7]))

                    # Only expect months that have already passed
                    if year_int < current_year:
                        expected = set(range(1, 13))
                    elif year_int == current_year:
                        expected = set(range(1, current_month + 1))
                    else:
                        # Future year — skip
                        continue

                    missing = sorted(expected - months_present)
                    if missing:
                        print(f"    Year {year_str} gaps: months {', '.join(str(m) for m in missing)}")


def print_holes_report(ticker_stats: dict, all_meta: dict) -> None:
    """Detailed gap analysis — tickers with missing months."""
    print_divider("DATA GAPS — MONTHLY HOLES")

    issues_found = 0
    now = datetime.now()
    current_year, current_month = now.year, now.month

    for ticker in sorted(ticker_stats.keys()):
        for tf in ("1min", "5min"):
            meta = all_meta.get(tf, {}).get(ticker, {})
            coverage_dates = set(meta.get("coverage", {}).keys())
            stats = ticker_stats[ticker].get(tf, {})
            if not coverage_dates or not stats.get("years"):
                continue

            for year_str in stats["years"]:
                year_int = int(year_str)
                months_present = set()
                for d in coverage_dates:
                    if d.startswith(year_str):
                        months_present.add(int(d[5:7]))

                # Only expect months that have already passed
                if year_int < current_year:
                    expected = set(range(1, 13))
                elif year_int == current_year:
                    expected = set(range(1, current_month + 1))
                else:
                    continue  # future year

                missing = sorted(expected - months_present)
                if missing:
                    print(f"  {ticker:<8} {tf:<5} {year_str}  missing months: {', '.join(f'{m:02d}' for m in missing)}")
                    issues_found += 1
                    if issues_found >= 40:
                        print(f"  ... (capped at 40 entries)")
                        return

    if issues_found == 0:
        print("  No monthly gaps found. All tickers have complete month coverage.")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Market data cache inspector")
    parser.add_argument("--ticker", help="Show detail for a single ticker")
    parser.add_argument("--summary-only", action="store_true", help="Skip per-ticker detail")
    parser.add_argument("--holes", action="store_true", help="Show monthly gap report only")
    parser.add_argument("--top", type=int, default=20, help="Number of top/bottom tickers to show")
    parser.add_argument("--no-health", action="store_true", help="Skip health checks")
    args = parser.parse_args()

    os.chdir(DATA_DIR.parent)  # Ensure relative paths work

    print("Scanning cache...", file=sys.stderr, end="", flush=True)
    all_meta = gather_all_meta()
    ticker_stats = collect_ticker_stats(all_meta)
    print(f" done ({len(ticker_stats)} tickers across {len(TIMEFRAMES)} timeframes)", file=sys.stderr)

    if args.ticker:
        ticker = args.ticker.upper()
        if ticker not in ticker_stats:
            print(f"Ticker '{ticker}' not found in cache.")
            print(f"Available tickers: {', '.join(sorted(ticker_stats.keys())[:50])}...")
            sys.exit(1)
        print_summary(all_meta, ticker_stats)
        print_ticker_detail(ticker, ticker_stats, all_meta, show_holes=True)
    elif args.holes:
        print_holes_report(ticker_stats, all_meta)
    else:
        print_summary(all_meta, ticker_stats)
        print_top_tickers(ticker_stats, n=args.top)
        print_year_coverage(ticker_stats)
        print_provider_distribution(all_meta)
        print_freshness(all_meta)
        print_cross_timeframe_gaps(ticker_stats)
        if not args.no_health:
            issues = check_health(ticker_stats, all_meta)
            print_health(issues)

    print()


if __name__ == "__main__":
    main()
