"""Additive SWING runner for multi-day (cross-session) releases — see
strategies.base.SwingStrategyRelease. The intraday per-session engine
(runner/pipeline.py) is unchanged; this is a parallel path for daily-rebalanced,
multi-day-hold strategies that persists to the SAME DuckDB tables (runs / sessions /
candidates / signals / orders / trades / fills) via the existing pipeline helpers, so
swing releases are first-class in the ledger / dashboard / funnel.

Per rebalance date (every ``release.rebalance_cadence_days`` trading days): hydrate a
daily context THROUGH the rebalance close (inclusive), rank via ``build_candidates``,
take the top ``release.top_n``, and simulate each name's ``release.hold_days`` hold on
daily bars (``core.execution.simulate_daily_hold``). One session row per rebalance.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

import pandas as pd

from trading.lab.core.execution import simulate_daily_hold
from trading.lab.core.models import ExecutionConfig, StrategyContext
from trading.lab.data.market_data import fetch_daily_range
from trading.lab.data.testsets import TestSet, load_testset
from trading.lab.data.universes import load_universe_tickers
from trading.lab.storage.duckdb import connect, init_db
from trading.lab.strategies import get_release_class
from trading.lab.runner.pipeline import (
    _create_run, _finalize_run, _now, _trading_days, summarize_run,
    _insert_candidate, _insert_signal, _insert_order, _insert_trade, _insert_fills,
)

log = logging.getLogger("strategy_lab.runner.swing_pipeline")


def is_swing_release(release_id: str) -> bool:
    return bool(getattr(get_release_class(release_id)(), "is_swing", False))


def _load_daily_bars(tickers, start, end, force, adjustment="split"):
    """One ranged daily fetch per ticker → {ticker: date-indexed df}.

    ``adjustment`` defaults to split-adjusted: a multi-day hold can straddle a
    stock split, and a split inside the momentum lookback corrupts the rank, so
    swing bars must be on a split-continuous series (unlike the raw intraday path).
    """
    out = {}
    for i, t in enumerate(sorted(tickers), 1):
        try:
            df = fetch_daily_range(t, start, end, force=force, adjustment=adjustment)
        except Exception as exc:
            log.warning(
                "swing daily fetch failed for %s (%s..%s, adjustment=%s): %s",
                t, start, end, adjustment, exc,
            )
            df = None
        if df is not None and not df.empty:
            d = df.copy()
            d.index = pd.DatetimeIndex(d.index).normalize().tz_localize(None)
            out[t] = d[~d.index.duplicated(keep="last")].sort_index()
        if i % 250 == 0 or i == len(tickers):
            log.info("swing prefetch %d/%d daily series", i, len(tickers))
    return out


def run_swing_backtest_for_testset(
    release_id: str,
    testset_name: str,
    execution_config: ExecutionConfig | None = None,
    force_data: bool = False,
) -> str:
    init_db()
    testset = load_testset(testset_name)
    release = get_release_class(release_id)()
    if not getattr(release, "is_swing", False):
        raise ValueError(f"{release_id} is not a swing release")
    exec_cfg = execution_config or ExecutionConfig()
    H = int(release.hold_days)
    cadence = int(release.rebalance_cadence_days)
    top_n = int(release.top_n)
    lookback_rows = max(260, int(getattr(release, "daily_lookback_days", 420) / 1.4))

    run_id = _create_run(release_id, testset, testset.date_ranges, exec_cfg)
    print(f"Swing run {run_id}: {release_id} on '{testset.name}', "
          f"hold={H}d cadence={cadence}d top_n={top_n}")
    try:
        for dr in testset.date_ranges:
            tdays = [pd.Timestamp(d) for d in _trading_days(dr.start, dr.end)]
            if len(tdays) <= H:
                print(f"  range {dr.label}: only {len(tdays)} trading days (<= hold {H}); skipped")
                continue
            rebal_days = tdays[::cadence]
            # union of PIT-universe tickers across rebalance dates
            members = {rd: set(load_universe_tickers(testset.universe, rd.date())) for rd in rebal_days}
            union = set().union(*members.values()) if members else set()
            print(f"  range {dr.label}: {len(rebal_days)} rebalances, {len(union)} tickers; prefetching daily…")
            bars = _load_daily_bars(union, dr.start - timedelta(days=600),
                                    dr.end + timedelta(days=int(H * 1.6) + 10), force_data,
                                    adjustment=getattr(release, "daily_adjustment", "split"))
            spy_daily = None
            if getattr(release, "requires_spy_daily", False):
                spy_lookback = max(
                    int(getattr(release, "spy_daily_lookback_days", 40)),
                    int(getattr(release, "daily_lookback_days", 40)),
                )
                spy_daily = fetch_daily_range(
                    "SPY",
                    dr.start - timedelta(days=int(spy_lookback * 1.5) + 10),
                    dr.end,
                    force=force_data,
                    adjustment=getattr(release, "daily_adjustment", "split"),
                )
                if spy_daily is not None and not spy_daily.empty:
                    spy_daily = spy_daily.copy()
                    spy_daily.index = pd.DatetimeIndex(spy_daily.index).normalize().tz_localize(None)
                    spy_daily = spy_daily[~spy_daily.index.duplicated(keep="last")].sort_index()

            for ri, rd in enumerate(rebal_days, 1):
                # last complete H-day hold must fit inside available data
                _run_swing_session(run_id, release_id, release, testset, rd, H, top_n,
                                   members[rd], bars, exec_cfg, spy_daily=spy_daily)
                if ri % 5 == 0 or ri == len(rebal_days):
                    print(f"    {dr.label}: {ri}/{len(rebal_days)} rebalances", flush=True)
        _finalize_run(run_id, "completed")
        # Populate release_metrics for the dashboard, but do NOT auto-evaluate the
        # funnel: its gates are tuned for intraday per-trade R and would mislabel a
        # 20-day swing book (per peer review). Funnel placement for swing is manual.
        try:
            summarize_run(run_id)
        except Exception:
            log.warning("swing summarize_run failed", exc_info=True)
    except Exception as exc:
        _finalize_run(run_id, "failed", notes=str(exc))
        raise
    return run_id


def _run_swing_session(run_id, release_id, release, testset, rebal_ts, H, top_n,
                       pit_members, bars, exec_cfg, spy_daily=None) -> None:
    rd = rebal_ts.date()
    session_id = f"sw_{release_id}_{testset.name}_{rd.isoformat()}_{uuid.uuid4().hex[:8]}"
    # daily context THROUGH the rebalance close (inclusive), PIT members only
    ctx_daily = {}
    for t in pit_members:
        b = bars.get(t)
        if b is None or rebal_ts not in b.index:
            continue
        upto = b[b.index <= rebal_ts]
        if len(upto) >= 253:
            ctx_daily[t] = upto.tail(300)
    ctx_spy_daily = None
    if spy_daily is not None and rebal_ts in spy_daily.index:
        upto_spy = spy_daily[spy_daily.index <= rebal_ts]
        if len(upto_spy) >= 253:
            ctx_spy_daily = upto_spy.tail(300)
    context = StrategyContext(trade_date=rd, release_id=release_id, testset=testset.name,
                              bars_5m={}, daily=ctx_daily, spy_daily=ctx_spy_daily)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, run_id, trade_date, testset, release_id, strategy_letter,
                strategy_alias, status, started_at, universe_name, ticker_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [session_id, run_id, rd, testset.name, release_id, release.strategy_letter,
             release.strategy_alias, "running", _now(), testset.universe, len(ctx_daily)],
        )

    candidates = release.build_candidates(context)[:top_n]
    n_signals = n_trades = 0
    with connect() as db:
        db.execute("BEGIN TRANSACTION")
        try:
            for cand in candidates:
                _insert_candidate(session_id, rd, release, cand, conn=db)
                signal = release.build_signal(context, cand)
                if signal is None:
                    continue
                full = bars.get(cand.ticker)
                trade = simulate_daily_hold(full, signal, rebal_ts, H, exec_cfg,
                                            use_close_stop=getattr(release, "use_close_stop", False))
                if trade is None:
                    continue
                n_signals += 1
                sig_id = _insert_signal(session_id, rd, release, signal, conn=db)
                ord_id = _insert_order(session_id, sig_id, signal, conn=db)
                _insert_trade(run_id, session_id, rd, testset, release, sig_id, trade, conn=db)
                _insert_fills(session_id, ord_id, sig_id, signal, trade, conn=db)
                if trade.entry_time is not None:
                    n_trades += 1
            db.execute(
                "UPDATE sessions SET status='completed', completed_at=?, "
                "candidate_count=?, signal_count=?, trade_count=? WHERE session_id=?",
                [_now(), len(candidates), n_signals, n_trades, session_id],
            )
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            with connect() as c2:
                c2.execute("UPDATE sessions SET status='failed', completed_at=? WHERE session_id=?",
                           [_now(), session_id])
            raise
