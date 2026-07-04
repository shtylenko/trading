# Trading Video Library

Searchable transcript archive. One SQLite FTS5 database per topic.

## Structure

```
library/
  query.py                # search tool
  import_topic.py         # create/update topic DBs from source files
  <topic_name>/
    library.db            # self-contained: meta + transcripts + FTS5
    content/              # source .txt and .md files
```

## Query

```bash
cd /Users/shtylenko/Projects/trading/library

# Search all topics
python3 query.py "stop loss 30 cents"

# Search one topic
python3 query.py "VWAP micro pullback" --topic ross_cameron

# Filtered
python3 query.py "short squeeze" --min-views 100000 --limit 5

# JSON output (pipeable)
python3 query.py "icebreaker" --json | jq .

# Overview
python3 query.py -i          # stats
python3 query.py -l          # list topics
```

query.py auto-discovers every `*/library.db` under the library root. Results are grouped by video (best chunk per video).

## Import a New Topic

Source files (`.txt` or `.md`) must contain a header and body separated by `=======` for YouTube transcripts:

```
Title: Video Title
Views: 12345
URL: https://youtube.com/watch?v=VIDEO_ID
======================================================================
<transcript text follows>
```

Or YAML frontmatter:

```
---
title: Video Title
views: 12345
url: "https://..."
video_id: "VIDEO_ID"
---
<transcript text follows>
```

```bash
python3 import_topic.py \
    --name short_name \
    --display "Display Name" \
    --desc "One-line description" \
    --dir /path/to/content

# Re-process existing files (replaces old data)
python3 import_topic.py --name short_name --dir /path --update
```

Re-import without `--update` is idempotent — existing source_ids are skipped.

## Re-index an Existing Topic

After adding or editing files in an existing topic's `content/` folder:

```bash
# Add new files only (skips unchanged)
python3 import_topic.py --name ross_cameron --dir ross_cameron/content

# Rebuild everything from scratch (deletes old, re-indexes all)
python3 import_topic.py --name ross_cameron --dir ross_cameron/content --update
```

`--update` is safe to run repeatedly — it deletes all existing rows for each file and re-inserts fresh. The full rebuild is also the recommended way to migrate if the DB schema changes in a future update.

## Per-Topic Directory Layout

```
<topic_name>/
  library.db              # auto-generated
  content/                # source .txt and .md files
  <analysis>.md           # optional human-written reports
```

## Agent Notes

- `query.py "question" --topic <name>` is the primary research tool. Use it before asking the user for context already transcribed.
- After importing a new topic, run `query.py -l` to confirm discovery.
- Long transcripts are automatically split at sentence boundaries for better FTS results (with guards against pathological tiny chunks).
- `--update` fully replaces all chunks for a video atomically (per-video transactions) — safe to run on changed transcripts.
- Corrupt or unreadable topics are skipped with a warning for broad searches, but explicit `--topic foo` fails loudly with a clear error.
- Cross-topic result order is stabilized (by view count) rather than depending on thread completion order.
