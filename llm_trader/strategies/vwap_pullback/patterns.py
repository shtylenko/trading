"""Same-day VWAP pullback detection + bar-path simulation (5-minute RTH)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.indicators import normalize_to_et, session_vwap
from trading.llm_trader.models import Entry

from .config import VwapPullbackConfig


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


def screen_ticker(ticker: str, cfg: VwapPullbackConfig) -> list[DayCandidate]:
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
    df["avg_vol"] = df["volume"].shift(1).rolling(cfg.rvol_lookback).mean()
    df["gap_pct"] = (df["open"] - df["prior_close"]) / df["prior_close"].replace(0, pd.NA) * 100.0
    df["rvol"] = df["volume"] / df["avg_vol"].replace(0, pd.NA)

    out: list[DayCandidate] = []
    for row in df.itertuples():
        d = row.Index.date() if hasattr(row.Index, "date") else pd.Timestamp(row.Index).date()
        if d < cfg.start or d > cfg.end:
            continue
        if pd.isna(row.prior_close) or pd.isna(row.avg_vol) or row.prior_close <= 0:
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
    # RTH only 09:30–16:00
    df = df.between_time(time(9, 30), time(16, 0), inclusive="left")
    if df.empty:
        return None
    df = df.copy()
    df["vwap"] = session_vwap(df)
    return df


def detect_from_frame(
    df: pd.DataFrame,
    cand: DayCandidate,
    cfg: VwapPullbackConfig,
) -> Optional[Entry]:
    """First VWAP pullback reclaim in the entry window, after morning strength."""
    if df is None or df.empty or "vwap" not in df.columns:
        return None

    # Morning confirmation: bars 09:30 → morning_confirm_end mostly above VWAP
    m_end = datetime.strptime(cfg.morning_confirm_end, "%H:%M").time()
    morning = df.between_time(time(9, 30), m_end, inclusive="left")
    if morning.empty or len(morning) < cfg.min_bars_above_vwap_before:
        return None
    above = (morning["close"] > morning["vwap"]).sum()
    if above < cfg.min_bars_above_vwap_before:
        return None
    # Prefer open not deeply below VWAP
    if float(morning["close"].iloc[0]) < float(morning["vwap"].iloc[0]) * 0.995:
        return None

    e0 = datetime.strptime(cfg.entry_window_start, "%H:%M").time()
    e1 = datetime.strptime(cfg.entry_window_end, "%H:%M").time()
    win = df.between_time(e0, e1, inclusive="left")
    if win.empty:
        return None

    # Count consecutive bars above VWAP before a touch
    bars_above = 0
    # Also count from morning into window
    for _, row in morning.iterrows():
        if float(row["close"]) > float(row["vwap"]):
            bars_above += 1
        else:
            bars_above = 0

    for ts, row in win.iterrows():
        vwap = float(row["vwap"])
        lo, hi, op, cl = float(row["low"]), float(row["high"]), float(row["open"]), float(row["close"])
        if not np.isfinite(vwap) or vwap <= 0:
            continue
        # Still building "above" streak until touch
        touched = lo <= vwap <= hi
        if not touched:
            if cl > vwap:
                bars_above += 1
            else:
                bars_above = 0
            continue

        if bars_above < cfg.min_bars_above_vwap_before:
            # touch without prior strength — reset
            bars_above = 1 if cl > vwap else 0
            continue

        # Reclaim: close back above VWAP
        if cl < vwap:
            bars_above = 0
            continue
        if cfg.require_green_reclaim and cl <= op:
            bars_above = 0
            continue

        # Setup found
        stop_px = round(vwap * (1.0 - cfg.stop_below_vwap_pct / 100.0), 4)
        entry_px = round(cl, 4)  # reclaim close as reference; sim may fill next open
        if stop_px >= entry_px:
            return None
        if getattr(cfg, "nml_gate", False):
            from trading.llm_trader.admission.no_mans_land import evaluate_long_edge

            # signal bar index in full session frame
            try:
                sig_i = list(df.index).index(ts)
            except ValueError:
                sig_i = -1
            if sig_i >= 0:
                nml = evaluate_long_edge(df, sig_i, entry_px)
                if not nml.admit:
                    bars_above = 1 if cl > vwap else 0
                    continue
        risk = entry_px - stop_px
        t1 = round(entry_px + cfg.target1_r_mult * risk, 4)
        t2 = round(entry_px + cfg.target2_r_mult * risk, 4)
        t_et = ts.strftime("%H:%M") if hasattr(ts, "strftime") else str(ts)[11:16]

        features: dict[str, Any] = {
            "signal_kind": "vwap_reclaim",
            "signal_as_of": cand.day.isoformat(),
            "entry_trigger": entry_px,
            "stop_px": stop_px,
            "target1_px": t1,
            "target2_px": t2,
            "vwap": round(vwap, 4),
            "atr": round(risk, 4),  # risk unit as pseudo-atr for plan tools
            "measured_move_px": round(risk * cfg.target2_r_mult, 4),
            "arm_expiry_bars": 1,
            "max_entry_gap_atr": 0.5,
            "gap_pct": cand.gap_pct,
            "rvol": cand.rvol,
            "horizon": "intraday",
            "construction": "v0.1.0_vwap_pullback_reclaim",
        }
        return Entry(
            ticker=cand.ticker,
            day=cand.day,
            time_et=t_et,
            pattern="vwap_pullback",
            entry_px=entry_px,
            bar_close=entry_px,
            reason=(
                f"VWAP pullback reclaim {t_et} ET: morning above VWAP, touch+reclaim "
                f"@ ${entry_px:.2f}; stop ${stop_px:.2f}; T1 ${t1:.2f} / T2 ${t2:.2f}."
            ),
            strategy="vwap_pullback",
            gap_pct=cand.gap_pct,
            rvol=cand.rvol,
            features=features,
        )
    return None


def detect_entry(cand: DayCandidate, cfg: VwapPullbackConfig) -> Optional[Entry]:
    df = _rth_5m(cand.ticker, cand.day)
    if df is None:
        return None
    return detect_from_frame(df, cand, cfg)


def simulate_trade(entry: Entry, cfg: VwapPullbackConfig) -> Optional[SimTrade]:
    """Walk 5m bars after entry bar; stop / T1 scale / T2 / EOD.

    Entry: next bar open after signal bar (realistic). Stop/targets from features.
    Half off at T1, remainder at T2 or stop/EOD. R based on full risk.
    """
    df = _rth_5m(entry.ticker, entry.day)
    if df is None or df.empty:
        return None
    feats = entry.features or {}
    stop = float(feats["stop_px"])
    t1 = float(feats["target1_px"])
    t2 = float(feats["target2_px"])
    risk_px = float(feats.get("entry_trigger", entry.entry_px)) - stop
    if risk_px <= 0:
        return None

    # Find signal bar
    sig_time = entry.time_et
    times = [ts.strftime("%H:%M") for ts in df.index]
    if sig_time not in times:
        return None
    i = times.index(sig_time)
    if i + 1 >= len(df):
        return None

    # Fill next bar open
    fill_row = df.iloc[i + 1]
    entry_px = float(fill_row["open"])
    entry_time = df.index[i + 1].strftime("%H:%M")
    # Slippage/fees
    slip = cfg.slippage_bps_one_way / 10_000.0
    fee = cfg.fee_bps_one_way / 10_000.0
    entry_px_eff = entry_px * (1.0 + slip + fee)

    # Recompute risk from actual fill vs stop
    if entry_px_eff <= stop:
        return None
    risk_px = entry_px_eff - stop
    shares = max(1, int(cfg.risk_budget / risk_px))
    # Cap notional somewhat
    if shares * entry_px_eff > cfg.risk_budget * 50:
        shares = max(1, int(cfg.risk_budget * 50 / entry_px_eff))

    eod = datetime.strptime(cfg.eod_exit_et, "%H:%M").time()
    remaining = shares
    pnl = 0.0
    exit_time = entry_time
    exit_px = entry_px_eff
    exit_reason = "EOD"
    half_done = False

    for j in range(i + 1, len(df)):
        row = df.iloc[j]
        ts = df.index[j]
        t = ts.time() if hasattr(ts, "time") else datetime.strptime(times[j], "%H:%M").time()
        lo, hi, cl = float(row["low"]), float(row["high"]), float(row["close"])

        # Stop first (conservative)
        if lo <= stop:
            px = stop * (1.0 - slip - fee)
            pnl += (px - entry_px_eff) * remaining
            exit_time = ts.strftime("%H:%M")
            exit_px = px
            exit_reason = "STOP"
            remaining = 0
            break
        # Targets
        if not half_done and hi >= t1:
            px = t1 * (1.0 - slip - fee)
            half = remaining // 2
            if half > 0:
                pnl += (px - entry_px_eff) * half
                remaining -= half
                half_done = True
            if remaining == 0:
                exit_time = ts.strftime("%H:%M")
                exit_px = px
                exit_reason = "TARGET1"
                break
        if half_done and hi >= t2:
            px = t2 * (1.0 - slip - fee)
            pnl += (px - entry_px_eff) * remaining
            remaining = 0
            exit_time = ts.strftime("%H:%M")
            exit_px = px
            exit_reason = "TARGET2"
            break
        if t >= eod:
            px = cl * (1.0 - slip - fee)
            pnl += (px - entry_px_eff) * remaining
            remaining = 0
            exit_time = ts.strftime("%H:%M")
            exit_px = px
            exit_reason = "EOD"
            break

    if remaining > 0:
        # last bar
        cl = float(df.iloc[-1]["close"])
        px = cl * (1.0 - slip - fee)
        pnl += (px - entry_px_eff) * remaining
        exit_time = df.index[-1].strftime("%H:%M")
        exit_px = px
        exit_reason = "EOD"
        remaining = 0

    r_mult = pnl / cfg.risk_budget if cfg.risk_budget else 0.0
    return SimTrade(
        ticker=entry.ticker,
        day=entry.day,
        entry_time=entry_time,
        entry_px=round(entry_px_eff, 4),
        stop_px=stop,
        target1_px=t1,
        target2_px=t2,
        exit_time=exit_time,
        exit_px=round(exit_px, 4),
        exit_reason=exit_reason,
        r_multiple=round(r_mult, 4),
        pnl_usd=round(pnl, 2),
        shares=shares,
    )
