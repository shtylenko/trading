# Loading the Chrome Extension (Unpacked)

1. Open Chrome and go to `chrome://extensions`
2. Turn on "Developer mode" (top right)
3. Click "Load unpacked"
4. Navigate to and select the `chrome-extension/` folder inside this project
5. Pin the extension for convenience
6. After code changes: click **Reload** on the extension card, then reload any open Webull tabs

The extension activates automatically on pages matching `https://app.webull.com/*`.

## After loading

1. Start the backend first (see below).
2. **Chart** — open https://app.webull.com/stocks (log in if needed) → popup shows **chart** mode → **Start Capture** for closed candles.
3. **Screener** — open https://app.webull.com/screener → **My Screeners** → select **Gap'n'Go**. Popup should show **Armed: YES**. Only then are result tickers added to today's session. Stock Screener and unselected My Screeners are ignored.
4. Check session membership:
   ```bash
   curl -s http://127.0.0.1:8787/session/today | python3 -m json.tool
   ```

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
curl http://127.0.0.1:8787/session/today
```

## Troubleshooting

- Popup shows "no response": reload the Webull tab after loading/reloading the extension.
- Screener shows "waiting for network responses": open DevTools → Console on the screener tab; look for `[webull-monitor-inject] screener rows`. Heuristics may need tightening against live API shapes (DEBUG_SCREENER dumps help).
- No candle data: heuristics in inject.js are starting points. Console logs on chart tab; trigger chart loads/TF changes.
- Mixed content: handled via background proxy.
- Backend not reachable: make sure `receiver.py` is running and `backend/data/` is writable.

This is dev-only (unpacked). Do not publish to store without review.
