"""
Daily pipeline orchestrator (spec §2, §7.1).

The LLM (Hermes) drives the pipeline by calling this CLI. The work splits in two:

  Phase 1 (this module, mechanical): for each active analyst, search YouTube,
  dedup by youtube_id, fetch transcripts, store new interviews. ZERO content work.

  Phase 2 (LLM-driven): the LLM reads each pending transcript, returns prediction
  JSON, and calls ``extract.store_predictions`` to validate-and-store it. The LLM
  uses ``--pending`` here to find interviews awaiting extraction.

Run from the monorepo root, e.g. ``python3 -m trading.analyst_radar.pipeline --phase-1``.
"""
import argparse
import sys

from .db import get_db, init_db, seed_analysts, _now
from . import search


def _start_run(conn, phase: str) -> int:
    cur = conn.execute(
        "INSERT INTO pipeline_runs (phase, started_at, status) VALUES (?, ?, 'running')",
        (phase, _now()),
    )
    conn.commit()
    return cur.lastrowid


def _finish_run(conn, run_id: int, *, found=0, new=0, predictions=0,
                status="completed", error=None) -> None:
    conn.execute(
        """UPDATE pipeline_runs
              SET finished_at = ?, interviews_found = ?, interviews_new = ?,
                  predictions_found = ?, status = ?, error_message = ?
            WHERE id = ?""",
        (_now(), found, new, predictions, status, error, run_id),
    )
    conn.commit()


def run_phase1(conn=None) -> dict:
    """Search + dedup + transcript + store for every active analyst.

    Returns {"interviews_found", "interviews_new"}. A per-analyst search failure
    is recorded but does not abort the whole run.
    """
    conn = conn or get_db()
    run_id = _start_run(conn, "phase-1")
    found = new = 0
    try:
        api = search._api()
        analysts = conn.execute(
            "SELECT id, name FROM analysts WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        for a in analysts:
            try:
                candidates = search.search_analyst_interviews(a["name"], api=api)
            except Exception as e:
                print(f"  ! search failed for {a['name']}: {e}", file=sys.stderr)
                continue
            for cand in candidates:
                found += 1
                # Skip transcript fetch if we already know this video.
                known = conn.execute(
                    "SELECT 1 FROM interviews WHERE youtube_id = ?",
                    (cand["youtube_id"],),
                ).fetchone()
                if known:
                    continue
                transcript = search.fetch_transcript(cand["youtube_id"], api=api)
                if search.store_interview(conn, cand, transcript):
                    new += 1
                    flag = "" if transcript else " (no transcript)"
                    print(f"  + {a['name']}: {cand['title'][:70]}{flag}")
        _finish_run(conn, run_id, found=found, new=new)
    except Exception as e:
        _finish_run(conn, run_id, found=found, new=new, status="failed", error=str(e))
        raise
    return {"interviews_found": found, "interviews_new": new}


def pending_extractions(conn=None) -> list[dict]:
    """Interviews with a transcript but no predictions yet — Phase 2's worklist."""
    conn = conn or get_db()
    rows = conn.execute(
        """SELECT i.id, i.youtube_id, i.title, i.channel_name, i.published_date
             FROM interviews i
            WHERE i.transcript_text IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM predictions p WHERE p.interview_id = i.id)
            ORDER BY i.published_date DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Analyst Radar pipeline")
    ap.add_argument("--init", action="store_true", help="init schema + seed analysts")
    ap.add_argument("--phase-1", action="store_true", help="search/fetch/store interviews")
    ap.add_argument("--pending", action="store_true", help="list interviews awaiting extraction")
    args = ap.parse_args(argv)

    if args.init:
        conn = init_db()
        n = seed_analysts(conn)
        print(f"Initialized. {n} new analysts seeded.")
        conn.close()
        return 0

    if args.phase_1:
        result = run_phase1()
        print(f"Phase 1 complete: {result}")
        return 0

    if args.pending:
        for r in pending_extractions():
            print(f"[{r['id']}] {r['published_date']}  {r['title']}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
