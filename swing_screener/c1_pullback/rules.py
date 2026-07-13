"""C1_PULLBACK filter rules — pure functions over enriched daily rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

_DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "c1_pullback.yaml"
)


@dataclass(frozen=True)
class MRConfig:
    rsi2_max: float = 10.0
    require_perf_21d_positive: bool = True


@dataclass(frozen=True)
class PBConfig:
    rsi14_min: float = 35.0
    rsi14_max: float = 50.0
    perf_5d_max: float = 0.0
    sma20_extension_max: float = 0.03
    relvol_max: float = 1.2


@dataclass(frozen=True)
class C1Config:
    rules_version: str = "c1_pullback_v1"
    universe: str = "liquid_pit"
    adjustment: str = "split"
    price_min: float = 10.0
    avg_vol_window: int = 20
    avg_vol_min: float = 500_000.0
    require_above_sma50: bool = True
    require_above_sma200: bool = True
    min_dollar_vol: float = 0.0
    warmup_calendar_days: int = 400
    mr: MRConfig = field(default_factory=MRConfig)
    pb: PBConfig = field(default_factory=PBConfig)


def load_config(path: str | Path | None = None) -> C1Config:
    p = Path(path) if path else _DEFAULT_CONFIG
    raw: dict[str, Any] = {}
    if p.exists():
        loaded = yaml.safe_load(p.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config must be a mapping: {p}")
        raw = loaded

    mr_raw = raw.get("mr") or {}
    pb_raw = raw.get("pb") or {}
    return C1Config(
        rules_version=str(raw.get("rules_version", "c1_pullback_v1")),
        universe=str(raw.get("universe", "liquid_pit")),
        adjustment=str(raw.get("adjustment", "split")),
        price_min=float(raw.get("price_min", 10.0)),
        avg_vol_window=int(raw.get("avg_vol_window", 20)),
        avg_vol_min=float(raw.get("avg_vol_min", 500_000)),
        require_above_sma50=bool(raw.get("require_above_sma50", True)),
        require_above_sma200=bool(raw.get("require_above_sma200", True)),
        min_dollar_vol=float(raw.get("min_dollar_vol", 0.0)),
        warmup_calendar_days=int(raw.get("warmup_calendar_days", 400)),
        mr=MRConfig(
            rsi2_max=float(mr_raw.get("rsi2_max", 10.0)),
            require_perf_21d_positive=bool(
                mr_raw.get("require_perf_21d_positive", True)
            ),
        ),
        pb=PBConfig(
            rsi14_min=float(pb_raw.get("rsi14_min", 35.0)),
            rsi14_max=float(pb_raw.get("rsi14_max", 50.0)),
            perf_5d_max=float(pb_raw.get("perf_5d_max", 0.0)),
            sma20_extension_max=float(pb_raw.get("sma20_extension_max", 0.03)),
            relvol_max=float(pb_raw.get("relvol_max", 1.2)),
        ),
    )


def _finite(s: pd.Series) -> pd.Series:
    return s.notna() & np_isfinite(s)


def np_isfinite(s: pd.Series) -> pd.Series:
    import numpy as np

    return pd.Series(np.isfinite(s.to_numpy(dtype=float)), index=s.index)


def shared_mask(df: pd.DataFrame, cfg: C1Config) -> pd.Series:
    """Boolean mask for shared C1 universe/liquidity/trend gates."""
    close = df["close"].astype(float)
    m = _finite(close) & (close >= cfg.price_min)
    m &= _finite(df["avg_vol_20"]) & (df["avg_vol_20"] >= cfg.avg_vol_min)
    if cfg.require_above_sma50:
        m &= _finite(df["sma50"]) & (close > df["sma50"])
    if cfg.require_above_sma200:
        m &= _finite(df["sma200"]) & (close > df["sma200"])
    if cfg.min_dollar_vol and cfg.min_dollar_vol > 0:
        dvol = close * df["avg_vol_20"].astype(float)
        m &= _finite(dvol) & (dvol >= cfg.min_dollar_vol)
    return m.fillna(False)


def mr_mask(df: pd.DataFrame, cfg: C1Config) -> pd.Series:
    """C1_MR candidate mask (includes shared gates)."""
    m = shared_mask(df, cfg)
    m &= _finite(df["rsi2"]) & (df["rsi2"] < cfg.mr.rsi2_max)
    if cfg.mr.require_perf_21d_positive:
        m &= _finite(df["perf_21d"]) & (df["perf_21d"] > 0.0)
    return m.fillna(False)


def pb_mask(df: pd.DataFrame, cfg: C1Config) -> pd.Series:
    """C1_PB candidate mask (includes shared gates)."""
    m = shared_mask(df, cfg)
    m &= _finite(df["rsi14"])
    m &= (df["rsi14"] >= cfg.pb.rsi14_min) & (df["rsi14"] <= cfg.pb.rsi14_max)
    m &= _finite(df["perf_5d"]) & (df["perf_5d"] <= cfg.pb.perf_5d_max)
    m &= _finite(df["sma20_ext"]) & (df["sma20_ext"] <= cfg.pb.sma20_extension_max)
    m &= _finite(df["relvol"]) & (df["relvol"] <= cfg.pb.relvol_max)
    return m.fillna(False)


_METRIC_COLS = [
    "close",
    "volume",
    "avg_vol_20",
    "relvol",
    "sma20",
    "sma50",
    "sma200",
    "rsi2",
    "rsi14",
    "perf_5d",
    "perf_21d",
    "perf_126d",
    "sma20_ext",
]


def extract_hits(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    ticker: str,
    variant: str,
    universe: str,
    rules_version: str,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Rows where mask is True, clipped to [start, end] on the index date."""
    if df is None or df.empty or not mask.any():
        return pd.DataFrame()
    hit = df.loc[mask].copy()
    # Normalize index to dates
    idx = pd.to_datetime(hit.index)
    if getattr(idx, "tz", None) is not None:
        asof = idx.tz_convert("America/New_York").normalize().tz_localize(None)
    else:
        asof = idx.normalize()
    hit = hit.copy()
    hit["asof_date"] = asof
    if start is not None:
        hit = hit[hit["asof_date"] >= pd.Timestamp(start)]
    if end is not None:
        hit = hit[hit["asof_date"] <= pd.Timestamp(end)]
    if hit.empty:
        return pd.DataFrame()

    out = pd.DataFrame({"asof_date": hit["asof_date"].values})
    out["ticker"] = ticker.upper()
    out["variant"] = variant
    for c in _METRIC_COLS:
        if c in hit.columns:
            out[c] = hit[c].to_numpy()
        elif c == "volume" and "volume" in df.columns:
            out[c] = hit["volume"].to_numpy()
        else:
            out[c] = float("nan")
    out["universe"] = universe
    out["rules_version"] = rules_version
    out["earnings_ok"] = pd.NA
    return out.reset_index(drop=True)
