# Simulation artifacts + web viewer — SPEC

**Goal:** every `TRADE_SIMULATOR` run leaves a self-contained **session folder** of
artifacts (bars, indicators, the agent's turn-by-turn thoughts, every fill, and a
P&L file), and a local **web UI** renders that folder — a TradingView candlestick
chart with indicator overlays and entry/exit markers, alongside the model's
reasoning timeline. Everything lives inside
`/Users/shtylenko/Hermes/projects/trading/day_trading_simulator`.

Status: **APPROVED — building.**

---

## 1. Session folder

```
day_trading_simulator/simulations/{TS}-{TICKER}/
```

`{TS}` = the **real wall-clock** time the simulation was run,
`datetime.now().strftime("%Y%m%d%H%M%S")` (e.g. `20260630143052-EVTV`). This is the
folder name the web UI takes as input. (The *historical* trading date lives inside
the artifacts, not the folder name.)

### Files (all JSON unless noted)

| File | Writer | Purpose |
|---|---|---|
| `stream.jsonl` | `replay --out-file` | **Source of truth** — raw replay output: one `meta` line, a `tick` line per minute, one `end` line. Bars + indicators + setup meta + session outcome all derive from here. |
| `decisions.jsonl` | agent, via `recorder log` | **Append-only**, one record per turn (bar): the LLM's `thought`, the `action`, any fill. Durable as the run progresses. |
| `session.json` | `recorder finalize` | Manifest: schema version, ids, ticker, historical date, real run ts, config, setup meta + reference levels, result summary, file index. The UI reads this first. |
| `bars.json` | `recorder finalize` | Chart-ready bars: `[{t (epoch s), time (HH:MM), o,h,l,c,v, vwap, ema9, ema20, macd, macd_signal, macd_hist, session_high, new_high, rvol_bar}]`. |
| `actions.json` | `recorder finalize` | Discrete fills only (ENTER/ADD/SCALE/EXIT): `{i, t, time, action, side (buy/sell), price, shares, position_after, avg_entry, realized_delta, reason}`. Chart markers + the trade blotter. |
| `decisions.json` | `recorder finalize` | Normalized turn timeline: every decision with `t`/epoch + the **computed** position snapshot at that bar (`shares, avg_entry, stop, unrealized, realized_to_date`) so the UI shows P&L evolving alongside each thought. |
| `pnl.json` | `recorder finalize` | Outcome: `realized_pnl`; `r_multiple` (vs the account **risk budget**) and `r_multiple_actual` (vs the `initial_risk` = shares×stop-distance actually taken at entry, when a stop was recorded); `risk_budget`, `initial_risk`; `entry_avg` (**blended** cost basis across all buys, not the first fill); `mfe_per_share`/`mfe_pct` (max favorable excursion vs `entry_avg`); `win` bool; `forced_exit`; assumptions. |
| `journal.md` | `recorder finalize` (baseline) | Human-readable recap generated from the above; the agent may append a richer post-mortem. |

> **Join key = `t` (epoch seconds), not `i`.** `i` is an index *within its own
> file*: in `bars.json` it counts the full RTH day from 09:30, while in
> `decisions.json`/`actions.json` it is the stream index (0 = the breakout bar the
> agent first saw). Those two index spaces differ, so anything cross-referencing
> bars with decisions/actions (as the viewer does) must join on `t`, never `i`.

### `decisions.jsonl` record (what the agent appends each turn)

Minimal and authoritative-free — the recorder computes all P&L/position from the
sequence, so the agent never has to do arithmetic that could drift:

```json
{"i": 3, "time": "10:23",
 "thought": "Tagged $3.99 = pm_high/round number on 2.8x rvol, closed 3.96 over VWAP. First push into resistance; banking 1/2 at +1R and trailing the rest.",
 "action": "SCALE", "fill_px": 3.90, "shares_delta": -150, "stop": 3.75,
 "note": "scale 1/2 at +1R"}
```

- `action ∈ {OBSERVE, ENTER, ADD, SCALE, TRAIL, EXIT, STAND_DOWN}`.
- `fill_px` / `shares_delta`: a fill this turn (`+`=buy, `−`=sell); `null`/omit when
  no fill (OBSERVE / TRAIL just updates `stop`).
- `stop`: the stop level in force *after* this turn (for the chart's stop line).
- `thought`: the model's reasoning for this bar — the heart of the timeline.

### Position / P&L engine (recorder, deterministic)

Average-cost. Walk `decisions.jsonl` in order:
- **buy** (`shares_delta>0`): `avg_entry = (avg_entry*shares + fill*qty)/(shares+qty)`, `shares += qty`.
- **sell** (`shares_delta<0`): `realized += qty*(fill − avg_entry)`, `shares -= qty`.
- `unrealized` at a bar = `shares*(close − avg_entry)`.
- If `shares>0` at the `end` line, recorder force-closes at `end.close` and flags it.
- `r_multiple = realized_pnl / risk_budget`; `mfe_per_share = max(high after entry) − avg_entry_at_entry`.

Invariants enforced (else `finalize` errors): shares never negative; a SCALE/EXIT
needs an open position; ENTER only while flat.

---

## 2. Web viewer (SPA)

The viewer is now a small web UI server. Run:

```
python3 -m trading.day_trading_simulator.viewer
```

It opens a page showing the **list of all sessions** (newest first) with status,
ticker, dates, PnL, etc.

- Click a session → loads detail (chart + timeline) in the main area (sidebar stays).
- Cmd/Ctrl+Click opens in new tab.
- Running sessions show live updates via **Server-Sent Events (SSE)** using server-computed state from `stream.jsonl` + `decisions.jsonl` (revealed data **only**).
- "Finalize" button snapshots the session (forces close of any open position at last known price) and marks it complete.
- Only revealed bars are shown for ongoing sessions (no future peeking).

The server also provides:
- `/api/sessions`
- `/api/session/<id>/state`
- `/api/session/<id>/finalize`
- `/api/session/<id>/events` (SSE)

Direct `?session=ID` links continue to work.

### Layout & behavior
- **Header** — ticker, historical date, setup chips (gap %, RVOL, float, anchor,
  reason), reference levels (prior close/high/low, pm high/low), and a P&L badge
  (realized $, R, win/loss) from `pnl.json`.
- **Chart** — [TradingView **Lightweight Charts** v4](https://github.com/tradingview/lightweight-charts)
  (CDN). *(The hosted TradingView "widget" only plots TradingView's own symbols;
  Lightweight Charts is the library for arbitrary OHLC data — that's the correct
  tool here.)* Candlestick series from `bars.json`; **VWAP** and **EMA9** line
  overlays; a **volume** histogram pane; price lines for **entry**, **stop**,
  **pm_high/round levels**; **markers** from `actions.json` (▲ buy below bar / ▼
  sell above bar, labeled with shares & price). X-axis uses ET wall-clock (epoch
  stored as ET-as-UTC so labels read 10:20, 10:21 …).
- **Decision timeline** — scrollable panel of `decisions.json`: per turn show
  `time`, action badge, the `thought`, and the position/P&L snapshot. **Selecting a
  turn moves the chart crosshair to that bar** (and vice-versa: clicking the chart
  highlights the turn). This is the "thoughts turn by turn" view tied to price.
- **Blotter** — `actions.json` as a small table (time, side, shares, price, realized).
- Graceful: a missing optional file degrades that panel, doesn't break the page.

---

## 3. Skill integration (TRADE_SIMULATOR)
1. **Start:** `recorder init` → prints the session dir; launch `replay … --out-file
   <dir>/stream.jsonl`.
2. **Each turn:** after deciding, `recorder log --session <dir> --record '<json>'`
   (the decision record above) — so thoughts/actions persist live.
3. **End:** `recorder finalize --session <dir>` → builds all artifacts + baseline
   journal; then optionally enrich `journal.md`.
4. Tell the user: `python3 -m trading.day_trading_simulator.viewer --session <id>`.

## 4. Out of scope (v1)
- Multi-session comparison / aggregate dashboards (one session at a time).
- Editing/replaying decisions from the UI (read-only viewer).
- Bundling Lightweight Charts locally (CDN; a `--vendor` copy can come later).
