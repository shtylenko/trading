"""Freshness / staleness rules for cached Parquet partitions.

TTLs are parameterised by timeframe and by whether the data is in the
mutable window (today/recent days) or immutable (historical).

``applies_when`` predicates use America/New_York date boundaries (not UTC)
to align with market trading day semantics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from .storage import partition_latest_timestamp

logger = logging.getLogger("strategy_lab.marketdata.ttl")

# ── Date-boundary predicates ──────────────────────────────────────────────────

_TZ_NY = "America/New_York"


def _ny_date(dt: datetime) -> date:
    """Return the date of *dt* in America/New_York."""
    return dt.astimezone(ZoneInfo(_TZ_NY)).date()


def _trading_days_since(data_date: date) -> int:
    """Number of trading sessions strictly after *data_date* through today (ET).

    Falls back to calendar-day distance if the exchange calendar is
    unavailable. Using trading days (not calendar days) keeps Friday's data
    in the mutable window through Monday — otherwise a partial Friday
    session fetched mid-day would be frozen as "immutable" over the weekend.
    """
    ny_today = _ny_date(datetime.now(timezone.utc))
    if data_date >= ny_today:
        return 0
    try:
        from .calendar import trading_days_in_range

        sessions = trading_days_in_range(data_date, ny_today)
        return len([s for s in sessions if s > data_date])
    except Exception:
        # Weekday-only fallback: counting raw calendar days would make
        # Friday's data 3 days old by Monday and wrongly freeze it as
        # immutable over the weekend. Excluding Sat/Sun keeps Fri→Mon at 1.
        # (Holidays are still slightly over-counted, but that only re-checks
        # a touch more often — it never freezes fresh data prematurely.)
        cur = data_date + timedelta(days=1)
        count = 0
        while cur <= ny_today:
            if cur.weekday() < 5:
                count += 1
            cur += timedelta(days=1)
        return count


def is_today_or_yesterday(data_latest_et: datetime) -> bool:
    """Return True if *data_latest_et* is today or the prior trading session."""
    return _trading_days_since(_ny_date(data_latest_et)) <= 1


def is_within_last_3_days(data_latest_et: datetime) -> bool:
    """Return True if *data_latest_et* is within the last 3 trading days (ET)."""
    return _trading_days_since(_ny_date(data_latest_et)) <= 3


# ── Freshness rule table ──────────────────────────────────────────────────────


@dataclass
class FreshnessRule:
    timeframe: str
    staleness_threshold: timedelta
    applies_when: Callable[[datetime], bool]


FRESHNESS_RULES: list[FreshnessRule] = [
    FreshnessRule("1min", timedelta(hours=2), is_today_or_yesterday),
    FreshnessRule("5min", timedelta(hours=2), is_today_or_yesterday),
    FreshnessRule("15min", timedelta(hours=4), is_today_or_yesterday),
    FreshnessRule("1day", timedelta(days=1), is_within_last_3_days),
]

_RULES_BY_TF: dict[str, FreshnessRule] = {r.timeframe: r for r in FRESHNESS_RULES}


# ── Staleness check ───────────────────────────────────────────────────────────


def is_stale(
    ticker: str,
    timeframe: str,
    file_path: Path,
    session: str = "rth",
    adjustment: str = "raw",
    data_latest: Optional[datetime] = None,
) -> bool:
    """Return True if the cached partition file should be re-fetched.

    Uses the file's ``st_mtime`` (when written to disk) as ``retrieved_at``,
    NOT the data's latest timestamp.  A partition file written yesterday
    containing yesterday's bars is not stale — the mtime correctly reflects
    when it was cached.

    The mutable-window check uses this partition's own latest timestamp
    (Parquet footer statistics), never a dataset-global max — otherwise a
    single recent partition would make every historical partition subject
    to the mutable-window TTL.
    """
    rule = _RULES_BY_TF.get(timeframe)
    if rule is None:
        return False  # Unknown timeframe = never stale

    # retrieved_at = file's last-modified time (UTC)
    try:
        stat = file_path.stat()
        retrieved_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    except OSError:
        return True  # File doesn't exist or can't be stat'd

    if data_latest is None:
        data_latest = partition_latest_timestamp(file_path)
    if data_latest is None:
        return True  # Unreadable partition — re-fetch

    # Check if data is in the mutable window (ET date boundaries)
    data_latest_et = data_latest.astimezone(ZoneInfo(_TZ_NY))
    if not rule.applies_when(data_latest_et):
        return False  # Historical data — immutable

    # Within mutable window: compare mtime to staleness threshold
    age = datetime.now(timezone.utc) - retrieved_at
    return age > rule.staleness_threshold


# ── Negative cache TTL helpers ────────────────────────────────────────────────


# A confirmed-empty date this far in the past can never change: the
# session is long closed and providers have published whatever exists.
# Without this, every thin ticker's no-trade dates are re-fetched from
# the network once per 24h TTL window, forever.
_IMMUTABLE_AFTER_DAYS = 7


def is_negative_cache_expired(
    entry: dict,
    date_key: str | None = None,
) -> bool:
    """Return True if a negative cache entry has expired and should be re-checked.

    ``non_trading_day`` entries never expire (infinite TTL).
    ``provider_empty`` entries (providers responded, confirmed no data)
    expire after 24 hours — except for dates older than
    ``_IMMUTABLE_AFTER_DAYS``, which never expire: historical absence is
    final.  Pass ``date_key`` (ISO date string) to enable that check.
    ``provider_error`` entries (all providers errored — e.g. a network
    outage) expire after 15 minutes so a transient failure does not black
    out the dataset for a full day.
    """
    reason = entry.get("reason", "")
    if reason == "non_trading_day":
        return False  # Never re-fetch non-trading dates
    if reason == "provider_empty" and date_key:
        try:
            entry_date = date.fromisoformat(date_key)
        except ValueError:
            entry_date = None
        if entry_date is not None:
            ny_today = _ny_date(datetime.now(timezone.utc))
            if (ny_today - entry_date).days > _IMMUTABLE_AFTER_DAYS:
                return False  # Historical absence is final
    ttl_by_reason = {
        "provider_empty": timedelta(hours=24),
        "provider_error": timedelta(minutes=15),
    }
    ttl = ttl_by_reason.get(reason)
    if ttl is not None:
        retrieved_at_str = entry.get("retrieved_at", "")
        try:
            retrieved_at = datetime.fromisoformat(retrieved_at_str)
            return (datetime.now(timezone.utc) - retrieved_at) > ttl
        except (ValueError, TypeError):
            return True  # Can't parse — re-fetch to be safe
    return True  # Unknown reason — re-fetch
