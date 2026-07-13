"""Load daily OHLCV panels via trading.marketdata."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from trading.marketdata import fetch_bars

from trading.swing_screener.c1_pullback.indicators import enrich_daily

logger = logging.getLogger("trading.swing_screener.panel")
_NY = ZoneInfo("America/New_York")


def _ny_day(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=_NY)


def fetch_daily_enriched(
    ticker: str,
    start: date,
    end: date,
    *,
    adjustment: str = "split",
    force: bool = False,
) -> pd.DataFrame | None:
    """Fetch daily bars and attach C1 indicators. Returns None if empty."""
    df = fetch_bars(
        ticker,
        "1day",
        start=_ny_day(start, 0, 0),
        end=_ny_day(end, 23, 59),
        session="rth",
        adjustment=adjustment,
        force=force,
    )
    if df is None or df.empty:
        return None
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    if "close" not in out.columns or "volume" not in out.columns:
        return None
    # Ensure chronological index
    if not isinstance(out.index, pd.DatetimeIndex):
        if "timestamp" in out.columns:
            out = out.set_index("timestamp")
        else:
            return None
    out = out.sort_index()
    return enrich_daily(out)


def _worker_fetch(args: tuple) -> tuple[str, pd.DataFrame | None]:
    ticker, start, end, adjustment = args
    try:
        return ticker, fetch_daily_enriched(
            ticker, start, end, adjustment=adjustment
        )
    except Exception as e:  # noqa: BLE001 — isolate bad tickers
        logger.warning("fetch failed %s: %s", ticker, e)
        return ticker, None


def load_enriched_panel(
    tickers: Iterable[str],
    start: date,
    end: date,
    *,
    adjustment: str = "split",
    warmup_calendar_days: int = 400,
    workers: int = 1,
    progress_every: int = 100,
) -> dict[str, pd.DataFrame]:
    """Prefetch enriched daily frames for many tickers.

    Warmup is applied by starting fetches ``warmup_calendar_days`` before
    ``start`` so SMA200 is available inside the scan window.
    """
    tickers = [str(t).upper() for t in tickers]
    fetch_start = start - timedelta(days=warmup_calendar_days)
    payload = [(t, fetch_start, end, adjustment) for t in tickers]
    result: dict[str, pd.DataFrame] = {}

    if workers <= 1:
        for i, args in enumerate(payload, 1):
            t, df = _worker_fetch(args)
            if df is not None and not df.empty:
                result[t] = df
            if progress_every and i % progress_every == 0:
                logger.info("loaded %d/%d tickers (%d ok)", i, len(payload), len(result))
        return result

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_worker_fetch, a): a[0] for a in payload}
        done = 0
        for fut in as_completed(futs):
            done += 1
            t, df = fut.result()
            if df is not None and not df.empty:
                result[t] = df
            if progress_every and done % progress_every == 0:
                logger.info(
                    "loaded %d/%d tickers (%d ok)", done, len(payload), len(result)
                )
    return result
