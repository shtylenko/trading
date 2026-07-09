# TRADE_SIMULATOR experiment log

One row per behavioral version: the hypothesis, the batch that tested it, the paired
result vs its baseline, and the promote/revert decision. Keeps future maintainers from
re-trying dead ends. Append newest at the top. See `IMPROVING.md` for the protocol.

Columns: **version** · **hypothesis** · **baseline→candidate batch tags** ·
**paired ΔR / sign-p** (`batchsim compare`) · **decision**.

---

### 2.5.0 — objectify the §B.2 soft-bailout OR-chain  ⏳ CANDIDATE — NOT YET VALIDATED
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
