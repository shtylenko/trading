#!/usr/bin/env python3
"""Inspect and steer where each release sits on the evaluation funnel.

Examples:
    # show every release's rung + disposition
    python3 -m trading.lab.scripts.lifecycle --list

    # recompute one release (or all) from its stored runs
    python3 -m trading.lab.scripts.lifecycle --evaluate o03
    python3 -m trading.lab.scripts.lifecycle --evaluate-all

    # manual sign-off / override (e.g. clear a fuzzy review rung, or retire)
    python3 -m trading.lab.scripts.lifecycle --set o03 \\
        --disposition archived --reason "superseded by o04"
    python3 -m trading.lab.scripts.lifecycle --set f06 \\
        --stage 3 --disposition active --reason "robustness signed off"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.storage.duckdb import connect, init_db
from trading.lab.storage.lifecycle import get_lifecycle, list_lifecycle, upsert_lifecycle
from trading.lab.strategies import list_releases
from trading.lab.validation.funnel import (
    DISPOSITION_ACTIVE,
    DISPOSITION_ARCHIVED,
    DISPOSITION_KILLED,
    DISPOSITION_PROMOTED,
    FUNNEL,
)
from trading.lab.validation.funnel_eval import evaluate_release

_DISPOSITIONS = (
    DISPOSITION_ACTIVE, DISPOSITION_KILLED, DISPOSITION_PROMOTED, DISPOSITION_ARCHIVED,
)
# Sort terminal/parked states to the bottom; active/promoted climb to the top.
_DISP_ORDER = {
    DISPOSITION_PROMOTED: 0,
    DISPOSITION_ACTIVE: 1,
    DISPOSITION_KILLED: 2,
    DISPOSITION_ARCHIVED: 3,
}


def _stage_label(stage: int) -> str:
    if 0 <= stage < len(FUNNEL):
        return f"{stage}:{FUNNEL[stage].name}"
    return str(stage)


def cmd_list(conn) -> None:
    rows = list_lifecycle(conn)
    releases = list_releases()
    merged = [get_lifecycle(conn, r) if r not in rows else rows[r] for r in releases]
    merged.sort(key=lambda r: (_DISP_ORDER.get(r["disposition"], 9), -int(r["stage"] or 0), r["release_id"]))
    print(f"{'release':<8} {'disposition':<11} {'stage':<14} reason")
    print("-" * 72)
    for r in merged:
        killed = f" (killed@{r['killed_stage']})" if r.get("killed_stage") is not None else ""
        print(f"{r['release_id']:<8} {r['disposition']:<11} "
              f"{_stage_label(int(r['stage'] or 0)):<14} {(r.get('reason') or '')}{killed}")


def cmd_evaluate(conn, releases: list[str]) -> None:
    for rid in releases:
        lc = evaluate_release(conn, rid)
        killed = f" killed@{lc['killed_stage']}" if lc.get("killed_stage") is not None else ""
        print(f"{rid}: {lc['disposition']} @ stage {_stage_label(int(lc['stage'] or 0))}{killed} — {lc.get('reason')}")


def cmd_set(conn, args) -> None:
    current = get_lifecycle(conn, args.set)
    stage = args.stage if args.stage is not None else int(current["stage"] or 0)
    disposition = args.disposition or current["disposition"]
    killed_stage = args.killed_stage if args.killed_stage is not None else (
        current.get("killed_stage") if disposition == DISPOSITION_KILLED else None
    )
    upsert_lifecycle(
        conn, args.set,
        stage=stage,
        disposition=disposition,
        killed_stage=killed_stage,
        reason=args.reason or current.get("reason"),
        decided_by_run=current.get("decided_by_run"),
    )
    lc = get_lifecycle(conn, args.set)
    print(f"{args.set}: {lc['disposition']} @ stage {_stage_label(int(lc['stage'] or 0))} — {lc.get('reason')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect/steer release lifecycle on the evaluation funnel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--list", action="store_true", help="List every release's rung + disposition")
    parser.add_argument("--evaluate", metavar="RELEASE", help="Recompute one release from its runs")
    parser.add_argument("--evaluate-all", action="store_true", help="Recompute every registered release")
    parser.add_argument("--set", metavar="RELEASE", help="Manually set lifecycle fields for a release")
    parser.add_argument("--stage", type=int, default=None, help="(with --set) furthest rung index reached")
    parser.add_argument("--disposition", choices=_DISPOSITIONS, default=None, help="(with --set) disposition")
    parser.add_argument("--killed-stage", type=int, default=None, help="(with --set) rung index it died on")
    parser.add_argument("--reason", default=None, help="(with --set) human note explaining the change")

    args = parser.parse_args()
    init_db()

    if not (args.list or args.evaluate or args.evaluate_all or args.set):
        parser.error("one of --list, --evaluate, --evaluate-all, or --set is required")

    with connect() as conn:
        if args.set:
            cmd_set(conn, args)
        if args.evaluate:
            cmd_evaluate(conn, [args.evaluate])
        if args.evaluate_all:
            cmd_evaluate(conn, list_releases())
        if args.list:
            cmd_list(conn)


if __name__ == "__main__":
    main()
