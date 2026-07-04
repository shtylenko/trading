#!/usr/bin/env python3
"""Cross-asset momentum × x03 — ADDITIVITY test (the decisive diversifier bar).

The same bar that KILLED quality/value as diversifiers, now applied to cross-asset momentum:
corr to the x03 residual-momentum stock book, and whether an x03+cross-asset BLEND beats x03 alone
on Sharpe AND drawdown. Both books computed on the SAME rebalance dates (shared NYSE calendar,
H=21, forward returns over identical [d, d+21]) so the correlation is real, not a calendar artifact.

Windows: clean 2022–2024 (primary, x03 true-PIT) + 2017–2024 (secondary, more power, x03 pre-2022
survivorship-flagged). 2025 EXCLUDED (cross-asset's reserved sealed year). Usage:
    python3 -m trading.lab.experiments.crossasset.multiday_crossasset_additivity --start-year 2022 --end-year 2024
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.market_data import fetch_daily_range

H = 21
TOP_N_STK = 50
TOP_N_ETF = 5
COST = 10.0 / 10000.0
FORM_LB = 252
SKIP = 21
MIN_OBS = 126
EQUITY = ["SPY", "QQQ", "IWM", "EFA", "EEM"]
NONEQ = ["TLT", "IEF", "LQD", "HYG", "AGG", "GLD", "DBC", "VNQ"]
RISK = EQUITY + NONEQ
CASH = "BIL"


def _metrics(r, m):
    r = np.asarray(r); m = np.asarray(m); ann = np.sqrt(252.0 / H); sd = r.std(ddof=1)
    eq = np.cumprod(1 + r); dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    X = np.column_stack([np.ones(len(m)), m]); beta = float(np.linalg.lstsq(X, r, rcond=None)[0][1])
    return {"sharpe": r.mean() / sd * ann if sd > 0 else np.nan, "maxdd": dd, "beta": beta}


def _resid_mom(rets_win, spy_win):
    spd = spy_win - np.nanmean(spy_win); var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win); R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0); sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def main() -> None:
    p = argparse.ArgumentParser(description="cross-asset × x03 additivity")
    p.add_argument("--price-ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument("--no-equity", action="store_true",
                   help="restrict cross-asset basket to non-equity (bonds/gold/commodities/REITs) — "
                        "uncorrelated-to-x03-by-construction sleeve")
    p.add_argument("--top-n-etf", type=int, default=TOP_N_ETF)
    args = p.parse_args()
    risk = NONEQ if args.no_equity else RISK
    top_n_etf = args.top_n_etf

    lp = Path(args.price_ledger)
    if not lp.is_absolute():
        lp = PROJECT_ROOT / lp
    df = pd.read_parquet(lp)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change(fill_method=None)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    dates = list(close.index)

    # ETF total-return matrix on the stock calendar
    def etf(sym):
        s = fetch_daily_range(sym, dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="all")
        if s is None or s.empty:
            return None
        idx = pd.DatetimeIndex(s.index).normalize().tz_localize(None)
        return pd.Series(s["close"].values, index=idx).sort_index().pipe(lambda x: x[~x.index.duplicated(keep="last")])
    # always load SPY for market beta even when it's not in the tradeable basket (--no-equity)
    load_syms = list(dict.fromkeys(risk + [CASH, "SPY"]))
    etfpx = pd.DataFrame({s: etf(s) for s in load_syms}).reindex(close.index).ffill()
    spy = etfpx["SPY"]
    spy_ret = spy.pct_change(fill_method=None)

    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])
    rebal = [j for j in range(len(dates)) if j % H == 0 and in_window[j] and j - FORM_LB >= 1 and j + H < len(dates)]

    x03_r, ca_r, agg_r, ewne_r, mkt, yrs = [], [], [], [], [], []
    NONEQ_BASKET = ["TLT", "IEF", "LQD", "HYG", "AGG", "GLD", "DBC", "VNQ"]
    for j in rebal:
        d = dates[j]
        # x03 residual stock book, forward H
        win = rets.iloc[j - FORM_LB:j - SKIP].values
        sp = spy_ret.iloc[j - FORM_LB:j - SKIP].values
        if not np.isfinite(sp).all():
            continue
        elig_row = (elig.loc[d] == True).values        # NaN==True → False, avoids fillna downcast
        fwdH = (close.iloc[j + H].values / close.iloc[j].values - 1.0)
        cand = elig_row & np.isfinite(fwdH) & (np.isfinite(win).sum(axis=0) >= MIN_OBS)
        if cand.sum() < TOP_N_STK:
            continue
        resid = _resid_mom(win[:, cand], sp)
        if np.isfinite(resid).sum() < TOP_N_STK:
            continue
        fwd_c = fwdH[cand]
        order = np.argsort(np.where(np.isfinite(resid), -resid, np.inf))[:TOP_N_STK]
        x03 = float(np.mean(fwd_c[order])) - COST
        # cross-asset ETF book, forward H (same d, H)
        mom = {}
        for s in risk:
            p0 = etfpx[s].iloc[j - FORM_LB]; p1 = etfpx[s].iloc[j - SKIP]
            if np.isfinite(p0) and np.isfinite(p1) and p0 > 0:
                mom[s] = p1 / p0 - 1.0
        pos = {s: m for s, m in mom.items() if m > 0}
        if len(mom) < top_n_etf:
            continue
        ranked = sorted(pos, key=pos.get, reverse=True)[:top_n_etf]
        n_cash = top_n_etf - len(ranked)
        def fwd(s):
            return etfpx[s].iloc[j + H] / etfpx[s].iloc[j] - 1.0
        ca = (sum(fwd(s) for s in ranked) + n_cash * fwd(CASH)) / top_n_etf - COST
        # static-diversifier benchmarks (no momentum): buy&hold AGG, and EW non-equity basket
        agg = fwd("AGG")
        ewne = float(np.mean([fwd(s) for s in NONEQ_BASKET]))
        x03_r.append(x03); ca_r.append(ca); agg_r.append(agg); ewne_r.append(ewne)
        mkt.append(float(spy.iloc[j + H] / spy.iloc[j] - 1.0)); yrs.append(d.year)

    x03_r, ca_r, agg_r, ewne_r, mkt, yrs = map(np.array, (x03_r, ca_r, agg_r, ewne_r, mkt, yrs))
    n = len(x03_r)
    basket = "NON-EQUITY only (bonds/gold/commod/REIT)" if args.no_equity else "all 13 asset-class ETFs"
    print(f"Cross-asset × x03 additivity [{basket}, top-{top_n_etf}]: {args.start_year}-{args.end_year} "
          f"({n} aligned monthly periods, 2025 reserved)\n")
    if n < 10:
        print("too few periods"); return
    corr = float(np.corrcoef(x03_r, ca_r)[0, 1])
    blends = {"x03 alone": x03_r, "cross-asset alone": ca_r,
              "50/50 blend": 0.5 * x03_r + 0.5 * ca_r, "60/40 x03/CA": 0.6 * x03_r + 0.4 * ca_r}
    print(f"corr(x03, cross-asset) = {corr:+.2f}   (quality/value diversifiers died at +0.6–0.8)\n")
    print(f"{'book':20}{'annSh':>7}{'maxDD':>8}{'βSPY':>7}")
    M = {}
    for name, r in blends.items():
        m = _metrics(r, mkt); M[name] = m
        print(f"{name:20}{m['sharpe']:>+7.2f}{m['maxdd']*100:>+8.1f}{m['beta']:>+7.2f}")
    x = M["x03 alone"]; b = M["50/50 blend"]
    sh_lift = (b["sharpe"] - x["sharpe"]) / abs(x["sharpe"]) if x["sharpe"] else float("nan")
    dd_imp = b["maxdd"] >= x["maxdd"]            # blend DD shallower (less negative)
    print(f"\n50/50 vs x03 alone: Sharpe {x['sharpe']:+.2f}→{b['sharpe']:+.2f} ({sh_lift*100:+.0f}%), "
          f"maxDD {x['maxdd']*100:+.1f}%→{b['maxdd']*100:+.1f}%, βSPY {x['beta']:+.2f}→{b['beta']:+.2f}")
    print(">>> BAR (the diversifier test): corr < 0.5 AND blend Sharpe ≥ x03 AND blend DD shallower")
    ok = corr < 0.5 and b["sharpe"] >= x["sharpe"] and dd_imp
    print(f">>> VERDICT: {'ADDITIVE — genuine diversifier (→ full pipeline + sealed-2025)' if ok else 'NOT additive on this window'}")

    # ── per-year decomposition: is the benefit BROAD or BEAR-CONCENTRATED? ──
    blend = 0.5 * x03_r + 0.5 * ca_r
    print("\n=== per-year: is the diversification broad or bear-only? ===")
    print(f"{'year':6}{'SPY%':>8}{'x03%':>8}{'CA%':>8}{'blend%':>8}{'x03 vs blend Δ':>16}")
    for y in sorted(set(yrs.tolist())):
        sel = yrs == y
        sc = float(np.prod(1 + mkt[sel]) - 1)
        xc = float(np.prod(1 + x03_r[sel]) - 1)
        cc = float(np.prod(1 + ca_r[sel]) - 1)
        bc = float(np.prod(1 + blend[sel]) - 1)
        bear = " (bear)" if sc < 0 else ""
        print(f"{y:6}{sc*100:>+8.1f}{xc*100:>+8.1f}{cc*100:>+8.1f}{bc*100:>+8.1f}{(bc-xc)*100:>+12.1f}pp{bear}")
    # Sharpe ex-bear-years: does the blend still help when equities were UP?
    up = mkt > 0 if False else np.array([np.prod(1 + mkt[yrs == y]) - 1 > 0 for y in yrs])
    if up.sum() > 5:
        xs = _metrics(x03_r[up], mkt[up]); bs = _metrics(blend[up], mkt[up])
        print(f"\nUP-year periods only ({up.sum()}): x03 Sharpe {xs['sharpe']:+.2f} / DD {xs['maxdd']*100:+.1f}%  "
              f"→ blend {bs['sharpe']:+.2f} / DD {bs['maxdd']*100:+.1f}%")
        print("  (if the blend only helps in bear years and HURTS Sharpe in up-years → it's crash "
              "insurance, not an all-weather diversifier)")

    # ── does the momentum ROTATION beat naive static diversification? ──
    print("\n=== does the cross-asset MOMENTUM sleeve beat 'just hold bonds' (static diversifier)? ===")
    print(f"{'50/50 blend of x03 +':28}{'annSh':>7}{'maxDD':>8}{'βSPY':>7}{'corr':>7}")
    for name, sleeve in [("cross-asset momentum", ca_r), ("static AGG (buy&hold)", agg_r),
                         ("static EW non-equity", ewne_r)]:
        bl = 0.5 * x03_r + 0.5 * sleeve
        m = _metrics(bl, mkt); cr = float(np.corrcoef(x03_r, sleeve)[0, 1])
        print(f"  {name:26}{m['sharpe']:>+7.2f}{m['maxdd']*100:>+8.1f}{m['beta']:>+7.2f}{cr:>+7.2f}")
    print("  → if the momentum sleeve's blend Sharpe/DD isn't BETTER than the static-AGG blend, the "
          "rotation machinery adds nothing over simply holding bonds (just diversify statically).")


if __name__ == "__main__":
    main()
