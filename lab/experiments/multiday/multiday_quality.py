#!/usr/bin/env python3
"""x04 quality-sleeve scoring — pre-registered test (`multiday_x04_quality_preregistration.md`).

Reads the PIT-fundamentals ledger from `scripts/capture_fundamentals.py` (run that first — the
long EDGAR fetch) + the price split parquet, and judges the quality signal on the locked bars:

  A. IS IT REAL?  beta-adjusted alpha (intercept + t vs SPY), Sharpe ≥ 0.5, DSR ≥ 0.95, on
     clean 2022–2024 (+ 2017–2024 secondary).
  B. IS IT ADDITIVE to x03?  corr(quality, residual-momentum book) < 0.6 AND a 50/50 blend's
     Sharpe ≥ x03 × 1.10 with no worse drawdown.

The x03 residual book is recomputed inline from the price parquet + SPY (same vectorized CAPM
residual as scripts/multiday_residmom.py) so the comparison is apples-to-apples. 2025 sealed out.

Usage:
    python3 -m trading.lab.experiments.multiday.multiday_quality \
        --fundamentals trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet \
        --price-ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --start-year 2022 --end-year 2024
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

from trading.lab.data.market_data import fetch_daily_range
from trading.lab.validation.deflated_sharpe import deflated_sharpe_ratio

H = 20
TOP_N = 50
COST = 10.0 / 10000.0
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


def _metrics(r, m):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    return {"n": len(r), "sharpe": r.mean() / sd * ann if sd > 0 else np.nan,
            "beta": beta, "alpha": a, "t_alpha": t_a, "maxdd": float((eq / peak - 1).min())}


def _resid_mom(rets_win, spy_win):
    spd = spy_win - np.nanmean(spy_win); var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win); R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def main() -> None:
    p = argparse.ArgumentParser(description="x04 quality sleeve scoring")
    p.add_argument("--fundamentals", default="trading/lab/experiments/_data/_capture_fundamentals_2017_2024.parquet")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument("--signal", default="gp_assets", choices=["gp_assets", "ni_yoy"])
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    fund = pd.read_parquet(_abs(args.fundamentals))
    fund["trade_date"] = pd.to_datetime(fund["trade_date"]).dt.normalize()
    df = pd.read_parquet(_abs(args.price_ledger))
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()

    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values="fwd_20", aggfunc="last")
    mom = df.pivot_table(index="trade_date", columns="ticker", values="mom_12_1", aggfunc="last")
    qmat = fund.pivot_table(index="trade_date", columns="ticker", values=args.signal, aggfunc="last")
    dates = list(close.index)

    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal = [d for j, d in enumerate(dates) if j % H == 0 and in_window[j] and d in set(qmat.index)]

    qual_r, resid_r, mom_r, mkt, kept = [], [], [], [], []
    for d in rebal:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi].values
        sp = spy_ret.iloc[lo:hi].values
        if not np.isfinite(sp).all():
            continue
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        cand = elig_row & np.isfinite(fwd_row)
        if cand.sum() < TOP_N:
            continue
        fwd_c = fwd_row[cand]
        # residual-momentum book (x03)
        resid = _resid_mom(win[:, cand], sp)
        # quality book (x04) — align signal to candidate tickers
        qrow = qmat.loc[d].reindex(close.columns).values[cand] if d in qmat.index else np.full(cand.sum(), np.nan)
        mom_c = mom.loc[d].values[cand]

        def topmean(score):
            if np.isfinite(score).sum() < TOP_N:
                return None
            order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
            return float(np.mean(fwd_c[order])) - COST

        q = topmean(qrow); rr = topmean(resid); mm = topmean(mom_c)
        if q is None or rr is None or mm is None:
            continue
        qual_r.append(q); resid_r.append(rr); mom_r.append(mm)
        mkt.append(float(spy_fwd.loc[d])); kept.append(d)

    qual_r, resid_r, mom_r, mkt = map(np.array, (qual_r, resid_r, mom_r, mkt))
    fin = np.all([np.isfinite(x) for x in (qual_r, resid_r, mom_r, mkt)], axis=0)
    qual_r, resid_r, mom_r, mkt = qual_r[fin], resid_r[fin], mom_r[fin], mkt[fin]
    n = len(qual_r)
    print(f"Quality sleeve test: signal={args.signal}  {args.start_year}-{args.end_year} "
          f"({n} non-overlapping periods, 2025 sealed)")
    if n < 10:
        print("too few periods — check the fundamentals capture window/coverage"); return

    # DSR scaled across the candidate schemes considered
    schemes = {"x01 mom": mom_r, "x03 resid": resid_r, f"x04 {args.signal}": qual_r}
    srs = [s.mean() / s.std(ddof=1) for s in schemes.values()]
    sr_var = float(np.var(srs, ddof=1))
    print(f"\n=== A. IS IT REAL? ===")
    print(f"{'scheme':16}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'DSR':>7}")
    dsr = {}
    for name, s in schemes.items():
        m = _metrics(s, mkt); d_ = deflated_sharpe_ratio(s, sr_var, float(len(schemes)))["dsr"]
        dsr[name] = d_
        print(f"{name:16}{m['sharpe']:>+7.2f}{m['beta']:>+7.2f}{m['alpha']*100:>+8.2f}"
              f"{m['t_alpha']:>+7.2f}{m['maxdd']*100:>+8.1f}{d_:>7.3f}")
    qm = _metrics(qual_r, mkt)
    A_ok = (qm["alpha"] > 0 and qm["t_alpha"] > 0 and qm["sharpe"] >= 0.5 and dsr[f"x04 {args.signal}"] >= 0.95)
    print(f"  bar A: α>0 & t>0 (ideally |t|>2) & Sharpe≥0.5 & DSR≥0.95  → {'PASS' if A_ok else 'FAIL'}")

    # B. additivity to x03
    corr = float(np.corrcoef(qual_r, resid_r)[0, 1])
    blend = 0.5 * qual_r + 0.5 * resid_r
    bm = _metrics(blend, mkt); rm = _metrics(resid_r, mkt)
    print(f"\n=== B. IS IT ADDITIVE TO x03? ===")
    print(f"  corr(x04, x03) = {corr:+.2f}   (bar < 0.60)")
    print(f"  x03 alone:   annSh {rm['sharpe']:+.2f}  maxDD {rm['maxdd']*100:+.1f}%")
    print(f"  50/50 blend: annSh {bm['sharpe']:+.2f}  maxDD {bm['maxdd']*100:+.1f}%  "
          f"(bar: Sharpe ≥ x03×1.10 = {rm['sharpe']*1.10:+.2f}, DD no worse)")
    B_ok = (corr < 0.60 and bm["sharpe"] >= rm["sharpe"] * 1.10 and bm["maxdd"] >= rm["maxdd"])
    print(f"  bar B → {'PASS' if B_ok else 'FAIL'}")

    verdict = ("PROMOTE-CANDIDATE" if (A_ok and B_ok) else
               "REAL-BUT-NOT-ADDITIVE" if A_ok else "KILL")
    print(f"\n>>> VERDICT: {verdict}")


if __name__ == "__main__":
    main()
