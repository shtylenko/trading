"""Evaluator — read a release's runs, apply the funnel gates, write the ledger.

This is the bridge between the pure ladder spec (``funnel.py``, no database) and
the mutable lifecycle ledger (``storage/lifecycle.py``). For each *gated* rung
(one with canonical testsets) it pools the release's latest run on each of that
rung's testsets, builds a :class:`GateInput`, applies the gate, and derives the
release's ``(stage, disposition)``. The fuzzy rungs (robustness / tradeability /
portfolio) have no testset and are advanced only by a human via the CLI.

Auto-advance with manual override:
- A KILL is terminal — the release stops at the rung it died on.
- A REVIEW (weak edge, one-bucket carry, or a fuzzy rung) stops auto-advance;
  a human signs it off, also via the CLI.
- A manual ``archived`` disposition is never overwritten by auto-eval.

Lifecycle is global to a release *relative to the canonical funnel*: a run on an
ad-hoc, off-funnel testset does not move the release's stage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace

from trading.lab.storage.lifecycle import get_lifecycle, upsert_lifecycle
from trading.lab.validation.funnel import (
    DISPOSITION_ACTIVE,
    DISPOSITION_ARCHIVED,
    DISPOSITION_KILLED,
    DISPOSITION_PROMOTED,
    FUNNEL,
    GateInput,
    Verdict,
)
from trading.lab.validation.run_stats import validate_daily_r

logger = logging.getLogger("strategy_lab.validation.funnel_eval")

# ~ trading days per quarter; turns a pooled trade count + day span into the
# >20/quarter cadence the broad gate checks.
_TRADING_DAYS_PER_QUARTER = 63
# Sign-flip iterations for the gate p-value. Vectorized; a few ms even here.
_PERM_ITERS = 10_000


def _latest_run_on(conn, release_id: str, testset: str):
    """(run_id, status) of the release's most recent run on a testset, or None."""
    row = conn.execute(
        """
        SELECT run_id, status FROM runs
        WHERE release_id = ? AND testset = ?
        ORDER BY started_at DESC, run_id DESC
        LIMIT 1
        """,
        [release_id, testset],
    ).fetchone()
    return (row[0], row[1]) if row else None


def _run_sum_r(conn, run_id: str) -> float:
    """total_realized_r for a run, read from the overall release_metrics row."""
    row = conn.execute(
        "SELECT metrics_json FROM release_metrics WHERE run_id = ? AND metric_scope = 'overall'",
        [run_id],
    ).fetchone()
    if not row or not row[0]:
        return 0.0
    try:
        return float(json.loads(row[0]).get("total_realized_r", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_gate_input(conn, release_id: str, rung) -> tuple[GateInput | None, str | None]:
    """Pool the release's latest run on each of the rung's testsets into one
    GateInput. Each testset is a *bucket* (so the broad rung can spot a
    one-bucket carry across years). Returns (None, None) if the release has no
    run on any of the rung's testsets.
    """
    runs: list[tuple[str, str, str]] = []  # (testset, run_id, status)
    for testset in sorted(rung.testsets):
        found = _latest_run_on(conn, release_id, testset)
        if found:
            runs.append((testset, found[0], found[1]))
    if not runs:
        return None, None

    pooled_trades: list[tuple] = []
    total_days = 0
    bucket_sums: list[float] = []
    ran_clean = True
    last_run_id = runs[-1][1]
    for _testset, run_id, status in runs:
        if status not in ("completed", "completed_with_errors"):
            ran_clean = False
        trades = conn.execute(
            """
            SELECT trade_date, realized_r FROM trades
            WHERE run_id = ? AND realized_r IS NOT NULL
            ORDER BY trade_date
            """,
            [run_id],
        ).fetchall()
        pooled_trades.extend((str(d), float(r)) for d, r in trades)
        day_row = conn.execute(
            "SELECT COUNT(DISTINCT trade_date) FROM sessions WHERE run_id = ?",
            [run_id],
        ).fetchone()
        total_days += int(day_row[0] or 0) if day_row else 0
        bucket_sums.append(_run_sum_r(conn, run_id))

    trade_count = len(pooled_trades)
    sum_r = sum(bucket_sums)
    worst_bucket_r = min(bucket_sums) if bucket_sums else 0.0

    # Sign-flip p on the pooled daily-R series (same gate as the dashboard).
    if trade_count and total_days:
        p_value = validate_daily_r(pooled_trades, total_days, iters=_PERM_ITERS)["p_value"]
    else:
        p_value = 1.0

    # Trades per quarter over the pooled session-day span.
    trades_per_quarter = (
        trade_count / (total_days / _TRADING_DAYS_PER_QUARTER) if total_days else 0.0
    )

    gi = GateInput(
        sum_r=sum_r,
        trade_count=trade_count,
        p_value=p_value,
        trades_per_quarter=trades_per_quarter,
        worst_bucket_r=worst_bucket_r,
        ran_clean=ran_clean,
        integrity_ok=True,  # deeper integrity checks are a later add
    )
    return gi, last_run_id


def evaluate_release(conn, release_id: str) -> dict:
    """Walk the gated rungs bottom-up, apply each gate, upsert the lifecycle row.

    Returns the resulting lifecycle dict. A manually-archived release is left
    untouched.
    """
    existing = get_lifecycle(conn, release_id)
    if existing.get("disposition") == DISPOSITION_ARCHIVED:
        return existing

    gated = [r for r in FUNNEL if r.testsets]  # smoke, screen, broad_is, oos

    last_passed: int | None = None
    broad_is_sum_r: float | None = None
    disposition = DISPOSITION_ACTIVE
    killed_stage: int | None = None
    reason = "no funnel runs yet"
    decided_by_run: str | None = None
    promoted = False

    for rung in gated:
        gi, run_id = build_gate_input(conn, release_id, rung)
        if gi is None:
            # No run at this rung yet; can't judge further up the ladder.
            if last_passed is not None:
                reason = f"cleared {gated_name(last_passed)}; awaiting {rung.name} run"
            break
        if rung.name == "oos":
            gi = replace(gi, is_sum_r=broad_is_sum_r)
        res = rung.gate(gi)
        decided_by_run = run_id
        if res.verdict is Verdict.KILL:
            disposition = DISPOSITION_KILLED
            killed_stage = rung.index
            reason = f"killed @ {rung.name}: {res.reason}"
            break
        if res.verdict is Verdict.REVIEW:
            reason = f"review @ {rung.name}: {res.reason}"
            break
        last_passed = rung.index
        if rung.name == "broad_is":
            broad_is_sum_r = gi.sum_r
        reason = f"passed {rung.name}: {res.reason}"
        if rung.is_oos:
            promoted = True

    stage = last_passed if last_passed is not None else 0
    if disposition == DISPOSITION_ACTIVE and promoted:
        disposition = DISPOSITION_PROMOTED

    upsert_lifecycle(
        conn, release_id,
        stage=stage,
        disposition=disposition,
        killed_stage=killed_stage,
        reason=reason,
        decided_by_run=decided_by_run,
    )
    return get_lifecycle(conn, release_id)


def gated_name(index: int) -> str:
    return FUNNEL[index].name


def check_oos_prerequisite(conn, release_id: str, testset_name: str) -> tuple[bool, str]:
    """Guard the one-shot holdout: refuse an OOS run on a release that has not
    yet cleared the prerequisite in-sample stage.

    Returns ``(allowed, message)``. Non-OOS (or off-funnel) testsets are always
    allowed. Every premature peek at OOS data stacks selection bias no later
    test can remove — so the runner blocks it unless explicitly overridden.
    """
    from trading.lab.validation.funnel import rung_for_testset

    rung = rung_for_testset(testset_name)
    if rung is None or not rung.is_oos:
        return True, ""
    lc = get_lifecycle(conn, release_id)
    stage = int(lc.get("stage") or 0)
    if stage >= rung.prereq_stage:
        return True, ""
    need = FUNNEL[rung.prereq_stage].name
    return False, (
        f"{release_id} is at stage {stage} ({lc.get('disposition')}); "
        f"'{testset_name}' is an OUT-OF-SAMPLE rung that requires clearing "
        f"'{need}' (stage {rung.prereq_stage}) first. Spending the holdout now "
        f"burns it. Re-run the in-sample funnel, or pass --allow-oos to override."
    )
