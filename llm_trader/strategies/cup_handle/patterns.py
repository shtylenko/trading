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
    out = enrich_daily_for_replay(
        out,
        volume_lookback=cfg.rvol_lookback,
        sma50_rising_lookback=cfg.sma50_rising_lookback,
    )
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
        if not bool(row.get("sma50_rising")):
            return False
    return True


def _index_date(index_value: Any) -> date:
    return index_value.date() if hasattr(index_value, "date") else pd.Timestamp(index_value).date()


def fetch_market_regime(cfg: CupHandleConfig) -> set[date]:
    """Return dates on which SPY closed above its SMA50 for this scan window.

    This is deliberately a separate, explicit fetch.  A regime option that cannot
    be evaluated must not silently become a no-op.
    """
    warmup_days = 150
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup_days
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    spy = fetch_bars("SPY", "1day", start=start, end=end, adjustment="raw")
    if spy is None or spy.empty:
        raise RuntimeError("SPY regime filter is enabled but no SPY daily bars are available")
    prepared = _prep_daily(spy, cfg)
    return {
        _index_date(ts)
        for ts, row in prepared.iterrows()
        if pd.notna(row.get("sma50")) and bool(row.get("above_sma50"))
    }


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


def _entry_from_geometry(
    *,
    ticker: str,
    day: date,
    row: pd.Series,
    geom: CupGeometry,
    cfg: CupHandleConfig,
    strategy_id: str,
    signal_kind: str,
    time_et: str,
) -> Optional[Entry]:
    """Build a fully specified plan using only data through ``day``."""
    atr_px = float(row["atr14"])
    if atr_px <= 0 or pd.isna(atr_px):
        return None

    trigger = round(geom.handle_high, 4)
    stop_dist = round(cfg.stop_atr_mult * atr_px, 4)
    stop_px = round(trigger - stop_dist, 4)
    measured = geom.cup_depth_px
    t1 = round(trigger + cfg.target1_cup_frac * measured, 4)
    t2 = round(trigger + cfg.target2_cup_frac * measured, 4)
    formation_key = "|".join(
        str(i)
        for i in (geom.left_lip_i, geom.cup_low_i, geom.right_lip_i)
    )
    features: dict[str, Any] = {
        "signal_kind": signal_kind,
        "signal_as_of": day.isoformat(),
        "entry_trigger": trigger,
        "arm_expiry_bars": cfg.arm_expiry_bars,
        "max_entry_gap_atr": cfg.max_entry_gap_atr,
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
        "formation_key": formation_key,
        "sma20": round(float(row["sma20"]), 4),
        "sma50": round(float(row["sma50"]), 4),
        "sma200": round(float(row["sma200"]), 4),
        "bar_vol_mult": (
            round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None
        ),
        "horizon": "multi_day",
    }
    if signal_kind == "prebreak_arm":
        reason = (
            f"Cup-and-handle arm: trigger ${trigger:.2f} after the {day.isoformat()} close "
            f"(cup depth {geom.cup_depth_pct:.1f}% / ${geom.cup_depth_px:.2f}); "
            f"stop ${stop_px:.2f} ({cfg.stop_atr_mult}×ATR=${stop_dist:.2f}); "
            f"T1 ${t1:.2f} / T2 ${t2:.2f}."
        )
    else:
        reason = (
            f"Cup-and-handle confirmed breakout: cleared ${trigger:.2f} "
            f"(cup depth {geom.cup_depth_pct:.1f}% / ${geom.cup_depth_px:.2f}); "
            f"next-session plan stop ${stop_px:.2f}; T1 ${t1:.2f} / T2 ${t2:.2f}."
        )
    return Entry(
        ticker=ticker.upper(),
        day=day,
        time_et=time_et,
        pattern="cup_handle",
        # Entry is a trigger/plan level, not a claim of a same-bar fill.
        entry_px=trigger,
        bar_close=round(float(row["close"]), 4),
        reason=reason,
        strategy=strategy_id,
        rvol=round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None,
        bar_vol_mult=(
            round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None
        ),
        features=features,
    )


def _detect_confirmed_breakouts_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
    market_ok_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Historical confirmation labels, retained for offline analysis only.

    A label is emitted only after the breakout bar has closed.  It is intentionally
    not the default scanner mode because it cannot justify a same-day fill.
    """
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
        d = _index_date(ts)
        if d < cfg.start or d > cfg.end or d in seen_days:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates are required when require_spy_above_sma50=True")
            if d not in market_ok_dates:
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

        entry = _entry_from_geometry(
            ticker=ticker,
            day=d,
            row=row,
            geom=geom,
            cfg=cfg,
            strategy_id=strategy_id,
            signal_kind="confirmed_breakout",
            time_et="16:00",
        )
        if entry is None:
            continue
        # This outcome is a post-close research label.  Preserve the observed
        # confirmation facts for diagnostics, but never imply a 09:30 fill.
        entry.features["breakout_vol_mult"] = round(vol_mult, 2) if vol_mult is not None else None
        entry.features["breakout_close_above_trigger"] = close > entry.entry_px
        out.append(entry)
        seen_days.add(d)

    return out


def _detect_prebreak_arms_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
    market_ok_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Emit causal end-of-day plans for a completed cup-and-handle.

    The buy-stop is not active until a later session.  No breakout-day close,
    volume, or high is inspected to decide whether to publish the plan.
    """
    min_len = cfg.cup_min_bars + cfg.handle_min_bars + cfg.atr_period + 5
    if df is None or df.empty or len(df) < min_len:
        return []

    frame = _prep_daily(df, cfg)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    out: list[Entry] = []
    seen_formations: set[str] = set()
    last_arm_i: Optional[int] = None
    start_i = cfg.cup_min_bars + cfg.handle_min_bars + 5

    for plan_i in range(start_i, len(frame)):
        d = _index_date(frame.index[plan_i])
        if d < cfg.start or d > cfg.end:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates are required when require_spy_above_sma50=True")
            if d not in market_ok_dates:
                continue
        if last_arm_i is not None and plan_i - last_arm_i <= cfg.arm_expiry_bars:
            continue

        row = frame.iloc[plan_i]
        close = float(row["close"])
        avg_vol = row.get("vol_avg20")
        if not (cfg.price_min <= close <= cfg.price_max):
            continue
        if pd.isna(avg_vol) or float(avg_vol) < cfg.avg_vol_min:
            continue
        if not _passes_trend(row, cfg):
            continue

        geom = _find_cup_and_handle(high, low, volume, plan_i, cfg)
        if geom is None:
            continue
        if not _room_to_run(high, plan_i + 1, geom.handle_high, geom.cup_depth_px):
            continue

        formation_key = "|".join(
            str(i) for i in (geom.left_lip_i, geom.cup_low_i, geom.right_lip_i)
        )
        if formation_key in seen_formations:
            continue
        entry = _entry_from_geometry(
            ticker=ticker,
            day=d,
            row=row,
            geom=geom,
            cfg=cfg,
            strategy_id=strategy_id,
            signal_kind="prebreak_arm",
            time_et="16:00",
        )
        if entry is None:
            continue
        out.append(entry)
        seen_formations.add(formation_key)
        last_arm_i = plan_i
    return out


def detect_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
    market_ok_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Detect the configured cup-and-handle signal type over a daily frame.

    ``prebreak_arm`` is the production default.  ``confirmed_breakout`` exists
    for post-event research labels and produces a next-session plan, never a
    same-day execution claim.
    """
    cfg.validate()
    if cfg.signal_mode == "prebreak_arm":
        return _detect_prebreak_arms_from_frame(
            df, ticker, cfg, strategy_id=strategy_id, market_ok_dates=market_ok_dates
        )
    return _detect_confirmed_breakouts_from_frame(
        df, ticker, cfg, strategy_id=strategy_id, market_ok_dates=market_ok_dates
    )


def detect_ticker(
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
    market_ok_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Fetch daily bars and detect entries for one ticker."""
    cfg.validate()
    warmup = max(220, cfg.cup_max_bars + cfg.handle_max_bars + cfg.atr_period + 40)
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=int(warmup * 1.7)
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty:
        return []
    if cfg.require_spy_above_sma50 and market_ok_dates is None:
        market_ok_dates = fetch_market_regime(cfg)
    return detect_from_frame(
        df, ticker, cfg, strategy_id=strategy_id, market_ok_dates=market_ok_dates
    )
