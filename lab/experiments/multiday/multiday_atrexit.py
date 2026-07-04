#!/usr/bin/env python3
"""x04 ATR/chandelier trailing exit on x03 — pre-registered test
(`multiday_x04_atrexit_preregistration.md`).

x03 selection unchanged (top-50 CAPM-residual momentum, monthly, H=20); the ONLY change is the
EXIT: a chandelier stop trails k·ATR_proxy below each hold's running peak close, exiting
crash-prone names mid-hold (capital → cash to end of window, no replacement). ATR_proxy = 14-day
mean |Δclose| (close-based; capture has no high/low). Risk lever, not alpha — judged on drawdown
reduction with Sharpe held ≥ base. 2025 sealed. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_atrexit \
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
ATR_WIN = 14
K_GRID = [3.0, 2.5]          # primary 3.0, secondary 2.5


def _beta_adj(r, m):
    r = np.asarray(r); m = np.asarray(m); n = len(r)
    X = np.column_stack([np.ones(n), m])
    bhat, *_ = np.linalg.lstsq(X, r, rcond=None)
    e = r - X @ bhat; s2 = (e @ e) / (n - 2); cov = s2 * np.linalg.inv(X.T @ X)
    return bhat[0], bhat[0] / np.sqrt(cov[0, 0]), bhat[1]


def _metrics(r, m):
    r = np.asarray(r); m = np.asarray(m); ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    a, t, b = _beta_adj(r, m)
    return {"sharpe": r.mean() / sd * ann if sd > 0 else np.nan, "beta": b, "alpha": a,
            "t_alpha": t, "maxdd": float((eq / peak - 1).min())}


def _resid_mom(rets_win, spy_win):
    spd = spy_win - np.nanmean(spy_win); var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win); R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def _chandelier_ret(prices: np.ndarray, atr: np.ndarray, k: float) -> tuple[float, bool]:
    """Realized H-period return of one hold under a chandelier stop. prices[0]=entry close,
    prices[1..H]=subsequent closes; atr[t] aligned to prices[t]. Returns (ret, stopped?)."""
    entry = prices[0]
    peak = entry
    for t in range(1, len(prices)):
        peak = max(peak, prices[t])
        stop = peak - k * atr[t]
        if prices[t] < stop:
            return prices[t] / entry - 1.0, True
    return prices[-1] / entry - 1.0, False


def main() -> None:
    p = argparse.ArgumentParser(description="x04 ATR/chandelier exit on x03")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    args = p.parse_args()

    def _abs(x):
        x = Path(x); return x if x.is_absolute() else PROJECT_ROOT / x

    df = pd.read_parquet(_abs(args.price_ledger))
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    atr = close.diff().abs().rolling(ATR_WIN).mean()          # close-based ATR proxy
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    fwd = df.pivot_table(index="trade_date", columns="ticker", values="fwd_20", aggfunc="last")
    dates = list(close.index)
    cols = list(close.columns)
    col_ix = {c: i for i, c in enumerate(cols)}

    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    spy_fwd = (spy["close"].shift(-H) / spy["close"] - 1.0).reindex(close.index)

    closev, atrv = close.values, atr.values
    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal_ix = [j for j in range(len(dates)) if j % H == 0 and in_window[j]]

    base_r, mkt = [], []
    atr_r = {k: [] for k in K_GRID}
    stop_cnt = {k: 0 for k in K_GRID}; held_cnt = 0
    for j in rebal_ix:
        d = dates[j]
        lo, hi = j - FORM_LB, j - SKIP
        if lo < 1 or hi <= lo + MIN_OBS or j + H >= len(dates):
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
        resid = _resid_mom(win[:, cand], sp)
        if np.isfinite(resid).sum() < TOP_N:
            continue
        cand_ix = np.where(cand)[0]
        order = cand_ix[np.argsort(np.where(np.isfinite(resid), -resid, np.inf))[:TOP_N]]
        # base book = full-hold mean
        base_r.append(float(np.mean(fwd_row[order])) - COST)
        mkt.append(float(spy_fwd.loc[d]))
        # chandelier per held name over the H-day path
        for k in K_GRID:
            rs = []
            for ci in order:
                prices = closev[j:j + H + 1, ci]
                a = atrv[j:j + H + 1, ci]
                if not np.isfinite(prices).all() or not np.isfinite(a[1:]).all():
                    rs.append(float(fwd_row[ci]))          # fall back to full hold if path NaN
                    continue
                ret, stopped = _chandelier_ret(prices, a, k)
                rs.append(ret)
                if k == K_GRID[0]:
                    pass
                stop_cnt[k] += int(stopped)
            atr_r[k].append(float(np.mean(rs)) - COST)
        held_cnt += TOP_N

    base_r, mkt = np.array(base_r), np.array(mkt)
    n = len(base_r)
    print(f"ATR/chandelier exit on x03: {args.start_year}-{args.end_year} ({n} periods, 2025 sealed, "
          f"ATR_proxy=14d mean|Δclose|)")
    if n < 10:
        print("too few periods"); return
    schemes = {"x03 base (time exit)": base_r, **{f"x03 + chand k={k}": np.array(atr_r[k]) for k in K_GRID}}
    srs = [s.mean() / s.std(ddof=1) for s in schemes.values()]
    sr_var = float(np.var(srs, ddof=1))
    print(f"\n{'scheme':24}{'annSh':>7}{'alpha%':>8}{'t(α)':>7}{'beta':>7}{'maxDD':>8}{'DSR':>7}{'stop%':>7}")
    base_m = _metrics(base_r, mkt)
    for name, s in schemes.items():
        m = _metrics(s, mkt); d_ = deflated_sharpe_ratio(s, sr_var, float(len(schemes)))["dsr"]
        sp = "" if "base" in name else f"{100*stop_cnt[float(name.split('=')[1])]/held_cnt:.0f}%"
        print(f"{name:24}{m['sharpe']:>+7.2f}{m['alpha']*100:>+8.2f}{m['t_alpha']:>+7.2f}"
              f"{m['beta']:>+7.2f}{m['maxdd']*100:>+8.1f}{d_:>7.3f}{sp:>7}")

    # verdict on primary k=3.0
    pm = _metrics(np.array(atr_r[3.0]), mkt)
    dd_red = (base_m["maxdd"] - pm["maxdd"]) / abs(base_m["maxdd"])    # >0 means shallower
    adopt = (dd_red >= 0.10 and pm["sharpe"] >= base_m["sharpe"] and pm["alpha"] >= base_m["alpha"])
    print(f"\nprimary k=3.0 vs base: maxDD {base_m['maxdd']*100:+.1f}%→{pm['maxdd']*100:+.1f}% "
          f"({dd_red*100:+.0f}% rel), Sharpe {base_m['sharpe']:+.2f}→{pm['sharpe']:+.2f}, "
          f"alpha {base_m['alpha']*100:+.2f}%→{pm['alpha']*100:+.2f}%")
    print(">>> BAR: DD ≥10% shallower AND Sharpe ≥ base AND alpha ≥ base")
    print(f">>> VERDICT: {'ADOPT chandelier exit' if adopt else 'REJECT — pure time exit optimal'}")


if __name__ == "__main__":
    main()
