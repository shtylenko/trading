"""Trading calendar, expected bar labels, and coverage gap detection.

Uses ``exchange_calendars`` for NYSE trading sessions, holidays, and
early closes.  All public functions work in America/New_York timezone
for session boundary comparisons; storage always normalizes to UTC.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from exchange_calendars import get_calendar

from .errors import CalendarError

logger = logging.getLogger("strategy_lab.marketdata.calendar")

# ── Calendar singleton ────────────────────────────────────────────────────────

_nyse = get_calendar("XNYS")
_TZ_NY = str(_nyse.tz) if _nyse.tz else "America/New_York"

# Closures announced after the pinned exchange_calendars release (4.5.6 is
# the last version supporting Python 3.9, so upgrading is not an option).
# Without this, gap detection expects bars on these dates and every ticker
# falls through to lower-priority providers chasing data that cannot exist.
_EXTRA_CLOSURES: frozenset = frozenset({
    date(2025, 1, 9),  # National Day of Mourning for President Carter
})

# session open/close (UTC) for a given trading date
_open_col = _nyse.schedule["open"]
_close_col = _nyse.schedule["close"]


def is_trading_day(d: date) -> bool:
    """Return True if *d* is a regular NYSE trading day."""
    if d in _EXTRA_CLOSURES:
        return False
    try:
        return _nyse.is_session(d.isoformat())
    except Exception:
        return False


def session_open_utc(d: date) -> datetime:
    """Return the RTH open datetime (UTC) for trading day *d*."""
    try:
        return _open_col.loc[d.isoformat()].to_pydatetime()
    except KeyError:
        raise CalendarError(f"{d} is not a trading day")


def session_close_utc(d: date) -> datetime:
    """Return the RTH close datetime (UTC) for trading day *d*."""
    try:
        return _close_col.loc[d.isoformat()].to_pydatetime()
    except KeyError:
        raise CalendarError(f"{d} is not a trading day")


def is_early_close(d: date) -> bool:
    """Return True if *d* has an early close (< 16:00 ET)."""
    try:
        close_et = _close_col.loc[d.isoformat()].to_pydatetime().astimezone(
            ZoneInfo("America/New_York")
        )
        return (close_et.hour, close_et.minute) < (16, 0)
    except KeyError:
        return False


def trading_days_in_range(start: date, end: date) -> list[date]:
    """Return sorted list of NYSE trading days in [start, end]."""
    try:
        sessions = _nyse.sessions_in_range(start.isoformat(), end.isoformat())
        days = [s.date() if hasattr(s, "date") else s for s in sessions]
        return [d for d in days if d not in _EXTRA_CLOSURES]
    except Exception as e:
        raise CalendarError(f"Failed to enumerate sessions: {e}")


# ── Expected bar labels ───────────────────────────────────────────────────────


def _bar_label_range(
    session_open_utc: datetime,
    session_close_utc: datetime,
    freq: str,
) -> pd.DatetimeIndex:
    """Generate left-labeled bar timestamps (UTC) for a single trading session.

    Uses ``closed=\"left\", label=\"left\"`` convention matching the storage
    format in the existing strategy harnesses.
    """
    return pd.date_range(
        start=session_open_utc,
        end=session_close_utc,
        freq=freq,
        inclusive="left",
        tz="UTC",
    )


def expected_bars(
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
) -> pd.DatetimeIndex:
    """Return expected bar labels (America/New_York) for valid trading sessions.

    Parameters
    ----------
    timeframe : str
        One of ``1min``, ``5min``, ``15min``, ``1day``.
    start, end : datetime
        Request range (can be tz-aware or naive; naive assumed ET).
    session : str
        ``\"rth\"`` for regular hours or ``\"extended\"`` for premarket + RTH.

    Returns
    -------
    pd.DatetimeIndex
        Expected bar labels in America/New_York timezone.  Empty if no
        trading days in range.
    """
    # Normalize to date boundaries in ET
    _tz = "America/New_York"
    if start.tzinfo is None:
        start = start.replace(tzinfo=ZoneInfo(_tz))
    if end.tzinfo is None:
        end = end.replace(tzinfo=ZoneInfo(_tz))

    start_date = start.date()
    end_date = end.date()
    freq_map = {"1min": "1min", "5min": "5min", "15min": "15min", "1day": "D"}
    freq = freq_map.get(timeframe, "1min")

    tz_ny = ZoneInfo(_tz)

    all_bars: list[pd.DatetimeIndex] = []

    start_et = start.astimezone(tz_ny) if start.tzinfo is not None else start
    end_et = end.astimezone(tz_ny) if end.tzinfo is not None else end

    for trade_date in trading_days_in_range(start_date, end_date):
        try:
            open_utc = session_open_utc(trade_date)
            close_utc = session_close_utc(trade_date)

            if session == "extended":
                # Extended session: 04:00 ET. Construct in NY time and convert to UTC.
                open_ny = datetime(
                    trade_date.year, trade_date.month, trade_date.day,
                    4, 0, tzinfo=ZoneInfo(_TZ_NY),
                )
                open_utc = open_ny.astimezone(timezone.utc)
            # else RTH — use the exchange calendar open/close

            if timeframe == "1day":
                # Daily bars: one bar per trading day, labelled at 00:00 ET.
                # Apply the same [start, end] clamp as intraday labels — a
                # request starting mid-day must not "expect" a bar
                # timestamped before its own start.
                label = pd.Timestamp(datetime(
                    trade_date.year, trade_date.month, trade_date.day,
                    tzinfo=tz_ny,
                ))
                if pd.Timestamp(start_et) <= label <= pd.Timestamp(end_et):
                    all_bars.append(pd.DatetimeIndex([label]))
            else:
                labels = _bar_label_range(open_utc, close_utc, freq)
                if not labels.empty:
                    labels_et = labels.tz_convert(_tz)
                    labels_et = labels_et[
                        (labels_et >= pd.Timestamp(start_et))
                        & (labels_et <= pd.Timestamp(end_et))
                    ]
                    labels = labels_et.tz_convert("UTC")
                if not labels.empty:
                    all_bars.append(labels)
        except CalendarError:
            continue  # Not a trading day — skip

    if not all_bars:
        return pd.DatetimeIndex([])

    # Per-day indexes never overlap, so a single concat + sort suffices.
    # The old per-day .union() loop was O(n²) — ~12M element copies for a
    # year of 1-minute bars, on the hot path of every ranged cache check.
    if len(all_bars) == 1:
        combined = all_bars[0]
    else:
        values = np.concatenate([b.asi8 for b in all_bars])
        values.sort()
        combined = pd.to_datetime(values, utc=True)
    return combined.tz_convert(_tz)


def clip_to_session_close(df: pd.DataFrame) -> pd.DataFrame:
    """Drop bars at/after each trading day's RTH close (UTC-indexed input).

    Providers filter sessions with a fixed ``between_time("..", "15:59")``,
    which on early-close days (13:00 ET) lets the closing-auction print and
    any post-close prints through.  The calendar's expected-bar set treats
    the close as exclusive, so those bars must not be cached.  Dates the
    calendar does not know are left untouched.
    """
    if df is None or df.empty:
        return df
    idx_utc = df.index.tz_convert("UTC")
    day_keys = idx_utc.tz_convert(_TZ_NY).normalize()
    close_map: dict = {}
    for ts_day in day_keys.unique():
        try:
            close_map[ts_day] = pd.Timestamp(session_close_utc(ts_day.date()))
        except CalendarError:
            close_map[ts_day] = pd.NaT
    closes = pd.DatetimeIndex(day_keys.map(close_map))
    keep = closes.isna() | (idx_utc < closes)
    return df[keep]


def _is_early_close_session(trade_date: date, close_utc: datetime) -> bool:
    """Check if a session closes early based on the exchange calendar."""
    try:
        cal_close = _close_col.loc[trade_date.isoformat()].to_pydatetime()
        return cal_close < close_utc
    except KeyError:
        return False


def coverage_gaps(
    actual_index: pd.DatetimeIndex,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str,
    negative_cache: Optional[dict[str, dict]] = None,
) -> list[datetime]:
    """Compare actual timestamps against expected bars.

    Returns a list of *expected* timestamps (America/New_York) that are
    missing from ``actual_index``.  Non-trading dates and known negative-
    cache entries are excluded.

    Parameters
    ----------
    actual_index : pd.DatetimeIndex
        The timestamps actually present in cache / returned by a provider.
    timeframe, start, end, session : ...
        Same as ``expected_bars()``.
    negative_cache : dict or None
        Per-date negative cache dict where keys are ISO date strings
        (``\"YYYY-MM-DD\"``) and values have a ``\"reason\"`` key
        (e.g. ``{\"reason\": \"non_trading_day\"}``).

    Returns
    -------
    list[datetime]
        Missing expected bar timestamps.
    """
    expected = expected_bars(timeframe, start, end, session)
    if expected.empty:
        return []

    if negative_cache is None:
        negative_cache = {}
    neg_dates = set()
    for k in negative_cache:
        try:
            neg_dates.add(date.fromisoformat(k))
        except ValueError:
            continue

    if actual_index.empty:
        return [ts for ts in expected if ts.date() not in neg_dates]

    # Normalize actual for comparison. A naive index can't have come from
    # storage (always UTC tz-aware) — assume UTC rather than comparing
    # naive-vs-aware, which would silently match nothing and report the
    # entire range missing.
    if actual_index.tz is None:
        actual_index = actual_index.tz_localize("UTC")
    actual_et = actual_index.tz_convert("America/New_York")

    # Vectorized membership: ~100k per-timestamp set lookups + strftime
    # calls per ranged check otherwise.
    missing_mask = ~expected.isin(actual_et)
    if not missing_mask.any():
        return []
    if not neg_dates:
        return list(expected[missing_mask])
    return [ts for ts in expected[missing_mask] if ts.date() not in neg_dates]
