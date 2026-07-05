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


def _prompt(version: str, skill_path: Path, tag: str, ticker: str, date: str) -> str:
    """The per-setup task handed to a headless hermes agent. Thin wrapper: it pins the
    *mechanics* (version, batch tag, setup) and defers all trading logic to the skill."""
    return f"""You are executing ONE trade simulation as an automated backtest. The current
working directory is the monorepo root.

Read and follow EXACTLY the trading rules in this file (read it fully first). Do NOT
read any other skill file, and do NOT read the live skills/TRADE_SIMULATOR.md:
  {skill_path}

Setup to trade (do NOT choose your own): ticker={ticker}  date={date}

Run these EXACT commands — they pin the skill version and tag the batch cohort:

  SDIR=$(python3 -m trading.llm_trader.recorder init \\
      --ticker {ticker} --date {date} --profile small \\
      --skill {skill_path} --pin-version {version} --batch {tag})
  python3 -m trading.llm_trader.step start --session "$SDIR" --ticker {ticker} --date {date}

Then loop: `step next --session "$SDIR"` → decide per the skill → `recorder log
--session "$SDIR" --record '{{...}}'` → repeat until STATUS end. Then:

  python3 -m trading.llm_trader.recorder finalize --session "$SDIR"

HARD RULES (violating any voids the run): never open a file whose name starts with
`_`; never run `replay` or `fetch_bars` directly; never re-run `step start`. When
`finalize` prints its summary, echo the SDIR path and stop.
"""


def _completed_counts(tag: str) -> dict[tuple, int]:
    """(ticker, date) → number of finalized sessions already recorded for this batch."""
    counts: dict[tuple, int] = defaultdict(int)
    if not recorder.SIM_ROOT.exists():
        return counts
    for d in recorder.SIM_ROOT.iterdir():
        s = recorder._load_json(d / "session.json", {}) or {}
        if s.get("batch") == tag and s.get("status") == "complete":
            counts[(s.get("ticker"), s.get("historical_date"))] += 1
    return counts


def _run_one(work: dict) -> dict:
    """Spawn one headless hermes agent for a single (setup, repeat). Returns a result dict."""
    log_dir = BATCH_LOGS / work["tag"]
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{work['ticker']}_{work['date']}_r{work['rep']}.log"

    cmd = ["hermes", "-z", work["prompt"], "--yolo", "-m", work["model"]]
    if work.get("dry_run"):
        return {"item": work["item"], "status": "dry-run", "cmd": cmd, "log": str(log_path)}

    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=work["timeout"],
        )
        log_path.write_text(
            f"$ {' '.join(cmd[:2])} …\n[exit {proc.returncode}]\n"
            f"===== STDOUT =====\n{proc.stdout}\n===== STDERR =====\n{proc.stderr}\n"
        )
        return {"item": work["item"], "status": "ok" if proc.returncode == 0 else "err",
                "returncode": proc.returncode, "log": str(log_path)}
    except subprocess.TimeoutExpired:
        log_path.write_text(f"$ {' '.join(cmd[:2])} …\n[TIMEOUT after {work['timeout']}s]\n")
        return {"item": work["item"], "status": "timeout", "log": str(log_path)}
    except FileNotFoundError:
        return {"item": work["item"], "status": "no-hermes",
                "error": "`hermes` CLI not found on PATH"}


def run(
    version: str, *, model: str, testset: Path = TESTSET_DEFAULT, parallel: int = 4,
    repeats: int = 1, tag: Optional[str] = None, timeout: int = 900,
    resume: bool = False, dry_run: bool = False,
) -> str:
    """Run the batch: spawn agents for every (setup × repeat), then audit + report."""
    skill_path = _archived_skill(version)
    setups = load_testset(testset)
    tag = tag or f"{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    done = _completed_counts(tag) if resume else {}
    work: list[dict] = []
    for su in setups:
        already = done.get((su["ticker"], su["date"]), 0)
        for rep in range(repeats):
            if resume and rep < already:
                continue   # this (setup, rep) already finalized under this tag
            work.append({
                "item": f"{su['ticker']}_{su['date']}#r{rep}",
                "ticker": su["ticker"], "date": su["date"], "rep": rep,
                "tag": tag, "model": model, "timeout": timeout, "dry_run": dry_run,
                "prompt": _prompt(version, skill_path, tag, su["ticker"], su["date"]),
            })

    print(f"batch {tag}: version {version}, {len(setups)} setups × {repeats} "
          f"= {len(work)} runs (parallel {parallel}, model {model})"
          f"{' [DRY RUN]' if dry_run else ''}", file=sys.stderr)

    results: list[dict] = []
    if parallel <= 1 or dry_run:
        results = [_run_one(w) for w in work]
    else:
        with _cf.ThreadPoolExecutor(max_workers=parallel) as ex:
            for r in ex.map(_run_one, work):
                results.append(r)
                print(f"  [{r['status']}] {r['item']}", file=sys.stderr)

    if dry_run:
        print(json.dumps(results, indent=2))
        return tag

    n_void = audit(tag)
    print(f"\nbatch {tag} done: {sum(r['status']=='ok' for r in results)}/{len(results)} "
          f"agents ok, {n_void} sessions voided by audit\n", file=sys.stderr)
    _print_batch_report(tag)
    return tag


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


def _transcript_for(session_dir: Path, tag: str) -> Optional[str]:
    """Best-effort: the captured hermes transcript for this session's setup."""
    s = recorder._load_json(session_dir / "session.json", {}) or {}
    ticker, date = s.get("ticker"), s.get("historical_date")
    log_dir = BATCH_LOGS / tag
    if not log_dir.exists():
        return None
    hits = sorted(log_dir.glob(f"{ticker}_{date}_r*.log"))
    return "\n".join(p.read_text(errors="replace") for p in hits) if hits else None


def audit(tag: str) -> int:
    """Scan each session's captured transcript for look-ahead / determinism breaks and
    mark the session ``void`` (with a reason). Returns the number voided.

    A session with no transcript to check is flagged ``void`` too (unverifiable), so
    the report never silently counts an un-auditable run — better a false void than a
    tainted number in the aggregate.
    """
    voided = 0
    for d in _sessions_for_batch(tag):
        session = recorder._load_json(d / "session.json", {}) or {}
        if session.get("status") != "complete":
            continue
        transcript = _transcript_for(d, tag)
        reason = None
        if transcript is None:
            reason = "no transcript captured — unverifiable"
        else:
            for pat in _PEEK_PATTERNS:
                if pat in transcript:
                    reason = f"transcript references forbidden `{pat}`"
                    break
            if reason is None and _REPLAY_RE in transcript:
                reason = "transcript calls replay directly (look-ahead)"
            if reason is None and transcript.count(_STEP_START_RE) > 1:
                reason = "transcript re-ran `step start` (re-seal / look-ahead)"

        if reason:
            session["void"] = reason
            (d / "session.json").write_text(json.dumps(session, indent=2))
            voided += 1
        elif session.pop("void", None) is not None:
            # previously voided, now clean (e.g. transcript re-captured) → clear it
            (d / "session.json").write_text(json.dumps(session, indent=2))
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
