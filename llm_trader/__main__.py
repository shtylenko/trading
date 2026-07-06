"""Entry point for `python -m trading.llm_trader`.

Defaults to running the entry scanner (equivalent to `runner`). Other tools
are available as submodules:

  python -m trading.llm_trader.replay ...
  python -m trading.llm_trader.recorder ...
  python -m trading.llm_trader.viewer ...
  python -m trading.llm_trader.feed ...

Or import directly from trading.llm_trader.
"""

from __future__ import annotations

import sys

from .runner import main as runner_main


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in {"viewer", "replay", "recorder", "feed", "batchsim", "step"}:
        sys.stderr.write(
            f"error: '{argv[0]}' is a submodule. Run via: python3 -m trading.llm_trader.{argv[0]} ...\n"
        )
        return 2
    # For now delegate to the scanner. Users who want replay etc. use the
    # explicit submodule form (documented in README/COMMANDS).
    return runner_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
