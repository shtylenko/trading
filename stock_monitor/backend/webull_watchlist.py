"""
Sync new Gap'n'Go screener tickers into a Webull watchlist.

Uses the official Webull OpenAPI Python SDK, which exposes the same operations
as the Webull Cloud MCP tools:

  get_watchlists / get_watchlist
  create_watchlist
  get_watchlist_instruments
  add_watchlist_instruments
  remove_watchlist_instruments

Docs: https://developer.webull.com/apis/docs/AI-friendly-Resources/mcp/

Credentials (env or backend/.env):
  WEBULL_APP_KEY
  WEBULL_APP_SECRET
  WEBULL_ENVIRONMENT   (prod|uat, default from config)
  WEBULL_REGION_ID     (us, default)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CONFIG_PATH = Path(__file__).parent / "config" / "watchlist.json"
_lock = threading.RLock()
_db_path: Path | None = None
_client_factory: Callable[[], Any] | None = None  # test override

DEFAULT_CONFIG = {
    "enabled": True,
    "dry_run": False,
    # mcp_oauth  → Cloud MCP OAuth (browser login) — retail paper/live account
    # openapi_sdk → App key/secret OpenAPI SDK — developer sandbox/prod API
    "auth_mode": "mcp_oauth",
    "watchlist_name": "Today's Gap'n'Go",
    "screener_keys": ["gap-n-go"],
    "instrument_category": "US_STOCK",
    "reset_daily": True,
    "region_id": "us",
    # Only used when auth_mode=openapi_sdk
    "environment": "uat",
}


def _now_iso() -> str:
    return datetime.now(tz=NY).astimezone().isoformat()


def _session_date_today() -> str:
    return datetime.now(tz=NY).date().isoformat()


def load_dotenv() -> None:
    """Load backend/.env if present (optional)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.is_file():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    p = path or CONFIG_PATH
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    # Env overrides
    if os.environ.get("WEBULL_WATCHLIST_ENABLED") is not None:
        cfg["enabled"] = os.environ["WEBULL_WATCHLIST_ENABLED"].lower() in ("1", "true", "yes")
    if os.environ.get("WEBULL_WATCHLIST_DRY_RUN") is not None:
        cfg["dry_run"] = os.environ["WEBULL_WATCHLIST_DRY_RUN"].lower() in ("1", "true", "yes")
    if os.environ.get("WEBULL_WATCHLIST_NAME"):
        cfg["watchlist_name"] = os.environ["WEBULL_WATCHLIST_NAME"]
    if os.environ.get("WEBULL_REGION_ID"):
        cfg["region_id"] = os.environ["WEBULL_REGION_ID"]
    if os.environ.get("WEBULL_ENVIRONMENT"):
        cfg["environment"] = os.environ["WEBULL_ENVIRONMENT"]
    if os.environ.get("WEBULL_AUTH_MODE"):
        cfg["auth_mode"] = os.environ["WEBULL_AUTH_MODE"].strip().lower()
    return cfg


def make_client(cfg: dict | None = None) -> Any:
    """Build the active watchlist client from config (MCP OAuth or OpenAPI SDK)."""
    cfg = cfg or load_config()
    mode = str(cfg.get("auth_mode") or "mcp_oauth").lower().strip()
    dry = bool(cfg.get("dry_run"))

    if dry:
        return WebullWatchlistClient(data_client=None, dry_run=True)

    if mode in ("mcp_oauth", "mcp", "oauth", "cloud_mcp"):
        import webull_mcp
        # Ensure we have a token; raise a clear error if not logged in
        webull_mcp.get_valid_access_token()
        return webull_mcp.WebullMcpWatchlistClient()

    # Legacy / developer API path
    return WebullWatchlistClient.from_env(
        region_id=str(cfg.get("region_id") or "us"),
        environment=str(cfg.get("environment") or "uat"),
        dry_run=False,
    )


def set_db_path(path: Path | str) -> None:
    global _db_path
    _db_path = Path(path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    init_sync_db()


def get_db_path() -> Path:
    if _db_path is None:
        raise RuntimeError("watchlist db path not set")
    return _db_path


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_sync_db() -> None:
    with _lock:
        conn = _conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlist_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    watchlist_id TEXT,
                    watchlist_name TEXT,
                    session_date TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS watchlist_sync (
                    id INTEGER PRIMARY KEY,
                    session_date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    watchlist_id TEXT,
                    watchlist_name TEXT,
                    status TEXT NOT NULL,  -- pending|synced|error|dry_run|skipped
                    error TEXT,
                    attempts INTEGER DEFAULT 0,
                    first_seen_at TEXT NOT NULL,
                    last_attempt_at TEXT,
                    synced_at TEXT,
                    UNIQUE(session_date, ticker)
                );
                CREATE INDEX IF NOT EXISTS idx_watchlist_sync_status
                    ON watchlist_sync(status);
                """
            )
            conn.commit()
        finally:
            conn.close()


def _extract_data(response: Any) -> Any:
    if response is None:
        return None
    if hasattr(response, "json") and callable(response.json):
        try:
            return response.json()
        except Exception:
            return getattr(response, "content", response)
    return response


def _as_list(data: Any) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "result", "data", "watchlists", "instruments"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


class WebullWatchlistClient:
    """Thin wrapper around OpenAPI SDK watchlist methods (MCP-equivalent)."""

    def __init__(self, data_client: Any | None = None, dry_run: bool = False):
        self._data = data_client
        self.dry_run = dry_run
        self._calls: list[tuple[str, dict]] = []  # for dry-run / tests
        # In-memory state for dry-run so CLI add/remove/sync can be exercised offline
        self._dry_lists: dict[str, dict] = {}  # id -> {watchlist_id, name}
        self._dry_instruments: dict[str, dict[str, dict]] = {}  # id -> symbol -> instrument

    @classmethod
    def from_env(cls, region_id: str = "us", environment: str = "prod", dry_run: bool = False) -> "WebullWatchlistClient":
        load_dotenv()
        app_key = os.environ.get("WEBULL_APP_KEY", "").strip()
        app_secret = os.environ.get("WEBULL_APP_SECRET", "").strip()
        if dry_run or not app_key or not app_secret:
            return cls(data_client=None, dry_run=True)

        import logging
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient

        # Quiet noisy SDK request dumps on auth failures
        logging.getLogger("webull.core.client").setLevel(logging.CRITICAL)

        env = (environment or "prod").lower().strip()
        # Official hosts (developer.webull.com/apis/docs/sdk/):
        #   prod → api.webull.com
        #   paper/test/uat/sandbox → api.sandbox.webull.com
        if env in ("uat", "test", "sandbox", "paper"):
            env = "uat"
            host = "api.sandbox.webull.com"
        else:
            env = "prod"
            host = "api.webull.com"

        api = ApiClient(app_key, app_secret, region_id)
        if env == "uat":
            try:
                from webull.core.common.api_type import DEFAULT, QUOTES, EVENTS
                # Must override all endpoint types; SDK defaults are production-only.
                api.add_endpoint(region_id, host, DEFAULT)
                api.add_endpoint(region_id, host, QUOTES)
                api.add_endpoint(region_id, "events-api.sandbox.webull.com", EVENTS)
            except Exception:
                api.add_endpoint(region_id, host)
        try:
            data = DataClient(api)
        except Exception as e:
            msg = str(e)
            hint = (
                "\n\nWebull OpenAPI authentication failed (401 UNAUTHORIZED).\n"
                "Checklist:\n"
                "  1. WEBULL_APP_KEY / WEBULL_APP_SECRET are from the OpenAPI developer portal\n"
                "     (not your Webull login email/password).\n"
                "  2. No quotes/spaces/newlines around values in backend/.env\n"
                "  3. Environment matches the app:\n"
                "       paper / test / sandbox → WEBULL_ENVIRONMENT=uat  (api.sandbox.webull.com)\n"
                "       live production        → WEBULL_ENVIRONMENT=prod (api.webull.com)\n"
                f"     Currently: environment={env!r} → host {host}\n"
                "  4. App is approved and keys were generated for that same environment.\n"
                "  5. If you recently rotated secrets, update .env and try again.\n"
                f"\nCurrent: region={region_id!r} environment={env!r} "
                f"key_prefix={app_key[:8]}… key_len={len(app_key)} secret_len={len(app_secret)}\n"
            )
            raise RuntimeError(hint + f"\nOriginal error: {msg}") from e
        return cls(data_client=data, dry_run=False)

    @property
    def watchlist_api(self):
        if self._data is None:
            return None
        return self._data.watchlist

    def get_watchlists(self) -> list[dict]:
        self._calls.append(("get_watchlists", {}))
        if self.dry_run or self.watchlist_api is None:
            return list(self._dry_lists.values())
        data = _extract_data(self.watchlist_api.get_watchlist())
        return [x for x in _as_list(data) if isinstance(x, dict)]

    def create_watchlist(self, name: str, sort: int | None = None) -> str | None:
        self._calls.append(("create_watchlist", {"name": name, "sort": sort}))
        if self.dry_run or self.watchlist_api is None:
            # Reuse id if same name already created in this process
            for w in self._dry_lists.values():
                if w.get("name") == name:
                    return w["watchlist_id"]
            # Deterministic id (hash() is process-randomized under PYTHONHASHSEED)
            import hashlib
            wid = "dry-run-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
            self._dry_lists[wid] = {"watchlist_id": wid, "name": name, "sort": sort}
            self._dry_instruments.setdefault(wid, {})
            return wid
        data = _extract_data(self.watchlist_api.create_watchlist(name=name, sort=sort))
        if isinstance(data, dict):
            return data.get("watchlist_id") or data.get("id")
        return None

    def get_instruments(self, watchlist_id: str) -> list[dict]:
        self._calls.append(("get_watchlist_instruments", {"watchlist_id": watchlist_id}))
        if self.dry_run or self.watchlist_api is None:
            return list(self._dry_instruments.get(watchlist_id, {}).values())
        data = _extract_data(self.watchlist_api.get_instruments(watchlist_id=watchlist_id))
        if isinstance(data, dict):
            items = data.get("instruments") or data.get("items") or []
            return [x for x in items if isinstance(x, dict)]
        return [x for x in _as_list(data) if isinstance(x, dict)]

    def add_instruments(self, watchlist_id: str, instruments: list[dict]) -> Any:
        self._calls.append((
            "add_watchlist_instruments",
            {"watchlist_id": watchlist_id, "instruments": instruments},
        ))
        if self.dry_run or self.watchlist_api is None:
            bucket = self._dry_instruments.setdefault(watchlist_id, {})
            for inst in instruments:
                sym = (inst.get("symbol") or "").upper()
                if sym:
                    bucket[sym] = {
                        "symbol": sym,
                        "category": inst.get("category") or "US_STOCK",
                        "sort": inst.get("sort"),
                    }
            return {"ok": True, "dry_run": True, "count": len(instruments)}
        return _extract_data(
            self.watchlist_api.add_instruments(
                watchlist_id=watchlist_id, instruments=instruments
            )
        )

    def remove_instruments(self, watchlist_id: str, instruments: list[dict]) -> Any:
        self._calls.append((
            "remove_watchlist_instruments",
            {"watchlist_id": watchlist_id, "instruments": instruments},
        ))
        if self.dry_run or self.watchlist_api is None:
            bucket = self._dry_instruments.setdefault(watchlist_id, {})
            for inst in instruments:
                sym = (inst.get("symbol") or "").upper()
                bucket.pop(sym, None)
            return {"ok": True, "dry_run": True, "count": len(instruments)}
        return _extract_data(
            self.watchlist_api.remove_instruments(
                watchlist_id=watchlist_id, instruments=instruments
            )
        )


def _get_state() -> dict | None:
    with _lock:
        conn = _conn()
        try:
            row = conn.execute("SELECT * FROM watchlist_state WHERE id = 1").fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def _set_state(watchlist_id: str, watchlist_name: str, session_date: str) -> None:
    now = _now_iso()
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO watchlist_state(id, watchlist_id, watchlist_name, session_date, updated_at)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    watchlist_id=excluded.watchlist_id,
                    watchlist_name=excluded.watchlist_name,
                    session_date=excluded.session_date,
                    updated_at=excluded.updated_at
                """,
                (watchlist_id, watchlist_name, session_date, now),
            )
            conn.commit()
        finally:
            conn.close()


def ensure_today_watchlist(
    client: WebullWatchlistClient,
    *,
    name: str,
    session_date: str,
    reset_daily: bool,
    category: str,
) -> tuple[str, list[str]]:
    """
    Return (watchlist_id, actions_log).
    Creates 'Today's Gap'n'Go' if missing. Optionally clears instruments on new day.
    """
    actions: list[str] = []
    state = _get_state()
    lists = client.get_watchlists()
    by_name = {str(w.get("name") or ""): w for w in lists}
    wl = by_name.get(name)

    if wl and wl.get("watchlist_id"):
        wl_id = str(wl["watchlist_id"])
        actions.append(f"found existing watchlist {name!r} id={wl_id}")
    else:
        wl_id = client.create_watchlist(name)
        if not wl_id:
            raise RuntimeError(f"create_watchlist failed for {name!r}")
        actions.append(f"created watchlist {name!r} id={wl_id}")

    # Daily reset: clear instruments when session_date rolls
    prev_date = state.get("session_date") if state else None
    if reset_daily and prev_date and prev_date != session_date and state.get("watchlist_id") == wl_id:
        existing = client.get_instruments(wl_id)
        if existing:
            payload = [
                {
                    "symbol": (i.get("symbol") or "").upper(),
                    "category": category,
                }
                for i in existing
                if i.get("symbol")
            ]
            if payload:
                client.remove_instruments(wl_id, payload)
                actions.append(f"reset daily: removed {len(payload)} instruments from prior day {prev_date}")

    _set_state(wl_id, name, session_date)
    return wl_id, actions


def _record_sync(
    session_date: str,
    ticker: str,
    *,
    status: str,
    watchlist_id: str | None = None,
    watchlist_name: str | None = None,
    error: str | None = None,
) -> None:
    now = _now_iso()
    with _lock:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT id, attempts FROM watchlist_sync WHERE session_date = ? AND ticker = ?",
                (session_date, ticker),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE watchlist_sync SET
                        status = ?,
                        watchlist_id = COALESCE(?, watchlist_id),
                        watchlist_name = COALESCE(?, watchlist_name),
                        error = ?,
                        attempts = attempts + 1,
                        last_attempt_at = ?,
                        synced_at = CASE WHEN ? IN ('synced','dry_run') THEN ? ELSE synced_at END
                    WHERE id = ?
                    """,
                    (
                        status, watchlist_id, watchlist_name, error, now,
                        status, now, row["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO watchlist_sync(
                        session_date, ticker, watchlist_id, watchlist_name,
                        status, error, attempts, first_seen_at, last_attempt_at, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        session_date, ticker, watchlist_id, watchlist_name,
                        status, error, now, now,
                        now if status in ("synced", "dry_run") else None,
                    ),
                )
            conn.commit()
        finally:
            conn.close()


def already_synced(session_date: str, ticker: str) -> bool:
    with _lock:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT status FROM watchlist_sync WHERE session_date = ? AND ticker = ?",
                (session_date, ticker.upper()),
            ).fetchone()
            return bool(row and row["status"] in ("synced", "dry_run"))
        finally:
            conn.close()


def sync_new_tickers(
    tickers: list[str],
    *,
    session_date: str | None = None,
    screener_key: str | None = None,
    config: dict | None = None,
    client: WebullWatchlistClient | None = None,
) -> dict[str, Any]:
    """
    Add newly observed tickers to Today's Gap'n'Go watchlist.

    Safe to call with empty list. Skips tickers already synced for the day.
    """
    cfg = config or load_config()
    date = session_date or _session_date_today()
    symbols = sorted({str(t).upper().strip() for t in tickers if t and str(t).strip()})

    result: dict[str, Any] = {
        "ok": True,
        "enabled": bool(cfg.get("enabled", True)),
        "session_date": date,
        "watchlist_name": cfg.get("watchlist_name") or "Today's Gap'n'Go",
        "requested": symbols,
        "added": [],
        "skipped": [],
        "errors": [],
        "actions": [],
        "dry_run": False,
    }

    if not cfg.get("enabled", True):
        result["ok"] = True
        result["skipped"] = symbols
        result["actions"].append("watchlist sync disabled in config")
        return result

    allowed_keys = set(cfg.get("screener_keys") or ["gap-n-go"])
    if screener_key and screener_key not in allowed_keys:
        result["skipped"] = symbols
        result["actions"].append(f"screener_key {screener_key!r} not in {sorted(allowed_keys)}")
        return result

    if not symbols:
        return result

    to_add = [s for s in symbols if not already_synced(date, s)]
    result["skipped"] = [s for s in symbols if s not in to_add]
    if not to_add:
        result["actions"].append("all tickers already synced for session")
        return result

    dry = bool(cfg.get("dry_run"))
    load_dotenv()
    mode = str(cfg.get("auth_mode") or "mcp_oauth").lower()

    if client is None:
        if _client_factory:
            client = _client_factory()
        elif dry:
            client = WebullWatchlistClient(data_client=None, dry_run=True)
            result["actions"].append("dry_run=true")
        elif mode in ("mcp_oauth", "mcp", "oauth", "cloud_mcp"):
            try:
                client = make_client(cfg)
                result["actions"].append("auth_mode=mcp_oauth")
            except Exception as e:
                result["ok"] = False
                result["errors"].append(str(e))
                for t in to_add:
                    _record_sync(date, t, status="error", watchlist_name=str(cfg.get("watchlist_name")), error=str(e))
                return result
        else:
            # OpenAPI SDK — dry-run if no app keys
            if not os.environ.get("WEBULL_APP_KEY") or not os.environ.get("WEBULL_APP_SECRET"):
                dry = True
                result["actions"].append("no WEBULL_APP_KEY/SECRET — dry_run mode")
            client = WebullWatchlistClient.from_env(
                region_id=str(cfg.get("region_id") or "us"),
                environment=str(cfg.get("environment") or "uat"),
                dry_run=dry,
            )
            result["actions"].append(f"auth_mode=openapi_sdk dry_run={client.dry_run}")

    result["dry_run"] = bool(getattr(client, "dry_run", False))

    name = str(cfg.get("watchlist_name") or "Today's Gap'n'Go")
    category = str(cfg.get("instrument_category") or "US_STOCK")

    try:
        wl_id, actions = ensure_today_watchlist(
            client,
            name=name,
            session_date=date,
            reset_daily=bool(cfg.get("reset_daily", True)),
            category=category,
        )
        result["actions"].extend(actions)
        result["watchlist_id"] = wl_id
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"ensure_watchlist: {e}")
        for t in to_add:
            _record_sync(date, t, status="error", watchlist_name=name, error=str(e))
        return result

    instruments = [{"symbol": s, "category": category} for s in to_add]
    try:
        client.add_instruments(wl_id, instruments)
        status = "dry_run" if client.dry_run else "synced"
        for s in to_add:
            _record_sync(
                date, s,
                status=status,
                watchlist_id=wl_id,
                watchlist_name=name,
            )
        result["added"] = to_add
        result["actions"].append(
            f"{'dry-run ' if client.dry_run else ''}added {len(to_add)} tickers to {name!r}"
        )
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"add_instruments: {e}")
        for s in to_add:
            _record_sync(
                date, s,
                status="error",
                watchlist_id=wl_id,
                watchlist_name=name,
                error=str(e),
            )

    return result


def list_sync_for_session(session_date: str) -> list[dict]:
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute(
                """
                SELECT ticker, status, error, attempts, first_seen_at, synced_at, watchlist_name
                FROM watchlist_sync
                WHERE session_date = ?
                ORDER BY first_seen_at ASC
                """,
                (session_date,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def set_client_factory(factory: Callable[[], WebullWatchlistClient] | None) -> None:
    """Test helper to inject a fake client."""
    global _client_factory
    _client_factory = factory
