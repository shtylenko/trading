"""Main entry point — orchestrates caching, provider routing, and storage.

The primary public function is ``fetch_bars()``, which implements the
three-phase check-cache → fetch-from-providers → store-and-return
pipeline.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from .calendar import (
    CalendarError,
    coverage_gaps,
    expected_bars,
    session_close_utc,
    trading_days_in_range,
)
from .config import (
    SUPPORTED_TIMEFRAMES,
    Timeframe,
    COMPLETENESS_TOLERANCE_1MIN_RTH,
    COMPLETENESS_TOLERANCE_DEFAULT,
)
from .errors import ConnectionTimeoutError
from .locks import dataset_lock
from .provider import (
    get_providers_for_timeframe,
    register_provider,
)
from .providers import AlpacaProvider, MarketDataProvider, YFinanceProvider
from .storage import (
    get_negative_cache,
    get_partition_paths,
    read_bars,
    read_meta,
    resolve_path,
    update_meta_coverage_bulk,
    update_meta_summary,
    write_bars,
    write_negative_cache_bulk,
)
from .ttl import is_negative_cache_expired, is_stale

logger = logging.getLogger("strategy_lab.marketdata.fetcher")

# ── Auto-register providers on first import ───────────────────────────────────

_REGISTERED = False
_REGISTER_LOCK = threading.Lock()


def _ensure_providers():
    global _REGISTERED
    if _REGISTERED:
        return
    with _REGISTER_LOCK:
        _ensure_providers_locked()


def _ensure_providers_locked():
    global _REGISTERED
    if _REGISTERED:
        return
    # MARKETDATA_PROVIDERS=alpaca (comma-separated) restricts the chain.
    # Bulk prefetches over broad universes use this to skip the slow
    # gap-fill fallthrough: thin tickers miss expected bars on every date
    # (minutes with no trades), which otherwise re-queries the full range
    # from every lower-priority provider per ticker.
    allowed_env = os.getenv("MARKETDATA_PROVIDERS", "").strip()
    allowed = {p.strip().lower() for p in allowed_env.split(",") if p.strip()} or None

    def _allowed(name: str) -> bool:
        return allowed is None or name in allowed

    if _allowed("alpaca"):
        try:
            register_provider(AlpacaProvider())
        except (RuntimeError, ImportError) as e:
            logger.info("Alpaca provider not available: %s", e)
    if _allowed("marketdata"):
        try:
            register_provider(MarketDataProvider())
        except Exception as e:
            logger.info("MarketData provider not available: %s", e)
    if _allowed("yfinance"):
        try:
            register_provider(YFinanceProvider())
        except Exception as e:
            logger.info("YFinance provider not available: %s", e)
    if allowed is not None:
        logger.info("Provider chain restricted to: %s", sorted(allowed))
    _REGISTERED = True


# ── Core entry point ──────────────────────────────────────────────────────────


def fetch_bars(
    ticker: str,
    timeframe: str | Timeframe,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    session: str = "rth",
    adjustment: Optional[str] = None,
    tz: str = "America/New_York",
    force: bool = False,
) -> pd.DataFrame | None:
    """Fetch OHLCV bars for a single ticker.

    Three-phase pipeline:

    1. **Check cache** — reads the Hive-partitioned Parquet cache, checks
       TTL and coverage.  Returns cached data if it's fresh and complete.

    2. **Fetch** — iterates providers by priority.  Each provider receives
       only the date ranges still missing.  Provider-empty responses on
       trading dates are written as 24-hour negative cache entries.

    3. **Store + return** — merges new data into the Parquet cache, updates
       the per-dataset ``meta.json`` sidecar, and returns the combined data.

    Parameters
    ----------
    ticker : str
        Stock symbol (e.g. ``\"AAPL\"``).
    timeframe : str or Timeframe
        One of ``\"1min\"``, ``\"5min\"``, ``\"15min\"``, ``\"1day\"``.
    start : datetime, optional
        Start of range (inclusive).  If None, defaults to
        ``end - Timeframe(timeframe).lookback_days_default``.
    end : datetime, optional
        End of range (inclusive).  If None, defaults to now (UTC).
    session : str
        ``\"rth\"`` (regular hours) or ``\"extended\"`` (premarket + RTH).
    adjustment : str, optional
        ``\"raw\"``, ``\"split\"``, or ``\"all\"``.  Defaults to ``\"raw\"``
        for intraday timeframes, ``\"split\"`` for ``\"1day\"``.
    tz : str
        Return timezone for the DatetimeIndex (default America/New_York).
    force : bool
        If True, bypass all freshness checks and re-fetch from providers.

    Returns
    -------
    pd.DataFrame or None
        OHLCV DataFrame with a ``DatetimeIndex`` named ``\"timestamp\"``
        in the requested timezone.  ``None`` if all providers failed.

    Raises
    ------
    ValueError
        If ``timeframe``, ``session``, or ``adjustment`` is unsupported.
    """
    _ensure_providers()

    # ── Normalize parameters ──────────────────────────────────────────────
    if isinstance(timeframe, Timeframe):
        timeframe = timeframe.value
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}. "
                         f"Supported: {SUPPORTED_TIMEFRAMES}")

    if session not in ("rth", "extended"):
        raise ValueError(f"Unsupported session: {session}")
    if adjustment is None:
        adjustment = "raw"
    if adjustment not in ("raw", "split", "all"):
        raise ValueError(f"Unsupported adjustment: {adjustment}")

    if end is None:
        end = datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start is None:
        start = end - timedelta(days=Timeframe(timeframe).lookback_days_default)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    # Guard: if the range contains NO trading days, short-circuit
    if not _range_has_any_trading_days(start, end):
        logger.debug("%s %s–%s: no trading days in range — returning None",
                     ticker, start.date(), end.date())
        return None

    # ── Phase 1: Check cache (with lock) ──────────────────────────────────
    if not force:
        with dataset_lock(ticker, timeframe, session, adjustment):
            cached = _get_cached_data(ticker, timeframe, start, end, session, adjustment, tz)
            if cached is not None:
                return cached

    # Note: Phase 1 lock is released before Phase 2 begins, introducing a brief TOCTOU window.
    # Under high multi-threaded concurrency, two threads might both check cache, miss, and redundantly
    # fetch/write the same dataset. This is acceptable as the final `write_bars(..., merge=True)` handles
    # deduplication and safely merges new rows, preventing duplicate records. Keep these phases decoupled
    # to avoid holding lock during slow network requests.

    # ── Phase 2: Fetch from providers ────────────────────────────────
    providers = get_providers_for_timeframe(timeframe, session=session, adjustment=adjustment)
    if not providers:
        logger.error("No providers available for %s/%s/%s", timeframe, session, adjustment)
        return None

    # Track coverage gaps per trading date. Trading days are NY dates —
    # enumerating from UTC .date() would include the next NY day for any
    # evening request and poison the negative cache with days that have
    # no data yet.
    _tz_ny = "America/New_York"
    trading_dates = trading_days_in_range(
        start.astimezone(ZoneInfo(_tz_ny)).date(),
        end.astimezone(ZoneInfo(_tz_ny)).date(),
    )

    with dataset_lock(ticker, timeframe, session, adjustment):
        missing_dates = _find_missing_dates(ticker, timeframe, session, adjustment,
                                             trading_dates, start, end,
                                             ignore_complete=force,
                                             ignore_negative_cache=force)

    all_new_data: list[pd.DataFrame] = []
    contributing_providers: list[str] = []
    remaining_dates = list(missing_dates)
    accumulated_new = pd.DataFrame()
    # True once at least one provider responded successfully (even with no
    # data). Distinguishes "providers confirmed empty" from "providers all
    # errored" so transient outages don't poison the negative cache.
    any_provider_responded = False
    # Dates whose most recent provider attempt errored — these get the
    # short-TTL "provider_error" entry, never the 24h "provider_empty".
    errored_dates: set = set()
    # Connection timeout aborts the whole fetch, but only after Phase 3 has
    # stored whatever was fetched before the outage.
    timeout_exc: ConnectionTimeoutError | None = None

    def _absorb_new_data(provider_df: pd.DataFrame, provider_name: str) -> None:
        nonlocal accumulated_new
        provider_df = provider_df.copy()
        provider_df["provider"] = provider_name
        all_new_data.append(provider_df)
        if provider_name not in contributing_providers:
            contributing_providers.append(provider_name)
        accumulated_new = pd.concat([accumulated_new, provider_df]).sort_index()
        accumulated_new = accumulated_new[
            ~accumulated_new.index.duplicated(keep="first")
        ]

    for provider in providers:
        if not remaining_dates or timeout_exc is not None:
            break

        provider_errored = False
        # Group the missing dates into contiguous runs so a request for
        # {Jan 2, Dec 30} doesn't refetch the entire cached year in between.
        for run_dates in _contiguous_date_runs(remaining_dates):
            miss_start = datetime(
                run_dates[0].year, run_dates[0].month, run_dates[0].day,
                tzinfo=ZoneInfo(_tz_ny),
            )
            miss_end = datetime(
                run_dates[-1].year, run_dates[-1].month, run_dates[-1].day,
                23, 59, 59, tzinfo=ZoneInfo(_tz_ny),
            )
            # Clamp to [start, end]
            fetch_start = max(miss_start, start)
            fetch_end = min(miss_end, end)
            provider_fetch_end = (
                fetch_end + timedelta(days=1)
                if timeframe == "1day"
                else fetch_end
            )

            logger.info("[%s] Fetching %s %s–%s from %s",
                        ticker, timeframe, fetch_start.date(), fetch_end.date(),
                        provider.capabilities.name)

            try:
                provider_df = provider.fetch_bars(
                    ticker, timeframe, fetch_start, provider_fetch_end,
                    session=session, adjustment=adjustment,
                )
            except ConnectionTimeoutError as e:
                timeout_exc = e
                provider_errored = True
                errored_dates.update(run_dates)
                break
            except Exception as e:
                logger.warning("[%s] %s: %s", provider.capabilities.name, ticker, e)
                provider_errored = True
                errored_dates.update(run_dates)
                # PartialDataError carries the bars fetched before the
                # failure — store them, but keep the dates marked errored.
                partial_df = getattr(e, "df", None)
                if partial_df is not None and not partial_df.empty:
                    _absorb_new_data(partial_df, provider.capabilities.name)
                continue

            any_provider_responded = True
            errored_dates.difference_update(run_dates)
            if provider_df is not None and not provider_df.empty:
                _absorb_new_data(provider_df, provider.capabilities.name)

        # Mark only fully covered dates as filled. A provider that
        # returns one bar for a date should not prevent lower-priority
        # providers from filling missing bars on that same date.
        if not accumulated_new.empty:
            remaining_dates = _dates_with_gaps(
                accumulated_new.index,
                timeframe,
                remaining_dates,
                start,
                end,
                session,
            )

        # An authoritative provider (full consolidated tape) that answered
        # without errors has given the final word: bars still "missing" are
        # no-trade minutes on thin tickers, and chasing them through
        # lower-priority providers re-fetches the whole range for nothing.
        # Break instead of clearing remaining_dates: the dates fall through
        # to the negative-cache step below as confirmed "provider_empty",
        # so subsequent runs don't re-probe them either.
        if provider.capabilities.authoritative and not provider_errored:
            if remaining_dates:
                logger.debug(
                    "[%s] %s: %d dates below coverage after authoritative "
                    "provider %s — accepting as final (no fallthrough)",
                    ticker, timeframe, len(remaining_dates),
                    provider.capabilities.name,
                )
            break

    # Negative-cache the dates we could not fill. Dates whose absence was
    # confirmed by a responding provider get "provider_empty" (24h TTL);
    # dates whose last attempt errored get "provider_error" (15 min TTL) so
    # a transient failure doesn't black out the dataset for a day. Days
    # whose session has not finished yet (plus a publication grace period)
    # are never negative-cached — "no data yet" is not "no data".
    if remaining_dates and timeout_exc is None:
        now_utc = datetime.now(timezone.utc)
        reasons_by_date: dict[str, str] = {}
        for d in remaining_dates:
            try:
                close_utc = session_close_utc(d)
            except CalendarError:
                continue
            if now_utc < close_utc + timedelta(hours=1):
                continue  # session still open / just closed — retry later
            if d in errored_dates or not any_provider_responded:
                reasons_by_date[d.isoformat()] = "provider_error"
            else:
                reasons_by_date[d.isoformat()] = "provider_empty"
        if reasons_by_date:
            with dataset_lock(ticker, timeframe, session, adjustment):
                write_negative_cache_bulk(
                    ticker, timeframe, session, adjustment, reasons_by_date,
                )

    # ── Phase 3: Store and return ─────────────────────────────────────
    with dataset_lock(ticker, timeframe, session, adjustment):
        if all_new_data:
            combined_new = pd.concat(all_new_data)
            combined_new = combined_new[~combined_new.index.duplicated(keep="first")]
            combined_new = combined_new.sort_index()

            provider_name = contributing_providers[0] if contributing_providers else "unknown"

            rows = write_bars(
                ticker, timeframe, combined_new,
                session=session, adjustment=adjustment,
                provider_name=provider_name,
                merge=True,
            )
            logger.info("[Cache WRITE] %s %s: %d rows stored", ticker, timeframe, rows)

            # Update coverage (reads all bars once, bins by date) and
            # bump the 'latest' timestamp in meta.json for fast TTL checks.
            _update_sidecar_coverage(ticker, timeframe, session, adjustment, trading_dates)

        # A connection timeout aborts the fetch — but only after the data
        # fetched before the outage was stored above, so the retry after
        # connectivity returns doesn't refetch it.
        if timeout_exc is not None:
            raise timeout_exc

        # Read final result (cache should now be populated)
        result = read_bars(
            ticker, timeframe, start=start, end=end,
            session=session, adjustment=adjustment, tz=tz,
        )
        if result.empty:
            return None
        return result


def active_negative_cache(neg_cache: dict[str, dict]) -> dict[str, dict]:
    """Filter out expired negative cache entries."""
    return {
        k: v for k, v in neg_cache.items()
        if not is_negative_cache_expired(v, date_key=k)
    }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _get_cached_data(
    ticker: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
    adjustment: str,
    tz: str,
) -> pd.DataFrame | None:
    """Read from Parquet cache if fresh and covering expected bars.

    Returns None if cache is stale, missing, or has coverage gaps.
    """
    partition_paths = get_partition_paths(ticker, timeframe, start, end,
                                           session=session, adjustment=adjustment)
    if not partition_paths:
        return None

    # Check TTL for each partition (each partition uses its own data_latest,
    # NOT a global max — otherwise a single recent partition makes all
    # historical partitions subject to the mutable-window TTL).
    for p in partition_paths:
        if is_stale(ticker, timeframe, p, session=session, adjustment=adjustment):
            logger.debug("[Cache STALE] %s %s: %s", ticker, timeframe, p)
            return None

    # Fast path: meta.json already stores per-date completeness, computed
    # with the same tolerance at write time. When every trading date in the
    # range is either complete or negative-cached, skip the full
    # coverage_gaps recompute (which reads 100k+ bars and rebuilds the
    # expected-bar grid on every cache hit).
    _tz_ny = ZoneInfo("America/New_York")
    meta = read_meta(ticker, timeframe, session, adjustment)
    coverage = meta.get("coverage", {})
    active_neg_cache = active_negative_cache(meta.get("negative_cache", {}))
    if coverage:
        t_days = trading_days_in_range(
            start.astimezone(_tz_ny).date(), end.astimezone(_tz_ny).date()
        )
        all_accounted = all(
            coverage.get(d.isoformat(), {}).get("complete", False)
            or d.isoformat() in active_neg_cache
            for d in t_days
        )
        if all_accounted:
            df = read_bars(ticker, timeframe, start=start, end=end,
                           session=session, adjustment=adjustment, tz=tz)
            if df.empty:
                return None
            logger.debug("[Cache HIT] %s %s: %d rows (meta coverage)",
                         ticker, timeframe, len(df))
            return df

    # Slow path (legacy datasets without coverage entries, or ranges with
    # incomplete dates): load data and recompute coverage from the bars.
    df = read_bars(ticker, timeframe, start=start, end=end,
                   session=session, adjustment=adjustment, tz=tz)
    if df.empty:
        return None

    # Check coverage gaps — tolerate up to 5 % missing bars (handles rare
    # single-bar data noise from providers without rejecting the cache).
    gaps = coverage_gaps(
        df.index, timeframe, start=start, end=end,
        session=session, negative_cache=active_neg_cache,
    )
    if gaps:
        expected_total = expected_bars(timeframe, start, end, session=session)
        total = len(expected_total)
        tolerance = COMPLETENESS_TOLERANCE_1MIN_RTH if (timeframe == "1min" and session == "rth") else COMPLETENESS_TOLERANCE_DEFAULT
        if total > 0 and len(gaps) / total < tolerance:
            # Small gap (< tolerance) — provider data noise or illiquid stock, cache is good enough
            logger.debug("[Cache HIT] %s %s: %d rows (%d gap bars tolerated)",
                         ticker, timeframe, len(df), len(gaps))
            return df
        logger.debug("[Cache GAP] %s %s: %d missing bars (%.1f%% of expected %d)",
                     ticker, timeframe, len(gaps),
                     len(gaps) / total * 100 if total else 0.0, total)
        return None

    logger.debug("[Cache HIT] %s %s: %d rows", ticker, timeframe, len(df))
    return df


def _contiguous_date_runs(dates: list, max_gap_days: int = 5) -> list[list]:
    """Split a sorted list of dates into runs separated by > max_gap_days.

    Keeps provider requests close to the actually-missing windows instead of
    one span from the first to the last missing date (which would refetch
    everything cached in between).
    """
    if not dates:
        return []
    runs: list[list] = [[dates[0]]]
    for d in dates[1:]:
        if (d - runs[-1][-1]).days > max_gap_days:
            runs.append([d])
        else:
            runs[-1].append(d)
    return runs


def _range_has_any_trading_days(start: datetime, end: datetime) -> bool:
    """Return True if at least one NYSE trading day falls in [start, end]."""
    _ny = ZoneInfo("America/New_York")
    days = trading_days_in_range(
        start.astimezone(_ny).date(), end.astimezone(_ny).date()
    )
    return len(days) > 0


def _find_missing_dates(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    trading_dates: list,
    start: datetime,
    end: datetime,
    ignore_complete: bool = False,
    ignore_negative_cache: bool = False,
) -> list:
    """Return list of trading dates that are missing from cache.

    Checks negative cache and filters out dates covered by existing
    partitions that are fresh and complete.  ``force`` fetches pass both
    ignore flags — a forced re-fetch must bypass the negative cache too,
    or a poisoned entry can never be corrected.
    """
    if ignore_negative_cache:
        active_neg_cache = {}
    else:
        neg_cache = get_negative_cache(ticker, timeframe, session, adjustment)
        active_neg_cache = active_negative_cache(neg_cache)
    missing = []
    # trading_dates comes from trading_days_in_range (same calendar as
    # is_trading_day), so every date here is already a trading day.
    for d in trading_dates:
        date_key = d.isoformat()
        if date_key in active_neg_cache:
            continue  # Known non-trading or provider-empty (not expired)
        missing.append(d)

    # Further narrow: check if existing cached data already covers this date
    # (read coverage from meta.json to avoid unnecessary reads)
    meta = read_meta(ticker, timeframe, session, adjustment)
    coverage = meta.get("coverage", {})
    still_missing = []
    
    gran = Timeframe(timeframe).partition_granularity
    stale_partitions = {}

    for d in missing:
        date_key = d.isoformat()
        cov = coverage.get(date_key, {})
        
        # Determine if the partition containing this date is stale
        year = d.year
        month = d.month if gran == "month" else None
        part_path = resolve_path(ticker, timeframe, session, adjustment, year, month)
        
        if part_path not in stale_partitions:
            stale_partitions[part_path] = is_stale(
                ticker, timeframe, part_path, session=session, adjustment=adjustment
            )
        is_date_stale = stale_partitions[part_path]

        if not ignore_complete and cov.get("complete", False) and not is_date_stale:
            continue  # Already fully cached, complete, and fresh
        still_missing.append(d)

    return still_missing


def _dates_with_gaps(
    actual_index,
    timeframe: str,
    dates: list,
    start: datetime,
    end: datetime,
    session: str,
) -> list:
    """Return requested dates that still have expected-bar gaps.

    A date is considered fully covered if at least 95 % of expected bars
    are present in the accumulated data.  This tolerates rare single-bar
    gaps from providers (e.g. a missing 1-minute bar due to exchange or
    ticker-level data noise) and avoids expensive fallthrough to lower-
    priority providers for inconsequential gaps.
    """
    if actual_index is None or len(actual_index) == 0:
        return list(dates)

    _tz = ZoneInfo("America/New_York")
    tolerance = COMPLETENESS_TOLERANCE_1MIN_RTH if (timeframe == "1min" and session == "rth") else COMPLETENESS_TOLERANCE_DEFAULT

    # Bin the accumulated index by ET date once. The old per-date
    # coverage_gaps() calls each rebuilt a set of the *entire* index —
    # ~25M hash insertions for a ticker-year of 1-minute bars. Counts
    # decide the common cases; the exact timestamp diff runs only for
    # dates whose count is in the ambiguous band (count says covered but
    # off-grid timestamps could be inflating it).
    idx = pd.DatetimeIndex(actual_index)
    idx_et = idx.tz_convert(_tz) if idx.tz is not None else idx.tz_localize("UTC").tz_convert(_tz)
    by_day = idx_et.groupby(idx_et.normalize())

    remaining = []
    for d in dates:
        day_start = datetime(d.year, d.month, d.day, tzinfo=_tz)
        day_end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=_tz)
        req_start = max(day_start, start)
        req_end = min(day_end, end)
        expected_idx = expected_bars(timeframe, req_start, req_end, session=session)
        total = len(expected_idx)
        if total == 0:
            continue

        day_key = pd.Timestamp(day_start)
        day_actual = by_day.get(day_key)
        if day_actual is None or len(day_actual) == 0:
            remaining.append(d)
            continue
        if total - len(day_actual) >= total * tolerance:
            # Even if every actual bar matched an expected label the date
            # would still be under-covered — no exact diff needed.
            remaining.append(d)
            continue

        # Count says covered; verify against labels in case off-grid
        # timestamps inflated it.
        gaps = expected_idx[~expected_idx.isin(pd.DatetimeIndex(day_actual))]
        if len(gaps) and len(gaps) / total >= tolerance:
            remaining.append(d)
    return remaining


def _update_sidecar_coverage(ticker, timeframe, session, adjustment, trading_dates):
    """Update coverage entries for all trading days in the range in a single pass.

    Reads all cached bars once, then bins by date and updates meta coverage
    in bulk — avoids O(n_dates × n_partitions) Parquet reads.
    """
    if not trading_dates:
        return
    # Read only the affected date range — reading the full cached history
    # here made every fetch O(total cache size) and long backtests quadratic.
    _tz = ZoneInfo("America/New_York")
    d0, d1 = min(trading_dates), max(trading_dates)
    range_start = datetime(d0.year, d0.month, d0.day, tzinfo=_tz)
    range_end = datetime(d1.year, d1.month, d1.day, 23, 59, 59, tzinfo=_tz)
    try:
        all_bars = read_bars(ticker, timeframe, start=range_start, end=range_end,
                             session=session, adjustment=adjustment,
                             tz="America/New_York")
    except Exception:
        all_bars = pd.DataFrame()

    if all_bars is None or all_bars.empty:
        actual_by_date: dict[str, int] = {}
    else:
        # Bin bar counts by date (date is in the index as America/New_York)
        dates_series = all_bars.index.floor("D")
        counts = dates_series.value_counts()
        actual_by_date = {d.strftime("%Y-%m-%d"): int(c) for d, c in counts.items()}

    entries: dict[str, tuple[int, int]] = {}
    for d in trading_dates:
        date_key = d.isoformat()
        expected = len(expected_bars(
            timeframe,
            datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("America/New_York")),
            datetime(d.year, d.month, d.day, 23, 59, tzinfo=ZoneInfo("America/New_York")),
            session=session,
        ))
        entries[date_key] = (expected, actual_by_date.get(date_key, 0))

    # Single read-modify-write for the whole range — a per-date meta.json
    # rewrite made long-range prefetches O(days²) in JSON size.
    update_meta_coverage_bulk(ticker, timeframe, session, adjustment, entries)

    # Refresh summary stats for just the partitions this fetch touched —
    # a full directory scan per write made day-loop appends O(history).
    touched = get_partition_paths(ticker, timeframe, range_start, range_end,
                                  session=session, adjustment=adjustment)
    update_meta_summary(ticker, timeframe, session, adjustment, touched=touched)
