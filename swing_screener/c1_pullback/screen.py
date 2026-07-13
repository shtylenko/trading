"""Historical C1_PULLBACK candidate scan."""

from __future__ import annotations

import logging
from datetime import date
from typing import Iterable, Sequence

import pandas as pd

from trading.swing_screener.c1_pullback.rules import (
    C1Config,
    extract_hits,
    mr_mask,
    pb_mask,
)
from trading.swing_screener.c1_pullback.universe import ticker_union
from trading.swing_screener.data.panel import load_enriched_panel

logger = logging.getLogger("trading.swing_screener.c1_pullback.screen")

VARIANTS_ALL = ("C1_MR", "C1_PB")


def _normalize_variants(variant: str | Sequence[str]) -> list[str]:
    if isinstance(variant, str):
        v = variant.strip().upper()
        if v in ("BOTH", "ALL"):
            return list(VARIANTS_ALL)
        if v in VARIANTS_ALL:
            return [v]
        # allow mr / pb shortcuts
        if v in ("MR", "C1-MR"):
            return ["C1_MR"]
        if v in ("PB", "C1-PB"):
            return ["C1_PB"]
        raise ValueError(f"Unknown variant: {variant}")
    out = []
    for item in variant:
        out.extend(_normalize_variants(item))
    # preserve order, unique
    seen = set()
    ordered = []
    for x in out:
        if x not in seen:
            seen.add(x)
            ordered.append(x)
    return ordered


def _date_index_ny(df: pd.DataFrame) -> pd.Series:
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        return idx.tz_convert("America/New_York").normalize().tz_localize(None)
    return pd.Series(idx.normalize(), index=df.index)


def screen_ticker(
    ticker: str,
    df: pd.DataFrame,
    cfg: C1Config,
    *,
    start: date,
    end: date,
    variants: Sequence[str],
    membership: dict[date, frozenset[str]] | None = None,
) -> pd.DataFrame:
    """Apply C1 masks to one enriched frame; optional PIT membership filter."""
    if df is None or df.empty:
        return pd.DataFrame()

    # Restrict membership per row when snapshot map provided
    if membership is not None:
        asof = _date_index_ny(df)
        # map each row date to membership — use last snapshot <= date
        # Precompute sorted snapshot dates
        snap_dates = sorted(membership.keys())
        if not snap_dates:
            return pd.DataFrame()
        member_flags = []
        for d in asof:
            d_date = d.date() if hasattr(d, "date") else pd.Timestamp(d).date()
            # binary search last snap <= d_date
            lo, hi = 0, len(snap_dates) - 1
            chosen = None
            while lo <= hi:
                mid = (lo + hi) // 2
                if snap_dates[mid] <= d_date:
                    chosen = snap_dates[mid]
                    lo = mid + 1
                else:
                    hi = mid - 1
            if chosen is None:
                member_flags.append(False)
            else:
                member_flags.append(ticker.upper() in membership[chosen])
        in_univ = pd.Series(member_flags, index=df.index)
    else:
        in_univ = pd.Series(True, index=df.index)

    frames: list[pd.DataFrame] = []
    for variant in variants:
        if variant == "C1_MR":
            mask = mr_mask(df, cfg) & in_univ
        elif variant == "C1_PB":
            mask = pb_mask(df, cfg) & in_univ
        else:
            raise ValueError(variant)
        hits = extract_hits(
            df,
            mask,
            ticker=ticker,
            variant=variant,
            universe=cfg.universe,
            rules_version=cfg.rules_version,
            start=pd.Timestamp(start),
            end=pd.Timestamp(end),
        )
        if not hits.empty:
            frames.append(hits)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _build_membership_map(
    universe: str, start: date, end: date
) -> dict[date, frozenset[str]]:
    """Snapshot effective_date → members, for dates we need."""
    from trading.swing_screener.c1_pullback.universe import _snapshot_table

    snaps = _snapshot_table(universe)
    # keep snaps that could apply during window (plus previous for continuity)
    relevant = [s for s in snaps if s[0] <= end]
    return {ed: members for ed, members in relevant}


def run_screen(
    *,
    start: date,
    end: date,
    cfg: C1Config,
    variant: str | Sequence[str] = "both",
    tickers: Iterable[str] | None = None,
    max_tickers: int | None = None,
    workers: int = 1,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Run full historical C1 candidate screen."""
    if end < start:
        raise ValueError("end must be >= start")
    variants = _normalize_variants(variant)

    if tickers is None:
        tickers_list = ticker_union(cfg.universe, start, end)
    else:
        tickers_list = [str(t).upper() for t in tickers]
    if max_tickers is not None:
        tickers_list = tickers_list[: int(max_tickers)]

    logger.info(
        "C1 screen %s..%s variants=%s universe=%s tickers=%d",
        start,
        end,
        variants,
        cfg.universe,
        len(tickers_list),
    )

    panel = load_enriched_panel(
        tickers_list,
        start,
        end,
        adjustment=cfg.adjustment,
        warmup_calendar_days=cfg.warmup_calendar_days,
        workers=workers,
        progress_every=progress_every,
    )
    logger.info("enriched panel ready: %d tickers with data", len(panel))

    membership = _build_membership_map(cfg.universe, start, end)
    frames: list[pd.DataFrame] = []
    for i, (ticker, df) in enumerate(panel.items(), 1):
        hits = screen_ticker(
            ticker,
            df,
            cfg,
            start=start,
            end=end,
            variants=variants,
            membership=membership if tickers is None else None,
        )
        # If user passed explicit tickers, skip PIT filter (debug mode)
        if not hits.empty:
            frames.append(hits)
        if progress_every and i % progress_every == 0:
            logger.info("screened %d/%d tickers", i, len(panel))

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["asof_date", "variant", "ticker"]).reset_index(drop=True)
    logger.info("total candidate rows: %d", len(out))
    return out
