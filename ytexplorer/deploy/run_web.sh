#!/bin/zsh
# Persistent local monitor for the LaunchAgent installed by `install-schedule`.
set -euo pipefail

PROJECT_ROOT="/Users/shtylenko/Projects"
export PATH="/Users/shtylenko/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$PROJECT_ROOT"
exec /usr/bin/python3 -m trading.ytexplorer.cli serve --host 127.0.0.1 --port 8791
