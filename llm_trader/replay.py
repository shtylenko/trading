"""Replay one recorded setup minute-by-minute (paper/TradingView practice aid).

Picks a setup from the scanner's ``entries.db`` (default: a random one whose
entry is **after 09:30 ET**, i.e. a regular-session breakout rather than a
premarket one), prefetches that day's **1-minute** bars for the ticker via
``trading.marketdata``, and prints the bars in chronological order from the
entry time to the close — as if you were watching the tape tick forward.

This is a *viewing* tool: it streams price/volume (+ running VWAP, cumulative
volume, and move vs the entry price). It does **not** simulate exits or P&L —
that judgement is yours on the replay (consistent with the scanner's scope).

Two output modes:
  * ``human`` (default) — an aligned table for a person to read.
  * ``jsonl``           — one JSON object per line (a ``meta`` line, then a
                          ``tick`` line per minute, then an ``end`` line). This is
                          what the TRADE_SIMULATOR skill consumes: each tick
                          carries the indicators Cameron uses (VWAP, EMA9, running
                          session high, new-high flag, move vs the entry price).

With ``--delay 60`` the stream emits one tick per minute of wall-clock time, so a
backgrounded run paces like a live tape. Pair it with ``--out-file`` to append
each tick to a file an agent can poll.

Usage (from the monorepo root, repo-root .env loaded for provider keys):

    python3 -m trading.llm_trader.replay                 # random RTH setup
    python3 -m trading.llm_trader.replay --ticker VIVO   # random VIVO setup
    python3 -m trading.llm_trader.replay --ticker AEHL --date 2025-04-22
    python3 -m trading.llm_trader.replay --seed 7        # reproducible pick
    python3 -m trading.llm_trader.replay --delay 0.3     # stream ~live
    python3 -m trading.llm_trader.replay --from-open     # start at 09:30, not entry
    python3 -m trading.llm_trader.replay --format jsonl --out-file ticks.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Optional, TextIO

import pandas as pd

from trading.marketdata import fetch_bars

from .config import DATA_DIR, ScanConfig
from .indicators import (
    DAILY_REPLAY_REQUIRED_INDICATORS,
    enrich_1min_for_replay,
    session_vwap,
)

RTH_OPEN = dtime(9, 30)
RTH_CLOSE = dtime(16, 0)
logger = logging.getLogger("llm_trader.replay")

# A 200-session SMA plus the 40-bar visible planning window needs substantially
# more than 280 calendar days once weekends, exchange holidays, and sparse data
# are accounted for.  This minimum also leaves a small buffer for ATR/RVOL.
_DAILY_SMA_WARMUP_BARS = 200
_DAILY_WARMUP_BUFFER_BARS = 10
_MIN_DAILY_WARMUP_CALENDAR_DAYS = 420


@dataclass
class Setup:
    ticker: str
    day: date
    time_et: str           # "HH:MM"
    entry_px: Optional[float]
    gap_pct: Optional[float]
    rvol: Optional[float]
    float_shares: Optional[float]
    reason: str
    strategy: str = "warrior"
    pattern: str = "acd_orb"
    features: Optional[dict] = None

    @property
    def entry_time(self) -> dtime:
        try:
            h, m = (int(x) for x in self.time_et.split(":"))
            return dtime(h, m)
        except (ValueError, AttributeError):
            return RTH_OPEN


# ───────────────────────────── setup selection ──────────────────────────────


def _hhmm_after(time_et: str, cutoff: dtime) -> bool:
    try:
        h, m = (int(x) for x in time_et.split(":"))
    except (ValueError, AttributeError):
        return False
    return dtime(h, m) >= cutoff


def pick_setup(
    db_path: str | Path,
    ticker: Optional[str] = None,
    day: Optional[date] = None,
    after: dtime = RTH_OPEN,
    seed: Optional[int] = None,
    at_time: Optional[str] = None,
    strategy: Optional[str] = None,
    skip_time_filter: bool = False,
) -> Setup:
    """Choose a setup row, defaulting to a random RTH (after-09:30) entry.

    Filters: optional ``ticker`` / ``day`` / ``strategy`` exact match, and
    ``time_et >= after`` (so premarket breakouts are excluded by default for
    warrior). ``at_time`` ("HH:MM") pins an *exact* setup. Multi-day strategies
    should pass ``skip_time_filter=True`` (daily entries use a nominal time).
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM entries WHERE 1=1"
        params: list = []
        if ticker:
            sql += " AND ticker = ?"
            params.append(ticker.upper())
        if day:
            sql += " AND date = ?"
            params.append(day.isoformat())
        if at_time:
            sql += " AND time_et = ?"
            params.append(at_time)
        # strategy column may be missing on very old DBs — try/except
        cols = {r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
        if strategy and "strategy" in cols:
            sql += " AND strategy = ?"
            params.append(strategy)
        rows = conn.execute(sql, params).fetchall()

    if not skip_time_filter:
        rows = [r for r in rows if _hhmm_after(r["time_et"], after)]
    if not rows:
        raise SystemExit(
            "No matching setup found (after "
            f"{after.strftime('%H:%M')} ET"
            + (f", ticker={ticker}" if ticker else "")
            + (f", date={day}" if day else "")
            + (f", strategy={strategy}" if strategy else "")
            + ")."
        )

    rng = random.Random(seed)
    r = rng.choice(rows)
    keys = r.keys()
    features = None
    if "features_json" in keys and r["features_json"]:
        try:
            features = json.loads(r["features_json"])
        except (TypeError, json.JSONDecodeError):
            features = None
    return Setup(
        ticker=r["ticker"],
        day=datetime.strptime(r["date"], "%Y-%m-%d").date(),
        time_et=r["time_et"],
        entry_px=r["entry_px"],
        gap_pct=r["gap_pct"],
        rvol=r["rvol"],
        float_shares=r["float_shares"],
        reason=r["reason"],
        strategy=r["strategy"] if "strategy" in keys and r["strategy"] else "warrior",
        pattern=r["pattern"] if "pattern" in keys else "acd_orb",
        features=features,
    )


# ───────────────────────────── bar prefetch ─────────────────────────────────


def fetch_minute_bars(ticker: str, day: date, force: bool = False, session: str = "rth") -> pd.DataFrame:
    """Prefetch the day's 1-minute bars for ``ticker`` (ET-indexed OHLCV).

    Returns an empty frame if the provider can't serve the day (e.g. on-demand
    intraday access blocked for dates >1yr old — see SPEC §2).
    """
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    df = fetch_bars(
        ticker, "1min", start=start, end=end,
        session=session, adjustment="raw", force=force,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_index()
    if df.index.tz is None:
        df = df.tz_localize("America/New_York")
    else:
        df = df.tz_convert("America/New_York")
    return df[df.index.date == day]


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add the indicators Cameron reads (over the full RTH session).

    Delegates to shared :func:`indicators.enrich_1min_for_replay`.
    """
    return enrich_1min_for_replay(df, rvol_bar_window=20, rvol_min_periods=5)


def _context(ticker: str, day: date, force: bool = False, ext_df: Optional[pd.DataFrame] = None) -> dict:
    """One-time reference levels for the meta line (best-effort, never fatal).

    ``prior_close/high/low`` from the previous daily bar and ``pm_high/low`` from
    the day's pre-market (extended-session) 1-minute bars — the round-number /
    overnight levels a trader marks before the open. Any field is ``None`` if the
    provider can't serve it; a context miss must not abort the replay.
    """
    ctx = {"prior_close": None, "prior_high": None, "prior_low": None,
           "pm_high": None, "pm_low": None, "context_warnings": []}
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    try:
        dd = fetch_bars(ticker, "1day", start=start - timedelta(days=12), end=end,
                        session="rth", adjustment="raw", force=force)
        if dd is not None and not dd.empty:
            prior = dd[dd.index.date < day]
            if not prior.empty:
                last = prior.iloc[-1]
                ctx["prior_close"] = round(float(last["close"]), 4)
                ctx["prior_high"] = round(float(last["high"]), 4)
                ctx["prior_low"] = round(float(last["low"]), 4)
    except Exception as exc:
        logger.debug("daily context fetch failed for %s %s", ticker, day, exc_info=True)
        ctx["context_warnings"].append(f"daily_context_unavailable:{type(exc).__name__}")
    try:
        if ext_df is None:
            ext_df = fetch_bars(ticker, "1min", start=start, end=end,
                             session="extended", adjustment="raw", force=force)
            if ext_df is not None and not ext_df.empty:
                ext_df = ext_df.sort_index()
                ext_df = ext_df.tz_localize("America/New_York") if ext_df.index.tz is None \
                    else ext_df.tz_convert("America/New_York")
        if ext_df is not None and not ext_df.empty:
            pm = ext_df[(ext_df.index.date == day) & (ext_df.index.time < RTH_OPEN)]
            if not pm.empty:
                ctx["pm_high"] = round(float(pm["high"].max()), 4)
                ctx["pm_low"] = round(float(pm["low"].min()), 4)
    except Exception as exc:
        logger.debug("premarket context fetch failed for %s %s", ticker, day, exc_info=True)
        ctx["context_warnings"].append(f"premarket_context_unavailable:{type(exc).__name__}")
    return ctx


# ───────────────────────────── streaming ────────────────────────────────────


def _fmt_float(f: Optional[float]) -> str:
    return f"{f / 1e6:.1f}M" if f else "n/a"


def _emit(line: str, streams: list[TextIO]) -> None:
    """Write one line to every stream and flush (pacing is the caller's job)."""
    for s in streams:
        s.write(line + "\n")
        s.flush()


def replay(
    setup: Setup,
    *,
    from_open: bool = False,
    neutral_meta: bool = False,
    five_minute_context: bool = False,
    delay: float = 0.0,
    force: bool = False,
    fmt: str = "human",
    out: TextIO = sys.stdout,
    out_file: Optional[str | Path] = None,
    bar_resolution: Optional[str] = None,
    max_hold_bars: Optional[int] = None,
    plan_lookback_bars: int = 40,
) -> int:
    """Stream bars for a setup (1-minute same-day, or daily multi-day).

    ``bar_resolution`` defaults from ``setup.strategy`` (``1day`` for cup_handle,
    else ``1min``). Daily mode streams enriched daily OHLCV for plan lookback +
    hold window — see :func:`replay_daily`.
    """
    resolution = bar_resolution
    if resolution is None:
        resolution = "1day" if setup.strategy and setup.strategy != "warrior" else "1min"
        # cup_handle and any multi_day family use daily
        if setup.strategy == "cup_handle":
            resolution = "1day"

    if resolution in ("1day", "daily"):
        return replay_daily(
            setup,
            neutral_meta=neutral_meta,
            delay=delay,
            force=force,
            fmt=fmt,
            out=out,
            out_file=out_file,
            max_hold_bars=max_hold_bars,
            plan_lookback_bars=plan_lookback_bars,
        )

    if fmt == "jsonl":
        ext_df = fetch_minute_bars(setup.ticker, setup.day, force=force, session="extended")
        df = ext_df[(ext_df.index.time >= RTH_OPEN) & (ext_df.index.time < RTH_CLOSE)]
    else:
        ext_df = None
        df = fetch_minute_bars(setup.ticker, setup.day, force=force)
    streams: list[TextIO] = [out]
    fh: Optional[TextIO] = None
    if out_file is not None:
        out_file = Path(out_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(out_file, "w", encoding="utf-8")
        streams.append(fh)

    try:
        if df.empty:
            msg = (
                f"No 1-minute bars available for {setup.ticker} on {setup.day} "
                "(provider may not serve this date — see SPEC §2)."
            )
            if fmt == "jsonl":
                _emit(json.dumps({"type": "error", "message": msg}), streams)
            else:
                for s in streams:
                    print(msg, file=s)
            return 3

        df = _enrich(df)
        start_t = RTH_OPEN if from_open else setup.entry_time
        anchor = setup.entry_px if setup.entry_px else float(df["open"].iloc[0])

        if fmt == "jsonl":
            return _stream_jsonl(
                setup, df, start_t, anchor, streams, delay, force=force, ext_df=ext_df,
                neutral_meta=neutral_meta, five_minute_context=five_minute_context,
            )
        return _stream_human(setup, df, start_t, anchor, streams, delay)
    finally:
        if fh is not None:
            fh.close()


def fetch_daily_bars(
    ticker: str,
    start_day: date,
    end_day: date,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """Fetch daily OHLCV for ``ticker`` covering ``[start_day, end_day]`` (ET)."""
    start = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=5)
    end = datetime.combine(end_day, datetime.max.time(), tzinfo=timezone.utc) + timedelta(days=5)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw", force=force)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_index()
    if df.index.tz is None:
        # daily often tz-naive; treat as ET calendar dates
        pass
    else:
        df = df.tz_convert("America/New_York")
    return df


def _daily_replay_warmup_days(plan_lookback_bars: int) -> int:
    """Calendar lookback that warms every indicator before the first visible bar."""
    if plan_lookback_bars < 0:
        raise ValueError("plan_lookback_bars must be non-negative")
    required_sessions = (
        _DAILY_SMA_WARMUP_BARS + plan_lookback_bars + _DAILY_WARMUP_BUFFER_BARS
    )
    # Five weekday sessions take seven calendar days; add a further cushion for
    # market holidays and providers whose date boundaries are slightly coarse.
    return max(
        _MIN_DAILY_WARMUP_CALENDAR_DAYS,
        math.ceil(required_sessions * 7 / 5) + 21,
    )


def _daily_indicator_gaps(window: pd.DataFrame, dates: list[date]) -> list[str]:
    """Describe missing/non-finite required daily fields in a replay window."""
    gaps: list[str] = []
    for field in DAILY_REPLAY_REQUIRED_INDICATORS:
        if field not in window:
            gaps.append(f"{field} (missing column)")
            continue
        values = window[field]
        missing = values.isna()
        if not pd.api.types.is_bool_dtype(values):
            numeric = pd.to_numeric(values, errors="coerce")
            missing = missing | ~numeric.map(math.isfinite)
        positions = [i for i, bad in enumerate(missing.tolist()) if bad]
        if positions:
            first = dates[positions[0]].isoformat()
            last = dates[positions[-1]].isoformat()
            span = first if first == last else f"{first}..{last}"
            gaps.append(f"{field} ({len(positions)} bar(s), {span})")
    return gaps


def replay_daily(
    setup: Setup,
    *,
    neutral_meta: bool = False,
    delay: float = 0.0,
    force: bool = False,
    fmt: str = "jsonl",
    out: TextIO = sys.stdout,
    out_file: Optional[str | Path] = None,
    max_hold_bars: Optional[int] = None,
    plan_lookback_bars: int = 40,
) -> int:
    """Stream daily bars for a multi-day swing setup (plan lookback + hold).

    Bars before ``setup.day`` give the agent chart structure to build a plan;
    bars from ``setup.day`` onward resolve the buy-stop / targets / stop.
    ``max_hold_bars`` defaults to 40 trading days after the setup day.
    """
    from .indicators import enrich_daily_for_replay

    hold = max_hold_bars if max_hold_bars is not None else 40
    # Warmup must cover the SMA200 *before the first visible planning bar*, not
    # merely before the setup date.  The old 280-calendar-day fetch left early
    # bars with null SMA200 and let simulations trade them.
    warmup_cal = _daily_replay_warmup_days(plan_lookback_bars)
    start_fetch = setup.day - timedelta(days=warmup_cal)
    end_fetch = setup.day + timedelta(days=int(hold * 2.2) + 10)
    raw = fetch_daily_bars(setup.ticker, start_fetch, end_fetch, force=force)

    streams: list[TextIO] = [out]
    fh: Optional[TextIO] = None
    if out_file is not None:
        out_file = Path(out_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(out_file, "w", encoding="utf-8")
        streams.append(fh)

    try:
        if raw.empty:
            msg = f"No daily bars for {setup.ticker} around {setup.day}"
            if fmt == "jsonl":
                _emit(json.dumps({"type": "error", "message": msg}), streams)
            else:
                for s in streams:
                    print(msg, file=s)
            return 3

        df = enrich_daily_for_replay(raw)
        # index to dates
        def _d(ts) -> date:
            return ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()

        dates = [_d(ts) for ts in df.index]
        # find setup day index (or first session on/after)
        setup_i = None
        for i, d in enumerate(dates):
            if d >= setup.day:
                setup_i = i
                break
        if setup_i is None:
            msg = f"Setup day {setup.day} not in daily frame for {setup.ticker}"
            if fmt == "jsonl":
                _emit(json.dumps({"type": "error", "message": msg}), streams)
            else:
                for s in streams:
                    print(msg, file=s)
            return 3

        stream_start = max(0, setup_i - plan_lookback_bars)
        stream_end = min(len(df) - 1, setup_i + hold)
        window = df.iloc[stream_start : stream_end + 1]
        win_dates = dates[stream_start : stream_end + 1]

        gaps = _daily_indicator_gaps(window, win_dates)
        if gaps:
            msg = (
                f"Daily replay data-integrity failure for {setup.ticker}: required "
                f"indicator(s) unavailable in the planned stream: {'; '.join(gaps)}. "
                "Refusing to emit a tradable stream."
            )
            if fmt == "jsonl":
                _emit(json.dumps({"type": "error", "message": msg}), streams)
            else:
                for s in streams:
                    print(msg, file=s)
            return 3

        feats = setup.features or {}
        anchor = setup.entry_px
        meta = {
            "type": "meta",
            "ticker": setup.ticker,
            "date": setup.day.isoformat(),
            "strategy": setup.strategy,
            "pattern": setup.pattern,
            "horizon": "multi_day",
            "bar_resolution": "1day",
            "plan_lookback_bars": plan_lookback_bars,
            "max_hold_bars": hold,
            "entry_time": setup.time_et,
            "session_end": win_dates[-1].isoformat() if win_dates else setup.day.isoformat(),
        }
        if not neutral_meta:
            meta.update({
                "entry_px": setup.entry_px,
                "anchor_px": setup.entry_px,
                "gap_pct": setup.gap_pct,
                "rvol": setup.rvol,
                "float_shares": setup.float_shares,
                "reason": setup.reason,
                "stop_px": feats.get("stop_px"),
                "target1_px": feats.get("target1_px"),
                "target2_px": feats.get("target2_px"),
                "atr": feats.get("atr"),
                "handle_high": feats.get("handle_high"),
                "cup_depth_px": feats.get("cup_depth_px"),
            })
        else:
            # Watchlist-only context (no planned levels leak)
            meta.update({
                "reason": "scanner-selected multi-day setup (levels not disclosed)",
            })

        if fmt != "jsonl":
            for s in streams:
                print(f"{setup.ticker} multi-day daily replay {win_dates[0]} → {win_dates[-1]}", file=s)
                print(setup.reason, file=s)

        _emit(json.dumps(meta), streams) if fmt == "jsonl" else None

        n = 0
        for (ts, row), d in zip(window.iterrows(), win_dates):
            close = float(row["close"])
            tick = {
                "type": "tick",
                "i": n,
                "date": d.isoformat(),
                "time": "16:00",  # daily bar close marker for chart axis
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(close, 4),
                "v": int(row["volume"]),
                "sma20": round(float(row["sma20"]), 4) if pd.notna(row.get("sma20")) else None,
                "sma50": round(float(row["sma50"]), 4) if pd.notna(row.get("sma50")) else None,
                "sma200": round(float(row["sma200"]), 4) if pd.notna(row.get("sma200")) else None,
                "atr14": round(float(row["atr14"]), 4) if pd.notna(row.get("atr14")) else None,
                "rvol": round(float(row["rvol"]), 2) if pd.notna(row.get("rvol")) else None,
                "above_sma20": bool(row["above_sma20"]) if pd.notna(row.get("above_sma20")) else None,
                "above_sma50": bool(row["above_sma50"]) if pd.notna(row.get("above_sma50")) else None,
                "above_sma200": bool(row["above_sma200"]) if pd.notna(row.get("above_sma200")) else None,
                "sma50_rising": bool(row["sma50_rising"]) if pd.notna(row.get("sma50_rising")) else None,
                "is_setup_day": d == setup.day,
            }
            # A causal pre-break scanner can disclose its plan only once the
            # completed plan bar is revealed.  This lets the execution agent use
            # deterministic scanner math without leaking a later confirmation.
            if d == setup.day and feats.get("signal_kind") == "prebreak_arm":
                tick["scanner_plan"] = {
                    "signal_as_of": feats.get("signal_as_of"),
                    "trigger": feats.get("entry_trigger", setup.entry_px),
                    "stop": feats.get("stop_px"),
                    "target1": feats.get("target1_px"),
                    "target2": feats.get("target2_px"),
                    "atr": feats.get("atr"),
                    "cup_depth_px": feats.get("cup_depth_px"),
                    "arm_expiry_bars": feats.get("arm_expiry_bars"),
                    "max_entry_gap_atr": feats.get("max_entry_gap_atr"),
                }
            if not neutral_meta and anchor:
                tick["vs_anchor_pct"] = round((close - anchor) / anchor * 100.0, 3)
            if fmt == "jsonl":
                _emit(json.dumps(tick), streams)
            else:
                for s in streams:
                    print(
                        f"  {d}  o={tick['o']} h={tick['h']} l={tick['l']} c={tick['c']} "
                        f"atr={tick['atr14']} sma50={tick['sma50']}",
                        file=s,
                    )
            n += 1
            if delay > 0:
                time.sleep(delay)

        last = float(window["close"].iloc[-1])
        end = {
            "type": "end",
            "bars": n,
            "close": round(last, 4),
            "session_end": win_dates[-1].isoformat() if win_dates else None,
        }
        if fmt == "jsonl":
            _emit(json.dumps(end), streams)
        return n
    finally:
        if fh is not None:
            fh.close()


def _stream_human(setup, df, start_t, anchor, streams, delay) -> int:
    def w(line=""):
        for s in streams:
            print(line, file=s)
            s.flush()

    w("═" * 72)
    w(f"  {setup.ticker}   {setup.day:%Y-%m-%d} ({setup.day:%a})")
    w(
        f"  entry {setup.time_et} ET @ ${setup.entry_px:.2f}   "
        f"gap +{setup.gap_pct:.1f}%   RVOL {setup.rvol:.1f}×   "
        f"float {_fmt_float(setup.float_shares)}"
        if setup.entry_px is not None else f"  entry {setup.time_et} ET"
    )
    w(f"  {setup.reason}")
    w(f"  streaming 1-min bars {start_t:%H:%M}→{RTH_CLOSE:%H:%M} ET  (vs entry ${anchor:.2f})")
    w("═" * 72)
    w(
        f"  {'time':>5}  {'open':>8} {'high':>8} {'low':>8} {'close':>8}  "
        f"{'vol':>9} {'rvolB':>6} {'vwap':>8} {'ema9':>8}  {'vs anch':>8}"
    )
    w("  " + "─" * 78)

    n = 0
    day_high = float("-inf")
    for ts, row in df.iterrows():
        t = ts.time()
        if t < start_t or t >= RTH_CLOSE:
            continue
        close = float(row["close"])
        hi = float(row["high"])
        day_high = max(day_high, hi)
        chg = (close - anchor) / anchor * 100.0 if anchor else 0.0
        rvb = f"{row['rvol_bar']:5.1f}" if pd.notna(row["rvol_bar"]) else "    -"
        mark = ""
        if setup.entry_px is not None and ts.strftime("%H:%M") == setup.time_et:
            mark = "  ◀ ENTRY"
        elif row["new_high"]:
            mark = "  ▲ new high"
        w(
            f"  {ts:%H:%M}  {row['open']:8.3f} {hi:8.3f} {row['low']:8.3f} "
            f"{close:8.3f}  {int(row['volume']):9,d} {rvb}× {row['vwap']:8.3f} "
            f"{row['ema9']:8.3f}  {chg:+7.2f}%{mark}"
        )
        n += 1
        if delay > 0:
            time.sleep(delay)

    w("  " + "─" * 78)
    if n == 0 or day_high == float("-inf"):
        w(f"  bars streamed: 0   no bars matched streaming window (start {start_t:%H:%M} ET)")
    elif anchor:
        last = float(df["close"].iloc[-1])
        run = (day_high - anchor) / anchor * 100.0
        eod = (last - anchor) / anchor * 100.0
        w(
            f"  bars streamed: {n}   session high ${day_high:.3f} ({run:+.1f}% vs entry)"
            f"   close ${last:.3f} ({eod:+.1f}%)"
        )
    return n


def _stream_jsonl(
    setup, df, start_t, anchor, streams, delay, force: bool = False,
    ext_df: Optional[pd.DataFrame] = None, *, neutral_meta: bool = False,
    five_minute_context: bool = False,
) -> int:
    ctx = _context(setup.ticker, setup.day, force=force, ext_df=ext_df)
    meta = {
        "type": "meta",
        "ticker": setup.ticker,
        "date": setup.day.isoformat(),
        "gap_pct": setup.gap_pct,
        "float_shares": setup.float_shares,
        "prior_close": ctx["prior_close"],
        "prior_high": ctx["prior_high"],
        "prior_low": ctx["prior_low"],
        "pm_high": ctx["pm_high"],
        "pm_low": ctx["pm_low"],
        "context_warnings": ctx["context_warnings"],
        "session_end": RTH_CLOSE.strftime("%H:%M"),
    }
    if neutral_meta:
        # The scanner chose the ticker/date, but the trader must discover its own
        # entry from the live tape. Do not reveal the scanner's completed-bar trigger,
        # its all-day RVOL, or its retrospective explanation.
        meta["session_start"] = RTH_OPEN.strftime("%H:%M")
        meta["scanner_trigger_hidden"] = True
    else:
        meta.update({
            "entry_time": setup.time_et,
            "entry_px": setup.entry_px,
            "rvol": setup.rvol,
            "anchor_px": round(anchor, 4) if anchor else None,
            "anchor_note": ("anchor_px is the recorded 5-MIN breakout level, not your "
                            "fill — enter on the 1-min criteria and track P&L from your "
                            "actual 1-min entry; vs_anchor_pct below is vs anchor_px."),
            "reason": setup.reason,
        })
    _emit(json.dumps(meta), streams)

    n = 0
    day_high = float("-inf")
    entry_idx = None
    active5: Optional[dict] = None
    completed5: list[dict] = []
    for ts, row in df.iterrows():
        t = ts.time()
        if t < start_t or t >= RTH_CLOSE:
            continue
        close = float(row["close"])
        hi = float(row["high"])
        day_high = max(day_high, hi)
        is_entry = setup.entry_px is not None and ts.strftime("%H:%M") == setup.time_et
        if is_entry:
            entry_idx = n
        bar5 = None
        if five_minute_context:
            bucket = ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)
            if active5 is None or active5["bucket"] != bucket:
                active5 = {
                    "bucket": bucket,
                    "time": bucket.strftime("%H:%M"),
                    "o": float(row["open"]), "h": hi, "l": float(row["low"]),
                    "c": close, "v": int(row["volume"]),
                }
            else:
                active5["h"] = max(active5["h"], hi)
                active5["l"] = min(active5["l"], float(row["low"]))
                active5["c"] = close
                active5["v"] += int(row["volume"])
            # The 5-minute candle is actionable only after minute :04/:09/... closes.
            if ts.minute % 5 == 4:
                prior = completed5[-3:]
                prior_high = max((b["h"] for b in prior), default=None)
                prior_low = min((b["l"] for b in prior), default=None)
                prior_avg_volume = (sum(b["v"] for b in prior) / len(prior)) if prior else None
                bar5 = {
                    "time": active5["time"],
                    "o": round(active5["o"], 4), "h": round(active5["h"], 4),
                    "l": round(active5["l"], 4), "c": round(active5["c"], 4),
                    "v": active5["v"],
                    "prior_3_high": round(prior_high, 4) if prior_high is not None else None,
                    "prior_3_low": round(prior_low, 4) if prior_low is not None else None,
                    "prior_3_avg_volume": round(prior_avg_volume, 2) if prior_avg_volume else None,
                    "volume_ratio": round(active5["v"] / prior_avg_volume, 2)
                    if prior_avg_volume else None,
                }
                completed5.append(dict(active5))
        tick = {
            "type": "tick",
            "i": n,
            "time": ts.strftime("%H:%M"),
            "o": round(float(row["open"]), 4),
            "h": round(hi, 4),
            "l": round(float(row["low"]), 4),
            "c": round(close, 4),
            "v": int(row["volume"]),
            "cum_vol": int(row["cum_vol"]),
            "vwap": round(float(row["vwap"]), 4) if pd.notna(row["vwap"]) else None,
            "ema9": round(float(row["ema9"]), 4),
            "ema20": round(float(row["ema20"]), 4),
            "macd": round(float(row["macd"]), 4),
            "macd_signal": round(float(row["macd_signal"]), 4),
            "macd_hist": round(float(row["macd_hist"]), 4),
            "session_high": round(float(row["session_high"]), 4),
            "new_high": bool(row["new_high"]),
            "above_vwap": bool(close >= float(row["vwap"])) if pd.notna(row["vwap"]) else None,
            "rvol_bar": round(float(row["rvol_bar"]), 2) if pd.notna(row["rvol_bar"]) else None,
        }
        if neutral_meta:
            # No scanner trigger timing or price leaks into the live decision stream.
            pass
        else:
            tick.update({
                "bars_since_entry": (n - entry_idx) if entry_idx is not None else None,
                "vs_anchor_pct": round((close - anchor) / anchor * 100.0, 3) if anchor else None,
                "is_entry_bar": is_entry,
            })
        if five_minute_context:
            tick["bar5_complete"] = bar5
        _emit(json.dumps(tick), streams)
        n += 1
        if delay > 0:
            time.sleep(delay)

    last = float(df["close"].iloc[-1])
    end = {
        "type": "end",
        "bars": n,
        "session_high": round(day_high, 4) if day_high != float("-inf") else None,
        "close": round(last, 4),
    }
    if not neutral_meta:
        end.update({
            "run_vs_anchor_pct": round((day_high - anchor) / anchor * 100.0, 3) if anchor else None,
            "close_vs_anchor_pct": round((last - anchor) / anchor * 100.0, 3) if anchor else None,
        })
    _emit(json.dumps(end), streams)
    return n


# ───────────────────────────── CLI ──────────────────────────────────────────


def _parse_date(s: Optional[str]) -> Optional[date]:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


def _parse_hhmm(s: str) -> dtime:
    h, m = (int(x) for x in s.split(":"))
    return dtime(h, m)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m trading.llm_trader.replay",
        description="Replay one recorded setup (1-min day-trade or multi-day daily).",
    )
    p.add_argument("--db", default=str(DATA_DIR / "entries.db"),
                   help="entries SQLite DB (default: package data/entries.db)")
    p.add_argument("--strategy", default=None,
                   help="filter setups by strategy family (warrior, cup_handle, …)")
    p.add_argument("--ticker", help="restrict the random pick to this ticker")
    p.add_argument("--date", help="restrict the pick to this date (YYYY-MM-DD)")
    p.add_argument("--after", default="09:30",
                   help="only pick setups entering at/after this ET time (default 09:30)")
    p.add_argument("--seed", type=int, help="seed the random pick (reproducible)")
    p.add_argument("--from-open", action="store_true",
                   help="stream from 09:30 instead of from the entry time (1min only)")
    p.add_argument("--neutral-meta", action="store_true",
                   help="hide the scanner's historical trigger/RVOL/reason from JSONL output")
    p.add_argument("--five-minute-context", action="store_true",
                   help="include one completed 5-minute candle after each fifth minute")
    p.add_argument("--delay", type=float, default=0.0,
                   help="seconds to pause between bars (stream ~live; default 0). "
                        "Use 60 for one tick per wall-clock minute.")
    p.add_argument("--format", choices=("human", "jsonl"), default="human",
                   help="output format: human table (default) or JSON lines")
    p.add_argument("--out-file",
                   help="also append each output line to this file (poll target)")
    p.add_argument("--force", action="store_true",
                   help="force a fresh provider fetch (bypass cache)")
    p.add_argument("--bar-resolution", choices=("1min", "1day"), default=None,
                   help="force bar resolution (default: inferred from strategy)")
    p.add_argument("--max-hold-bars", type=int, default=None,
                   help="multi-day: trading days after setup day (default 40)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    strategy = args.strategy
    skip_time = strategy is not None and strategy != "warrior"
    # default db per strategy when caller didn't override and strategy is set
    db = args.db
    if strategy and strategy != "warrior" and args.db == str(DATA_DIR / "entries.db"):
        try:
            from .strategies import get_strategy
            db = str(get_strategy(strategy).default_db_path())
        except KeyError:
            pass
    setup = pick_setup(
        db,
        ticker=args.ticker,
        day=_parse_date(args.date),
        after=_parse_hhmm(args.after),
        seed=args.seed,
        strategy=strategy,
        skip_time_filter=skip_time,
    )
    return replay(
        setup,
        from_open=args.from_open,
        neutral_meta=args.neutral_meta,
        five_minute_context=args.five_minute_context,
        delay=args.delay,
        force=args.force,
        fmt=args.format,
        out_file=args.out_file,
        bar_resolution=args.bar_resolution,
        max_hold_bars=args.max_hold_bars,
    )


if __name__ == "__main__":
    raise SystemExit(main())
