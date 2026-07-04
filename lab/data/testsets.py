from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

TESTSETS_DIR = Path(__file__).resolve().parent.parent / "testsets"


@dataclass
class DateRange:
    start: date
    end: date
    label: str | None = None
    role: str = "eval"


@dataclass
class TestSet:
    name: str
    description: str = ""
    date_ranges: list[DateRange] = field(default_factory=list)
    universe: str | None = None
    universe_policy: str = "point_in_time"
    tickers: list[str] | None = None
    candidate_limit: int | None = None
    notes: str = ""


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_testset(name: str) -> TestSet:
    path = TESTSETS_DIR / f"{name}.yaml"
    if not path.exists():
        path = TESTSETS_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"TestSet '{name}' not found in {TESTSETS_DIR}")

    data = yaml.safe_load(path.read_text()) or {}
    ranges = [
        DateRange(
            start=_parse_date(r["start"]),
            end=_parse_date(r["end"]),
            label=r.get("label"),
            role=r.get("role", "eval"),
        )
        for r in data.get("date_ranges", [])
    ]
    return TestSet(
        name=data.get("name", name),
        description=data.get("description", ""),
        date_ranges=ranges,
        universe=data.get("universe"),
        universe_policy=data.get("universe_policy", "point_in_time"),
        tickers=data.get("tickers"),
        candidate_limit=data.get("candidate_limit"),
        notes=data.get("notes", ""),
    )


def list_testsets() -> list[str]:
    if not TESTSETS_DIR.exists():
        return []
    names = {p.stem for p in TESTSETS_DIR.glob("*.yaml")}
    names.update(p.stem for p in TESTSETS_DIR.glob("*.yml"))
    return sorted(names)
