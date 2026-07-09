# TRADE_SIMULATOR experiment log

One row per behavioral version: the hypothesis, the batch that tested it, the paired
result vs its baseline, and the promote/revert decision. Keeps future maintainers from
re-trying dead ends. Append newest at the top. See `IMPROVING.md` for the protocol.

Columns: **version** · **hypothesis** · **baseline→candidate batch tags** ·
**paired ΔR / sign-p** (`batchsim compare`) · **decision**.

---

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
