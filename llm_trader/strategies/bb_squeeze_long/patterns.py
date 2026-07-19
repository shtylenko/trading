"""BB squeeze → long expansion on 5m RTH bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.indicators import normalize_to_et
from trading.llm_trader.models import Entry

from .config import BbSqueezeLongConfig


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


def screen_ticker(ticker: str, cfg: BbSqueezeLongConfig) -> list[DayCandidate]:
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
    # Causal RVOL: prior-day volume only (was full-day look-ahead).
    df["rvol"] = df["volume"].shift(1) / df["avg_vol"].replace(0, pd.NA)

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
    df = df.between_time(time(9, 30), time(16, 0), inclusive="left")
    if len(df) < 50:
        return None
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, nstd: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    mid = out["close"].rolling(period, min_periods=period).mean()
    sd = out["close"].rolling(period, min_periods=period).std(ddof=0)
    out["bb_mid"] = mid
    out["bb_upper"] = mid + nstd * sd
    out["bb_lower"] = mid - nstd * sd
    out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / mid.replace(0, np.nan)
    return out


def _bb_width_pctile(width: np.ndarray, lookback: int) -> np.ndarray:
    """Causal percentile of width vs *past-only* lookback window.

    Value at i = fraction of past widths *strictly less than* current
    (low ≈ squeeze / at-or-near lookback min).

    Strict `<` (not `<=`) matters: a multi-bar equal-width squeeze plateau
    would otherwise rank mid-range as ties accumulate under `<=`.

    Requires at least max(8, lookback//2) finite past widths.
    """
    n = len(width)
    out = np.full(n, np.nan, dtype=float)
    min_past = max(8, lookback // 2)
    for i in range(n):
        if not np.isfinite(width[i]):
            continue
        # Prefer full lookback; allow shorter windows once enough finite past
        # widths exist so signals can appear inside the entry window.
        j0 = max(0, i - lookback)
        window = width[j0:i]
        window = window[np.isfinite(window)]
        if len(window) < min_past:
            continue
        out[i] = float(np.mean(window < width[i]))
    return out


def detect_from_frame(
    df: pd.DataFrame,
    cand: DayCandidate,
    cfg: BbSqueezeLongConfig,
) -> Optional[Entry]:
    # Need BB period + enough history for a meaningful width percentile,
    # but NOT bb_period+lookback before scanning (that pushed first candidate
    # past entry_window_end on a single RTH session → systematic n=0).
    min_bars = cfg.bb_period + max(12, cfg.squeeze_lookback // 2) + 5
    if df is None or len(df) < min_bars:
        return None
    out = add_bollinger(df, cfg.bb_period, cfg.bb_std)
    vals = out["bb_width"].to_numpy(dtype=float)
    out["bb_width_pctile"] = _bb_width_pctile(vals, cfg.squeeze_lookback)

    e0 = datetime.strptime(cfg.entry_window_start, "%H:%M").time()
    e1 = datetime.strptime(cfg.entry_window_end, "%H:%M").time()

    # Start as soon as mid-band exists; percentile validity is checked per bar.
    for i in range(cfg.bb_period + 1, len(out)):
        ts = out.index[i]
        t = ts.time() if hasattr(ts, "time") else pd.Timestamp(ts).time()
        if t < e0 or t >= e1:
            continue
        row = out.iloc[i]
        mid = float(row["bb_mid"])
        width = float(row["bb_width"])
        pct = float(row["bb_width_pctile"])
        if not all(np.isfinite(x) for x in (mid, width, pct)):
            continue
        # Squeeze condition on *previous* bar (compression before expansion)
        prev = out.iloc[i - 1]
        prev_pct = float(prev["bb_width_pctile"])
        prev_w = float(prev["bb_width"])
        if not np.isfinite(prev_pct) or prev_pct > cfg.squeeze_pctile_max:
            continue
        # Expansion: width rising
        if cfg.require_width_expanding and not (width > prev_w):
            continue
        cl, op = float(row["close"]), float(row["open"])
        if cfg.require_green and cl <= op:
            continue
        if cfg.require_close_above_mid and cl < mid:
            continue
        if cfg.require_close_above_prior_high:
            prev_hi = float(out.iloc[i - 1]["high"])
            if cl <= prev_hi:
                continue

        # Stop under recent lows
        j0 = max(0, i - cfg.stop_lookback_bars)
        struct_low = float(out["low"].iloc[j0 : i + 1].min())
        stop_px = round(struct_low * (1.0 - cfg.stop_buffer_pct / 100.0), 4)
        entry_px = round(cl, 4)
        if stop_px >= entry_px:
            continue
        risk = entry_px - stop_px
        t1 = round(entry_px + cfg.target1_r_mult * risk, 4)
        t2 = round(entry_px + cfg.target2_r_mult * risk, 4)
        t_et = ts.strftime("%H:%M")

        features = {
            "signal_kind": "bb_squeeze_expand",
            "signal_as_of": cand.day.isoformat(),
            "entry_trigger": entry_px,
            "stop_px": stop_px,
            "target1_px": t1,
            "target2_px": t2,
            "atr": round(risk, 4),
            "measured_move_px": round(risk * cfg.target2_r_mult, 4),
            "arm_expiry_bars": 1,
            "max_entry_gap_atr": 0.5,
            "bb_mid": round(mid, 4),
            "bb_width": round(width, 6),
            "bb_width_pctile": round(pct, 4),
            "squeeze_pctile": round(prev_pct, 4),
            "gap_pct": cand.gap_pct,
            "rvol": cand.rvol,
            "horizon": "intraday",
            "construction": "v0.1.1_bb_squeeze_long",
        }
        return Entry(
            ticker=cand.ticker,
            day=cand.day,
            time_et=t_et,
            pattern="bb_squeeze_long",
            entry_px=entry_px,
            bar_close=entry_px,
            reason=(
                f"BB squeeze expand {t_et}: width pctile was {prev_pct:.2f}, "
                f"expand green above mid @ ${entry_px:.2f}; stop ${stop_px:.2f}."
            ),
            strategy="bb_squeeze_long",
            gap_pct=cand.gap_pct,
            rvol=cand.rvol,
            features=features,
        )
    return None


def detect_entry(cand: DayCandidate, cfg: BbSqueezeLongConfig) -> Optional[Entry]:
    df = _rth_5m(cand.ticker, cand.day)
    if df is None:
        return None
    return detect_from_frame(df, cand, cfg)


def simulate_trade(entry: Entry, cfg: BbSqueezeLongConfig) -> Optional[SimTrade]:
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
