# Webull Chart Candle Monitor — Spec

**Project location**: `/Users/shtylenko/Hermes/projects/trading/stock_monitor`

**Goal**: A Chrome extension + local backend that observes an open chart on https://app.webull.com/stocks (and related quote pages), extracts the visible/loaded candlestick (OHLCV) data in real time or near-real time, and pushes it to a local backend for storage, querying, and downstream use.

This gives you a reliable way to capture the exact candles the trader is viewing inside the Webull web UI (including any custom timeframe, extended hours view, or symbol the user has navigated to), without relying solely on external APIs.

---

## 1. High-Level Architecture

```
┌─────────────────────────────┐
│  Chrome (user opens chart)  │
│  https://app.webull.com/... │
│                             │
│  ┌─────────────────────┐    │
│  │ Webull SPA (Canvas  │    │
│  │  + JS chart + WS)   │    │
│  └──────────┬──────────┘    │
│             │               │
│   (network hooks + DOM)     │
│             ▼               │
│  ┌─────────────────────┐    │
│  │ page-inject.js      │◄───┼── runs in PAGE world (MAIN)
│  │ (fetch/WS/XHR hook) │    │   detects bar payloads
│  └──────────┬──────────┘    │
│             │ postMessage   │
│             ▼               │
│  ┌─────────────────────┐    │
│  │ content.js          │    │   (ISOLATED world)
│  │ - symbol/tf detect  │    │
│  │ - buffer + batch    │    │
│  └──────────┬──────────┘    │
│             │ runtime msg   │
│             ▼               │
│  ┌─────────────────────┐    │
│  │ background.js       │    │   (service worker)
│  │ - proxy to backend  │    │
│  │ - health / config   │    │
│  └──────────┬──────────┘    │
│             │ fetch           │
│             ▼               │
│      http://127.0.0.1:8787   │   (or configured port)
└─────────────────────────────┘

┌─────────────────────────────┐
│  Local Backend (minimal)    │
│  • Receives POST /push     │
│  • Writes NDJSON + per-    │
│    symbol .json files      │
│  • (optional) tiny query   │
└─────────────────────────────┘
```

**Why this split?**
- Extension runs where the authenticated chart lives (user's session, their watchlist, drawings, indicators, exact view).
- Backend is simple, local-only, durable storage + query surface that other tools (Python scripts, lab, live trading) can consume.
- Avoids mixed-content problems (HTTPS page → HTTP localhost) by proxying through background worker.

---

## 2. Data Model (v1)

### Backend SQLite

**symbols**
- id, ticker (UNIQUE), first_seen, last_seen, meta (json)

**timeframes**
- id, code (e.g. "1m", "5m", "1D"), minutes (int or null for daily+)

**candles**
- id (autoincrement)
- symbol_id
- timeframe_id
- ts (INTEGER unix ms or epoch seconds — the bar start time, UNIQUE per symbol+tf)
- open REAL
- high REAL
- low REAL
- close REAL
- volume REAL (or INTEGER)
- source TEXT ('webull-web' default)
- captured_at TEXT (ISO when we received it)
- raw_json TEXT (nullable, original payload snippet for debugging)

**Constraints**: UNIQUE(symbol_id, timeframe_id, ts)

**sessions** (optional v1 or v2)
- id, started_at, symbol, tf, notes

Indexes on (symbol, ts), (symbol, tf, ts)

### In-Extension (in-memory / storage.local)
- Current active symbol + tf
- Buffer of recent candles (ring buffer, last 2000 bars per tf or global limit)
- Last push timestamp

### Payload format (extension → backend)

```json
{
  "symbol": "AAPL",
  "timeframe": "5m",
  "captured_at": "2026-07-02T14:31:05.123Z",
  "candles": [
    {
      "t": 1751471400000,
      "o": 212.45,
      "h": 212.89,
      "l": 212.31,
      "c": 212.67,
      "v": 1243500
    }
  ]
}
```

Timestamps: prefer the bar open time in milliseconds since epoch (common in trading UIs).

Backend normalizes timeframe strings (accepts "5", "5m", "m5", "5min" etc.).

---

## 3. Chrome Extension Details (Manifest V3)

### Files
```
chrome-extension/
├── manifest.json
├── background.js
├── content.js
├── inject.js                 # web_accessible_resources
├── popup.html
├── popup.js (or inline)
├── styles.css (minimal)
└── icons/ (16,48,128 png placeholders)
```

### manifest.json key points
- manifest_version: 3
- permissions: ["activeTab", "storage", "scripting"]
- host_permissions:
  - "https://app.webull.com/*"
  - "http://localhost/*"   # or specific port range if possible; localhost is special
  - Optionally "https://127.0.0.1/*"
- content_scripts: matches on "https://app.webull.com/*" (and subpaths like /stocks, /quote etc.)
- web_accessible_resources: ["inject.js"]
- action: popup
- background: service_worker

### Content Script Responsibilities
- Inject `inject.js` into page (create script element, src = chrome.runtime.getURL).
- Listen for `window.postMessage` of type `WEBULL_DATA` or `CANDLES`.
- Detect current symbol:
  - Try URL parsing first (`/stocks/TSLA`, `/quote/NVDA` etc.)
  - Fallback: MutationObserver + query for common ticker elements (textContent matching `[A-Z]{1,5}` in header area, or data attributes).
- Detect active timeframe: observe the timeframe selector buttons (look for "active", "selected", aria-current or class containing selected state). Common labels: 1m,5m,15m,30m,1h,4h,1D,1W.
- Maintain a small local buffer keyed by `${symbol}:${tf}`.
- On receiving new candle data (or batch), merge (by timestamp), then decide when to push:
  - Immediately on new bar detection, or
  - Throttled (e.g. max every 2-5s or on 10 new candles), or
  - User-triggered via popup "Capture now".
- Send to background via `chrome.runtime.sendMessage({type: "PUSH_CANDLES", payload})`.
- Surface status in popup (current symbol/tf, last captured count, connection state to backend).

### Page Inject (inject.js)
Runs in the **page's main JavaScript world** so it can:
- Override `window.fetch`
- Override `XMLHttpRequest.prototype.open` + `send`
- Wrap `WebSocket` constructor and hook `onmessage` / `addEventListener('message')`
- (Future) Try to locate global chart objects (e.g. `window.echartsInstance`, TradingView widget, or Webull-specific `chartApi` or `__APP__` state) and read series data directly.

Heuristic for "this is candle data":
- Response is JSON
- Root or nested value is an Array
- Array items are objects containing at least 4 numeric-ish fields that look like price levels + optional volume + a time field (number or ISO)
- Typical keys observed in practice: `open/high/low/close/volume` or `o/h/l/c/v`, `timestamp`, `time`, `t`, `date`, `kline`, etc.
- The request URL or payload contains the ticker or "kline"/"bars"/"chart"/"history"/"quote" hints.

When candidate data is found:
- Try to also extract symbol + timeframe from the **request** (URL query params, path, request body JSON).
- If successful, postMessage the normalized candles + meta to the content script.
- De-dupe within the inject layer if possible (last N request signatures).

**Robustness notes**:
- Webull will likely change their internal format and endpoints. Logging + a "raw capture" mode (store original JSON + request URL) is very valuable for future reverse-engineering.
- Some responses may be gzipped / protobuf — start with JSON only; add decompression later if needed.
- Real-time updates often come via WS as incremental ticks or "latest bar update". Need to convert the forming candle (the last incomplete one) correctly or mark it.

### Popup
- Shows current symbol + active/open timeframe + how many closed bars are buffered.
- One prominent control: **"Start Capture"** button (turns into **"Stop Capture"** when active).
- Turning capture ON for a tab:
  - Starts automatic background collection.
  - Immediately pushes all currently closed candles for the open timeframe.
  - Then keeps pushing automatically every time a new candle fully closes.
- "Dump DOM Debug" button (also triggers automatically ~every 8s) pushes detailed snapshots of the current page DOM / canvases / price labels to `data/captures/debug/`. This lets you directly inspect the real HTML structure the extension sees.
- Secondary actions: Test push + Clear buffer.
- Per-tab: each open chart tab has its own capture on/off state.

### Background
- Receives messages from content script.
- Performs the actual HTTP POST to backend (avoids mixed content).
- Can also answer external PING for health checks (like the metaia example).
- Stores minimal state (last known backend URL).
- Optional: on startup or alarm, health-check the backend.

### Permissions & Privacy
- Only runs on app.webull.com (and configured hosts).
- All data stays on user's machine.
- No telemetry.
- User explicitly loads the unpacked extension.

---

## 4. Backend (Minimal — JSON file focused)

**User-stated goal (2026-07-02)**: Collect candlebar data into local JSON file(s).

### Tech (keep it tiny)
- Python 3 stdlib preferred where possible (`http.server` + simple handler or a ~60-line Flask app).
- Write path produces clean, loadable JSON/NDJSON.
- Optional tiny SQLite index for fast latest queries (still write the JSON).
- No Pydantic/FastAPI/uvicorn unless we decide the ergonomics are worth the deps.

### Recommended output files (in `backend/data/captures/` or project root `data/`)

1. Append-only NDJSON (perfect for "just collect"):
   `candles.ndjson`
   One line per received candle:
   `{"symbol":"AAPL","tf":"5m","ts":1751471400000,"o":212.45,"h":212.89,"l":212.31,"c":212.67,"v":1243500,"received_at":"..."}`

2. Per-symbol latest view (easy `json.load`):
   `AAPL_5m.json` (full array of candles + metadata, updated on each push)

The receiver always dedupes by timestamp when rewriting the per-symbol JSON.

### Minimal structure
```
backend/
├── receiver.py          # runnable: python3 receiver.py  (or ./run.sh)
├── requirements.txt     # "flask>=3" only if we use Flask (tiny)
├── run.sh
└── data/
    └── captures/        # gitignored; JSON files land here
```

### Core "API" (if we keep a receiver server)

POST /push   — body same shape as before, appends to files
GET /health

That's mostly it. Consumers just read the .json / .ndjson files directly from disk.

This satisfies "collect candlebar data into a local json file" with the least moving parts.

---

## 5. Data Flow & Lifecycle (Closed-candle rules)

1. User opens a chart.
2. Capture is OFF by default on every tab.
3. User clicks the single **"Start Capture"** button in the popup.
   - Capture turns ON.
   - Current closed candles are pushed immediately.
   - Future closed candles will be auto-pushed as they complete on the active timeframe.
4. content.js keeps only closed candles (never the bar with the current highest timestamp).
5. As new bars arrive with higher `t`, the previous bar is treated as closed and sent.
6. User clicks "Stop Capture" to turn it off for that tab.
7. Backend writes to the local JSON files. Multiple tabs can independently have capture on or off.

**Important**: The extension never intentionally sends a forming/incomplete bar. The highest-t bar seen so far for a (symbol, tf) is held back until a later bar confirms it closed.

**Closed candles only (user decision 2026-07-02)**:
- We do **not** want forming / incomplete candles.
- We only record and push a candle once it has fully closed.
- The active **timeframe that is currently open/selected** in the chart UI is what matters.
- Detection of "a candle just closed": when the chart data source emits a bar with a *strictly later* timestamp than any previously seen for the current (symbol, tf), all prior bars become confirmed closed.
- In practice the extension drops the bar with the highest `t` from any batch (presumed forming) and only pushes bars whose `t` is < the highest `t` seen so far for that symbol+tf.
- When a new higher `t` appears, the previous highest bar is now treated as closed and is eligible for push.
- Push happens (throttled) when newly closed candle(s) are detected.
- "Capture now" button still respects the closed-only rule (or has an explicit "include latest" option later if needed).
- Only raw OHLCV (no indicator values) for v1.

**Symbol / TF change**:
- Detect via network (new requests carry new symbol/period) + DOM.
- On change, optionally flush current buffer or tag the push with old meta.

---

## 6. Development & Run Instructions (to be finalized in README)

**Backend (minimal receiver - recommended)**
```bash
cd backend
./run.sh
# or directly:
python3 receiver.py
```

(Uses `python3` by default. The script auto-detects `python3` / `python` and supports `fastapi` mode too.)
```bash
cd backend
python3 -m venv .venv     # only needed for fastapi mode
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8787
```

**Extension**
1. `chrome://extensions` → Developer mode ON
2. "Load unpacked" → select `chrome-extension/` folder
3. Pin it
4. Open a Webull chart tab

**Verify**
- Popup shows detected symbol
- Backend logs show POSTs
- GET /api/candles returns data

**Scripts helpers**
- `scripts/start-backend.sh`
- `scripts/dev-reload.sh` (optional)
- Instructions for packaging later if desired (but unpacked is fine)

---

## 7. Risks & Challenges (be explicit)

1. **Chart is Canvas-heavy**: DOM text scraping of prices will be poor. Network + internal state hooking is the only robust path.
2. **Obfuscation / format changes**: Webull (or their charting vendor) can change payload shapes, field names, or switch to binary/WS protobuf. Design must be heuristic + log raw on failure.
3. **Mixed content & MV3 restrictions**: Handled by background proxy + careful permissions.
4. **Authentication state**: Extension only sees what the logged-in browser session sees. If page requires specific market data subscription for full L2 or tick data, candles may be limited.
5. **Rate / volume**: High-frequency timeframes (1s? tick?) on active names can produce lots of updates. Throttle pushes + dedupe.
6. **Multiple tabs**: Each tab runs its own content script with independent `monitoringEnabled` flag and its own closed-candle trackers. Tabs monitoring the same (symbol + active tf) will naturally push overlapping closed candles — backend dedupes on (symbol, tf, ts). No session id needed in v1.
7. **Extended hours / pre/post**: Need to capture or tag session correctly if user cares.
8. **Legal / ToS**: Reading your own browser UI data for personal use is generally fine, but document that this is a local personal tool. Do not redistribute captured data.

---

## 8. Phased Implementation Plan (suggested)

**Phase 0 — Spec & scaffolding** (current)
- Write this spec + ask questions.
- Create folder skeleton + empty files with comments.
- Basic manifest + hello world popup.

**Phase 1 — Minimal viable capture**
- Backend: FastAPI skeleton + /health + /api/candles POST/GET + sqlite upsert.
- Extension: manifest + inject basic fetch + XHR hook that logs to console everything that looks like bars.
- content <-> background plumbing.
- Popup shows "last captured raw count".
- Manual "push test data" button.

**Phase 2 — Symbol/TF + real pushes**
- DOM + network symbol detection.
- Timeframe detection.
- Proper normalization + batching.
- Actual POSTs on real pages.
- De-dupe logic.

**Phase 3 — Polish + reliability**
- Better heuristics, raw logging mode (save unknown payloads to backend for review).
- Robust closed-candle detection across different response shapes (initial load vs live updates).
- Active timeframe detection (the one "which is open").
- Popup status, config, manual capture (only closed candles).
- Error resilience (backend down → queue/retry limited).
- Basic dashboard or export.

**Phase 4 — Integration**
- Python client lib (`from stock_monitor_client import get_latest_candles`)
- Feed into trading/marketdata or lab workflows.
- Pattern detection in backend or separate service.
- Alerts (macOS notifications via terminal-notifier or pyobjc, or just console).

---

## 9. Open Questions / Decisions Needed

Please answer as many as possible before we write significant code. I will update this spec with your answers.

### Scope & Purpose
1. **Primary use case**? (pick one or rank)
   - a) Record what I am looking at for later review / journaling.
   - b) Real-time input for local signals / scanners (e.g. "notify on new 5m breakout").
   - c) Create a personal historical dataset that exactly matches what the Webull chart showed me (vs using yfinance/alpaca which may differ slightly in timing or extended hours).
   - **d) Other?** → **Collect candlebar data into local JSON file(s)** (user preference stated 2026-07-02).

2. **Timeframes** to prioritize? (1m, 5m, etc. — all? intraday only?)
   - **Answer (2026-07-02)**: The timeframe that is currently open/selected in the chart ("timeframe matters which is open"). We detect the active one.

3. **Do we care about the forming (incomplete) current candle**, or only closed/completed bars?
   - **Answer (2026-07-02)**: Only closed/completed bars. Never send forming candles. Push when a candle fully closes (i.e. when a newer bar timestamp appears).

4. **Indicators**? Should we also try to read values of any displayed indicators (VWAP, EMA, volume profile) or just raw OHLCV for now?
   - **Answer (2026-07-02)**: Only OHLCV for now.

### Extraction Strategy
5. **Preferred extraction method** if we have to choose one first:
   - A) Aggressive network interception (fetch/WS + URL param parsing) — most promising.
   - B) Try to find and call internal chart JS APIs first.
   - C) Hybrid (A + best-effort B).

6. Accept that initial version may require the user to open DevTools once to help discover the exact payload shapes on their account?

### Backend & Data
7. **Backend language/runtime** preference? (Strong recommendation: Python + FastAPI to stay consistent with `trading/` monorepo. Alternatives?)
   - **Answer (2026-07-02)**: Minimal (Flask or even just sqlite + http.server). Goal is primarily writing local JSON file(s). We will use a tiny receiver.

8. Do you want a **minimal web UI** in the backend (table + basic chart) in v1, or API-only + you will consume from Python/Jupyter/scripts?

9. Retention policy? (e.g. keep last 30 days of 1m data, forever for daily, or "user manages manually").

10. Multi-symbol support in parallel tabs important from day 1?
    - **Answer (2026-07-02)**: Yes. Multiple tabs can have "Capture" independently turned on or off. Each tab has its own capture state. When a tab has capture ON it pushes closed candles for whatever timeframe is currently open on that tab. Backend dedupes by (symbol, tf, ts).

### UX / Operation
11. Should the extension auto-start pushing whenever it sees a chart, or require explicit "Start monitoring" toggle per tab/session?
   - **Answer (2026-07-02)**: Explicit control. Single **"Start Capture"** button in the popup turns on automatic closed-candle pushing for that tab (and does an immediate capture of current closed bars). No separate monitoring vs manual buttons.

12. Any need for **authentication / token** between extension and backend, even for localhost? (simple shared secret in env or none?)

13. Future integration desires with existing code:
    - Feed `trading.marketdata`?
    - Trigger things in `trading.live`?
    - Used inside other skills?

### Technical / Env
14. Target Python version? Any objection to adding `uv` or `poetry` for backend, or stick to pip + requirements.txt like analyst_radar?

15. Do you want the extension to also support the **desktop Webull app** (Electron) if it exposes similar web content, or Chrome-only for now?

16. Any hard constraints (e.g. must not require self-signed HTTPS certs, must work on first try with default Chrome settings)?

### Nice-to-haves (for later)
- Desktop notifications on certain candle events.
- Overlay badge on the Webull tab itself ("monitoring 142 bars").
- Ability to "replay" captured session.

---

## 10. Non-Goals (v1)

- Placing trades or modifying orders via the extension.
- Full Level 2 / order book capture (unless trivial as side effect).
- Supporting every possible Webull page (focus on the main stock chart view).
- Official Chrome Web Store packaging (unpacked + documented sideloading is fine).
- Cross-browser (Chrome/Edge only initially).

---

## 11. Next Steps After Answers

1. Update spec.md + create a short README.md with the agreed answers.
2. Scaffold the code (empty + well-commented files).
3. Implement Phase 1 (skeleton + logging).
4. Test on real page (you will need to open a chart).
5. Iterate on detection heuristics (this part will involve live debugging).

---

**Status (updated 2026-07-02)**: All your latest decisions incorporated:
- Only closed candles (never forming)
- Push on close (new higher ts confirms previous bar closed)
- Active/open timeframe is what is recorded
- Multiple tabs with independent monitoring toggles
- JSON files as primary output

Implementation updated (content.js closed-candle trackers + enable catch-up, popup, receiver). Ready for live chart testing.

This document lives at `trading/stock_monitor/spec.md` and should be the source of truth.
