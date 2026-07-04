#!/usr/bin/env python3
"""x04 Frog-in-the-Pan / information-discreteness momentum — pre-registered test
(`validation/multiday_x04_fip_preregistration.md`).

Da, Gurun & Warachka (2014): momentum is stronger/more persistent when the formation
information arrived CONTINUOUSLY (steady drip) vs in DISCRETE jumps. Proxy:

    ID = sgn(PRET) · (%neg_days − %pos_days)    over [d-252, d-21]

low ID = smooth winner (keep); high ID = jumpy/lottery winner (drop). Construction =
double-sort: top-150 by momentum, then the 50 LOWEST ID, top-50 EW, H=20. Two arms:
faithful (momentum = raw mom_12_1, vs x01) and residual (momentum = CAPM-residual, vs
x03). Headline metric = BETA-ADJUSTED ALPHA. Computed from the existing split-adjusted
capture parquet + SPY; 2025 hard-sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_fip \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
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
PRECUT = 150              # momentum "winners" pool before the ID select (= 3× TOP_N)
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
    a, b = bhat[0], bhat[1]
    return a, a / np.sqrt(cov[0, 0]), b


def _metrics(r, m):
    r = np.asarray(r); m = np.asarray(m)
    ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t_a, beta = _beta_adj_alpha(r, m)
    return {"n": len(r), "mean": r.mean(), "sharpe": r.mean() / sd * ann if sd > 0 else np.nan,
            "beta": beta, "alpha": a, "t_alpha": t_a, "maxdd": float((eq / peak - 1).min())}


def _resid_mom(rets_win, spy_win):
    spd = spy_win - np.nanmean(spy_win); var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win); R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def _info_discreteness(rets_win, pret):
    """ID = sgn(PRET)·(%neg − %pos) over the formation window, per column (name)."""
    fin = np.isfinite(rets_win)
    cnt = fin.sum(axis=0).astype(float)
    pos = (rets_win > 0).sum(axis=0) / np.where(cnt > 0, cnt, np.nan)
    neg = (rets_win < 0).sum(axis=0) / np.where(cnt > 0, cnt, np.nan)
    return np.sign(pret) * (neg - pos)


def main() -> None:
    p = argparse.ArgumentParser(description="x04 Frog-in-the-Pan momentum test")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024, help="inclusive; 2025 sealed-but-spent")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    yr = df["trade_date"].dt.year
    df = df[(yr >= args.start_year) & (yr <= args.end_year)].copy() if False else df  # keep full hist for formation

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
    mom = df.pivot_table(index="trade_date", columns="ticker", values="mom_12_1", aggfunc="last")

    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal = [d for j, d in enumerate(dates) if j % H == 0 and in_window[j]]

    # collect per-period returns for: x01, x03, FIP-faithful, FIP-residual
    cols = {"x01_base": [], "x03_resid": [], "fip_faithful": [], "fip_residual": [], "mkt": []}
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
        mom_row = mom.loc[d].values
        obs = np.isfinite(win).sum(axis=0)
        cand = elig_row & np.isfinite(fwd_row) & np.isfinite(mom_row) & (obs >= MIN_OBS)
        if cand.sum() < PRECUT:
            continue
        Rc = win[:, cand]
        fwd_c = fwd_row[cand]; mom_c = mom_row[cand]
        resid_c = _resid_mom(Rc, sp)
        id_c = _info_discreteness(Rc, mom_c)

        def top_by(score, n=TOP_N):
            return np.argsort(np.where(np.isfinite(score), -score, np.inf))[:n]

        def low_by(score, pool, n=TOP_N):
            # lowest ID within the given pool of indices
            sub = score[pool]
            order = np.argsort(np.where(np.isfinite(sub), sub, np.inf))[:n]
            return pool[order]

        if np.isfinite(mom_c).sum() < PRECUT or np.isfinite(resid_c).sum() < PRECUT:
            continue
        # bases
        cols["x01_base"].append(float(fwd_c[top_by(mom_c)].mean()) - COST)
        cols["x03_resid"].append(float(fwd_c[top_by(resid_c)].mean()) - COST)
        # FIP: momentum pre-cut of 150, then 50 lowest ID
        pool_mom = top_by(mom_c, PRECUT)
        pool_res = top_by(resid_c, PRECUT)
        cols["fip_faithful"].append(float(fwd_c[low_by(id_c, pool_mom)].mean()) - COST)
        cols["fip_residual"].append(float(fwd_c[low_by(id_c, pool_res)].mean()) - COST)
        cols["mkt"].append(float(spy_fwd.loc[d]))

    arr = {k: np.array(v) for k, v in cols.items()}
    fin = np.all([np.isfinite(arr[k]) for k in arr], axis=0)
    for k in arr:
        arr[k] = arr[k][fin]
    n = len(arr["mkt"])
    print(f"Frog-in-the-Pan test: {path.name}  {args.start_year}-{args.end_year} "
          f"({n} non-overlapping periods, 2025 sealed)")
    if n < 10:
        print("too few periods"); return

    schemes = ["x01_base", "x03_resid", "fip_faithful", "fip_residual"]
    srs = [arr[s].mean() / arr[s].std(ddof=1) for s in schemes]
    sr_var = float(np.var(srs, ddof=1))
    print(f"{'scheme':16}{'perPer%':>9}{'annSh':>7}{'beta':>7}{'alpha%':>8}{'t(α)':>7}{'maxDD':>8}{'DSR':>7}")
    dsr = {}
    for s in schemes:
        m = _metrics(arr[s], arr["mkt"])
        d_ = deflated_sharpe_ratio(arr[s], sr_var, float(len(schemes)))["dsr"]
        dsr[s] = d_
        print(f"{s:16}{m['mean']*100:>+9.2f}{m['sharpe']:>+7.2f}{m['beta']:>+7.2f}"
              f"{m['alpha']*100:>+8.2f}{m['t_alpha']:>+7.2f}{m['maxdd']*100:>+8.1f}{d_:>7.3f}")

    c01 = np.corrcoef(arr["fip_faithful"], arr["x01_base"])[0, 1]
    c03 = np.corrcoef(arr["fip_residual"], arr["x03_resid"])[0, 1]
    c_fr = np.corrcoef(arr["fip_faithful"], arr["x03_resid"])[0, 1]
    print(f"\ncorr(fip_faithful, x01) = {c01:+.2f}   corr(fip_residual, x03) = {c03:+.2f}   "
          f"corr(fip_faithful, x03) = {c_fr:+.2f}")
    bm = _metrics(arr["x01_base"], arr["mkt"])
    fm = _metrics(arr["fip_faithful"], arr["mkt"])
    print(">>> x04-FIP BAR (faithful vs x01): α-t materially > base (x01≈+0.31; want |t|>2), "
          "Sharpe ≥ x01, DSR ≥ 0.95.")
    ok = (fm["t_alpha"] > bm["t_alpha"] and fm["sharpe"] >= bm["sharpe"]
          and dsr["fip_faithful"] >= 0.95 and fm["alpha"] > 0)
    print(f"    → {'PROMOTE-CANDIDATE' if ok else 'does NOT clear the bar (path quality subsumed by return-level momentum)'}")


if __name__ == "__main__":
    main()
