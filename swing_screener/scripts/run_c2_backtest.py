#!/usr/bin/env python3
"""Simulate C2_BREAKOUT trades from candidate screen output."""

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
    p = argparse.ArgumentParser(description="C2_BREAKOUT trade backtest")
    p.add_argument("--candidates", required=True)
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from trading.swing_screener.c1_pullback.backtest import summarize_trades
    from trading.swing_screener.c2_breakout.backtest import run_backtest
    from trading.swing_screener.c2_breakout.rules import load_config

    cand_path = Path(args.candidates)
    candidates = pd.read_parquet(cand_path)
    cfg = load_config(args.config)
    trades = run_backtest(candidates, cfg=cfg, workers=args.workers)

    out_dir = Path(args.out) if args.out else cand_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = cand_path.stem.replace("candidates_", "trades_")
    if stem == cand_path.stem:
        stem = f"trades_{cand_path.stem}"

    if trades is None or trades.empty:
        print("No trades.")
        pd.DataFrame().to_parquet(out_dir / f"{stem}.parquet", index=False)
        return 0

    trades.to_parquet(out_dir / f"{stem}.parquet", index=False)
    trades.to_csv(out_dir / f"{stem}.csv", index=False)
    summary = summarize_trades(trades)
    summary.to_parquet(out_dir / f"metrics_{stem}.parquet", index=False)
    summary.to_csv(out_dir / f"metrics_{stem}.csv", index=False)

    print(f"Trades: {len(trades):,} → {out_dir / f'{stem}.parquet'}")
    show = summary.copy()
    show["year"] = show["year"].replace({0: "ALL"})
    cols = [
        "year",
        "variant",
        "n_trades",
        "win_rate",
        "avg_r",
        "median_r",
        "sum_r",
        "profit_factor",
        "avg_hold_days",
        "stop_pct",
    ]
    pd.set_option("display.float_format", lambda x: f"{x:0.3f}")
    print(show[[c for c in cols if c in show.columns]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
