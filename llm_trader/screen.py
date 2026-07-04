"""A1 — daily gap pre-screen.

For each ticker and trading day in the window, compute the daily-bar Pillars
(gap %, price band, average volume, relative volume) and keep the day-ticker
pairs that pass. This narrows ~4,950 symbols to a small set of gappers per day,
which Stage B then inspects intraday.

Source: ``trading.marketdata.fetch_bars(..., "1day", adjustment="split")``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from trading.marketdata import fetch_bars

from .config import ScanConfig


@dataclass
class GapCandidate:
    ticker: str
    day: date
    open_px: float
    prior_close: float
    gap_pct: float
    rvol: float
    avg_vol: float
    day_volume: float


def screen_ticker(ticker: str, cfg: ScanConfig) -> list[GapCandidate]:
    """Return all gap-up candidates for one ticker across the window.

    Pulls daily bars with ``rvol_lookback`` days of warm-up before ``start`` so
    the relative-volume baseline is defined from the first scan day.
    """
    warmup = cfg.rvol_lookback + 10
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=warmup * 2  # calendar pad for weekends/holidays
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)

    # RAW prices so the gap/price band match the *actual* prices the trader (and
    # the raw intraday detector in Stage B) would see — split-adjusted daily would
    # rescale reverse-split penny names out of the band. The gap_max_pct guard
    # below drops the split-day false gaps that raw prices can otherwise produce.
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty or len(df) < cfg.rvol_lookback + 2:
        return []

    df = df.sort_index()
    prior_close = df["close"].shift(1)
    # average volume of the trailing `rvol_lookback` days, excluding today
    avg_vol = df["volume"].shift(1).rolling(cfg.rvol_lookback).mean()

    gap_pct = (df["open"] - prior_close) / prior_close * 100.0
    rvol = df["volume"] / avg_vol

    out: list[GapCandidate] = []
    for ts, row in df.iterrows():
        d = ts.date()
        if d < cfg.start or d > cfg.end:
            continue
        pc = prior_close.loc[ts]
        av = avg_vol.loc[ts]
        if pd.isna(pc) or pd.isna(av) or av <= 0:
            continue
        g = float(gap_pct.loc[ts])
        rv = float(rvol.loc[ts])
        op = float(row["open"])
        if g < cfg.gap_min_pct or g > cfg.gap_max_pct:
            continue
        if not (cfg.price_min <= op <= cfg.price_max):
            continue
        if av < cfg.avg_vol_min:
            continue
        if rv < cfg.rvol_min:
            continue
        out.append(
            GapCandidate(
                ticker=ticker.upper(),
                day=d,
                open_px=op,
                prior_close=float(pc),
                gap_pct=g,
                rvol=rv,
                avg_vol=float(av),
                day_volume=float(row["volume"]),
            )
        )
    return out
