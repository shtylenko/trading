"""Batch backtest harness — run a fixed setup set against a pinned skill version.

The point of skill versioning is to answer "did this rule change actually help?".
This harness answers it: it spawns one **headless `hermes` agent** per
``(setup × repeat)``, each running a single *version-pinned* simulation of the
``TRADE_SIMULATOR`` skill, then aggregates the resulting ``pnl.json`` files into a
profitability report. Because every session is version + batch stamped
(``recorder init --pin-version … --batch …``), comparing two skill versions is just
running the **same setups** against each and diffing the reports.

Subcommands
-----------
    build-set   stratified, deterministic sample of setups from entries.db → testset.json
    run         spawn the agents for one skill version, tagged as one batch cohort
    audit       scan agent transcripts; mark any peeking session void (excluded from stats)
    report      thin wrapper over ``recorder report --batch`` for one cohort

Design choices (per the harness spec):
- **Local executor model** by default (`--model`) — we measure what actually trades live.
- **Fixed curated holdout** — `build-set` writes a version-controlled set reused every run,
  so version-to-version comparison is apples-to-apples, not confounded by setup luck.
- **Post-hoc audit** — `run` can't sandbox the agent's bash, so `audit` scans each run's
  captured transcript for look-ahead (reading `_sealed.jsonl`, calling `replay`, re-running
  `step start`) and voids the session rather than trusting it.
"""

from __future__ import annotations

import argparse
import concurrent.futures as _cf
import json
import random
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import recorder, skillmeta
from .config import DATA_DIR

# monorepo root — the directory that contains `trading/`, so `import trading` resolves.
REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRIES_DB = DATA_DIR / "entries.db"
# the holdout is a committed artifact, so it lives in the package (NOT under the
# gitignored data/ tree). entries.db it's sampled from is regenerable and ignored.
TESTSET_DEFAULT = Path(__file__).parent / "batch" / "testset.json"
BATCH_LOGS = recorder.SIM_ROOT / "_batch"   # captured agent transcripts, per cohort

# patterns in a captured transcript that mean the agent broke no-look-ahead / determinism
_PEEK_PATTERNS = ("_sealed.jsonl", "_step.json", "fetch_bars", "fetch_minute_bars")
_REPLAY_RE = "trading.llm_trader.replay"
_STEP_START_RE = "step start"


# ───────────────────────────── build-set ────────────────────────────────────


def _hhmm_after(t: str, after: str) -> bool:
    return (t or "") >= after


def build_set(
    n: int = 30, *, seed: int = 13, db: Path = ENTRIES_DB, after: str = "09:30"
) -> list[dict]:
    """Stratified, deterministic sample of ~``n`` setups from ``entries.db``.

    Buckets by time-of-day (early/late vs 10:30) × float (low/mid vs 5M) and takes a
    proportional slice from each, so the holdout mirrors the population instead of
    over-weighting whatever is most common. Deterministic given ``seed`` → the same
    set every run, which is what makes version comparison apples-to-apples.
    Deduped to one setup per (ticker, date) so `step start --ticker --date` is
    unambiguous.
    """
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM entries")]
    conn.close()
    rows = [r for r in rows if _hhmm_after(r.get("time_et", ""), after)]

    # dedupe to one per (ticker, date)
    seen: dict[tuple, dict] = {}
    for r in rows:
        seen.setdefault((r["ticker"], r["date"]), r)
    rows = list(seen.values())

    def bucket(r: dict) -> tuple:
        tb = "early" if (r.get("time_et") or "") < "10:30" else "late"
        fb = "lowfloat" if (r.get("float_shares") or 0) < 5e6 else "midfloat"
        return (tb, fb)

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[bucket(r)].append(r)

    rng = random.Random(seed)
    total = len(rows)
    picks: list[dict] = []
    for key in sorted(groups):
        grp = sorted(groups[key], key=lambda r: (r["ticker"], r["date"]))
        rng.shuffle(grp)
        k = max(1, round(n * len(grp) / total)) if total else 0
        picks.extend(grp[:k])

    rng.shuffle(picks)
    picks = picks[:n]
    return [
        {
            "ticker": r["ticker"], "date": r["date"], "time_et": r.get("time_et"),
            "pattern": r.get("pattern"), "float_shares": r.get("float_shares"),
            "gap_pct": r.get("gap_pct"),
        }
        for r in sorted(picks, key=lambda r: (r["ticker"], r["date"]))
    ]


def write_testset(setups: list[dict], out: Path, seed: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "created": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "n": len(setups),
        "setups": setups,
    }, indent=2) + "\n")


def load_testset(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())["setups"]


# ───────────────────────────── run ──────────────────────────────────────────


def _archived_skill(version: str) -> Path:
    p = skillmeta.archive_dir_for(skillmeta.DEFAULT_SKILL_PATH) / f"TRADE_SIMULATOR@{version}.md"
    if not p.exists():
        raise FileNotFoundError(
            f"no archived skill for version {version} at {p}. Archived snapshots are "
            "created when a version is first recorded (run one sim on it, or check "
            "skills/archive/)."
        )
    return p


def _prompt(version: str, skill_path: Path, tag: str, ticker: str, date: str,
            time_et: Optional[str]) -> str:
    """The per-setup task handed to a headless hermes agent. Thin wrapper: it pins the
    *mechanics* (version, batch tag, exact setup) and defers trading logic to the skill.

    Command lines are NOT indented (leading whitespace on `\\`-continued lines would be
    passed to the agent verbatim); the exact setup is pinned with `--time` so the agent
    trades the same row the holdout snapshotted, not an unseeded same-day pick."""
    time_flag = f" --time {time_et}" if time_et else ""
    return f"""You are executing ONE trade simulation as an automated backtest. The current
working directory is the monorepo root.

Read and follow EXACTLY the trading rules in this file (read it fully first). Do NOT
read any other skill file, and do NOT read the live skills/TRADE_SIMULATOR.md:
  {skill_path}

Setup to trade (do NOT choose your own): ticker={ticker}  date={date}  time={time_et}

Run these EXACT commands — copy them as written (do not add indentation). They pin the
skill version, the exact setup, and the batch cohort:

SDIR=$(python3 -m trading.llm_trader.recorder init --ticker {ticker} --date {date} --profile small --skill {skill_path} --pin-version {version} --batch {tag})
python3 -m trading.llm_trader.step start --session "$SDIR" --ticker {ticker} --date {date}{time_flag}

Then loop: `step next --session "$SDIR"` -> decide per the skill -> `recorder log
--session "$SDIR" --record '{{...}}'` -> repeat until STATUS end. Then:

python3 -m trading.llm_trader.recorder finalize --session "$SDIR"

HARD RULES (violating any voids the run): never open a file whose name starts with
`_`; never run `replay` or `fetch_bars` directly; never re-run `step start`. When
`finalize` prints its summary, print — as the very last line, exactly — the anchored
marker `BATCHSIM_SID=$SDIR` and stop.
"""


def _session_name(tag: str, ticker: str, date: str, rep: int) -> str:
    """A deterministic, addressable hermes session title per run, so the audit can
    export exactly that agent's tool-call log afterward."""
    return f"batchsim-{tag}-{ticker}-{date}-r{rep}"


# a recorder session id: {14 digits}-{TICKER}-{6 hex} (see recorder.init)
_SID_RE = re.compile(r"\d{14}-[A-Z0-9]+-[0-9a-f]{6}")
# the agent is told to print `BATCHSIM_SID=<sdir>` as its last line — prefer that
# anchored marker so a stray path / error / retry in the output can't mis-map the run.
_ANCHOR_RE = re.compile(r"BATCHSIM_SID=\S*?(\d{14}-[A-Z0-9]+-[0-9a-f]{6})")


def _extract_sid(text: str) -> Optional[str]:
    """Pull the recorder session id from the agent's output. Prefer the anchored
    ``BATCHSIM_SID=…`` marker (last one wins); fall back to a bare id only if no
    anchor is present, so we don't silently attribute the wrong session."""
    text = text or ""
    anchored = _ANCHOR_RE.findall(text)
    if anchored:
        return anchored[-1]
    hits = _SID_RE.findall(text)
    return hits[-1] if hits else None


def _completed_counts(tag: str) -> dict[tuple, int]:
    """(ticker, date) → number of **clean** finalized sessions for this batch.

    Voided sessions do NOT count as done, so ``--resume`` re-runs a setup whose only
    prior attempt was audit-voided instead of leaving you a tainted cohort."""
    counts: dict[tuple, int] = defaultdict(int)
    if not recorder.SIM_ROOT.exists():
        return counts
    for d in recorder.SIM_ROOT.iterdir():
        s = recorder._load_json(d / "session.json", {}) or {}
        if s.get("batch") == tag and s.get("status") == "complete" and not s.get("void"):
            counts[(s.get("ticker"), s.get("historical_date"))] += 1
    return counts


def _manifest_path(tag: str) -> Path:
    return BATCH_LOGS / tag / "manifest.jsonl"


def _load_manifest(tag: str) -> list[dict]:
    p = _manifest_path(tag)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def _run_one(work: dict) -> dict:
    """Spawn one headless hermes agent for a single (setup, repeat). Returns a result
    dict including the recorder session id (parsed from the agent's echo) and the
    hermes session name, so the audit can map session → its tool-call log."""
    log_dir = BATCH_LOGS / work["tag"]
    log_dir.mkdir(parents=True, exist_ok=True)
    name = work["session_name"]
    log_path = log_dir / f"{name}.log"

    # hermes assigns its own opaque session id (it can't be forced), so the audit
    # finds this run's session afterward by the unique recorder SDIR it contains
    # (see _resolve_batch_commands) rather than by a name here.
    cmd = ["hermes", "-z", work["prompt"], "--yolo", "-m", work["model"]]
    if work.get("dry_run"):
        return {"item": work["item"], "status": "dry-run", "cmd": cmd,
                "session_name": name, "sid": None}

    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=work["timeout"],
        )
        log_path.write_text(
            f"[exit {proc.returncode}]\n===== STDOUT =====\n{proc.stdout}\n"
            f"===== STDERR =====\n{proc.stderr}\n"
        )
        sid = _extract_sid(proc.stdout)
        return {"item": work["item"], "session_name": name, "sid": sid,
                "ticker": work["ticker"], "date": work["date"], "rep": work["rep"],
                "status": "ok" if proc.returncode == 0 else "err",
                "returncode": proc.returncode, "log": str(log_path)}
    except subprocess.TimeoutExpired:
        log_path.write_text(f"[TIMEOUT after {work['timeout']}s]\n")
        return {"item": work["item"], "session_name": name, "sid": None,
                "ticker": work["ticker"], "date": work["date"], "rep": work["rep"],
                "status": "timeout"}
    except FileNotFoundError:
        return {"item": work["item"], "session_name": name, "sid": None,
                "status": "no-hermes", "error": "`hermes` CLI not found on PATH"}


def run(
    version: str, *, model: str, testset: Path = TESTSET_DEFAULT, parallel: int = 4,
    repeats: int = 1, tag: Optional[str] = None, timeout: int = 900,
    resume: bool = False, dry_run: bool = False,
) -> str:
    """Run the batch: spawn agents for every (setup × repeat), then audit + report."""
    skill_path = _archived_skill(version)
    setups = load_testset(testset)
    tag = tag or f"{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # exact-setup pinning requires time_et on every row; a missing one would silently
    # revert to an unseeded same-day pick (the finding-5 bug). Fail loudly instead.
    missing = [f"{s.get('ticker')} {s.get('date')}" for s in setups if not s.get("time_et")]
    if missing:
        raise ValueError(
            f"testset has {len(missing)} setup(s) with no time_et (e.g. {missing[:3]}). "
            "Regenerate with `batchsim build-set` — exact-setup pinning needs it."
        )

    done = _completed_counts(tag) if resume else {}
    work: list[dict] = []
    for su in setups:
        already = done.get((su["ticker"], su["date"]), 0)
        for rep in range(repeats):
            if resume and rep < already:
                continue   # a clean (non-void) attempt already exists for this slot
            work.append({
                "item": f"{su['ticker']}_{su['date']}#r{rep}",
                "ticker": su["ticker"], "date": su["date"], "rep": rep,
                "session_name": _session_name(tag, su["ticker"], su["date"], rep),
                "tag": tag, "model": model, "timeout": timeout, "dry_run": dry_run,
                "prompt": _prompt(version, skill_path, tag, su["ticker"], su["date"],
                                  su.get("time_et")),
            })

    print(f"batch {tag}: version {version}, {len(setups)} setups × {repeats} "
          f"= {len(work)} runs (parallel {parallel}, model {model})"
          f"{' [DRY RUN]' if dry_run else ''}", file=sys.stderr)

    if dry_run:
        print(json.dumps([_run_one(w) for w in work], indent=2))
        return tag

    # Persist each run's sid ↔ hermes-session-name mapping **as it finishes** (not in
    # one write at the end), so a crash mid-batch can't strand finalized sessions with
    # no manifest entry — which the audit would then void as unverifiable.
    results: list[dict] = []
    if parallel <= 1:
        for w in work:
            r = _run_one(w)
            _append_manifest(tag, r)
            results.append(r)
    else:
        with _cf.ThreadPoolExecutor(max_workers=parallel) as ex:
            for r in ex.map(_run_one, work):     # yielded in the main thread → serial writes
                _append_manifest(tag, r)
                results.append(r)
                print(f"  [{r['status']}] {r['item']}", file=sys.stderr)

    n_void = audit(tag)
    print(f"\nbatch {tag} done: {sum(r['status']=='ok' for r in results)}/{len(results)} "
          f"agents ok, {n_void} sessions voided by audit", file=sys.stderr)

    # Loud guard: if (nearly) every finalized session voided as *unverifiable*, the
    # hermes export / --continue contract almost certainly isn't satisfied — the report
    # below would be meaningless (n≈0). Say so, actionably, instead of printing zeros.
    n_complete, n_unverif = _void_stats(tag)
    if n_complete and n_unverif >= n_complete:
        print(f"\n🛑 ALL {n_complete} finalized sessions voided as UNVERIFIABLE. The "
              "`hermes sessions export`/`--continue` audit contract is likely not\n"
              "   satisfied on this hermes build — the report below is meaningless. Run "
              "the 1-setup smoke test in the README and confirm\n   `hermes sessions "
              "export --session-id batchsim-… -` returns tool calls before trusting a "
              "batch.\n", file=sys.stderr)

    _print_batch_report(tag)
    return tag


def _append_manifest(tag: str, result: dict) -> None:
    p = _manifest_path(tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps({k: result.get(k) for k in
                 ("item", "sid", "session_name", "ticker", "date", "rep",
                  "status")}) + "\n")


def _void_stats(tag: str) -> tuple[int, int]:
    """(finalized sessions in batch, of which voided as *unverifiable*)."""
    n_complete = n_unverif = 0
    for d in _sessions_for_batch(tag):
        s = recorder._load_json(d / "session.json", {}) or {}
        if s.get("status") != "complete":
            continue
        n_complete += 1
        if "unverifiable" in (s.get("void") or ""):
            n_unverif += 1
    return n_complete, n_unverif


# ───────────────────────────── audit ────────────────────────────────────────


def _sessions_for_batch(tag: str) -> list[Path]:
    out = []
    if not recorder.SIM_ROOT.exists():
        return out
    for d in sorted(recorder.SIM_ROOT.iterdir()):
        s = recorder._load_json(d / "session.json", {}) or {}
        if s.get("batch") == tag:
            out.append(d)
    return out


def _tool_calls_in(message: dict):
    """Yield (name, args) for every tool call in a message, tolerant of shape.

    Handles the two common layouts so the audit doesn't go blind on a hermes/schema
    variation: (1) a top-level ``tool_calls: [{function:{name,arguments}}]`` list, and
    (2) tool calls embedded in a ``content`` array as ``{type: tool_use|function_call,
    name, input|arguments}``. Anything unrecognized yields nothing (caller treats an
    empty result as *unverifiable*, not clean)."""
    for tc in (message.get("tool_calls") or []):
        fn = tc.get("function", {}) or {}
        yield fn.get("name") or tc.get("name"), fn.get("arguments") or tc.get("arguments")
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") in (
                "tool_use", "function_call", "tool_call"
            ):
                yield part.get("name"), part.get("input") or part.get("arguments")


def _parse_export(export_text: str) -> Optional[str]:
    """Extract *only the executed tool-call commands* from a `hermes sessions export`
    dump — never the assistant's prose. The prose quotes the rules (which name
    `_sealed.jsonl`, `step start`, …) on every compliant run, so scanning it would
    false-positive; the tool-call arguments are what the agent actually executed.
    Returns None if no tool calls were found (the session is then unverifiable)."""
    parts: list[str] = []
    for line in export_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        for m in obj.get("messages", []):
            for name, args in _tool_calls_in(m):
                if name is not None:
                    parts.append(str(name))
                if args is not None:
                    parts.append(str(args))
    return "\n".join(parts) if parts else None


# a hermes cli session id, e.g. 20260705_150340_e347bb
_HERMES_ID_RE = re.compile(r"\d{8}_\d{6}_[0-9a-f]{6}")


def _recent_session_ids(limit: int) -> list[str]:
    """Most-recent hermes cli session ids (newest first), parsed from `sessions list`.

    We can't force or predict the id hermes assigns a `-z` run (--continue names
    nothing, --pass-session-id doesn't set it), so the audit correlates a run to its
    session by the unique recorder SDIR the session contains — starting from the recent
    ids here."""
    try:
        proc = subprocess.run(
            ["hermes", "sessions", "list", "--source", "cli", "--limit", str(limit)],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return _HERMES_ID_RE.findall(proc.stdout or "")


def _export_session(session_id: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["hermes", "sessions", "export", "--session-id", session_id, "-"],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return proc.stdout if (proc.returncode == 0 and proc.stdout.strip()) else None


def _resolve_batch_commands(sids: list[str]) -> dict[str, Optional[str]]:
    """Map each recorder session id → its agent's executed tool-call commands (or None
    if its hermes session can't be found). Finds the session by the SDIR it contains
    (globally unique, so this is correct even under parallelism), scanning recent
    hermes sessions and stopping once every sid is matched."""
    result: dict[str, Optional[str]] = {sid: None for sid in sids}
    remaining = set(s for s in sids if s)
    if not remaining:
        return result
    saw_content = False
    for hid in _recent_session_ids(limit=max(20, 3 * len(sids))):
        if not remaining:
            break
        text = _export_session(hid)
        if not text:
            continue
        matched = [s for s in remaining if s in text]
        if not matched:
            continue
        saw_content = True
        cmds = _parse_export(text)
        if cmds is None:
            print(f"⚠ audit: hermes session {hid} matched a run but yielded no parseable "
                  f"tool calls — export schema mismatch? head:\n{text[:400]}", file=sys.stderr)
        for s in matched:
            result[s] = cmds
            remaining.discard(s)
    if remaining and not saw_content:
        print(f"⚠ audit: could not locate hermes sessions for {len(remaining)} run(s) by "
              "SDIR — `hermes sessions export` contract may not hold (see README smoke "
              "test); those runs will be voided as unverifiable.", file=sys.stderr)
    return result


def _scan_commands(commands: str) -> Optional[str]:
    """Return a void reason if the executed commands break no-look-ahead / determinism,
    else None. Operates on tool-call commands only (see ``_parse_export``)."""
    for pat in _PEEK_PATTERNS:
        if pat in commands:
            return f"agent command referenced forbidden `{pat}`"
    if _REPLAY_RE in commands:
        return "agent invoked replay directly (look-ahead)"
    if commands.count(_STEP_START_RE) > 1:
        return "agent re-ran `step start` (re-seal / look-ahead)"
    return None


def audit(tag: str) -> int:
    """Void any session in the batch whose executed tool-call commands show look-ahead
    or a determinism break, or that can't be verified. Returns the number voided.

    The command source is the structured `hermes sessions export` tool calls for each
    run's session (located by the unique SDIR it contains) — NOT the free-form
    transcript, so the agent quoting its own rules no longer false-positives. A session
    with no retrievable command log is voided as *unverifiable* rather than trusted.
    """
    sessions = [d for d in _sessions_for_batch(tag)
                if (recorder._load_json(d / "session.json", {}) or {}).get("status") == "complete"]
    cmd_map = _resolve_batch_commands([d.name for d in sessions])
    voided = 0
    for d in sessions:
        session = recorder._load_json(d / "session.json", {}) or {}
        commands = cmd_map.get(d.name)
        reason = (
            "no agent command log to verify (unverifiable)"
            if commands is None else _scan_commands(commands)
        )
        if reason:
            session["void"] = reason
            (d / "session.json").write_text(json.dumps(session, indent=2))
            voided += 1
        elif session.pop("void", None) is not None:
            (d / "session.json").write_text(json.dumps(session, indent=2))  # now clean
    return voided


# ───────────────────────────── report ───────────────────────────────────────


def _print_batch_report(tag: str) -> None:
    print(f"=== batch {tag} ===")
    recorder._print_report(recorder.report_by_version(batch=tag))


# ───────────────────────────── CLI ──────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.batchsim",
        description="Batch backtest a pinned TRADE_SIMULATOR version over a fixed setup set.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build-set", help="write a stratified holdout testset.json")
    pb.add_argument("--n", type=int, default=30)
    pb.add_argument("--seed", type=int, default=13)
    pb.add_argument("--out", default=str(TESTSET_DEFAULT))
    pb.add_argument("--db", default=str(ENTRIES_DB))

    pr = sub.add_parser("run", help="spawn agents for one version/batch")
    pr.add_argument("--version", required=True, help="skill version to pin (archived)")
    pr.add_argument("--model", required=True, help="hermes model id (the local executor)")
    pr.add_argument("--set", dest="testset", default=str(TESTSET_DEFAULT))
    pr.add_argument("--parallel", type=int, default=4)
    pr.add_argument("--repeats", type=int, default=1)
    pr.add_argument("--tag", help="batch cohort tag (default: <version>-<timestamp>)")
    pr.add_argument("--timeout", type=int, default=900, help="per-setup seconds")
    pr.add_argument("--resume", action="store_true", help="skip already-finalized items")
    pr.add_argument("--dry-run", action="store_true",
                    help="print the hermes commands without spawning agents")

    pa = sub.add_parser("audit", help="scan transcripts; void peeking sessions")
    pa.add_argument("--tag", required=True)

    prep = sub.add_parser("report", help="profitability for one batch cohort")
    prep.add_argument("--tag", required=True)
    prep.add_argument("--format", choices=["table", "json"], default="table")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.cmd == "build-set":
        setups = build_set(n=args.n, seed=args.seed, db=Path(args.db))
        write_testset(setups, Path(args.out), args.seed)
        print(f"wrote {len(setups)} setups → {args.out}")
    elif args.cmd == "run":
        run(args.version, model=args.model, testset=Path(args.testset),
            parallel=args.parallel, repeats=args.repeats, tag=args.tag,
            timeout=args.timeout, resume=args.resume, dry_run=args.dry_run)
    elif args.cmd == "audit":
        n = audit(args.tag)
        print(f"voided {n} session(s) in batch {args.tag}")
    elif args.cmd == "report":
        rows = recorder.report_by_version(batch=args.tag)
        if args.format == "json":
            print(json.dumps(rows, indent=2))
        else:
            _print_batch_report(args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
