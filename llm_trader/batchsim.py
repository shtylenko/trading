"""Batch backtest harness — run a fixed setup set against a pinned skill version.

The point of skill versioning is to answer "did this rule change actually help?".
This harness answers it: it spawns one **headless `hermes` agent** per
``(setup × repeat)``, each running a single *version-pinned* simulation of the
``TRADE_SIMULATOR`` skill, then aggregates the resulting ``pnl.json`` files into a
profitability report. Because every session is version + batch stamped
(``recorder init --pin-version … --batch …``), comparing two skill versions is just
running the **same setups** against each and diffing the reports.

**AI note**: The harness seals each batch stream in memory and exposes it through a
one-tick gateway only. The agent runs in a macOS sandbox that cannot read prior
simulation artifacts, the market-data layer, or the harness's private process state;
it receives a staging-session path with only the currently revealed stream. The
harness publishes/finalizes that session only after the agent exits. Transcript audit
remains defense in depth. The prompt still defines trading behavior; edits that change
what it is told to do should be treated as skill changes and accompanied by a version
bump (see skills/MAINTAINING.md).

Subcommands
-----------
    build-set   stratified, deterministic sample of setups from entries.db → testset.json
    run         spawn the agents for one skill version, tagged as one batch cohort
    audit       scan agent transcripts; mark any peeking session void (excluded from stats)
    report      thin wrapper over ``recorder report --batch`` for one cohort
    portfolio   chronologically replay sealed deterministic cup-handle fills under shared limits

Design choices (per the harness spec):
- **Local executor model** by default (`--model`) — we measure what actually trades live.
- **Fixed curated holdout** — `build-set` writes a version-controlled set reused every run,
  so version-to-version comparison is apples-to-apples, not confounded by setup luck.
- **Sandboxed agent + post-hoc audit** — the agent runs credential-less against an
  already-sealed session, so the data layer is out of reach. `audit` remains as a
  backstop: it scans each run's captured transcript for any look-ahead (reading
  `_sealed.jsonl`, calling `replay`, re-running `step start`) and voids the session.
"""

from __future__ import annotations

import argparse
import concurrent.futures as _cf
import hashlib
import inspect
import json
import os
import random
import re
import secrets
import signal
import shutil
import sqlite3
import statistics as _statistics
import subprocess
import sys
import tempfile
from math import floor
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from . import recorder, skillmeta, step
from .execution import EXECUTION_MODEL, ExecutionConfig, ExecutionEngine
from .config import DATA_DIR
from .fsutils import atomic_write_json

# Provider API credentials. The harness (this process) holds them so it can seal each
# day and finalize; the *agent* subprocess is spawned WITHOUT them (see _agent_env).
_CRED_ENV_VARS = (
    "ALPACA_API_KEY_ID", "ALPACA_SECRET_KEY", "ALPACA_PAPER", "ALPACA_RPM",
    "FINNHUB_API_KEY", "MARKETDATA_TOKEN",
)
def _agent_env(cache_dir: Path) -> dict:
    """The environment handed to the headless agent: harness env minus provider creds,
    with the marketdata cache redirected to `cache_dir` (a fresh EMPTY dir per run) and
    the provider chain disabled. The agent's ONLY window into price is `step next`
    against the harness-owned one-tick gateway, so that keeps working while any direct
    data-layer access (`replay`, `fetch_bars`) fails.

    Two non-obvious pitfalls, both handled here:
    - Unsetting the cache-dir env vars is NOT enough: marketdata.config falls back to a
      hardcoded default cache (which holds the day's bars), so `replay` would read the
      future from cache. We redirect the cache to an empty dir so every lookup misses.
    - An empty MARKETDATA_PROVIDERS means "all providers" — including yfinance, which
      needs no creds and would happily serve (and cache!) the day's bars. We name a
      sentinel provider that matches nothing, so the chain is empty and no fetch can
      succeed. Using a fresh per-run dir also means a stray cached file can never leak
      the future into a later run."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for k in _CRED_ENV_VARS:
        env.pop(k, None)
    env["STRATEGY_LAB_MARKETDATA_DIR"] = str(cache_dir)
    env["STOCKMARKETDATA_DIR"] = str(cache_dir)
    env["MARKETDATA_PROVIDERS"] = "__none__"   # matches no real provider → empty chain
    env["MARKETDATA_DISABLED"] = "1"           # belt-and-suspenders; documents intent
    return env

# monorepo root — the directory that contains `trading/`, so `import trading` resolves.
REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRIES_DB = DATA_DIR / "entries.db"
# Per-strategy holdouts live under batch/<strategy>/ (committed artifacts, not
# under the gitignored data/ tree). entries.db is regenerable and ignored.
BATCH_ROOT = Path(__file__).parent / "batch"
TESTSET_DEFAULT = BATCH_ROOT / "warrior" / "testset.json"
BATCH_LOGS = recorder.SIM_ROOT / "_batch"   # captured agent transcripts, per cohort
# Default hermes executor when ``run --model`` is omitted (new batches).
DEFAULT_MODEL = "deepseek-v4-flash"


def batch_dir(strategy_id: str = "warrior") -> Path:
    """``llm_trader/batch/<strategy>/`` — testsets for that family only."""
    return BATCH_ROOT / (strategy_id or "warrior").strip().lower().replace("-", "_")


def default_testset_path(strategy_id: str = "warrior") -> Path:
    """Default holdout JSON for a family: ``batch/<strategy>/testset.json``."""
    return batch_dir(strategy_id) / "testset.json"


def resolve_testset_path(
    spec: str | Path | None,
    strategy_id: str = "warrior",
) -> Path:
    """Resolve a ``--set`` argument to an absolute testset path.

    Accepts:
      * ``None`` → ``batch/<strategy>/testset.json``
      * bare name (``testset_30`` / ``testset_30.json``) → under ``batch/<strategy>/``
      * relative path that exists from cwd
      * absolute path

    Strategy folder is always preferred for bare names so callers need not type
    ``trading/llm_trader/batch/cup_handle/…``.
    """
    sid = (strategy_id or "warrior").strip().lower().replace("-", "_")
    family = batch_dir(sid)

    if spec is None or str(spec).strip() == "":
        path = default_testset_path(sid)
        if not path.exists():
            raise SystemExit(
                f"no default testset at {path} — pass --set <name> or run "
                f"`batchsim build-set --strategy {sid} --n 30` first."
            )
        return path.resolve()

    raw = Path(spec)
    candidates: list[Path] = []

    # 1. As given (absolute, or relative to cwd)
    candidates.append(raw)
    # 2. Bare name under the strategy batch folder
    name = raw.name
    candidates.append(family / name)
    if not name.endswith(".json"):
        candidates.append(family / f"{name}.json")
    # 3. Full relative path under package batch root (e.g. cup_handle/testset_30.json)
    if not raw.is_absolute() and len(raw.parts) > 1:
        candidates.append(BATCH_ROOT / raw)

    for c in candidates:
        try:
            if c.is_file():
                return c.resolve()
        except OSError:
            continue

    tried = ", ".join(str(c) for c in candidates)
    available = sorted(p.name for p in family.glob("*.json")) if family.is_dir() else []
    hint = f" Available under {family}: {available}" if available else f" (no *.json in {family})"
    raise SystemExit(
        f"testset not found for strategy={sid!r} --set {spec!r}. Tried: {tried}.{hint}"
    )


def _sandbox_executable() -> Optional[str]:
    """macOS primitive used to deny the agent access to private historical data."""
    return shutil.which("sandbox-exec")


def _sandbox_subpath(path: str | Path) -> str:
    """Return a canonical sandbox profile matcher for ``path``.

    macOS evaluates filesystem paths after resolving ``/var`` → ``/private/var``;
    resolving first prevents a symlink spelling from bypassing a deny rule.
    """
    return f"(subpath {json.dumps(str(Path(path).resolve()))})"


def _write_agent_sandbox(profile_dir: Path, agent_session: Path) -> Path:
    """Write the fail-closed sandbox policy for one batch agent.

    The agent needs the llm_trader code, its disposable staged session, and normal
    network access for the model provider. It must not be able to read any previous
    simulations, the scanner database/cache, or the shared marketdata/lab packages.
    The future stream itself is held only in the batch harness's memory gateway.
    """
    code_root = Path(__file__).resolve().parent
    protected = (
        recorder.SIM_ROOT,
        DATA_DIR,
        REPO_ROOT / "trading" / "marketdata" / "data",
        REPO_ROOT / "trading" / "lab",
    )
    lines = ["(version 1)", "(allow default)"]
    # Disallow source changes too: otherwise a model could patch its local runtime
    # into a data reader. The staging session lives outside code_root and remains
    # writable for `recorder log`.
    lines.append(f"(deny file-write* {_sandbox_subpath(code_root)})")
    for path in protected:
        matcher = _sandbox_subpath(path)
        lines.append(f"(deny file-read-data {matcher})")
        lines.append(f"(deny file-read-metadata {matcher})")
        lines.append(f"(deny file-write* {matcher})")
    # The staged session must be explicit in the profile. It is outside every
    # protected subtree today, but this makes that invariant clear and future-safe.
    session_matcher = _sandbox_subpath(agent_session)
    lines.append(f"(allow file-read-data {session_matcher})")
    lines.append(f"(allow file-read-metadata {session_matcher})")
    lines.append(f"(allow file-write* {session_matcher})")
    profile = profile_dir / "agent.sb"
    profile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return profile


# The audit is a DENYLIST: a run is void only when a command shows a *concrete* look-ahead
# or determinism break. Benign shell the agents wrap around the sanctioned tools — cd,
# env-load, viewer management (lsof/kill), journal writes, `python3 -c` step loops — is NOT
# policed, because none of it can reveal an unrevealed bar. (An earlier allowlist that voided
# any unrecognized command systematically false-voided legitimate runs; agents' benign shell
# is unbounded and can't be enumerated.) The vectors that CAN leak the future, all detected
# below, are: touching the private sealed stream/state, reconstructing bars from the raw
# market-data layer, or re-sealing the day.
# Private per-session files holding the future / cursor. NAMING them in a benign existence
# check (ls / test -f — the setup block's own hygiene step does this) is fine; READING their
# content is the peek. _reads_private_content() distinguishes the two.
_PRIVATE_FILES = ("_sealed.jsonl", "_step.json")
# Direct access to the raw market-data layer — reconstructing bars bypasses step next.
_DATA_LAYER_PATTERNS = ("fetch_bars", "fetch_minute_bars", "trading.marketdata",
                        "marketdata/data", "entries.db")
# Out-of-band network fetch: the sandbox strips provider creds and the private
# cache, but leaves general outbound network up, so a batch agent could still
# `curl` a public price API for the very bars the gateway is protecting. A sealed
# batch agent has no legitimate reason to fetch a URL — its only price window is
# `step next` — so any network-fetch verb or http(s) URL in an executed command
# is a look-ahead vector and voids the run. (Prose is never scanned; see
# ``_parse_export`` — this only sees tool-call action fields.)
_NETWORK_FETCH_RE = re.compile(
    r"\b(?:curl|wget|ncat|telnet|scp|sftp|ftp)\b"
    r"|https?://"
    r"|\brequests\.(?:get|post|request)\b"
    r"|\bhttpx\.(?:get|post)\b"
    r"|\burllib\b|\burlopen\b|\bwebbrowser\b",
    re.I,
)
_REPLAY_RE = "trading.llm_trader.replay"
_STEP_START_RE = "step start"
_STEP_NEXT_RE = "step next"
# commands that READ a file's content (vs ls/test/stat which only name it)
_READ_VERB_RE = re.compile(
    r"\b(?:cat|head|tail|less|more|nl|od|xxd|hexdump|strings|grep|egrep|awk|sed|cut|"
    r"sort|uniq|wc|python|python3|open|read_text|readlines|load)\b")

# The hermes API prints this (and exits 0) when the account has no balance. The agent
# never runs a single tool call, so its session has no command log — which the audit
# would otherwise mis-void as "unverifiable". This is an infrastructure failure, NOT a
# look-ahead: we tag it `out_of_credits` and exclude it from stats instead of voiding.
_OUT_OF_CREDITS_RE = re.compile(
    r"HTTP\s*402|Insufficient\s+Balance|insufficient\s+(?:funds|credits?|balance)", re.I)
_OUT_OF_CREDITS_LABEL = "out of credits (HTTP 402)"
_TIMEOUT_LABEL = "killed after per-setup timeout"
_DEFAULT_RETRIES = 1  # extra attempts on a timeout before giving up (0 = no retry)

# Bump only when the batch-agent contract deliberately changes in a way that source
# hashes alone cannot describe clearly to a reviewer. The hashes below still make an
# unintentional prompt or isolation-harness edit a comparison-breaking change.
RUNNER_CONTRACT_VERSION = "isolated_one_tick_v1"

# recorder.finalize() replays decisions.jsonl through the fill engine and raises
# ValueError if the agent logged an inconsistent sequence (e.g. an EXIT with no
# matching prior ENTER — seen when a model collapses an "armed fill immediately
# followed by a failed-break bailout" same-bar event into a single decision row).
# Left unhandled, the exception left session.json stuck at status "running"
# forever: invisible to stats/audit/resume, indistinguishable from a session that
# is still legitimately in flight. Stamp it instead, same pattern as timeout/ooc.
_FINALIZE_ERROR_LABEL = "finalize failed — inconsistent decision log (see finalize_error)"
_NO_DECISION_LOG_LABEL = "agent produced no decision intents"
_AGENT_ABANDONED_LABEL = (
    "agent stopped logging while still armed or in a position "
    "(must keep step next until flat with no pending entry, STAND_DOWN, or STATUS end)"
)
# Intents that open or keep a multi-day plan live (abandoning after these is incomplete).
_LIVE_PLAN_ACTIONS = frozenset({
    "ARM_BUY_STOP", "ENTER_CLOSE", "ENTER", "SCALE_LIMIT", "SET_STOP",
    "ADD_CLOSE", "EXIT_CLOSE",
})
# Multi-day streams are long (~80 daily bars). Hermes agents often exit mid-arm
# after ~25–30 turns; the harness re-invokes the same SDIR/gateway until the plan
# is terminal or this budget is exhausted.
_DEFAULT_MAX_CONTINUES_MULTI_DAY = 5
_DEFAULT_MAX_CONTINUES_INTRADAY = 0
# Bars immediately before the scanner setup day that the LLM still walks manually
# (plan/arm window). Earlier lookback is harness auto-OBSERVE to cut turn count.
_DEFAULT_MULTI_DAY_LLM_LOOKBACK = 20

# Operator-only skill sections that confuse batch agents (session is already live).
_SKILL_DROP_SECTION_HEADERS = (
    "## Shell / $SDIR discipline",
    "## Step 0 — Init + seal",
    "## Finalize",
    "## Step 0",
)


def _text_out_of_credits(text: Optional[str]) -> bool:
    """True if agent output shows the account ran out of API credits."""
    return bool(text and _OUT_OF_CREDITS_RE.search(text))


def _latest_version() -> str:
    """Return the highest semver key from the skill registry (e.g. '2.0.3')."""
    reg = skillmeta._load_registry(skillmeta.DEFAULT_REGISTRY_PATH)
    versions = reg["versions"]
    if not versions:
        raise RuntimeError(f"no versions in skill registry at {skillmeta.DEFAULT_REGISTRY_PATH}")
    # reuse skillmeta's semver parser (single source of truth); non-numeric tags
    # sort lowest rather than crashing the max().
    return max(versions.keys(), key=lambda v: skillmeta._parse_semver(v) or [0, 0, 0])


# ───────────────────────────── build-set ────────────────────────────────────


def _hhmm_after(t: str, after: str) -> bool:
    return (t or "") >= after


def _load_keys(path: Path) -> set:
    """(ticker, date) keys from an existing testset JSON — for --exclude holdouts."""
    data = json.loads(Path(path).read_text())
    setups = data.get("setups", data) if isinstance(data, dict) else data
    return {(s["ticker"], s["date"]) for s in setups}


def _causal_entry_feature_errors(row: dict) -> list[str]:
    """Return plan-contract errors for a raw scanner row.

    `entries.db` deliberately retains prior research artifacts until their scan
    scope is refreshed.  A cup-handle holdout, however, is an execution input,
    not a research sample: it must contain only the complete causal plans that
    the current scanner can disclose on the setup bar.
    """
    from . import replay

    raw_features = row.get("features_json")
    try:
        features = json.loads(raw_features) if isinstance(raw_features, str) else raw_features
    except json.JSONDecodeError:
        features = {}
    setup = replay.Setup(
        ticker=str(row.get("ticker") or ""),
        day=datetime.fromisoformat(str(row.get("date"))).date(),
        time_et=str(row.get("time_et") or ""),
        entry_px=row.get("entry_px"),
        gap_pct=row.get("gap_pct"),
        rvol=row.get("rvol"),
        float_shares=row.get("float_shares"),
        reason=str(row.get("reason") or ""),
        strategy="cup_handle",
        pattern=str(row.get("pattern") or "cup_handle"),
        features=features if isinstance(features, dict) else {},
    )
    return replay.causal_plan_feature_errors(setup)


def _research_universe_feature(row: dict) -> Optional[dict]:
    """Return validated PIT provenance embedded by ``research_scan``, if any."""
    raw_features = row.get("features_json")
    try:
        features = json.loads(raw_features) if isinstance(raw_features, str) else raw_features
    except json.JSONDecodeError:
        return None
    provenance = features.get("research_universe") if isinstance(features, dict) else None
    if not isinstance(provenance, dict):
        return None
    interval = provenance.get("interval")
    if (
        provenance.get("membership_basis") != "point_in_time"
        or not isinstance(provenance.get("manifest_sha256"), str)
        or not provenance["manifest_sha256"].startswith("sha256:")
        or not isinstance(interval, dict)
    ):
        return None
    required_interval = {"start", "end", "as_of", "source", "symbols_sha256"}
    if not required_interval.issubset(interval):
        return None
    if provenance.get("source_quality", "unqualified") not in {
        "primary_or_licensed", "public_pit_unverified", "unqualified",
    }:
        return None
    return provenance


def research_provenance_for_setups(db: Path, setups: list[dict]) -> dict:
    """Build one immutable PIT-provenance stamp for a selected test set.

    Test sets are validated against scanner rows twice: here, when they are
    created, and again before a cup-handle batch runs.  Both checks reject a
    mixture of different universe manifests so a result cannot accidentally
    combine current-snapshot and historical-PIT scans.
    """
    expected = {
        (str(s.get("ticker") or "").upper(), str(s.get("date") or ""), str(s.get("time_et") or ""))
        for s in setups
    }
    if not expected:
        raise ValueError("cannot stamp research provenance for an empty test set")
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
        if "features_json" not in cols:
            raise ValueError("entries database has no features_json; re-run the PIT research scanner")
        rows = [dict(r) for r in conn.execute("SELECT * FROM entries")]
    by_key = {
        (str(r.get("ticker") or "").upper(), str(r.get("date") or ""), str(r.get("time_et") or "")): r
        for r in rows
    }
    missing: list[str] = []
    provenance_rows: list[dict] = []
    for key in sorted(expected):
        provenance = _research_universe_feature(by_key.get(key, {}))
        if provenance is None:
            missing.append(" ".join(key))
        else:
            provenance_rows.append(provenance)
    if missing:
        preview = ", ".join(missing[:4])
        suffix = f" (+{len(missing) - 4} more)" if len(missing) > 4 else ""
        raise ValueError(
            "selected cup_handle setups lack valid point-in-time universe provenance: "
            f"{preview}{suffix}. Re-run research_scan with a PIT manifest first."
        )

    identities = {
        (
            p.get("manifest_sha256"),
            p.get("manifest_name"),
            p.get("membership_basis"),
            p.get("source_quality", "unqualified"),
        )
        for p in provenance_rows
    }
    if len(identities) != 1:
        raise ValueError(
            "selected cup_handle setups span multiple research universe manifests; "
            "build a holdout from one immutable PIT scan corpus"
        )
    manifest_sha256, manifest_name, membership_basis, source_quality = identities.pop()
    intervals = {
        json.dumps(p["interval"], sort_keys=True, separators=(",", ":"))
        for p in provenance_rows
    }
    return {
        "schema_version": 1,
        "membership_basis": membership_basis,
        "source_quality": source_quality,
        "manifest_name": manifest_name,
        "manifest_sha256": manifest_sha256,
        "intervals": [json.loads(value) for value in sorted(intervals)],
        "setup_count": len(setups),
    }


def build_set(
    n: int = 30, *, seed: int = 13, db: Path = ENTRIES_DB, after: str = "09:30",
    exclude: Optional[set] = None, unique_ticker: bool = False,
    causal_only: bool = False, require_exact: bool = False,
    require_research_provenance: bool = False,
    start_date: Optional[date] = None, end_date: Optional[date] = None,
    all_rows: bool = False,
) -> list[dict]:
    """Stratified, deterministic sample of ~``n`` setups from ``entries.db``.

    Buckets by time-of-day (early/late vs 10:30) × float (low/mid vs 5M) and takes a
    proportional slice from each, so the holdout mirrors the population instead of
    over-weighting whatever is most common. Deterministic given ``seed`` → the same
    set every run, which is what makes version comparison apples-to-apples.
    Deduped to one setup per (ticker, date) so `step start --ticker --date` is
    unambiguous.

    ``exclude`` is a set of ``(ticker, date)`` keys to leave out — pass the dev set's
    keys to carve a **disjoint holdout** (see IMPROVING.md §6 / BACKLOG DX).

    ``unique_ticker`` collapses the pool to **one setup per ticker** (keeping each
    ticker's most-recent date) before sampling, so every setup is a distinct name — max
    cross-ticker diversity, no correlated repeats of the same ticker on different days.

    ``causal_only`` is for execution holdouts of plan-first strategies.  It excludes
    legacy labels and incomplete scanner rows instead of allowing them to turn into
    agent stand-downs or invalid pseudo-results later in the batch.

    ``start_date`` and ``end_date`` bound the setup bar inclusively, allowing an
    immutable chronological development/holdout split. ``all_rows`` returns every
    eligible, deduplicated row in that bounded pool rather than a sample.

    ``require_exact`` makes the request a hard contract.  The CLI enables it so a
    file called ``testset_10`` can never silently contain nine rows because the
    eligible (or unique-ticker) pool was too small.
    """
    if n < 1:
        raise ValueError("testset size n must be positive")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    exclude = exclude or set()
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM entries")]
    rows = [r for r in rows if _hhmm_after(r.get("time_et", ""), after)]
    if start_date is not None:
        rows = [r for r in rows if str(r.get("date") or "") >= start_date.isoformat()]
    if end_date is not None:
        rows = [r for r in rows if str(r.get("date") or "") <= end_date.isoformat()]
    if causal_only:
        rows = [r for r in rows if not _causal_entry_feature_errors(r)]
    if require_research_provenance:
        rows = [r for r in rows if _research_universe_feature(r) is not None]

    # dedupe to one per (ticker, date), skipping excluded keys
    seen: dict[tuple, dict] = {}
    for r in rows:
        key = (r["ticker"], r["date"])
        if key in exclude:
            continue
        seen.setdefault(key, r)
    rows = list(seen.values())

    if unique_ticker:
        # Collapse to one row per ticker, preferring the most RECENT date — keeps the
        # set in the latest era where possible; a ticker seen only in an earlier period
        # contributes that earlier date. Result: every setup is a distinct ticker.
        by_ticker: dict[str, dict] = {}
        for r in rows:
            cur = by_ticker.get(r["ticker"])
            if cur is None or (r.get("date") or "") > (cur.get("date") or ""):
                by_ticker[r["ticker"]] = r
        rows = list(by_ticker.values())

    if require_exact and not all_rows and len(rows) < n:
        scope = "unique tickers" if unique_ticker else "eligible setup rows"
        raise ValueError(
            f"requested {n} setup(s), but only {len(rows)} {scope} are available "
            "after filters; expand the scan universe or request fewer setups"
        )

    def bucket(r: dict) -> tuple:
        tb = "early" if (r.get("time_et") or "") < "10:30" else "late"
        fb = "lowfloat" if (r.get("float_shares") or 0) < 5e6 else "midfloat"
        return (tb, fb)

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[bucket(r)].append(r)

    rng = random.Random(seed)
    total = len(rows)
    wanted = total if all_rows else min(n, total)
    shuffled_groups: dict[tuple, list[dict]] = {}
    quotas: dict[tuple, int] = {}
    remainders: dict[tuple, float] = {}
    for key in sorted(groups):
        grp = sorted(groups[key], key=lambda r: (r["ticker"], r["date"]))
        rng.shuffle(grp)
        shuffled_groups[key] = grp
        exact = wanted * len(grp) / total if total else 0.0
        quotas[key] = floor(exact)
        remainders[key] = exact - quotas[key]

    # Largest-remainder apportionment preserves the stratified mix *and* makes
    # the requested count exact whenever the pool is large enough.  The previous
    # independent round() allocation could sum to n-1 (the testset_10 failure).
    remaining = wanted - sum(quotas.values())
    for key in sorted(quotas, key=lambda k: (-remainders[k], k)):
        if remaining <= 0:
            break
        quotas[key] += 1
        remaining -= 1
    picks = [row for key in sorted(shuffled_groups) for row in shuffled_groups[key][:quotas[key]]]
    rng.shuffle(picks)
    return [
        {
            "ticker": r["ticker"], "date": r["date"], "time_et": r.get("time_et"),
            "pattern": r.get("pattern"), "float_shares": r.get("float_shares"),
            "gap_pct": r.get("gap_pct"),
        }
        for r in sorted(picks, key=lambda r: (r["ticker"], r["date"]))
    ]


def write_testset(
    setups: list[dict],
    out: Path,
    seed: int,
    *,
    research_provenance: Optional[dict] = None,
    cohort: Optional[dict] = None,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "n": len(setups),
        "setups": setups,
    }
    if research_provenance is not None:
        doc["research_provenance"] = research_provenance
    if cohort is not None:
        doc["cohort"] = cohort
    out.write_text(json.dumps(doc, indent=2) + "\n")


def load_testset(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    return data.get("setups", data) if isinstance(data, dict) else data


def _cup_handle_testset_research_provenance(path: Path, setups: list[dict]) -> dict:
    """Fail closed unless a cup-handle holdout is bound to one PIT manifest."""
    data = json.loads(Path(path).read_text())
    provenance = data.get("research_provenance") if isinstance(data, dict) else None
    if not isinstance(provenance, dict):
        raise ValueError(
            "cup_handle batch testset lacks research_provenance. Rebuild it from a "
            "point-in-time research scan; legacy/current-universe cohorts remain "
            "readable but are not promotion-eligible."
        )
    if provenance.get("membership_basis") != "point_in_time":
        raise ValueError("cup_handle batch testset is not backed by point-in-time membership")
    manifest_hash = provenance.get("manifest_sha256")
    if not isinstance(manifest_hash, str) or not manifest_hash.startswith("sha256:"):
        raise ValueError("cup_handle batch testset has no valid universe manifest hash")
    if provenance.get("setup_count") != len(setups):
        raise ValueError(
            "cup_handle batch testset research provenance setup_count does not match its setups"
        )
    if not isinstance(provenance.get("intervals"), list) or not provenance["intervals"]:
        raise ValueError("cup_handle batch testset research provenance has no interval evidence")
    if provenance.get("source_quality", "unqualified") not in {
        "primary_or_licensed", "public_pit_unverified", "unqualified",
    }:
        raise ValueError("cup_handle batch testset has an unknown universe source_quality")
    return provenance


def _cup_handle_research_tier(
    path: Path,
    setups: list[dict],
    *,
    exploratory: bool,
) -> tuple[dict, str]:
    """Return testset provenance plus an explicit promotion-eligibility tier.

    The normal path never accepts an unproven universe.  ``--exploratory`` is a
    deliberate escape hatch for fast deterministic *diagnostics* over legacy or
    current-snapshot data; it stamps the batch as non-promotable and the compare
    gate refuses to treat it as validation evidence.
    """
    try:
        provenance = _cup_handle_testset_research_provenance(path, setups)
        source_quality = provenance.get("source_quality", "unqualified")
        if source_quality == "primary_or_licensed":
            return provenance, "promotion_eligible"
        # A dated public snapshot is useful research evidence, but without a
        # licensed/primary membership feed it must not silently pass the final
        # promotion gate.  Keep it distinct from legacy exploratory scans: it
        # remains reproducible PIT validation, just not final validation.
        if source_quality == "public_pit_unverified":
            return provenance, "pit_public_validation_only"
        raise ValueError(
            "cup_handle batch testset has unqualified universe provenance; "
            "use a declared public PIT source or --exploratory"
        )
    except ValueError as exc:
        if not exploratory:
            raise
        return {
            "schema_version": 1,
            "membership_basis": "unverified_exploratory",
            "promotion_eligible": False,
            "reason": str(exc),
            "setup_count": len(setups),
        }, "exploratory"


# ───────────────────────────── run ──────────────────────────────────────────


def _strategy_paths(strategy_id: str = "warrior"):
    """Return (registry_path, trade_skills_dir, default_entries_db) for a family."""
    from .strategies import get_strategy

    s = get_strategy(strategy_id or "warrior")
    return s.registry_path(), s.trade_skills_dir(), s.default_db_path(), s


def _archived_skill(version: str, strategy_id: str = "warrior") -> Path:
    _, trade_skills_dir, _, _ = _strategy_paths(strategy_id)
    p = skillmeta.skill_path_for(version, trade_skills_dir)
    if not p.exists():
        raise FileNotFoundError(
            f"no skill file for version {version} at {p}. Create one with "
            f"`batchsim new-version --strategy {strategy_id} --from <existing> --to "
            f"{version}`."
        )
    return p


def _skill_text_for_batch_agent(skill_text: str) -> str:
    """Drop operator/init/finalize sections that batch agents must not re-run.

    Batch hermes sessions are already init+sealed; shell tutorials waste context and
    encourage re-init (look-ahead / void). Keep checklists, actions, and manage rules.
    """
    text = skill_text or ""
    # Drop the "Run from monorepo root / .env" operator block (often before Step 0).
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    skip_until_header = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if any(stripped.startswith(h) or stripped == h for h in _SKILL_DROP_SECTION_HEADERS):
                skipping = True
                skip_until_header = True
                continue
            if skip_until_header:
                skipping = False
                skip_until_header = False
        if skipping:
            continue
        # Drop standalone env-load / import-check operator blurbs.
        if stripped.startswith("Run from the **monorepo root**") or stripped.startswith(
            "Run from the monorepo root"
        ):
            skipping = True
            skip_until_header = True
            continue
        if skipping and stripped.startswith("```"):
            # skip fenced block after env blurb — handled by section drop usually
            pass
        out.append(line)
    cleaned = "".join(out)
    # Collapse excessive blank lines after drops.
    while "\n\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n\n", "\n\n\n")
    return cleaned.strip() + "\n"


def _auto_observe_multi_day_lookback(
    sdir: Path,
    gateway: "step.IsolatedStreamGateway",
    setup_date: str,
    *,
    llm_lookback: int = _DEFAULT_MULTI_DAY_LLM_LOOKBACK,
) -> dict:
    """Harness-advance early lookback bars with OBSERVE so the LLM starts nearer setup.

    Leaves the last ``llm_lookback`` bars before the setup day (and everything after)
    for the agent to plan/arm/manage. Returns summary stats for the prompt.
    """
    import io

    sdir = Path(sdir)
    setup_i = gateway.setup_bar_index(setup_date)
    first_llm_i = max(0, int(setup_i) - int(llm_lookback))
    n_auto = 0
    # Reveal+log until the next tick to reveal is first_llm_i.
    while gateway.revealed_tick_count() < first_llm_i:
        buf = io.StringIO()
        rc = step.next_(sdir, out=buf)
        if rc != 0:
            break
        # Last revealed tick is the one we must log.
        meta, ticks, _end = recorder._parse_stream(sdir / "stream.jsonl")
        if not ticks:
            break
        tick = ticks[-1]
        i = int(tick["i"])
        hhmm = tick.get("time") or "16:00"
        date_s = tick.get("date") or ""
        recorder.log(sdir, {
            "i": i,
            "time": hhmm if len(str(hhmm)) == 5 else "16:00",
            "action": "OBSERVE",
            "thought": (
                f"harness auto-observe lookback i={i} date={date_s} "
                f"(LLM window starts at i={first_llm_i}; setup_i={setup_i})"
            ),
        })
        n_auto += 1
    return {
        "n_auto_observe": n_auto,
        "first_llm_i": first_llm_i,
        "setup_i": setup_i,
        "llm_lookback": int(llm_lookback),
    }


def _prompt(version: str, skill_text: str, tag: str, session_id: str,
            ticker: str, date: str, time_et: Optional[str], sdir: str,
            max_reentries: int = 1, trade_until: Optional[str] = None,
            execution_model: str = "reported_fill_v1",
            session_from_open: bool = False,
            horizon: str = "intraday",
            bar_resolution: str = "1min",
            auto_lookback: Optional[dict] = None,
            engine_owned_targets: bool = False) -> str:
    """The per-setup task handed to a headless hermes agent.

    The harness has ALREADY created the session and holds the sealed day in a private
    in-memory one-tick gateway. The agent receives only a disposable staged SDIR; it
    never runs init/start/finalize — its whole job is reveal a bar, decide, log, repeat.
    The macOS sandbox blocks prior simulations and the market-data layer, while the
    gateway cannot serve arbitrary/future bars. The agent is also spawned WITHOUT
    market-data credentials (see _agent_env), so `replay`/`fetch` fail outright.

    Command lines are NOT indented (leading whitespace on `\\`-continued lines would be
    passed to the agent verbatim)."""
    multi_day = (horizon or "").lower() in ("multi_day", "multiday", "swing") or (
        bar_resolution or ""
    ).lower() in ("1day", "daily")
    skill_for_agent = _skill_text_for_batch_agent(skill_text)
    auto_lb = auto_lookback or {}
    position_actions = "SCALE_LIMIT / " if not engine_owned_targets else ""
    # The early-stop rule (condition b) is set by the run's §C re-entry BUDGET
    # (max_reentries) and an optional cutoff time (trade_until). Budget 1 + no cutoff
    # reproduces the classic single-re-entry behaviour exactly.
    if multi_day:
        # Daily bars all print time "16:00" — NEVER use clock-of-day cutoffs here.
        auto_note = ""
        if auto_lb.get("n_auto_observe"):
            auto_note = (
                f" Early lookback bars i=0..{int(auto_lb['first_llm_i']) - 1} were already "
                f"revealed and logged as OBSERVE by the harness "
                f"({auto_lb['n_auto_observe']} bars); your first `step next` continues at "
                f"i≈{auto_lb['first_llm_i']} (setup day i={auto_lb.get('setup_i')}). "
            )
        done_rule = (
            "This is a MULTI-DAY swing run (one bar = one trading day; time is usually 16:00). "
            "Do NOT stop because the clock says after 11:00 — that rule is for intraday only. "
            + auto_note
            + "NEVER stop merely because you are flat: a live ARM_BUY_STOP / pending buy-stop "
            "means you are NOT done — keep `step next` + `resolve` + log every bar until "
            "the order fills, you CANCEL_ENTRY, or the stream ends. "
            "While IN a position, keep going every bar ("
            + position_actions
            + "SET_STOP / "
            + "OBSERVE / "
            "EXIT as the skill requires) until `resolve` shows flat. "
            "You may stop ONLY when ALL of these are true: "
            "(1) no open position, AND "
            "(2) no pending entry order (you never armed, or you cancelled, or it filled and "
            "you later flattened), AND "
            "(3) either you logged STAND_DOWN for a terminal invalidation, OR you finished "
            "the plan after a round-trip and will not re-enter, OR `step next` prints STATUS end. "
            "You must at least reach the scanner setup date before standing down for "
            "'no setup'. "
            "The scanner setup date is NOT a wait-to-arm clock: if the ENTRY checklist "
            "passes, ARM_BUY_STOP (or ENTER_CLOSE only when the skill's breakout quality "
            "gates pass) immediately. "
            "ARM_BUY_STOP only fills on later bars. "
            "Abandoning the loop after ARM while still waiting for a fill is a FAILED run."
        )
    elif session_from_open:
        done_rule = (
            "This is a from-open discovery run. While flat, keep revealing bars through 11:00 ET; "
            "a valid completed 5-minute entry may still form. After 11:00 ET, if flat with no "
            "pending order, stop."
        )
    elif max_reentries <= 0:
        done_rule = (
            "RE-ENTRY IS DISABLED for this run (budget 0), so being flat means you are done — "
            "stop immediately. Do NOT take any §C re-entry and do NOT keep revealing bars."
        )
    else:
        cutoff = (
            f", OR the clock has reached {trade_until} ET (take NO new or re-entry at/after "
            f"{trade_until} ET — a flat position then ends the run)"
            if trade_until else ""
        )
        keep_going = f" and it is before {trade_until} ET" if trade_until else ""
        stop_when = "the budget is spent" + (f" or {trade_until} ET has passed" if trade_until else "")
        done_rule = (
            f"you have used your entire §C re-entry BUDGET of {max_reentries} "
            f"(track `re_entries_used`){cutoff}. IMPORTANT: while you are flat with re-entries "
            f"remaining{keep_going}, do NOT stop — keep revealing bars and watch for the next "
            "qualifying §C re-entry (respect the mandatory 3-bar cooldown and the full setup "
            f"gate; each re-entry must stand on its own merits). Only stop once {stop_when}."
        )
    if execution_model == EXECUTION_MODEL:
        actions = "OBSERVE|ENTER_CLOSE|ARM_BUY_STOP|CANCEL_ENTRY|SET_STOP|ADD_CLOSE|EXIT_CLOSE|STAND_DOWN"
        if not engine_owned_targets:
            actions = actions.replace("|SET_STOP", "|SET_STOP|SCALE_LIMIT")
        loop_commands = f'''1. Reveal the next bar:
python3 -m trading.llm_trader.step next --session "{sdir}"

2. Resolve all orders that were active before that exact revealed tick (after EVERY tick):
python3 -m trading.llm_trader.recorder resolve --session "{sdir}" --i <i>

3. Log ONE intent for the revealed bar. Never send a fill price or share count:
python3 -m trading.llm_trader.recorder log --session "{sdir}" --record '{{"i":<i>,"time":"<HH:MM>","thought":"...","action":"{actions}","note":"..."}}'

Repeat 1→2→3.'''
    else:
        loop_commands = f'''1. Reveal the next bar:
python3 -m trading.llm_trader.step next --session "{sdir}"

2. Log your decision for the bar you just saw (after EVERY bar):
python3 -m trading.llm_trader.recorder log --session "{sdir}" --record '{{"i":<i>,"time":"<HH:MM>","thought":"...","action":"OBSERVE|ENTER|...","fill_px":null,"shares_delta":null,"stop":null,"note":"..."}}'

Repeat 1→2.'''

    if session_from_open and multi_day:
        setup_line = (
            f"Setup to trade (scanner-selected ticker/date): ticker={ticker}  date={date}. "
            f"The date is the setup reference day in a multi-day daily stream. "
            f"Arm when the skill checklist passes — do not wait for that calendar day."
        )
    elif session_from_open:
        setup_line = f"Setup to trade (scanner-selected ticker/date only): ticker={ticker}  date={date}"
    else:
        setup_line = (
            f"Setup to trade (do NOT choose your own): ticker={ticker}  date={date}  time={time_et}"
        )
    return f"""You are executing ONE trade simulation as an automated backtest.

Trading rules (runtime contract only — session is already live; do NOT init/start/finalize):

===== BEGIN TRADE_SIMULATOR SKILL (v{version}) =====
{skill_for_agent}
===== END TRADE_SIMULATOR SKILL =====

{setup_line}
Batch tag: {tag}   Session ID: {session_id}   pinned skill version: {version}

=== SESSION (already set up) ===
SDIR="{sdir}"
Do NOT run recorder init, step start, or recorder finalize.
Your ONLY price window is `step next` (one bar per call). No replay/fetch/marketdata.

=== LOOP (only commands) ===
{loop_commands}

=== STOP when ===
  (a) `step next` prints `STATUS end`, OR
  (b) you are truly DONE — {done_rule}

Then print exactly: BATCHSIM_SID={sdir}
NEVER print BATCHSIM_SID while ARMED or IN a position.
NEVER exit with a "progress report / need more turns".

=== VOID if you ===
- call replay / fetch_bars / marketdata, or open `_sealed.jsonl` / `_step.json`
- re-init / re-seal / finalize yourself
- invent recovery paths when a command fails (fail closed instead)
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


def _summarize_session(sid: Optional[str]) -> str:
    """Compact one-line summary of whether a position was initiated plus entry/exit counts+details."""
    if not sid:
        return ""
    sdir = recorder.SIM_ROOT / sid
    acts = recorder._load_json(sdir / "actions.json", []) or []
    if not isinstance(acts, list):
        acts = []
    enters = [a for a in acts if a.get("action") == "ENTER"]
    adds = [a for a in acts if a.get("action") == "ADD"]
    exits = [a for a in acts if a.get("action") in ("SCALE", "EXIT")]
    initiated = bool(enters)
    n_ent = len(enters) + len(adds)
    n_ex = len(exits)
    parts = [
        f"initiated={'yes' if initiated else 'no'}",
        f"entries={n_ent}",
        f"exits={n_ex}",
    ]
    # brief event list (time + action + price)
    evs = []
    for a in enters + adds:
        evs.append(f"{a.get('time','?')}:{a['action']}@{a.get('price','?')}")
    for a in exits:
        evs.append(f"{a.get('time','?')}:{a['action']}@{a.get('price','?')}")
    if evs:
        parts.append(" ".join(evs))
    return "    " + "  ".join(parts)


def _completed_counts(tag: str) -> dict[tuple, int]:
    """(ticker, date) → number of **clean** finalized sessions for this batch.

    Voided, out-of-credits and timed-out sessions do NOT count as done, so ``--resume``
    re-runs a setup whose only prior attempt was audit-voided, died on HTTP 402 (out of
    credits), or was killed at the timeout — instead of leaving a tainted or incomplete
    cohort."""
    counts: dict[tuple, int] = defaultdict(int)
    for d in _sessions_for_batch(tag):
        s = recorder._load_json(d / "session.json", {}) or {}
        if (s.get("status") == "complete"
                and not s.get("void") and not s.get("out_of_credits")
                and not s.get("timed_out") and not s.get("finalize_error")
                and not s.get("no_decision_log")
                and not s.get("agent_abandoned")):
            counts[(s.get("ticker"), s.get("historical_date"))] += 1
    return counts


def _manifest_path(tag: str) -> Path:
    return BATCH_LOGS / tag / "manifest.jsonl"


def _load_manifest(tag: str) -> list[dict]:
    p = _manifest_path(tag)
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except (json.JSONDecodeError, TypeError):
            pass  # tolerate a partially written manifest line
    return out


def _preseal(work: dict, skill_path: Path, version: str, session_id: str) -> tuple[Path, step.IsolatedStreamGateway]:
    """Create a staged session and hold its complete day behind an in-memory gateway.

    The staged directory is deliberately outside ``SIM_ROOT``: the sandboxed agent can
    write decisions there, but cannot read any historical simulation tree. The gateway
    exposes only one sequential tick and the full stream is published after the agent
    exits, immediately before harness-side finalization and promotion into ``SIM_ROOT``.
    """
    staging_root = Path(tempfile.mkdtemp(prefix="llm-trader-agent-session-"))
    strategy_id = work.get("strategy") or "warrior"
    profile = work.get("profile") or ("swing" if strategy_id != "warrior" else "small")
    try:
        sdir = recorder.init(
            work["ticker"], work["date"], profile=profile, skill=skill_path,
            pin_version=version, batch=work["tag"], session=session_id,
            runner_contract=work["runner_contract"],
            strategy=strategy_id,
            root=staging_root,
        )
        gateway = step.start_isolated(
            sdir, ticker=work["ticker"], date=work["date"], at_time=work.get("time_et"),
            from_open=work.get("session_from_open", False),
            neutral_meta=work.get("session_from_open", False),
            five_minute_context=work.get("five_minute_context", False),
            db=work.get("db") or ENTRIES_DB,
            strategy=strategy_id,
        )
        # Multi-day: harness auto-OBSERVEs deep lookback so the agent starts nearer
        # the plan/arm window (cuts ~20–40 LLM turns of pure narration).
        multi_day = bool(work.get("multi_day"))
        if multi_day and not work.get("decision_policy"):
            llm_lb = int(work.get("llm_lookback", _DEFAULT_MULTI_DAY_LLM_LOOKBACK))
            work["auto_lookback"] = _auto_observe_multi_day_lookback(
                sdir, gateway, work["date"], llm_lookback=llm_lb,
            )
        return sdir, gateway
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _promote_staged_session(sdir: Path) -> Path:
    """Move a finalized staged leaf into the durable simulations tree."""
    sdir = Path(sdir)
    if sdir.parent == recorder.SIM_ROOT:
        return sdir
    destination = recorder.SIM_ROOT / sdir.name
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing session {destination}")
    recorder.SIM_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.move(str(sdir), str(destination))
    try:
        sdir.parent.rmdir()  # the per-agent staging root should now be empty
    except OSError:
        pass
    return destination


def _continue_prompt(
    base_prompt: str,
    sdir: str | Path,
    reason: str,
    continue_n: int,
    max_continues: int,
) -> str:
    """Prompt for a re-invoked hermes agent on the same staged SDIR / gateway."""
    header = f"""===== HARNESS CONTINUE ({continue_n}/{max_continues}) =====
A previous agent session exited while the trading plan was STILL LIVE:
  {reason}

You are RESUMING the same session. Session path (unchanged):
  SDIR="{sdir}"

Rules for this continue:
1. Do NOT run init / step start / finalize. The session is already sealed and live.
2. Immediately resume the loop: step next → resolve → log, every bar.
3. Do NOT write a "progress report" / "in progress" / "need more turns" and exit.
4. Do NOT print BATCHSIM_SID until you are truly done (flat, no pending entry,
   STAND_DOWN, or STATUS end). Printing it while ARMED or IN a position fails the run.
5. Keep going until the plan is terminal — the harness will re-invoke you again if
   you stop early, but you should finish in this session if you can.

===== END CONTINUE — original task follows =====

"""
    return header + base_prompt


def _live_plan_state(sdir: Path) -> Optional[str]:
    """If the revealed stream still has an open position or pending arm, return why."""
    sdir = Path(sdir)
    session = recorder._load_json(sdir / "session.json", {}) or {}
    stream = sdir / "stream.jsonl"
    if not stream.exists():
        return None
    try:
        meta, ticks, end = recorder._parse_stream(stream)
    except Exception:  # noqa: BLE001
        return None
    if meta is None or not ticks:
        return None
    try:
        decisions = recorder._read_jsonl(sdir / "decisions.jsonl")
    except Exception:  # noqa: BLE001
        decisions = []
    bars = recorder._build_bars(meta, ticks)
    if not bars:
        return None
    config = session.get("config", {}) or {}
    if config.get("execution_model") == EXECUTION_MODEL:
        from .execution import ExecutionConfig, ExecutionEngine
        engine = ExecutionEngine(ExecutionConfig.from_session_config(config))
        engine.run(bars, decisions, force_close=False)
        snap = engine.snapshot()
        if snap.get("position_shares"):
            return f"open position {snap['position_shares']} sh (stop={snap.get('stop')})"
        armed = snap.get("armed_entry")
        if armed:
            return f"pending ARM_BUY_STOP trigger={armed.get('trigger')} stop={armed.get('stop')}"
        return None
    # Legacy reported-fill: heuristic from intents only.
    actions = {str(d.get("action") or "") for d in decisions}
    last = max(decisions, key=lambda d: int(d.get("i", -1))) if decisions else None
    if last and str(last.get("action")) == "STAND_DOWN":
        return None
    if "ARM_BUY_STOP" in actions and "ENTER" not in actions and "EXIT" not in actions:
        if last and str(last.get("action")) != "CANCEL_ENTRY":
            return "pending ARM_BUY_STOP (legacy)"
    return None


def _agent_needs_continue(
    sdir: Path,
    gateway: "step.IsolatedStreamGateway",
    *,
    multi_day: bool,
) -> Optional[str]:
    """Return a reason to re-invoke hermes, or None if the agent may stop.

    Called *before* gateway.publish so only revealed bars are considered for
    live-plan state; unrevealed ticks are detected via the gateway cursor.
    """
    sdir = Path(sdir)
    try:
        remaining = gateway.remaining_ticks()
    except Exception:  # noqa: BLE001
        remaining = 0
    if remaining <= 0:
        return None

    try:
        raw = [
            json.loads(ln) for ln in (sdir / "decisions.jsonl").read_text().splitlines()
            if ln.strip()
        ]
    except (OSError, json.JSONDecodeError):
        raw = []

    last_action = str(raw[-1].get("action") or "") if raw else ""
    if last_action == "STAND_DOWN":
        return None

    live = _live_plan_state(sdir)
    if live:
        return f"{live}; {remaining} sealed bar(s) still unrevealed"

    if not multi_day:
        return None

    # Multi-day: still more sealed days and no terminal stand-down. If a plan was
    # never engaged, the agent must keep walking lookback to the setup day / end.
    # If a plan engaged and is now flat with no pending orders, allow stop even
    # with hold bars remaining (skill allows ending after a completed round-trip).
    actions_used = {str(d.get("action") or "") for d in raw}
    if actions_used & _LIVE_PLAN_ACTIONS:
        # Live plan intents exist but engine says flat+unarmed → round-trip done
        # (or cancelled). Do not force walking the rest of the hold window.
        return None
    # Pure OBSERVE walk mid-stream — keep going (do not abort mid-lookback).
    return f"multi-day stream incomplete ({remaining} bar(s) unrevealed; last={last_action or 'none'})"


def _run_one(work: dict) -> dict:
    """Spawn one headless hermes agent for a single (setup, repeat) whose session was
    ALREADY pre-sealed by the harness (work['sdir']). The agent runs the trading loop
    only (step next + recorder log); this function then finalizes the run harness-side
    (the agent has no data creds and cannot). The session id is known up front (the
    sdir name), so the audit no longer depends on parsing it from agent output.

    Multi-day: if the agent exits while still armed / in position (or mid-lookback),
    the harness re-invokes hermes on the **same** SDIR + gateway with a CONTINUE
    prompt until the plan is terminal or ``max_continues`` is exhausted.
    """
    log_dir = BATCH_LOGS / work["tag"]
    log_dir.mkdir(parents=True, exist_ok=True)
    name = work["session_name"]
    log_path = log_dir / f"{name}.log"

    if work.get("dry_run"):
        cmd = ["hermes", "-z", work["prompt"], "--yolo", "-m", work["model"]]
        return {"item": work["item"], "status": "dry-run", "cmd": cmd,
                "session_name": name, "sid": None}

    sdir = Path(work["sdir"])
    sid = sdir.name
    gateway: step.IsolatedStreamGateway = work["gateway"]
    multi_day = bool(work.get("multi_day"))
    if "multi_day" not in work:
        hz = str(work.get("horizon") or "").lower()
        br = str(work.get("bar_resolution") or "").lower()
        multi_day = hz in ("multi_day", "multiday", "swing") or br in ("1day", "daily")
    max_continues = int(work.get(
        "max_continues",
        _DEFAULT_MAX_CONTINUES_MULTI_DAY if multi_day else _DEFAULT_MAX_CONTINUES_INTRADAY,
    ))
    base_prompt = work["prompt"]
    continues_used = 0
    log_chunks: list[str] = []

    def _result(status: str, **extra) -> dict:
        # The agent can only see incrementally revealed bars. Once it exits, publish
        # the full stream, finalize in the harness, and only then promote the staged
        # artifact into the durable simulations tree.
        final_sdir = sdir
        try:
            gateway.publish()
            recorder.finalize(sdir)
            if _has_no_decision_log(sdir):
                _stamp_no_decision_log(sdir)
                status = "no-decisions"
            else:
                abandoned = _agent_abandoned_stream(sdir)
                if abandoned:
                    _stamp_agent_abandoned(sdir, abandoned)
                    status = "agent-abandoned"
        except Exception as e:  # noqa: BLE001 — never let finalize sink the batch
            # finalize() raised BEFORE writing session.json, so status is still
            # whatever it was pre-run ("running") — stamp it directly so the leaf
            # is visibly broken (not mistaken for a still-live session) and
            # excluded/re-run like any other infra failure, instead of silently
            # vanishing with only an in-memory (never-persisted) error string.
            extra["finalize_error"] = str(e)
            status = "finalize-error"
            _stamp_finalize_error(sdir, str(e))
        finally:
            # ``publish`` normally closes the gateway itself. On an integrity or
            # finalization error, close it here too so an abandoned staged session
            # never leaves a live endpoint holding the sealed day in memory.
            gateway.close()
        try:
            final_sdir = _promote_staged_session(sdir)
        except Exception as e:  # noqa: BLE001 — a result outside SIM_ROOT is unusable
            extra["promotion_error"] = str(e)
            status = "promotion-error"
        if status == "out-of-credits":
            # Stamp the session so the audit / viewer treat it as an infra failure
            # (excluded from stats) rather than a look-ahead void. Done after finalize,
            # which rewrites session.json.
            _stamp_out_of_credits(final_sdir)
        elif status == "timeout":
            # Same idea for a killed-on-timeout run: stamp it so it is never a clean
            # "complete no-trade" — excluded from stats and re-run by --resume.
            _stamp_timeout(final_sdir)
        base = {"item": work["item"], "session_name": name, "sid": sid,
                "ticker": work["ticker"], "date": work["date"], "rep": work["rep"],
                "status": status, "continues_used": continues_used}
        base.update(extra)
        return base

    def _attempt(prompt_text: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """One agent run. Returns (stdout, stderr, returncode); (None, None, None) on
        timeout (process killed)."""
        cmd = ["hermes", "-z", prompt_text, "--yolo", "-m", work["model"]]
        # Fresh empty marketdata cache per agent so a stray cached bar can never leak
        # the future into another run; auto-removed when the agent exits.
        with tempfile.TemporaryDirectory(prefix="batchsim-nomd-") as nomd:
            sandbox = _sandbox_executable()
            if sandbox is None:
                raise RuntimeError("sandbox-exec is required for isolated batch runs")
            profile = _write_agent_sandbox(Path(nomd), sdir)
            sandboxed_cmd = [sandbox, "-f", str(profile), *cmd]
            with subprocess.Popen(
                sandboxed_cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True, env=_agent_env(Path(nomd)),
            ) as proc:
                try:
                    stdout, stderr = proc.communicate(timeout=work["timeout"])
                    return stdout, stderr, proc.returncode
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        proc.kill()
                    proc.wait()
                    return None, None, None

    def _run_with_timeout_retries(prompt_text: str, label: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """Run hermes; retry pure timeouts. Returns (stdout, stderr, rc) or
        (None, None, None) if every attempt timed out."""
        retries = work.get("retries", _DEFAULT_RETRIES)
        for attempt in range(retries + 1):
            stdout, stderr, rc = _attempt(prompt_text)
            if rc is not None:
                return stdout, stderr, rc
            if attempt < retries:
                log_chunks.append(
                    f"[{label} TIMEOUT after {work['timeout']}s] attempt {attempt + 1}/"
                    f"{retries + 1} — retrying\n"
                )
        log_chunks.append(
            f"[{label} TIMEOUT after {work['timeout']}s] gave up after {retries + 1} attempt(s)\n"
        )
        return None, None, None

    try:
        # A timeout is an infra hiccup (slow API / a hung turn), not a trading result, so
        # retry it a few times before giving up. Each attempt re-seals nothing — the same
        # pre-sealed SDIR is reused, so no look-ahead risk. Only a persistent timeout is
        # recorded as a (stamped, re-runnable) failure — never a clean "complete".
        prompt_text = base_prompt
        last_rc: Optional[int] = None
        while True:
            label = "initial" if continues_used == 0 else f"continue-{continues_used}"
            stdout, stderr, rc = _run_with_timeout_retries(prompt_text, label)
            if rc is None:
                log_path.write_text("".join(log_chunks))
                return _result("timeout", attempts=work.get("retries", _DEFAULT_RETRIES) + 1)

            last_rc = rc
            log_chunks.append(
                f"===== {label} exit {rc} =====\n"
                f"===== STDOUT =====\n{stdout}\n===== STDERR =====\n{stderr}\n"
            )
            if _text_out_of_credits(f"{stdout}\n{stderr}"):
                log_path.write_text("".join(log_chunks))
                return _result("out-of-credits", returncode=rc, log=str(log_path))

            # Re-invoke while the plan is still live and sealed bars remain.
            need = _agent_needs_continue(sdir, gateway, multi_day=multi_day)
            if not need or continues_used >= max_continues:
                if need and continues_used >= max_continues:
                    log_chunks.append(
                        f"[continue-budget] still live after {continues_used} continue(s): {need}\n"
                    )
                break
            continues_used += 1
            log_chunks.append(f"[continue] re-invoking hermes ({continues_used}/{max_continues}): {need}\n")
            prompt_text = _continue_prompt(
                base_prompt, sdir, need, continues_used, max_continues,
            )

        log_path.write_text("".join(log_chunks))
        return _result(
            "ok" if last_rc == 0 else "err",
            returncode=last_rc,
            log=str(log_path),
            continues_used=continues_used,
        )
    except FileNotFoundError:
        if log_chunks:
            log_path.write_text("".join(log_chunks))
        return _result("no-hermes", error="`hermes` CLI not found on PATH")
    except RuntimeError as e:
        if log_chunks:
            log_path.write_text("".join(log_chunks))
        return _result("isolation-error", error=str(e))


def _run_policy_one(work: dict) -> dict:
    """Execute one sealed deterministic-policy leaf without starting an agent.

    The gateway still owns disclosure and publishes the same sealed stream used by
    an agent batch.  Once complete, the policy materializes recorder-validated
    intents, the normal engine finalizes them, and the durable leaf is promoted.
    There is deliberately no prompt, model process, sandbox, or transcript.
    """
    from .strategies.cup_handle import policy as cup_handle_policy

    sdir = Path(work["sdir"])
    sid = sdir.name
    gateway: step.IsolatedStreamGateway = work["gateway"]
    status = "ok"
    extra: dict = {}
    final_sdir = sdir
    try:
        gateway.publish()
        records = cup_handle_policy.apply_to_session(sdir)
        recorder.finalize(sdir)
        extra["decisions"] = len(records)
    except Exception as e:  # noqa: BLE001 — preserve a visible, re-runnable leaf
        status = "policy-error"
        extra["finalize_error"] = str(e)
        _stamp_finalize_error(sdir, str(e))
    finally:
        gateway.close()
    try:
        final_sdir = _promote_staged_session(sdir)
    except Exception as e:  # noqa: BLE001 — an unpromoted leaf is not a usable result
        status = "promotion-error"
        extra["promotion_error"] = str(e)
    return {
        "item": work["item"],
        "session_name": None,
        "sid": sid,
        "ticker": work["ticker"],
        "date": work["date"],
        "rep": work["rep"],
        "status": status,
        "policy_id": work.get("decision_policy"),
        **extra,
    }


def _source_hash(*subjects: object) -> str:
    """Hash the relevant runner source without depending on a Git checkout at runtime."""
    digest = hashlib.sha256()
    for subject in subjects:
        try:
            source = inspect.getsource(subject)
        except (OSError, TypeError) as e:
            raise RuntimeError(f"cannot source-stamp runner contract component {subject!r}") from e
        digest.update(source.encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def runner_contract() -> dict:
    """Immutable provenance for the agent prompt and its execution harness.

    Skill bytes and frozen execution configuration are stamped independently. This
    contract captures the surrounding behavior that can otherwise shift an LLM's
    decisions: the prompt template, sandbox/data access, staged-session lifecycle,
    and one-tick gateway semantics.
    """
    return {
        "harness_version": RUNNER_CONTRACT_VERSION,
        "prompt_hash": _source_hash(_prompt),
        "harness_hash": _source_hash(
            _agent_env,
            _write_agent_sandbox,
            _preseal,
            _run_one,
            step.IsolatedStreamGateway,
            step.start_isolated,
        ),
    }


def deterministic_policy_runner_contract(policy_id: str) -> dict:
    """Immutable provenance for a no-agent deterministic policy runner."""
    from .strategies.cup_handle import policy as cup_handle_policy

    if policy_id != cup_handle_policy.POLICY_ID:
        raise ValueError(f"unsupported deterministic policy {policy_id!r}")
    return {
        "harness_version": "deterministic_policy_v1",
        "decision_source": cup_handle_policy.DECISION_SOURCE,
        "policy_id": policy_id,
        "policy_hash": _source_hash(
            cup_handle_policy.decisions_for_ticks,
            cup_handle_policy.apply_to_session,
        ),
        "harness_hash": _source_hash(
            _preseal,
            _run_policy_one,
            step.IsolatedStreamGateway,
            step.start_isolated,
        ),
    }


def _file_hash(path: Path) -> str:
    try:
        return f"sha256:{hashlib.sha256(Path(path).read_bytes()).hexdigest()}"
    except OSError as e:
        raise ValueError(f"cannot hash test set {path}") from e


def _existing_session_id(tag: str) -> Optional[str]:
    """The top-level session id (``…-BATCH-<hex>``) already used by this batch's
    leaves, so ``--resume`` rejoins the original batch in the viewer instead of
    forking a new top-level session. None if the batch has no leaves yet."""
    for d in _sessions_for_batch(tag):
        sid = (recorder._load_json(d / "session.json", {}) or {}).get("session")
        if sid:
            return sid
    return None


def _tag_for_session(session_id: str) -> Optional[str]:
    """The batch `tag` (cohort key for manifest/logs) behind a top-level session id,
    recovered from that session's leaves — so `--resume --session <id>` works without
    also passing --tag. None if no leaf carries that session id."""
    for _, s in recorder.iter_sessions():
        if s.get("session") == session_id and s.get("batch"):
            return s.get("batch")
    return None


def _requires_causal_scanner_plan(skill_meta: dict) -> bool:
    value = skill_meta.get("arm_on_scanner_plan_required")
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _deterministic_policy_id(skill_meta: dict, strategy_id: str) -> Optional[str]:
    """Return the named supported deterministic policy, or None for an agent skill.

    A frontmatter declaration is an executable contract, not a hint.  Reject an
    unknown source/policy at batch setup rather than silently falling back to an
    LLM or running a policy for the wrong strategy family.
    """
    source = str(skill_meta.get("decision_source") or "").strip().lower()
    if not source or source in {"agent", "llm"}:
        return None
    if source != "deterministic_policy":
        raise ValueError(f"unsupported decision_source {source!r}")
    if strategy_id != "cup_handle":
        raise ValueError("deterministic_policy is currently implemented only for cup_handle")
    from .strategies.cup_handle import policy as cup_handle_policy

    policy_id = skill_meta.get("decision_policy")
    if policy_id != cup_handle_policy.POLICY_ID:
        raise ValueError(
            "cup_handle deterministic_policy requires decision_policy "
            f"{cup_handle_policy.POLICY_ID!r}, got {policy_id!r}"
        )
    return policy_id


def _validate_causal_testset(
    setups: list[dict],
    *,
    db: Path,
    strategy_id: str,
) -> None:
    """Refuse a batch before preseal when its named scanner rows are stale.

    This check uses the exact ``ticker/date/time_et`` testset pin.  It catches a
    deleted/replaced row as well as an old confirmed-breakout label, so a batch never
    produces a collection of quiet 0R stand-downs from incompatible provenance.
    """
    from . import replay

    invalid: list[str] = []
    for item in setups:
        ticker, day, time_et = item.get("ticker"), item.get("date"), item.get("time_et")
        label = f"{ticker} {day} {time_et}"
        try:
            setup = replay.pick_setup(
                db, ticker=ticker, day=datetime.fromisoformat(str(day)).date(),
                at_time=time_et, strategy=strategy_id, skip_time_filter=True,
            )
        except Exception as e:  # the exact testset pin is unavailable
            invalid.append(f"{label}: scanner row unavailable ({e})")
            continue
        errors = replay.causal_plan_feature_errors(setup)
        if errors:
            invalid.append(f"{label}: " + "; ".join(errors))
    if invalid:
        preview = "\n  - ".join(invalid[:8])
        more = f"\n  ... and {len(invalid) - 8} more" if len(invalid) > 8 else ""
        raise ValueError(
            "batch testset is incompatible with the causal cup-handle skill:\n  - "
            + preview + more
            + "\nRe-run the cup_handle scanner and regenerate this test set before running agents."
        )


def run(
    version: Optional[str] = None, *, model: Optional[str] = None,
    testset: Optional[str | Path] = None, parallel: int = 3,
    repeats: int = 1, tag: Optional[str] = None, timeout: int = 900,
    retries: int = _DEFAULT_RETRIES, max_reentries: int = 1,
    trade_until: Optional[str] = None,
    resume: bool = False, dry_run: bool = False, session: Optional[str] = None,
    strategy: str = "warrior", exploratory: bool = False,
    db: Optional[str | Path] = None,
) -> str:
    """Run the batch: spawn agents for every (setup × repeat), then audit + report."""
    resume_meta: dict = {}
    strategy_id = (strategy or "warrior").strip().lower().replace("-", "_")
    registry_path, trade_skills_dir, strategy_db, strat = _strategy_paths(strategy_id)
    entry_db = Path(db).expanduser().resolve() if db is not None else strategy_db.resolve()
    # ── Resolve the batch identity FIRST (before touching skill/testset) so a --resume
    # can recover the batch's recorded config. A batch is keyed internally by its `tag`
    # (manifest/logs/batch.json) and displayed under its top-level `session` id
    # (…-BATCH-…). Name it by EITHER; the missing one is derived from the other's
    # existing leaves — so `--resume --session <id>` needs no --tag, and vice versa.
    if session and not tag:
        tag = _tag_for_session(session)
        if tag:
            print(f"--session {session}: resolved batch tag {tag}", file=sys.stderr)
        elif resume:
            raise SystemExit(
                f"cannot resume: no existing runs found for session {session} "
                "(nothing to derive the batch tag from). Check the session id, or "
                "pass --tag as well.")

    # On --resume, fill in version / model / testset / repeats from what the batch
    # recorded in batch.json, so you don't have to repeat them. Explicit CLI values win.
    if resume:
        if not tag:
            raise SystemExit("cannot resume without a batch to resume — pass --session "
                             "<id> or --tag <tag>.")
        bmeta = _read_batch_meta(tag)
        if not bmeta:
            raise SystemExit(f"cannot resume: no recorded batch config (batch.json) for "
                             f"tag {tag}.")
        resume_meta = bmeta
        version = version or bmeta.get("version")
        model = model or bmeta.get("model")
        if testset is None and bmeta.get("testset"):
            testset = Path(bmeta["testset"])
        recorded_db = bmeta.get("entry_db")
        if recorded_db:
            recorded_db = Path(recorded_db).expanduser().resolve()
            if db is None:
                entry_db = recorded_db
            elif entry_db != recorded_db:
                raise ValueError(
                    "cannot resume with a different entry database than the batch's "
                    f"recorded entry_db ({recorded_db})"
                )
        if repeats == 1 and isinstance(bmeta.get("repeats"), int):
            repeats = bmeta["repeats"]
        # Re-entry budget + cutoff are fixed for the batch — a resume must match them, so
        # recover from batch.json rather than re-deriving from the CLI (you can't mix modes).
        if "max_reentries" in bmeta:
            max_reentries = int(bmeta["max_reentries"])
        elif "reentry" in bmeta:  # older batches recorded only the on/off flag
            max_reentries = 1 if bmeta["reentry"] else 0
        if "trade_until" in bmeta:
            trade_until = bmeta["trade_until"]
        if bmeta.get("research_tier") == "exploratory":
            exploratory = True
        print(f"--resume: using version={version} model={model} "
              f"set={testset} repeats={repeats} max_reentries={max_reentries} "
              f"trade_until={trade_until} db={entry_db} (from batch.json)", file=sys.stderr)

    if not model:
        model = DEFAULT_MODEL
        print(f"no --model provided; using default {model}", file=sys.stderr)
    # Resolve --set: bare names land under batch/<strategy>/; absolute paths keep working.
    try:
        testset = resolve_testset_path(testset, strategy_id)
    except SystemExit:
        raise
    if trade_until is not None and not re.fullmatch(r"\d{1,2}:\d{2}", trade_until):
        raise SystemExit(f"--trade-until must be HH:MM ET (got {trade_until!r}).")
    if max_reentries < 0:
        raise SystemExit(f"--max-reentries must be ≥ 0 (got {max_reentries}).")
    if not entry_db.is_file():
        raise ValueError(f"entry database does not exist or is not a file: {entry_db}")

    # Source the skill from the current BASE version by default so a batch tests the
    # accepted rules. Its text is inlined into every agent prompt (see _prompt), so
    # the agent never reads a skill file — that agent-side file read is exactly what
    # the audit was voiding. An explicit --version still runs that pinned, immutable
    # version file (also inlined; the harness reads it, never the agent).
    if version:
        skill_path = _archived_skill(version, strategy_id)
    else:
        skill_path = skillmeta.base_skill_path(registry_path, trade_skills_dir)
        version = skillmeta.read_skill_meta(skill_path).get("version")
        print(
            f"no --version provided; using {strategy_id} base skill "
            f"{skill_path.name} (v{version})",
            file=sys.stderr,
        )
    # A real pinned batch is the first use of many candidate files.  Register and
    # seal it *before* any preseal/agent work so every leaf is bound to immutable
    # bytes.  `recorder.init(..., pin_version=...)` intentionally stays read-only,
    # so this is the one batch-level place that performs first-use registration.
    # A dry-run remains inspect-only and leaves a candidate writable.
    if not dry_run:
        registered_meta, _ = skillmeta.resolve_version(
            skill_path, registry_path
        )
        if registered_meta.get("version") != version:
            raise ValueError(
                f"skill file {skill_path} declares version {registered_meta.get('version')!r}, "
                f"not requested --version {version!r}"
            )
    skill_meta = skillmeta.read_skill_meta(skill_path)
    execution_model = skill_meta.get("execution_model") or "reported_fill_v1"
    decision_policy = _deterministic_policy_id(skill_meta, strategy_id)
    session_from_open = str(skill_meta.get("session_from_open")).lower() == "true"
    five_minute_context = str(skill_meta.get("five_minute_context")).lower() == "true"
    engine_owned_targets = str(
        skill_meta.get("scanner_plan_targets_engine_owned")
    ).strip().lower() in {"1", "true", "yes"}
    if five_minute_context and not session_from_open:
        raise ValueError("five_minute_context requires session_from_open: true")
    horizon = skill_meta.get("horizon") or strat.horizon.kind
    bar_resolution = skill_meta.get("bar_resolution") or strat.horizon.bar_resolution
    skill_text = skill_path.read_text(encoding="utf-8")
    current_runner_contract = (
        deterministic_policy_runner_contract(decision_policy)
        if decision_policy else runner_contract()
    )
    testset_hash = _file_hash(testset)
    if resume:
        recorded_runner_contract = resume_meta.get("runner_contract")
        if not isinstance(recorded_runner_contract, dict):
            raise ValueError(
                "cannot resume an unstamped batch: runner_contract is missing from batch.json. "
                "Start a new batch so its leaves have consistent provenance."
            )
        if recorded_runner_contract != current_runner_contract:
            raise ValueError(
                "cannot resume under a different runner contract: prompt or harness behavior "
                "changed since this batch began. Start a new batch."
            )
        if resume_meta.get("testset_hash") != testset_hash:
            raise ValueError(
                "cannot resume with different test-set bytes than the batch's recorded testset_hash"
            )
        if resume_meta.get("skill_hash") != skill_meta.get("content_hash"):
            raise ValueError(
                "cannot resume with different skill bytes than the batch's recorded skill_hash"
            )
    setups = load_testset(testset)
    research_provenance, research_tier = (
        _cup_handle_research_tier(testset, setups, exploratory=exploratory)
        if strategy_id == "cup_handle" else (None, "not_applicable")
    )

    # Do this before allocating a batch id, staging a session, or starting an
    # agent.  v0.5 needs scanner-produced plans; historical confirmed labels are
    # not safe substitutes even if their dates and tickers still exist in the DB.
    if _requires_causal_scanner_plan(skill_meta):
        _validate_causal_testset(setups, db=entry_db, strategy_id=strategy_id)

    tag = tag or f"{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if session:
        session_id = session
    elif resume and (recovered := _existing_session_id(tag)):
        session_id = recovered
        print(f"--resume: rejoining existing session {session_id}", file=sys.stderr)
    else:
        session_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-BATCH-{secrets.token_hex(3)}"
        if resume:
            print(f"--resume: no existing leaves for tag {tag}; starting fresh session "
                  f"{session_id}", file=sys.stderr)

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
                "time_et": su.get("time_et"),
                "session_name": _session_name(tag, su["ticker"], su["date"], rep),
                "tag": tag,
                "session": session_id,
                "runner_contract": current_runner_contract,
                "decision_policy": decision_policy,
                "model": model, "timeout": timeout, "retries": retries,
                "max_reentries": max_reentries, "trade_until": trade_until,
                "dry_run": dry_run,
                "session_from_open": session_from_open,
                "five_minute_context": five_minute_context,
                "engine_owned_targets": engine_owned_targets,
                "horizon": horizon,
                "bar_resolution": bar_resolution,
                "strategy": strategy_id,
                "profile": strat.risk.profile,
                "db": str(entry_db),
                "multi_day": (horizon or "").lower() in ("multi_day", "multiday", "swing")
                    or (bar_resolution or "").lower() in ("1day", "daily"),
            })

    reentry_desc = (f"reentry-budget {max_reentries}" if max_reentries > 0 else "reentry OFF") + \
        (f" until {trade_until} ET" if trade_until else "")
    executor_desc = (
        f"deterministic policy {decision_policy}; no LLM"
        if decision_policy else f"model {model}, {reentry_desc}"
    )
    research_tier_note = (
        "" if research_tier == "promotion_eligible"
        else f" [{research_tier.upper().replace('_', ' ')} — NON-PROMOTABLE]"
    )
    print(f"batch {tag} (session {session_id}): version {version}, {len(setups)} setups × {repeats} "
          f"= {len(work)} runs (parallel {parallel}, {executor_desc})"
          f"{research_tier_note}"
          f"{' [DRY RUN]' if dry_run else ''}", file=sys.stderr)

    if dry_run:
        if decision_policy:
            print(json.dumps([
                {"item": w["item"], "status": "dry-run-deterministic-policy",
                 "policy_id": decision_policy, "model_used": False}
                for w in work
            ], indent=2))
            return tag
        # Don't create real sessions in a dry run — show the agent prompt with a
        # placeholder SDIR so the plan is inspectable without touching the provider.
        for w in work:
            w["prompt"] = _prompt(version, skill_text, tag, session_id, w["ticker"],
                                  w["date"], w.get("time_et"), sdir="<PRE-SEALED-SDIR>",
                                  max_reentries=w["max_reentries"], trade_until=w["trade_until"],
                                  execution_model=execution_model,
                                  session_from_open=w["session_from_open"],
                                  horizon=w.get("horizon") or "intraday",
                                  bar_resolution=w.get("bar_resolution") or "1min",
                                  auto_lookback=w.get("auto_lookback"),
                                  engine_owned_targets=w.get("engine_owned_targets", False))
        print(json.dumps([_run_one(w) for w in work], indent=2))
        return tag

    # Pre-seal every session in the harness's memory, then hand the agent a literal
    # *staged* SDIR. The full stream remains behind a one-tick gateway; the sandbox
    # cannot read the durable simulations/data trees. Sealing is serial so provider
    # fetches do not contend with N parallel agents.
    ready: list[dict] = []
    for w in work:
        try:
            sdir, gateway = _preseal(w, skill_path, version, session_id)
            w["sdir"] = str(sdir)
            w["gateway"] = gateway
            if not decision_policy:
                w["prompt"] = _prompt(version, skill_text, tag, session_id, w["ticker"],
                                      w["date"], w.get("time_et"), w["sdir"],
                                      max_reentries=w["max_reentries"], trade_until=w["trade_until"],
                                      execution_model=execution_model,
                                      session_from_open=w["session_from_open"],
                                      horizon=w.get("horizon") or "intraday",
                                      bar_resolution=w.get("bar_resolution") or "1min",
                                      auto_lookback=w.get("auto_lookback"),
                                      engine_owned_targets=w.get("engine_owned_targets", False))
            ready.append(w)
        except Exception as e:  # noqa: BLE001 — one bad setup shouldn't sink the batch
            print(f"  [preseal-err] {w['item']}: {e}", file=sys.stderr)
    work = ready
    if not work:
        raise RuntimeError("pre-sealing failed for every setup — no sessions to run "
                           "(check market-data credentials and provider coverage)")

    # record the batch so the viewer's Batches list shows it as *running* with an
    # accurate planned total (len(setups)×repeats, not len(work) which drops resumed
    # items) from the moment it starts — before any session finalizes.
    _write_batch_meta(
        tag, version=version, model=model, testset=str(testset),
        testset_hash=testset_hash, skill_hash=skill_meta.get("content_hash"),
        entry_db=str(entry_db),
        research_provenance=research_provenance,
        research_tier=research_tier,
        runner_contract=current_runner_contract,
        decision_source=("deterministic_policy" if decision_policy else "agent"),
        decision_policy=decision_policy,
        strategy=strategy_id,
        planned=len(setups) * repeats, repeats=repeats,
        reentry=(max_reentries > 0),  # kept for back-compat display / compare guardrail
        max_reentries=max_reentries, trade_until=trade_until,
        started_ts=datetime.now().isoformat(timespec="seconds"),
        finished_ts=None, status="running",
    )

    # Persist each run's sid ↔ hermes-session-name mapping **as it finishes** (not in
    # one write at the end), so a crash mid-batch can't strand finalized sessions with
    # no manifest entry — which the audit would then void as unverifiable.
    results: list[dict] = []
    run_leaf = _run_policy_one if decision_policy else _run_one
    if parallel <= 1:
        for w in work:
            r = run_leaf(w)
            _append_manifest(tag, r)
            results.append(r)
            print(f"  [{r['status']}] {r['item']}", file=sys.stderr)
            if r.get("status") == "ok":
                summ = _summarize_session(r.get("sid"))
                if summ:
                    print(summ, file=sys.stderr)
    else:
        with _cf.ThreadPoolExecutor(max_workers=parallel) as ex:
            for r in ex.map(run_leaf, work):     # yielded in the main thread → serial writes
                _append_manifest(tag, r)
                results.append(r)
                print(f"  [{r['status']}] {r['item']}", file=sys.stderr)
                if r.get("status") == "ok":
                    summ = _summarize_session(r.get("sid"))
                    if summ:
                        print(summ, file=sys.stderr)

    n_void = audit(tag)
    n_ooc = sum(r.get("status") == "out-of-credits" for r in results)
    n_timeout = sum(r.get("status") == "timeout" for r in results)
    runner_label = "policy runs" if decision_policy else "agents"
    print(f"\nbatch {tag} done: {sum(r['status']=='ok' for r in results)}/{len(results)} "
          f"{runner_label} ok, {n_void} sessions voided by audit"
          + (f", {n_ooc} out of credits (excluded, not void)" if n_ooc else "")
          + (f", {n_timeout} timed out (excluded, not complete)" if n_timeout else ""),
          file=sys.stderr)
    if n_ooc:
        print(f"⚠️  {n_ooc} run(s) hit HTTP 402 (out of API credits) and never traded — "
              "top up credits and re-run with --resume to fill them in.", file=sys.stderr)
    if n_timeout:
        print(f"⚠️  {n_timeout} run(s) exhausted their retries and timed out — recorded as "
              "failed (not complete). Re-run with --resume to retry them.", file=sys.stderr)

    # Loud guard: if (nearly) every finalized session voided as *unverifiable*, the
    # hermes export / --continue contract almost certainly isn't satisfied — the report
    # below would be meaningless (n≈0). Say so, actionably, instead of printing zeros.
    n_complete, n_unverif = _void_stats(tag)
    if n_complete and n_unverif >= n_complete:
        print(f"\n🛑 ALL {n_complete} finalized sessions voided as UNVERIFIABLE — the "
              "audit could not locate any run's hermes session by its SDIR.\n"
              "   The `hermes sessions list`/`export` contract likely differs on this "
              "build; the report below is meaningless. Run the 1-setup\n   smoke test in "
              "the README and confirm `hermes sessions export` returns tool calls before "
              "trusting a batch.\n", file=sys.stderr)

    _write_batch_meta(
        tag, status="complete", n_void=n_void,
        finished_ts=datetime.now().isoformat(timespec="seconds"),
    )
    _print_batch_report(tag)
    return tag


def _batch_meta_path(tag: str) -> Path:
    return BATCH_LOGS / tag / "batch.json"


def _read_batch_meta(tag: str) -> dict:
    """The batch's recorded config (version, model, testset, repeats, …) from
    batch.json, so --resume can recover what to run. Empty dict if none."""
    p = _batch_meta_path(tag)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError, TypeError):
        return {}


def _write_batch_meta(tag: str, **fields) -> None:
    """Merge fields into the batch's `batch.json` (drives the viewer's Batches list:
    planned count, version/model, running↔complete status, timestamps)."""
    p = _batch_meta_path(tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    meta = {}
    if p.exists():
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError):
            meta = {}
    meta.update(fields)
    atomic_write_json(p, meta, indent=2)


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
    """Return every local leaf for a batch, including manifest-orphaned sessions.

    A manifest is useful for correlating agent transcripts, but it is not an
    authority for research integrity: interrupted/older runs can exist on disk
    without a manifest row and must still be audited and excluded from metrics.
    """
    manifest = _load_manifest(tag)
    paths: list[Path] = []
    seen: set[Path] = set()
    if manifest:
        for r in manifest:
            sid = r.get("sid")
            if sid:
                d = recorder.SIM_ROOT / sid
                if d.exists() and d not in seen:
                    paths.append(d)
                    seen.add(d)
    for d, s in recorder.iter_sessions():
        if s.get("batch") == tag and d not in seen:
            paths.append(d)
            seen.add(d)
    return paths


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


# tool-call argument keys that carry an actual action — a shell command or a file
# path. We scan ONLY these, never a planning/todo tool's arguments: those quote the
# plan ("run step start", "do NOT read _sealed.jsonl") and would false-positive exactly
# like scanning prose would (the bug this whole audit exists to avoid).
_ACTION_KEYS = ("command", "cmd", "script", "code", "path", "file",
                "filename", "file_path", "paths", "files")
_SHELL_TOOL_HINT = ("terminal", "bash", "shell", "sh", "exec", "run", "command")


def _command_text(name: Optional[str], args) -> str:
    """The actionable text of one tool call: its shell command / file path(s), or ""
    for a non-action tool (todos, thinking, …) whose args carry no action key."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            nm = (name or "").lower()          # unparseable: trust only a shell tool
            return args if any(h in nm for h in _SHELL_TOOL_HINT) else ""
    if isinstance(args, dict):
        vals = []
        for k in _ACTION_KEYS:
            v = args.get(k)
            if v is not None:
                vals.append(v if isinstance(v, str) else json.dumps(v))
        return "\n".join(vals)
    return ""


def _parse_export(export_text: str) -> Optional[str]:
    """Extract *only the executed shell commands / file accesses* from a `hermes
    sessions export` dump — never the assistant's prose, and never a planning tool's
    arguments. Both quote the rules (which name `_sealed.jsonl`, `step start`, …) on
    every compliant run, so scanning them would false-positive; only a tool call's
    action fields (`command`, `path`, …) are what the agent actually did.
    Returns None if no action tool calls were found (session is then unverifiable)."""
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
                txt = _command_text(name, args)
                if txt:
                    parts.append(txt)
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


# A run's session prints these markers bound to its own SDIR (see the setup block in
# _prompt): `echo "CAPTURED_SDIR=$SDIR"` and the final `BATCHSIM_SID=$SDIR`. Both resolve
# to the literal SDIR only in the owner's export; a `recorder report` / `ls` listing shows
# other runs' SDIRs as bare paths with no such marker. So a marker immediately preceding
# the SDIR is a definitive owner signal, immune to report-output cross-contamination.
_OWNER_MARKERS = ("BATCHSIM_SID=", "CAPTURED_SDIR=")


def _owns_marker(text: Optional[str], sid: str) -> bool:
    """True if ``text`` binds this SDIR to a session via a setup-block owner marker."""
    if not text:
        return False
    return re.search(r"(?:BATCHSIM_SID|CAPTURED_SDIR)=\S*" + re.escape(sid), text) is not None


def _resolve_batch_commands(sids: list[str]) -> dict[str, Optional[str]]:
    """Map each recorder session id → its agent's executed tool-call commands (or None
    if its hermes session can't be found). Finds the session by the SDIR it contains
    (globally unique, so this is correct even under parallelism), scanning recent
    hermes sessions and stopping once every sid is matched."""
    result: dict[str, Optional[str]] = {sid: None for sid in sids}
    remaining = set(s for s in sids if s)
    if not remaining:
        return result
    recent_ids = _recent_session_ids(limit=max(20, 3 * len(sids)))

    # Export every candidate session once, keeping (raw_text, parsed_commands).
    exported: list[tuple[str, Optional[str]]] = []
    with _cf.ThreadPoolExecutor(max_workers=min(10, max(1, len(recent_ids)))) as pool:
        future_to_hid = {pool.submit(_export_session, hid): hid for hid in recent_ids}
        for future in _cf.as_completed(future_to_hid):
            try:
                text = future.result()
            except Exception:
                text = None
            if text:
                exported.append((text, _parse_export(text)))

    # Attribute each run to the session that OWNS it. Priority (strongest signal first):
    #   1. the owner's export contains a setup-block marker binding it to this SDIR:
    #      `CAPTURED_SDIR=<sdir>` (echoed right after init) or `BATCHSIM_SID=<sdir>` (the
    #      agent's final line). Only the owning agent emits these for its own $SDIR.
    #   2. the SDIR appears in the session's executed COMMANDS (owner typed the literal path).
    #   3. fallback: the SDIR appears anywhere in the raw export (captured into $SDIR from
    #      init output, never re-typed); prefer a session that has parseable commands.
    # This stops cross-contamination: an agent that runs `recorder report`/`ls` prints OTHER
    # runs' SDIRs in its OUTPUT as bare paths (no marker), which used to pull that session's
    # commands (its own re-run `step start`, `_sealed` reference, …) onto innocent leaves.
    for sid in list(remaining):
        owners = [c for t, c in exported if _owns_marker(t, sid)]
        if owners:
            result[sid] = next((c for c in owners if c), owners[0])  # prefer a parseable one
            remaining.discard(sid)
            continue
        pick = next((c for _, c in exported if c and sid in c), None)
        if pick is None:
            pick = next((c for t, c in exported if c and sid in t), None)
        if pick is not None:
            result[sid] = pick
            remaining.discard(sid)

    if remaining and not any(v is not None for v in result.values()):
        print(f"⚠ audit: could not locate hermes sessions for {len(remaining)} run(s) by "
              "SDIR — `hermes sessions export` contract may not hold (see README smoke "
              "test); those runs will be voided as unverifiable.", file=sys.stderr)
    return result


def _reads_private_content(line: str, name: str) -> bool:
    """True if `line` READS the private file's content (cat/grep/python/input-redirect, …),
    as opposed to a benign existence check (ls / test -f / stat) that only names it."""
    idx = line.find(name)
    if idx < 0:
        return False
    seg = re.split(r"[&;|]", line[:idx])[-1]      # the command governing this file arg
    if re.search(r"<\s*\S*$", seg):               # input redirect  … < _sealed.jsonl
        return True
    return bool(_READ_VERB_RE.search(seg))


def _scan_commands(commands: str) -> Optional[str]:
    """Return a void reason if the executed commands show look-ahead / a determinism break,
    else None. DENYLIST model: only concrete peek vectors void a run — benign shell the agent
    wraps around the sanctioned tools (cd, env-load, viewer management, journal writes, step
    loops, re-running a no-op `step start`, or an `ls`/`test` on a private file) is not
    policed, since none of it can reveal an unrevealed bar. Operates on tool-call commands
    only (see ``_parse_export``)."""
    lines = _command_lines(commands)
    executable = "\n".join(lines)
    # 1) reading the private sealed stream / cursor content (not merely naming it in ls/test)
    for line in lines:
        for name in _PRIVATE_FILES:
            if _reads_private_content(line, name):
                return f"agent read forbidden `{name}`"
    # 2) direct access to the raw market-data layer
    for pat in _DATA_LAYER_PATTERNS:
        if pat in executable:
            return f"agent command referenced forbidden `{pat}`"
    if _REPLAY_RE in executable:
        return "agent invoked replay directly (look-ahead)"
    # 2b) out-of-band network fetch (public price API, exfiltration) — a sealed
    #     batch agent must only read bars through `step next`.
    if _NETWORK_FETCH_RE.search(executable):
        return "agent issued an out-of-band network fetch (possible look-ahead / data exfiltration)"
    # 3) re-seal AFTER revealing bars: reveal the day → reset cursor → re-trade with
    #    foreknowledge. A plain re-run of `step start` is a harmless no-op (step.start refuses
    #    to re-seal a started session); only a --force re-seal following a `step next` leaks.
    seen_next = False
    for line in lines:
        if _STEP_NEXT_RE in line:
            seen_next = True
        elif _STEP_START_RE in line and "--force" in line and seen_next:
            return "agent force-re-sealed after revealing bars (look-ahead)"
    return None


def _command_lines(commands: str) -> list[str]:
    out: list[str] = []
    pending = ""   # accumulates backslash-continued lines into one logical command
    for raw in (commands or "").splitlines():
        line = raw.strip()
        if pending:
            line = (pending + " " + line).strip()
            pending = ""
        if line.endswith("\\"):          # shell line continuation → join with the next line
            pending = line[:-1].strip()
            continue
        if not line or line.startswith("#"):
            continue
        out.append(line)
    if pending:
        out.append(pending)
    return out


def _stamp_out_of_credits(sdir: Path) -> None:
    """Mark a finalized session as an out-of-credits infra failure (not a void)."""
    sj = Path(sdir) / "session.json"
    s = recorder._load_json(sj, {}) or {}
    s["out_of_credits"] = _OUT_OF_CREDITS_LABEL
    s.pop("void", None)  # a run is never both out-of-credits and voided
    atomic_write_json(sj, s, indent=2)


def _stamp_timeout(sdir: Path) -> None:
    """Mark a finalized session as a timed-out infra failure (not a void, and NOT a
    clean 'complete no-trade'). Mirrors _stamp_out_of_credits: the stats/viewer/resume
    layers treat `timed_out` exactly like out-of-credits — excluded, re-runnable."""
    sj = Path(sdir) / "session.json"
    s = recorder._load_json(sj, {}) or {}
    s["timed_out"] = _TIMEOUT_LABEL
    s.pop("void", None)  # a run is never both timed-out and voided
    atomic_write_json(sj, s, indent=2)


def _stamp_finalize_error(sdir: Path, message: str) -> None:
    """Mark a session whose finalize() replay raised (status never reached
    "complete") so it is a visibly broken, re-runnable infra failure — not an
    orphaned "running" leaf that looks like it's still live. Sets status
    explicitly (finalize never got to write it) so the viewer/audit stop
    treating it as in-progress."""
    sj = Path(sdir) / "session.json"
    s = recorder._load_json(sj, {}) or {}
    s["status"] = "error"
    s["finalize_error"] = message
    s.pop("void", None)
    atomic_write_json(sj, s, indent=2)


def _has_no_decision_log(sdir: Path) -> bool:
    """True when an agent finalized a session without one logged intent.

    Every valid strategy outcome, including a deliberate stand-down, requires at
    least one intent record. An empty log means the agent/harness failed before it
    made a trading decision; it must never be scored as a 0R stand-down.
    """
    try:
        return not any(line.strip() for line in (Path(sdir) / "decisions.jsonl").read_text().splitlines())
    except OSError:
        return True


def _stamp_no_decision_log(sdir: Path) -> None:
    """Mark an empty-intent session as a re-runnable infrastructure failure."""
    sj = Path(sdir) / "session.json"
    s = recorder._load_json(sj, {}) or {}
    s["no_decision_log"] = _NO_DECISION_LOG_LABEL
    s.pop("void", None)
    atomic_write_json(sj, s, indent=2)


def _agent_abandoned_stream(sdir: Path) -> Optional[str]:
    """Return a reason if the agent stopped logging while a plan was still live.

    Multi-day agents sometimes ARM and then exit the loop while the buy-stop is
    still pending (or while a fill later occurs without any manage-phase logs).
    That is not a clean complete run — flag it so ``--resume`` re-runs the setup.
    """
    sdir = Path(sdir)
    try:
        raw = [
            json.loads(ln) for ln in (sdir / "decisions.jsonl").read_text().splitlines()
            if ln.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return None
    if not raw:
        return None

    last = max(raw, key=lambda d: int(d.get("i", -1)))
    last_i = int(last.get("i", -1))
    last_action = str(last.get("action") or "")
    # Deliberate terminal stand-down is a complete early stop even mid-stream.
    if last_action == "STAND_DOWN":
        return None

    # Deterministic sessions have an authoritative state machine.  Replay only
    # through the final revealed/logged bar; using the raw ARM history alone
    # incorrectly flagged a completed CANCEL_ENTRY or engine gap-cancel as an
    # abandoned live order.
    session = recorder._load_json(sdir / "session.json", {}) or {}
    if session.get("config", {}).get("execution_model") == EXECUTION_MODEL:
        try:
            meta, ticks, _end = recorder._parse_stream(sdir / "stream.jsonl")
            if meta is not None and ticks:
                bars = recorder._build_bars(meta, ticks)
                engine = ExecutionEngine(ExecutionConfig.from_session_config(session.get("config", {})))
                engine.run(bars, raw, through_i=last_i, force_close=False)
                snap = engine.snapshot(last_i)
                if snap.get("position_shares"):
                    return (
                        f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} while position "
                        f"was still open"
                    )
                if snap.get("armed_entry"):
                    return (
                        f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} with live arm"
                    )
                return None
        except Exception:  # fall through to the legacy artifact heuristic below
            pass

    actions_used = {str(d.get("action") or "") for d in raw}
    if not (actions_used & _LIVE_PLAN_ACTIONS):
        return None  # pure OBSERVE walk / no plan engaged — not this failure mode

    # Prefer engine fills after finalize (authoritative entry/exit indices).
    fills = recorder._load_json(sdir / "actions.json", []) or []
    buy_is = [int(a["i"]) for a in fills if a.get("side") == "buy" and a.get("i") is not None]
    sell_is = [int(a["i"]) for a in fills if a.get("side") == "sell" and a.get("i") is not None]
    entry_i = min(buy_is) if buy_is else None
    exit_i = max(sell_is) if sell_is else None

    if entry_i is not None and exit_i is not None and last_i < exit_i:
        return (
            f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} before exit bar i={exit_i}"
        )
    if entry_i is not None and exit_i is None and last_i < entry_i:
        return (
            f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} before entry bar i={entry_i}"
        )
    if entry_i is not None and exit_i is None:
        # Still open at end of agent log; engine may force-flat later.
        return (
            f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} while position still open "
            f"(entry i={entry_i}, no exit fill logged under agent control)"
        )

    # Armed, never filled, never cancelled — abandoned pending entry.
    if "ARM_BUY_STOP" in actions_used and entry_i is None:
        if last_action in ("CANCEL_ENTRY",):
            return None
        # Confirm stream still had bars after the last log.
        max_tick = None
        try:
            for ln in (sdir / "stream.jsonl").read_text().splitlines():
                if not ln.strip():
                    continue
                o = json.loads(ln)
                if o.get("type") == "tick" and o.get("i") is not None:
                    max_tick = int(o["i"]) if max_tick is None else max(max_tick, int(o["i"]))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            max_tick = None
        if max_tick is not None and last_i < max_tick:
            return (
                f"{_AGENT_ABANDONED_LABEL}: last decision i={last_i} with live arm "
                f"(stream continues to i={max_tick})"
            )
    return None


def _stamp_agent_abandoned(sdir: Path, reason: str) -> None:
    """Mark a session the agent left mid-plan as a re-runnable incomplete run."""
    sj = Path(sdir) / "session.json"
    s = recorder._load_json(sj, {}) or {}
    s["agent_abandoned"] = reason or _AGENT_ABANDONED_LABEL
    # Keep status complete so artifacts remain viewable; resume skips only clean runs.
    s.pop("void", None)
    atomic_write_json(sj, s, indent=2)


def _agent_log_for(tag: str, session_name: Optional[str]) -> Optional[Path]:
    """The captured agent log for one run, if present (BATCH_LOGS/<tag>/<name>.log)."""
    if not session_name:
        return None
    p = BATCH_LOGS / tag / f"{session_name}.log"
    return p if p.exists() else None


def _ran_out_of_credits(tag: str, session: dict, session_name: Optional[str]) -> bool:
    """True if this run's session is already stamped out-of-credits, or its captured
    agent log shows the API ran out of balance (retroactive detection for batches run
    before the stamp existed)."""
    if session.get("out_of_credits"):
        return True
    p = _agent_log_for(tag, session_name)
    if not p:
        return False
    try:
        return _text_out_of_credits(p.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return False


def _is_deterministic_policy_session(session: dict) -> bool:
    """Whether a leaf claims the no-agent deterministic-policy decision path."""
    skill = session.get("skill") or {}
    policy = session.get("decision_policy") or {}
    return (
        str(skill.get("decision_source") or "").strip().lower() == "deterministic_policy"
        or str(policy.get("source") or "").strip().lower() == "deterministic_policy"
    )


def _deterministic_policy_integrity_errors(sdir: Path, session: dict) -> list[str]:
    """Verify a deterministic leaf directly against its published sealed stream.

    This replaces the Hermes command-log proof for this explicitly no-agent path.
    It is deliberately stricter than ordinary record validation: every persisted
    intent, including policy metadata and engine-owned targets, must equal the
    output re-derived from the sealed stream.
    """
    from .strategies.cup_handle import policy as cup_handle_policy

    errors: list[str] = []
    skill = session.get("skill") or {}
    stamp = session.get("decision_policy")
    if str(skill.get("decision_source") or "").strip().lower() != cup_handle_policy.DECISION_SOURCE:
        errors.append("skill is missing decision_source: deterministic_policy")
    if skill.get("decision_policy") != cup_handle_policy.POLICY_ID:
        errors.append(f"skill is missing decision_policy: {cup_handle_policy.POLICY_ID}")
    if not isinstance(stamp, dict):
        errors.append("session is missing deterministic policy provenance stamp")
    else:
        if stamp.get("source") != cup_handle_policy.DECISION_SOURCE:
            errors.append("session deterministic policy source does not match the supported policy")
        if stamp.get("id") != cup_handle_policy.POLICY_ID:
            errors.append("session deterministic policy id does not match the supported policy")
    if errors:
        return errors

    try:
        _meta, ticks, _end = recorder._parse_stream(Path(sdir) / "stream.jsonl")
        expected = cup_handle_policy.decisions_for_ticks(ticks)
        plan_by_i = {
            tick.get("i"): tick.get("scanner_plan")
            for tick in ticks if isinstance(tick, dict)
        }
        for record in expected:
            if record.get("action") != "ARM_BUY_STOP":
                continue
            plan = plan_by_i.get(record["i"])
            if not isinstance(plan, dict):
                raise cup_handle_policy.PolicyError("expected ARM tick has no scanner_plan")
            record["engine_targets"] = {
                "target1": float(plan["target1"]),
                "target2": float(plan["target2"]),
            }
        actual = recorder._read_jsonl(Path(sdir) / "decisions.jsonl")
    except Exception as e:  # noqa: BLE001 — audit must fail closed, never crash a cohort
        return [f"unable to re-derive deterministic policy decisions: {e}"]
    if actual != expected:
        errors.append("persisted decisions do not exactly match the deterministic policy replay")
    return errors


def audit(tag: str) -> int:
    """Void any session in the batch whose executed tool-call commands show look-ahead
    or a determinism break, or that can't be verified. Returns the number voided.

    The command source is the structured `hermes sessions export` tool calls for each
    run's session (located by the unique SDIR it contains) — NOT the free-form
    transcript, so the agent quoting its own rules no longer false-positives. A session
    with no retrievable command log is voided as *unverifiable* rather than trusted —
    UNLESS its agent never ran because the API was out of credits (HTTP 402), which is
    an infrastructure failure tagged `out_of_credits` and excluded from stats, not a
    look-ahead void.
    """
    all_dirs = _sessions_for_batch(tag)
    # Backfill leaves orphaned by the finalize-swallowing bug fixed alongside this
    # audit pass: pre-fix, a leaf whose finalize() raised was left stuck at status
    # "running" forever (indistinguishable from a genuinely live session) with the
    # exception silently dropped. Retry finalize now; if it still raises, stamp it
    # a visible, re-runnable finalize-error instead of leaving it orphaned.
    for d in all_dirs:
        session = recorder._load_json(d / "session.json", {}) or {}
        if session.get("status") == "running" and not session.get("finalize_error"):
            try:
                recorder.finalize(d)
            except Exception as e:  # noqa: BLE001
                _stamp_finalize_error(d, str(e))
        session = recorder._load_json(d / "session.json", {}) or {}
        if session.get("status") == "complete" and _has_no_decision_log(d):
            _stamp_no_decision_log(d)
        session = recorder._load_json(d / "session.json", {}) or {}
        if session.get("status") == "complete":
            if _is_deterministic_policy_session(session):
                # This heuristic infers an *agent* stopped requesting ticks.  A
                # deterministic policy intentionally writes its complete intent
                # log in one pass, so applying the heuristic here corrupts a
                # valid in-position leaf into an infrastructure failure.  Policy
                # replay below is the stronger, exact integrity proof.
                if session.pop("agent_abandoned", None) is not None:
                    atomic_write_json(d / "session.json", session, indent=2)
            else:
                abandoned = _agent_abandoned_stream(d)
                if abandoned:
                    if session.get("agent_abandoned") != abandoned:
                        _stamp_agent_abandoned(d, abandoned)
                elif session.pop("agent_abandoned", None) is not None:
                    # A newer deterministic replay can prove that a prior ARM was
                    # cancelled (manually or by the gap/expiry guard). Clear the old
                    # heuristic stamp so valid no-trade outcomes are scored normally.
                    atomic_write_json(d / "session.json", session, indent=2)

    sessions = [d for d in all_dirs
                if (recorder._load_json(d / "session.json", {}) or {}).get("status") == "complete"]
    # Data integrity is a precondition for every other audit.  Check it before
    # asking Hermes for transcripts, both to fail cheaply and to ensure a clean
    # command log cannot legitimize a stream that should never have traded.
    voided = 0
    integrity_invalid: set[Path] = set()
    deterministic_policy_sessions: set[Path] = set()
    for d in sessions:
        session = recorder._load_json(d / "session.json", {}) or {}
        integrity_errors = recorder.batch_integrity_errors(d, session)
        reason = None
        if integrity_errors:
            reason = "data-integrity: " + "; ".join(integrity_errors)
        elif _is_deterministic_policy_session(session):
            policy_errors = _deterministic_policy_integrity_errors(d, session)
            if policy_errors:
                reason = "deterministic-policy-integrity: " + "; ".join(policy_errors)
            else:
                deterministic_policy_sessions.add(d)
        if reason is None:
            continue
        integrity_invalid.add(d)
        if session.get("void") != reason:
            session["void"] = reason
            atomic_write_json(d / "session.json", session, indent=2)
            voided += 1
    sessions = [d for d in sessions if d not in integrity_invalid]
    # Do not invoke the external transcript exporter for an empty cohort.  Besides
    # avoiding needless work, this keeps a failed data-integrity preflight entirely
    # local: no agent artifact is consulted once every leaf was rejected.
    agent_sessions = [d for d in sessions if d not in deterministic_policy_sessions]
    cmd_map = _resolve_batch_commands([d.name for d in agent_sessions]) if agent_sessions else {}
    # sid → session_name, so a run with no command log can still be matched to its
    # captured agent log to distinguish out-of-credits from genuinely unverifiable.
    manifest = _load_manifest(tag)
    name_map = {r.get("sid"): r.get("session_name") for r in manifest}
    # sids the harness recorded as killed-on-timeout, so a run finalized before the
    # timeout stamp existed (or by an older build) is still reconciled here.
    timeout_sids = {r.get("sid") for r in manifest if r.get("status") == "timeout"}
    for d in sessions:
        session = recorder._load_json(d / "session.json", {}) or {}
        if d in deterministic_policy_sessions:
            continue  # policy replay above is the complete no-agent audit proof
        if session.get("no_decision_log") or session.get("agent_abandoned"):
            continue  # infra failure; excludes from stats and is re-run by --resume
        if session.get("timed_out") or d.name in timeout_sids:
            # A timeout infra failure (excluded from stats, re-run by --resume). Ensure
            # it's stamped (backfills old runs finalized as a bare "complete") and never
            # void it as a look-ahead peek.
            if not session.get("timed_out"):
                _stamp_timeout(d)
            continue
        commands = cmd_map.get(d.name)
        if commands is None and _ran_out_of_credits(tag, session, name_map.get(d.name)):
            # Infra failure, not a peek: mark out-of-credits, never void.
            session["out_of_credits"] = _OUT_OF_CREDITS_LABEL
            session.pop("void", None)
            atomic_write_json(d / "session.json", session, indent=2)
            continue
        reason = (
            "no agent command log to verify (unverifiable)"
            if commands is None else _scan_commands(commands)
        )
        # A run that now has a real command log is no longer an out-of-credits stub.
        stale_ooc = session.pop("out_of_credits", None) is not None
        if reason:
            session["void"] = reason
            atomic_write_json(d / "session.json", session, indent=2)
            voided += 1
        elif session.pop("void", None) is not None or stale_ooc:
            atomic_write_json(d / "session.json", session, indent=2)  # now clean
    return voided


# ───────────────────────────── report ───────────────────────────────────────


def _print_batch_report(tag: str) -> None:
    print(f"=== batch {tag} ===")
    recorder._print_report(recorder.report_by_version(batch=tag))


# ───────────────────────────── compare (the promotion gate) ──────────────────

import math as _math


def _leaves_by_key(tag: str) -> dict:
    """One representative leaf per (ticker, date) for a batch, so resume duplicates and
    void/out-of-credits stubs don't double-count. Prefers a completed, non-void,
    non-out-of-credits leaf; else the most recent leaf. Returns {(ticker,date): pnl+flags}."""
    best: dict = {}
    for d in _sessions_for_batch(tag):
        s = recorder._load_json(d / "session.json", {}) or {}
        key = (s.get("ticker"), s.get("historical_date"))
        if key == (None, None):
            continue
        p = recorder._load_json(d / "pnl.json", {}) or {}
        config = s.get("config", {}) or {}
        execution_model = (
            p.get("execution_model")
            or config.get("execution_model")
            or "reported_fill_v1"
        )
        rec = {
            "void": bool(s.get("void")), "ooc": bool(s.get("out_of_credits")),
            "timeout": bool(s.get("timed_out")),
            "finalize_error": bool(s.get("finalize_error")),
            "no_decision_log": bool(s.get("no_decision_log")),
            "agent_abandoned": bool(s.get("agent_abandoned")),
            "status": s.get("status"), "ts": s.get("real_run_ts") or "",
            "traded": bool(p.get("traded")), "r": p.get("r_multiple"),
            "pnl": p.get("realized_pnl"), "win": bool(p.get("win")),
            "execution_model": execution_model,
            # Legacy reported fills have no frozen execution config; their model
            # identifier is the complete execution contract. Deterministic leaves
            # must match every frozen cost/liquidity setting exactly.
            "execution_contract": (
                config.get("execution")
                if execution_model == EXECUTION_MODEL
                else {"execution_model": execution_model}
            ),
            "skill_hash": (
                p.get("skill_hash")
                or (s.get("skill", {}) or {}).get("content_hash")
            ),
            "runner_contract": s.get("runner_contract"),
        }
        def clean(r):
            return (r["status"] == "complete" and not r["void"] and not r["ooc"]
                    and not r["timeout"] and not r["finalize_error"]
                    and not r["no_decision_log"] and not r.get("agent_abandoned"))
        prev = best.get(key)
        if (prev is None or (clean(rec) and not clean(prev))
                or (clean(rec) == clean(prev) and rec["ts"] > prev["ts"])):
            best[key] = rec
    return best


def _effective_r(rec: dict) -> Optional[float]:
    """Deployment R for one leaf: traded → realized R; stood-down → 0R; void/ooc/timeout
    → None (excluded from the pair). None if a completed traded leaf is missing its R."""
    if (rec["void"] or rec["ooc"] or rec["timeout"] or rec["finalize_error"]
            or rec.get("no_decision_log", False)
            or rec.get("agent_abandoned", False)
            or rec["status"] != "complete"):
        return None
    if not rec["traded"]:
        return 0.0
    return rec["r"] if isinstance(rec["r"], (int, float)) else None


def _sign_test_p(n_up: int, n_down: int) -> Optional[float]:
    """Two-sided binomial sign-test p-value (H0: p=0.5), ties excluded. None if no pairs."""
    n = n_up + n_down
    if n == 0:
        return None
    k = min(n_up, n_down)
    tail = sum(_math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _contract_key(value: object) -> str:
    """Canonical, hashable representation for stamped comparison contracts."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _require_matching_batch_metadata(tag_a: str, tag_b: str) -> None:
    """Require stamped provenance and match every non-strategy batch contract.

    A comparison exists to measure a strategy/skill change, so the two batches'
    skill hashes must be present but are intentionally allowed to differ. Every
    other stamped condition has to match before a paired result is meaningful.
    """
    meta_a, meta_b = _read_batch_meta(tag_a), _read_batch_meta(tag_b)
    if {meta_a.get("strategy"), meta_b.get("strategy")} & {"cup_handle"}:
        tiers = (meta_a.get("research_tier"), meta_b.get("research_tier"))
        if tiers != ("promotion_eligible", "promotion_eligible"):
            raise ValueError(
                "cannot compare a non-promotable cup_handle cohort. Both batches must be "
                "built from point-in-time universe provenance; exploratory runs are for "
                "diagnostics only."
            )
    fields = [
        ("model", "model"),
        ("testset_hash", "test-set hash"),
        ("runner_contract", "runner contract"),
        ("reentry", "re-entry policy"),
    ]
    if {meta_a.get("strategy"), meta_b.get("strategy")} & {"cup_handle"}:
        fields.append(("entry_db", "entry database"))
    for field, label in fields:
        va, vb = meta_a.get(field), meta_b.get(field)
        if va is None or vb is None:
            missing = tag_a if va is None else tag_b
            raise ValueError(
                f"cannot compare unstamped batch {missing!r}: missing {field}. "
                "Run new cohorts under the current harness; historical results remain readable "
                "but are not promotion-comparable."
            )
        if _contract_key(va) != _contract_key(vb):
            raise ValueError(
                f"cannot compare batches with different {label}: A={tag_a}, B={tag_b}. "
                "This would confound a strategy comparison."
            )
    # A missing skill stamp is still a provenance failure, even though the two
    # values are supposed to be different for a version comparison.
    for tag, meta in ((tag_a, meta_a), (tag_b, meta_b)):
        if meta.get("skill_hash") is None:
            raise ValueError(
                f"cannot compare unstamped batch {tag!r}: missing skill_hash. "
                "Run a stamped cohort so the tested skill is auditable."
            )


def _require_matching_leaf_contract(leaves_a: dict, leaves_b: dict, field: str,
                                    label: str, *, match_between: bool = True) -> None:
    """Ensure each batch is internally uniform, and optionally equal to the other.

    Skill hash is intentionally internal-only: each candidate batch must use one
    immutable skill, but its hash is expected to differ from the baseline.
    """
    def unique(leaves: dict, tag_label: str) -> set[str]:
        values = []
        for key, row in leaves.items():
            value = row.get(field)
            if value is None:
                raise ValueError(
                    f"cannot compare unstamped {tag_label} leaf {key}: missing {field}"
                )
            values.append(_contract_key(value))
        out = set(values)
        if len(out) != 1:
            raise ValueError(
                f"cannot compare a batch with mixed {label} across its selected leaves"
            )
        return out

    values_a, values_b = unique(leaves_a, "baseline"), unique(leaves_b, "candidate")
    if match_between and values_a != values_b:
        raise ValueError(
            f"cannot compare batches with different {label}. "
            "This would confound a strategy comparison."
        )


def compare(tag_a: str, tag_b: str) -> dict:
    """Paired promotion gate: is candidate B better than baseline A on shared setups?
    A/B are batch tags. Pairs on (ticker,date), effective R (stood-down=0R, void/ooc
    excluded), sign test, tail-guard, and per-batch guardrails."""
    A, B = _leaves_by_key(tag_a), _leaves_by_key(tag_b)
    models_a = {r["execution_model"] for r in A.values()}
    models_b = {r["execution_model"] for r in B.values()}
    if len(models_a) != 1 or len(models_b) != 1 or models_a != models_b:
        raise ValueError(
            "cannot compare batches with different execution models: "
            f"A={sorted(models_a)}, B={sorted(models_b)}. "
            "A fill-model change is a major rebaseline; establish a new baseline first."
        )
    _require_matching_batch_metadata(tag_a, tag_b)
    _require_matching_leaf_contract(A, B, "skill_hash", "skill hash", match_between=False)
    _require_matching_leaf_contract(A, B, "execution_contract", "frozen execution config")
    _require_matching_leaf_contract(A, B, "runner_contract", "runner contract")
    keys = sorted(set(A) & set(B))
    pairs = []  # (key, rA, rB, dR)
    for k in keys:
        ra, rb = _effective_r(A[k]), _effective_r(B[k])
        if ra is None or rb is None:
            continue
        pairs.append((k, ra, rb, rb - ra))
    drs = [p[3] for p in pairs]
    n = len(drs)
    mean_d = sum(drs) / n if n else 0.0
    med_d = sorted(drs)[n // 2] if n else 0.0
    up = sum(1 for x in drs if x > 0.05)
    down = sum(1 for x in drs if x < -0.05)
    eq = n - up - down
    p_sign = _sign_test_p(up, down)
    # tail-guard: does a handful of setups explain the whole positive delta?
    pos = sorted((p for p in pairs if p[3] > 0), key=lambda p: -p[3])
    sum_pos = sum(p[3] for p in pos)
    top3_share = (sum(p[3] for p in pos[:3]) / sum_pos) if sum_pos > 0 else 0.0

    def batch_stats(leaves: dict) -> dict:
        vals = list(leaves.values())
        traded = [r for r in vals if _effective_r(r) is not None and r["traded"]]
        losers = [r["pnl"] for r in traded if not r["win"] and (r["pnl"] or 0) != 0]
        return {
            "n_keys": len(vals),
            "void": sum(1 for r in vals if r["void"] and not r["ooc"] and not r["timeout"]),
            "ooc": sum(1 for r in vals if r["ooc"]),
            "timeout": sum(1 for r in vals if r["timeout"]),
            "finalize_error": sum(1 for r in vals if r["finalize_error"]),
            "no_decision_log": sum(1 for r in vals if r["no_decision_log"]),
            "agent_abandoned": sum(1 for r in vals if r.get("agent_abandoned")),
            "stood": sum(1 for r in vals if _effective_r(r) == 0.0 and not r["traded"]),
            "avg_loser": (sum(losers) / len(losers)) if losers else None,
        }

    return {
        "tag_a": tag_a, "tag_b": tag_b, "n_pairs": n,
        "mean_dR": round(mean_d, 3), "median_dR": round(med_d, 3),
        "better": up, "worse": down, "equal": eq, "sign_p": p_sign,
        "top3_share": round(top3_share, 2),
        "top_contributors": [(k, round(dr, 2)) for k, _, _, dr in
                             sorted(pairs, key=lambda p: -abs(p[3]))[:8]],
        "stats_a": batch_stats(A), "stats_b": batch_stats(B),
    }


def _print_compare(r: dict) -> None:
    a, b = r["stats_a"], r["stats_b"]
    print(f"=== compare  A(baseline)={r['tag_a']}  vs  B(candidate)={r['tag_b']} ===")
    print(f"paired on {r['n_pairs']} shared setups (effective R; stood-down=0R; invalid runs excluded)\n")
    print(f"  mean ΔR (B−A) : {r['mean_dR']:+.3f}")
    print(f"  median ΔR     : {r['median_dR']:+.3f}")
    print(f"  better/worse/≈: {r['better']} / {r['worse']} / {r['equal']}")
    sp = f"{r['sign_p']:.4f}" if r["sign_p"] is not None else "—"
    print(f"  sign-test p   : {sp}  (two-sided, ties excluded)")
    print(f"  tail-guard    : top-3 winners = {int(r['top3_share']*100)}% of positive ΔR")
    print("  top movers    : " + ", ".join(f"{k[0]} {dr:+.2f}" for k, dr in r["top_contributors"]))
    print(f"\n  guardrails            A={r['tag_a']:<28} B={r['tag_b']}")
    al_a = f"${a['avg_loser']:.0f}" if a['avg_loser'] is not None else "—"
    al_b = f"${b['avg_loser']:.0f}" if b['avg_loser'] is not None else "—"
    kv_a = (f"{a['n_keys']}/{a['void']}/{a['ooc']}/{a['timeout']}/"
            f"{a['finalize_error']}/{a['no_decision_log']}/{a.get('agent_abandoned', 0)}")
    kv_b = (f"{b['n_keys']}/{b['void']}/{b['ooc']}/{b['timeout']}/"
            f"{b['finalize_error']}/{b['no_decision_log']}/{b.get('agent_abandoned', 0)}")
    print(f"    keys/void/ooc/t.out/fin-err/no-intent/abandon {kv_a:<20} {kv_b}")
    print(f"    stood-down          {a['stood']:<28} {b['stood']}")
    print(f"    avg loser           {al_a:<28} {al_b}")

    # verdict (the gate: broad, significant, not tail-driven, guardrails not worse)
    sig = r["sign_p"] is not None and r["sign_p"] < 0.05
    broad = r["median_dR"] >= 0 and r["top3_share"] <= 0.5
    guard_ok = (b["void"] <= a["void"] + 2 and b["ooc"] == 0 and b["timeout"] == 0
                and b["finalize_error"] == 0 and b["no_decision_log"] == 0
                and b.get("agent_abandoned", 0) == 0)
    if r["mean_dR"] > 0 and sig and broad and guard_ok:
        verdict = "✅ ACCEPT — B is broadly better and clears the gate."
    elif r["mean_dR"] > 0 and (sig or r["median_dR"] > 0):
        verdict = ("🟡 INVESTIGATE — positive but not a clean pass "
                   "(tail-driven, marginal significance, or a guardrail slipped).")
    else:
        verdict = "❌ REJECT — B is not a broad improvement over A."
    print(f"\n  VERDICT: {verdict}")
    if r["n_pairs"] < 80:
        print(f"  ⚠  only {r['n_pairs']} paired setups — use the 100-set for a promotable result.")


# ───────────────────────── repeat panels (LLM-variation aware) ──────────────

def _batch_stats(leaves: dict) -> dict:
    """One batch's deployment metrics, using the same effective-R definition as compare."""
    vals = list(leaves.values())
    effective = [(r, _effective_r(r)) for r in vals]
    eligible = [(r, value) for r, value in effective if value is not None]
    traded = [r for r, _ in eligible if r["traded"]]
    losers = [r["pnl"] for r in traded if not r["win"] and (r["pnl"] or 0) != 0]
    return {
        "keys": len(vals),
        "eligible": len(eligible),
        "pnl": round(sum(float(r["pnl"] or 0.0) for r, _ in eligible), 2),
        "effective_r": round(sum(value for _, value in eligible) / len(eligible), 3) if eligible else None,
        "trades": len(traded),
        "stood": sum(1 for r, value in eligible if value == 0.0 and not r["traded"]),
        "void": sum(1 for r in vals if r["void"] and not r["ooc"] and not r["timeout"]),
        "ooc": sum(1 for r in vals if r["ooc"]),
        "timeout": sum(1 for r in vals if r["timeout"]),
        "finalize_error": sum(1 for r in vals if r["finalize_error"]),
        "no_decision_log": sum(1 for r in vals if r["no_decision_log"]),
        "agent_abandoned": sum(1 for r in vals if r.get("agent_abandoned")),
        "avg_loser": round(sum(losers) / len(losers), 2) if losers else None,
    }


def _require_repeat_panel(tags: list[str], label: str) -> dict[str, dict]:
    if not tags:
        raise ValueError(f"{label} needs at least one batch tag")
    if len(set(tags)) != len(tags):
        raise ValueError(f"{label} contains a duplicate batch tag")
    leaves = {tag: _leaves_by_key(tag) for tag in tags}
    if any(not rows for rows in leaves.values()):
        missing = [tag for tag, rows in leaves.items() if not rows]
        raise ValueError(f"{label} has no session leaves: {', '.join(missing)}")

    first = tags[0]
    first_meta = _read_batch_meta(first)
    for tag in tags[1:]:
        _require_matching_batch_metadata(first, tag)
    skill_hashes = {_contract_key(_read_batch_meta(tag).get("skill_hash")) for tag in tags}
    if len(skill_hashes) != 1:
        raise ValueError(f"{label} batches use different skill hashes; repeat one exact version")
    for tag, rows in leaves.items():
        # Passing a batch to itself verifies that each repeat is internally stamped
        # with one execution and runner contract before panel aggregation.
        _require_matching_leaf_contract(rows, rows, "skill_hash", "skill hash")
        _require_matching_leaf_contract(rows, rows, "execution_contract", "frozen execution config")
        _require_matching_leaf_contract(rows, rows, "runner_contract", "runner contract")
    for tag in tags[1:]:
        _require_matching_leaf_contract(
            leaves[first], leaves[tag], "execution_contract", "frozen execution config",
        )
        _require_matching_leaf_contract(
            leaves[first], leaves[tag], "runner_contract", "runner contract",
        )
    return leaves


def _panel_summary(tags: list[str], label: str) -> dict:
    leaves = _require_repeat_panel(tags, label)
    runs = [{"tag": tag, **_batch_stats(leaves[tag])} for tag in tags]
    def distribution(field: str) -> dict:
        values = [r[field] for r in runs if r[field] is not None]
        return {
            "mean": round(_statistics.mean(values), 3) if values else None,
            "min": round(min(values), 3) if values else None,
            "max": round(max(values), 3) if values else None,
        }
    return {
        "label": label,
        "tags": tags,
        "runs": runs,
        "pnl": distribution("pnl"),
        "effective_r": distribution("effective_r"),
        "trades": distribution("trades"),
        "stood": distribution("stood"),
    }


def repeat_panel(tags: list[str]) -> dict:
    """Summarize repeated identical batches without treating one run as the truth."""
    return _panel_summary(tags, "panel")


def compare_repeats(tags_a: list[str], tags_b: list[str]) -> dict:
    """Compare repeated baseline and candidate panels on averaged per-setup R.

    Every batch inside a panel must be the same skill and contract. The two panels
    may differ only in skill hash, exactly like the existing single-run compare.
    """
    leaves_a = _require_repeat_panel(tags_a, "baseline panel")
    leaves_b = _require_repeat_panel(tags_b, "candidate panel")
    _require_matching_batch_metadata(tags_a[0], tags_b[0])
    _require_matching_leaf_contract(
        leaves_a[tags_a[0]], leaves_b[tags_b[0]], "execution_contract", "frozen execution config",
    )
    _require_matching_leaf_contract(
        leaves_a[tags_a[0]], leaves_b[tags_b[0]], "runner_contract", "runner contract",
    )

    shared = set.intersection(*(set(rows) for rows in [*leaves_a.values(), *leaves_b.values()]))
    pairs = []
    for key in sorted(shared):
        a_values = [_effective_r(leaves_a[tag][key]) for tag in tags_a]
        b_values = [_effective_r(leaves_b[tag][key]) for tag in tags_b]
        if any(value is None for value in [*a_values, *b_values]):
            continue
        r_a, r_b = _statistics.mean(a_values), _statistics.mean(b_values)
        pairs.append((key, r_a, r_b, r_b - r_a))
    deltas = [p[3] for p in pairs]
    up = sum(delta > 0.05 for delta in deltas)
    down = sum(delta < -0.05 for delta in deltas)
    positive = sorted((p for p in pairs if p[3] > 0), key=lambda p: -p[3])
    positive_sum = sum(p[3] for p in positive)
    return {
        "baseline": _panel_summary(tags_a, "baseline panel"),
        "candidate": _panel_summary(tags_b, "candidate panel"),
        "n_pairs": len(pairs),
        "mean_dR": round(_statistics.mean(deltas), 3) if deltas else 0.0,
        "median_dR": round(_statistics.median(deltas), 3) if deltas else 0.0,
        "better": up,
        "worse": down,
        "equal": len(deltas) - up - down,
        "sign_p": _sign_test_p(up, down),
        "top3_share": round(sum(p[3] for p in positive[:3]) / positive_sum, 2) if positive_sum else 0.0,
        "top_contributors": [(key, round(delta, 2)) for key, _, _, delta in
                             sorted(pairs, key=lambda p: -abs(p[3]))[:8]],
    }


def _print_repeat_panel(panel: dict) -> None:
    print(f"=== repeat panel ({len(panel['runs'])} runs) ===")
    for run in panel["runs"]:
        print(f"  {run['tag']}: P&L ${run['pnl']:.2f}, effR {run['effective_r']:.3f}, "
              f"trades {run['trades']}, stood down {run['stood']}, "
              f"void/ooc/timeout/error/no-intent {run['void']}/{run['ooc']}/{run['timeout']}/{run['finalize_error']}/{run['no_decision_log']}")
    print(f"  P&L range/mean: ${panel['pnl']['min']:.2f} to ${panel['pnl']['max']:.2f} "
          f"(mean ${panel['pnl']['mean']:.2f})")
    print(f"  effective-R range/mean: {panel['effective_r']['min']:.3f} to "
          f"{panel['effective_r']['max']:.3f} (mean {panel['effective_r']['mean']:.3f})")


def _print_compare_repeats(result: dict) -> None:
    print("=== repeat-aware compare ===")
    _print_repeat_panel(result["baseline"])
    _print_repeat_panel(result["candidate"])
    print(f"\npaired on {result['n_pairs']} setups using each setup's average R across runs")
    print(f"  mean ΔR (candidate − baseline): {result['mean_dR']:+.3f}")
    print(f"  median ΔR: {result['median_dR']:+.3f}")
    print(f"  better/worse/≈: {result['better']} / {result['worse']} / {result['equal']}")
    sign_p = f"{result['sign_p']:.4f}" if result["sign_p"] is not None else "—"
    print(f"  sign-test p: {sign_p}")
    print(f"  top-3 share of positive ΔR: {int(result['top3_share'] * 100)}%")
    print("  top movers: " + ", ".join(f"{key[0]} {delta:+.2f}" for key, delta in result["top_contributors"]))


# ───────────────────────── batch diagnostics ────────────────────────────────

def _diagnostic_grade(session: dict) -> str:
    """Reconstruct the 3.0 setup grade from frozen setup metadata.

    The agent's prose grade is not a reliable data field. This deliberately uses
    the explicit 3.0 rules so all control-panel runs are classified identically.
    """
    setup = session.get("setup") or {}
    try:
        price = float(setup["entry_px"])
        rvol = float(setup["rvol"])
        floating = float(setup["float_shares"])
        gap = float(setup["gap_pct"])
        entry_time = str(setup["entry_time"])
    except (KeyError, TypeError, ValueError):
        return "unknown"
    if price < 2 or price > 20 or rvol < 2:
        return "C"
    if rvol >= 5 and floating < 10_000_000 and gap > 10 and entry_time < "11:30":
        return "A"
    return "B"


def _diagnostic_group() -> dict:
    return {"setups": 0, "trades": 0, "wins": 0, "pnl": 0.0, "effective_r": 0.0}


def _add_diagnostic_row(group: dict, pnl: dict) -> None:
    group["setups"] += 1
    traded = bool(pnl.get("traded"))
    group["trades"] += int(traded)
    group["wins"] += int(traded and bool(pnl.get("win")))
    group["pnl"] += float(pnl.get("realized_pnl") or 0.0)
    if traded and isinstance(pnl.get("r_multiple"), (int, float)):
        group["effective_r"] += float(pnl["r_multiple"])


def _finalize_diagnostic_groups(groups: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for name, group in sorted(groups.items()):
        setups, trades = group["setups"], group["trades"]
        out[name] = {
            **group,
            "pnl": round(group["pnl"], 2),
            "effective_r": round(group["effective_r"] / setups, 3) if setups else None,
            "win_rate": round(100 * group["wins"] / trades, 1) if trades else None,
        }
    return out


def _in_position_mfe(sdir: Path, actions: list[dict]) -> Optional[float]:
    """MFE from ticks while a first position was actually open, never post-exit bars."""
    entry = next((a for a in actions if a.get("side") == "buy"), None)
    if entry is None:
        return None
    final_exit = next((a for a in reversed(actions)
                       if a.get("side") == "sell" and a.get("position_after") == 0), None)
    entry_i = int(entry["i"])
    final_i = int(final_exit["i"]) if final_exit is not None else None
    ticks = []
    try:
        for line in (sdir / "stream.jsonl").read_text().splitlines():
            row = json.loads(line)
            if row.get("type") != "tick" or int(row.get("i", -1)) <= entry_i:
                continue
            if final_i is not None and int(row["i"]) > final_i:
                continue
            # The engine resolves protective stops before targets on an ambiguous
            # bar, so its high is not usable MFE when the final exit is that stop.
            if (final_exit is not None and int(row["i"]) == final_i
                    and "protective stop" in str(final_exit.get("reason", ""))):
                continue
            ticks.append(float(row["h"]))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return round(max(ticks) - float(entry["price"]), 4) if ticks else None


def _trade_interval_for_portfolio(
    session: dict,
    pnl: dict,
    actions: list[dict],
) -> Optional[dict]:
    """Extract one executed position interval for a portfolio-control shadow.

    Batch leaves remain intentionally independent.  This helper does not invent
    a portfolio P&L; it provides the minimum causal control needed to expose
    same-ticker overlap: once a prior fill is open, a later signal in that
    ticker cannot open a second position.  Action dates are required because
    setup dates alone do not establish whether an arm was actually filled.
    """
    if not pnl.get("traded"):
        return None
    buys = [a for a in actions if a.get("side") == "buy"]
    exits = [
        a for a in actions
        if a.get("side") == "sell" and a.get("position_after") == 0
    ]
    if not buys or not exits:
        return None
    entry, exit_ = buys[0], exits[-1]
    ticker = str(session.get("ticker") or "").upper()
    setup = str(session.get("historical_date") or "")
    entry_day, exit_day = entry.get("date"), exit_.get("date")
    if not ticker or not setup or not entry_day or not exit_day:
        return None
    # ISO dates are deliberately compared as strings: the engine emits YYYY-MM-DD
    # and that preserves chronological order without locale/time-zone ambiguity.
    if not isinstance(entry_day, str) or not isinstance(exit_day, str) or entry_day > exit_day:
        return None
    risk = pnl.get("initial_risk")
    return {
        "ticker": ticker,
        "setup": setup,
        "entry_day": entry_day,
        "exit_day": exit_day,
        "r_multiple": float(pnl.get("r_multiple") or 0.0),
        "realized_pnl": float(pnl.get("realized_pnl") or 0.0),
        "initial_risk": float(risk) if isinstance(risk, (int, float)) else None,
    }


def _ticker_exclusive_portfolio_control(
    intervals: list[dict],
    *,
    setup_count: int,
    unresolved_trades: int,
) -> dict:
    """Causal one-open-position-per-ticker shadow portfolio summary.

    For each ticker, fills are processed in entry-date order.  A later fill on
    or before the prior position's exit date is skipped.  This is deliberately
    conservative on a same-day turnover: independent daily leaves lack a
    globally ordered close, so counting both would reintroduce the ambiguity
    this control is meant to reveal.
    """
    accepted: list[dict] = []
    skipped: list[dict] = []
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for interval in intervals:
        by_ticker[interval["ticker"]].append(interval)
    for ticker, rows in by_ticker.items():
        occupied_until: Optional[str] = None
        for row in sorted(rows, key=lambda r: (r["entry_day"], r["setup"])):
            if occupied_until is not None and row["entry_day"] <= occupied_until:
                skipped.append({
                    "ticker": ticker,
                    "setup": row["setup"],
                    "entry_day": row["entry_day"],
                    "exit_day": row["exit_day"],
                    "r_multiple": round(row["r_multiple"], 3),
                    "reason": f"ticker already open through {occupied_until}",
                })
                continue
            accepted.append(row)
            occupied_until = row["exit_day"]

    # Conservative concurrency: an entry and a close printed on the same daily
    # timestamp count as overlapping until a true portfolio event ordering exists.
    events: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for row in intervals:
        events[row["entry_day"]].append(("open", row))
        events[row["exit_day"]].append(("close", row))
    open_positions: dict[tuple[str, str], dict] = {}
    max_positions = 0
    max_risk = 0.0
    max_risk_known = False
    for day in sorted(events):
        for kind, row in events[day]:
            if kind == "open":
                open_positions[(row["ticker"], row["setup"])] = row
        max_positions = max(max_positions, len(open_positions))
        known_risks = [r["initial_risk"] for r in open_positions.values()]
        if all(risk is not None for risk in known_risks):
            max_risk_known = True
            max_risk = max(max_risk, sum(known_risks))
        for kind, row in events[day]:
            if kind == "close":
                open_positions.pop((row["ticker"], row["setup"]), None)

    return {
        "available": bool(intervals) and unresolved_trades == 0,
        "setup_count": setup_count,
        "raw_trades": len(intervals) + unresolved_trades,
        "unresolved_trades": unresolved_trades,
        "ticker_exclusive_trades": len(accepted),
        "skipped_overlapping_trades": len(skipped),
        "ticker_exclusive_pnl": round(sum(r["realized_pnl"] for r in accepted), 2),
        "ticker_exclusive_effective_r": (
            round(sum(r["r_multiple"] for r in accepted) / setup_count, 3)
            if setup_count else None
        ),
        "max_independent_concurrent_positions": max_positions,
        "max_independent_initial_risk": round(max_risk, 2) if max_risk_known else None,
        "skipped": skipped,
    }


def diagnostics(tag: str) -> dict:
    """Describe frozen batch behavior by grade, entry, exit, adds, and in-trade MFE."""
    chosen: dict[tuple, tuple[Path, dict, dict]] = {}
    for sdir in _sessions_for_batch(tag):
        session = recorder._load_json(sdir / "session.json", {}) or {}
        if recorder._is_infra_fail(session) or session.get("void"):
            continue
        key = (session.get("ticker"), session.get("historical_date"))
        if key == (None, None):
            continue
        pnl = recorder._load_json(sdir / "pnl.json", {}) or {}
        previous = chosen.get(key)
        if previous is None or (session.get("real_run_ts") or "") > (previous[1].get("real_run_ts") or ""):
            chosen[key] = (sdir, session, pnl)

    by_grade: dict[str, dict] = defaultdict(_diagnostic_group)
    by_entry: dict[str, dict] = defaultdict(_diagnostic_group)
    by_exit: dict[str, dict] = defaultdict(_diagnostic_group)
    adds_attempted = adds_filled = 0
    in_position_mfes: list[float] = []
    portfolio_intervals: list[dict] = []
    unresolved_portfolio_trades = 0

    for sdir, session, pnl in chosen.values():
        _add_diagnostic_row(by_grade[_diagnostic_grade(session)], pnl)
        if not pnl.get("traded"):
            continue
        actions = recorder._load_json(sdir / "actions.json", []) or []
        interval = _trade_interval_for_portfolio(session, pnl, actions)
        if interval is None:
            unresolved_portfolio_trades += 1
        else:
            portfolio_intervals.append(interval)
        decisions = []
        try:
            decisions = [json.loads(line) for line in (sdir / "decisions.jsonl").read_text().splitlines() if line]
        except (OSError, json.JSONDecodeError):
            pass
        adds_attempted += sum(d.get("action") == "ADD_CLOSE" for d in decisions)
        adds_filled += sum(a.get("action") == "ADD" for a in actions)

        entry = next((a for a in actions if a.get("side") == "buy"), {})
        entry_kind = "armed buy-stop" if "armed buy-stop" in str(entry.get("reason", "")) else "confirmed close"
        _add_diagnostic_row(by_entry[entry_kind], pnl)
        exit_action = next((a for a in reversed(actions) if a.get("side") == "sell" and a.get("position_after") == 0), {})
        reason = str(exit_action.get("reason", ""))
        if "protective stop" in reason or "armed-entry/stop" in reason:
            exit_kind = "protective stop"
        elif "auto-flat" in reason:
            exit_kind = "session-end exit"
        elif "close-confirmed" in reason:
            exit_kind = "close-confirmed exit"
        else:
            exit_kind = "other exit"
        _add_diagnostic_row(by_exit[exit_kind], pnl)
        mfe = _in_position_mfe(sdir, actions)
        if mfe is not None:
            in_position_mfes.append(mfe)

    return {
        "tag": tag,
        "setups": len(chosen),
        "by_grade": _finalize_diagnostic_groups(by_grade),
        "by_entry": _finalize_diagnostic_groups(by_entry),
        "by_exit": _finalize_diagnostic_groups(by_exit),
        "adds": {"attempted": adds_attempted, "filled": adds_filled},
        "in_position_mfe_per_share": {
            "n": len(in_position_mfes),
            "mean": round(_statistics.mean(in_position_mfes), 4) if in_position_mfes else None,
            "median": round(_statistics.median(in_position_mfes), 4) if in_position_mfes else None,
        },
        "ticker_exclusive_portfolio_control": _ticker_exclusive_portfolio_control(
            portfolio_intervals,
            setup_count=len(chosen),
            unresolved_trades=unresolved_portfolio_trades,
        ),
    }


def portfolio_replay(
    tag: str,
    *,
    max_open_positions: int = 3,
    max_open_risk: float = 1_500.0,
    max_gross_notional: float = 50_000.0,
    out: str | Path | None = None,
) -> tuple[dict, Path]:
    """Replay one completed deterministic cup-handle batch as a shared portfolio.

    Leaf sessions are selected by their immutable ``(ticker, historical_date)``
    identity, retaining the newest finalized run if an operator re-ran a leaf.
    Invalid/void/infrastructure-failed leaves are excluded just as they are from
    the regular batch report.  The replay module independently checks the
    actions-to-P&L identity before it permits a result.
    """
    from .strategies.cup_handle import portfolio as cup_portfolio

    meta = _read_batch_meta(tag)
    if not meta:
        raise ValueError(f"unknown batch tag {tag!r}: missing batch.json")
    if meta.get("strategy") != "cup_handle":
        raise ValueError(
            f"portfolio replay is currently cup_handle-only; batch {tag!r} has "
            f"strategy={meta.get('strategy')!r}"
        )
    if meta.get("decision_source") != "deterministic_policy":
        raise ValueError(
            "portfolio replay requires a deterministic-policy batch; "
            f"batch {tag!r} has decision_source={meta.get('decision_source')!r}"
        )
    if meta.get("status") != "complete":
        raise ValueError(
            f"portfolio replay requires a completed batch; {tag!r} has status={meta.get('status')!r}"
        )

    chosen: dict[tuple[str, str], tuple[Path, dict, dict]] = {}
    for sdir in _sessions_for_batch(tag):
        session = recorder._load_json(sdir / "session.json", {}) or {}
        if (session.get("status") != "complete" or recorder._is_infra_fail(session)
                or session.get("void")):
            continue
        ticker = str(session.get("ticker") or "").upper()
        setup_day = str(session.get("historical_date") or "")
        if not ticker or not setup_day:
            continue
        pnl = recorder._load_json(sdir / "pnl.json", {}) or {}
        key = (ticker, setup_day)
        previous = chosen.get(key)
        if previous is None or (session.get("real_run_ts") or "") > (previous[1].get("real_run_ts") or ""):
            chosen[key] = (sdir, session, pnl)
    if not chosen:
        raise ValueError(f"batch {tag!r} has no finalized, replayable leaf sessions")
    planned = meta.get("planned")
    repeats = meta.get("repeats")
    if (not isinstance(planned, int) or planned < 1
            or not isinstance(repeats, int) or repeats < 1 or planned % repeats):
        raise ValueError(
            f"batch {tag!r} has invalid planned/repeats metadata: "
            f"planned={planned!r}, repeats={repeats!r}"
        )
    expected_setups = planned // repeats
    if len(chosen) != expected_setups:
        raise ValueError(
            f"batch {tag!r} is incomplete for portfolio replay: expected {expected_setups} "
            f"unique setup leaves from planned={planned}, repeats={repeats}; found {len(chosen)} "
            "complete, non-void, non-infrastructure-failed leaves"
        )

    leaves = []
    for sdir, session, pnl in chosen.values():
        leaves.append({
            "sid": sdir.name,
            "ticker": session.get("ticker"),
            "setup_day": session.get("historical_date"),
            "pnl": pnl,
            "actions": recorder._load_json(sdir / "actions.json", []) or [],
        })
    config = cup_portfolio.PortfolioConfig(
        max_open_positions=max_open_positions,
        max_open_risk=max_open_risk,
        max_gross_notional=max_gross_notional,
    )
    result = cup_portfolio.replay(leaves, config)
    result["source"] = {
        "batch_tag": tag,
        "strategy": meta.get("strategy"),
        "decision_source": meta.get("decision_source"),
        "research_tier": meta.get("research_tier"),
        "entry_db": meta.get("entry_db"),
        "testset_hash": meta.get("testset_hash"),
        "skill_version": meta.get("version"),
        "leaf_sessions": sorted(row["sid"] for row in leaves),
    }
    artifact = Path(out) if out else BATCH_LOGS / tag / "portfolio.json"
    artifact = artifact.expanduser().resolve()
    atomic_write_json(artifact, result, indent=2)
    return result, artifact


def _print_diagnostics(result: dict) -> None:
    print(f"=== diagnostics — {result['tag']} ({result['setups']} setups) ===")
    for label, rows in (("grade", result["by_grade"]), ("entry", result["by_entry"]), ("final exit", result["by_exit"])):
        print(f"\n  by {label}")
        print("  group                     setups trades  win%       P&L   effR")
        for name, row in rows.items():
            win = f"{row['win_rate']:.1f}%" if row["win_rate"] is not None else "—"
            eff = f"{row['effective_r']:.3f}" if row["effective_r"] is not None else "—"
            print(f"  {name:<25} {row['setups']:>6} {row['trades']:>6} {win:>6} ${row['pnl']:>9.2f} {eff:>6}")
    adds = result["adds"]
    mfe = result["in_position_mfe_per_share"]
    print(f"\n  adds attempted/filled: {adds['attempted']}/{adds['filled']}")
    print(f"  in-position MFE/share: n={mfe['n']}, mean={mfe['mean']}, median={mfe['median']}")
    portfolio = result["ticker_exclusive_portfolio_control"]
    status = "available" if portfolio["available"] else "incomplete action-date evidence"
    print(
        "  ticker-exclusive control: "
        f"{portfolio['ticker_exclusive_trades']}/{portfolio['raw_trades']} trades, "
        f"skipped overlap={portfolio['skipped_overlapping_trades']}, "
        f"P&L ${portfolio['ticker_exclusive_pnl']:.2f}, "
        f"effR {portfolio['ticker_exclusive_effective_r']} ({status})"
    )


# ───────────────────────────── CLI ──────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.batchsim",
        description="Batch backtest a pinned TRADE_SIMULATOR version over a fixed setup set.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build-set", help="write a stratified holdout under batch/<strategy>/")
    pb.add_argument("--strategy", default="warrior",
                    help="strategy family (warrior, cup_handle, …); picks default --db/--out")
    pb.add_argument("--n", type=int, default=30)
    pb.add_argument("--all", action="store_true",
                    help="select every eligible setup after filters instead of a sample; "
                    "use with --start/--end for a complete chronological cohort")
    pb.add_argument("--seed", type=int, default=13)
    pb.add_argument("--start", default=None, metavar="YYYY-MM-DD",
                    help="inclusive setup-date lower bound for an immutable chronological cohort")
    pb.add_argument("--end", default=None, metavar="YYYY-MM-DD",
                    help="inclusive setup-date upper bound for an immutable chronological cohort")
    pb.add_argument("--out", default=None,
                    help="output path (default: batch/<strategy>/testset.json)")
    pb.add_argument("--db", default=None,
                    help="entries SQLite (default: that family's entries.db)")
    pb.add_argument("--exclude", action="append", default=[],
                    help="testset JSON whose (ticker,date) keys to leave out; repeatable. "
                    "Pass the dev set to carve a disjoint holdout (see IMPROVING.md §6).")
    pb.add_argument("--unique-ticker", action="store_true",
                    help="one setup per ticker (most-recent date) — a single-entry, "
                    "max-diversity set with no repeated tickers.")
    pb.add_argument("--exploratory", action="store_true",
                    help="cup_handle only: allow a non-PIT source for an explicitly "
                    "non-promotable exploratory set. Such a set is rejected by batch run.")

    pr = sub.add_parser("run", help="spawn agents for one version/batch")
    pr.add_argument("--strategy", default="warrior",
                    help="strategy family (warrior, cup_handle, …); selects skill tree + DB")
    pr.add_argument("--version", help="skill version to pin (from that family's trade_skills/); "
                    "defaults to the current base version. On --resume, recovered from "
                    "the batch if omitted.")
    pr.add_argument("--model", default=None,
                    help=f"hermes model id (default: {DEFAULT_MODEL}). "
                    "On --resume, recovered from the batch if omitted.")
    pr.add_argument("--set", dest="testset", default=None,
                    help="testset name or path (default: batch/<strategy>/testset.json). "
                    "Bare names like testset_30 resolve under batch/<strategy>/. "
                    "On --resume, recovered from the batch if omitted.")
    pr.add_argument("--db", default=None,
                    help="entries SQLite bound to this batch (default: strategy database). "
                    "Use the same PIT corpus that produced --set; resume recovers it.")
    pr.add_argument("--parallel", type=int, default=3,
                    help="concurrent hermes agents (default: 3)")
    pr.add_argument("--repeats", type=int, default=1,
                    help="runs per setup (default: 1)")
    pr.add_argument("--tag", help="batch cohort tag (default: <version>-<timestamp>). "
                    "Optional when --session identifies an existing batch to resume.")
    pr.add_argument("--session", help="top-level session id (…-BATCH-<hex>) to (re)join. "
                    "With --resume you can pass this ALONE (no --tag) to resume that "
                    "batch; the tag, version, model and testset are recovered from it.")
    pr.add_argument("--timeout", type=int, default=900, help="per-setup seconds")
    pr.add_argument("--retries", type=int, default=_DEFAULT_RETRIES,
                    help="extra attempts on a timeout before recording it as failed "
                         f"(default {_DEFAULT_RETRIES}; 0 = no retry)")
    pr.add_argument("--max-reentries", type=int, default=1,
                    help="§C re-entry budget: how many re-entries the agent may take after "
                         "its first round trip (default 1 = classic single re-entry; 0 = "
                         "none; higher = keep taking qualifying second legs). Recorded in "
                         "batch.json; a resume inherits it. Hold constant across an A/B pair.")
    pr.add_argument("--trade-until", metavar="HH:MM",
                    help="cutoff time in ET: take NO new or re-entry at/after this time (a "
                         "flat position then ends the run). Default: no cutoff — stop once the "
                         "re-entry budget is spent. Recorded in batch.json; a resume inherits it.")
    pr.add_argument("--no-reentry", action="store_true",
                    help="shorthand for --max-reentries 0 (agent stops as soon as it is flat).")
    pr.add_argument("--resume", action="store_true", help="skip already-finalized items")
    pr.add_argument("--dry-run", action="store_true",
                    help="print the hermes commands without spawning agents")
    pr.add_argument("--exploratory", action="store_true",
                    help="cup_handle only: permit an unproven/current-universe testset for "
                    "deterministic diagnostics. The batch is stamped non-promotable and "
                    "cannot be used by the comparison gate.")

    pa = sub.add_parser("audit", help="scan transcripts; void peeking sessions")
    pa.add_argument("--tag", required=True)

    prep = sub.add_parser("report", help="profitability for one batch cohort")
    prep.add_argument("--tag", required=True)
    prep.add_argument("--format", choices=["table", "json"], default="table")

    pc = sub.add_parser("compare", help="paired promotion gate: candidate B vs baseline A")
    pc.add_argument("--a", required=True, help="baseline batch tag (accepted version)")
    pc.add_argument("--b", required=True, help="candidate batch tag")
    pc.add_argument("--format", choices=["table", "json"], default="table")

    prp = sub.add_parser("repeat-report", help="summarize repeated identical batch runs")
    prp.add_argument("--tag", action="append", required=True,
                     help="batch tag; repeat for each run in the panel")
    prp.add_argument("--format", choices=["table", "json"], default="table")

    pcr = sub.add_parser("compare-repeats", help="compare repeated candidate and baseline panels")
    pcr.add_argument("--a", action="append", required=True,
                     help="baseline batch tag; repeat for every baseline run")
    pcr.add_argument("--b", action="append", required=True,
                     help="candidate batch tag; repeat for every candidate run")
    pcr.add_argument("--format", choices=["table", "json"], default="table")

    pd = sub.add_parser("diagnostics", help="behavior breakdown for one completed batch")
    pd.add_argument("--tag", required=True)
    pd.add_argument("--format", choices=["table", "json"], default="table")

    ppf = sub.add_parser(
        "portfolio",
        help="chronologically replay a deterministic cup-handle batch under shared limits",
    )
    ppf.add_argument("--tag", required=True)
    ppf.add_argument("--max-open-positions", type=int, default=3,
                     help="maximum simultaneous positions (default: 3)")
    ppf.add_argument("--max-open-risk", type=float, default=1_500.0,
                     help="maximum simultaneous initial risk in dollars (default: 1500)")
    ppf.add_argument("--max-gross-notional", type=float, default=50_000.0,
                     help="maximum simultaneous long gross notional in dollars (default: 50000)")
    ppf.add_argument("--out", default=None,
                     help="artifact path (default: simulations/_batch/<tag>/portfolio.json)")
    ppf.add_argument("--format", choices=["table", "json"], default="table")

    pn = sub.add_parser("new-version", help="fork a new, unsealed candidate skill file")
    pn.add_argument("--strategy", default="warrior",
                    help="strategy family whose skill tree to fork")
    pn.add_argument("--from", dest="from_version", required=True,
                    help="existing (sealed) version to copy from")
    pn.add_argument("--to", dest="to_version", default=None,
                    help="new version name (default: next free patch after --from)")

    pp = sub.add_parser("promote", help="point unpinned runs at an already-run version")
    pp.add_argument("--strategy", default="warrior",
                    help="strategy family whose base pointer to move")
    pp.add_argument("--version", required=True)

    pc_cur = sub.add_parser("current", help="print the current base version")
    pc_cur.add_argument("--strategy", default="warrior")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.cmd == "build-set":
        strategy_id = (getattr(args, "strategy", None) or "warrior").strip().lower().replace("-", "_")
        _, _, strategy_db, _ = _strategy_paths(strategy_id)
        db_path = Path(args.db) if args.db else strategy_db
        out_path = Path(args.out) if args.out else default_testset_path(strategy_id)
        exclude: set = set()
        for p in args.exclude:
            exclude |= _load_keys(Path(p))
        try:
            start_date = date.fromisoformat(args.start) if args.start else None
            end_date = date.fromisoformat(args.end) if args.end else None
        except ValueError as exc:
            raise SystemExit("--start/--end must be YYYY-MM-DD") from exc
        setups = build_set(
            n=args.n, seed=args.seed, db=db_path, exclude=exclude,
            unique_ticker=args.unique_ticker,
            causal_only=(strategy_id == "cup_handle"),
            require_research_provenance=(strategy_id == "cup_handle" and not args.exploratory),
            require_exact=True,
            start_date=start_date, end_date=end_date, all_rows=args.all,
        )
        research_provenance = (
            research_provenance_for_setups(db_path, setups)
            if strategy_id == "cup_handle" and not args.exploratory else None
        )
        write_testset(
            setups, out_path, args.seed, research_provenance=research_provenance,
            cohort={
                "selection": "all_eligible_rows" if args.all else "stratified_sample",
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
                "after": "09:30",
                "source_entry_db": str(db_path.resolve()),
            },
        )
        extra = f" (excluded {len(exclude)} keys)" if exclude else ""
        if args.unique_ticker:
            extra += f" ({len({s['ticker'] for s in setups})} unique tickers)"
        suffix = (
            " [PIT provenance sealed]" if research_provenance
            else (" [exploratory only]" if strategy_id == "cup_handle" else "")
        )
        print(f"wrote {len(setups)} setups → {out_path}{extra}  [strategy={strategy_id}]{suffix}")
    elif args.cmd == "run":
        run(args.version, model=args.model,
            testset=args.testset,  # bare name or path; resolved inside run()
            parallel=args.parallel, repeats=args.repeats, tag=args.tag,
            timeout=args.timeout, retries=args.retries,
            max_reentries=0 if args.no_reentry else args.max_reentries,
            trade_until=args.trade_until,
            resume=args.resume, dry_run=args.dry_run,
            session=args.session,
            strategy=getattr(args, "strategy", None) or "warrior",
            exploratory=args.exploratory,
            db=args.db)
    elif args.cmd == "audit":
        n = audit(args.tag)
        print(f"voided {n} session(s) in batch {args.tag}")
    elif args.cmd == "report":
        rows = recorder.report_by_version(batch=args.tag)
        if args.format == "json":
            print(json.dumps(rows, indent=2))
        else:
            _print_batch_report(args.tag)
    elif args.cmd == "compare":
        result = compare(args.a, args.b)
        if args.format == "json":
            print(json.dumps(result, indent=2, default=list))
        else:
            _print_compare(result)
    elif args.cmd == "repeat-report":
        result = repeat_panel(args.tag)
        if args.format == "json":
            print(json.dumps(result, indent=2, default=list))
        else:
            _print_repeat_panel(result)
    elif args.cmd == "compare-repeats":
        result = compare_repeats(args.a, args.b)
        if args.format == "json":
            print(json.dumps(result, indent=2, default=list))
        else:
            _print_compare_repeats(result)
    elif args.cmd == "diagnostics":
        result = diagnostics(args.tag)
        if args.format == "json":
            print(json.dumps(result, indent=2, default=list))
        else:
            _print_diagnostics(result)
    elif args.cmd == "portfolio":
        result, artifact = portfolio_replay(
            args.tag,
            max_open_positions=args.max_open_positions,
            max_open_risk=args.max_open_risk,
            max_gross_notional=args.max_gross_notional,
            out=args.out,
        )
        if args.format == "json":
            print(json.dumps(result, indent=2, default=list))
        else:
            summary = result["summary"]
            print(f"=== portfolio replay — {args.tag} ===")
            print(
                f"accepted {summary['accepted_trades']}/{summary['raw_trades']} trades "
                f"({summary['skipped_entries']} skipped); "
                f"realized P&L ${summary['portfolio_realized_pnl']:.2f}; "
                f"effective R {summary['portfolio_effective_r']:.3f}"
            )
            print(
                f"peaks: {summary['max_open_positions']} positions, "
                f"${summary['max_open_risk']:.2f} initial risk, "
                f"${summary['max_gross_notional']:.2f} gross; "
                f"realized-P&L max drawdown ${summary['realized_pnl_max_drawdown']:.2f}"
            )
            print(f"artifact: {artifact}")
    elif args.cmd == "new-version":
        reg, tdir, _, _ = _strategy_paths(getattr(args, "strategy", None) or "warrior")
        dest = skillmeta.new_version(
            args.from_version, args.to_version, trade_skills_dir=tdir
        )
        print(f"forked {args.from_version} → {dest} (unsealed — edit freely, "
              f"not registered until first run)")
    elif args.cmd == "promote":
        reg, _, _, _ = _strategy_paths(getattr(args, "strategy", None) or "warrior")
        skillmeta.set_base(args.version, registry_path=reg)
        print(f"base version → {args.version} (unpinned runs now use this)")
    elif args.cmd == "current":
        reg, _, _, _ = _strategy_paths(getattr(args, "strategy", None) or "warrior")
        print(skillmeta.base_version(reg) or "(no base version set)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
