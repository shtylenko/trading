"""Shared 1-minute intraday engine for VWAP Bounce and Gap-and-Go.

Session VWAP + a per-day one-trade simulator (stop / target / time-cutoff) on
1-min RTH bars. Same cost model (bps/side) as the daily engine so intraday and
daily results are comparable.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

_NY = ZoneInfo("America/New_York")


def load_1min(ticker: str, start: date, end: date) -> pd.DataFrame | None:
    df = fetch_bars(
        ticker, "1min",
        start=datetime(start.year, start.month, start.day, 0, 0, tzinfo=_NY),
        end=datetime(end.year, end.month, end.day, 23, 59, tzinfo=_NY),
        session="rth", adjustment="raw",
    )
    if df is None or df.empty:
        return None
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]]


def load_daily_prevclose(ticker: str, start: date, end: date) -> dict:
    """date -> prior session close (for gap computation)."""
    df = fetch_bars(
        ticker, "1day",
        start=datetime(start.year - (start.month == 1), 12 if start.month == 1 else start.month - 1, 1, tzinfo=_NY),
        end=datetime(end.year, end.month, end.day, 23, 59, tzinfo=_NY),
        session="rth", adjustment="raw",
    )
    if df is None or df.empty:
        return {}
    c = df["close"] if "close" in df.columns else df[[x for x in df.columns if str(x).lower() == "close"][0]]
    idx = pd.to_datetime(df.index).tz_convert("America/New_York").tz_localize(None).normalize()
    prev = {}
    vals = c.to_numpy(float)
    for k in range(1, len(vals)):
        prev[idx[k].date()] = float(vals[k - 1])
    return prev


def session_vwap(bars: pd.DataFrame) -> np.ndarray:
    tp = (bars["high"] + bars["low"] + bars["close"]).to_numpy(float) / 3.0
    v = bars["volume"].to_numpy(float)
    cum_v = np.cumsum(v)
    cum_pv = np.cumsum(tp * v)
    return cum_pv / np.where(cum_v == 0, np.nan, cum_v)


def simulate_intraday(o, h, l, c, entry_i, entry_px, stop, target, cutoff_i, cost_bps):
    """Walk 1-min bars from entry_i..cutoff_i. Returns (exit_px, reason, exit_i)."""
    cf = cost_bps / 10_000.0
    entry = entry_px * (1.0 + cf)
    for d in range(entry_i, cutoff_i + 1):
        if l[d] <= stop:
            raw = o[d] if (d == entry_i and o[d] < stop) else stop
            return entry, raw * (1.0 - cf), "stop", d, entry
        if target is not None and h[d] >= target:
            raw = o[d] if (d == entry_i and o[d] > target) else target
            return entry, raw * (1.0 - cf), "target", d, entry
        if d == cutoff_i:
            return entry, c[d] * (1.0 - cf), "time", d, entry
    return None


def run_intraday(ticker, day_fn, start: date, end: date, *, cost_bps: float = 5.0,
                 need_prevclose: bool = False) -> list[dict]:
    bars = load_1min(ticker, start, end)
    if bars is None or bars.empty:
        return []
    idx = pd.to_datetime(bars.index).tz_convert("America/New_York").tz_localize(None)
    day_key = idx.normalize()
    prevclose = load_daily_prevclose(ticker, start, end) if need_prevclose else {}

    trades = []
    for day, g in bars.groupby(day_key):
        d = day.date()
        if len(g) < 60:
            continue
        o = g["open"].to_numpy(float); h = g["high"].to_numpy(float)
        l = g["low"].to_numpy(float); c = g["close"].to_numpy(float)
        vwap = session_vwap(g)
        sig = day_fn(o, h, l, c, vwap, prevclose.get(d))
        if sig is None:
            continue
        entry_i, entry_px, stop, target, cutoff_i = sig
        res = simulate_intraday(o, h, l, c, entry_i, entry_px, stop, target, cutoff_i, cost_bps)
        if res is None:
            continue
        _, exit_px, reason, exit_i, entry_cost = res
        risk = entry_cost - stop
        trades.append({
            "ticker": ticker, "signal_date": d, "entry_date": d, "exit_date": d,
            "entry_price": entry_cost, "exit_price": exit_px, "stop_price": stop,
            "risk_per_share": risk,
            "realized_r": (exit_px - entry_cost) / risk if risk > 0 else np.nan,
            "pnl_pct": exit_px / entry_cost - 1.0,
            "hold_days": 1, "hold_bars": exit_i - entry_i + 1, "exit_reason": reason,
        })
    return trades
