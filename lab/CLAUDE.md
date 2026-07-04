# trading.lab (formerly `strategy_lab`)

Research harness for comparing **long-only stock trading strategies** (intraday same-day + multi-day swing). Generic engine: independent strategy families, immutable Python release modules, point-in-time universes, DuckDB as the research ledger. See `spec.md` for the full design and `roadmap.md` for P0/P1/P2 scope.

> This is the **lab** subsystem of the `trading` monorepo (see `../CLAUDE.md`). It depends on
> `trading.marketdata` (the data layer) and is the source of the validated `Release` classes
> that `trading.live` executes. Validated edge to productionize: **x03** (residual momentum).

## 🍪 GOAL (juicy cookie) — what we're chasing

- Find **one or more strategy families** with **positive, statistically reliable sum-R** across **multiple years and regimes** (2022 bear, 2023 chop, 2024 trend, 2025+ OOS).
- Strategies with complementary regime biases so the portfolio is smoother than any single strategy.
- **Clean data, correct simulation** — no cross-ticker contamination, no look-ahead, no split-adjustment mismatches, no universe-selection artifacts.
- Enough trades to be meaningful: **>20 per quarter**, not single-digit lottery tickets.

## 🔥 ANTI-GOAL (fire at your back) — what we're running from

- **Overfitting** — tuning parameters/filters to one year that collapse out-of-sample. The 2024-only trap.
- **Data contamination** — cross-ticker state leaks, mutable reference sharing, future bars used in feature computation.
- **Filter-until-zero** — adding constraints until trade count collapses to single digits. A strategy with 4 trades in 65 days is statistically meaningless.
- **Silent bugs** — computation errors that corrupt every backtest result across all releases. Zero unit-test coverage of core logic (VWAP, EMA, ATR, resampling).
- **Universe-selection artifacts** — mistaking a cached-ticker bias for alpha. The o03 gate verdict (Jun 2026) was exactly this: +34.4R on hindsight-selected names, -38R on honest universe.

Every time you design a filter, run a backtest, or add a release: ask whether this moves us toward the cookie or toward the fire. Err on the side of widening parameters and validating on holdout years. A clean negative result is worth more than a contaminated positive one.

All commands run from the **monorepo root** (so the `trading` package is importable), and the package is invoked as `trading.lab.*`:

```text
/Users/shtylenko/Hermes/projects   # <- cwd for all commands (parent of the `trading/` package)
```

## Package layout (grouped by responsibility)

| Dir | Role |
|---|---|
| `core/` | domain models (`models.py`), execution simulator (`execution.py`), metrics, time helpers. The engine contract — see `core/CLAUDE.md`. |
| `data/` | adapters: `market_data.py` (the **only** market-data source), `testsets.py`, `universes.py` |
| `storage/` | DuckDB schema + connection (`duckdb.py`); the ledger file `strategy_lab.duckdb` lives here |
| `research/` | reusable strategy `filters.py` and `signal_helpers.py` (shared across families) |
| `runner/` | `pipeline.py` — backtest orchestration + persistence flow |
| `strategies/` | strategy families and immutable release modules — see `strategies/CLAUDE.md` |
| `validation/` | the validation **library** (reusable, imported by the engine): `permutation.py`, `walkforward.py`, `gates.py`, `metrics.py`, `cscv.py`, `deflated_sharpe.py`, `run_stats.py`; **`funnel.py`** = the evaluation ladder (rungs + gates), **`funnel_eval.py`** = the DB-reading evaluator. Evergreen process docs live here too: **`EXPLORATION_PLAYBOOK.md`** = the 0→1 process for taking a NEW strategy idea from hunch to a trustworthy promote/retire verdict (capture → search → walk-forward → PBO → pre-registered sealed-OOS) — read it before starting any new family — plus `STRATEGY_SYNTHESIS.md`, `oos_spend_ledger.md`. **`research_log/`** = the per-experiment audit trail (`*_preregistration.md`, `*_findings.md`, `*_spec.md`) — the immutable record the family backlogs cite. |
| `scripts/` | **only** evergreen engine CLI entry points (`backtest`, `report`, `dashboard`, `lifecycle`, `validate_run`, `permutation_gate`, `build_universe`, `build_screen_testset`, `build_sector_map`, `disk_usage`). One-off research scripts do NOT go here — they go in `experiments/`. |
| `experiments/` | research scratch — one-off triage/test scripts grouped by direction (`multiday/`, `overnight/`, `meanrev/`, `crossasset/`, `capture/`, `misc/`), the reusable feature-search **`harness/`** (`feature_search`, `feature_search_v2`, `synthetic_control`, `multiday_search`, `multiday_power`, `portfolio_sim`), and gitignored capture ledgers in **`_data/`** (`*.parquet`, ~1.5GB, regenerated on demand). Invoked as `python3 -m trading.lab.experiments.<bucket>.<name>`. Not part of the shipped engine. |
| `testsets/` | `*.yaml` named test sets (date ranges + tickers/universe ref) |
| `universes/` | `*.yaml` point-in-time universe snapshots |
| `tests/` | unit tests + live-provider marketdata checks |

New code imports from layered packages directly, e.g. `trading.lab.runner.pipeline`, `trading.lab.core.models`.

## Anti-bloat conventions (READ before adding a script, doc, or data file)

`scripts/` + `validation/` previously accreted ~40 one-off experiment scripts and 1.5 GB of
parquet mixed in with the engine. To keep that from recurring, every new file follows three
rules — enforced by `tests/test_repo_hygiene.py`, so a violation fails CI, not a future audit:

1. **Where a new `.py` goes.** Ask: *is it imported by other code, or a cross-family
   pipeline/CLI entry point?* If yes → `scripts/` (evergreen engine CLI) or
   `experiments/harness/` (reusable research harness). If it's a script to answer **one
   research question** → `experiments/<bucket>/`, creating a **new bucket dir for a new
   direction** (don't pile unrelated one-offs into `misc/`). **Default for anything you write
   to get a result = `experiments/<bucket>/`.** A new file in `scripts/` also requires adding
   it to the `EVERGREEN_SCRIPTS` allowlist in the hygiene test — that friction is intentional.

2. **Where data goes.** All captures (`*.parquet` and any other generated data) live in
   `experiments/_data/`, which is **gitignored and regenerated on demand**. Never write data
   into a source dir; never `git add` a ledger. (The hygiene test fails if any `*.parquet` is
   tracked.)

3. **Record vs. tooling (the real anti-bloat lever).** The **permanent** record of a research
   direction is its **backlog verdict row + the `validation/research_log/` preregistration /
   findings** — *not* the script. Once a direction is logged, its experiment script is
   disposable reproduction tooling: keep it only if it's genuinely reusable; otherwise it may
   be pruned (git history preserves it). `experiments/` is scratch, not an archive that must
   grow forever — the *evidence* is the durable artifact, so the scripts needn't be.

## Common commands

```bash
# from repo root
python3 -m compileall -q trading/lab
python3 -m pytest trading/lab/tests -q

# list available releases
python3 -m trading.lab.scripts.backtest --list

# run a backtest (release + testset)
python3 -m trading.lab.scripts.backtest --release d01 --testset gap_drive_smoke_april_2024
python3 -m trading.lab.scripts.backtest -r o01 -t smoke_april_2024_sample

# resume an interrupted run by id
python3 -m trading.lab.scripts.backtest --resume <run_id>

# reporting + dashboard
python3 -m trading.lab.scripts.report
python3 -m trading.lab.scripts.dashboard --port 8890

# validate a run (permutation gate)
python3 -m trading.lab.scripts.validate_run --run <run_id> --iters 10000 --top-k 5

# evaluation funnel: where each release sits on the ladder (see Conventions)
python3 -m trading.lab.scripts.lifecycle --list          # rung + disposition per release
python3 -m trading.lab.scripts.lifecycle --evaluate-all  # recompute from stored runs
python3 -m trading.lab.scripts.lifecycle --set o03 --disposition archived --reason "..."
```

Live data uses `MARKETDATA_PROVIDERS=alpaca` (env var). `--force-data` bypasses cache; `--no-prefetch` skips the bulk prefetch pass.

Other scripts: `build_universe.py`, `build_screen_testset.py`, `permutation_gate.py`, `disk_usage.py`.

## Conventions

- **Strategy families** have a stable alias + single letter: `stocks_in_play_orb`/`o`, `post_gap_opening_drive`/`d`, `dominance_flip_reversal`/`f`. A letter is owned by one family (`d` is taken, hence reversal uses `f`).
- **Releases are immutable**: `o01`, `o02`, `d01`, `f01`, ... Never mutate a shipped release; add a new numbered one. Each release file opens with a substantial header docstring (identity, thesis, data requirements, entry rules, exit/risk rules, known limitations, next intended releases).
- **DuckDB tables** carry `strategy_alias`, `strategy_letter`, `release_id` so families stay comparable. Tables: `runs`, `sessions`, `candidates`, `signals`, `orders`, `fills`, `trades`, `release_metrics`, `release_lifecycle`, `search_runs`/`search_results`.
- **Taking a NEW idea from 0→1** (finding a *candidate* worth putting on the funnel): follow **`validation/EXPLORATION_PLAYBOOK.md`** — the family-agnostic process (Stage 0 baseline/triage → broad feature capture → pre-registered narrow search → walk-forward → PBO → pre-registered sealed-OOS confirmatory → engine cross-check). It encodes the hard-won anti-overfitting discipline (capture broad / lock search narrow, daily-portfolio objective + pooled/LOO selection, sealed year spent once, leakage checklist). The **funnel below is the complement**: how a release is evaluated once you have one.
- **Evaluation funnel** (the formalized screening ladder, defined in `validation/funnel.py`): every release climbs fixed rungs, each mapped to canonical testset(s) with a PASS/KILL/REVIEW gate, cheap→expensive:
  0. **smoke** (`smoke_*`) — ran clean, sane fills. Kills only on crash/integrity (0 trades is NOT a kill).
  1. **screen** (`screen_2022_2026_sampled`) — kill if `sum R < 0`, pooled sign-flip `p > 0.5`, or `< 30` trades.
  2. **broad_is** (`eval_2022/2023/2024_*_broad`, pooled as buckets) — kill if `sum R ≤ 0`, `p > 0.5`, or `< 20` trades/qtr; REVIEW on one-bucket carry (worst bucket `< −5R`) or weak `p`.
  3. **robustness** — param-perturbation, honest universe, regime split. Manual REVIEW (no testset).
  4. **oos** (`eval_2025_broad`, `eval_2026_h1_broad`) — the one-shot holdout; **guardrailed**: the backtest CLI refuses an OOS run below stage 2 unless `--allow-oos`.
  5. **tradeability** / 6. **portfolio** — manual REVIEW.
  - A release's position (`stage`, `disposition` ∈ active/killed/promoted/archived) lives in `release_lifecycle` — **never** as a class attribute (it's mutable and would corrupt the run code-signature). It is **auto-recomputed after every canonical-testset run** (`pipeline._auto_evaluate_lifecycle`) and surfaced as the dashboard "Funnel" column (graveyard dimmed/sorted to the bottom). Off-funnel ad-hoc testsets don't move it. Manual `archived` is never overwritten by auto-eval. Backfill/override via `scripts.lifecycle`.
  - Thresholds are named constants at the top of `validation/funnel.py`; tuning them is a code-reviewed change. Watch for 2026H1-only carry — see the cross-family finding in auto-memory.
