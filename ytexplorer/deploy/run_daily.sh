#!/bin/zsh
# Installed by `trading.ytexplorer.cli install-schedule`; no interactive shell required.
set -euo pipefail

PROJECT_ROOT="/Users/shtylenko/Projects"
LOG_DIR="$PROJECT_ROOT/trading/ytexplorer/data/logs"
mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

# The untracked root .env must define RAPIDAPI_KEY as well as any Hermes provider settings.
set -a
source "$PROJECT_ROOT/trading/.env"
set +a

if [[ -z "${RAPIDAPI_KEY:-}" ]]; then
  print -u2 "YT Explorer daily run skipped: RAPIDAPI_KEY is not set in trading/.env"
  exit 78
fi

exec /usr/bin/python3 -m trading.ytexplorer.cli run-scheduled --cadence daily --json \
  >> "$LOG_DIR/daily.log" 2>&1
