#!/usr/bin/env python3
"""
Search the trading video library — per-topic databases.

Usage:
  python3 query.py "first candle new high"             # search all topics
  python3 query.py "30 cent max loss" --topic ross_cameron  # one topic
  python3 query.py -l                                   # list topics
  python3 query.py -i                                   # stats
"""

import sqlite3, os, sys, re, argparse

LIB = os.path.dirname(os.path.abspath(__file__))

def discover_topics():
    """Scan for */library.db directories."""
    topics = []
    for entry in sorted(os.listdir(LIB)):
        db = os.path.join(LIB, entry, "library.db")
        if os.path.isfile(db):
            try:
                conn = sqlite3.connect(db)
                c = conn.cursor()
                name = c.execute("SELECT value FROM meta WHERE key='topic_name'").fetchone()[0]
                display = c.execute("SELECT value FROM meta WHERE key='display_name'").fetchone()[0]
                count = c.execute("SELECT value FROM meta WHERE key='video_count'").fetchone()[0]
                conn.close()
                topics.append((name, display, int(count), db))
            except Exception:
                topics.append((entry, entry, 0, db))
    return topics

def search_db(db_path, query, limit=10):
    """FTS5 search on a single per-topic DB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only=1")
    c = conn.cursor()

    terms = [t for t in query.split() if len(t) > 1]
    fts_query = ' AND '.join(terms) if terms else query

    try:
        c.execute("""
            SELECT t.id, t.title, t.url, t.view_count, t.video_id,
                   snippet(transcripts_fts, 1, '\x01', '\x02', '...', 40)
            FROM transcripts_fts
            JOIN transcripts t ON t.id = transcripts_fts.rowid
            WHERE transcripts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit))
        results = c.fetchall()
    except sqlite3.OperationalError:
        results = []

    conn.close()
    return results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search the trading video library')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('-t', '--topic', help='Limit to one topic (slug)')
    parser.add_argument('-l', '--list-topics', action='store_true', help='List topics')
    parser.add_argument('-i', '--info', action='store_true', help='Library stats')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()

    topics = discover_topics()

    if args.list_topics:
        print("Available topics:")
        for name, display, count, _ in topics:
            print(f"  {name:20s}  {display:30s}  {count} transcripts")
        sys.exit(0)

    if args.info:
        total_vids = sum(t[2] for t in topics)
        total_bytes = sum(os.path.getsize(t[3]) for t in topics)
        print(f"Topics:     {len(topics)}")
        print(f"Transcripts: {total_vids}")
        print(f"DB size:    {total_bytes/1024/1024:.1f}MB")
        for name, display, count, db in topics:
            print(f"  {display}: {count} transcripts ({os.path.getsize(db)/1024/1024:.1f}MB)")
        sys.exit(0)

    if not args.query:
        print("Usage:")
        print("  python3 query.py <search query>           # all topics")
        print("  python3 query.py <q> --topic <name>       # one topic")
        print("  python3 query.py -l                       # list topics")
        print("  python3 query.py -i                       # stats")
        sys.exit(0)

    # Filter topics
    if args.topic:
        target_topics = [(n, d, c, db) for n, d, c, db in topics if n == args.topic]
        if not target_topics:
            print(f"Topic '{args.topic}' not found. Use -l to list.")
            sys.exit(1)
    else:
        target_topics = topics

    # Search each topic
    all_results = []
    for name, display, count, db in target_topics:
        results = search_db(db, args.query, args.limit)
        for r in results:
            all_results.append((display, name, r))

    if not all_results:
        print(f"No results for: {args.query}")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  Query: {args.query}")
    print(f"  Results: {len(all_results)}")
    if args.topic:
        print(f"  Topic: {args.topic}")
    else:
        print(f"  Topics searched: {len(target_topics)}")
    print(f"{'='*60}\n")

    for i, (display, topic_name, row) in enumerate(all_results):
        rid, title, url, views, vid, snippet = row
        snippet = snippet.replace('\x01', '\033[1;33m').replace('\x02', '\033[0m')

        print(f"  [{i+1}] {title}")
        print(f"      Topic: {display}")
        print(f"      URL:   {url}")
        if views:
            print(f"      Views: {views:,}")
        print(f"      {snippet}")
        print()
