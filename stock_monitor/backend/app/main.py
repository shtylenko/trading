"""
backend/app/main.py — Webull Stock Monitor local backend (FastAPI version)

NOTE (2026-07-02): User prefers MINIMAL backend focused on writing local JSON files.
receiver.py is the primary path (closed candles only, active timeframe, multi-tab safe).
This FastAPI version is kept only for reference.

Run the preferred one with:  ./run.sh   (defaults to minimal)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Any
import time
import sqlite3
import os
from datetime import datetime

# --- Config ---
DB_PATH = os.environ.get("DB_PATH", "./data/stock_monitor.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

app = FastAPI(title="stock-monitor-backend", version="0.1.0")

# Allow only local calls (tighten later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],  # during dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---

class Candle(BaseModel):
    t: int = Field(..., description="Bar timestamp (ms since epoch)")
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

class CandleBatch(BaseModel):
    symbol: str
    timeframe: str
    captured_at: Optional[str] = None
    candles: List[Candle]

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str

# --- DB helpers (sync for v1 simplicity) ---

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY,
            ticker TEXT UNIQUE NOT NULL,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timeframes (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            minutes INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY,
            symbol_id INTEGER NOT NULL,
            timeframe_id INTEGER NOT NULL,
            ts INTEGER NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT DEFAULT 'webull-web',
            captured_at TEXT,
            raw TEXT,
            UNIQUE(symbol_id, timeframe_id, ts)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_sym_tf_ts ON candles(symbol_id, timeframe_id, ts)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_ts ON candles(ts)")

    # Seed common timeframes
    tfs = [
        ("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30),
        ("1h", 60), ("4h", 240), ("1d", None), ("1w", None),
    ]
    for code, mins in tfs:
        cur.execute(
            "INSERT OR IGNORE INTO timeframes(code, minutes) VALUES (?, ?)",
            (code, mins)
        )
    conn.commit()
    conn.close()

init_db()

def get_or_create_symbol(ticker: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("SELECT id FROM symbols WHERE ticker = ?", (ticker.upper(),))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE symbols SET last_seen = ? WHERE id = ?", (now, row["id"]))
        conn.commit()
        sid = row["id"]
    else:
        cur.execute(
            "INSERT INTO symbols(ticker, first_seen, last_seen) VALUES (?, ?, ?)",
            (ticker.upper(), now, now)
        )
        sid = cur.lastrowid
        conn.commit()
    conn.close()
    return sid

def get_or_create_timeframe(code: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    norm = normalize_tf(code)
    cur.execute("SELECT id FROM timeframes WHERE code = ?", (norm,))
    row = cur.fetchone()
    if row:
        tfid = row["id"]
    else:
        cur.execute("INSERT INTO timeframes(code) VALUES (?)", (norm,))
        tfid = cur.lastrowid
        conn.commit()
    conn.close()
    return tfid

def normalize_tf(raw: str) -> str:
    s = (raw or "").lower().strip().replace("min", "m").replace(" ", "")
    mapping = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1h", "m1": "1m", "m5": "5m", "m15": "15m",
        "h1": "1h", "d": "1d", "day": "1d", "w": "1w", "week": "1w",
    }
    return mapping.get(s, s or "1m")

def upsert_candles(symbol: str, tf: str, candles: List[dict], captured_at: str):
    if not candles:
        return {"inserted": 0, "updated": 0}

    conn = get_conn()
    cur = conn.cursor()
    sid = get_or_create_symbol(symbol)
    tfid = get_or_create_timeframe(tf)

    inserted = 0
    updated = 0

    for c in candles:
        try:
            cur.execute("""
                INSERT INTO candles(symbol_id, timeframe_id, ts, open, high, low, close, volume, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol_id, timeframe_id, ts) DO UPDATE SET
                    open=excluded.open,
                    high=MAX(high, excluded.high),
                    low=MIN(low, excluded.low),
                    close=excluded.close,
                    volume=excluded.volume,
                    captured_at=excluded.captured_at
            """, (
                sid, tfid, int(c["t"]),
                float(c["o"]), float(c["h"]), float(c["l"]), float(c["c"]),
                float(c.get("v", 0) or 0),
                captured_at
            ))
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            print("upsert error", e)

    conn.commit()
    conn.close()
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}

# --- Routes ---

@app.get("/api/health", response_model=HealthResponse)
def health():
    try:
        conn = get_conn()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "version": "0.1.0", "db": db_status}

@app.post("/api/candles")
def post_candles(batch: CandleBatch):
    captured = batch.captured_at or datetime.utcnow().isoformat()
    result = upsert_candles(
        batch.symbol,
        batch.timeframe,
        [c.model_dump() for c in batch.candles],
        captured,
    )
    return {"ok": True, **result}

@app.get("/api/candles")
def get_candles(
    symbol: str,
    tf: str = "5m",
    limit: int = 500,
    since: Optional[int] = None,
    until: Optional[int] = None,
):
    conn = get_conn()
    cur = conn.cursor()
    sid = get_or_create_symbol(symbol)  # creates if new (harmless)
    tfid = get_or_create_timeframe(tf)

    q = """
        SELECT ts, open, high, low, close, volume, captured_at
        FROM candles
        WHERE symbol_id = ? AND timeframe_id = ?
    """
    args = [sid, tfid]
    if since:
        q += " AND ts >= ?"
        args.append(since)
    if until:
        q += " AND ts <= ?"
        args.append(until)
    q += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)

    rows = cur.execute(q, args).fetchall()
    conn.close()

    data = [
        {
            "t": r["ts"],
            "o": r["open"],
            "h": r["high"],
            "l": r["low"],
            "c": r["close"],
            "v": r["volume"],
            "captured_at": r["captured_at"],
        }
        for r in reversed(rows)  # return ascending
    ]
    return {"symbol": symbol.upper(), "timeframe": normalize_tf(tf), "count": len(data), "candles": data}

@app.get("/api/symbols")
def list_symbols():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.ticker, MAX(c.ts) as last_ts, COUNT(c.id) as n
        FROM symbols s
        LEFT JOIN candles c ON c.symbol_id = s.id
        GROUP BY s.id
        ORDER BY last_ts DESC NULLS LAST
    """).fetchall()
    conn.close()
    return [
        {"symbol": r["ticker"], "last_ts": r["last_ts"], "candle_count": r["n"]}
        for r in rows
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)
