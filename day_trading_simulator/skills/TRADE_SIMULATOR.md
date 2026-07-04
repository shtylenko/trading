---
name: trade-simulator
description: Paper-trade ONE recorded setup live, minute by minute — stream its 1-min bars at one tick per wall-clock minute and make Ross Cameron momentum long-side entry/management/exit decisions in real time, then write a trade journal. Use when the user wants to "simulate trading", "paper trade", or "trade a setup" from day_trading_simulator.
---

# TRADE_SIMULATOR — live paced paper-trading of one recorded setup

You are the **trader**. A setup recorded by `day_trading_simulator` (a gap-up,
low-float, high-RVOL small cap that broke out in the morning) is replayed to you
**one 1-minute bar at a time**. As each bar arrives you decide — using **Ross
Cameron's / Warrior Trading's momentum rules**
(`library/analyst_warrior_trading_strategy.md`) — whether to **go long**, how to
**manage** the position (scale / stop / trail / target), and when to **exit**.
Every turn — your reasoning, fills, indicators — is recorded into a **session
folder** that the bundled web viewer renders (chart + markers + your timeline).

**You advance through bars automatically** — as soon as you finish analyzing the
current bar and logging your decision, you immediately fetch and evaluate the next
bar. No wall-clock wait, no user prompting between bars. Read bar N, decide, log,
read bar N+1, repeat until flat after exit or the stream ends.

This is a simulated fill environment: fills are assumed at the bar's close (no
slippage, no Level 2). Long only. One position at a time (small-account "breakout
or bailout": one round trip).

Run everything from the monorepo root `/Users/shtylenko/Hermes/projects` with the
repo-root `.env` loaded (`set -a && . trading/.env && set +a`).

---

## ⛔ No-look-ahead protocol (the core rule — non-negotiable)

**Every entry/exit decision must be made from past and current ticks only — never
from a bar that has not yet been revealed.** This is enforced **physically** by a
sealed source with incremental reveal — the future is not in any file you read:

1. **Sealed source.** `step start` generates the *entire* day **once** into a
   **private** `_sealed.jsonl` (leading underscore = off-limits; it holds the
   future) and reveals **only** the `meta` line into the visible `stream.jsonl`.
2. **Incremental reveal.** Each `step next` appends **exactly one** more bar to the
   visible `stream.jsonl` and prints it. The visible file — the only stream file
   you ever read — therefore contains **only past + current bars**; the next bar
   is not written to it until you ask for it. There is no `peek`; you cannot pull a
   bar you haven't revealed.

So you may read `stream.jsonl` freely and still not see the future. Only the
clearly-marked `_sealed.jsonl` holds the whole day, and that file is off-limits.

**Forbidden (these are look-ahead, even if indirect) — never do any of them:**
- ❌ reading `_sealed.jsonl` (it contains the whole day) or the private
  `_step.json` cursor state;
- ❌ running `replay` or `step start` again with different parameters after the
  session has started, or running `replay` in `--format human` / with `head`/`tail`
  to see bars beyond what you've revealed;
- ❌ calling `fetch_bars` / `fetch_minute_bars` / the replay internals directly to
  pull the day's bars;
- ❌ reading `entries.db`, the `.csv`/`.txt` dumps, or any other file to infer how
  the day went;
- ❌ using your own prior knowledge of this ticker/date. Decide blind, bar by bar.

If you ever already know what happens later in the session, the simulation is void —
stop and say so rather than producing a tainted journal.

---

## Step 0 — choose the setup

Default: a random regular-session setup. Honor any ticker/date/seed the user gives.

```bash
# read ONLY the meta line for the setup you're about to trade (never the ticks):
python3 -m trading.day_trading_simulator.replay --seed <N> --format jsonl | head -1
```

`head -1` is deliberate — it shows the `meta` line and nothing else, so you do not
see any bar before the live run. The `meta` line gives `ticker, date, entry_time,
entry_px, gap_pct, rvol, float_shares, anchor_px, reason`. `anchor_px`/`entry_px`
is the **recorded ACD/ORB breakout level** — the consolidation high that was
cleared. The first revealed `tick` is that breakout bar.

## Step 1 — open a session folder, then seal the day

Create the session folder first — it collects every artifact and is what the web
viewer reads:

```bash
SDIR=$(python3 -m trading.day_trading_simulator.recorder init \
    --ticker <TICKER> --date <YYYY-MM-DD> --seed <N> --profile small)
echo "$SDIR"     # …/simulations/{YYYYMMDDHHMMSS}-{TICKER}
```

Now **seal the day** into that folder. Use the **same `--seed`/`--ticker`/`--date`**
as `init` (same seed ⇒ same setup as the Step 0 peek):

```bash
python3 -m trading.day_trading_simulator.step start --session "$SDIR" --seed <N>
```

`step start` writes the whole day to a **private** `_sealed.jsonl` and reveals
**only** the `meta` line into the visible `$SDIR/stream.jsonl`. No bars are visible
yet — you reveal them one at a time in the loop below. This is the physical
no-look-ahead guarantee: the future lives only in `_sealed.jsonl`, which you never
read.

> You read only `$SDIR/stream.jsonl`, and only through `step next` (below) — never
> `cat`/`tail`/`grep` it for bars, and never open `_sealed.jsonl`.

## Step 2 — the trading loop (reveal one bar at a time, auto-advance)

The agent drives this loop automatically: reveal bar N, decide, log, reveal bar N+1,
repeat. No user prompting between bars.

Keep a small **state**: `position ∈ {flat, long}`, `shares`, `avg_entry`, `stop`,
`high_water` (best price since entry), `realized_pnl`, `bars_since_entry`, and a
running bar index `i` (starts at 0). Persist each turn with `recorder log` (below) —
that file is your durable journal, so you don't keep one in your head.

Reveal the next bar with `step next` — it appends exactly one bar to the visible
stream and prints it:

```bash
python3 -m trading.day_trading_simulator.step next --session "$SDIR"
```

The output gives the tick (or the `end` line), then a `STATUS` line:

- `STATUS ok next=<n> ended=false` → you revealed a bar. **Decide from this tick +
  everything you've already seen**, log it (below), and immediately loop — reveal
  the next bar.
- `STATUS ok next=<n> ended=true` / `STATUS end bars=<n>` → that was the last bar /
  the stream is over. If still `long`, exit at the `end` line's `close`, then
  finalize.

You are structurally unable to act ahead — `step next` only ever appends the *next*
bar, and the future is sealed away. Stop the loop when you are `flat` after an exit,
or on `STATUS end`.

### Tick fields you decide on
`time, o,h,l,c, v, cum_vol, vwap, ema9, ema20, macd, macd_signal, macd_hist,
session_high, new_high, above_vwap,
rvol_bar (this bar's vol ÷ trailing-20-bar avg — your volume-expansion gauge),
vs_anchor_pct, bars_since_entry, is_entry_bar`. `ema20` is the slower pullback
reference (Cameron uses the 9- or 20-EMA); `macd`/`macd_signal`/`macd_hist` are the
12/26/9 MACD — a **trend-confirmation filter** (§4.6), used only *with* the pattern,
never as a standalone trigger: `macd_hist > 0` and rising (MACD above signal) =
momentum intact; a negative crossover / shrinking histogram = momentum fading.
From the `meta` line you also have
reference levels: `prior_close, prior_high, prior_low, pm_high, pm_low` (mark these
as support/resistance — e.g. a push into `pm_high` or a round number is where you
expect a fight) and `anchor_px` with its `anchor_note` (read it).

> **anchor_px vs your fill.** `anchor_px`/`entry_px` is the recorded **5-minute**
> breakout level. The 1-minute bar you actually enter on can sit **below** it (a
> 5-min candle spans five 1-min bars). So: **your entry price is the 1-min bar's
> close where you commit, not `anchor_px`.** Track all P&L, stops, and R from *your*
> fill. `vs_anchor_pct` is provided for context only — it is measured against
> `anchor_px`, not your fill.

### Fill model — intra-bar for hard levels, close for soft signals (read first)
Each 1-min tick gives `o, h, l, c`. Apply this consistently:

- **Hard price levels are intra-bar.** A **hard stop** triggers when the bar's
  **low** crosses it (`l ≤ stop`), not when the close does — that's how a real stop
  fills. Assume the fill **at the stop level** (no slippage). Likewise a **profit
  target / scale level** triggers when the bar's **high** reaches it (`h ≥ target`),
  filled **at the target level**. (Touch, not close.)
- **Soft / discretionary signals are close-confirmed.** "Lost VWAP", "topping tail",
  "big red candle", "made a new high" are judged on the **closed bar** (`c`, and the
  bar's shape) — you don't bail on a wick that reclaims. This matches Cameron: the
  hard stop is a price; trend-loss is a candle *closing* through the line.

### A. ENTRY (while `flat`) — the ACD / ORB breakout
The first tick **is** the recorded breakout bar. Confirm Cameron's entry criteria on
the current (closed) bar before committing:

- `new_high` is true (price is making a new session high — the break), **and**
- bar is **green** (`c >= o`), **and**
- `above_vwap` is true (uptrend confirmation), **and**
- **volume expansion** — `rvol_bar` is clearly elevated (**≳1.5–2×**; the breakout
  bar should show participation, not drift).

**MACD confirmation (filter, not a trigger — §4.6):** do **not** enter *against* the
MACD. Prefer `macd_hist ≥ 0` (MACD line at/above signal). If `macd_hist` is clearly
negative (a fresh bearish crossover / fading momentum) while the four criteria above
fire, treat the breakout as suspect — demand a cleaner bar or stand down. Never let a
positive MACD *alone* pull you into a trade; it only confirms a pattern already firing.

If all hold → **GO LONG**, fill at this bar's `c` — **this close is your `avg_entry`**
(not `anchor_px`). Set the initial **stop**:

- **default:** just below the breakout/consolidation low — `anchor_px − a few cents`
  — *but only if that sits below your fill.*
- **if your fill is below `anchor_px`** (common — see the anchor note: you entered on
  a 1-min bar inside the 5-min candle), an anchor-based stop would be *above* your
  entry, which is nonsensical. **Use a fixed small stop below your fill instead:
  `avg_entry − $0.10…$0.30`** (low end for low float), or just under the entry bar's
  own low if tighter.

Then `stop_distance = avg_entry − stop`, size the position (Step 3), and journal the
entry with the rule that fired.

If the breakout bar **fails** confirmation (red, below VWAP, or limp `rvol_bar`): do
not chase. Wait for the next bar that makes a clean green new high while holding VWAP.
If none appears within **~10–15 minutes**, or price loses VWAP and trends down,
**stand down — no trade** (a no-trade is a valid, disciplined outcome; journal why).

### B. MANAGE (while `long`) — "Breakout or Bailout"
Evaluate every tick, in this priority order:

1. **HARD STOP (intra-bar, highest priority)** — if `l ≤ stop`, you are **out at
   `stop`**. No close check; the level was hit. This is the bailout.
2. **SOFT BAILOUT (close-confirmed, exit all)** if, on the *closed* bar, any of:
   - price **closes back below VWAP** after the move (`above_vwap` flips false) —
     trend broken, or
   - a **large red candle / topping tail** rejects a push (big upper wick: `h` far
     above `c`, bar red) — distribution into strength, or
   - **MACD rolls over** — `macd_hist` flips clearly negative / `macd` crosses below
     `macd_signal` after the move: momentum has faded. On its own this is a *tighten
     the stop / take profits into it* signal (a confirmation, per §4.6), not a
     stand-alone panic exit — combine it with price (lost VWAP, red rejection), or
   - **time stop**: `bars_since_entry ≥ 5` and the position has **not made a new
     high** since entry and is not meaningfully green ("almost immediate resolution"
     — if it just sits, get out).
3. **SCALE OUT** into strength — on a **touch** (`h ≥`) of the first clear resistance
   (e.g. `pm_high`, prior-day level, a round number) or about **+1R**
   (`avg_entry + stop_distance`): sell **1/3–1/2** filled at that level, and **move
   the stop on the remainder to break-even**. Bank the win; let the rest work
   risk-free.
4. **TRAIL** the remainder once up ≳1R: ratchet the stop up to just under the most
   recent swing low or a moving average (`ema9` for a tight trail, `ema20` for a
   looser one on a strong runner; ≈10–20¢). Never loosen a stop.
5. **ADD** (optional, only with conviction): on a fresh **green new-high
   continuation** bar that closes above VWAP with healthy `rvol_bar` **and MACD still
   supportive** (`macd_hist ≥ 0`), you may add. **Never add to a red or extended bar,
   into a negative MACD, and never average down.**
6. **TARGET**: aim for **2:1** as a ceiling but accept the realized **~1:1**; the
   primary target is a retest/break of the day's high or the next marked resistance.
   Scaling out (step 3) is how you bank it.

Always be **flat by session end** — never hold overnight. If the `end` line arrives
while still long, exit at the `end` line's `close`.

### Each tick → log one decision record (this is the artifact the viewer shows)
After deciding on a bar, **persist the turn** with `recorder log` — one record per
processed bar, so your reasoning and fills are saved live:

```bash
python3 -m trading.day_trading_simulator.recorder log --session "$SDIR" --record \
  '{"i":<i>,"time":"<HH:MM>","thought":"<your reasoning for THIS bar — cite the rule>","action":"<OBSERVE|ENTER|ADD|SCALE|TRAIL|EXIT|STAND_DOWN>","fill_px":<price or null>,"shares_delta":<+buy/-sell or null>,"stop":<current stop or null>,"note":"<short tag>"}'
```

`i` is the revealed bar's index (0,1,2,…) — it must **strictly increase** across
your log calls; the recorder rejects a duplicate or out-of-order `i` (a retried
turn must not re-log a bar).

- `thought` is the heart of the timeline — explain what you see and which rule fires.
- Set `fill_px` + `shares_delta` **only on a fill** (ENTER/ADD/SCALE/EXIT); leave
  them `null` for OBSERVE/TRAIL. `stop` carries the current stop for the chart line.
- **You don't compute P&L** — the recorder derives position, avg entry, realized and
  unrealized from your fills (average-cost). Just report thoughts, actions, fills.
- Log every turn you act on (including plain `OBSERVE` holds) so the timeline is
  continuous; at minimum log every fill and every bar where your thesis changes.

## Step 3 — position sizing (small-account profile, default)

```
risk_budget   = $40           # Cameron small-account per-trade max loss ($30–$50)
buying_power  = $2,000 × 6     # Webull 6× on the $2k challenge = $12,000
stop_distance = avg_entry − stop          # $/share you risk
shares        = min( floor(risk_budget / stop_distance),
                     floor(buying_power / avg_entry) )
```

Cash P&L accrues as `Σ shares_scaled × (exit_px − avg_entry)` across every scale-out
and the final exit. Express the result in **R multiples** too (`realized $ / risk_budget`).
Cameron's daily targets for context: **+$200 (10%) good day; −$200 stop for the day.**

## Step 4 — finalize the session, then view it

When you hit `STATUS end` (and are flat), build all viewer artifacts from the raw
stream + your decision log:

```bash
python3 -m trading.day_trading_simulator.recorder finalize --session "$SDIR"
```

This writes `session.json`, `bars.json`, `actions.json`, `decisions.json`,
`pnl.json`, and a baseline `journal.md` into the folder, computing P&L/R/MFE
deterministically from your fills (`SIMULATION_VIEWER_SPEC.md`). If you left a
position open it is auto-flattened at the session close and flagged.

Then **enrich `journal.md`** with a short Cameron-style post-mortem (append to the
file): did the pattern resolve or did you bail? Did you follow the plan or was it an
execution miss? One lesson.

Finally, **(re)start the viewer and hand the user a live URL**. Always kill any
existing listener on the port first — a long-running viewer keeps serving whatever
code it loaded at launch, so a stale instance can shadow the current code (and an
old single-threaded build freezes the moment the browser opens its live-update
stream). Kill, then start fresh in the background:

```bash
FOLDER=$(basename "$SDIR")
# kill any viewer already bound to :8765 so we never serve stale code
lsof -nP -tiTCP:8765 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null; sleep 1
nohup python3 -m trading.day_trading_simulator.viewer --session "$FOLDER" --no-browser \
    >/tmp/day_trading_viewer.log 2>&1 &
sleep 2
echo "open: http://127.0.0.1:8765/viewer/index.html?session=$FOLDER"
```

Then tell the user to open that URL (hard-reload with Cmd-Shift-R if a stale tab is
still spinning). It shows the TradingView-style chart with your entries/exits,
indicators, and the turn-by-turn reasoning timeline.

---

## Fidelity & guardrails (read before trading)
- **No look-ahead.** Reveal bars only via `step next`, one at a time; the future is
  sealed in `_sealed.jsonl` (which you never read), so you are structurally unable to
  act on future data. Never pull bars by any other path.
- **Long only** (Cameron only buys; the user can't short).
- **One position at a time** (small-account = one round trip per day).
- **Every action cites a rule** from the strategy doc — no discretionary drift.
- Fills at bar close; no slippage / Level 2 / time-and-sales (we don't have them).
  Note this assumption in the journal.
- A clean **stand-down / small bailout is success**, not failure — "get really good
  at losing." Protecting the account beats forcing a trade.
