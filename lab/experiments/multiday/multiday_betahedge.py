#!/usr/bin/env python3
"""Beta-hedged momentum study — pre-registered (`multiday_betahedge_preregistration.md`).

Tests whether hedging the market beta of the validated equal-weight 12-1 book raises
risk-adjusted return and cuts drawdown (the no-shorting-adapted long/short higher ceiling):

    hedged_return(β) = book_return − β · spy_fwd_H

β ∈ FIXED {0.0, 0.5, 1.0, 1.3} (β=0 = unhedged base). Two cost treatments: idealized
short SPY, and a buyable inverse-S&P ETF haircut (0.9% expense + 0.5% path-decay /yr on
|β| exposure). Reports per β: Sharpe, ann vol, max drawdown, residual SPY beta, CAGR.
2025 hard-sealed out; 2026 never read. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_betahedge \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet \
        --horizon 20 --top-n 50 --cost-bps 10
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.data.market_data import fetch_daily_range

BETAS = (0.0, 0.5, 1.0, 1.3)
ETF_EXPENSE_APR = 0.009      # inverse-S&P ETF expense ratio
ETF_DECAY_APR = 0.005        # conservative daily-reset path-decay allowance


def _base_periods(df: pd.DataFrame, rebal_days, top_n: int) -> pd.Series:
    rows = {}
    for d in rebal_days:
        day = df[df["trade_date"] == d]
        b = day[day["eligible"] & day["mom_12_1"].notna()]
        if b.empty:
            continue
        book = b.sort_values("mom_12_1", ascending=False).head(top_n)
        rows[d] = float(book["realized_r"].astype(float).mean())
    return pd.Series(rows).sort_index()


def _spy_fwd(start, end, H: int) -> pd.Series:
    """SPY split-adjusted forward H-trading-day return, indexed by trading date."""
    spy = fetch_daily_range("SPY", start - timedelta(days=20), end + timedelta(days=int(H * 1.6) + 10),
                            adjustment="split")
    spy = spy.copy()
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    c = spy["close"].astype(float)
    return (c.shift(-H) / c - 1.0)


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def _metrics(r: np.ndarray, spy: np.ndarray, H: int) -> dict:
    n = len(r)
    ann = float(np.sqrt(252.0 / H))
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    equity = np.cumprod(1.0 + r)
    span_years = n * H / 252.0
    cagr = equity[-1] ** (1.0 / span_years) - 1.0 if equity[-1] > 0 else -1.0
    # residual beta vs SPY
    if np.std(spy) > 0:
        beta = float(np.cov(r, spy, ddof=1)[0, 1] / np.var(spy, ddof=1))
        corr = float(np.corrcoef(r, spy)[0, 1])
    else:
        beta = corr = float("nan")
    return {"mean": mean, "ann_vol": sd * ann,
            "sharpe": (mean / sd * ann) if sd > 0 else float("nan"),
            "maxdd": _max_drawdown(equity), "cagr": cagr,
            "resid_beta": beta, "resid_corr": corr}


def _report(label, book, spy, H, haircut: bool):
    print(f"\n=== {label} ===")
    print(f"{'beta':>5} {'Sharpe':>7} {'annVol':>7} {'maxDD':>8} {'CAGR':>8} {'residβ':>7} {'corrSPY':>8}")
    base = None
    for b in BETAS:
        r = book - b * spy
        if haircut:
            r = r - abs(b) * (ETF_EXPENSE_APR + ETF_DECAY_APR) * H / 252.0
        m = _metrics(r.to_numpy(), spy.to_numpy(), H)
        if b == 0.0:
            base = m
        tag = ""
        if b != 0.0 and base is not None:
            dd_better = m["maxdd"] > base["maxdd"] * 0.75  # ≥25% shallower
            sh_better = m["sharpe"] > base["sharpe"]
            tag = "  <-- Sharpe↑ & DD↓" if (dd_better and sh_better) else ""
        print(f"{b:>5.2f} {m['sharpe']:>+7.2f} {m['ann_vol']*100:>6.1f}% {m['maxdd']*100:>+7.1f}% "
              f"{m['cagr']*100:>+7.1f}% {m['resid_beta']:>+7.2f} {m['resid_corr']:>+8.2f}{tag}")


def main() -> None:
    p = argparse.ArgumentParser(description="Beta-hedged momentum study")
    p.add_argument("--ledger", required=True)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--cost-bps", type=float, default=10.0)
    args = p.parse_args()
    H = args.horizon

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    fwd = f"fwd_{H}"
    df = df[df["eligible"] & df[fwd].notna()].copy()
    df["realized_r"] = df[fwd].astype(float) - args.cost_bps / 10000.0
    df["year"] = df["trade_date"].dt.year
    df = df[df["year"] != fs.OOS_YEAR].copy()             # hard seal 2025
    all_days = sorted(df["trade_date"].unique())
    years = sorted(df["year"].unique())

    book = _base_periods(df, all_days[0::H], args.top_n)
    spy_fwd = _spy_fwd(book.index.min(), book.index.max(), H)
    spy = spy_fwd.reindex(book.index)                     # align to rebalance dates
    ok = book.notna() & spy.notna()
    book, spy = book[ok], spy[ok]

    print(f"Beta-hedge study: {path.name}, H={H}d, top_n={args.top_n}, cost={args.cost_bps:.0f}bps")
    print(f"years {years[0]}–{years[-1]} (2025 sealed), {len(book)} non-overlapping periods")
    print(f"SPY per-period mean fwd {spy.mean()*100:+.2f}%  (the market tailwind being hedged)")
    _report("IDEALIZED short-SPY hedge", book, spy, H, haircut=False)
    _report("BUYABLE inverse-ETF hedge (0.9% expense + 0.5% decay /yr on |β|)", book, spy, H, haircut=True)
    print("\nBar (pre-registered): a β IMPROVES only if Sharpe↑ AND maxDD ≥25% shallower vs β=0, "
          "on BOTH windows AND under the ETF haircut.")


if __name__ == "__main__":
    main()
