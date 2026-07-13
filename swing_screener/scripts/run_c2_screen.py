#!/usr/bin/env python3
"""Run C2_BREAKOUT historical candidate screen."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="C2_BREAKOUT historical screen")
    p.add_argument("--start", type=_parse_date, required=True)
    p.add_argument("--end", type=_parse_date, required=True)
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--tickers", default=None)
    p.add_argument("--max-tickers", type=int, default=None)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from trading.swing_screener.c2_breakout.rules import load_config
    from trading.swing_screener.c2_breakout.screen import run_screen
    import pandas as pd

    from trading.swing_screener.data.store import write_candidates

    cfg = load_config(args.config)
    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    df = run_screen(
        start=args.start,
        end=args.end,
        cfg=cfg,
        tickers=tickers,
        max_tickers=args.max_tickers,
        workers=args.workers,
    )

    out_dir = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "outputs" / "c2_breakout"
    )
    stem = f"candidates_{args.start.isoformat()}_{args.end.isoformat()}"
    if df is None or df.empty:
        import pandas as pd

        empty = pd.DataFrame()
        path = write_candidates(empty, out_dir, stem)
        print(f"No candidates. Wrote empty {path}")
        return 0

    path = write_candidates(df, out_dir, stem)
    tmp = df.copy()
    tmp["year"] = pd.to_datetime(tmp["asof_date"]).dt.year
    summary = (
        tmp.groupby("year", as_index=False)
        .agg(n_hits=("ticker", "size"), n_tickers=("ticker", "nunique"))
        .sort_values("year")
    )
    summary.to_csv(out_dir / f"summary_by_year_{args.start.isoformat()}_{args.end.isoformat()}.csv", index=False)
    print(f"Candidates: {len(df):,} → {path}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
