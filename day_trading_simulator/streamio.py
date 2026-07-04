"""Shared JSON-lines helpers for the replay tick stream.

The replay/step tools write a stream of JSON objects, one per line: a single
``meta`` line, a ``tick`` line per minute, then a terminal ``end`` (or ``error``)
line. Three consumers used to each carry their own copy of the parser
(``recorder``, ``feed``, ``step``); this module is the single source of truth so
they can't drift.

All readers tolerate a partially-written final line — the stream may be polled
mid-write — by skipping any line that doesn't parse as JSON yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def read_jsonl(path: str | Path) -> list[dict]:
    """Return every complete JSON object in ``path`` (missing file → ``[]``)."""
    out: list[dict] = []
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # last line may be half-flushed; ignore and let the next read see it
            continue
    return out


def parse_stream(path: str | Path) -> tuple[Optional[dict], list[dict], Optional[dict]]:
    """Split a stream file into ``(meta, ticks, end)``.

    ``meta`` is the setup line (or None if not written yet), ``ticks`` the list of
    per-minute bars in file order, and ``end`` the terminal ``end``/``error`` line
    (or None if the stream hasn't finished).
    """
    meta: Optional[dict] = None
    ticks: list[dict] = []
    end: Optional[dict] = None
    for obj in read_jsonl(path):
        t = obj.get("type")
        if t == "meta":
            meta = obj
        elif t == "tick":
            ticks.append(obj)
        elif t in ("end", "error"):
            end = obj
    return meta, ticks, end
