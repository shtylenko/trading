#!/usr/bin/env python3
"""
Import a topic into its own per-topic library database.

Usage:
  python3 import_topic.py --name my_trader --display "My Trader" \
      --desc "Description" --dir /path/to/transcripts
  python3 import_topic.py --name my_trader --update --dir /path/to/new_files
"""

import sqlite3, os, sys, re, argparse

LIB = os.path.dirname(os.path.abspath(__file__))

YAML_RE = re.compile(r'^---\s*$', re.MULTILINE)
VIDEO_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
CHUNK_SIZE = 5000

def safe_int(val, default=0):
    if not val: return default
    val = str(val).strip().replace(',', '').replace('"', '').replace("'", '')
    try: return int(float(val))
    except (ValueError, TypeError): return default

def parse_transcript(content):
    """Parse a transcript file. Returns dict + body text.
    Supports YAML frontmatter (--- delimited) and legacy header format."""
    meta = {'title': '', 'views': 0, 'url': '', 'video_id': '',
            'duration': 0, 'published': ''}
    body = content

    # Try YAML frontmatter
    m = YAML_RE.match(content)
    if m:
        end = m.end()
        end_m = YAML_RE.search(content, end)
        if end_m:
            raw = content[end:end_m.start()].strip()
            body = content[end_m.end():].strip()
            for line in raw.split('\n'):
                line = line.strip()
                if ':' not in line: continue
                k, v = line.split(':', 1)
                k, v = k.strip().lower(), v.strip().strip('"').strip("'")
                if k == 'title':       meta['title'] = v
                elif k == 'views':     meta['views'] = safe_int(v)
                elif k == 'url':       meta['url'] = v
                elif k == 'video_id':  meta['video_id'] = v
                elif k == 'duration':  meta['duration'] = safe_int(v)
                elif k == 'published': meta['published'] = v
            return meta, body

    # Legacy header format
    for line in content.split('\n')[:10]:
        if line.startswith('Title:'):
            meta['title'] = line.replace('Title:', '', 1).strip()
        elif line.startswith('Views:'):
            meta['views'] = safe_int(line.replace('Views:', '', 1).strip())
        elif line.startswith('URL:'):
            meta['url'] = line.replace('URL:', '', 1).strip()

    sep_pos = content.find('=' * 70)
    if sep_pos != -1:
        body_start = content.find('\n', sep_pos) + 1
        body = content[body_start:].strip() if body_start > 0 else content
    else:
        body = content

    return meta, body


def extract_video_id(meta, fname, url):
    """Extract and validate 11-char YouTube video_id."""
    if VIDEO_ID_RE.match(meta.get('video_id', '')):
        return meta['video_id']
    m = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', url or '')
    if m: return m.group(1)
    m = re.match(r'transcript_([a-zA-Z0-9_-]{11})', os.path.basename(fname))
    if m: return m.group(1)
    return None


def chunk_text(text, max_chars=CHUNK_SIZE):
    """Split text into chunks at sentence/paragraph boundaries.

    Tries hard to respect natural breaks (paragraphs, sentences, clauses).
    Includes a guard to avoid tiny non-final chunks when substantial
    text remains (better than pure fixed-byte splits in most spoken cases).
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        if len(text) - start <= max_chars:
            chunks.append(text[start:])
            break
        end = start + max_chars
        # Walk back to nearest sentence end or paragraph break
        best = -1
        for sep in ['\n\n', '. ', '.\n', '! ', '? ', ', ']:
            pos = text.rfind(sep, start, end)
            if pos > start + max_chars // 2:
                best = max(best, pos)
        if best == -1:
            best = text.rfind(' ', start, end)
        if best == -1 or best <= start:
            best = end
        else:
            best += 1  # include the separator

        # Guard: avoid creating tiny non-final chunks when lots of text remains.
        # This prevents pathological cases (early break + long remainder)
        # that are sometimes worse than a simple fixed split.
        chunk_len = best - start
        remaining = len(text) - best
        if chunk_len < 800 and remaining > 1500:
            best = min(end + 1500, len(text))
            if best - start > max_chars * 1.5:
                best = min(end + 500, len(text))

        chunks.append(text[start:best])
        start = best
    return chunks


def import_topic(name, display_name, description, transcripts_dir, update=False):
    topic_dir = os.path.join(LIB, name)
    db_path = os.path.join(topic_dir, "library.db")
    os.makedirs(topic_dir, exist_ok=True)

    exists = os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA busy_timeout=5000")
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY,
            video_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            view_count INTEGER DEFAULT 0,
            url TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            published TEXT DEFAULT '',
            file_path TEXT,
            char_count INTEGER,
            indexed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(video_id, chunk_index)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            title, transcript_text,
            tokenize='porter unicode61',   -- good recall for "trade/trading/trader" etc. in spoken content
            prefix='2 3'
        );
    """)

    c.execute("INSERT OR REPLACE INTO meta VALUES ('topic_name', ?)", (name,))
    if not exists:
        c.execute("INSERT OR REPLACE INTO meta VALUES ('display_name', ?)", (display_name,))
        c.execute("INSERT OR REPLACE INTO meta VALUES ('description', ?)", (description,))

    files = sorted(os.listdir(transcripts_dir))
    txt_files = [f for f in files if f.endswith('.txt')]
    print(f"Found {len(txt_files)} .txt files in {transcripts_dir}")

    inserted = processed = skipped = 0
    for i, fname in enumerate(txt_files):
        fpath = os.path.join(transcripts_dir, fname)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        meta, body = parse_transcript(content)
        url = meta['url'] or ''
        video_id = extract_video_id(meta, fname, url)
        if not video_id:
            print(f"  SKIP {fname}: could not extract valid video_id")
            skipped += 1
            continue

        if not meta['title']:
            meta['title'] = (os.path.splitext(fname)[0]
                             .replace('transcript_', '', 1)
                             .split('_', 1)[-1].replace('_', ' ').title()[:200])
        if not url:
            url = f"https://youtube.com/watch?v={video_id}"

        chunks = chunk_text(body)

        # Per-video transaction for atomicity: either all chunks (and deletes) succeed
        # for this video, or none do. This is the key reliability improvement over
        # relying solely on every-50 commits.
        c.execute("BEGIN IMMEDIATE")
        video_inserted = 0
        try:
            if update:
                # Delete ALL rows for this video_id (base + all chunks) atomically
                c.execute("DELETE FROM transcripts_fts WHERE rowid IN "
                          "(SELECT id FROM transcripts WHERE video_id=?)", (video_id,))
                c.execute("DELETE FROM transcripts WHERE video_id=?", (video_id,))

            for ci, chunk in enumerate(chunks):
                title = meta['title'][:200]
                if len(chunks) > 1 and ci > 0:
                    title = f"{meta['title'][:190]} [part {ci+1}]"

                before = conn.total_changes
                c.execute("""
                    INSERT OR IGNORE INTO transcripts
                    (video_id, chunk_index, title, view_count, url, duration, published, file_path, char_count)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (video_id, ci, title, meta['views'], url,
                      meta['duration'], meta['published'], fpath, len(chunk)))
                if conn.total_changes > before:
                    rowid = c.lastrowid
                    c.execute("INSERT INTO transcripts_fts(rowid, title, transcript_text) VALUES (?,?,?)",
                              (rowid, title, chunk))
                    if ci == 0:
                        video_inserted = 1

            c.execute("COMMIT")
            inserted += video_inserted
            processed += 1
        except Exception as e:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass  # best effort
            print(f"  Error {fname}: {e}")
            skipped += 1

        if (i + 1) % 50 == 0:
            conn.commit()

    conn.commit()

    unique_videos = c.execute("SELECT COUNT(DISTINCT video_id) FROM transcripts").fetchone()[0]
    total_rows = c.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    c.execute("INSERT OR REPLACE INTO meta VALUES ('video_count', ?)", (str(unique_videos),))
    c.execute("INSERT OR REPLACE INTO meta VALUES ('chunk_count', ?)", (str(total_rows),))
    conn.commit()
    conn.close()

    action = "Updated" if update else "Imported"
    print(f"\n{action}: {inserted} new videos, {processed - inserted} unchanged, {skipped} skipped")
    print(f"  Unique videos in DB: {unique_videos}")
    print(f"  Total rows (including chunks): {total_rows}")
    print(f"  DB: {db_path} ({os.path.getsize(db_path)/1024/1024:.1f}MB)")
    return inserted


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Import a topic into its own library DB')
    p.add_argument('--name', required=True)
    p.add_argument('--display', default='')
    p.add_argument('--desc', default='')
    p.add_argument('--dir', required=True)
    p.add_argument('--update', action='store_true', help='Replace existing records for re-processed files')
    args = p.parse_args()

    if not os.path.isdir(args.dir):
        print(f"Error: not a directory: {args.dir}")
        sys.exit(1)

    import_topic(args.name, args.display, args.desc, args.dir, update=args.update)
