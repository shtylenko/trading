# Peer review request — Warrior v4/v5 research and implementation

## What I want from you

Please act as a hostile-but-constructive reviewer of this work. Do not assume the
reported P&L demonstrates an edge. Look for look-ahead, selection bias, invalid
comparisons, implementation defects, missing market microstructure, unjustified
translations of discretionary trading advice into rules, and data-mining.

I want a written review with:

1. the three most serious validity problems, ranked;
2. a verdict on whether the v4/v5 architecture is a sensible direction;
3. specific changes that are justified now versus ideas that must wait for new
   forward data; and
4. a short prioritized next-experiment plan with pass/fail criteria.

Please challenge the premise if needed. “Use more indicators,” “train an LLM,” or
“tune the thresholds” is not useful without a causal mechanism and a validation
plan.

## Repository pointers

- Strategy scanner: `strategies/warrior/screen.py`, `patterns.py`, `runner.py`
- Historical replay: `replay.py`, `step.py`, `batchsim.py`
- Deterministic candle patterns: `candlebar.py` / tests and replay pattern fields
- Deterministic policy generations: `strategies/warrior/policy*.py`
- Versioned rules: `strategies/warrior/skills/trade_skills/`
- Experiment log and result provenance: `strategies/warrior/skills/CHANGELOG.md`
- Rule-to-source mapping: `strategies/warrior/skills/RULE_TRACE.md`
- Original teaching transcript/canon: `library/ross_cameron/all_content_structured.md`

## System and data model

Warrior is a small-cap, long-only momentum strategy inspired by Ross Cameron /
Warrior Trading teaching material. It is not a claim that a discretionary trader’s
judgment can be fully encoded in OHLCV rules.

### Scanner

The scanner walks a stock universe and records one ACD/ORB-like setup per
`(ticker, date, pattern)`:

- Daily gates: price band, gap-up, average daily volume, and a field called RVOL.
  **Important:** its RVOL is causal but is `prior_day_volume / rolling_prior_20_day
  average_volume`, not same-day intraday relative volume.
- Float gate: currently sourced from a cache of current float snapshots. This is
  **not point-in-time historical float** and is the principal unresolved data
  limitation.
- Intraday signal: a 5-minute bar in the morning window makes a new high after a
  consolidation, is green, has volume expansion against prior bars, and is above
  session VWAP. The detector walks bars sequentially; volume average and VWAP are
  backward-looking.
- Market-data storage convention is left-labelled: a 5-minute `09:35` bar covers
  the `09:35` through `09:39` minutes.

The test database currently has 567 scanner rows, but only 139 regular-hours
setups. Earlier development/holdout panels consumed 127 distinct regular-hours
`(ticker,date)` keys, leaving only 12 unused rows. Historical float vendors were
investigated but are not available at present, so a large valid historical OOS
cohort cannot yet be built.

### Execution and audit infrastructure

- Minute-by-minute stream is sealed and revealed sequentially; the decision path
  cannot read future bars.
- Execution engine, not a model/policy, computes fills, sizing, commissions,
  configured adverse slippage, participation caps, stops, targets, and P&L from
  decision intent.
- Ambiguous OHLC stop/target bars resolve stop-first. This is conservative but
  remains an OHLC approximation; bid/ask/NBBO and fill latency are absent.
- Batches archive skill bytes, deterministic policy code contract, stream,
  decisions, and re-derived audit output. Deterministic versions have been
  reproduced across parallelism with identical stream/decision/P&L semantics.

## Baseline: v3.0.0

v3 is the active historical baseline and is an **LLM-driven** policy, not a
deterministic one. The scanner selects a ticker/date and v3 receives the recorded
historical breakout metadata at the start of replay:

- scanner trigger time and breakout level;
- scanner RVOL and English reason;
- gap/float context.

Replay begins at that recorded trigger, then the LLM sees one-minute bars and
applies a structured momentum checklist: new high, green close, VWAP, volume,
MACD, wick/quality, time-of-day, stop under structure, break-even, 1R/2R scaling,
failed-break bailout, 5-minute runner exit, and limited re-entry. It emits intent;
the deterministic engine handles fills and P&L.

On the inspected 100-row development panel, v3.0 produced 93 trades, +$988.08,
and +0.25 effective R/setup. This is **not a clean benchmark** for v4/v5 because
it has a different information and timing contract, LLM discretion, historical
scanner metadata, and an initially too-early scanner-event interpretation.

## What was built in v4

### v4.0 — from-open, neutral replay contract

Purpose: remove the obvious historical-trigger leak from the visible trading
stream. The policy begins at 09:30 and receives no scanner time, trigger, reason,
or RVOL. It receives completed clock-aligned five-minute candles only after their
constituent minutes and can enter only on a completed 5-minute break of the prior
three candles with green/upper-third close, above VWAP, volume expansion, and
non-negative MACD.

It still uses an LLM for the final decision and management.

Result: `4.0.0-20260711220358` on the familiar 100-row panel recorded 40 trades,
59 stand-downs, one finalization error, +$719.87, and +0.18 effective R/setup. It
was never promoted: the panel was already inspected and this is not comparable to
v3 because the entry-information contract changed.

### v4.1 — deterministic candlebar evidence, LLM score interpretation

Purpose: move candle-pattern recognition out of the LLM. A small extensible
library emits deterministic events from completed 1-minute and completed 5-minute
OHLCV:

- candle-over-candle continuation;
- micro-pullback break;
- bull-flag break;
- bearish topping tail; and
- bearish breakout failure.

Each event has a geometric quality score in `[0,1]`; it is explicitly **not a
probability**. Correlated bullish patterns do not stack. v4.1 supplied those events
to the LLM plus an experimental entry score (pattern/volume/trend/candle/time) and
exit-pressure score (bearish pattern/VWAP/red-volume/MACD/stall).

The v4.1 result is only a DRUG single-name smoke: +$834.16 / +20.85R. It exposed
two defects, not an edge: the agent could enter before true three-prior-5-minute
structure existed, and it could stop producing decisions while still long, leaving
a forced end-of-day liquidation to create a misleading result.

## What was built in v5

### Core architectural change

v5 moves the v4.1 entry/exit cards into a deterministic Python state machine.
No LLM makes entry, scale, stop, or exit decisions. The policy emits one auditable
decision per completed minute; the existing execution engine remains responsible
for fills and position math.

Common v5 safeguards:

- one entry attempt; no discretionary adds/re-entries;
- engine-owned 1R and 2R scale limits;
- structural stop plus deterministic break-even handling;
- deterministic failed-break / exit-pressure / 5-minute runner exits;
- policy-authored mandatory flat by 15:55, including repeat exit intent when a
  participation cap leaves shares;
- strict completed-five-minute evidence: all five minutes must exist and
  `prior_3_*` fields are withheld until exactly three completed predecessors exist;
- exact replay audit and reproducibility checks.

### v5 experiment sequence and results

All numbers below are historical simulation diagnostics, not live performance.

| Version(s) | Change / conclusion | Result |
| --- | --- | --- |
| 5.0 | First deterministic v4.1 policy; fixes false 5-minute history and forced-EOD outcome. | 10-row smoke: +$23.11 / +0.058 effective R vs v3 +$213.23 / +0.534. Useful reliability proof, no alpha proof. |
| 5.1 | Requires all five constituent minutes for a completed 5-minute candle. | 100-row dev: −$56.43 / −0.014 effective R. Kept as integrity correction, not alpha. |
| 5.2–5.6 | Early-only and higher entry/exit score thresholds. | Some apparent dev gains, but 5.5 stood down on all 27 holdout rows. Rejected as over-selective/data-mined. |
| 5.7–5.8 | Scanner-event parity and private warm-up. Scanner event withheld until its nominal trigger; first visible tick begins at scanner event. | Wiring/smoke only; later found nominal event time was too early for a left-labelled 5-minute source bar. |
| 5.10 | Permit direct 1-minute confirmation within five minutes of scanner event. | 100-row dev: +$582.00 / +0.146 effective R, 72 trades. Timing-optimistic. |
| 5.11 | Event-minute-only entry. | 100-row dev: +$773.46 / +0.194, 21 trades; 27-row holdout: +$93.08 / +0.086, 4 trades. Timing-optimistic and not promotable. |
| 5.12 | Correct scanner-event availability from label to completed-bar close: `09:35` signal releases at `09:39`; omit retrospective reason. | 12 unused residual RTH rows: 1 trade, +$10.23 / +0.02 effective R, zero audit voids. Single vs two-worker reproduction is semantically identical. Too little data to assess. |

### v5.12 is the current valid contract, not a promoted strategy

v5.12 maintains private indicator/5-minute warm-up from 09:30, but begins the
visible/policy stream only at the scanner event’s actual availability minute. It
passes trigger and causal prior-day RVOL but not the historical English reason.
It requires on that release minute: price near/above trigger, above VWAP, current
session high, non-negative MACD, no bearish candlebar event, and score >=70.

The key caveat remains scanner selection: current float was not known historically.
The current result is therefore a **conditional replay of names selected with a
non-PIT float snapshot**, even though the intraday decision stream is causal.

## Management-only diagnostic

To separate entry selection from exits, I compared v3.0 and v5.11 only on the
already-inspected development setups where both entered at the same minute and
same average fill (15 setups). v5.11 totaled 8.78R versus v3’s 9.18R (−0.40R).
v5 exited earlier on all 15; its largest deficit was runner handling in JEM, while
it improved DTSS and STEM. This is diagnostic only and must not motivate fitting a
new rule on that panel.

The larger descriptive difference is participation: v3 traded 93/100 on its
information-rich/LLM contract; v5.11 traded 21/100. It is not legitimate to call
that delta “management alpha.”

## Explicit limitations and decisions already made

1. No v4/v5 version is promoted over v3.
2. Historical panels have been inspected during development and cannot be used for
   another threshold sweep or claimed as independent validation.
3. No historical point-in-time float source is currently accessible. Do not propose
   silently substituting current float, shares outstanding, or a reconstructed SEC
   proxy as equivalent free float.
4. v5.10/5.11 results are retained only as timing diagnostics; their scanner event
   was released four minutes too early.
5. Pattern quality weights, score thresholds, 1-minute stop formula, time cutoffs,
   and exit-pressure weights are engineering hypotheses, not Cameron quotes.
6. No bid/ask, level 2, tape, halts, short-sale constraints, news/catalyst timing,
   or actual order latency is modeled.
7. The immediate productive path is a frozen forward paper/shadow cohort: snapshot
   scanner inputs and current float at scan time, run v5.12 unchanged, and assess
   it only after a predeclared number of scanner events.

## Hard questions for review

Please answer these directly.

### Research validity

1. Does the scanner itself create a selection-conditioned backtest even after the
   event release is fixed? What information was available at the start, close, and
   following minute of the 5-minute breakout bar?
2. Is using prior-day volume / 20-day average as “RVOL” conceptually misleading or
   an acceptable causal premarket liquidity proxy? Should it be renamed and kept
   separate from intraday RVOL?
3. Is current float only a universe-selection defect, or can it materially distort
   the conditional trade distribution enough to invalidate all historical claims?
4. Are the 12 residual rows meaningful at all, or should the result be treated as
   a pure wiring test with no performance interpretation?
5. What additional survivorship, ticker-symbol, corporate-action, cache-revision,
   session, and calendar biases should be audited?

### Strategy design

6. Is it sound to make candle geometry deterministic while retaining a separate
   score layer, or is the score merely a fragile hand-built classifier? Which
   patterns/measurements would you remove first?
7. Is the v5 event-minute requirement structurally sensible, or does it make the
   policy unreasonably selective after a breakout has already completed? Give a
   causal alternative that does not chase.
8. Does the v5 fixed 1R/2R scaling and deterministic exit pressure distort the
   intended “breakout or bailout, then runner” behavior? What management rule
   should be pre-registered for forward testing, if any?
9. Should scanner-event trigger information be visible to a deterministic policy at
   all, or should the policy re-derive the break entirely from the revealed tape?
10. Is an LLM useful anywhere in this architecture after deterministic pattern and
    execution work, or should it be limited to non-decisionary annotations?

### Engineering and validation

11. Review the event timing convention carefully: is release on the `:39` minute
    a correct simulation of knowledge after the left-labelled `:35` bar closes, or
    should execution begin on the next minute/open instead?
12. Which fill assumptions are likely most consequential for low-float momentum
    names, and how would you report sensitivity without pretending OHLC can model
    the order book?
13. What exact forward-paper protocol would make a future v5.12 result credible:
    event count, freeze date, scorecard, comparison baseline, and kill criteria?
14. What test cases are missing from the pattern engine, event release plumbing,
    execution engine, and audit/reproduction path?

## Constraint for proposed improvements

Classify each recommendation as one of:

- **Integrity fix:** can implement immediately; should not be optimized for P&L.
- **Forward experiment:** may implement only with a sealed rule and predeclared
  paper-validation protocol.
- **Blocked:** requires unavailable historical point-in-time data or richer market
  microstructure data.

Please be explicit when the right answer is to stop optimizing historical results.
