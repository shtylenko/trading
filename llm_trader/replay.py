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
from .indicators import enrich_1min_for_replay, session_vwap

RTH_OPEN = dtime(9, 30)
RTH_CLOSE = dtime(16, 0)
logger = logging.getLogger("llm_trader.replay")


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

    @property
    def entry_time(self) -> dtime:
        h, m = (int(x) for x in self.time_et.split(":"))
        return dtime(h, m)


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
) -> Setup:
    """Choose a setup row, defaulting to a random RTH (after-09:30) entry.

    Filters: optional ``ticker`` / ``day`` exact match, and ``time_et >= after``
    (so premarket breakouts are excluded by default). ``at_time`` ("HH:MM") pins an
    *exact* setup — the batch harness passes it so the agent trades the same row the
    holdout snapshotted, not an unseeded pick among same-day setups. Raises if nothing
    matches.
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
        rows = conn.execute(sql, params).fetchall()

    rows = [r for r in rows if _hhmm_after(r["time_et"], after)]
    if not rows:
        raise SystemExit(
            "No matching setup found (after "
            f"{after.strftime('%H:%M')} ET"
            + (f", ticker={ticker}" if ticker else "")
            + (f", date={day}" if day else "")
            + ")."
        )

    rng = random.Random(seed)
    r = rng.choice(rows)
    return Setup(
        ticker=r["ticker"],
        day=datetime.strptime(r["date"], "%Y-%m-%d").date(),
        time_et=r["time_et"],
        entry_px=r["entry_px"],
        gap_pct=r["gap_pct"],
        rvol=r["rvol"],
        float_shares=r["float_shares"],
        reason=r["reason"],
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
    delay: float = 0.0,
    force: bool = False,
    fmt: str = "human",
    out: TextIO = sys.stdout,
    out_file: Optional[str | Path] = None,
) -> int:
    """Stream the day's 1-minute bars from the entry (or open) to the close.

    ``fmt='human'`` prints an aligned table; ``fmt='jsonl'`` emits a ``meta``
    line, a ``tick`` line per minute, then an ``end`` line. With ``out_file`` set,
    every line is also appended there (so a backgrounded run can be polled).
    Returns the number of bars streamed. Indicators are computed over the full
    RTH session so they match a chart; only bars from the start point are shown.
    """
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
            return 0

        df = _enrich(df)
        start_t = RTH_OPEN if from_open else setup.entry_time
        anchor = setup.entry_px if setup.entry_px else float(df["open"].iloc[0])

        if fmt == "jsonl":
            return _stream_jsonl(setup, df, start_t, anchor, streams, delay, force=force, ext_df=ext_df)
        return _stream_human(setup, df, start_t, anchor, streams, delay)
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


def _stream_jsonl(setup, df, start_t, anchor, streams, delay, force: bool = False, ext_df: Optional[pd.DataFrame] = None) -> int:
    ctx = _context(setup.ticker, setup.day, force=force, ext_df=ext_df)
    meta = {
        "type": "meta",
        "ticker": setup.ticker,
        "date": setup.day.isoformat(),
        "entry_time": setup.time_et,
        "entry_px": setup.entry_px,
        "gap_pct": setup.gap_pct,
        "rvol": setup.rvol,
        "float_shares": setup.float_shares,
        "anchor_px": round(anchor, 4) if anchor else None,
        "anchor_note": ("anchor_px is the recorded 5-MIN breakout level, not your "
                        "fill — enter on the 1-min criteria and track P&L from your "
                        "actual 1-min entry; vs_anchor_pct below is vs anchor_px."),
        "prior_close": ctx["prior_close"],
        "prior_high": ctx["prior_high"],
        "prior_low": ctx["prior_low"],
        "pm_high": ctx["pm_high"],
        "pm_low": ctx["pm_low"],
        "context_warnings": ctx["context_warnings"],
        "session_end": RTH_CLOSE.strftime("%H:%M"),
        "reason": setup.reason,
    }
    _emit(json.dumps(meta), streams)

    n = 0
    day_high = float("-inf")
    entry_idx = None
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
        tick = {
            "type": "tick",
            "i": n,
            "bars_since_entry": (n - entry_idx) if entry_idx is not None else None,
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
            "vs_anchor_pct": round((close - anchor) / anchor * 100.0, 3) if anchor else None,
            "is_entry_bar": is_entry,
        }
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
        "run_vs_anchor_pct": round((day_high - anchor) / anchor * 100.0, 3) if anchor else None,
        "close_vs_anchor_pct": round((last - anchor) / anchor * 100.0, 3) if anchor else None,
    }
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
        description="Replay one recorded setup's day minute-by-minute.",
    )
    p.add_argument("--db", default=str(DATA_DIR / "entries.db"),
                   help="entries SQLite DB (default: package data/entries.db)")
    p.add_argument("--ticker", help="restrict the random pick to this ticker")
    p.add_argument("--date", help="restrict the pick to this date (YYYY-MM-DD)")
    p.add_argument("--after", default="09:30",
                   help="only pick setups entering at/after this ET time (default 09:30)")
    p.add_argument("--seed", type=int, help="seed the random pick (reproducible)")
    p.add_argument("--from-open", action="store_true",
                   help="stream from 09:30 instead of from the entry time")
    p.add_argument("--delay", type=float, default=0.0,
                   help="seconds to pause between bars (stream ~live; default 0). "
                        "Use 60 for one tick per wall-clock minute.")
    p.add_argument("--format", choices=("human", "jsonl"), default="human",
                   help="output format: human table (default) or JSON lines")
    p.add_argument("--out-file",
                   help="also append each output line to this file (poll target)")
    p.add_argument("--force", action="store_true",
                   help="force a fresh provider fetch (bypass cache)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup = pick_setup(
        args.db,
        ticker=args.ticker,
        day=_parse_date(args.date),
        after=_parse_hhmm(args.after),
        seed=args.seed,
    )
    replay(
        setup,
        from_open=args.from_open,
        delay=args.delay,
        force=args.force,
        fmt=args.format,
        out_file=args.out_file,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
