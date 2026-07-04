#!/usr/bin/env python3
"""Local web dashboard for Strategy Lab backtest results."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.runner.pipeline import current_code_signature
from trading.lab.storage.duckdb import DB_PATH, connect, init_db
from trading.lab.storage.lifecycle import list_lifecycle
from trading.lab.validation.funnel import FUNNEL
from trading.lab.validation.run_stats import validate_daily_r

# Sort order for lifecycle dispositions: live work on top, graveyard at bottom.
_DISPOSITION_RANK = {"promoted": 0, "active": 1, "killed": 2, "archived": 3}


def _annotate_lifecycle(conn, rows: list[dict]) -> list[dict]:
    """Attach each release's funnel position (stage/disposition) to its rows.

    A release with no ledger row is treated as stage 0 / active. ``stage_name``
    and ``disposition_rank`` are added so the UI can label and sort without
    re-deriving the ladder.
    """
    ledger = list_lifecycle(conn)
    for row in rows:
        lc = ledger.get(row.get("release_id"))
        stage = int(lc["stage"]) if lc else 0
        disposition = lc["disposition"] if lc else "active"
        row["stage"] = stage
        row["stage_name"] = FUNNEL[stage].name if 0 <= stage < len(FUNNEL) else str(stage)
        row["disposition"] = disposition
        row["killed_stage"] = lc.get("killed_stage") if lc else None
        row["lifecycle_reason"] = lc.get("reason") if lc else None
        row["disposition_rank"] = _DISPOSITION_RANK.get(disposition, 9)
    return rows


def _dicts(cur) -> list[dict]:
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _annotate_freshness(rows: list[dict], cache: dict | None = None) -> list[dict]:
    """Tag each row with whether its stored code_signature matches HEAD.

    Sets ``code_fresh`` (True=matches current code, False=stale, None=unknown
    when the run predates signatures or the release is no longer registered)
    and ``current_signature`` (today's hash) for the stale tooltip. The per-
    release ``cache`` means each release's source is hashed at most once per
    request; pass a shared dict to reuse it across multiple result sets.
    """
    if cache is None:
        cache = {}
    for row in rows:
        release_id = row.get("release_id")
        stored = row.get("code_signature")
        if not release_id or not stored:
            row["code_fresh"] = None
            row["current_signature"] = None
            continue
        if release_id not in cache:
            try:
                cache[release_id] = current_code_signature(release_id)
            except Exception:
                # unknown/unregistered release — can't judge freshness
                cache[release_id] = None
        current = cache[release_id]
        row["current_signature"] = current
        row["code_fresh"] = (stored == current) if current else None
    return rows


# R-based metrics live in release_metrics.metrics_json, not in dedicated
# columns; lift them into the row dicts so the UI can read them directly.
_JSON_METRIC_KEYS = (
    "total_realized_r",
    "avg_realized_r",
    "best_trade_r",
    "worst_trade_r",
    "account_return_pct_at_1pct_risk",
    "no_fill_count",
)


def _lift_json_metrics(rows: list[dict]) -> list[dict]:
    for row in rows:
        raw = row.get("metrics_json")
        if not raw:
            continue
        try:
            extra = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for key in _JSON_METRIC_KEYS:
            if key in extra and row.get(key) is None:
                row[key] = extra[key]
    return rows


def _latest_metric_rows(conn, testset: str | None = None) -> list[dict]:
    where = "WHERE rm.testset = ?" if testset else ""
    params = [testset] if testset else []
    cur = conn.execute(
        f"""
        WITH ranked AS (
            SELECT
                rm.run_id, rm.testset, rm.release_id, rm.strategy_alias,
                rm.strategy_letter, rm.metric_scope, rm.trade_count, rm.wins,
                rm.losses, rm.win_rate, rm.profit_factor, rm.total_pnl_pct,
                rm.avg_pnl_pct, rm.best_trade_pct, rm.worst_trade_pct,
                rm.metrics_json,
                r.run_type, r.status, r.started_at, r.completed_at,
                r.completed_days, r.total_days, r.engine_version, r.code_signature,
                ROW_NUMBER() OVER (
                    PARTITION BY rm.release_id, COALESCE(rm.testset, ''), rm.metric_scope
                    ORDER BY r.started_at DESC, r.completed_at DESC, rm.run_id DESC
                ) AS recency_rank
            FROM release_metrics rm
            LEFT JOIN runs r ON r.run_id = rm.run_id
            {where}
        )
        SELECT *
        FROM ranked
        WHERE recency_rank = 1
        ORDER BY release_id, metric_scope
        """,
        params,
    )
    return _lift_json_metrics(_dicts(cur))


# ── Marketdata cache coverage page ──────────────────────────────────────────
# A read-only view of which months we have cached bars for, per ticker ×
# timeframe, built entirely from the per-ticker meta.json `coverage` maps
# (no parquet reads). Sample group = long-lived large caps that have traded
# continuously since well before our earliest data, so any in-range hole is a
# real cache gap, not a listing gap.
_MARKETDATA_DIR = PROJECT_ROOT / "engine" / "strategy_lab" / "marketdata" / "data"
CACHE_TIMEFRAMES = ["1min", "5min", "15min", "1day"]
CACHE_SAMPLE_GROUPS: dict[str, list[str]] = {
    "long_lived": ["MSFT", "AAPL", "BAC", "JPM", "KO", "XOM", "JNJ", "WMT", "PG", "GE"],
}


def _read_coverage_meta(ticker: str, timeframe: str) -> dict | None:
    """Load one ticker×timeframe meta.json (raw/rth), or None if absent."""
    path = (
        _MARKETDATA_DIR / timeframe / ticker
        / "session=rth" / "adjustment=raw" / "meta.json"
    )
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _month_iter(start_ym: str, end_ym: str):
    """Yield 'YYYY-MM' strings inclusive from start_ym to end_ym."""
    sy, sm = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_ym[:4]), int(end_ym[5:7])
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            m, y = 1, y + 1


def get_cache_coverage(group: str = "long_lived") -> dict:
    """Per ticker×timeframe monthly cache-coverage matrix for a sample group.

    For each month in range, a cell is classified against the NYSE trading
    calendar: ``full`` (every expected session cached and complete),
    ``partial`` (some sessions cached, or some flagged incomplete),
    ``missing`` (an in-range month with zero cached sessions), or ``na``
    (before the ticker's earliest cached month, or a timeframe never cached —
    e.g. 15min today). Expected trading days are computed once for the whole
    axis (ticker-independent) and reused.
    """
    from datetime import date

    tickers = CACHE_SAMPLE_GROUPS.get(group) or CACHE_SAMPLE_GROUPS["long_lived"]

    metas: dict[tuple[str, str], dict] = {}
    earliest_ym: str | None = None
    for ticker in tickers:
        for tf in CACHE_TIMEFRAMES:
            meta = _read_coverage_meta(ticker, tf)
            if not meta:
                continue
            metas[(ticker, tf)] = meta
            e = (meta.get("earliest") or "")[:7]
            if e and (earliest_ym is None or e < earliest_ym):
                earliest_ym = e

    today = date.today()
    current_ym = f"{today.year:04d}-{today.month:02d}"
    if earliest_ym is None:
        earliest_ym = current_ym
    months = list(_month_iter(earliest_ym, current_ym))

    # Expected NYSE sessions per month, computed once over the full axis.
    expected_by_month: dict[str, int] = dict.fromkeys(months, 0)
    try:
        from trading.marketdata.calendar import trading_days_in_range

        axis_start = date(int(earliest_ym[:4]), int(earliest_ym[5:7]), 1)
        for d in trading_days_in_range(axis_start, today):
            ym = f"{d.year:04d}-{d.month:02d}"
            if ym in expected_by_month:
                expected_by_month[ym] += 1
    except Exception:
        # Calendar unavailable — fall back to present/absent only (expected=0
        # means a month with any coverage reads as full).
        pass

    rows: list[dict] = []
    for ticker in tickers:
        for tf in CACHE_TIMEFRAMES:
            meta = metas.get((ticker, tf))
            row = {
                "ticker": ticker,
                "timeframe": tf,
                "last_updated": (meta or {}).get("last_updated"),
                "earliest": (meta or {}).get("earliest"),
                "latest": (meta or {}).get("latest"),
                "total_rows": (meta or {}).get("total_rows", 0),
            }
            present: dict[str, int] = defaultdict(int)
            incomplete: dict[str, int] = defaultdict(int)
            if meta:
                for day, info in (meta.get("coverage") or {}).items():
                    ym = day[:7]
                    present[ym] += 1
                    if isinstance(info, dict) and not info.get("complete", True):
                        incomplete[ym] += 1
            row_earliest = (row["earliest"] or "")[:7]

            cells = []
            counts = {"full": 0, "partial": 0, "missing": 0, "na": 0}
            for ym in months:
                exp = expected_by_month.get(ym, 0)
                n = present.get(ym, 0)
                inc = incomplete.get(ym, 0)
                if not meta or not row_earliest or ym < row_earliest:
                    status = "na"
                elif n == 0:
                    status = "missing"
                elif (exp == 0 or n >= exp) and inc == 0:
                    status = "full"
                else:
                    status = "partial"
                counts[status] += 1
                cells.append({
                    "month": ym, "status": status,
                    "present": n, "expected": exp, "incomplete": inc,
                })
            row["cells"] = cells
            row["counts"] = counts
            rows.append(row)

    return {"group": group, "months": months, "rows": rows,
            "groups": sorted(CACHE_SAMPLE_GROUPS)}


def get_testsets(conn) -> dict:
    rows = _dicts(
        conn.execute(
            """
            SELECT DISTINCT testset
            FROM runs
            WHERE testset IS NOT NULL AND testset != ''
            UNION
            SELECT DISTINCT testset
            FROM release_metrics
            WHERE testset IS NOT NULL AND testset != ''
            ORDER BY testset
            """
        )
    )
    names = [r["testset"] for r in rows]
    latest = _latest_metric_rows(conn)
    by_testset: dict[str, list[dict]] = defaultdict(list)
    for row in latest:
        if row.get("testset"):
            by_testset[row["testset"]].append(row)

    out = []
    for name in names:
        metrics = by_testset.get(name, [])
        range_row = conn.execute(
            """
            SELECT MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
            FROM sessions
            WHERE testset = ?
            """,
            [name],
        ).fetchone()
        run_row = conn.execute(
            """
            SELECT COUNT(*) AS run_count, MAX(started_at) AS last_run
            FROM runs
            WHERE testset = ?
            """,
            [name],
        ).fetchone()
        trade_count = sum(int(m.get("trade_count") or 0) for m in metrics)
        wins = sum(int(m.get("wins") or 0) for m in metrics)
        total_pnl = sum(float(m.get("total_pnl_pct") or 0.0) for m in metrics)
        total_r = sum(float(m.get("total_realized_r") or 0.0) for m in metrics)
        out.append(
            {
                "name": name,
                "run_count": int(run_row[0] or 0) if run_row else 0,
                "last_run": run_row[1] if run_row else None,
                "date_range": {
                    "start": range_row[0] if range_row else None,
                    "end": range_row[1] if range_row else None,
                },
                "release_count": len(metrics),
                "releases": [m["release_id"] for m in metrics],
                "total_trades": trade_count,
                "win_rate": (wins / trade_count * 100.0) if trade_count else 0.0,
                "total_pnl": total_pnl,
                "total_realized_r": total_r,
            }
        )
    return {"testsets": out}


def get_testset_detail(conn, testset: str) -> dict:
    # One row per release = its MOST RECENT run, whether running or finished,
    # LEFT JOINed to its overall metrics. This unifies status/progress and
    # results in a single table: a still-running latest run shows up with live
    # progress and null metrics (rendered as dashes) until it completes.
    backtests = _lift_json_metrics(
        _dicts(
            conn.execute(
                """
                WITH latest AS (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY release_id ORDER BY started_at DESC, run_id DESC
                    ) AS rn
                    FROM runs
                    WHERE testset = ?
                )
                SELECT lr.run_id, lr.testset, lr.release_id, lr.strategy_alias,
                       lr.strategy_letter, lr.status, lr.started_at, lr.completed_at,
                       lr.completed_days, lr.total_days, lr.code_signature,
                       rm.metric_scope, rm.trade_count, rm.wins, rm.losses, rm.win_rate,
                       rm.profit_factor, rm.total_pnl_pct, rm.avg_pnl_pct,
                       rm.best_trade_pct, rm.worst_trade_pct, rm.metrics_json
                FROM latest lr
                LEFT JOIN release_metrics rm
                       ON rm.run_id = lr.run_id AND rm.metric_scope = 'overall'
                WHERE lr.rn = 1
                ORDER BY (lr.status = 'running') DESC, lr.release_id
                """,
                [testset],
            )
        )
    )
    _annotate_freshness(backtests)
    _annotate_lifecycle(conn, backtests)
    for row in backtests:
        run_id = row["run_id"]
        trades = conn.execute(
            """
            SELECT trade_date, pnl_pct, realized_r
            FROM trades
            WHERE run_id = ? AND entry_time IS NOT NULL
            ORDER BY trade_date, entry_time
            """,
            [run_id],
        ).fetchall()

        daily: dict[str, list[float]] = {}
        for trade_date, pnl_pct, realized_r in trades:
            day = str(trade_date)
            agg = daily.setdefault(day, [0.0, 0.0])
            agg[0] += float(pnl_pct or 0.0)
            agg[1] += float(realized_r or 0.0)

        cumulative = 0.0
        cum_r = 0.0
        equity_curve = []
        for day in sorted(daily):
            cumulative += daily[day][0]
            cum_r += daily[day][1]
            equity_curve.append({
                "date": day,
                "pnl": round(cumulative, 4),
                "cum_r": round(cum_r, 4),
            })
        row["equity_curve"] = equity_curve

        # Sign-flip permutation p + tail share for the table. Same helper /
        # seed / iters as the run page, so the column matches the panel
        # exactly. Skip the histogram (not needed in a table cell).
        val = get_run_validation(conn, run_id)
        if "error" not in val:
            row["perm_p"] = val["p_value"]
            row["top_k_share"] = val["top_k_share"]
            row["r_without_top_k"] = val["r_without_top_k"]

    sessions = _dicts(
        conn.execute(
            """
            SELECT session_id, run_id, trade_date, release_id, strategy_alias,
                   status, ticker_count, candidate_count, signal_count, trade_count
            FROM sessions
            WHERE testset = ?
            ORDER BY trade_date DESC, release_id
            LIMIT 500
            """,
            [testset],
        )
    )
    return {"testset": testset, "backtests": backtests, "sessions": sessions}


def get_run_detail(conn, run_id: str) -> dict:
    run = conn.execute(
        """
        SELECT run_id, run_type, testset, release_id, strategy_alias,
               strategy_letter, status, started_at, completed_at,
               engine_version, code_signature, completed_days, total_days, notes
        FROM runs
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchone()
    if not run:
        return {"error": "Run not found"}
    run_cols = [
        "run_id",
        "run_type",
        "testset",
        "release_id",
        "strategy_alias",
        "strategy_letter",
        "status",
        "started_at",
        "completed_at",
        "engine_version",
        "code_signature",
        "completed_days",
        "total_days",
        "notes",
    ]
    metrics = _lift_json_metrics(
        _dicts(
            conn.execute(
                """
                SELECT metric_scope, trade_count, wins, losses, win_rate, profit_factor,
                       total_pnl_pct, avg_pnl_pct, best_trade_pct, worst_trade_pct,
                       metrics_json
                FROM release_metrics
                WHERE run_id = ?
                ORDER BY metric_scope
                """,
                [run_id],
            )
        )
    )
    sessions = _dicts(
        conn.execute(
            """
            SELECT session_id, trade_date, status, ticker_count, candidate_count,
                   signal_count, trade_count, error
            FROM sessions
            WHERE run_id = ?
            ORDER BY trade_date
            """,
            [run_id],
        )
    )
    trades = _dicts(
        conn.execute(
            """
            SELECT trade_id, signal_id, session_id, trade_date, testset, ticker,
                   release_id, strategy_alias, setup_type, direction, entry_time,
                   entry_price, exit_time, exit_price, exit_reason, pnl_pct,
                   gross_pnl_pct, realized_r, mfe_pct, mae_pct, fees_pct,
                   slippage_pct, context_json
            FROM trades
            WHERE run_id = ?
              AND entry_time IS NOT NULL
            ORDER BY trade_date, entry_time, ticker
            """,
            [run_id],
        )
    )

    daily: dict[str, dict[str, Any]] = {}
    for trade in trades:
        if trade.get("entry_time") is None:
            continue
        day = str(trade["trade_date"])
        if day not in daily:
            daily[day] = {"date": day, "daily_pnl": 0.0, "daily_r": 0.0, "trades": 0}
        daily[day]["daily_pnl"] += float(trade.get("pnl_pct") or 0.0)
        daily[day]["daily_r"] += float(trade.get("realized_r") or 0.0)
        daily[day]["trades"] += 1
    # Model equity at 1% account risk per trade: each day's summed R moves
    # the account by R percent (trades within a day are concurrent, so they
    # compound daily, not per-trade). This is "1%-risk model equity", not a
    # margin-accurate simulation: it assumes the full 1% risk is always on
    # (the 4x leverage cap can clip size) and ignores concurrency limits.
    cumulative = 0.0
    cum_r = 0.0
    equity = 100.0
    peak = 100.0
    max_dd_pct = 0.0
    equity_curve = []
    for day in sorted(daily):
        cumulative += daily[day]["daily_pnl"]
        cum_r += daily[day]["daily_r"]
        equity *= 1.0 + 0.01 * daily[day]["daily_r"]
        peak = max(peak, equity)
        max_dd_pct = min(max_dd_pct, (equity - peak) / peak * 100.0)
        equity_curve.append(
            {
                "date": day,
                "daily_pnl": round(daily[day]["daily_pnl"], 4),
                "pnl": round(cumulative, 4),
                "daily_r": round(daily[day]["daily_r"], 4),
                "cum_r": round(cum_r, 4),
                "equity": round(equity, 4),
                "trades": daily[day]["trades"],
            }
        )

    run_dict = dict(zip(run_cols, run))
    _annotate_freshness([run_dict])
    _annotate_lifecycle(conn, [run_dict])

    months, quarters = _period_breakdown(trades)

    return {
        "run": run_dict,
        "metrics": metrics,
        "sessions": sessions,
        "trades": trades,
        "equity_curve": equity_curve,
        "max_drawdown_pct": round(max_dd_pct, 2),
        "months": months,
        "quarters": quarters,
    }


def _period_breakdown(trades: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aggregate filled trades into per-month and per-quarter metric rows.

    Buckets by ``trade_date`` (YYYY-MM-DD). Each row carries the same shape so
    the UI can render both tables from one template: trades, sum/mean R, win
    rate (R > 0), and unsized PnL%, plus a running cumulative R across rows so
    the regime carry is visible at a glance.
    """
    months: dict[str, dict[str, float]] = {}
    quarters: dict[str, dict[str, float]] = {}
    for t in trades:
        if t.get("entry_time") is None:
            continue
        d = str(t["trade_date"])
        if len(d) < 7:
            continue
        ym = d[:7]
        q = (int(d[5:7]) - 1) // 3 + 1
        yq = f"{d[:4]}-Q{q}"
        r = float(t.get("realized_r") or 0.0)
        pnl = float(t.get("pnl_pct") or 0.0)
        for key, bucket in ((ym, months), (yq, quarters)):
            b = bucket.setdefault(
                key, {"trades": 0, "sum_r": 0.0, "sum_pnl": 0.0, "wins": 0}
            )
            b["trades"] += 1
            b["sum_r"] += r
            b["sum_pnl"] += pnl
            if r > 0:
                b["wins"] += 1

    def finalize(bucket: dict[str, dict[str, float]]) -> list[dict]:
        out: list[dict] = []
        cum_r = 0.0
        for key in sorted(bucket):
            b = bucket[key]
            n = int(b["trades"])
            cum_r += b["sum_r"]
            out.append(
                {
                    "period": key,
                    "trades": n,
                    "sum_r": round(b["sum_r"], 3),
                    "mean_r": round(b["sum_r"] / n, 4) if n else 0.0,
                    "win_rate": round(100.0 * b["wins"] / n, 1) if n else 0.0,
                    "sum_pnl_pct": round(b["sum_pnl"], 3),
                    "cum_r": round(cum_r, 3),
                }
            )
        return out

    return finalize(months), finalize(quarters)


def get_run_validation(conn, run_id: str, iters: int = 10_000) -> dict:
    """Sign-flip permutation validation of a run's daily R series.

    Cheap enough (vectorized numpy) to compute on demand per request. This
    is the same gate used in the screen funnel; the UI draws the null
    distribution with the observed total R marked.
    """
    run = conn.execute(
        "SELECT release_id, testset FROM runs WHERE run_id = ?", [run_id]
    ).fetchone()
    if run is None:
        return {"error": "Run not found"}
    trades = conn.execute(
        """
        SELECT trade_date, realized_r FROM trades
        WHERE run_id = ? AND realized_r IS NOT NULL
        ORDER BY trade_date
        """,
        [run_id],
    ).fetchall()
    if not trades:
        return {"error": "Run has no trades with realized_r"}
    n_days = conn.execute(
        "SELECT COUNT(DISTINCT trade_date) FROM sessions "
        "WHERE run_id = ? AND status = 'completed'",
        [run_id],
    ).fetchone()[0]

    result = validate_daily_r(trades, int(n_days or 0), iters=iters)
    result["run_id"] = run_id
    result["release_id"] = run[0]
    result["testset"] = run[1]
    return result


def get_trade_detail(conn, trade_id: str) -> dict:
    from datetime import datetime

    row = conn.execute(
        """
        SELECT trade_id, signal_id, session_id, run_id, trade_date, testset, ticker,
               release_id, strategy_letter, strategy_alias, setup_type, direction,
               entry_time, entry_price, exit_time, exit_price, exit_reason, pnl_pct,
               gross_pnl_pct, realized_r, mfe_pct, mae_pct, fees_pct, slippage_pct,
               context_json
        FROM trades
        WHERE trade_id = ?
        """,
        [trade_id],
    ).fetchone()
    if not row:
        return {"error": "Trade not found"}

    cols = [
        "trade_id", "signal_id", "session_id", "run_id", "trade_date", "testset", "ticker",
        "release_id", "strategy_letter", "strategy_alias", "setup_type", "direction",
        "entry_time", "entry_price", "exit_time", "exit_price", "exit_reason", "pnl_pct",
        "gross_pnl_pct", "realized_r", "mfe_pct", "mae_pct", "fees_pct", "slippage_pct",
        "context_json"
    ]
    trade = dict(zip(cols, row))

    # Query engine_version from runs
    engine_ver = conn.execute(
        "SELECT engine_version FROM runs WHERE run_id = ?",
        [trade["run_id"]]
    ).fetchone()
    trade["engine_version"] = engine_ver[0] if engine_ver else "unknown"

    # Query signal details
    sig = conn.execute(
        """
        SELECT stop_price, target_price, signal_time, entry_trigger
        FROM signals
        WHERE signal_id = ?
        """,
        [trade["signal_id"]],
    ).fetchone()
    if sig:
        trade["signal_stop_price"] = sig[0]
        trade["signal_target_price"] = sig[1]
        trade["signal_time"] = sig[2]
        trade["signal_entry_trigger"] = sig[3]
    else:
        trade["signal_stop_price"] = None
        trade["signal_target_price"] = None
        trade["signal_time"] = None
        trade["signal_entry_trigger"] = None

    # DuckDB returns TIMESTAMP columns as naive datetimes in the MACHINE's
    # timezone (aware values are converted on insert). Interpreting them as
    # ET in the UI displaces every marker by the machine-vs-ET offset, so
    # ship true epochs (naive .timestamp() assumes local time — correct
    # here) plus ET-formatted strings for display.
    from zoneinfo import ZoneInfo as _Zi

    def _to_unix(v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v)
            except ValueError:
                return None
        try:
            return v.timestamp()
        except (OSError, OverflowError, ValueError):
            return None

    def _to_et(u):
        if u is None:
            return None
        return datetime.fromtimestamp(u, _Zi("America/New_York")).strftime(
            "%Y-%m-%d %H:%M:%S ET")

    for fld in ("entry_time", "exit_time", "signal_time"):
        unix = _to_unix(trade.get(fld))
        trade[f"{fld}_unix"] = unix
        trade[f"{fld}_et"] = _to_et(unix)

    # Per-trade chart. Intraday trades (same-day entry & exit) get 1-minute RTH
    # bars + session VWAP. MULTI-DAY (swing) trades get DAILY bars over a window
    # spanning the hold plus a ~60-trading-day lead-in (the trend that drove
    # selection) and a short tail, with a 50-day SMA for trend context — VWAP and
    # an intraday axis are meaningless across a 20-day hold.
    def _as_date(v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v).date()
            except ValueError:
                try:
                    return datetime.strptime(v, "%Y-%m-%d").date()
                except ValueError:
                    return None
        return v.date() if hasattr(v, "date") else None

    entry_d = _as_date(trade.get("entry_time")) or _as_date(trade.get("trade_date"))
    exit_d = _as_date(trade.get("exit_time"))
    is_multiday = bool(entry_d and exit_d and exit_d > entry_d)
    trade["chart_mode"] = "daily" if is_multiday else "intraday"

    if is_multiday:
        # ── swing: daily bars + 50d SMA, date-string time axis ──────────────
        try:
            from trading.marketdata import fetch_bars
            from datetime import timedelta as _td
            disp_start = entry_d - _td(days=88)     # ~60 trading days of lead-in
            disp_end = exit_d + _td(days=14)         # short tail after exit
            fetch_start = disp_start - _td(days=90)  # extra history for the 50d SMA
            bars = fetch_bars(
                trade["ticker"], "1day",
                start=datetime(fetch_start.year, fetch_start.month, fetch_start.day),
                end=datetime(disp_end.year, disp_end.month, disp_end.day, 23, 59),
                session="rth", adjustment="raw", tz="America/New_York",
            )
            bars_json, sma_json = [], []
            if bars is not None and not bars.empty:
                bars = bars.sort_index()
                sma = bars["close"].rolling(50).mean()
                for ts, r in bars.iterrows():
                    dd = ts.date()
                    if dd < disp_start or dd > disp_end:
                        continue
                    tstr = dd.strftime("%Y-%m-%d")
                    bars_json.append({
                        "time": tstr, "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"]),
                        "volume": int(r["volume"]),
                    })
                    sv = sma.loc[ts]
                    if sv == sv:  # not NaN
                        sma_json.append({"time": tstr, "value": round(float(sv), 4)})
            trade["bars"] = bars_json
            trade["sma50"] = sma_json
            trade["vwap"] = []
            trade["entry_date_str"] = entry_d.strftime("%Y-%m-%d")
            trade["exit_date_str"] = exit_d.strftime("%Y-%m-%d")
        except Exception as e:
            trade["bars"] = []
            trade["sma50"] = []
            trade["vwap"] = []
            trade["bars_error"] = str(e)
        return trade

    # ── intraday: 1-minute bars + session VWAP (unchanged) ──────────────────
    try:
        from trading.marketdata import fetch_bars
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        d = trade["trade_date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()

        bars = fetch_bars(
            trade["ticker"], "1min",
            start=datetime(d.year, d.month, d.day, 9, 30, tzinfo=ny),
            end=datetime(d.year, d.month, d.day, 16, 0, tzinfo=ny),
            session="rth", adjustment="raw", tz="America/New_York",
        )
        if bars is not None and not bars.empty:
            typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
            cum_tp_vol = (typical * bars["volume"]).cumsum()
            cum_vol = bars["volume"].cumsum()
            vwap_series = cum_tp_vol / cum_vol

            bars_json = []
            vwap_json = []
            for ts, r in bars.iterrows():
                bars_json.append({
                    "time": int(ts.timestamp()),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(r["volume"]),
                })
                vwap_json.append({
                    "time": int(ts.timestamp()),
                    "value": round(float(vwap_series.loc[ts]), 4),
                })
            trade["bars"] = bars_json
            trade["vwap"] = vwap_json
        else:
            trade["bars"] = []
            trade["vwap"] = []
    except Exception as e:
        trade["bars"] = []
        trade["vwap"] = []
        trade["bars_error"] = str(e)

    return trade


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/report"):
            self._serve_html()
            return
        if path == "/api/testsets":
            with connect(read_only=True) as conn:
                self._serve_json(get_testsets(conn))
            return
        if path == "/api/testset":
            name = params.get("name", [None])[0]
            if not name:
                self._serve_json({"error": "Missing name"})
                return
            with connect(read_only=True) as conn:
                self._serve_json(get_testset_detail(conn, name))
            return
        if path == "/api/run":
            run_id = params.get("run_id", [None])[0]
            if not run_id:
                self._serve_json({"error": "Missing run_id"})
                return
            with connect(read_only=True) as conn:
                self._serve_json(get_run_detail(conn, run_id))
            return
        if path == "/api/validation":
            run_id = params.get("run_id", [None])[0]
            if not run_id:
                self._serve_json({"error": "Missing run_id"})
                return
            with connect(read_only=True) as conn:
                self._serve_json(get_run_validation(conn, run_id))
            return
        if path == "/api/cache":
            group = params.get("group", ["long_lived"])[0]
            self._serve_json(get_cache_coverage(group))
            return
        if path == "/api/trade":
            trade_id = params.get("trade_id", [None])[0]
            if not trade_id:
                self._serve_json({"error": "Missing trade_id"})
                return
            with connect(read_only=True) as conn:
                self._serve_json(get_trade_detail(conn, trade_id))
            return
        self._send_error(404, "Not found")

    def _serve_html(self):
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _json_sanitize(obj):
        """Replace non-finite floats (Infinity/NaN — e.g. a no-loss run's
        profit factor) with None. ``json.dumps`` emits bare ``Infinity``/
        ``NaN`` tokens which are invalid JSON and rejected by the browser's
        ``JSON.parse``/``response.json``, breaking the whole API response.
        """
        import math

        if isinstance(obj, float):
            return obj if math.isfinite(obj) else None
        if isinstance(obj, dict):
            return {k: DashboardHandler._json_sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [DashboardHandler._json_sanitize(v) for v in obj]
        return obj

    def _serve_json(self, payload):
        body = json.dumps(
            self._json_sanitize(payload), default=str, allow_nan=False
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, fmt, *args):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            super().log_message(fmt, *args)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Strategy Lab Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://unpkg.com/lightweight-charts@4.2.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root {
  --bg:#0d1117; --card:#161b22; --card2:#1c2333; --hover:#252d3f;
  --border:#30363d; --text:#f0f6fc; --text2:#8b949e; --text3:#6e7681;
  --green:#3fb950; --green-bg:rgba(63,185,80,.12);
  --red:#f85149; --red-bg:rgba(248,81,73,.12);
  --blue:#58a6ff; --blue-bg:rgba(88,166,255,.1);
  --yellow:#d29922; --orange:#f0883e; --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:var(--font); font-size:14px; line-height:1.45; padding:24px; }
.container { max-width:1400px; margin:0 auto; }
h1 { font-size:28px; margin:0 0 4px; }
h2 { font-size:18px; margin:0 0 14px; }
a { color:var(--blue); text-decoration:none; cursor:pointer; }
a:hover { text-decoration:underline; }
.subtitle { color:var(--text2); margin:0 0 24px; }
.breadcrumb { display:flex; gap:8px; align-items:center; color:var(--text2); margin-bottom:20px; flex-wrap:wrap; font-size:13px; }
.breadcrumb a { color:var(--text2); }
.sep { color:var(--text3); }
.grid { display:grid; gap:16px; }
.ts-card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px; cursor:pointer; transition:border-color .15s, transform .15s; }
.ts-card:hover { border-color:var(--text3); transform:translateY(-1px); }
.ts-card h3 { margin:0 0 8px; font-size:16px; }
.meta { display:flex; gap:18px; color:var(--text2); flex-wrap:wrap; font-size:13px; }
.badges { margin-top:12px; display:flex; gap:6px; flex-wrap:wrap; }
.badge { display:inline-flex; align-items:center; min-height:22px; padding:2px 9px; border-radius:999px; background:var(--blue-bg); color:var(--blue); font-size:11px; font-weight:650; text-transform:uppercase; }
.badge.green { background:var(--green-bg); color:var(--green); }
.badge.red { background:var(--red-bg); color:var(--red); }
.badge.amber { background:rgba(245,158,11,0.15); color:#f59e0b; }
.badge.running { background:rgba(59,130,246,0.16); color:var(--blue); }
.badge.running::before { content:''; width:7px; height:7px; border-radius:50%; background:currentColor; margin-right:6px; animation:pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.25; } }
.pbar { height:6px; border-radius:999px; background:var(--blue-bg); overflow:hidden; min-width:90px; }
.pbar > span { display:block; height:100%; background:var(--blue); border-radius:999px; transition:width .4s ease; }
.pbar.done > span { background:var(--green); }
.pbar.err > span { background:var(--red); }
.section { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px; margin-bottom:18px; }
.section.flush { padding:0; overflow:hidden; }
.mini-stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px; margin-bottom:18px; }
.mini-stat { background:var(--card2); border-radius:8px; padding:12px; text-align:center; min-height:68px; }
.mini-stat .v { font-size:18px; font-weight:750; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mini-stat .l { margin-top:3px; font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:.3px; }
.positive { color:var(--green); }
.negative { color:var(--red); }
.neutral { color:var(--text); }
.q-green { color:var(--green); }
.q-yellow { color:var(--yellow); }
.q-orange { color:var(--orange); }
.q-red { color:var(--red); }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th { text-align:left; padding:10px 12px; color:var(--text2); border-bottom:1px solid var(--border); white-space:nowrap; font-weight:650; }
td { padding:8px 12px; border-bottom:1px solid var(--border); white-space:nowrap; }
tbody tr.clickable { cursor:pointer; }
tbody tr.clickable:hover td { background:var(--hover); }
.run-id { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; color:var(--text2); }
.chart-card { background:var(--card2); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:18px; }
.chart-card h4 { color:var(--text2); margin:0 0 12px; font-size:13px; }
.chart-box { height:340px; position:relative; }
.loading { padding:60px; text-align:center; color:var(--text3); }
.spinner { display:inline-block; width:24px; height:24px; border:3px solid var(--border); border-top-color:var(--blue); border-radius:50%; animation:spin .8s linear infinite; margin-bottom:12px; }
@keyframes spin { to { transform:rotate(360deg); } }
@media(max-width:768px) { body { padding:12px; } .mini-stats { grid-template-columns:repeat(2,minmax(0,1fr)); } }
/* Cache-coverage heatmap */
.cache-wrap { overflow-x:auto; }
table.heat { border-collapse:separate; border-spacing:0; font-size:11px; }
table.heat th, table.heat td { padding:0; }
table.heat th.lbl, table.heat td.lbl { position:sticky; left:0; z-index:2; background:var(--card); text-align:left; padding:4px 10px; white-space:nowrap; border-bottom:1px solid var(--border); font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
table.heat thead th { position:sticky; top:0; z-index:1; background:var(--card); color:var(--text2); font-weight:600; }
table.heat thead th.lbl { z-index:3; }
table.heat th.yr { text-align:center; border-bottom:1px solid var(--border); padding:4px 0; color:var(--text2); }
table.heat th.mo { text-align:center; color:var(--text3); font-weight:500; padding:2px 0; width:16px; }
.cell { width:15px; height:15px; }
.heat-cell { display:block; width:13px; height:13px; margin:1px auto; border-radius:2px; }
.h-full { background:var(--green); }
.h-partial { background:var(--yellow); }
.h-missing { background:var(--red); }
.h-na { background:#21262d; }
.cache-legend { display:flex; gap:16px; flex-wrap:wrap; align-items:center; margin:0 0 16px; color:var(--text2); font-size:12px; }
.cache-legend .sw { display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-1px; margin-right:5px; }
.cnt-summary { color:var(--text3); font-size:10px; white-space:nowrap; padding-left:8px; }
</style>
</head>
<body>
<div class="container" id="app"></div>
<script>
let chartInstance = null;

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function fmtPct(v) {
  const n = Number(v || 0);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}
function fmtNum(v) {
  return Number(v || 0).toLocaleString();
}
function fmtR(v) {
  if (v === null || v === undefined) return 'n/a';
  const n = Number(v);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + 'R';
}
function fmtDate(v) {
  if (!v) return 'n/a';
  return String(v).replace('T', ' ').slice(0, 16);
}
function cls(v) {
  return Number(v || 0) >= 0 ? 'positive' : 'negative';
}
function pfCls(v) {
  const n = Number(v || 0);
  return n >= 1.3 ? 'positive' : (n >= 1 ? 'neutral' : 'negative');
}
// 4-tier (green/yellow/orange/red) scoring for the permutation-test panel.
// Perm p: lower = better; kill line is p > 0.5.
function pValueCls(p) {
  p = Number(p);
  return p < 0.05 ? 'q-green' : (p < 0.2 ? 'q-yellow' : (p <= 0.5 ? 'q-orange' : 'q-red'));
}
// Pace CI: green if confidently positive (lower>0), red if confidently
// negative (upper<0); straddling zero → yellow if mostly +, orange if mostly −.
function paceCiCls(lo, hi) {
  lo = Number(lo); hi = Number(hi);
  if (lo > 0) return 'q-green';
  if (hi < 0) return 'q-red';
  return (lo + hi) / 2 > 0 ? 'q-yellow' : 'q-orange';
}
// Tail share: lower = better (less outlier-dependent). Red once the top-k
// carry the entire profit (share ≥ 1 or R-without-top-k goes negative).
function tailShareCls(share, without) {
  if (share == null) return 'q-yellow';
  if (Number(without) < 0 || Number(share) >= 1) return 'q-red';
  share = Number(share);
  return share > 0.6 ? 'q-orange' : (share > 0.3 ? 'q-yellow' : 'q-green');
}
// Null mean is a sanity anchor: it should sit near 0 (random signs cancel).
// Color by distance from zero — a large drift flags a suspect series.
function nullMeanCls(v) {
  const x = Math.abs(Number(v || 0));
  return x < 2 ? 'q-green' : (x < 5 ? 'q-yellow' : (x < 10 ? 'q-orange' : 'q-red'));
}
function statusBadge(status) {
  const s = status || 'unknown';
  const c = s === 'completed' ? 'green' : (s === 'failed' ? 'red' : '');
  return `<span class="badge ${c}">${esc(s)}</span>`;
}

// Code-freshness pill: does the run's stored code_signature still match the
// signature the release would get on current code? false => the release/engine
// source changed since this backtest, so it should be re-run.
function codeFreshBadge(row) {
  const stored = row.code_signature ? esc(row.code_signature) : '-';
  if (row.code_fresh === true) {
    return `<span class="badge green" title="Backtest ran on current code (${stored})">🟢 Current</span>`;
  }
  if (row.code_fresh === false) {
    const cur = row.current_signature ? esc(row.current_signature) : '?';
    return `<span class="badge amber" title="Code changed since backtest — re-run. Ran on ${stored}, current is ${cur}">🟠 Stale — re-run</span>`;
  }
  return `<span class="badge" title="No stored code signature for this run (${stored})">⚪ Unknown</span>`;
}

// Funnel disposition + furthest rung reached. Drives the dimming/sort of the
// testset table (active/promoted on top, killed/archived at the bottom).
function dispositionBadge(row) {
  const disp = row.disposition || 'active';
  const stage = row.stage_name ? esc(row.stage_name) : '?';
  const reason = esc(row.lifecycle_reason || '');
  if (disp === 'promoted') {
    return `<span class="badge green" title="Survived OOS — portfolio candidate. ${reason}">★ Promoted · ${stage}</span>`;
  }
  if (disp === 'killed') {
    const at = (row.killed_stage !== null && row.killed_stage !== undefined)
      ? ` @${esc(row.stage_name)}` : '';
    return `<span class="badge red" title="${reason}">✖ Killed${at}</span>`;
  }
  if (disp === 'archived') {
    return `<span class="badge" title="Retired/superseded. ${reason}">▽ Archived</span>`;
  }
  return `<span class="badge" title="Climbing the funnel. ${reason}">● Active · ${stage}</span>`;
}

function runPct(run) {
  const tot = Number(run.total_days || 0);
  if (!tot) return 0;
  return Math.min(100, Math.round(Number(run.completed_days || 0) / tot * 100));
}

// Status pill mapping to the labels requested: Running (X%), Completed, Error.
function runStatusBadge(run) {
  const s = run.status || 'unknown';
  if (s === 'running') return `<span class="badge running">Running (${runPct(run)}%)</span>`;
  if (s === 'completed') return `<span class="badge green">Completed</span>`;
  if (s === 'failed') return `<span class="badge red">Error</span>`;
  if (s === 'completed_with_errors') return `<span class="badge amber">Partial</span>`;
  return `<span class="badge">${esc(s)}</span>`;
}

// Signature of in-flight progress: changes whenever any running run advances
// a day. Used to detect stalls without relying on the client clock.
function runsSignature(rows) {
  return (rows || []).filter(r => r.status === 'running')
    .map(r => r.run_id + ':' + (r.completed_days || 0)).sort().join('|');
}

// Poll the testset endpoint while any run is in progress and refresh ONLY the
// table body (so the comparison checkbox selections and the chart survive).
// Stops polling once no running run has advanced for ~2 min, so an orphaned
// run stuck in 'running' (e.g. a kill -9'd process) can't poll forever.
const RUNS_STALL_LIMIT = 40;  // 40 * 3s ≈ 2 min of no progress
function scheduleRunsPoll(name, rows) {
  if (window.__runsPoll) { clearTimeout(window.__runsPoll); window.__runsPoll = null; }
  if (!(rows || []).some(r => r.status === 'running')) { window.__runsStall = 0; return; }
  const sig = runsSignature(rows);
  if (sig === window.__runsLastSig) {
    window.__runsStall = (window.__runsStall || 0) + 1;
  } else {
    window.__runsStall = 0; window.__runsLastSig = sig;
  }
  if (window.__runsStall >= RUNS_STALL_LIMIT) return;  // stalled — stop polling
  const here = '/testset/' + encodeURIComponent(name);
  window.__runsPoll = setTimeout(async () => {
    if (route() !== here) return;  // navigated away
    try {
      const data = await api('/api/testset?name=' + encodeURIComponent(name));
      const tb = document.getElementById('ts-rows');
      if (!tb || route() !== here) return;  // navigated during the await
      // preserve the user's compare-checkbox selections across the refresh
      const sel = new Set(Array.from(document.querySelectorAll('.compare-chk:checked'))
        .map(cb => cb.getAttribute('data-run-id')));
      window.currentTestsetData = data;  // keep equity_curve fresh for the chart
      tb.innerHTML = (data.backtests || []).slice()
        .sort((a, b) => (a.disposition_rank ?? 9) - (b.disposition_rank ?? 9))
        .map(tsRow).join('');
      tb.querySelectorAll('.compare-chk').forEach(cb => {
        if (sel.has(cb.getAttribute('data-run-id'))) cb.checked = true;
      });
      updateCombinedEquityChart();
      scheduleRunsPoll(name, data.backtests);
    } catch (e) { /* transient; let the next navigation retry */ }
  }, 3000);
}
function parseETToUnix(dtStr) {
  if (!dtStr) return null;
  const s = String(dtStr).replace(' ', 'T').split('.')[0];
  const d = new Date(s + 'Z');
  if (isNaN(d.getTime())) return null;
  try {
    const tzStr = d.toLocaleString('en-US', { timeZone: 'America/New_York' });
    const localStr = d.toLocaleString('en-US', { timeZone: 'UTC' });
    const diffMs = new Date(tzStr).getTime() - new Date(localStr).getTime();
    return (d.getTime() - diffMs) / 1000;
  } catch (e) {
    return d.getTime() / 1000;
  }
}
function filterBarsBetween(bars, startTs, endTs) {
  if (!bars || !bars.length) return [];
  const toUnix = (v, fallback) => v == null ? fallback
    : (typeof v === 'number' ? v : (parseETToUnix(v) || fallback));
  const t0 = toUnix(startTs, bars[0].time);
  const t1 = toUnix(endTs, bars[bars.length - 1].time);
  return bars.filter(b => b.time >= t0 - 60 && b.time <= t1 + 60);
}
function route() { return location.hash.slice(1) || '/'; }
function navigate(path) { history.pushState(null, '', '#' + path); render(); }
window.addEventListener('popstate', render);
async function api(url) {
  const res = await fetch(url);
  return res.json();
}

async function render() {
  try {
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
    if (window.combinedEquityChartInstance) {
      window.combinedEquityChartInstance.destroy();
      window.combinedEquityChartInstance = null;
    }
    if (window.validationChartInstance) {
      window.validationChartInstance.destroy();
      window.validationChartInstance = null;
    }
    if (window.__runsPoll) { clearTimeout(window.__runsPoll); window.__runsPoll = null; }
    window.__runsStall = 0; window.__runsLastSig = null;
    const app = document.getElementById('app');
    const r = route();
    const runMatch = r.match(/^\/run\/(.+)$/);
    if (runMatch) {
      app.innerHTML = loading('Loading backtest');
      const data = await api('/api/run?run_id=' + encodeURIComponent(decodeURIComponent(runMatch[1])));
      if (data.error) { app.innerHTML = error(data.error); return; }
      app.innerHTML = renderRun(data);
      setTimeout(() => drawEquity(data.equity_curve), 50);
      loadValidation(decodeURIComponent(runMatch[1]));
      return;
    }
    if (r.startsWith('/trade/')) {
      const tradeId = decodeURIComponent(r.slice('/trade/'.length));
      app.innerHTML = loading('Loading trade details');
      const data = await api('/api/trade?trade_id=' + encodeURIComponent(tradeId));
      if (data.error) { app.innerHTML = error(data.error); return; }
      app.innerHTML = renderTradePage(data);
      setTimeout(() => renderTradeChart(data), 50);
      return;
    }
    if (r === '/cache' || r.startsWith('/cache?')) {
      const group = new URLSearchParams(r.split('?')[1] || '').get('group') || 'long_lived';
      app.innerHTML = loading('Scanning marketdata cache');
      const data = await api('/api/cache?group=' + encodeURIComponent(group));
      if (data.error) { app.innerHTML = error(data.error); return; }
      app.innerHTML = renderCache(data);
      return;
    }
    if (r.startsWith('/testset/')) {
      const name = decodeURIComponent(r.slice('/testset/'.length));
      app.innerHTML = loading('Loading test set');
      const data = await api('/api/testset?name=' + encodeURIComponent(name));
      if (data.error) { app.innerHTML = error(data.error); return; }
      app.innerHTML = renderTestset(data);
      scheduleRunsPoll(name, data.backtests);
      return;
    }
    app.innerHTML = loading('Loading dashboard');
    const data = await api('/api/testsets');
    app.innerHTML = renderOverview(data);
  } catch (err) {
    document.getElementById('app').innerHTML = `<div class="section" style="color:var(--red); padding: 20px;">
      <h2>JS Error inside render()</h2>
      <pre style="white-space: pre-wrap; font-family: monospace;">${err.stack || err.message || err}</pre>
    </div>`;
  }
}

function loading(text) {
  return `<div class="loading"><div class="spinner"></div><div>${esc(text)}</div></div>`;
}
function error(text) {
  return `<div class="section" style="color:var(--red);">${esc(text)}</div>`;
}

function renderOverview(data) {
  const testsets = data.testsets || [];
  const totalTrades = testsets.reduce((a, t) => a + Number(t.total_trades || 0), 0);
  const totalPnl = testsets.reduce((a, t) => a + Number(t.total_pnl || 0), 0);
  const totalR = testsets.reduce((a, t) => a + Number(t.total_realized_r || 0), 0);
  return `<h1>Strategy Lab</h1>
    <p class="subtitle">${testsets.length} test sets · ${fmtNum(totalTrades)} trades · <span class="${cls(totalPnl)}">${fmtPct(totalPnl)}</span> sum PnL% · <span class="${cls(totalR)}">${totalR >= 0 ? '+' : ''}${totalR.toFixed(2)}R</span> Σ realized R · <a onclick="navigate('/cache');return false;">Cache coverage →</a></p>
    <div class="grid">${testsets.map(renderTestsetCard).join('') || '<div class="section">No test sets found.</div>'}</div>`;
}

function renderTestsetCard(t) {
  const start = t.date_range?.start || 'n/a';
  const end = t.date_range?.end || 'n/a';
  return `<div class="ts-card" onclick="navigate('/testset/${encodeURIComponent(t.name)}')">
    <h3>${esc(t.name)}</h3>
    <div class="meta">
      <span>${esc(start)} → ${esc(end)}</span>
      <span>${fmtNum(t.run_count)} runs</span>
      <span>${fmtNum(t.total_trades)} trades</span>
      <span class="${Number(t.win_rate) >= 50 ? 'positive' : 'negative'}">${Number(t.win_rate || 0).toFixed(1)}% WR</span>
      <span class="${cls(t.total_pnl)}">${fmtPct(t.total_pnl)}</span>
      <span class="${cls(t.total_realized_r)}">${fmtR(t.total_realized_r)}</span>
      <span>Last ${fmtDate(t.last_run)}</span>
    </div>
    <div class="badges">${(t.releases || []).map(r => `<span class="badge">${esc(r)}</span>`).join('')}</div>
  </div>`;
}

// Marketdata cache-coverage heatmap: rows = ticker×timeframe, cols = months.
// Cell color encodes how complete that month is vs the NYSE trading calendar.
function renderCache(data) {
  const months = data.months || [];
  const rows = data.rows || [];
  // Group months by year for a two-tier header (year span + month number).
  const yearSpans = [];
  months.forEach(m => {
    const y = m.slice(0, 4);
    const last = yearSpans[yearSpans.length - 1];
    if (last && last.year === y) last.span++;
    else yearSpans.push({ year: y, span: 1 });
  });
  const yearHdr = yearSpans.map(y =>
    `<th class="yr" colspan="${y.span}">${esc(y.year)}</th>`).join('');
  const moHdr = months.map(m =>
    `<th class="mo">${esc(m.slice(5, 7))}</th>`).join('');

  const groupOpts = (data.groups || [data.group]).map(g =>
    `<option value="${esc(g)}"${g === data.group ? ' selected' : ''}>${esc(g)}</option>`).join('');

  const body = rows.map(r => {
    const cells = (r.cells || []).map(c => {
      const tip = c.status === 'na'
        ? `${esc(r.ticker)} ${esc(r.timeframe)} · ${c.month} · not cached`
        : `${esc(r.ticker)} ${esc(r.timeframe)} · ${c.month} · ${c.present}/${c.expected || '?'} sessions`
          + (c.incomplete ? ` · ${c.incomplete} incomplete` : '');
      return `<td class="cell"><span class="heat-cell h-${c.status}" title="${tip}"></span></td>`;
    }).join('');
    const cnt = r.counts || {};
    const summary = r.total_rows
      ? `${cnt.full || 0}f / ${cnt.partial || 0}p / ${cnt.missing || 0}m`
      : 'none cached';
    const lbl = `${esc(r.ticker)} <span style="color:var(--text3);">${esc(r.timeframe)}</span>`
      + `<span class="cnt-summary">${summary}</span>`;
    return `<tr><td class="lbl">${lbl}</td>${cells}</tr>`;
  }).join('');

  return `<div class="breadcrumb"><a onclick="navigate('/');return false;">Dashboard</a><span class="sep">/</span><span>Cache coverage</span></div>
    <h1>Marketdata Cache Coverage</h1>
    <p class="subtitle">Sample group:
      <select onchange="navigate('/cache?group=' + encodeURIComponent(this.value))" style="background:var(--card2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;">${groupOpts}</select>
      · ${rows.length} ticker×timeframe rows · ${months.length} months · built from cache meta.json (no parquet reads)</p>
    <div class="cache-legend">
      <span><span class="sw h-full"></span>Full — every trading day cached</span>
      <span><span class="sw h-partial"></span>Partial — some days missing / incomplete</span>
      <span><span class="sw h-missing"></span>Missing — in-range month, nothing cached</span>
      <span><span class="sw h-na"></span>n/a — before earliest / never cached</span>
    </div>
    <div class="section flush"><div class="cache-wrap"><table class="heat">
      <thead>
        <tr><th class="lbl" rowspan="2">Ticker · TF</th>${yearHdr}</tr>
        <tr>${moHdr}</tr>
      </thead>
      <tbody>${body || `<tr><td class="lbl">No tickers.</td></tr>`}</tbody>
    </table></div></div>`;
}

// One combined row: live status + progress AND results. A row whose latest
// run has no metrics yet (still running / failed before finishing) shows the
// progress bar and dashes the result columns.
function tsRow(r) {
  const noMetrics = (r.win_rate === null || r.win_rate === undefined);
  const dash = '<span style="color:var(--text3);">—</span>';
  // Dim the graveyard (killed/archived) so live work stands out.
  const terminal = (r.disposition === 'killed' || r.disposition === 'archived');
  const dim = terminal ? ' style="opacity:0.55;"' : '';
  return `<tr class="clickable"${dim} onclick="navigate('/run/${encodeURIComponent(r.run_id)}')">
      <td>${esc(r.release_id)}</td>
      <td>${esc(r.strategy_alias)}</td>
      <td>${dispositionBadge(r)}</td>
      <td>${runStatusBadge(r)}</td>
      <td>${codeFreshBadge(r)}</td>
      <td>${noMetrics ? dash : fmtNum(r.trade_count)}</td>
      <td class="${Number(r.win_rate) >= 50 ? 'positive' : 'negative'}">${noMetrics ? dash : Number(r.win_rate || 0).toFixed(1) + '%'}</td>
      <td class="${pfCls(r.profit_factor)}">${noMetrics ? dash : Number(r.profit_factor || 0).toFixed(2)}</td>
      <td class="${cls(r.total_realized_r)}">${noMetrics ? dash : fmtR(r.total_realized_r)}</td>
      <td class="${r.perm_p == null ? '' : pValueCls(r.perm_p)}">${r.perm_p == null ? dash : Number(r.perm_p).toFixed(3)}</td>
      <td class="${r.top_k_share == null ? '' : tailShareCls(r.top_k_share, r.r_without_top_k)}">${r.top_k_share == null ? dash : (Number(r.top_k_share) * 100).toFixed(0) + '%'}</td>
      <td class="${cls(r.total_pnl_pct)}">${noMetrics ? dash : fmtPct(r.total_pnl_pct)}</td>
      <td class="${cls(r.avg_pnl_pct)}">${noMetrics ? dash : fmtPct(r.avg_pnl_pct)}</td>
      <td>${fmtDate(r.started_at)}</td>
      <td style="text-align: center; vertical-align: middle;" onclick="event.stopPropagation();">
        <input type="checkbox" class="compare-chk" data-run-id="${r.run_id}" style="transform: scale(1.2); cursor: pointer;" onclick="updateCombinedEquityChart();">
      </td>
    </tr>`;
}

function renderTestset(data) {
  window.currentTestsetData = data;
  const rows = data.backtests || [];
  const done = rows.filter(r => (r.win_rate !== null && r.win_rate !== undefined));
  const trades = done.reduce((a, r) => a + Number(r.trade_count || 0), 0);
  const wins = done.reduce((a, r) => a + Number(r.wins || 0), 0);
  const pnl = done.reduce((a, r) => a + Number(r.total_pnl_pct || 0), 0);
  const sumR = done.reduce((a, r) => a + Number(r.total_realized_r || 0), 0);
  const wr = trades ? wins / trades * 100 : 0;
  const running = rows.filter(r => r.status === 'running').length;
  // Live work (promoted/active) on top, graveyard (killed/archived) at the
  // bottom; within a group keep the server's running-first / release-id order.
  const sorted = rows.slice().sort((a, b) =>
    (a.disposition_rank ?? 9) - (b.disposition_rank ?? 9));
  const body = sorted.map(tsRow).join('');
  return `<div class="breadcrumb"><a onclick="navigate('/');return false;">Dashboard</a><span class="sep">/</span><span>${esc(data.testset)}</span></div>
    <h1>${esc(data.testset)}</h1>
    <p class="subtitle">${rows.length} releases${running ? ` · <span style="color:var(--blue);">${running} running</span>` : ''} · ${fmtNum(trades)} trades · <span class="${Number(wr) >= 50 ? 'positive' : 'negative'}">${wr.toFixed(1)}% WR</span> · <span class="${cls(sumR)}">${fmtR(sumR)}</span> · <span class="${cls(pnl)}">${fmtPct(pnl)}</span> PnL%</p>
    <div class="chart-card full" id="combined-equity-card" style="display:none; margin-bottom:20px;">
      <h4 style="color:var(--text2); margin:0 0 12px; font-size:13px;">Cumulative R Comparison</h4>
      <div style="height:340px; position:relative;">
        <canvas id="combined-equity-chart"></canvas>
      </div>
    </div>
    <div class="section flush">
      <div class="table-wrap"><table><thead><tr>
        <th>Release</th><th>Strategy</th><th title="Position on the evaluation funnel. Active/Promoted on top; Killed/Archived dimmed at the bottom.">Funnel</th><th>Status</th><th title="Whether this backtest ran on the current code. Stale = release/engine source changed since the run.">Code</th><th>Trades</th><th>WR</th><th>PF</th><th>Total R</th><th title="Sign-flip permutation p-value on daily R (one-sided). Kill at p > 0.5.">Perm P</th><th title="Share of total R from the top-5 trades. ≥100% (red) = profit is entirely tail-driven.">Top-5</th><th>Total PnL%</th><th>Avg</th><th>Started</th><th style="text-align: center; width: 60px;">Compare</th>
      </tr></thead><tbody id="ts-rows">${body || '<tr><td colspan="15">No runs found.</td></tr>'}</tbody></table></div>
    </div>`;
}

function renderRun(data) {
  const run = data.run;
  const metric = (data.metrics || [])[0] || {};
  const trades = data.trades || [];
  const sessions = data.sessions || [];
  const tradeRows = trades.map(t => `<tr class="clickable" onclick="navigate('/trade/${encodeURIComponent(t.trade_id)}')">
      <td>${esc(t.trade_date)}</td>
      <td>${esc(t.ticker)}</td>
      <td>${esc(t.setup_type)}</td>
      <td>${money(t.entry_price)}</td>
      <td>${money(t.exit_price)}</td>
      <td class="${cls(t.pnl_pct)}">${fmtPct(t.pnl_pct)}</td>
      <td>${Number(t.realized_r || 0).toFixed(2)}</td>
      <td>${esc(t.exit_reason || '-')}</td>
      <td>${fmtDate(t.entry_time)}</td>
      <td>${fmtDate(t.exit_time)}</td>
    </tr>`).join('');
  const sessionRows = sessions.map(s => `<tr>
      <td>${esc(s.trade_date)}</td>
      <td>${statusBadge(s.status)}</td>
      <td>${fmtNum(s.ticker_count)}</td>
      <td>${fmtNum(s.candidate_count)}</td>
      <td>${fmtNum(s.signal_count)}</td>
      <td>${fmtNum(s.trade_count)}</td>
      <td>${esc(s.error || '')}</td>
    </tr>`).join('');
  const periodRows = (rows) => (rows || []).map(p => `<tr>
      <td>${esc(p.period)}</td>
      <td style="text-align:right;">${fmtNum(p.trades)}</td>
      <td style="text-align:right;" class="${cls(p.sum_r)}">${fmtR(p.sum_r)}</td>
      <td style="text-align:right;" class="${cls(p.mean_r)}">${Number(p.mean_r || 0).toFixed(3)}</td>
      <td style="text-align:right;" class="${Number(p.win_rate) >= 50 ? 'positive' : 'negative'}">${Number(p.win_rate || 0).toFixed(1)}%</td>
      <td style="text-align:right;" class="${cls(p.sum_pnl_pct)}">${fmtPct(p.sum_pnl_pct)}</td>
      <td style="text-align:right;" class="${cls(p.cum_r)}">${fmtR(p.cum_r)}</td>
    </tr>`).join('');
  const periodTable = (title, rows) => `<div style="flex:1; min-width:340px;">
      <h4 style="color:var(--text2); margin:0 0 8px; font-size:13px;">${title}</h4>
      <div class="table-wrap"><table><thead><tr>
        <th>Period</th><th style="text-align:right;">Trades</th><th style="text-align:right;">Sum R</th><th style="text-align:right;">Mean R</th><th style="text-align:right;">Win%</th><th style="text-align:right;">PnL%</th><th style="text-align:right;">Cum R</th>
      </tr></thead><tbody>${rows || `<tr><td colspan="7">No trades.</td></tr>`}</tbody></table></div>
    </div>`;
  return `<div class="breadcrumb">
      <a onclick="navigate('/');return false;">Dashboard</a><span class="sep">/</span>
      <a onclick="navigate('/testset/${encodeURIComponent(run.testset || '')}');return false;">${esc(run.testset || 'adhoc')}</a><span class="sep">/</span>
      <span>${esc(run.release_id)}</span>
    </div>
    <h1>${esc(run.release_id)} <span style="font-size:16px;color:var(--text2);font-weight:400;">${esc(run.strategy_alias)} · ${esc(shortRun(run.run_id))}</span></h1>
    <p class="subtitle">${dispositionBadge(run)} · ${statusBadge(run.status)} · Started ${fmtDate(run.started_at)} · Completed ${fmtDate(run.completed_at)} · ${codeFreshBadge(run)}</p>
    <div class="mini-stats">
      <div class="mini-stat"><div class="v ${cls(metric.total_realized_r)}">${fmtR(metric.total_realized_r)}</div><div class="l">Total R (= Acct % @1% risk)</div></div>
      <div class="mini-stat"><div class="v ${cls(metric.avg_realized_r)}">${fmtR(metric.avg_realized_r)}</div><div class="l">Avg R / Trade</div></div>
      <div class="mini-stat"><div class="v ${cls(metric.total_pnl_pct)}">${fmtPct(metric.total_pnl_pct)}</div><div class="l">Total PnL% (unsized)</div></div>
      <div class="mini-stat"><div class="v ${Number(metric.win_rate) >= 50 ? 'positive' : 'negative'}">${Number(metric.win_rate || 0).toFixed(1)}%</div><div class="l">Win Rate</div></div>
      <div class="mini-stat"><div class="v ${pfCls(metric.profit_factor)}">${Number(metric.profit_factor || 0).toFixed(2)}</div><div class="l">Profit Factor</div></div>
      <div class="mini-stat"><div class="v">${fmtNum(metric.trade_count)}${metric.no_fill_count ? ` <span style="font-size:11px;color:var(--text2);">(+${fmtNum(metric.no_fill_count)} no-fill)</span>` : ''}</div><div class="l">Trades</div></div>
      <div class="mini-stat"><div class="v">${Number(run.completed_days || 0)}/${Number(run.total_days || 0)}</div><div class="l">Days</div></div>
      <div class="mini-stat"><div class="v positive">${fmtR(metric.best_trade_r)}</div><div class="l">Best</div></div>
      <div class="mini-stat"><div class="v negative">${fmtR(metric.worst_trade_r)}</div><div class="l">Worst</div></div>
    </div>
    <div class="chart-card"><h4>Model Equity @1% Risk <span style="font-weight:400;color:var(--text2);font-size:12px;">· Max DD ${fmtPct(data.max_drawdown_pct)}</span></h4><div class="chart-box"><canvas id="equityChart"></canvas></div></div>
    <div class="chart-card">
      <h4>Period Breakdown <span style="font-weight:400;color:var(--text2);font-size:12px;">· filled trades · Cum R exposes regime carry</span></h4>
      <div style="display:flex; flex-wrap:wrap; gap:20px;">
        ${periodTable('By Quarter', periodRows(data.quarters))}
        ${periodTable('By Month', periodRows(data.months))}
      </div>
    </div>
    <div class="chart-card" id="validation-card">
      <h4>Permutation Test <span style="font-weight:400;color:var(--text2);font-size:12px;">· sign-flip null on daily R · one-sided</span></h4>
      <div id="validation-stats" class="mini-stats" style="margin-bottom:14px;"></div>
      <div class="chart-box" style="height:300px;"><canvas id="validationChart"></canvas></div>
      <div id="validation-note" style="margin-top:10px;color:var(--text2);font-size:12px;"></div>
    </div>
    <div class="section flush">
      <div style="padding:18px 18px 0;"><h2>Trades (${trades.length})</h2></div>
      <div class="table-wrap"><table><thead><tr>
        <th>Date</th><th>Ticker</th><th>Setup</th><th>Entry</th><th>Exit</th><th>PnL</th><th>R</th><th>Exit Reason</th><th>Entry Time</th><th>Exit Time</th>
      </tr></thead><tbody>${tradeRows || '<tr><td colspan="10">No trades found.</td></tr>'}</tbody></table></div>
    </div>
    <div class="section flush">
      <div style="padding:18px 18px 0;"><h2>Sessions (${sessions.length})</h2></div>
      <div class="table-wrap"><table><thead><tr>
        <th>Date</th><th>Status</th><th>Tickers</th><th>Candidates</th><th>Signals</th><th>Trades</th><th>Error</th>
      </tr></thead><tbody>${sessionRows || '<tr><td colspan="7">No sessions found.</td></tr>'}</tbody></table></div>
    </div>`;
}

function drawEquity(points) {
  const canvas = document.getElementById('equityChart');
  if (!canvas) return;
  const data = points || [];
  chartInstance = new Chart(canvas, {
    type:'line',
    data:{
      labels:data.map(p => p.date),
      datasets:[{
        label:'Model Equity @1% risk (start=100)',
        data:data.map(p => p.equity),
        borderColor:'#58a6ff',
        backgroundColor:'rgba(88,166,255,.1)',
        fill:true,
        tension:.1,
        pointRadius:0,
        borderWidth:2,
        yAxisID:'y'
      },{
        label:'Cumulative R',
        data:data.map(p => p.cum_r),
        borderColor:'#d29922',
        fill:false,
        tension:.1,
        pointRadius:0,
        borderWidth:1.5,
        yAxisID:'y1'
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      plugins:{legend:{labels:{color:'#8b949e'}}},
      scales:{
        x:{ticks:{color:'#6e7681',maxTicksLimit:12},grid:{color:'rgba(48,54,61,.5)'}},
        y:{position:'left',ticks:{color:'#58a6ff'},grid:{color:'rgba(48,54,61,.5)'}},
        y1:{position:'right',ticks:{color:'#d29922'},grid:{drawOnChartArea:false}}
      }
    }
  });
}

async function loadValidation(runId) {
  const card = document.getElementById('validation-card');
  if (!card) return;
  const statsEl = document.getElementById('validation-stats');
  const noteEl = document.getElementById('validation-note');
  statsEl.innerHTML = '<div style="color:var(--text3);padding:8px;">Computing permutation null…</div>';
  let data;
  try {
    data = await api('/api/validation?run_id=' + encodeURIComponent(runId));
  } catch (e) {
    card.style.display = 'none';
    return;
  }
  if (!data || data.error) {
    // No realized_r trades (e.g. all no-fill): hide the panel quietly.
    card.style.display = 'none';
    return;
  }
  // p-value coloring follows the screen-funnel gate: kill at p > 0.5.
  const p = Number(data.p_value);
  const pCls = pValueCls(p);
  const verdict = p < 0.05 ? 'strong edge' : (p < 0.2 ? 'likely edge' : (p <= 0.5 ? 'weak / noise' : 'KILL (p > 0.5)'));
  const pace = data.pace_ci || [0, 0];
  const sharePct = data.top_k_share == null ? 'n/a' : (data.top_k_share * 100).toFixed(0) + '%';
  statsEl.innerHTML = `
    <div class="mini-stat"><div class="v ${cls(data.observed_r)}">${fmtR(data.observed_r)}</div><div class="l">Observed Σ R</div></div>
    <div class="mini-stat"><div class="v ${pCls}">${p.toFixed(4)}</div><div class="l">Perm p (one-sided)</div></div>
    <div class="mini-stat"><div class="v ${pCls}" style="font-size:13px;">${verdict}</div><div class="l">Verdict</div></div>
    <div class="mini-stat"><div class="v ${nullMeanCls(data.null_mean)}">${data.null_mean?.toFixed?.(2) ?? '0'}R</div><div class="l">Null Mean Σ R</div></div>
    <div class="mini-stat"><div class="v ${paceCiCls(pace[0], pace[1])}">${pace[0]}..${pace[1]}</div><div class="l">Pace 95% CI (R/yr)</div></div>
    <div class="mini-stat"><div class="v ${tailShareCls(data.top_k_share, data.r_without_top_k)}">${sharePct}</div><div class="l">Top-${data.top_k} share</div></div>`;
  noteEl.innerHTML = `Null: ${fmtNum(data.iters)} random daily sign-flips · ${fmtNum(data.n_trades)} trades over ${fmtNum(data.n_days)} days · `
    + `p = P(null Σ R ≥ observed). Σ R without top-${data.top_k}: <span class="${cls(data.r_without_top_k)}">${fmtR(data.r_without_top_k)}</span>.`;
  setTimeout(() => drawValidationChart(data), 30);
}

function drawValidationChart(data) {
  const canvas = document.getElementById('validationChart');
  if (!canvas || !data.null_hist) return;
  if (window.validationChartInstance) { window.validationChartInstance.destroy(); window.validationChartInstance = null; }
  const centers = data.null_hist.centers || [];
  const counts = data.null_hist.counts || [];
  const observed = Number(data.observed_r);

  // Inline plugin: dashed line at the observed Σ R + shaded right tail (the
  // p-value region). Observed is mapped onto the category axis by linear
  // interpolation across the evenly-spaced bins; if it sits beyond the null
  // range (the good case — low p) it pins to the right edge.
  const observedMarker = {
    id: 'observedMarker',
    afterDraw(chart) {
      if (!centers.length) return;
      const xs = chart.scales.x, area = chart.chartArea, ctx = chart.ctx;
      const span = centers.length > 1 ? (centers[centers.length - 1] - centers[0]) / (centers.length - 1) : 1;
      let frac = span ? (observed - centers[0]) / span : 0;
      const clamped = frac > centers.length - 1 || frac < 0;
      frac = Math.max(0, Math.min(centers.length - 1, frac));
      const lo = Math.floor(frac), hi = Math.ceil(frac);
      const pLo = xs.getPixelForValue(lo), pHi = xs.getPixelForValue(hi);
      const px = lo === hi ? pLo : pLo + (pHi - pLo) * (frac - lo);
      ctx.save();
      ctx.fillStyle = 'rgba(248,81,73,.12)';
      ctx.fillRect(px, area.top, area.right - px, area.bottom - area.top);
      ctx.strokeStyle = '#f0f6fc'; ctx.lineWidth = 2; ctx.setLineDash([5, 3]);
      ctx.beginPath(); ctx.moveTo(px, area.top); ctx.lineTo(px, area.bottom); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = '#f0f6fc'; ctx.font = '11px ' + getComputedStyle(document.body).fontFamily;
      const right = px > (area.left + area.right) / 2;
      ctx.textAlign = right ? 'right' : 'left';
      const label = 'observed ' + (observed >= 0 ? '+' : '') + observed.toFixed(1) + 'R' + (clamped ? ' →' : '');
      ctx.fillText(label, px + (right ? -6 : 6), area.top + 12);
      ctx.restore();
    }
  };

  window.validationChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: centers.map(c => c.toFixed(1)),
      datasets: [{
        label: 'Permutation null (Σ R)',
        data: counts,
        backgroundColor: 'rgba(88,166,255,.45)',
        borderColor: '#58a6ff',
        borderWidth: 0,
        barPercentage: 1.0,
        categoryPercentage: 1.0,
      }]
    },
    plugins: [observedMarker],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8b949e' } },
        tooltip: { callbacks: { title: items => 'Σ R ≈ ' + items[0].label } }
      },
      scales: {
        x: { ticks: { color: '#6e7681', maxTicksLimit: 12 }, grid: { display: false }, title: { display: true, text: 'Total R under null', color: '#6e7681' } },
        y: { ticks: { color: '#6e7681' }, grid: { color: 'rgba(48,54,61,.5)' }, title: { display: true, text: 'permutations', color: '#6e7681' } }
      }
    }
  });
}

function updateCombinedEquityChart() {
  const checkboxes = document.querySelectorAll('.compare-chk:checked');
  const card = document.getElementById('combined-equity-card');
  const ctx = document.getElementById('combined-equity-chart');
  
  if (!card || !ctx) return;
  
  if (checkboxes.length === 0) {
    card.style.display = 'none';
    if (window.combinedEquityChartInstance) {
      window.combinedEquityChartInstance.destroy();
      window.combinedEquityChartInstance = null;
    }
    return;
  }
  
  const selectedRunIds = [];
  checkboxes.forEach(cb => {
    selectedRunIds.push(cb.getAttribute('data-run-id'));
  });
  
  const testsetData = window.currentTestsetData;
  if (!testsetData || !testsetData.backtests) return;
  
  const selectedBacktests = testsetData.backtests.filter(b => selectedRunIds.includes(b.run_id));
  
  const dateSet = new Set();
  selectedBacktests.forEach(b => {
    if (b.equity_curve) {
      b.equity_curve.forEach(p => {
        if (p.date) dateSet.add(p.date);
      });
    }
  });
  
  const sortedDates = Array.from(dateSet).sort();
  if (sortedDates.length === 0) {
    card.style.display = 'none';
    return;
  }
  
  card.style.display = 'block';
  
  const datasets = selectedBacktests.map((b, index) => {
    const curveMap = new Map();
    if (b.equity_curve) {
      b.equity_curve.forEach(p => {
        curveMap.set(p.date, p.cum_r ?? p.pnl);
      });
    }

    let currentPnL = 0;
    const alignedData = sortedDates.map(d => {
      if (curveMap.has(d)) {
        currentPnL = curveMap.get(d);
      }
      return currentPnL;
    });
    
    const hue = (index * 137.5) % 360;
    const color = `hsl(${hue}, 75%, 60%)`;
    
    return {
      label: `${b.release_id.toUpperCase()} (${b.strategy_alias})`,
      data: alignedData,
      borderColor: color,
      backgroundColor: 'transparent',
      fill: false,
      tension: 0.1,
      pointRadius: 0,
      pointHoverRadius: 4,
      borderWidth: 2
    };
  });
  
  if (window.combinedEquityChartInstance) {
    window.combinedEquityChartInstance.destroy();
  }
  
  window.combinedEquityChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: sortedDates,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#8b949e',
            font: {
              size: 11
            }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          ticks: {
            color: '#6e7681',
            maxTicksLimit: 10
          },
          grid: {
            color: 'rgba(48,54,61,0.5)'
          }
        },
        y: {
          ticks: {
            color: '#6e7681',
            callback: function(value) {
              return (value >= 0 ? '+' : '') + value.toFixed(2) + 'R';
            }
          },
          grid: {
            color: 'rgba(48,54,61,0.5)'
          }
        }
      }
    }
  });
}


function renderTradePage(t) {
  const pnlCls = Number(t.pnl_pct)>=0?'positive':'negative';
  const fields = [
    {l:'Ticker', v:t.ticker}, {l:'Date', v:t.trade_date},
    {l:'Setup Type', v:t.setup_type}, {l:'Exit Reason', v:t.exit_reason || '-'},
    {l:'Entry Price', v:'$'+Number(t.entry_price).toFixed(2)}, {l:'Exit Price', v:'$'+Number(t.exit_price).toFixed(2)},
    {l:'PnL %', v:'<span class="'+pnlCls+'">'+fmtPct(t.pnl_pct)+'</span>'},
    {l:'Gross PnL %', v:'<span class="'+pnlCls+'">'+fmtPct(t.gross_pnl_pct)+'</span>'},
    {l:'Direction', v:t.direction||'long'},
    {l:'Release ID', v:t.release_id}, {l:'Strategy Alias', v:t.strategy_alias},
    {l:'Engine', v:t.engine_version || '-'},
    {l:'MFE %', v:t.mfe_pct?fmtPct(t.mfe_pct):'-'},
    {l:'MAE %', v:t.mae_pct?fmtPct(t.mae_pct):'-'},
    {l:'Fees %', v:t.fees_pct?Number(t.fees_pct).toFixed(4):'-'},
    {l:'Slippage %', v:t.slippage_pct?Number(t.slippage_pct).toFixed(4):'-'},
    {l:'Signal Trigger', v:t.signal_entry_trigger?'$'+Number(t.signal_entry_trigger).toFixed(2):'-'},
    {l:'Signal Stop', v:t.signal_stop_price?'$'+Number(t.signal_stop_price).toFixed(2):'-'},
    {l:'Signal Target', v:t.signal_target_price?'$'+Number(t.signal_target_price).toFixed(2):'-'},
    {l:'Signal Time', v:t.signal_time_et || (t.signal_time?fmtDate(t.signal_time):'-')},
    {l:'Entry Time', v:t.entry_time_et || (t.entry_time?fmtDate(t.entry_time):'-')},
    {l:'Exit Time', v:t.exit_time_et || (t.exit_time?fmtDate(t.exit_time):'-')},
    {l:'Trade ID', v:t.trade_id||'-'},
    {l:'Session ID', v:t.session_id},
  ];
  const grid = fields.map(f=>
    `<div class="trade-field" style="display:flex; justify-content:space-between; padding:8px 12px; background:var(--card2); border-radius:6px; margin-bottom:8px;"><span class="label" style="color:var(--text2); font-size:12px;">${f.l}</span><span class="value" style="font-weight:600;">${f.v}</span></div>`
  ).join('');
  return `<div class="breadcrumb">
    <a onclick="navigate('/');return false;">Dashboard</a>
    <span class="sep">/</span>
    <a onclick="navigate('/testset/${encodeURIComponent(t.testset||'')}');return false;">${t.testset||'Test Set'}</a>
    <span class="sep">/</span>
    <a onclick="navigate('/run/${encodeURIComponent(t.run_id)}');return false;">${t.release_id}</a>
    <span class="sep">/</span>
    <span>${t.ticker} · ${t.trade_date}</span>
  </div>
  <h1>${t.ticker} <span style="font-size:16px;font-weight:400;color:var(--text2);">${t.trade_date} · ${t.setup_type}</span></h1>
  <p class="subtitle">Trade ID: ${t.trade_id}</p>
  <div class="chart-card full" style="margin-bottom:16px; background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px;">
    <h4>Intraday Chart — ${t.ticker} on ${t.trade_date}</h4>
    <div class="tv-chart-container" id="tvChart" style="width:100%; height:500px; border-radius:8px; overflow:hidden; background:#1c2333; margin-top:12px;"></div>
  </div>
  <div class="chart-card full" style="background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px;">
    <h4>Trade Details</h4>
    <div class="trade-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px;">${grid}</div>`;
}

// Multi-day (swing) per-trade chart: DAILY candles over a ~60-trading-day lead-in
// (the trend that drove selection) + the hold + a short tail, with a 50-day SMA and
// the hold window bracketed by the entry price line. Date axis (no intraday HH:MM).
function renderDailyTradeChart(container, t) {
  const candles = t.bars.map(b => ({
    time: b.time, open: b.open, high: b.high, low: b.low, close: b.close,
  }));
  const chart = LightweightCharts.createChart(container, {
    layout: { textColor: '#8b949e', background: { type: 'solid', color: '#1c2333' } },
    grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    timeScale: { timeVisible: false, secondsVisible: false, borderColor: '#30363d' },
    rightPriceScale: { borderColor: '#30363d' },
  });
  const candleSeries = chart.addCandlestickSeries({
    upColor: '#3fb950', downColor: '#f85149',
    borderDownColor: '#f85149', borderUpColor: '#3fb950',
    wickDownColor: '#f85149', wickUpColor: '#3fb950',
    lastValueVisible: false, priceLineVisible: false,
  });
  candleSeries.setData(candles);

  // 50-day SMA (trend context)
  if (t.sma50 && t.sma50.length) {
    chart.addLineSeries({
      color: '#d29922', lineWidth: 1.5, title: '50d SMA',
      lastValueVisible: false, priceLineVisible: false,
    }).setData(t.sma50);
  }

  // Entry price line drawn ONLY across the hold (entry_date → exit_date) to bracket it
  const entryPrice = Number(t.entry_price);
  const eS = t.entry_date_str, xS = t.exit_date_str;
  if (entryPrice > 0 && eS && xS) {
    const holdBars = t.bars.filter(b => b.time >= eS && b.time <= xS)
                           .map(b => ({ time: b.time, value: entryPrice }));
    if (holdBars.length) {
      chart.addLineSeries({
        color: '#3fb950', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'Entry $' + entryPrice.toFixed(2),
        lastValueVisible: false, priceLineVisible: false,
      }).setData(holdBars);
    }
  }

  // Markers on the entry and exit days
  const markers = [];
  if (eS) markers.push({ time: eS, position: 'belowBar', color: '#3fb950',
                         shape: 'arrowUp', text: 'Entry $' + entryPrice.toFixed(2) });
  const exitPrice = Number(t.exit_price);
  if (xS) markers.push({ time: xS, position: 'aboveBar', color: '#f85149',
                         shape: 'arrowDown', text: 'Exit $' + (exitPrice > 0 ? exitPrice.toFixed(2) : '') });
  if (markers.length) candleSeries.setMarkers(markers);

  chart.timeScale().fitContent();
}


function renderTradeChart(t) {
  const container = document.getElementById('tvChart');
  try {
    if (!container || !t.bars || !t.bars.length) {
      if (container) container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3);">No chart data available for this trade</div>';
      return;
    }

    // Multi-day (swing) trades: daily bars + 50d SMA, date axis (see below).
    if (t.chart_mode === 'daily') { renderDailyTradeChart(container, t); return; }

    // Prefer server-computed epochs: DB timestamp strings are in the
    // server machine's timezone, NOT ET — parsing them as ET shifts
    // markers off the chart (they then clamp to the first bar).
    const entryUnix = t.entry_time_unix || parseETToUnix(t.entry_time);
    const exitUnix = t.exit_time_unix || parseETToUnix(t.exit_time);

    let windowStart = null, windowEnd = null;
    if (entryUnix) windowStart = entryUnix - 3600; // 1 hour before entry
    if (exitUnix) {
      windowEnd = exitUnix + 3600; // 1 hour after exit
    } else if (entryUnix) {
      windowEnd = entryUnix + 7200; // fallback to 2 hours after entry
    }

    let visibleBars = t.bars;
    if (windowStart) {
      visibleBars = t.bars.filter(b => b.time >= windowStart);
    }
    if (windowEnd) {
      visibleBars = visibleBars.filter(b => b.time <= windowEnd);
    }
    if (!visibleBars.length) visibleBars = t.bars;

    const chartData = visibleBars.map(b => ({
      time: b.time, open: b.open, high: b.high, low: b.low, close: b.close,
    }));

    const chart = LightweightCharts.createChart(container, {
      layout: { textColor: '#8b949e', background: { type: 'solid', color: '#1c2333' } },
      grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      timeScale: {
        timeVisible: true, secondsVisible: false,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          return d.toLocaleString('en-US', {
            timeZone: 'America/New_York',
            hour: '2-digit', minute: '2-digit',
            hour12: false,
          });
        },
      },
      rightPriceScale: { borderColor: '#30363d' },
      localization: {
        timeFormatter: (time) => {
          const d = new Date(time * 1000);
          return d.toLocaleString('en-US', {
            timeZone: 'America/New_York',
            hour: '2-digit', minute: '2-digit',
            hour12: false,
          });
        },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#3fb950', downColor: '#f85149',
      borderDownColor: '#f85149', borderUpColor: '#3fb950',
      wickDownColor: '#f85149', wickUpColor: '#3fb950',
      lastValueVisible: false,
      priceLineVisible: false,
    });
    candleSeries.setData(chartData);

    // Entry price line
    const entryPrice = Number(t.entry_price);
    if (entryPrice > 0) {
      chart.addLineSeries({
        color: '#3fb950', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'Entry $' + entryPrice.toFixed(2),
      }).setData(visibleBars.map(b => ({ time: b.time, value: entryPrice })));
    }

    // VWAP line
    if (t.vwap && t.vwap.length) {
      const vwapVisible = t.vwap.filter(p => {
        const t0 = windowStart || visibleBars[0]?.time;
        const t1 = windowEnd || visibleBars[visibleBars.length-1]?.time;
        return p.time >= t0 && p.time <= t1;
      });
      if (vwapVisible.length) {
        chart.addLineSeries({
          color: '#58a6ff', lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Solid,
          title: 'VWAP',
          lastValueVisible: false, priceLineVisible: false,
        }).setData(vwapVisible);
      }
    }

    // Stop price line
    const stopPrice = Number(t.signal_stop_price);
    if (stopPrice > 0) {
      const stopBars = filterBarsBetween(visibleBars, entryUnix, exitUnix);
      if (stopBars.length) {
        chart.addLineSeries({
          color: '#f85149', lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Solid,
          title: 'Stop $' + stopPrice.toFixed(2),
          lastValueVisible: false, priceLineVisible: false,
        }).setData(stopBars.map(b => ({ time: b.time, value: stopPrice })));
      }
    }

    // Target price line
    const targetPrice = Number(t.signal_target_price);
    if (targetPrice > 0 && targetPrice < 999000) {
      const targetBars = filterBarsBetween(visibleBars, entryUnix, exitUnix);
      if (targetBars.length) {
        chart.addLineSeries({
          color: '#3fb950', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted,
          title: 'Target $' + targetPrice.toFixed(2),
          lastValueVisible: false, priceLineVisible: false,
        }).setData(targetBars.map(b => ({ time: b.time, value: targetPrice })));
      }
    }

    // Exit price line
    const exitPrice = Number(t.exit_price);
    if (exitPrice > 0) {
      chart.addLineSeries({
        color: '#f85149', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'Exit $' + exitPrice.toFixed(2),
      }).setData(visibleBars.map(b => ({ time: b.time, value: exitPrice })));
    }

    // Markers
    const markers = [];
    if (entryUnix) {
      markers.push({
        time: entryUnix, position: 'belowBar', color: '#3fb950', shape: 'arrowUp',
        text: 'Entry $' + entryPrice.toFixed(2),
      });
    }
    if (exitUnix) {
      markers.push({
        time: exitUnix, position: 'aboveBar', color: '#f85149', shape: 'arrowDown',
        text: 'Exit $' + exitPrice.toFixed(2),
      });
    }
    if (markers.length) candleSeries.setMarkers(markers);

    chart.timeScale().fitContent();
  } catch (err) {
    if (container) {
      container.innerHTML = `<div style="padding:40px;color:var(--red);font-family:monospace;white-space:pre-wrap;">Chart Render Error: ${err.stack || err.message || err}</div>`;
    }
  }
}


function shortRun(id) {
  const s = String(id || '');
  if (s.length <= 24) return s;
  return s.slice(0, 16) + '…' + s.slice(-6);
}
function money(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
  return '$' + Number(v).toFixed(2);
}

render();
</script>
</body>
</html>
"""


def kill_process_on_port(port: int) -> None:
    import subprocess
    import os
    import signal
    import time
    try:
        # Get PIDs using the port
        out = subprocess.check_output(["lsof", "-t", f"-itcp:{port}"], text=True)
        pids = [int(p.strip()) for p in out.strip().split("\n") if p.strip()]
        for pid in pids:
            if pid == os.getpid():
                continue
            print(f"Port {port} is in use. Killing process {pid}...", flush=True)
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                continue

            # Poll for process termination
            for _ in range(20):
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
                time.sleep(0.1)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(0.2)
                except OSError:
                    pass
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Start strategy_lab dashboard")
    parser.add_argument("--port", type=int, default=8890)
    args = parser.parse_args()
    init_db()

    try:
        server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    except OSError as e:
        # Errno 48 is 'Address already in use' on macOS / Unix
        if e.errno == 48:
            kill_process_on_port(args.port)
            server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
        else:
            raise

    print(f"Strategy Lab dashboard: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
