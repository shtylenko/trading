"""Cup-and-handle detection on daily bars (pure + fetch wrapper).

Objectified Davidson checklist (mechanical subset):
  1. Strong uptrend — price above SMA20/50/200; SMA50 rising or stacked
  2. Healthy cup — depth band, multi-bar trough, lips aligned
  3. Tight handle — short, shallow vs cup, lighter volume
  4. Room to run — simplified resistance check
  5. Breakout — first bar that clears handle high with volume

Entry plan fields (ATR stop, T1/T2) are attached on the breakout bar.

For every candidate plan bar, the bounded handle/cup search enumerates all
valid causal geometries and selects one with a fixed structural score and
stable tie-breaker. It never uses future price or outcome information.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    cup_window_bars: int
    lip_to_lip_bars: int
    handle_bars: int
    lip_diff_pct: float
    handle_volume_fraction: float
    trough_centrality: float
    # Filled only after all valid candidates for one plan bar are scored and
    # selected. Raw candidates intentionally leave these at their defaults.
    selection_score: Optional[float] = None
    selection_components: dict[str, float] = field(default_factory=dict)
    selection_candidate_count: int = 1


class MarketRegimeDataError(RuntimeError):
    """Required causal SPY diagnostics are incomplete for a scanner scope."""


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


def _replay_window_indicators_available(frame: pd.DataFrame, plan_i: int) -> bool:
    """Require the scanner plan to satisfy its complete visible replay window."""
    stream_start = max(0, plan_i - DAILY_REPLAY_PLAN_LOOKBACK_BARS)
    return daily_replay_indicators_available(frame.iloc[stream_start : plan_i + 1])


def _index_date(index_value: Any) -> date:
    return index_value.date() if hasattr(index_value, "date") else pd.Timestamp(index_value).date()


def fetch_market_regime_features(cfg: CupHandleConfig) -> dict[date, dict[str, Any]]:
    """Return one fully-defined, causal SPY regime record per trading date.

    The research corpus stores these records as diagnostics even when the optional
    ``require_spy_above_sma50`` gate is disabled.  This fetch is deliberately
    strict: a date that has a candidate stock signal but no finite SPY SMA data is
    a data-integrity failure, never an implicit "regime unknown" value.
    """
    # SMA200 needs at least 200 trading sessions.  Four hundred and twenty
    # calendar days leaves enough room for weekends and market holidays.
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
            # Do not fail for every calendar date in the requested range: only
            # trading dates can be setup dates.  Detectors below fail closed if
            # a candidate falls on an omitted date.
            continue
        above_sma50 = bool(row["close"] > row["sma50"])
        above_sma200 = bool(row["close"] > row["sma200"])
        sma50_rising = bool(row.get("sma50_rising"))
        if above_sma50 and above_sma200:
            regime = "above_sma50_and_sma200"
        elif above_sma50:
            regime = "above_sma50_only"
        elif above_sma200:
            regime = "above_sma200_only"
        else:
            regime = "below_sma50_and_sma200"
        records[as_of] = {
            "schema_version": 1,
            "as_of": as_of.isoformat(),
            "close": round(float(row["close"]), 4),
            "sma50": round(float(row["sma50"]), 4),
            "sma200": round(float(row["sma200"]), 4),
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
            "sma50_rising": sma50_rising,
            "regime": regime,
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


def fetch_market_regime(cfg: CupHandleConfig) -> set[date]:
    """Return dates on which the strict SPY record is above its SMA50."""
    return {
        as_of for as_of, record in fetch_market_regime_features(cfg).items()
        if record["above_sma50"]
    }


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _geometry_selection_components(geom: CupGeometry, cfg: CupHandleConfig) -> dict[str, float]:
    """Fixed structural score used to choose among valid causal geometries.

    This is a deterministic definition, not an outcome-trained model or a
    signal gate. Every candidate has already passed the scanner's hard cup and
    handle constraints; the score only makes an otherwise accidental iteration
    order explicit and reproducible.
    """
    return {
        "handle_shallowness": _clamp_unit(
            1.0 - geom.handle_depth_px / (cfg.handle_depth_max_frac * geom.cup_depth_px)
        ),
        "lip_alignment": _clamp_unit(1.0 - geom.lip_diff_pct / cfg.lip_tolerance_pct),
        "trough_centrality": _clamp_unit(
            1.0 - abs(geom.trough_centrality - 0.5) / 0.5
        ),
        "volume_dryup": _clamp_unit(
            1.0 - geom.handle_volume_fraction / cfg.handle_vol_frac_max
        ),
    }


def _select_cup_and_handle(
    candidates: list[CupGeometry], cfg: CupHandleConfig,
) -> CupGeometry:
    """Select one valid formation with a stable, outcome-independent key.

    Tie-break order is intentionally part of the strategy definition: highest
    structural score, then longer cup, then shorter handle, then earlier
    geometry indices.  The full selection evidence is persisted with the plan.
    """
    if not candidates:
        raise ValueError("cannot select a cup-handle geometry from an empty candidate list")

    scored = [
        (geom, _geometry_selection_components(geom, cfg))
        for geom in candidates
    ]

    def key(item: tuple[CupGeometry, dict[str, float]]) -> tuple[float, int, int, int, int, int]:
        geom, components = item
        score = sum(components.values()) / len(components)
        return (
            -score,
            -geom.cup_window_bars,
            geom.handle_bars,
            geom.left_lip_i,
            geom.cup_low_i,
            geom.right_lip_i,
        )

    selected, components = min(scored, key=key)
    score = sum(components.values()) / len(components)
    return replace(
        selected,
        selection_score=round(score, 6),
        selection_components={name: round(value, 6) for name, value in components.items()},
        selection_candidate_count=len(candidates),
    )


def _formation_quality_features(geom: CupGeometry, cfg: CupHandleConfig) -> dict[str, Any]:
    """Log a predeclared structural quality score; it is not an entry gate.

    The component formula deliberately uses only formation observations visible at
    the setup close.  It gives development analysis a stable, inspectable ranking
    candidate without changing v0.7's decision rule or its historical outcomes.
    """
    components = {
        "handle_high_position": _clamp_unit(
            (geom.handle_low - geom.cup_low_px) / geom.cup_depth_px
        ),
        "handle_shallowness": _clamp_unit(1.0 - geom.handle_depth_px / geom.cup_depth_px),
        "lip_alignment": _clamp_unit(1.0 - geom.lip_diff_pct / cfg.lip_tolerance_pct),
        "trough_centrality": _clamp_unit(1.0 - abs(geom.trough_centrality - 0.5) / 0.5),
        "volume_dryup": _clamp_unit(
            1.0 - geom.handle_volume_fraction / cfg.handle_vol_frac_max
        ),
    }
    return {
        "schema_version": 1,
        "definition": "formation_quality_v1_diagnostics_only",
        "score": round(sum(components.values()) / len(components), 4),
        "components": {name: round(value, 4) for name, value in components.items()},
        "raw": {
            "cup_window_bars": geom.cup_window_bars,
            "lip_to_lip_bars": geom.lip_to_lip_bars,
            "handle_bars": geom.handle_bars,
            "lip_diff_pct": round(geom.lip_diff_pct, 4),
            "handle_depth_fraction": round(geom.handle_depth_px / geom.cup_depth_px, 4),
            "handle_volume_fraction": round(geom.handle_volume_fraction, 4),
            "trough_centrality": round(geom.trough_centrality, 4),
        },
    }


def _geometry_selection_features(geom: CupGeometry) -> dict[str, Any]:
    """Return auditable evidence for the selected candidate, or fail closed."""
    if (
        geom.selection_score is None
        or geom.selection_candidate_count < 1
        or set(geom.selection_components) != {
            "handle_shallowness", "lip_alignment", "trough_centrality", "volume_dryup",
        }
    ):
        raise RuntimeError("cup-handle geometry is missing deterministic selection evidence")
    return {
        "schema_version": 1,
        "definition": "geometry_selection_v1",
        "score": geom.selection_score,
        "components": dict(geom.selection_components),
        "candidate_count": geom.selection_candidate_count,
        "tie_break_order": [
            "higher_score",
            "longer_cup_window_bars",
            "shorter_handle_bars",
            "earlier_left_lip_index",
            "earlier_cup_low_index",
            "earlier_right_lip_index",
        ],
        "selected_geometry": {
            "left_lip_i": geom.left_lip_i,
            "cup_low_i": geom.cup_low_i,
            "right_lip_i": geom.right_lip_i,
            "cup_window_bars": geom.cup_window_bars,
            "handle_bars": geom.handle_bars,
        },
    }


def _market_regime_for_setup(
    day: date,
    market_regime_features: Optional[dict[date, dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    """Return an immutable-as-practice setup-day SPY record or fail closed."""
    if market_regime_features is None:
        return None
    record = market_regime_features.get(day)
    if record is None:
        raise MarketRegimeDataError(
            "SPY regime diagnostics are unavailable for candidate setup date "
            f"{day.isoformat()}"
        )
    return dict(record)


def _valid_cup_and_handle_geometries(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    end_i: int,
    cfg: CupHandleConfig,
) -> list[CupGeometry]:
    """Enumerate every valid cup+handle ending at ``end_i`` (last handle bar)."""
    if end_i < cfg.cup_min_bars + cfg.handle_min_bars + 5:
        return []

    candidates: list[CupGeometry] = []

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
            if cup_vol <= 0:
                continue

            lip_to_lip_bars = right_lip_i - left_lip_i
            if lip_to_lip_bars <= 0:
                continue

            candidates.append(CupGeometry(
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
                cup_window_bars=cup_len,
                lip_to_lip_bars=lip_to_lip_bars,
                handle_bars=handle_len,
                lip_diff_pct=round(lip_diff_pct, 4),
                handle_volume_fraction=round(handle_vol / cup_vol, 6),
                trough_centrality=round((cup_low_i - left_lip_i) / lip_to_lip_bars, 6),
            ))
    return candidates


def _find_cup_and_handle(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    end_i: int,
    cfg: CupHandleConfig,
) -> Optional[CupGeometry]:
    """Return the deterministically selected geometry for a completed plan bar."""
    candidates = _valid_cup_and_handle_geometries(high, low, volume, end_i, cfg)
    return _select_cup_and_handle(candidates, cfg) if candidates else None


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
    market_regime: Optional[dict[str, Any]] = None,
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
        # Quality remains descriptive; geometry_selection records why this
        # valid formation, rather than another valid formation, was chosen.
        "formation_quality": _formation_quality_features(geom, cfg),
        "geometry_selection": _geometry_selection_features(geom),
    }
    if market_regime is not None:
        features["market_regime"] = dict(market_regime)
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
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
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
        if eligible_plan_dates is not None and d not in eligible_plan_dates:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates are required when require_spy_above_sma50=True")
            if d not in market_ok_dates:
                continue

        row = frame.iloc[bi]
        if not _replay_window_indicators_available(frame, bi):
            continue
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
            market_regime=_market_regime_for_setup(d, market_regime_features),
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
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
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
        # Point-in-time research may restrict which completed sessions a ticker
        # was eligible to arm on.  Apply that membership decision before the
        # cooldown and formation state are updated: an ineligible plan was never
        # actionable, so it must not suppress a later eligible one.
        if eligible_plan_dates is not None and d not in eligible_plan_dates:
            continue
        if cfg.require_spy_above_sma50:
            if market_ok_dates is None:
                raise ValueError("SPY regime dates are required when require_spy_above_sma50=True")
            if d not in market_ok_dates:
                continue
        if last_arm_i is not None and plan_i - last_arm_i <= cfg.arm_expiry_bars:
            continue

        row = frame.iloc[plan_i]
        if not _replay_window_indicators_available(frame, plan_i):
            continue
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
            market_regime=_market_regime_for_setup(d, market_regime_features),
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
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
) -> list[Entry]:
    """Detect the configured cup-and-handle signal type over a daily frame.

    ``prebreak_arm`` is the production default.  ``confirmed_breakout`` exists
    for post-event research labels and produces a next-session plan, never a
    same-day execution claim.
    """
    cfg.validate()
    if cfg.signal_mode == "prebreak_arm":
        return _detect_prebreak_arms_from_frame(
            df,
            ticker,
            cfg,
            strategy_id=strategy_id,
            market_ok_dates=market_ok_dates,
            market_regime_features=market_regime_features,
            eligible_plan_dates=eligible_plan_dates,
        )
    return _detect_confirmed_breakouts_from_frame(
        df,
        ticker,
        cfg,
        strategy_id=strategy_id,
        market_ok_dates=market_ok_dates,
        market_regime_features=market_regime_features,
        eligible_plan_dates=eligible_plan_dates,
    )


def detect_ticker(
    ticker: str,
    cfg: CupHandleConfig,
    *,
    strategy_id: str = "cup_handle",
    market_ok_dates: Optional[set[date]] = None,
    market_regime_features: Optional[dict[date, dict[str, Any]]] = None,
    eligible_plan_dates: Optional[set[date]] = None,
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
        # An unavailable provider series is not a negative pattern result.  In a
        # research scan, returning [] here would make a broken or invalid symbol
        # indistinguishable from a fully evaluated no-signal and let the corpus
        # publish with a hidden coverage hole.
        raise RuntimeError(f"no daily market-data bars available for {ticker}")
    if cfg.require_spy_above_sma50 and market_ok_dates is None:
        if market_regime_features is None:
            market_regime_features = fetch_market_regime_features(cfg)
        market_ok_dates = {
            as_of for as_of, record in market_regime_features.items()
            if record["above_sma50"]
        }
    return detect_from_frame(
        df,
        ticker,
        cfg,
        strategy_id=strategy_id,
        market_ok_dates=market_ok_dates,
        market_regime_features=market_regime_features,
        eligible_plan_dates=eligible_plan_dates,
    )
