
# `python3 -m trading.llm_trader.batchsim current` prints the base version, e.g. 2.4.1
Read and follow /Users/shtylenko/Hermes/projects/trading/llm_trader/skills/trade_skills/2.4.1.md


python3 -m trading.llm_trader.viewer
# Web UI: list of all sessions (newest first) + live detail view with SSE updates.
# Cmd-click a session in the list to open in new tab.




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

