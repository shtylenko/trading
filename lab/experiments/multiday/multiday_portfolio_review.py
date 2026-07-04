#!/usr/bin/env python3
"""Portfolio / capacity / turnover / drawdown review for the validated 12-1 momentum
book (x01) — the "the simulation is optimistic" gate before treating it as deployable
(EXPLORATION_PLAYBOOK §6b). Offline on the existing capture; no engine, no new data.

The idealized backtest assumes independent equal-weight trades and (conservatively)
charged 10 bps as if the WHOLE book turns over every rebalance. This review checks what
deployment actually looks like:

  1. TURNOVER  — fraction of the top-50 that changes each rebalance. Momentum is
     persistent, so real turnover < 100% → realistic cost is LOWER than the 10 bps
     headline. Reports turnover-adjusted net Sharpe.
  2. CAPACITY  — AUM the equal-weight book can absorb at ≤ 5% of each name's 20-day
     dollar volume (the least-liquid held name binds). Median + 10th percentile.
  3. DRAWDOWN  — max drawdown and worst rebalance of the net equity curve.
  4. CONCENTRATION — equal-weight 50 names = 2%/name (stated).

Default window 2022–2025 (survivorship-honest PIT); pre-2022 is survivorship-optimistic.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_portfolio_review \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

H = 20
TOP_N = 50
RT_COST = 0.0010   # 10 bps round-trip per name actually traded
ADV_CAP = 0.05     # max 5% of a name's 20-day dollar volume
ANN = float(np.sqrt(252.0 / H))


def main() -> None:
    p = argparse.ArgumentParser(description="Momentum portfolio/capacity/turnover review")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025.parquet")
    p.add_argument("--start-year", type=int, default=2022, help="honest PIT window start")
    p.add_argument("--end-year", type=int, default=2024, help="inclusive; 2025 sealed-but-spent")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    yr = df["trade_date"].dt.year
    df = df[df["eligible"] & (yr >= args.start_year) & (yr <= args.end_year) & df["fwd_20"].notna()].copy()

    all_days = sorted(df["trade_date"].unique())
    rebal = all_days[::H]
    print(f"Portfolio review: {path.name}, {args.start_year}-{args.end_year}, "
          f"top-{TOP_N} 12-1 momentum, {len(rebal)} rebalances. "
          f"(pre-2022 survivorship-optimistic; this window is PIT-honest)\n")

    books, period_ret, caps = [], [], []
    for d in rebal:
        day = df[df["trade_date"] == d].dropna(subset=["mom_12_1", "fwd_20", "dollar_vol_20d"])
        if len(day) < TOP_N:
            continue
        top = day.sort_values("mom_12_1", ascending=False).head(TOP_N)
        books.append((d, set(top["ticker"])))
        period_ret.append((d, float(top["fwd_20"].mean())))
        # capacity: equal weight A/50 per name ≤ 5% of that name's $vol → A ≤ 50*0.05*min($vol)
        caps.append(float(TOP_N * ADV_CAP * top["dollar_vol_20d"].min()))

    # ── turnover ─────────────────────────────────────────────────────────────
    turns = [len(books[i][1] - books[i - 1][1]) / TOP_N for i in range(1, len(books))]
    avg_turn = float(np.mean(turns))
    print("=== 1. TURNOVER ===")
    print(f"  avg one-way turnover/rebalance = {avg_turn*100:.0f}% of the book "
          f"({avg_turn*TOP_N:.0f} of {TOP_N} names change)")
    print(f"  → names held: ~{(1-avg_turn)*100:.0f}% persist month-to-month (momentum is sticky)")

    # ── returns: headline (100%-turnover cost) vs realistic (turnover-scaled) ─
    r = np.array([x[1] for x in period_ret])
    dts = pd.DatetimeIndex([x[0] for x in period_ret])
    def stats(net):
        m, sd = net.mean(), net.std(ddof=1)
        eq = (1 + pd.Series(net)).cumprod()
        dd = float((eq / eq.cummax() - 1).min())
        return m, (m / sd * ANN if sd > 0 else float("nan")), dd
    head_net = r - RT_COST                         # headline: charge full book (my 10bps)
    real_net = r - avg_turn * RT_COST              # realistic: charge only the turned-over fraction
    print("\n=== 2. COST REALISM ===")
    for label, net in [("headline (100% turnover, -10bps)", head_net),
                       ("realistic (turnover-scaled cost)", real_net),
                       ("gross (0 cost)", r)]:
        m, sh, _ = stats(net)
        print(f"  {label:38} per-period {m*100:+.3f}%  ann.Sharpe {sh:+.2f}")
    print(f"  → realistic per-name cost ≈ {avg_turn*RT_COST*1e4:.1f} bps/rebalance "
          f"(vs the 10 bps headline) — momentum's persistence makes it cheaper to run.")

    # ── drawdown ─────────────────────────────────────────────────────────────
    _, _, dd = stats(real_net)
    worst = float(real_net.min())
    print("\n=== 3. DRAWDOWN / TAIL (realistic-cost net equity curve) ===")
    print(f"  max drawdown = {dd*100:+.1f}%   worst single rebalance = {worst*100:+.1f}%")
    print(f"  positive rebalances = {100*(real_net>0).mean():.0f}%")

    # ── capacity ─────────────────────────────────────────────────────────────
    caps = np.array(caps)
    print("\n=== 4. CAPACITY (equal-weight, ≤5% of each name's 20d $-volume; least-liquid binds) ===")
    print(f"  median AUM capacity = ${np.median(caps)/1e6:.0f}M   "
          f"10th pct = ${np.percentile(caps,10)/1e6:.0f}M   min = ${caps.min()/1e6:.0f}M")
    print(f"  (1-day-ADV basis; spreading entries over the 20-day hold scales this up ~linearly)")
    print(f"  concentration: equal-weight {TOP_N} names = {100/TOP_N:.0f}% each.")

    print("\nReadout: the 10-bps headline OVER-charges (assumes full turnover); real "
          "turnover-scaled costs are lower, so deployed net ≥ the reported figure. "
          "Capacity is the binding real-world limit for larger AUM. Drawdown/tail is the "
          "risk to size against. Still owes live borrow/slippage validation before capital.")


if __name__ == "__main__":
    main()
