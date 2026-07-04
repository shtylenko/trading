#!/usr/bin/env python3
"""Build the Phase v2 ML dataset for stocks_in_play_orb from cached 1-min bars.

For every (ticker, trade_date) passing the Stocks-in-Play v1 filters, this
script computes:
  - entry-time features (all observable at the opening-range close), and
  - trade outcome labels for stop-entry and passive-pullback-limit entries,
for each opening-range window (3m / 5m / 10m), at 1-minute resolution.

All prices are raw (unadjusted), consistent within each trailing window;
days whose trailing window likely spans a split (>40% single-day move) are
dropped.

Output: research/data/orb_ml_dataset.parquet (one row per ticker/date/window).
"""
from __future__ import annotations

import glob
import os
import sys
import time
from datetime import date

import numpy as np
import pandas as pd

LAB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_1MIN = os.path.join(LAB_ROOT, "marketdata", "data", "1min")
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")

ETF_EXCLUDE = {"SPY", "QQQ", "SMH", "IWM", "DIA", "XLK", "XLF", "XLE"}

OR_WINDOWS = [3, 5, 10]
STOP_ATR_FRAC = 0.10
TARGET_R = 2.0
PULLBACK_OFFSETS = {"pb02": 0.02, "pb05": 0.05}
PULLBACK_TTL_MIN = 30
EOD_MINUTE = 389  # 15:59 bar index relative to 9:30


def load_ticker_year(ticker: str, year: int = 2024) -> pd.DataFrame | None:
    paths = sorted(
        glob.glob(
            os.path.join(
                DATA_1MIN, ticker, "session=rth", "adjustment=raw", f"year={year}", "month=*", "data.parquet"
            )
        )
    )
    if not paths:
        return None
    frames = [pd.read_parquet(p, columns=["timestamp", "open", "high", "low", "close", "volume"]) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    # minute offset from 9:30
    tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute - (9 * 60 + 30)
    df = df[(tod >= 0) & (tod < 390)]
    df["minute"] = tod[(tod >= 0) & (tod < 390)]
    df["day"] = df["timestamp"].dt.date
    return df


def wilder_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ATR; out[i] uses data up to and including day i."""
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    atr = np.full(n, np.nan)
    if n < period:
        return atr
    atr[period - 1] = tr[:period].mean()
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def build_spy_context() -> pd.DataFrame:
    spy = load_ticker_year("SPY")
    if spy is None:
        raise RuntimeError("SPY 1min data missing")
    rows = []
    for day, g in spy.groupby("day", sort=True):
        m = g["minute"].values
        o, h, l, c, v = (g[k].values for k in ("open", "high", "low", "close", "volume"))
        first5 = m < 5
        if first5.sum() == 0:
            continue
        upto935 = m < 5
        px935 = c[upto935][-1]
        tp = (h + l + c) / 3.0
        cum_v = v[upto935].sum()
        vwap935 = (tp[upto935] * v[upto935]).sum() / cum_v if cum_v > 0 else px935
        rows.append(
            dict(
                day=day,
                spy_open=o[0],
                spy_high=h.max(),
                spy_low=l.min(),
                spy_close=c[-1],
                spy_ret_5m=(px935 - o[0]) / o[0],
                spy_vwap_dist_935=(px935 - vwap935) / vwap935,
            )
        )
    sdf = pd.DataFrame(rows).set_index("day").sort_index()
    closes = sdf["spy_close"].values
    highs = sdf["spy_high"].values
    lows = sdf["spy_low"].values
    atr5 = pd.Series(
        np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1)),
            ),
        ),
        index=sdf.index,
    )
    atr5.iloc[0] = highs[0] - lows[0]
    sdf["spy_vr"] = (atr5.rolling(5).mean() / atr5.rolling(20).mean()).shift(1)
    sdf["spy_gap"] = (sdf["spy_open"] - sdf["spy_close"].shift(1)) / sdf["spy_close"].shift(1)
    return sdf


def simulate_outcomes(m, o, h, l, c, or_end, or_high, stop, atr):
    """Simulate stop-entry and pullback entries on 1-min arrays after the OR.

    Returns dict or None if no breach.
    """
    after = m >= or_end
    idx = np.nonzero(after & (h > or_high))[0]
    if len(idx) == 0:
        # candidate never breached the OR high: selectable at OR close, but no
        # trade occurs. Emit a flat row so selection is not breach-conditioned.
        return {
            "breached": False,
            "breach_delay_min": -1,
            "entry_stop_px": or_high,
            "exit_stop_px": or_high,
            "stop_entry_stopped": False,
            "stop_entry_exit_minute": -1,
            "hit_2r_before_stop": False,
            "mfe_r": 0.0,
            "realized_r_stop_entry": 0.0,
            "risk_per_share": or_high - stop,
            "pb02_loose_filled": False,
            "realized_r_pb02_loose": 0.0,
            "pb05_loose_filled": False,
            "realized_r_pb05_loose": 0.0,
            "pb02_strict_filled": False,
            "realized_r_pb02_strict": 0.0,
            "pb05_strict_filled": False,
            "realized_r_pb05_strict": 0.0,
        }
    t0 = idx[0]
    breach_minute = int(m[t0])
    risk = or_high - stop

    out = {"breached": True, "breach_delay_min": breach_minute - or_end}

    # --- stop-order entry (v1 style) ---
    entry = max(o[t0], or_high)
    stopped = False
    target = or_high + TARGET_R * risk
    hit_target_first = False
    exit_px = None
    exit_minute = None
    mfe = -np.inf
    resolved = False
    for i in range(t0, len(m)):
        mfe = max(mfe, h[i])
        if l[i] <= stop:
            stopped = True
            exit_px = stop
            exit_minute = int(m[i])
            break
        if not resolved and h[i] >= target:
            hit_target_first = True
            resolved = True
    if exit_px is None:
        exit_px = c[-1]
        exit_minute = int(m[-1])
    out.update(
        entry_stop_px=entry,
        exit_stop_px=exit_px,
        stop_entry_stopped=stopped,
        stop_entry_exit_minute=exit_minute,
        hit_2r_before_stop=bool(hit_target_first),
        mfe_r=(mfe - or_high) / risk if np.isfinite(mfe) else 0.0,
        realized_r_stop_entry=(exit_px - entry) / risk,
        risk_per_share=risk,
    )

    # --- pullback limit entries ---
    # "loose": order can fill in the breach minute itself (optimistic).
    # "strict": fills start the minute after the breach (order latency).
    for name, frac in PULLBACK_OFFSETS.items():
        limit = or_high - frac * atr
        for variant, start_i in (("_loose", t0), ("_strict", t0 + 1)):
            filled = False
            fill_i = None
            for i in range(start_i, len(m)):
                if m[i] - breach_minute > PULLBACK_TTL_MIN:
                    break
                if l[i] <= stop:
                    # price collapsed through the stop level: conservative fill
                    # at limit then immediate stop-out in the same minute
                    filled = True
                    fill_i = i
                    break
                if l[i] < limit:
                    filled = True
                    fill_i = i
                    break
            key = f"{name}{variant}"
            if not filled:
                out[f"{key}_filled"] = False
                out[f"realized_r_{key}"] = 0.0
                continue
            f_entry = min(limit, o[fill_i])  # if bar opens below limit, fill at open
            f_exit = None
            for i in range(fill_i, len(m)):
                if l[i] <= stop:
                    f_exit = min(o[i], stop)
                    break
            if f_exit is None:
                f_exit = c[-1]
            out[f"{key}_filled"] = True
            out[f"realized_r_{key}"] = (f_exit - f_entry) / risk
            out[f"entry_{key}_px"] = f_entry
    return out


def process_ticker(ticker: str, spy: pd.DataFrame) -> list[dict]:
    df = load_ticker_year(ticker)
    if df is None or df.empty:
        return []
    days = []
    day_groups = []
    for day, g in df.groupby("day", sort=True):
        days.append(day)
        day_groups.append(g)

    n = len(days)
    if n < 20:
        return []

    d_open = np.array([g["open"].values[0] for g in day_groups])
    d_high = np.array([g["high"].values.max() for g in day_groups])
    d_low = np.array([g["low"].values.min() for g in day_groups])
    d_close = np.array([g["close"].values[-1] for g in day_groups])
    d_vol = np.array([g["volume"].values.sum() for g in day_groups], dtype=float)
    first5_vol = np.array([g["volume"].values[g["minute"].values < 5].sum() for g in day_groups], dtype=float)

    atr = wilder_atr(d_high, d_low, d_close)
    rows = []
    for i in range(15, n):
        g = day_groups[i]
        m = g["minute"].values
        if (m < 5).sum() < 3 or len(m) < 100:
            continue
        o, h, l, c, v = (g[k].values for k in ("open", "high", "low", "close", "volume"))

        prior_atr = atr[i - 1]
        avg_vol_14 = d_vol[i - 14 : i].mean()
        prior_close = d_close[i - 1]
        open_px = o[0]

        # v1 SIP filters
        if not np.isfinite(prior_atr) or prior_atr <= 0.50:
            continue
        if open_px <= 5.0 or avg_vol_14 < 1_000_000:
            continue
        # split / data-glitch guard over trailing window
        prior_rets = np.abs(np.diff(d_close[i - 15 : i]) / d_close[i - 15 : i - 1])
        if np.nanmax(prior_rets) > 0.40 or abs(open_px - prior_close) / prior_close > 0.40:
            continue

        mean_open_vol = first5_vol[i - 14 : i].mean()
        if mean_open_vol <= 0:
            continue
        rv = first5_vol[i] / mean_open_vol
        if rv < 2.0:
            continue

        # first 5-minute candle (green filter, v1 parity)
        f5 = m < 5
        f5_open = o[f5][0]
        f5_close = c[f5][-1]
        f5_high = h[f5].max()
        f5_low = l[f5].min()
        if f5_close <= f5_open:
            continue

        spy_day = spy.loc[days[i]] if days[i] in spy.index else None

        gap_pct = (open_px - prior_close) / prior_close
        prior_day_ret = (d_close[i - 1] - d_close[i - 2]) / d_close[i - 2]

        for w in OR_WINDOWS:
            in_or = m < w
            if in_or.sum() < max(2, w - 2):
                continue
            or_high = h[in_or].max()
            or_low = l[in_or].min()
            or_close = c[in_or][-1]
            or_vol = v[in_or].sum()
            stop = or_high - STOP_ATR_FRAC * prior_atr
            res = simulate_outcomes(m, o, h, l, c, w, or_high, stop, prior_atr)
            row = dict(
                ticker=ticker,
                day=days[i],
                window=w,
                # features (all known at OR close)
                rv=rv,
                gap_pct=gap_pct,
                gap_abs=abs(gap_pct),
                atr_pct=prior_atr / prior_close,
                range_width_atr=(or_high - or_low) / prior_atr,
                or_close_pos=(or_close - or_low) / (or_high - or_low) if or_high > or_low else 0.5,
                f5_body_ratio=(f5_close - f5_open) / (f5_high - f5_low) if f5_high > f5_low else 0.0,
                f5_ret=(f5_close - f5_open) / f5_open,
                open_px=open_px,
                log_dollar_vol=np.log10(max(avg_vol_14 * prior_close, 1.0)),
                vol_concentration=first5_vol[i] / max(avg_vol_14, 1.0),
                prior_day_ret=prior_day_ret,
                or_vol_ratio=or_vol / max(mean_open_vol, 1.0),
                dow=days[i].weekday(),
                spy_gap=float(spy_day["spy_gap"]) if spy_day is not None else 0.0,
                spy_ret_5m=float(spy_day["spy_ret_5m"]) if spy_day is not None else 0.0,
                spy_vwap_dist=float(spy_day["spy_vwap_dist_935"]) if spy_day is not None else 0.0,
                spy_vr=float(spy_day["spy_vr"]) if spy_day is not None and np.isfinite(spy_day["spy_vr"]) else 1.0,
                daily_atr=prior_atr,
                or_high=or_high,
                **res,
            )
            rows.append(row)
    return rows


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    tickers = sorted(
        t
        for t in os.listdir(DATA_1MIN)
        if not t.startswith(".") and t not in ETF_EXCLUDE and os.path.isdir(os.path.join(DATA_1MIN, t))
    )
    print(f"{len(tickers)} tickers")
    spy = build_spy_context()
    all_rows: list[dict] = []
    t_start = time.time()
    for k, t in enumerate(tickers, 1):
        try:
            rows = process_ticker(t, spy)
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {t}: {e}", file=sys.stderr)
        if k % 25 == 0:
            print(f"{k}/{len(tickers)} tickers, {len(all_rows)} rows, {time.time()-t_start:.0f}s", flush=True)
    out = pd.DataFrame(all_rows)
    path = os.path.join(OUT_DIR, "orb_ml_dataset.parquet")
    out.to_parquet(path, index=False)
    print(f"wrote {len(out)} rows -> {path}")
    if not out.empty:
        for w in OR_WINDOWS:
            sub = out[out["window"] == w]
            print(
                f"window={w}m rows={len(sub)} hit2R={sub['hit_2r_before_stop'].mean():.3f} "
                f"meanR(stop-entry)={sub['realized_r_stop_entry'].mean():.4f} "
                f"pb05 loose fill={sub['pb05_loose_filled'].mean():.3f}"
            )


if __name__ == "__main__":
    main()
