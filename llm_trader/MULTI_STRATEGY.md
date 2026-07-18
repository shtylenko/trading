# Multi-strategy architecture (llm_trader)

`llm_trader` supports **strategy families**: isolated scan pipelines, skill trees,
risk defaults, and horizons that share platform infrastructure (sealed step,
deterministic execution, recorder, batchsim, viewer).

## Families (symmetric layout)

Every family lives under `strategies/<id>/` with the **same** shape:

```text
strategies/<id>/
  __init__.py          # StrategySpec adapter (id, horizon, risk, skills paths, run_scan)
  config.py            # family ScanConfig
  screen.py / patterns.py / runner.py   # (as needed)
  SPEC.md
  skills/
    skill_versions.json      # base pointer + content hashes
    trade_skills/<ver>.md    # immutable sealed skill versions
    CHANGELOG.md
    RULE_TRACE.md
    MAINTAINING.md           # version mechanics for this family
    IMPROVING.md             # promotion / experiment method (when used)
```

| id | Horizon | Skills | Entries DB |
|---|---|---|---|
| `warrior` | same-day 1min | `strategies/warrior/skills/` | `data/entries.db` |
| `cup_handle` | multi-day 1day | `strategies/cup_handle/skills/` | `data/cup_handle/entries.db` |
| `trend_pullback` | multi-day 1day | `strategies/trend_pullback/skills/` | `data/trend_pullback/entries.db` |
| `breakout_first_pullback` | multi-day 1day | `strategies/breakout_first_pullback/skills/` | `data/breakout_first_pullback/entries.db` |
| `right_side_v` | multi-day 1day | `strategies/right_side_v/skills/` | `data/right_side_v/entries.db` |
| `vwap_pullback` | same-day 5min | `strategies/vwap_pullback/skills/` | `data/vwap_pullback/entries.db` |
| `bb_squeeze_long` | same-day 5min | `strategies/bb_squeeze_long/skills/` | `data/bb_squeeze_long/entries.db` |
| `micro_pullback` | same-day 5min | `strategies/micro_pullback/skills/` | `data/micro_pullback/entries.db` |

```bash
python3 -m trading.llm_trader.runner --list-strategies
python3 -m trading.llm_trader.runner --strategy cup_handle --max-symbols 100
python3 -m trading.llm_trader.runner --strategy trend_pullback --symbols AAPL MSFT NVDA
python3 -m trading.llm_trader.batchsim current --strategy warrior
python3 -m trading.llm_trader.batchsim current --strategy cup_handle
python3 -m trading.llm_trader.batchsim current --strategy trend_pullback
```

Top-level `config.py` / `screen.py` / `patterns.py` are **thin re-exports** of the
warrior family so existing imports (`from trading.llm_trader.config import …`)
keep working.

## Platform vs family

| Platform (shared) | Family-owned |
|---|---|
| `step`, `feed`, sealed streams | `config` / screen / patterns / runner |
| `execution.ExecutionEngine` | `skills/` tree + registry |
| `recorder` session lifecycle | risk profile defaults |
| `indicators` (VWAP, SMA, ATR, …) | SPEC / RULE_TRACE / CHANGELOG |
| `batchsim` compare/promote mechanics | holdout testsets |
| `store.Entry` + strategy column | |

## Session stamp

`recorder init --strategy cup_handle` (or `warrior`) writes the family id and
horizon flags into `session.json`. `step start` reads that stamp and seals the
correct resolution stream. Skills resolve from **that family's** registry only.

## Adding a third family

1. Copy the layout of `strategies/cup_handle/` or `strategies/warrior/`.
2. Register in `strategies/__init__._build_registry`.
3. Ship `skills/trade_skills/0.1.0.md` + `skill_versions.json` with `"base": "0.1.0"`.
4. Keep testsets under `batch/<family>/` and promotion gates **within** the family.

## Batch testsets

```text
llm_trader/batch/
  warrior/
    testset.json              # default 30-set
    testset_100.json          # dev set
    testset_mini.json         # smoke
    …
  cup_handle/
    testset_30.json           # smoke / first holdout
    testset.json              # default when build-set --strategy cup_handle
```

```bash
python3 -m trading.llm_trader.batchsim build-set --strategy cup_handle --n 30 --unique-ticker
python3 -m trading.llm_trader.batchsim run --strategy cup_handle --set batch/cup_handle/testset_30.json …
```

## Design rules

- Never promote across families in one compare table.
- Never share a single skill `base` across families.
- Prefer daily multi-day sealed streams for swing v0 (not multi-week 1min).
