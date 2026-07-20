# YT Explorer commands and workflow

Run every command from the monorepo root:

```bash
cd /Users/shtylenko/Projects
```

The daily scheduler is autonomous. These commands are for inspecting it,
running an immediate pass, or accelerating a bounded part of the pipeline.

## The lifecycle

```text
YouTube search
  → Inbox (video metadata)
  → rank strongest rule-language videos
  → download selected transcripts
  → Hermes extracts exact, cited claims
  → Claims / Research Candidates
  → experiment brief and strategy testing
```

Videos are not strategies. A video must produce an exact transcript citation
and a sufficiently explicit rule before it can become a Research Candidate.

## 1. Daily automatic discovery

The configured daily plan lives in [config/queries.yaml](config/queries.yaml).
It searches the current long-only trading topics for videos from the last week.
For each query, it stores all returned videos in **Inbox**, ranks them using
their title/description, then spends the configured Hermes budget on the best
few.

The installed macOS scheduler runs this automatically. To run the same process
immediately:

```bash
python3 -m trading.ytexplorer.cli --json run-scheduled --cadence due
```

Useful variants:

```bash
# Show what would run, without provider, transcript, or Hermes calls.
python3 -m trading.ytexplorer.cli --json run-scheduled --cadence due --dry-run

# Run only plan entries labelled daily.
python3 -m trading.ytexplorer.cli --json run-scheduled --cadence daily

# Bot-friendly: clean JSON and no interactive progress bar.
python3 -m trading.ytexplorer.cli --json --no-progress run-scheduled --cadence due
```

`--json` keeps the result machine-readable on stdout. When attached to a
terminal, the progress bar is written to stderr and is enabled by default.

## 2. One-off video search

Use `discover` to add the results of one query to Inbox. It does not run
Hermes unless `--extract` is explicitly supplied.

```bash
# Search recent videos and store metadata only.
python3 -m trading.ytexplorer.cli discover \
  --query "stock trading" \
  --upload-date week \
  --max-results 50

# Search the provider's most recent matching results without a date filter.
python3 -m trading.ytexplorer.cli discover \
  --query "VWAP trading" \
  --sort-by date \
  --max-results 200
```

Supported explicit recency filters are `hour`, `today` (or `day`), `week`,
`month`, and `year`. With no `--upload-date`, there is no recency filter.

To fetch transcripts and invoke Hermes for every returned video (normally only
appropriate for a small, deliberate query):

```bash
python3 -m trading.ytexplorer.cli discover \
  --query "VWAP trading" \
  --upload-date week \
  --max-results 10 \
  --transcripts \
  --extract
```

## 3. Historical all-time discovery

`backfill` runs every configured query with no upload-date filter and asks the
provider for date-sorted results. It stores metadata only by default, so a
large search does not immediately create thousands of transcript or Hermes
jobs.

```bash
# All configured queries, up to 200 date-sorted videos per query.
python3 -m trading.ytexplorer.cli --json backfill --max-results 200
```

Use `--transcripts` only for a deliberately small backfill:

```bash
python3 -m trading.ytexplorer.cli --json backfill --max-results 50 --transcripts
```

For a full backfill, omit `--transcripts` and let the historical processor
select a bounded, ranked batch instead.

## 4. Process historical Inbox videos

`process-backfill` selects pending historical videos by rule-language score,
downloads their transcripts, and runs Hermes. A completed video becomes either
cited evidence, a Research Candidate, or a source that is recorded as a
reference/rejection.

```bash
# Process ten historical videos now.
python3 -m trading.ytexplorer.cli --json process-backfill --limit 10

# Accelerate a one-off batch.
python3 -m trading.ytexplorer.cli --json process-backfill --limit 50
```

The daily scheduler also runs this worker automatically. Its daily limit is
controlled here:

```yaml
# config/queries.yaml
daily_limits:
  max_backfill_videos_per_run: 10
```

Raise that value (for example, to `50`) to make future scheduled runs drain the
historical Inbox faster. The scheduler reads the YAML at run time; no restart is
needed.

## 5. What Hermes does with a transcript

For each selected video, Hermes receives a bounded strategy-dense excerpt and
the checked-in extraction skill. Its JSON is validated before anything is
queued:

1. Every evidence quote must be an exact contiguous excerpt of the transcript.
2. Claims describe a setup, entry, exit, risk rule, filter, or market context.
3. A candidate needs an observable trigger, protection/exit information, and
   named data requirements. Missing pieces are labelled `needs-detail`; Hermes
   is never allowed to invent them.

The processor creates:

- **Claims** for cited factual/rule evidence.
- **Research Candidates** only when the evidence can support a testable idea.
- **References** when the video is useful context but not a strategy hypothesis.

## 6. Reprocess or recover failed output

If Hermes returns malformed JSON, a non-exact quote, or times out, the video is
recorded as an extraction error rather than silently accepted. Retry a bounded
set and surface incomplete evidence with:

```bash
python3 -m trading.ytexplorer.cli --json recover --limit 8 --promote-limit 20
```

`recover` retries invalid extractions and can promote existing evidence bundles
to transparent `needs-detail` cards. It does not fabricate missing rules.

## 7. Inspect results

Start the local UI if it is not already running:

```bash
python3 -m trading.ytexplorer.cli serve
```

Open `http://127.0.0.1:8791`.

- **Inbox** — every discovered video and transcript state.
- **Claims** — exact evidence extracted from transcripts.
- **Research Candidates** — ideas ready for rule completion and evaluation.
- **Channels** — discovered sources and their trading-content audit state.
- **Search plan** — current configured queries and limits.
- **Operations** — scheduled-run history, parameters, events, and errors.

CLI inspection is also available:

```bash
python3 -m trading.ytexplorer.cli --json list videos --limit 50
python3 -m trading.ytexplorer.cli --json list claims --limit 50
python3 -m trading.ytexplorer.cli --json list candidates --limit 50
python3 -m trading.ytexplorer.cli --json list channels
```

## 8. Move an idea into strategy testing

YT Explorer stops at evidence and a research brief. It does not automatically
write or execute a trading strategy. Once a Research Candidate has explicit
entry, exit/invalidation, universe, and data assumptions, link the evaluation
run to it:

```bash
python3 -m trading.ytexplorer.cli link-experiment CANDIDATE_ID \
  --system lab \
  --run-ref "your-lab-run-reference" \
  --state planned \
  --note "Testing the preregistered long-only rules."
```

Use `--system llm_trader` when the evaluation lives there instead. The testing
system, not YT Explorer, owns backtests and any later live-trading decision.
