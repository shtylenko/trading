#!/usr/bin/env python3
"""
Import a topic into its own per-topic library database.

Usage:
  python3 import_topic.py --name my_trader --display "My Trader" \\
      --desc "Description" --dir /path/to/transcripts
"""

import sqlite3, os, sys, re, argparse

LIB = os.path.dirname(os.path.abspath(__file__))

def import_topic(name, display_name, description, transcripts_dir):
    topic_dir = os.path.join(LIB, name)
    db_path = os.path.join(topic_dir, "library.db")
    os.makedirs(topic_dir, exist_ok=True)

    if os.path.exists(db_path):
        print(f"DB exists at {db_path} — appending (skipping existing video_ids)")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA synchronous=OFF")
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY,
            video_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            view_count INTEGER DEFAULT 0,
            url TEXT NOT NULL,
            file_path TEXT,
            char_count INTEGER,
            indexed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            title, transcript_text,
            tokenize='porter unicode61',
            prefix='2 3'
        );
    """)

    c.execute("INSERT OR REPLACE INTO meta VALUES ('topic_name', ?)", (name,))
    c.execute("INSERT OR REPLACE INTO meta VALUES ('display_name', ?)", (display_name,))
    c.execute("INSERT OR REPLACE INTO meta VALUES ('description', ?)", (description,))

    files = sorted(os.listdir(transcripts_dir))
    txt_files = [f for f in files if f.endswith('.txt')]
    print(f"Found {len(txt_files)} .txt files in {transcripts_dir}")

    inserted = skipped = 0
    for i, fname in enumerate(txt_files):
        fpath = os.path.join(transcripts_dir, fname)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        title = views = url = ""
        for line in content.split('\n')[:10]:
            if line.startswith('Title:'):    title = line.replace('Title:', '').strip()
            elif line.startswith('Views:'):
                try: views = int(line.replace('Views:', '').strip().replace(',', ''))
                except: views = 0
            elif line.startswith('URL:'):    url = line.replace('URL:', '').strip()

        m = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', fpath + url)
        video_id = ""
        if m:
            video_id = m.group(1)
        m2 = re.match(r'transcript_([a-zA-Z0-9_-]{11})', fname)
        if not video_id and m2:
            video_id = m2.group(1)
        if not video_id:
            video_id = fname.replace('transcript_', '').split('_')[0][:11]

        body_start = content.find('='*70)
        if body_start != -1:
            body_start = content.find('\n', body_start) + 1
            transcript_text = content[body_start:].strip()
        else:
            transcript_text = content

        if not url:
            url = f"https://youtube.com/watch?v={video_id}"

        try:
            c.execute("INSERT OR IGNORE INTO transcripts (video_id, title, view_count, url, file_path, char_count) VALUES (?,?,?,?,?,?)",
                      (video_id, title[:200], views, url, fpath, len(transcript_text)))
            rowid = c.lastrowid
            if rowid:
                c.execute("INSERT INTO transcripts_fts(rowid, title, transcript_text) VALUES (?,?,?)",
                          (rowid, title[:200], transcript_text))
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error {fname}: {e}")
            skipped += 1

        if (i + 1) % 50 == 0:
            conn.commit()

    c.execute("INSERT OR REPLACE INTO meta VALUES ('video_count', ?)", (str(inserted),))
    conn.commit()

    c.execute("SELECT COUNT(*) FROM transcripts")
    total = c.fetchone()[0]
    conn.close()

    print(f"\nDone: {inserted} new, {skipped} skipped (total in DB: {total})")
    print(f"DB: {db_path} ({os.path.getsize(db_path)/1024/1024:.1f}MB)")
    return inserted


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Import a topic into its own library DB')
    p.add_argument('--name', required=True)
    p.add_argument('--display', required=True)
    p.add_argument('--desc', default='')
    p.add_argument('--dir', required=True)
    args = p.parse_args()

    if not os.path.isdir(args.dir):
        print(f"Error: not a directory: {args.dir}")
        sys.exit(1)

    import_topic(args.name, args.display, args.desc, args.dir)
