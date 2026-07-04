"""Entry point for `python -m trading.day_trading_simulator`.

Defaults to running the entry scanner (equivalent to `runner`). Other tools
are available as submodules:

  python -m trading.day_trading_simulator.replay ...
  python -m trading.day_trading_simulator.recorder ...
  python -m trading.day_trading_simulator.viewer ...
  python -m trading.day_trading_simulator.feed ...

Or import directly from trading.day_trading_simulator.
"""

from __future__ import annotations

import sys

from .runner import main as runner_main


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    # For now delegate to the scanner. Users who want replay etc. use the
    # explicit submodule form (documented in README/COMMANDS).
    return runner_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
