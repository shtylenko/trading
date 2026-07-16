"""Cup-and-handle detection on daily bars (pure + fetch wrapper).

Objectified Davidson checklist (mechanical subset):
  1. Strong uptrend — price above SMA20/50/200; SMA50 rising or stacked
  2. Healthy cup — depth band, multi-bar trough, lips aligned
  3. Tight handle — short, shallow vs cup, lighter volume
  4. Room to run — simplified resistance check
  5. Breakout — first bar that clears handle high with volume

Entry plan fields (ATR stop, T1/T2) are attached on the breakout bar.

Algorithm is O(n): for each candidate breakout bar, fix handle length band
and locate the cup low / lips in a single backward window (no nested
cup_len × handle_len grid search).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.indicators import atr, enrich_daily_for_replay
from trading.llm_trader.models import Entry

from .config import CupHandleConfig


@dataclass
class CupGeometry:
    left_lip_i: int
    cup_low_i: int
    right_lip_i: int
    handle_start_i: int
    handle_end_i: int
    left_lip_px: float
    cup_low_px: float
    right_lip_px: float
    handle_high: float
    handle_low: float
    cup_depth_pct: float
    cup_depth_px: float
    handle_depth_px: float


def _prep_daily(df: pd.DataFrame, cfg: CupHandleConfig) -> pd.DataFrame:
    out = df.sort_index().copy()
    if out.index.tz is not None:
        out.index = out.index.tz_convert("America/New_York")
    out = enrich_daily_for_replay(out)
    if cfg.atr_period != 14:
        out["atr14"] = atr(out, cfg.atr_period)
    return out


def _passes_trend(row: pd.Series, cfg: CupHandleConfig) -> bool:
    for col in ("sma20", "sma50", "sma200", "atr14"):
        if pd.isna(row.get(col)):
            return False
    if cfg.require_above_sma20 and not bool(row.get("above_sma20")):
        return False
    if cfg.require_above_sma50 and not bool(row.get("above_sma50")):
        return False
    if cfg.require_above_sma200 and not bool(row.get("above_sma200")):
        return False
    if cfg.require_sma50_rising:
        rising = bool(row.get("sma50_rising"))
        stacked = float(row["sma50"]) >= float(row["sma200"]) * 0.995
        if not (rising or stacked):
            return False
    return True


def _find_cup_and_handle(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    end_i: int,
    cfg: CupHandleConfig,
) -> Optional[CupGeometry]:
    """Locate cup+handle ending at ``end_i`` (last handle bar), using numpy arrays.

    For each allowed handle length, take the cup window immediately before it
    (cup_min..cup_max bars) and score geometry — first match wins (prefer
    shorter handles, then mid cup lengths).
    """
    if end_i < cfg.cup_min_bars + cfg.handle_min_bars + 5:
        return None

    for handle_len in range(cfg.handle_min_bars, cfg.handle_max_bars + 1):
        handle_start = end_i - handle_len + 1
        if handle_start < cfg.cup_min_bars:
            continue

        handle_high = float(high[handle_start : end_i + 1].max())
        handle_low = float(low[handle_start : end_i + 1].min())
        handle_depth_px = handle_high - handle_low
        if handle_depth_px <= 0:
            continue
        handle_vol = float(volume[handle_start : end_i + 1].mean())

        # Prefer cup lengths near the middle of the allowed range first for speed
        cup_lens = list(range(cfg.cup_min_bars, cfg.cup_max_bars + 1))
        # try longer cups first (more classic) but cap iterations
        for cup_len in cup_lens:
            cup_start = handle_start - cup_len
            if cup_start < 0:
                break

            cup_high = high[cup_start:handle_start]
            cup_low_arr = low[cup_start:handle_start]
            cup_vol_arr = volume[cup_start:handle_start]
            if len(cup_high) < cfg.cup_min_bars:
                continue

            third = max(1, len(cup_high) // 3)
            left_rel = int(np.argmax(cup_high[:third]))
            right_rel = len(cup_high) - third + int(np.argmax(cup_high[-third:]))
            left_lip_i = cup_start + left_rel
            right_lip_i = cup_start + right_rel
            left_lip_px = float(high[left_lip_i])
            right_lip_px = float(high[right_lip_i])
            if left_lip_px <= 0:
                continue

            lip_ref = min(left_lip_px, right_lip_px)
            lip_diff_pct = abs(right_lip_px - left_lip_px) / left_lip_px * 100.0
            if lip_diff_pct > cfg.lip_tolerance_pct:
                continue

            # trough between lips
            lo0 = min(left_lip_i, right_lip_i)
            lo1 = max(left_lip_i, right_lip_i)
            if lo1 <= lo0:
                continue
            trough_slice = low[lo0 : lo1 + 1]
            cup_low_i = lo0 + int(np.argmin(trough_slice))
            cup_low_px = float(low[cup_low_i])
            if cup_low_px <= 0 or cup_low_px >= lip_ref:
                continue

            cup_depth_px = lip_ref - cup_low_px
            cup_depth_pct = cup_depth_px / lip_ref * 100.0
            if not (cfg.cup_depth_min_pct <= cup_depth_pct <= cfg.cup_depth_max_pct):
                continue

            # roundedness: ≥2 bars within 3% of trough low
            near = trough_slice[trough_slice <= cup_low_px * 1.03]
            if len(near) < 2:
                continue

            if handle_depth_px > cfg.handle_depth_max_frac * cup_depth_px:
                continue

            # handle under the lips
            if handle_high > max(left_lip_px, right_lip_px) * 1.01:
                continue

            cup_vol = float(cup_vol_arr.mean())
            if cup_vol > 0 and handle_vol > cfg.handle_vol_frac_max * cup_vol:
                continue

            return CupGeometry(
                left_lip_i=left_lip_i,
                cup_low_i=cup_low_i,
                right_lip_i=right_lip_i,
                handle_start_i=handle_start,
                handle_end_i=end_i,
                left_lip_px=round(left_lip_px, 4),
                cup_low_px=round(cup_low_px, 4),
                right_lip_px=round(right_lip_px, 4),
                handle_high=round(handle_high, 4),
                handle_low=round(handle_low, 4),
                cup_depth_pct=round(cup_depth_pct, 2),
                cup_depth_px=round(cup_depth_px, 4),
                handle_depth_px=round(handle_depth_px, 4),
            )
    return None


def _room_to_run(
    high: np.ndarray,
    breakout_i: int,
    handle_high: float,
    cup_depth_px: float,
) -> bool:
    """True unless a prior swing high sits in a tight band just *above* the breakout.

    Structure at/near the handle high (lips within ~2%) is expected. Block only
    when there is stacked supply overhead inside half a measured move.
    """
    start = max(0, breakout_i - 60)
    if start >= breakout_i:
        return True
    ceiling = float(high[start:breakout_i].max())
    if ceiling > handle_high * 1.02 and (ceiling - handle_high) < 0.5 * cup_depth_px:
        return False
    return True


def detect_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
) -> list[Entry]:
    """Detect cup-and-handle breakout entries over a daily frame (pure, no I/O)."""
    min_len = cfg.cup_min_bars + cfg.handle_min_bars + cfg.atr_period + 5
    if df is None or df.empty or len(df) < min_len:
        return []

    frame = _prep_daily(df, cfg)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    opens = frame["open"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)

    out: list[Entry] = []
    seen_days: set[date] = set()
    start_i = cfg.cup_min_bars + cfg.handle_min_bars + 5

    for bi in range(start_i, len(frame)):
        ts = frame.index[bi]
        d = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        if d < cfg.start or d > cfg.end or d in seen_days:
            continue

        row = frame.iloc[bi]
        close = float(closes[bi])
        if not (cfg.price_min <= close <= cfg.price_max):
            continue
        avg_vol = row.get("vol_avg20")
        if pd.isna(avg_vol) or float(avg_vol) < cfg.avg_vol_min:
            continue
        if not _passes_trend(row, cfg):
            continue

        geom = _find_cup_and_handle(high, low, volume, bi - 1, cfg)
        if geom is None:
            continue

        hi = float(high[bi])
        if hi <= geom.handle_high:
            continue
        if cfg.require_green_breakout and close <= float(opens[bi]):
            continue

        vol_mult = None
        if pd.notna(avg_vol) and float(avg_vol) > 0:
            vol_mult = float(volume[bi]) / float(avg_vol)
        if cfg.require_breakout_volume and (vol_mult is None or vol_mult < cfg.breakout_vol_mult):
            continue

        if not _room_to_run(high, bi, geom.handle_high, geom.cup_depth_px):
            continue

        atr_px = float(row["atr14"])
        if atr_px <= 0 or pd.isna(atr_px):
            continue

        entry_px = round(geom.handle_high, 4)
        stop_dist = round(cfg.stop_atr_mult * atr_px, 4)
        stop_px = round(entry_px - stop_dist, 4)
        measured = geom.cup_depth_px
        t1 = round(entry_px + cfg.target1_cup_frac * measured, 4)
        t2 = round(entry_px + cfg.target2_cup_frac * measured, 4)

        features: dict[str, Any] = {
            "atr": round(atr_px, 4),
            "stop_atr_mult": cfg.stop_atr_mult,
            "stop_distance": stop_dist,
            "stop_px": stop_px,
            "target1_px": t1,
            "target2_px": t2,
            "cup_depth_px": geom.cup_depth_px,
            "cup_depth_pct": geom.cup_depth_pct,
            "handle_high": geom.handle_high,
            "handle_low": geom.handle_low,
            "left_lip_px": geom.left_lip_px,
            "right_lip_px": geom.right_lip_px,
            "cup_low_px": geom.cup_low_px,
            "sma20": round(float(row["sma20"]), 4),
            "sma50": round(float(row["sma50"]), 4),
            "sma200": round(float(row["sma200"]), 4),
            "bar_vol_mult": round(vol_mult, 2) if vol_mult is not None else None,
            "plan_date": d.isoformat(),
            "horizon": "multi_day",
        }

        reason = (
            f"Cup-and-handle breakout: cleared handle high ${entry_px:.2f} "
            f"(cup depth {geom.cup_depth_pct:.1f}% / ${geom.cup_depth_px:.2f}); "
            f"ATR stop ${stop_px:.2f} ({cfg.stop_atr_mult}×ATR=${stop_dist:.2f}); "
            f"T1 ${t1:.2f} / T2 ${t2:.2f}"
            + (f"; breakout vol {vol_mult:.1f}×" if vol_mult is not None else "")
            + "."
        )

        out.append(
            Entry(
                ticker=ticker.upper(),
                day=d,
                time_et="09:30",
                pattern="cup_handle",
                entry_px=entry_px,
                bar_close=round(close, 4),
                reason=reason,
                strategy=strategy_id,
                rvol=round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None,
                bar_vol_mult=round(vol_mult, 2) if vol_mult is not None else None,
                features=features,
            )
        )
        seen_days.add(d)

    return out


def detect_ticker(
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
) -> list[Entry]:
    """Fetch daily bars and detect entries for one ticker."""
    warmup = max(220, cfg.cup_max_bars + cfg.handle_max_bars + cfg.atr_period + 40)
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=int(warmup * 1.7)
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty:
        return []
    return detect_from_frame(df, ticker, cfg, strategy_id=strategy_id)
