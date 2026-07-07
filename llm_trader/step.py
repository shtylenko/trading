"""Interactive, LLM-paced stepping of a simulation — no wall-clock delay.

The paced mode (``replay --delay 60`` + ``feed --wait``) advances one bar per
wall-clock minute. This module is the alternative: the **model drives the clock**.
It pings ``step next`` whenever it has finished analyzing the current bar and gets
the next one immediately — no waiting.

No-look-ahead is preserved by a **sealed source + incremental reveal**:

* ``step start`` generates the whole day's stream once into a **private**
  ``_sealed.jsonl`` (the model must never read it — it holds the future) and writes
  only the ``meta`` line to the visible ``stream.jsonl``.
* ``step next`` reveals exactly **one** more bar: it appends that bar to the visible
  ``stream.jsonl`` and prints it. The visible file — which the recorder, the viewer,
  and the model read — therefore only ever contains past + current bars. There is no
  ``peek``; you cannot pull a bar you haven't revealed.

So the model can read ``stream.jsonl`` freely and still not see the future; only the
clearly-marked ``_sealed.jsonl`` is off-limits.

    python3 -m trading.llm_trader.step start --session <DIR> --seed 7
    python3 -m trading.llm_trader.step next  --session <DIR>   # the "ping"
    python3 -m trading.llm_trader.step status --session <DIR>
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from .config import DATA_DIR
from .fsutils import atomic_write_json, atomic_write_text, file_lock
from .streamio import parse_stream as _parse_sealed

# NOTE: `replay` (and its heavy pandas / marketdata imports) is imported lazily
# inside `start()` only. `next`/`status` are the hot path — the agent calls them
# hundreds of times per run, each in a fresh subprocess — and they never touch
# `replay`, so paying its import cost on every ping would dominate their runtime.

DEFAULT_DB = DATA_DIR / "entries.db"


def _paths(session_dir: str | Path):
    sdir = Path(session_dir)
    return sdir, sdir / "_sealed.jsonl", sdir / "stream.jsonl", sdir / "_step.json"


def _lock_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / ".session.lock"


def _get_sealed_line(path: Path, idx: int) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i == idx:
                    return line.strip()
    except FileNotFoundError:
        pass
    return None


def start(
    session_dir: str | Path,
    *,
    seed: Optional[int] = None,
    ticker: Optional[str] = None,
    date: Optional[str] = None,
    after: str = "09:30",
    from_open: bool = False,
    db: str | Path = DEFAULT_DB,
    force: bool = False,
    at_time: Optional[str] = None,
    out: TextIO = sys.stdout,
) -> int:
    """Seal the full day's stream privately, reveal only the meta line, cursor=0."""
    from . import replay  # heavy (pandas/marketdata); only `start` needs it

    sdir, sealed, stream, state = _paths(session_dir)
    sdir.mkdir(parents=True, exist_ok=True)

    # Idempotency guard: never re-seal a session that was already started. A model that
    # loses the $SDIR shell variable (a warned-about hazard in batch runs) and re-runs the
    # setup block would otherwise silently re-seal the day — a fresh sealed file with cursor
    # reset to 0, discarding revealed progress. Refuse so the mistake is a harmless no-op.
    #
    # The refusal message deliberately does NOT mention --force: a confused agent that reads
    # "pass --force to override" will do exactly that, and a --force re-seal AFTER bars were
    # revealed is a genuine look-ahead (reveal the day → reset → re-trade with knowledge).
    # For that reason --force is itself refused once any bar has been revealed (cursor > 0).
    if sealed.exists() and state.exists():
        try:
            revealed = json.loads(state.read_text(encoding="utf-8")).get("cursor", 0)
        except (ValueError, OSError):
            revealed = 0
        if revealed > 0:
            print("STATUS already-started — this session has revealed bars; re-sealing is "
                  "forbidden (look-ahead). Continue with `step next`.", file=out)
            return 0
        if not force:
            print("STATUS already-started — this session is already sealed. Do NOT re-run "
                  "`step start`; continue with `step next`.", file=out)
            return 0

    day = datetime.strptime(date, "%Y-%m-%d").date() if date else None
    h, m = (int(x) for x in after.split(":"))
    from datetime import time as dtime
    setup = replay.pick_setup(db, ticker=ticker, day=day, after=dtime(h, m),
                              seed=seed, at_time=at_time)

    # generate the whole day, instantly, into the sealed (private) file
    replay.replay(setup, from_open=from_open, delay=0, force=force,
                  fmt="jsonl", out=io.StringIO(), out_file=str(sealed))
    meta, ticks, end = _parse_sealed(sealed)
    if meta is None:
        print("STATUS error no bars sealed (provider may not serve this date)", file=out)
        return 3

    with file_lock(_lock_path(sdir)):
        # visible stream: meta only, no ticks yet
        atomic_write_text(stream, json.dumps(meta) + "\n")
        atomic_write_json(state, {"cursor": 0, "n": len(ticks), "done": False})

    print(json.dumps(meta), file=out)
    print(f"STATUS started ticks={len(ticks)} — call `step next` to reveal bar 0", file=out)
    return 0


def next_(session_dir: str | Path, out: TextIO = sys.stdout) -> int:
    """Reveal exactly one more bar into the visible stream and print it."""
    sdir, sealed, stream, state = _paths(session_dir)
    if not sealed.exists() or not state.exists():
        print("STATUS nostart — run `step start` first", file=out)
        return 3

    with file_lock(_lock_path(sdir)):
        st = json.loads(state.read_text(encoding="utf-8"))
        cur = st["cursor"]
        n_ticks = st["n"]

        if cur < n_ticks:
            line_str = _get_sealed_line(sealed, cur + 1)
            if line_str is not None:
                with open(stream, "a", encoding="utf-8") as f:
                    f.write(line_str + "\n")
                    f.flush()
                st["cursor"] = cur + 1
                atomic_write_json(state, st)
                print(line_str, file=out)
                ended = cur + 1 >= n_ticks
                print(f"STATUS ok next={cur + 1} ended={str(ended).lower()}", file=out)
                return 0

        # past the last tick: reveal the end line once, then report end idempotently
        end_str = _get_sealed_line(sealed, n_ticks + 1)
        if not st.get("done"):
            if end_str is not None:
                with open(stream, "a", encoding="utf-8") as f:
                    f.write(end_str + "\n")
                    f.flush()
            st["done"] = True
            atomic_write_json(state, st)
        if end_str is not None:
            print(end_str, file=out)
        print(f"STATUS end bars={n_ticks}", file=out)
    return 0


def status(session_dir: str | Path, out: TextIO = sys.stdout) -> int:
    """Report progress without revealing any bar."""
    sdir, sealed, stream, state = _paths(session_dir)
    if not state.exists():
        print("STATUS nostart", file=out)
        return 3
    with file_lock(_lock_path(sdir)):
        st = json.loads(state.read_text(encoding="utf-8"))
    print(f"STATUS cursor={st['cursor']} of {st['n']} done={str(st.get('done', False)).lower()}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.step",
        description="Interactive, LLM-paced stepping (no wall-clock delay).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("start", help="seal the day; reveal meta only")
    ps.add_argument("--session", required=True)
    ps.add_argument("--seed", type=int)
    ps.add_argument("--ticker")
    ps.add_argument("--date")
    ps.add_argument("--after", default="09:30")
    ps.add_argument("--time", dest="at_time",
                    help="pin the EXACT setup at this time_et (HH:MM); "
                    "disambiguates same-day setups for reproducible backtests")
    ps.add_argument("--from-open", action="store_true")
    ps.add_argument("--db", default=str(DEFAULT_DB))
    ps.add_argument("--force", action="store_true")

    pn = sub.add_parser("next", help="reveal the next bar (the ping)")
    pn.add_argument("--session", required=True)

    pt = sub.add_parser("status", help="progress without revealing a bar")
    pt.add_argument("--session", required=True)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "start":
        return start(args.session, seed=args.seed, ticker=args.ticker, date=args.date,
                     after=args.after, from_open=args.from_open, db=args.db,
                     force=args.force, at_time=args.at_time)
    if args.cmd == "next":
        return next_(args.session)
    if args.cmd == "status":
        return status(args.session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
