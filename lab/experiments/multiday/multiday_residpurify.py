#!/usr/bin/env python3
"""x05 Arm A — β-estimate cleaning on x03 residual momentum (PRE-REGISTERED, LOCKED).

Spec: `validation/research_log/multiday_x05_residual_purification_preregistration.md`.
Zero new data — recomputes everything from the split/YF capture ledgers + SPY.

Baseline = x03 exactly (CAPM-residual score mean(ε)/std(ε), formation [d-252,d-21], top-50 EW,
monthly non-overlapping H=20, 10bps). Arm A pre-FILTERS the eligible set by β-estimate
trustworthiness BEFORE ranking, then ranks survivors by the UNCHANGED IR score and takes top-50:
  • primary  : split-half instability |β_h1 − β_h2| over the formation window; drop worst 20%.
  • se(β)    : OLS standard error of the full-window β; drop worst 20%  (robustness proxy).
Book width stays 50 (this is not the concentration lever — that is x04). Headline metric =
BETA-ADJUSTED ALPHA (intercept + t of book per-period returns on SPY) + realized β, Sharpe,
maxDD, gross CAGR, corr to baseline. Verdict per the locked decision rule (both windows).
No sealed year touched (rebalance dates bounded to the in-sample window). Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residpurify \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet --window 2022-2024
    python3 -m trading.lab.experiments.multiday.multiday_residpurify \
        --ledger trading/lab/experiments/_data/_capture_multiday_2009_2016_yf.parquet --window 2009-2016
"""
from __future__ import annotations

import argparse
import sys
import warnings
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")  # pandas pct_change/fillna FutureWarnings — cosmetic

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
FORM_LB = 252
SKIP = 21
MIN_OBS = 126
DROP_FRAC = 0.20          # pre-committed: exclude the worst 20% by β-untrustworthiness


def _beta_adj_alpha(r, m):
    """OLS intercept (alpha) + t-stat + slope (beta) of book returns r on market m."""
    n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat
    s2 = (e @ e) / (n - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _metrics(r, m):
    r = np.asarray(r); ann = np.sqrt(252.0 / H)
    sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    cagr = float(eq[-1] ** (252.0 / H / len(r)) - 1.0)
    return {"n": len(r), "sharpe": r.mean() / sd * ann if sd > 0 else np.nan,
            "beta": beta, "alpha": a * 100, "t_alpha": t_a,
            "maxdd": float((eq / peak - 1).min()) * 100, "cagr": cagr * 100}


def _topmean(score, fwd, n=TOP_N):
    order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:n]
    return float(np.mean(fwd[order])) - COST


def build(path: Path, y0: int, y1: int):
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dates = list(close.index)
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10),
                            adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values=f"fwd_{H}", aggfunc="last")

    base, a_pri, a_se, mkt = [], [], [], []
    for d in dates[::H]:
        if not (y0 <= d.year <= y1):
            continue
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        mid = (lo + hi) // 2
        win = rets.iloc[lo:hi].values
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        cand = elig_row & np.isfinite(fwd_row) & (np.isfinite(win).sum(axis=0) >= MIN_OBS)
        if cand.sum() < TOP_N + 10:
            continue
        Rc = win[:, cand]; mask = np.isfinite(Rc); Rc0 = np.where(mask, Rc, 0.0)
        # full-window CAPM beta + residual IR score (UNCHANGED from x03)
        beta = (Rc0 * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        score = np.nanmean(resid, axis=0) / np.nanstd(resid, axis=0, ddof=1)
        # split-half betas for instability
        sp1 = sp[: mid - lo]; sp2 = sp[mid - lo:]
        spd1 = sp1 - np.nanmean(sp1); spd2 = sp2 - np.nanmean(sp2)
        v1 = np.nansum(spd1 * spd1); v2 = np.nansum(spd2 * spd2)
        R1 = Rc0[: mid - lo]; R2 = Rc0[mid - lo:]
        b1 = (R1 * spd1[:, None]).sum(axis=0) / v1
        b2 = (R2 * spd2[:, None]).sum(axis=0) / v2
        instab = np.abs(b1 - b2)
        # se(beta) over full window: sqrt( var(resid)/df / Sxx )
        dfree = mask.sum(axis=0) - 2
        sse = np.nansum(resid * resid, axis=0)
        se_beta = np.sqrt(np.where(dfree > 0, sse / dfree, np.nan) / var_sp)
        fwd_c = fwd_row[cand]
        ok = np.isfinite(score)
        if ok.sum() < TOP_N + 5:
            continue
        # baseline: top-50 by score
        base.append(_topmean(score, fwd_c))
        # arm A: drop worst DROP_FRAC by instability / se(beta) among scored candidates, then top-50
        def filtered(badness):
            valid = ok & np.isfinite(badness)
            thr = np.nanquantile(badness[valid], 1.0 - DROP_FRAC)
            keep = valid & (badness <= thr)
            if keep.sum() < TOP_N:
                return np.nan
            s = np.where(keep, score, np.nan)
            return _topmean(s, fwd_c)
        a_pri.append(filtered(instab))
        a_se.append(filtered(se_beta))
        mkt.append(float(spy_fwd.loc[d]))
    b, p, s, m = map(np.array, (base, a_pri, a_se, mkt))
    fin = np.isfinite(b) & np.isfinite(p) & np.isfinite(s) & np.isfinite(m)
    return b[fin], p[fin], s[fin], m[fin]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--window", required=True, help="YYYY-YYYY rebalance-date bound, e.g. 2022-2024")
    args = ap.parse_args()
    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    y0, y1 = (int(x) for x in args.window.split("-"))

    base, a_pri, a_se, mkt = build(path, y0, y1)
    n = len(base)
    print(f"\nx05 Arm A — β-cleaning vs x03 baseline | {path.name} | window {y0}-{y1} | {n} periods")
    if n < 10:
        print("too few periods"); return
    rows = [("baseline (x03 top-50)", base),
            ("A-primary (split-half |Δβ|, drop20%)", a_pri),
            ("A-se(β) (drop20%)", a_se)]
    bm = _metrics(base, mkt)
    print(f"{'book':<38}{'beta':>7}{'sharpe':>8}{'maxDD%':>8}{'cagr%':>8}{'alpha%':>8}{'t_a':>6}{'corr':>7}")
    for name, r in rows:
        mt = _metrics(r, mkt)
        corr = np.corrcoef(base, r)[0, 1] if name != rows[0][0] else 1.0
        print(f"{name:<38}{mt['beta']:>7.2f}{mt['sharpe']:>8.2f}{mt['maxdd']:>8.1f}"
              f"{mt['cagr']:>8.1f}{mt['alpha']:>8.2f}{mt['t_alpha']:>6.2f}{corr:>7.2f}")
    # locked decision-rule readout (primary arm)
    pm = _metrics(a_pri, mkt)
    print("\n  decision-rule check (A-primary vs baseline, THIS window):")
    print(f"   β lower?         {pm['beta']:.2f} < {bm['beta']:.2f}  -> {pm['beta'] < bm['beta']}")
    print(f"   DD shallower≥2pp OR Sharpe↑?  ΔDD {pm['maxdd']-bm['maxdd']:+.1f}pp  ΔSh {pm['sharpe']-bm['sharpe']:+.2f}"
          f"  -> {(pm['maxdd']-bm['maxdd'] >= 2.0) or (pm['sharpe'] > bm['sharpe'])}")
    print(f"   α not worse?     t {pm['t_alpha']:+.2f} vs {bm['t_alpha']:+.2f}  -> {pm['t_alpha'] >= bm['t_alpha']}")
    print(f"   CAGR within ~1pp? Δ {pm['cagr']-bm['cagr']:+.1f}pp  -> {abs(pm['cagr']-bm['cagr']) <= 1.0}")


if __name__ == "__main__":
    main()
