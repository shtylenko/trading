#!/usr/bin/env python3
"""x04 value-sleeve scoring — pre-registered test (`multiday_x04_value_preregistration.md`).

Reads the PIT value ledger from `scripts/capture_value.py` + the price split parquet, and judges
the value signal on the locked bars, BETA-ADJUSTED from the start (the lesson from the quality KILL):

  A. IS IT REAL?  beta-adjusted alpha (t>0), Sharpe ≥ 0.3, DSR ≥ 0.90 on clean 2022–2024.
  B. IS IT ADDITIVE to x03?  corr(value, residual-mom book) < 0.5 AND 50/50 blend Sharpe ≥
     x03 × 1.10 with no worse drawdown.
  Plus the pre-registered 2022-POSITIVITY check (value should shine in the bear where momentum
  crashed — the regime-complementarity that justifies holding it).

x03 residual book recomputed inline from the price parquet + SPY (same as multiday_quality.py).
2025 sealed out. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_value \
        --value trading/lab/experiments/_data/_capture_value_2017_2024.parquet \
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
    a, t_a, beta = _beta_adj_alpha(r, m) if len(r) > 3 else (np.nan, np.nan, np.nan)
    return {"n": len(r), "mean": r.mean(), "sharpe": r.mean() / sd * ann if sd > 0 else np.nan,
            "beta": beta, "alpha": a, "t_alpha": t_a, "maxdd": float((eq / peak - 1).min())}


def _resid_mom(rets_win, spy_win):
    spd = spy_win - np.nanmean(spy_win); var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win); R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def main() -> None:
    p = argparse.ArgumentParser(description="x04 value sleeve scoring")
    p.add_argument("--value", default="trading/lab/experiments/_data/_capture_value_2017_2024.parquet")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument("--signal", default="book_to_market", choices=["book_to_market", "earnings_yield"])
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    val = pd.read_parquet(_abs(args.value))
    val["trade_date"] = pd.to_datetime(val["trade_date"]).dt.normalize()
    df = pd.read_parquet(_abs(args.price_ledger))
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()

    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values="fwd_20", aggfunc="last")
    vmat = val.pivot_table(index="trade_date", columns="ticker", values=args.signal, aggfunc="last")
    dates = list(close.index)

    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal = [d for j, d in enumerate(dates) if j % H == 0 and in_window[j] and d in set(vmat.index)]

    val_r, resid_r, mkt, yrs = [], [], [], []
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
        resid = _resid_mom(win[:, cand], sp)
        vrow = vmat.loc[d].reindex(close.columns).values[cand]

        def topmean(score):
            if np.isfinite(score).sum() < TOP_N:
                return None
            order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
            return float(np.mean(fwd_c[order])) - COST

        v = topmean(vrow); rr = topmean(resid)
        if v is None or rr is None:
            continue
        val_r.append(v); resid_r.append(rr); mkt.append(float(spy_fwd.loc[d])); yrs.append(d.year)

    val_r, resid_r, mkt, yrs = map(np.array, (val_r, resid_r, mkt, yrs))
    fin = np.all([np.isfinite(x) for x in (val_r, resid_r, mkt)], axis=0)
    val_r, resid_r, mkt, yrs = val_r[fin], resid_r[fin], mkt[fin], yrs[fin]
    n = len(val_r)
    print(f"Value sleeve test: signal={args.signal}  {args.start_year}-{args.end_year} "
          f"({n} non-overlapping periods, 2025 sealed)")
    if n < 10:
        print("too few periods — check the value capture window/coverage"); return

    schemes = {"x03 resid": resid_r, f"x04 {args.signal}": val_r}
    srs = [s.mean() / s.std(ddof=1) for s in schemes.values()]
    sr_var = float(np.var(srs, ddof=1))
    print("\n=== A. IS IT REAL? (beta-adjusted) ===")
    print(f"{'scheme':18}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'DSR':>7}")
    dsr = {}
    for name, s in schemes.items():
        m = _metrics(s, mkt); d_ = deflated_sharpe_ratio(s, sr_var, 2.0)["dsr"]; dsr[name] = d_
        print(f"{name:18}{m['sharpe']:>+7.2f}{m['beta']:>+7.2f}{m['alpha']*100:>+8.2f}"
              f"{m['t_alpha']:>+7.2f}{m['maxdd']*100:>+8.1f}{d_:>7.3f}")
    vm = _metrics(val_r, mkt)
    A_ok = (vm["alpha"] > 0 and vm["t_alpha"] > 0 and vm["sharpe"] >= 0.3 and dsr[f"x04 {args.signal}"] >= 0.90)
    print(f"  bar A: α>0 & t>0 & Sharpe≥0.3 & DSR≥0.90  → {'PASS' if A_ok else 'FAIL'}")

    # per-year (the 2022-positivity check)
    print("\n=== per-year value-book mean per-period return % (2022 should be POSITIVE) ===")
    for y in sorted(set(yrs.tolist())):
        sub = val_r[yrs == y]
        print(f"  {y}: {sub.mean()*100:+.2f}%  ({len(sub)} periods)")

    corr = float(np.corrcoef(val_r, resid_r)[0, 1])
    blend = 0.5 * val_r + 0.5 * resid_r
    bm = _metrics(blend, mkt); rm = _metrics(resid_r, mkt)
    print("\n=== B. IS IT ADDITIVE TO x03? ===")
    print(f"  corr(x04, x03) = {corr:+.2f}   (bar < 0.50; expect low/negative)")
    print(f"  x03 alone:   annSh {rm['sharpe']:+.2f}  maxDD {rm['maxdd']*100:+.1f}%")
    print(f"  50/50 blend: annSh {bm['sharpe']:+.2f}  maxDD {bm['maxdd']*100:+.1f}%  "
          f"(bar: Sharpe ≥ {rm['sharpe']*1.10:+.2f}, DD no worse)")
    B_ok = (corr < 0.50 and bm["sharpe"] >= rm["sharpe"] * 1.10 and bm["maxdd"] >= rm["maxdd"])
    print(f"  bar B → {'PASS' if B_ok else 'FAIL'}")

    verdict = ("PROMOTE-CANDIDATE" if (A_ok and B_ok) else
               "REAL-BUT-NOT-ADDITIVE" if A_ok else "KILL")
    print(f"\n>>> VERDICT: {verdict}")


if __name__ == "__main__":
    main()
