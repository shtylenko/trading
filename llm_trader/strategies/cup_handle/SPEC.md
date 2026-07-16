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
| 5 | Sector/market? | Optional SPY>SMA50 (off by default until wired) |

**Entry:** first daily bar whose high clears handle high, green close, volume ≥1.3× 20d avg.

**Stop:** entry − 1.5 × ATR(14).  
**T1:** entry + 0.50 × cup_depth.  
**T2:** entry + 0.80 × cup_depth.

## Pipeline

```
universe (Finnhub exchange-listed)
  → daily structure + cup/handle detect (patterns.detect_from_frame)
  → EntryStore (strategy=cup_handle, features JSON with plan levels)
```

## Outputs

- DB default: `llm_trader/data/cup_handle/entries.db`
- Skill: `strategies/cup_handle/skills/trade_skills/0.1.0.md`
- Replay: daily bars, plan lookback 40 + hold 40 trading days

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
