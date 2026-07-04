from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trading.marketdata import fetch_bars

from trading.lab.core.time_utils import ensure_ny_index, ny_dt


def _normalize_columns(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    return ensure_ny_index(out)


def fetch_intraday_day(
    ticker: str,
    trade_date: date,
    timeframe: str = "5min",
    session: str = "rth",
    force: bool = False,
) -> pd.DataFrame | None:
    if session == "extended":
        start = ny_dt(trade_date, 4, 0)
    else:
        start = ny_dt(trade_date, 9, 30)
    end = ny_dt(trade_date, 16, 0)
    return _normalize_columns(
        fetch_bars(
            ticker,
            timeframe,
            start=start,
            end=end,
            session=session,
            adjustment="raw",
            force=force,
        )
    )


def fetch_intraday_range(
    ticker: str,
    start_date: date,
    end_date: date,
    timeframe: str = "5min",
    session: str = "rth",
    force: bool = False,
) -> pd.DataFrame | None:
    if session == "extended":
        start = ny_dt(start_date, 4, 0)
    else:
        start = ny_dt(start_date, 9, 30)
    end = ny_dt(end_date, 16, 0)
    return _normalize_columns(
        fetch_bars(
            ticker,
            timeframe,
            start=start,
            end=end,
            session=session,
            adjustment="raw",
            force=force,
        )
    )


def fetch_daily_range(
    ticker: str,
    start_date: date,
    end_date: date,
    force: bool = False,
    adjustment: str = "raw",
) -> pd.DataFrame | None:
    """Daily bars for an explicit date range (used for bulk prefetching).

    Populates the same cache that ``fetch_daily_context`` reads from, so a
    single ranged call per ticker makes all subsequent per-day context
    fetches cache-only.
    """
    start = ny_dt(start_date, 0, 0)
    end = ny_dt(end_date, 23, 59)
    return _normalize_columns(
        fetch_bars(
            ticker,
            "1day",
            start=start,
            end=end,
            session="rth",
            adjustment=adjustment,
            force=force,
        )
    )


def fetch_daily_context(
    ticker: str,
    trade_date: date,
    lookback_days: int = 40,
    force: bool = False,
    adjustment: str = "raw",
) -> pd.DataFrame | None:
    """Daily bars strictly before *trade_date*.

    Defaults to RAW (unadjusted) prices: intraday bars are raw, and
    split-adjusted daily data is rescaled by providers to the run date's
    scale — mixing the two misprices ATR stops, gaps, and price filters for
    any ticker that split between trade_date and the present, and makes
    backtest results depend on when they were run. Strategies must guard
    against split-day jumps inside their trailing windows instead (see
    ``research.filters.has_split_like_jump``).
    """
    start = ny_dt(trade_date - timedelta(days=lookback_days), 0, 0)
    end = ny_dt(trade_date - timedelta(days=1), 23, 59)
    return _normalize_columns(
        fetch_bars(
            ticker,
            "1day",
            start=start,
            end=end,
            session="rth",
            adjustment=adjustment,
            force=force,
        )
    )
