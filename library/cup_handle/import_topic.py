#!/usr/bin/env python3
"""Import the cup_handle research into the library database."""
import sqlite3
import json
from pathlib import Path

LIBRARY_DIR = Path(__file__).parent
DOCUMENTS = [
    ("00_MASTER_LIBRARY.md", "Cup-and-Handle Master Library — comprehensive research archive covering Bulkowski stats, academic papers, VCP comparison, entry/exit mechanics, volume analysis, ML approaches, position sizing, and comparison to current implementation"),
    ("03_youtube_research.md", "YouTube research — 184 video transcripts from 25 search queries, 2.6M chars. Covers VCP studies, O'Neil rules, false breakout analysis, Python algorithms, and practitioner trade walkthroughs"),
]

def main():
    db = LIBRARY_DIR / "library.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    # Meta table (required by query.py)
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    meta_rows = {
        "topic_name": "cup_handle",
        "display_name": "Cup-and-Handle Pattern Research",
        "video_count": "0",
        "description": "Comprehensive research on cup-and-handle pattern detection, optimization, and backtest performance for stock swing trading",
    }
    for k, v in meta_rows.items():
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (k, v))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL DEFAULT 'cup_handle',
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            description TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, description, content, content='documents', content_rowid='id'
        )
    """)

    for filename, desc in DOCUMENTS:
        path = LIBRARY_DIR / filename
        if not path.exists():
            print(f"SKIP: {filename} not found")
            continue
        content = path.read_text(encoding="utf-8")
        conn.execute(
            "INSERT OR REPLACE INTO documents (topic, title, file_path, description, content) VALUES (?, ?, ?, ?, ?)",
            ("cup_handle", filename, str(path), desc, content),
        )
        # Sync FTS
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT OR REPLACE INTO documents_fts (rowid, title, description, content) VALUES (?, ?, ?, ?)",
            (row_id, filename, desc, content),
        )

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM documents WHERE topic='cup_handle'").fetchone()[0]
    conn.close()
    print(f"Imported {total} document(s) into cup_handle library.")

if __name__ == "__main__":
    main()
