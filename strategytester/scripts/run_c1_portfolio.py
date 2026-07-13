#!/usr/bin/env python3
"""Apply capacity portfolio layer to C1 simulated trades.

Example:

    python3 -m trading.swing_screener.scripts.run_c1_portfolio \\
      --trades trading/swing_screener/outputs/c1_pullback/trades_2025_v2.parquet \\
      --candidates trading/swing_screener/outputs/c1_pullback/candidates_2025_v2.parquet \\
      --max-positions 4 --max-per-sector 2
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="C1 capacity portfolio layer")
    p.add_argument("--trades", required=True, help="trades parquet from run_c1_backtest")
    p.add_argument(
        "--candidates",
        default=None,
        help="candidates parquet (for ranking features rsi2, sma20_ext, ...)",
    )
    p.add_argument("--max-positions", type=int, default=4)
    p.add_argument("--max-per-sector", type=int, default=2)
    p.add_argument("--starting-equity", type=float, default=20_000.0)
    p.add_argument("--risk-frac", type=float, default=0.0075)
    p.add_argument(
        "--allocation",
        default="merge",
        choices=["merge", "mr_first", "pb_first"],
    )
    p.add_argument(
        "--variant",
        default="both",
        help="both | C1_MR | C1_PB",
    )
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from trading.swing_screener.c1_pullback.portfolio import (
        PortfolioConfig,
        apply_portfolio,
    )
    from trading.swing_screener.c1_pullback.screen import _normalize_variants

    trades_path = Path(args.trades)
    trades = pd.read_parquet(trades_path)
    # entry year cleanliness: keep all; caller can prefilter
    candidates = None
    if args.candidates:
        candidates = pd.read_parquet(args.candidates)

    variants = _normalize_variants(args.variant)
    cfg = PortfolioConfig(
        max_positions=args.max_positions,
        max_per_sector=args.max_per_sector,
        starting_equity=args.starting_equity,
        risk_frac=args.risk_frac,
        allocation=args.allocation,
    )
    selected, summary = apply_portfolio(
        trades,
        cfg=cfg,
        candidates=candidates,
        variants=variants,
    )

    out_dir = Path(args.out) if args.out else trades_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = trades_path.stem.replace("trades_", "portfolio_")
    if stem == trades_path.stem:
        stem = f"portfolio_{trades_path.stem}"

    sel_path = out_dir / f"{stem}.parquet"
    sum_path = out_dir / f"metrics_{stem}.parquet"
    if selected is not None and not selected.empty:
        selected.to_parquet(sel_path, index=False)
        selected.to_csv(out_dir / f"{stem}.csv", index=False)
    else:
        pd.DataFrame().to_parquet(sel_path, index=False)
    summary.to_parquet(sum_path, index=False)
    summary.to_csv(out_dir / f"metrics_{stem}.csv", index=False)

    print(f"Selected: {0 if selected is None else len(selected):,} → {sel_path}")
    print(f"Metrics:  {sum_path}")
    print()
    cols = [
        c
        for c in [
            "scope",
            "n_selected",
            "n_available",
            "n_skipped_pool",
            "win_rate",
            "avg_r",
            "sum_r",
            "profit_factor",
            "return_pct",
            "end_equity",
            "max_dd",
            "max_concurrent",
        ]
        if c in summary.columns
    ]
    pd.set_option("display.float_format", lambda x: f"{x:0.3f}")
    print(summary[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
