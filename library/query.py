#!/usr/bin/env python3
"""
Search the trading video library — per-topic databases.

Usage:
  python3 query.py "first candle new high"                  # search all topics
  python3 query.py "stop loss" --topic ross_cameron          # one topic
  python3 query.py "big loss" -t ross_cameron -t other       # specific topics
  python3 query.py -l                                        # list topics
  python3 query.py -i                                        # stats
  python3 query.py "icebreaker rule" --json                  # JSON output
  python3 query.py "VWAP" --min-views 50000 --limit 5        # filtered
  python3 query.py --full abc123 --topic ross_cameron        # full transcript text
  python3 query.py "VWAP" --show 1                          # show full transcript for result #1
  python3 query.py "VWAP" --cat 1                            # raw text for piping
"""

import sqlite3, os, sys, re, argparse, json
from concurrent.futures import ThreadPoolExecutor, as_completed

LIB = os.path.dirname(os.path.abspath(__file__))


def discover_topics(strict=False):
    """Scan for */library.db directories.

    Returns (good_topics, errors) where errors is list of (slug, error_msg).
    In non-strict mode (default), corrupt/locked/missing-meta DBs are skipped
    with a warning so that a bad topic doesn't kill a multi-topic search.
    When strict=True (used for explicit --topic requests), errors cause failure.
    """
    topics = []
    errors = []
    for entry in sorted(os.listdir(LIB)):
        db_path = os.path.join(LIB, entry, "library.db")
        if not os.path.isfile(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA busy_timeout=3000")
            conn.execute("PRAGMA query_only=1")
            c = conn.cursor()
            name = c.execute("SELECT value FROM meta WHERE key='topic_name'").fetchone()
            display = c.execute("SELECT value FROM meta WHERE key='display_name'").fetchone()
            count = c.execute("SELECT value FROM meta WHERE key='video_count'").fetchone()
            conn.close()

            if not name or not display or count is None:
                raise RuntimeError("missing required meta rows (topic_name/display_name/video_count)")

            topics.append((name[0], display[0], int(count[0]), db_path))
        except Exception as e:
            msg = f"{entry}: {e}"
            errors.append((entry, str(e)))
            if strict:
                # Will be handled by caller for explicit topics
                pass
            else:
                print(f"  WARN: skipping '{msg}'", file=sys.stderr)
    return topics, errors


def search_db(db_path, query, min_views=0, limit=40):
    """FTS5 search on a single per-topic DB. Returns results grouped by source_id."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA query_only=1")
    c = conn.cursor()

    try:
        c.execute("""
            SELECT t.id, t.source_id, t.chunk_index, t.title, t.url, t.view_count, t.file_path,
                   snippet(transcripts_fts, 1, '\x01', '\x02', '...', 40)
            FROM transcripts_fts
            JOIN transcripts t ON t.id = transcripts_fts.rowid
            WHERE transcripts_fts MATCH ?
              AND t.view_count >= ?
            ORDER BY rank
            LIMIT ?
        """, (query, min_views, limit))

        # Group by source_id, keep the best chunk per document
        groups = {}
        for row in c.fetchall():
            sid = row[1]
            if sid not in groups:
                groups[sid] = row
        results = list(groups.values())
    except sqlite3.OperationalError:
        results = []

    conn.close()
    return results


def format_snippet(snippet):
    return snippet.replace('\x01', '\033[1;33m').replace('\x02', '\033[0m')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search the trading video library')
    parser.add_argument('query', nargs='?', help='Search query (raw FTS5 syntax)')
    parser.add_argument('-t', '--topic', action='append', help='Topic slug(s) to search (repeatable)')
    parser.add_argument('-l', '--list-topics', action='store_true', help='List topics')
    parser.add_argument('-i', '--info', action='store_true', help='Library stats')
    parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    parser.add_argument('--min-views', type=int, default=0, help='Minimum view count filter')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--no-color', action='store_true', help='Disable color highlighting')
    parser.add_argument('--full', metavar='SOURCE_ID', help='Print full document text (needs --topic)')
    parser.add_argument('--show', metavar='SOURCE_ID', help='Alias for --full')
    args = parser.parse_args()

    # --show is an alias for --full
    if args.show and not args.full:
        args.full = args.show

    # Use strict mode when the user explicitly asked for particular topics.
    # This makes missing/corrupt topics fail loudly instead of being silently dropped.
    strict = bool(args.topic)
    topics, discovery_errors = discover_topics(strict=strict)

    # Surface discovery problems
    for slug, err in discovery_errors:
        if strict and any(t == slug for t in (args.topic or [])):
            print(f"ERROR: failed to load requested topic '{slug}': {err}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"  WARN: skipping '{slug}' ({err})", file=sys.stderr)

    if args.list_topics:
        for name, display, count, _ in topics:
            print(f"{name:20s}  {display:30s}  {count} documents")
        sys.exit(0)

    if args.info:
        total_vids = sum(t[2] for t in topics)
        total_bytes = sum(os.path.getsize(t[3]) for t in topics)
        print(f"Topics:          {len(topics)}")
        print(f"Total documents: {total_vids}")
        print(f"DB size:         {total_bytes/1024/1024:.1f}MB")
        for name, display, count, db_path in topics:
            extra = ""
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA busy_timeout=3000")
                conn.execute("PRAGMA query_only=1")
                chunks = conn.execute("SELECT value FROM meta WHERE key='chunk_count'").fetchone()
                if chunks:
                    extra = f" ({chunks[0]} rows)"
                conn.close()
            except Exception:
                pass
            print(f"  {display}: {count} docs{extra} ({os.path.getsize(db_path)/1024/1024:.1f}MB)")
        sys.exit(0)

    if not args.query and not args.full:
        print("Usage:")
        print("  python3 query.py <query>               # search all topics")
        print("  python3 query.py <q> -t <topic>        # one topic")
        print("  python3 query.py <q> -t A -t B         # specific topics")
        print("  python3 query.py -l                    # list topics")
        print("  python3 query.py -i                    # stats")
        print("  python3 query.py <q> --json            # JSON output")
        print("  python3 query.py <q> --min-views 50000")
        print("  python3 query.py --full <id> -t <topic>  # full transcript")
        sys.exit(0)

    # --full / --show mode: print the source file for a source_id
    if args.full:
        if not args.topic:
            # Search all topics for this source_id
            for name, display, count, db_path in topics:
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA query_only=1")
                c = conn.cursor()
                exists = c.execute("SELECT 1 FROM transcripts WHERE source_id=? LIMIT 1", (args.full,)).fetchone()
                conn.close()
                if exists:
                    args.topic = [name]
                    break
            if not args.topic:
                print(f"ERROR: --show requires --topic, or the source_id must exist in a known topic", file=sys.stderr)
                sys.exit(1)
        target = [(n, d, c, db) for n, d, c, db in topics if n in args.topic]
        if not target:
            print(f"Topic '{args.topic}' not found.", file=sys.stderr)
            sys.exit(1)

        db_path = target[0][3]
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA query_only=1")
        c = conn.cursor()

        fpath = c.execute(
            "SELECT file_path FROM transcripts WHERE source_id=? AND chunk_index=0 LIMIT 1",
            (args.full,)
        ).fetchone()
        conn.close()

        if not fpath or not os.path.isfile(fpath[0]):
            print(f"Source file not found for source_id: {args.full}", file=sys.stderr)
            sys.exit(1)

        with open(fpath[0], 'r', encoding='utf-8', errors='ignore') as f:
            print(f.read().rstrip())
        sys.exit(0)

    if args.topic:
        target = [(n, d, c, db) for n, d, c, db in topics if n in args.topic]
        # Also check if user asked for topics that were filtered due to errors
        requested = set(args.topic)
        found = {t[0] for t in target}
        missing = requested - found
        if missing:
            print(f"ERROR: requested topic(s) not available: {sorted(missing)}", file=sys.stderr)
            sys.exit(1)
        if not target:
            print(f"No matching topics for: {args.topic}. Use -l to list.", file=sys.stderr)
            sys.exit(1)
    else:
        target = topics

    if not target:
        print("No topics found.", file=sys.stderr)
        sys.exit(1)

    per_topic_limit = args.limit * 3
    all_results = []

    explicit_topics = set(args.topic) if args.topic else set()
    with ThreadPoolExecutor(max_workers=min(8, len(target))) as pool:
        futures = {
            pool.submit(search_db, db, args.query, args.min_views, per_topic_limit):
            (name, display) for name, display, _, db in target
        }
        for future in as_completed(futures):
            name, display = futures[future]
            try:
                results = future.result()
                all_results.extend((display, name, r) for r in results)
            except Exception as e:
                if name in explicit_topics:
                    print(f"ERROR: search failed for requested topic '{display}': {e}", file=sys.stderr)
                else:
                    print(f"  WARN: search failed for '{display}': {e}", file=sys.stderr)

    if not all_results:
        print(f"No results for: {args.query}")
        sys.exit(0)

    # Stabilize cross-topic ordering.
    # Within each topic results are already ordered by FTS rank of the best chunk.
    # Across topics (as_completed order) we use view_count as a cheap, stable,
    # comparable secondary key so that result order is no longer dependent on
    # thread scheduling. Higher-view videos are preferred on ties.
    all_results.sort(key=lambda item: -(item[2][5] or 0))

    # Global limit (applied after stabilization)
    all_results = all_results[:args.limit]

    if args.json:
        output = []
        for display, topic_name, row in all_results:
            _, sid, ci, title, url, views, fpath, snippet = row
            output.append({
                'title': title,
                'topic': display,
                'topic_slug': topic_name,
                'url': url,
                'views': views,
                'source_id': sid,
                'chunk': ci,
                'file_path': fpath,
                'snippet': snippet.replace('\x01', '').replace('\x02', ''),
            })
        print(json.dumps(output, indent=2))
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  Query: {args.query}")
    print(f"  Results: {len(all_results)}")
    if args.topic:
        print(f"  Topics: {', '.join(args.topic)}")
    else:
        print(f"  Topics searched: {len(target)}")
    if args.min_views:
        print(f"  Min views: {args.min_views:,}")
    print(f"{'='*60}\n")

    for i, (display, topic_name, row) in enumerate(all_results):
        _, sid, ci, title, url, views, fpath, snippet = row
        snippet = snippet if args.no_color else format_snippet(snippet)

        print(f"  [{i+1}] {title}")
        print(f"      Topic: {display}")
        print(f"      File:  {fpath}")
        print(f"      {snippet}")
        print()
