# YT Explorer

Local, evidence-first YouTube intake for trading research. It discovers videos,
records timestamped source claims, audits new channels, deduplicates hypotheses,
and exposes a human-governed research queue. It never creates a strategy, runs a
broker action, or promotes a result.

Run from the monorepo root (`/Users/shtylenko/Projects`):

```bash
python3 -m trading.ytexplorer.cli init

# Discovery bot: adds videos and their channels as candidate sources.
python3 -m trading.ytexplorer.cli discover \
  --query "anchored VWAP trading entry stop" --max-results 20 --transcripts --extract --json

# Or process all previously downloaded, unprocessed transcripts. Hermes receives
# a local extraction skill and must return validated structured JSON.
python3 -m trading.ytexplorer.cli extract --limit 20 --model <hermes-model> --json

# One-time macOS setup: installs and enables an autonomous 06:05 daily run.
python3 -m trading.ytexplorer.cli install-schedule

# Audit a discovered channel. --auto-promote applies only an evidence-based
# source status; it does not certify the channel's claims.
python3 -m trading.ytexplorer.cli audit-channel CHANNEL_ID \
  --transcripts --auto-promote --json

# Add a cited claim and a human-review candidate.
python3 -m trading.ytexplorer.cli add-claim --video-id VIDEO_ID --claim-type setup \
  --summary "Rule summary" --evidence-quote "Short source excerpt" \
  --evidence-start 320 --evidence-end 342 --horizon swing
python3 -m trading.ytexplorer.cli add-candidate --claim-id CLAIM_ID \
  --title "Hypothesis title" --summary "Falsifiable hypothesis" --priority 50

# Explore the shared local ledger in a browser at http://127.0.0.1:8791.
python3 -m trading.ytexplorer.cli serve
```

For an offline UI walkthrough, run `python3 -m trading.ytexplorer.cli seed-demo`
before starting the server. Local state is stored in ignored `ytexplorer/data/`.
Set `YTEXPLORER_DB` to use another SQLite path, `YTEXPLORER_CACHE_DIR` for
transcript caching, and `YTMCP_DIR` if the sibling `ytmcp` project lives elsewhere.

The autonomous query registry is [`config/queries.yaml`](config/queries.yaml), visible
under **Search plan** in the UI. The scheduled pipeline records each search, transcript,
Hermes extraction, and channel-audit failure independently. It needs `RAPIDAPI_KEY` in the
untracked root `.env`; without it the scheduled job logs a clear configuration error instead
of partially running.

The automatic extractor invokes Hermes with the version-controlled
[`video-hypothesis-extractor` skill](skills/video_hypothesis_extractor/SKILL.md) embedded in
its one-shot prompt. It verifies every LLM evidence quote occurs in the downloaded transcript
before storing a claim. Set `YTEXPLORER_HERMES_SKILL` to additionally preload a registered
Hermes skill by name. The current `ytmcp` cleaned-transcript interface does not preserve
subtitle timings, so it intentionally records exact quotes + transcript hashes rather than
invented timestamps.

To keep autonomous runs bounded, Hermes receives one relevance-selected transcript excerpt
(at most 9,000 characters) per video and has a 90-second hard process-group timeout. A timeout
is recorded as an extraction error and the pipeline continues to the next video.
