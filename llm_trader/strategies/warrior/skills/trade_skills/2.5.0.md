---
name: trade-simulator
version: 2.5.0
description: Paper-trade ONE recorded setup live, minute by minute — stream its 1-min bars at one tick per wall-clock minute and make Ross Cameron momentum long-side entry/management/exit decisions in real time, then write a trade journal. Use when the user wants to "simulate trading", "paper trade", or "trade a setup" from llm_trader.
---

> **AI / tooling note**: Any edit to this file (including examples and the
> mechanical instructions below) changes the exact text the agent sees.
> A version bump **must** accompany such changes. See `MAINTAINING.md`.

# TRADE_SIMULATOR — live paced paper-trading of one recorded setup

You are the **trader**. A setup recorded by `llm_trader` (a gap-up,
low-float, high-RVOL small cap that broke out in the morning) is replayed to you
**one 1-minute bar at a time**. As each bar arrives you decide — using **Ross
Cameron's / Warrior Trading's momentum rules**
(`library/ross_cameron/all_content_structured.md`) — whether to **go long**, how to
**manage** the position (scale / stop / trail / target), and when to **exit**.
Every turn — your reasoning, fills, indicators — is recorded into a **session
folder** that the bundled web viewer renders (chart + markers + your timeline).

> Section references below like **§4**, **§9**, **§10**, **§18** point into the
> **canon** (`library/ross_cameron/all_content_structured.md`), *not* into this
> file. They are citations, not links you must open mid-run — the rule you need is
> always restated here.

**You advance through bars automatically** — as soon as you finish analyzing the
current bar and logging your decision, you immediately fetch and evaluate the next
bar. No wall-clock wait, no user prompting between bars. Read bar N, decide, log,
read bar N+1, repeat. See "Step 2 → when to stop the loop" for the exact end
condition (short version: run to `STATUS end`, unless you go flat and decide not to
take the optional §C re-entry).

This is a simulated fill environment: fills are assumed at the bar's close (no
slippage, no Level 2). Long only. One position at a time (small-account "breakout
or bailout": one round trip).

> **✅ What you are NOT responsible for (read this first — it removes most of the worry).**
> Your job is small and concrete: **each bar, apply the checklists below and log one
> record.** These things are handled *for* you — do not try to enforce or compute them:
> - **You do not police look-ahead.** It is structural, not willpower. Follow the two
>   rules in the next section and the future is simply absent from everything you read
>   — you *cannot* see it, so there is nothing to "rigorously enforce." (§No-look-ahead)
> - **You do not compute P&L, position, average cost, or R.** The recorder derives all
>   of that from the fills you report. You just report thoughts, actions, and fills.
> - **You do not manage versioning.** It is automatic (`recorder init` handles it). It
>   has zero bearing on any trading decision. See `MAINTAINING.md` if you're curious.
> - **You do not need perfect foresight.** A clean stand-down or a small bailout is a
>   *success*, not a failure. When in doubt, protect the account and journal why.
>
> So the whole task reduces to: reveal a bar → run the **ENTRY checklist** (if flat) or
> the **per-bar MANAGE procedure** (if long) → log the decision → repeat. That's it.

Run everything from the **monorepo root** — the directory that *contains* `trading/`
(on this machine `/Users/shtylenko/Projects`) — so that `import trading…` resolves.
Load the repo `.env` first: `set -a && . trading/.env && set +a`.

**Sanity-check before Step 0** (do this once; it catches the most common failure —
being in the wrong directory):

```bash
python3 -c "import trading.llm_trader" && echo OK   # must print OK
```

If it raises `ModuleNotFoundError`, you are in the wrong directory — `cd` to the
parent of `trading/` and retry. Do not proceed until it prints `OK`.

---

## ⛔ No-look-ahead protocol (the core rule — non-negotiable)

**Your entire duty here is two rules:**
> 1. **Only reveal bars with `step next`** — never by any other command or file read.
> 2. **Never open a file whose name starts with `_`** (`_sealed.jsonl`, `_step.json`).

Follow those two and you are done — you do **not** have to audit yourself, cross-check
timestamps, or "enforce" anything else. Here's *why* two rules suffice: the future is
physically absent from everything you read, so there is nothing to accidentally peek at.

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

**Fail closed, never improvise a recovery.** If anything looks wrong — you lose `$SDIR`,
a `step`/`recorder` command errors, the cursor looks inconsistent, or you're unsure
which bar you're on — **STOP and report it.** Do **not** try to recover by re-running
`step start`, forcing, re-initializing, or reading the data another way. Almost every
voided run in practice came from an agent "helpfully" recovering from confusion; an
aborted run is fine, a creative workaround is look-ahead. Your only tool for advancing
the clock is `step next`; if it isn't working, halt rather than reach around it.

---

## ⛔⛔ Shell, $SDIR and filesystem discipline (read this — batch/automated runs fail here)

**The single most common way a run becomes VOID is files landing in the wrong place.**

- You always start with `cwd` = monorepo root (the directory that *contains* `trading/`).
- `$SDIR` is a variable you capture from `recorder init`. It points to one folder under
  `trading/llm_trader/simulations/`.
- hermes terminal tool calls often run in fresh or semi-fresh shells. Shell variables
  **do not reliably survive** from one tool call to the next. You must use the captured
  value with quotes every time.
- All simulation state (`stream.jsonl`, decisions, etc.) must live **inside** `$SDIR`.
  Private files (`_sealed.jsonl`, `_step.json`) must **only** ever be created inside `$SDIR`
  by the official `step start` command.

### Golden rules (non-negotiable)

1. **Capture once, quote always**
   ```bash
   SDIR=$(python3 -m trading.llm_trader.recorder init ...)
   echo "CAPTURED_SDIR=$SDIR"
   ```
   Then **every** later command uses exactly:
   ```bash
   python3 -m trading.llm_trader.step next --session "$SDIR"
   python3 -m trading.llm_trader.recorder log --session "$SDIR" ...
   python3 -m trading.llm_trader.step start --session "$SDIR" ...
   ```

2. **Verify immediately after setup (and occasionally during long flat periods)**
   ```bash
   echo "SDIR=$SDIR"
   ls -la "$SDIR" | cat
   test -f "$SDIR/stream.jsonl" && echo "✓ stream inside SDIR" || echo "PROBLEM"
   # Check project root (cwd) for leaks. Use a command that does not contain
   # the substrings _sealed.jsonl or _step.json in its text.
   ROOT=$(pwd)
   ls -la "$ROOT" | grep -E '^[d-].*_' | head -5 || echo "✓ root is clean"
   python3 -m trading.llm_trader.step status --session "$SDIR"
   ```

3. **If private files ever appear outside $SDIR (especially in the project root):**
   - **DO NOT** run `mv`, `cp`, `cat`, `head`, `ls .../_sealed*`, or any command whose
     argument contains `_sealed.jsonl` or `_step.json`.
   - **DO NOT** try to "repair" or move them yourself.
   - Keep using only the documented commands that pass `--session "$SDIR"`.
   - The audit will still see any command that names the forbidden files and will void
     the run. Touching them guarantees a void.

4. Never run `step start` a second time. Never run `replay`, direct `fetch_*`, or
   anything that bypasses `step next`.

5. Before pasting a long sequence of OBSERVE steps, quickly re-assert:
   ```bash
   echo "Still using SDIR=$SDIR"; python3 -m trading.llm_trader.step status --session "$SDIR"
   ```

Following the two no-look-ahead rules + the $SDIR hygiene rules above keeps runs clean.

---

## Step 0 — choose the setup

Default: a random regular-session setup. Honor any ticker/date/seed the user gives.

```bash
# read ONLY the meta line for the setup you're about to trade (never the ticks):
python3 -m trading.llm_trader.replay --seed <N> --format jsonl | head -1
```

`head -1` is deliberate — it shows the `meta` line and nothing else, so you do not
see any bar before the live run. The `meta` line gives `ticker, date, entry_time,
entry_px, gap_pct, rvol, float_shares, anchor_px, reason`. `anchor_px`/`entry_px`
is the **recorded ACD/ORB breakout level** — the consolidation high that was
cleared. The first revealed `tick` is that breakout bar.

## Step 0.5 — grade the setup (5-Pillars gate — decides how you trade it)

Cameron: *"trade the best, leave the rest"* — in anything but a hot tape, **A-setups
only**. Grade the setup from the `meta` line **before** revealing any bar, and log
the grade + reasoning in your first record. (If the session was pre-sealed for you —
batch mode — the `meta` line is the first line of `$SDIR/stream.jsonl`, which you may
read.) Score the four measurable pillars:

| Pillar | Pass |
|---|---|
| Price | `entry_px` in **$2–$20** (small-account band) |
| Relative volume | `rvol ≥ 5` |
| Float | `float_shares < 10M` |
| Gap | `gap_pct > 10` |

- **Grade A** — all 4 pass. Trade the plan exactly as written below.
- **Grade B** — price is in band and `rvol ≥ 2`, but one or more soft pillars miss
  (`rvol` 2–5×, float ≥ 10M, or gap 5–10%), **or** `entry_time` is at/after
  **11:30 ET** (late-morning follow-through is the corpus's weakest window; the
  hard no-fresh-entry rule at 12:00 ET still applies on top). Trade it, but **only
  on a flawless trigger**: every entry-checklist box must pass *decisively* — no
  borderline judgment calls, no "fractionally above VWAP", no rationalizing a
  wick. When in doubt on a B, stand down. A soft-pillar miss is a *caution flag*,
  not a disqualifier — B-grade setups with clean triggers are still profitable;
  what the grade buys you is refusing the *sloppy* trigger on a weak setup.
- **Grade C (hard gate — structural, not judgment)** — `entry_px` outside
  **$2–$20**, or `rvol < 2`. **STAND DOWN — no trade, regardless of how the bars
  look.** Outside the price band the rule-set's stop math breaks: a $23 stock
  makes a $0.10–$0.30 stop pure noise (the corpus uses $0.50–$1.00 stops there,
  which the $40 risk budget can't afford), and `rvol < 2` is the corpus's hard
  momentum floor. Log one `STAND_DOWN` record citing the failed pillar; you may
  stop revealing bars and go to Step 4.

A stood-down C is a **success** (the discipline is the edge), exactly like any
other stand-down — journal why and move on.

## Step 1 — open a session folder, then seal the day

Create the session folder first — it collects every artifact and is what the web
viewer reads. Fill `<TICKER>` and `<YYYY-MM-DD>` with the `ticker` and `date` from
the **meta line you read in Step 0**, and reuse the **same `<N>`** seed:

```bash
SDIR=$(python3 -m trading.llm_trader.recorder init \
    --ticker <TICKER> --date <YYYY-MM-DD> --seed <N> --profile small)
echo "CAPTURED_SDIR=$SDIR"     # …/simulations/{YYYYMMDDHHMMSS}-{TICKER}
```

`init` stamps this run with the skill's version automatically (so results can be
grouped by rule-set later — Step 4). You don't do anything for this; if `init` prints
a `• auto-bumped skill version …` line, that's expected and needs no action. (Details
for maintainers: `MAINTAINING.md`.)

Now **seal the day** into that folder. Use the **same `--seed`/`--ticker`/`--date`**
as `init` (same seed ⇒ same setup as the Step 0 peek):

```bash
python3 -m trading.llm_trader.step start --session "$SDIR" --seed <N>
# immediately verify (see Shell discipline section)
echo "SDIR=$SDIR"; ls -la "$SDIR" | cat
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
`high_water` (best price since entry), `realized_pnl`, `bars_since_entry` (**your own**
count; the bar you filled on is `0`), `re_entries_used` (0; caps at 1 per §C),
`armed_trigger` (a buy-stop level you set on a *previous* bar, or none — §A),
`break_level` (the price you bought — your `armed_trigger`, or the breakout bar's high
for a confirmed-close entry; the §B.2 failed-break test reads this), `made_nh_since_entry`
(bool — has any bar since your fill closed a **new high above your entry bar's high**;
the §B.2 time stop reads this), a rolling **5-minute candle** aggregate
(`bars5` — §B.5), and a running bar index `i` (starts at 0). Persist each turn with `recorder log` (below) —
that file is your durable journal, so you don't keep one in your head.

Reveal the next bar with `step next` — it appends exactly one bar to the visible
stream and prints it:

```bash
python3 -m trading.llm_trader.step next --session "$SDIR"
```

The output gives the tick (or the `end` line), then a `STATUS` line:

- `STATUS ok next=<n> ended=false` → you revealed a bar. **Decide from this tick +
  everything you've already seen**, log it (below), and immediately loop — reveal
  the next bar.
- `STATUS ok next=<n> ended=true` / `STATUS end bars=<n>` → that was the last bar /
  the stream is over. If still `long`, exit at the `end` line's `close`, then
  finalize.

You are structurally unable to act ahead — `step next` only ever appends the *next*
bar, and the future is sealed away.

**When to stop the loop.** Stop when *either*:
- (a) `STATUS end` / `ended=true` arrives — the stream is over (if still `long`, exit
  at the `end` line's `close` first), **or**
- (b) you are `flat` after your final trade — meaning you have *either* already used
  your one optional §C re-entry, *or* you have decided not to take one.

Until you have made that decision, **keep revealing bars** (logging `OBSERVE`) — do
not stop the loop merely because you are momentarily flat.

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

> **Feed fields vs your own state — do not confuse them.** `bars_since_entry` and
> `is_entry_bar` on a tick are measured against the **recorded** breakout, *not your
> fill* — and you may enter later than bar 0, stand down, or re-enter. So every
> time-based rule (the §B time stop, the free-trade window) must count bars from
> **your own** entry bar, held in *your* state (§Step 2 state list) — **never** read
> the tick's `bars_since_entry`/`is_entry_bar` for that. Treat those tick fields as
> context about the recorded setup only.

### Fill model — intra-bar for hard levels, close for soft signals (read first)
Each 1-min tick gives `o, h, l, c`. **Cheat-sheet — which price triggers a fill:**

| Event | Triggers when | Fill price |
|---|---|---|
| **Armed buy-stop entry** (§A — armed on a *previous* bar) | bar's **high** `h ≥ armed_trigger` | at `armed_trigger` |
| Hard **stop** | bar's **low** `l ≤ stop` | at `stop` |
| Profit **target / scale** level | bar's **high** `h ≥ target` | at `target` |
| Soft signal (lost VWAP, topping tail, red-candle exit, new high) | judged on the **close** `c` + bar shape | at `c` |

Apply this consistently:

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
The first tick **is** the recorded breakout bar.

**Two ways to get long — buy the break itself whenever you can:**

1. **Armed buy-stop (preferred after bar 0)** — Cameron's actual entry: *"the moment
   the price breaks that candle, I do not wait for the candle to close."* Entering at
   a confirming bar's close pays up the whole bar; on a $0.10–$0.30 stop that eats a
   large fraction of every winner. So when you see a setup **forming** on closed bars,
   **arm a trigger in advance** (see "Arming the break" below) and get filled at the
   break level, not the close.
2. **Confirmed-close entry (fallback — bar 0, or a break you hadn't armed)** — the
   full checklist below passes on the current *closed* bar → enter at this bar's `c`.
   This is the only mode available on bar 0 (there was no earlier turn to arm on).

#### Which bar is "the breakout"? (objective — do not eyeball this)

On a gap-and-go the first several 1-min bars can *all* print `new_high=true` in one
vertical ramp, so "*the* first new high" is ambiguous — and that ambiguity is the
single biggest source of divergent, non-reproducible entries (one run buys the first
confirmed bar cheap with a tight stop; another calls that same bar "extended," waits,
and chases in $2 higher with a wide stop for a fraction of the size). Pin it down
mechanically instead of by feel:

> **The trigger bar is the FIRST revealed bar on which EVERY box of the ENTRY CHECKLIST
> below is simultaneously true.** That bar **is** the breakout — arm/enter it
> immediately. Earlier bars that made a new high but failed *any* box (still below
> VWAP, red, topping tail, or volume-not-yet-confirmed) were **never valid entries** —
> they are pre-break noise, not a first entry you "missed."

Two corollaries, which resolve the trap directly:

- **Never anchor "first new high" to a bar you skipped.** If you passed an earlier
  new-high bar because a box failed, that bar was not an entry — so the *next* bar that
  passes every box is still your **first** clean breakout, not an "extension" of it.
- **"Extended" is measured from the confirmed trigger, not from the first raw
  new-high.** A bar is a chase only if price has already run well past the bar where all
  boxes first aligned. The confirming bar itself is, by definition, on time — even if
  two or three *unconfirmed* new-highs preceded it. Do not talk yourself out of the
  first valid trigger by counting pre-break noise bars as part of "the move."

**ENTRY CHECKLIST — for a confirmed-close entry, go long only if EVERY box is true on
the current (closed) bar. The first bar on which they all hold is the trigger (above);
enter it. If any one fails, do NOT enter: log `OBSERVE`/`STAND_DOWN` and reveal the
next bar.**
- [ ] `new_high` is true (this bar makes a new session high — the break)
- [ ] bar is **green** (`c ≥ o`)
- [ ] `above_vwap` is true
- [ ] **volume expansion**: green-bar volume > red-bar volume over the last ~5 bars — **and** `rvol_bar ≳ 1.5–2×` *once it is populated* (see the null-rvol note below; a null `rvol_bar` on the early bars does **not** fail this box)
- [ ] **clean candle shape**: closes in the upper part of its range, `h − c < (h − l)/3` (no topping tail)
- [ ] **not extended**: this bar is the trigger (first bar all boxes align), or price is still near it — **not** a 3rd–4th bar *past a confirmed trigger* (see "Which bar is the breakout")
- [ ] **time OK**: before ~10:30–11:00 ET (or an A+ bar if later); **never** a fresh entry at/after 12:00 ET
- [ ] **MACD not against you**: `macd_hist ≥ 0` (if clearly negative, stand down)

Each box is explained below. Confirm them on the current (closed) bar before committing:

- `new_high` is true (price is making a new session high — the break), **and**
- bar is **green** (`c >= o`), **and**
- `above_vwap` is true (uptrend confirmation), **and**
- **volume expansion** — the recent **green bars carry more volume than the red bars**
  (buyers in control, not distribution — §9), **and** `rvol_bar` is clearly elevated
  (**≳1.5–2×**) *once it exists*. To judge the green/red half concretely: over roughly
  the **last ~5 revealed bars**, sum `v` on the green bars (`c ≥ o`) vs the red bars
  (`c < o`) — green total should be the larger.
  > **Null `rvol_bar` (critical — this is where the early breakout gets missed).**
  > `rvol_bar` is each bar's volume ÷ a **trailing-20-bar** average, so it is `null`
  > until ~20 bars have been revealed — i.e. for most of the prime 9:30–10:00 window
  > where these setups actually fire. **A null `rvol_bar` does NOT fail the volume box.**
  > When it is null, the **green > red dominance test above IS the volume gate** —
  > judge participation from it alone and take the trigger. Do **not** stand down on an
  > otherwise-perfect breakout merely because `rvol_bar` hasn't warmed up yet; that
  > waits out the entire early move and forces a late, wide-stop chase. Apply the
  > `≳1.5–2×` threshold only on bars where `rvol_bar` is actually populated. **And**
- **clean candle shape — the bar held its break** ("let it break, hold, then enter"
  — §18). The breakout bar must **close in the upper portion of its range** (upper
  wick < ~⅓ of the bar's range, i.e. `h − c < (h − l)/3`). A **topping tail /
  shooting star** on the breakout bar means sellers rejected the high — that is a
  failed confirmation even if every other criterion fires: **stand down** and wait
  for the next clean bar. Never rationalize past a topping tail, **and**
- **not extended (don't chase)** — you enter the **trigger bar** (the first bar all
  boxes align, per "Which bar is the breakout"), or a bar still right at it — *not* the
  3rd–4th green bar *past* a confirmed trigger. Measure "extended" from that trigger,
  **not** from the first raw new-high: unconfirmed new-high bars that preceded the
  trigger are not part of "the move" and do not make the trigger a chase. Where it
  genuinely applies: if you were flat through a confirmed trigger and price has since
  run far above VWAP in a stack of big green bodies, the easy entry is gone and a fresh
  buy there is where late longs get trapped — **stand down and wait for the
  pullback/washout** (§C), rather than chase. ("You're never going to capture the
  entire move.") A tell that you are chasing: the only structural stop now available is
  several times wider than it would have been at the trigger bar — that wide stop
  collapses your size and caps the trade's upside, which is exactly the late-entry trap.

**Time-of-day (volume fades late morning).** These are morning gap-ups, so most
breakouts fire early. But follow-through weakens as the session ages: the open and
first ~90 minutes are prime; after **~10:30–11:00 ET** volume dries up and breakouts
fade. If the `time` on your breakout bar is late morning, demand an A+ bar (strong
`rvol_bar`, clean green, well clear of VWAP) or **stand down**. Never open a fresh
momentum entry around/after **12:00 ET**.

**MACD confirmation (filter, not a trigger — §4.6):** do **not** enter *against* the
MACD. Prefer `macd_hist ≥ 0` (MACD line at/above signal). If `macd_hist` is clearly
negative (a fresh bearish crossover / fading momentum) while the criteria above
fire, treat the breakout as suspect — demand a cleaner bar or stand down. Never let a
positive MACD *alone* pull you into a trade; it only confirms a pattern already firing.

If all hold → **GO LONG** (confirmed-close mode), fill at this bar's `c` — **this
close is your `avg_entry`** (not `anchor_px`).

#### Where the stop goes (objective — do not eyeball this either)

Stop placement is the twin of the trigger-bar rule: it sets `stop_distance`, which
sets share count AND every R multiple, so two readings of "structural low" turn one
identical entry into a 45-share trade and a 666-share trade. Pin it down:

> **stop = min(trigger bar's low, the prior bar's low) − $0.01.**
> (On bar 0 there is no prior bar: use the trigger bar's low − $0.01.)
> One formula, computed from bars you have already revealed. That is the two-bar
> structure the break actually cleared — Cameron's "my stop is the low of that
> pullback, it's as simple as that," expressed on the 1-min feed.

Hard corollaries:

- **The stop is NEVER above the trigger bar's own low.** A stop parked a few cents
  under your fill (or under `anchor_px`) usually sits *inside* the trigger bar's
  range — that is one bar's ordinary noise, and it is a donation. If a stop like
  that survives, it is luck, not edge: do not let a tight-stop reading inflate your
  share count 10× on a wide-range breakout bar.
- **Do not use `anchor_px` for stop placement at all.** It is a 5-minute reference
  level; your risk is defined by the 1-min structure you actually entered on.
- **A wide trigger bar means a wide stop and a SMALL position — accept it.** The
  $0.10–$0.30/share range is a **sizing cap**, not a placement rule: if the formula
  gives more than ~$0.30, cut shares per Step 3 (never widen or tighten the stop to
  hit a share count). If the resulting position rounds to 0 shares, skip the trade.

Then `stop_distance = avg_entry − stop`, size the position (Step 3), and journal the
entry with the rule that fired.

#### Arming the break (armed buy-stop — the preferred entry after bar 0)

When flat and you can see a setup **coiling** on the bars you've already revealed —
a 1–3 bar micro-pullback or flat base holding **above VWAP**, green-bar volume still
dominant over the last ~5 bars, `macd_hist ≥ 0`, time-of-day OK, not extended —
**arm a buy-stop** instead of waiting for the breakout bar to close:

- `armed_trigger = (high of the base / the session_high being coiled under) + $0.01`
- planned **stop** = `(lowest low of the base bars named in the arm) − $0.01` — the
  same objectivity rule as above: a specific low of specific revealed bars, never a
  cent-offset from the trigger, and never above the last closed bar's low at arm time.
- if `armed_trigger − stop` is wider than ~$0.30, that is a **sizing** problem, not a
  placement one: keep the stop, cut shares per Step 3, or pass on the arm.

**Log the arm on the bar you decide it** (an `OBSERVE` record with
`note:"ARM trigger=<px> stop=<px>"` and the `stop` field set). An arm is only valid
if it appears in a **previous** bar's logged record — never fill yourself
retroactively at a trigger you didn't log in advance.

On the **next** bar:
- `h ≥ armed_trigger` → you are **FILLED at `armed_trigger`** — unconditionally,
  even if that bar closes red or ugly. That is the real risk of buying the break;
  the failed-break bailout (§B.2) handles it, exactly as it does for Cameron.
  `avg_entry = armed_trigger`; the pre-planned stop stands. Log `ENTER`.
- `h < armed_trigger` → not filled. Re-evaluate on this closed bar: keep the arm,
  re-arm at a new level, or cancel (e.g. VWAP lost, MACD flipped negative, base
  broke down). Log the decision either way.

One armed trigger at a time; every checklist idea above (volume dominance, MACD,
not-extended, time-of-day) is judged on **closed bars at arm time** — the touch
itself is the `new_high` box firing in real time.

If the breakout bar **fails** confirmation (red, below VWAP, or limp `rvol_bar`): do
not chase, and do not wait passively for another bar to *close* well — **arm the
break** (above) over the level that bar failed at, if the base is still holding VWAP
with green-vol dominance. If no clean arm sets up within **~10–15 minutes**, or price
loses VWAP and trends down, **stand down — no trade** (a no-trade is a valid,
disciplined outcome; journal why).

### B. MANAGE (while `long`) — "Breakout or Bailout"

**PER-BAR PROCEDURE — on every bar while long, walk this list top-to-bottom and act on
the FIRST item that applies, then log and move to the next bar:**
1. Hard stop hit (`l ≤ stop`)? → **exit all at `stop`**, trade over.
2. Soft bailout — walk the §B.2 **predicate ladder** (failed break → lost VWAP → topping-tail rejection → time stop); the first predicate `true` on the *closed* bar → **exit all at close**, trade over.
3. Not yet at break-even and price popped ~+$0.10? → **raise stop to `avg_entry`** (free trade).
4. Reached a scale level (+1R, then +2R / resistance)? → **sell ⅓** there, stop to break-even.
5. Holding the runner and a completed red **5-min** candle closed below the prior green 5-min candle's low? → **sell the remainder at close**.
6. (Optional) strong continuation and you have conviction? → **add** (pyramid), then re-anchor the stop.
7. None of the above → **hold**, log `OBSERVE`.

Detail for each rule follows (the list below adds the profit-**target** rationale
behind the scale levels as its last item):

1. **HARD STOP (intra-bar, highest priority)** — if `l ≤ stop`, you are **out at
   `stop`**. No close check; the level was hit. This is the bailout.
2. **SOFT BAILOUT — the predicate ladder (close-confirmed, exit all at `c`).**
   On every *completed* bar while `long`, evaluate the four predicates **in order**;
   the **first** one that is `true` exits the whole position at the bar's close, trade
   over. Every predicate reads only revealed fields and your own state
   (`avg_entry`, `stop_distance`, `break_level`, `bars_since_entry`, `high_water`,
   `made_nh_since_entry`) — **no feel-call.** This objectifies Cameron's
   breakout-or-bailout tree into a reproducible ladder (why: two runs of the same
   version diverged on "did the break fail?" — see `IMPROVING.md` §2).

   Let `k = bars_since_entry` (your own count; the bar you filled on is `k = 0`).

   - **(a) Failed break** — *only while `k ≤ 1`* (the entry bar and the one after):
     `c < break_level`. The bar closed back below the level you bought → the pattern
     failed; the cheapest exit is now. Cameron's tree is literal: *entry candle closes
     green AND above the breakout level → hold; anything else → bail.* Do **not** wait
     for VWAP loss or the hard stop.
   - **(b) Lost VWAP** — *only while `k ≥ 2`* (after the break has had its 1–2 bars):
     `c < vwap` (i.e. `above_vwap` is false) on the completed bar → trend broken, exit.
   - **(c) Topping-tail rejection** — a completed **red** bar that tested a new high and
     got sold. All four must hold, with `upper_wick = h − max(o, c)` and
     `body = |c − o|`:
     `c < o` **and** `h ≥ high_water` **and** `upper_wick ≥ 2 × body` **and**
     `upper_wick ≥ 0.5 × stop_distance`. (A real distribution wick off the highs, not a
     one-tick noise wick.)
   - **(d) Time stop** — `k ≥ 5` **and** `made_nh_since_entry` is false **and**
     `c < avg_entry + 0.25 × stop_distance` (five bars, no new high, not even ¼R green →
     "almost immediate resolution" failed; stop paying the time premium).

   **MACD is deliberately NOT on this ladder.** `macd_hist < 0` on **2+ consecutive
   closed bars** is, on its own, a *tighten-the-stop-to-break-even / take-profits-into-it*
   confirmation (§4), **never** a stand-alone soft-bailout trigger — one bar of negative
   histogram on a 1-min feed is noise, and a genuine momentum failure will already trip
   (b) lost-VWAP or (c) red-rejection. Never bail on MACD alone.
3. **FREE TRADE (move to break-even early)** — the "10-cent" rule. If, within the
   **first bar or two** after entry, your `high_water` (best price since entry)
   reaches ~**avg_entry + $0.10** (or +~1/3 of your stop_distance, whichever comes
   first) and price holds, **raise the stop to your `avg_entry`**. Now the trade is risk-free ("essentially a free trade"), so a fade
   back through entry takes you out flat instead of at a full stop. This is *before*
   any scale-out and is the single biggest cut to average-loss size. Never move the
   stop back down.
4. **SCALE OUT in thirds** into strength (§4/§10 — his standard exit plan, all
   three tiers):
   - **First 1/3 at ~+1R** (`avg_entry + stop_distance`) or the first clear
     resistance (e.g. `pm_high`, prior-day level, a round number) — touch-filled
     (`h ≥` level). Move the stop on the remainder to **break-even** if not
     already there.
   - **Second 1/3 on the extended move** — ~+2R or the *next* marked resistance /
     a retest of `session_high`, again touch-filled into strength.
   - **Final 1/3 is the runner** — it rides with the break-even hard stop and
     exits only on the red-candle rule (step 5) or a hard-stop/soft-bailout hit.
   Scale out **slowly into strength** — sell into the up-move, don't dump the whole
   position on one bar, and don't collapse the three tiers into one exit.
5. **RUNNER EXIT (close-confirmed, on the 5-MINUTE lens) + TRAIL.** The runner's
   exit signal is Cameron's final-exit rule: the **first red candle that closes
   below the prior green candle's low** → sell the remainder at the current bar's
   close. **Judge this rule on rolling 5-minute candles, not raw 1-min bars.**
   Cameron's primary chart is the 5-minute (the 1-min is for fine timing only);
   applying his red-candle rule to every 1-min bar sells the runner into one bar
   of ordinary noise, which is why past runs captured only ~25–30% of the
   favorable move. Build the 5-min view in your state from bars you've already
   revealed (no new data involved):
   - **Aggregation**: group revealed 1-min bars into clock-aligned 5-min buckets
     (`:00–:04`, `:05–:09`, …): `o` = first bar's `o`, `h` = max `h`, `l` = min `l`,
     `c` = last bar's `c`, `v` = Σ`v`. A 5-min candle is **complete** only when
     you've revealed its last 1-min bar (or the stream ends).
   - **Exit signal**: the first **completed red 5-min candle** that closes below
     the prior **green 5-min candle's low** → sell the remainder at the current
     1-min bar's `c`.
   - Everything else stays on the 1-min feed: the hard break-even stop, scale-out
     touch levels, the VWAP soft bailout. The runner is already risk-free behind
     the break-even stop — giving it 5-min room risks nothing below your entry.
   Do **not** trail a hard intra-bar stop a few
   cents under every swing low (that gets wicked out of runners for pennies; the
   only hard stop on the runner is break-even, or higher once real structure
   forms). On a strong runner you may ratchet the hard stop up under a *major*
   completed **5-min** swing low or the `ema20` once price is multiple R above it —
   but the working exit is the red-candle close, not the wick-stop. Never loosen a stop.
6. **ADD / SCALE IN (pyramiding — optional, only with conviction, §10)**. Add to a
   *winner*, never a loser. The three-step pyramid:
   - **Starter** = your 1/3 entry position (already on).
   - **Add #2** when the **first bar since entry closes green and above your entry** —
     confirmation the break held. Your average cost rises (up-average), which is the
     point: you only pay up because the trade is already working.
   - **Add #3** on a fresh **green new-high continuation** bar with healthy `rvol_bar`
     **and MACD still supportive** (`macd_hist ≥ 0`).
   After any add, **re-anchor the stop off your new (higher) average** so total open
   risk stays inside `risk_budget`. **Never add to a red bar, into an extended/parabolic
   bar, into a negative MACD, and never average down.** Skip pyramiding entirely if the
   tape is choppy or volume is thin — one clean entry/exit beats a bad pyramid.
7. **TARGET**: aim for **2:1** as a ceiling but accept the realized **~1:1** — the
   blended average lands near 1:1 because the first third banks at 1R and losers
   bail small; the edge is win rate, not R:R. The primary target is a retest/break
   of the day's high or the next marked resistance. Scaling out in thirds (step 4)
   is how you bank it while still giving the runner a chance at the outsized move.

Always be **flat by session end** — never hold overnight. If the `end` line arrives
while still long, exit at the `end` line's `close`.

### C. RE-ENTRY after a bailout (optional — Cameron's favorite second leg)
Default remains **one round trip**. But Cameron's two favorite setups are *second-leg*
entries after a first move fails — "I can always get back in if there's another setup."
So after you've **exited/bailed and are flat**, you MAY take **at most one** re-entry on
the same ticker *if* a clean qualifying setup re-forms before the stream ends. Still
**one position at a time**; never re-enter while already long, and never to "make back"
the prior loss (that's the loser cognitive loop — a re-entry must be a genuine A-setup
on its own merits, not revenge).

**Cooldown (mandatory): a re-entry is never the same fight re-joined.** After any
exit — failed-break bailout, stop-out, or soft bailout — you must see **at least 3
full bars flat** before entering again, and those bars must show a **fresh base**:
holding above VWAP (or, for the sub-VWAP trap, the completed washout structure),
with green-vol dominance re-established. Re-entering 1–2 bars after a bailout into
the same chop is exactly the pattern that loses — the first exit told you the tape
is choppy, and the corpus's answer to chop is *fewer* entries, not faster ones. If
the setup can't survive a 3-bar wait, it was never an A-setup.

**Either** of the two patterns below qualifies — they are **alternatives, not a
classification you must decide between**. You are not labelling the setup; you are just
watching for *whichever* one appears. If neither appears cleanly, you take no re-entry.

- **Sub-VWAP trap / washout reclaim** (his #1 intraday setup): price spiked, then
  washed **below VWAP** (`above_vwap` false) trapping late longs, then **reclaims VWAP**
  (`above_vwap` flips back true) on a green bar with renewed `rvol_bar`. Enter on the
  reclaim; **stop below the washout low**; target a retest of `session_high`.
- **Fresh new-high after consolidation**: price bases sideways above VWAP, then prints a
  clean green `new_high` bar meeting the full §A entry criteria (incl. MACD support).

If neither re-forms cleanly, **stay flat** — a disciplined single round trip is the
success case, not a failure. Apply the same sizing (Step 3), the free-trade/BE rule,
scaling, and exits to the re-entry, and journal it as a distinct trade.

### Each tick → log one decision record (this is the artifact the viewer shows)
After deciding on a bar, **persist the turn** with `recorder log` — one record per
processed bar, so your reasoning and fills are saved live:

```bash
python3 -m trading.llm_trader.recorder log --session "$SDIR" --record \
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

**Stop-width sanity**: the $0.10–$0.30/share band assumes a $2–$20 stock. If the
*structural* stop needs to be wider than ~$0.30 to sit outside ordinary bar noise
(typical once `entry_px` > $20, where the corpus itself uses $0.50–$1.00 stops),
this profile cannot afford the trade — that setup is a Step 0.5 grade-C: stand
down rather than trade it with a noise stop that gets wicked out.

Cash P&L accrues as `Σ shares_scaled × (exit_px − avg_entry)` across every scale-out
and the final exit. Express the result in **R multiples** too (`realized $ / risk_budget`).
Cameron's daily targets for context: **+$200 (10%) good day; −$200 stop for the day.**

## Step 4 — finalize the session, then view it

When you hit `STATUS end` (and are flat), build all viewer artifacts from the raw
stream + your decision log:

```bash
python3 -m trading.llm_trader.recorder finalize --session "$SDIR"
```

This writes `session.json`, `bars.json`, `actions.json`, `decisions.json`,
`pnl.json`, and a baseline `journal.md` into the folder, computing P&L/R/MFE
deterministically from your fills (`SIMULATION_VIEWER_SPEC.md`). If you left a
position open it is auto-flattened at the session close and flagged.

Then **enrich `journal.md`** with a short Cameron-style post-mortem (append to the
file): did the pattern resolve or did you bail? Did you follow the plan or was it an
execution miss? One lesson.

**Cross-session review (5-Step System, steps 2 & 5 — "analyze historical data").**
After the single-trade post-mortem, aggregate every recorded session so lessons
compound instead of resetting each day. Group by **skill version** — this is how
you tell whether a rule change actually improved profitability:

```bash
python3 -m trading.llm_trader.recorder report --by-version
# version         n  win%       P&L   avgR  notes   (numbers below are illustrative)
# unversioned    10   80%   $179.64   0.45
# 2.0.0           3   67%    $48.20   0.40
```

Append that table to `journal.md`, and for **this** session also note its
**MFE-capture** (realized $/share ÷ `mfe_per_share` — how much of the favorable
move you kept). Then name **one thing to improve tomorrow** — a single concrete
rule tweak or execution fix, not a vague intention. If a rule tweak is warranted,
just edit the rules — the next `init` auto-versions the change, so those runs land
in a fresh cohort automatically.

Finally, **(re)start the viewer and hand the user a live URL**. Always kill any
existing listener on the port first — a long-running viewer keeps serving whatever
code it loaded at launch, so a stale instance can shadow the current code (and an
old single-threaded build freezes the moment the browser opens its live-update
stream). Kill, then start fresh in the background:

```bash
FOLDER=$(basename "$SDIR")
# kill any viewer already bound to :8765 so we never serve stale code
lsof -nP -tiTCP:8765 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null; sleep 1
nohup python3 -m trading.llm_trader.viewer --session "$FOLDER" --no-browser \
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
- **One position at a time** (small-account = one round trip per day; at most one
  optional re-entry per §C, never concurrent).
- **Every action cites a rule** from the strategy doc — no discretionary drift.
- Fills at bar close; no slippage / Level 2 / time-and-sales (we don't have them).
  Note this assumption in the journal.
- A clean **stand-down / small bailout is success**, not failure — "get really good
  at losing." Protecting the account beats forcing a trade.
