"""
Webull Cloud MCP client (OAuth + tools/call).

Docs: https://developer.webull.com/apis/docs/AI-friendly-Resources/mcp/

Auth (OAuth 2.0 Authorization Code + PKCE):
  discovery:  https://api.webull.com/.well-known/oauth-authorization-server
  authorize:  https://passport.webull.com/oauth2/ai-mcp/login
  token:      https://u1suserauth.webullfintech.com/api/userauth/oauth/token/token
  register:   https://u1suserauth.webullfintech.com/api/userauth/oauth/client/register

MCP:
  endpoint:   https://api.webull.com/mcp
  tools:      get_watchlists, create_watchlist, get_watchlist_instruments,
              add_watchlist_instruments, remove_watchlist_instruments, ...

This is the retail-account path (browser login / paper or live account you authorize),
NOT the OpenAPI app-key sandbox SDK path.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

CONF_DIR = Path(__file__).parent / "conf"
CLIENT_PATH = CONF_DIR / "webull_mcp_client.json"
TOKEN_PATH = CONF_DIR / "webull_mcp_tokens.json"

ISSUER = "https://api.webull.com"
MCP_URL = os.environ.get("WEBULL_MCP_URL", "https://api.webull.com/mcp")
OAUTH_META_URL = f"{ISSUER}/.well-known/oauth-authorization-server"

DEFAULT_SCOPES = "account:read order:read order:write market:read instrument:read"
REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = int(os.environ.get("WEBULL_MCP_REDIRECT_PORT", "8765"))
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"


class McpError(RuntimeError):
    pass


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    body: dict | bytes | None = None,
    form: dict | None = None,
    timeout: float = 30,
) -> tuple[int, Any, dict]:
    hdrs = {"Accept": "application/json", **(headers or {})}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif isinstance(body, (bytes, bytearray)):
        data = body

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            parsed: Any
            if "json" in ctype or (raw[:1] in (b"{", b"[")):
                try:
                    parsed = json.loads(raw.decode("utf-8") or "null")
                except json.JSONDecodeError:
                    parsed = raw.decode("utf-8", errors="replace")
            else:
                parsed = raw.decode("utf-8", errors="replace")
            return resp.status, parsed, dict(resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode("utf-8") or "null")
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return e.code, parsed, dict(e.headers)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def fetch_oauth_metadata() -> dict:
    status, data, _ = _http_json("GET", OAUTH_META_URL)
    if status != 200 or not isinstance(data, dict):
        raise McpError(f"OAuth discovery failed ({status}): {data}")
    return data


def load_or_register_client(meta: dict | None = None) -> dict:
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    if CLIENT_PATH.is_file():
        try:
            client = json.loads(CLIENT_PATH.read_text(encoding="utf-8"))
            if client.get("client_id") and REDIRECT_URI in (client.get("redirect_uris") or [REDIRECT_URI]):
                return client
        except Exception:
            pass

    meta = meta or fetch_oauth_metadata()
    reg_url = meta.get("registration_endpoint")
    if not reg_url:
        raise McpError("OAuth metadata missing registration_endpoint")

    status, data, _ = _http_json(
        "POST",
        reg_url,
        body={
            "client_name": "stock-monitor-gapngo",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    if status not in (200, 201) or not isinstance(data, dict) or not data.get("client_id"):
        raise McpError(f"Dynamic client registration failed ({status}): {data}")

    CLIENT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def save_tokens(tokens: dict) -> None:
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    tokens = dict(tokens)
    tokens["saved_at"] = int(time.time())
    if "expires_in" in tokens and "expires_at" not in tokens:
        try:
            tokens["expires_at"] = int(time.time()) + int(tokens["expires_in"]) - 60
        except Exception:
            pass
    TOKEN_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def load_tokens() -> dict | None:
    if not TOKEN_PATH.is_file():
        return None
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("access_token") else None
    except Exception:
        return None


def clear_tokens() -> None:
    if TOKEN_PATH.is_file():
        TOKEN_PATH.unlink()


def _exchange_code(
    meta: dict,
    client: dict,
    *,
    code: str,
    code_verifier: str,
) -> dict:
    token_url = meta["token_endpoint"]
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client["client_id"],
        "code_verifier": code_verifier,
    }
    status, data, _ = _http_json("POST", token_url, form=form)
    if status != 200 or not isinstance(data, dict) or not data.get("access_token"):
        raise McpError(f"Token exchange failed ({status}): {data}")
    return data


def refresh_access_token(meta: dict | None = None, client: dict | None = None) -> dict:
    tokens = load_tokens()
    if not tokens or not tokens.get("refresh_token"):
        raise McpError("No refresh_token — run: python manage_watchlist.py login")
    meta = meta or fetch_oauth_metadata()
    client = client or load_or_register_client(meta)
    form = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client["client_id"],
    }
    status, data, _ = _http_json("POST", meta["token_endpoint"], form=form)
    if status != 200 or not isinstance(data, dict) or not data.get("access_token"):
        raise McpError(f"Token refresh failed ({status}): {data}")
    # Keep old refresh_token if server omits a new one
    if not data.get("refresh_token"):
        data["refresh_token"] = tokens["refresh_token"]
    save_tokens(data)
    return data


def get_valid_access_token() -> str:
    tokens = load_tokens()
    if not tokens:
        raise McpError(
            "Not logged in to Webull Cloud MCP.\n"
            "Run:  python manage_watchlist.py login\n"
            "This opens a browser OAuth flow (paper/live account you authorize)."
        )
    exp = tokens.get("expires_at")
    if exp and int(time.time()) >= int(exp) - 30:
        tokens = refresh_access_token()
    return str(tokens["access_token"])


def login_interactive(*, open_browser: bool = True, scopes: str | None = None) -> dict:
    """
    Browser OAuth login for Webull Cloud MCP.
    Opens passport login; user authorizes accounts/capabilities; tokens saved locally.
    """
    meta = fetch_oauth_metadata()
    client = load_or_register_client(meta)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    scope = scopes or os.environ.get("WEBULL_MCP_SCOPES", DEFAULT_SCOPES)

    params = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)

    result: dict[str, Any] = {"code": None, "state": None, "error": None}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet
            return

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            if qs.get("error"):
                result["error"] = qs.get("error", ["unknown"])[0]
                if qs.get("error_description"):
                    result["error"] += ": " + qs["error_description"][0]
            else:
                result["code"] = (qs.get("code") or [None])[0]
                result["state"] = (qs.get("state") or [None])[0]
            body = (
                b"<html><body style='font-family:sans-serif;padding:2rem'>"
                b"<h2>Webull MCP login complete</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("Webull Cloud MCP OAuth login")
    print(f"  authorize: {meta['authorization_endpoint']}")
    print(f"  redirect:  {REDIRECT_URI}")
    print(f"  client_id: {client['client_id'][:16]}…")
    print()
    print("Open this URL if the browser does not open automatically:")
    print(auth_url)
    print()
    if open_browser:
        webbrowser.open(auth_url)

    if not done.wait(timeout=300):
        server.shutdown()
        raise McpError("Login timed out after 5 minutes — try again")

    server.shutdown()

    if result.get("error"):
        raise McpError(f"OAuth error: {result['error']}")
    if result.get("state") != state:
        raise McpError("OAuth state mismatch — try login again")
    if not result.get("code"):
        raise McpError("OAuth callback missing authorization code")

    tokens = _exchange_code(meta, client, code=result["code"], code_verifier=verifier)
    save_tokens(tokens)
    print(f"Login OK — tokens saved to {TOKEN_PATH}")
    if tokens.get("expires_in"):
        print(f"  access_token expires_in={tokens.get('expires_in')}s")
    return tokens


def mcp_request(
    method: str,
    params: dict | None = None,
    *,
    request_id: int | str = 1,
    access_token: str | None = None,
) -> Any:
    """JSON-RPC call to Webull Cloud MCP with OAuth bearer token."""
    token = access_token or get_valid_access_token()
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-03-26",
    }
    status, data, resp_headers = _http_json("POST", MCP_URL, headers=headers, body=payload)

    # Some MCP HTTP transports return SSE
    if isinstance(data, str) and "data:" in data:
        data = _parse_sse_jsonrpc(data)

    if status == 401:
        # try refresh once
        try:
            tokens = refresh_access_token()
            headers["Authorization"] = f"Bearer {tokens['access_token']}"
            status, data, resp_headers = _http_json("POST", MCP_URL, headers=headers, body=payload)
            if isinstance(data, str) and "data:" in data:
                data = _parse_sse_jsonrpc(data)
        except Exception:
            pass

    if status != 200:
        raise McpError(f"MCP {method} HTTP {status}: {data}")

    if not isinstance(data, dict):
        raise McpError(f"MCP {method} unexpected response: {data!r}")

    if data.get("error"):
        raise McpError(f"MCP {method} error: {data['error']}")

    return data.get("result", data)


def _parse_sse_jsonrpc(text: str) -> Any:
    """Extract last JSON-RPC object from an SSE body."""
    last = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if not chunk:
                continue
            try:
                last = json.loads(chunk)
            except json.JSONDecodeError:
                continue
    return last if last is not None else text


def call_tool(name: str, arguments: dict | None = None) -> Any:
    """tools/call — Cloud MCP tool invocation."""
    result = mcp_request(
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )
    # MCP tools/call often wraps content as [{type:text,text:"..."}]
    if isinstance(result, dict) and "content" in result:
        texts = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text") or "")
        if texts:
            joined = "\n".join(texts)
            try:
                return json.loads(joined)
            except json.JSONDecodeError:
                return {"text": joined, "raw": result}
    return result


def initialize_session() -> Any:
    return mcp_request(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "stock-monitor", "version": "0.3.0"},
        },
    )


# --- Watchlist helpers via MCP tools ---

def get_watchlists() -> list[dict]:
    data = call_tool("get_watchlists")
    return _as_watchlist_list(data)


def create_watchlist(name: str, sort: int | None = None) -> str | None:
    args: dict[str, Any] = {"name": name}
    if sort is not None:
        args["sort"] = sort
    data = call_tool("create_watchlist", args)
    if isinstance(data, dict):
        return data.get("watchlist_id") or data.get("id")
    if isinstance(data, str):
        # try parse id from text
        for token in data.replace(",", " ").split():
            if token.startswith("openapi-") or len(token) > 20:
                return token
    return None


def get_watchlist_instruments(watchlist_id: str) -> list[dict]:
    data = call_tool("get_watchlist_instruments", {"watchlist_id": watchlist_id})
    return _as_instrument_list(data)


def add_watchlist_instruments(watchlist_id: str, instruments: list[dict]) -> Any:
    return call_tool(
        "add_watchlist_instruments",
        {"watchlist_id": watchlist_id, "instruments": instruments},
    )


def remove_watchlist_instruments(watchlist_id: str, instruments: list[dict]) -> Any:
    return call_tool(
        "remove_watchlist_instruments",
        {"watchlist_id": watchlist_id, "instruments": instruments},
    )


def _as_watchlist_list(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("watchlists", "items", "result", "data"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        if "watchlist_id" in data or "name" in data:
            return [data]
        if "text" in data and isinstance(data["text"], str):
            # best-effort parse lines "name: X" — return empty and let caller print text
            return []
    return []


def _as_instrument_list(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("instruments", "items", "result", "data"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    return []


class WebullMcpWatchlistClient:
    """
    Drop-in style client mirroring WebullWatchlistClient methods,
    backed by Cloud MCP OAuth tools.
    """

    dry_run = False

    def __init__(self):
        self._calls: list[tuple[str, dict]] = []

    def get_watchlists(self) -> list[dict]:
        self._calls.append(("get_watchlists", {}))
        return get_watchlists()

    def create_watchlist(self, name: str, sort: int | None = None) -> str | None:
        self._calls.append(("create_watchlist", {"name": name, "sort": sort}))
        return create_watchlist(name, sort=sort)

    def get_instruments(self, watchlist_id: str) -> list[dict]:
        self._calls.append(("get_watchlist_instruments", {"watchlist_id": watchlist_id}))
        return get_watchlist_instruments(watchlist_id)

    def add_instruments(self, watchlist_id: str, instruments: list[dict]) -> Any:
        self._calls.append((
            "add_watchlist_instruments",
            {"watchlist_id": watchlist_id, "instruments": instruments},
        ))
        return add_watchlist_instruments(watchlist_id, instruments)

    def remove_instruments(self, watchlist_id: str, instruments: list[dict]) -> Any:
        self._calls.append((
            "remove_watchlist_instruments",
            {"watchlist_id": watchlist_id, "instruments": instruments},
        ))
        return remove_watchlist_instruments(watchlist_id, instruments)
