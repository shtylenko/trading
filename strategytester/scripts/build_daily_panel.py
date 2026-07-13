"""Build & cache the shared daily panel + market context for short-hold tests.

Usage (from monorepo root /Users/shtylenko/Projects):
    python3 -m trading.strategytester.scripts.build_daily_panel
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from trading.strategytester.common.panel import build_panel, market_context, CACHE_DIR
from trading.strategytester.common.universe import union_tickers

CACHE_KEY = "liquid_2022_2025"
START = date(2022, 1, 1)
END = date(2025, 12, 31)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--universe", default="liquid_pit")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    uni = union_tickers(args.universe, START, END)
    print(f"universe {args.universe}: {len(uni)} tickers, {START}..{END}")
    panel = build_panel(uni, START, END, cache_key=CACHE_KEY, force=args.force, warmup_days=500)
    print(f"panel built: {len(panel)} tickers with data")

    ctx = market_context(START, END)
    ctx_path = CACHE_DIR / "market_context.parquet"
    ctx.to_parquet(ctx_path)
    print(f"market context: {len(ctx)} rows -> {ctx_path.name}")
    print("bull days (spy 10>20):", round(float(ctx['spy_bull'].mean()), 3),
          "| median VIX:", round(float(ctx['vix'].median()), 1))


if __name__ == "__main__":
    main()
