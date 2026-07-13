"""Capacity-aware portfolio layer for C1 trades.

Takes *already simulated* trades (from ``backtest.run_backtest``) and selects
a subset under:

* max concurrent positions (default 4 ≈ 3% heat at 0.75%/trade)
* optional max positions per sector (via lab sector_map → SPDR ETF)
* ranking when more signals want to enter than free slots

Does **not** re-simulate prices — uses each trade's realized_r as given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger("trading.swing_screener.c1_pullback.portfolio")

_SECTOR_MAP_PATH = (
    Path(__file__).resolve().parents[2] / "lab" / "universes" / "sector_map.yaml"
)


@dataclass(frozen=True)
class PortfolioConfig:
    max_positions: int = 4
    max_per_sector: int = 2
    starting_equity: float = 20_000.0
    risk_frac: float = 0.0075  # fraction of equity risked per open trade
    # When both variants compete: "merge" ranks in one pool; "mr_first" fills MR then PB
    allocation: str = "merge"  # merge | mr_first | pb_first


def load_sector_map(path: Path | None = None) -> dict[str, str]:
    p = path or _SECTOR_MAP_PATH
    if not p.exists():
        logger.warning("sector map not found at %s — sector caps disabled", p)
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    raw = data.get("map") or {}
    return {str(k).upper(): str(v).upper() for k, v in raw.items()}


def _as_date(v: Any) -> date:
    if isinstance(v, date) and not isinstance(v, pd.Timestamp):
        return v
    return pd.Timestamp(v).date()


def attach_rank_features(
    trades: pd.DataFrame,
    candidates: pd.DataFrame | None,
) -> pd.DataFrame:
    """Join screen diagnostics onto trades for ranking."""
    t = trades.copy()
    t["ticker"] = t["ticker"].astype(str).str.upper()
    t["variant"] = t["variant"].astype(str)
    t["signal_date"] = t["signal_date"].map(_as_date)
    t["entry_date"] = t["entry_date"].map(_as_date)
    t["exit_date"] = t["exit_date"].map(_as_date)

    if candidates is None or candidates.empty:
        for col in ("rsi2", "rsi14", "sma20_ext", "pullback_depth_atr", "relvol"):
            if col not in t.columns:
                t[col] = np.nan
        return t

    c = candidates.copy()
    c["ticker"] = c["ticker"].astype(str).str.upper()
    c["variant"] = c["variant"].astype(str)
    c["signal_date"] = c["asof_date"].map(_as_date)
    cols = [
        "ticker",
        "variant",
        "signal_date",
        "rsi2",
        "rsi14",
        "sma20_ext",
        "pullback_depth_atr",
        "relvol",
    ]
    have = [x for x in cols if x in c.columns or x in ("ticker", "variant", "signal_date")]
    # ensure optional metrics exist
    for col in ("rsi2", "rsi14", "sma20_ext", "pullback_depth_atr", "relvol"):
        if col not in c.columns:
            c[col] = np.nan
    c = c[["ticker", "variant", "signal_date", "rsi2", "rsi14", "sma20_ext", "pullback_depth_atr", "relvol"]]
    # one row per key
    c = c.drop_duplicates(["ticker", "variant", "signal_date"], keep="last")
    t = t.merge(c, on=["ticker", "variant", "signal_date"], how="left")
    return t


def quality_score(row: pd.Series) -> float:
    """Higher = better candidate for a free slot.

    C1_MR: more oversold RSI(2) → higher score in ~[0, 1].
    C1_PB: closer to SMA20 and deeper orderly pullback → higher score in ~[0, 1].
    """
    variant = row["variant"]
    if variant == "C1_MR":
        rsi = row.get("rsi2")
        rsi = float(rsi) if pd.notna(rsi) else 10.0
        # rsi2=0 → 1.0; rsi2=10 → 0.0
        return max(0.0, min(1.0, (10.0 - rsi) / 10.0))
    # PB
    ext = row.get("sma20_ext")
    ext = abs(float(ext)) if pd.notna(ext) else 0.05
    near = max(0.0, 1.0 - min(ext / 0.03, 1.0))
    depth = row.get("pullback_depth_atr")
    depth = float(depth) if pd.notna(depth) else 0.0
    # favor 0.5–2.5 ATR pullbacks
    if depth <= 0:
        depth_score = 0.0
    elif depth < 0.5:
        depth_score = depth / 0.5
    elif depth <= 2.5:
        depth_score = 1.0
    else:
        depth_score = max(0.0, 1.0 - (depth - 2.5) / 2.0)
    return 0.6 * near + 0.4 * depth_score


def rank_key(row: pd.Series) -> tuple:
    """Lower tuple sorts first (higher priority)."""
    # negate quality so ascending sort = best first; tie-break ticker
    return (-quality_score(row), str(row.get("variant", "")), str(row["ticker"]))


def apply_portfolio(
    trades: pd.DataFrame,
    *,
    cfg: PortfolioConfig | None = None,
    candidates: pd.DataFrame | None = None,
    sector_map: dict[str, str] | None = None,
    variants: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select capacity-constrained trades.

    Returns
    -------
    selected : DataFrame
        Trades that received a slot (extra columns: sector, rank_in_day, selected).
    summary : DataFrame
        One-row (or per-variant) metrics including compound equity path stats.
    """
    cfg = cfg or PortfolioConfig()
    if trades is None or trades.empty:
        return pd.DataFrame(), pd.DataFrame()

    t = attach_rank_features(trades, candidates)
    if variants:
        t = t[t["variant"].isin(variants)].copy()
    if t.empty:
        return pd.DataFrame(), pd.DataFrame()

    smap = sector_map if sector_map is not None else load_sector_map()
    t["sector"] = t["ticker"].map(lambda x: smap.get(x, "UNKNOWN"))

    # Sort for greedy fill by entry date, then rank
    t = t.sort_values(["entry_date", "variant", "ticker"]).reset_index(drop=True)
    t["_rank_tuple"] = t.apply(rank_key, axis=1)

    open_pos: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    skipped = 0

    for entry_day, day_df in t.groupby("entry_date", sort=True):
        # free slots whose exit is strictly before this entry day
        open_pos = [p for p in open_pos if p["exit_date"] >= entry_day]
        free = cfg.max_positions - len(open_pos)
        if free <= 0:
            skipped += len(day_df)
            continue

        day = day_df.copy()
        if cfg.allocation == "mr_first":
            day = pd.concat(
                [
                    day[day.variant == "C1_MR"].sort_values("_rank_tuple"),
                    day[day.variant == "C1_PB"].sort_values("_rank_tuple"),
                    day[~day.variant.isin(["C1_MR", "C1_PB"])].sort_values("_rank_tuple"),
                ],
                ignore_index=True,
            )
        elif cfg.allocation == "pb_first":
            day = pd.concat(
                [
                    day[day.variant == "C1_PB"].sort_values("_rank_tuple"),
                    day[day.variant == "C1_MR"].sort_values("_rank_tuple"),
                    day[~day.variant.isin(["C1_MR", "C1_PB"])].sort_values("_rank_tuple"),
                ],
                ignore_index=True,
            )
        else:
            day = day.sort_values("_rank_tuple")

        # sector counts currently open
        sector_count: dict[str, int] = {}
        for p in open_pos:
            sector_count[p["sector"]] = sector_count.get(p["sector"], 0) + 1

        taken_today = 0
        for rank_i, (_, row) in enumerate(day.iterrows(), start=1):
            if taken_today >= free:
                skipped += 1
                continue
            # already in open ticker? (should be rare — backtest already one-per-ticker)
            if any(p["ticker"] == row["ticker"] for p in open_pos):
                skipped += 1
                continue
            sec = row["sector"]
            if (
                cfg.max_per_sector > 0
                and sector_count.get(sec, 0) >= cfg.max_per_sector
            ):
                skipped += 1
                continue

            rec = row.to_dict()
            rec["rank_in_day"] = rank_i
            rec["selected"] = True
            selected_rows.append(rec)
            open_pos.append(
                {
                    "ticker": row["ticker"],
                    "exit_date": row["exit_date"],
                    "sector": sec,
                }
            )
            sector_count[sec] = sector_count.get(sec, 0) + 1
            taken_today += 1

    if not selected_rows:
        empty = pd.DataFrame()
        summary = _summarize(empty, trades_in=len(t), skipped=skipped, cfg=cfg)
        return empty, summary

    selected = pd.DataFrame(selected_rows)
    # drop helper
    if "_rank_tuple" in selected.columns:
        selected = selected.drop(columns=["_rank_tuple"])
    selected = selected.sort_values(["entry_date", "variant", "ticker"]).reset_index(
        drop=True
    )
    summary = _summarize(selected, trades_in=len(t), skipped=skipped, cfg=cfg)
    logger.info(
        "portfolio: took %d / %d trades (skipped %d), max_pos=%d",
        len(selected),
        len(t),
        skipped,
        cfg.max_positions,
    )
    return selected, summary


def _equity_path(
    selected: pd.DataFrame,
    *,
    starting_equity: float,
    risk_frac: float,
) -> tuple[float, float, pd.Series]:
    if selected.empty:
        return starting_equity, 0.0, pd.Series(dtype=float)
    s = selected.sort_values(["exit_date", "ticker"])
    eq = starting_equity
    peak = eq
    max_dd = 0.0
    curve = []
    for _, row in s.iterrows():
        eq = eq + float(row["realized_r"]) * (eq * risk_frac)
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        curve.append(eq)
    return eq, max_dd, pd.Series(curve)


def _max_concurrent(selected: pd.DataFrame) -> int:
    if selected.empty:
        return 0
    events: list[tuple] = []
    for _, row in selected.iterrows():
        events.append((row["entry_date"], 1))
        # free the day after exit
        events.append((row["exit_date"], -1))  # same-day exit frees for next entry rules handled by >=
    # For concurrent count during hold: entry +1, day after exit -1
    events = []
    for _, row in selected.iterrows():
        events.append((pd.Timestamp(row["entry_date"]), +1))
        events.append((pd.Timestamp(row["exit_date"]) + pd.Timedelta(days=1), -1))
    events.sort(key=lambda x: (x[0], x[1]))
    cur = mx = 0
    for _, d in events:
        cur += d
        mx = max(mx, cur)
    return mx


def _summarize(
    selected: pd.DataFrame,
    *,
    trades_in: int,
    skipped: int,
    cfg: PortfolioConfig,
) -> pd.DataFrame:
    rows = []
    scopes: list[tuple[str, pd.DataFrame]] = [("ALL", selected)]
    if not selected.empty and "variant" in selected.columns:
        for v, g in selected.groupby("variant"):
            scopes.append((str(v), g))

    for name, g in scopes:
        n = len(g)
        if n == 0:
            rows.append(
                {
                    "scope": name,
                    "n_available": trades_in if name == "ALL" else n,
                    "n_selected": 0,
                    "n_skipped_pool": skipped if name == "ALL" else np.nan,
                    "win_rate": np.nan,
                    "avg_r": np.nan,
                    "median_r": np.nan,
                    "sum_r": 0.0,
                    "profit_factor": np.nan,
                    "end_equity": cfg.starting_equity,
                    "return_pct": 0.0,
                    "max_dd": 0.0,
                    "max_concurrent": 0,
                    "max_positions": cfg.max_positions,
                    "max_per_sector": cfg.max_per_sector,
                    "risk_frac": cfg.risk_frac,
                    "starting_equity": cfg.starting_equity,
                }
            )
            continue
        r = g["realized_r"].astype(float)
        wins = r > 0
        gw = r[r > 0].sum()
        gl = r[r <= 0].sum()
        pf = abs(gw / gl) if gl != 0 else np.nan
        end_eq, max_dd, _ = _equity_path(
            g, starting_equity=cfg.starting_equity, risk_frac=cfg.risk_frac
        )
        rows.append(
            {
                "scope": name,
                "n_available": trades_in if name == "ALL" else n,
                "n_selected": n,
                "n_skipped_pool": skipped if name == "ALL" else np.nan,
                "win_rate": float(wins.mean()),
                "avg_r": float(r.mean()),
                "median_r": float(r.median()),
                "sum_r": float(r.sum()),
                "profit_factor": float(pf) if pf == pf else np.nan,
                "avg_win_r": float(r[r > 0].mean()) if wins.any() else np.nan,
                "avg_loss_r": float(r[r <= 0].mean()) if (~wins).any() else np.nan,
                "end_equity": end_eq,
                "return_pct": end_eq / cfg.starting_equity - 1.0,
                "max_dd": max_dd,
                "max_concurrent": _max_concurrent(g),
                "max_positions": cfg.max_positions,
                "max_per_sector": cfg.max_per_sector,
                "risk_frac": cfg.risk_frac,
                "starting_equity": cfg.starting_equity,
            }
        )
    return pd.DataFrame(rows)
