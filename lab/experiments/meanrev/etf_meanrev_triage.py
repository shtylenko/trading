#!/usr/bin/env python3
"""STAGE-0 TRIAGE: index-level short-horizon mean-reversion ETF sleeve vs x03.

Origin: the 2026-06-22 Kimi research bundles surfaced ONE direction we have not
cleanly tested on this universe — index-level "buy the dip in an uptrend" mean
reversion (IBS / RSI-2) on a handful of liquid ETFs. The reports' strongest
cross-dimensional claim is that momentum and mean reversion run ≈ -0.35 correlated
(J.P. Morgan: a 50/50 blend cut momentum max-DD -57.6%→-32.9%). Our backlog says
"no long-only diversifier exists for x03" — but that verdict was reached WITHIN the
cross-sectional stock-momentum universe (every sleeve shared market beta). An
index-level IBS sleeve is a structurally DIFFERENT mechanism (behavioral
overreaction, 1-5 day hold), and our prior mean-reversion kill (f-series) was on
cross-sectional STOCK setups, not index dip-buying. So this is genuinely untested.

This is a STAGE-0 TRIAGE, not a promotion test. The bar is NOT "beats x03" — it is:
  (1) does the sleeve earn POSITIVE returns gross + after a cost stub on 2022-24, and
  (2) is it LOW / NEGATIVELY correlated to the x03 book at a comparable (20-day) freq,
  (3) does a naive 50/50 blend with x03 raise Sharpe / shrink max-DD?
If yes on (2)+(3) it's worth a real capture→search→WF run; if it's just another
+beta sleeve or it bleeds, it dies here cheap. 2025 stays HARD-SEALED.

Sleeve mechanics (each ETF = its own equal-capital 1/N sub-account, long or flat —
conservative, no concentration leverage; reports show MR edges degraded 30-50% since
2010 so we do NOT flatter it by concentrating capital into the few signaled names):
  trend filter : long only when close > SMA(200)        (dip-buy in an uptrend)
  IBS variant  : IBS=(C-L)/(H-L); enter IBS<ent, exit IBS>0.7 or hold>=MAX_HOLD
  RSI2 variant : RSI(2); enter RSI2<ent, exit RSI2>50 or hold>=MAX_HOLD
  signal uses info through close[t]; exposure applies to the t+1 close-to-close return
  cost stub: ONEWAY bp charged on each per-ETF entry and exit (to its 1/N slice)

x03 book: the live CAPM-residual "sharpe" score, top-50 EW, non-overlapping H=20 —
recomputed on the SAME split ledger so the correlation is apples-to-apples. Usage:
    python3 -m trading.lab.experiments.meanrev.etf_meanrev_triage \
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

# liquid, deep ETFs: broad indices + the sector sleeves (all $100M+ ADV, tight spreads)
ETFS = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV", "XLP", "XLU", "XLI", "XLY", "XLB"]
H = 20
TOP_N = 50
FORM_LB = 252
SKIP = 21
MIN_OBS = 126
SMA_N = 200
MAX_HOLD = 10
ONEWAY = 5.0 / 10000.0   # 5bp one-way cost stub on each per-ETF transition


def _sharpe(r, periods_per_year):
    r = np.asarray(r, float)
    sd = r.std(ddof=1)
    return r.mean() / sd * np.sqrt(periods_per_year) if sd > 0 else np.nan


def _maxdd(r):
    eq = np.cumprod(1 + np.asarray(r, float))
    return float((eq / np.maximum.accumulate(eq) - 1).min())


def _rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    rs = up.ewm(alpha=1.0 / n, adjust=False).mean() / dn.ewm(alpha=1.0 / n, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + rs)


def sleeve_daily(bars: dict[str, pd.DataFrame], cal: pd.DatetimeIndex, kind: str, ent: float):
    """Returns (daily_ret Series on cal, exposure_fraction). Per-ETF 1/N equal capital."""
    n_uni = len(bars)
    contrib = pd.DataFrame(0.0, index=cal, columns=list(bars.keys()))
    exposure = pd.DataFrame(0.0, index=cal, columns=list(bars.keys()))
    for tk, df in bars.items():
        c = df["close"]; ret = c.pct_change()
        sma = c.rolling(SMA_N).mean()
        up = c > sma
        if kind == "ibs":
            rng = (df["high"] - df["low"]).replace(0.0, np.nan)
            sig = (df["close"] - df["low"]) / rng
            enter = up & (sig < ent); exit_ = sig > 0.7
        else:  # rsi2
            sig = _rsi(c, 2)
            enter = up & (sig < ent); exit_ = sig > 50.0
        enter = enter.reindex(cal).fillna(False).values
        exit_ = exit_.reindex(cal).fillna(False).values
        retv = ret.reindex(cal).fillna(0.0).values
        held = np.zeros(len(cal), dtype=bool)  # position state at END of day t
        in_pos = False; days = 0
        for i in range(len(cal)):
            if in_pos:
                days += 1
                if exit_[i] or days >= MAX_HOLD:
                    in_pos = False
            if not in_pos and enter[i]:
                in_pos = True; days = 0
            held[i] = in_pos
        # exposure on day t+1 = state at end of day t; charge cost on transitions
        w_next = np.concatenate([[False], held[:-1]])
        trans = np.concatenate([[False], held[:-1] != held[1:]])  # entries+exits
        slice_ret = w_next * retv - trans * ONEWAY
        contrib[tk] = slice_ret / n_uni
        exposure[tk] = w_next.astype(float)
    daily = contrib.sum(axis=1)
    return daily, float(exposure.values.mean())


def x03_periods(ledger: Path):
    """Live x03 'sharpe' book: per-period (20-day) returns + the period date windows."""
    df = pd.read_parquet(ledger)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    df = df[df["trade_date"].dt.year != fs.OOS_YEAR].copy()
    close = df.pivot_table(index="trade_date", columns="ticker", values="close", aggfunc="last").sort_index()
    rets = close.pct_change()
    dates = list(close.index)
    spy = fetch_daily_range("SPY", dates[0] - timedelta(days=10), dates[-1] + timedelta(days=10), adjustment="split")
    spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    spy_ret = spy["close"].pct_change().reindex(close.index)
    elig = df.pivot_table(index="trade_date", columns="ticker", values="eligible", aggfunc="last")
    cols = np.array(close.columns)
    rows = []  # (d_start, d_end, book_ret)
    for d in dates[::H]:
        di = close.index.get_loc(d)
        lo, hi = di - FORM_LB, di - SKIP
        if lo < 1 or hi <= lo + MIN_OBS or di + H >= len(dates):
            continue
        win = rets.iloc[lo:hi]
        sp = spy_ret.iloc[lo:hi].values
        spd = sp - np.nanmean(sp); var_sp = np.nansum(spd * spd)
        elig_row = elig.loc[d].fillna(False).values.astype(bool)
        fwd_row = close.iloc[di + H].values / close.iloc[di].values - 1.0
        cand = elig_row & np.isfinite(fwd_row) & (np.isfinite(win.values).sum(axis=0) >= MIN_OBS)
        if cand.sum() < TOP_N:
            continue
        Rc = win.values[:, cand]; mask = np.isfinite(Rc)
        beta = (np.where(mask, Rc, 0.0) * spd[:, None]).sum(axis=0) / var_sp
        resid = np.where(mask, Rc - beta[None, :] * sp[:, None], np.nan)
        score = np.nanmean(resid, axis=0) / np.nanstd(resid, axis=0, ddof=1)
        fc = fwd_row[cand]; good = np.isfinite(score) & np.isfinite(fc)
        if good.sum() < TOP_N:
            continue
        sel = np.argsort(-score[good])[:TOP_N]
        rows.append((dates[di], dates[di + H], float(np.mean(fc[good][sel]))))
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    args = p.parse_args()
    ledger = Path(args.ledger)
    if not ledger.is_absolute():
        ledger = PROJECT_ROOT / ledger

    rows = x03_periods(ledger)
    x_start, x_end = rows[0][0], rows[-1][1]
    x_ret = np.array([r[2] for r in rows])
    x_sh = _sharpe(x_ret, 252.0 / H); x_dd = _maxdd(x_ret)

    # fetch ETF bars over the x03 window + SMA warmup
    bars: dict[str, pd.DataFrame] = {}
    for tk in ETFS:
        b = fetch_daily_range(tk, (x_start - timedelta(days=420)).date(), (x_end + timedelta(days=5)).date(),
                              adjustment="split")
        if b is None or b.empty:
            continue
        b.index = pd.DatetimeIndex(b.index).normalize().tz_localize(None)
        b = b[~b.index.duplicated(keep="last")].sort_index()
        bars[tk] = b
    cal = sorted(set().union(*[set(b.index) for b in bars.values()]))
    cal = pd.DatetimeIndex([d for d in cal if x_start <= d <= x_end])

    print(f"ETF mean-reversion STAGE-0 triage  (ledger={ledger.name})")
    print(f"window {x_start.date()}..{x_end.date()}  |  {len(bars)} ETFs  |  2025 SEALED")
    print(f"x03 book: {len(rows)} periods  Sharpe {x_sh:+.2f}  maxDD {x_dd*100:+.1f}%\n")
    print(f"{'signal':>10}{'expo%':>7}{'sleeveSh':>9}{'sleeveDD':>9}{'sumRet%':>9}"
          f"{'corr_x03':>9}{'blendSh':>8}{'blendDD':>8}")

    grid = [("ibs", 0.2), ("ibs", 0.3), ("rsi2", 5.0), ("rsi2", 10.0)]
    for kind, ent in grid:
        daily, expo = sleeve_daily(bars, cal, kind, ent)
        s_sh = _sharpe(daily.values, 252.0); s_dd = _maxdd(daily.values)
        s_sum = float((np.cumprod(1 + daily.values)[-1] - 1) * 100)
        # compound sleeve daily returns over each x03 20-day period window -> aligned series
        sleeve_p = []
        for d0, d1, _ in rows:
            seg = daily.loc[(daily.index > d0) & (daily.index <= d1)].values
            sleeve_p.append(float(np.prod(1 + seg) - 1) if len(seg) else 0.0)
        sleeve_p = np.array(sleeve_p)
        corr = float(np.corrcoef(sleeve_p, x_ret)[0, 1])
        blend = 0.5 * x_ret + 0.5 * sleeve_p
        b_sh = _sharpe(blend, 252.0 / H); b_dd = _maxdd(blend)
        print(f"{kind+'<'+str(ent):>10}{expo*100:>7.0f}{s_sh:>+9.2f}{s_dd*100:>+9.1f}{s_sum:>+9.1f}"
              f"{corr:>+9.2f}{b_sh:>+8.2f}{b_dd*100:>+8.1f}")

    print("\n>>> Read: TRIAGE PASS needs (a) sleeve sumRet%>0 net of the 5bp stub, (b) corr_x03")
    print("    near 0 or NEGATIVE, (c) blendSh > x03 Sharpe AND blendDD shallower than x03 maxDD.")
    print("    If corr is high-positive or the sleeve bleeds, it's another beta sleeve -> dies here.")


if __name__ == "__main__":
    main()
