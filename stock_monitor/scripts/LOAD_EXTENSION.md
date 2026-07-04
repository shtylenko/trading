# Loading the Chrome Extension (Unpacked)

1. Open Chrome and go to `chrome://extensions`
2. Turn on "Developer mode" (top right)
3. Click "Load unpacked"
4. Navigate to and select the `chrome-extension/` folder inside this project
5. Pin the extension for convenience

The extension activates automatically on pages matching `https://app.webull.com/*`.

## After loading

- Click the extension icon → popup appears.
- Open a chart on https://app.webull.com (log in if needed).
- The popup should show detected symbol/timeframe once data flows.
- Start the backend first (see below).

## Backend

From the project:

```bash
cd trading/stock_monitor/backend
bash run.sh
# or
./scripts/start-backend.sh
```

It runs on http://127.0.0.1:8787 by default.

Test manually from another terminal:
```bash
curl http://127.0.0.1:8787/health
# or
curl http://127.0.0.1:8787/api/health
```

## Troubleshooting

- Popup shows "no response": reload the Webull tab after loading the extension.
- No data appearing: the heuristics in inject.js are starting points. Open DevTools on the chart tab → Console. You will see logs. Use the page to trigger chart loads/changes.
- Mixed content: handled via background proxy.
- Backend not reachable from popup: make sure backend is running and DB_PATH is writable.

This is dev-only (unpacked). Do not publish to store without review.
