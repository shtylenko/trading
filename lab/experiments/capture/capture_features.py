#!/usr/bin/env python3
"""Feature-capture driver for the offline gap-and-go feature search.

Runs the ``capture_d_features`` variant (d01 minimum admission + the full
research.features vector) over a date range and universe, UNCAPPED, then exports
a rectangular feature ledger (parquet) — one row per admitted candidate with its
feature vector, gap score, fill flag, and realized R. See
validation/feature_search_spec.md.

    # one-month smoke (validate ledger shape + hydration wiring)
    python3 -m trading.lab.experiments.capture.capture_features \
        --start 2024-03-01 --end 2024-03-31 \
        --universe liquid_pit --max-tickers 40 \
        --out trading/lab/experiments/_data/_capture_smoke.parquet

    # full multi-year capture (after smoke passes)
    python3 -m trading.lab.experiments.capture.capture_features \
        --start 2022-01-01 --end 2025-12-31 \
        --universe liquid_pit \
        --out trading/lab/experiments/_data/_capture_2022_2025.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from tqdm import tqdm
except ImportError:  # graceful fallback: keep running without a progress bar
    tqdm = None

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.data.universes import load_universe_tickers
from trading.marketdata.calendar import trading_days_in_range
from trading.lab.research.features import FEATURE_NAMES
from trading.lab.runner.pipeline import (
    ENGINE_VERSION,
    _finalize_run,
    _now,
    compute_code_signature,
    run_backtest_for_date,
    summarize_run,
)
from trading.lab.storage.duckdb import connect, init_db

RELEASE_ID = "capture_d_features"


def _create_capture_run(run_id: str, total_days: int, config: dict) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, run_type, release_id, strategy_letter, strategy_alias,
                status, started_at, engine_version, code_signature, total_days, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [run_id, "feature_capture", RELEASE_ID, "d",
             "post_gap_opening_drive", "running", _now(), ENGINE_VERSION,
             compute_code_signature(RELEASE_ID), total_days, json.dumps(config)],
        )


def export_ledger(run_id: str, out_path: Path) -> pd.DataFrame:
    """Join admitted candidates to their trades and explode features → parquet."""
    with connect(read_only=True) as conn:
        cands = conn.execute(
            """
            SELECT c.session_id, c.trade_date, c.ticker, c.score, c.rank, c.features_json
            FROM candidates c JOIN sessions s ON s.session_id = c.session_id
            WHERE s.run_id = ?
            """,
            [run_id],
        ).fetch_df()
        trades = conn.execute(
            """
            SELECT session_id, ticker, realized_r, exit_reason, entry_time
            FROM trades WHERE run_id = ?
            """,
            [run_id],
        ).fetch_df()

    if cands.empty:
        raise SystemExit(f"No candidates captured for run {run_id}")

    feat_rows = [json.loads(j) if j else {} for j in cands["features_json"]]
    feats = pd.DataFrame(feat_rows).reindex(columns=list(FEATURE_NAMES))
    base = cands.drop(columns=["features_json"]).reset_index(drop=True)
    # sector_etf is candidate metadata, not a FEATURE_NAMES column — preserve it
    # explicitly so the reindex above doesn't silently drop it.
    base["sector_etf"] = [r.get("sector_etf") for r in feat_rows]
    ledger = pd.concat([base, feats.reset_index(drop=True)], axis=1)

    ledger = ledger.merge(trades, on=["session_id", "ticker"], how="left")
    ledger["filled"] = ledger["entry_time"].notna()
    ledger = ledger.drop(columns=["entry_time"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(out_path, index=False)
    return ledger


def _print_summary(ledger: pd.DataFrame, out_path: Path) -> None:
    n = len(ledger)
    filled = int(ledger["filled"].sum())
    days = ledger["trade_date"].nunique()
    print(f"\nLedger: {out_path}")
    print(f"  rows (admitted candidates): {n}  over {days} days")
    print(f"  filled (became trades):     {filled} ({filled / n * 100:.0f}%)")
    if filled:
        r = ledger.loc[ledger["filled"], "realized_r"]
        print(f"  sum realized R (uncapped):  {r.sum():+.1f}  meanR {r.mean():+.3f}")
    print("  feature non-null coverage (key ones):")
    for k in ("gap_pct_vs_prior_high", "first_close_pos", "first_range_atr_frac",
              "opening_rv", "close_vs_own_200d_sma", "beta_60d", "rel_spy_gap",
              "spy_below_50d_sma", "sector_below_50d_sma", "rel_sector_momentum_20d"):
        if k in ledger:
            pct = ledger[k].notna().mean() * 100
            print(f"    {k:28} {pct:5.0f}%")
    missing = [k for k in FEATURE_NAMES if ledger[k].notna().mean() == 0]
    if missing:
        print(f"  ALL-NULL features (check hydration): {missing}")


def main() -> None:
    p = argparse.ArgumentParser(description="Capture gap-and-go candidate features")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--universe", default="liquid_pit",
                   help="point-in-time universe; must match the broad evals (liquid_pit)")
    p.add_argument("--max-tickers", type=int, default=None,
                   help="cap universe size (smoke runs only)")
    p.add_argument("--out", required=True, help="output parquet path")
    p.add_argument("--force-data", action="store_true")
    p.add_argument("--export-only", help="skip the run; just export this run_id")
    p.add_argument("--resume", help="continue an existing run_id; skip days already "
                                    "completed (use the SAME --start/--end/--universe)")
    args = p.parse_args()

    init_db()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path

    if args.export_only:
        ledger = export_ledger(args.export_only, out_path)
        _print_summary(ledger, out_path)
        return

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    days = trading_days_in_range(start, end)
    if not days:
        raise SystemExit(f"No trading days in {args.start}..{args.end}")
    # Fail fast on a universe with no point-in-time snapshot covering the start
    # date (e.g. cached_1min_2024_pit has only a 2024 snapshot → empty for 2022).
    if not load_universe_tickers(args.universe, days[0]):
        raise SystemExit(
            f"Universe '{args.universe}' resolves to ZERO tickers on {days[0]} — "
            f"it has no point-in-time snapshot on/before the start date. Use "
            f"'liquid_pit' (quarterly snapshots 2022→2026, matches the broad evals).")
    done_dates: set = set()
    if args.resume:
        run_id = args.resume
        with connect(read_only=True) as conn:
            exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", [run_id]).fetchone()
            if not exists:
                raise SystemExit(f"--resume run_id '{run_id}' not found")
            done_dates = {
                r[0] for r in conn.execute(
                    "SELECT DISTINCT trade_date FROM sessions "
                    "WHERE run_id = ? AND status = 'completed'", [run_id]).fetchall()
            }
        # re-open the run for writing (it was finalized as failed on the crash)
        with connect() as conn:
            conn.execute("UPDATE runs SET status='running', total_days=? WHERE run_id=?",
                         [len(days), run_id])
        print(f"RESUMING {run_id}: {len(done_dates)}/{len(days)} days already done, "
              f"continuing with the rest")
    else:
        run_id = (f"run_{RELEASE_ID}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_"
                  f"{uuid.uuid4().hex[:6]}")
        _create_capture_run(run_id, len(days), {
            "start": args.start, "end": args.end, "universe": args.universe,
            "max_tickers": args.max_tickers})
        print(f"Capture run {run_id}: {len(days)} days, universe {args.universe}"
              + (f" (max {args.max_tickers} tickers)" if args.max_tickers else ""))

    failed = 0
    # Progress bar + ETA over the full day list; on resume it starts pre-advanced
    # by the already-completed days so the ETA reflects only the remaining work.
    pending = [d for d in days if d not in done_dates]
    bar = (tqdm(total=len(days), initial=len(done_dates), unit="day", desc="capture",
                dynamic_ncols=True, smoothing=0.05) if tqdm is not None else None)

    def _log(msg: str) -> None:
        (tqdm.write if bar is not None else print)(msg, file=sys.stderr)

    for d in pending:
        tickers = load_universe_tickers(args.universe, d)
        if args.max_tickers:
            tickers = tickers[: args.max_tickers]
        if not tickers:
            _log(f"{d} skipped (no universe tickers)")
            if bar is not None:
                bar.update(1)
            continue
        try:
            run_backtest_for_date(
                release_id=RELEASE_ID, trade_date=d, run_id=run_id,
                testset=None, tickers=tickers, candidate_limit=None,
                force_data=args.force_data,
            )
        except Exception as exc:  # session-isolated; keep going
            failed += 1
            _log(f"{d} FAILED: {exc}")
            if bar is not None:
                bar.set_postfix(failed=failed); bar.update(1)
            continue
        with connect() as conn:
            conn.execute(
                "UPDATE runs SET completed_days = (SELECT COUNT(DISTINCT trade_date) "
                "FROM sessions WHERE run_id = ? AND status = 'completed') WHERE run_id = ?",
                [run_id, run_id])
        if bar is not None:
            bar.set_postfix(date=str(d), failed=failed); bar.update(1)
        else:
            print(f"  {d} done")
    if bar is not None:
        bar.close()

    summarize_run(run_id)
    _finalize_run(run_id, "completed_with_errors" if failed else "completed",
                  f"{failed} failed sessions" if failed else "")
    ledger = export_ledger(run_id, out_path)
    _print_summary(ledger, out_path)


if __name__ == "__main__":
    main()
