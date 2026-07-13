"""Shared daily trade simulator enforcing the short-hold (<=3 session) mandate.

A strategy produces a list of `Signal`s; this engine fills entries, applies
stop / optional target / hard time-stop exits over a bounded hold window, and
returns a trades DataFrame. One shared, auditable exit model → results are
comparable across all strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

import numpy as np
import pandas as pd


@dataclass
class Signal:
    ticker: str
    signal_date: date
    stop: float                      # initial stop price
    target: float | None = None      # optional profit target (price)
    trigger: float | None = None     # buy-stop trigger (for entry='buy_stop')
    entry: str = "next_open"         # next_open | buy_stop | signal_close
    exit_on_open: bool = False       # exit at open of first held session (overnight)
    meta: dict | None = None


def _sessions(idx) -> np.ndarray:
    i = pd.to_datetime(idx)
    if getattr(i, "tz", None) is not None:
        i = i.tz_convert("America/New_York").tz_localize(None)
    return i.normalize().to_numpy(dtype="datetime64[D]")


def simulate(
    df: pd.DataFrame,
    signals: Sequence[Signal],
    *,
    max_hold: int = 3,
    cost_bps: float = 5.0,
    one_at_a_time: bool = True,
) -> list[dict[str, Any]]:
    """Simulate one ticker's signals. `df` = that ticker's enriched daily frame.

    max_hold = number of sessions the position may be held (incl. entry day);
    3 = the mandate (flat by end of T+2).
    """
    sess = _sessions(df.index)
    pos = {pd.Timestamp(d).date(): k for k, d in enumerate(sess)}
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(c)
    cf = cost_bps / 10_000.0

    trades: list[dict[str, Any]] = []
    flat_after = -1
    for sig in sorted(signals, key=lambda s: s.signal_date):
        si = pos.get(sig.signal_date)
        if si is None:
            continue
        # entry session index
        if sig.entry == "signal_close":
            ei = si
        else:
            ei = si + 1
        if ei >= n:
            continue
        if one_at_a_time and ei <= flat_after:
            continue

        # fill
        if sig.entry == "buy_stop":
            trig = sig.trigger
            if trig is None or h[ei] < trig:
                continue  # breakout did not trigger next session
            raw_entry = max(o[ei], trig)
        elif sig.entry == "signal_close":
            raw_entry = c[si]
        else:  # next_open
            raw_entry = o[ei]
        if not np.isfinite(raw_entry) or raw_entry <= 0:
            continue
        entry = raw_entry * (1.0 + cf)

        stop = float(sig.stop)
        target = float(sig.target) if sig.target is not None else None
        risk = entry - stop
        if not np.isfinite(risk) or risk <= 0:
            continue

        # signal_close enters at close of signal bar -> exposure starts next
        # session; next_open/buy_stop enter at ei's open -> exposure includes ei.
        scan_start = ei + 1 if sig.entry == "signal_close" else ei
        scan_end = min(scan_start + max_hold - 1, n - 1)
        if scan_start >= n:
            continue
        exit_i = exit_raw = reason = None

        # overnight: exit at the open of the first held session
        if sig.exit_on_open:
            exit_raw, exit_i, reason = o[scan_start], scan_start, "overnight_open"

        if exit_i is None:
            for d in range(scan_start, scan_end + 1):
                od, hd, ld, cd = o[d], h[d], l[d], c[d]
                if d == scan_start and od <= stop:      # gap-through at open
                    exit_raw, exit_i, reason = od, d, "stop_gap"
                    break
                if ld <= stop:
                    exit_raw = od if od < stop else stop
                    exit_i, reason = d, "stop"
                    break
                if target is not None and hd >= target:
                    exit_raw = od if od >= target else target
                    exit_i, reason = d, "target"
                    break
                if d == scan_end:
                    exit_raw, exit_i, reason = cd, d, "time"
                    break
        if exit_i is None:
            continue
        exit_px = float(exit_raw) * (1.0 - cf)
        rr = (exit_px - entry) / risk
        trades.append({
            "ticker": sig.ticker,
            "signal_date": sig.signal_date,
            "entry_date": pd.Timestamp(sess[ei]).date(),
            "exit_date": pd.Timestamp(sess[exit_i]).date(),
            "entry_price": entry,
            "exit_price": exit_px,
            "stop_price": stop,
            "risk_per_share": risk,
            "realized_r": rr,
            "pnl_pct": exit_px / entry - 1.0,
            "hold_days": exit_i - ei + 1,
            "exit_reason": reason,
        })
        flat_after = exit_i
    return trades


def run_strategy(
    panel: dict[str, pd.DataFrame],
    signal_fn,
    *,
    max_hold: int = 3,
    cost_bps: float = 5.0,
    ctx: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Apply `signal_fn(ticker, df, ctx) -> list[Signal]` across the panel."""
    all_trades: list[dict[str, Any]] = []
    for t, df in panel.items():
        try:
            sigs = signal_fn(t, df, ctx)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("strategytester.engine").warning("signal fail %s: %s", t, e)
            sigs = []
        if not sigs:
            continue
        all_trades.extend(simulate(df, sigs, max_hold=max_hold, cost_bps=cost_bps))
    if not all_trades:
        return pd.DataFrame()
    return pd.DataFrame(all_trades).sort_values(["entry_date", "ticker"]).reset_index(drop=True)
