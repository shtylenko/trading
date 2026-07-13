"""C2_BREAKOUT filter config and masks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

_DEFAULT = Path(__file__).resolve().parents[1] / "config" / "c2_breakout.yaml"


@dataclass(frozen=True)
class C2BacktestConfig:
    cost_bps_per_side: float = 5.0
    one_position_per_ticker: bool = True
    entry_mode: str = "next_open"
    stop_atr_buffer: float = 0.10
    max_stop_atr: float = 1.25
    max_stop_pct: float = 0.08
    target_r: float = 2.5
    max_hold_days: int = 8
    no_progress_days: int = 3
    no_progress_min_r: float = 0.5
    max_gap_atr: float = 0.75


@dataclass(frozen=True)
class C2Config:
    rules_version: str = "c2_breakout_v1"
    universe: str = "liquid_pit"
    adjustment: str = "split"
    warmup_calendar_days: int = 450
    price_min: float = 10.0
    avg_vol_min: float = 500_000.0
    require_above_sma20: bool = True
    require_above_sma50: bool = True
    require_above_sma200: bool = True
    near_52w_pct: float = 0.10
    perf_63d_min: float = 0.10
    perf_21d_min: float = 0.0
    rsi14_min: float = 50.0
    rsi14_max: float = 75.0
    max_ext_above_sma20: float = 0.10
    base_lookback: int = 15
    base_depth_atr_max: float = 2.5
    base_range_pct_max: float = 0.12
    require_vol_dryup: bool = True
    relvol_min: float = 1.5
    max_break_extension_atr: float = 0.75
    require_rs_spy_21d: bool = True
    backtest: C2BacktestConfig = field(default_factory=C2BacktestConfig)


def load_config(path: str | Path | None = None) -> C2Config:
    p = Path(path) if path else _DEFAULT
    raw: dict[str, Any] = {}
    if p.exists():
        loaded = yaml.safe_load(p.read_text()) or {}
        if isinstance(loaded, dict):
            raw = loaded
    bt = raw.get("backtest") or {}
    return C2Config(
        rules_version=str(raw.get("rules_version", "c2_breakout_v1")),
        universe=str(raw.get("universe", "liquid_pit")),
        adjustment=str(raw.get("adjustment", "split")),
        warmup_calendar_days=int(raw.get("warmup_calendar_days", 450)),
        price_min=float(raw.get("price_min", 10.0)),
        avg_vol_min=float(raw.get("avg_vol_min", 500_000)),
        require_above_sma20=bool(raw.get("require_above_sma20", True)),
        require_above_sma50=bool(raw.get("require_above_sma50", True)),
        require_above_sma200=bool(raw.get("require_above_sma200", True)),
        near_52w_pct=float(raw.get("near_52w_pct", 0.10)),
        perf_63d_min=float(raw.get("perf_63d_min", 0.10)),
        perf_21d_min=float(raw.get("perf_21d_min", 0.0)),
        rsi14_min=float(raw.get("rsi14_min", 50.0)),
        rsi14_max=float(raw.get("rsi14_max", 75.0)),
        max_ext_above_sma20=float(raw.get("max_ext_above_sma20", 0.10)),
        base_lookback=int(raw.get("base_lookback", 15)),
        base_depth_atr_max=float(raw.get("base_depth_atr_max", 2.5)),
        base_range_pct_max=float(raw.get("base_range_pct_max", 0.12)),
        require_vol_dryup=bool(raw.get("require_vol_dryup", True)),
        relvol_min=float(raw.get("relvol_min", 1.5)),
        max_break_extension_atr=float(raw.get("max_break_extension_atr", 0.75)),
        require_rs_spy_21d=bool(raw.get("require_rs_spy_21d", True)),
        backtest=C2BacktestConfig(
            cost_bps_per_side=float(bt.get("cost_bps_per_side", 5.0)),
            one_position_per_ticker=bool(bt.get("one_position_per_ticker", True)),
            entry_mode=str(bt.get("entry_mode", "next_open")),
            stop_atr_buffer=float(bt.get("stop_atr_buffer", 0.10)),
            max_stop_atr=float(bt.get("max_stop_atr", 1.25)),
            max_stop_pct=float(bt.get("max_stop_pct", 0.08)),
            target_r=float(bt.get("target_r", 2.5)),
            max_hold_days=int(bt.get("max_hold_days", 8)),
            no_progress_days=int(bt.get("no_progress_days", 3)),
            no_progress_min_r=float(bt.get("no_progress_min_r", 0.5)),
            max_gap_atr=float(bt.get("max_gap_atr", 0.75)),
        ),
    )


def _fin(s: pd.Series) -> pd.Series:
    return s.notna() & pd.Series(np.isfinite(s.to_numpy(dtype=float)), index=s.index)


def c2_mask(df: pd.DataFrame, cfg: C2Config) -> pd.Series:
    """Boolean mask: base quality + breakout trigger on this bar."""
    close = df["close"].astype(float)
    m = _fin(close) & (close >= cfg.price_min)
    m &= _fin(df["avg_vol_20"]) & (df["avg_vol_20"] >= cfg.avg_vol_min)
    if cfg.require_above_sma20:
        m &= _fin(df["sma20"]) & (close > df["sma20"])
    if cfg.require_above_sma50:
        m &= _fin(df["sma50"]) & (close > df["sma50"])
    if cfg.require_above_sma200:
        m &= _fin(df["sma200"]) & (close > df["sma200"])
    m &= _fin(df["dist_52w"]) & (df["dist_52w"] <= cfg.near_52w_pct)
    m &= _fin(df["perf_63d"]) & (df["perf_63d"] >= cfg.perf_63d_min)
    m &= _fin(df["perf_21d"]) & (df["perf_21d"] >= cfg.perf_21d_min)
    m &= _fin(df["rsi14"]) & (df["rsi14"] >= cfg.rsi14_min) & (df["rsi14"] <= cfg.rsi14_max)
    m &= _fin(df["sma20_ext"]) & (df["sma20_ext"] <= cfg.max_ext_above_sma20)

    # Base structure (precomputed causal columns)
    m &= _fin(df["pivot"]) & _fin(df["base_low"])
    m &= _fin(df["base_depth_atr"]) & (df["base_depth_atr"] <= cfg.base_depth_atr_max)
    m &= _fin(df["base_range_pct"]) & (df["base_range_pct"] <= cfg.base_range_pct_max)
    if cfg.require_vol_dryup:
        m &= df["base_vol_dryup"].fillna(False).astype(bool)

    # Breakout trigger
    m &= close > df["pivot"]
    m &= df["high"].astype(float) >= df["pivot"]
    m &= _fin(df["relvol"]) & (df["relvol"] >= cfg.relvol_min)
    if cfg.max_break_extension_atr and cfg.max_break_extension_atr > 0:
        ext_atr = (close - df["pivot"]) / df["atr14"].replace(0.0, np.nan)
        m &= _fin(ext_atr) & (ext_atr <= cfg.max_break_extension_atr)
    if cfg.require_rs_spy_21d:
        m &= _fin(df["rs_spy_21d"]) & (df["rs_spy_21d"] >= 0.0)
    return m.fillna(False)


_METRIC_COLS = [
    "close",
    "high",
    "low",
    "volume",
    "avg_vol_20",
    "relvol",
    "sma20",
    "sma50",
    "sma200",
    "rsi14",
    "atr14",
    "perf_21d",
    "perf_63d",
    "high_252",
    "dist_52w",
    "sma20_ext",
    "pivot",
    "base_low",
    "base_depth_atr",
    "base_range_pct",
    "base_vol_dryup",
    "rs_spy_21d",
]


def extract_hits(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    ticker: str,
    cfg: C2Config,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if df is None or df.empty or not mask.any():
        return pd.DataFrame()
    hit = df.loc[mask].copy()
    idx = pd.to_datetime(hit.index)
    if getattr(idx, "tz", None) is not None:
        asof = idx.tz_convert("America/New_York").normalize().tz_localize(None)
    else:
        asof = idx.normalize()
    hit["asof_date"] = asof
    if start is not None:
        hit = hit[hit["asof_date"] >= pd.Timestamp(start)]
    if end is not None:
        hit = hit[hit["asof_date"] <= pd.Timestamp(end)]
    if hit.empty:
        return pd.DataFrame()

    out = pd.DataFrame({"asof_date": hit["asof_date"].values})
    out["ticker"] = ticker.upper()
    out["variant"] = "C2_BREAKOUT"
    for c in _METRIC_COLS:
        out[c] = hit[c].to_numpy() if c in hit.columns else np.nan
    out["universe"] = cfg.universe
    out["rules_version"] = cfg.rules_version
    return out.reset_index(drop=True)
