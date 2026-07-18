"""Right-side-of-V detection: selloff then confirmed reclaim (not knife-catch).

Lance: same price ≠ same EV. Left side of V (falling knife) is terrible EV.
Right side (turn confirmed) has trend + structure with defined risk under pivot.
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

from .config import RightSideVConfig


class MarketRegimeDataError(RuntimeError):
    pass


def _prep_daily(df: pd.DataFrame, cfg: RightSideVConfig) -> pd.DataFrame:
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


def _index_date(v: Any) -> date:
    return v.date() if hasattr(v, "date") else pd.Timestamp(v).date()


def _replay_ok(frame: pd.DataFrame, plan_i: int) -> bool:
    s = max(0, plan_i - DAILY_REPLAY_PLAN_LOOKBACK_BARS)
    return daily_replay_indicators_available(frame.iloc[s : plan_i + 1])


def fetch_market_regime_features(cfg: RightSideVConfig) -> dict[date, dict[str, Any]]:
    warmup = 420
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    spy = fetch_bars("SPY", "1day", start=start, end=end, adjustment="raw")
    if spy is None or spy.empty:
        raise MarketRegimeDataError("SPY bars unavailable")
    prepared = _prep_daily(spy, cfg)
    records: dict[date, dict[str, Any]] = {}
    for ts, row in prepared.iterrows():
        d = _index_date(ts)
        if d < cfg.start or d > cfg.end:
            continue
        if pd.isna(row.get("sma50")) or pd.isna(row.get("close")):
            continue
        records[d] = {
            "schema_version": 1,
            "as_of": d.isoformat(),
            "close": round(float(row["close"]), 4),
            "sma50": round(float(row["sma50"]), 4),
            "above_sma50": bool(row["close"] > row["sma50"]),
        }
    missing = [d for d in trading_days_in_range(cfg.start, cfg.end) if d not in records]
    if missing:
        raise MarketRegimeDataError(
            "incomplete SPY regime: " + ", ".join(x.isoformat() for x in missing[:5])
        )
    return records


def _find_v_geometry(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    sma20: np.ndarray,
    plan_i: int,
    cfg: RightSideVConfig,
) -> Optional[dict[str, float | int]]:
    """If plan_i is a right-side reclaim after a qualifying drop, return geometry."""
    if plan_i < cfg.drop_lookback_max + 5:
        return None

    c = float(close[plan_i])
    if not np.isfinite(c):
        return None

    # Search for pivot low ending at plan_i-1 or plan_i (pivot on or before setup)
    # Setup day is reclaim: close rising from a recent pivot.
    best: Optional[dict[str, float | int]] = None

    for pivot_i in range(plan_i - 1, plan_i - cfg.drop_lookback_max - 1, -1):
        if pivot_i < cfg.drop_lookback_min:
            break
        pivot_low = float(low[pivot_i])
        if not np.isfinite(pivot_low) or pivot_low <= 0:
            continue
        # Local pivot: low is min of neighborhood
        left = max(0, pivot_i - 2)
        right = min(len(low) - 1, pivot_i + 2)
        if pivot_low > float(np.min(low[left : right + 1])) + 1e-9:
            continue

        # Swing high: max high in [pivot_i - drop_lookback_max, pivot_i)
        hs = max(0, pivot_i - cfg.drop_lookback_max)
        he = pivot_i  # exclusive of pivot bar for peak search before drop ends
        if he - hs < cfg.drop_lookback_min:
            continue
        peak_slice = high[hs:he]
        if peak_slice.size == 0:
            continue
        peak_off = int(np.argmax(peak_slice))
        peak_i = hs + peak_off
        swing_high = float(high[peak_i])
        if swing_high <= pivot_low:
            continue
        drop_bars = pivot_i - peak_i
        if drop_bars < cfg.drop_lookback_min or drop_bars > cfg.drop_lookback_max:
            continue
        drop_pct = (swing_high - pivot_low) / swing_high * 100.0
        if not (cfg.drop_min_pct <= drop_pct <= cfg.drop_max_pct):
            continue

        # Bars after pivot until plan_i: right side forming
        if plan_i <= pivot_i:
            continue
        if plan_i - pivot_i > 8:  # reclaim should not be too delayed for "V"
            continue

        # --- RIGHT SIDE CONFIRMATION (not left-side catch) ---
        # 1) Close above SMA20
        s20 = float(sma20[plan_i])
        if cfg.require_close_above_sma20:
            if not np.isfinite(s20) or c < s20:
                continue
            ext = (c / s20 - 1.0) * 100.0
            if ext > cfg.max_extension_above_sma20_pct:
                continue

        # 2) Minimum retrace from pivot toward swing high
        retrace_level = pivot_low + cfg.min_retrace_frac * (swing_high - pivot_low)
        if c < retrace_level:
            continue

        # 3) Turn day: close above prior day high (structure flipping)
        if cfg.require_close_above_prior_high:
            if plan_i < 1:
                continue
            if c <= float(high[plan_i - 1]):
                continue

        # 4) Close above pivot (obvious)
        if c <= pivot_low:
            continue

        # Prefer the most recent qualifying pivot (first found scanning back)
        setup_high = float(high[plan_i])
        best = {
            "peak_i": peak_i,
            "pivot_i": pivot_i,
            "swing_high": swing_high,
            "pivot_low": pivot_low,
            "drop_pct": drop_pct,
            "drop_bars": drop_bars,
            "drop_px": swing_high - pivot_low,
            "retrace_level": retrace_level,
            "sma20": s20,
            "setup_high": setup_high,
            "setup_close": c,
            "extension_pct": (c / s20 - 1.0) * 100.0 if np.isfinite(s20) and s20 > 0 else 0.0,
        }
        break

    return best


def _entry_from_geometry(
    *,
    ticker: str,
    day: date,
    row: pd.Series,
    geom: dict[str, float | int],
    cfg: RightSideVConfig,
    strategy_id: str,
    market_regime: Optional[dict[str, Any]] = None,
) -> Optional[Entry]:
    atr_px = float(row["atr14"])
    if atr_px <= 0 or pd.isna(atr_px):
        return None

    if cfg.entry_trigger_mode == "reclaim_close":
        trigger = round(float(geom["setup_close"]), 4)
    else:
        trigger = round(float(geom["setup_high"]), 4)

    pivot_low = float(geom["pivot_low"])
    stop_px = round(pivot_low - cfg.stop_buffer_atr * atr_px, 4)
    if stop_px >= trigger:
        return None

    swing_high = float(geom["swing_high"])
    drop_px = float(geom["drop_px"])
    t1 = round(pivot_low + cfg.target1_retrace_frac * drop_px, 4)
    t2 = round(pivot_low + cfg.target2_retrace_frac * drop_px, 4)
    # Ensure targets above trigger
    if t1 <= trigger:
        t1 = round(trigger + 0.5 * (swing_high - trigger) if swing_high > trigger else trigger + atr_px, 4)
    if t2 <= t1:
        t2 = round(max(swing_high, t1 + atr_px), 4)
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
        "measured_move_px": round(drop_px, 4),
        "pivot_low": round(pivot_low, 4),
        "swing_high": round(swing_high, 4),
        "drop_pct": round(float(geom["drop_pct"]), 2),
        "drop_bars": int(geom["drop_bars"]),
        "retrace_level": round(float(geom["retrace_level"]), 4),
        "sma20": round(float(geom["sma20"]), 4) if np.isfinite(float(geom["sma20"])) else None,
        "extension_pct": round(float(geom["extension_pct"]), 2),
        "construction": "v0.1.0_right_side_v_reclaim",
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
        f"Right-side-V arm on {day.isoformat()}: drop {float(geom['drop_pct']):.1f}% "
        f"then reclaim (SMA20 + structure); trigger ${trigger:.2f}; "
        f"stop ${stop_px:.2f} under pivot; T1 ${t1:.2f} / T2 ${t2:.2f}."
    )
    return Entry(
        ticker=ticker.upper(),
        day=day,
        time_et="16:00",
        pattern="right_side_v",
        entry_px=trigger,
        bar_close=round(float(row["close"]), 4),
        reason=reason,
        strategy=strategy_id,
        rvol=features["bar_vol_mult"],
        bar_vol_mult=features["bar_vol_mult"],
        features=features,
    )


def detect_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: RightSideVConfig,
    *,
    strategy_id: str = "right_side_v",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    min_len = 220
    if df is None or df.empty or len(df) < min_len:
        return []

    frame = _prep_daily(df, cfg)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    sma20 = frame["sma20"].to_numpy(dtype=float)

    out: list[Entry] = []
    last_arm_i: Optional[int] = None
    start_i = max(cfg.drop_lookback_max + 10, 200)

    for plan_i in range(start_i, len(frame)):
        d = _index_date(frame.index[plan_i])
        if d < cfg.start or d > cfg.end:
            continue
        if eligible_plan_dates is not None and d not in eligible_plan_dates:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime required")
            if d not in market_ok_dates:
                continue
        if last_arm_i is not None and plan_i - last_arm_i <= cfg.min_bars_between_arms:
            continue

        row = frame.iloc[plan_i]
        if not _replay_ok(frame, plan_i):
            continue
        c = float(row["close"])
        avg_vol = row.get("vol_avg20")
        if not (cfg.price_min <= c <= cfg.price_max):
            continue
        if pd.isna(avg_vol) or float(avg_vol) < cfg.avg_vol_min:
            continue
        if cfg.require_above_sma200 and not bool(row.get("above_sma200")):
            continue

        geom = _find_v_geometry(high, low, close, sma20, plan_i, cfg)
        if geom is None:
            continue

        regime = None
        if market_regime_features is not None and d in market_regime_features:
            regime = dict(market_regime_features[d])

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
        last_arm_i = plan_i
    return out


def detect_ticker(
    ticker: str,
    cfg: RightSideVConfig,
    *,
    strategy_id: str = "right_side_v",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    warmup = 420
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup
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
