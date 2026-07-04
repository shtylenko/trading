#!/usr/bin/env python3
"""x04 overlapping-portfolio construction — pre-registered test
(`validation/multiday_x04_overlapping_preregistration.md`).

Jegadeesh-Titman (1993) overlapping sleeves vs the current non-overlapping (whole-book
every H days) construction, on the SAME x03 residual-momentum ranking. The textbook
benefit is NOT lower per-unit-time turnover (capital still rolls over H days either way)
but (1) VARIANCE REDUCTION — averaging K staggered sleeves removes single-rebalance-date
timing luck → higher gross Sharpe; and (2) CAPACITY — overlap trades (AUM/K)/50 per name
per day instead of a lumpy AUM/50 clip, so peak participation drops ~K× and the convex
impact cost is paid on far smaller clips. This script measures both and prints the
net-Sharpe-vs-AUM cost curve (the "extended cost curve" deliverable).

Computed from the existing split-adjusted capture parquet (per-ticker daily close) + SPY.
2025 hard-sealed out of the in-sample windows. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_overlapping \
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

# ── pre-committed constants (locked in the spec) ──────────────────────────────
H = 20                     # hold / formation horizon (trading days)
TOP_N = 50
FORM_LB = 252              # residual-momentum formation lookback
SKIP = 21                 # skip-month
MIN_OBS = 126             # min formation obs (excludes recent IPOs)
K_PRIMARY = H             # daily-overlapping sleeves (step = 1)
SPREAD_BPS = 5.0          # half-spread cost component is SPREAD_BPS/2
IMPACT_BPS = 10.0         # √-law impact coefficient (100% of ADV → 10 bps)
AUM_GRID = [5, 10, 25, 50, 100, 250]   # $M
ANN_D = float(np.sqrt(252.0))          # daily → annual Sharpe


def _resid_rank(rets_win: np.ndarray, spy_win: np.ndarray) -> np.ndarray:
    """CAPM-residual momentum mean(ε)/std(ε) per column (name), vectorized.

    rets_win: (Twin × Ncand) formation daily returns; spy_win: (Twin,). Matches
    scripts/multiday_residmom.py so the ranking reproduces x03 exactly.
    """
    spd = spy_win - np.nanmean(spy_win)
    var_sp = float(np.nansum(spd * spd))
    mask = np.isfinite(rets_win)
    R0 = np.where(mask, rets_win, 0.0)
    beta = (R0 * spd[:, None]).sum(axis=0) / var_sp
    resid = np.where(mask, rets_win - beta[None, :] * spy_win[:, None], np.nan)
    mu = np.nanmean(resid, axis=0)
    sd = np.nanstd(resid, axis=0, ddof=1)
    return np.where(sd > 0, mu / sd, np.nan)


def _sharpe(daily: np.ndarray) -> float:
    daily = daily[np.isfinite(daily)]
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * ANN_D) if sd > 0 else float("nan")


def _maxdd(daily: np.ndarray) -> float:
    eq = np.cumprod(1.0 + np.nan_to_num(daily))
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def _cost_frac(clip_notional: np.ndarray, adv: np.ndarray) -> float:
    """Round-trip cost as a fraction of the clip, averaged over the names traded.

    Per name: bps = SPREAD_BPS/2 + IMPACT_BPS·√(participation); ×2 for round trip.
    Returned value is the weighted cost as a fraction of the *book* (clip-weighted).
    """
    ok = (adv > 0) & np.isfinite(adv) & (clip_notional > 0)
    if not ok.any():
        return 0.0
    part = clip_notional[ok] / adv[ok]
    bps = (SPREAD_BPS / 2.0 + IMPACT_BPS * np.sqrt(part)) * 2.0
    # cost in $ = Σ clip·bps/1e4; as a fraction of the traded notional:
    return float((clip_notional[ok] * bps / 1e4).sum() / clip_notional[ok].sum())


def main() -> None:
    p = argparse.ArgumentParser(description="x04 overlapping vs non-overlapping construction")
    p.add_argument("--ledger", default="trading/lab/experiments/_data/_capture_multiday_2017_2025_split.parquet")
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--end-year", type=int, default=2024, help="inclusive; 2025 sealed-but-spent")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()

    # daily close / dollar-volume / eligibility matrices (full history for formation)
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dvol = df.pivot_table(index="trade_date", columns="ticker", values="dollar_vol_20d", aggfunc="last").reindex(close.index)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last").reindex(close.index)
    dates = list(close.index)

    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)

    tickers = np.array(close.columns)
    rets_v = rets.values
    spy_v = spy_ret.values
    n_days = len(dates)
    in_window = np.array([args.start_year <= d.year <= args.end_year for d in dates])

    # ── form a top-50 sleeve at every eligible day (the overlapping schedule) ──
    # sleeves[j] = (indices into `tickers`) chosen at formation day j, or None.
    sleeves: list[np.ndarray | None] = [None] * n_days
    minadv: list[float] = [float("nan")] * n_days
    for j in range(n_days):
        lo, hi = j - FORM_LB, j - SKIP
        if lo < 1 or hi <= lo + MIN_OBS:
            continue
        win = rets_v[lo:hi]
        sp = spy_v[lo:hi]
        if not np.isfinite(sp).all():
            continue
        elig_row = np.nan_to_num(elig.values[j]).astype(bool)
        obs = np.isfinite(win).sum(axis=0)
        cand = elig_row & (obs >= MIN_OBS) & np.isfinite(dvol.values[j])
        if cand.sum() < TOP_N:
            continue
        score = np.full(len(tickers), np.nan)
        score[cand] = _resid_rank(win[:, cand], sp)
        if np.isfinite(score).sum() < TOP_N:
            continue
        order = np.argsort(np.where(np.isfinite(score), -score, np.inf))[:TOP_N]
        sleeves[j] = order
        minadv[j] = float(np.nanmin(dvol.values[j][order]))

    # ── daily book returns ────────────────────────────────────────────────────
    # overlapping: book ret[j] = mean over active sleeves (formed in (j-H, j]) of the
    # sleeve's equal-weight 1-day return on day j.
    # non-overlapping: only sleeves formed on the H-grid contribute; one active at a time.
    grid = set(range(0, n_days, H))
    over_r = np.full(n_days, np.nan)
    nonov_r = np.full(n_days, np.nan)
    # per-day traded clip bookkeeping (fraction of names rolled × min-adv proxy)
    over_turn = np.full(n_days, np.nan)
    nonov_turn = np.full(n_days, np.nan)

    def sleeve_ret(idx_arr: np.ndarray, j: int) -> float:
        return float(np.nanmean(rets_v[j][idx_arr]))

    last_nonov: np.ndarray | None = None
    for j in range(n_days):
        # active sleeves: formed at f with f < j <= f+H
        active = [sleeves[f] for f in range(max(0, j - H), j) if sleeves[f] is not None]
        if active:
            over_r[j] = float(np.mean([sleeve_ret(s, j) for s in active]))
        # one sleeve rolls per day under daily overlap: the sleeve formed at f=j
        if sleeves[j] is not None:
            prev = sleeves[j - H] if j - H >= 0 else None
            new = set(sleeves[j].tolist())
            old = set(prev.tolist()) if prev is not None else set()
            over_turn[j] = len(new - old) / TOP_N      # one-way name turnover of the rolling sleeve
        # non-overlapping: hold the sleeve formed at the most recent grid date
        if j in grid and sleeves[j] is not None:
            last_nonov = sleeves[j]
            new = set(sleeves[j].tolist())
            old = set(last_nonov.tolist()) if last_nonov is not None else set()
            # turnover vs the sleeve from the previous grid date
            pf = j - H
            old = set(sleeves[pf].tolist()) if pf >= 0 and sleeves[pf] is not None else set()
            nonov_turn[j] = len(new - old) / TOP_N
        if last_nonov is not None:
            nonov_r[j] = sleeve_ret(last_nonov, j)

    # restrict to the scoring window
    w = in_window
    og, ng = over_r[w], nonov_r[w]
    gross_over, gross_nonov = _sharpe(og), _sharpe(ng)
    dd_over, dd_nonov = _maxdd(og[np.isfinite(og)]), _maxdd(ng[np.isfinite(ng)])

    print(f"Overlapping construction test: {path.name}  {args.start_year}-{args.end_year} "
          f"(2025 sealed-but-spent; pre-2022 survivorship-optimistic)")
    print(f"x03 residual ranking, top-{TOP_N} EW, H={H}.  daily-overlap K={K_PRIMARY} sleeves.\n")
    print("=== 1. VARIANCE REDUCTION (gross, no cost) ===")
    print(f"  {'construction':22}{'annSharpe':>11}{'maxDD':>9}{'meanTurn/roll':>15}")
    print(f"  {'non-overlap (H-block)':22}{gross_nonov:>+11.2f}{dd_nonov*100:>+9.1f}"
          f"{np.nanmean(nonov_turn)*100:>14.0f}%")
    print(f"  {'overlap (daily K=20)':22}{gross_over:>+11.2f}{dd_over*100:>+9.1f}"
          f"{np.nanmean(over_turn)*100:>14.0f}%")
    print(f"  → bar #1: overlap gross Sharpe ≥ non-overlap "
          f"({'PASS' if gross_over >= gross_nonov else 'FAIL'})\n")

    # ── 2. net-Sharpe-vs-AUM cost curve ───────────────────────────────────────
    # clip per name: non-overlap = AUM/50 on grid days; overlap = (AUM/K)/50 on every day.
    # cost charged on the rolling fraction; min-ADV of the rolled sleeve is the conservative ADV.
    print("=== 2. NET SHARPE vs AUM (convex impact: spread/2 + 10bps·√participation, round-trip) ===")
    print(f"  {'AUM':>6} | {'non-overlap':>22} | {'overlap K=20':>22}")
    print(f"  {'($M)':>6} | {'netSh   peakPart':>22} | {'netSh   peakPart':>22}")

    def net_curve(daily, turn, clip_per_name_fn, adv_series):
        """Subtract per-day modeled cost; return (net daily series, peak participation)."""
        net = daily.copy()
        peak_part = 0.0
        for j in np.where(np.isfinite(turn))[0]:
            s = sleeves[j]
            if s is None:
                continue
            adv = adv_series[j][s]
            clip = clip_per_name_fn(turn[j], adv)          # $ per name actually traded
            cf = _cost_frac(clip, adv)                     # round-trip cost frac of traded notional
            # fraction of book traded that day:
            traded_book_frac = (turn[j]) if j in grid_or_daily else turn[j]
            net[j] = net[j] - cf * traded_book_frac
            pr = np.nanmax(clip / np.where(adv > 0, adv, np.nan)) if np.isfinite(adv).any() else 0.0
            peak_part = max(peak_part, float(np.nan_to_num(pr)))
        return net, peak_part

    advv = dvol.values
    grid_or_daily = grid  # marker; non-overlap trades on grid, overlap daily (handled per-fn)

    for aum_m in AUM_GRID:
        aum = aum_m * 1e6
        # non-overlap: full position clip AUM/50, only names that turned over actually trade
        def nonov_clip(turn_frac, adv, aum=aum):
            # names traded = turn_frac*50; each at AUM/50 notional
            return np.full(len(adv), aum / TOP_N)
        # overlap: rolling sleeve holds AUM/K; per-name clip = (AUM/K)/50
        def over_clip(turn_frac, adv, aum=aum):
            return np.full(len(adv), (aum / K_PRIMARY) / TOP_N)

        # non-overlap net (trade on grid days only)
        nv_net = ng.copy()
        nv_peak = 0.0
        idx_w = np.where(w)[0]
        offset = idx_w[0]
        for j in idx_w:
            if j in grid and np.isfinite(nonov_turn[j]) and sleeves[j] is not None:
                s = sleeves[j]; adv = advv[j][s]
                clip = nonov_clip(nonov_turn[j], adv)
                cf = _cost_frac(clip, adv)
                nv_net[j - offset] = ng[j - offset] - cf * nonov_turn[j]
                pr = np.nanmax(clip / np.where(adv > 0, adv, np.nan))
                nv_peak = max(nv_peak, float(np.nan_to_num(pr)))
        # overlap net (trade every day, small clips)
        ov_net = og.copy()
        ov_peak = 0.0
        for j in idx_w:
            if np.isfinite(over_turn[j]) and sleeves[j] is not None:
                s = sleeves[j]; adv = advv[j][s]
                clip = over_clip(over_turn[j], adv)
                cf = _cost_frac(clip, adv)
                # book fraction traded today = (1/K)*turn (only the rolling sleeve, its turned names)
                ov_net[j - offset] = og[j - offset] - cf * (over_turn[j] / K_PRIMARY)
                pr = np.nanmax(clip / np.where(adv > 0, adv, np.nan))
                ov_peak = max(ov_peak, float(np.nan_to_num(pr)))

        print(f"  {aum_m:>6} | {_sharpe(nv_net):>+10.2f}  {nv_peak*100:>8.1f}% | "
              f"{_sharpe(ov_net):>+10.2f}  {ov_peak*100:>8.1f}%")

    print("\n  peakPart = largest single-name participation (clip / 20d $ADV) — the binding "
          "capacity constraint. Overlap's ~K× smaller clips push the cost-stressed AUM far higher.")
    print("\n=== DECISION BAR (from the locked spec) ===")
    print("  1. overlap gross Sharpe ≥ non-overlap  (variance reduction is real)")
    print("  2. overlap practical capacity ≥ 2× non-overlap  (net Sharpe within 10% of gross)")
    print("  3. overlap net Sharpe ≥ non-overlap at the non-overlap binding AUM (~$48M)")
    print("  ADOPT x04 iff all three hold; else REJECT (keep non-overlapping).")


if __name__ == "__main__":
    main()
