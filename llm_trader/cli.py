"""CLI argument parsing for the multi-strategy entry scanner.

    python -m trading.llm_trader.runner \\
        --start 2025-01-01 --end 2026-06-30 --profile small

    python -m trading.llm_trader.runner --strategy cup_handle --max-symbols 100
    python -m trading.llm_trader.runner --strategy cup_handle --symbols JPM AAPL
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .config import DATA_DIR, ScanConfig
from .strategies import default_strategy_id, list_strategies


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm_trader",
        description="Multi-strategy entry scanner (warrior default; cup_handle swing, …).",
    )
    p.add_argument(
        "--strategy",
        default=default_strategy_id(),
        choices=list_strategies(),
        help=f"Strategy family (default: {default_strategy_id()}).",
    )
    p.add_argument("--config", help="YAML config file (CLI flags override).")
    p.add_argument("--start", help="YYYY-MM-DD.")
    p.add_argument("--end", help="YYYY-MM-DD.")
    p.add_argument("--profile", choices=["small", "main"], help="Account profile (warrior).")
    p.add_argument("--gap-min", type=float, help="Min gap %% (warrior; default 5).")
    p.add_argument(
        "--rvol-min", type=float,
        help="Min prior-day volume ratio (legacy flag name; warrior default 2).",
    )
    p.add_argument(
        "--float-max",
        type=float,
        help="Max float shares (warrior; default 20e6; pass 0 to disable).",
    )
    p.add_argument("--price-min", type=float)
    p.add_argument("--price-max", type=float)
    p.add_argument("--db", help="Output SQLite path.")
    p.add_argument(
        "--forward-shadow-ledger",
        help="Append contemporaneous Warrior scanner inputs to this JSONL ledger.",
    )
    p.add_argument(
        "--max-symbols",
        type=int,
        help="Scan only the first N symbols (pipeline test).",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        help="Scan only these tickers (skips universe fetch).",
    )
    p.add_argument(
        "--list-strategies",
        action="store_true",
        help="Print registered strategy families and exit.",
    )
    return p


def _date(s: str):
    return date.fromisoformat(s)


def config_from_args(args: argparse.Namespace) -> ScanConfig:
    """Warrior ScanConfig from CLI (used when --strategy warrior)."""
    cfg = ScanConfig.from_yaml(args.config) if args.config else ScanConfig()
    if args.start:
        cfg.start = _date(args.start)
    if args.end:
        cfg.end = _date(args.end)
    if args.profile:
        cfg.account_profile = args.profile
    cfg.apply_profile()
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
        cfg.db_path = Path(args.db)
    if args.forward_shadow_ledger:
        cfg.forward_shadow_ledger = Path(args.forward_shadow_ledger)
    return cfg
