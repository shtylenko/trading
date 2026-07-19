"""Micro-pullback continuation on 5m RTH (Ross / warrior phase-2).

Sequence: morning impulse (runner) → 1–3 bar shallow pullback holding VWAP
→ first green that breaks the pullback high. Stop under pullback low; 1R/2R; EOD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.indicators import normalize_to_et, session_vwap
from trading.llm_trader.models import Entry

from .config import MicroPullbackConfig


@dataclass
class DayCandidate:
    ticker: str
    day: date
    open_px: float
    prior_close: float
    gap_pct: float
    rvol: float
    avg_vol: float


@dataclass
class SimTrade:
    ticker: str
    day: date
    entry_time: str
    entry_px: float
    stop_px: float
    target1_px: float
    target2_px: float
    exit_time: str
    exit_px: float
    exit_reason: str
    r_multiple: float
    pnl_usd: float
    shares: int


def screen_ticker(ticker: str, cfg: MicroPullbackConfig) -> list[DayCandidate]:
    warmup = cfg.rvol_lookback + 15
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup * 2
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty or len(df) < cfg.rvol_lookback + 2:
        return []
    df = df.sort_index()
    df["prior_close"] = df["close"].shift(1)
    # Causal liquidity: prior 20 sessions only (no same-day completed volume).
    df["avg_vol"] = df["volume"].shift(1).rolling(cfg.rvol_lookback).mean()
    df["gap_pct"] = (df["open"] - df["prior_close"]) / df["prior_close"].replace(0, pd.NA) * 100.0
    # Causal RVOL: prior-day volume / avg of days before that window end (E0 PREREG).
    # Old bug: df["volume"]/avg_vol used full-session volume unknown at 09:45–14:00.
    df["rvol"] = df["volume"].shift(1) / df["avg_vol"].replace(0, pd.NA)

    out: list[DayCandidate] = []
    for row in df.itertuples():
        d = row.Index.date() if hasattr(row.Index, "date") else pd.Timestamp(row.Index).date()
        if d < cfg.start or d > cfg.end:
            continue
        if pd.isna(row.prior_close) or pd.isna(row.avg_vol) or row.prior_close <= 0:
            continue
        if pd.isna(row.gap_pct) or pd.isna(row.rvol) or pd.isna(row.open):
            continue
        g, rv, op, av = float(row.gap_pct), float(row.rvol), float(row.open), float(row.avg_vol)
        if not (cfg.gap_min_pct <= g <= cfg.gap_max_pct):
            continue
        if not (cfg.price_min <= op <= cfg.price_max):
            continue
        if av < cfg.avg_vol_min or rv < cfg.rvol_min:
            continue
        out.append(
            DayCandidate(
                ticker=ticker.upper(),
                day=d,
                open_px=op,
                prior_close=float(row.prior_close),
                gap_pct=g,
                rvol=rv,
                avg_vol=av,
            )
        )
    return out


def _rth_5m(ticker: str, day: date) -> Optional[pd.DataFrame]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    df = fetch_bars(ticker, "5min", start=start, end=end, session="rth", adjustment="raw")
    if df is None or df.empty:
        return None
    df = normalize_to_et(df, day=day)
    if df.empty:
        return None
    df = df.between_time(time(9, 30), time(16, 0), inclusive="left")
    if len(df) < 20:
        return None
    df = df.copy()
    df["vwap"] = session_vwap(df)
    return df


def detect_from_frame(
    df: pd.DataFrame,
    cand: DayCandidate,
    cfg: MicroPullbackConfig,
) -> Optional[Entry]:
    """First micro-pullback breakout after a morning impulse."""
    if df is None or df.empty or "vwap" not in df.columns or len(df) < 12:
        return None

    e0 = datetime.strptime(cfg.entry_window_start, "%H:%M").time()
    e1 = datetime.strptime(cfg.entry_window_end, "%H:%M").time()
    open_px = float(df.iloc[0]["open"])
    if open_px <= 0:
        return None

    # State machine over RTH bars
    # impulse_high_i: index of bar that made the impulse high
    # After impulse confirmed, collect pullback bars until break or fail.
    impulse_high = open_px
    impulse_high_i = 0
    impulse_low_anchor = open_px  # low of the impulse leg start region
    up_bars = 0
    impulse_ok = False

    pb_start: Optional[int] = None
    pb_high = 0.0
    pb_low = float("inf")
    pb_bars = 0

    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        t = ts.time() if hasattr(ts, "time") else pd.Timestamp(ts).time()
        hi = float(row["high"])
        lo = float(row["low"])
        op = float(row["open"])
        cl = float(row["close"])
        vwap = float(row["vwap"]) if np.isfinite(row["vwap"]) else np.nan

        if not impulse_ok:
            if cl > op:
                up_bars += 1
            else:
                up_bars = max(0, up_bars - 1)
            if hi > impulse_high:
                impulse_high = hi
                impulse_high_i = i
            impulse_pct = (impulse_high - open_px) / open_px * 100.0
            above_vwap = (not cfg.require_above_vwap) or (
                np.isfinite(vwap) and cl >= vwap
            )
            if (
                up_bars >= cfg.impulse_min_bars
                and impulse_pct >= cfg.impulse_min_pct
                and above_vwap
                and i >= 1
            ):
                impulse_ok = True
                # seed pullback tracking from next bar
                pb_start = None
                pb_high = 0.0
                pb_low = float("inf")
                pb_bars = 0
            continue

        # --- impulse established: look for micro-pullback then break ---
        # Update impulse high if runner extends without a pullback yet
        if pb_start is None and hi > impulse_high:
            impulse_high = hi
            impulse_high_i = i
            continue

        # Starting or extending pullback: no new high of the impulse
        if hi <= impulse_high + 1e-9:
            if pb_start is None:
                pb_start = i
                pb_high = hi
                pb_low = lo
                pb_bars = 1
            else:
                pb_bars += 1
                pb_high = max(pb_high, hi)
                pb_low = min(pb_low, lo)

            if pb_bars > cfg.pb_max_bars:
                # Pullback too long — reset impulse from here
                impulse_ok = False
                up_bars = 1 if cl > op else 0
                impulse_high = hi
                impulse_high_i = i
                open_px = cl  # re-anchor mild (avoid huge stale impulse)
                pb_start = None
                continue

            # Depth check continuously
            impulse_range = impulse_high - min(impulse_low_anchor, open_px)
            if impulse_range <= 0:
                impulse_range = max(impulse_high - open_px, 1e-6)
            depth = impulse_high - pb_low
            if depth > cfg.pb_max_depth_frac * impulse_range:
                # Too deep — not a micro-pullback
                impulse_ok = False
                up_bars = 0
                impulse_high = hi
                impulse_high_i = i
                pb_start = None
                continue

            if cfg.pb_must_hold_vwap and np.isfinite(vwap) and lo < vwap * 0.999:
                impulse_ok = False
                up_bars = 0
                impulse_high = max(hi, cl)
                impulse_high_i = i
                pb_start = None
                continue
            continue  # still in pullback / wait for break on a later bar

        # hi > impulse_high — potential breakout. Need an actual pullback first.
        if pb_start is None or pb_bars < cfg.pb_min_bars:
            # Extension without pause — keep running impulse
            impulse_high = hi
            impulse_high_i = i
            continue

        # Break of structure: prefer break of *pullback high* (Ross), not only impulse high
        # Signal: bar makes new high through pb_high (and usually impulse)
        break_level = pb_high
        if hi <= break_level:
            continue

        # Entry only inside window
        if t < e0 or t >= e1:
            # Missed window — abandon this setup for the day
            return None

        if cfg.require_green_break and cl <= op:
            # Failed break attempt on red — treat as pullback extension if still ≤ max
            if pb_bars < cfg.pb_max_bars:
                pb_bars += 1
                pb_high = max(pb_high, hi)
                pb_low = min(pb_low, lo)
                continue
            impulse_ok = False
            pb_start = None
            up_bars = 0
            impulse_high = hi
            continue

        if cfg.require_green_break and cl <= break_level:
            # High pierced but close failed back under pb high
            if pb_bars < cfg.pb_max_bars:
                pb_high = max(pb_high, hi)
                pb_low = min(pb_low, lo)
                pb_bars += 1
                continue
            return None

        if cfg.require_above_vwap and np.isfinite(vwap) and cl < vwap:
            continue

        # Valid signal
        stop_px = round(pb_low * (1.0 - cfg.stop_buffer_pct / 100.0), 4)
        entry_px = round(cl, 4)
        if stop_px >= entry_px:
            return None
        risk = entry_px - stop_px
        if risk <= 0:
            return None
        t1 = round(entry_px + cfg.target1_r_mult * risk, 4)
        t2 = round(entry_px + cfg.target2_r_mult * risk, 4)
        t_et = ts.strftime("%H:%M")

        impulse_range = max(impulse_high - open_px, 1e-6)
        depth_frac = (impulse_high - pb_low) / impulse_range

        if getattr(cfg, "nml_gate", False):
            from trading.llm_trader.admission.no_mans_land import evaluate_long_edge

            nml = evaluate_long_edge(df, i, entry_px)
            if not nml.admit:
                # Skip this bar; allow later setups same day by resetting pb
                impulse_ok = False
                pb_start = None
                up_bars = 0
                impulse_high = hi
                impulse_high_i = i
                continue

        features: dict[str, Any] = {
            "signal_kind": "micro_pullback_break",
            "signal_as_of": cand.day.isoformat(),
            "entry_trigger": entry_px,
            "stop_px": stop_px,
            "target1_px": t1,
            "target2_px": t2,
            "atr": round(risk, 4),
            "measured_move_px": round(risk * cfg.target2_r_mult, 4),
            "arm_expiry_bars": 1,
            "max_entry_gap_atr": 0.5,
            "impulse_high": round(impulse_high, 4),
            "pb_high": round(pb_high, 4),
            "pb_low": round(pb_low, 4),
            "pb_bars": pb_bars,
            "impulse_high_i": impulse_high_i,
            "depth_frac": round(float(depth_frac), 4),
            "vwap": round(float(vwap), 4) if np.isfinite(vwap) else None,
            "gap_pct": cand.gap_pct,
            "rvol": cand.rvol,
            "horizon": "intraday",
            "construction": "v0.1.0_micro_pullback_causal_e0",
        }
        return Entry(
            ticker=cand.ticker,
            day=cand.day,
            time_et=t_et,
            pattern="micro_pullback",
            entry_px=entry_px,
            bar_close=entry_px,
            reason=(
                f"Micro-pullback break {t_et}: impulse ${impulse_high:.2f}, "
                f"{pb_bars}-bar pb high ${pb_high:.2f} → green break @ ${entry_px:.2f}; "
                f"stop ${stop_px:.2f}."
            ),
            strategy="micro_pullback",
            gap_pct=cand.gap_pct,
            rvol=cand.rvol,
            features=features,
        )

    return None


def detect_entry(cand: DayCandidate, cfg: MicroPullbackConfig) -> Optional[Entry]:
    df = _rth_5m(cand.ticker, cand.day)
    if df is None:
        return None
    return detect_from_frame(df, cand, cfg)


def simulate_trade(entry: Entry, cfg: MicroPullbackConfig) -> Optional[SimTrade]:
    """Same-day path sim (next-bar open entry; stop / 1R half / 2R / EOD)."""
    df = _rth_5m(entry.ticker, entry.day)
    if df is None or df.empty:
        return None
    feats = entry.features or {}
    stop = float(feats["stop_px"])
    t1 = float(feats["target1_px"])
    t2 = float(feats["target2_px"])

    times = [ts.strftime("%H:%M") for ts in df.index]
    if entry.time_et not in times:
        return None
    i = times.index(entry.time_et)
    if i + 1 >= len(df):
        return None

    slip = cfg.slippage_bps_one_way / 10_000.0
    fee = cfg.fee_bps_one_way / 10_000.0
    entry_px = float(df.iloc[i + 1]["open"]) * (1.0 + slip + fee)
    entry_time = df.index[i + 1].strftime("%H:%M")
    if entry_px <= stop:
        return None
    risk_px = entry_px - stop
    shares = max(1, int(cfg.risk_budget / risk_px))
    if shares * entry_px > cfg.risk_budget * 50:
        shares = max(1, int(cfg.risk_budget * 50 / entry_px))

    eod = datetime.strptime(cfg.eod_exit_et, "%H:%M").time()
    remaining = shares
    pnl = 0.0
    exit_time, exit_px, exit_reason = entry_time, entry_px, "EOD"
    half_done = False

    for j in range(i + 1, len(df)):
        row = df.iloc[j]
        ts = df.index[j]
        t = ts.time() if hasattr(ts, "time") else datetime.strptime(times[j], "%H:%M").time()
        lo, hi, cl = float(row["low"]), float(row["high"]), float(row["close"])
        if lo <= stop:
            px = stop * (1.0 - slip - fee)
            pnl += (px - entry_px) * remaining
            remaining = 0
            exit_time, exit_px, exit_reason = ts.strftime("%H:%M"), px, "STOP"
            break
        if not half_done and hi >= t1:
            px = t1 * (1.0 - slip - fee)
            half = remaining // 2
            if half > 0:
                pnl += (px - entry_px) * half
                remaining -= half
                half_done = True
            if remaining == 0:
                exit_time, exit_px, exit_reason = ts.strftime("%H:%M"), px, "TARGET1"
                break
        if half_done and hi >= t2:
            px = t2 * (1.0 - slip - fee)
            pnl += (px - entry_px) * remaining
            remaining = 0
            exit_time, exit_px, exit_reason = ts.strftime("%H:%M"), px, "TARGET2"
            break
        if t >= eod:
            px = cl * (1.0 - slip - fee)
            pnl += (px - entry_px) * remaining
            remaining = 0
            exit_time, exit_px, exit_reason = ts.strftime("%H:%M"), px, "EOD"
            break

    if remaining > 0:
        cl = float(df.iloc[-1]["close"])
        px = cl * (1.0 - slip - fee)
        pnl += (px - entry_px) * remaining
        exit_time = df.index[-1].strftime("%H:%M")
        exit_px, exit_reason = px, "EOD"

    return SimTrade(
        ticker=entry.ticker,
        day=entry.day,
        entry_time=entry_time,
        entry_px=round(entry_px, 4),
        stop_px=stop,
        target1_px=t1,
        target2_px=t2,
        exit_time=exit_time,
        exit_px=round(exit_px, 4),
        exit_reason=exit_reason,
        r_multiple=round(pnl / cfg.risk_budget, 4),
        pnl_usd=round(pnl, 2),
        shares=shares,
    )
