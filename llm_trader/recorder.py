"""Session recorder — turns a TRADE_SIMULATOR run into web-viewable artifacts.

A simulation session is a folder
``simulations/{YYYYMMDDHHMMSS}-{TICKER}-{hex}/`` (real wall-clock ts + a random
suffix so concurrent same-ticker runs can't collide) holding the raw
replay stream, the agent's per-turn decisions, and — after ``finalize`` — a set of
JSON files the viewer renders. See ``SIMULATION_VIEWER_SPEC.md`` for the contract.

Lifecycle (used by the skill):

    # 1. start of run
    python3 -m trading.llm_trader.recorder init \
        --ticker EVTV --date 2026-01-13 --seed 7 --profile small
    #   -> prints the session dir; point `replay --out-file <dir>/stream.jsonl` at it

    # 2. each turn (append one decision *intent*)
    python3 -m trading.llm_trader.recorder log --session <dir> \
        --record '{"i":3,"time":"10:23","thought":"…","action":"SCALE_LIMIT",
                   "target":3.90,"fraction":0.333}'

    # 3. end of run (build all artifacts)
    python3 -m trading.llm_trader.recorder finalize --session <dir>

The P&L / position engine is deterministic.  New major skills record intents and
the engine, not the agent, derives fills, position size, costs, and P&L.  Legacy
sessions retain their reported-fill format for historical readability.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import skillmeta
from .config import DATA_DIR
from .execution import EXECUTION_MODEL, ExecutionConfig, ExecutionEngine, INTENT_ACTIONS
from .fsutils import atomic_write_json, atomic_write_text, file_lock
from .indicators import DAILY_REPLAY_REQUIRED_INDICATORS
from .streamio import epoch_et as _epoch_et
from .streamio import parse_stream as _parse_stream
from .streamio import read_jsonl as _read_jsonl

logger = logging.getLogger("llm_trader.recorder")

SCHEMA_VERSION = 1
# The one source of truth for the sessions tree. Other modules (viewer, batchsim,
# step) import this rather than re-deriving the path, so they can never disagree
# about where sessions live.
SIM_ROOT = DATA_DIR.parent / "simulations"
# The skill registry + experiment log. Used to classify each session's rule-set
# version as the accepted base, a pending candidate, or a rejected experiment so
# the viewer can tint its row.
# Warrior skill tree (default family). Other families use strategies/<id>/skills/.
SKILLS_DIR = DATA_DIR.parent / "strategies" / "warrior" / "skills"

# Fields copied from stream meta → session.setup on finalize / live view.
_SETUP_META_KEYS = (
    "entry_time", "entry_px", "anchor_px", "gap_pct", "rvol", "float_shares",
    "prior_close", "prior_high", "prior_low", "pm_high", "pm_low",
    "session_end", "reason",
    # multi-strategy / swing plan levels
    "strategy", "pattern", "horizon", "bar_resolution",
    "stop_px", "target1_px", "target2_px", "atr", "handle_high",
    "cup_depth_px", "cup_depth_pct",
)


def _strategy_of(session: dict) -> str:
    """Best-effort strategy id from a session.json dict."""
    return (
        session.get("strategy")
        or (session.get("config") or {}).get("strategy")
        or (session.get("skill") or {}).get("strategy")
        or "warrior"
    )


def _setup_from_meta(meta: Optional[dict]) -> dict:
    if not meta:
        return {}
    return {k: meta.get(k) for k in _SETUP_META_KEYS if meta.get(k) is not None}


def _is_multi_day_session(session: dict, meta: Optional[dict] = None) -> bool:
    """True when the sealed stream is multi-day daily (not a same-day 1-min tape)."""
    meta = meta or {}
    cfg = session.get("config") or {}
    skill = session.get("skill") or {}
    horizon = (
        cfg.get("horizon")
        or skill.get("horizon")
        or meta.get("horizon")
        or ""
    )
    bar_res = (
        cfg.get("bar_resolution")
        or skill.get("bar_resolution")
        or meta.get("bar_resolution")
        or ""
    )
    strategy = _strategy_of(session) or meta.get("strategy") or ""
    if str(horizon).lower() in ("multi_day", "multiday", "swing"):
        return True
    if str(bar_res).lower() in ("1day", "daily"):
        return True
    if strategy and strategy not in ("warrior", "mixed"):
        # Non-warrior families default to multi-day chart handling.
        return str(cfg.get("same_day_only", True)).lower() in ("0", "false", "no")
    return False


def _daily_indicator_integrity_errors(session: dict, meta: dict, ticks: list[dict]) -> list[str]:
    """Return unavailable required daily fields; empty means the stream is tradable.

    Replay prevents these states before a session begins.  Keeping this verifier at
    the recorder boundary makes hand-written streams, old tooling, and direct
    JSONL edits fail closed too.
    """
    if not _is_multi_day_session(session, meta):
        return []
    missing: dict[str, list[dict]] = defaultdict(list)
    for tick in ticks:
        for field in DAILY_REPLAY_REQUIRED_INDICATORS:
            value = tick.get(field)
            unavailable = value is None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                unavailable = unavailable or not math.isfinite(float(value))
            if unavailable:
                missing[field].append(tick)
    errors: list[str] = []
    for field, affected in missing.items():
        first = affected[0]
        errors.append(
            f"{field} unavailable on {len(affected)} daily bar(s), first "
            f"i={first.get('i')} date={first.get('date')}"
        )
    return errors


def _causal_plan_integrity_errors(
    session: dict,
    meta: dict,
    ticks: list[dict],
    *,
    allow_pending_setup: bool = False,
) -> list[str]:
    """Verify that a causal daily session actually received its scanner plan.

    A one-tick gateway reveals and records the lookback before the setup bar.  During
    that phase a plan is correctly absent; once the stream reaches the planned date,
    though, its absence is a hard integrity failure.  Finalization/audit always use
    the strict form because their streams are complete.
    """
    skill = session.get("skill") or {}
    required = skill.get("arm_on_scanner_plan_required")
    if not (required is True or str(required).strip().lower() in {"1", "true", "yes"}):
        return []
    setup_ticks = [tick for tick in ticks if tick.get("is_setup_day")]
    if not setup_ticks and allow_pending_setup:
        planned_date = str(meta.get("date") or session.get("historical_date") or "")
        # ISO date strings sort chronologically.  Until the planned setup date is
        # visible, no scanner_plan is expected (and auto-observe is safe).
        if planned_date and all(str(tick.get("date") or "") < planned_date for tick in ticks):
            return []
    if len(setup_ticks) != 1:
        return [
            f"causal scanner plan requires exactly one setup bar; found {len(setup_ticks)}"
        ]
    plan = setup_ticks[0].get("scanner_plan")
    if not isinstance(plan, dict):
        return [
            "causal scanner_plan is missing from the setup bar; entries source is stale "
            "or a research label, not a prebreak arm"
        ]
    required_fields = (
        "signal_as_of", "trigger", "stop", "target1", "target2", "atr",
        "cup_depth_px", "arm_expiry_bars", "max_entry_gap_atr",
    )
    missing = [field for field in required_fields if plan.get(field) is None]
    return (["causal scanner_plan missing field(s): " + ", ".join(missing)] if missing else [])


def daily_stream_integrity_errors(session_dir: str | Path, session: Optional[dict] = None) -> list[str]:
    """Check a persisted stream without changing it (used by batch audit)."""
    sdir = Path(session_dir)
    session = session or _load_json(sdir / "session.json", {}) or {}
    if not _is_multi_day_session(session):
        return []
    meta, ticks, _end = _parse_stream(sdir / "stream.jsonl")
    if meta is None:
        return ["stream has no meta record"]
    return _daily_indicator_integrity_errors(session, meta, ticks)


def stream_integrity_errors(session_dir: str | Path, session: Optional[dict] = None) -> list[str]:
    """All fail-closed stream checks used by batch audit."""
    sdir = Path(session_dir)
    session = session or _load_json(sdir / "session.json", {}) or {}
    if not _is_multi_day_session(session):
        return []
    meta, ticks, _end = _parse_stream(sdir / "stream.jsonl")
    if meta is None:
        return ["stream has no meta record"]
    return (
        _daily_indicator_integrity_errors(session, meta, ticks)
        + _causal_plan_integrity_errors(session, meta, ticks)
    )

# default account profile knobs (mirrors skill / strategy family sizing)
PROFILE_RISK = {"small": 40.0, "main": 1350.0, "swing": 500.0}
PROFILE_BUYING_POWER = {"small": 12_000.0, "main": 100_000.0, "swing": 50_000.0}
LEGACY_EXECUTION_MODEL = "reported_fill_v1"

# a running session idle longer than this (no file writes) is treated as stale
_STALE_AFTER_S = 15 * 60

# Legacy reported-fill action sets (also used by PositionEngine).  Intent actions
# for the deterministic model deliberately live in execution.py so they never get
# accidentally accepted by the historical reported-fill path.
ACTION_FILLS = {"ENTER", "ADD", "SCALE", "EXIT"}
ALL_ACTIONS = {"OBSERVE", "ENTER", "ADD", "SCALE", "TRAIL", "EXIT", "STAND_DOWN"}
_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


class PositionEngine:
    """Deterministic average-cost long-only position & P&L tracker.

    The simulator/LLM only reports actions + fills; this class walks the
    decisions and produces blotter actions, per-bar timeline snapshots, and
    final pnl dict. It is fully deterministic and unit-testable in isolation.
    """

    def __init__(self) -> None:
        self.shares: int = 0
        self.avg_entry: float = 0.0
        self.realized: float = 0.0
        self.entry_i: Optional[int] = None
        self.entry_avg: Optional[float] = None
        # blended cost basis across every buy (avg-cost: sells don't change it),
        # so "entry avg" stays correct after an ADD instead of showing the 1st fill.
        self._buy_value: float = 0.0
        self._buy_shares: int = 0
        # $ risked at the initial entry (entry shares × per-share stop distance),
        # captured on the first buy — the denominator for a true R multiple.
        self.initial_risk: Optional[float] = None
        # shares bought on the very first ENTER (published for reference).
        self.entry_shares: Optional[int] = None
        # peak position size ever held — the correct scale for the capture ratio, so
        # pyramiding (ADD) doesn't make capture read >1 against the initial tranche.
        self.max_shares: int = 0
        # most negative (close - avg_entry) while in position; used for MAE per share
        self.worst_price_vs_entry: float = 0.0
        # bar index / reason when first returned to flat — bounds in-position MFE
        self.exit_i: Optional[int] = None
        self.exit_reason: Optional[str] = None

    def _validate_action(
        self, i: int, action: str, has_fill: bool, dq: Optional[int]
    ) -> None:
        if action not in ALL_ACTIONS:
            raise ValueError(f"turn i={i}: invalid action {action!r}")
        if action in ACTION_FILLS and not has_fill:
            raise ValueError(f"turn i={i}: action {action} requires fill_px + shares_delta")
        if action in ("OBSERVE", "TRAIL", "STAND_DOWN") and has_fill:
            raise ValueError(f"turn i={i}: action {action} must not carry a fill (shares_delta set)")
        if action == "ENTER" and self.shares > 0:
            raise ValueError(f"turn i={i}: ENTER while already long {self.shares} (use ADD)")
        if action in ("ENTER", "ADD") and dq and dq < 0:
            raise ValueError(f"turn i={i}: {action} must be a buy (shares_delta > 0)")
        if action in ("SCALE", "EXIT") and dq and dq > 0:
            raise ValueError(f"turn i={i}: {action} must be a sell (shares_delta < 0)")

    def step(
        self,
        i: int,
        hhmm: Optional[str],
        action: str,
        fill: Optional[float],
        dq: Optional[int],
        stop: Optional[float],
        close: Optional[float],
        low: Optional[float] = None,
    ) -> tuple[Optional[dict], dict]:
        """Process one decision. Returns (action_row or None, timeline_row).

        ``low`` is the bar's low, used for MAE (max adverse excursion) — the worst
        the position sat through is an *intra-bar* level, so it is measured from the
        bar low, not the close. Falls back to ``close`` when a low isn't supplied."""
        action = action or "OBSERVE"
        has_fill = bool(dq)
        self._validate_action(i, action, has_fill, dq)

        realized_delta = 0.0
        action_row = None

        if dq:
            if fill is None:
                raise ValueError(f"turn i={i}: shares_delta set but fill_px missing")
            if dq > 0:  # buy
                if self.shares == 0:
                    if self.entry_i is None:
                        self.entry_i = i
                    if self.entry_avg is None:
                        self.entry_avg = fill
                    if self.entry_shares is None:
                        self.entry_shares = dq
                    # first buy: record the $ risk implied by the stop, if given
                    if self.initial_risk is None and stop is not None and fill > stop:
                        self.initial_risk = round(dq * (fill - stop), 2)
                new_total = self.shares + dq
                self.avg_entry = (self.avg_entry * self.shares + fill * dq) / new_total
                self.shares = new_total
                self.max_shares = max(self.max_shares, self.shares)
                self._buy_value += fill * dq
                self._buy_shares += dq
            else:  # sell
                qty = -dq
                if qty > self.shares:
                    raise ValueError(f"turn i={i}: selling {qty} but only {self.shares} held")
                realized_delta = qty * (fill - self.avg_entry)
                self.realized += realized_delta
                self.shares -= qty
                if self.shares == 0:
                    self.avg_entry = 0.0
                    if self.exit_i is None:
                        self.exit_i = i
                        self.exit_reason = action  # ENTER/SCALE/EXIT label

            side = "buy" if dq > 0 else "sell"
            action_row = {
                "i": i,
                "t": None,  # caller fills in epoch time
                "time": hhmm,
                "action": action,
                "side": side,
                "price": round(fill, 4),
                "shares": abs(dq),
                "position_after": self.shares,
                "avg_entry": round(self.avg_entry, 4) if self.shares else None,
                "realized_delta": round(realized_delta, 2),
                "reason": "",  # filled by caller
            }

        unreal = (
            round(self.shares * (close - self.avg_entry), 2)
            if (self.shares and close is not None)
            else 0.0
        )
        # MAE is intra-bar: measure the worst excursion from the bar LOW (the deepest
        # heat the open position actually sat through), not the close. Skip the entry
        # bar itself — a confirmed-close entry fills at that bar's close, so its low is
        # PRE-entry and never real heat. Only bars strictly after entry count.
        mae_ref = low if low is not None else close
        if (self.shares > 0 and mae_ref is not None
                and self.entry_i is not None and i > self.entry_i):
            vs_entry = mae_ref - self.avg_entry
            if vs_entry < self.worst_price_vs_entry:
                self.worst_price_vs_entry = vs_entry
        timeline_row = {
            "i": i,
            "t": None,  # filled later
            "time": hhmm,
            "action": action,
            "thought": "",
            "note": None,
            "fill_px": fill,
            "shares_delta": dq,
            "stop": stop,
            "close": round(close, 4) if close is not None else None,
            "position_shares": self.shares,
            "avg_entry": round(self.avg_entry, 4) if self.shares else None,
            "unrealized": unreal,
            "realized_to_date": round(self.realized, 2),
        }
        return action_row, timeline_row

    def force_close_if_needed(
        self, last_bar: Optional[dict], end_close: Optional[float]
    ) -> Optional[dict]:
        """If still long at end, create a forced EXIT action row (no epoch yet)."""
        if self.shares <= 0:
            return None
        close = end_close
        if close is None and last_bar:
            close = last_bar.get("c")
        if close is None:
            return None
        realized_delta = self.shares * (close - self.avg_entry)
        self.realized += realized_delta
        forced = {
            "i": last_bar["i"] if last_bar else 0,
            "t": None,
            "time": last_bar.get("time") if last_bar else None,
            "action": "EXIT",
            "side": "sell",
            "price": round(close, 4),
            "shares": self.shares,
            "position_after": 0,
            "avg_entry": None,
            "realized_delta": round(realized_delta, 2),
            "reason": "auto-flat at session end (position left open)",
        }
        self.shares = 0
        self.avg_entry = 0.0
        if self.exit_i is None and last_bar is not None:
            self.exit_i = last_bar.get("i")
            self.exit_reason = "auto-flat at session end (position left open)"
        return forced

    def peak_high_since_entry(self, bars: list[dict]) -> Optional[float]:
        """Highest bar high while the first position was open (in-position MFE).

        Delegates to :meth:`execution.ExecutionEngine.in_position_peak_high` so
        legacy reported-fill and deterministic paths share one definition.
        """
        from .execution import ExecutionEngine

        return ExecutionEngine.in_position_peak_high(
            bars, self.entry_i, self.exit_i, self.exit_reason
        )

    def mfe_per_share(self, bars: list[dict]) -> Optional[float]:
        peak = self.peak_high_since_entry(bars)
        if peak is None or self.entry_avg is None:
            return None
        return round(peak - self.entry_avg, 4)

    def mae_per_share(self) -> Optional[float]:
        """Worst (most negative) price vs entry_avg while long, as positive MAE value.
        Mirrors mfe_per_share for adverse excursion per share."""
        if self.entry_i is None or self.worst_price_vs_entry >= 0:
            return None
        return round(-self.worst_price_vs_entry, 4)

    @property
    def realized_pnl(self) -> float:
        return round(self.realized, 2)

    @property
    def blended_entry(self) -> Optional[float]:
        """True average cost basis across all buys (None if never long)."""
        if self._buy_shares <= 0:
            return None
        return round(self._buy_value / self._buy_shares, 4)


# ───────────────────────────── helpers ──────────────────────────────────────


def _session_lock_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / ".session.lock"


# stream parsing lives in ``streamio`` (shared with feed/step) — imported above.


# ───────────────────────────── init / log ───────────────────────────────────


def init(
    ticker: str,
    date: str,
    *,
    seed: Optional[int] = None,
    profile: str = "small",
    delay: Optional[float] = None,
    risk_budget: Optional[float] = None,
    buying_power: Optional[float] = None,
    skill: Optional[str | Path] = None,
    mode: str = "simulated",
    pin_version: Optional[str] = None,
    batch: Optional[str] = None,
    session: Optional[str] = None,
    runner_contract: Optional[dict] = None,
    strategy: Optional[str] = None,
    root: Path = SIM_ROOT,
    now: Optional[datetime] = None,
) -> Path:
    """Create the session folder and a provisional ``session.json``; return its path.

    The driving skill's version is read and *frozen* here (at run start) so later
    edits to the skill never retroactively re-tag this run. Normally the version is
    resolved (and auto-bumped on drift) via ``skillmeta.resolve_version``.

    **Backtest mode (``pin_version``).** When replaying a *specific* version for a
    batch, pass ``pin_version="2.0.2"`` with ``skill`` pointing at that version's file
    (``skills/trade_skills/2.0.2.md``). The session is stamped exactly with that
    version + the file's hash, and ``resolve_version`` is **skipped entirely** — a
    backtest must never bump the version or touch the registry.
    ``batch`` or ``session`` tags the run. Use ``session`` for top-level grouping
    (live trading day or simulation batch). ``batch`` kept for backward compat.
    Batch harnesses may also stamp an immutable ``runner_contract`` describing the
    prompt and execution harness that drove this leaf; ordinary/manual sessions do
    not need one.

    **Multi-strategy.** Pass ``strategy`` (e.g. ``cup_handle``) to use that family's
    skill registry, risk defaults, and horizon flags. Default is ``warrior``.
    """
    from .strategies import get_strategy

    now = now or datetime.now()
    # A short random suffix makes the id collision-proof: under batch parallelism two
    # agents trading the same ticker can `init` in the same wall-clock second, and a
    # second-granularity id would race on the same folder (one clobbering the other).
    sid = f"{now.strftime('%Y%m%d%H%M%S')}-{ticker.upper()}-{secrets.token_hex(3)}"
    sdir = Path(root) / sid
    sdir.mkdir(parents=True, exist_ok=False)

    strategy_id = (strategy or "warrior").strip().lower().replace("-", "_")
    try:
        strat = get_strategy(strategy_id)
    except KeyError:
        strat = get_strategy("warrior")
        strategy_id = "warrior"

    # Profile / risk defaults from family when caller uses family profile name.
    if profile == "swing" or strategy_id != "warrior":
        default_profile = strat.risk.profile
        if profile == "small" and strategy_id != "warrior":
            profile = default_profile
    default_risk = PROFILE_RISK.get(profile, strat.risk.risk_budget)
    default_bp = PROFILE_BUYING_POWER.get(profile, strat.risk.buying_power)

    if skill is not None:
        skill_path = Path(skill)
        registry_path = None  # colocated registry for ad-hoc skills
    else:
        skill_path = skillmeta.base_skill_path(
            strat.registry_path(), strat.trade_skills_dir()
        )
        registry_path = strat.registry_path()

    note = None
    if pin_version is not None:
        # backtest: stamp the pinned version read-only — no resolve/bump/archive.
        try:
            m = skillmeta.read_skill_meta(skill_path)
            content_hash = m["content_hash"]
        except FileNotFoundError:
            m = {}
            content_hash = None
        skill_meta = {
            "name": m.get("name") or "trade-simulator",
            "version": pin_version,
            "content_hash": content_hash,
            "path": str(skill_path),
            "execution_model": m.get("execution_model"),
            "entry_bracket_required": m.get("entry_bracket_required"),
            "entry_pyramid_required": m.get("entry_pyramid_required"),
            "daily_enter_close_prohibited": m.get("daily_enter_close_prohibited"),
            "armed_entry_gap_guard_required": m.get("armed_entry_gap_guard_required"),
            "armed_entry_expiry_required": m.get("armed_entry_expiry_required"),
            "arm_on_scanner_plan_required": m.get("arm_on_scanner_plan_required"),
            "session_from_open": m.get("session_from_open"),
            "five_minute_context": m.get("five_minute_context"),
            "completed_five_minute_entry_required": m.get(
                "completed_five_minute_entry_required"
            ),
            "strategy": m.get("strategy") or strategy_id,
            "horizon": m.get("horizon"),
            "bar_resolution": m.get("bar_resolution"),
            "same_day_only": m.get("same_day_only"),
            "max_hold_bars": m.get("max_hold_bars"),
        }
    else:
        try:
            skill_meta, note = skillmeta.resolve_version(skill_path, registry_path)
        except FileNotFoundError:
            skill_meta = {
                "name": None,
                "version": None,
                "content_hash": None,
                "path": str(skill_path),
            }
            note = f"skill file not found at {skill_path} — run recorded as unversioned."
    if note:
        print(f"• {note}", file=sys.stderr)

    resolved_risk_budget = (
        risk_budget if risk_budget is not None else default_risk
    )
    resolved_bp = buying_power if buying_power is not None else default_bp
    execution_model = skill_meta.get("execution_model") or LEGACY_EXECUTION_MODEL

    # Horizon flags: skill frontmatter wins, else strategy defaults.
    def _boolish(v, default):
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes")

    same_day_only = _boolish(
        skill_meta.get("same_day_only"), strat.horizon.same_day_only
    )
    max_hold_raw = skill_meta.get("max_hold_bars")
    if max_hold_raw is None or max_hold_raw == "":
        max_hold_bars = strat.horizon.max_hold_bars
    else:
        max_hold_bars = int(max_hold_raw)

    config = {
        "seed": seed,
        "profile": profile,
        "delay": delay,
        "risk_budget": resolved_risk_budget,
        "buying_power": resolved_bp,
        "execution_model": execution_model,
        "strategy": strategy_id,
        "same_day_only": same_day_only,
        "max_hold_bars": max_hold_bars,
        "horizon": skill_meta.get("horizon") or strat.horizon.kind,
        "bar_resolution": skill_meta.get("bar_resolution") or strat.horizon.bar_resolution,
    }
    if execution_model == EXECUTION_MODEL:
        # Freeze every cost/liquidity assumption at session creation.  Replaying
        # a session after a later code-default change must produce identical P&L.
        config["execution"] = ExecutionConfig.from_session_config(config).to_dict()

    if runner_contract is not None and not isinstance(runner_contract, dict):
        raise ValueError("runner_contract must be a dictionary when provided")

    session = {
        "schema_version": SCHEMA_VERSION,
        "id": sid,
        "mode": mode,   # "simulated" (paper) or "live" (real-time market session)
        "status": "running",
        "ticker": ticker.upper(),
        "historical_date": date,
        "strategy": strategy_id,
        "real_run_ts": now.isoformat(timespec="seconds"),
        "skill": skill_meta,
        "batch": batch,   # legacy
        "session": session or batch,  # top-level session (live day or batch tag)
        "config": config,
        "files": {},
    }
    if runner_contract is not None:
        # JSON round-trip makes a detached, serializable snapshot. A caller cannot
        # mutate the in-memory dict after init and silently change session provenance.
        session["runner_contract"] = json.loads(json.dumps(runner_contract, sort_keys=True))
    atomic_write_json(sdir / "session.json", session, indent=2)
    # touch the append targets so the run never trips over a missing file
    (sdir / "decisions.jsonl").touch()
    return sdir


def _last_logged_i(path: Path) -> int:
    """The largest decision ``i`` already appended to ``decisions.jsonl`` (-1 if
    none). Scans from the end and returns the first parseable line's ``i`` — records
    are written in increasing order, so that is the max; a half-flushed trailing line
    is skipped."""
    p = Path(path)
    if not p.exists():
        return -1
    for line in reversed(p.read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        i = obj.get("i")
        return i if isinstance(i, int) else -1
    return -1


def _validate_common_record(record: dict) -> None:
    """Validate fields shared by legacy fills and deterministic intents."""
    i = record.get("i")
    if not isinstance(i, int) or i < 0:
        raise ValueError("decision record 'i' must be a non-negative integer")

    hhmm = record.get("time")
    if not isinstance(hhmm, str) or not _HHMM_RE.match(hhmm):
        raise ValueError("decision record 'time' must be HH:MM")
    h, m = (int(x) for x in hhmm.split(":"))
    if h > 23 or m > 59:
        raise ValueError("decision record 'time' must be a valid HH:MM")


def _validate_legacy_record(record: dict) -> None:
    action = record.get("action")
    if action not in ALL_ACTIONS:
        raise ValueError(f"action must be one of {sorted(ALL_ACTIONS)}, got {action!r}")
    _validate_common_record(record)

    fill = record.get("fill_px")
    dq = record.get("shares_delta")
    stop = record.get("stop")
    if fill is not None and not isinstance(fill, (int, float)):
        raise ValueError("decision record 'fill_px' must be numeric or null")
    if fill is not None and fill <= 0:
        raise ValueError("decision record 'fill_px' must be positive")
    if dq is not None and (not isinstance(dq, int) or dq == 0):
        raise ValueError("decision record 'shares_delta' must be a non-zero integer or null")
    if stop is not None and not isinstance(stop, (int, float)):
        raise ValueError("decision record 'stop' must be numeric or null")

    if action in ACTION_FILLS:
        if fill is None or dq is None:
            raise ValueError(f"action {action} requires fill_px + shares_delta")
        if action in ("ENTER", "ADD") and dq < 0:
            raise ValueError(f"action {action} must use positive shares_delta")
        if action in ("SCALE", "EXIT") and dq > 0:
            raise ValueError(f"action {action} must use negative shares_delta")
    elif fill is not None or dq is not None:
        raise ValueError(f"action {action} must not carry fill_px or shares_delta")


def _number(record: dict, key: str, *, positive: bool = True) -> float:
    value = record.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"deterministic action requires numeric '{key}'")
    value = float(value)
    if positive and value <= 0:
        raise ValueError(f"deterministic action '{key}' must be positive")
    return value


def _validate_entry_bracket(record: dict) -> None:
    """Validate an optional engine-derived R-multiple scale ladder."""
    bracket = record.get("bracket")
    if bracket is None:
        return
    if not isinstance(bracket, dict):
        raise ValueError("entry bracket must be an object")
    scales = bracket.get("scales")
    if not isinstance(scales, list) or not scales:
        raise ValueError("entry bracket requires a non-empty 'scales' list")
    total_fraction = 0.0
    previous_r = 0.0
    for scale in scales:
        if not isinstance(scale, dict):
            raise ValueError("each entry bracket scale must be an object")
        r_multiple = scale.get("r_multiple")
        fraction = scale.get("fraction")
        if not isinstance(r_multiple, (int, float)) or isinstance(r_multiple, bool) or r_multiple <= 0:
            raise ValueError("entry bracket scale 'r_multiple' must be positive")
        if (not isinstance(fraction, (int, float)) or isinstance(fraction, bool)
                or not 0 < fraction <= 1):
            raise ValueError("entry bracket scale 'fraction' must be in (0, 1]")
        if r_multiple <= previous_r:
            raise ValueError("entry bracket scales must have strictly increasing R multiples")
        previous_r = float(r_multiple)
        total_fraction += float(fraction)
    if total_fraction > 1.0 + 1e-12:
        raise ValueError("entry bracket scale fractions may not total more than 1")


def _validate_entry_pyramid(record: dict) -> None:
    """Validate an optional engine-managed starter/add plan."""
    pyramid = record.get("pyramid")
    if pyramid is None:
        return
    if not isinstance(pyramid, dict):
        raise ValueError("entry pyramid must be an object")
    starter = pyramid.get("starter_fraction")
    max_adds = pyramid.get("max_adds")
    if (not isinstance(starter, (int, float)) or isinstance(starter, bool)
            or not 0 < starter <= 0.5):
        raise ValueError("entry pyramid 'starter_fraction' must be in (0, 0.5]")
    if not isinstance(max_adds, int) or isinstance(max_adds, bool) or max_adds not in {1, 2}:
        raise ValueError("entry pyramid 'max_adds' must be 1 or 2")


def _validate_intent_record(
    record: dict,
    *,
    require_entry_bracket: bool = False,
    require_entry_pyramid: bool = False,
    forbid_daily_enter_close: bool = False,
    require_armed_entry_gap_guard: bool = False,
    require_armed_entry_expiry: bool = False,
) -> None:
    """Validate the no-agent-fill contract used by deterministic skills."""
    _validate_common_record(record)
    action = record.get("action")
    if action not in INTENT_ACTIONS:
        raise ValueError(f"action must be one of {sorted(INTENT_ACTIONS)}, got {action!r}")
    if record.get("fill_px") is not None or record.get("shares_delta") is not None:
        raise ValueError(
            "deterministic execution derives fills and size; do not supply fill_px or shares_delta"
        )
    if action == "ENTER_CLOSE" and forbid_daily_enter_close:
        raise ValueError("this daily skill prohibits ENTER_CLOSE on a revealed daily bar")
    if action in {"ENTER_CLOSE", "ARM_BUY_STOP", "SET_STOP", "ADD_CLOSE"}:
        _number(record, "stop")
    if action == "ARM_BUY_STOP":
        trigger = _number(record, "trigger")
        if _number(record, "stop") >= trigger:
            raise ValueError("ARM_BUY_STOP stop must be below trigger")
        if require_armed_entry_gap_guard and record.get("max_entry_gap_atr") is None:
            raise ValueError("this skill requires max_entry_gap_atr and atr on every armed entry")
        if record.get("max_entry_gap_atr") is not None:
            if _number(record, "max_entry_gap_atr") < 0:
                raise ValueError("ARM_BUY_STOP max_entry_gap_atr must be non-negative")
            if _number(record, "atr") <= 0:
                raise ValueError("ARM_BUY_STOP gap guard requires positive atr")
        if require_armed_entry_expiry and record.get("expiry_bars") is None:
            raise ValueError("this skill requires expiry_bars on every armed entry")
        if record.get("expiry_bars") is not None:
            expiry_bars = record["expiry_bars"]
            if (not isinstance(expiry_bars, int) or isinstance(expiry_bars, bool)
                    or expiry_bars < 1):
                raise ValueError("ARM_BUY_STOP expiry_bars must be a positive integer")
    if action in {"ENTER_CLOSE", "ARM_BUY_STOP"}:
        if require_entry_bracket and record.get("bracket") is None:
            raise ValueError("this skill requires an entry bracket on every new entry")
        if require_entry_pyramid and record.get("pyramid") is None:
            raise ValueError("this skill requires an entry pyramid on every new entry")
        _validate_entry_bracket(record)
        _validate_entry_pyramid(record)
    if action == "SCALE_LIMIT":
        _number(record, "target")
        fraction = _number(record, "fraction")
        if fraction > 1:
            raise ValueError("SCALE_LIMIT fraction must be in (0, 1]")
    if action == "ADD_CLOSE":
        fraction = _number(record, "risk_fraction")
        if fraction > 1:
            raise ValueError("ADD_CLOSE risk_fraction must be in (0, 1]")


def _validate_decision_record(
    record: dict,
    execution_model: str = LEGACY_EXECUTION_MODEL,
    *,
    require_entry_bracket: bool = False,
    require_entry_pyramid: bool = False,
    forbid_daily_enter_close: bool = False,
    require_armed_entry_gap_guard: bool = False,
    require_armed_entry_expiry: bool = False,
) -> None:
    if execution_model == EXECUTION_MODEL:
        _validate_intent_record(
            record,
            require_entry_bracket=require_entry_bracket,
            require_entry_pyramid=require_entry_pyramid,
            forbid_daily_enter_close=forbid_daily_enter_close,
            require_armed_entry_gap_guard=require_armed_entry_gap_guard,
            require_armed_entry_expiry=require_armed_entry_expiry,
        )
    else:
        _validate_legacy_record(record)


def log(session_dir: str | Path, record: dict) -> None:
    """Append one decision record to ``decisions.jsonl``.

    Validated beyond the shape check: a decision may not be logged into a session
    that has already been finalized (the finalized artifacts are frozen, so a late
    append would be silently ignored by the viewer's fast path), and the bar index
    ``i`` must strictly increase — a duplicate or out-of-order ``i`` (easy to emit
    after a retried turn) would be replayed by the engine as a second fill and
    double the position.
    """
    sdir = Path(session_dir)

    with file_lock(_session_lock_path(sdir)):
        session = _load_json(sdir / "session.json", {}) or {}
        if session.get("status") == "complete":
            raise ValueError(
                f"session {sdir.name} is finalized — cannot log new decisions "
                "(re-init a fresh session instead)"
            )

        execution_model = session.get("config", {}).get("execution_model", LEGACY_EXECUTION_MODEL)
        bracket_contract = session.get("skill", {}).get("entry_bracket_required")
        require_entry_bracket = bracket_contract is True or str(bracket_contract).lower() == "true"
        pyramid_contract = session.get("skill", {}).get("entry_pyramid_required")
        require_entry_pyramid = pyramid_contract is True or str(pyramid_contract).lower() == "true"
        no_daily_close_contract = session.get("skill", {}).get("daily_enter_close_prohibited")
        forbid_daily_enter_close = (
            no_daily_close_contract is True or str(no_daily_close_contract).lower() == "true"
        )
        gap_guard_contract = session.get("skill", {}).get("armed_entry_gap_guard_required")
        require_armed_entry_gap_guard = (
            gap_guard_contract is True or str(gap_guard_contract).lower() == "true"
        )
        expiry_contract = session.get("skill", {}).get("armed_entry_expiry_required")
        require_armed_entry_expiry = (
            expiry_contract is True or str(expiry_contract).lower() == "true"
        )
        scanner_plan_contract = session.get("skill", {}).get("arm_on_scanner_plan_required")
        require_scanner_plan_arm = (
            scanner_plan_contract is True or str(scanner_plan_contract).lower() == "true"
        )
        bar5_contract = session.get("skill", {}).get("completed_five_minute_entry_required")
        require_completed_bar5_entry = bar5_contract is True or str(bar5_contract).lower() == "true"
        _validate_decision_record(
            record, execution_model,
            require_entry_bracket=require_entry_bracket,
            require_entry_pyramid=require_entry_pyramid,
            forbid_daily_enter_close=forbid_daily_enter_close,
            require_armed_entry_gap_guard=require_armed_entry_gap_guard,
            require_armed_entry_expiry=require_armed_entry_expiry,
        )

        # Intent sessions must be bound to an already-revealed tick.  This
        # makes timestamps an executable constraint, not an agent convention.
        if execution_model == EXECUTION_MODEL:
            _meta, ticks, _end = _parse_stream(sdir / "stream.jsonl")
            tick = next((t for t in ticks if t.get("i") == record["i"]), None)
            if tick is None:
                raise ValueError(
                    f"decision i={record['i']} has not been revealed in stream.jsonl"
                )
            if tick.get("time") != record["time"]:
                raise ValueError(
                    f"decision time {record['time']} does not match revealed tick time {tick.get('time')}"
                )
            integrity_errors = (
                _daily_indicator_integrity_errors(session, _meta or {}, ticks)
                + _causal_plan_integrity_errors(
                    session, _meta or {}, ticks, allow_pending_setup=True,
                )
            )
            if integrity_errors:
                raise ValueError(
                    "daily stream data-integrity failure — " + "; ".join(integrity_errors)
                )
            if require_scanner_plan_arm and record.get("action") == "ARM_BUY_STOP":
                plan = tick.get("scanner_plan")
                if not isinstance(plan, dict):
                    raise ValueError(
                        "this skill permits ARM_BUY_STOP only on the revealed scanner plan bar"
                    )
                # The plan is published at the completed-handle close.  Binding
                # all executable order parameters to it prevents both early arms
                # and a model quietly substituting a hindsight-derived level.
                plan_fields = {
                    "trigger": "trigger",
                    "stop": "stop",
                    "atr": "atr",
                    "max_entry_gap_atr": "max_entry_gap_atr",
                    "expiry_bars": "arm_expiry_bars",
                }
                for decision_key, plan_key in plan_fields.items():
                    expected = plan.get(plan_key)
                    actual = record.get(decision_key)
                    if expected is None or actual is None:
                        raise ValueError(
                            f"scanner plan is missing required armed-entry field {plan_key!r}"
                        )
                    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                        if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-8):
                            raise ValueError(
                                f"ARM_BUY_STOP {decision_key} must match the revealed scanner plan"
                            )
                    elif actual != expected:
                        raise ValueError(
                            f"ARM_BUY_STOP {decision_key} must match the revealed scanner plan"
                        )
            if require_completed_bar5_entry:
                if record.get("action") in {"ARM_BUY_STOP", "ADD_CLOSE"}:
                    raise ValueError("4.0 entry contract permits only completed-5-minute ENTER_CLOSE entries")
                if record.get("action") == "ENTER_CLOSE":
                    if not tick.get("bar5_complete"):
                        raise ValueError("ENTER_CLOSE requires a completed 5-minute candle on this tick")
                    prior_entries = [d for d in _read_jsonl(sdir / "decisions.jsonl")
                                     if d.get("action") == "ENTER_CLOSE"]
                    if prior_entries:
                        raise ValueError("4.0 permits one first-entry attempt only; re-entry is disabled")

        i = record["i"]
        # Decisions are append-only in strictly increasing `i`, so the last written
        # record already holds the max — parse only that line instead of the whole file
        # (this runs on every turn; a full re-parse would be O(n²) over a session).
        last_i = _last_logged_i(sdir / "decisions.jsonl")
        if i <= last_i:
            raise ValueError(
                f"decision i={i} is not ahead of the last logged i={last_i} "
                "(bars must be logged in strictly increasing order; retried turns "
                "must not re-log a bar)"
            )

        with open(sdir / "decisions.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()


# ───────────────────────────── finalize ─────────────────────────────────────


def _build_bars(meta: dict, ticks: list[dict]) -> list[dict]:
    """Bars from the streamed ticks (traded window only) — the fallback source."""
    date = meta["date"]
    bars = []
    for tk in ticks:
        bar_date = tk.get("date") or date
        hhmm = tk.get("time") or "16:00"
        # daily ticks use time="16:00" + date=YYYY-MM-DD
        bars.append({
            "t": _epoch_et(bar_date, hhmm if len(hhmm) == 5 else "16:00"),
            "time": hhmm,
            "date": bar_date,
            "i": tk["i"],
            "o": tk["o"], "h": tk["h"], "l": tk["l"], "c": tk["c"],
            "v": tk["v"],
            "vwap": tk.get("vwap"),
            "ema9": tk.get("ema9"),
            "ema20": tk.get("ema20"),
            "macd": tk.get("macd"),
            "macd_signal": tk.get("macd_signal"),
            "macd_hist": tk.get("macd_hist"),
            "session_high": tk.get("session_high"),
            "new_high": tk.get("new_high"),
            "rvol_bar": tk.get("rvol_bar"),
            "sma20": tk.get("sma20"),
            "sma50": tk.get("sma50"),
            "sma200": tk.get("sma200"),
            "atr14": tk.get("atr14"),
        })
    return bars


def _full_day_bars(meta: dict) -> Optional[list[dict]]:
    """The whole RTH session (09:30→16:00) for the chart — so the viewer shows the
    full day's context, not just the traded window. Best-effort: returns None if
    the provider can't serve the day (caller falls back to the streamed ticks).

    Indicators are recomputed over the full session, matching the streamed values
    at each timestamp (replay enriches over the same full RTH fetch)."""
    import pandas as pd  # noqa: F401 (ensure pandas present)
    from datetime import datetime as _dt

    from . import replay

    day = _dt.strptime(meta["date"], "%Y-%m-%d").date()
    try:
        df = replay.fetch_minute_bars(meta["ticker"], day)
    except (OSError, ValueError, KeyError, TypeError) as e:
        # provider miss is a legitimate fallback path (caller uses streamed ticks),
        # but record why so a broken provider isn't silently masked as "no data".
        logger.debug("full-day bar fetch failed for %s %s: %s", meta["ticker"], day, e)
        return None
    except Exception:
        logger.debug("full-day bar fetch unexpected error for %s %s", meta["ticker"], day, exc_info=True)
        return None
    if df is None or df.empty:
        return None
    df = replay._enrich(df)

    def _r(v, n=4):
        return round(float(v), n) if v is not None and pd.notna(v) else None

    bars = []
    for idx, (ts, row) in enumerate(df.iterrows()):
        hhmm = ts.strftime("%H:%M")
        bars.append({
            "t": _epoch_et(meta["date"], hhmm), "time": hhmm, "i": idx,
            "o": _r(row["open"]), "h": _r(row["high"]),
            "l": _r(row["low"]), "c": _r(row["close"]),
            "v": int(row["volume"]),
            "vwap": _r(row["vwap"]), "ema9": _r(row["ema9"]),
            "ema20": _r(row["ema20"]),
            "macd": _r(row["macd"]), "macd_signal": _r(row["macd_signal"]),
            "macd_hist": _r(row["macd_hist"]),
            "session_high": _r(row["session_high"]),
            "new_high": bool(row["new_high"]),
            "rvol_bar": _r(row["rvol_bar"], 2),
        })
    return bars


def _bar_by_i(bars: list[dict]) -> dict:
    return {int(b["i"]): b for b in bars if b.get("i") is not None}


def _stamp_bar_clock(row: dict, bar: Optional[dict], meta_date: str) -> None:
    """Attach date + epoch ``t`` from the bar this row belongs to (multi-day safe).

    Historically we stamped every fill with ``meta["date"]`` + HH:MM, which collapses
    all multi-day markers onto the setup day. Prefer the bar's own ``date``/``t``.
    """
    hhmm = row.get("time") or (bar or {}).get("time") or "16:00"
    bar_date = (bar or {}).get("date") or meta_date
    row["date"] = bar_date
    if bar and bar.get("t") is not None:
        row["t"] = bar["t"]
    elif hhmm:
        row["t"] = _epoch_et(bar_date, hhmm if len(str(hhmm)) == 5 else "16:00")
    else:
        row["t"] = None


def _run_engine(meta, bars, decisions, risk_budget, end, force_close=True):
    """Average-cost position/P&L walk using PositionEngine. Returns (actions, timeline, pnl)."""
    date_str = meta["date"]
    by_i = _bar_by_i(bars)
    close_by_i = {b["i"]: b["c"] for b in bars}
    low_by_i = {b["i"]: b.get("l") for b in bars}

    engine = PositionEngine()
    actions: list[dict] = []
    timeline: list[dict] = []

    for d in sorted(decisions, key=lambda x: x.get("i", 0)):
        i = d.get("i")
        hhmm = d.get("time")
        action = d.get("action", "OBSERVE")
        fill = d.get("fill_px")
        dq = d.get("shares_delta")
        stop = d.get("stop")
        close = close_by_i.get(i)
        low = low_by_i.get(i)
        bar = by_i.get(i) if i is not None else None

        action_row, timeline_row = engine.step(i, hhmm, action, fill, dq, stop, close, low)

        # fill epoch times from the *bar's* calendar date (not setup-day meta only)
        if action_row is not None:
            _stamp_bar_clock(action_row, bar, date_str)
            action_row["reason"] = d.get("note") or d.get("thought", "")[:140]
            actions.append(action_row)

        if timeline_row is not None:
            _stamp_bar_clock(timeline_row, bar, date_str)
            timeline_row["thought"] = d.get("thought", "")
            timeline_row["note"] = d.get("note")
            timeline.append(timeline_row)

    # force-close any open position at the session end close (finalize only). For a
    # LIVE view we leave the position open and report unrealized P&L, so the chart/
    # blotter never shows a phantom exit the agent hasn't actually made.
    last = bars[-1] if bars else None
    end_close = (end or {}).get("close") if end else None
    forced = engine.force_close_if_needed(last, end_close) if force_close else None
    if forced is not None:
        _stamp_bar_clock(forced, last, date_str)
        actions.append(forced)

    # one scan of the bars for the peak high since entry, reused for both metrics.
    peak_high = engine.peak_high_since_entry(bars)
    mfe_ps = (                                   # max(high) − first-fill price
        round(peak_high - engine.entry_avg, 4)
        if (peak_high is not None and engine.entry_avg is not None) else None
    )
    entry_avg = engine.blended_entry             # blended cost across all buys
    entry_shares = engine.entry_shares
    max_shares = engine.max_shares or None
    # capture ratio: realized $ ÷ the best-case dollars had you held your *peak* size
    # to the high and sold there (mfe-vs-blended-cost × peak shares). Peak size (not
    # the initial tranche) is the right scale, so pyramiding doesn't inflate capture
    # past ~1. ≈ "fraction of the favorable move you kept"; negative if the trade lost.
    cap_ps = (peak_high - entry_avg) if (peak_high is not None and entry_avg) else None
    mfe_dollars = (cap_ps * max_shares) if (cap_ps and max_shares) else None
    mfe_capture = (
        round(engine.realized / mfe_dollars, 3)
        if (mfe_dollars and mfe_dollars > 0) else None
    )

    mae_ps = engine.mae_per_share()
    pnl = {
        "realized_pnl": engine.realized_pnl,
        "risk_budget": risk_budget,
        # planned R: realized vs the account's per-trade budget (position sizing target)
        "r_multiple": round(engine.realized / risk_budget, 2) if risk_budget else None,
        # actual R: realized vs the $ actually risked at entry (shares × stop distance);
        # None if no stop was recorded on the entry bar
        "initial_risk": engine.initial_risk,
        "r_multiple_actual": (
            round(engine.realized / engine.initial_risk, 2)
            if engine.initial_risk else None
        ),
        "win": engine.realized > 0,
        "traded": engine.entry_i is not None,
        "n_fills": len(actions),
        "entry_index": engine.entry_i,
        "entry_avg": entry_avg,   # blended cost basis across all buys
        "entry_shares": entry_shares,
        "max_shares": max_shares,
        "mfe_per_share": mfe_ps,
        "mfe_pct": round(mfe_ps / entry_avg * 100, 2) if (mfe_ps and entry_avg) else None,
        "mfe_capture": mfe_capture,
        "mae_per_share": mae_ps,
        "mae_pct": round(mae_ps / entry_avg * 100, 2) if (mae_ps and entry_avg) else None,
        "forced_exit": forced is not None,
        "assumptions": "fills at reported price; no slippage/fees/Level-2; avg-cost basis.",
    }
    return actions, timeline, pnl


def _run_session_engine(
    session: dict,
    meta: dict,
    bars: list[dict],
    decisions: list[dict],
    end: Optional[dict],
    *,
    force_close: bool = True,
    through_i: Optional[int] = None,
) -> tuple[list[dict], list[dict], dict]:
    """Dispatch by the execution contract frozen in ``session.json``.

    Historical sessions retain reported-fill replay.  A deterministic skill is
    never allowed to silently fall back to it: its intents are interpreted only
    by :class:`ExecutionEngine`.
    """
    config = session.get("config", {}) or {}
    if config.get("execution_model") != EXECUTION_MODEL:
        risk_budget = config.get("risk_budget") or PROFILE_RISK["small"]
        return _run_engine(meta, bars, decisions, risk_budget, end, force_close=force_close)

    engine = ExecutionEngine(ExecutionConfig.from_session_config(config))
    actions, timeline, pnl = engine.run(
        bars,
        decisions,
        through_i=through_i,
        end_close=(end or {}).get("close"),
        force_close=force_close,
    )
    by_i = _bar_by_i(bars)
    meta_date = meta.get("date") or ""
    for row in actions:
        bar = by_i.get(int(row["i"])) if row.get("i") is not None else None
        _stamp_bar_clock(row, bar, meta_date)
    for row in timeline:
        bar = by_i.get(int(row["i"])) if row.get("i") is not None else None
        _stamp_bar_clock(row, bar, meta_date)
    return actions, timeline, pnl


def resolve(session_dir: str | Path, i: Optional[int] = None) -> dict:
    """Resolve active deterministic orders through a revealed tick.

    Call this immediately after ``step next`` and before deciding on that tick.
    Only decisions strictly *before* ``i`` are applied, so the returned state is
    what was actually known at the start of the current bar.  The function is
    read-only; ``finalize`` remains the sole artifact writer.
    """
    sdir = Path(session_dir)
    with file_lock(_session_lock_path(sdir)):
        session = _load_json(sdir / "session.json", {}) or {}
        if session.get("config", {}).get("execution_model") != EXECUTION_MODEL:
            raise ValueError("resolve is available only to deterministic execution sessions")
        meta, ticks, _end = _parse_stream(sdir / "stream.jsonl")
        if meta is None or not ticks:
            raise ValueError("no revealed tick to resolve")
        current_i = max(t.get("i", -1) for t in ticks) if i is None else i
        tick = next((t for t in ticks if t.get("i") == current_i), None)
        if tick is None:
            raise ValueError(f"tick i={current_i} is not revealed")
        integrity_errors = (
            _daily_indicator_integrity_errors(session, meta, ticks)
            + _causal_plan_integrity_errors(session, meta, ticks, allow_pending_setup=True)
        )
        if integrity_errors:
            raise ValueError(
                "daily stream data-integrity failure — " + "; ".join(integrity_errors)
            )
        decisions = [d for d in _read_jsonl(sdir / "decisions.jsonl") if d.get("i", -1) < current_i]
        bars = _build_bars(meta, ticks)
        engine = ExecutionEngine(ExecutionConfig.from_session_config(session.get("config", {})))
        engine.run(bars, decisions, through_i=current_i, force_close=False)
        return engine.snapshot(current_i)


def _journal(session, meta, pnl, actions, timeline) -> str:
    L = []
    L.append(f"# Simulation — {meta['ticker']} {meta['date']}")
    L.append("")
    L.append(f"_Run {session['real_run_ts']} · session `{session['id']}`_")
    L.append("")
    L.append("## Setup")
    L.append(f"- gap **+{meta.get('gap_pct')}%**, RVOL **{meta.get('rvol')}×**, "
             f"float **{(meta.get('float_shares') or 0)/1e6:.1f}M**, "
             f"anchor (5-min breakout) **${meta.get('anchor_px')}**")
    lv = f"prior_close {meta.get('prior_close')}, prior_high {meta.get('prior_high')}, " \
         f"pm_high {meta.get('pm_high')}, pm_low {meta.get('pm_low')}"
    L.append(f"- levels: {lv}")
    L.append(f"- _{meta.get('reason','')}_")
    L.append("")
    L.append("## Result")
    if pnl["traded"]:
        r_actual = (f"  ·  **{pnl['r_multiple_actual']}R** on risk taken"
                    if pnl.get("r_multiple_actual") is not None else "")
        L.append(f"- realized **${pnl['realized_pnl']}**  ·  **{pnl['r_multiple']}R** vs budget"
                 f"{r_actual}  ·  {'WIN' if pnl['win'] else 'LOSS'}")
        L.append(f"- entry avg ${pnl['entry_avg']}; max favorable "
                 f"+${pnl['mfe_per_share']}/sh ({pnl['mfe_pct']}%)"
                 + (f"; max adverse -${pnl.get('mae_per_share')}/sh ({pnl.get('mae_pct')}%)" if pnl.get('mae_per_share') else "")
                 + ("  ·  _auto-flat at close_" if pnl["forced_exit"] else ""))
    else:
        L.append("- **stood down — no trade taken**")
    L.append("")
    L.append("## Blotter")
    for a in actions:
        when = a.get("date") or a.get("time") or ""
        if a.get("date") and a.get("time") and a.get("time") != "16:00":
            when = f"{a['date']} {a['time']}"
        elif a.get("date"):
            when = a["date"]
        L.append(f"- {when}  {a['side'].upper():4}  {a['shares']:>5} @ ${a['price']}"
                 f"   (Δreal ${a['realized_delta']})  — {a['reason']}")
    L.append("")
    L.append("## Decision timeline")
    for t in timeline:
        pos = f"[{t['position_shares']}sh @ {t['avg_entry']}]" if t["position_shares"] else "[flat]"
        when = t.get("date") or t.get("time") or ""
        if t.get("date") and t.get("time") and t.get("time") != "16:00":
            when = f"{t['date']} {t['time']}"
        elif t.get("date"):
            when = t["date"]
        L.append(f"- **{when}** `{t['action']}` {pos} uPnL ${t['unrealized']} — {t['thought']}")
    L.append("")
    return "\n".join(L)


def finalize(session_dir: str | Path, full_day: bool = True) -> dict:
    """Build bars/actions/decisions/pnl/session/journal from the raw inputs.

    ``full_day=True`` (default, the skill/CLI end-of-run path) draws the chart over
    the whole RTH session for context. ``full_day=False`` (the viewer's force-close
    of a still-live session) clamps the chart to revealed bars so the artifact can't
    leak price action past where trading stopped.
    """
    sdir = Path(session_dir)
    t0 = time.time()
    with file_lock(_session_lock_path(sdir)):
        session_path = sdir / "session.json"
        if not session_path.exists():
            raise FileNotFoundError(f"no session.json in {sdir} — run `init` first")
        session = json.loads(session_path.read_text())

        meta, ticks, end = _parse_stream(sdir / "stream.jsonl")
        if meta is None:
            raise ValueError(f"{sdir}/stream.jsonl has no meta line — was replay --out-file pointed here?")
        integrity_errors = (
            _daily_indicator_integrity_errors(session, meta, ticks)
            + _causal_plan_integrity_errors(session, meta, ticks)
        )
        if integrity_errors:
            raise ValueError(
                "daily stream data-integrity failure — " + "; ".join(integrity_errors)
            )
        decisions = _read_jsonl(sdir / "decisions.jsonl")
        # Chart bars: multi-day / daily streams already *are* the full sealed
        # context — never replace them with a 1-min RTH fetch of the setup date
        # (that made swing sessions look like day-trades and n_bars≈390).
        # Intraday: full_day=True expands to whole RTH for context; full_day=False
        # (live viewer finalize) clamps to revealed ticks only.
        stream_bars = _build_bars(meta, ticks)
        multi_day = _is_multi_day_session(session, meta)
        if multi_day or not full_day:
            bars = stream_bars
        else:
            bars = _full_day_bars(meta) or stream_bars
        actions, timeline, pnl = _run_session_engine(
            session, meta, stream_bars, decisions, end, force_close=True
        )

        # mirror the frozen skill stamp into pnl.json so `report --by-version` can
        # group by reading one file per session (not session.json + pnl.json).
        skill = session.get("skill", {}) or {}
        pnl["skill_version"] = skill.get("version")
        pnl["skill_hash"] = skill.get("content_hash")
        pnl["batch"] = session.get("batch")

        # enrich session manifest with setup meta + outcome + file index. Write
        # session.json last so "complete" only appears after all artifacts exist.
        session["status"] = "complete"
        session["finalized_ts"] = datetime.now().isoformat(timespec="seconds")
        session["setup"] = _setup_from_meta(meta)
        # Ensure strategy is stamped even if meta omitted it.
        session.setdefault("strategy", _strategy_of(session))
        if session.get("setup") is not None and "strategy" not in session["setup"]:
            session["setup"]["strategy"] = session["strategy"]
        session["result"] = {
            "traded": pnl["traded"], "realized_pnl": pnl["realized_pnl"],
            "r_multiple": pnl["r_multiple"], "win": pnl["win"],
            "mfe_per_share": pnl["mfe_per_share"], "n_bars": len(bars),
            "n_decisions": len(timeline), "n_fills": len(actions),
            "skill_version": skill.get("version"),
            "execution_model": pnl.get("execution_model", LEGACY_EXECUTION_MODEL),
        }
        session["files"] = {
            "bars": "bars.json", "actions": "actions.json", "decisions": "decisions.json",
            "pnl": "pnl.json", "journal": "journal.md", "stream": "stream.jsonl",
        }

        atomic_write_json(sdir / "bars.json", bars, indent=2)
        atomic_write_json(sdir / "actions.json", actions, indent=2)
        atomic_write_json(sdir / "decisions.json", timeline, indent=2)
        atomic_write_json(sdir / "pnl.json", pnl, indent=2)
        atomic_write_text(sdir / "journal.md", _journal(session, meta, pnl, actions, timeline))
        atomic_write_json(sdir / "session.json", session, indent=2)
        dt = round(time.time() - t0, 3)
        logger.info("finalize %s took %ss (full_day=%s)", sdir.name, dt, full_day)
        return session


# ───────────────────────────── Live / UI view helpers ────────────────────────

def _load_json(path: Path, default=None, *, log_errors: bool = True):
    """Tolerant JSON loader for session artifacts.

    Returns default for missing or unparseable files (expected for running
    sessions). Distinguishes FileNotFound vs decode errors for better diagnostics.
    Callers that need strict behavior should check the result or pass log_errors=False.
    """
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        if log_errors:
            logger.debug("failed to parse JSON at %s: %s", path, e)
        return default
    except Exception:
        # Other I/O or unexpected problems
        if log_errors:
            logger.debug("failed to load JSON at %s", path, exc_info=True)
        return default


def _validate_session_artifact(sdir: Path, *, require_complete: bool = False) -> list[str]:
    """Lightweight structural validation. Returns list of problem strings (empty = ok).

    Used by tests and can be called from finalize or admin tools. Does not raise.
    """
    problems = []
    sess = _load_json(sdir / "session.json", {})
    if not sess:
        problems.append("missing or unreadable session.json")
        return problems
    if require_complete and sess.get("status") != "complete":
        problems.append("session not marked complete")
    for name in ("bars.json", "actions.json", "decisions.json", "pnl.json"):
        if not (sdir / name).exists() and sess.get("status") == "complete":
            problems.append(f"missing {name} for complete session")
    # spot check keys on complete
    if sess.get("status") == "complete":
        pnl = _load_json(sdir / "pnl.json", {})
        if pnl is not None and not isinstance(pnl.get("realized_pnl"), (int, float, type(None))):
            problems.append("pnl.realized_pnl has unexpected type")
    return problems


def iter_sessions(*, skip_private: bool = True):
    """Yield ``(dir, session_dict)`` for every session folder under ``SIM_ROOT``,
    newest-first by folder name.

    The single source of truth for the "walk ``SIM_ROOT``, load ``session.json``,
    tolerate junk" scan that was previously copy-pasted across the list/report/batch
    helpers (and had already drifted on whether it skipped ``_``-prefixed bookkeeping
    dirs). Skips ``_``-prefixed dirs (e.g. ``_batch``) by default and any folder
    without a parseable ``session.json``.
    """
    if not SIM_ROOT.exists():
        return
    for d in sorted(SIM_ROOT.iterdir(), reverse=True):
        if skip_private and d.name.startswith("_"):
            continue
        s = _load_json(d / "session.json")
        if s:
            yield d, s


def get_session_view(session_dir: str | Path) -> dict:
    """Return a UI-friendly view for a session (works for both running and complete).

    Accepts either a full path or just the session id (folder name).
    For running sessions we compute everything on the fly from the live
    append-only files (stream.jsonl + decisions.jsonl) using *only revealed data*.
    No peeking at future bars.
    """
    p = Path(session_dir)
    if p.is_absolute() or (p.parts and p.parts[0] == "simulations"):
        sdir = p
    else:
        # treat as id
        sdir = SIM_ROOT / p.name

    session = _load_json(sdir / "session.json", {}) or {}
    status = session.get("status", "running")
    is_live = status != "complete"

    # Fast path for finalized complete sessions
    if not is_live:
        bars = _load_json(sdir / "bars.json", [])
        actions = _load_json(sdir / "actions.json", [])
        decisions = _load_json(sdir / "decisions.json", [])
        pnl = _load_json(sdir / "pnl.json", {})
        last_i = max([b.get("i", -1) for b in bars]) if bars else None
        return {
            "session": session,
            "bars": bars,
            "actions": actions,
            "decisions": decisions,
            "pnl": pnl,
            "is_live": False,
            "last_tick_i": last_i,
        }

    # Live path: use only what has been revealed
    try:
        meta, ticks, end = _parse_stream(sdir / "stream.jsonl")
    except Exception:
        logger.debug("parse_stream failed for live view %s", sdir.name, exc_info=True)
        meta = None
    if meta is None:
        # brand new, only session.json exists
        return {
            "session": session,
            "bars": [],
            "actions": [],
            "decisions": [],
            "pnl": {},
            "is_live": True,
            "last_tick_i": None,
        }

    decisions_raw = _read_jsonl(sdir / "decisions.jsonl")
    # NO-LOOK-AHEAD (live): the stream file may physically contain the WHOLE day
    # — the skill writes every bar at once with `replay --delay 0`, so "on disk"
    # is not "revealed". Show only bars the agent has actually PROCESSED: up to the
    # furthest bar index it has logged a decision for. Before the first decision,
    # show nothing (conservative). Also pass end=None so we never force-close the
    # position at the (future, unrevealed) session close.
    processed_i = max((d.get("i", -1) for d in decisions_raw), default=-1)
    ticks = [t for t in ticks if t.get("i", 0) <= processed_i]

    # IMPORTANT: for live we deliberately use ONLY the revealed stream ticks
    # (no _full_day_bars call)
    stream_bars = _build_bars(meta, ticks)
    actions, timeline, pnl = _run_session_engine(
        session, meta, stream_bars, decisions_raw, None, force_close=False
    )

    last_i = max([b.get("i", -1) for b in stream_bars]) if stream_bars else None

    # Merge some live info into the returned session dict for convenience
    live_session = dict(session)
    live_session.setdefault("status", "running")
    live_session.setdefault("strategy", _strategy_of(session))
    # Setup chips (gap / ATR / targets) come from stream meta until finalize
    # writes them permanently into session.json.
    if not live_session.get("setup") and meta:
        live_session["setup"] = _setup_from_meta(meta)

    return {
        "session": live_session,
        "bars": stream_bars,
        "actions": actions,
        "decisions": timeline,
        "pnl": pnl,
        "is_live": True,
        "last_tick_i": last_i,
    }


# cache the (heavier) live-pnl recompute per session, keyed by input-file mtime,
# so repeated /api/sessions polls don't re-run the engine on unchanged sessions.
# The viewer server is threaded, so guard the dict with a lock; bound its size so a
# long-lived server that has viewed thousands of sessions can't grow it unbounded.
_LIVE_PNL_CACHE_MAX = 512
_live_pnl_cache: dict[str, tuple[float, Optional[dict]]] = {}
_live_pnl_lock = threading.Lock()
_completed_mtime_cache: dict[str, float] = {}


def _live_pnl_snapshot(sdir: Path, mtime: Optional[float] = None) -> Optional[dict]:
    sid = sdir.name
    if mtime is None:
        mtime = 0.0
        for name in ("stream.jsonl", "decisions.jsonl"):
            f = sdir / name
            if f.exists():
                mtime = max(mtime, f.stat().st_mtime)
    with _live_pnl_lock:
        cached = _live_pnl_cache.get(sid)
        if cached and cached[0] == mtime:
            return cached[1]
    snapshot = None
    try:
        live = get_session_view(sdir)
        lp = live.get("pnl", {}) or {}
        if lp:
            decs = live.get("decisions") or []
            snapshot = {
                "realized_pnl": lp.get("realized_pnl"),
                "unrealized": decs[-1].get("unrealized") if decs else None,
            }
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
        # Expected for half-written running sessions or missing artifacts
        logger.debug("live pnl snapshot failed for %s: %s", sid, e)
        snapshot = None
    except Exception:
        logger.debug("live pnl snapshot unexpected error for %s", sid, exc_info=True)
        snapshot = None
    with _live_pnl_lock:
        # Bound the cache: drop oldest (by insertion) when full for a new key.
        # Use a simple pop of first item; for very large histories consider LRU.
        if len(_live_pnl_cache) >= _LIVE_PNL_CACHE_MAX and sid not in _live_pnl_cache:
            try:
                oldest = next(iter(_live_pnl_cache))
                _live_pnl_cache.pop(oldest, None)
            except StopIteration:
                pass
        _live_pnl_cache[sid] = (mtime, snapshot)
    return snapshot


def _session_newest_mtime(d: Path, is_complete: bool = False) -> float:
    """Newest write to any live file — the session's real wall-clock last activity."""
    sid = d.name
    if is_complete and sid in _completed_mtime_cache:
        return _completed_mtime_cache[sid]
    newest = 0.0
    for name in ("decisions.jsonl", "stream.jsonl", "session.json"):
        f = d / name
        if f.exists():
            newest = max(newest, f.stat().st_mtime)
    if is_complete and newest > 0:
        _completed_mtime_cache[sid] = newest
    return newest


def _top_level_id(s: dict, d: Path) -> str:
    """Single source of truth for grouping leaf sessions under a top-level id.

    Prefers the explicit "session" field (live day or batch tag), falls back to
    legacy "batch", then the leaf "id", then folder name. This centralizes the
    logic that previously used repeated ternaries and prevents drift.
    """
    return s.get("session") or s.get("batch") or s.get("id") or d.name


def _session_entry(d: Path, s: dict) -> dict:
    """Lightweight summary of one session folder (for the list + batch views)."""
    # Last activity = newest live-file write as real wall-clock time (NOT the last
    # decision's historical bar clock like "10:23", which would sort nonsensically).
    status = s.get("status", "running")
    newest_mtime = _session_newest_mtime(d, is_complete=(status == "complete"))
    last_ts = (
        datetime.fromtimestamp(newest_mtime).isoformat(timespec="seconds")
        if newest_mtime
        else s.get("finalized_ts") or s.get("real_run_ts")
    )

    # A "running" session whose files haven't changed in a while was almost certainly
    # abandoned (crash / closed terminal) — flag it so the UI can distinguish it from
    # a live one instead of showing it green forever.
    stale = (
        status != "complete"
        and newest_mtime > 0
        and (time.time() - newest_mtime) > _STALE_AFTER_S
    )

    cfg = s.get("config") or {}
    entry = {
        "id": s.get("id") or d.name,
        "ticker": s.get("ticker"),
        "historical_date": s.get("historical_date"),
        "real_run_ts": s.get("real_run_ts"),
        "finalized_ts": s.get("finalized_ts"),
        "mode": s.get("mode", "simulated"),
        "status": status,
        "stale": stale,
        "result": s.get("result"),
        "last_activity": last_ts,
        # batch attribution (null for ad-hoc sessions) so the UI can group / filter
        "batch": s.get("batch"),
        "skill_version": (s.get("skill") or {}).get("version"),
        "strategy": _strategy_of(s),
        "horizon": cfg.get("horizon") or (s.get("skill") or {}).get("horizon"),
        "bar_resolution": cfg.get("bar_resolution") or (s.get("skill") or {}).get("bar_resolution"),
        "void": s.get("void"),
        "out_of_credits": s.get("out_of_credits"),
        "timed_out": s.get("timed_out"),
        "finalize_error": s.get("finalize_error"),
        "no_decision_log": s.get("no_decision_log"),
        "agent_abandoned": s.get("agent_abandoned"),
    }

    # For running sessions, include a current PnL snapshot (mtime-cached).
    if status != "complete":
        snap = _live_pnl_snapshot(d, mtime=newest_mtime)
        if snap:
            entry["live_pnl"] = snap

    return entry


def _skills_dir_for(strategy_id: str = "warrior") -> Path:
    """Skill tree root for a family (CHANGELOG + skill_versions.json)."""
    try:
        from .strategies import get_strategy
        return get_strategy(strategy_id or "warrior").skills_dir()
    except Exception:
        return SKILLS_DIR


def _version_status_map(strategy_id: str = "warrior") -> dict[str, str]:
    """Map each skill version → a highlight bucket for the sessions table:

        "base"       accepted baseline lineage (registry `base`, PROMOTE'd, kept) → green
        "candidate"  under test, not yet accepted (HOLD / "not yet validated")   → blue
        "rejected"   failed / superseded experiment (REJECT)                      → red

    Versions with no clear signal (e.g. pre-methodology) are omitted (no tint).
    Scoped to one strategy family's skills dir so warrior and cup_handle never
    share a tint map.
    """
    skills_dir = _skills_dir_for(strategy_id)
    out: dict[str, str] = {}
    try:
        text = (skills_dir / "CHANGELOG.md").read_text()
    except OSError:
        text = ""
    # Each experiment is a "### <versions> — <title> …" section. Split on the header
    # marker; take the versions from the header's lead (before the em-dash) only, so a
    # version merely *mentioned* in the title (e.g. "decompose the 2.6.0 REJECT") is
    # not misclassified by a neighbour's section.
    for sec in re.split(r"(?m)^### ", text):
        head = sec.splitlines()[0] if sec else ""
        lead = head.split("—", 1)[0]  # em-dash separates versions from the title
        versions = re.findall(r"\d+\.\d+\.\d+", lead)
        if not versions:
            continue
        m = re.search(r"\*\*Decision:\*\*(.+)", sec)
        verdict = (m.group(1) if m else head).upper()
        # The ✅/❌/⏳ emoji is the authoritative verdict marker; keyword fallbacks
        # cover the emoji-less "keep." lines and header text. Order matters: test
        # candidate (HOLD) before base so a line like "HOLD — do not treat as
        # promoted" classifies as candidate, not base.
        if "❌" in verdict or "REJECT" in verdict or "SUPERSED" in verdict:
            bucket = "rejected"
        elif "⏳" in verdict or "HOLD" in verdict or "CANDIDATE" in verdict or "NOT YET VALIDATED" in verdict:
            bucket = "candidate"
        elif "✅" in verdict or "PROMOTE" in verdict or re.search(r"\bKEEP\b", verdict):
            bucket = "base"
        else:
            bucket = None
        if bucket:
            for v in versions:
                out.setdefault(v, bucket)  # newest section (listed first) wins
    # The registry's declared base is authoritative — it is always green.
    try:
        reg = json.loads((skills_dir / "skill_versions.json").read_text())
        if reg.get("base"):
            out[reg["base"]] = "base"
    except (OSError, ValueError):
        pass
    return out


def list_sessions() -> list[dict]:
    """Return top-level sessions (live or simulated batches). New primary grouping."""
    vstatus_cache: dict[str, dict[str, str]] = {}
    groups: dict[str, list] = defaultdict(list)
    for d, s in iter_sessions():
        if _is_archived(s):
            continue  # hidden from the lists (both the table and the sidebar use this)
        sid = _top_level_id(s, d)
        groups[sid].append((d, s))
    out = []
    for sid, items in groups.items():
        modes = {ss.get("mode", "simulated") for _, ss in items}
        sess_type = "live" if "live" in modes else "simulated"
        total_pnl = 0.0
        n_traded = 0   # leaf sessions that actually took a trade
        n_fills = 0    # blotter fills across those sessions
        n_wins = 0
        tickers = set()
        strategies: set[str] = set()
        last_activity = None
        name = None
        version = None
        n_complete = 0   # leaf sessions that have finalized
        for d, ss in items:
            res = ss.get("result") or {}
            tickers.add(ss.get("ticker"))
            strategies.add(_strategy_of(ss))
            # "complete" = finalized AND ran; an out-of-credits or timed-out run
            # finalized as an empty stub but never ran, so it does not count as progress.
            if ss.get("status") == "complete" and not _is_infra_fail(ss):
                n_complete += 1
            if res.get("traded"):
                total_pnl += res.get("realized_pnl", 0) or 0.0
                n_traded += 1
                n_fills += res.get("n_fills", 1) or 0
                if res.get("win"):
                    n_wins += 1
            ts = ss.get("finalized_ts") or ss.get("real_run_ts")
            if ts and (not last_activity or ts > last_activity):
                last_activity = ts
            if name is None and ss.get("batch"):
                name = ss.get("batch")  # human label = batch tag if present
            if version is None:
                version = (ss.get("skill") or {}).get("version")
        # win rate is winning *sessions* over traded *sessions* — NOT over fills
        # (a single 3-fill winner must read 100%, not 33%).
        win_rate = round(n_wins / n_traded * 100, 1) if n_traded else None
        # batch.json (keyed by the human tag = `name`) carries the hermes model
        # and the pinned skill version. Fall back to the leaf skill version.
        bmeta = _batch_meta(name) if name else {}
        strategy = (
            bmeta.get("strategy")
            or (next(iter(strategies)) if len(strategies) == 1 else None)
            or ("mixed" if len(strategies) > 1 else "warrior")
        )
        # Ongoing vs completed. Prefer the batch's own status flag (batchsim writes
        # "running" at start, "complete" at finish); otherwise infer from the leaves:
        # still running if any leaf hasn't finalized or fewer leaves exist than planned.
        planned = bmeta.get("planned")
        meta_status = bmeta.get("status")
        if meta_status in ("running", "complete"):
            status = meta_status
        else:
            leaves_pending = n_complete < len(items) or (
                isinstance(planned, int) and len(items) < planned)
            status = "running" if leaves_pending else "complete"
        # Edge metrics (expectancy, PF, dispersion) — same computation the tickers
        # detail view already shows, surfaced here so versions/models are rankable.
        metrics = _compute_batch_metrics([ss for _, ss in items])
        dist = metrics.get("r_distribution") or {}
        pf = metrics.get("profit_factor_r")
        # inf/nan would serialize as JS-invalid `Infinity`/`NaN` and break
        # JSON.parse for the whole response — send null instead.
        if isinstance(pf, float) and (pf != pf or pf in (float("inf"), float("-inf"))):
            pf = None
        ver = version or bmeta.get("version")
        # Version tint from that family's CHANGELOG/registry — never cross-family.
        strat_for_tint = strategy if strategy != "mixed" else "warrior"
        if strat_for_tint not in vstatus_cache:
            vstatus_cache[strat_for_tint] = _version_status_map(strat_for_tint)
        out.append({
            "id": sid,
            "name": name or sid,
            "type": sess_type,
            "strategy": strategy,
            "version": ver,
            "version_status": vstatus_cache[strat_for_tint].get(ver) if ver else None,
            "model": bmeta.get("model"),
            "pnl": round(total_pnl, 2),
            "n_tickers": len(tickers),
            "n_trades": n_traded,   # traded sessions (matches win_rate denominator)
            "n_fills": n_fills,
            "win_rate": win_rate,
            "expectancy_r": metrics.get("clean_expectancy_r"),
            "effective_r": metrics.get("effective_expectancy_r"),
            "std_r": dist.get("std"),
            "profit_factor_r": pf,
            "avg_win_r": metrics.get("avg_win_r"),
            "avg_loss_r": metrics.get("avg_loss_r"),
            "n_planned": metrics.get("n_planned"),
            "n_void": metrics.get("n_void"),
            "n_out_of_credits": metrics.get("n_out_of_credits"),
            "n_timed_out": metrics.get("n_timed_out"),
            "n_finalize_error": metrics.get("n_finalize_error"),
            "last_activity": last_activity,
            "status": status,
            "n_complete": n_complete,
            "planned": planned if isinstance(planned, int) else len(items),
        })
    out.sort(key=lambda x: (x.get("last_activity") or ""), reverse=True)
    return out


# ───────────────────────────── batches ──────────────────────────────────────

BATCH_ROOT = SIM_ROOT / "_batch"


def _batch_meta(tag: str) -> dict:
    """Metadata a `batchsim run` writes at start/finish (planned count, version,
    model, status). Empty dict if the batch predates metadata or was hand-audited."""
    return _load_json(BATCH_ROOT / tag / "batch.json", {}) or {}


# ───────────────────────────── metric helpers (synthesized from proposal) ────

def _r_from_session(s: dict) -> Optional[float]:
    """Extract the primary R for a leaf session dict (prefers actual if present)."""
    res = s.get("result") or {}
    r = res.get("r_multiple_actual")
    if r is None:
        r = res.get("r_multiple")
    return r if isinstance(r, (int, float)) else None


def _is_void(s: dict) -> bool:
    v = s.get("void")
    return bool(v) and v != "false"


def _is_out_of_credits(s: dict) -> bool:
    """A run whose agent never executed because the API was out of credits (HTTP 402).
    An infrastructure failure — excluded from stats, shown distinctly from a void."""
    return bool(s.get("out_of_credits"))


def _is_timed_out(s: dict) -> bool:
    """A run the harness KILLED for exceeding its per-setup timeout. Like out-of-credits
    it is an infrastructure failure — never a clean 'complete no-trade': excluded from
    stats (no penalty), shown distinctly from a void, and re-run by ``--resume``."""
    return bool(s.get("timed_out"))


def _is_finalize_error(s: dict) -> bool:
    """A run whose finalize() replay raised (e.g. an inconsistent decision log —
    an EXIT with no matching prior ENTER). status never reached "complete", so
    this is stamped explicitly (batchsim._stamp_finalize_error) rather than left
    as an orphaned "running" leaf. Infra failure: excluded from stats, re-run by
    ``--resume``, never a clean 'complete no-trade'."""
    return bool(s.get("finalize_error"))


def _is_no_decision_log(s: dict) -> bool:
    """True when an agent finalized without logging even one required intent.

    This is an infrastructure/agent failure, not a valid strategy stand-down. It
    is stamped by batchsim and treated like timeout/out-of-credits everywhere
    that computes batch metrics or resume eligibility.
    """
    return bool(s.get("no_decision_log"))


def _is_agent_abandoned(s: dict) -> bool:
    """True when the agent stopped the loop while still armed or in a position.

    Stamped by batchsim after finalize. Artifacts remain viewable (status complete)
    but the run is excluded from stats and re-run by ``--resume``.
    """
    return bool(s.get("agent_abandoned"))


def _is_infra_fail(s: dict) -> bool:
    """Any non-result infra failure (out-of-credits, timeout, or finalize error):
    the agent didn't run to a real decision, so the run is excluded from stats
    rather than scored."""
    return (_is_out_of_credits(s) or _is_timed_out(s) or _is_finalize_error(s)
            or _is_no_decision_log(s) or _is_agent_abandoned(s))


def _is_archived(s: dict) -> bool:
    """User hid this session from the viewer lists via the Archive button. Purely a
    UI filter — kept as a separate flag (not `status`) so it does NOT affect batch
    resume/metrics/audit, which key off `status == "complete"`."""
    return bool(s.get("archived"))


def _stamp_archived(sdir: Path, value: bool = True) -> None:
    """Set/clear the `archived` flag on a leaf's session.json (atomic)."""
    sj = Path(sdir) / "session.json"
    s = _load_json(sj, {}) or {}
    if value:
        s["archived"] = True
    else:
        s.pop("archived", None)
    atomic_write_json(sj, s, indent=2)


def archive_session(sid: str, *, archived: bool = True) -> int:
    """Archive (or un-archive) a session the viewer shows. Accepts EITHER a concrete
    leaf dir name (archives just that run) OR a top-level/batch group id (archives every
    member leaf). Returns the number of leaves stamped. Archived sessions are dropped
    from list_sessions / the tickers view but remain on disk and re-openable by URL."""
    n = 0
    leaf = SIM_ROOT / sid
    if (leaf / "session.json").exists():
        _stamp_archived(leaf, archived)
        return 1
    for d, _s in _iter_session_members(sid):
        _stamp_archived(d, archived)
        n += 1
    return n


def _resolved_slots(members: list[dict]) -> set:
    """(ticker, historical_date) slots that have a genuinely completed, non-void,
    non-out-of-credits leaf. `--resume` reruns a failed slot into a NEW leaf directory
    without deleting the old stub, so a stale out-of-credits/void leaf can outlive the
    clean run that superseded it — this tells the metrics/badges which stubs to ignore."""
    return {
        (m.get("ticker"), m.get("historical_date")) for m in members
        if m.get("status") == "complete" and not _is_void(m) and not _is_infra_fail(m)
    }


def _compute_batch_metrics(members: list[dict]) -> dict:
    """Compute clean and effective metrics for a top-level batch from list of member session views.
    members are the dicts from _session_entry (have 'result', possibly 'live_pnl', 'void').
    """
    resolved = _resolved_slots(members)
    clean_rs: list[float] = []
    effective_rs: list[float] = []
    n_planned = 0
    n_void = 0
    n_out_of_credits = 0
    n_timed_out = 0
    n_finalize_error = 0
    n_no_decision_log = 0
    n_agent_abandoned = 0
    n_stood = 0
    n_traded = 0
    total_pnl = 0.0
    for m in members:
        slot = (m.get("ticker"), m.get("historical_date"))
        # A void/infra-failed leaf whose slot was later resolved by a clean --resume
        # run is a stale historical stub, not a result — exclude it entirely (the
        # resolved leaf already contributes its own counts), so old failed attempts
        # stop lingering in aggregate stats/badges after a successful resume.
        if (_is_void(m) or _is_infra_fail(m)) and slot in resolved:
            continue
        # Infra failures (out-of-credits / timed-out) are not results: exclude entirely
        # (no penalty, not a stand-down) so expectancy/PF/win-rate stay clean over the
        # runs that actually executed.
        if _is_out_of_credits(m):
            n_out_of_credits += 1
            continue
        if _is_timed_out(m):
            n_timed_out += 1
            continue
        if _is_finalize_error(m):
            n_finalize_error += 1
            continue
        if _is_no_decision_log(m):
            n_no_decision_log += 1
            continue
        if _is_agent_abandoned(m):
            n_agent_abandoned += 1
            continue
        n_planned += 1
        if _is_void(m):
            n_void += 1
            effective_rs.append(-1.0)  # penalty
            continue
        r = _r_from_session(m)
        res = m.get("result") or {}
        traded = bool(res.get("traded"))
        if not traded:
            n_stood += 1
            effective_rs.append(0.0)
            continue
        if r is not None:
            clean_rs.append(r)
            effective_rs.append(r)
            total_pnl += res.get("realized_pnl", 0) or 0.0
            n_traded += 1
        else:
            # fallback
            effective_rs.append(0.0)
    n_clean = len(clean_rs)
    clean_exp = round(sum(clean_rs) / n_clean, 4) if n_clean > 0 else None
    eff_exp = round(sum(effective_rs) / len(effective_rs), 4) if effective_rs else None

    wins = [r for r in clean_rs if r > 0]
    losses = [r for r in clean_rs if r < 0]
    pos = sum(wins)
    neg = abs(sum(losses))
    # Never emit float("inf") — json.dumps writes the token Infinity which is not
    # valid JSON and breaks the browser viewer (JSON.parse). No-loss books → null.
    pf = round(pos / neg, 4) if neg > 0 else None
    avg_win_r = round(pos / len(wins), 4) if wins else None
    avg_loss_r = round(-neg / len(losses), 4) if losses else None

    # distribution
    if clean_rs:
        clean_rs_sorted = sorted(clean_rs)
        n = len(clean_rs_sorted)
        mean_r = round(sum(clean_rs_sorted) / n, 4)
        med_r = round(clean_rs_sorted[n // 2] if n % 2 else (clean_rs_sorted[n//2-1] + clean_rs_sorted[n//2]) / 2, 4)
        # simple std
        var = sum((x - mean_r)**2 for x in clean_rs_sorted) / n if n > 1 else 0.0
        std_r = round(var ** 0.5, 4)
        p10 = clean_rs_sorted[max(0, int(0.1 * (n-1)))]
        p90 = clean_rs_sorted[min(n-1, int(0.9 * (n-1)))]
        dist = {"mean": mean_r, "median": med_r, "std": std_r, "p10": round(p10,4), "p90": round(p90,4), "min": round(min(clean_rs_sorted),4), "max": round(max(clean_rs_sorted),4)}
    else:
        dist = None

    # sequence drawdown using deterministic order by leaf id (stable across runs)
    ordered_eff = []
    for m in sorted(members, key=lambda x: x.get("id", "")):
        slot = (m.get("ticker"), m.get("historical_date"))
        if (_is_void(m) or _is_infra_fail(m)) and slot in resolved:
            continue  # stale stub superseded by a later resume — not a real result
        if _is_infra_fail(m):
            continue  # infra failure (ooc / timeout) — not part of the traded sequence
        if _is_void(m):
            ordered_eff.append(-1.0)
        else:
            r = _r_from_session(m)
            res = m.get("result") or {}
            if res.get("traded"):
                ordered_eff.append(r or 0.0)
            else:
                ordered_eff.append(0.0)
    cum = 0.0
    peak = 0.0
    seq_dd = 0.0
    for r in ordered_eff:
        cum += r
        if cum > peak:
            peak = cum
        dd = cum - peak
        if dd < seq_dd:
            seq_dd = dd
    seq_dd = round(-seq_dd, 4) if seq_dd < 0 else 0.0
    recovery = round(total_pnl / seq_dd, 4) if seq_dd > 0 else None
    if isinstance(recovery, float) and (recovery != recovery or abs(recovery) == float("inf")):
        recovery = None

    return {
        "clean_expectancy_r": clean_exp,
        "effective_expectancy_r": eff_exp,
        "profit_factor_r": pf,
        "avg_win_r": avg_win_r,
        "avg_loss_r": avg_loss_r,
        "r_distribution": dist,
        "n_planned": n_planned,
        "n_traded": n_traded,
        "n_void": n_void,
        "n_out_of_credits": n_out_of_credits,
        "n_timed_out": n_timed_out,
        "n_finalize_error": n_finalize_error,
        "n_no_decision_log": n_no_decision_log,
        "n_agent_abandoned": n_agent_abandoned,
        "n_stood_down": n_stood,
        "sequence_drawdown_r": seq_dd,
        "recovery_factor_r": recovery,
        "total_pnl": round(total_pnl, 2),
    }


def _iter_session_members(sess_id: str):
    """Yield leaves belonging to a top-level session (by ``session`` or ``batch`` field).

    Uses the single _top_level_id resolver so grouping never drifts between
    list_sessions, get_top_session_view, and reporting.
    """
    for d, s in iter_sessions():
        if _top_level_id(s, d) == sess_id:
            yield d, s


def get_top_session_view(sess_id: str) -> dict:
    """Detail for a top-level session (batch or live day): list of tickers with aggregates."""
    tickers: dict[str, dict] = defaultdict(lambda: {
        "ticker": None,
        "n_traded": 0,   # leaf runs on this ticker that traded (win_rate denominator)
        "n_fills": 0,    # blotter fills across those runs
        "pnl": 0.0,
        "wins": 0,
        "leaf_id": None,
        "n_void": 0,       # leaf runs on this ticker the audit voided
        "void_reason": None,  # a representative void reason for the UI
        "n_out_of_credits": 0,  # leaf runs that died on HTTP 402 (out of credits)
        "n_timed_out": 0,  # leaf runs the harness killed for exceeding the timeout
        "n_finalize_error": 0,  # leaf runs whose finalize() replay raised
        "n_no_decision_log": 0,  # complete leaf with no agent intent
        "n_agent_abandoned": 0,  # agent stopped while armed / in position
        "n_leaves": 0,     # total leaf runs on this ticker
        "n_complete": 0,   # of those, how many are finalized
        "running_any": False,
        "stale_any": False,
    })
    members = []
    batch_tag = None
    modes = set()
    strategies: set[str] = set()
    for d, s in _iter_session_members(sess_id):
        if _is_archived(s):
            continue  # archived leaves are hidden from the tickers view too
        entry = _session_entry(d, s)
        members.append(entry)
        strategies.add(entry.get("strategy") or "warrior")
        if not batch_tag:
            batch_tag = s.get("batch")
        modes.add(s.get("mode", "simulated"))
        t = s.get("ticker")
        res = s.get("result") or {}
        td = tickers[t]
        td["ticker"] = t
        # progress: is this leaf finalized-and-ran, still running, stale (abandoned),
        # or out-of-credits (terminal, but never actually ran — so NOT "complete")?
        td["n_leaves"] += 1
        if _is_out_of_credits(s):
            td["n_out_of_credits"] += 1   # terminal; neither complete nor running
        elif _is_timed_out(s):
            td["n_timed_out"] += 1        # terminal infra failure; never "complete"
        elif _is_finalize_error(s):
            td["n_finalize_error"] += 1   # terminal infra failure; never "complete"
        elif _is_no_decision_log(s):
            td["n_no_decision_log"] += 1  # completed artifacts, but no trading decision
        elif _is_agent_abandoned(s):
            td["n_agent_abandoned"] += 1  # stopped mid-plan; not a clean complete
        elif entry.get("status") == "complete":
            td["n_complete"] += 1
        elif entry.get("stale"):
            td["stale_any"] = True
        else:
            td["running_any"] = True
        if _is_void(s):
            td["n_void"] += 1
            if not td["void_reason"]:
                td["void_reason"] = str(s.get("void"))
        if res.get("traded") and not _is_infra_fail(s):
            td["n_traded"] += 1
            td["n_fills"] += res.get("n_fills", 1) or 0
            td["pnl"] += res.get("realized_pnl", 0) or 0.0
            if res.get("win"):
                td["wins"] += 1
            if "r" not in td or td["r"] is None:
                td["r"] = res.get("r_multiple_actual") or res.get("r_multiple")
        if not td["leaf_id"]:
            td["leaf_id"] = s.get("id") or d.name
    ticker_list = []
    n_complete_total = 0
    n_running_total = 0
    for t, data in tickers.items():
        n = data["n_traded"]
        # win% is winning runs over traded runs — not over fills (see list_sessions).
        wr = round((data["wins"] / n * 100), 1) if n > 0 else None
        # per-ticker rollup status. "complete" means at least one leaf actually ran
        # and finalized; a ticker whose only leaves hit HTTP 402 never ran, so it is
        # "out_of_credits", NOT complete. (stale = a running leaf whose files went
        # quiet, treated as abandoned.)
        if data["running_any"]:
            tstatus = "running"
        elif data["n_complete"] > 0:
            tstatus = "complete"
        elif data["n_out_of_credits"] > 0:
            tstatus = "out_of_credits"
        elif data["n_timed_out"] > 0:
            tstatus = "timeout"
        elif data["n_finalize_error"] > 0:
            tstatus = "finalize_error"
        elif data["n_no_decision_log"] > 0:
            tstatus = "no_decision_log"
        elif data["n_agent_abandoned"] > 0:
            tstatus = "agent_abandoned"
        elif data["stale_any"]:
            tstatus = "stale"
        else:
            tstatus = "running"
        if tstatus == "complete":
            n_complete_total += 1
        elif tstatus == "running":
            n_running_total += 1
        ticker_list.append({
            "ticker": t,
            "n_trades": n,   # traded runs (matches win_rate denominator)
            "n_fills": data["n_fills"],
            "pnl": round(data["pnl"], 2),
            "win_rate": wr,
            "leaf_id": data["leaf_id"],
            "r": data.get("r"),
            "n_void": data["n_void"],
            "void_reason": data["void_reason"],
            "n_out_of_credits": data["n_out_of_credits"],
            "n_timed_out": data["n_timed_out"],
            "n_finalize_error": data["n_finalize_error"],
            "n_no_decision_log": data["n_no_decision_log"],
            "n_agent_abandoned": data["n_agent_abandoned"],
            "status": tstatus,
            "n_leaves": data["n_leaves"],
            "n_complete": data["n_complete"],
        })
    ticker_list.sort(key=lambda x: x["ticker"])

    meta = (_batch_meta(batch_tag) if batch_tag else None) or _batch_meta(sess_id) or {}
    name = meta.get("tag") or meta.get("name") or batch_tag or sess_id
    sess_type = "live" if "live" in modes else "simulated"
    strategy = (
        meta.get("strategy")
        or (next(iter(strategies)) if len(strategies) == 1 else None)
        or ("mixed" if len(strategies) > 1 else "warrior")
    )

    batch_metrics = _compute_batch_metrics(members) if members else {}
    # is the whole top-level session still in progress? drives the viewer's live refresh.
    planned = meta.get("planned")
    is_running = n_running_total > 0 or (isinstance(planned, int) and len(members) < planned)

    return {
        "id": sess_id,
        "name": name,
        "meta": meta,
        "type": sess_type,
        "strategy": strategy,
        "tickers": ticker_list,
        "sessions": members,
        "metrics": batch_metrics,
        "n_tickers": len(ticker_list),
        "n_complete": n_complete_total,
        "n_running": n_running_total,
        "is_running": is_running,
    }


# ───────────────────────────── reporting ────────────────────────────────────


def report_by_version(
    mode: Optional[str] = None, batch: Optional[str] = None
) -> list[dict]:
    """Aggregate finalized sessions by skill version → profitability rows.

    One row per ``skill_version`` (versionless sessions bucket as ``"unversioned"``).
    Stats are over *traded, non-void* sessions; stood-down runs are counted in
    ``stood_down`` and audit-voided runs in ``n_void`` (both excluded from win%/P&L/R).
    ``hashes`` carries the distinct content hashes seen for the version, to flag drift.

    ``mode`` restricts to simulated/live. ``batch`` restricts to one backtest cohort
    (matched against ``session.batch`` / ``pnl.batch``) — the apples-to-apples view.
    """
    # `--resume` reruns a failed/voided (batch,ticker,date) slot into a NEW leaf dir
    # without deleting the old stub, so a stale void/out-of-credits/timed-out/
    # finalize-error stub can outlive the clean run that superseded it. Without this,
    # both the stub and its replacement get counted, inflating `n` past `planned` and
    # showing phantom failures a resume already fixed. Same slot-resolution concept as
    # `_resolved_slots` (used by the per-session-view metrics), scoped here by
    # (batch, ticker, date) since this aggregates across many top-level sessions.
    resolved_slots: set[tuple] = set()
    for _, s in iter_sessions():
        if s.get("status") == "complete" and not _is_void(s) and not _is_infra_fail(s):
            resolved_slots.add((s.get("batch"), s.get("ticker"), s.get("historical_date")))

    buckets: dict[str, dict] = {}
    fin_err_buckets: dict[str, int] = defaultdict(int)
    no_intent_buckets: dict[str, int] = defaultdict(int)
    for d, session in iter_sessions():
        slot = (session.get("batch"), session.get("ticker"), session.get("historical_date"))
        if _is_finalize_error(session):
            if slot in resolved_slots:
                continue  # stale stub superseded by a later --resume — not a real result
            # finalize() never wrote pnl.json / status="complete" for these, so they'd
            # otherwise vanish below with no count anywhere — track them by the pinned
            # skill version (finalize errors happen pre-pnl, so read it off session.skill).
            if mode is None or session.get("mode", "simulated") == mode:
                sbatch = session.get("batch")
                if batch is None or sbatch == batch:
                    ver = session.get("skill", {}).get("version") or "unversioned"
                    fin_err_buckets[ver] += 1
            continue
        if _is_no_decision_log(session):
            if slot in resolved_slots:
                continue
            if mode is None or session.get("mode", "simulated") == mode:
                sbatch = session.get("batch")
                if batch is None or sbatch == batch:
                    ver = session.get("skill", {}).get("version") or "unversioned"
                    no_intent_buckets[ver] += 1
            continue
        pnl = _load_json(d / "pnl.json")
        if pnl is None or session.get("status") != "complete":
            continue  # skip running/abandoned/unfinalized sessions
        if mode is not None and session.get("mode", "simulated") != mode:
            continue
        sbatch = session.get("batch") or pnl.get("batch")
        if batch is not None and sbatch != batch:
            continue
        if (_is_void(session) or _is_infra_fail(session)) and slot in resolved_slots:
            continue  # stale void/ooc/timeout stub superseded by a later --resume

        ver = pnl.get("skill_version") or session.get("skill", {}).get("version") \
            or "unversioned"
        b = buckets.setdefault(ver, {
            "version": ver, "n": 0, "wins": 0, "stood_down": 0, "n_void": 0,
            "n_out_of_credits": 0, "n_timed_out": 0, "n_finalize_error": 0,
            "n_no_decision_log": 0,
            "pnl": 0.0, "r_sum": 0.0, "eff_r_sum": 0.0, "eff_n": 0,
            "cap_sum": 0.0, "cap_n": 0, "hashes": set(),
            "batches": set(), "models": set(),
        })
        # Track the batch tags and models feeding this version's row, so the printer can
        # warn when a version is aggregated across multiple cohorts (mixing batches/models
        # makes the row invalid for ranking — use `batchsim compare` for that).
        sbtag = session.get("batch") or pnl.get("batch")
        if sbtag:
            b["batches"].add(sbtag)
        bmeta = _batch_meta(sbtag) if sbtag else {}
        if bmeta.get("model"):
            b["models"].add(bmeta["model"])
        h = pnl.get("skill_hash") or session.get("skill", {}).get("content_hash")
        if h:
            b["hashes"].add(h)
        if _is_out_of_credits(session):
            # Infra failure (HTTP 402), agent never traded — not a disciplined
            # stand-down and not a void; exclude from the cohort entirely.
            b["n_out_of_credits"] += 1
            continue
        if _is_timed_out(session):
            # Infra failure (harness killed the run at the timeout) — like out-of-credits,
            # the agent never reached a real decision; exclude from the cohort entirely.
            b["n_timed_out"] += 1
            continue
        if _is_no_decision_log(session):
            b["n_no_decision_log"] += 1
            continue
        if session.get("void") or pnl.get("void"):
            b["n_void"] += 1          # audit-tainted → excluded from stats
            continue
        # Effective R (deployment view): stood-down counts as 0R, so a version can't look
        # good merely by refusing marginal-but-profitable trades. Traded uses realized R.
        b["eff_n"] += 1
        if not pnl.get("traded"):
            b["stood_down"] += 1
            continue
        b["eff_r_sum"] += pnl.get("r_multiple") or 0.0
        b["n"] += 1
        b["wins"] += 1 if pnl.get("win") else 0
        b["pnl"] += pnl.get("realized_pnl") or 0.0
        b["r_sum"] += pnl.get("r_multiple") or 0.0
        # capture ("how much of the up-move you kept") is only meaningful on WINS —
        # a loser has negative capture, which would drag the cohort average into
        # nonsense. Average it over winners only.
        cap = pnl.get("mfe_capture")
        if cap is not None and pnl.get("win"):
            b["cap_sum"] += cap
            b["cap_n"] += 1

    rows = []
    for b in buckets.values():
        n = b["n"]
        rows.append({
            "version": b["version"],
            "n": n,
            "stood_down": b["stood_down"],
            "n_void": b["n_void"],
            "n_out_of_credits": b["n_out_of_credits"],
            "n_timed_out": b["n_timed_out"],
            "n_finalize_error": fin_err_buckets.pop(b["version"], 0),
            "n_no_decision_log": no_intent_buckets.pop(b["version"], 0),
            "win_pct": round(100 * b["wins"] / n) if n else None,
            "pnl": round(b["pnl"], 2),
            "avg_r": round(b["r_sum"] / n, 2) if n else None,          # clean (traded only)
            "eff_r": round(b["eff_r_sum"] / b["eff_n"], 2) if b["eff_n"] else None,  # deployment
            "avg_capture": round(b["cap_sum"] / b["cap_n"], 2) if b["cap_n"] else None,
            "n_batches": len(b["batches"]),
            "n_models": len(b["models"]),
            "hashes": sorted(b["hashes"]),
        })
    # a version whose ONLY leaves are finalize-errors has no bucket above (never
    # traded/stood-down) — still surface it so the failure isn't invisible.
    for ver in sorted(set(fin_err_buckets) | set(no_intent_buckets)):
        n_fe = fin_err_buckets[ver]
        n_no_intent = no_intent_buckets[ver]
        rows.append({
            "version": ver, "n": 0, "stood_down": 0, "n_void": 0,
            "n_out_of_credits": 0, "n_timed_out": 0, "n_finalize_error": n_fe,
            "n_no_decision_log": n_no_intent,
            "win_pct": None, "pnl": 0.0, "avg_r": None, "eff_r": None,
            "avg_capture": None, "n_batches": 0, "n_models": 0, "hashes": [],
        })
    rows.sort(key=lambda r: r["version"])
    return rows


def _print_report(rows: list[dict]) -> None:
    if not rows:
        print("no finalized sessions to report")
        return
    # cleanR = mean R over traded leaves; effR = deployment mean (stood-down = 0R).
    print(f"{'version':<14}{'n':>4}{'win%':>6}{'P&L':>10}{'cleanR':>8}{'effR':>7}{'capt':>6}  notes")
    mixed = False
    for r in rows:
        win = f"{r['win_pct']}%" if r["win_pct"] is not None else "—"
        avg = f"{r['avg_r']:.2f}" if r["avg_r"] is not None else "—"
        eff = f"{r['eff_r']:.2f}" if r.get("eff_r") is not None else "—"
        cap = f"{r['avg_capture']:.2f}" if r.get("avg_capture") is not None else "—"
        pnl = f"${r['pnl']:.2f}"
        notes = []
        if r["stood_down"]:
            notes.append(f"{r['stood_down']} stood down")
        if r.get("n_void"):
            notes.append(f"⚠ {r['n_void']} void")
        if r.get("n_out_of_credits"):
            notes.append(f"⚠ {r['n_out_of_credits']} out-of-credits")
        if r.get("n_timed_out"):
            notes.append(f"⚠ {r['n_timed_out']} timed-out")
        if r.get("n_finalize_error"):
            notes.append(f"⚠ {r['n_finalize_error']} finalize-error")
        if r.get("n_no_decision_log"):
            notes.append(f"⚠ {r['n_no_decision_log']} no-intent")
        # A version aggregated across >1 batch or >1 model is NOT a valid ranking row.
        if r.get("n_batches", 0) > 1:
            notes.append(f"⚠ {r['n_batches']} batches MIXED"); mixed = True
        if r.get("n_models", 0) > 1:
            notes.append(f"⚠ {r['n_models']} models MIXED"); mixed = True
        if len(r["hashes"]) > 1:
            notes.append(f"⚠ {len(r['hashes'])} distinct hashes (drift)")
        print(f"{r['version']:<14}{r['n']:>4}{win:>6}{pnl:>10}{avg:>8}{eff:>7}{cap:>6}  "
              f"{', '.join(notes)}")
    if mixed:
        print("\n⚠  Rows marked MIXED aggregate multiple batches/models and are NOT valid "
              "for ranking versions.\n   Rank a version pair with `batchsim compare --a <tagA> "
              "--b <tagB>` (paired, one batch each).")


# ───────────────────────── execution attribution ──────────────────────────


_ATTRIBUTION_PROFILES = (
    ("recorded", "frozen session execution assumptions"),
    ("no_commission", "commission = $0; slippage and participation cap retained"),
    ("no_slippage", "entry/exit slippage = 0 bps; commissions and cap retained"),
    ("no_participation_cap", "participation cap = 100% of each bar; costs retained"),
    ("frictionless", "zero commissions/slippage and 100% bar participation"),
)


def _attribution_configs(config: ExecutionConfig) -> dict[str, ExecutionConfig]:
    """Counterfactual configs for a frozen deterministic session.

    These intentionally vary exactly one execution assumption at a time from the
    recorded configuration, plus a fully frictionless reference.  The agent's
    sealed intent log is never changed or regenerated.
    """
    return {
        "recorded": config,
        "no_commission": replace(config, commission_per_share=0.0),
        "no_slippage": replace(config, entry_slippage_bps=0.0, exit_slippage_bps=0.0),
        "no_participation_cap": replace(config, max_participation_rate=1.0),
        "frictionless": replace(
            config,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            commission_per_share=0.0,
            max_participation_rate=1.0,
        ),
    }


def _aggregate_attribution_profile(name: str, description: str, results: list[dict],
                                   expected_n: int, errors: list[dict]) -> dict:
    """Summarize a list of deterministic ``ExecutionEngine`` P&L dictionaries."""
    traded = [p for p in results if p.get("traded")]
    r_sum = sum((p.get("r_multiple") or 0.0) for p in traded)
    pnl = round(sum((p.get("realized_pnl") or 0.0) for p in results), 2)
    return {
        "profile": name,
        "description": description,
        "n": len(results),
        "n_expected": expected_n,
        "n_errors": len(errors),
        "trades": len(traded),
        "stood_down": len(results) - len(traded),
        "wins": sum(1 for p in traded if p.get("win")),
        "win_pct": round(100 * sum(1 for p in traded if p.get("win")) / len(traded), 1)
        if traded else None,
        "pnl": pnl,
        "avg_r": round(r_sum / len(traded), 3) if traded else None,
        "eff_r": round(r_sum / len(results), 3) if results else None,
        "fees": round(sum((p.get("fees") or 0.0) for p in results), 2),
        "errors": errors,
    }


def execution_attribution(batch: str) -> dict:
    """Replay a deterministic batch under controlled execution assumptions.

    The report is read-only: it uses each completed session's sealed stream and
    append-only raw intents, then runs fresh in-memory :class:`ExecutionEngine`
    instances.  It is specifically an *execution* attribution, not a new
    strategy backtest—the decisions remain constant across every profile.

    Only clean deterministic-execution leaves in ``batch`` qualify.  A stored
    P&L mismatch for the ``recorded`` profile is retained in the result instead
    of being silently treated as a counterfactual difference.
    """
    if not batch:
        raise ValueError("batch is required for execution attribution")

    members = [(d, s) for d, s in iter_sessions() if s.get("batch") == batch]
    if not members:
        raise ValueError(f"no sessions found for batch {batch!r}")

    resolved = _resolved_slots([s for _, s in members])
    eligible: list[tuple[Path, dict]] = []
    skipped: list[dict] = []
    for sdir, session in members:
        slot = (session.get("ticker"), session.get("historical_date"))
        if (_is_void(session) or _is_infra_fail(session)) and slot in resolved:
            continue  # stale failed attempt superseded by a clean --resume leaf
        if session.get("status") != "complete":
            skipped.append({"session": sdir.name, "reason": "not complete"})
            continue
        if _is_void(session):
            skipped.append({"session": sdir.name, "reason": "void"})
            continue
        if _is_infra_fail(session):
            skipped.append({"session": sdir.name, "reason": "infrastructure failure"})
            continue
        if session.get("config", {}).get("execution_model") != EXECUTION_MODEL:
            skipped.append({"session": sdir.name, "reason": "not deterministic OHLC"})
            continue
        eligible.append((sdir, session))

    if not eligible:
        raise ValueError(
            f"batch {batch!r} has no completed {EXECUTION_MODEL} sessions to attribute"
        )

    profile_results: dict[str, list[dict]] = {name: [] for name, _ in _ATTRIBUTION_PROFILES}
    profile_errors: dict[str, list[dict]] = {name: [] for name, _ in _ATTRIBUTION_PROFILES}
    recorded_mismatches: list[dict] = []

    for sdir, session in eligible:
        meta, ticks, end = _parse_stream(sdir / "stream.jsonl")
        decisions = _read_jsonl(sdir / "decisions.jsonl")
        if meta is None or not ticks:
            skipped.append({"session": sdir.name, "reason": "missing sealed stream"})
            continue
        if not decisions:
            skipped.append({"session": sdir.name, "reason": "missing intent log"})
            continue

        bars = _build_bars(meta, ticks)
        stored_pnl = _load_json(sdir / "pnl.json", {}) or {}
        configs = _attribution_configs(
            ExecutionConfig.from_session_config(session.get("config", {}))
        )
        for name, _description in _ATTRIBUTION_PROFILES:
            try:
                _actions, _timeline, pnl = ExecutionEngine(configs[name]).run(
                    bars,
                    decisions,
                    end_close=(end or {}).get("close"),
                    force_close=True,
                )
            except Exception as e:  # preserve one bad historical artifact in the report
                profile_errors[name].append({"session": sdir.name, "error": str(e)})
                continue
            profile_results[name].append(pnl)
            if name == "recorded":
                replayed = pnl.get("realized_pnl")
                persisted = stored_pnl.get("realized_pnl")
                if not isinstance(persisted, (int, float)) or abs(replayed - persisted) > 0.005:
                    recorded_mismatches.append({
                        "session": sdir.name,
                        "persisted_pnl": persisted,
                        "replayed_pnl": replayed,
                    })

    expected_n = len(eligible)
    profiles = []
    for name, description in _ATTRIBUTION_PROFILES:
        row = _aggregate_attribution_profile(
            name, description, profile_results[name], expected_n, profile_errors[name]
        )
        profiles.append(row)

    recorded = next(row for row in profiles if row["profile"] == "recorded")
    for row in profiles:
        row["delta_pnl_vs_recorded"] = (
            round(row["pnl"] - recorded["pnl"], 2)
            if row["n"] == recorded["n"] else None
        )

    return {
        "batch": batch,
        "execution_model": EXECUTION_MODEL,
        "n_eligible": expected_n,
        "n_skipped": len(skipped),
        "skipped": skipped,
        "verification": {
            "recorded_replays": recorded["n"],
            "recorded_mismatches": recorded_mismatches,
        },
        "profiles": profiles,
    }


def _print_execution_attribution(report: dict) -> None:
    """Render the read-only execution-attribution report for the terminal."""
    print(f"execution attribution — batch {report['batch']} ({report['execution_model']})")
    verification = report["verification"]
    if verification["recorded_mismatches"]:
        print(f"⚠ recorded replay mismatch in {len(verification['recorded_mismatches'])} session(s)")
    else:
        print(f"recorded replay verified for {verification['recorded_replays']} session(s)")
    print(
        f"{'profile':<22}{'n':>4}{'trades':>8}{'win%':>7}{'P&L':>11}"
        f"{'Δ P&L':>10}{'cleanR':>8}{'effR':>7}{'fees':>10}"
    )
    for row in report["profiles"]:
        win = f"{row['win_pct']:.1f}%" if row["win_pct"] is not None else "—"
        pnl = f"${row['pnl']:.2f}"
        fees = f"${row['fees']:.2f}"
        delta = "—" if row["profile"] == "recorded" else (
            f"${row['delta_pnl_vs_recorded']:.2f}"
            if row["delta_pnl_vs_recorded"] is not None else "incomplete"
        )
        clean_r = f"{row['avg_r']:.3f}" if row["avg_r"] is not None else "—"
        eff_r = f"{row['eff_r']:.3f}" if row["eff_r"] is not None else "—"
        note = f" ⚠ {row['n_errors']} replay error(s)" if row["n_errors"] else ""
        print(
            f"{row['profile']:<22}{row['n']:>4}{row['trades']:>8}{win:>7}"
            f"{pnl:>11}{delta:>10}{clean_r:>8}{eff_r:>7}{fees:>10}{note}"
        )
    print("profiles: no_commission and no_slippage retain the other recorded assumptions; "
          "no_participation_cap permits up to 100% of each bar's volume.")
    if report["n_skipped"]:
        print(f"skipped {report['n_skipped']} non-qualifying session(s); use --format json for details.")


# ───────────────────────────── CLI ──────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.recorder",
        description="Record + finalize a TRADE_SIMULATOR session into viewer artifacts.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create a session folder")
    pi.add_argument("--ticker", required=True)
    pi.add_argument("--date", required=True, help="historical trade date YYYY-MM-DD")
    pi.add_argument("--seed", type=int)
    pi.add_argument("--profile", default="small",
                    help="account profile: small | main | swing")
    pi.add_argument("--strategy", default="warrior",
                    help="strategy family (warrior, cup_handle, …)")
    pi.add_argument("--delay", type=float)
    pi.add_argument("--risk-budget", type=float)
    pi.add_argument("--buying-power", type=float)
    pi.add_argument("--skill", help="path to the driving skill .md "
                    "(default: the current base version for the strategy family)")
    pi.add_argument("--mode", default="simulated", choices=["simulated", "live"],
                    help="simulated paper run (default) or a real-time live session")
    pi.add_argument("--pin-version", help="backtest: stamp this exact version "
                    "read-only (skip registration); pair with --skill = "
                    "skills/trade_skills/<version>.md")
    pi.add_argument("--batch", help="legacy backtest cohort tag")
    pi.add_argument("--session", help="top-level session id (live day or sim batch)")

    pl = sub.add_parser("log", help="append one decision record")
    pl.add_argument("--session", required=True)
    pl.add_argument("--record", required=True, help="JSON decision record")

    px = sub.add_parser("resolve", help="resolve active deterministic orders on a revealed tick")
    px.add_argument("--session", required=True)
    px.add_argument("--i", type=int, help="revealed tick index (default: latest)")

    pf = sub.add_parser("finalize", help="build all artifacts")
    pf.add_argument("--session", required=True)

    sub.add_parser("list", help="list sessions")

    pr = sub.add_parser("report", help="aggregate profitability by skill version")
    pr.add_argument("--by-version", action="store_true", default=True,
                    help="group by skill version (default)")
    pr.add_argument("--mode", choices=["simulated", "live"],
                    help="restrict to simulated or live sessions")
    pr.add_argument("--batch", help="restrict to one backtest cohort tag")
    pr.add_argument("--format", choices=["table", "json"], default="table",
                    help="table (default) or json for programmatic diffing")

    pa = sub.add_parser(
        "attribution",
        help="replay one deterministic batch under controlled execution assumptions",
    )
    pa.add_argument("--batch", required=True,
                    help="backtest cohort tag; uses only deterministic OHLC leaves")
    pa.add_argument("--format", choices=["table", "json"], default="table",
                    help="table (default) or json with per-profile replay errors")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "init":
        sdir = init(args.ticker, args.date, seed=args.seed, profile=args.profile,
                    delay=args.delay, risk_budget=args.risk_budget,
                    buying_power=args.buying_power, skill=args.skill, mode=args.mode,
                    pin_version=args.pin_version, batch=args.batch, session=args.session,
                    strategy=getattr(args, "strategy", None) or "warrior")
        print(str(sdir))
    elif args.cmd == "log":
        log(args.session, json.loads(args.record))
    elif args.cmd == "resolve":
        print(json.dumps(resolve(args.session, args.i), sort_keys=True))
    elif args.cmd == "finalize":
        session = finalize(args.session)
        r = session.get("result", {})
        print(f"finalized {session['id']}: traded={r.get('traded')} "
              f"realized=${r.get('realized_pnl')} ({r.get('r_multiple')}R)")
    elif args.cmd == "list":
        for s in list_sessions():
            # grouped view (top sessions / batches)
            name = s.get("name") or s["id"]
            ntk = s.get("n_tickers", "?")
            ntr = s.get("n_trades", "?")
            pnl = s.get("pnl")
            pnl_s = f"${pnl}" if pnl is not None else "—"
            print(f"{s['id']}  {name}  {s.get('type','?')}  {ntk}tickers {ntr}trades  pnl={pnl_s}")
    elif args.cmd == "report":
        rows = report_by_version(mode=args.mode, batch=args.batch)
        if args.format == "json":
            print(json.dumps(rows, indent=2))
        else:
            _print_report(rows)
    elif args.cmd == "attribution":
        report = execution_attribution(args.batch)
        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            _print_execution_attribution(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
