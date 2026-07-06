"""Output store — idempotent SQLite table of entry setups.

Uniqueness (SPEC §5): a setup is keyed by ``(ticker, date, pattern)`` — at most
one primary entry per ticker per day per pattern. Writes upsert on that key, so
re-running the scanner over the same range never duplicates a setup; it refreshes
the row in place. ``setup_id = sha1("{ticker}|{date}|{pattern}")``.
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .patterns import Entry
from .fsutils import atomic_write_text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    setup_id     TEXT PRIMARY KEY,
    ticker       TEXT NOT NULL,
    date         TEXT NOT NULL,
    time_et      TEXT NOT NULL,
    pattern      TEXT NOT NULL,
    entry_px     REAL,
    bar_close    REAL,
    gap_pct      REAL,
    rvol         REAL,
    float_shares REAL,
    bar_vol_mult REAL,
    reason       TEXT,
    updated_at   TEXT NOT NULL,
    UNIQUE (ticker, date, pattern)
);
CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date);
"""


def setup_id(ticker: str, day, pattern: str) -> str:
    raw = f"{ticker.upper()}|{day.isoformat()}|{pattern}"
    return hashlib.sha1(raw.encode()).hexdigest()


class EntryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def upsert(self, e: Entry) -> None:
        sid = setup_id(e.ticker, e.day, e.pattern)
        self.conn.execute(
            """
            INSERT INTO entries (setup_id, ticker, date, time_et, pattern,
                entry_px, bar_close, gap_pct, rvol, float_shares, bar_vol_mult,
                reason, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, date, pattern) DO UPDATE SET
                time_et=excluded.time_et,
                entry_px=excluded.entry_px,
                bar_close=excluded.bar_close,
                gap_pct=excluded.gap_pct,
                rvol=excluded.rvol,
                float_shares=excluded.float_shares,
                bar_vol_mult=excluded.bar_vol_mult,
                reason=excluded.reason,
                updated_at=excluded.updated_at
            """,
            (
                sid, e.ticker, e.day.isoformat(), e.time_et, e.pattern,
                e.entry_px, e.bar_close, e.gap_pct, e.rvol, e.float_shares,
                e.bar_vol_mult, e.reason,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def all_rows(self) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute(
            "SELECT * FROM entries ORDER BY date, time_et, ticker"
        ).fetchall()

    def dump_text(self, path: str | Path) -> Path:
        """Regenerate a human-readable text dump from the table."""
        path = Path(path)
        lines = []
        for r in self.all_rows():
            lines.append(
                f"{r['date']}  {r['time_et']} ET  {r['ticker']:<6}  "
                f"${r['entry_px']:.2f}  | {r['reason']}"
            )
        atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))
        return path

    def dump_csv(self, path: str | Path) -> Path:
        import csv

        path = Path(path)
        rows = self.all_rows()
        cols = [
            "ticker", "date", "time_et", "pattern", "entry_px", "bar_close",
            "gap_pct", "rvol", "float_shares", "bar_vol_mult", "reason",
        ]
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
        atomic_write_text(path, out.getvalue())
        return path

    def close(self) -> None:
        self.conn.close()
