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
clearly-marked ``_sealed.jsonl`` is off-limits. Batch runs use the stronger
``start_isolated`` path: the harness keeps the full stream only in memory behind a
one-tick Unix-socket gateway, and publishes the complete stream only after the agent
has exited.

    python3 -m trading.llm_trader.step start --session <DIR> --seed 7
    python3 -m trading.llm_trader.step next  --session <DIR>   # the "ping"
    python3 -m trading.llm_trader.step status --session <DIR>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
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
_GATEWAY_META = ".step_gateway.json"
_GATEWAY_PROTOCOL = "one_tick_v1"


def _paths(session_dir: str | Path):
    sdir = Path(session_dir)
    return sdir, sdir / "_sealed.jsonl", sdir / "stream.jsonl", sdir / "_step.json"


def _gateway_meta_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / _GATEWAY_META


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


def _sealed_error_message(path: Path) -> Optional[str]:
    """Return a replay error emitted before any sealed stream meta, if present."""
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
        record = json.loads(first)
    except (IndexError, OSError, json.JSONDecodeError):
        return None
    if record.get("type") == "error":
        return str(record.get("message") or "replay failed before producing a stream")
    return None


def _requires_causal_scanner_plan(skill: dict) -> bool:
    value = skill.get("arm_on_scanner_plan_required")
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _causal_setup_error(replay_module, setup, skill: dict) -> Optional[str]:
    """Return a fail-closed message when a v0.5 session receives stale scanner data."""
    if not _requires_causal_scanner_plan(skill):
        return None
    errors = replay_module.causal_plan_feature_errors(setup)
    if not errors:
        return None
    return (
        "causal cup-handle setup is incompatible with this skill: "
        + "; ".join(errors)
        + ". Re-run the cup_handle scanner and regenerate the batch test set."
    )


class IsolatedStreamGateway:
    """Harness-owned, one-tick gateway for a pre-sealed in-memory stream.

    The agent receives only the Unix-socket endpoint. The full stream is never
    written under its session directory and this gateway exposes no random-access
    operation: it can reveal exactly the next tick, only after the previous tick has
    an append-only decision record. The gateway snapshots every decision before it
    permits the next tick and verifies that the session manifest and revealed stream
    have not been rewritten. ``publish`` is an in-process owner operation, not a
    socket command, so an agent cannot expose the rest of the day or revise a past
    decision after seeing a future bar.
    """

    def __init__(self, session_dir: str | Path, records: list[dict]) -> None:
        if not records or records[0].get("type") != "meta":
            raise ValueError("isolated stream requires a leading meta record")
        self.sdir = Path(session_dir)
        self._records = records
        self._meta = records[0]
        self._ticks = [r for r in records if r.get("type") == "tick"]
        ends = [r for r in records if r.get("type") in ("end", "error")]
        self._end = ends[-1] if ends else None
        self._cursor = 0
        self._done = False
        self._published = False
        self._closed = False
        manifest = self.sdir / "session.json"
        # ``start_isolated`` is also a low-level test/helper API and may be used
        # before recorder.init creates a manifest. Batch sessions always have one;
        # when present, it is frozen for the full agent lifetime.
        self._manifest_digest = self._file_digest(manifest) if manifest.exists() else None
        self._visible_records: list[dict] = [self._meta]
        self._committed_decisions: list[str] = []
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._socket_dir = Path(tempfile.mkdtemp(prefix="llm-trader-gateway-"))
        self.socket_path = self._socket_dir / "one_tick.sock"
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _file_digest(path: Path) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as e:
            raise ValueError("isolated session artifact is unavailable") from e

    @staticmethod
    def _decision_fingerprint(record: dict) -> str:
        return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _visible_stream_text(self) -> str:
        return "".join(json.dumps(record) + "\n" for record in self._visible_records)

    def _assert_session_manifest_unchanged(self) -> None:
        if self._manifest_digest is None:
            return
        if self._file_digest(self.sdir / "session.json") != self._manifest_digest:
            raise ValueError("isolated session manifest was modified")

    def _assert_visible_stream_unchanged(self) -> None:
        try:
            actual = (self.sdir / "stream.jsonl").read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError("revealed stream is unavailable") from e
        if actual != self._visible_stream_text():
            raise ValueError("revealed stream was modified outside the gateway")

    def _decision_history(self) -> tuple[list[int], list[str]]:
        """Return validated raw-decision indexes and canonical content fingerprints.

        ``recorder log`` is the only supported writer, but the agent has a writable
        staging directory. The gateway therefore treats this file as untrusted until
        it has committed an exact snapshot before revealing the following tick.
        """
        path = self.sdir / "decisions.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return [], []
        except OSError as e:
            raise ValueError("decision log is unavailable") from e

        indexes: list[int] = []
        fingerprints: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError("decision log contains an incomplete record") from e
            if not isinstance(record, dict) or not isinstance(record.get("i"), int):
                raise ValueError("decision log contains an invalid record")
            indexes.append(record["i"])
            fingerprints.append(self._decision_fingerprint(record))
        return indexes, fingerprints

    def _commit_decisions_before_next_tick(self) -> bool:
        """Freeze all decisions that causally precede the next reveal.

        Before revealing tick ``n``, decisions ``0..n-1`` must exist exactly once and
        match the history committed before earlier reveals. A direct rewrite, truncate,
        duplicate, or fabricated future decision fails closed without serving a bar.
        Returns ``False`` only for the ordinary case where the latest decision has not
        been logged yet, so the caller can retain its useful ``decision-required``
        status rather than treating a missing record as tampering.
        """
        indexes, fingerprints = self._decision_history()
        if indexes != list(range(len(indexes))) or len(indexes) > self._cursor:
            raise ValueError("decision log has duplicate, missing, or future indexes")
        if fingerprints[:len(self._committed_decisions)] != self._committed_decisions:
            raise ValueError("a committed decision was modified")
        if len(indexes) < self._cursor:
            return False
        self._committed_decisions = fingerprints
        return True

    def _assert_final_decision_history(self) -> None:
        """Ensure the agent did not rewrite prior decisions just before exit.

        The decision for the last revealed tick need not have been committed by a
        later ``next`` call, so it may be present or absent. It cannot alter any
        decision committed before that tick.
        """
        indexes, fingerprints = self._decision_history()
        committed_n = len(self._committed_decisions)
        if fingerprints[:committed_n] != self._committed_decisions:
            raise ValueError("a committed decision was modified")
        if indexes != list(range(len(indexes))):
            raise ValueError("decision log has duplicate, missing, or future indexes")
        if len(indexes) not in {committed_n, self._cursor}:
            raise ValueError("decision log changed after the last committed tick")

    def _assert_gateway_integrity(self) -> None:
        self._assert_session_manifest_unchanged()
        self._assert_visible_stream_unchanged()

    def start(self) -> "IsolatedStreamGateway":
        """Publish only meta, then serve one-tick requests in a daemon thread."""
        self.sdir.mkdir(parents=True, exist_ok=True)
        stream = self.sdir / "stream.jsonl"
        atomic_write_text(stream, json.dumps(self._meta) + "\n")

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(8)
        server.settimeout(0.2)
        self._server = server
        atomic_write_json(_gateway_meta_path(self.sdir), {
            "protocol": _GATEWAY_PROTOCOL,
            "socket": str(self.socket_path),
        })
        self._thread = threading.Thread(
            target=self._serve, name=f"one-tick-{self.sdir.name}", daemon=True
        )
        self._thread.start()
        return self

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    raw = conn.recv(4096)
                    request = json.loads(raw.decode("utf-8"))
                    op = request.get("op")
                    if op == "next":
                        response = self._next_response()
                    elif op == "status":
                        response = self._status_response()
                    else:
                        response = {"rc": 3, "lines": ["STATUS gateway-invalid-request"]}
                except Exception as e:  # never expose a traceback/data through the gateway
                    response = {"rc": 3, "lines": [f"STATUS gateway-error {type(e).__name__}"]}
                conn.sendall(json.dumps(response).encode("utf-8"))

    def _next_response(self) -> dict:
        with self._state_lock, file_lock(_lock_path(self.sdir)):
            if self._closed or self._published:
                return {"rc": 3, "lines": ["STATUS gateway-closed"]}
            try:
                self._assert_gateway_integrity()
                decision_ready = self._commit_decisions_before_next_tick()
            except ValueError:
                return {"rc": 3, "lines": ["STATUS decision-integrity-error"]}

            # Bar i must have an immutable decision before the gateway permits i+1.
            if self._cursor > 0 and not decision_ready:
                return {
                    "rc": 3,
                    "lines": [f"STATUS decision-required i={self._cursor - 1}"],
                }

            if self._cursor < len(self._ticks):
                tick = self._ticks[self._cursor]
                line = json.dumps(tick)
                with open(self.sdir / "stream.jsonl", "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    f.flush()
                self._visible_records.append(tick)
                self._cursor += 1
                ended = self._cursor >= len(self._ticks)
                return {
                    "rc": 0,
                    "lines": [line, f"STATUS ok next={self._cursor} ended={str(ended).lower()}"],
                }

            if not self._done:
                if self._end is not None:
                    line = json.dumps(self._end)
                    with open(self.sdir / "stream.jsonl", "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                        f.flush()
                    self._visible_records.append(self._end)
                self._done = True
            end_line = json.dumps(self._end) if self._end is not None else None
            lines = [end_line] if end_line is not None else []
            lines.append(f"STATUS end bars={len(self._ticks)}")
            return {"rc": 0, "lines": lines}

    def _status_response(self) -> dict:
        with self._state_lock:
            return {
                "rc": 0,
                "lines": [
                    f"STATUS cursor={self._cursor} of {len(self._ticks)} "
                    f"done={str(self._done).lower()}"
                ],
            }

    def remaining_ticks(self) -> int:
        """How many sealed ticks have not yet been revealed (owner-only probe)."""
        with self._state_lock:
            return max(0, len(self._ticks) - self._cursor)

    def revealed_tick_count(self) -> int:
        """Number of ticks already revealed to the agent."""
        with self._state_lock:
            return self._cursor

    def setup_bar_index(self, setup_date: str) -> int:
        """Index of the scanner setup day in the sealed multi-day stream (owner-only)."""
        with self._state_lock:
            for t in self._ticks:
                if t.get("is_setup_day"):
                    return int(t["i"])
            for t in self._ticks:
                if t.get("date") == setup_date:
                    return int(t["i"])
            # Fallback: plan_lookback_bars after stream start (classic cup_handle shape).
            try:
                pl = int(self._meta.get("plan_lookback_bars") or 40)
            except (TypeError, ValueError):
                pl = 40
            return min(pl, max(0, len(self._ticks) - 1))

    def publish(self) -> None:
        """Owner-only finalization: publish the full stream after the agent exits."""
        with self._state_lock, file_lock(_lock_path(self.sdir)):
            if self._published:
                return
            self._assert_gateway_integrity()
            self._assert_final_decision_history()
            atomic_write_text(
                self.sdir / "stream.jsonl",
                "".join(json.dumps(record) + "\n" for record in self._records),
            )
            self._published = True
        self.close()

    def close(self) -> None:
        """Stop serving and remove the public endpoint metadata."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            if self._server is not None:
                try:
                    self._server.close()
                except OSError:
                    pass
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        _gateway_meta_path(self.sdir).unlink(missing_ok=True)
        self.socket_path.unlink(missing_ok=True)
        shutil.rmtree(self._socket_dir, ignore_errors=True)


def _gateway_request(session_dir: str | Path, op: str) -> dict:
    """Send a constrained request to a harness-owned isolated gateway."""
    try:
        meta = json.loads(_gateway_meta_path(session_dir).read_text(encoding="utf-8"))
        if meta.get("protocol") != _GATEWAY_PROTOCOL:
            raise ValueError("unexpected protocol")
        endpoint = meta["socket"]
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5.0)
            client.connect(endpoint)
            client.sendall(json.dumps({"op": op}).encode("utf-8"))
            client.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                data = client.recv(4096)
                if not data:
                    break
                chunks.append(data)
        return json.loads(b"".join(chunks).decode("utf-8"))
    except Exception:
        # Fail closed. Do not fall back to a local sealed file for an isolated session.
        return {"rc": 3, "lines": ["STATUS gateway-unavailable"]}


def start_isolated(
    session_dir: str | Path,
    *,
    seed: Optional[int] = None,
    ticker: Optional[str] = None,
    date: Optional[str] = None,
    after: str = "09:30",
    from_open: bool = False,
    neutral_meta: bool = False,
    five_minute_context: bool = False,
    db: str | Path = DEFAULT_DB,
    at_time: Optional[str] = None,
    strategy: Optional[str] = None,
    bar_resolution: Optional[str] = None,
    max_hold_bars: Optional[int] = None,
) -> IsolatedStreamGateway:
    """Pre-seal a batch stream in harness memory and return its one-tick gateway.

    Unlike :func:`start`, this never creates ``_sealed.jsonl`` or ``_step.json``.
    It is intentionally owner-process-only: an agent gets a gateway endpoint via
    ``step next`` but has neither a file path nor a protocol operation that can read
    future records.
    """
    from . import replay  # heavy (pandas/marketdata); harness only

    # Prefer strategy stamped on session.json (recorder.init --strategy …).
    session_meta: dict = {}
    sj = Path(session_dir) / "session.json"
    if sj.exists():
        try:
            session_meta = json.loads(sj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            session_meta = {}
    strategy_id = (
        strategy
        or session_meta.get("strategy")
        or (session_meta.get("config") or {}).get("strategy")
        or "warrior"
    )
    cfg = session_meta.get("config") or {}
    bar_resolution = bar_resolution or cfg.get("bar_resolution")
    max_hold = max_hold_bars if max_hold_bars is not None else cfg.get("max_hold_bars")
    if max_hold is not None:
        try:
            max_hold = int(max_hold)
        except (TypeError, ValueError):
            max_hold = None

    db_path = Path(db)
    if strategy_id != "warrior" and db_path == DEFAULT_DB:
        try:
            from .strategies import get_strategy
            db_path = get_strategy(strategy_id).default_db_path()
        except KeyError:
            pass

    day = datetime.strptime(date, "%Y-%m-%d").date() if date else None
    h, m = (int(x) for x in after.split(":"))
    from datetime import time as dtime
    setup = replay.pick_setup(
        db_path,
        ticker=ticker,
        day=day,
        after=dtime(h, m),
        seed=seed,
        at_time=at_time,
        strategy=strategy_id if strategy_id != "warrior" else None,
        skip_time_filter=strategy_id != "warrior",
    )
    causal_error = _causal_setup_error(replay, setup, session_meta.get("skill") or {})
    if causal_error:
        raise RuntimeError(causal_error)
    captured = io.StringIO()
    replay.replay(
        setup,
        from_open=from_open,
        neutral_meta=neutral_meta,
        five_minute_context=five_minute_context,
        delay=0,
        force=False,
        fmt="jsonl",
        out=captured,
        bar_resolution=bar_resolution,
        max_hold_bars=max_hold,
    )
    records = []
    for line in captured.getvalue().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not records or records[0].get("type") != "meta":
        message = records[0].get("message") if records else None
        raise RuntimeError(message or "no bars sealed (provider may not serve this date)")
    return IsolatedStreamGateway(session_dir, records).start()


def start(
    session_dir: str | Path,
    *,
    seed: Optional[int] = None,
    ticker: Optional[str] = None,
    date: Optional[str] = None,
    after: str = "09:30",
    from_open: bool = False,
    neutral_meta: bool = False,
    five_minute_context: bool = False,
    db: str | Path = DEFAULT_DB,
    force: bool = False,
    at_time: Optional[str] = None,
    strategy: Optional[str] = None,
    out: TextIO = sys.stdout,
) -> int:
    """Seal the full stream privately, reveal only the meta line, cursor=0.

    Strategy is read from ``session.json`` when present (set by ``recorder init
    --strategy``), else from the ``strategy`` argument / setup row.
    """
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

    session_meta: dict = {}
    session_json = sdir / "session.json"
    if session_json.exists():
        try:
            session_meta = json.loads(session_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            session_meta = {}

    strategy_id = (
        strategy
        or session_meta.get("strategy")
        or (session_meta.get("config") or {}).get("strategy")
        or "warrior"
    )
    cfg = session_meta.get("config") or {}
    bar_resolution = cfg.get("bar_resolution")
    max_hold = cfg.get("max_hold_bars")
    if max_hold is not None:
        try:
            max_hold = int(max_hold)
        except (TypeError, ValueError):
            max_hold = None

    # Default DB per strategy when caller left the warrior default.
    db_path = Path(db)
    if strategy_id != "warrior" and db_path == DEFAULT_DB:
        try:
            from .strategies import get_strategy
            db_path = get_strategy(strategy_id).default_db_path()
        except KeyError:
            pass

    day = datetime.strptime(date, "%Y-%m-%d").date() if date else None
    if day is None and session_meta.get("historical_date"):
        day = datetime.strptime(session_meta["historical_date"], "%Y-%m-%d").date()
    ticker = ticker or session_meta.get("ticker")
    h, m = (int(x) for x in after.split(":"))
    from datetime import time as dtime
    skip_time = strategy_id != "warrior"
    setup = replay.pick_setup(
        db_path,
        ticker=ticker,
        day=day,
        after=dtime(h, m),
        seed=seed,
        at_time=at_time,
        strategy=strategy_id if strategy_id != "warrior" else None,
        skip_time_filter=skip_time,
    )

    # Skill frontmatter may request neutral meta / 5m context / from-open
    skill = session_meta.get("skill") or {}
    causal_error = _causal_setup_error(replay, setup, skill)
    if causal_error:
        print(f"STATUS error {causal_error}", file=out)
        return 3
    if skill.get("session_from_open") in (True, "true", "True", "1", "yes"):
        from_open = True
    if skill.get("five_minute_context") in (True, "true", "True", "1", "yes"):
        five_minute_context = True
    if skill.get("completed_five_minute_entry_required") in (True, "true", "True", "1", "yes"):
        neutral_meta = True  # v4 warrior: don't leak scanner trigger
    # Daily swing sessions begin before their scanner reference date.  The
    # default metadata includes scanner-derived levels, so exposing it before
    # the causal plan bar would leak future information in manual replay.
    horizon = str(cfg.get("horizon") or skill.get("horizon") or "").lower()
    resolution = str(cfg.get("bar_resolution") or skill.get("bar_resolution") or "").lower()
    if horizon in ("multi_day", "multiday", "swing") or resolution in ("1day", "daily"):
        neutral_meta = True

    # generate the whole stream into the sealed (private) file
    replay.replay(
        setup,
        from_open=from_open,
        neutral_meta=neutral_meta,
        five_minute_context=five_minute_context,
        delay=0,
        force=force,
        fmt="jsonl",
        out=io.StringIO(),
        out_file=str(sealed),
        bar_resolution=bar_resolution,
        max_hold_bars=max_hold,
    )
    meta, ticks, end = _parse_sealed(sealed)
    if meta is None:
        message = _sealed_error_message(sealed)
        print(
            f"STATUS error {message or 'no bars sealed (provider may not serve this date)'}",
            file=out,
        )
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
    if _gateway_meta_path(session_dir).exists():
        response = _gateway_request(session_dir, "next")
        for line in response["lines"]:
            print(line, file=out)
        return int(response["rc"])

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
    if _gateway_meta_path(session_dir).exists():
        response = _gateway_request(session_dir, "status")
        for line in response["lines"]:
            print(line, file=out)
        return int(response["rc"])

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
    ps.add_argument("--neutral-meta", action="store_true",
                    help="hide scanner trigger/time/RVOL/reason from the visible stream")
    ps.add_argument("--five-minute-context", action="store_true",
                    help="add a completed 5-minute candle to each fifth revealed tick")
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
                     force=args.force, at_time=args.at_time,
                     neutral_meta=args.neutral_meta,
                     five_minute_context=args.five_minute_context)
    if args.cmd == "next":
        return next_(args.session)
    if args.cmd == "status":
        return status(args.session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
