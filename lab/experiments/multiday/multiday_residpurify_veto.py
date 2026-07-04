#!/usr/bin/env python3
"""x05 Arm B (issuance veto) — net-share-issuance veto on x03 residual winners (PRE-REGISTERED).

Spec: `validation/research_log/multiday_x05_residual_purification_preregistration.md` (Arm B).
Baseline = x03 (CAPM-residual IR, top-50 EW, monthly H=20). Arm B: within the top-90 by IR (wider
candidate pool so the veto still fills 50), EXCLUDE the top quintile by split-adjusted 12-month net
share issuance (most dilutive), then take the top-50 EW. A post-selection exclusion on a DIFFERENT
anomaly (corporate financing), NOT a primary ranking sleeve. Issuance ledger from
`capture_issuance.py`. Same beta-adjusted decision rule + windows as Arm A. No sealed year touched.
Usage:
    python3 -m trading.lab.experiments.multiday.multiday_residpurify_veto \
        --ledger trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet \
        --issuance trading/lab/experiments/_data/_capture_issuance_2017_2025.parquet --window 2022-2024
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
from trading.lab.experiments.multiday.multiday_residpurify import (
    H, TOP_N, COST, FORM_LB, SKIP, MIN_OBS, _metrics,
)

POOL = 90              # IR candidate pool the veto trims from (pre-committed)
VETO_Q = 0.80          # exclude top-quintile NSI (>= 80th pct among the pool)


def _topmean(score, fwd, n=TOP_N):
    order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:n]
    return float(np.mean(fwd[order])) - COST


def build(path: Path, nsi_path: Path, y0: int, y1: int):
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    nsi = pd.read_parquet(nsi_path)
    nsi["trade_date"] = pd.to_datetime(nsi["trade_date"]).dt.normalize()

    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    # Reindex NSI onto the price ledger's date grid + ffill (≤1 quarter): the capture wrote NSI on
    # its OWN [::H] rebalance grid, which is phase-shifted from this script's grid whenever the ledger
    # has warmup years (e.g. 2008 in the 2009-16 YF ledger) — exact-date lookup would then silently
    # match nothing. ffill is PIT-safe: NSI at date t was computed from filed≤t data, so carrying it
    # to a later rebalance d>t uses only as-known-at-d information.
    nsi_piv = (nsi.pivot_table(index="trade_date", columns="ticker", values="nsi_12m", aggfunc="last")
               .reindex(close.index).ffill(limit=65))
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
    cols = np.array(close.columns)

    base, veto, mkt, vetoed = [], [], [], []
    for d in dates[::H]:
        if not (y0 <= d.year <= y1):
            continue
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets.iloc[lo:hi].values
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = fwd.loc[d].values
        cand = elig_row & np.isfinite(fwd_row) & (np.isfinite(win).sum(axis=0) >= MIN_OBS)
        if cand.sum() < POOL + 5:
            continue
        Rc = win[:, cand]; mask = np.isfinite(Rc); Rc0 = np.where(mask, Rc, 0.0)
        beta = (Rc0 * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        score = np.nanmean(resid, axis=0) / np.nanstd(resid, axis=0, ddof=1)
        fwd_c = fwd_row[cand]; tick_c = cols[cand]
        ok = np.isfinite(score)
        if ok.sum() < POOL:
            continue
        # baseline top-50
        base.append(_topmean(score, fwd_c))
        # veto: take top-POOL by score, drop top-quintile NSI among them, take top-50
        nsi_row = nsi_piv.loc[d].reindex(tick_c).values if d in nsi_piv.index else np.full(len(tick_c), np.nan)
        order = np.argsort(np.where(ok, -score, np.inf))[:POOL]
        pool_nsi = nsi_row[order]
        have = np.isfinite(pool_nsi)
        keep_mask = np.ones(POOL, dtype=bool)
        n_drop = 0
        if have.sum() >= 10:                      # only veto if enough NSI coverage in the pool
            thr = np.nanquantile(pool_nsi[have], VETO_Q)
            keep_mask = ~(have & (pool_nsi >= thr))   # missing-NSI names are KEPT (documented fallback)
            n_drop = int((have & (pool_nsi >= thr)).sum())
        kept_idx = order[keep_mask]
        if len(kept_idx) < TOP_N:                 # backfill down the IR ranking if veto over-trims
            extra = [j for j in np.argsort(np.where(ok, -score, np.inf)) if j not in set(kept_idx)]
            kept_idx = np.concatenate([kept_idx, np.array(extra[: TOP_N - len(kept_idx)], dtype=int)])
        sel = kept_idx[:TOP_N]
        veto.append(float(np.mean(fwd_c[sel])) - COST)
        vetoed.append(n_drop)
        mkt.append(float(spy_fwd.loc[d]))
    b, v, m = map(np.array, (base, veto, mkt))
    fin = np.isfinite(b) & np.isfinite(v) & np.isfinite(m)
    return b[fin], v[fin], m[fin], float(np.mean(vetoed)) if vetoed else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--issuance", required=True)
    ap.add_argument("--window", required=True)
    args = ap.parse_args()
    path = Path(args.ledger);  nsi_path = Path(args.issuance)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not nsi_path.is_absolute():
        nsi_path = PROJECT_ROOT / nsi_path
    y0, y1 = (int(x) for x in args.window.split("-"))

    base, veto, mkt, avg_drop = build(path, nsi_path, y0, y1)
    n = len(base)
    print(f"\nx05 Arm B — issuance veto vs x03 baseline | {path.name} | window {y0}-{y1} | "
          f"{n} periods | avg {avg_drop:.1f} names vetoed/period")
    if n < 10:
        print("too few periods"); return
    bm, vm = _metrics(base, mkt), _metrics(veto, mkt)
    corr = np.corrcoef(base, veto)[0, 1]
    print(f"{'book':<34}{'beta':>7}{'sharpe':>8}{'maxDD%':>8}{'cagr%':>8}{'alpha%':>8}{'t_a':>6}{'corr':>7}")
    print(f"{'baseline (x03 top-50)':<34}{bm['beta']:>7.2f}{bm['sharpe']:>8.2f}{bm['maxdd']:>8.1f}"
          f"{bm['cagr']:>8.1f}{bm['alpha']:>8.2f}{bm['t_alpha']:>6.2f}{1.0:>7.2f}")
    print(f"{'issuance-veto (top-90→50)':<34}{vm['beta']:>7.2f}{vm['sharpe']:>8.2f}{vm['maxdd']:>8.1f}"
          f"{vm['cagr']:>8.1f}{vm['alpha']:>8.2f}{vm['t_alpha']:>6.2f}{corr:>7.2f}")
    print("\n  decision-rule check (veto vs baseline, THIS window):")
    print(f"   β lower?         {vm['beta']:.2f} < {bm['beta']:.2f}  -> {vm['beta'] < bm['beta']}")
    print(f"   DD shallower≥2pp OR Sharpe↑?  ΔDD {vm['maxdd']-bm['maxdd']:+.1f}pp  ΔSh {vm['sharpe']-bm['sharpe']:+.2f}"
          f"  -> {(vm['maxdd']-bm['maxdd'] >= 2.0) or (vm['sharpe'] > bm['sharpe'])}")
    print(f"   α not worse?     t {vm['t_alpha']:+.2f} vs {bm['t_alpha']:+.2f}  -> {vm['t_alpha'] >= bm['t_alpha']}")
    print(f"   CAGR within ~1pp? Δ {vm['cagr']-bm['cagr']:+.1f}pp  -> {abs(vm['cagr']-bm['cagr']) <= 1.0}")


if __name__ == "__main__":
    main()
