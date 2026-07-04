#!/usr/bin/env python3
"""EXPLORATORY: turnover buffer (rank hysteresis) on x03 residual momentum.

Peer reviewers (Gemini, Grok) suggested a turnover buffer: don't sell a current
holding the moment it drops below rank top_n — keep it until it falls past a wider
band B (e.g. rank 65), and only fill the freed slots with fresh top names. This cuts
churn. Question: does the cost saving (less trading) beat the gross drag (holding
slightly staler, lower-ranked names)?

Honest prior (LOW): our own work showed turnover is already low (~30% one-way,
~3bps/rebalance) and net Sharpe ≈ gross, flat to $250M AUM — so cost is NOT the leak
here, which caps the buffer's upside. This settles it with evidence.

Mechanics per rebalance, for a target book of TOP_N with band B (B >= TOP_N):
  1. score + rank all eligible candidates (rank 1 = best residual momentum).
  2. KEEP current holdings whose new rank <= B (hysteresis); cap keepers at TOP_N best.
  3. FILL the remaining slots with the highest-ranked non-held names.
  4. turnover = (# names sold) / TOP_N  (one-way).  B == TOP_N reproduces hard x03.
Cost is turnover-scaled and charged to EVERY scheme identically: cost_rebal =
turnover * COST_ONEWAY (COST_ONEWAY=10bps == the per-rebalance charge at 100% turnover,
matching the project's 3bps@30%-turnover convention). Reports GROSS and NET so the
cost-saving vs gross-drag decomposition is visible. 2025 hard-sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom_buffer \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet
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

H = 20
TOP_N = 50
COST_ONEWAY = 10.0 / 10000.0   # per-rebalance charge at 100% turnover
FORM_LB = 252
SKIP = 21
MIN_OBS = 126


def _beta_adj_alpha(r, m):
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _stats(r, m):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    return (r.mean(), r.mean() / sd * ann if sd > 0 else np.nan, beta, a, t_a,
            float((eq / peak - 1).min()))


def simulate(periods, top_n, band):
    """periods: list of (tickers[np.str], scores[np.float], fwd[np.float], mkt).
    Returns gross_r, net_r, mkt, turnovers (excl. initial deploy)."""
    held: list[str] = []
    gross, net, mkts, turns = [], [], [], []
    for tk, sc, fw, mk in periods:
        order = np.argsort(-sc)                         # best first
        ranked = tk[order]                              # tickers by rank
        rank_of = {t: i for i, t in enumerate(ranked)}  # 0-based rank
        fwd_of = dict(zip(tk, fw))
        # keepers: current holdings still within the band, best-ranked first, capped
        keepers = [t for t in held if rank_of.get(t, 10**9) < band]
        keepers.sort(key=lambda t: rank_of[t])
        keepers = keepers[:top_n]
        keep_set = set(keepers)
        # fills: highest-ranked names not already held, until book == top_n
        fills = []
        for t in ranked:
            if len(keepers) + len(fills) >= top_n:
                break
            if t not in keep_set:
                fills.append(t)
        book = keepers + fills
        sold = len(set(held) - set(book)) if held else 0
        turnover = sold / top_n
        g = float(np.mean([fwd_of[t] for t in book]))
        cost = turnover * COST_ONEWAY
        gross.append(g); net.append(g - cost); mkts.append(mk)
        if held:                                        # skip initial deploy in turnover stat
            turns.append(turnover)
        held = book
    return np.array(gross), np.array(net), np.array(mkts), np.array(turns)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    p.add_argument("--top-n", type=int, default=TOP_N)
    args = p.parse_args()
    top_n = args.top_n
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()

    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dates = list(close.index)
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")
    cols = np.array(close.columns)

    periods = []
    for d in dates[::H]:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi]
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        cand = elig_row & np.isfinite(fwd_row) & (np.isfinite(win.values).sum(axis=0) >= MIN_OBS)
        if cand.sum() < top_n:
            continue
        Rc = win.values[:, cand]; mask = np.isfinite(Rc)
        beta = (np.where(mask, Rc, 0.0) * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        score = np.nanmean(resid, axis=0) / np.nanstd(resid, axis=0, ddof=1)
        good = np.isfinite(score) & np.isfinite(fwd_row[cand])
        mk = float(spy_fwd.loc[d])
        if good.sum() < top_n or not np.isfinite(mk):
            continue
        tk = cols[cand][good]
        periods.append((tk, score[good], fwd_row[cand][good], mk))

    n = len(periods)
    print(f"Turnover-buffer sweep: {path.name}  (top_n={top_n}, {n} periods, 2025 sealed)\n")
    print(f"{'band':>10}{'turn%':>7}{'GROSSsh':>8}{'NETsh':>7}{'NETper%':>9}"
          f"{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}")
    for band in (top_n, top_n + 10, top_n + 15, top_n + 25, top_n + 50, 2 * top_n):
        g, nt, mk, tu = simulate(periods, top_n, band)
        gmean, gsh, _, _, _, _ = _stats(g, mk)
        nmean, nsh, beta, a, t_a, dd = _stats(nt, mk)
        lbl = f"{band}" + (" (x03)" if band == top_n else "")
        print(f"{lbl:>10}{tu.mean()*100:>7.0f}{gsh:>+8.2f}{nsh:>+7.2f}{nmean*100:>+9.2f}"
              f"{beta:>+7.2f}{a*100:>+8.2f}{t_a:>+7.2f}{dd*100:>+8.1f}")
    print("\n>>> Read: band==top_n is the hard x03 baseline (NET, turnover-scaled cost).")
    print("    A buffer WINS only if NETsh rises as band widens. If GROSSsh falls faster")
    print("    than cost is saved, the buffer holds staler names for no net gain → reject.")


if __name__ == "__main__":
    main()
