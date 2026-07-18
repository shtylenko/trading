"""Deterministic paper book for vwap_pullback (portfolio ON, NML OFF)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from trading.llm_trader.admission.portfolio import PortfolioLimits
from trading.llm_trader.admission.short_hold_paper import (
    build_short_hold_paper_book,
    write_short_hold_paper_book,
)

from .config import VwapPullbackConfig
from .patterns import simulate_trade
from .runner import run_cost_stress

log = logging.getLogger("llm_trader.vwap_pullback.paper")

PAPER_CONTRACT = "vwap_pullback_paper_book_v0.1.0"
STRATEGY_ID = "vwap_pullback"


def build_paper_book(cfg: VwapPullbackConfig, **kwargs):
    return build_short_hold_paper_book(
        strategy_id=STRATEGY_ID,
        contract=PAPER_CONTRACT,
        cfg=cfg,
        simulate=simulate_trade,
        run_cost_stress=run_cost_stress,
        promotion_notes=(
            "Thin multi-year edge under portfolio packaging; more cost-fragile than "
            "micro_pullback. Do not live-size. NML gate remains OFF (A/B hard fail)."
        ),
        **kwargs,
    )


def write_paper_book(result: dict, out_dir: Path):
    return write_short_hold_paper_book(
        result, out_dir, title="VWAP pullback paper book"
    )


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Build vwap_pullback paper book")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--db", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--no-portfolio", action="store_true")
    p.add_argument("--max-concurrent", type=int, default=None)
    p.add_argument("--max-per-day", type=int, default=None)
    p.add_argument("--no-stress", action="store_true")
    args = p.parse_args(argv)

    cfg = VwapPullbackConfig(
        start=datetime.fromisoformat(args.start).date(),
        end=datetime.fromisoformat(args.end).date(),
        paper_portfolio=not args.no_portfolio,
        nml_gate=False,
    )
    if args.db:
        cfg.db_path = Path(args.db)
    if args.max_concurrent is not None:
        cfg.paper_max_concurrent = args.max_concurrent
    if args.max_per_day is not None:
        cfg.paper_max_per_day = args.max_per_day
    if not cfg.db_path.exists():
        raise SystemExit(f"entries db missing: {cfg.db_path}")

    limits = PortfolioLimits(
        max_concurrent=cfg.paper_max_concurrent if cfg.paper_portfolio else 10_000,
        max_per_day=cfg.paper_max_per_day if cfg.paper_portfolio else 10_000,
    )
    result = build_paper_book(cfg, limits=limits, run_stress=not args.no_stress)
    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[2] / "batch" / "vwap_pullback" / "paper"
    )
    jpath, mpath = write_paper_book(result, out_dir)
    print(json.dumps(result["paper"]["pooled"], indent=2))
    print("gates", result["paper"]["gates"])
    print("skipped", result["paper"]["n_skipped_portfolio"])
    if result.get("cost_stress_on_taken"):
        for k, a in result["cost_stress_on_taken"].items():
            print(f"{k:16} effR={a['eff_r']:+.4f} pass={a['pass']}")
    print("wrote", jpath, mpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
