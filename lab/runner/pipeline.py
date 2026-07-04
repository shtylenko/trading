from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import traceback
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from trading.lab import ENGINE_VERSION
from trading.lab.core.execution import (
    simulate_long_breakout,
    simulate_pullback_limit_long,
    simulate_short_breakout,
)
from trading.lab.core.models import ExecutionConfig, StrategyContext, SimulatedTrade
from trading.lab.data.market_data import (
    fetch_daily_context,
    fetch_daily_range,
    fetch_intraday_day,
    fetch_intraday_range,
)
from trading.lab.data.testsets import DateRange, TestSet, load_testset
from trading.lab.data.universes import load_universe_tickers
from trading.lab.storage.duckdb import connect, init_db
from trading.lab.strategies import get_release_class


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, default=str)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trading_days(start: date, end: date) -> list[date]:
    try:
        from trading.marketdata.calendar import trading_days_in_range

        return list(trading_days_in_range(start, end))
    except Exception as exc:
        import logging

        logging.getLogger("strategy_lab.runner.pipeline").warning(
            "Exchange calendar unavailable (%s) — falling back to weekday "
            "enumeration; holidays will be treated as trading days",
            exc,
        )
        days = []
        cur = start
        from datetime import timedelta

        while cur <= end:
            if cur.weekday() < 5:
                days.append(cur)
            cur += timedelta(days=1)
        return days


# Engine modules whose changes alter simulation semantics for ALL releases.
# They are folded into every code signature so two runs with the same
# signature are actually comparable (a release file alone is not enough —
# e.g. a change to the fill simulator changes results without touching any
# release module).
_ENGINE_SIGNATURE_MODULES = [
    "trading.lab.core.execution",
    "trading.lab.core.models",
    "trading.lab.core.metrics",
    "trading.lab.core.time_utils",
    "trading.lab.research.filters",
    "trading.lab.research.signal_helpers",
    "trading.lab.runner.pipeline",
]


def compute_code_signature(release_id: str) -> str:
    release_cls = get_release_class(release_id)
    digest = hashlib.sha256()
    module_names = [release_cls.__module__, *_ENGINE_SIGNATURE_MODULES]
    # include shared per-strategy helpers living next to the release module.
    # `variants.py` defines the parametrized base for whole batches (d02-d10,
    # o04-o09, f02-f05), so editing it changes those releases' semantics; it
    # MUST be in the signature or those runs look falsely comparable.
    pkg = release_cls.__module__.rsplit(".", 1)[0]
    module_names.append(f"{pkg}.common")
    module_names.append(f"{pkg}.variants")
    seen = set()
    for name in module_names:
        if name in seen:
            continue
        seen.add(name)
        try:
            module = __import__(name, fromlist=["__file__"])
        except ImportError:
            continue
        path = Path(module.__file__ or "")
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    # Release-declared non-source inputs (binary model artifacts, and any
    # runtime-selected execution mode). A release that ranks with an ML model
    # in one run and with an RV fallback in another executed a DIFFERENT
    # strategy, so its signature must differ — otherwise the two runs are
    # wrongly treated as the same immutable experiment.
    try:
        extra = release_cls.signature_inputs()
    except Exception as exc:  # never let signature hooks break a run
        import logging

        logging.getLogger("strategy_lab.runner.pipeline").warning(
            "signature_inputs() failed for %s (%s); signature omits artifact identity",
            release_id, exc,
        )
        extra = []
    for label, payload in extra:
        digest.update(str(label).encode())
        digest.update(payload if isinstance(payload, bytes) else str(payload).encode())
    digest.update(ENGINE_VERSION.encode())
    return digest.hexdigest()[:16]


def current_code_signature(release_id: str) -> str:
    """Signature the NEXT run of this release would receive.

    Compare against a stored ``runs.code_signature`` to detect that the
    release/engine source changed after a backtest was recorded — i.e. the
    backtest is stale and should be re-run on current code.
    """
    return compute_code_signature(release_id)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds >= 3600:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
    if seconds >= 60:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{seconds:.1f}s"


def _is_connection_failure(exc: Exception) -> bool:
    """True when a prefetch failure is a network outage, not a data problem.

    The marketdata retry wrapper raises ConnectionTimeoutError after
    exhausting its in-call retries; anything else connection-shaped is
    classified by the shared heuristic.
    """
    from trading.marketdata.errors import ConnectionTimeoutError
    from trading.marketdata.retry import is_connection_error

    if isinstance(exc, ConnectionTimeoutError):
        return True
    return is_connection_error(exc)


def _wait_for_connectivity(log, host: str = "data.alpaca.markets", port: int = 443) -> None:
    """Block until the data provider is reachable again (probe every 15s)."""
    import socket
    import time

    attempt = 0
    while True:
        try:
            with socket.create_connection((host, port), timeout=5):
                if attempt:
                    log.info("Connectivity to %s restored after %d probes", host, attempt)
                return
        except OSError:
            attempt += 1
            if attempt == 1 or attempt % 20 == 0:
                log.warning(
                    "Waiting for connectivity to %s (probe %d, retrying every 15s)",
                    host, attempt,
                )
            time.sleep(15)


def _prefetch_testset_data(
    release,
    testset: TestSet,
    trading_days: list[date],
    force_data: bool = False,
    max_workers: int = 8,
) -> None:
    """Bulk-prefetch market data for the whole testset date range.

    The per-day loop fetches one ticker-day per provider request, which for
    a broad universe means ~100k sequential HTTP round trips per run. One
    ranged request per ticker per timeframe (parallelized across tickers)
    populates the same Parquet cache, so the day loop becomes cache-only.

    Tickers that fail on connection errors (internet/provider outage) are
    re-queued and retried in fresh rounds after connectivity returns — they
    are never skipped; if the outage outlasts ``max_rounds`` the run aborts
    (resumable) rather than continuing with data holes. Only non-connection
    failures (ticker-specific data/provider errors) are logged and left for
    the day loop to surface.
    """
    import concurrent.futures as cf
    import logging
    import sys

    if not trading_days:
        return
    start, end = min(trading_days), max(trading_days)

    print(
        f"Resolving universe '{getattr(testset, 'universe', None) or 'tickers'}' "
        f"across {len(trading_days)} trading days...",
        flush=True,
    )
    tickers: set[str] = set()
    for d in trading_days:
        tickers.update(_resolve_tickers(testset, d, None))
    tickers.discard("SPY")
    if not tickers:
        return

    hist_lookback = getattr(release, "historical_5m_lookback_days", 0)
    five_min_start = start - timedelta(days=hist_lookback * 3) if hist_lookback else start
    daily_start = start - timedelta(days=41)  # fetch_daily_context lookback_days=40
    requires_rth_1m = getattr(release, "requires_rth_1m", False)
    requires_ext_1m = getattr(release, "requires_extended_1m", False)

    log = logging.getLogger("strategy_lab.runner.pipeline")
    log.info(
        "Prefetching %s..%s for %d tickers (%d workers)",
        start.isoformat(), end.isoformat(), len(tickers), max_workers,
    )
    print(
        f"Prefetching {start.isoformat()}..{end.isoformat()} for "
        f"{len(tickers)} tickers ({max_workers} workers)",
        flush=True,
    )

    try:
        from trading.marketdata.storage import sweep_tmp_files

        sweep_tmp_files()
    except Exception:
        pass  # best-effort hygiene; never block a run on it

    # SPY first on the main thread; this also triggers one-time provider
    # registration before worker threads race for it.
    print("Fetching SPY context (5min/daily/1min for the full range)...", flush=True)
    fetch_intraday_range("SPY", start, end, "5min", "rth", force=force_data)
    fetch_daily_range("SPY", daily_start, end, force=force_data)
    if requires_rth_1m:
        fetch_intraday_range("SPY", start, end, "1min", "rth", force=force_data)
    print("SPY done; starting parallel ticker prefetch...", flush=True)

    def _prefetch_ticker(ticker: str) -> None:
        fetch_intraday_range(ticker, five_min_start, end, "5min", "rth", force=force_data)
        fetch_daily_range(ticker, daily_start, end, force=force_data)
        if requires_rth_1m:
            fetch_intraday_range(ticker, start, end, "1min", "rth", force=force_data)
        if requires_ext_1m:
            fetch_intraday_range(ticker, start, end, "1min", "extended", force=force_data)

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    pending = sorted(tickers)
    failed_data: list[str] = []
    max_rounds = 20
    for round_no in range(1, max_rounds + 1):
        retry_conn: list[str] = []
        done = 0
        round_t0 = time.time()
        round_part = f" (round {round_no})" if round_no > 1 else ""
        bar = None
        # tqdm draws on stderr: gate on *stderr* so `... | tee log` keeps the
        # live bar on screen while stdout's plain lines go to the log.
        if tqdm is not None and sys.stderr.isatty():
            bar = tqdm(
                total=len(pending),
                desc=f"Prefetching market data{round_part}",
                unit="ticker",
                dynamic_ncols=True,
            )
        with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_prefetch_ticker, t): t for t in pending}
            for fut in cf.as_completed(futures):
                try:
                    fut.result()
                except Exception as exc:
                    if _is_connection_failure(exc):
                        retry_conn.append(futures[fut])
                    else:
                        failed_data.append(futures[fut])
                        log.warning("Prefetch failed for %s: %s", futures[fut], exc)
                done += 1
                if bar is not None:
                    if retry_conn:
                        bar.set_postfix_str(f"{len(retry_conn)} to retry")
                    bar.update(1)
                    continue
                elapsed = time.time() - round_t0
                rate = done / elapsed * 60 if elapsed > 0 else 0.0
                rem = (len(pending) - done) / (rate / 60) if rate > 0 else 0.0
                eta_part = (
                    f" | {rate:.1f} tickers/min | ETA {int(rem // 3600)}h{int((rem % 3600) // 60):02d}m"
                    if done >= 10
                    else ""
                )
                progress = (
                    f"Prefetching market data{round_part}: {done}/{len(pending)} tickers"
                    f"{f' ({len(retry_conn)} to retry)' if retry_conn else ''}{eta_part}"
                )
                if sys.stdout.isatty():
                    if done % 10 == 0 or done == len(pending):
                        sys.stdout.write(f"\r{progress}   ")
                        sys.stdout.flush()
                elif done % 25 == 0 or done == len(pending):
                    # piped/teed runs would otherwise be silent for hours
                    print(progress, flush=True)
        if bar is not None:
            bar.close()
        elif sys.stdout.isatty():
            print()
        if not retry_conn:
            break
        log.warning(
            "Prefetch round %d: %d tickers hit connection failures; "
            "waiting for connectivity, then retrying: %s",
            round_no, len(retry_conn), retry_conn[:20],
        )
        _wait_for_connectivity(log)
        pending = retry_conn
    else:
        raise RuntimeError(
            f"Prefetch aborted: {len(pending)} tickers still failing on "
            f"connection errors after {max_rounds} rounds: {pending[:20]}"
        )
    if failed_data:
        log.warning(
            "Prefetch finished with %d tickers failing on non-connection "
            "errors (left for the day loop): %s",
            len(failed_data), failed_data[:20],
        )


def run_backtest_for_testset(
    release_id: str,
    testset_name: str,
    execution_config: ExecutionConfig | None = None,
    candidate_limit: int | None = None,
    force_data: bool = False,
    resume_run_id: str | None = None,
    max_failed_sessions: int = 10,
    prefetch: bool = True,
    prefetch_workers: int = 8,
) -> str:
    """Run (or resume) a multi-day backtest for a named testset.

    Individual session failures are isolated: the failed date is recorded on
    the session row and the run continues, aborting only after
    ``max_failed_sessions`` failures. Pass ``resume_run_id`` to continue an
    interrupted run — dates with completed sessions are skipped.
    """
    import sys
    import time

    testset = load_testset(testset_name)
    ranges = testset.date_ranges
    if not ranges:
        raise ValueError(f"TestSet '{testset_name}' has no date_ranges")

    done_dates: set[date] = set()
    if resume_run_id is not None:
        init_db()
        with connect() as conn:
            row = conn.execute(
                "SELECT release_id, testset, status FROM runs WHERE run_id = ?",
                [resume_run_id],
            ).fetchone()
            if row is None:
                raise ValueError(f"Cannot resume: run '{resume_run_id}' not found")
            if row[0] != release_id or row[1] != testset_name:
                raise ValueError(
                    f"Cannot resume run '{resume_run_id}': it is for "
                    f"release={row[0]} testset={row[1]}, not {release_id}/{testset_name}"
                )
            done_dates = {
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT trade_date FROM sessions WHERE run_id = ? AND status = 'completed'",
                    [resume_run_id],
                ).fetchall()
            }
            conn.execute(
                "UPDATE runs SET status = 'running', completed_at = NULL WHERE run_id = ?",
                [resume_run_id],
            )
        run_id = resume_run_id
    else:
        run_id = _create_run(release_id, testset, ranges, execution_config or ExecutionConfig())

    release_cls = get_release_class(release_id)
    release = release_cls()

    # Pre-calculate trading days to determine total_days
    all_trading_days = []
    for dr in ranges:
        for trade_date in _trading_days(dr.start, dr.end):
            all_trading_days.append((trade_date, dr.label))
    total_days = len(all_trading_days)

    print(
        f"Run {run_id}: {release_id} on '{testset_name}', "
        f"{total_days} trading days"
        f"{f' ({len(done_dates)} already completed, resuming)' if done_dates else ''}",
        flush=True,
    )

    if prefetch:
        pending_days = [d for d, _ in all_trading_days if d not in done_dates]
        _prefetch_testset_data(
            release,
            testset,
            pending_days,
            force_data=force_data,
            max_workers=prefetch_workers,
        )

    grid_start_time = time.time()
    last_run_duration = None
    completed = 0

    def _draw_progress(is_before: bool, current_dt: date, range_label: str | None = None):
        if total_days <= 1:
            return
        if not sys.stdout.isatty():
            # piped/teed runs: one plain line per completed day
            if is_before:
                return
            elapsed = time.time() - grid_start_time
            eta = (total_days - completed) * (elapsed / completed) if completed else 0.0
            print(
                f"Simulated {current_dt.isoformat()} | {completed}/{total_days} days "
                f"({completed / total_days * 100:.0f}%) | last {format_duration(last_run_duration)}"
                f" | ETA {int(eta // 3600)}h{int((eta % 3600) // 60):02d}m",
                flush=True,
            )
            return
        elapsed = time.time() - grid_start_time
        if completed > 0:
            avg = elapsed / completed
            rem = total_days - completed
            eta = rem * avg
        else:
            avg = 0.0
            eta = 0.0

        if eta >= 3600:
            eta_str = f"{int(eta // 3600)}h {int((eta % 3600) // 60)}m"
        elif eta >= 60:
            eta_str = f"{int(eta // 60)}m {int(eta % 60)}s"
        else:
            eta_str = f"{int(eta)}s" if eta > 0 else "?"

        avg_str = format_duration(avg) if avg > 0 else "?"

        bar_width = 30
        filled = int(round(bar_width * completed / total_days))
        bar = '█' * filled + '░' * (bar_width - filled)
        pct = (completed / total_days) * 100

        range_part = f"[{range_label}] " if range_label else ""
        if is_before:
            label = f"Simulating: {current_dt.isoformat()} ({release_id.upper()})"
            eta_display = eta_str
        else:
            label = f"{current_dt.isoformat()} ({release_id.upper()})"
            eta_display = "Done" if completed >= total_days else eta_str

        sys.stdout.write(
            f"\rProgress: [{bar}] {pct:.1f}% ({completed}/{total_days}) | "
            f"TestSet:{testset_name} | Release: {release_id.upper()} ({release.strategy_alias}) | {range_part}{label} | "
            f"Last: {format_duration(last_run_duration)} | Avg: {avg_str} | ETA: {eta_display}   "
        )
        sys.stdout.flush()

    import logging

    log = logging.getLogger("strategy_lab.runner.pipeline")
    failed_dates: list[date] = []
    try:
        for trade_date, range_label in all_trading_days:
            if trade_date in done_dates:
                completed += 1
                continue
            session_start = time.time()
            _draw_progress(True, trade_date, range_label)

            try:
                run_backtest_for_date(
                    release_id=release_id,
                    trade_date=trade_date,
                    run_id=run_id,
                    testset=testset,
                    execution_config=execution_config,
                    candidate_limit=candidate_limit,
                    force_data=force_data,
                )
            except Exception as exc:
                # Session-level isolation: the failure is already recorded on
                # the session row by run_backtest_for_date. Keep going unless
                # failures pile up (systemic problem, e.g. network outage).
                failed_dates.append(trade_date)
                log.warning("Session %s failed (%d/%d allowed): %s",
                            trade_date.isoformat(), len(failed_dates), max_failed_sessions, exc)
                if len(failed_dates) > max_failed_sessions:
                    raise RuntimeError(
                        f"Aborting run: {len(failed_dates)} sessions failed "
                        f"(> {max_failed_sessions}). Failed dates: "
                        f"{[d.isoformat() for d in failed_dates]}"
                    ) from exc
                continue

            last_run_duration = time.time() - session_start
            completed += 1
            with connect() as conn:
                # derive progress from the sessions table rather than a local
                # counter so crashes/resumes can't make it drift
                conn.execute(
                    """
                    UPDATE runs SET completed_days = (
                        SELECT COUNT(DISTINCT trade_date) FROM sessions
                        WHERE run_id = ? AND status = 'completed'
                    ) WHERE run_id = ?
                    """,
                    [run_id, run_id],
                )
            _draw_progress(False, trade_date, range_label)

        if total_days > 1 and sys.stdout.isatty():
            print()
        if failed_dates:
            _finalize_run(
                run_id,
                "completed_with_errors",
                f"failed sessions: {[d.isoformat() for d in failed_dates]}",
            )
        else:
            # Pass "" (not None) so a resumed run's stale failure traceback
            # in notes is cleared rather than COALESCE-preserved.
            _finalize_run(run_id, "completed", "")
    except Exception:
        if total_days > 1 and sys.stdout.isatty():
            print()
        _finalize_run(run_id, "failed", traceback.format_exc())
        raise
    summarize_run(run_id)
    _auto_evaluate_lifecycle(release_id, testset_name)
    return run_id


def run_backtest_for_date(
    release_id: str,
    trade_date: date,
    run_id: str | None = None,
    testset: TestSet | None = None,
    tickers: list[str] | None = None,
    execution_config: ExecutionConfig | None = None,
    candidate_limit: int | None = None,
    force_data: bool = False,
) -> str:
    init_db()
    release_cls = get_release_class(release_id)
    release = release_cls()
    exec_cfg = execution_config or ExecutionConfig()
    owns_run = run_id is None
    if run_id is None:
        run_id = _create_adhoc_run(release_id, trade_date, tickers, exec_cfg)

    session_id = f"sl_{release_id}_{testset.name if testset else 'adhoc'}_{trade_date.isoformat()}_{uuid.uuid4().hex[:8]}"
    universe_name = testset.universe if testset else None
    ticker_list = _resolve_tickers(testset, trade_date, tickers)
    if candidate_limit is None and testset is not None:
        candidate_limit = testset.candidate_limit

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, run_id, trade_date, testset, release_id, strategy_letter, strategy_alias,
                status, started_at, universe_name, ticker_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session_id,
                run_id,
                trade_date,
                testset.name if testset else None,
                release_id,
                release.strategy_letter,
                release.strategy_alias,
                "running",
                _now(),
                universe_name,
                len(ticker_list),
            ],
        )

    try:
        context = _load_context(release_id, trade_date, testset.name if testset else None, ticker_list, force_data)
        candidates = release.build_candidates(context)
        # Guard against duplicate tickers from a release bug — the candidates
        # table PK is (session_id, ticker) and a duplicate would kill the
        # whole session instead of just being redundant.
        seen_tickers: set[str] = set()
        deduped = []
        for candidate in candidates:
            if candidate.ticker in seen_tickers:
                import logging
                logging.getLogger("strategy_lab.runner.pipeline").warning(
                    "Release %s returned duplicate candidate %s on %s — keeping first",
                    release_id, candidate.ticker, trade_date.isoformat(),
                )
                continue
            seen_tickers.add(candidate.ticker)
            deduped.append(candidate)
        candidates = deduped
        if candidate_limit is not None:
            candidates = candidates[:candidate_limit]
        signals = []
        trades = []

        with connect() as db_conn:
            db_conn.execute("BEGIN TRANSACTION")
            try:
                for candidate in candidates:
                    _insert_candidate(session_id, trade_date, release, candidate, conn=db_conn)
                    signal = release.build_signal(context, candidate)
                    if signal is None:
                        continue

                    # Engine-level finite guard: a non-finite entry/stop/target
                    # (e.g. NaN from a present-but-NaN volume or OHLC bar slipping
                    # through a release's gate) would otherwise produce a garbage
                    # simulated trade — NaN price comparisons silently evaluate
                    # False, so the simulator neither rejects nor fills cleanly.
                    # Drop it loudly here instead of corrupting the ledger. This
                    # is a family-agnostic safety net; it does not relieve a
                    # release from validating its own inputs.
                    levels = [signal.entry_trigger, signal.stop_price]
                    if signal.target_price is not None:
                        levels.append(signal.target_price)
                    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in levels):
                        logging.getLogger("strategy_lab.runner.pipeline").warning(
                            "Non-finite signal levels for %s on %s (entry=%r stop=%r "
                            "target=%r) — skipping execution simulation",
                            signal.ticker, trade_date.isoformat(),
                            signal.entry_trigger, signal.stop_price, signal.target_price,
                        )
                        continue

                    bars = context.bars_5m.get(signal.ticker)
                    if bars is None or bars.empty:
                        import logging
                        logging.getLogger("strategy_lab.runner.pipeline").warning(
                            "No 5m bars found for %s on %s, skipping execution simulation",
                            signal.ticker,
                            trade_date.isoformat(),
                        )
                        continue
                    
                    if getattr(release, "entry_style", "breakout_stop") == "pullback_limit":
                        # prefer 1-minute bars for limit-fill fidelity
                        sim_bars = context.bars_1m.get(signal.ticker)
                        if sim_bars is None or sim_bars.empty:
                            sim_bars = context.extended_1m.get(signal.ticker)
                        if sim_bars is not None and not sim_bars.empty:
                            # Same look-ahead guard as the breakout branch:
                            # signal_time labels the opening-range bar's OPEN;
                            # 1m bars 1-4 minutes later sit INSIDE that 5m
                            # setup bar. Detecting a breach or filling a
                            # pullback there trades the setup bar against the
                            # opening-range levels it itself defines.
                            sim_bars = sim_bars[
                                sim_bars.index >= signal.signal_time + timedelta(minutes=5)
                            ]
                        if sim_bars is None or sim_bars.empty:
                            sim_bars = bars
                        trade = simulate_pullback_limit_long(
                            sim_bars,
                            signal,
                            release.exit_cutoff(context),
                            exec_cfg,
                        )
                    else:
                        # Prefer 1-minute bars: with tight stops (e.g.
                        # 0.10 ATR ≈ a third of a 5m bar's range) the
                        # conservative same-bar stop rule fires on most 5m
                        # entry bars and overstates losses ~40% (measured
                        # on o04, 2026-06-12). Fall back to 5m when no 1m.
                        sim_bars = context.bars_1m.get(signal.ticker)
                        if sim_bars is not None and not sim_bars.empty:
                            # signal_time labels the signal bar's OPEN; the
                            # simulator's strict > filter correctly skips
                            # that 5m bar, but 1m bars 1-4 minutes later sit
                            # INSIDE it — filling there trades the setup bar
                            # against levels it itself defined (look-ahead).
                            sim_bars = sim_bars[
                                sim_bars.index >= signal.signal_time + timedelta(minutes=5)
                            ]
                        if sim_bars is None or sim_bars.empty:
                            sim_bars = bars
                        simulate = (
                            simulate_short_breakout
                            if signal.metadata.get("direction") == "short"
                            else simulate_long_breakout
                        )
                        trade = simulate(
                            sim_bars,
                            signal,
                            release.exit_cutoff(context),
                            exec_cfg,
                        )
                    if trade is None:
                        continue
                    
                    signals.append(signal)
                    trades.append(trade)
                    signal_id = _insert_signal(session_id, trade_date, release, signal, conn=db_conn)
                    order_id = _insert_order(session_id, signal_id, signal, conn=db_conn)
                    _insert_trade(run_id, session_id, trade_date, testset, release, signal_id, trade, conn=db_conn)
                    _insert_fills(session_id, order_id, signal_id, signal, trade, conn=db_conn)

                db_conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'completed', completed_at = ?, candidate_count = ?,
                        signal_count = ?, trade_count = ?
                    WHERE session_id = ?
                    """,
                    [_now(), len(candidates), len(signals), len([t for t in trades if t.entry_time]), session_id],
                )
                db_conn.execute("COMMIT")
            except Exception:
                db_conn.execute("ROLLBACK")
                raise

        if owns_run:
            summarize_run(run_id)
            _finalize_run(run_id, "completed")
        return session_id
    except Exception as exc:
        with connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = 'failed', completed_at = ?, error = ? WHERE session_id = ?",
                [_now(), f"{exc}\n{traceback.format_exc()}", session_id],
            )
        if owns_run:
            _finalize_run(run_id, "failed", traceback.format_exc())
        raise


def _auto_evaluate_lifecycle(release_id: str, testset_name: str) -> None:
    """Re-evaluate the release's funnel position after a run on a canonical
    testset. Off-funnel (ad-hoc) testsets don't move the lifecycle. Never let a
    lifecycle failure break a completed backtest — the run is already persisted.
    """
    from trading.lab.validation.funnel import rung_for_testset

    if rung_for_testset(testset_name) is None:
        return
    try:
        from trading.lab.validation.funnel_eval import evaluate_release

        with connect() as conn:
            evaluate_release(conn, release_id)
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger("strategy_lab.runner.pipeline").warning(
            "lifecycle auto-eval failed for %s after %s: %s",
            release_id, testset_name, exc,
        )


def summarize_run(run_id: str) -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT release_id, strategy_letter, strategy_alias, testset, setup_type, pnl_pct, entry_time, exit_reason, realized_r, mfe_pct, mae_pct, fees_pct, slippage_pct
            FROM trades
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchall()
        if not rows:
            run_info = conn.execute(
                """
                SELECT release_id, strategy_letter, strategy_alias, testset
                FROM runs
                WHERE run_id = ?
                """,
                [run_id]
            ).fetchone()
            if not run_info:
                return {}
            release_id, strategy_letter, strategy_alias, testset = run_info
            metrics = {
                "trade_count": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "gross_win_pct": 0.0,
                "gross_loss_pct": 0.0,
                "profit_factor": 0.0,
                "total_pnl_pct": 0.0,
                "avg_pnl_pct": 0.0,
                "best_trade_pct": 0.0,
                "worst_trade_pct": 0.0,
                # R-based (size-aware) — zeroed when no trades exist
                "total_realized_r": 0.0,
                "avg_realized_r": 0.0,
                "best_trade_r": 0.0,
                "worst_trade_r": 0.0,
                "account_return_pct_at_1pct_risk": 0.0,
                "no_fill_count": 0,
            }
        else:
            from trading.lab.core.metrics import compute_trade_metrics

            trades_list = []
            for r in rows:
                t = SimulatedTrade(
                    ticker="",
                    setup_type=r[4],
                    direction="long",
                    entry_time=r[6],
                    entry_price=None,
                    exit_time=None,
                    exit_price=None,
                    exit_reason=r[7] or "",
                    pnl_pct=float(r[5] or 0.0),
                    gross_pnl_pct=0.0,
                    realized_r=float(r[8]) if r[8] is not None else None,
                    mfe_pct=float(r[9]) if r[9] is not None else None,
                    mae_pct=float(r[10]) if r[10] is not None else None,
                    fees_pct=float(r[11] or 0.0),
                    slippage_pct=float(r[12] or 0.0),
                )
                trades_list.append(t)

            metrics = compute_trade_metrics(trades_list)
            release_id = rows[0][0]
            strategy_letter = rows[0][1]
            strategy_alias = rows[0][2]
            testset = rows[0][3]

        conn.execute(
            """
            INSERT OR REPLACE INTO release_metrics (
                run_id, testset, release_id, strategy_letter, strategy_alias, metric_scope,
                trade_count, wins, losses, win_rate, gross_win_pct, gross_loss_pct,
                profit_factor, total_pnl_pct, avg_pnl_pct, best_trade_pct,
                worst_trade_pct, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                testset,
                release_id,
                strategy_letter,
                strategy_alias,
                "overall",
                metrics["trade_count"],
                metrics["wins"],
                metrics["losses"],
                metrics["win_rate"],
                metrics["gross_win_pct"],
                metrics["gross_loss_pct"],
                metrics["profit_factor"],
                metrics["total_pnl_pct"],
                metrics["avg_pnl_pct"],
                metrics["best_trade_pct"],
                metrics["worst_trade_pct"],
                _json(metrics),
            ],
        )
        return metrics


def _create_run(
    release_id: str,
    testset: TestSet,
    ranges: list[DateRange],
    exec_cfg: ExecutionConfig,
) -> str:
    init_db()
    release_cls = get_release_class(release_id)
    release = release_cls()
    total_days = sum(len(_trading_days(r.start, r.end)) for r in ranges)
    utc_now = datetime.now(timezone.utc)
    run_id = f"run_{release_id}_{testset.name}_{utc_now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, testset, release_id, strategy_letter, strategy_alias, status,
                started_at, engine_version, execution_config_json, testset_config_json,
                code_signature, total_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                "backtest",
                testset.name,
                release_id,
                release.strategy_letter,
                release.strategy_alias,
                "running",
                _now(),
                ENGINE_VERSION,
                _json(exec_cfg.as_dict()),
                _json(asdict(testset)),
                compute_code_signature(release_id),
                total_days,
            ],
        )
    return run_id


def _create_adhoc_run(release_id: str, trade_date: date, tickers: list[str] | None, exec_cfg: ExecutionConfig) -> str:
    release_cls = get_release_class(release_id)
    release = release_cls()
    run_id = f"run_{release_id}_adhoc_{trade_date.isoformat()}_{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, release_id, strategy_letter, strategy_alias, status, started_at,
                engine_version, execution_config_json, code_signature, total_days, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                "adhoc_backtest",
                release_id,
                release.strategy_letter,
                release.strategy_alias,
                "running",
                _now(),
                ENGINE_VERSION,
                _json(exec_cfg.as_dict()),
                compute_code_signature(release_id),
                1,
                _json({"trade_date": trade_date, "tickers": tickers}),
            ],
        )
    return run_id


def _finalize_run(run_id: str, status: str, notes: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ?, notes = COALESCE(?, notes) WHERE run_id = ?",
            [status, _now(), notes, run_id],
        )


def _resolve_tickers(testset: TestSet | None, trade_date: date, override: list[str] | None) -> list[str]:
    if override:
        return sorted({t.upper() for t in override})
    if testset is None:
        raise ValueError("Ad-hoc runs require explicit tickers")
    if testset.tickers:
        return sorted({t.upper() for t in testset.tickers})
    if testset.universe:
        return load_universe_tickers(testset.universe, trade_date)
    raise ValueError(f"TestSet '{testset.name}' must define tickers or universe")


def _load_context(
    release_id: str,
    trade_date: date,
    testset_name: str | None,
    tickers: list[str],
    force_data: bool,
) -> StrategyContext:
    release = get_release_class(release_id)()
    bars_5m = {}
    daily = {}
    extended_1m = {}
    bars_1m = {}
    historical_5m = {}
    historical_lookback = getattr(release, "historical_5m_lookback_days", 0)
    historical_days = []
    if historical_lookback:
        historical_days = _trading_days(
            trade_date - timedelta(days=historical_lookback * 3),
            trade_date - timedelta(days=1),
        )[-historical_lookback:]

    for ticker in tickers:
        b = fetch_intraday_day(ticker, trade_date, "5min", "rth", force=force_data)
        d = fetch_daily_context(
            ticker, trade_date,
            lookback_days=getattr(release, "daily_lookback_days", 40),
            force=force_data,
        )
        if getattr(release, "requires_extended_1m", False):
            ext = fetch_intraday_day(ticker, trade_date, "1min", "extended", force=force_data)
            if ext is not None and not ext.empty:
                extended_1m[ticker] = ext
        if getattr(release, "requires_rth_1m", False):
            one = fetch_intraday_day(ticker, trade_date, "1min", "rth", force=force_data)
            if one is not None and not one.empty:
                bars_1m[ticker] = one
        if historical_days:
            h = fetch_intraday_range(
                ticker,
                historical_days[0],
                historical_days[-1],
                "5min",
                "rth",
                force=force_data,
            )
            if h is not None and not h.empty:
                historical_5m[ticker] = h
        if b is not None and not b.empty:
            bars_5m[ticker] = b
        if d is not None and not d.empty:
            daily[ticker] = d
    spy = fetch_intraday_day("SPY", trade_date, "5min", "rth", force=force_data)
    spy_daily = None
    if getattr(release, "requires_spy_daily", False):
        spy_daily = fetch_daily_context(
            "SPY",
            trade_date,
            lookback_days=getattr(release, "spy_daily_lookback_days", 40),
            force=force_data,
        )
    if getattr(release, "requires_rth_1m", False):
        # Fetch SPY 1-min bars for strategy-level feature computation
        # (_spy_features VWAP). Stored under key "SPY" in bars_1m —
        # ensure SPY is excluded from trading universes to avoid
        # clobbering the per-ticker fetch for this key.
        spy_1m = fetch_intraday_day("SPY", trade_date, "1min", "rth", force=force_data)
        if spy_1m is not None and not spy_1m.empty:
            bars_1m["SPY"] = spy_1m
    # Extra non-traded daily series (sector ETFs, breadth proxies) for regime
    # gates. Same window as SPY daily; keyed by symbol in context.extra_daily.
    extra_daily = {}
    for sym in getattr(release, "extra_daily_symbols", []) or []:
        ed = fetch_daily_context(
            sym,
            trade_date,
            lookback_days=getattr(release, "spy_daily_lookback_days", 40),
            force=force_data,
        )
        if ed is not None and not ed.empty:
            extra_daily[sym] = ed
    return StrategyContext(
        trade_date=trade_date,
        release_id=release_id,
        testset=testset_name,
        bars_5m=bars_5m,
        daily=daily,
        extended_1m=extended_1m,
        bars_1m=bars_1m,
        historical_5m=historical_5m,
        spy_5m=spy,
        spy_daily=spy_daily,
        extra_daily=extra_daily,
    )


def _insert_candidate(session_id, trade_date, release, candidate, conn=None) -> None:
    def _run(db_conn):
        db_conn.execute(
            """
            INSERT INTO candidates (
                session_id, trade_date, ticker, release_id, strategy_letter, strategy_alias,
                rank, score, reason, features_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session_id,
                trade_date,
                candidate.ticker,
                release.release_id,
                release.strategy_letter,
                release.strategy_alias,
                candidate.rank,
                candidate.score,
                candidate.reason,
                _json(candidate.features),
            ],
        )

    if conn is None:
        with connect() as db_conn:
            _run(db_conn)
    else:
        _run(conn)


def _insert_signal(session_id, trade_date, release, signal, conn=None) -> str:
    signal_id = f"sig_{uuid.uuid4().hex}"
    def _run(db_conn):
        db_conn.execute(
            """
            INSERT INTO signals (
                signal_id, session_id, trade_date, ticker, release_id, strategy_letter,
                strategy_alias, setup_type, signal_time, entry_trigger, stop_price,
                target_price, risk_per_share, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                signal_id,
                session_id,
                trade_date,
                signal.ticker,
                release.release_id,
                release.strategy_letter,
                release.strategy_alias,
                signal.setup_type,
                signal.signal_time,
                signal.entry_trigger,
                signal.stop_price,
                signal.target_price,
                signal.risk_per_share,
                _json(signal.metadata),
            ],
        )

    if conn is None:
        with connect() as db_conn:
            _run(db_conn)
    else:
        _run(conn)
    return signal_id


def _insert_order(session_id: str, signal_id: str, signal, conn=None) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"

    def _run(db_conn):
        db_conn.execute(
            """
            INSERT INTO orders (
                order_id, signal_id, session_id, ticker, side, order_type,
                trigger_price, limit_price, stop_price, target_price, created_at,
                expires_at, status, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                order_id,
                signal_id,
                session_id,
                signal.ticker,
                "sell" if signal.metadata.get("direction") == "short" else "buy",
                "stop",
                signal.entry_trigger,
                None,
                signal.stop_price,
                signal.target_price,
                signal.signal_time,
                None,
                "simulated",
                _json({}),
            ],
        )

    if conn is None:
        with connect() as db_conn:
            _run(db_conn)
    else:
        _run(conn)
    return order_id


def _insert_fills(session_id: str, order_id: str, signal_id: str, signal, trade, conn=None) -> None:
    if trade.entry_time is None or trade.entry_price is None:
        return

    quantity = signal.metadata.get("shares")
    is_short = trade.direction == "short"
    fill_rows = [
        (
            f"fil_{uuid.uuid4().hex}",
            order_id,
            signal_id,
            session_id,
            signal.ticker,
            "sell" if is_short else "buy",
            trade.entry_time,
            trade.entry_price,
            quantity,
            trade.fees_pct / 2.0,
            trade.slippage_pct / 2.0,
            _json({"unit": "pct", "leg": "entry"}),
        )
    ]
    if trade.exit_time is not None and trade.exit_price is not None:
        fill_rows.append(
            (
                f"fil_{uuid.uuid4().hex}",
                order_id,
                signal_id,
                session_id,
                signal.ticker,
                "buy" if is_short else "sell",
                trade.exit_time,
                trade.exit_price,
                quantity,
                trade.fees_pct / 2.0,
                trade.slippage_pct / 2.0,
                _json({"unit": "pct", "leg": "exit", "exit_reason": trade.exit_reason}),
            )
        )

    def _run(db_conn):
        db_conn.executemany(
            """
            INSERT INTO fills (
                fill_id, order_id, signal_id, session_id, ticker, side, fill_time,
                fill_price, quantity, fees, slippage, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fill_rows,
        )

    if conn is None:
        with connect() as db_conn:
            _run(db_conn)
    else:
        _run(conn)


def _insert_trade(run_id, session_id, trade_date, testset, release, signal_id, trade, conn=None) -> None:
    def _run(db_conn):
        db_conn.execute(
            """
            INSERT INTO trades (
                trade_id, signal_id, session_id, run_id, trade_date, testset, ticker,
                release_id, strategy_letter, strategy_alias, setup_type, direction,
                entry_time, entry_price, exit_time, exit_price, exit_reason, pnl_pct,
                gross_pnl_pct, realized_r, mfe_pct, mae_pct, fees_pct, slippage_pct,
                context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"trd_{uuid.uuid4().hex}",
                signal_id,
                session_id,
                run_id,
                trade_date,
                testset.name if testset else None,
                trade.ticker,
                release.release_id,
                release.strategy_letter,
                release.strategy_alias,
                trade.setup_type,
                trade.direction,
                trade.entry_time,
                trade.entry_price,
                trade.exit_time,
                trade.exit_price,
                trade.exit_reason,
                trade.pnl_pct,
                trade.gross_pnl_pct,
                trade.realized_r,
                trade.mfe_pct,
                trade.mae_pct,
                trade.fees_pct,
                trade.slippage_pct,
                _json(trade.context),
            ],
        )

    if conn is None:
        with connect() as db_conn:
            _run(db_conn)
    else:
        _run(conn)
