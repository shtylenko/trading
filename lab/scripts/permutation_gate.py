#!/usr/bin/env python3
"""Run the four-step permutation gauntlet on a bar-signal strategy.

Steps (Masters / neurotrader):
  1. In-sample excellence (optimize on the train window, eyeball the PF)
  2. In-sample Monte Carlo permutation test   — pass: p < 0.01
  3. Walk-forward test on the holdout window
  4. Walk-forward Monte Carlo permutation test — pass: p <= 0.05 (1y OOS),
     p < 0.01 (2y+ OOS)

By default runs the built-in Donchian breakout demo on cached daily bars.
Custom strategies: pass --strategy mymodule:OBJ where OBJ is a dict with
keys ``optimize_fn(ohlc)->params``, ``signal_fn(ohlc, params)->Series``
and ``optimize_objective_fn(ohlc)->float``.

Usage:
    python3 -m trading.lab.scripts.permutation_gate \\
        --ticker SPY --timeframe 1day --train-start 2018-01-01 \\
        --train-end 2023-12-31 --oos-end 2025-12-31 \\
        --insample-perms 1000 --wf-perms 200
"""

from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from trading.lab.validation import (
    insample_permutation_test,
    position_returns,
    profit_factor,
    walk_forward_signal,
    walkforward_permutation_test,
)
from trading.lab.validation.examples import (
    optimize_donchian,
    donchian_signal,
    optimize_donchian_objective,
)


def _load_strategy(spec: str | None) -> dict:
    if not spec:
        return {
            "name": "donchian_breakout (demo)",
            "optimize_fn": optimize_donchian,
            "signal_fn": donchian_signal,
            "optimize_objective_fn": optimize_donchian_objective,
        }
    mod_name, _, obj_name = spec.partition(":")
    obj = getattr(importlib.import_module(mod_name), obj_name)
    missing = {"optimize_fn", "signal_fn", "optimize_objective_fn"} - set(obj)
    if missing:
        raise SystemExit(f"Strategy spec missing keys: {missing}")
    obj.setdefault("name", spec)
    return obj


def main() -> None:
    p = argparse.ArgumentParser(description="Permutation-test gauntlet",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--timeframe", default="1day", choices=["1min", "5min", "15min", "1day"])
    p.add_argument("--train-start", required=True)
    p.add_argument("--train-end", required=True, help="end of in-sample window (= first walk-forward fold)")
    p.add_argument("--oos-end", required=True, help="end of walk-forward evaluation data")
    p.add_argument("--train-step", type=int, default=30, help="bars between walk-forward refits")
    p.add_argument("--insample-perms", type=int, default=1000)
    p.add_argument("--wf-perms", type=int, default=200)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--strategy", help="module:dict spec for a custom strategy")
    args = p.parse_args()

    strat = _load_strategy(args.strategy)

    from zoneinfo import ZoneInfo
    from trading.marketdata import fetch_bars

    ny = ZoneInfo("America/New_York")
    t0 = datetime.fromisoformat(args.train_start).replace(tzinfo=ny)
    t1 = datetime.fromisoformat(args.train_end).replace(tzinfo=ny, hour=23, minute=59)
    t2 = datetime.fromisoformat(args.oos_end).replace(tzinfo=ny, hour=23, minute=59)

    print(f"Strategy: {strat['name']}   Data: {args.ticker} {args.timeframe} "
          f"{args.train_start}..{args.oos_end}")
    bars = fetch_bars(args.ticker, args.timeframe, start=t0, end=t2, session="rth")
    if bars is None or bars.empty:
        raise SystemExit("No data")
    bars = bars[["open", "high", "low", "close"]
                + (["volume"] if "volume" in bars.columns else [])].dropna()
    train = bars[bars.index <= t1]
    train_lookback = len(train)
    oos_bars = len(bars) - train_lookback
    print(f"Bars: {len(bars)} total = {train_lookback} train + {oos_bars} OOS\n")

    # ── Step 1: in-sample excellence ───────────────────────────────────
    real_is = float(strat["optimize_objective_fn"](train))
    print(f"[1] In-sample optimized objective: {real_is:.4f}")
    print("    Judge it yourself: is this excellent? Is it obviously overfit?\n")

    # ── Step 2: in-sample permutation test ─────────────────────────────
    print(f"[2] In-sample permutation test ({args.insample_perms} permutations)...")
    r2 = insample_permutation_test(train, strat["optimize_objective_fn"],
                                   n_permutations=args.insample_perms,
                                   seed=args.seed, progress=True)
    print(r2.summary())
    is_pass = r2.p_value < 0.01
    print(f"    GATE: {'PASS' if is_pass else 'FAIL'} (require p < 0.01)\n")
    if not is_pass:
        print("In-sample gate failed — stop here; do NOT spend out-of-sample data.")
        return

    # ── Step 3: walk-forward test ──────────────────────────────────────
    sig = walk_forward_signal(bars, strat["optimize_fn"], strat["signal_fn"],
                              train_lookback, args.train_step)
    wf_pf = profit_factor(position_returns(bars["close"], sig))
    print(f"[3] Walk-forward objective on {oos_bars} OOS bars: {wf_pf:.4f}")
    print("    Judge it yourself: is this worth trading?\n")

    # ── Step 4: walk-forward permutation test ──────────────────────────
    print(f"[4] Walk-forward permutation test ({args.wf_perms} permutations; slow)...")
    r4 = walkforward_permutation_test(bars, strat["optimize_fn"], strat["signal_fn"],
                                      train_lookback, args.train_step,
                                      n_permutations=args.wf_perms,
                                      seed=args.seed, progress=True)
    print(r4.summary())
    years_oos = oos_bars / (252 if args.timeframe == "1day" else 252 * 390)
    threshold = 0.05 if years_oos <= 1.25 else 0.01
    wf_pass = r4.p_value <= threshold
    print(f"    GATE: {'PASS' if wf_pass else 'FAIL'} "
          f"(require p <= {threshold:.0%} for ~{years_oos:.1f}y OOS)\n")

    print("VERDICT:", "PASS — strategy survives both permutation gates"
          if wf_pass else "FAIL — do not trade this configuration")


if __name__ == "__main__":
    main()
