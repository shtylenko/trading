"""Breakout → first pullback detection on daily bars.

Lance swing #2 (mechanical subset):
  1. Multi-week consolidation (base) with bounded range
  2. Breakout: close clears base high with volume expansion
  3. First pullback tags the breakout level; close holds above it
  4. Arm buy-stop for a later session (causal prebreak_arm)

No future bars after the plan day are inspected.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars
from trading.marketdata.calendar import trading_days_in_range

from trading.llm_trader.indicators import (
    DAILY_REPLAY_PLAN_LOOKBACK_BARS,
    atr,
    daily_replay_indicators_available,
    enrich_daily_for_replay,
)
from trading.llm_trader.models import Entry

from .config import BreakoutFirstPullbackConfig


class MarketRegimeDataError(RuntimeError):
    """Required causal SPY diagnostics are incomplete."""


def _prep_daily(df: pd.DataFrame, cfg: BreakoutFirstPullbackConfig) -> pd.DataFrame:
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


def _index_date(index_value: Any) -> date:
    return index_value.date() if hasattr(index_value, "date") else pd.Timestamp(index_value).date()


def _passes_trend(row: pd.Series, cfg: BreakoutFirstPullbackConfig) -> bool:
    for col in ("sma50", "sma200", "atr14"):
        if pd.isna(row.get(col)):
            return False
    if cfg.require_above_sma50 and not bool(row.get("above_sma50")):
        return False
    if cfg.require_above_sma200 and not bool(row.get("above_sma200")):
        return False
    if cfg.require_sma50_rising and not bool(row.get("sma50_rising")):
        return False
    return True


def _replay_window_ok(frame: pd.DataFrame, plan_i: int) -> bool:
    stream_start = max(0, plan_i - DAILY_REPLAY_PLAN_LOOKBACK_BARS)
    return daily_replay_indicators_available(frame.iloc[stream_start : plan_i + 1])


def fetch_market_regime_features(cfg: BreakoutFirstPullbackConfig) -> dict[date, dict[str, Any]]:
    warmup_days = 420
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup_days
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    spy = fetch_bars("SPY", "1day", start=start, end=end, adjustment="raw")
    if spy is None or spy.empty:
        raise MarketRegimeDataError("SPY daily bars unavailable")
    prepared = _prep_daily(spy, cfg)
    records: dict[date, dict[str, Any]] = {}
    for ts, row in prepared.iterrows():
        as_of = _index_date(ts)
        if as_of < cfg.start or as_of > cfg.end:
            continue
        if any(pd.isna(row.get(f)) for f in ("close", "sma50", "sma200")):
            continue
        above50 = bool(row["close"] > row["sma50"])
        above200 = bool(row["close"] > row["sma200"])
        records[as_of] = {
            "schema_version": 1,
            "as_of": as_of.isoformat(),
            "close": round(float(row["close"]), 4),
            "sma50": round(float(row["sma50"]), 4),
            "sma200": round(float(row["sma200"]), 4),
            "above_sma50": above50,
            "above_sma200": above200,
            "sma50_rising": bool(row.get("sma50_rising")),
        }
    expected = trading_days_in_range(cfg.start, cfg.end)
    missing = [d for d in expected if d not in records]
    if missing:
        preview = ", ".join(d.isoformat() for d in missing[:5])
        raise MarketRegimeDataError(f"incomplete SPY regime dates: {preview}")
    if not records:
        raise MarketRegimeDataError("no SPY regime records in range")
    return records


def _find_base_and_breakout(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
    volume: np.ndarray,
    vol_avg: np.ndarray,
    end_i: int,
    cfg: BreakoutFirstPullbackConfig,
) -> Optional[dict[str, float | int]]:
    """Find a base ending just before a breakout at ``breakout_i`` ≤ end_i.

    We search for breakout bars in a window before ``end_i`` such that the
    first pullback can complete by ``end_i``.
    """
    # breakout must leave room for pullback
    earliest_bo = cfg.base_min_bars + 5
    latest_bo = end_i - cfg.min_bars_after_breakout
    if latest_bo < earliest_bo:
        return None

    # Prefer the most recent valid breakout that has not yet had a completed
    # first-pullback arm earlier (caller enforces cooldown). Scan backward.
    for bo_i in range(latest_bo, max(earliest_bo, end_i - cfg.max_bars_to_first_pullback) - 1, -1):
        base_end = bo_i - 1
        # try several base lengths ending at base_end
        for base_len in range(cfg.base_min_bars, cfg.base_max_bars + 1):
            base_start = base_end - base_len + 1
            if base_start < 0:
                break
            bh = float(np.max(high[base_start : base_end + 1]))
            bl = float(np.min(low[base_start : base_end + 1]))
            if not np.isfinite(bh) or not np.isfinite(bl) or bh <= 0:
                continue
            range_pct = (bh - bl) / bh * 100.0
            if not (cfg.base_range_min_pct <= range_pct <= cfg.base_range_max_pct):
                continue
            # Breakout day clears base high
            bo_close = float(close[bo_i])
            bo_high = float(high[bo_i])
            bo_open = float(open_[bo_i])
            clear = bh * (1.0 + cfg.breakout_clear_pct / 100.0)
            if bo_close < clear or bo_high < bh:
                continue
            if cfg.require_green_breakout and bo_close <= bo_open:
                continue
            va = float(vol_avg[bo_i]) if np.isfinite(vol_avg[bo_i]) else np.nan
            if not np.isfinite(va) or va <= 0:
                continue
            vol_mult = float(volume[bo_i]) / va
            if vol_mult < cfg.breakout_vol_mult:
                continue
            # After breakout, until end_i: first pullback should not have already
            # completed too early with a prior arm — we only care geometry at end_i
            bars_after = end_i - bo_i
            if bars_after < cfg.min_bars_after_breakout:
                continue
            if bars_after > cfg.max_bars_to_first_pullback:
                continue
            return {
                "base_start_i": base_start,
                "base_end_i": base_end,
                "breakout_i": bo_i,
                "base_high": bh,
                "base_low": bl,
                "base_range_pct": range_pct,
                "base_height_px": bh - bl,
                "breakout_close": bo_close,
                "breakout_vol_mult": vol_mult,
            }
    return None


def _find_first_pullback_setup(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    plan_i: int,
    bo: dict[str, float | int],
    cfg: BreakoutFirstPullbackConfig,
) -> Optional[dict[str, float | int]]:
    """Validate that ``plan_i`` is the first reclaim after tagging breakout level."""
    bo_i = int(bo["breakout_i"])
    breakout_level = float(bo["base_high"])
    if plan_i <= bo_i:
        return None

    # Post-breakout swing high (from breakout through plan day)
    post = high[bo_i : plan_i + 1]
    swing_high = float(np.max(post))
    swing_high_i = bo_i + int(np.argmax(post))
    if swing_high <= breakout_level:
        return None

    # Must have tagged breakout level in (bo_i, plan_i]
    tol = cfg.retest_tol_pct / 100.0
    tag_indices = []
    for j in range(bo_i + 1, plan_i + 1):
        if float(low[j]) <= breakout_level * (1.0 + tol):
            tag_indices.append(j)
    if not tag_indices:
        return None

    first_tag = tag_indices[0]
    c = float(close[plan_i])
    if cfg.require_close_above_breakout and c < breakout_level:
        return None
    ext = (c / breakout_level - 1.0) * 100.0
    if ext > cfg.max_extension_above_breakout_pct:
        return None

    pl_slice = low[first_tag : plan_i + 1]
    pullback_low_i = first_tag + int(np.argmin(pl_slice))
    pullback_low = float(low[pullback_low_i])
    if pullback_low <= 0 or pullback_low >= swing_high:
        return None

    depth_pct = (swing_high - pullback_low) / swing_high * 100.0
    if not (cfg.pullback_depth_min_pct <= depth_pct <= cfg.pullback_depth_max_pct):
        return None

    for j in range(bo_i + 1, first_tag):
        if float(low[j]) <= breakout_level * (1.0 + tol):
            return None

    # Volume dry-up on the tag day vs breakout day (structural quality)
    if cfg.require_pullback_vol_below_breakout:
        bo_vol = float(volume[bo_i])
        tag_vol = float(volume[first_tag])
        if not (np.isfinite(bo_vol) and np.isfinite(tag_vol) and bo_vol > 0):
            return None
        if tag_vol >= bo_vol:
            return None

    setup_high = float(high[plan_i])
    if setup_high <= pullback_low:
        return None

    return {
        **bo,
        "plan_i": plan_i,
        "first_tag_i": first_tag,
        "pullback_low_i": pullback_low_i,
        "swing_high_i": swing_high_i,
        "breakout_level": breakout_level,
        "swing_high": swing_high,
        "pullback_low": pullback_low,
        "depth_pct": depth_pct,
        "extension_pct": ext,
        "setup_high": setup_high,
        "bars_after_breakout": plan_i - bo_i,
        "tag_vol": float(volume[first_tag]),
        "breakout_vol": float(volume[bo_i]),
    }


def _entry_from_geometry(
    *,
    ticker: str,
    day: date,
    row: pd.Series,
    geom: dict[str, float | int],
    cfg: BreakoutFirstPullbackConfig,
    strategy_id: str,
    market_regime: Optional[dict[str, Any]] = None,
) -> Optional[Entry]:
    atr_px = float(row["atr14"])
    if atr_px <= 0 or pd.isna(atr_px):
        return None

    breakout_level = float(geom["breakout_level"])
    if cfg.entry_trigger_mode == "breakout_level":
        trigger = round(breakout_level, 4)
    else:
        trigger = round(float(geom["setup_high"]), 4)

    pullback_low = float(geom["pullback_low"])
    stop_px = round(pullback_low - cfg.stop_buffer_atr * atr_px, 4)
    if stop_px >= trigger:
        return None

    swing_high = float(geom["swing_high"])
    base_height = float(geom["base_height_px"])
    # T1: retest of post-breakout swing high (or just above trigger)
    t1 = round(max(swing_high, trigger + 0.25 * atr_px), 4)
    t2 = round(t1 + cfg.measured_move_frac * base_height, 4)
    if t1 <= trigger or t2 <= t1:
        return None

    stop_dist = round(trigger - stop_px, 4)
    features: dict[str, Any] = {
        "signal_kind": "prebreak_arm",
        "signal_as_of": day.isoformat(),
        "entry_trigger": trigger,
        "entry_trigger_mode": cfg.entry_trigger_mode,
        "arm_expiry_bars": cfg.arm_expiry_bars,
        "max_entry_gap_atr": cfg.max_entry_gap_atr,
        "atr": round(atr_px, 4),
        "stop_buffer_atr": cfg.stop_buffer_atr,
        "stop_distance": stop_dist,
        "stop_px": stop_px,
        "target1_px": t1,
        "target2_px": t2,
        "measured_move_px": round(base_height, 4),
        "breakout_level": round(breakout_level, 4),
        "base_high": round(float(geom["base_high"]), 4),
        "base_low": round(float(geom["base_low"]), 4),
        "base_range_pct": round(float(geom["base_range_pct"]), 2),
        "base_height_px": round(base_height, 4),
        "breakout_vol_mult": round(float(geom["breakout_vol_mult"]), 2),
        "swing_high": round(swing_high, 4),
        "pullback_low": round(pullback_low, 4),
        "pullback_depth_pct": round(float(geom["depth_pct"]), 2),
        "extension_pct": round(float(geom["extension_pct"]), 2),
        "bars_after_breakout": int(geom["bars_after_breakout"]),
        "construction": (
            f"v0.2.0_{cfg.entry_trigger_mode}_sma200_"
            f"vol{cfg.breakout_vol_mult:g}"
        ),
        "horizon": "multi_day",
        "sma50": round(float(row["sma50"]), 4) if pd.notna(row.get("sma50")) else None,
        "sma200": round(float(row["sma200"]), 4) if pd.notna(row.get("sma200")) else None,
        "bar_vol_mult": (
            round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None
        ),
    }
    if market_regime is not None:
        features["market_regime"] = dict(market_regime)

    reason = (
        f"Breakout first-pullback arm on {day.isoformat()}: base high "
        f"${breakout_level:.2f} retested and held; trigger ${trigger:.2f}; "
        f"stop ${stop_px:.2f}; T1 ${t1:.2f} / T2 ${t2:.2f}."
    )
    return Entry(
        ticker=ticker.upper(),
        day=day,
        time_et="16:00",
        pattern="breakout_first_pullback",
        entry_px=trigger,
        bar_close=round(float(row["close"]), 4),
        reason=reason,
        strategy=strategy_id,
        rvol=round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None,
        bar_vol_mult=features["bar_vol_mult"],
        features=features,
    )


def detect_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: BreakoutFirstPullbackConfig,
    *,
    strategy_id: str = "breakout_first_pullback",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    min_len = cfg.base_min_bars + cfg.max_bars_to_first_pullback + 30
    if df is None or df.empty or len(df) < min_len:
        return []

    frame = _prep_daily(df, cfg)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    vol_avg = frame["vol_avg20"].to_numpy(dtype=float)

    out: list[Entry] = []
    last_arm_i: Optional[int] = None
    seen_breakouts: set[int] = set()
    start_i = cfg.base_min_bars + cfg.min_bars_after_breakout + 10

    for plan_i in range(start_i, len(frame)):
        d = _index_date(frame.index[plan_i])
        if d < cfg.start or d > cfg.end:
            continue
        if eligible_plan_dates is not None and d not in eligible_plan_dates:
            continue
        if cfg.require_spy_above_sma50 or cfg.require_spy_above_sma200:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates required")
            if d not in market_ok_dates:
                continue
        if last_arm_i is not None and plan_i - last_arm_i <= cfg.min_bars_between_arms:
            continue

        row = frame.iloc[plan_i]
        if not _replay_window_ok(frame, plan_i):
            continue
        c = float(row["close"])
        avg_vol = row.get("vol_avg20")
        if not (cfg.price_min <= c <= cfg.price_max):
            continue
        if pd.isna(avg_vol) or float(avg_vol) < cfg.avg_vol_min:
            continue
        if not _passes_trend(row, cfg):
            continue

        bo = _find_base_and_breakout(
            high, low, close, open_, volume, vol_avg, plan_i, cfg
        )
        if bo is None:
            continue
        bo_i = int(bo["breakout_i"])
        if bo_i in seen_breakouts:
            continue

        geom = _find_first_pullback_setup(high, low, close, volume, plan_i, bo, cfg)
        if geom is None:
            continue

        regime = None
        if market_regime_features is not None:
            rec = market_regime_features.get(d)
            if rec is not None:
                regime = dict(rec)

        entry = _entry_from_geometry(
            ticker=ticker,
            day=d,
            row=row,
            geom=geom,
            cfg=cfg,
            strategy_id=strategy_id,
            market_regime=regime,
        )
        if entry is None:
            continue
        out.append(entry)
        seen_breakouts.add(bo_i)
        last_arm_i = plan_i
    return out


def detect_ticker(
    ticker: str,
    cfg: BreakoutFirstPullbackConfig,
    *,
    strategy_id: str = "breakout_first_pullback",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    warmup_days = 420
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup_days
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty:
        return []
    return detect_from_frame(
        df,
        ticker,
        cfg,
        strategy_id=strategy_id,
        market_ok_dates=market_ok_dates,
        market_regime_features=market_regime_features,
        eligible_plan_dates=eligible_plan_dates,
    )
