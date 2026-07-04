"""CLI argument parsing for the entry scanner.

    python -m trading.llm_trader.runner \\
        --start 2025-01-01 --end 2026-06-30 --profile small

    # quick pipeline smoke test on a slice / explicit tickers
    python -m trading.llm_trader.runner --max-symbols 50
    python -m trading.llm_trader.runner --symbols AAOI TLRY GME
"""

from __future__ import annotations

import argparse
from datetime import datetime

from .config import DATA_DIR, ScanConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm_trader",
        description="Warrior Trading momentum entry scanner (entries only, no P&L).",
    )
    p.add_argument("--config", help="YAML config file (CLI flags override).")
    p.add_argument("--start", help="YYYY-MM-DD (default 2025-01-01).")
    p.add_argument("--end", help="YYYY-MM-DD (default 2026-06-30).")
    p.add_argument("--profile", choices=["small", "main"], help="Account profile.")
    p.add_argument("--gap-min", type=float, help="Min gap %% (default 5).")
    p.add_argument("--rvol-min", type=float, help="Min relative volume (default 2).")
    p.add_argument("--float-max", type=float,
                   help="Max float shares (default 20e6; pass 0 to disable).")
    p.add_argument("--price-min", type=float)
    p.add_argument("--price-max", type=float)
    p.add_argument("--db", help="Output SQLite path (default data/entries.db).")
    p.add_argument("--max-symbols", type=int,
                   help="Scan only the first N symbols (pipeline test).")
    p.add_argument("--symbols", nargs="+",
                   help="Scan only these tickers (skips universe fetch).")
    return p


def _date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()


def config_from_args(args: argparse.Namespace) -> ScanConfig:
    cfg = ScanConfig.from_yaml(args.config) if args.config else ScanConfig()
    if args.start:
        cfg.start = _date(args.start)
    if args.end:
        cfg.end = _date(args.end)
    if args.profile:
        cfg.account_profile = args.profile
    cfg.apply_profile()
    # explicit band overrides applied after profile so they win
    if args.price_min is not None:
        cfg.price_min = args.price_min
    if args.price_max is not None:
        cfg.price_max = args.price_max
    if args.gap_min is not None:
        cfg.gap_min_pct = args.gap_min
    if args.rvol_min is not None:
        cfg.rvol_min = args.rvol_min
    if args.float_max is not None:
        cfg.float_max = None if args.float_max <= 0 else args.float_max
    if args.db:
        from pathlib import Path
        cfg.db_path = Path(args.db)
    else:
        cfg.db_path = DATA_DIR / "entries.db"
    return cfg
