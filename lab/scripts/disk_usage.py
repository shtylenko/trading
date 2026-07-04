#!/usr/bin/env python3
"""
Disk usage report for strategy_lab — fast targeted scan, cleanup recommendations.
Queries subdirectories individually to stay under timeout limits.

Usage:
    python3 engine/strategy_lab/scripts/disk_usage.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


ROOT = Path(__file__).resolve().parent.parent  # strategy_lab/


def du(path: str, timeout: int = 30) -> int:
    """Return size in bytes using `du -sk` then x1024."""
    try:
        r = subprocess.run(["du", "-sk", path], capture_output=True, text=True, timeout=timeout)
        if r.stdout.strip():
            return int(r.stdout.split()[0]) * 1024
        return 0
    except subprocess.TimeoutExpired:
        print(f"    (timeout: {path})", file=sys.stderr)
        return 0
    except Exception:
        return 0


def du_file(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def fmt(n: int) -> str:
    f: float = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(f) < 1024.0:
            if unit == "B":
                return f"{n} B"
            return f"{f:.1f} {unit}"
        f /= 1024.0
    return f"{f:.1f} PB"


def section(title: str) -> None:
    print(f"\n{'─' * 78}")
    print(f"  {title}")
    print(f"{'─' * 78}")


def main() -> None:
    print(f"strategy_lab disk usage report — {ROOT}\n")

    log_files: list[Path] = []
    log_dir = ROOT / "marketdata" / "logs"

    # ── Top-level ──────────────────────────────────────────────────────
    section("TOP-LEVEL DIRECTORIES")

    # Compute marketdata as sum of its children (avoids timeout on 26GB dir)
    md_data = du(str(ROOT / "marketdata" / "data"), timeout=120)
    md_logs = du(str(ROOT / "marketdata" / "logs"), timeout=10)
    md_providers = du(str(ROOT / "marketdata" / "providers"), timeout=10)
    md_total = md_data + md_logs + md_providers

    tops: dict[str, int] = {
        "marketdata": md_total,
        "storage": du(str(ROOT / "storage"), timeout=10),
        "universes": du(str(ROOT / "universes"), timeout=10),
    }

    # Small dirs — batch with du
    small_dirs = ["strategies", "tests", "peer-review", "scripts", "testsets",
                  "runner", "core", "validation", "roadmap", "research", "data",
                  "reports", "logs"]
    for d in small_dirs:
        p = ROOT / d
        if p.exists():
            tops[d] = du(str(p), timeout=10)

    total = sum(tops.values())
    for k in tops:
        print(f"  {k:<30} {fmt(tops[k]):>12}")
    print(f"  {'─' * 42}")
    print(f"  {'TOTAL':<30} {fmt(total):>12}")

    # ── Marketdata ─────────────────────────────────────────────────────
    section("MARKETDATA BREAKDOWN")
    print(f"  marketdata/data         {fmt(md_data):>12}")
    print(f"  marketdata/logs         {fmt(md_logs):>12}")
    print(f"  marketdata/providers    {fmt(md_providers):>12}")

    # data by timeframe
    print()
    for tf in ["1min", "5min", "1day"]:
        tf_dir = ROOT / "marketdata" / "data" / tf
        if tf_dir.exists():
            sz = du(str(tf_dir), timeout=60)
            n_tickers = len(list(tf_dir.iterdir()))
            print(f"    {tf:<8} {fmt(sz):>10}  ({n_tickers} tickers)")

    # logs
    print()
    if log_dir.exists():
        log_files = sorted(log_dir.glob("*.log"))
        log_total = sum(f.stat().st_size for f in log_files)
        print(f"  marketdata/logs: {fmt(log_total)} in {len(log_files)} log files")
        for f in log_files[-5:]:
            print(f"    {f.name:<28} {fmt(f.stat().st_size):>10}")

    # ── Storage ────────────────────────────────────────────────────────
    section("STORAGE")
    db = ROOT / "storage" / "strategy_lab.duckdb"
    if db.exists():
        sz = db.stat().st_size
        print(f"  strategy_lab.duckdb  {fmt(sz)}")
        try:
            import duckdb
            con = duckdb.connect(str(db), read_only=True)
            tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
            table_names = [t[0] for t in tables]
            if "simulation_trades" in table_names:
                trades = con.execute("SELECT COUNT(*) FROM simulation_trades").fetchone()
                trades_n = trades[0] if trades else 0
                print(f"    {trades_n:,} simulation trades stored")
            if "backtest_runs" in table_names:
                runs = con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()
                runs_n = runs[0] if runs else 0
                print(f"    {runs_n} backtest runs")
            # Show all table names
            print(f"    Tables: {', '.join(sorted(table_names))}")
            con.close()
        except Exception as e:
            print(f"    (DuckDB query skipped: {e})")

    # ── Universes ──────────────────────────────────────────────────────
    section("UNIVERSES")
    for f in sorted((ROOT / "universes").iterdir()):
        if f.name.startswith("."):
            continue
        sz = du_file(f) if f.is_file() else du(str(f))
        tag = ""
        if f.name == "_daily_screen_cache.parquet":
            tag = "  ← rebuildable cache"
        print(f"  {f.name:<40} {fmt(sz):>10}{tag}")

    # ── Strategies ─────────────────────────────────────────────────────
    section("STRATEGIES")
    strat_dir = ROOT / "strategies"
    if strat_dir.exists():
        for d in sorted(strat_dir.iterdir()):
            if not d.is_dir() or d.name.startswith(".") or d.name == "__pycache__":
                continue
            sz = du(str(d))
            print(f"  strategies/{d.name:<42} {fmt(sz):>10}")
            for sub in sorted(d.iterdir()):
                if not sub.is_dir():
                    continue
                if sub.name.startswith("."):
                    continue
                subsz = du(str(sub))
                if subsz > 4096:
                    print(f"    └─ {sub.name:<40} {fmt(subsz):>10}")

    # ── Cleanup candidates ─────────────────────────────────────────────
    section("CLEANUP CANDIDATES")
    savings = 0

    # 1. Old log files (keep last 3)
    if log_dir.exists():
        log_files = sorted(log_dir.glob("*.log"))
        keep = 3
        old_logs = log_files[:-keep] if len(log_files) > keep else []
        old_logs_size = sum(f.stat().st_size for f in old_logs)
        if old_logs:
            print(f"  Old marketdata logs (keep last {keep}):      {fmt(old_logs_size)}  ({len(old_logs)} files)")
            for f in old_logs:
                print(f"    {f.name}")
            savings += old_logs_size
        else:
            print(f"  Old marketdata logs: none to clean ({len(log_files)} files, keeping {keep})")

    # 2. Universe dump cache
    cache = ROOT / "universes" / "_daily_screen_cache.parquet"
    if cache.exists():
        sz = du_file(cache)
        print(f"  _daily_screen_cache.parquet (rebuildable): {fmt(sz)}")
        savings += sz

    # 3. ML model artifacts
    artifacts_dir = ROOT / "strategies" / "stocks_in_play_orb" / "research" / "artifacts"
    if artifacts_dir.exists():
        for a in sorted(artifacts_dir.glob("*.pkl")):
            sz = du_file(a)
            print(f"  ML artifact (rebuildable):                  {fmt(sz)}  ({a.name})")
            savings += sz

    # 4. Stale lock files
    locks_dir = ROOT / "marketdata" / "data" / ".locks"
    if locks_dir.exists():
        n_locks = len(list(locks_dir.iterdir()))
        if n_locks > 50:
            print(f"  Stale lock files:                           {n_locks} files (~0B each)")
            print(f"    (storage.py now auto-cleans — these are pre-fix remnants)")

    # 5. .DS_Store files
    ds_stores = list(ROOT.rglob(".DS_Store"))
    ds_size = sum(du_file(f) for f in ds_stores)
    if ds_stores:
        print(f"  .DS_Store files:                            {fmt(ds_size)}  ({len(ds_stores)} files)")
        savings += ds_size

    # 6. __pycache__ dirs
    pycache_dirs = list(ROOT.rglob("__pycache__"))
    pycache_size = sum(du(str(d), timeout=5) for d in pycache_dirs)
    if pycache_dirs:
        print(f"  __pycache__ dirs (rebuildable):             {fmt(pycache_size)}  ({len(pycache_dirs)} dirs)")
        savings += pycache_size

    # 7. pytest cache
    pytest_cache = ROOT / ".pytest_cache"
    if pytest_cache.exists():
        sz = du(str(pytest_cache), timeout=5)
        print(f"  .pytest_cache (rebuildable):                {fmt(sz)}")
        savings += sz

    # ── Summary ────────────────────────────────────────────────────────
    section("SUMMARY")
    print(f"  Total disk usage:     {fmt(total)}")
    print(f"  Safe to clean:        {fmt(savings)}")
    print(f"  After cleanup:        {fmt(total - savings)}")
    print()
    print(f"  19 GB — 1min intraday cache (don't delete unless re-download acceptable)")
    print(f"  6.3 GB — 5min intraday cache")
    print(f"  5.6 GB — DuckDB backtest history (shrink only if old runs unwanted)")
    print(f"  41 MB  — daily logs + universe cache + ML artifacts (safe to clean)")
    print()


if __name__ == "__main__":
    main()
