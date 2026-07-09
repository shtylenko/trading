# TRADE_SIMULATOR experiment log

One row per behavioral version: the hypothesis, the batch that tested it, the paired
result vs its baseline, and the promote/revert decision. Keeps future maintainers from
re-trying dead ends. Append newest at the top. See `IMPROVING.md` for the protocol.

Columns: **version** · **hypothesis** · **baseline→candidate batch tags** ·
**paired ΔR / sign-p** (`batchsim compare`) · **decision**.

---

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
- **Test:** ⏳ **pending** — supersedes 2.5.0 as the candidate; both validate together in ONE
  paired 100-set batch vs 2.4.x when hermes credits return. **2.4.1 remains the accepted
  baseline.** Archived at `archive/TRADE_SIMULATOR@2.6.0.md` (`sha256:ee6f108e`).
- **Decision:** ⏳ HOLD — run `compare --a 2.4.x-<batch> --b 2.6.0-<batch>` first.

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
