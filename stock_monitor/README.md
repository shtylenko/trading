# stock_monitor

Chrome extension + local backend for capturing live candlestick (OHLCV) data from charts on https://app.webull.com/stocks (and related Webull web quote/chart pages).

**Everything is local.** Your authenticated browser session + your machine only.

## Quick Links

- Full specification and architecture: [spec.md](./spec.md)
- Project root: `trading/stock_monitor/`
  - `chrome-extension/` — MV3 extension (unpacked)
  - `backend/` — minimal receiver (writes JSON files) + optional heavier FastAPI skeleton
  - `scripts/` — helpers

## Current Status (2026-07-02)

**Spec + light scaffolding complete.** User feedback incorporated (latest 2026-07-02):

- Primary goal: **collect candlebar data into local JSON file(s)**
- Only **fully closed candles** (never forming/incomplete)
- Single **"Start Capture"** button per tab turns on automatic pushing (also captures current closed bars immediately)
- Track the **active/open timeframe** on the chart
- **Multiple tabs**: capture can be independently started/stopped on each
- Backend: **minimal** (JSON writer preferred)

Scaffolding present:
- Full Chrome MV3 files (manifest, background, content, inject hooks, popup with toggle)
- `backend/receiver.py` — tiny stdlib-based server that writes `data/captures/*.json` + `candles.ndjson`
- `backend/app/main.py` — heavier FastAPI version kept for reference

**Next**: 
- Start backend: `cd backend && ./run.sh`
- Load unpacked extension (see `scripts/LOAD_EXTENSION.md`)
- Open a chart on https://app.webull.com , enable the toggle in popup
- Watch files appear under `backend/data/captures/`

We are ready for live testing + heuristic tuning once you open a real chart. No heavy implementation happened before your answers.

## Why This Approach

- Webull's chart is a rich interactive canvas/JS app. The best way to see *exactly* the candles you are looking at (with your subscriptions, extended hours view, selected timeframe, etc.) is to observe the page while you use it.
- Network interception + limited DOM observation inside a content script + page-world injection is the reliable path.
- Local backend gives durable storage you can query from Python, notebooks, or future trading tools in this monorepo.

## Non-Goals (v1)

See spec.md. No trading execution, no public distribution, Chrome-focused.

## Development Notes

- Backend should stay consistent with the rest of `trading/` (Python).
- Extension follows patterns from the existing `metaia_plugin/chrome-extension/` example in the workspace.
- All data stays on disk locally. No cloud.

Next step: your feedback on the questions in spec.md.
