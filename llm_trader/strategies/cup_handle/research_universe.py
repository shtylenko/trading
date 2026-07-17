"""Versioned point-in-time universe manifests for cup-handle research.

A scanner can be causal about prices yet still be invalid research if it uses
today's surviving tickers for dates in the past.  This module makes historical
membership an explicit, hashable input rather than an undocumented static list.

The manifest is deliberately small and provider-neutral.  It records *which*
symbols were eligible over each inclusive calendar interval plus the source and
as-of date from which that membership was obtained.  It does not fabricate
historical membership: a current snapshot is represented as
``membership_basis: current_snapshot`` and is rejected by the research scanner.

Schema v1::

    {
      "schema_version": 1,
      "name": "sp500-pit-2025-2026",
      "membership_basis": "point_in_time",
      "source_quality": "primary_or_licensed",
      "intervals": [{
        "start": "2025-01-01", "end": "2025-03-31",
        "as_of": "2024-12-31", "source": "vendor/export/version",
        "symbols": ["AAPL", "..."],
        "source_sha256": "optional immutable source-file hash"
      }]
    }

Intervals must be ordered, non-overlapping, and cover every calendar day of a
requested historical scan.  Calendar coverage is intentional: it makes an
omitted interval visible even if its gap happens to contain a weekend.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from trading.llm_trader.fsutils import atomic_write_bytes, atomic_write_json


SCHEMA_VERSION = 1
POINT_IN_TIME = "point_in_time"
CURRENT_SNAPSHOT = "current_snapshot"
SOURCE_QUALITY_PRIMARY = "primary_or_licensed"
SOURCE_QUALITY_PUBLIC = "public_pit_unverified"
SOURCE_QUALITY_UNQUALIFIED = "unqualified"
_SOURCE_QUALITIES = {
    SOURCE_QUALITY_PRIMARY,
    SOURCE_QUALITY_PUBLIC,
    SOURCE_QUALITY_UNQUALIFIED,
}
_YFIUA_SP500_URL = (
    "https://yfiua.github.io/index-constituents/"
    "{year:04d}/{month:02d}/constituents-sp500.json"
)
_FJA_SP500_HISTORY_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20%28Updated%29.csv"
)


class UniverseManifestError(ValueError):
    """A manifest is malformed, unsuitable for research, or lacks coverage."""


def _date(value: object, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise UniverseManifestError(f"{label} must be YYYY-MM-DD, got {value!r}") from exc


def _symbols(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise UniverseManifestError(f"{label}.symbols must be a JSON array")
    normalized = tuple(str(s).strip().upper() for s in value if str(s).strip())
    if not normalized:
        raise UniverseManifestError(f"{label}.symbols must not be empty")
    if len(set(normalized)) != len(normalized):
        raise UniverseManifestError(f"{label}.symbols contains duplicate tickers")
    return normalized


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _previous_month(day: date) -> date:
    return date(day.year - 1, 12, 1) if day.month == 1 else date(day.year, day.month - 1, 1)


def _next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def _monthly_snapshot_symbols(raw: bytes, label: str) -> tuple[str, ...]:
    """Read one archived public monthly snapshot without trusting its filename."""
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UniverseManifestError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(doc, list):
        raise UniverseManifestError(f"{label} must be a JSON array")
    symbols: list[str] = []
    for i, row in enumerate(doc):
        if isinstance(row, str):
            symbols.append(row)
        elif isinstance(row, dict):
            symbol = row.get("Symbol")
            if symbol is None:
                symbol = row.get("symbol")
            if symbol is None:
                raise UniverseManifestError(f"{label}[{i}] has no Symbol")
            symbols.append(str(symbol))
        else:
            raise UniverseManifestError(f"{label}[{i}] must be a string or object")
    return _symbols(symbols, label)


def archive_yfiua_sp500_snapshots(
    out_dir: str | Path,
    *,
    start: date,
    end: date,
    url_template: str = _YFIUA_SP500_URL,
) -> dict[str, Any]:
    """Archive the prior-month snapshots needed for a conservative PIT scan.

    The archive is all-or-nothing: every remote payload is parsed and hashed in
    memory before any local snapshot is published.  The subsequent manifest
    builder reads these immutable local bytes, never the mutable URL.
    """
    if start > end:
        raise UniverseManifestError("archive start must be on or before end")
    needed: list[date] = []
    cursor = _month_start(start)
    final = _month_start(end)
    while cursor <= final:
        needed.append(_previous_month(cursor))
        cursor = _next_month(cursor)

    downloaded: list[tuple[date, bytes, str]] = []
    for source_month in needed:
        url = url_template.format(year=source_month.year, month=source_month.month)
        try:
            with urlopen(url, timeout=30) as response:  # nosec B310: caller-controlled public URL
                raw = response.read()
        except (OSError, URLError) as exc:
            raise UniverseManifestError(
                f"cannot archive PIT source {url}: {exc}; no archive was written"
            ) from exc
        _monthly_snapshot_symbols(raw, url)
        downloaded.append((source_month, raw, url))

    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for source_month, raw, url in downloaded:
        filename = f"{source_month:%Y-%m}.json"
        # Source snapshots are immutable evidence, so a different byte payload
        # for an existing month is an error instead of an in-place revision.
        target = out / filename
        if target.exists() and target.read_bytes() != raw:
            raise UniverseManifestError(
                f"refusing to overwrite archived PIT snapshot with different bytes: {target}"
            )
        if not target.exists():
            atomic_write_bytes(target, raw)
        records.append({
            "month": source_month.isoformat(),
            "filename": filename,
            "url": url,
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "symbols_count": len(_monthly_snapshot_symbols(raw, url)),
        })
    archive = {
        "schema_version": 1,
        "source_quality": SOURCE_QUALITY_PUBLIC,
        "source": "yfiua/index-constituents monthly S&P 500 snapshots",
        "records": records,
    }
    atomic_write_json(out / "archive.json", archive, indent=2, sort_keys=True)
    return archive


def build_lagged_monthly_snapshot_manifest(
    source_dir: str | Path,
    *,
    start: date,
    end: date,
    name: str,
    url_template: str = _YFIUA_SP500_URL,
    source_quality: str = SOURCE_QUALITY_PUBLIC,
) -> dict[str, Any]:
    """Build a complete, conservative PIT manifest from archived monthly bytes.

    A snapshot for month ``M`` only controls the following calendar month.  This
    intentional one-month lag prevents a source refreshed during a month from
    being used to decide a signal earlier in that same month.
    """
    if start > end:
        raise UniverseManifestError("manifest start must be on or before end")
    if source_quality not in _SOURCE_QUALITIES:
        raise UniverseManifestError(
            f"source_quality must be one of {sorted(_SOURCE_QUALITIES)}, got {source_quality!r}"
        )
    source_dir = Path(source_dir).resolve()
    intervals = []
    cursor = _month_start(start)
    final = _month_start(end)
    while cursor <= final:
        source_month = _previous_month(cursor)
        snapshot_path = source_dir / f"{source_month:%Y-%m}.json"
        try:
            raw = snapshot_path.read_bytes()
        except OSError as exc:
            raise UniverseManifestError(
                f"missing archived PIT snapshot {snapshot_path}; expected the prior-month "
                "snapshot for conservative monthly membership"
            ) from exc
        symbols = _monthly_snapshot_symbols(raw, str(snapshot_path))
        interval_end = _next_month(cursor) - timedelta(days=1)
        url = url_template.format(year=source_month.year, month=source_month.month)
        intervals.append({
            "start": max(start, cursor).isoformat(),
            "end": min(end, interval_end).isoformat(),
            "as_of": source_month.isoformat(),
            "source": url,
            "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "symbols": list(symbols),
        })
        cursor = _next_month(cursor)
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "membership_basis": POINT_IN_TIME,
        "source_quality": source_quality,
        "source_notes": (
            "Public monthly snapshot archive. Each snapshot is intentionally applied "
            "only to the following calendar month; this is point-in-time membership "
            "evidence but not a primary/licensed constituent feed."
        ),
        "intervals": intervals,
    }


def write_lagged_monthly_snapshot_manifest(
    out: str | Path,
    source_dir: str | Path,
    *,
    start: date,
    end: date,
    name: str,
    url_template: str = _YFIUA_SP500_URL,
    source_quality: str = SOURCE_QUALITY_PUBLIC,
) -> dict[str, Any]:
    """Build and atomically publish a lagged monthly PIT manifest."""
    manifest = build_lagged_monthly_snapshot_manifest(
        source_dir, start=start, end=end, name=name,
        url_template=url_template, source_quality=source_quality,
    )
    atomic_write_json(Path(out), manifest, indent=2, sort_keys=True)
    return manifest


def _daily_csv_memberships(raw: bytes, label: str) -> list[tuple[date, tuple[str, ...]]]:
    """Parse and validate the dated membership records of one archived CSV."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UniverseManifestError(f"{label} is not UTF-8 text") from exc
    rows = csv.DictReader(io.StringIO(text))
    if not rows.fieldnames or not {"date", "tickers"}.issubset(rows.fieldnames):
        raise UniverseManifestError(f"{label} must have date,tickers CSV columns")
    records: list[tuple[date, tuple[str, ...]]] = []
    prior: date | None = None
    for i, row in enumerate(rows, start=2):
        day = _date(row.get("date"), f"{label}:{i}.date")
        if prior is not None and day <= prior:
            raise UniverseManifestError(f"{label}:{i}.date is duplicate or out of order")
        symbols = _symbols((row.get("tickers") or "").split(","), f"{label}:{i}")
        records.append((day, symbols))
        prior = day
    if not records:
        raise UniverseManifestError(f"{label} has no membership rows")
    return records


def archive_fja_sp500_history(
    out_dir: str | Path,
    *,
    url: str = _FJA_SP500_HISTORY_URL,
) -> dict[str, Any]:
    """Archive one public dated S&P 500 membership CSV as immutable evidence."""
    try:
        with urlopen(url, timeout=30) as response:  # nosec B310: caller-controlled public URL
            raw = response.read()
    except (OSError, URLError) as exc:
        raise UniverseManifestError(f"cannot archive PIT source {url}: {exc}") from exc
    records = _daily_csv_memberships(raw, url)
    out = Path(out_dir).resolve()
    target = out / "sp500_history.csv"
    if target.exists() and target.read_bytes() != raw:
        raise UniverseManifestError(
            f"refusing to overwrite archived PIT source with different bytes: {target}"
        )
    if not target.exists():
        atomic_write_bytes(target, raw)
    archive = {
        "schema_version": 1,
        "source_quality": SOURCE_QUALITY_PUBLIC,
        "source": url,
        "records": [{
            "filename": target.name,
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "first_date": records[0][0].isoformat(),
            "last_date": records[-1][0].isoformat(),
            "rows": len(records),
        }],
    }
    atomic_write_json(out / "archive.json", archive, indent=2, sort_keys=True)
    return archive


def build_lagged_daily_csv_manifest(
    source_path: str | Path,
    *,
    start: date,
    end: date,
    name: str,
    source_url: str = _FJA_SP500_HISTORY_URL,
    source_quality: str = SOURCE_QUALITY_PUBLIC,
) -> dict[str, Any]:
    """Build a conservative PIT manifest from one archived dated-membership CSV.

    The membership listed for a source date becomes eligible the *next calendar
    day*.  This avoids assuming the source was known before that source day's
    market session.  Consecutive identical memberships are coalesced, retaining
    the earliest source date, exact source hash, and full calendar coverage.
    """
    if start > end:
        raise UniverseManifestError("manifest start must be on or before end")
    if source_quality not in _SOURCE_QUALITIES:
        raise UniverseManifestError(
            f"source_quality must be one of {sorted(_SOURCE_QUALITIES)}, got {source_quality!r}"
        )
    source_path = Path(source_path).resolve()
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise UniverseManifestError(f"cannot read archived PIT source {source_path}: {exc}") from exc
    records = _daily_csv_memberships(raw, str(source_path))
    source_hash = "sha256:" + hashlib.sha256(raw).hexdigest()

    # Candidate effective intervals are [source_day + 1, next_source_day].
    # The source before ``start`` is essential for coverage of the first day.
    candidates: list[tuple[date, date, date, tuple[str, ...]]] = []
    for index, (as_of, symbols) in enumerate(records):
        effective_start = as_of + timedelta(days=1)
        next_source = records[index + 1][0] if index + 1 < len(records) else None
        effective_end = next_source if next_source is not None else end
        if effective_end < start or effective_start > end:
            continue
        candidates.append((
            max(start, effective_start), min(end, effective_end), as_of, symbols,
        ))
    if not candidates or candidates[0][0] > start or candidates[-1][1] < end:
        raise UniverseManifestError(
            f"archived PIT source {source_path} cannot cover {start.isoformat()} through "
            f"{end.isoformat()} with a one-calendar-day availability lag"
        )
    cursor = start
    for interval_start, interval_end, _as_of, _symbols_ in candidates:
        if interval_start != cursor:
            raise UniverseManifestError(
                f"archived PIT source {source_path} has no dated membership coverage for "
                f"{cursor.isoformat()} through {(interval_start - timedelta(days=1)).isoformat()}"
            )
        cursor = interval_end + timedelta(days=1)
    if cursor <= end:
        raise UniverseManifestError(
            f"archived PIT source {source_path} has no dated membership coverage for "
            f"{cursor.isoformat()} through {end.isoformat()}"
        )

    intervals: list[dict[str, Any]] = []
    for interval_start, interval_end, as_of, symbols in candidates:
        if intervals and tuple(intervals[-1]["symbols"]) == symbols:
            # Membership did not change; the older as_of is still valid for the
            # extended interval and keeps the proof compact without relaxing time.
            intervals[-1]["end"] = interval_end.isoformat()
            continue
        intervals.append({
            "start": interval_start.isoformat(),
            "end": interval_end.isoformat(),
            "as_of": as_of.isoformat(),
            "source": source_url,
            "source_sha256": source_hash,
            "symbols": list(symbols),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "membership_basis": POINT_IN_TIME,
        "source_quality": source_quality,
        "source_notes": (
            "Public dated S&P 500 membership archive. Each source-day snapshot is "
            "applied no earlier than the following calendar day. It is reproducible "
            "PIT evidence but not a primary/licensed constituent feed."
        ),
        "intervals": intervals,
    }


def write_lagged_daily_csv_manifest(
    out: str | Path,
    source_path: str | Path,
    *,
    start: date,
    end: date,
    name: str,
    source_url: str = _FJA_SP500_HISTORY_URL,
    source_quality: str = SOURCE_QUALITY_PUBLIC,
) -> dict[str, Any]:
    """Build and atomically publish a lagged daily-CSV PIT manifest."""
    manifest = build_lagged_daily_csv_manifest(
        source_path, start=start, end=end, name=name, source_url=source_url,
        source_quality=source_quality,
    )
    atomic_write_json(Path(out), manifest, indent=2, sort_keys=True)
    return manifest


@dataclass(frozen=True)
class UniverseInterval:
    """One inclusive effective-membership interval from a declared source."""

    start: date
    end: date
    as_of: date
    source: str
    symbols: tuple[str, ...]
    source_sha256: str | None = None

    def intersects(self, start: date, end: date) -> bool:
        return self.start <= end and start <= self.end

    def selected(self, start: date, end: date) -> "UniverseInterval":
        return UniverseInterval(
            start=max(self.start, start),
            end=min(self.end, end),
            as_of=self.as_of,
            source=self.source,
            symbols=self.symbols,
            source_sha256=self.source_sha256,
        )

    def provenance(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "as_of": self.as_of.isoformat(),
            "source": self.source,
            "source_sha256": self.source_sha256,
            "symbols_count": len(self.symbols),
            "symbols_sha256": "sha256:" + hashlib.sha256(
                "\n".join(self.symbols).encode("utf-8")
            ).hexdigest(),
        }


@dataclass(frozen=True)
class ResearchUniverse:
    """Parsed manifest plus exact-byte provenance for historical research."""

    name: str
    membership_basis: str
    source_quality: str
    intervals: tuple[UniverseInterval, ...]
    path: Path
    manifest_sha256: str

    def require_point_in_time(self) -> None:
        if self.membership_basis != POINT_IN_TIME:
            raise UniverseManifestError(
                f"research universe {self.path} has membership_basis="
                f"{self.membership_basis!r}, not {POINT_IN_TIME!r}. A current snapshot "
                "must never be used to score historical strategy performance."
            )

    def slices_for(self, start: date, end: date) -> list[UniverseInterval]:
        """Return selected membership intervals, or fail on any coverage gap."""
        self.require_point_in_time()
        if start > end:
            raise UniverseManifestError("requested scan start must be on or before end")
        cursor = start
        selected: list[UniverseInterval] = []
        for interval in self.intervals:
            if interval.end < cursor:
                continue
            if interval.start > cursor:
                raise UniverseManifestError(
                    f"point-in-time universe {self.path} has no membership coverage for "
                    f"{cursor.isoformat()} through {(interval.start - timedelta(days=1)).isoformat()}"
                )
            selected.append(interval.selected(cursor, end))
            if interval.end >= end:
                return selected
            cursor = interval.end + timedelta(days=1)
        raise UniverseManifestError(
            f"point-in-time universe {self.path} has no membership coverage for "
            f"{cursor.isoformat()} through {end.isoformat()}"
        )

    def provenance(self, start: date, end: date) -> dict[str, Any]:
        """Immutable provenance record for a particular requested scan range."""
        intervals = self.slices_for(start, end)
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "membership_basis": self.membership_basis,
            "source_quality": self.source_quality,
            "manifest_path": str(self.path),
            "manifest_sha256": self.manifest_sha256,
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "intervals": [interval.provenance() for interval in intervals],
        }


def load_research_universe(path: str | Path) -> ResearchUniverse:
    """Parse and structurally validate a versioned universe manifest.

    Parsing accepts a non-PIT basis so the caller receives a precise failure at
    the policy boundary (:meth:`ResearchUniverse.require_point_in_time`) rather
    than being tempted to relabel a current snapshot.  The research scan itself
    always invokes that policy boundary before any data is fetched or changed.
    """
    path = Path(path).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UniverseManifestError(f"cannot read universe manifest {path}: {exc}") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UniverseManifestError(f"universe manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise UniverseManifestError("universe manifest root must be a JSON object")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise UniverseManifestError(
            f"universe manifest schema_version must be {SCHEMA_VERSION}, got "
            f"{doc.get('schema_version')!r}"
        )
    name = str(doc.get("name") or "").strip()
    if not name:
        raise UniverseManifestError("universe manifest name must be non-empty")
    basis = str(doc.get("membership_basis") or "").strip()
    if basis not in {POINT_IN_TIME, CURRENT_SNAPSHOT}:
        raise UniverseManifestError(
            "membership_basis must be 'point_in_time' or 'current_snapshot'"
        )
    source_quality = str(doc.get("source_quality") or SOURCE_QUALITY_UNQUALIFIED).strip()
    if source_quality not in _SOURCE_QUALITIES:
        raise UniverseManifestError(
            f"source_quality must be one of {sorted(_SOURCE_QUALITIES)}, got {source_quality!r}"
        )
    raw_intervals = doc.get("intervals")
    if not isinstance(raw_intervals, list) or not raw_intervals:
        raise UniverseManifestError("universe manifest intervals must be a non-empty JSON array")

    intervals: list[UniverseInterval] = []
    prior_end: date | None = None
    for i, item in enumerate(raw_intervals):
        label = f"intervals[{i}]"
        if not isinstance(item, dict):
            raise UniverseManifestError(f"{label} must be a JSON object")
        start = _date(item.get("start"), f"{label}.start")
        end = _date(item.get("end"), f"{label}.end")
        as_of = _date(item.get("as_of"), f"{label}.as_of")
        source = str(item.get("source") or "").strip()
        if start > end:
            raise UniverseManifestError(f"{label}.start must be on or before end")
        if as_of > start:
            raise UniverseManifestError(
                f"{label}.as_of ({as_of}) cannot be after its effective start ({start})"
            )
        if not source:
            raise UniverseManifestError(f"{label}.source must be non-empty")
        if prior_end is not None and start <= prior_end:
            raise UniverseManifestError(f"{label} overlaps or is out of order with the prior interval")
        source_sha256 = item.get("source_sha256")
        if source_sha256 is not None:
            source_sha256 = str(source_sha256)
            if not source_sha256.startswith("sha256:"):
                raise UniverseManifestError(f"{label}.source_sha256 must start with 'sha256:'")
        intervals.append(UniverseInterval(
            start=start,
            end=end,
            as_of=as_of,
            source=source,
            symbols=_symbols(item.get("symbols"), label),
            source_sha256=source_sha256,
        ))
        prior_end = end

    return ResearchUniverse(
        name=name,
        membership_basis=basis,
        source_quality=source_quality,
        intervals=tuple(intervals),
        path=path,
        manifest_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cup_handle.research_universe",
        description="Archive and materialize source-qualified PIT universe manifests.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    archive = sub.add_parser("archive-yfiua-sp500", help="archive required public monthly source snapshots")
    build = sub.add_parser("build-lagged-monthly", help="build a PIT manifest from an archived monthly source")
    archive_fja = sub.add_parser("archive-fja-sp500", help="archive public dated S&P 500 membership CSV")
    build_fja = sub.add_parser("build-lagged-daily-csv", help="build a PIT manifest from archived dated membership CSV")
    for command in (archive, build):
        command.add_argument("--start", required=True, help="inclusive YYYY-MM-DD")
        command.add_argument("--end", required=True, help="inclusive YYYY-MM-DD")
    archive.add_argument("--out-dir", required=True)
    archive.add_argument("--url-template", default=_YFIUA_SP500_URL)
    build.add_argument("--source-dir", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--name", required=True)
    build.add_argument("--url-template", default=_YFIUA_SP500_URL)
    build.add_argument("--source-quality", default=SOURCE_QUALITY_PUBLIC,
                       choices=sorted(_SOURCE_QUALITIES))
    archive_fja.add_argument("--out-dir", required=True)
    archive_fja.add_argument("--url", default=_FJA_SP500_HISTORY_URL)
    build_fja.add_argument("--start", required=True, help="inclusive YYYY-MM-DD")
    build_fja.add_argument("--end", required=True, help="inclusive YYYY-MM-DD")
    build_fja.add_argument("--source-path", required=True)
    build_fja.add_argument("--out", required=True)
    build_fja.add_argument("--name", required=True)
    build_fja.add_argument("--source-url", default=_FJA_SP500_HISTORY_URL)
    build_fja.add_argument("--source-quality", default=SOURCE_QUALITY_PUBLIC,
                           choices=sorted(_SOURCE_QUALITIES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "archive-yfiua-sp500":
            start, end = _date(args.start, "start"), _date(args.end, "end")
            archive = archive_yfiua_sp500_snapshots(
                args.out_dir, start=start, end=end, url_template=args.url_template,
            )
            print(f"archived {len(archive['records'])} PIT source snapshot(s) → {args.out_dir}")
        elif args.command == "build-lagged-monthly":
            start, end = _date(args.start, "start"), _date(args.end, "end")
            manifest = write_lagged_monthly_snapshot_manifest(
                args.out, args.source_dir, start=start, end=end, name=args.name,
                url_template=args.url_template, source_quality=args.source_quality,
            )
            print(f"wrote {len(manifest['intervals'])} PIT interval(s) → {args.out}")
        elif args.command == "archive-fja-sp500":
            archive = archive_fja_sp500_history(args.out_dir, url=args.url)
            print(f"archived {archive['records'][0]['rows']} PIT source row(s) → {args.out_dir}")
        else:
            start, end = _date(args.start, "start"), _date(args.end, "end")
            manifest = write_lagged_daily_csv_manifest(
                args.out, args.source_path, start=start, end=end, name=args.name,
                source_url=args.source_url, source_quality=args.source_quality,
            )
            print(f"wrote {len(manifest['intervals'])} PIT interval(s) → {args.out}")
    except (UniverseManifestError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
