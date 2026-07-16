# Cup-and-handle swing family — SPEC

**Goal:** Scan for Davidson-style cup-and-handle swing setups and paper-trade them
with a plan-first LLM skill under sealed multi-day daily replay.

**Status:** Implemented (v0 mechanical subset). Objectification of "rounded cup"
and "clean air" will iterate via the family skill changelog.

## Philosophy

Plan the trade first, then trade the plan. Few high-quality multi-day setups;
ATR-based stops; dual profit targets; position size from dollar risk.

## Mechanical checklist (objectified)

| # | Question | Mechanical gate |
|---|---|---|
| 1 | Strong uptrend? | Close > SMA20, SMA50, SMA200; SMA50 rising vs 20 bars ago |
| 2 | Healthy cup? | 20–90 bar cup; depth 12–35%; ≥2 bars near trough; lips within 5% |
| 3 | Tight handle? | 3–15 bars; depth ≤40% of cup depth; volume ≤85% of cup avg; under lip |
| 4 | Room to run? | No prior high within 0.5× cup depth stacked just above handle high |
| 5 | Sector/market? | Optional, enforced SPY>SMA50 regime gate (off by default) |

**Production signal:** at the close of the first completed, valid handle, publish an
**arm plan** for a later-session buy-stop at the handle high.  The plan is never a
claim of an intraday fill on the already-completed bar.

**Confirmed-breakout label (research only):** first daily bar whose high clears
handle high, green close, volume ≥1.3× trailing-volume average.  This label is
known only after that bar closes; any confirmation strategy enters no earlier than
the next session and must model its opening gap.

**Stop:** entry − 1.5 × ATR(14).  
**T1:** entry + 0.50 × cup_depth.  
**T2:** entry + 0.80 × cup_depth.

## Pipeline

```
universe (Finnhub exchange-listed)
  → daily structure + completed-handle arm plan (patterns.detect_from_frame)
  → EntryStore (strategy=cup_handle, features JSON with plan levels)
```

## Outputs

- DB default: `llm_trader/data/cup_handle/entries.db`
- Current causal skill: `strategies/cup_handle/skills/trade_skills/0.5.0.md`
- Replay: daily bars, plan lookback 40 + hold 40 trading days. Scanner plan levels
  are hidden until the causal plan bar is revealed.

## CLI

```bash
python3 -m trading.llm_trader.runner --strategy cup_handle --max-symbols 50
python3 -m trading.llm_trader.runner --strategy cup_handle --symbols JPM AAPL MSFT

python3 -m trading.llm_trader.recorder init \
  --ticker JPM --date 2025-06-01 --strategy cup_handle --profile swing
python3 -m trading.llm_trader.step start --session "$SDIR"
```

## Out of scope (v0)

- Finviz scrape; PE/optionable filters (no fundamentals feed yet)
- Full sector ETF trifecta
- Minute-level multi-week tape
- News/catalyst filter

## Research validity contract

- `signal_mode: prebreak_arm` is the default and is the only production mode.
  `confirmed_breakout` creates post-event labels for offline diagnostics; it is
  not a same-day entry source.
- A daily `ENTER_CLOSE` is prohibited by the current skill: observing a complete
  daily candle and filling at that candle's close is temporally invalid.
- Daily replay preloads enough prehistory for SMA200 plus the visible planning
  window. It fails before emitting any stream if SMA20/50/200, ATR, RVOL, or
  the derived trend flags are unavailable or non-finite; the recorder and batch
  audit independently enforce the same contract.
- The default `max_scan_failure_rate: 0.0` is all-or-nothing: a provider/data
  failure leaves the DB unchanged. If an operator deliberately permits failures,
  only successfully scanned ticker/date scopes replace stale rows; the manifest
  records every failed symbol. Every completed scan writes `<entries>.last_scan.json`
  provenance.
