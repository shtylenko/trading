# Adversarial review request: `llm_trader` cup-and-handle strategy

You are reviewing a Python trading-research/simulation system. Act as both a
skeptical systematic-trading researcher and a senior reliability engineer.

The goal is not encouragement or a superficial code-quality review. Determine
whether the current cup-and-handle results are temporally valid, reproducible,
and sufficiently realistic to support further paper trading. Identify the
highest-value changes for stability and risk-adjusted profitability **without
data snooping or curve fitting**.

Please read the implementation and artifacts before drawing conclusions. Do not
write, reset, or delete files; this workspace can contain intentional,
uncommitted changes.

## Repository and execution context

- Monorepo root (use this as the working directory for module commands):
  `/Users/shtylenko/Projects`
- Review target / package root:
  `/Users/shtylenko/Projects/trading/llm_trader`
- Shared market-data package, if the data-fetch/cache behavior needs review:
  `/Users/shtylenko/Projects/trading/marketdata`
- Run the focused test suite from the monorepo root:

  ```bash
  python3 -m pytest trading/llm_trader/tests -q
  ```

The broader monorepo has a deliberate dependency direction:
`trading.marketdata ← trading.lab ← trading.live`. `llm_trader` is a
research/simulation harness that must use point-in-time market data and must
not create a separate, incompatible market-data interpretation.

## What the cup strategy is meant to do

This is a daily, multi-day cup-and-handle breakout strategy. At the close of a
completed handle, the scanner emits a causal arm plan. A simulated buy-stop can
fill only on a *later* session. There must never be a daily same-bar close fill.

The intended mechanical setup is:

- Price above SMA20, SMA50, and SMA200; SMA50 rising versus 20 sessions ago.
- 20–90-bar cup, 12–35% depth, multiple trough bars, lips within 5%.
- 3–15-bar tight handle with restricted depth and lighter volume.
- Optional SPY regime filter (currently disabled by default).
- Initial stop: 1.5 ATR(14) below entry.
- Scanner targets: T1 = 50% of cup depth; T2 = 80% of cup depth.
- Arm expires after five later sessions; next-session entry gaps larger than
  0.5 ATR above the trigger cancel the arm.

The primary implementation/specification paths are:

- Strategy specification:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/SPEC.md`
- Config/defaults:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/config.py`
- Pattern detection and plan construction:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/patterns.py`
- Scanner runner and persistence:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/runner.py`
- Skill versions and review history:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/`

## Important current contracts and recent fixes

There were real historical correctness failures. Treat the following as claims
to verify independently in code and artifacts, not as established facts.

### Causality and indicators

- Production signal mode is `prebreak_arm`; legacy `confirmed_breakout` is
  intended only as a research label.
- The replay stream should hide `scanner_plan` until the setup bar is revealed.
- The daily stream should preload sufficient history for SMA200 and fail before
  simulation if any required daily field is absent/non-finite. Required fields
  include SMA20/50/200, ATR, RVOL, and derived trend flags.
- A prior LEVI investigation found SMA200 appearing late in a historical
  session. The intended fix was to extend warm-up/history and make missing
  required indicators fatal rather than silently allowing trading. Please
  specifically validate this claim end-to-end.
- The scanner and batch preflight should reject stale or legacy rows that lack
  exactly one complete causal plan for the pinned ticker/date/time.

Relevant paths:

- `/Users/shtylenko/Projects/trading/llm_trader/replay.py`
- `/Users/shtylenko/Projects/trading/llm_trader/step.py`
- `/Users/shtylenko/Projects/trading/llm_trader/recorder.py`
- `/Users/shtylenko/Projects/trading/llm_trader/batchsim.py`
- `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/SPEC.md`

### Deterministic execution and target ownership (v0.6 candidate)

The execution engine, not the LLM, now owns the scanner's targets:

- On a valid scanner-plan `ARM_BUY_STOP`, the recorder copies immutable T1/T2
  values into the persisted decision as `engine_targets`.
- Once the entry actually fills, the engine places exact share tranches: half
  at T1 and the entire remainder at T2.
- An LLM `SCALE_LIMIT` is prohibited for this skill and rejected by the engine.
- After a fully completed T1 tranche, the engine raises the stop to actual
  average entry; later LLM `SET_STOP` intents may only tighten it.
- The engine uses daily OHLC, configured entry/exit slippage, commission,
  participation cap, gap-aware stops, and a conservative stop-first policy on
  ambiguous target/stop bars.

Inspect these paths closely:

- `/Users/shtylenko/Projects/trading/llm_trader/execution.py`
- `/Users/shtylenko/Projects/trading/llm_trader/recorder.py`
- `/Users/shtylenko/Projects/trading/llm_trader/batchsim.py`
- `/Users/shtylenko/Projects/trading/llm_trader/skillmeta.py`
- Candidate skill:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/trade_skills/0.6.0.md`
- Previous skill:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/trade_skills/0.5.0.md`
- Version registry (currently still has base `0.5.0`; determine whether/when
  `0.6.0` is ready to promote):
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/skill_versions.json`
- Change/rule trace:
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/CHANGELOG.md`
  and
  `/Users/shtylenko/Projects/trading/llm_trader/strategies/cup_handle/skills/RULE_TRACE.md`

### Batch integrity and agent isolation

The batch runner exposes only a one-tick staged stream to the LLM and audits
transcripts/file access. It should fail closed for malformed input. Its
abandonment detector was recently changed to replay deterministic terminal state
instead of declaring every historical arm abandoned; a manually cancelled,
gap-cancelled, or expired arm must be a valid no-trade outcome.

Review whether the isolation, prompt, recorder validation, finalization, and
audit form an actual security/research-integrity boundary or merely a best
effort convention. In particular, look for data leakage through side files,
logs, timestamps, exception messages, process environment, cached data, or
post-hoc artifact mutation.

## Results that need an adversarial interpretation

### Historical v0.5.1 cohort: do not trust the original headline

Batch tag: `cup-10-v051`

- Batch metadata:
  `/Users/shtylenko/Projects/trading/llm_trader/simulations/_batch/cup-10-v051/batch.json`
- Leaf sessions:
  `/Users/shtylenko/Projects/trading/llm_trader/simulations/20260716160853-*/`

After re-audit, only three trades remained valid: `$3,238.15`, `2.16` clean R,
two valid no-trades, and four voids. The voids were EBAY (incorrect T2
remainder), GOOGL (duplicate/incorrect target ladder), PGY (missing T2), and
LEVI (forbidden file access). The original larger result must not be used as
strategy evidence.

### Current v0.6 cohort: promising execution test, not proof of edge

Top-level session ID: `20260716163724-BATCH-7d7397`

Batch tag: `cup-10-v060`

- Batch metadata and logs:
  `/Users/shtylenko/Projects/trading/llm_trader/simulations/_batch/cup-10-v060/`
- Fixed test set:
  `/Users/shtylenko/Projects/trading/llm_trader/batch/cup_handle/testset_10.json`
- Leaf sessions:
  `/Users/shtylenko/Projects/trading/llm_trader/simulations/20260716163724-*/`

The fixed set has nine causal scanner setups (seed 42; the file is named
`testset_10` but currently contains nine valid causal rows). One repeat was run
with `deepseek-v4-flash`.

Current report:

- Six valid trades: `$6,035.47`, `2.01` clean R, all winning at the complete
  trade level.
- Two valid no-trades: AU and LEVI arms expired after five later sessions.
- One no-trade void: ON correctly gap-cancelled, but the agent read forbidden
  `_step.json`; it must remain excluded from statistics.
- All nine arms were at the causal setup bar and contain engine-owned targets;
  no LLM scale order was accepted.
- Two trades (GOOGL and ORCL) reached T2. Four (EBAY, ESI, HON, PGY) hit T1 and
  then the remaining shares exited at/near the gap-aware breakeven stop.
- The two T2 trades account for about 71% of both P&L and total R. Median trade
  is about 1.16R; the other four average about 0.86R.

This sample has only six trades, no clean initial-stop loss, one agent policy
violation, and a holdout created during the same implementation cycle. A 100%
trade win rate here is not evidence of a robust 100% strategy. Confirm whether
the test set construction, scanner provenance, and scan range make it a valid
out-of-sample comparison at all.

Read-only report command:

```bash
cd /Users/shtylenko/Projects
python3 -m trading.llm_trader.batchsim report --tag cup-10-v060
```

`batchsim audit` updates session metadata; do not run it unless you first state
what it will mutate and why.

## Specific review questions

1. **Temporal validity:** Can any indicator, target, pattern feature, scanner
   row, stream field, or execution decision see future information? Check
   off-by-one boundaries at plan reveal, entry fill, target activation, expiry,
   forced close, and MFE/MAE attribution.
2. **Data integrity:** Is every required input verified at every relevant layer?
   Does a missing/late SMA200 truly stop the simulation before any possible
   trade? Are cache/provider failures, partial scans, stale DB rows, duplicate
   plans, delistings, splits, dividends, adjusted/unadjusted price handling,
   and calendar behavior handled safely?
3. **Scanner validity:** Are the cup, lip, trough, handle, volume, and
   clean-air rules mechanically faithful and robust? Which filters are likely
   overfit, redundant, or too weak? What objective improvements are justified
   by a pre-declared hypothesis rather than by these nine outcomes?
4. **Execution realism:** Are sizing, fills, slippage, liquidity participation,
   daily OHLC ordering, gaps, stops, target fills, fees, and end-of-hold
   treatment conservative and internally consistent? Does the engine-owned
   ladder correctly implement the intended half-at-T1/remainder-at-T2 policy
   under partial fills and odd share counts?
5. **Statistical validity:** Is `testset_10` an appropriate fixed holdout? What
   is missing to estimate expectancy, drawdown, hit rate, profit factor,
   tail loss, and parameter uncertainty? Propose a chronological walk-forward
   protocol, sample-size target, and acceptance criteria that prevent strategy
   promotion from a small winner-only cohort.
6. **LLM/harness safety:** Can an agent produce an invalid but apparently clean
   record, silently fail to act, access hidden data, or evade audit? Is the
   deterministic engine enough to make multiple LLM repeats unnecessary, or
   should the arm decision be fully deterministic too?
7. **Reliability and maintainability:** Find code paths where exceptions are
   swallowed, state is mutated after finalization, tests are insufficient, or
   interfaces can drift. Review these tests in particular:

   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_cup_handle.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_patterns.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_replay.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_step.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_recorder.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_execution.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_batchsim.py`
   - `/Users/shtylenko/Projects/trading/llm_trader/tests/test_indicators.py`

## Requested response format

Return a rigorous review with:

1. A one-paragraph verdict: whether the current system is suitable for further
   research, paper trading, or neither.
2. Findings ranked `P0` (invalidates results/security), `P1` (material
   reliability or bias), `P2` (important improvement), and `P3` (nice to have).
   Each finding must cite an exact file and line/function and explain the
   consequence.
3. A separate list of what you independently verified versus what remains an
   unproven claim because the data/artifacts were unavailable.
4. A concrete, pre-registered evaluation plan: data split, universe, time
   range, treatment of no-trades/voids, metrics, parameter-freezing rules, and
   explicit promotion/rejection thresholds.
5. The smallest high-confidence code/test changes that should happen before
   another paid batch, with suggested tests. Do not suggest parameter tuning
   based only on this cohort.
6. A direct answer to: “What would have to be true before you would trust this
   for paper trading, and what would have to be true before considering live
   capital?”

Be blunt about unsupported conclusions. Prefer falsifiable checks and
conservative assumptions over attractive backtest metrics.
