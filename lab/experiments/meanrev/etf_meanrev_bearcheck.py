#!/usr/bin/env python3
"""STAGE-0 part 2: does the RSI-2 deep-oversold ETF sleeve SURVIVE 2022?

The triage (`etf_meanrev_triage.py`) gave RSI2<5 a CONDITIONAL pass — corr −0.02 to
x03, blend Sharpe 1.66→1.78, maxDD −7.9→−4.2 — but on a 2023-24 ONLY window (the x03
ledger's 252-day formation eats 2022) with just 6% time-in-market. The whole diversifier
thesis is about CRASH regimes, so the decisive question the triage could not answer is:
**how does this dip-buy sleeve behave in the 2022 bear?** Dip-buying a falling knife is
the classic way short-horizon mean reversion dies. We can't get x03's CORRELATION in 2022
(no book pre-2023 from this ledger), but we CAN measure the sleeve STANDALONE straight off
the ETF bars — which answers what matters:

  • Is the sleeve POSITIVE (or at least not run-over) in the 2022 bear, vs SPY's ~−18%?
  • Real TRADE COUNT per year — is the +1.37 triage Sharpe a sample or a fluke?
  • Per-year Sharpe / maxDD across 2022 (bear) / 2023 (recovery) / 2024 (trend).

PASS → open a real mean-reversion family (own letter) + run capture→WF→PBO.
FAIL (bleeds in 2022 or trades too thin) → clean kill, the META-FINDING stands. 2025
stays SEALED (window capped at 2024-12-31). Usage:
    python3 -m trading.lab.experiments.meanrev.etf_meanrev_bearcheck
"""
from __future__ import annotations

import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")  # silence urllib3/LibreSSL + pandas downcast noise

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.experiments.meanrev.etf_meanrev_triage import (
    ETFS, SMA_N, MAX_HOLD, ONEWAY, _rsi, _sharpe, _maxdd,
)

START = date(2021, 1, 1)     # warmup for SMA200 before 2022-01
END = date(2024, 12, 31)     # 2025 SEALED
EVAL_START = pd.Timestamp(2022, 1, 1)


def sleeve(bars: dict[str, pd.DataFrame], cal: pd.DatetimeIndex, ent: float):
    """RSI-2 deep-oversold sleeve. Returns (daily_ret, held_count, total_trades).
    Per-ETF 1/N equal capital, long-or-flat, 200d-uptrend filter."""
    n_uni = len(bars)
    contrib = pd.DataFrame(0.0, index=cal, columns=list(bars.keys()))
    held_cnt = pd.Series(0.0, index=cal)
    trades = 0
    for tk, df in bars.items():
        c = df["close"]; ret = c.pct_change()
        up = c > c.rolling(SMA_N).mean()
        sig = _rsi(c, 2)
        enter = (up & (sig < ent)).reindex(cal, fill_value=False).values
        exit_ = (sig > 50.0).reindex(cal, fill_value=False).values
        warmup = int((df.index < cal[0]).sum())          # bars before the eval window
        if warmup < SMA_N:                               # guard: SMA200 not warm at 2022-01
            print(f"  ! {tk}: only {warmup} warmup bars before {cal[0].date()} "
                  f"(<{SMA_N}) — SMA{SMA_N} undefined early, 2022 read CONTAMINATED")
        retv = ret.reindex(cal).fillna(0.0).values
        held = np.zeros(len(cal), dtype=bool)
        in_pos = False; days = 0
        for i in range(len(cal)):
            if in_pos:
                days += 1
                if exit_[i] or days >= MAX_HOLD:
                    in_pos = False
            if not in_pos and enter[i]:
                in_pos = True; days = 0
            held[i] = in_pos
        w_next = np.concatenate([[False], held[:-1]])
        trans = np.concatenate([[False], held[:-1] != held[1:]])
        trades += int(((~np.concatenate([[False], held[:-1]])) & np.concatenate([[False], held[1:]])).sum())
        contrib[tk] = (w_next * retv - trans * ONEWAY) / n_uni
        held_cnt += pd.Series(w_next.astype(float), index=cal)
    return contrib.sum(axis=1), held_cnt, trades


def yr_stats(daily: pd.Series, held_cnt: pd.Series, year: int, spy: pd.Series):
    d = daily[daily.index.year == year]
    h = held_cnt[held_cnt.index.year == year]
    sp = spy[spy.index.year == year]
    sleeve_ret = float(np.prod(1 + d.values) - 1) * 100
    spy_ret = float(np.prod(1 + sp.values) - 1) * 100
    return (sleeve_ret, _sharpe(d.values, 252.0) if d.std() > 0 else float("nan"),
            _maxdd(d.values) * 100, float((h > 0).mean()) * 100, spy_ret)


def main() -> None:
    force = "--force" in sys.argv
    bars: dict[str, pd.DataFrame] = {}
    for tk in ETFS:
        b = fetch_daily_range(tk, START, END, adjustment="split", force=force)
        if b is None or b.empty:
            continue
        b.index = pd.DatetimeIndex(b.index).normalize().tz_localize(None)
        b = b[~b.index.duplicated(keep="last")].sort_index()
        bars[tk] = b
    spy_bars = fetch_daily_range("SPY", START, END, adjustment="split", force=force)
    spy_bars.index = pd.DatetimeIndex(spy_bars.index).normalize().tz_localize(None)
    spy_ret = spy_bars["close"].pct_change()

    cal = sorted(set().union(*[set(b.index) for b in bars.values()]))
    cal = pd.DatetimeIndex([d for d in cal if d >= EVAL_START and d <= pd.Timestamp(END)])
    spy_ret = spy_ret.reindex(cal).fillna(0.0)

    print(f"RSI-2 ETF sleeve — 2022 BEAR-WINDOW standalone check  ({len(bars)} ETFs, 2025 SEALED)")
    print(f"window {cal[0].date()}..{cal[-1].date()}\n")
    for ent in (5.0, 10.0):
        daily, held_cnt, trades = sleeve(bars, cal, ent)
        full_sh = _sharpe(daily.values, 252.0)
        full_dd = _maxdd(daily.values) * 100
        full_ret = float(np.prod(1 + daily.values) - 1) * 100
        print(f"=== RSI2<{ent:g}  |  full 2022-24: ret {full_ret:+.1f}%  Sharpe {full_sh:+.2f}"
              f"  maxDD {full_dd:+.1f}%  trades {trades}  ===")
        print(f"{'year':>6}{'sleeve%':>9}{'Sharpe':>8}{'maxDD%':>8}{'expo%':>7}{'SPY%':>8}{'regime':>10}")
        for year, lbl in ((2022, "BEAR"), (2023, "recovery"), (2024, "trend")):
            sret, ssh, sdd, sexp, spyr = yr_stats(daily, held_cnt, year, spy_ret)
            print(f"{year:>6}{sret:>+9.1f}{ssh:>+8.2f}{sdd:>+8.1f}{sexp:>7.0f}{spyr:>+8.1f}{lbl:>10}")
        print()
    print(">>> PASS: sleeve POSITIVE (or clearly beats SPY) in 2022 BEAR + a real trade count")
    print("    (≳40-50 across 3yr) -> open a mean-reversion family, run capture→WF→PBO.")
    print("    FAIL: negative/run-over in 2022 or trades too thin -> kill; META-FINDING stands.")


if __name__ == "__main__":
    main()
