
# `python3 -m trading.llm_trader.batchsim current` prints the base version, currently 3.0.0
Read and follow /Users/shtylenko/Projects/trading/llm_trader/strategies/warrior/skills/trade_skills/3.0.0.md


python3 -m trading.llm_trader.viewer
# Web UI: list of all sessions (newest first) + live detail view with SSE updates.
# Cmd-click a session in the list to open in new tab.


cd /Users/shtylenko/Projects

set -a && . trading/.env && set +a

python3 -m trading.llm_trader.viewer

python3 -m trading.llm_trader.replay                # random RTH setup (>09:30)
python3 -m trading.llm_trader.replay --seed 7       # reproducible pick
python3 -m trading.llm_trader.replay --ticker VIVO  # random VIVO setup
python3 -m trading.llm_trader.replay --ticker AEHL --date 2025-04-22
python3 -m trading.llm_trader.replay --delay 0.3    # stream ~live (0.3s/bar)
python3 -m trading.llm_trader.replay --from-open    # start at 09:30 instead of entry


BATCH TESTING

# 1. build the fixed holdout (once) — 30 stratified setups, committed & reused every run
python3 -m trading.llm_trader.batchsim build-set --n 30

# 2. backtest a pinned version (spawns local-model agents, then audits + reports)
python3 -m trading.llm_trader.batchsim run --version 2.0.2 --model <your-local-model> \
    --parallel 6 --repeats 2 --tag v2.0.2

# 3. compare cohorts
python3 -m trading.llm_trader.recorder report --by-version

# 4. measure normal LLM variation across repeated, otherwise identical runs
python3 -m trading.llm_trader.batchsim repeat-report \
    --tag 3.0.0-20260710201028 \
    --tag 3.0.0-20260711083918 \
    --tag 3.0.0-20260711092732

# 5. compare repeated candidate and baseline panels (three runs of each recommended)
python3 -m trading.llm_trader.batchsim compare-repeats \
    --a <baseline-tag-1> --a <baseline-tag-2> --a <baseline-tag-3> \
    --b <candidate-tag-1> --b <candidate-tag-2> --b <candidate-tag-3>

# 6. inspect grades, entries, exits, adds, and in-position MFE for a cohort
python3 -m trading.llm_trader.batchsim diagnostics --tag 3.0.0-20260710201028



cd /Users/shtylenko/Projects && set -a && . trading/.env && set +a


python3 -m trading.llm_trader.batchsim run --version 2.4.1 --model deepseek-v4-flash \
    --set trading/llm_trader/batch/testset_100u.json --no-reentry


python3 -m trading.llm_trader.batchsim run --version 2.4.1 --model muse-spark-1.1 \
    --set trading/llm_trader/batch/testset_100u.json --no-reentry


python3 -m trading.llm_trader.batchsim run \
    --model muse-spark-1.1 \
    --set trading/llm_trader/batch/testset_100.json \
    --parallel 10 --repeats 1 --version 2.8.0


cd /Users/shtylenko/Projects && set -a && . trading/.env && set +a
python3 -m trading.llm_trader.batchsim run \
    --model deepseek-v4-flash \
    --set trading/llm_trader/batch/testset.json \
    --parallel 6 --repeats 2 --tag v2-baseline


cd /Users/shtylenko/Projects && set -a && . trading/.env && set +a
python3 -m trading.llm_trader.batchsim run \
    --model deepseek-v4-flash \
    --set trading/llm_trader/batch/testset_mini.json \
    --parallel 3 --repeats 1 --tag mini

FULL DAY:

python3 -m trading.llm_trader.batchsim run \
    --version 3.0.0 \
    --model deepseek-v4-flash \
    --set trading/llm_trader/batch/testset-DRUG-2024-10-15.json
    --parallel 1



python3 -m trading.llm_trader.batchsim run \
    --version 3.4.0 --model deepseek-v4-flash \
    --set trading/llm_trader/batch/testset-DRUG-2024-10-15.json \
    --max-reentries 100 --trade-until 11:30 --tag drug-reentry

# CUP HANDLE!

shtylenko@Andreys-MacBook-Air Projects % python3 -m trading.llm_trader.batchsim run \
  --strategy cup_handle \
  --version 0.1.0 \
  --set trading/llm_trader/batch/cup_handle/testset_30.json \
  --parallel 10 \
  --tag cup-smoke-30

ENTRY SCAN
  python3 -m trading.llm_trader.strategies.cup_handle.entry_scan \
    --date 2026-07-16 \
    --universe-file batch/cup_handle/universe_sp500.json \
    --max-scan-failure-rate 0.02 \
    --json scans/sp500-asof-2026-07-16.json

python3 -m trading.llm_trader.strategies.cup_handle.entry_scan \
    --date 2026-07-16 \
    --universe-file trading/llm_trader/batch/cup_handle/universe_smoke_sp500.json \
    --max-scan-failure-rate 0.02 \
    --json trading/llm_trader/scans/aapl-asof-2026-07-16.json

# TREND PULLBACK (Lance MA reclaim swing)

python3 -m trading.llm_trader.runner --strategy trend_pullback \
  --start 2024-01-01 --end 2025-12-31 \
  --symbols AAPL MSFT NVDA AMZN META GOOGL JPM

python3 -m trading.llm_trader.batchsim build-set --strategy trend_pullback --n 10 --unique-ticker --seed 7 \
  --out trading/llm_trader/batch/trend_pullback/testset_smoke.json

python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.1.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_smoke.json \
  --parallel 4 --tag tp-smoke-v010

python3 -m trading.llm_trader.viewer --port 8765


# trend_pullback 0.2.0 larger cohort (30 unique tickers)
python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.2.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_30.json \
  --parallel 6 --tag tp-v020-n30
python3 -m trading.llm_trader.batchsim report --tag tp-v020-n30

# trend_pullback 0.3.0 n30 (construction)
python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.3.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_30_v030.json \
  --parallel 6 --tag tp-v030-n30

# trend_pullback 0.4.0 n30 (SMA50 — current best)
python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.4.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_30_v040.json \
  --parallel 6 --tag tp-v040-n30

# trend_pullback 0.4.0 second key-disjoint n30
python3 -m trading.llm_trader.batchsim build-set --strategy trend_pullback --n 30 --unique-ticker --seed 42 \
  --exclude trading/llm_trader/batch/trend_pullback/testset_30_v040.json \
  --out trading/llm_trader/batch/trend_pullback/testset_30_v040_b.json
python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.4.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_30_v040_b.json \
  --parallel 6 --tag tp-v040-n30-b

# multi-year 0.4.0 (parked — FAIL)
# tags: tp-v040-y2022 .. y2025, tp-v040-2022-2025
# results: trading/llm_trader/batch/trend_pullback/multiyear/RESULTS.md


# BREAKOUT FIRST PULLBACK (Lance swing #2)
python3 -m trading.llm_trader.runner --strategy breakout_first_pullback \
  --start 2024-01-01 --end 2025-12-31 --symbols AAPL MSFT NVDA AMZN META
python3 -m trading.llm_trader.batchsim build-set --strategy breakout_first_pullback --n 10 --unique-ticker --seed 7 \
  --out trading/llm_trader/batch/breakout_first_pullback/testset_smoke.json
python3 -m trading.llm_trader.batchsim run --strategy breakout_first_pullback --version 0.1.0 \
  --set trading/llm_trader/batch/breakout_first_pullback/testset_smoke.json \
  --parallel 4 --tag bfp-smoke-v010

# breakout_first_pullback n30 + multi-year
python3 -m trading.llm_trader.batchsim run --strategy breakout_first_pullback --version 0.1.0 \
  --set trading/llm_trader/batch/breakout_first_pullback/testset_30.json --parallel 6 --tag bfp-v010-n30
# multi-year tags: bfp-v010-y2022..y2025, bfp-v010-2022-2025
# results: batch/breakout_first_pullback/multiyear/RESULTS.md

# right_side_v (PARKED multi-year FAIL)
# tags: rsv-v010-n30, rsv-v010-y2022..y2025, rsv-v010-2022-2025


# SHORT-HOLD paper books (portfolio ON, NML OFF)
# primary: micro_pullback
python3 -m trading.llm_trader.strategies.micro_pullback.paper \
  --start 2022-01-01 --end 2025-12-31
# results: batch/micro_pullback/paper/PAPER_BOOK.md
# second book: vwap_pullback
python3 -m trading.llm_trader.strategies.vwap_pullback.paper \
  --start 2022-01-01 --end 2025-12-31
# results: batch/vwap_pullback/paper/PAPER_BOOK.md
# structural A/B (NML + portfolio): batch/admission/structural_ab/RESULTS.md

# micro_pullback warrior-universe probe (current float only; not multi-year)
python3 -m trading.llm_trader.strategies.micro_pullback.probe_warrior \
  --start 2025-01-01 --end 2026-06-30
# results: batch/micro_pullback/warrior_probe/RESULTS.md  (probe FAIL years+)

# WeBull opportunity track
# Opp A: costs in trading/llm_trader/costs/webull.py
# Opp C: in-play gap continuation 12m probe
python3 -m trading.llm_trader.strategies.inplay_continuation.runner \
  --start 2025-07-01 --end 2026-06-30
# results: batch/inplay_continuation/probe_12m/RESULTS.md
# Opp B selection A/B (pre-reg select_A etc.)
python3 -m trading.llm_trader.strategies.inplay_continuation.selection_b
# results: batch/inplay_continuation/selection_b/RESULTS.md
# Opp E boring baseline scoreboard vs select_A
python3 -m trading.llm_trader.strategies.boring_baseline.scoreboard \
  --start 2025-07-01 --end 2026-06-30
# results: batch/boring_baseline/scoreboard_v010/RESULTS.md

