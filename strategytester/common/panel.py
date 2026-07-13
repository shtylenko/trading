"""Daily panel loader (cached) + market-context series.

Loads daily bars via ``trading.marketdata``, enriches with
``common.indicators.enrich``, and caches the full enriched panel to a single
parquet so all 13 strategies reuse one build.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.marketdata import fetch_bars

from trading.strategytester.common.indicators import enrich, ema, sma

logger = logging.getLogger("strategytester.common.panel")
_NY = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).resolve().parent.parent / "outputs" / "_panel_cache"


def _ny(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=_NY)


def _norm_index(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df = df.copy()
    df.index = idx.normalize()
    return df.sort_index()


def fetch_daily(ticker: str, start: date, end: date, *, adjustment: str = "split") -> pd.DataFrame | None:
    df = fetch_bars(
        ticker, "1day", start=_ny(start, 0), end=_ny(end, 23, 59),
        session="rth", adjustment=adjustment,
    )
    if df is None or df.empty:
        return None
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    need = {"open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        return None
    return _norm_index(df[list(need)])


def build_panel(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_key: str,
    adjustment: str = "split",
    warmup_days: int = 420,
    force: bool = False,
) -> dict[str, pd.DataFrame]:
    """Return {ticker: enriched daily frame} for [start-warmup, end].

    Caches the concatenated long panel to parquet under CACHE_DIR/<cache_key>.parquet.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{cache_key}.parquet"
    if cache_path.exists() and not force:
        logger.info("panel cache hit %s", cache_path.name)
        long = pd.read_parquet(cache_path)
        out: dict[str, pd.DataFrame] = {}
        for t, g in long.groupby("ticker", sort=False):
            g = g.drop(columns=["ticker"]).set_index("date").sort_index()
            out[str(t)] = g
        return out

    fetch_start = start - timedelta(days=warmup_days)
    frames: list[pd.DataFrame] = []
    result: dict[str, pd.DataFrame] = {}
    n_ok = 0
    for i, t in enumerate(tickers, 1):
        try:
            raw = fetch_daily(t, fetch_start, end, adjustment=adjustment)
        except Exception as e:  # noqa: BLE001
            logger.warning("fetch fail %s: %s", t, e)
            raw = None
        if raw is None or len(raw) < 60:
            continue
        en = enrich(raw)
        result[t] = en
        g = en.copy()
        g.insert(0, "ticker", t)
        g = g.reset_index().rename(columns={"index": "date", "timestamp": "date"})
        if "date" not in g.columns:
            g = g.rename(columns={g.columns[1]: "date"})
        frames.append(g)
        n_ok += 1
        if i % 200 == 0:
            logger.info("panel %d/%d (%d ok)", i, len(tickers), n_ok)
    if frames:
        long = pd.concat(frames, ignore_index=True)
        long.to_parquet(cache_path, index=False)
        logger.info("panel cached %s (%d tickers, %d rows)", cache_path.name, n_ok, len(long))
    return result


def market_context(start: date, end: date, *, warmup_days: int = 60) -> pd.DataFrame:
    """SPY/QQQ trend flags + VIX + a battery of regime filters (all causal).

    Regime columns (bool, known at that day's close): spy_bull (10>20 EMA),
    spy_above_200 / _100 / _50, spy_50_200 (golden cross), spy_dd_ok (within 8%
    of the trailing 63d high), vix_lt20 / vix_lt25, plus combos.
    """
    fs = start - timedelta(days=warmup_days + 320)
    spy = fetch_daily("SPY", fs, end)
    qqq = fetch_daily("QQQ", fs, end)
    vix = fetch_daily("^VIX", fs, end)
    c = spy["close"]
    ctx = pd.DataFrame(index=spy.index)
    ctx["spy_close"] = c
    ctx["spy_ema10"] = ema(c, 10)
    ctx["spy_ema20"] = ema(c, 20)
    ctx["spy_bull"] = ctx["spy_ema10"] > ctx["spy_ema20"]
    ctx["spy_above_sma50"] = c > sma(c, 50)
    ctx["spy_above_100"] = c > sma(c, 100)
    ctx["spy_above_200"] = c > sma(c, 200)
    ctx["spy_50_200"] = sma(c, 50) > sma(c, 200)
    ctx["spy_dd_ok"] = c > 0.92 * c.rolling(63, min_periods=40).max()
    # combos
    ctx["reg_bull_200"] = ctx["spy_bull"] & ctx["spy_above_200"]
    ctx["reg_50_200"] = ctx["spy_bull"] & ctx["spy_50_200"]
    ctx["reg_dd_bull"] = ctx["spy_bull"] & ctx["spy_dd_ok"]
    if qqq is not None:
        q = qqq["close"].reindex(ctx.index)
        ctx["qqq_bull"] = ema(q, 10) > ema(q, 20)
    if vix is not None:
        ctx["vix"] = vix["close"].reindex(ctx.index)
        ctx["vix_ma10"] = sma(ctx["vix"], 10)
        ctx["vix_lt20"] = ctx["vix"] < 20.0
        ctx["vix_lt25"] = ctx["vix"] < 25.0
        ctx["reg_bull_vix25"] = ctx["spy_bull"] & ctx["vix_lt25"]
    return ctx
