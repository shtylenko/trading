"""Session recorder — turns a TRADE_SIMULATOR run into web-viewable artifacts.

A simulation session is a folder
``simulations/{YYYYMMDDHHMMSS}-{TICKER}/`` (real wall-clock ts) holding the raw
replay stream, the agent's per-turn decisions, and — after ``finalize`` — a set of
JSON files the viewer renders. See ``SIMULATION_VIEWER_SPEC.md`` for the contract.

Lifecycle (used by the skill):

    # 1. start of run
    python3 -m trading.llm_trader.recorder init \
        --ticker EVTV --date 2026-01-13 --seed 7 --profile small
    #   -> prints the session dir; point `replay --out-file <dir>/stream.jsonl` at it

    # 2. each turn (append one decision record)
    python3 -m trading.llm_trader.recorder log --session <dir> \
        --record '{"i":3,"time":"10:23","thought":"…","action":"SCALE",
                   "fill_px":3.90,"shares_delta":-150,"stop":3.75}'

    # 3. end of run (build all artifacts)
    python3 -m trading.llm_trader.recorder finalize --session <dir>

The P&L / position engine is deterministic (average-cost) so the agent never has to
compute money — it just reports thoughts, actions, and fills.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import skillmeta
from .config import DATA_DIR
from .streamio import parse_stream as _parse_stream
from .streamio import read_jsonl as _read_jsonl

SCHEMA_VERSION = 1
SIM_ROOT = DATA_DIR.parent / "simulations"

# default account profile knobs (mirrors the skill's small-account sizing)
PROFILE_RISK = {"small": 40.0, "main": 1350.0}

# a running session idle longer than this (no file writes) is treated as stale
_STALE_AFTER_S = 15 * 60

# Action sets (also used by PositionEngine)
ACTION_FILLS = {"ENTER", "ADD", "SCALE", "EXIT"}
ALL_ACTIONS = {"OBSERVE", "ENTER", "ADD", "SCALE", "TRAIL", "EXIT", "STAND_DOWN"}


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
        # shares bought on the very first ENTER — the base size the MFE (best price
        # since entry) is measured against for the capture ratio.
        self.entry_shares: Optional[int] = None

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
    ) -> tuple[Optional[dict], dict]:
        """Process one decision. Returns (action_row or None, timeline_row)."""
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
        return forced

    def mfe_per_share(self, bars: list[dict]) -> Optional[float]:
        if self.entry_i is None or self.entry_avg is None:
            return None
        highs = [b["h"] for b in bars if b.get("i", -1) >= self.entry_i]
        if not highs:
            return None
        return round(max(highs) - self.entry_avg, 4)

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


def _epoch_et(date_str: str, hhmm: str) -> int:
    """ET wall-clock as a unix timestamp, stored as if UTC so chart axis labels
    read the ET clock (10:20, 10:21 …). One session, so no DST ambiguity."""
    d = datetime.strptime(f"{date_str} {hhmm}", "%Y-%m-%d %H:%M")
    return int(d.replace(tzinfo=timezone.utc).timestamp())


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
    root: Path = SIM_ROOT,
    now: Optional[datetime] = None,
) -> Path:
    """Create the session folder and a provisional ``session.json``; return its path.

    The driving skill's version is read and *frozen* here (at run start) so later
    edits to the skill never retroactively re-tag this run. Normally the version is
    resolved (and auto-bumped on drift) via ``skillmeta.resolve_version``.

    **Backtest mode (``pin_version``).** When replaying a *specific* archived version
    for a batch, pass ``pin_version="2.0.2"`` with ``skill`` pointing at the archived
    file (``skills/archive/TRADE_SIMULATOR@2.0.2.md``). The session is stamped exactly
    with that version + the archived file's hash, and ``resolve_version`` is **skipped
    entirely** — a backtest must never bump the version or mutate the registry/archive.
    ``batch`` tags the session so re-runs of one version stay distinguishable
    (``report --batch <tag>``).
    """
    now = now or datetime.now()
    sid = f"{now.strftime('%Y%m%d%H%M%S')}-{ticker.upper()}"
    sdir = Path(root) / sid
    sdir.mkdir(parents=True, exist_ok=True)

    skill_path = skill or skillmeta.DEFAULT_SKILL_PATH
    note = None
    if pin_version is not None:
        # backtest: stamp the pinned version read-only — no resolve/bump/archive.
        try:
            m = skillmeta.read_skill_meta(skill_path)
            content_hash = m["content_hash"]
        except FileNotFoundError:
            content_hash = None
        skill_meta = {"name": "trade-simulator", "version": pin_version,
                      "content_hash": content_hash, "path": str(skill_path)}
    else:
        try:
            skill_meta, note = skillmeta.resolve_version(skill_path)
        except FileNotFoundError:
            skill_meta = {"name": None, "version": None, "content_hash": None,
                          "path": str(skill_path)}
            note = f"skill file not found at {skill_path} — run recorded as unversioned."
    if note:
        print(f"• {note}", file=sys.stderr)

    session = {
        "schema_version": SCHEMA_VERSION,
        "id": sid,
        "mode": mode,   # "simulated" (paper) or "live" (real-time market session)
        "status": "running",
        "ticker": ticker.upper(),
        "historical_date": date,
        "real_run_ts": now.isoformat(timespec="seconds"),
        "skill": skill_meta,
        "batch": batch,   # backtest cohort tag (None for ad-hoc/live runs)
        "config": {
            "seed": seed,
            "profile": profile,
            "delay": delay,
            "risk_budget": risk_budget if risk_budget is not None
            else PROFILE_RISK.get(profile, PROFILE_RISK["small"]),
            "buying_power": buying_power,
        },
        "files": {},
    }
    (sdir / "session.json").write_text(json.dumps(session, indent=2))
    # touch the append targets so the run never trips over a missing file
    (sdir / "decisions.jsonl").touch()
    return sdir


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
    action = record.get("action")
    if action not in ALL_ACTIONS:
        raise ValueError(f"action must be one of {sorted(ALL_ACTIONS)}, got {action!r}")
    if "i" not in record or "time" not in record:
        raise ValueError("decision record needs at least 'i' and 'time'")

    session = _load_json(sdir / "session.json", {}) or {}
    if session.get("status") == "complete":
        raise ValueError(
            f"session {sdir.name} is finalized — cannot log new decisions "
            "(re-init a fresh session instead)"
        )

    i = record.get("i")
    prior = _read_jsonl(sdir / "decisions.jsonl")
    last_i = max((d.get("i", -1) for d in prior), default=-1)
    if isinstance(i, int) and i <= last_i:
        raise ValueError(
            f"decision i={i} is not ahead of the last logged i={last_i} "
            "(bars must be logged in strictly increasing order; retried turns "
            "must not re-log a bar)"
        )

    with open(sdir / "decisions.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


# ───────────────────────────── finalize ─────────────────────────────────────


def _build_bars(meta: dict, ticks: list[dict]) -> list[dict]:
    """Bars from the streamed ticks (traded window only) — the fallback source."""
    date = meta["date"]
    bars = []
    for tk in ticks:
        bars.append({
            "t": _epoch_et(date, tk["time"]),
            "time": tk["time"],
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
    except Exception:
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


def _run_engine(meta, bars, decisions, risk_budget, end, force_close=True):
    """Average-cost position/P&L walk using PositionEngine. Returns (actions, timeline, pnl)."""
    date_str = meta["date"]
    close_by_i = {b["i"]: b["c"] for b in bars}

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

        action_row, timeline_row = engine.step(i, hhmm, action, fill, dq, stop, close)

        # fill epoch times (kept out of engine for pure time math)
        if action_row is not None:
            action_row["t"] = _epoch_et(date_str, hhmm) if hhmm else None
            action_row["reason"] = d.get("note") or d.get("thought", "")[:140]
            actions.append(action_row)

        if timeline_row is not None:
            timeline_row["t"] = _epoch_et(date_str, hhmm) if hhmm else None
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
        if forced["time"]:
            forced["t"] = _epoch_et(date_str, forced["time"])
        actions.append(forced)

    mfe_ps = engine.mfe_per_share(bars)
    entry_avg = engine.blended_entry
    entry_shares = engine.entry_shares
    # capture ratio: realized $ ÷ the best-case dollars had you sold the whole entry
    # size at the high (mfe_per_share × entry_shares). ≈ "how much of the favorable
    # move you kept". >0 and ≤~1 for a normal win; negative if the trade lost.
    mfe_dollars = (mfe_ps * entry_shares) if (mfe_ps and entry_shares) else None
    mfe_capture = (
        round(engine.realized / mfe_dollars, 3)
        if (mfe_dollars and mfe_dollars > 0) else None
    )

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
        "mfe_per_share": mfe_ps,
        "mfe_pct": round(mfe_ps / entry_avg * 100, 2) if (mfe_ps and entry_avg) else None,
        "mfe_capture": mfe_capture,
        "forced_exit": forced is not None,
        "assumptions": "fills at reported price; no slippage/fees/Level-2; avg-cost basis.",
    }
    return actions, timeline, pnl


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
                 + ("  ·  _auto-flat at close_" if pnl["forced_exit"] else ""))
    else:
        L.append("- **stood down — no trade taken**")
    L.append("")
    L.append("## Blotter")
    for a in actions:
        L.append(f"- {a['time']}  {a['side'].upper():4}  {a['shares']:>5} @ ${a['price']}"
                 f"   (Δreal ${a['realized_delta']})  — {a['reason']}")
    L.append("")
    L.append("## Decision timeline")
    for t in timeline:
        pos = f"[{t['position_shares']}sh @ {t['avg_entry']}]" if t["position_shares"] else "[flat]"
        L.append(f"- **{t['time']}** `{t['action']}` {pos} uPnL ${t['unrealized']} — {t['thought']}")
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
    session_path = sdir / "session.json"
    if not session_path.exists():
        raise FileNotFoundError(f"no session.json in {sdir} — run `init` first")
    session = json.loads(session_path.read_text())

    meta, ticks, end = _parse_stream(sdir / "stream.jsonl")
    if meta is None:
        raise ValueError(f"{sdir}/stream.jsonl has no meta line — was replay --out-file pointed here?")
    decisions = _read_jsonl(sdir / "decisions.jsonl")
    risk_budget = session.get("config", {}).get("risk_budget") or PROFILE_RISK["small"]

    # chart bars = the whole RTH day for context when the run is legitimately done
    # (`full_day=True`, the skill/CLI path). When force-finalizing a *live* session
    # (the viewer button, `full_day=False`) we clamp to the revealed ticks so the
    # saved artifact never shows price action past where trading stopped.
    stream_bars = _build_bars(meta, ticks)
    bars = (_full_day_bars(meta) or stream_bars) if full_day else stream_bars
    actions, timeline, pnl = _run_engine(meta, stream_bars, decisions, risk_budget, end)

    # mirror the frozen skill stamp into pnl.json so `report --by-version` can
    # group by reading one file per session (not session.json + pnl.json).
    skill = session.get("skill", {}) or {}
    pnl["skill_version"] = skill.get("version")
    pnl["skill_hash"] = skill.get("content_hash")
    pnl["batch"] = session.get("batch")

    # enrich session manifest with setup meta + outcome + file index
    session["status"] = "complete"
    session["finalized_ts"] = datetime.now().isoformat(timespec="seconds")
    session["setup"] = {
        k: meta.get(k) for k in (
            "entry_time", "entry_px", "anchor_px", "gap_pct", "rvol", "float_shares",
            "prior_close", "prior_high", "prior_low", "pm_high", "pm_low",
            "session_end", "reason",
        )
    }
    session["result"] = {
        "traded": pnl["traded"], "realized_pnl": pnl["realized_pnl"],
        "r_multiple": pnl["r_multiple"], "win": pnl["win"],
        "mfe_per_share": pnl["mfe_per_share"], "n_bars": len(bars),
        "n_decisions": len(timeline), "n_fills": len(actions),
        "skill_version": skill.get("version"),
    }
    session["files"] = {
        "bars": "bars.json", "actions": "actions.json", "decisions": "decisions.json",
        "pnl": "pnl.json", "journal": "journal.md", "stream": "stream.jsonl",
    }

    (sdir / "bars.json").write_text(json.dumps(bars, indent=2))
    (sdir / "actions.json").write_text(json.dumps(actions, indent=2))
    (sdir / "decisions.json").write_text(json.dumps(timeline, indent=2))
    (sdir / "pnl.json").write_text(json.dumps(pnl, indent=2))
    (sdir / "session.json").write_text(json.dumps(session, indent=2))
    (sdir / "journal.md").write_text(_journal(session, meta, pnl, actions, timeline))
    return session


# ───────────────────────────── Live / UI view helpers ────────────────────────

def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


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
    meta, ticks, end = _parse_stream(sdir / "stream.jsonl")
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
    risk_budget = session.get("config", {}).get("risk_budget") or PROFILE_RISK.get(
        session.get("config", {}).get("profile", "small"), PROFILE_RISK["small"]
    )

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
    actions, timeline, pnl = _run_engine(
        meta, stream_bars, decisions_raw, risk_budget, None, force_close=False
    )

    last_i = max([b.get("i", -1) for b in stream_bars]) if stream_bars else None

    # Merge some live info into the returned session dict for convenience
    live_session = dict(session)
    live_session.setdefault("status", "running")

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
_live_pnl_cache: dict[str, tuple[float, Optional[dict]]] = {}


def _live_pnl_snapshot(sdir: Path) -> Optional[dict]:
    sid = sdir.name
    mtime = 0.0
    for name in ("stream.jsonl", "decisions.jsonl"):
        f = sdir / name
        if f.exists():
            mtime = max(mtime, f.stat().st_mtime)
    cached = _live_pnl_cache.get(sid)
    if cached and cached[0] == mtime:
        return cached[1]
    snapshot = None
    try:
        live = get_session_view(sdir)
        lp = live.get("pnl", {})
        if lp:
            decs = live.get("decisions") or []
            snapshot = {
                "realized_pnl": lp.get("realized_pnl"),
                "unrealized": decs[-1].get("unrealized") if decs else None,
            }
    except Exception:
        snapshot = None
    _live_pnl_cache[sid] = (mtime, snapshot)
    return snapshot


def list_sessions() -> list[dict]:
    """Return lightweight info for every session folder (newest first)."""
    if not SIM_ROOT.exists():
        return []
    out = []
    for d in sorted(SIM_ROOT.iterdir(), reverse=True):   # newest first by folder ts
        sess_file = d / "session.json"
        if not sess_file.exists():
            continue
        try:
            s = json.loads(sess_file.read_text())
        except Exception:
            continue

        # Last activity = newest write to any live file, as real wall-clock time
        # (NOT the last decision's historical bar clock like "10:23", which would
        # sort/display nonsensically next to real timestamps).
        newest_mtime = 0.0
        for name in ("decisions.jsonl", "stream.jsonl", "session.json"):
            f = d / name
            if f.exists():
                newest_mtime = max(newest_mtime, f.stat().st_mtime)
        last_ts = (
            datetime.fromtimestamp(newest_mtime).isoformat(timespec="seconds")
            if newest_mtime
            else s.get("finalized_ts") or s.get("real_run_ts")
        )

        status = s.get("status", "running")
        # A "running" session whose files haven't changed in a while was almost
        # certainly abandoned (crash / closed terminal) — flag it so the UI can
        # distinguish it from a live one instead of showing it green forever.
        stale = (
            status != "complete"
            and newest_mtime > 0
            and (time.time() - newest_mtime) > _STALE_AFTER_S
        )

        entry = {
            "id": s.get("id") or d.name,
            "ticker": s.get("ticker"),
            "historical_date": s.get("historical_date"),
            "real_run_ts": s.get("real_run_ts"),
            "mode": s.get("mode", "simulated"),
            "status": status,
            "stale": stale,
            "result": s.get("result"),
            "last_activity": last_ts,
        }

        # For running sessions, include a current PnL snapshot (mtime-cached).
        if entry["status"] != "complete":
            snap = _live_pnl_snapshot(d)
            if snap:
                entry["live_pnl"] = snap

        out.append(entry)
    return out


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
    if not SIM_ROOT.exists():
        return []
    buckets: dict[str, dict] = {}
    for d in sorted(SIM_ROOT.iterdir()):
        pnl = _load_json(d / "pnl.json")
        session = _load_json(d / "session.json", {}) or {}
        if pnl is None or session.get("status") != "complete":
            continue  # skip running/abandoned/unfinalized sessions
        if mode is not None and session.get("mode", "simulated") != mode:
            continue
        sbatch = session.get("batch") or pnl.get("batch")
        if batch is not None and sbatch != batch:
            continue

        ver = pnl.get("skill_version") or session.get("skill", {}).get("version") \
            or "unversioned"
        b = buckets.setdefault(ver, {
            "version": ver, "n": 0, "wins": 0, "stood_down": 0, "n_void": 0,
            "pnl": 0.0, "r_sum": 0.0, "cap_sum": 0.0, "cap_n": 0, "hashes": set(),
        })
        h = pnl.get("skill_hash") or session.get("skill", {}).get("content_hash")
        if h:
            b["hashes"].add(h)
        if session.get("void") or pnl.get("void"):
            b["n_void"] += 1          # audit-tainted → excluded from stats
            continue
        if not pnl.get("traded"):
            b["stood_down"] += 1
            continue
        b["n"] += 1
        b["wins"] += 1 if pnl.get("win") else 0
        b["pnl"] += pnl.get("realized_pnl") or 0.0
        b["r_sum"] += pnl.get("r_multiple") or 0.0
        cap = pnl.get("mfe_capture")
        if cap is not None:
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
            "win_pct": round(100 * b["wins"] / n) if n else None,
            "pnl": round(b["pnl"], 2),
            "avg_r": round(b["r_sum"] / n, 2) if n else None,
            "avg_capture": round(b["cap_sum"] / b["cap_n"], 2) if b["cap_n"] else None,
            "hashes": sorted(b["hashes"]),
        })
    rows.sort(key=lambda r: r["version"])
    return rows


def _print_report(rows: list[dict]) -> None:
    if not rows:
        print("no finalized sessions to report")
        return
    print(f"{'version':<14}{'n':>4}{'win%':>6}{'P&L':>10}{'avgR':>7}{'capt':>6}  notes")
    for r in rows:
        win = f"{r['win_pct']}%" if r["win_pct"] is not None else "—"
        avg = f"{r['avg_r']:.2f}" if r["avg_r"] is not None else "—"
        cap = f"{r['avg_capture']:.2f}" if r.get("avg_capture") is not None else "—"
        pnl = f"${r['pnl']:.2f}"
        notes = []
        if r["stood_down"]:
            notes.append(f"{r['stood_down']} stood down")
        if r.get("n_void"):
            notes.append(f"⚠ {r['n_void']} void")
        if len(r["hashes"]) > 1:
            notes.append(f"⚠ {len(r['hashes'])} distinct hashes (drift)")
        print(f"{r['version']:<14}{r['n']:>4}{win:>6}{pnl:>10}{avg:>7}{cap:>6}  "
              f"{', '.join(notes)}")


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
    pi.add_argument("--profile", default="small")
    pi.add_argument("--delay", type=float)
    pi.add_argument("--risk-budget", type=float)
    pi.add_argument("--buying-power", type=float)
    pi.add_argument("--skill", help="path to the driving skill .md "
                    "(default: bundled TRADE_SIMULATOR.md)")
    pi.add_argument("--mode", default="simulated", choices=["simulated", "live"],
                    help="simulated paper run (default) or a real-time live session")
    pi.add_argument("--pin-version", help="backtest: stamp this exact version "
                    "read-only (skip resolve/bump); pair with --skill = the archived "
                    "TRADE_SIMULATOR@<version>.md")
    pi.add_argument("--batch", help="backtest cohort tag for this run")

    pl = sub.add_parser("log", help="append one decision record")
    pl.add_argument("--session", required=True)
    pl.add_argument("--record", required=True, help="JSON decision record")

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
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "init":
        sdir = init(args.ticker, args.date, seed=args.seed, profile=args.profile,
                    delay=args.delay, risk_budget=args.risk_budget,
                    buying_power=args.buying_power, skill=args.skill, mode=args.mode,
                    pin_version=args.pin_version, batch=args.batch)
        print(str(sdir))
    elif args.cmd == "log":
        log(args.session, json.loads(args.record))
    elif args.cmd == "finalize":
        session = finalize(args.session)
        r = session.get("result", {})
        print(f"finalized {session['id']}: traded={r.get('traded')} "
              f"realized=${r.get('realized_pnl')} ({r.get('r_multiple')}R)")
    elif args.cmd == "list":
        for s in list_sessions():
            status = s["status"]
            mode = s.get("mode", "simulated")
            print(f"{s['id']}  {s['ticker']}  {s['historical_date']}  {mode} {status}")
    elif args.cmd == "report":
        rows = report_by_version(mode=args.mode, batch=args.batch)
        if args.format == "json":
            print(json.dumps(rows, indent=2))
        else:
            _print_report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
