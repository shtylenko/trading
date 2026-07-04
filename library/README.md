# Trading Video Library

Searchable transcript archive. One SQLite FTS5 database per topic.

## Structure

```
library/
  query.py                     # search tool
  import_topic.py              # create new topic from transcript .txt files
  <topic_name>/
    library.db                 # self-contained: meta + transcripts + FTS5
    transcripts/               # source .txt files
```

## Query

```bash
cd /Users/shtylenko/Projects/trading/library

# Search everything
python3 query.py "stop loss placement"

# Search one topic
python3 query.py "VWAP micro pullback" --topic ross_cameron

# Library overview
python3 query.py -i    # stats
python3 query.py -l    # list topics
```

query.py auto-discovers every `*/library.db` under the library root.

## Add a New Topic

```bash
python3 import_topic.py \
    --name short_name \
    --display "Display Name" \
    --desc "One-line description" \
    --dir /path/to/transcript_dir
```

Transcript files must have a header:
```
Title: Video Title Here
Views: 12345
URL: https://youtube.com/watch?v=VIDEO_ID
======================================================================
<transcript text follows>
```

This creates `short_name/library.db` with its own FTS5 index.

## Topic Directory Convention

```
<topic_name>/
  library.db              # auto-generated, do not edit by hand
  transcripts/            # source .txt files (one per video)
  <any analysis .md>      # optional analysis reports
```

No `_library_index/` or other generated artifacts inside topic dirs.

## Agent Notes

- `query.py "question" --topic <name>` is the primary research tool. Use it before asking the user for context they've already transcribed.
- When adding a new topic, run `query.py -l` afterward to confirm discovery.
- Re-importing the same data is idempotent — existing video_ids are skipped.
