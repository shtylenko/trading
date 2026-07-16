"""Output store — idempotent SQLite table of entry setups.

Uniqueness: a setup is keyed by ``(strategy, ticker, date, pattern)`` — at most
one primary entry per strategy/ticker/day/pattern. Writes upsert on that key.
``setup_id = sha1("{strategy}|{ticker}|{date}|{pattern}")``.

Legacy DBs created before multi-strategy support used ``(ticker, date, pattern)``
only; :meth:`EntryStore.__init__` migrates them in place (adds ``strategy`` and
``features_json`` columns, defaults strategy to ``warrior``).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .fsutils import atomic_write_text
from .models import Entry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    setup_id     TEXT PRIMARY KEY,
    strategy     TEXT NOT NULL DEFAULT 'warrior',
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
    features_json TEXT,
    updated_at   TEXT NOT NULL,
    UNIQUE (strategy, ticker, date, pattern)
);
CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date);
CREATE INDEX IF NOT EXISTS idx_entries_strategy ON entries(strategy);
"""


def setup_id(ticker: str, day, pattern: str, strategy: str = "warrior") -> str:
    raw = f"{strategy}|{ticker.upper()}|{day.isoformat() if hasattr(day, 'isoformat') else day}|{pattern}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _legacy_setup_id(ticker: str, day, pattern: str) -> str:
    """Pre-multi-strategy id (no strategy prefix)."""
    raw = f"{ticker.upper()}|{day.isoformat() if hasattr(day, 'isoformat') else day}|{pattern}"
    return hashlib.sha1(raw.encode()).hexdigest()


class EntryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._migrate()
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def _migrate(self) -> None:
        """Add strategy/features columns and rebuild unique index if needed."""
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        )
        if cur.fetchone() is None:
            return
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(entries)").fetchall()}
        if "strategy" not in cols:
            self.conn.execute(
                "ALTER TABLE entries ADD COLUMN strategy TEXT NOT NULL DEFAULT 'warrior'"
            )
        if "features_json" not in cols:
            self.conn.execute("ALTER TABLE entries ADD COLUMN features_json TEXT")
        # Rebuild table if old UNIQUE(ticker,date,pattern) still present without strategy.
        # Detect via sqlite_master sql text.
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        sql = (row[0] or "") if row else ""
        if "UNIQUE (strategy, ticker, date, pattern)" not in sql and "UNIQUE(strategy, ticker, date, pattern)" not in sql:
            # If the table still has the old 3-col unique, rebuild.
            if "UNIQUE (ticker, date, pattern)" in sql or "UNIQUE(ticker, date, pattern)" in sql:
                self._rebuild_with_strategy_unique()
        self.conn.commit()

    def _rebuild_with_strategy_unique(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries_new (
                setup_id     TEXT PRIMARY KEY,
                strategy     TEXT NOT NULL DEFAULT 'warrior',
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
                features_json TEXT,
                updated_at   TEXT NOT NULL,
                UNIQUE (strategy, ticker, date, pattern)
            );
            INSERT OR IGNORE INTO entries_new
                (setup_id, strategy, ticker, date, time_et, pattern, entry_px,
                 bar_close, gap_pct, rvol, float_shares, bar_vol_mult, reason,
                 features_json, updated_at)
            SELECT
                setup_id,
                COALESCE(strategy, 'warrior'),
                ticker, date, time_et, pattern, entry_px, bar_close, gap_pct,
                rvol, float_shares, bar_vol_mult, reason,
                features_json, updated_at
            FROM entries;
            DROP TABLE entries;
            ALTER TABLE entries_new RENAME TO entries;
            CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date);
            CREATE INDEX IF NOT EXISTS idx_entries_strategy ON entries(strategy);
            """
        )
        # Rehash setup_ids to include strategy for consistency going forward.
        rows = self.conn.execute(
            "SELECT setup_id, strategy, ticker, date, pattern FROM entries"
        ).fetchall()
        for sid, strategy, ticker, day, pattern in rows:
            new_sid = setup_id(ticker, day, pattern, strategy or "warrior")
            if new_sid != sid:
                # avoid PK collision: delete+insert if needed
                self.conn.execute(
                    "UPDATE entries SET setup_id=? WHERE setup_id=?",
                    (new_sid, sid),
                )

    def __enter__(self) -> "EntryStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _upsert(self, e: Entry) -> None:
        strategy = getattr(e, "strategy", None) or "warrior"
        sid = setup_id(e.ticker, e.day, e.pattern, strategy)
        features = getattr(e, "features", None) or {}
        # Invalid JSON numbers create artifacts the viewer cannot safely consume.
        features_json = json.dumps(features, sort_keys=True, allow_nan=False) if features else None
        self.conn.execute(
            """
            INSERT INTO entries (setup_id, strategy, ticker, date, time_et, pattern,
                entry_px, bar_close, gap_pct, rvol, float_shares, bar_vol_mult,
                reason, features_json, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(strategy, ticker, date, pattern) DO UPDATE SET
                time_et=excluded.time_et,
                entry_px=excluded.entry_px,
                bar_close=excluded.bar_close,
                gap_pct=excluded.gap_pct,
                rvol=excluded.rvol,
                float_shares=excluded.float_shares,
                bar_vol_mult=excluded.bar_vol_mult,
                reason=excluded.reason,
                features_json=excluded.features_json,
                updated_at=excluded.updated_at,
                setup_id=excluded.setup_id
            """,
            (
                sid, strategy, e.ticker, e.day.isoformat(), e.time_et, e.pattern,
                e.entry_px, e.bar_close, e.gap_pct, e.rvol, e.float_shares,
                e.bar_vol_mult, e.reason, features_json,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    def upsert(self, e: Entry) -> None:
        self._upsert(e)
        self.conn.commit()

    def sync_scope(
        self,
        entries: list[Entry],
        *,
        strategy: str,
        tickers: list[str],
        start_day: str,
        end_day: str,
    ) -> int:
        """Atomically replace a successfully scanned ticker/date scope.

        A full scanner refresh must remove rows that no longer satisfy the current
        rules, rather than leaving prior-config signals in the active output.  The
        caller supplies only successfully scanned tickers, so provider failures can
        never delete a ticker's last known rows.

        Returns the number of stale rows removed.
        """
        scope = sorted({str(t).upper() for t in tickers if str(t).strip()})
        if not scope:
            return 0
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _scan_scope "
                "(ticker TEXT PRIMARY KEY)"
            )
            self.conn.execute("DELETE FROM _scan_scope")
            self.conn.executemany(
                "INSERT OR IGNORE INTO _scan_scope(ticker) VALUES (?)",
                [(ticker,) for ticker in scope],
            )
            self.conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _scan_keys "
                "(ticker TEXT, date TEXT, pattern TEXT, PRIMARY KEY(ticker, date, pattern))"
            )
            self.conn.execute("DELETE FROM _scan_keys")
            self.conn.executemany(
                "INSERT OR IGNORE INTO _scan_keys(ticker, date, pattern) VALUES (?,?,?)",
                [
                    (e.ticker.upper(), e.day.isoformat(), e.pattern)
                    for e in entries
                    if (getattr(e, "strategy", None) or "warrior") == strategy
                ],
            )
            for entry in entries:
                self._upsert(entry)
            cur = self.conn.execute(
                """
                DELETE FROM entries
                WHERE strategy=?
                  AND date >= ? AND date <= ?
                  AND ticker IN (SELECT ticker FROM _scan_scope)
                  AND NOT EXISTS (
                    SELECT 1 FROM _scan_keys k
                    WHERE k.ticker=entries.ticker
                      AND k.date=entries.date
                      AND k.pattern=entries.pattern
                  )
                """,
                (strategy, start_day, end_day),
            )
            removed = cur.rowcount if cur.rowcount >= 0 else 0
            self.conn.commit()
            return removed
        except Exception:
            self.conn.rollback()
            raise

    def count(self, strategy: Optional[str] = None) -> int:
        if strategy:
            return self.conn.execute(
                "SELECT COUNT(*) FROM entries WHERE strategy=?", (strategy,)
            ).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def all_rows(self, strategy: Optional[str] = None) -> list[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.row_factory = sqlite3.Row
        if strategy:
            return cur.execute(
                "SELECT * FROM entries WHERE strategy=? ORDER BY date, time_et, ticker",
                (strategy,),
            ).fetchall()
        return cur.execute(
            "SELECT * FROM entries ORDER BY date, time_et, ticker"
        ).fetchall()

    def dump_text(self, path: str | Path, strategy: Optional[str] = None) -> Path:
        path = Path(path)
        lines = []
        for r in self.all_rows(strategy=strategy):
            strat = r["strategy"] if "strategy" in r.keys() else "warrior"
            lines.append(
                f"{r['date']}  {r['time_et']} ET  {r['ticker']:<6}  "
                f"[{strat}]  ${r['entry_px']:.2f}  | {r['reason']}"
            )
        atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))
        return path

    def dump_csv(self, path: str | Path, strategy: Optional[str] = None) -> Path:
        path = Path(path)
        rows = self.all_rows(strategy=strategy)
        cols = [
            "setup_id", "strategy", "ticker", "date", "time_et", "pattern", "entry_px",
            "bar_close", "gap_pct", "rvol", "float_shares", "bar_vol_mult",
            "reason", "features_json", "updated_at",
        ]
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = {c: r[c] if c in r.keys() else None for c in cols}
            w.writerow(row)
        atomic_write_text(path, out.getvalue())
        return path

    def close(self) -> None:
        self.conn.close()
