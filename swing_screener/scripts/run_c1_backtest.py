#!/usr/bin/env python3
"""Simulate C1_MR / C1_PB trades from candidate screen output.

Usage (from monorepo root):

    python3 -m trading.swing_screener.scripts.run_c1_backtest \\
        --candidates trading/swing_screener/outputs/c1_pullback/candidates_2022-01-01_2026-06-30.parquet
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
    parser = argparse.ArgumentParser(description="C1_PULLBACK trade backtest")
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates parquet from run_c1_screen",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="c1_pullback.yaml (screen + backtest sections)",
    )
    parser.add_argument(
        "--variant",
        default="both",
        help="both | C1_MR | C1_PB",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: same dir as candidates)",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from trading.swing_screener.c1_pullback.backtest import (
        load_backtest_config,
        run_backtest,
        summarize_trades,
    )
    from trading.swing_screener.c1_pullback.rules import load_config
    from trading.swing_screener.c1_pullback.screen import _normalize_variants

    cand_path = Path(args.candidates)
    if not cand_path.exists():
        print(f"Candidates file not found: {cand_path}", file=sys.stderr)
        return 1

    candidates = pd.read_parquet(cand_path)
    cfg = load_config(args.config)
    bt_cfg = load_backtest_config(args.config)
    variants = _normalize_variants(args.variant)

    trades = run_backtest(
        candidates,
        cfg=cfg,
        bt_cfg=bt_cfg,
        variants=variants,
        workers=args.workers,
    )

    out_dir = Path(args.out) if args.out else cand_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = cand_path.stem.replace("candidates_", "trades_")
    if stem == cand_path.stem:
        stem = f"trades_{cand_path.stem}"

    if trades is None or trades.empty:
        print("No trades simulated.")
        empty = pd.DataFrame()
        empty.to_parquet(out_dir / f"{stem}.parquet", index=False)
        return 0

    trades_path = out_dir / f"{stem}.parquet"
    trades.to_parquet(trades_path, index=False)
    trades.head(50_000).to_csv(out_dir / f"{stem}.csv", index=False)

    summary = summarize_trades(trades)
    summary_path = out_dir / f"metrics_{stem}.parquet"
    summary.to_parquet(summary_path, index=False)
    summary.to_csv(out_dir / f"metrics_{stem}.csv", index=False)

    print(f"Trades: {len(trades):,} → {trades_path}")
    print(f"Metrics: {summary_path}")
    print()
    # Pretty print overall + yearly
    show = summary.copy()
    show["year"] = show["year"].replace({0: "ALL"})
    cols = [
        "year",
        "variant",
        "n_trades",
        "win_rate",
        "avg_r",
        "median_r",
        "avg_win_r",
        "avg_loss_r",
        "profit_factor",
        "avg_hold_days",
        "stop_pct",
    ]
    pd.set_option("display.float_format", lambda x: f"{x:0.3f}")
    print(show[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
