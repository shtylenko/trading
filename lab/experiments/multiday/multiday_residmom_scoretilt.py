#!/usr/bin/env python3
"""EXPLORATORY: rank-based score-tilt weighting vs equal-weight, on residual momentum.

Question (operator-posed): x03/x04 hold the top-N residual-momentum names EQUAL-WEIGHT.
Would a MILD tilt toward the higher-scored names (~10-15% more on the top, ~10-15% less
on the bottom) improve risk-adjusted return — without skewing the book too much?

Scheme (bounded, monotonic, reduces to equal-weight at s=0 so EW is the embedded null):
  for a name at rank r in 1..N (1 = highest score):
      multiplier_r = 1 + s * (1 - 2*(r-1)/(N-1))     # top -> 1+s, bottom -> 1-s, mean = 1
      weight_r     = multiplier_r / sum(multiplier)   # renormalized, fully invested
  s = 0.125 ~= the operator's "+/-12.5%". This is RANK-based, not score-proportional:
  the score's cross-sectional RANK is informative; its cardinal gaps are noisy, so we do
  NOT weight proportional to the raw score.

It reports, per (top_n, s): per-period mean, annualized Sharpe, market beta,
beta-adjusted alpha + t(alpha) (the edge we actually care about — raw Sharpe can be
beta), max drawdown, and effective-N (1/sum w^2, the concentration cost of the tilt).

WARNING: diagnostic, NOT a validated scheme. Sweeping s and reading the best back is
selection bias. The honest bar: a tilt must MEANINGFULLY beat equal-weight on t(alpha)
AND not deepen maxDD / shrink effective-N for little gain — and then survive a sealed
OOS year before it could ship. Run on BOTH in-sample windows (regime robustness); 2025
is hard-sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residmom_scoretilt \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet
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
COST = 10.0 / 10000.0
FORM_LB = 252
SKIP = 21
MIN_OBS = 126
TOP_NS = (50, 35)
TILTS = (0.0, 0.05, 0.10, 0.125, 0.15, 0.25, 0.50)


def _beta_adj_alpha(r, m):
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    a, b = bhat[0], bhat[1]
    return a, a / np.sqrt(cov[0, 0]), b


def _tilt_weights(n, s):
    """Rank-based bounded tilt weights for n names (rank 0 = top). EW when s=0."""
    if n == 1:
        return np.array([1.0])
    ranks = np.arange(n)
    mult = 1.0 + s * (1.0 - 2.0 * ranks / (n - 1))   # top->1+s, bottom->1-s, mean=1
    return mult / mult.sum()


def _row(label, r, m, eff_n):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    sh = r.mean() / sd * ann if sd > 0 else np.nan
    maxdd = float((eq / peak - 1).min())
    print(f"{label:>14}{eff_n:>8.1f}{r.mean()*100:>+9.2f}{sh:>+7.2f}"
          f"{beta:>+7.2f}{a*100:>+8.2f}{t_a:>+7.2f}{maxdd*100:>+8.1f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    args = p.parse_args()
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()    # hard seal 2025

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

    rebal = dates[::H]
    periods = []   # per rebalance: (sorted-desc score array, matching fwd array, market fwd)
    minN = min(TOP_NS)
    for d in rebal:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi]
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        ok_fwd = np.isfinite(fwd_row)
        Rw = win.values
        obs = np.isfinite(Rw).sum(axis=0)
        cand = elig_row & ok_fwd & (obs >= MIN_OBS)
        if cand.sum() < minN:
            continue
        Rc = Rw[:, cand]
        mask = np.isfinite(Rc)
        Rc0 = np.where(mask, Rc, 0.0)
        beta = (Rc0 * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        rm = np.nanmean(resid, axis=0)
        rs = np.nanstd(resid, axis=0, ddof=1)
        score = np.where(rs > 0, rm / rs, np.nan)
        fwd_c = fwd_row[cand]
        good = np.isfinite(score) & np.isfinite(fwd_c)
        mk = float(spy_fwd.loc[d])
        if good.sum() < minN or not np.isfinite(mk):
            continue
        sc, fw = score[good], fwd_c[good]
        order = np.argsort(-sc)            # high score first
        periods.append((sc[order], fw[order], mk))

    n = len(periods)
    print(f"Score-tilt weighting sweep: {path.name}  ({n} non-overlapping periods, 2025 sealed)\n")
    if n < 10:
        print("too few periods"); return
    print("weighting: rank-based, multiplier_r = 1 + s*(1 - 2*(r-1)/(N-1)); s=0 is equal-weight.")
    print("flat 10bps cost per period (turnover from the tilt is small and NOT separately charged"
          " — this mildly FAVORS the tilt, so a non-win is a robust non-win).\n")

    for top_n in TOP_NS:
        ew_ret = None
        print(f"=== top_n = {top_n} ===")
        print(f"{'scheme':>14}{'effN':>8}{'perPer%':>9}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}")
        for s in TILTS:
            w = _tilt_weights(top_n, s)
            eff_n = 1.0 / float(np.sum(w * w))
            rr, mm = [], []
            for sc, fw, mk in periods:
                if len(fw) < top_n:
                    continue
                rr.append(float(np.dot(w, fw[:top_n])) - COST); mm.append(mk)
            label = "EW (s=0)" if s == 0.0 else f"s={s:.3f}"
            _row(label, rr, mm, eff_n)
            if s == 0.0:
                ew_ret = np.asarray(rr)
        # correlation of the strongest tilt to EW (how different is the book really?)
        if ew_ret is not None:
            w = _tilt_weights(top_n, max(TILTS))
            tr = np.array([float(np.dot(w, fw[:top_n])) - COST
                           for sc, fw, mk in periods if len(fw) >= top_n])
            print(f"   corr(EW, s={max(TILTS):.2f}) per-period returns = "
                  f"{np.corrcoef(ew_ret, tr)[0,1]:+.4f}\n")

    print(">>> Read: a tilt is only interesting if t(α) rises MEANINGFULLY vs EW while maxDD does")
    print("    NOT deepen and effN stays high. If t(α)/Sharpe are flat and corr-to-EW ~1.00, the")
    print("    tilt is doing nothing but adding concentration/turnover risk — keep equal-weight.")
    print("    Any apparent winner is in-sample + cherry-picked; it must clear a SEALED OOS year.")


if __name__ == "__main__":
    main()
