"""
Validate-and-store side of prediction extraction (spec §5, §5.2, §5.5).

ABSOLUTE BOUNDARY: this module does ZERO content analysis. No keyword matching,
no regex extraction, no sentiment classification, no ticker heuristics. The LLM
(Hermes) reads the transcript and returns a JSON array of predictions; Python's
only jobs here are:

  - Structural validation of that JSON against the pydantic schema (§5.5).
  - Mechanical dedup of predictions via content_hash (§5.1).
  - Mechanical ticker validation against ``trading.marketdata`` — does a real
    instrument with this symbol trade? Valid → tickers + junction; invalid →
    unresolved_mentions (§5.2). This is set-membership, not an NLP judgement.

Python decides nothing about *meaning*.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .db import _now

PROMPT_VERSION = "v1"

_VALID_TYPES = {"price_target", "sector_call", "macro_call",
                "direction_call", "earnings_call", "other"}
_VALID_DIRECTIONS = {"bullish", "bearish", "neutral"}
_VALID_CONFIDENCE = {"high", "medium", "low"}


class PredictionItem(BaseModel):
    """One extracted prediction, as returned by the LLM (spec §5.5).

    Validators enforce the enum contract structurally — they reject out-of-set
    values; they never reinterpret content.
    """
    prediction_text: str = Field(min_length=1)
    prediction_type: str = "other"
    direction: str = "neutral"
    confidence: Optional[str] = None
    time_horizon: Optional[str] = None
    raw_quote: Optional[str] = None
    tickers: list[str] = Field(default_factory=list)

    @field_validator("prediction_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"prediction_type must be one of {sorted(_VALID_TYPES)}")
        return v

    @field_validator("direction")
    @classmethod
    def _check_direction(cls, v: str) -> str:
        if v not in _VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {sorted(_VALID_DIRECTIONS)}")
        return v

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_CONFIDENCE:
            raise ValueError(f"confidence must be null or one of {sorted(_VALID_CONFIDENCE)}")
        return v


def validate_predictions(items: list[dict]) -> list[PredictionItem]:
    """Structurally validate a raw LLM JSON array. Raises on schema violation."""
    return [PredictionItem.model_validate(it) for it in items]


def sanitize_ticker(raw: str) -> str:
    """Cosmetic only: strip + uppercase. No filtering, no rejection (spec §5)."""
    return raw.strip().upper()


def content_hash(interview_id: int, prediction_text: str) -> str:
    """SHA-256 of (interview_id, normalized text) — the dedup key (spec §5.1)."""
    key = f"{interview_id}\x00{prediction_text.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ── Ticker validation via marketdata (spec §5.2) ──────────────────────────────

def has_market_data(symbol: str) -> bool:
    """True iff trading.marketdata can return recent bars for the symbol.

    Mechanical existence check (does a real tradeable instrument carry this
    symbol?), not a semantic 'is this a ticker' judgement. Any failure to
    resolve — None, empty, or provider error — counts as 'not a ticker'.
    """
    try:
        from trading.marketdata import fetch_bars
    except Exception:
        # marketdata unavailable → cannot validate; treat as unresolved.
        return False
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=10)
    try:
        df = fetch_bars(symbol, "1day", start=start, end=end)
    except Exception:
        return False
    return df is not None and len(df) > 0


def _upsert_ticker(conn, symbol: str) -> int:
    """Return tickers.id for symbol, inserting it if new. Caller guarantees it
    validated. Already-present symbols skip re-validation (the table is the cache)."""
    cur = conn.execute("SELECT id FROM tickers WHERE ticker = ?", (symbol,))
    row = cur.fetchone()
    if row is not None:
        # Works with both tuple and sqlite3.Row (row_factory agnostic).
        return row[0]
    cur = conn.execute(
        "INSERT INTO tickers (ticker, created_at) VALUES (?, ?)",
        (symbol, _now()),
    )
    return cur.lastrowid


def _resolve_tickers(conn, prediction_id: int, raw_symbols: list[str]) -> None:
    """Validate each proposed symbol; link valid ones, queue the rest (§5.2)."""
    now = _now()
    seen: set[str] = set()
    for raw in raw_symbols:
        symbol = sanitize_ticker(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)

        # Already accumulated → trust the prior validation, just link.
        existing = conn.execute(
            "SELECT id FROM tickers WHERE ticker = ?", (symbol,)
        ).fetchone()
        if existing is not None or has_market_data(symbol):
            ticker_id = _upsert_ticker(conn, symbol)
            conn.execute(
                "INSERT OR IGNORE INTO prediction_tickers (prediction_id, ticker_id) "
                "VALUES (?, ?)",
                (prediction_id, ticker_id),
            )
        else:
            conn.execute(
                "INSERT INTO unresolved_mentions "
                "(prediction_id, raw_symbol, created_at) VALUES (?, ?, ?)",
                (prediction_id, symbol, now),
            )


def store_predictions(
    conn,
    interview_id: int,
    analyst_id: int,
    items: list[PredictionItem],
    model: Optional[str] = None,
    prompt_version: str = PROMPT_VERSION,
) -> int:
    """Persist validated predictions for one interview. Idempotent via
    content_hash (re-running Phase 2 does not duplicate). Returns count inserted."""
    inserted = 0
    now = _now()
    for item in items:
        chash = content_hash(interview_id, item.prediction_text)
        cur = conn.execute(
            """INSERT OR IGNORE INTO predictions
                   (interview_id, analyst_id, prediction_text, prediction_type,
                    direction, confidence, time_horizon, raw_quote,
                    content_hash, prompt_version, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (interview_id, analyst_id, item.prediction_text, item.prediction_type,
             item.direction, item.confidence, item.time_horizon, item.raw_quote,
             chash, prompt_version, model, now),
        )
        if cur.rowcount == 0:
            continue  # already stored (dedup hit) — skip ticker work too
        inserted += 1
        prediction_id = cur.lastrowid
        _resolve_tickers(conn, prediction_id, item.tickers)
    conn.commit()
    return inserted
