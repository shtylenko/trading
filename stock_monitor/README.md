# stock_monitor

Chrome extension + local backend for:

1. **Chart tabs** (`app.webull.com/stocks…`) — capture closed candlestick (OHLCV) data  
2. **Screener tabs** (`app.webull.com/screener…`) — auto-monitor results and track tickers in a **daily session** (SQLite)

**Everything is local.** Your authenticated browser session + your machine only.

## Quick Links

- Full specification: [spec.md](./spec.md)
- Load extension: [scripts/LOAD_EXTENSION.md](./scripts/LOAD_EXTENSION.md)

## Layout

```
stock_monitor/
  chrome-extension/   # MV3 extension (unpacked)
  backend/
    receiver.py       # primary HTTP receiver (:8787)
    db.py             # daily sessions SQLite
    data/
      captures/       # candle JSON + ndjson
      stock_monitor.db  # sessions (gitignored)
  scripts/
```

## Two page modes

| Tab | URL | Behavior |
|-----|-----|----------|
| Chart | `https://app.webull.com/stocks` | Explicit **Start Capture** → closed candles → `POST /push` → JSON files |
| Screener | `https://app.webull.com/screener` | **Only when a configured My Screener is selected** (default: **Gap'n'Go**) |

### Named screeners (My Screeners)

Config: `backend/config/screeners.json`

- **Stock Screener** tab → ignored  
- **My Screeners** list (nothing selected) → ignored  
- **My Screeners → Gap'n'Go** selected → armed → rows go to today's session  

```bash
curl -s http://127.0.0.1:8787/config/screeners | python3 -m json.tool
```

Add more entries under `screeners` with `enabled: true` to monitor additional named screeners.

### Webull watchlist auto-sync (Today's Gap'n'Go)

When a **new** ticker first appears in the Gap'n'Go session, the backend adds it to a Webull
watchlist named **`Today's Gap'n'Go`**.

**Preferred auth: Cloud MCP OAuth** (retail paper/live account you log into in the browser)  
Docs: https://developer.webull.com/apis/docs/AI-friendly-Resources/mcp/

```bash
cd trading/stock_monitor/backend
source .venv/bin/activate

# One-time: browser login to Webull Cloud MCP (api.webull.com/mcp)
python manage_watchlist.py login

# Then:
python manage_watchlist.py list
python manage_watchlist.py ensure
python manage_watchlist.py show
python manage_watchlist.py add AAPL NVDA
python manage_watchlist.py remove AAPL
python manage_watchlist.py sync --remove-stale
```

Tokens are stored in `backend/conf/webull_mcp_tokens.json` (gitignored).  
Config: `config/watchlist.json` → `"auth_mode": "mcp_oauth"`.

| Path | What it is |
|------|------------|
| **mcp_oauth** (default) | Cloud MCP OAuth → your Webull account watchlists |
| **openapi_sdk** | App key/secret OpenAPI SDK (developer sandbox/prod API) |

Optional fallback OpenAPI keys in `.env` only if you set `"auth_mode": "openapi_sdk"`.

### Daily sessions

- Session date = **America/New_York** calendar day (`YYYY-MM-DD`).
- First time a ticker appears in an **armed** configured screener today → `session_tickers` + raw snapshot (tagged with `screener_key` / `screener_name`).
- Re-seen tickers update `last_seen_at`; snapshots are throttled unless payload changes.

```bash
curl -s http://127.0.0.1:8787/session/today | python3 -m json.tool
curl -s http://127.0.0.1:8787/sessions | python3 -m json.tool
```

## Run

```bash
# Backend
cd trading/stock_monitor/backend
./run.sh
# or: python3 receiver.py
```

**Web UI** (sessions + screened tickers): open [http://127.0.0.1:8787/](http://127.0.0.1:8787/)

Load the unpacked extension from `chrome-extension/` (reload after updates).

1. Open Webull **My Screeners → Gap'n'Go** → popup shows **Armed: YES**.  
2. New symbols from that result table land in today's session.  
3. Chart tabs still need **Start Capture** for candles.

## API (receiver)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/push` | Closed candles → `data/captures/` |
| POST | `/screener` | Armed screener rows → SQLite (requires `screener_key`) |
| GET | `/config/screeners` | Enabled named screeners |
| GET | `/session/today` | Today's session + tickers |
| GET | `/session?date=YYYY-MM-DD` | Historical session |
| GET | `/sessions` | Recent session dates |
| GET | `/health` | Liveness + DB path |
| GET | `/` | Session web UI |
| POST | `/debug/dom` | Debug dumps |

## Tests

```bash
cd trading/stock_monitor/backend
python3 -m unittest test_receiver -v
```

## Status

**0.2.1** — named My Screeners config (Gap'n'Go); arm-on-select only; dual mode + daily sessions.
