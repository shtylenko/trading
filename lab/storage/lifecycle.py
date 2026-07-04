"""Read/write access to the ``release_lifecycle`` ledger.

A release's position on the evaluation ladder (see ``validation/funnel.py``)
is mutable state — it changes every time a run advances or kills the release —
so it lives in DuckDB, never as an attribute on the immutable release module.
(Putting it in the module would also change the file bytes and falsely flip
every prior run's code-signature freshness badge.)

A release with no row has never been evaluated: treat it as stage 0, active.
"""

from __future__ import annotations

from datetime import datetime, timezone

from trading.lab.validation.funnel import DISPOSITION_ACTIVE

# Columns selected/returned as a dict by the read helpers below.
_COLS = (
    "release_id", "stage", "disposition", "killed_stage",
    "reason", "decided_by_run", "updated_at",
)


def _default_row(release_id: str) -> dict:
    return {
        "release_id": release_id,
        "stage": 0,
        "disposition": DISPOSITION_ACTIVE,
        "killed_stage": None,
        "reason": None,
        "decided_by_run": None,
        "updated_at": None,
    }


def get_lifecycle(conn, release_id: str) -> dict:
    """Lifecycle row for one release, or the stage-0/active default if absent."""
    row = conn.execute(
        f"SELECT {', '.join(_COLS)} FROM release_lifecycle WHERE release_id = ?",
        [release_id],
    ).fetchone()
    if row is None:
        return _default_row(release_id)
    return dict(zip(_COLS, row))


def list_lifecycle(conn) -> dict[str, dict]:
    """All lifecycle rows, keyed by release_id (only releases with a row)."""
    rows = conn.execute(
        f"SELECT {', '.join(_COLS)} FROM release_lifecycle"
    ).fetchall()
    return {r[0]: dict(zip(_COLS, r)) for r in rows}


def upsert_lifecycle(
    conn,
    release_id: str,
    *,
    stage: int,
    disposition: str,
    killed_stage: int | None = None,
    reason: str | None = None,
    decided_by_run: str | None = None,
    updated_at: datetime | None = None,
) -> None:
    """Insert or replace the lifecycle row for a release."""
    conn.execute(
        """
        INSERT OR REPLACE INTO release_lifecycle (
            release_id, stage, disposition, killed_stage,
            reason, decided_by_run, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            release_id, stage, disposition, killed_stage,
            reason, decided_by_run, updated_at or datetime.now(timezone.utc),
        ],
    )
