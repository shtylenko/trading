"""C2 portfolio layer — thin wrapper around shared ranking + capacity rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from trading.swing_screener.c1_pullback.portfolio import (
    PortfolioConfig,
    apply_portfolio,
    load_sector_map,
)

_DEFAULT = Path(__file__).resolve().parents[1] / "config" / "c2_breakout.yaml"


def load_portfolio_config(path: str | Path | None = None) -> PortfolioConfig:
    p = Path(path) if path else _DEFAULT
    raw: dict[str, Any] = {}
    if p.exists():
        loaded = yaml.safe_load(p.read_text()) or {}
        raw = (loaded.get("portfolio") or {}) if isinstance(loaded, dict) else {}
    return PortfolioConfig(
        max_positions=int(raw.get("max_positions", 4)),
        max_per_sector=int(raw.get("max_per_sector", 2)),
        starting_equity=float(raw.get("starting_equity", 20_000)),
        risk_frac=float(raw.get("risk_frac", 0.0075)),
        allocation="merge",
    )


def attach_c2_rank_features(
    trades: pd.DataFrame, candidates: pd.DataFrame | None
) -> pd.DataFrame:
    t = trades.copy()
    t["ticker"] = t["ticker"].astype(str).str.upper()
    t["signal_date"] = pd.to_datetime(t["signal_date"]).dt.date
    if candidates is None or candidates.empty:
        for col in ("dist_52w", "relvol", "rsi14"):
            if col not in t.columns:
                t[col] = np.nan
        # map into portfolio rank fields
        t["rsi2"] = t.get("dist_52w", np.nan)  # lower dist_52w better → use as rsi2-like
        t["sma20_ext"] = t.get("dist_52w", np.nan)
        t["pullback_depth_atr"] = t.get("relvol", np.nan)
        t["variant"] = "C2_BREAKOUT"
        return t

    c = candidates.copy()
    c["ticker"] = c["ticker"].astype(str).str.upper()
    c["signal_date"] = pd.to_datetime(c["asof_date"]).dt.date
    keep = ["ticker", "signal_date", "dist_52w", "relvol", "rsi14", "base_depth_atr"]
    for col in keep:
        if col not in c.columns and col not in ("ticker", "signal_date"):
            c[col] = np.nan
    c = c[keep].drop_duplicates(["ticker", "signal_date"], keep="last")
    t = t.merge(c, on=["ticker", "signal_date"], how="left")
    # Portfolio rank_key: for non-MR uses sma20_ext + pullback_depth.
    # We force C2 through quality_score by setting variant and fields:
    # Use dist_52w as primary (closer to high = better) via fake rsi2 path:
    t["variant"] = "C2_BREAKOUT"
    # Hack quality via MR branch: lower rsi2 ranks first — put dist_52w*100 as rsi2
    t["rsi2"] = t["dist_52w"].astype(float) * 100.0
    t["sma20_ext"] = t["dist_52w"]
    t["pullback_depth_atr"] = t["relvol"]
    return t


def run_c2_portfolio(
    trades: pd.DataFrame,
    candidates: pd.DataFrame | None = None,
    *,
    cfg: PortfolioConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Capacity filter for C2 trades.

    Ranking: closer to 52w high first (via dist_52w encoded as rsi2 for the
    shared portfolio helper's MR-style lower-is-better path — we temporarily
    set variant to C1_MR for ranking only).
    """
    cfg = cfg or load_portfolio_config()
    t = attach_c2_rank_features(trades, candidates)
    # Use MR rank path: lower rsi2 first → lower dist_52w first
    t = t.copy()
    t["variant"] = "C1_MR"
    selected, summary = apply_portfolio(
        t,
        cfg=cfg,
        candidates=None,  # features already attached
        variants=["C1_MR"],
    )
    if not selected.empty:
        selected["variant"] = "C2_BREAKOUT"
    if not summary.empty:
        summary = summary.copy()
        summary["scope"] = summary["scope"].replace({"C1_MR": "C2_BREAKOUT", "ALL": "ALL"})
    return selected, summary
