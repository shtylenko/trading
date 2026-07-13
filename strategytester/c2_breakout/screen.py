"""Historical C2_BREAKOUT candidate scan."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable

import pandas as pd

from trading.swing_screener.c1_pullback.indicators import performance
from trading.swing_screener.c1_pullback.universe import ticker_union
from trading.swing_screener.c2_breakout.indicators import enrich_c2
from trading.swing_screener.c2_breakout.rules import C2Config, c2_mask, extract_hits
from trading.swing_screener.data.panel import load_enriched_panel

logger = logging.getLogger("trading.swing_screener.c2_breakout.screen")


def _load_spy_perf_21d(start: date, end: date, warmup_days: int, adjustment: str) -> pd.Series:
    """SPY 21d performance series for RS filter."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from trading.marketdata import fetch_bars

    ny = ZoneInfo("America/New_York")
    fetch_start = start - timedelta(days=warmup_days)
    df = fetch_bars(
        "SPY",
        "1day",
        start=datetime(fetch_start.year, fetch_start.month, fetch_start.day, tzinfo=ny),
        end=datetime(end.year, end.month, end.day, 23, 59, tzinfo=ny),
        session="rth",
        adjustment=adjustment,
    )
    if df is None or df.empty:
        logger.warning("SPY daily unavailable — RS filter will fail closed if required")
        return pd.Series(dtype=float)
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    if not isinstance(out.index, pd.DatetimeIndex):
        if "timestamp" in out.columns:
            out = out.set_index("timestamp")
        else:
            return pd.Series(dtype=float)
    out = out.sort_index()
    close = out["close"].astype(float)
    perf = performance(close, 21)
    idx = pd.to_datetime(perf.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    perf.index = idx.normalize()
    return perf


def _membership_map(universe: str, end: date) -> dict[date, frozenset[str]]:
    from trading.swing_screener.c1_pullback.universe import _snapshot_table

    snaps = _snapshot_table(universe)
    return {ed: members for ed, members in snaps if ed <= end}


def _enrich_ticker(
    ticker: str,
    raw: pd.DataFrame,
    cfg: C2Config,
    spy_perf: pd.Series,
) -> pd.DataFrame | None:
    if raw is None or raw.empty:
        return None
    # strip c1 structure-only extras not needed — enrich_c2 starts from OHLCV
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in raw.columns]
    base = raw[cols].copy()
    return enrich_c2(base, base_lookback=cfg.base_lookback, spy_perf_21d=spy_perf)


def run_screen(
    *,
    start: date,
    end: date,
    cfg: C2Config,
    tickers: Iterable[str] | None = None,
    max_tickers: int | None = None,
    workers: int = 1,
    progress_every: int = 50,
) -> pd.DataFrame:
    if end < start:
        raise ValueError("end must be >= start")

    if tickers is None:
        tickers_list = ticker_union(cfg.universe, start, end)
    else:
        tickers_list = [str(t).upper() for t in tickers]
    if max_tickers is not None:
        tickers_list = tickers_list[: int(max_tickers)]

    logger.info(
        "C2 screen %s..%s universe=%s tickers=%d",
        start,
        end,
        cfg.universe,
        len(tickers_list),
    )

    spy_perf = _load_spy_perf_21d(start, end, cfg.warmup_calendar_days, cfg.adjustment)

    # Load panel with standard enrich, then re-enrich for C2 (cheaper than custom path)
    # Actually load_enriched_panel uses enrich_daily which includes structure — OK but heavy.
    # Use fetch via load_enriched_panel then re-run enrich_c2 from OHLCV columns.
    panel_raw = load_enriched_panel(
        tickers_list,
        start,
        end,
        adjustment=cfg.adjustment,
        warmup_calendar_days=cfg.warmup_calendar_days,
        workers=workers,
        progress_every=progress_every,
    )
    logger.info("panel loaded: %d tickers", len(panel_raw))

    membership = _membership_map(cfg.universe, end) if tickers is None else None
    frames: list[pd.DataFrame] = []

    for i, (ticker, raw) in enumerate(panel_raw.items(), 1):
        df = _enrich_ticker(ticker, raw, cfg, spy_perf)
        if df is None or df.empty:
            continue
        mask = c2_mask(df, cfg)
        if membership is not None:
            # membership by asof date
            idx = pd.to_datetime(df.index)
            if getattr(idx, "tz", None) is not None:
                dates = idx.tz_convert("America/New_York").normalize().tz_localize(None)
            else:
                dates = idx.normalize()
            snap_dates = sorted(membership.keys())
            flags = []
            for d in dates:
                d_date = pd.Timestamp(d).date()
                chosen = None
                lo, hi = 0, len(snap_dates) - 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if snap_dates[mid] <= d_date:
                        chosen = snap_dates[mid]
                        lo = mid + 1
                    else:
                        hi = mid - 1
                flags.append(
                    chosen is not None and ticker.upper() in membership[chosen]
                )
            mask = mask & pd.Series(flags, index=df.index)

        hits = extract_hits(
            df,
            mask,
            ticker=ticker,
            cfg=cfg,
            start=pd.Timestamp(start),
            end=pd.Timestamp(end),
        )
        if not hits.empty:
            frames.append(hits)
        if progress_every and i % progress_every == 0:
            logger.info("screened %d/%d", i, len(panel_raw))

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["asof_date", "ticker"]).reset_index(drop=True)
    logger.info("total C2 candidates: %d", len(out))
    return out
