"""Parquet Hive-partitioned read/write with meta.json sidecar management.

All Parquet files use a consistent schema:

    timestamp  (datetime64[ns, UTC], regular column, not index)
    open       (float64)
    high       (float64)
    low        (float64)
    close      (float64)
    volume     (int64)
    trade_count (int64, optional — only if provider supplies it)
    vwap       (float64, optional)
    provider   (string — winning provider after dedup)
    retrieved_at (datetime64[ns, UTC])

``timestamp`` is stored as a regular column so pyarrow predicate pushdown
works.  After reading, callers set it as the index via ``set_index``.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import (
    DATA_DIR,
    Timeframe,
    resolve_dataset_dir,
    resolve_meta_path,
    COMPLETENESS_TOLERANCE_1MIN_RTH,
    COMPLETENESS_TOLERANCE_DEFAULT,
)
from .errors import CorruptDataError, StorageError

logger = logging.getLogger("strategy_lab.marketdata.storage")

# ── Parquet column constants ──────────────────────────────────────────────────

PARQUET_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
PARQUET_COLUMNS_OPTIONAL = ["trade_count", "vwap", "provider", "retrieved_at"]


def _normalize_for_storage(df: pd.DataFrame, provider_name: str) -> pd.DataFrame:
    """Prepare a DataFrame for Parquet storage.

    - Ensures ``timestamp`` is a regular column (not index), UTC, tz-aware.
    - Adds ``provider`` and ``retrieved_at`` columns.
    - Drops rows with NaN in required OHLCV columns.
    - Returns a sorted, deduplicated-by-timestamp DataFrame.
    """
    out = df.copy()

    if out.empty:
        return pd.DataFrame()

    # Promote index to column if named "timestamp"
    if out.index.name == "timestamp":
        if "timestamp" in out.columns:
            # Already has a timestamp column — just drop the index
            out = out.reset_index(drop=True)
        else:
            out = out.reset_index()
    if "timestamp" not in out.columns:
        raise StorageError("DataFrame has no timestamp column or index")
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)

    # Ensure required columns exist
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in out.columns:
            out[col] = float("nan")
    out["volume"] = out["volume"].fillna(0).astype("int64")

    # Annotate
    if "provider" not in out.columns:
        out["provider"] = provider_name
    else:
        out["provider"] = out["provider"].fillna(provider_name)
    out["retrieved_at"] = datetime.now(timezone.utc)

    # Sort & dedup
    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

    # Drop rows with NaN in any OHLC column — a row with (say) a NaN close
    # but valid high/low would otherwise survive into the cache and poison
    # ATR/feature math downstream. Volume was already 0-filled above.
    out = out.dropna(subset=["open", "high", "low", "close"], how="any")

    return out


def _partition_cols(timeframe: str) -> list[str]:
    """Return Hive partition column names for the given timeframe."""
    gran = Timeframe(timeframe).partition_granularity
    if gran == "month":
        return ["year", "month"]
    return ["year"]  # year-only for daily/15min


def _add_partition_cols(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Add ``year`` and ``month`` partition columns from ``timestamp`` (UTC)."""
    out = df.copy()
    ts = out["timestamp"]
    out["year"] = ts.dt.year.astype(str)
    if "month" in _partition_cols(timeframe):
        out["month"] = ts.dt.month.astype(str)
    return out


# ── Path resolution ───────────────────────────────────────────────────────────


def resolve_path(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    year: int,
    month: Optional[int] = None,
) -> Path:
    """Return the Hive-partitioned Parquet file path for one partition.

    Examples
    --------
    1min: data/1min/AAPL/session=rth/adjustment=raw/year=2024/month=1/data.parquet
    1day: data/1day/AAPL/session=rth/adjustment=split/year=2024/data.parquet
    """
    ds_dir = resolve_dataset_dir(ticker, timeframe, session, adjustment)
    parts = [f"year={year}"]
    if month is not None:
        parts.append(f"month={month}")
    return ds_dir.joinpath(*parts) / "data.parquet"


def get_partition_paths(
    ticker: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    session: str = "rth",
    adjustment: str = "raw",
) -> list[Path]:
    """Return paths to all existing Parquet partitions that overlap [start, end].

    Scans the filesystem for year/month directories under the dataset key.
    """
    ds_dir = resolve_dataset_dir(ticker, timeframe, session, adjustment)
    if not ds_dir.exists():
        return []

    gran = Timeframe(timeframe).partition_granularity
    start_yr = start.year
    end_yr = end.year

    paths: list[Path] = []
    for yr in range(start_yr, end_yr + 1):
        yr_dir = ds_dir / f"year={yr}"
        if not yr_dir.exists():
            continue
        if gran == "month":
            start_mo = start.month if yr == start_yr else 1
            end_mo = end.month if yr == end_yr else 12
            for mo in range(start_mo, end_mo + 1):
                p = yr_dir / f"month={mo}" / "data.parquet"
                if p.exists():
                    paths.append(p)
        else:
            p = yr_dir / "data.parquet"
            if p.exists():
                paths.append(p)
    return sorted(paths)


# ── Read ──────────────────────────────────────────────────────────────────────


def read_bars(
    ticker: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    session: str = "rth",
    adjustment: str = "raw",
    columns: Optional[list[str]] = None,
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """Read OHLCV from Hive-partitioned Parquet files.

    Uses pyarrow's Hive-partitioned read to discover and filter partitions.
    ``timestamp`` is stored as a regular Parquet column and returned as a
    ``DatetimeIndex`` (tz-aware, in *tz* timezone).

    Parameters
    ----------
    ticker, timeframe, session, adjustment : str
        Dataset key components.
    start, end : datetime, optional
        Filter range.  If both None, returns all stored data.
    columns : list[str], optional
        Column projection (e.g. ``[\"timestamp\", \"close\", \"volume\"]``).
        If None, returns all columns *except* ``year``, ``month`` (internal
        partition columns are stripped).
    tz : str
        Return timezone for the index (default: America/New_York).

    Returns
    -------
    pd.DataFrame
        OHLCV DataFrame with ``DatetimeIndex`` named ``\"timestamp\"``.
        Empty DataFrame if no data exists.
    """
    ds_dir = resolve_dataset_dir(ticker, timeframe, session, adjustment)
    if not ds_dir.is_dir():
        return pd.DataFrame()

    # Build filter conditions (pyarrow filter syntax — all timestamps must be UTC)
    filters = None
    pyarrow_filters: list = []
    if start is not None:
        start_utc = start.astimezone(timezone.utc) if start.tzinfo is not None else start
        pyarrow_filters.append(("timestamp", ">=", start_utc))
    if end is not None:
        end_utc = end.astimezone(timezone.utc) if end.tzinfo is not None else end
        pyarrow_filters.append(("timestamp", "<=", end_utc))
    if pyarrow_filters:
        filters = pyarrow_filters

    # Column projection
    read_cols = None
    if columns:
        read_cols = [c for c in columns if c not in ("year", "month")]

    try:
        import pyarrow.parquet as pq
        import pyarrow.compute as pc

        # Discover relevant partition files
        partition_paths = get_partition_paths(ticker, timeframe, start or datetime(2000, 1, 1),
                                              end or datetime(2030, 1, 1),
                                              session=session, adjustment=adjustment)
        if not partition_paths:
            return pd.DataFrame()

        # Read each partition file with optional timestamp filter
        tables = []
        for p in partition_paths:
            if start is None and end is None:
                tbl = pq.read_table(str(p), columns=read_cols)
            else:
                tbl = pq.read_table(str(p), columns=read_cols,
                                    filters=filters)
            if tbl.num_rows > 0:
                tables.append(tbl)

        if not tables:
            return pd.DataFrame()

        # Convert to pandas and concat (handles schema differences gracefully)
        dfs = [t.to_pandas() for t in tables]
        df = pd.concat(dfs, ignore_index=True)
        if df.empty:
            return pd.DataFrame()

        # Remove Hive partition columns (added by pyarrow when reading
        # files under Hive-style paths like session=rth/adjustment=raw/year=2024/)
        _KNOWN_HIVE_COLS = {"year", "month", "session", "adjustment"}
        for col in list(df.columns):
            if col in _KNOWN_HIVE_COLS:
                df = df.drop(columns=[col])

        # Set timestamp as index
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
            df.index.name = "timestamp"

        # Timezone conversion
        if df.index.tz is not None and tz != "UTC":
            df.index = df.index.tz_convert(tz)
        elif df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(tz)

        # Sort and dedup
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        return df
    except FileNotFoundError:
        # Partition vanished between discovery and read (concurrent
        # quarantine/replace) — treat as no data.
        logger.debug(f"Partition disappeared during read for {ticker}/{timeframe}")
        return pd.DataFrame()
    except OSError as e:
        # Transient OS-level failure (EMFILE under parallel workers, etc.)
        # — distinct from corrupt data; the caller may refetch unnecessarily
        # but nothing is poisoned.
        logger.warning(f"Transient read failure for {ticker}/{timeframe}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Failed to read Parquet for {ticker}/{timeframe} "
                     f"(possible corrupt partition): {e}")
        return pd.DataFrame()


# ── Write ─────────────────────────────────────────────────────────────────────


def _atomic_replace(src: Path, dst: Path) -> None:
    """Atomically replace *dst* with *src*.  Both must be on the same FS."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = src.resolve()
    dst = dst.resolve()
    # POSIX atomic rename when on same filesystem
    # Use Path.rename (not shutil.move) — it's atomic on the same FS
    src.replace(dst)


def write_bars(
    ticker: str,
    timeframe: str,
    df: pd.DataFrame,
    session: str,
    adjustment: str,
    provider_name: str = "unknown",
    merge: bool = True,
) -> int:
    """Write OHLCV DataFrame to Hive-partitioned Parquet.

    Parameters
    ----------
    ticker, timeframe, session, adjustment : str
        Dataset key components.
    df : pd.DataFrame
        Data to write.  Must have a ``\"timestamp\"`` column or
        ``DatetimeIndex``.
    provider_name : str
        Provider name for the ``provider`` column annotation.
    merge : bool
        If True, merge with existing partition data before writing
        (dedup by timestamp).  If False, overwrite the partition files
        entirely with the provided data.

    Returns
    -------
    int
        Number of rows written.
    """
    out = _normalize_for_storage(df, provider_name)
    if out.empty:
        return 0

    out = _add_partition_cols(out, timeframe)

    partition_cols = _partition_cols(timeframe)
    gran = Timeframe(timeframe).partition_granularity

    rows_written = 0

    if gran == "month":
        grouped = out.groupby(["year", "month"])
    else:
        grouped = out.groupby(["year"])

    for group_keys, group_df in grouped:
        if partition_cols == ["year", "month"]:
            yr_str, mo_str = group_keys
            target_path = resolve_path(ticker, timeframe, session, adjustment, int(yr_str), int(mo_str))
        else:
            yr_str = group_keys[0] if isinstance(group_keys, tuple) else group_keys
            target_path = resolve_path(ticker, timeframe, session, adjustment, int(yr_str))

        # Drop partition columns before writing
        write_df = group_df.drop(columns=partition_cols, errors="ignore")

        if merge and target_path.exists():
            try:
                existing = pd.read_parquet(target_path)
                existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
                merged = pd.concat([existing, write_df])
                merged = merged.drop_duplicates(subset=["timestamp"], keep="last")
                merged = merged.sort_values("timestamp")
                write_df = merged
            except Exception as e:
                # Unreadable partition — quarantine it (spec: never silently
                # destroy corrupt files) and write only the new data. The
                # quarantined file keeps any rows the new fetch doesn't cover.
                logger.warning(f"Merge failed for {target_path}, quarantining and writing new data: {e}")
                try:
                    quarantine_corrupt(target_path)
                except OSError as qe:
                    logger.error(f"Failed to quarantine {target_path}: {qe}")

        # Atomic write: temp file → rename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(
            suffix=".parquet",
            dir=str(target_path.parent),
        )
        tmp_path = Path(tmp_path_str)
        try:
            import os

            os.close(fd)  # Close file descriptor; pandas will re-open
            write_df.to_parquet(
                tmp_path,
                index=False,
                compression="zstd",
                version="2.6",
            )
            _atomic_replace(tmp_path, target_path)
            # Note: rows_written accumulates the total row count of the written parquet partition file,
            # which includes both pre-existing merged rows and the new rows.
            rows_written += len(write_df)
        except Exception:
            # Cleanup temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    return rows_written


# ── Meta.json sidecar ─────────────────────────────────────────────────────────


# Parsed meta.json cache keyed by path, validated by mtime. fetch_bars
# parses the sidecar 3-4 times per call; with multi-year coverage entries a
# sidecar runs to ~100 KB of JSON, so repeated parses add up across
# thousands of fetches. Writes bump the mtime, which invalidates naturally
# (including writes from other processes).
# Bounded so a long-running prefetch over thousands of (ticker, timeframe,
# session, adjustment) keys cannot grow the cache without limit (~100 KB per
# entry). When full, the oldest-inserted entry is evicted (insertion-ordered
# dict); re-parsing on a miss is cheap relative to holding it all in RAM.
_META_CACHE: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_META_CACHE_MAXSIZE = 512
_META_CACHE_LOCK = threading.Lock()


def read_meta(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
) -> dict[str, Any]:
    """Read the meta.json sidecar for a dataset key.

    Returns an empty dict if the file doesn't exist or is corrupt.
    The result is a private copy — callers may mutate it freely.
    """
    path = resolve_meta_path(ticker, timeframe, session, adjustment)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    key = str(path)
    with _META_CACHE_LOCK:
        cached = _META_CACHE.get(key)
        if cached is not None and cached[0] == mtime:
            return _meta_copy(cached[1])
    try:
        parsed = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Corrupt meta.json at {path}: {e}")
        return {}
    with _META_CACHE_LOCK:
        _META_CACHE[key] = (mtime, parsed)
        _META_CACHE.move_to_end(key)
        while len(_META_CACHE) > _META_CACHE_MAXSIZE:
            _META_CACHE.popitem(last=False)
    return _meta_copy(parsed)


def _meta_copy(meta: dict) -> dict:
    """Two-level copy of a cached meta dict.

    Callers assign new entries into ``coverage``/``negative_cache`` but
    never mutate existing per-date entries in place, so sharing the leaf
    dicts is safe and avoids a full deep copy per read.
    """
    return {
        k: dict(v) if isinstance(v, dict) else v
        for k, v in meta.items()
    }


def write_meta(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    meta: dict[str, Any],
) -> None:
    """Atomically write the meta.json sidecar for a dataset key.

    Merges with existing data (write keys win).
    """
    path = resolve_meta_path(ticker, timeframe, session, adjustment)
    existing = read_meta(ticker, timeframe, session, adjustment)
    existing.update(meta)
    existing["version"] = 1
    existing["timezone_storage"] = "UTC"
    existing["timezone_default_return"] = "America/New_York"

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".json",
        dir=str(path.parent),
    )
    import os

    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        tmp_path.write_text(json.dumps(existing, indent=2, default=str))
        _atomic_replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


_DEFAULT_EMPTY_COVERAGE = {"expected_bars": 0, "actual_bars": 0, "complete": False}


def update_meta_coverage(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    trade_date: str,
    expected: int,
    actual: int,
) -> None:
    """Update the coverage entry for a single trading day in meta.json."""
    update_meta_coverage_bulk(
        ticker, timeframe, session, adjustment, {trade_date: (expected, actual)}
    )


def update_meta_coverage_bulk(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    entries: dict[str, tuple[int, int]],
) -> None:
    """Update coverage entries for many trading days in one read/write cycle.

    ``entries`` maps ISO date strings to ``(expected, actual)`` bar counts.
    A per-date read-modify-write of meta.json made long-range prefetches
    O(days²) in JSON size.
    """
    if not entries:
        return
    meta = read_meta(ticker, timeframe, session, adjustment)
    coverage = meta.get("coverage", {})

    tolerance = COMPLETENESS_TOLERANCE_1MIN_RTH if (timeframe == "1min" and session == "rth") else COMPLETENESS_TOLERANCE_DEFAULT
    for trade_date, (expected, actual) in entries.items():
        missing_pct = (expected - actual) / expected if expected > 0 else 0.0
        coverage[trade_date] = {
            "expected_bars": expected,
            "actual_bars": actual,
            "complete": missing_pct < tolerance,
        }
    meta["coverage"] = coverage
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    write_meta(ticker, timeframe, session, adjustment, meta)


def get_negative_cache(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
) -> dict[str, dict]:
    """Return the negative_cache dict from meta.json.

    Keys are ISO date strings (``\"YYYY-MM-DD\"``), values have
    ``\"reason\"`` and ``\"retrieved_at\"``.
    """
    meta = read_meta(ticker, timeframe, session, adjustment)
    return meta.get("negative_cache", {})


def write_negative_cache(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    date_key: str,
    reason: str,
) -> None:
    """Add a negative cache entry for a single date.

    ``reason`` is either ``\"non_trading_day\"`` (infinite TTL) or
    ``\"provider_empty\"`` (24h TTL — re-check after a day).
    """
    write_negative_cache_bulk(ticker, timeframe, session, adjustment,
                              {date_key: reason})


def write_negative_cache_bulk(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    reasons_by_date: dict[str, str],
) -> None:
    """Add negative cache entries for many dates in one read/write cycle."""
    if not reasons_by_date:
        return
    meta = read_meta(ticker, timeframe, session, adjustment)
    nc = meta.get("negative_cache", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    for date_key, reason in reasons_by_date.items():
        nc[date_key] = {"reason": reason, "retrieved_at": now_iso}
    meta["negative_cache"] = nc
    write_meta(ticker, timeframe, session, adjustment, meta)


def partition_latest_timestamp(path: Path) -> Optional[datetime]:
    """Return max(timestamp) of one partition file, preferring footer stats.

    Footer-only reads keep per-partition freshness checks O(1) instead of
    loading the whole timestamp column on every cache hit.  Falls back to a
    column read when statistics are unavailable; returns None when the file
    is unreadable or empty.
    """
    try:
        import pyarrow.parquet as pq

        md = pq.ParquetFile(str(path)).metadata
        if md.num_rows == 0:
            return None
        ts_max = None
        for rg in range(md.num_row_groups):
            row_group = md.row_group(rg)
            for ci in range(row_group.num_columns):
                col = row_group.column(ci)
                if col.path_in_schema == "timestamp" and col.statistics is not None:
                    stats = col.statistics
                    if stats.has_min_max:
                        cmax = pd.Timestamp(stats.max)
                        if cmax.tz is None:
                            cmax = cmax.tz_localize("UTC")
                        ts_max = cmax if ts_max is None else max(ts_max, cmax)
        if ts_max is not None:
            return ts_max.to_pydatetime()
        # Statistics unavailable — read just the timestamp column
        df_ts = pd.read_parquet(path, columns=["timestamp"])
        if df_ts.empty:
            return None
        return pd.to_datetime(df_ts["timestamp"], utc=True).max().to_pydatetime()
    except Exception as e:
        logger.debug(f"Failed to read latest timestamp from {path}: {e}")
        return None


def get_latest_data_timestamp(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
) -> Optional[datetime]:
    """Return the latest ``timestamp`` value across all partitions.

    Reads the file mtime + the data itself.  Returns None on empty data.
    """
    meta = read_meta(ticker, timeframe, session, adjustment)
    latest = meta.get("latest")
    if latest:
        try:
            return datetime.fromisoformat(latest)
        except (ValueError, TypeError):
            pass
    # Fallback: scan partitions
    ds_dir = resolve_dataset_dir(ticker, timeframe, session, adjustment)
    if not ds_dir.is_dir():
        return None
    try:
        df = read_bars(
            ticker, timeframe, session=session, adjustment=adjustment, tz="UTC"
        )
        if df.empty or df.index.empty:
            return None
        return df.index.max().to_pydatetime()
    except Exception:
        return None


def _partition_footer_stats(p: Path) -> Optional[dict]:
    """Footer-only stats for one partition: rows, earliest, latest.

    Returns None when the file is unreadable; rows may be 0.
    """
    import pyarrow.parquet as pq

    try:
        md = pq.ParquetFile(str(p)).metadata
        if md.num_rows == 0:
            return {"rows": 0, "earliest": None, "latest": None}
        ts_min = ts_max = None
        for rg in range(md.num_row_groups):
            row_group = md.row_group(rg)
            for ci in range(row_group.num_columns):
                col = row_group.column(ci)
                if col.path_in_schema == "timestamp" and col.statistics is not None:
                    stats = col.statistics
                    if stats.has_min_max:
                        cmin = pd.Timestamp(stats.min, tz="UTC") if pd.Timestamp(stats.min).tz is None else pd.Timestamp(stats.min)
                        cmax = pd.Timestamp(stats.max, tz="UTC") if pd.Timestamp(stats.max).tz is None else pd.Timestamp(stats.max)
                        ts_min = cmin if ts_min is None else min(ts_min, cmin)
                        ts_max = cmax if ts_max is None else max(ts_max, cmax)
        if ts_min is None:
            # Statistics unavailable — fall back to reading the column
            pf = pd.read_parquet(p, columns=["timestamp"])
            if pf.empty:
                return {"rows": 0, "earliest": None, "latest": None}
            ts = pd.to_datetime(pf["timestamp"], utc=True)
            ts_min, ts_max = ts.min(), ts.max()
        return {
            "rows": md.num_rows,
            "earliest": ts_min.isoformat(),
            "latest": ts_max.isoformat(),
        }
    except Exception:
        logger.debug(f"Skipping unreadable partition {p}")
        return None


def update_meta_summary(
    ticker: str,
    timeframe: str,
    session: str,
    adjustment: str,
    touched: Optional[list[Path]] = None,
) -> None:
    """Update meta.json summary fields from per-partition footer stats.

    When *touched* is given and meta already carries ``partition_stats``,
    only those partitions are re-read (footer-only) and the aggregates are
    recomputed from the stored stats — a write no longer pays a full
    directory scan over every historical partition. A full scan still runs
    when *touched* is None or on first migration.
    """
    meta = read_meta(ticker, timeframe, session, adjustment)
    ds_dir = resolve_dataset_dir(ticker, timeframe, session, adjustment)
    if not ds_dir.is_dir():
        return

    part_stats: dict[str, dict] = meta.get("partition_stats", {})

    if touched is not None and part_stats:
        targets = [p for p in touched if p.exists()]
    else:
        targets = sorted(ds_dir.rglob("data.parquet"))
        part_stats = {}
    if not targets and not part_stats:
        return

    for p in targets:
        rel = str(p.relative_to(ds_dir).parent)
        stats = _partition_footer_stats(p)
        if stats is not None:
            part_stats[rel] = stats

    # Drop stats for partitions that no longer exist (quarantined etc.)
    part_stats = {
        rel: s for rel, s in part_stats.items()
        if (ds_dir / rel / "data.parquet").exists()
    }

    total_rows = sum(s.get("rows", 0) for s in part_stats.values())
    earliests = [s["earliest"] for s in part_stats.values() if s.get("earliest")]
    latests = [s["latest"] for s in part_stats.values() if s.get("latest")]

    meta["partition_stats"] = part_stats
    if earliests:
        meta["earliest"] = min(earliests)
    if latests:
        meta["latest"] = max(latests)
    meta["total_rows"] = total_rows
    meta["partitions"] = sorted(part_stats.keys())
    meta["ticker"] = ticker.upper()
    meta["timeframe"] = timeframe
    meta["session"] = session
    meta["adjustment"] = adjustment
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    write_meta(ticker, timeframe, session, adjustment, meta)


def sweep_tmp_files(max_age_hours: float = 24.0) -> int:
    """Delete orphaned tempfiles left by crashed writers.

    ``write_bars``/``write_meta`` create ``tmp*`` files next to their
    targets and rename on success; a killed process leaves them behind.
    Only files older than *max_age_hours* are removed so in-flight writes
    from live processes are never touched. Returns the number deleted.
    """
    import time as _time

    if not DATA_DIR.is_dir():
        return 0
    cutoff = _time.time() - max_age_hours * 3600
    removed = 0
    # tmp files live next to data.parquet (year=/month= dirs) and next to
    # meta.json (adjustment= dirs) — glob both depths instead of rglob over
    # the whole tree.
    patterns = (
        "*/*/session=*/adjustment=*/tmp*",
        "*/*/session=*/adjustment=*/year=*/tmp*",
        "*/*/session=*/adjustment=*/year=*/month=*/tmp*",
    )
    for pattern in patterns:
        for p in DATA_DIR.glob(pattern):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:
                continue
    if removed:
        logger.info("Swept %d orphaned temp file(s) from %s", removed, DATA_DIR)
    return removed


def quarantine_corrupt(path: Path) -> Path:
    """Rename a corrupt Parquet file to ``data.parquet.corrupt.{timestamp}``.

    Returns the quarantine path.  Does NOT delete — spec says don't
    silently delete corrupt files.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    dest = path.with_name(f"{path.name}.corrupt.{ts}")
    path.rename(dest)
    logger.warning(f"Quarantined corrupt file {path} → {dest}")
    return dest
