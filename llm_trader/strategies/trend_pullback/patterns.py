"""Trend-pullback detection on daily bars (pure + fetch wrapper).

Mechanical subset of Lance swing #1 / Qullamaggie-style MA pullback:

  1. Uptrend — close above SMA50 (and SMA200); SMA50 rising
  2. Pullback — within the last N bars, price tagged the pullback MA from above
     (``ema20`` for 0.1–0.3; ``sma50`` for 0.4.0)
  3. Reclaim — setup bar closes back above that MA (confirmation)
  4. Plan — buy-stop / stop / targets per construction config

Plans are causal ``prebreak_arm`` signals: emitted at the close of the reclaim
bar for a *later* session fill. No future bars are inspected.
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

from .config import TrendPullbackConfig


class MarketRegimeDataError(RuntimeError):
    """Required causal SPY diagnostics are incomplete for a scanner scope."""


def _prep_daily(df: pd.DataFrame, cfg: TrendPullbackConfig) -> pd.DataFrame:
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


def _ma_column(cfg: TrendPullbackConfig) -> str:
    if cfg.pullback_ma == "sma50":
        return "sma50"
    return "ema20"


def _passes_trend(row: pd.Series, cfg: TrendPullbackConfig) -> bool:
    needed = ("sma50", "sma200", "atr14", _ma_column(cfg))
    for col in needed:
        if pd.isna(row.get(col)):
            return False
    if cfg.require_above_sma50 and not bool(row.get("above_sma50")):
        return False
    if cfg.require_above_sma200 and not bool(row.get("above_sma200")):
        return False
    if cfg.require_sma50_rising and not bool(row.get("sma50_rising")):
        return False
    return True


def _replay_window_indicators_available(frame: pd.DataFrame, plan_i: int) -> bool:
    stream_start = max(0, plan_i - DAILY_REPLAY_PLAN_LOOKBACK_BARS)
    return daily_replay_indicators_available(frame.iloc[stream_start : plan_i + 1])


def fetch_market_regime_features(cfg: TrendPullbackConfig) -> dict[date, dict[str, Any]]:
    """Return one fully-defined, causal SPY regime record per trading date."""
    warmup_days = 420
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup_days
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    spy = fetch_bars("SPY", "1day", start=start, end=end, adjustment="raw")
    if spy is None or spy.empty:
        raise MarketRegimeDataError(
            "SPY regime diagnostics require daily SPY bars, but none are available"
        )
    prepared = _prep_daily(spy, cfg)
    records: dict[date, dict[str, Any]] = {}
    for ts, row in prepared.iterrows():
        as_of = _index_date(ts)
        if as_of < cfg.start or as_of > cfg.end:
            continue
        required = ("close", "sma50", "sma200", "sma50_rising")
        if any(pd.isna(row.get(field)) or not np.isfinite(float(row[field])) for field in required):
            continue
        above_sma50 = bool(row["close"] > row["sma50"])
        above_sma200 = bool(row["close"] > row["sma200"])
        records[as_of] = {
            "schema_version": 1,
            "as_of": as_of.isoformat(),
            "close": round(float(row["close"]), 4),
            "sma50": round(float(row["sma50"]), 4),
            "sma200": round(float(row["sma200"]), 4),
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
            "sma50_rising": bool(row.get("sma50_rising")),
            "regime": (
                "above_sma50_and_sma200" if above_sma50 and above_sma200
                else "above_sma50_only" if above_sma50
                else "above_sma200_only" if above_sma200
                else "below_sma50_and_sma200"
            ),
        }
    if not records:
        raise MarketRegimeDataError(
            "SPY regime diagnostics have no indicator-complete trading dates in "
            f"{cfg.start.isoformat()}..{cfg.end.isoformat()}"
        )
    expected_dates = trading_days_in_range(cfg.start, cfg.end)
    missing_dates = [day for day in expected_dates if day not in records]
    if missing_dates:
        preview = ", ".join(day.isoformat() for day in missing_dates[:5])
        suffix = "" if len(missing_dates) <= 5 else f" (+{len(missing_dates) - 5} more)"
        raise MarketRegimeDataError(
            "SPY regime diagnostics are incomplete for the requested market-session scope: "
            f"{preview}{suffix}"
        )
    return records


def _market_regime_for_setup(
    day: date,
    market_regime_features: Optional[dict[date, dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    if market_regime_features is None:
        return None
    rec = market_regime_features.get(day)
    return dict(rec) if rec is not None else None


def _find_pullback_reclaim(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    ma: np.ndarray,
    plan_i: int,
    cfg: TrendPullbackConfig,
) -> Optional[dict[str, float | int]]:
    """Return geometry for a reclaim-of-pullback-MA setup ending at ``plan_i``.

    ``ma`` is the pullback reference series (EMA20 or SMA50). Uses only bars
    ``<= plan_i`` (causal).
    """
    if plan_i < cfg.max_pullback_bars + 5:
        return None

    c = float(close[plan_i])
    m = float(ma[plan_i])
    if not np.isfinite(c) or not np.isfinite(m) or m <= 0:
        return None
    # Reclaim confirmation: close back above the pullback MA
    if c < m:
        return None
    ext_pct = (c / m - 1.0) * 100.0
    if ext_pct > cfg.max_extension_above_ema_pct:
        return None

    touch_tol = cfg.touch_tol_pct / 100.0
    window_start = plan_i - cfg.max_pullback_bars + 1
    if window_start < 1:
        return None

    touch_indices: list[int] = []
    close_below = False
    for j in range(window_start, plan_i + 1):
        mj = float(ma[j])
        lj = float(low[j])
        cj = float(close[j])
        if not np.isfinite(mj) or mj <= 0 or not np.isfinite(lj):
            continue
        if lj <= mj * (1.0 + touch_tol):
            touch_indices.append(j)
        if np.isfinite(cj) and cj <= mj:
            close_below = True

    if not touch_indices:
        return None
    if cfg.require_close_below_ema and not close_below:
        return None

    first_touch = touch_indices[0]
    last_touch = touch_indices[-1]
    pullback_bars = plan_i - first_touch + 1
    if pullback_bars < cfg.min_pullback_bars:
        return None
    if last_touch > plan_i:
        return None

    # Before the pullback the name was above the MA (trend, not first contact)
    pre_i = first_touch - 1
    if pre_i < 0:
        return None
    pre_close = float(close[pre_i])
    pre_ma = float(ma[pre_i])
    if not np.isfinite(pre_close) or not np.isfinite(pre_ma) or pre_close < pre_ma:
        ok_pre = False
        for k in range(max(0, first_touch - 5), first_touch):
            if float(close[k]) > float(ma[k]):
                ok_pre = True
                break
        if not ok_pre:
            return None

    pullback_low_i = int(first_touch + np.argmin(low[first_touch : plan_i + 1]))
    pullback_low = float(low[pullback_low_i])
    if not np.isfinite(pullback_low) or pullback_low <= 0:
        return None

    ph_end = first_touch - 1
    ph_start = max(0, ph_end - cfg.prior_high_lookback + 1)
    if ph_end < ph_start:
        return None
    prior_slice = high[ph_start : ph_end + 1]
    if prior_slice.size == 0:
        return None
    prior_high_i = int(ph_start + np.argmax(prior_slice))
    prior_high = float(high[prior_high_i])
    if not np.isfinite(prior_high) or prior_high <= pullback_low:
        return None

    depth_pct = (prior_high - pullback_low) / prior_high * 100.0
    if not (cfg.pullback_depth_min_pct <= depth_pct <= cfg.pullback_depth_max_pct):
        return None

    setup_high = float(high[plan_i])
    if not np.isfinite(setup_high) or setup_high <= pullback_low:
        return None

    return {
        "first_touch_i": first_touch,
        "pullback_low_i": pullback_low_i,
        "prior_high_i": prior_high_i,
        "pullback_low": pullback_low,
        "prior_high": prior_high,
        "setup_high": setup_high,
        "ma_px": m,
        "ema20": m,  # retained key for stream/feature compatibility
        "depth_pct": depth_pct,
        "depth_px": prior_high - pullback_low,
        "pullback_bars": pullback_bars,
        "extension_pct": ext_pct,
    }


def _entry_from_geometry(
    *,
    ticker: str,
    day: date,
    row: pd.Series,
    geom: dict[str, float | int],
    cfg: TrendPullbackConfig,
    strategy_id: str,
    market_regime: Optional[dict[str, Any]] = None,
) -> Optional[Entry]:
    atr_px = float(row["atr14"])
    if atr_px <= 0 or pd.isna(atr_px):
        return None

    setup_close = float(row["close"])
    setup_high = float(geom["setup_high"])
    if cfg.entry_trigger_mode == "reclaim_close":
        # 0.3.0: arm above the reclaim close — less chase than setup high.
        trigger = round(setup_close, 4)
    else:
        trigger = round(setup_high, 4)

    pullback_low = float(geom["pullback_low"])
    stop_px = round(pullback_low - cfg.stop_buffer_atr * atr_px, 4)
    if stop_px >= trigger:
        return None

    prior_high = float(geom["prior_high"])
    depth_px = float(geom["depth_px"])
    stop_dist = round(trigger - stop_px, 4)
    if stop_dist <= 0:
        return None

    if cfg.target1_mode == "risk_r":
        # Risk-based ladder: T1 = 1R, T2 = 2R from the armed stop (symmetric RR).
        t1 = round(trigger + cfg.target1_r_mult * stop_dist, 4)
        t2 = round(trigger + cfg.target2_r_mult * stop_dist, 4)
    else:
        # Legacy structure targets (0.1–0.2).
        t1 = round(max(prior_high, trigger + 0.25 * atr_px), 4)
        t2 = round(t1 + cfg.measured_move_frac * depth_px, 4)
    if t1 <= trigger or t2 <= t1:
        return None

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
        "target1_mode": cfg.target1_mode,
        "target1_r_mult": cfg.target1_r_mult if cfg.target1_mode == "risk_r" else None,
        "target2_r_mult": cfg.target2_r_mult if cfg.target1_mode == "risk_r" else None,
        "measured_move_px": round(depth_px, 4),
        "pullback_low": round(pullback_low, 4),
        "prior_high": round(prior_high, 4),
        "setup_high": round(setup_high, 4),
        "setup_close": round(setup_close, 4),
        "ma_px": round(float(geom.get("ma_px", geom["ema20"])), 4),
        "ema20": round(float(geom["ema20"]), 4),
        "pullback_depth_pct": round(float(geom["depth_pct"]), 2),
        "pullback_bars": int(geom["pullback_bars"]),
        "extension_pct": round(float(geom["extension_pct"]), 2),
        "construction": (
            f"v0.4.0_{cfg.pullback_ma}_{cfg.entry_trigger_mode}_{cfg.target1_mode}"
        ),
        "sma20": round(float(row["sma20"]), 4) if pd.notna(row.get("sma20")) else None,
        "sma50": round(float(row["sma50"]), 4) if pd.notna(row.get("sma50")) else None,
        "sma200": round(float(row["sma200"]), 4) if pd.notna(row.get("sma200")) else None,
        "bar_vol_mult": (
            round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None
        ),
        "horizon": "multi_day",
        "pullback_ma": cfg.pullback_ma,
    }
    if market_regime is not None:
        features["market_regime"] = dict(market_regime)

    ma_label = cfg.pullback_ma.upper()
    reason = (
        f"Trend pullback arm: reclaim of {ma_label} on {day.isoformat()} "
        f"(depth {float(geom['depth_pct']):.1f}% / ${depth_px:.2f}); "
        f"trigger ${trigger:.2f} ({cfg.entry_trigger_mode}); "
        f"stop ${stop_px:.2f}; T1 ${t1:.2f} / T2 ${t2:.2f} ({cfg.target1_mode})."
    )
    return Entry(
        ticker=ticker.upper(),
        day=day,
        time_et="16:00",
        pattern="trend_pullback",
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


def detect_from_frame(
    df: pd.DataFrame,
    ticker: str,
    cfg: TrendPullbackConfig,
    *,
    strategy_id: str = "trend_pullback",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Detect causal trend-pullback plans over a daily frame."""
    min_len = 220  # SMA200 + cushion
    if df is None or df.empty or len(df) < min_len:
        return []

    frame = _prep_daily(df, cfg)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    ma = frame[_ma_column(cfg)].to_numpy(dtype=float)

    out: list[Entry] = []
    last_arm_i: Optional[int] = None
    start_i = max(cfg.max_pullback_bars + 10, 200)

    for plan_i in range(start_i, len(frame)):
        d = _index_date(frame.index[plan_i])
        if d < cfg.start or d > cfg.end:
            continue
        if eligible_plan_dates is not None and d not in eligible_plan_dates:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates are required when require_spy_above_sma50=True")
            if d not in market_ok_dates:
                continue
        if last_arm_i is not None and plan_i - last_arm_i <= cfg.min_bars_between_arms:
            continue

        row = frame.iloc[plan_i]
        if not _replay_window_indicators_available(frame, plan_i):
            continue
        c = float(row["close"])
        avg_vol = row.get("vol_avg20")
        if not (cfg.price_min <= c <= cfg.price_max):
            continue
        if pd.isna(avg_vol) or float(avg_vol) < cfg.avg_vol_min:
            continue
        if not _passes_trend(row, cfg):
            continue

        geom = _find_pullback_reclaim(high, low, close, ma, plan_i, cfg)
        if geom is None:
            continue

        entry = _entry_from_geometry(
            ticker=ticker,
            day=d,
            row=row,
            geom=geom,
            cfg=cfg,
            strategy_id=strategy_id,
            market_regime=_market_regime_for_setup(d, market_regime_features),
        )
        if entry is None:
            continue
        out.append(entry)
        last_arm_i = plan_i
    return out


def detect_ticker(
    ticker: str,
    cfg: TrendPullbackConfig,
    *,
    strategy_id: str = "trend_pullback",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Fetch daily bars and detect trend-pullback plans for one ticker."""
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
