#!/usr/bin/env python3
"""Run C1_PULLBACK historical candidate screen.

Usage (from monorepo root /Users/shtylenko/Projects):

    python3 -m trading.swing_screener.scripts.run_c1_screen \\
        --start 2022-01-01 --end 2026-06-30 \\
        --variant both
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# monorepo root = parents of trading/
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C1_PULLBACK historical candidate screen")
    parser.add_argument("--start", type=_parse_date, required=True)
    parser.add_argument("--end", type=_parse_date, required=True)
    parser.add_argument(
        "--variant",
        default="both",
        help="both | C1_MR | C1_PB",
    )
    parser.add_argument("--universe", default=None, help="override config universe name")
    parser.add_argument(
        "--config",
        default=None,
        help="path to c1_pullback.yaml",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: trading/swing_screener/outputs/c1_pullback)",
    )
    parser.add_argument(
        "--tickers",
        default=None,
        help="comma-separated ticker override (skips PIT membership filter)",
    )
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from trading.swing_screener.c1_pullback.rules import load_config
    from trading.swing_screener.c1_pullback.screen import run_screen
    from trading.swing_screener.data.store import write_candidates, write_summary

    cfg = load_config(args.config)
    if args.universe:
        # frozen dataclass — rebuild with override
        from dataclasses import replace

        cfg = replace(cfg, universe=args.universe)

    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    df = run_screen(
        start=args.start,
        end=args.end,
        cfg=cfg,
        variant=args.variant,
        tickers=tickers,
        max_tickers=args.max_tickers,
        workers=args.workers,
    )

    out_dir = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "outputs" / "c1_pullback"
    )
    stem = f"candidates_{args.start.isoformat()}_{args.end.isoformat()}"
    if df is None or df.empty:
        print("No candidates found.")
        # still write empty parquet for pipeline stability
        import pandas as pd

        empty = pd.DataFrame(
            columns=[
                "asof_date",
                "ticker",
                "variant",
                "close",
                "volume",
                "avg_vol_20",
                "relvol",
                "sma20",
                "sma50",
                "sma200",
                "rsi2",
                "rsi14",
                "perf_5d",
                "perf_21d",
                "perf_126d",
                "sma20_ext",
                "universe",
                "rules_version",
                "earnings_ok",
            ]
        )
        path = write_candidates(empty, out_dir, stem)
        print(f"Wrote empty results: {path}")
        return 0

    path = write_candidates(df, out_dir, stem)
    summary_path = write_summary(df, out_dir, f"summary_by_year_{args.start.isoformat()}_{args.end.isoformat()}")
    print(f"Candidates: {len(df):,} rows → {path}")
    if summary_path:
        print(f"Summary: {summary_path}")
        print(df.groupby(["variant"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
