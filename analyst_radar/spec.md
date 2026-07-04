# Analyst Radar — Spec

Track market analysts, surface their YouTube interview predictions, and
connect those predictions to specific tickers (stocks, ETFs, indices).  Daily pipeline runs,
deduplicates interviews, extracts predictions via LLM, and stores
everything in SQLite.

**Lives in the `trading` monorepo** as `trading.analyst_radar` (under
`/Users/shtylenko/Hermes/projects/trading/analyst_radar`). It depends only on
`trading.marketdata` (for ticker validation), respecting the monorepo's
`marketdata ← …` dependency direction. All Python is run from the monorepo root
(`/Users/shtylenko/Hermes/projects`) so `trading.*` imports resolve.

**Execution model — the LLM drives.** Hermes (an LLM agent with bash access)
runs the pipeline by *calling the Python CLIs*. Python is a mechanical tool the
LLM invokes; it never does content analysis (§5). The LLM reads transcripts and
returns structured JSON, then calls Python again to validate-and-store it.

---

## 1.  Data Model (SQLite)

### 1.1  `analysts` — the people we track

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| name          | TEXT    | "Tom Lee"                                  |
| firm          | TEXT    | "Fundstrat"                                |
| role          | TEXT    | "Head of Research"                         |
| bio           | TEXT    | Short free-text bio                        |
| is_active     | INTEGER | 1 = actively searched; 0 = paused          |
| created_at    | TEXT    | ISO-8601                                   |
| updated_at    | TEXT    | ISO-8601                                   |

### 1.2  `interviews` — YouTube videos discovered

| Column          | Type    | Notes                                      |
|-----------------|---------|--------------------------------------------|
| id              | INTEGER | PK                                         |
| youtube_url     | TEXT    | e.g. https://youtube.com/watch?v=xxx       |
| youtube_id      | TEXT    | Unique video ID (UNIQUE)                   |
| title           | TEXT    | Video title                                |
| channel_name    | TEXT    | e.g. "CNBC Television"                     |
| published_date  | TEXT    | ISO-8601 date (YYYY-MM-DD)                 |
| transcript_text | TEXT    | Full transcript or summary (nullable)      |
| summary         | TEXT    | LLM-generated 2-3 sentence summary         |
| fetched_at      | TEXT    | ISO-8601 timestamp of last fetch           |
| created_at      | TEXT    | ISO-8601                                   |

Notes:
- `youtube_id` is UNIQUE — dedup on it.
- `transcript_text` may be null when an interview is discovered but hasn't
  been transcribed yet.
- `fetched_at` = last time we refreshed transcript/summary metadata.

### 1.3  `tickers` — stocks, ETFs, indices mentioned

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| ticker        | TEXT    | e.g. "AAPL" (UNIQUE)                       |
| company_name  | TEXT    | e.g. "Apple Inc."                          |
| sector        | TEXT    | e.g. "Technology" (nullable)               |
| created_at    | TEXT    | ISO-8601                                   |

### 1.4  `predictions` — extracted forecasts

| Column          | Type    | Notes                                      |
|-----------------|---------|--------------------------------------------|
| id              | INTEGER | PK                                         |
| interview_id    | INTEGER | FK → interviews.id                         |
| analyst_id      | INTEGER | FK → analysts.id (denormalized for speed)  |
| prediction_text | TEXT    | The actual forecast / call                 |
| prediction_type | TEXT    | price_target | sector_call | macro_call | direction_call | earnings_call | other |
| direction       | TEXT    | bullish | bearish | neutral (CHECK)          |
| confidence      | TEXT    | high | medium | low (nullable, CHECK)         |
| time_horizon    | TEXT    | e.g. "3-6 months", "year-end 2026"         |
| raw_quote       | TEXT    | Verbatim quote from transcript (nullable)  |
| content_hash    | TEXT    | SHA-256 of (interview_id, normalized prediction_text) — dedup key, UNIQUE |
| prompt_version  | TEXT    | Version tag of the extraction prompt used  |
| model           | TEXT    | LLM model id that produced this row         |
| created_at      | TEXT    | ISO-8601                                   |

Notes:
- `direction` CHECK constraint: `IN ('bullish','bearish','neutral')`.
- `confidence` CHECK constraint: `IN ('high','medium','low')` (nullable).
- `prediction_type` CHECK constraint: `IN ('price_target','sector_call','macro_call','direction_call','earnings_call','other')`.
- `content_hash` is UNIQUE — re-running Phase 2 on the same interview must not
  duplicate predictions (see §5.1, dedup is mechanical).
- `prompt_version` + `model` make extraction reproducible and let us re-score
  predictions when the prompt changes.

### 1.5  `prediction_tickers` — junction table

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| prediction_id | INTEGER | FK → predictions.id                        |
| ticker_id     | INTEGER | FK → tickers.id                            |

UNIQUE(prediction_id, ticker_id)

### 1.5b  `unresolved_mentions` — ticker proposals that didn't validate

When the LLM proposes a ticker symbol that does not validate against the known
symbol list (§5.2), it lands here instead of being dropped — a review queue.

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| prediction_id | INTEGER | FK → predictions.id                        |
| raw_symbol    | TEXT    | The symbol/string the LLM returned         |
| context       | TEXT    | Surrounding phrase (nullable)              |
| resolved_ticker_id | INTEGER | FK → tickers.id once resolved (nullable) |
| created_at    | TEXT    | ISO-8601                                   |

### 1.5c  `prediction_outcomes` — closing the loop (scoring)

The point of tracking analysts is scoring whether their calls came true. One
row per prediction once it can be evaluated.

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| prediction_id | INTEGER | FK → predictions.id (UNIQUE)               |
| outcome       | TEXT    | correct | incorrect | partial | unresolvable (CHECK) |
| actual_value  | TEXT    | What actually happened (e.g. realized price) |
| resolved_at   | TEXT    | ISO-8601 when scored                       |
| notes         | TEXT    | Free-text rationale (nullable)             |
| created_at    | TEXT    | ISO-8601                                   |

Notes:
- `outcome` CHECK: `IN ('correct','incorrect','partial','unresolvable')`.
- Scoring is a separate pass (not part of the daily fetch pipeline); time-horizon
  drives when a prediction becomes evaluable. The evaluation itself is LLM/analyst
  work, never Python heuristics (§5).

### 1.6  `pipeline_runs` — audit trail

| Column        | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | PK                                         |
| started_at    | TEXT    | ISO-8601                                   |
| finished_at   | TEXT    | ISO-8601 (nullable if crashed)             |
| phase         | TEXT    | phase-1 (search/fetch) | phase-2 (extract) | scoring |
| interviews_found | INTEGER |                                          |
| interviews_new   | INTEGER |                                          |
| predictions_found| INTEGER |                                          |
| status        | TEXT    | running | completed | failed               |
| error_message | TEXT    | nullable                                   |

Notes:
- One row per phase run, so a failure can be attributed to the phase that broke.

### 1.7  Indexes

The §3 queries require these to stay fast as data grows:

```sql
CREATE INDEX idx_predictions_analyst    ON predictions(analyst_id);
CREATE INDEX idx_predictions_interview  ON predictions(interview_id);
CREATE INDEX idx_predictions_created_at ON predictions(created_at);
CREATE INDEX idx_pt_ticker              ON prediction_tickers(ticker_id);
CREATE INDEX idx_pt_prediction          ON prediction_tickers(prediction_id);
CREATE INDEX idx_interviews_published   ON interviews(published_date);
```

---

## 2.  Daily Pipeline Flow

```
┌──────────────────────────────────────────┐
│  1. SEARCH                               │
│  For each active analyst, search YouTube │
│  for recent interviews (past ~2 days).   │
│  Use: "{analyst_name} stock market        │
│  interview {today}"                       │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  2. DEDUP                                │
│  Check youtube_id against interviews     │
│  table. Skip already known videos.       │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  3. FETCH METADATA + TRANSCRIPT          │
│  For new videos: extract title, channel, │
│  published_date. Attempt transcript via  │
│  youtube-content skill or yt-dlp.        │
│  Store in interviews table.              │
│  NO TRANSCRIPT → store with NULL, mark   │
│  for extraction-skip (see §5.3).         │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  4. EXTRACT PREDICTIONS (LLM)            │
│  Pass transcript to LLM with prompt:     │
│  - Identify specific predictions/forecasts│
│  - Classify type, direction, confidence │
│  - Extract ticker symbols mentioned      │
│  - Return structured JSON list           │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  5. RESOLVE TICKERS                       │
│  For each ticker the LLM proposed:        │
│  validate against known-symbol list       │
│  (§5.2). Valid → upsert tickers + junction.│
│  Invalid → unresolved_mentions queue.     │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  6. LOG RUN                              │
│  Record pipeline_runs row with counts    │
│  and status.                              │
└──────────────────────────────────────────┘
```

---

## 3.  Key Queries (for the UI / reporting)

### 3.1  Latest predictions by ticker

```sql
SELECT t.ticker, t.company_name,
       p.prediction_text, p.direction, p.prediction_type,
       a.name as analyst_name, a.firm,
       i.title as interview_title, i.youtube_url,
       p.created_at
FROM prediction_tickers pt
JOIN predictions p  ON pt.prediction_id = p.id
JOIN tickers t      ON pt.ticker_id = t.id
JOIN analysts a     ON p.analyst_id = a.id
JOIN interviews i   ON p.interview_id = i.id
WHERE t.ticker = ?
ORDER BY p.created_at DESC
LIMIT 50;
```

### 3.2  Latest predictions by analyst

```sql
SELECT a.name, a.firm,
       p.prediction_text, p.direction, p.prediction_type,
       p.time_horizon,
       GROUP_CONCAT(t.ticker, ', ') as tickers,
       i.youtube_url, i.published_date
FROM predictions p
JOIN analysts a      ON p.analyst_id = a.id
JOIN interviews i    ON p.interview_id = i.id
LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
LEFT JOIN tickers t  ON pt.ticker_id = t.id
WHERE a.id = ?
GROUP BY p.id
ORDER BY i.published_date DESC
LIMIT 50;
```

### 3.3  Heatmap: analyst × ticker direction

```sql
SELECT a.name, t.ticker, p.direction, COUNT(*) as cnt
FROM predictions p
JOIN prediction_tickers pt ON pt.prediction_id = p.id
JOIN tickers t ON pt.ticker_id = t.id
JOIN analysts a ON p.analyst_id = a.id
WHERE p.created_at >= date('now', '-30 days')
GROUP BY a.name, t.ticker, p.direction
ORDER BY a.name, cnt DESC;
```

---

## 4.  Project Structure

Lives inside the `trading` monorepo (run all commands from the monorepo root
`/Users/shtylenko/Hermes/projects`):

Flat package, matching the `trading.marketdata` convention (the package dir IS
the project dir):

```
trading/analyst_radar/
├── spec.md              # this file
├── .gitignore
├── requirements.txt     # Python deps (minimal)
├── __init__.py
├── db.py                # SQLite schema init, migrations, seed (25 analysts only)
├── pipeline.py          # daily pipeline orchestrator (mechanical CLI the LLM calls)
├── search.py            # YouTube search + transcript fetch via ytmcp/ytapi (§5.4)
├── extract.py           # validate LLM JSON + ticker validation via marketdata (§5.2)
├── score.py             # prediction_outcomes scoring pass (separate from daily fetch)
├── data/
│   └── analyst_radar.db  # SQLite database (gitignored)
└── skills/              # Hermes skill for running the pipeline
    └── SKILL.md
```

Invoked as a module from the monorepo root, e.g.
`python3 -m trading.analyst_radar.pipeline --phase-1`.

Notes:
- Seed = the 25 analysts of §6 only. **No symbol seed** — `tickers` accumulates
  via marketdata validation (§5.2).
- Dependencies: `trading.marketdata` (ticker validation) + ytmcp `ytapi`
  (YouTube). Both are existing code, not vendored here.

---

## 5.  Python / LLM Boundary (HARD RULE)

```
 ┌─────────────────────────────────────────┐
 │  PYTHON (data plumbing ONLY)            │
 │  - Search YouTube for video URLs        │
 │  - Fetch transcript text (yt-dlp)       │
 │  - Call LLM with transcript + prompt    │
 │  - Receive structured JSON back         │
 │  - Validate JSON structure (pydantic)   │
 │  - Sanitize strings (strip, uppercase)  │
 │  - INSERT/UPDATE into SQLite            │
 │  - Log pipeline_runs                    │
 ├─────────────────────────────────────────┤
 │  LLM (ALL content analysis)             │
 │  - Read transcript, identify predictions│
 │  - Classify: type, direction, confidence│
 │  - Extract ticker symbols from context  │
 │  - Pull verbatim quotes                 │
 │  - Estimate time horizon                │
 │  - Disambiguate "AI" vs ticker vs word  │
 │  - Ignore noise, banter, non-predictions│
 │  - Return structured JSON only          │
 └─────────────────────────────────────────┘
```

**Python MUST NOT:**
- Do keyword matching or regex to find predictions
- Decide what is/isn't a ticker based on string heuristics
- Classify sentiment, direction, or confidence
- Parse natural language in any form
- Filter or reject predictions based on content rules

**Python MUST:**
- Validate that LLM JSON matches the pydantic schema (structural, not semantic)
- Sanitize: `.strip()`, `.upper()` on tickers (cosmetic only)
- Dedup by `youtube_id` (mechanical, not content-based)
- Store whatever the LLM returned that passes structural validation

### 5.1  Mechanical conventions

- **Date/times**: ISO-8601 strings in SQLite (not Python datetime objects).
- **YouTube dedup**: `youtube_id` is UNIQUE; `INSERT OR IGNORE`.
- **Idempotent runs**: pipeline can run multiple times per day — only new content lands.
- **Prediction dedup**: re-running Phase 2 on the same interview must not duplicate
  rows. `predictions.content_hash` = SHA-256 of `(interview_id, prediction_text.strip().lower())`
  is UNIQUE; `INSERT OR IGNORE`. (Computing a hash is mechanical, not content-based.)
- **Transcript fallback**: if yt-dlp fails, store interview with `transcript_text = NULL`.

### 5.2  Ticker validation (the boundary, made precise)

There is **no seeded symbol file**. The `tickers` table starts empty and
*accumulates* as interviews are processed. The LLM *proposes* ticker symbols;
Python *validates* each one mechanically by asking `trading.marketdata` whether
tradeable price data exists for that symbol:

```python
from trading.marketdata import fetch_bars
# valid iff marketdata can return bars for the symbol
ok = _has_market_data(fetch_bars(symbol, "1day", start=..., end=...))
```

This is a mechanical existence check (does a real instrument with this symbol
trade?), not a semantic "is this a ticker" judgement — so it respects the §5
boundary.

- Symbol resolves in marketdata → upsert into `tickers`, create junction row.
- Symbol does not resolve → row into `unresolved_mentions` (never silently
  dropped; reviewable / retryable later).
- Validation results are cached (the `tickers` table itself is the accumulated
  cache; a symbol already in `tickers` skips re-validation).
- `company_name` / `sector` are nullable and best-effort — populated when
  marketdata/metadata provides them, otherwise left NULL (never LLM-guessed).
- Python still MUST NOT decide *whether a string was meant as a ticker* — that
  disambiguation ("AI" the concept vs. the symbol) is the LLM's job upstream;
  Python only checks whether the proposed symbol trades.

### 5.3  No-transcript path

A large fraction of videos have no usable captions (members-only, no auto-caption,
rate-limited). These are the common case, not an edge case:

- ytapi search already filters to `features="subtitles"`, but availability still
  fails at fetch time — `ytapi.get_transcript(video_id)` returns
  `{"error": "No transcript available"}` (or a request error).
- On error: interview is still stored (metadata only, `transcript_text = NULL`).
- Phase 2 **skips** interviews with `transcript_text IS NULL` — no extraction is
  attempted, no predictions are fabricated from a title alone.
- A later run that successfully back-fills the transcript makes the interview
  eligible for extraction (selected by `transcript_text IS NOT NULL AND
  no predictions yet`). ytapi caches transcripts on disk, so a back-fill is cheap.

### 5.4  YouTube access (ytmcp / ytapi)

All YouTube I/O goes through the existing **ytmcp** wrapper at
`/Users/shtylenko/Projects/ytmcp` (`ytapi.YouTubeAPI`). **No yt-dlp.** Requires
`RAPIDAPI_KEY` in the environment.

- `search_videos(keyword, max_results, upload_date="week")` → list of
  `{title, video_id, channel, published_date_YYYYMMDD, url, ...}`.
- `get_transcript(video_id)` → `{raw_text, ...}` or `{error}`; disk-cached.
- ytmcp lives under a different root (`/Users/shtylenko/Projects`), not on the
  `trading` import path → `search.py` adds it to `sys.path` (or imports via an
  absolute path shim). Document the exact mechanism in `search.py`.

Search scope (cost + noise control):
- Cap results per analyst per run (default `max_results=10`, `upload_date="week"`).
- Relevance filtering — deciding a video actually *is* the named analyst giving a
  market interview — is LLM/skill work, never a Python keyword match.
- Optional channel allowlist (CNBC, Bloomberg, etc.) to cut re-uploads and clips,
  applied as a mechanical set filter on `channel_name`.

### 5.5  LLM extraction contract

Phase 2 calls the LLM with the transcript and a versioned prompt. The LLM returns
**only** a JSON array; Python validates each element against this pydantic schema
(structural validation only) before insert:

```json
[
  {
    "prediction_text": "S&P 500 reaches 7000 by year-end",
    "prediction_type": "price_target",
    "direction": "bullish",
    "confidence": "high",
    "time_horizon": "year-end 2026",
    "raw_quote": "I think we get to 7000 by December...",
    "tickers": ["SPX"]
  }
]
```

- `prediction_type`, `direction`, `confidence` MUST be one of the enum values
  (the prompt binds the LLM to these; Python's CHECK constraints are the backstop).
- `tickers` is a list of proposed symbols, fed into §5.2 validation.
- The prompt carries a `prompt_version` tag stored on every row it produces, along
  with the `model` id (§1.4).

---

## 6.  Analyst Seed List (initial 25)

| #  | Name               | Firm                    | Role                              |
|----|--------------------|-------------------------|-----------------------------------|
| 1  | Tom Lee            | Fundstrat               | Head of Research                  |
| 2  | Dan Ives           | Wedbush Securities      | Tech Analyst                      |
| 3  | Mike Wilson        | Morgan Stanley          | Chief U.S. Equity Strategist & CIO|
| 4  | David Kostin       | Goldman Sachs           | Chief U.S. Equity Strategist      |
| 5  | Lori Calvasina     | RBC Capital Markets     | Head of U.S. Equity Strategy      |
| 6  | Savita Subramanian | Bank of America         | Head of U.S. Equity & Quant Strat |
| 7  | Brian Belski       | Humilis / BMO           | Chief Investment Strategist       |
| 8  | Liz Ann Sonders    | Charles Schwab          | Chief Investment Strategist       |
| 9  | Ed Yardeni         | Yardeni Research        | President                         |
| 10 | Barry Bannister    | Stifel                  | Chief Equity Strategist           |
| 11 | Katie Stockton     | Fairlead Strategies     | Founder & Managing Partner        |
| 12 | Cameron Dawson     | NewEdge Wealth          | Chief Investment Officer          |
| 13 | Stephanie Link     | Hightower Advisors      | Chief Investment Strategist       |
| 14 | Josh Brown         | Ritholtz Wealth Mgmt    | CEO, CNBC Contributor             |
| 15 | Chris Vermeulen    | The Technical Traders   | Chief Market Strategist           |
| 16 | Torsten Slok       | Apollo Global Mgmt      | Chief Economist                   |
| 17 | David Rosenberg    | Rosenberg Research      | Founder & President               |
| 18 | Jeremy Siegel      | Wharton / WisdomTree    | Senior Economist                  |
| 19 | Jason Furman       | Harvard Kennedy School  | Professor, Former CEA Chair       |
| 20 | Mark Zandi         | Moody's Analytics       | Chief Economist                   |
| 21 | Michael Darda      | Roth Capital Partners   | Chief Economist & Macro Strategist|
| 22 | Jim Paulsen        | Paulsen Perspectives    | Author & Strategist               |
| 23 | Peter Boockvar     | Bleakley Financial      | CIO, The Boock Report             |
| 24 | David Zervos       | Jefferies               | Chief Market Strategist           |
| 25 | Lance Roberts      | RIA Advisors            | Chief Portfolio Strategist        |

---

## 7.  Skills

### 7.1  `fetch-updates` — main daily skill

Orchestrates the full daily pipeline:

**Phase 1** — the LLM launches Python via terminal (zero LLM content work),
from the monorepo root:
```
$ python3 -m trading.analyst_radar.pipeline --phase-1
```
Searches YouTube via ytmcp/ytapi for each active analyst (`upload_date="week"`),
deduplicates by youtube_id, fetches transcripts, stores new interviews in DB.

**Phase 2** — LLM reads each new transcript and extracts predictions:
- Identifies every forecast in the transcript
- Classifies: type, direction, confidence, time horizon
- Extracts ticker symbols from context (disambiguates "AI" etc.)
- Returns structured JSON → pydantic validates → Python INSERTs into DB

### 7.2  Additional skills (planned)

| Skill | Purpose |
|-------|---------|
| `view-by-ticker` | Show all predictions for a given ticker, grouped by analyst |
| `view-by-analyst` | Show an analyst's prediction history across all appearances |
| `view-recent` | Show last 7 days of predictions across all tickers |
| `heatmap` | Analyst × ticker sentiment matrix |
| `score-predictions` | Evaluate matured predictions → `prediction_outcomes` (§1.5c) |
| `scorecard` | Per-analyst hit-rate / track record from resolved outcomes |

---

## 8.  Web UI

All views live as pages in a single lightweight web app (Flask or FastAPI +
Jinja2 templates).  Styling: dark terminal aesthetic, no Bootstrap bloat.

### 8.1  `/` — Dashboard

Summary cards at the top:
- Total analysts tracked (25)
- Interviews collected this week
- Predictions extracted this week
- Unique tickers mentioned

Below: "Latest Predictions" table — most recent 20 predictions across all
analysts and tickers, with links to drill down.

### 8.2  `/analysts` — Analyst Directory

Searchable table of all 25 analysts.  Columns: name, firm, role, status
(active/paused), last interview found, prediction count.

Click an analyst → `/analyst/{id}` detail page.

### 8.3  `/analyst/{id}` — Analyst Detail

- Analyst info header (name, firm, bio)
- "Recent Interviews" — list of YouTube videos found, with dates and links
- "Predictions" table — all predictions from this analyst, with ticker badges

### 8.4  `/tickers` — Ticker Directory

Searchable table of all tickers mentioned in predictions.  Columns: ticker,
company name, sector, prediction count, latest prediction date.

Click a ticker → `/ticker/{id}` detail page.

### 8.5  `/ticker/{id}` — Ticker Detail

- Ticker header (symbol, company name, sector)
- "Predictions" table — all predictions mentioning this ticker, grouped by
  analyst, with direction badges (🟢 bullish / 🔴 bearish / ⚪ neutral)
- "Mentions Over Time" — simple sparkline or bar chart of prediction counts
  per week

### 8.6  `/interviews` — Interview Log

Paginated list of all fetched interviews.  Columns: date, analyst, title
(linked to YouTube), channel, has transcript (✓/✗), prediction count.

Click an interview → `/interview/{id}` detail page.

### 8.7  `/interview/{id}` — Interview Detail

- YouTube embed at top
- Interview metadata (date, channel, duration)
- "Predictions Extracted" — list of all predictions from this interview
- Full transcript collapsible section below

### 8.8  `/predictions` — All Predictions

Filterable table.  Filters: direction (bullish/bearish/neutral), type
(price_target/sector_call/etc.), analyst, ticker, date range.

Default sort: newest first.  Each row links to the source interview.

### 8.9  `/pipeline` — Pipeline Runs

Table of recent pipeline runs: start time, duration, interviews found/new,
predictions found, status (completed/failed).  Audit trail.

---

## 9.  Next Steps (after spec approval)

1. Create `analyst_radar/db.py` with schema init + seed (analysts + known-symbol list + indexes + CHECK constraints)
2. Create `analyst_radar/pipeline.py` skeleton (per-phase `pipeline_runs` logging)
3. Create `analyst_radar/search.py` for YouTube search + transcript fetch (result cap, no-transcript path)
4. Create `analyst_radar/extract.py` for LLM prediction extraction (versioned prompt, content_hash dedup, ticker validation → unresolved_mentions)
5. Create `analyst_radar/score.py` for the outcome-scoring pass (`prediction_outcomes`)
6. Create Hermes skill for `hermes run analyst-radar-daily`
7. Wire up as cron job for daily execution
