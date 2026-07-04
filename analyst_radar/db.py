"""
Schema initialization, migrations, and seed data for Analyst Radar.

Mechanical data layer only — see spec.md §5 (Python/LLM boundary). This module
creates the SQLite schema, applies indexes/CHECK constraints, and seeds the 25
tracked analysts. It seeds NO tickers: the `tickers` table accumulates as
interviews are processed and proposed symbols validate against
``trading.marketdata`` (spec §5.2).
"""
import sqlite3
import os
from datetime import datetime, timezone


DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "analyst_radar.db")


def _now() -> str:
    """ISO-8601 UTC timestamp — all datetimes in SQLite are ISO strings (spec §5.1)."""
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS analysts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    firm        TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    bio         TEXT    DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url     TEXT    NOT NULL,
    youtube_id      TEXT    NOT NULL UNIQUE,
    title           TEXT    NOT NULL,
    channel_name    TEXT    NOT NULL,
    published_date  TEXT    NOT NULL,
    transcript_text TEXT,
    summary         TEXT,
    fetched_at      TEXT,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tickers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL UNIQUE,
    company_name TEXT,
    sector       TEXT,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id    INTEGER NOT NULL,
    analyst_id      INTEGER NOT NULL,
    prediction_text TEXT    NOT NULL,
    prediction_type TEXT    NOT NULL DEFAULT 'other'
        CHECK (prediction_type IN
            ('price_target','sector_call','macro_call','direction_call','earnings_call','other')),
    direction       TEXT    NOT NULL DEFAULT 'neutral'
        CHECK (direction IN ('bullish','bearish','neutral')),
    confidence      TEXT
        CHECK (confidence IS NULL OR confidence IN ('high','medium','low')),
    time_horizon    TEXT,
    raw_quote       TEXT,
    content_hash    TEXT    NOT NULL UNIQUE,
    prompt_version  TEXT,
    model           TEXT,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (interview_id) REFERENCES interviews(id),
    FOREIGN KEY (analyst_id)   REFERENCES analysts(id)
);

CREATE TABLE IF NOT EXISTS prediction_tickers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id  INTEGER NOT NULL,
    ticker_id      INTEGER NOT NULL,
    UNIQUE(prediction_id, ticker_id),
    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    FOREIGN KEY (ticker_id)     REFERENCES tickers(id)
);

CREATE TABLE IF NOT EXISTS analyst_candidates (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT    NOT NULL,
    firm               TEXT,
    role               TEXT,
    bio                TEXT,
    source_youtube_url TEXT,
    source_interview_title TEXT,
    discovered_at      TEXT    NOT NULL,
    status             TEXT    NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected')),
    reviewed_at        TEXT,
    notes              TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_name ON analyst_candidates(name);

CREATE TABLE IF NOT EXISTS unresolved_mentions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id      INTEGER NOT NULL,
    raw_symbol         TEXT    NOT NULL,
    context            TEXT,
    resolved_ticker_id INTEGER,
    created_at         TEXT    NOT NULL,
    FOREIGN KEY (prediction_id)      REFERENCES predictions(id),
    FOREIGN KEY (resolved_ticker_id) REFERENCES tickers(id)
);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL UNIQUE,
    outcome       TEXT    NOT NULL
        CHECK (outcome IN ('correct','incorrect','partial','unresolvable')),
    actual_value  TEXT,
    resolved_at   TEXT,
    notes         TEXT,
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    phase             TEXT,
    started_at        TEXT    NOT NULL,
    finished_at       TEXT,
    interviews_found  INTEGER DEFAULT 0,
    interviews_new    INTEGER DEFAULT 0,
    predictions_found INTEGER DEFAULT 0,
    status            TEXT    NOT NULL DEFAULT 'running',
    error_message     TEXT
);

CREATE TABLE IF NOT EXISTS channels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    youtube_channel_id TEXT NOT NULL UNIQUE,
    youtube_handle  TEXT,
    description     TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_scanned_at TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

-- Indexes for the spec §3 query patterns.
CREATE INDEX IF NOT EXISTS idx_predictions_analyst    ON predictions(analyst_id);
CREATE INDEX IF NOT EXISTS idx_predictions_interview  ON predictions(interview_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);
CREATE INDEX IF NOT EXISTS idx_pt_ticker              ON prediction_tickers(ticker_id);
CREATE INDEX IF NOT EXISTS idx_pt_prediction          ON prediction_tickers(prediction_id);
CREATE INDEX IF NOT EXISTS idx_interviews_published   ON interviews(published_date);
CREATE INDEX IF NOT EXISTS idx_interviews_youtube_id  ON interviews(youtube_id);
"""

# ALTER TABLE migrations for columns added after initial schema.
# Each statement is attempted independently; failures are silently ignored
# so that init_db() remains idempotent on both new and existing databases.
_MIGRATIONS = [
    "ALTER TABLE tickers ADD COLUMN bull_bear_indicator REAL",
    "ALTER TABLE tickers ADD COLUMN bull_bear_updated_at TEXT",
    "ALTER TABLE tickers ADD COLUMN bull_bear_summary TEXT",
]

SEED_ANALYSTS = [
    ("Tom Lee",            "Fundstrat",              "Head of Research"),
    ("Dan Ives",           "Wedbush Securities",     "Tech Analyst"),
    ("Mike Wilson",        "Morgan Stanley",         "Chief U.S. Equity Strategist & CIO"),
    ("David Kostin",       "Goldman Sachs",          "Chief U.S. Equity Strategist"),
    ("Lori Calvasina",     "RBC Capital Markets",    "Head of U.S. Equity Strategy"),
    ("Savita Subramanian", "Bank of America",        "Head of U.S. Equity & Quant Strategy"),
    ("Brian Belski",       "Humilis / BMO",          "Chief Investment Strategist"),
    ("Liz Ann Sonders",    "Charles Schwab",         "Chief Investment Strategist"),
    ("Ed Yardeni",         "Yardeni Research",       "President"),
    ("Barry Bannister",    "Stifel",                 "Chief Equity Strategist"),
    ("Katie Stockton",     "Fairlead Strategies",    "Founder & Managing Partner"),
    ("Cameron Dawson",     "NewEdge Wealth",         "Chief Investment Officer"),
    ("Stephanie Link",     "Hightower Advisors",     "Chief Investment Strategist"),
    ("Josh Brown",         "Ritholtz Wealth Mgmt",   "CEO, CNBC Contributor"),
    ("Chris Vermeulen",    "The Technical Traders",  "Chief Market Strategist"),
    ("Torsten Slok",       "Apollo Global Mgmt",     "Chief Economist"),
    ("David Rosenberg",    "Rosenberg Research",     "Founder & President"),
    ("Jeremy Siegel",      "Wharton / WisdomTree",   "Senior Economist"),
    ("Jason Furman",       "Harvard Kennedy School", "Professor, Former CEA Chair"),
    ("Mark Zandi",         "Moody's Analytics",      "Chief Economist"),
    ("Michael Darda",      "Roth Capital Partners",  "Chief Economist & Macro Strategist"),
    ("Jim Paulsen",        "Paulsen Perspectives",   "Author & Strategist"),
    ("Peter Boockvar",     "Bleakley Financial",     "CIO, The Boock Report"),
    ("David Zervos",       "Jefferies",              "Chief Market Strategist"),
    ("Lance Roberts",      "RIA Advisors",           "Chief Portfolio Strategist"),
    ("Gene Munster",       "Deepwater Asset Mgmt",   "Managing Partner"),
]


def get_db() -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating the dir if needed."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    """Create all tables and indexes if not already present, then apply migrations."""
    conn = get_db()
    conn.executescript(SCHEMA)
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    return conn


def update_ticker_sentiment(
    conn,
    ticker: str,
    indicator: float,
    summary: str,
) -> None:
    """Write the bull/bear indicator (-10..+10) and ~1000-word reasoning for a ticker.

    Indicator scale: -10 = strongly bearish, 0 = neutral, +10 = strongly bullish.
    Upserts: updates existing row if ticker already in the table.
    """
    if not -10 <= indicator <= 10:
        raise ValueError(f"indicator must be in [-10, 10], got {indicator}")
    now = _now()
    conn.execute(
        """UPDATE tickers
              SET bull_bear_indicator  = ?,
                  bull_bear_updated_at = ?,
                  bull_bear_summary    = ?
            WHERE ticker = ?""",
        (indicator, now, summary, ticker),
    )
    conn.commit()


def seed_analysts(conn: "sqlite3.Connection | None" = None) -> int:
    """Insert the 25 seed analysts, skipping any already present by name.
    Returns the count of newly inserted rows."""
    if conn is None:
        conn = get_db()
    now = _now()
    inserted = 0
    for name, firm, role in SEED_ANALYSTS:
        cur = conn.execute("SELECT id FROM analysts WHERE name = ?", (name,))
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO analysts (name, firm, role, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, firm, role, now, now),
            )
            inserted += 1
    conn.commit()
    return inserted


def store_candidate(
    conn,
    name: str,
    firm: str = "",
    role: str = "",
    bio: str = "",
    source_youtube_url: str = "",
    source_interview_title: str = "",
) -> bool:
    """Queue an analyst discovered in the wild for human review.

    Idempotent: a candidate with the same name is inserted once (UNIQUE index).
    Returns True if a new row was created, False if already queued.
    Also a no-op if the analyst is already in the `analysts` table.
    """
    already = conn.execute(
        "SELECT id FROM analysts WHERE name = ?", (name,)
    ).fetchone()
    if already:
        return False
    cur = conn.execute(
        """INSERT OR IGNORE INTO analyst_candidates
               (name, firm, role, bio, source_youtube_url,
                source_interview_title, discovered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, firm, role, bio, source_youtube_url,
         source_interview_title, _now()),
    )
    conn.commit()
    return cur.rowcount > 0


def approve_candidate(conn, candidate_id: int) -> int:
    """Promote a pending candidate into the `analysts` table as active.

    Returns the new analyst.id, or raises if the candidate is not found / not pending.
    """
    row = conn.execute(
        "SELECT * FROM analyst_candidates WHERE id = ? AND status = 'pending'",
        (candidate_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"No pending candidate with id={candidate_id}")
    now = _now()
    cur = conn.execute(
        "INSERT INTO analysts (name, firm, role, bio, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?)",
        (row[1] if isinstance(row, tuple) else row["name"],
         row[2] if isinstance(row, tuple) else row["firm"] or "",
         row[3] if isinstance(row, tuple) else row["role"] or "",
         row[4] if isinstance(row, tuple) else row["bio"] or "",
         now, now),
    )
    analyst_id = cur.lastrowid
    conn.execute(
        "UPDATE analyst_candidates SET status='approved', reviewed_at=? WHERE id=?",
        (now, candidate_id),
    )
    conn.commit()
    return analyst_id


def reject_candidate(conn, candidate_id: int, notes: str = "") -> None:
    """Mark a candidate as rejected."""
    conn.execute(
        "UPDATE analyst_candidates SET status='rejected', reviewed_at=?, notes=? WHERE id=?",
        (_now(), notes, candidate_id),
    )
    conn.commit()


SEED_CHANNELS = [
    ("CNBC Television",       "UCrp_UI8XtuYfpiqluWLD7Lw", "@CNBCtelevision",   "US business news network — Halftime, Squawk Box, Closing Bell"),
    ("Bloomberg Television",  "UCIALMKvObZNtJ6AmdCLP7Lg", "@BloombergTV",      "Global financial news network — Surveillance, Open Interest"),
    ("Bloomberg Podcasts",    "UChF5O40UBqAc82I7-i5ig6A", "@BloombergPodcasts","Bloomberg podcast interviews and long-form discussions"),
    ("Schwab Network",        None, None,                                      "Charles Schwab's market analysis and strategy channel"),
    ("Kitco NEWS",            None, None,                                      "Precious metals and mining news, analyst interviews"),
    ("Yahoo Finance",         None, None,                                      "Yahoo Finance interviews, market news and analysis"),
    ("Fox Business",          None, None,                                      "Fox Business Network stock market and investing coverage"),
    ("Charles Schwab",        None, None,                                      "Schwab's On Investing podcast and market commentary"),
    ("The Compound",          None, None,                                      "Josh Brown's finance podcast network"),
]


def seed_channels(conn) -> int:
    """Insert the seed financial media channels, skipping existing ones by name."""
    now = _now()
    inserted = 0
    for name, yt_id, handle, desc in SEED_CHANNELS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO channels (name, youtube_channel_id, youtube_handle, description, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (name, yt_id or "", handle or "", desc or "", now, now),
        )
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    return inserted


def list_channels(conn, active_only: bool = True) -> list:
    """Return all channels, optionally only active ones."""
    if active_only:
        return conn.execute(
            "SELECT id, name, youtube_channel_id, youtube_handle, description, "
            "       last_scanned_at, created_at "
            "FROM channels WHERE is_active=1 ORDER BY name"
        ).fetchall()
    return conn.execute(
        "SELECT id, name, youtube_channel_id, youtube_handle, description, "
        "       is_active, last_scanned_at, created_at "
        "FROM channels ORDER BY name"
    ).fetchall()


if __name__ == "__main__":
    conn = init_db()
    n = seed_analysts(conn)
    c = seed_channels(conn)
    print(f"Schema initialized at {DB_PATH}. {n} new analysts seeded, {c} new channels seeded.")
    total = conn.execute("SELECT COUNT(*) FROM analysts").fetchone()[0]
    ch = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    print(f"Total analysts in DB: {total}")
    print(f"Total channels in DB: {ch}")
    conn.close()
