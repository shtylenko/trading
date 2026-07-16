# llm_trader

Multi-strategy **entry scanner + sealed LLM paper-trading lab**.

| Strategy | What it finds | Horizon | Skill |
|---|---|---|---|
| **`warrior`** (default) | Ross Cameron gap-up / low-float / ACD-ORB | same-day 1m | `strategies/warrior/skills/` |
| **`cup_handle`** | Davidson-style cup-and-handle swing | multi-day daily | `strategies/cup_handle/skills/` |

Architecture: [`MULTI_STRATEGY.md`](MULTI_STRATEGY.md). Warrior scanner details: [`SPEC.md`](SPEC.md). Cup-handle: [`strategies/cup_handle/SPEC.md`](strategies/cup_handle/SPEC.md).

## Run

All commands from the monorepo root (`/Users/shtylenko/Projects`) with the
repo-root `.env` loaded (Finnhub key + marketdata provider keys):

```bash
set -a && . trading/.env && set +a

# list families
python3 -m trading.llm_trader.runner --list-strategies

# warrior (default): full scan
python3 -m trading.llm_trader.runner

# cup-and-handle swing scan
python3 -m trading.llm_trader.runner --strategy cup_handle --max-symbols 100
python3 -m trading.llm_trader.runner --strategy cup_handle --symbols JPM AAPL MSFT

# pipeline smoke test on a slice or explicit names (warrior)
python3 -m trading.llm_trader.runner --max-symbols 100
python3 -m trading.llm_trader.runner --symbols AAOI ACVA ADEA --float-max 0

# custom window / profile
python3 -m trading.llm_trader.runner --start 2025-01-01 --end 2025-12-31 --profile main
```

Outputs (gitignored, under `data/`):
- **Warrior:** `entries.db` — unique on `(strategy, ticker, date, pattern)`.
- **Cup-handle:** `cup_handle/entries.db` — same schema + `features_json` (ATR, T1/T2, …).
- Matching `.txt` / `.csv` dumps beside each DB.

## Pipelines

**Warrior:** `A0` universe → `A1` gap screen → `A2` float gate → `B` ACD/ORB 5-min → store.

**Cup-handle:** universe → daily SMA/ATR + cup/handle geometry → breakout day with
ATR stop + dual targets in `features` → store.

### Paper-trade cup-handle

```bash
SDIR=$(python3 -m trading.llm_trader.recorder init \
  --ticker JPM --date 2025-06-01 --strategy cup_handle --profile swing)
python3 -m trading.llm_trader.step start --session "$SDIR"
# then step next / resolve / log per skills under strategies/cup_handle/skills/
python3 -m trading.llm_trader.recorder finalize --session "$SDIR"
```

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

The **warrior** skill at `strategies/warrior/skills/trade_skills/<version>.md`
(whichever is currently the `base` — see that family's `MAINTAINING.md`) drives an
LLM agent through a paced live session: it `init`s a session folder, streams the
tape, makes entry/management/exit decisions bar by bar (logging each turn's
reasoning), and `finalize`s the artifacts. Cup-and-handle uses the same layout
under `strategies/cup_handle/skills/`.

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

Each run records which **version** drove it. There's no separate "live" file to
duplicate — every version is its own immutable file under
`strategies/<family>/skills/trade_skills/<version>.md`, sealed (chmod read-only)
on first registration. That family's `skill_versions.json` tracks content hashes
plus a `base` pointer. To try a rule change:

```bash
python3 -m trading.llm_trader.batchsim new-version --strategy warrior --from 4.0.0 --to 4.1.0
# edit strategies/warrior/skills/trade_skills/4.1.0.md
python3 -m trading.llm_trader.batchsim run --strategy warrior --version 4.1.0 ...
python3 -m trading.llm_trader.batchsim promote --strategy warrior --version 4.1.0
```

See `strategies/warrior/skills/MAINTAINING.md` (and the cup_handle sibling).

Each session is a self-contained folder under `simulations/{TS}-{TICKER}/`
(`bars.json`, `actions.json`, `decisions.json`, `pnl.json`, `session.json`,
`journal.md`, raw `stream.jsonl`). See `SIMULATION_VIEWER_SPEC.md`.

### Batch backtesting a skill version (`batchsim`)

To measure whether a rule change actually helped, run a **fixed set of setups**
against a **pinned skill version** and compare. Each setup is traded by a headless
`hermes` agent following that version's frozen rules; every session is version +
batch stamped, so comparison is apples-to-apples.

```bash
# one-time: build a stratified, version-controlled holdout (~30 setups from entries.db)
# holdouts live under batch/<strategy>/
python3 -m trading.llm_trader.batchsim build-set --strategy warrior --n 30
# → llm_trader/batch/warrior/testset.json
python3 -m trading.llm_trader.batchsim build-set --strategy cup_handle --n 30 --unique-ticker
# → llm_trader/batch/cup_handle/testset.json

# run the holdout against a pinned version (spawns local-model agents, then audits + reports)
python3 -m trading.llm_trader.batchsim run \
    --version 2.0.2 --model <local-model> --parallel 6 --repeats 2 --tag v2.0.2

# --dry-run prints the per-setup hermes commands without spawning anything
```

`run` pins `strategies/<family>/skills/trade_skills/<version>.md` (via
`recorder init --pin-version … --batch …`, which stamps read-only — no version bump),
spawns a headless agent per setup, then runs a **post-hoc `audit`**. hermes assigns
each `-z` run its own opaque session id (it can't be named or forced), so the audit
locates each run's session by the **unique recorder SDIR** it contains — scanning
recent `hermes sessions list` ids and `hermes sessions export`-ing candidates until
every run is matched. It then voids any run whose *executed tool-call commands* show
look-ahead (read `_sealed.jsonl`, called `replay`, re-ran `step start`). It scans the
structured commands, **not** the agent's prose (which quotes the rules on every
compliant run), and voids as *unverifiable* any run whose session can't be located.
Finally it prints `recorder report --batch <tag>` (win% / P&L / avg-R / MFE-capture,
voided runs excluded). Change a rule → skill auto-bumps to `2.0.3` → run the **same
holdout** on `2.0.3` → the report tells you whether it helped, net of luck.

> First real run: smoke-test with one setup (`--repeats 1`, a 1-line testset). `run`
> prints a loud warning if it can't locate any session's commands (the `hermes
> sessions export` contract not holding on your build) instead of silently reporting
> `n=0`. Confirm the report shows `n=1` and the run is not voided as *unverifiable*.

## Tests

```bash
python3 -m pytest trading/llm_trader/tests -q
```
