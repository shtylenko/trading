# Trading Video Library

Searchable transcript archive. One SQLite FTS5 database per topic.

## Structure

```
library/
  query.py                # search tool
  import_topic.py         # create/update topic DBs from transcript .txt files
  <topic_name>/
    library.db            # self-contained: meta + transcripts + FTS5
    transcripts/          # source .txt files (one per video)
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

Transcript files must contain a header and body separated by `=======`:

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
    --dir /path/to/transcripts

# Re-process existing files (replaces old data)
python3 import_topic.py --name short_name --dir /path --update
```

Re-import without `--update` is idempotent — existing video_ids are skipped.

## Per-Topic Directory Layout

```
<topic_name>/
  library.db              # auto-generated
  transcripts/            # source .txt files
  <analysis>.md           # optional human-written reports
```

## Agent Notes

- `query.py "question" --topic <name>` is the primary research tool. Use it before asking the user for context already transcribed.
- After importing a new topic, run `query.py -l` to confirm discovery.
- Long transcripts are automatically split at sentence boundaries for better FTS results (with guards against pathological tiny chunks).
- `--update` fully replaces all chunks for a video atomically (per-video transactions) — safe to run on changed transcripts.
- Corrupt or unreadable topics are skipped with a warning for broad searches, but explicit `--topic foo` fails loudly with a clear error.
- Cross-topic result order is stabilized (by view count) rather than depending on thread completion order.
