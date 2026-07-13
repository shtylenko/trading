"""Validation battery for Momentum Burst @ 5-day hold.

(1) Out-of-sample temporal split: 2022-2023 (in-sample) vs 2024-2025 (held out).
    NB: no parameters are fitted on the data — thresholds come from the strategy
    doc — so this is an OOS *stability* check, not an overfit-recovery test.
(2) Parameter robustness: perturb each threshold; confirm the edge is not a
    knife-edge artifact of specific cutoffs.
(3) Cost stress: 5 / 10 / 15 / 20 bps per side.
(4) Regime-filter value + bear-year (2022) behavior.

    python3 -m trading.strategytester.scripts.validate_momentum_burst
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.strategytester.common.engine import run_strategy
from trading.strategytester.common.metrics import trade_metrics
from trading.strategytester.common.panel import build_panel, CACHE_DIR
from trading.strategytester.common.universe import union_tickers
from trading.strategytester.momentum_burst.signals import make_signals, DEFAULTS

CACHE_KEY = "liquid_2022_2025"
START, END = date(2022, 1, 1), date(2025, 12, 31)
HOLD = 5


def _m(trades, lo=START, hi=END):
    # default window = eval window (excludes 2020-2021 warmup-region signals)
    t = trades
    if lo is not None:
        t = t[pd.to_datetime(t["entry_date"]).dt.date >= lo]
    if hi is not None:
        t = t[pd.to_datetime(t["entry_date"]).dt.date <= hi]
    if t.empty:
        return dict(n=0, exp=np.nan, td=np.nan, pf=np.nan, win=np.nan)
    m = trade_metrics(t)
    return dict(n=m["n_trades"], exp=round(m["avg_ret_net"] * 1e4, 1),
                td=m["t_stat_day"], pf=m["profit_factor"], win=round(m["win_rate"], 2))


def main() -> None:
    uni = union_tickers("liquid_pit", START, END)
    panel = build_panel(uni, START, END, cache_key=CACHE_KEY, warmup_days=500)
    ctx = pd.read_parquet(CACHE_DIR / "market_context.parquet")
    base = make_signals()

    # ---- (1) OOS temporal split ----
    print("=" * 78)
    print("(1) OUT-OF-SAMPLE TEMPORAL SPLIT  (Momentum Burst, hold=5)")
    for cost in (5.0, 10.0):
        tr = run_strategy(panel, base, max_hold=HOLD, cost_bps=cost, ctx=ctx)
        full = _m(tr); is_ = _m(tr, date(2022,1,1), date(2023,12,31)); oos = _m(tr, date(2024,1,1), date(2025,12,31))
        print(f"\n  cost={cost:.0f}bps/side")
        for lab, mm in [("FULL 22-25", full), ("IS  22-23", is_), ("OOS 24-25", oos)]:
            print(f"    {lab:11s} n={mm['n']:6d} exp={mm['exp']:+6.1f}bps  day-t={mm['td']:+5.2f}  PF={mm['pf']:.3f}  win={mm['win']}")

    # ---- (2) parameter robustness (full sample, 5bps) ----
    print("\n" + "=" * 78)
    print("(2) PARAMETER ROBUSTNESS  (full sample, 5bps, hold=5) — edge should persist")
    grid = [
        ("default", {}),
        ("up_thresh=1.03", dict(up_thresh=1.03)),
        ("up_thresh=1.05", dict(up_thresh=1.05)),
        ("up_thresh=1.06", dict(up_thresh=1.06)),
        ("close_pos>=0.0", dict(close_pos_min=0.0)),
        ("close_pos>=0.6", dict(close_pos_min=0.6)),
        ("vol_gt_prior=off", dict(vol_gt_prior=False)),
        ("prior_calm=off", dict(prior_calm_max=1e9)),
        ("trend_filter=off", dict(require_trend=False)),
    ]
    for lab, ov in grid:
        tr = run_strategy(panel, make_signals(**ov), max_hold=HOLD, cost_bps=5.0, ctx=ctx)
        mm = _m(tr)
        print(f"    {lab:18s} n={mm['n']:6d} exp={mm['exp']:+6.1f}bps  day-t={mm['td']:+5.2f}  PF={mm['pf']:.3f}")

    # ---- (3) cost stress ----
    print("\n" + "=" * 78)
    print("(3) COST STRESS  (default, full sample, hold=5)")
    for cost in (5.0, 10.0, 15.0, 20.0):
        tr = run_strategy(panel, base, max_hold=HOLD, cost_bps=cost, ctx=ctx)
        mm = _m(tr)
        print(f"    {cost:4.0f}bps/side  exp={mm['exp']:+6.1f}bps  day-t={mm['td']:+5.2f}  PF={mm['pf']:.3f}")

    # ---- (4) regime filter value + bear year ----
    print("\n" + "=" * 78)
    print("(4) REGIME FILTER (spy_bull) value + 2022 bear behavior (5bps, hold=5)")
    for lab, ov in [("regime ON", {}), ("regime OFF", dict(require_regime=False))]:
        tr = run_strategy(panel, make_signals(**ov), max_hold=HOLD, cost_bps=5.0, ctx=ctx)
        allm = _m(tr); y22 = _m(tr, date(2022,1,1), date(2022,12,31))
        print(f"    {lab:11s} full: n={allm['n']:6d} exp={allm['exp']:+6.1f} day-t={allm['td']:+5.2f} | "
              f"2022: n={y22['n']:5d} exp={y22['exp']:+6.1f} day-t={y22['td']:+5.2f}")


if __name__ == "__main__":
    main()
