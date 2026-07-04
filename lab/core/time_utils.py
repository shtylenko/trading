from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def ny_dt(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute, second), tzinfo=NY)


def ensure_ny_index(df):
    if df is None or df.empty:
        return df
    out = df.copy()
    if out.index.tz is None:
        out.index = out.index.tz_localize(NY)
    else:
        out.index = out.index.tz_convert(NY)
    if not out.index.is_monotonic_increasing:
        out = out.sort_index()
    return out

