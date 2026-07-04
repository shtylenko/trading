"""
Prediction outcome scoring (spec §1.5c) — a pass separate from the daily fetch.

Like extraction, scoring is split: judging whether a call came true is content
work the LLM/analyst does; this module only supplies the mechanical worklist of
unscored predictions and stores the verdict the LLM returns.
"""
from typing import Optional

from .db import get_db, _now

_VALID_OUTCOMES = {"correct", "incorrect", "partial", "unresolvable"}


def unscored_predictions(conn=None) -> list[dict]:
    """Predictions with no outcome row yet — the scoring worklist.

    Time-horizon drives when a prediction is *evaluable*; that judgement is the
    LLM's, so this returns all unscored predictions with the context it needs.
    """
    conn = conn or get_db()
    rows = conn.execute(
        """SELECT p.id, p.prediction_text, p.prediction_type, p.direction,
                  p.time_horizon, p.raw_quote, p.created_at,
                  a.name AS analyst_name,
                  i.published_date,
                  GROUP_CONCAT(t.ticker, ', ') AS tickers
             FROM predictions p
             JOIN analysts a   ON p.analyst_id = a.id
             JOIN interviews i ON p.interview_id = i.id
        LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
        LEFT JOIN tickers t   ON pt.ticker_id = t.id
            WHERE NOT EXISTS (SELECT 1 FROM prediction_outcomes o
                               WHERE o.prediction_id = p.id)
            GROUP BY p.id
            ORDER BY i.published_date ASC"""
    ).fetchall()
    return [dict(r) for r in rows]


def store_outcome(
    conn,
    prediction_id: int,
    outcome: str,
    actual_value: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Record the LLM's verdict for one prediction (idempotent per prediction)."""
    if outcome not in _VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(_VALID_OUTCOMES)}")
    now = _now()
    conn.execute(
        """INSERT OR IGNORE INTO prediction_outcomes
               (prediction_id, outcome, actual_value, resolved_at, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (prediction_id, outcome, actual_value, now, notes, now),
    )
    conn.commit()


def scorecard(conn=None) -> list[dict]:
    """Per-analyst hit-rate over resolved outcomes (spec §7.2 `scorecard`)."""
    conn = conn or get_db()
    rows = conn.execute(
        """SELECT a.name AS analyst_name,
                  COUNT(*) AS scored,
                  SUM(o.outcome = 'correct')  AS correct,
                  SUM(o.outcome = 'partial')  AS partial,
                  SUM(o.outcome = 'incorrect') AS incorrect
             FROM prediction_outcomes o
             JOIN predictions p ON o.prediction_id = p.id
             JOIN analysts a    ON p.analyst_id = a.id
            WHERE o.outcome != 'unresolvable'
            GROUP BY a.id
            ORDER BY correct * 1.0 / COUNT(*) DESC"""
    ).fetchall()
    return [dict(r) for r in rows]
