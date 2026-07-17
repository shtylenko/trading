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

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
POINT_IN_TIME = "point_in_time"
CURRENT_SNAPSHOT = "current_snapshot"


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
        intervals=tuple(intervals),
        path=path,
        manifest_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
    )
