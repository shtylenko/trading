
Read and follow /Users/shtylenko/Hermes/projects/trading/llm_trader/skills/TRADE_SIMULATOR.md


python3 -m trading.llm_trader.viewer
# Web UI: list of all sessions (newest first) + live detail view with SSE updates.
# Cmd-click a session in the list to open in new tab.




python3 -m trading.llm_trader.replay                # random RTH setup (>09:30)
python3 -m trading.llm_trader.replay --seed 7       # reproducible pick
python3 -m trading.llm_trader.replay --ticker VIVO  # random VIVO setup
python3 -m trading.llm_trader.replay --ticker AEHL --date 2025-04-22
python3 -m trading.llm_trader.replay --delay 0.3    # stream ~live (0.3s/bar)
python3 -m trading.llm_trader.replay --from-open    # start at 09:30 instead of entry