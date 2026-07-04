#!/usr/bin/env python3
"""
Import a topic into its own per-topic library database.

Usage:
  python3 import_topic.py --name my_trader --display "My Trader" \
      --desc "Description" --dir /path/to/source_files
  python3 import_topic.py --name my_trader --update --dir /path/to/new_files
"""

import sqlite3, os, sys, re, argparse

LIB = os.path.dirname(os.path.abspath(__file__))

YAML_RE = re.compile(r'^---\s*$', re.MULTILINE)
YT_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
YT_URL_RE = re.compile(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})')
YT_FNAME_RE = re.compile(r'transcript_([a-zA-Z0-9_-]{11})')
CHUNK_SIZE = 5000


def safe_int(val, default=0):
    if not val:
        return default
    val = str(val).strip().replace(',', '').replace('"', '').replace("'", '')
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def parse_file(content, fname):
    """Parse a source file. Returns (meta dict, body text).

    Supports:
    - YAML frontmatter (--- delimited) with any metadata keys
    - Legacy YouTube header format (Title:/Views:/URL:/=======)
    - Plain .md with # title
    - Plain .txt (filename-derived title)
    """
    meta = {'title': '', 'views': 0, 'url': '', 'source_id': '',
            'duration': 0, 'published': ''}
    body = content

    # --- YAML frontmatter ---
    m = YAML_RE.match(content)
    if m:
        end = m.end()
        end_m = YAML_RE.search(content, end)
        if end_m:
            raw = content[end:end_m.start()].strip()
            body = content[end_m.end():].strip()
            for line in raw.split('\n'):
                line = line.strip()
                if ':' not in line:
                    continue
                k, v = line.split(':', 1)
                k, v = k.strip().lower(), v.strip().strip('"').strip("'")
                if k == 'title':
                    meta['title'] = v
                elif k in ('views', 'view_count'):
                    meta['views'] = safe_int(v)
                elif k == 'url':
                    meta['url'] = v
                elif k in ('source_id', 'video_id'):
                    meta['source_id'] = v
                elif k == 'duration':
                    meta['duration'] = safe_int(v)
                elif k == 'published':
                    meta['published'] = v
            return meta, body
        # no closing --- : treat as plain text, not YAML

    # --- Legacy YouTube header ---
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


def extract_source_id(meta, fname, url):
    """Derive a unique source_id for this document.

    Priority:
    1. Explicit source_id / video_id from metadata
    2. YouTube ID from URL
    3. YouTube ID from transcript_XXXXXXXXXXX filename pattern
    4. Filename stem (for .md, plain .txt, etc.)
    """
    if meta.get('source_id'):
        return meta['source_id']

    m = YT_URL_RE.search(url or '')
    if m:
        return m.group(1)
    m = YT_FNAME_RE.match(os.path.basename(fname))
    if m:
        return m.group(1)

    # Fallback: filename stem
    stem = os.path.splitext(fname)[0]
    for prefix in ('transcript_',):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    # Take first 64 chars max as source_id
    return stem[:64]


def infer_title(fname, content):
    """Derive title from file content or name."""
    # .md files: first # heading
    if fname.endswith('.md'):
        m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if m:
            return m.group(1).strip()[:200]
    # Fallback: filename → title
    stem = os.path.splitext(fname)[0]
    for prefix in ('transcript_',):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem.replace('_', ' ').replace('-', ' ').title()[:200]


def chunk_text(text, max_chars=CHUNK_SIZE):
    """Split text at sentence/paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        if len(text) - start <= max_chars:
            chunks.append(text[start:])
            break
        end = start + max_chars
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
            best += 1
        chunk_len = best - start
        remaining = len(text) - best
        if chunk_len < 800 and remaining > 1500:
            best = min(end + 1500, len(text))
            if best - start > max_chars * 1.5:
                best = min(end + 500, len(text))
        chunks.append(text[start:best])
        start = best
    return chunks


def import_topic(name, display_name, description, source_dir, update=False):
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
            source_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            view_count INTEGER DEFAULT 0,
            url TEXT DEFAULT '',
            duration INTEGER DEFAULT 0,
            published TEXT DEFAULT '',
            file_path TEXT,
            char_count INTEGER,
            indexed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source_id, chunk_index)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            title, transcript_text,
            tokenize='porter unicode61',
            prefix='2 3'
        );
    """)

    c.execute("INSERT OR REPLACE INTO meta VALUES ('topic_name', ?)", (name,))
    if not exists:
        c.execute("INSERT OR REPLACE INTO meta VALUES ('display_name', ?)", (display_name,))
        c.execute("INSERT OR REPLACE INTO meta VALUES ('description', ?)", (description,))

    files = sorted(os.listdir(source_dir))
    src_files = [f for f in files if f.endswith(('.txt', '.md'))]
    print(f"Found {len(src_files)} .txt/.md files in {source_dir}")

    inserted = processed = skipped = 0
    for i, fname in enumerate(src_files):
        fpath = os.path.join(source_dir, fname)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            print(f"  SKIP {fname}: empty")
            skipped += 1
            continue

        meta, body = parse_file(content, fname)
        source_id = extract_source_id(meta, fname, meta['url'])
        if not source_id:
            print(f"  SKIP {fname}: could not derive source_id")
            skipped += 1
            continue

        if not meta['title']:
            meta['title'] = infer_title(fname, content)

        chunks = chunk_text(body)

        doc_inserted = 0
        try:
            if update:
                c.execute("DELETE FROM transcripts_fts WHERE rowid IN "
                          "(SELECT id FROM transcripts WHERE source_id=?)", (source_id,))
                c.execute("DELETE FROM transcripts WHERE source_id=?", (source_id,))

            for ci, chunk in enumerate(chunks):
                title = meta['title'][:200]
                if len(chunks) > 1 and ci > 0:
                    title = f"{meta['title'][:190]} [part {ci+1}]"

                before = conn.total_changes
                c.execute("""
                    INSERT OR IGNORE INTO transcripts
                    (source_id, chunk_index, title, view_count, url, duration, published, file_path, char_count)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (source_id, ci, title, meta['views'], meta['url'],
                      meta['duration'], meta['published'], fpath, len(chunk)))
                if conn.total_changes > before:
                    rowid = c.lastrowid
                    c.execute("INSERT INTO transcripts_fts(rowid, title, transcript_text) VALUES (?,?,?)",
                              (rowid, title, chunk))
                    if ci == 0:
                        doc_inserted = 1

            if doc_inserted or update:
                conn.commit()
            inserted += doc_inserted
            processed += 1
        except Exception as e:
            print(f"  Error {fname}: {e}")
            skipped += 1

        if (i + 1) % 50 == 0:
            conn.commit()

    conn.commit()

    unique_docs = c.execute("SELECT COUNT(DISTINCT source_id) FROM transcripts").fetchone()[0]
    total_rows = c.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    c.execute("INSERT OR REPLACE INTO meta VALUES ('doc_count', ?)", (str(unique_docs),))
    c.execute("INSERT OR REPLACE INTO meta VALUES ('chunk_count', ?)", (str(total_rows),))
    # Keep legacy key for backward compat
    c.execute("INSERT OR REPLACE INTO meta VALUES ('video_count', ?)", (str(unique_docs),))
    conn.commit()
    conn.close()

    action = "Updated" if update else "Imported"
    print(f"\n{action}: {inserted} new documents, {processed - inserted} unchanged, {skipped} skipped")
    print(f"  Unique documents in DB: {unique_docs}")
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
