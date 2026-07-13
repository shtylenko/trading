#!/usr/bin/env python3
"""Capacity portfolio layer for C2 trades."""

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
    p = argparse.ArgumentParser(description="C2 portfolio capacity layer")
    p.add_argument("--trades", required=True)
    p.add_argument("--candidates", default=None)
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--max-positions", type=int, default=None)
    p.add_argument("--max-per-sector", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from dataclasses import replace

    from trading.swing_screener.c2_breakout.portfolio import (
        load_portfolio_config,
        run_c2_portfolio,
    )

    trades = pd.read_parquet(args.trades)
    candidates = pd.read_parquet(args.candidates) if args.candidates else None
    cfg = load_portfolio_config(args.config)
    if args.max_positions is not None:
        cfg = replace(cfg, max_positions=args.max_positions)
    if args.max_per_sector is not None:
        cfg = replace(cfg, max_per_sector=args.max_per_sector)

    selected, summary = run_c2_portfolio(trades, candidates, cfg=cfg)
    out_dir = Path(args.out) if args.out else Path(args.trades).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.trades).stem.replace("trades_", "portfolio_")
    if stem == Path(args.trades).stem:
        stem = f"portfolio_{Path(args.trades).stem}"

    if selected is not None and not selected.empty:
        selected.to_parquet(out_dir / f"{stem}.parquet", index=False)
        selected.to_csv(out_dir / f"{stem}.csv", index=False)
    summary.to_parquet(out_dir / f"metrics_{stem}.parquet", index=False)
    summary.to_csv(out_dir / f"metrics_{stem}.csv", index=False)

    print(f"Selected: {0 if selected is None else len(selected):,}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
