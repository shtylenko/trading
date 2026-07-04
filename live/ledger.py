"""Live ledger — SQLite (WAL) state store + kill switch (DESIGN §10.1, §17).

Authority for live state lives HERE, not in the backtest engine (session-isolated,
can't hold multi-day positions) and NOT in lab's research DuckDB. SQLite with WAL +
busy_timeout is the P0/P1 store (single-writer via the engine); migrate to Postgres
before serious live.

P0 implements the subset needed by the control-plane skeleton: schema init, the
kill-switch flags (mirrored to a disk file so the engine can check it even if the DB
is down), and rebalance-run + target-book snapshot persistence. Order/fill/approval
tables are declared now and exercised in P1.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from trading.live.config import EnvConfig, load_env_config

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS flags (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id TEXT PRIMARY KEY,
    release_id   TEXT NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'paper',
    status       TEXT NOT NULL DEFAULT 'active',
    code_hash    TEXT,
    universe     TEXT,
    capital      REAL DEFAULT 0,
    fractional   INTEGER DEFAULT 0,   -- 1 → size entries in fractional shares
    secret_handle TEXT,               -- env handle for this account's broker keys
    account_id_hash TEXT,             -- expected broker account identity (invariant #3)
    manifest     TEXT,                -- pinned ReleaseManifest JSON
    approval_policy TEXT,             -- JSON
    risk_policy  TEXT,                -- JSON
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rebalance_runs (
    run_id        TEXT PRIMARY KEY,
    portfolio_id  TEXT,
    release_id    TEXT NOT NULL,
    asof          TEXT NOT NULL,
    mode          TEXT NOT NULL,
    state         TEXT NOT NULL,
    code_hash     TEXT,
    snapshot_hash TEXT,
    target_book   TEXT,            -- JSON: [{ticker, rank, score, reason}, ...]
    blocked       TEXT,            -- JSON: [{ticker, reason}, ...] (tradability/denylist)
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS denylist (
    symbol TEXT NOT NULL, reason TEXT, scope TEXT NOT NULL DEFAULT 'platform',
    expires TEXT, added_by TEXT, added_at TEXT NOT NULL,
    PRIMARY KEY (symbol, scope)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, detail TEXT
);

-- ── P1: order lifecycle, fills, positions, approvals ──
CREATE TABLE IF NOT EXISTS order_proposals (
    proposal_id  TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    portfolio_id TEXT,
    state        TEXT NOT NULL,        -- created | executing | complete | blocked
    orders       TEXT NOT NULL,        -- JSON: classified orders
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id     TEXT PRIMARY KEY,
    proposal_id     TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    status          TEXT NOT NULL,     -- pending | approved | rejected | expired
    expires_at      TEXT NOT NULL,
    decided_at      TEXT, decided_by TEXT,
    created_at      TEXT NOT NULL
);

-- the idempotency spine: one row per intended order, keyed by client_order_id
CREATE TABLE IF NOT EXISTS order_intents (
    client_order_id TEXT PRIMARY KEY,
    run_id          TEXT, portfolio_id TEXT,
    ticker TEXT NOT NULL, side TEXT NOT NULL, qty REAL NOT NULL,
    status          TEXT NOT NULL,     -- intent | submitted | partially_filled | filled | rejected | canceled | unknown
    broker_order_id TEXT,
    filled_qty REAL DEFAULT 0, filled_avg_price REAL,
    reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT NOT NULL, portfolio_id TEXT,
    ticker TEXT NOT NULL, side TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL,
    filled_at TEXT NOT NULL
);

-- positions ledger: hold-day authority, sourced from fills (DESIGN §10.2)
CREATE TABLE IF NOT EXISTS positions (
    portfolio_id TEXT NOT NULL, ticker TEXT NOT NULL,
    qty REAL NOT NULL, avg_entry_price REAL NOT NULL,
    entry_date TEXT, updated_at TEXT NOT NULL,
    PRIMARY KEY (portfolio_id, ticker)
);

-- ── P2: parity audit, cash events, corporate actions ──
CREATE TABLE IF NOT EXISTS parity_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, portfolio_id TEXT,
    signal_match_pct REAL, slippage_bps REAL, drift INTEGER NOT NULL DEFAULT 0,
    detail TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL, amount REAL NOT NULL, reason TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corp_actions_applied (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT, symbol TEXT NOT NULL, ca_type TEXT NOT NULL,
    detail TEXT, status TEXT NOT NULL DEFAULT 'applied', applied_at TEXT NOT NULL
);

-- equity (NAV) time series for the portfolio-detail chart. One row per refresh/snapshot;
-- equity is the broker account NAV (valid as portfolio NAV under the one-account-per-
-- portfolio identity invariant). Populated by the `refresh` action (CLI + web button).
CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL,
    positions_value REAL,
    source TEXT,
    UNIQUE (portfolio_id, ts)
);

-- portfolio vs SPY performance (computed on refresh): close-to-close daily + total since
-- inception (portfolio total uses Alpaca base_value; SPY is price return, same window).
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    base_value REAL,
    port_total_pct REAL,
    port_daily_pct REAL,
    port_30d_pct REAL,
    spy_total_pct REAL,
    spy_daily_pct REAL,
    spy_30d_pct REAL,
    daily_json TEXT
);
"""

SCHEMA_VERSION = 4
_KILL_KEY_GLOBAL = "kill_switch:global"


def _kill_key(portfolio_id: str | None) -> str:
    return _KILL_KEY_GLOBAL if portfolio_id is None else f"kill_switch:{portfolio_id}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(env: EnvConfig | None = None):
    """Open the live DB with WAL + busy_timeout. One writer at a time (engine)."""
    env = env or load_env_config()
    env.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(env.db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.executescript(SCHEMA)
        _migrate_columns(conn)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", [SCHEMA_VERSION])


def _migrate_columns(conn) -> None:
    """Idempotently add columns missing from pre-existing tables (CREATE IF NOT EXISTS
    never alters an existing table). Each entry is safe to run on every startup."""
    additions = {
        "portfolios": [("fractional", "INTEGER DEFAULT 0")],
        "positions": [("last_price", "REAL"), ("last_price_at", "TEXT")],
        "performance_snapshots": [("port_30d_pct", "REAL"), ("spy_30d_pct", "REAL"),
                                  ("daily_json", "TEXT")],
    }
    for table, cols in additions.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, decl in cols:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


# ── Audit log ────────────────────────────────────────────────────────────────

def audit(action: str, *, actor: str = "system", detail: str = "",
          env: EnvConfig | None = None) -> None:
    """Append an actor+action record (DESIGN §13 — every control action is audited)."""
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute("INSERT INTO audit_log (ts, actor, action, detail) VALUES (?,?,?,?)",
                     [_now(), actor, action, detail])


def recent_audit(n: int = 50, env: EnvConfig | None = None) -> list[dict]:
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", [n]).fetchall()
        return [dict(r) for r in rows]


# ── Kill switch — per-portfolio + global (DB + disk file) ─────────────────────
# The global disk file is the fail-safe checked before any submit; per-portfolio
# kills live in the DB flags table. The engine treats a run as blocked if EITHER
# the global kill OR that portfolio's kill is active.

def _kill_file(env: EnvConfig) -> Path:
    return env.state_dir / "KILL_SWITCH"


def set_kill_switch(active: bool, *, portfolio_id: str | None = None, actor: str = "system",
                    env: EnvConfig | None = None) -> None:
    """Trip/reset a kill. ``portfolio_id=None`` = global (also writes the disk mirror)."""
    env = env or load_env_config()
    env.state_dir.mkdir(parents=True, exist_ok=True)
    key = _kill_key(portfolio_id)
    scope = "global" if portfolio_id is None else portfolio_id
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO flags (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            [key, "1" if active else "0", _now()],
        )
        conn.execute("INSERT INTO audit_log (ts, actor, action, detail) VALUES (?,?,?,?)",
                     [_now(), actor, "kill_switch",
                      f"{scope}:{'active' if active else 'reset'}"])
    if portfolio_id is None:    # disk mirror only for the global kill (DB-outage fail-safe)
        kf = _kill_file(env)
        if active:
            kf.write_text(f"tripped_at={_now()} by={actor}\n")
        elif kf.exists():
            kf.unlink()


def is_kill_switch_active(portfolio_id: str | None = None, env: EnvConfig | None = None) -> bool:
    """True if the GLOBAL kill is set (DB or disk) OR this portfolio's own kill is set."""
    env = env or load_env_config()
    if _kill_file(env).exists():
        return True
    try:
        with connect(env) as conn:
            keys = [_KILL_KEY_GLOBAL]
            if portfolio_id is not None:
                keys.append(_kill_key(portfolio_id))
            rows = conn.execute(
                f"SELECT value FROM flags WHERE key IN ({','.join('?' * len(keys))})", keys
            ).fetchall()
            return any(r["value"] == "1" for r in rows)
    except sqlite3.Error:
        # DB unreachable but no kill file → do not fabricate a trip; the engine's
        # own invariants still gate. (A real outage surfaces via health alerts.)
        return False


# ── Run + target-book snapshot persistence (P0) ──

def record_run(run_id: str, *, release_id: str, asof: date, mode: str, state: str,
               code_hash: str | None = None, snapshot_hash: str | None = None,
               target_book: list | None = None, blocked: list | None = None,
               portfolio_id: str | None = None, env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO rebalance_runs (run_id, portfolio_id, release_id, asof, mode, state, "
            "code_hash, snapshot_hash, target_book, blocked, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(run_id) DO UPDATE SET state=excluded.state, "
            "target_book=excluded.target_book, blocked=excluded.blocked",
            [run_id, portfolio_id, release_id, asof.isoformat(), mode, state,
             code_hash, snapshot_hash,
             json.dumps(target_book or []), json.dumps(blocked or []), _now()],
        )


def latest_run(env: EnvConfig | None = None, portfolio_id: str | None = None) -> dict | None:
    """Most recent run. Pass ``portfolio_id`` to scope it to one portfolio (the usual
    case — the global form leaks one portfolio's run/book into another's views)."""
    env = env or load_env_config()
    with connect(env) as conn:
        if portfolio_id is None:
            row = conn.execute(
                "SELECT * FROM rebalance_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM rebalance_runs WHERE portfolio_id=? ORDER BY created_at DESC LIMIT 1",
                [portfolio_id]).fetchone()
        return dict(row) if row else None


# ── P1: proposals + approvals ─────────────────────────────────────────────────

def create_proposal(proposal_id: str, *, run_id: str, portfolio_id: str | None,
                    orders: list, env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO order_proposals "
            "(proposal_id, run_id, portfolio_id, state, orders, created_at) VALUES (?,?,?,?,?,?)",
            [proposal_id, run_id, portfolio_id, "created", json.dumps(orders), _now()])


def set_proposal_state(proposal_id: str, state: str, env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute("UPDATE order_proposals SET state=? WHERE proposal_id=?", [state, proposal_id])


def create_approval(approval_id: str, *, proposal_id: str, client_order_id: str, ticker: str,
                    expires_at: str, env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO approvals (approval_id, proposal_id, client_order_id, ticker, "
            "status, expires_at, created_at) VALUES (?,?,?,?,?,?,?)",
            [approval_id, proposal_id, client_order_id, ticker, "pending", expires_at, _now()])


def decide_approval(approval_id: str, status: str, *, by: str = "user",
                    env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute("UPDATE approvals SET status=?, decided_at=?, decided_by=? WHERE approval_id=?",
                     [status, _now(), by, approval_id])


def expire_stale_approvals(now_iso: str | None = None, env: EnvConfig | None = None) -> int:
    """Flip pending approvals whose expiry has passed → 'expired'. Returns count."""
    env = env or load_env_config()
    now_iso = now_iso or _now()
    with connect(env) as conn:
        cur = conn.execute(
            "UPDATE approvals SET status='expired', decided_at=? "
            "WHERE status='pending' AND expires_at <= ?", [now_iso, now_iso])
        return cur.rowcount


def approved_client_order_ids(proposal_id: str, now_iso: str | None = None,
                              env: EnvConfig | None = None) -> set[str]:
    """Approved AND still fresh (not past expiry) — stale fills kill edge (DESIGN §7)."""
    env = env or load_env_config()
    now_iso = now_iso or _now()
    with connect(env) as conn:
        rows = conn.execute(
            "SELECT client_order_id FROM approvals "
            "WHERE proposal_id=? AND status='approved' AND expires_at > ?",
            [proposal_id, now_iso]).fetchall()
        return {r["client_order_id"] for r in rows}


# ── P1: order intents (idempotency spine), fills, positions ──────────────────

def has_submitted_intent(client_order_id: str, env: EnvConfig | None = None) -> bool:
    """True if this order was already submitted (any non-'intent' state) — anti double-submit."""
    env = env or load_env_config()
    with connect(env) as conn:
        row = conn.execute("SELECT status FROM order_intents WHERE client_order_id=?",
                           [client_order_id]).fetchone()
        return bool(row and row["status"] != "intent")


def record_intent(client_order_id: str, *, run_id: str, portfolio_id: str | None,
                  ticker: str, side: str, qty: float, reason: str = "",
                  env: EnvConfig | None = None) -> bool:
    """Insert an intent BEFORE submitting. Idempotent: returns False if it already exists."""
    env = env or load_env_config()
    with connect(env) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO order_intents (client_order_id, run_id, portfolio_id, ticker, "
            "side, qty, status, reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [client_order_id, run_id, portfolio_id, ticker, side, qty, "intent", reason,
             _now(), _now()])
        return cur.rowcount == 1


def update_intent(client_order_id: str, *, status: str, broker_order_id: str | None = None,
                  filled_qty: float | None = None, filled_avg_price: float | None = None,
                  env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    sets, vals = ["status=?", "updated_at=?"], [status, _now()]
    if broker_order_id is not None:
        sets.append("broker_order_id=?"); vals.append(broker_order_id)
    if filled_qty is not None:
        sets.append("filled_qty=?"); vals.append(filled_qty)
    if filled_avg_price is not None:
        sets.append("filled_avg_price=?"); vals.append(filled_avg_price)
    vals.append(client_order_id)
    with connect(env) as conn:
        conn.execute(f"UPDATE order_intents SET {', '.join(sets)} WHERE client_order_id=?", vals)


def record_fill(client_order_id: str, *, portfolio_id: str | None, ticker: str, side: str,
                qty: float, price: float, env: EnvConfig | None = None) -> None:
    """Record a fill and update the positions ledger (hold-day authority)."""
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO fills (client_order_id, portfolio_id, ticker, side, qty, price, filled_at) "
            "VALUES (?,?,?,?,?,?,?)",
            [client_order_id, portfolio_id, ticker, side, qty, price, _now()])
        row = conn.execute(
            "SELECT qty, avg_entry_price, entry_date FROM positions WHERE portfolio_id=? AND ticker=?",
            [portfolio_id, ticker]).fetchone()
        signed = qty if side == "buy" else -qty
        if row is None:
            if side == "buy":
                conn.execute(
                    "INSERT INTO positions (portfolio_id, ticker, qty, avg_entry_price, entry_date, "
                    "updated_at) VALUES (?,?,?,?,?,?)",
                    [portfolio_id, ticker, qty, price, _now()[:10], _now()])
        else:
            new_qty = row["qty"] + signed
            if new_qty <= 1e-9:
                conn.execute("DELETE FROM positions WHERE portfolio_id=? AND ticker=?",
                             [portfolio_id, ticker])
            else:
                avg = row["avg_entry_price"]
                if side == "buy":
                    avg = (row["avg_entry_price"] * row["qty"] + price * qty) / new_qty
                conn.execute(
                    "UPDATE positions SET qty=?, avg_entry_price=?, updated_at=? "
                    "WHERE portfolio_id=? AND ticker=?",
                    [new_qty, avg, _now(), portfolio_id, ticker])


def get_positions(portfolio_id: str, env: EnvConfig | None = None) -> dict[str, dict]:
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute("SELECT * FROM positions WHERE portfolio_id=?", [portfolio_id]).fetchall()
        return {r["ticker"]: dict(r) for r in rows}


def update_position_prices(portfolio_id: str, prices: dict[str, float], *,
                           ts: str | None = None, env: EnvConfig | None = None) -> int:
    """Stamp the latest market price onto held positions (for current-value display).

    Only updates rows that exist; unknown tickers are ignored. Returns rows touched."""
    env = env or load_env_config()
    ts = ts or _now()
    n = 0
    with connect(env) as conn:
        for ticker, px in prices.items():
            if px is None or px <= 0:
                continue
            cur = conn.execute(
                "UPDATE positions SET last_price=?, last_price_at=? WHERE portfolio_id=? AND ticker=?",
                [float(px), ts, portfolio_id, ticker])
            n += cur.rowcount
    return n


def record_equity_snapshot(portfolio_id: str, *, equity: float, cash: float | None = None,
                           positions_value: float | None = None, source: str = "manual",
                           ts: str | None = None, env: EnvConfig | None = None) -> None:
    """Append a NAV point for the equity chart (idempotent on (portfolio_id, ts))."""
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO equity_snapshots "
            "(portfolio_id, ts, equity, cash, positions_value, source) VALUES (?,?,?,?,?,?)",
            [portfolio_id, ts or _now(), float(equity),
             None if cash is None else float(cash),
             None if positions_value is None else float(positions_value), source])


def equity_series(portfolio_id: str, *, limit: int = 365,
                  env: EnvConfig | None = None) -> list[dict]:
    """Equity snapshots oldest→newest (last ``limit`` points) for the chart."""
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute(
            "SELECT ts, equity, cash, positions_value, source FROM equity_snapshots "
            "WHERE portfolio_id=? ORDER BY ts DESC LIMIT ?", [portfolio_id, limit]).fetchall()
        return [dict(r) for r in reversed(rows)]


def record_performance(portfolio_id: str, *, base_value: float | None = None,
                       port_total_pct: float | None = None, port_daily_pct: float | None = None,
                       port_30d_pct: float | None = None, spy_total_pct: float | None = None,
                       spy_daily_pct: float | None = None, spy_30d_pct: float | None = None,
                       daily_json: str | None = None,
                       ts: str | None = None, env: EnvConfig | None = None) -> None:
    """Append a portfolio-vs-SPY performance point (computed on refresh)."""
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO performance_snapshots (portfolio_id, ts, base_value, port_total_pct, "
            "port_daily_pct, port_30d_pct, spy_total_pct, spy_daily_pct, spy_30d_pct, daily_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [portfolio_id, ts or _now(), base_value, port_total_pct, port_daily_pct,
             port_30d_pct, spy_total_pct, spy_daily_pct, spy_30d_pct, daily_json])


def latest_performance(portfolio_id: str, env: EnvConfig | None = None) -> dict | None:
    """Most recent portfolio-vs-SPY performance row, or None if never computed."""
    env = env or load_env_config()
    with connect(env) as conn:
        r = conn.execute("SELECT * FROM performance_snapshots WHERE portfolio_id=? "
                         "ORDER BY ts DESC LIMIT 1", [portfolio_id]).fetchone()
        return dict(r) if r else None


def open_intents(portfolio_id: str, env: EnvConfig | None = None) -> list[dict]:
    """Order intents that may still need a fill update — anything not in a terminal,
    fully-booked state. Used by the fill-sync poll (P1 stand-in for the trade stream)."""
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute(
            "SELECT client_order_id, run_id, ticker, side, qty, status, filled_qty "
            "FROM order_intents WHERE portfolio_id=? AND status NOT IN ('rejected','canceled') "
            "AND (status != 'filled' OR filled_qty IS NULL OR filled_qty < qty)",
            [portfolio_id]).fetchall()
        return [dict(r) for r in rows]


def filled_qty_recorded(client_order_id: str, env: EnvConfig | None = None) -> float:
    """Total fill qty already booked to the fills ledger for an order (for delta sync)."""
    env = env or load_env_config()
    with connect(env) as conn:
        row = conn.execute("SELECT COALESCE(SUM(qty),0) AS q FROM fills WHERE client_order_id=?",
                           [client_order_id]).fetchone()
        return float(row["q"] or 0.0)


# ── P2: parity results ───────────────────────────────────────────────────────

def record_parity(run_id: str, portfolio_id: str, *, signal_match_pct: float | None,
                  slippage_bps: float | None, drift: bool, detail: dict | None = None,
                  env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO parity_results (run_id, portfolio_id, signal_match_pct, slippage_bps, "
            "drift, detail, created_at) VALUES (?,?,?,?,?,?,?)",
            [run_id, portfolio_id, signal_match_pct, slippage_bps, 1 if drift else 0,
             json.dumps(detail or {}), _now()])


def recent_parity(portfolio_id: str, n: int = 2, env: EnvConfig | None = None) -> list[dict]:
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute(
            "SELECT * FROM parity_results WHERE portfolio_id=? ORDER BY id DESC LIMIT ?",
            [portfolio_id, n]).fetchall()
        return [dict(r) for r in rows]


def parity_drift_active(portfolio_id: str, consecutive: int = 2,
                        env: EnvConfig | None = None) -> bool:
    """True if the last ``consecutive`` parity results all flagged drift (DESIGN §12)."""
    rows = recent_parity(portfolio_id, consecutive, env=env)
    return len(rows) >= consecutive and all(r["drift"] for r in rows)


# ── P2: cash events + corporate actions ──────────────────────────────────────

def credit_cash(portfolio_id: str, amount: float, reason: str, env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute("INSERT INTO cash_events (portfolio_id, amount, reason, created_at) "
                     "VALUES (?,?,?,?)", [portfolio_id, amount, reason, _now()])


def get_cash(portfolio_id: str, env: EnvConfig | None = None) -> float:
    env = env or load_env_config()
    with connect(env) as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM cash_events WHERE portfolio_id=?",
                           [portfolio_id]).fetchone()
        return float(row["s"])


def apply_split(portfolio_id: str, symbol: str, ratio: float, env: EnvConfig | None = None) -> bool:
    """Adjust a held position for a split (qty*ratio, avg_price/ratio). True if applied."""
    if ratio <= 0:
        return False
    env = env or load_env_config()
    with connect(env) as conn:
        row = conn.execute("SELECT qty, avg_entry_price FROM positions WHERE portfolio_id=? AND ticker=?",
                           [portfolio_id, symbol]).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE positions SET qty=?, avg_entry_price=?, updated_at=? "
            "WHERE portfolio_id=? AND ticker=?",
            [row["qty"] * ratio, row["avg_entry_price"] / ratio, _now(), portfolio_id, symbol])
        return True


def active_denylist(portfolio_id: str, asof: date, env: EnvConfig | None = None) -> list:
    """DB denylist entries in force for this portfolio (scope=platform OR this portfolio),
    excluding expired ones. Returned as ``DenylistEntry`` to merge with the YAML baseline."""
    from trading.live.denylist import DenylistEntry
    env = env or load_env_config()
    with connect(env) as conn:
        rows = conn.execute("SELECT * FROM denylist WHERE scope IN ('platform', ?)",
                            [portfolio_id]).fetchall()
    out = []
    for r in rows:
        exp = date.fromisoformat(r["expires"]) if r["expires"] else None
        e = DenylistEntry(symbol=r["symbol"], reason=r["reason"] or "", scope=r["scope"],
                          expires=exp, added_by=r["added_by"])
        if e.active_on(asof):
            out.append(e)
    return out


def add_denylist_entry(symbol: str, reason: str, *, scope: str = "platform",
                       expires: str | None = None, added_by: str = "user",
                       env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO denylist (symbol, reason, scope, expires, added_by, added_at) "
            "VALUES (?,?,?,?,?,?)", [symbol.upper(), reason, scope, expires, added_by, _now()])
    audit("denylist.add", actor=added_by, detail=f"{symbol} scope={scope}", env=env)


def record_corp_action(portfolio_id: str, symbol: str, ca_type: str, *, detail: dict | None = None,
                       status: str = "applied", env: EnvConfig | None = None) -> None:
    env = env or load_env_config()
    with connect(env) as conn:
        conn.execute(
            "INSERT INTO corp_actions_applied (portfolio_id, symbol, ca_type, detail, status, "
            "applied_at) VALUES (?,?,?,?,?,?)",
            [portfolio_id, symbol, ca_type, json.dumps(detail or {}), status, _now()])
