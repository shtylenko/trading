"""Multi-strategy scan CLI — dispatches to the registered family pipeline.

Default strategy is **warrior**. Pass ``--strategy cup_handle`` (etc.) for
other families. Family implementations live under ``strategies/<id>/``.
"""

from __future__ import annotations

import logging
import sys
from datetime import date as date_cls
from pathlib import Path

import yaml

from .strategies import get_strategy, list_strategies
from .strategies.warrior.runner import ScanStats, run_scan  # noqa: F401 — re-export

log = logging.getLogger("llm_trader")


def main(argv: list[str] | None = None) -> int:
    from .cli import build_parser, config_from_args

    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if getattr(args, "list_strategies", False):
        for sid in list_strategies():
            s = get_strategy(sid)
            print(f"{sid:12}  {s.name}  ({s.horizon.kind}/{s.horizon.bar_resolution})")
        return 0

    strategy_id = getattr(args, "strategy", None) or "warrior"
    strat = get_strategy(strategy_id)
    symbols = [s.upper() for s in args.symbols] if args.symbols else None

    if strategy_id == "warrior":
        cfg = config_from_args(args)
        strat.run_scan(
            cfg,
            max_symbols=args.max_symbols,
            symbols=symbols,
        )
    else:
        if args.config:
            raw = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
            cfg = strat.config_from_dict(raw)
        else:
            cfg = strat.default_scan_config()
        if args.start:
            cfg.start = date_cls.fromisoformat(args.start)
        if args.end:
            cfg.end = date_cls.fromisoformat(args.end)
        if args.db:
            cfg.db_path = Path(args.db)
        if args.price_min is not None:
            cfg.price_min = args.price_min
        if args.price_max is not None:
            cfg.price_max = args.price_max
        strat.run_scan(
            cfg,
            max_symbols=args.max_symbols,
            symbols=symbols,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
