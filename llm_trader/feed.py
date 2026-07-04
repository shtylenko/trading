"""Sanctioned no-look-ahead reader for a live replay tick stream.

The TRADE_SIMULATOR skill must make every entry/exit decision from **past and
current** bars only — never by peeking at the future. ``replay.py --delay 60
--out-file F`` already enforces this *physically*: at minute K the file holds
only K ticks; bar K+1 does not exist yet. This module is the **only sanctioned
way to consume that file**, and it makes the guarantee mechanical:

* It returns **exactly one tick — the one at your current cursor** — and only if
  it has already been streamed. You cannot request bar N+5 and get it early;
  if it isn't written yet you get ``STATUS waiting`` and must wait for the tape.
* It advances strictly sequentially (cursor 0,1,2,…), so the consumer can never
  jump ahead of the live stream.
* It never reads ``entries.db`` or calls a data provider — so there is no side
  channel to the future. The live file is the single source of truth.

Usage (the skill's loop):

    # cursor starts at 0; on STATUS ok, decide, then call again with cursor+1.
    # --wait blocks until that bar streams, so no manual polling loop is needed.
    python3 -m trading.llm_trader.feed --ticks F --cursor 0 --wait
    python3 -m trading.llm_trader.feed --ticks F --cursor 1 --wait
    ...

Output is JSON lines:
  * when cursor == 0, a ``meta`` line first (setup context), if available;
  * the single ``tick`` line at index == cursor, if it has streamed; then
  * a final ``STATUS`` line:
      STATUS ok       next_cursor=<n> ended=<bool>   tick delivered, keep going
      STATUS waiting  have=<n> ended=false           bar not streamed yet — wait
      STATUS end      bars=<n>                        stream finished; you're done
      STATUS nostream                                 file missing/empty yet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from .streamio import parse_stream


def _resolve(path: Path, cursor: int):
    """Return (meta, want_tick_or_None, end_or_None, n_ticks, has_next) for this
    cursor. ``has_next`` is whether the tick at ``cursor+1`` has streamed — used to
    decide ``ended`` from the actual tick sequence, not from whether the terminal
    ``end`` line happens to already be on disk (with ``--delay 0`` the whole file,
    end line included, is written at once, so ``end is not None`` is not a valid
    end-of-stream signal for the tick you're delivering)."""
    meta, ticks, end = parse_stream(path)
    if meta is None and not ticks and end is None:
        return None, None, None, 0, False
    want = next((t for t in ticks if t.get("i") == cursor), None)
    has_next = any(t.get("i") == cursor + 1 for t in ticks)
    return meta, want, end, len(ticks), has_next


def read(
    ticks_path: str | Path,
    cursor: int,
    out=sys.stdout,
    wait: bool = False,
    timeout: float = 120.0,
    poll: float = 1.0,
) -> int:
    """Emit at most one tick (the one at ``cursor``) plus a STATUS line.

    With ``wait=True`` this **blocks** (polling every ``poll`` s up to ``timeout``)
    until the tick at ``cursor`` has streamed — or the stream ends — instead of
    returning ``waiting`` immediately. It still only ever returns the tick **at**
    the cursor: waiting for a bar to exist is not looking ahead. Returns a
    process-style code: 0 ok/end, 2 waiting (timed out), 3 nostream.
    """
    path = Path(ticks_path)
    deadline = time.monotonic() + timeout
    while True:
        meta, want, end, n, has_next = _resolve(path, cursor)

        if meta is None and want is None and end is None and n == 0:
            if wait and time.monotonic() < deadline:
                time.sleep(poll)
                continue
            print("STATUS nostream", file=out)
            return 3

        if want is not None:
            if cursor == 0 and meta is not None:
                print(json.dumps(meta), file=out)
            print(json.dumps(want), file=out)
            # this tick is the last one iff no tick follows it AND the stream has
            # terminated — NOT merely because the end line exists in the file
            ended = end is not None and not has_next
            print(f"STATUS ok next_cursor={cursor + 1} ended={str(ended).lower()}", file=out)
            return 0

        # No tick at the cursor: stream finished, or not streamed yet.
        if end is not None:
            if cursor == 0 and meta is not None:
                print(json.dumps(meta), file=out)
            print(json.dumps(end), file=out)
            print(f"STATUS end bars={end.get('bars', n)}", file=out)
            return 0

        if wait and time.monotonic() < deadline:
            time.sleep(poll)
            continue

        if cursor == 0 and meta is not None:
            print(json.dumps(meta), file=out)
        print(f"STATUS waiting have={n} ended=false", file=out)
        return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.feed",
        description="No-look-ahead reader: yields one streamed tick at a time.",
    )
    p.add_argument("--ticks", required=True, help="path to the live --out-file stream")
    p.add_argument("--cursor", type=int, required=True,
                   help="index of the next tick to consume (0,1,2,…)")
    p.add_argument("--wait", action="store_true",
                   help="block until the tick at --cursor streams (or the stream "
                        "ends), instead of returning 'waiting' immediately")
    p.add_argument("--timeout", type=float, default=120.0,
                   help="max seconds to block when --wait is set (default 120)")
    p.add_argument("--poll", type=float, default=1.0,
                   help="seconds between polls when --wait is set (default 1)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return read(args.ticks, args.cursor, wait=args.wait,
                timeout=args.timeout, poll=args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
