# YT Explorer — Research-idea intake specification

**Status:** proposed — P0 is an evidence intake system, not an autonomous
strategy factory.  
**Owner:** research  
**Integrations:** `../ytmcp` for YouTube metadata/transcripts; `../llm_trader`
for bounded scanner/replay experiments; `trading.lab` remains the authoritative
research ledger and validation funnel.

## 1. Decision

**Build it, with a narrow mandate.** YouTube is a large, continuously updated
source of *hypotheses, vocabulary, and primary explanations of discretionary
setups*. It is not reliable evidence of tradable alpha. A system that turns every
video into an implementation/backtest will mostly automate data-mining,
duplicate already-failed ideas, and consume the remaining holdout budget.

The worthwhile product is therefore a durable **source-to-hypothesis queue**:

```text
YouTube discovery -> transcript evidence -> structured claim -> dedupe / prior-art
    -> human triage -> pre-registered experiment -> lab / llm_trader run
    -> immutable result linked back to the source
```

In particular, it must not write new `llm_trader` strategy families, change an
existing detector, or run confirmation data automatically. It may prepare a
mechanical candidate specification and, after approval, invoke a bounded smoke
or development run.

This separation is material: current `llm_trader` peer review identifies
look-ahead, mutable scan scope, incomplete provenance, and exhausted short-hold
ideas as higher-priority work than strategy invention. Until the integrity
milestone is complete, YT Explorer should operate in **intake-only mode**.

## 2. Goals and non-goals

### Goals

- Search a curated historical back-catalogue once, then discover new videos
  incrementally.
- Preserve the exact source claim, timestamped transcript evidence, metadata,
  query/channel that found it, and extraction-model version.
- Convert a narrative setup into a falsifiable, implementation-ready hypothesis
  *only when the source provides enough mechanical detail*.
- Detect duplicates, near-duplicates, and conflicts with existing
  `lab`/`llm_trader` results before an experiment is queued.
- Give the researcher a small, ranked review queue with explicit decisions.
- Hand approved candidates to the existing testing tools without becoming a
  competing market-data, backtest, or execution system.

### Non-goals

- No live trading signals, order submission, investment recommendations, or
  automatic capital allocation.
- No trust score based on subscribers, views, charisma, or claimed P&L.
- No automatic promotion based on a backtest or LLM summary.
- No scrape-all-of-YouTube loop. Search is bounded by a source registry, query
  budget, rate/cost budget, and dedupe threshold.
- No copying long video transcripts into the repository. Store source URLs,
  hashes, excerpts, and local cache references; comply with provider terms.

## 3. Product model

YT Explorer owns three layers. The unit of value is a **candidate hypothesis**,
not a video and not a generated strategy.

| Layer | Input / output | Responsibility |
|---|---|---|
| Acquisition | YouTube search/channel feeds -> video records + cached transcripts | Find and version source material. |
| Interpretation | transcripts -> claims -> candidate hypotheses | Extract cited, testable statements; never invent missing rules. |
| Governance | candidates -> decisions / experiment brief / result links | Prior art, dedupe, queue priority, and irreversible validation controls. |

One video can yield zero or several claims. Several sources can support one
candidate. A video that only says “watch VWAP” is a useful knowledge record but
is not an experiment candidate unless it specifies setup context, trigger,
invalidation, horizon, and instrument/universe well enough to test.

## 4. Architecture and boundaries

```text
ytmcp (external project)
  search_videos / list_channel_videos / get_transcript
              |
              v
ytexplorer acquisition + SQLite/DuckDB evidence store
              |
              v
claim extractor (schema-constrained LLM) ----> provenance / duplicate index
              |                                      |
              +-----------------------------> research review queue
                                                        |
                                        approved, pre-registered experiment brief
                                               |                         |
                                               v                         v
                                   trading.lab (validation)    llm_trader (scanner,
                                      + authoritative ledger)    sealed replay/batch)
```

`ytexplorer` must import neither `marketdata` providers nor `live`. It may call
the public `ytmcp` API through a thin adapter, and it may create files/records
consumed by `lab` or `llm_trader`; it must not bypass either package's data,
validation, or immutable-version conventions.

### Integration contracts

**`ytmcp` adapter.** Wrap `YouTubeAPI.search_videos`, `list_channel_videos`,
and `get_transcript` rather than duplicate API logic. Set `YTMCP_CACHE_DIR` to
an Explorer-owned ignored cache when desired, so raw transcript retention is
explicit. Persist only normalized metadata, transcript SHA-256, language,
fetch time, and timestamped excerpts in Explorer's ledger.

**`lab` adapter.** Produce a markdown/YAML experiment brief containing the
hypothesis, frozen rules, feasibility/data requirements, source citations,
known duplicates, development/validation/confirmation windows, expected
costs, null design, and kill criteria. `lab` is the first stop for broad,
deterministic factor/rule hypotheses and holds the authoritative experiment
and outcome lineage.

**`llm_trader` adapter.** Only after a human has chosen a scanner/replay-shaped
hypothesis. Create an *unregistered draft brief* for a strategy family or a
pre-registered variant—not code and not a sealed skill. A human creates the
family/version, uses the existing strategy registry, scanner DB, batch set and
sealed-skill workflow, then writes resulting run IDs/paths back to Explorer.
Never call `batchsim promote` from Explorer.

## 5. Acquisition design

### Source registry and search plan

Maintain version-controlled `sources.yaml` (channel IDs/handles, topic,
language, first-seen date, notes, status) and `queries.yaml` (query text,
intent, cadence, max results, upload-date filter, priority). Initial queries
should cover mechanisms rather than influencer names, for example:

- `opening range breakout trading entry stop`, `relative volume intraday setup`
- `anchored VWAP earnings pullback rules`, `post earnings drift systematic`
- `52 week high momentum position sizing`, `short term reversal stocks rules`
- `market profile auction trading setup` (captured as data-blocked when it needs
  order flow)

Run two separate jobs:

1. **Backfill:** paginate approved channels (oldest first) and execute the
   curated query set to a fixed per-run/video budget. Stop once marginal unique
   candidates fall below a predeclared rate.
2. **Incremental scan:** daily or weekly channel-newest and query searches
   (`today`, `week`, `month`). Deduplicate on YouTube video ID before fetching
   details/transcript.

Acquisition records failures and makes retries bounded. A video without a
transcript can be saved as metadata-only but cannot enter automated extraction.

### Cost and quality controls

- Cap transcript fetches per run and per channel; rate-limit API calls.
- Prefer source channels with clear rule exposition, complete examples, and
  explicit risk/invalidation discussion. This is a triage policy, not a claim
  that the creator has alpha.
- Detect reuploads using normalized title, duration, channel, and transcript
  fingerprint; retain the canonical record and source relations.
- Do not treat upload date as the date a strategy became valid. Store it only
  as publication provenance.

## 6. Claim extraction and evidence rules

Use a schema-constrained LLM extractor with deterministic post-validation. Its
job is transcription-to-structure, not judging profitability. It receives only
the necessary transcript chunks and must return verbatim evidence snippets with
start/end timestamps for every material field.

```yaml
claim:
  claim_id: clm_...
  video_id: ...
  claim_type: setup | filter | entry | exit | risk | market_context | assertion
  summary: "..."
  evidence:
    - start_seconds: 321
      end_seconds: 349
      quote: "short excerpt"
  fields:
    instrument: equities | ETF | futures | options | crypto | unknown
    side: long | short | both | unknown
    horizon: intraday | overnight | swing | unknown
    universe: "..."
    context: "..."
    trigger: "..."
    invalidation: "..."
    exit: "..."
    sizing: "..."
    required_data: [daily_ohlcv]
  extract_confidence: 0.0
  missing_fields: [trigger]
```

Post-validation rejects unsourced numerical thresholds, timestamps outside the
transcript, and claims with a mismatched video hash. It labels any assertion of
profitability as an unverified testimonial. A second extraction pass may
criticize completeness and ambiguity, but cannot fill gaps from general trading
knowledge.

### Candidate eligibility

A claim becomes `candidate` only if it has: an instrument/side/horizon;
observable conditions; a causal trigger; an invalidation/exit or a documented
reason it is a screen-only idea; and a data-feasibility assessment. Otherwise it
remains `reference` or `needs-researcher-clarification`.

The candidate generator produces a **mechanical translation** plus an
`assumption_register`. Every translation choice not explicitly in the source is
marked `researcher decision required`, never silently selected by an LLM.

## 7. Prior art, deduplication, and ranking

Before a candidate appears in the review queue, match it against:

- other Explorer candidates (embedding plus rules-field similarity);
- `lab` strategy families, releases, research backlog, and synthesis/kills;
- `llm_trader` roadmap, family specs, results, and peer reviews.

The reviewer sees a match as `duplicate`, `near_duplicate`, `structurally
distinct`, or `unknown`; automatic matching can only block obvious exact
duplicates. A new name for a killed mold is rejected unless the candidate has a
source-supported, pre-registered structural difference.

Use a transparent priority score for ordering—not an approval decision:

```text
priority = source_evidence + testability + data_feasibility + orthogonality
           + expected_value_of_information
           - duplicate_risk - cost_fragility - validation_budget_cost
```

Scores must explain their components. Penalize strategies that need unavailable
PIT data (float, news, delistings), L2/order flow, options, shorts, or unknown
fill economics; do not hide these limitations behind a high LLM confidence.

## 8. Queue and decision state machine

```text
discovered -> acquired -> extracted -> reference | needs-detail | triage
triage -> duplicate | data-blocked | parked | rejected | approved-for-brief
approved-for-brief -> preregistered -> development-run -> validation-run
validation-run -> killed | shadow-forward | research-supported
```

Only a human moves a candidate into `approved-for-brief`, `preregistered`,
`validation-run`, or `shadow-forward`. Every transition records user, time,
rationale, linked sources, immutable candidate revision, and relevant run IDs.
`research-supported` never means live-approved; `live` remains governed by its
own paper-first process.

### Experiment-brief gate

An approved brief must freeze:

- one mechanical thesis and named structural difference from prior art;
- point-in-time universe and data availability requirements;
- causal feature definitions and a future-information invariance test;
- execution/fill/cost model, failure policy, and missing-data threshold;
- development, validation, and untouched confirmation windows (with ledger
  reservation); 
- the primary metric, minimum economic effect, day-cluster uncertainty method,
  matched/randomized nulls, and explicit kill criteria;
- version/run/config/data/universe hashes and an all-opportunity accounting
  plan.

If any field is absent, the item remains a research note. No test data is spent.

## 9. Storage, provenance, and security

Use an ignored local `data/ytexplorer.duckdb` (or SQLite for P0) plus
version-controlled schemas/configuration and redacted example fixtures. Core
tables: `videos`, `video_fetches`, `transcripts`, `claims`, `claim_evidence`,
`candidates`, `candidate_sources`, `candidate_revisions`, `prior_art_matches`,
`queue_events`, `experiment_briefs`, and `experiment_links`.

Natural keys are YouTube `video_id`, transcript language + content hash, and an
Explorer-generated UUID for candidates/revisions. Raw transcripts/caches, API
credentials, and model prompts/responses that include full transcripts are
gitignored. API keys come only from environment variables; never write them to
the ledger, logs, or briefs.

## 10. Delivery plan and gates

### P0 — prove intake value (recommended first build)

1. Initialize package, config, schema migrations, CLI, and ignored data/cache.
2. Implement `ytmcp` adapter and idempotent acquire/backfill/incremental jobs.
3. Implement transcript hashing, Hermes-backed schema-constrained extraction,
   exact-quote validation, evidence links, and deterministic fixture tests. The
   extractor automatically records a claim/disposition; it creates a candidate
   only when the source output satisfies the skill's mechanical-evidence gate.
4. Implement prior-art index from the existing markdown corpus and a terminal/
   markdown review queue.
5. Export candidate and experiment briefs; do **not** mutate `lab` or
   `llm_trader`.

**P0 success (after a bounded 100-video corpus):** at least 95% of source/evidence
links resolve; zero unsourced thresholds in accepted claims; every candidate
has a prior-art disposition; reviewer accepts that the top 10 queue items are
meaningfully distinct or correctly rejected. If it mostly finds variants of
parked patterns, reduce/retarget the corpus rather than add automation.

### P1 — governed experimentation

Prerequisite: the research integrity work called out in the current reviews is
complete (causal features, immutable clean scan scopes, PIT manifests, failure
accounting, nulls, and calibrated costs). Add brief creation to the research
ledger and read-only result links from `lab`/`llm_trader`. One human-approved,
pre-registered development experiment at a time.

### P2 — optional assisted implementation

Only after P1 has produced useful, well-governed hypotheses. Generate a draft
strategy skeleton and tests in an isolated branch/worktree, with a human review
required before it reaches either package. It remains forbidden from selecting
parameters from outcomes or launching an unseen confirmation run.

## 11. Acceptance tests

- Re-running acquisition produces no duplicate videos or transcript fetches.
- A changed transcript creates a new immutable transcript revision and flags
  dependent claims for re-extraction.
- Every accepted material rule links to a valid timestamped excerpt.
- The extractor cannot create a candidate when required fields are absent.
- A known duplicate (e.g., ORB/gap-and-go) is surfaced with its existing kill
  evidence before review.
- A source requiring Level 2 or PIT news is `data-blocked`, not queued as
  runnable.
- No Explorer command can invoke broker code, mutate a `llm_trader` strategy,
  promote a skill, or spend a confirmation window.
- An exported brief validates against its schema and includes the assumption
  register, null plan, cost plan, and kill criteria.

## 12. Adversarial design review

### Research lead

**Position:** “This is worthwhile because it turns a lossy, ad hoc source of
ideas into a searchable evidence base. The goal is option discovery, especially
mechanisms and terms we are not already searching for—not using YouTube creators
as a source of expected returns.”

**Challenge received:** “Discovery volume will overwhelm the research budget.”

**Concession / change:** limit P0 to 100 videos and require a prior-art match
before extraction reaches the candidate queue. Make `validation_budget_cost` a
first-class ranking penalty and reserve confirmation windows in `lab` before
any test begins.

### Statistical skeptic

**Position:** “YouTube is an adversarial data source: survivorship, hindsight
charts, selective examples, undeclared discretion, and copied concepts. An LLM
can make its stories look more precise than the video is. Constant scanning is
a multiple-testing machine.”

**Challenge received:** “Could an evidence quote make this rigorous?”

**Concession / change:** provenance validates *what was claimed*, not whether
the claim is true. Add `extract_confidence`, `missing_fields`, the assumption
register, exact duplicate blocking, and the pre-registration gate. Treat every
video as a hypothesis generator with a prior near zero; never rank it by claimed
performance. Use all-opportunity samples, causal invariance tests, matched
nulls, and untouched confirmation data before any forward shadow book.

### Data and platform engineer

**Position:** “`ytmcp` already supplies search, channels, video details, and
cached transcripts. Reimplementing it or putting a second market-data path in
Explorer would create fragile duplication.”

**Challenge received:** “Can we make it fully autonomous and directly wire it
to `llm_trader`?”

**Concession / change:** use a thin, idempotent adapter and persist a small
normalized ledger. Explorer writes only briefs and links; it cannot register a
strategy or mutate a scanner database. Transcript and YouTube metadata are
volatile, so cache hashes, fetch receipts, and model/extractor versions. Keep
raw transcript retention and credentials out of git.

### Execution and risk owner

**Position:** “The present short-hold research has material causality, fill,
universe, and scope-integrity concerns. A polished discovery queue must not
give weak candidates an aura of readiness.”

**Challenge received:** “Won’t it delay useful testing?”

**Concession / change:** yes, deliberately. P0 has no automated testing. P1 is
blocked on the integrity release and uses zero-capital research runs only. The
queue prominently displays data prerequisites and rejection reasons; a
candidate requiring PIT float, news, L2, borrow, or realistic small-cap quotes
is worth retaining as `data-blocked`, not force-fitting to OHLCV.

### Resulting operating rule

Build **a periodic, curated, evidence-first Explorer**. Do not build a
constant, autonomous strategy-generator. Its output is a small number of
well-cited, deduplicated, pre-registration-ready hypotheses; its most valuable
outcome may often be a fast, documented rejection.
