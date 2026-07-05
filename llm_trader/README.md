# llm_trader

A **momentum entry scanner** encoding Ross Cameron's (Warrior Trading) day-trading
setup from `library/analyst_warrior_trading_strategy.md`. It replays historical
market data and emits the *entries* the strategy would have taken — gap-up,
low-float, high-RVOL small caps breaking out in the morning — as a deduplicated
list (`ticker · date · time · one-sentence reason`) for **manual replay on
TradingView**. There is **no exit / P&L / win-rate simulation** — see `SPEC.md`.

## Run

All commands from the monorepo root (`/Users/shtylenko/Hermes/projects`) with the
repo-root `.env` loaded (Finnhub key + marketdata provider keys):

```bash
set -a && . trading/.env && set +a

# full default scan (2025-01-01 → 2026-06-30, small-account profile, float < 20M)
python3 -m trading.llm_trader.runner

# pipeline smoke test on a slice or explicit names
python3 -m trading.llm_trader.runner --max-symbols 100
python3 -m trading.llm_trader.runner --symbols AAOI ACVA ADEA --float-max 0

# custom window / profile
python3 -m trading.llm_trader.runner --start 2025-01-01 --end 2025-12-31 --profile main
```

Outputs (gitignored, under `data/`):
- `entries.db` — SQLite, table `entries`, **unique on `(ticker, date, pattern)`** (idempotent upsert; re-running never duplicates).
- `entries.txt` — human-readable dump.
- `entries.csv` — columns: `ticker,date,time_et,pattern,entry_px,bar_close,gap_pct,rvol,float_shares,bar_vol_mult,reason`.

## Pipeline

`A0` symbol universe (Finnhub) → `A1` daily gap screen (raw daily: gap>5%, $2–20,
avgvol>500K, RVOL>2) → `A2` float gate (yfinance, <20M) → `B` intraday ACD/ORB
breakout (5-min, 07:00–12:00 ET, consolidation→new-high, volume expansion, above
VWAP) → idempotent SQLite + text/CSV.

## Known limitations (read before trusting a full run)

- **Intraday on-demand fetch is blocked** (Alpaca 401 / MarketData 402). Stage B
  only finds entries where 5-min bars are already cached, so the *effective* entry
  universe ≈ the cached intraday set until that cache is backfilled by a paid source.
  Compare `gappers` vs `entries` in the run log.
- **Float is a current snapshot** (yfinance), not point-in-time → window limited to
  2025–2026H1. Unknown float **fails** the gate when it's active.
- **No news/catalyst filter** — a 5%+ gap on high RVOL is the implicit catalyst proxy;
  confirm the actual news on TradingView during replay.
- Core **ACD/ORB** pattern only; VWAP-bounce / micro-pullback are phase 2.

## Replay & trade simulation

Beyond scanning, the package can **replay** a recorded setup minute-by-minute and
**paper-trade** it with Ross Cameron's rules, then visualize the session.

```bash
# stream a recorded setup's 1-min bars (human table or machine JSONL)
python3 -m trading.llm_trader.replay --seed 7
python3 -m trading.llm_trader.replay --seed 7 --format jsonl --delay 60 --out-file ticks.jsonl

# the no-look-ahead reader (one streamed tick at a time; --wait blocks for the next)
python3 -m trading.llm_trader.feed --ticks ticks.jsonl --cursor 0 --wait
```

Two pacing modes for the simulation loop, both no-look-ahead:
- **Paced** (`replay --delay 60` + `feed --wait`) — one bar per wall-clock minute.
- **Interactive** (`step start` / `step next`) — **LLM-paced**: the model pings for
  the next bar when it's done analyzing, no waiting. The full day is sealed privately
  and each ping reveals exactly one more bar into the visible `stream.jsonl`.

```bash
python3 -m trading.llm_trader.step start --session "$SDIR" --seed 7
python3 -m trading.llm_trader.step next  --session "$SDIR"   # the "ping"
```

The **`skills/TRADE_SIMULATOR.md`** skill drives an LLM agent through a paced live
session: it `init`s a session folder, streams the tape, makes entry/management/exit
decisions bar by bar (logging each turn's reasoning), and `finalize`s the artifacts.

```bash
# session lifecycle (normally driven by the skill)
SDIR=$(python3 -m trading.llm_trader.recorder init --ticker EVTV --date 2026-01-13 --seed 7)
#   … replay --out-file "$SDIR/stream.jsonl";  recorder log … per turn …
python3 -m trading.llm_trader.recorder finalize --session "$SDIR"

# profitability by skill version (each run is stamped with the driving skill's
# frontmatter `version:` + a content hash, frozen at init):
python3 -m trading.llm_trader.recorder report --by-version

# visualize: TradingView-style chart + indicators + entry/exit markers + reasoning timeline
python3 -m trading.llm_trader.viewer
# Opens browser to session list (newest first). Click to view live or completed.
# Supports live SSE updates for running sessions (revealed data only).
```

Each run records which **version** of `TRADE_SIMULATOR.md` drove it, and versioning
is **automatic**: when the skill's content changes, the next `init` detects the new
content hash, **auto-bumps the patch** `version:` (writing it into the frontmatter
and `skills/skill_versions.json`), and stamps the run with it. Set `version:` by
hand only for a bigger semantic jump (minor/major) — a hand-set version is honoured
as-is. `recorder report --by-version` then attributes win rate / P&L / avg-R to each
version so you can tell whether a rule change helped.

Each session is a self-contained folder under `simulations/{TS}-{TICKER}/`
(`bars.json`, `actions.json`, `decisions.json`, `pnl.json`, `session.json`,
`journal.md`, raw `stream.jsonl`). See `SIMULATION_VIEWER_SPEC.md`.

## Tests

```bash
python3 -m pytest trading/llm_trader/tests -q
```
