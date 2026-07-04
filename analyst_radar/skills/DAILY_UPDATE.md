---
name: analyst-radar-daily
description: Run daily Analyst Radar update — search YouTube for analyst interviews, fetch transcripts, extract market predictions, validate tickers, and store everything in SQLite.
---

# Analyst Radar — Daily Update

Trigger: User says "run analyst radar" or "update analyst radar" or any variant.
**RULES: Work through every step in order. Do not skip steps. Do not ask questions unless blocked.**

All commands run from: `/Users/shtylenko/Hermes/projects`
Database: `/Users/shtylenko/Hermes/projects/trading/analyst_radar/data/analyst_radar.db`
RAPIDAPI_KEY is already in your environment via `~/.hermes/.env`.

---

## 1. Phase 1 — Discover interviews (pure Python, no LLM content work)

```bash
python3 -m trading.analyst_radar.pipeline --phase-1
```

This searches YouTube for every active analyst (upload_date="week"), deduplicates
by youtube_id, fetches transcripts via ytapi, and stores new interviews. Note what
it prints — new videos found, which ones got transcripts, which didn't.

### 1b. Phase-channels — Scan tracked YouTube channels

After the analyst-name search, also scan the `channels` table for new videos:

```python
from trading.analyst_radar.db import get_db, list_channels
from trading.analyst_radar.search import scan_channel_feed

conn = get_db()
for ch in list_channels(conn, active_only=True):
    yt_id = ch["youtube_channel_id"]
    name = ch["name"]
    if not yt_id:
        print(f"  SKIP {name} — no youtube_channel_id resolved yet")
        continue
    n = scan_channel_feed(conn, name, yt_id)
    print(f"  {name}: {n} new interviews")
```

This lists recent videos from each channel (e.g. Bloomberg Television uploads)
and cross-references them against tracked analysts. Any video whose title
mentions a tracked analyst name AND is not already in the DB gets fetched and
stored. This catches clips that the keyword search misses (e.g. a Bloomberg
clip called "The Close" that has a Dan Ives segment).

**NEW — Auto-discover analyst candidates from financial media channels:**
If a video comes from a known financial media channel (CNBC, Bloomberg,
Fox Business, Yahoo Finance, Schwab, Kitco, Charles Schwab, The Compound)
and features an **unrecognised guest name**, the channel scan will:
1. Extract the guest name from the title (e.g. "Meghan Shue" from
   "Wilmington Trust's Meghan Shue says equities will outperform")
2. Queue them as a candidate via `store_candidate()`
3. Store the interview so it's ready when approved

Scans **40 recent videos** per channel (up from 20).

---

## 2. Get the extraction worklist

```python
import sqlite3
conn = sqlite3.connect('trading/analyst_radar/data/analyst_radar.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT i.id, i.published_date, i.title, i.channel_name, i.youtube_url
      FROM interviews i
     WHERE i.transcript_text IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM predictions p WHERE p.interview_id = i.id)
     ORDER BY i.published_date DESC
""").fetchall()
for r in rows:
    print(f"[{r['id']}] {r['published_date']}  {r['channel_name']}  {r['title'][:70]}")
```

If the list is empty → nothing to extract, skip to step 5.

Use channel_name to pre-filter before reading transcripts:
- **Process**: CNBC Television, Bloomberg Television, Fox Business, Yahoo Finance, Kitco NEWS, Charles Schwab, Fundstrat, Wedbush, analysts' own firm channels
- **Skip immediately** (no transcript read needed): CTV News, NBC News, ABC News, local news, gaming streams, audiobooks, non-English channels, sports channels

---

## 3. Extract predictions (YOU read transcripts, YOU extract)

For each interview in the worklist:

### 3a. Read the transcript from DB

Use the `conn` already opened in step 2 (do NOT open a second connection):

```python
row = conn.execute(
    "SELECT id, title, channel_name, youtube_url, transcript_text FROM interviews WHERE id = ?",
    (interview_id,)
).fetchone()
transcript = row['transcript_text']
title      = row['title']
```

Then match the analyst: look at the title/channel and find the most likely analyst
from the `analysts` table:

```python
analysts = conn.execute("SELECT id, name, firm FROM analysts WHERE is_active=1").fetchall()
```

Use your judgment (LLM reasoning) to identify which analyst from the list is the
subject of this interview.

**If the analyst IS in the tracked list** → use their `id`, proceed to extraction.

**If the analyst is NOT in the tracked list** → DO NOT skip. Instead, assess:
- Is this a credible market analyst with a formal background (real firm, identifiable
  role, genuine market commentary)? Examples: Gary Cohn, Lyn Alden, Philippe Laffont.
- If YES → queue as a candidate for human review:
  ```python
  from trading.analyst_radar.db import store_candidate
  store_candidate(conn, name="Gary Cohn", firm="Former NEC Director / Goldman Sachs",
                  role="Economist / Former Goldman President",
                  source_youtube_url=row['youtube_url'],
                  source_interview_title=row['title'])
  ```
  Then skip extraction for this interview.
- If NO (gaming stream, audiobook, entertainment, non-English, clearly not finance) →
  skip silently, no candidate stored.

The human reviews and approves/rejects candidates at `/candidates` in the web UI.

### 3b. Verify the analyst is actually speaking (not commentary)

Before extracting anything, read enough of the transcript to answer:
**Is this analyst speaking in first person, or is someone else discussing/summarizing their views?**

Signs the analyst IS speaking:
- First-person language: "I think", "I expect", "we see", "in my view", "I'm bullish on..."
- Interview-style: questions directed at them, their direct answers
- The channel is their own (Fundstrat, Wedbush, their firm's channel) or a known financial media outlet (CNBC Television, Bloomberg Television, Yahoo Finance, etc.)

Signs this is commentary (SKIP, do not extract):
- Third-person throughout: "Tom Lee says...", "According to Dan Ives...", "Here's what Lee predicted..."
- Someone else is summarizing, reacting to, or analyzing the analyst's views
- Channel name is clearly a fan/aggregator account ("Nvidia Investor", "Stocks Galore", "Wolf of Dubai", "Millionaires Investment Secrets", "Blue Cloud Trading", etc.)
- The analyst's name only appears in the title/thumbnail, not as a speaker in the transcript

**If it's commentary → skip extraction entirely.** Log it in the report as "skipped (commentary)".

### 3c. Extract predictions (primary source only)

Read the full transcript text. Identify every **specific, concrete market
prediction or forecast** the analyst makes. Ignore general commentary, banter,
and statements of fact. A prediction must be falsifiable (it implies an outcome
that can later be judged correct or incorrect).

For each prediction, return a JSON object:

```json
{
  "prediction_text": "concise statement",
  "prediction_type": "price_target | sector_call | macro_call | direction_call | earnings_call | other",
  "direction": "bullish | bearish | neutral",
  "confidence": "high | medium | low",
  "time_horizon": "e.g. 'year-end 2026', 'next 3-6 months', 'Q3 2026'",
  "raw_quote": "verbatim quote from the transcript",
  "tickers": ["AAPL", "SPX"]
}
```

**Ticker disambiguation rules:**
- "AI" as a concept → do NOT include as a ticker
- "AI" the stock (C3.ai) → include as "AI"
- "the S&P" / "S&P 500" → "SPX"
- "the Nasdaq" → "QQQ" or "NDX"
- "bonds" / "treasuries" → "TLT" (if directional call)
- Ambiguous single letters or generic words → omit

Return an array (can be empty `[]` if the interview has no extractable predictions).

### 3d. Validate and store via Python

```python
from trading.analyst_radar.extract import validate_predictions, store_predictions

items = validate_predictions(llm_json_array)
n = store_predictions(conn, interview_id=interview_id, analyst_id=analyst_id,
                      items=items, model="your-current-model-id", prompt_version="v1")
print(f"  Stored {n} predictions for interview {interview_id}")
conn.commit()
```

Storage is idempotent — re-running won't duplicate (content_hash dedup).

Tickers proposed by you get validated against `trading.marketdata` automatically
inside `store_predictions`. Symbols that don't trade go to `unresolved_mentions`
(not an error — just a review queue).

---

## 4. Repeat step 3 for all pending interviews

Work through the full worklist from step 2. One interview at a time.

---

## 5. Report

Summarize in the conversation with predictions listed **one by one**:

```
## Analyst Radar — {date}

**Phase 1 — Discovery:**
- Interviews found: N (new: M, already known: K)
- With transcript: X | No transcript: Y
- Channel scans: Z new from {N} tracked channels

**Phase 2 — Extraction:**
- Primary-source interviews processed: N
- New predictions stored: M  (total: {total})
- New analyst candidates queued: {list names}

---

### New predictions

#### {Analyst Name} — {short title}
ID {id} | {direction} | {confidence}
> "{raw_quote}"
Tickers: {tickers}
Horizon: {time_horizon}

#### {next one}
...

---

### Skipped

**Commentary channels:** {count} ({channel list})
**Non-finance / non-English:** {count}
**General news broadcasts:** {count}
```

---

## 6. Post-Run Learnings

After each run, note observations and patch this skill or related files if needed.
Save what you learn so future runs improve automatically.

### Checks after each run

- **New analysts added?** If a newly-added analyst's personal channel produces only
  non-finance content (Chinese drama, K-pop, gaming, sports, etc.), flag them for
  deactivation in the report.
- **Commentary channels discovered?** If a new commentary/aggregator channel keeps
  appearing (e.g. "Nvidia Investor", "Stocks Galore"), add it to the skip list in
  your mental model so you auto-skip it next run.
- **Channel scan gaps?** If a tracked channel has zero hit rate after several runs,
  consider removing it. If a major financial channel isn't tracked, add it.
- **Pipeline:**
  - Did `--phase-1` time out? May need background mode.
  - Did `scan_channel_feed` find duplicates? Check youtube_id dedup.
  - Did ticker validation fail for legit tickers? Fix Alpaca/marketdata provider.
- **Predictions stored this run:** if 3+ new predictions were stored, run the TRADE_IDEAS
  skill (`/Users/shtylenko/Hermes/projects/trading/analyst_radar/skills/TRADE_IDEAS.md`)
  immediately after to update bull/bear scores for affected tickers.

### Patch this skill

If you discovered a shortcut, pitfall, or recurring pattern during this run,
**edit this file directly** to harden it for next time. Specifically update:

- The channel skip list in step 2 (add newly discovered commentary/news channels)
- The channel process list in step 2 (add newly discovered legitimate financial channels)
- The `## Known channel patterns` section below

## Known channel patterns

### Always skip (commentary / noise)
- CTV News — Canadian local news, never analyst interviews
- NBC News — general news broadcasts
- ABC News — general news broadcasts  
- "Nvidia Investor", "Stocks Galore", "Wolf of Dubai", "Blue Cloud Trading" — aggregator farms
- Korean/Japanese/Telugu/Chinese channels — non-English content

### Always trust as primary source
- CNBC Television — primary source, major interviews
- Bloomberg Television — primary source, major interviews
- Bloomberg Originals — long-form business/finance interviews
- Fundstrat — Tom Lee's own channel
- Charles Schwab — Liz Ann Sonders appearances
- Schwab Network — market analysis from Schwab strategists
- Kitco NEWS — gold/silver analyst interviews (Vermeulen, Rosenberg etc.)
- David Lin — analyst interviews on gold, macro, equities
- Real Vision — professional macro market interviews
- Wealthion — macro analyst interview channel
- Investor's Business Daily — financial news, stock analysis
- Steve Eisman — tracked analyst's own channel
- Odds on Open — hedge fund manager interviews
- Verified Investing — daily technical market analysis
- Investor Center — curated clips from top investors
- The Motley Fool — stock picks and market commentary
- Zacks Investment Research — analyst stock calls
- MarketWatch — financial news with market analysis
- SchiffGold — gold and macro analysis
- Yahoo Finance — market interviews and news
- Fox Business — business news network

---

## Notes

- **Python/LLM boundary is hard** (spec.md §5): Python does zero content analysis.
  You identify predictions, classify them, and propose tickers. Python validates
  structure and checks whether symbols trade. Never ask Python to find predictions.
- If `validate_predictions` raises a `ValidationError`, fix the offending field
  (wrong enum value) and retry — don't skip the prediction.
- If an interview's analyst cannot be matched to tracked names, queue as candidate.
