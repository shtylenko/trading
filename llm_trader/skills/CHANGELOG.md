# TRADE_SIMULATOR experiment log

One row per behavioral version: the hypothesis, the batch that tested it, the paired
result vs its baseline, and the promote/revert decision. Keeps future maintainers from
re-trying dead ends. Append newest at the top. See `IMPROVING.md` for the protocol.

Columns: **version** · **hypothesis** · **baseline→candidate batch tags** ·
**paired ΔR / sign-p** (`batchsim compare`) · **decision**.

---

### 2.7.0 / 2.8.0 — decompose the 2.6.0 REJECT into its two halves  ⏳ CANDIDATES — NOT YET VALIDATED
- **Why:** 2.6.0 (bundle) was REJECT (mean ΔR −0.046, more stand-downs). It conflated
  two independent changes; the gate can't attribute the regression. Both are rebuilt
  **off 2.4.1** (the accepted baseline) so `2.7.0 ⊕ 2.8.0 ≈ 2.6.0` — a clean partition.
  The `break_level` bug fix rides in 2.7.0 (it's a correctness fix, part of the ladder).
- **2.7.0 = 2.4.1 + EXIT-side only** (`archive/TRADE_SIMULATOR@2.7.0.md`): the §B.2
  4-predicate soft-bailout ladder (a failed-break `c<break_level` / b lost-VWAP / c
  topping-tail / d time-stop), `break_level`+`made_nh_since_entry` state, free-trade BE
  as an every-bar predicate, runner "prior green" = most-recent-completed-green, washout
  `washout_low` tracking. **Entry checklist is verbatim 2.4.1** (fuzzy ~5-bar volume,
  ≳1.5–2× rvol, "clearly negative" MACD, "A+ bar", Grade-B "decisively" all unchanged).
  *Isolates: do crisper EXITS alone help?* Hypothesis: cuts avg loser without the
  stand-down drag 2.6.0 added.
- **2.8.0 = 2.4.1 + ENTRY-side only** (`archive/TRADE_SIMULATOR@2.8.0.md`): exact 5-completed-bar
  volume window, single `rvol_bar ≥ 1.5`, numeric time ladder with **A+ = all boxes +
  `rvol_bar ≥ 2.0`**, strictly-binary MACD box, Grade-B "decisively" → `green_vol ≥ 1.3×
  red_vol` + wick `< (h−l)/4`. **Manage/exit is verbatim 2.4.1** (prose OR-chain, no
  ladder). *Isolates: does tighter entry SELECTION alone pay for its extra stand-downs?*
- **Test:** ⏳ pending. Each needs its §4.1 clarity-review pass, then `compare --a
  2.4.0-20260708181528 --b <cand-batch>` (100-set, deepseek-v4-flash). Whichever half
  (if either) shows mean ΔR > 0 broadly is the keeper; then consider recombining the
  winners. **2.4.1 remains the accepted baseline.**
- **Decision:** ⏳ HOLD — both are un-validated candidates; live skill stays at 2.4.1.

### 2.6.0 — clarity-review fixes (external LLM review of the skill text)  ⏳ CANDIDATE — NOT YET VALIDATED
- **Source:** an executing-model clarity review (prompt: `peer_reviews/skill_clarity_review_prompt.md`)
  returned 14 findings; all were judged genuine, ~half of the suggested fixes were modified.
- **Bug fix (the big one):** 2.5.0's `break_level` for a confirmed-close entry was defined as
  "the breakout bar's high" → ladder (a) `c < break_level` fired **on the fill bar itself**
  (`c < h` on any wicked candle). Now `break_level = avg_entry` for confirmed-close
  (`armed_trigger` for armed fills, where k=0 firing is correct).
- **Definitions pinned (were fuzzy → now single-reading):** `made_nh_since_entry` = any `k≥1`
  bar `c >` entry-bar `h` (not the session-anchored `new_high` flag); volume window = exactly
  the last 5 completed bars; `rvol_bar ≥ 1.5` (was "≳1.5–2×"); time gate = `<10:30` /
  `10:30–<12:00` A+ only / `≥12:00` never, with **A+ defined** (all boxes + `rvol_bar ≥ 2.0`);
  MACD box strictly binary (dropped "clearly negative"); free-trade BE = every-bar predicate
  `high_water ≥ avg_entry + min($0.10, stop_dist/3)` (dropped "first bar or two" + "price
  holds"); Grade B "decisively" = green_vol ≥ 1.3× red_vol + wick < ¼ range, binary boxes at
  nominal; runner "prior green" = most recent completed green 5-min candle (skip reds);
  re-entry "washout structure" = cooldown lows hold ≥ tracked `washout_low`; stop formula
  scoped to confirmed-close (armed keeps arm-time stop).
- **Rejected from the review:** 10%-parity caution flag (new tuned threshold); 2-consecutive-bar
  MACD entry rule (new rule, no canon warrant for entries); tick-`new_high` for
  `made_nh_since_entry` (breaks re-entries); adjacency reading of "prior green" (dead zone);
  "rvol ≥ 1.5 also satisfies" re-entry loosening.
- **Test:** ✅ **ran** (2026-07-09). `compare --a 2.4.0-20260708181528 --b 2.6.0-20260708224608`,
  100-set, deepseek-v4-flash, 94 paired keys: **mean ΔR −0.046, median +0.000, better/worse/≈
  17/30/47, sign-p 0.079, tail-guard top-3 = 55% of +ΔR (JEM +3.99 dominates).** Guardrails:
  avg loser **improved $−15→$−12**, but **stood-down rose 10→14**; void 1/1.
- **Decision:** ❌ **REJECT — 2.4.1 stays the accepted baseline.** Diagnosis (§7 pattern): the
  objectified exits *did* cut loser size, but (a) tighter entry gates (Grade-B "decisively"
  thresholds, A+ `rvol≥2.0`, binary MACD) raised stand-downs, booking some winners as 0R, and
  (b) 30 worse vs 17 better with only +4 stand-downs ⇒ most damage is the ladder **exiting
  trades earlier for less R** — clipping runners to save on losers, net slightly negative.
  The `break_level` bug fix and the de-ambiguification remain *correct*; they just don't lift
  expectancy as a bundle. **Next:** decompose — isolate the bailout-ladder (minus the entry-gate
  tightening) from the entry-gate changes, so we learn which half hurt (see BACKLOG 3A follow-up).
  2.6.0 stays archived as a REJECTED candidate; do not run it live.

### 2.5.0 — objectify the §B.2 soft-bailout OR-chain  ⚠️ SUPERSEDED by 2.6.0 (never batched; contained the `break_level` bug above)
- **Hypothesis:** after entry (2.3.0) and stop (2.4.0) were objectified, the last big
  feel-call multiplying R is the manage-step-2 exit. The prose OR-chain ("failed break /
  lost VWAP / topping tail / MACD rollover / time stop") let two runs disagree on *whether
  the break failed*, producing different exits from the same tape. Replace with an **ordered
  4-predicate ladder** over revealed fields + own state — (a) failed break `c<break_level`
  (`k≤1`); (b) lost VWAP `c<vwap` (`k≥2`); (c) topping-tail (red + tested new high +
  `upper_wick≥2×body` and `≥0.5×stop_dist`); (d) time stop (`k≥5`, no new high, `<¼R` green).
  MACD removed as a stand-alone exit (§4 confirmation only). New state: `break_level`,
  `made_nh_since_entry`.
- **Expected delta:** lower run-to-run exit variance; fewer premature MACD-noise bails
  (should *help* MFE-capture / median R); crisper failed-break exits (should cut avg loser).
- **Test:** ⏳ **pending.** Requires a paired 100-set batch vs the 2.4.x baseline through
  `batchsim compare` (blocked: hermes out of credits as of 2026-07-08). **2.4.1 remains the
  accepted baseline until this passes the gate.** Archived at `archive/TRADE_SIMULATOR@2.5.0.md`.
- **Decision:** ⏳ HOLD — do not treat as promoted; run `compare --a 2.4.x-<batch> --b 2.5.0-<batch>` first.

### 2.4.1 — fix broken canon path + report hygiene (non-behavioral)
- **Change:** point the skill's strategy-doc reference at the real path
  `library/ross_cameron/all_content_structured.md` (was a broken
  `library/analyst_warrior_trading_strategy.md`). No trading-decision change.
- **Test:** none required (reference/patch fix). Not a promotion event.
- **Decision:** keep.

### 2.4.0 — objective stop placement
- **Hypothesis:** the residual entry-price variance (after 2.3.0) lived in stop
  placement — "just-under-breakout-level" vs "under-entry-bar-low" gave 14× different
  size/R from the same entry. Replace with `stop = min(trigger low, prior low) − $0.01`.
- **Test:** baseline `2.2.1-20260707225900` → candidate `2.4.0-20260708181528`,
  100-set, model deepseek-v4-flash. `batchsim compare`:
  **mean ΔR +0.249, median +0.01, 42/20/34, sign-p 0.0071, tail-guard top-3 = 22%.**
  Guardrails: avg loser −$15 vs −$18; void 1 vs 0; stood-down 10 vs 12.
- **Decision:** ✅ **PROMOTE.** First broad, significant, non-tail-driven win.
  (Note: the 2.2.1 baseline here is the clean 100-set batch, not the lucky 30-set run.)

### 2.3.0 — objective entry trigger + null-rvol fix
- **Hypothesis:** entry-timing variance (one run enters bar 3 tight-stop, another chases
  bar 13 wide-stop) came from an undefined "first clean new high" and a null-`rvol_bar`
  trap. Define the trigger as the first bar all boxes align; don't fail the volume box on
  a null rvol.
- **Test:** measured on the 30-set only (pre-`compare`) — not a promotable comparison by
  the current gate; the effect was later confirmed inside the 2.4.0 vs 2.2.1 100-set run
  (CPSH −0.27R → reliable win). Kept as a stepping stone; superseded by 2.4.0.
- **Decision:** keep; folded into the 2.4.0 evaluation.

### ≤2.2.1 — pre-methodology
- 2.0.x–2.2.1 were evaluated on 30-set eyeballing before the paired gate existed. Their
  relative ranking is **not trustworthy** (tail-driven; see `IMPROVING.md` §10). Treat
  2.2.1 as the accepted baseline that 2.4.0 beat on the 100-set.
