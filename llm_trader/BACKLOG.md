# llm_trader — improvement backlog (peer-review synthesis, 2026-07-08)

Source: three external reviews in `peer_reviews/2026-07-08-skill/`
(`antigravity_feedback.md`, `codex_feedback.md`, `grok_feedback.md`) of the
skill-improvement methodology. This backlog is the implementation plan.

## Decisions (locked)

1. **Single canon doc = `library/ross_cameron/all_content_structured.md`.**
   It's the stated north star, the most complete, and the skill's existing `§9/§10/§18`
   citations already match its TOC numbering. Only the *path* in the skill is broken
   (`library/analyst_warrior_trading_strategy.md` → should be under `library/ross_cameron/`).

2. **Holdout = disjoint-key temporal split**, enabled by expanding `entries.db` with
   earlier-period data (pre-2025). The current 100-set (`batch/testset_100.json`, all 2025)
   is permanently **dev** (we inspected its leaves to design v2.3/v2.4 → contaminated).
   A genuine **holdout** is carved from `(ticker,date)` keys NOT in the dev set, drawn from
   the expanded pool. The pool is **414 unique setups but all 2025-01…2026-06**; a temporal
   holdout needs pre-2025 (or post-2026-06) setups added — so **data expansion is the enabling
   task for honest generalization**.

## Metric of record (all three reviewers)

Primary = **paired effective expectancy in budget-R** on a fixed set:
traded → `r_multiple`; stood-down → **0R**; void/out-of-credits → excluded from the pair
but tracked as a guardrail. Report **effective AND clean** side by side. Win% / P&L are commentary.

Promotion gate: paired mean ΔR > 0 **and** (sign-test p<0.05 or bootstrap 95% CI excludes 0)
**and** no single setup contributes >⅓ of ΣΔR (tail-guard) **and** guardrails not worse
(void rate, avg loser, p10 R, stood-down rate).

---

## TIER 1 — cheap, verified, low-risk (do first)

- [x] **1A. MAE bug** (`recorder.py:~183`): `worst_price_vs_entry` uses bar `close`; must use
  bar `low` (max adverse excursion is intra-bar). Diagnostic-only (not P&L), but wrong.
  Thread `low` into the engine step; add a test. **DONE** — `step(low=…)`, entry-bar excluded,
  `test_mae_uses_bar_low_not_close`.
- [x] **1B. Fix broken corpus path + unify canon** in `skills/TRADE_SIMULATOR.md`:
  point the strategy-doc reference at `library/ross_cameron/all_content_structured.md`
  (Decision 1). Patch bump (non-behavioral reference fix → 2.4.1). **DONE** (2.4.1; config.py too).
- [x] **1C. `report --by-version` isolation**: it silently mixes batches/models (v2.2.1 shows
  avgR 0.79 over n=114 mixed vs 0.39 on the clean 100-set). Add (a) an **effective-R** column
  next to clean, (b) a loud warning when a version's rows span multiple batch tags or models,
  (c) dedup guidance. Keep `--batch`/tag-scoped reporting as the promotion path.
  **DONE** — `cleanR`/`effR` columns + `⚠ N batches/models MIXED` + footer redirect to `compare`.

## TIER 2 — methodology + tooling (the actual answer to the review)

- [x] **2A. `skills/IMPROVING.md`** — the researcher-facing playbook (separate from the
  agent/CI-facing `MAINTAINING.md`). Sections: objective & non-goals; single canon + RULE_TRACE
  gate; feel-to-formula design philosophy; how to choose the next change (disagreement mining);
  edit protocol; **promotion gate checklist**; holdout discipline; tooling commands;
  when-to-stop / major-bump; lessons 2.0→2.4.
- [x] **2B. `MAINTAINING.md` redirect** — keep it thin (mechanics), add a top block:
  "versioning ≠ improvement; before a behavioral edit follow IMPROVING.md; never rank versions
  from a mixed `report --by-version`."
- [x] **2C. `skills/RULE_TRACE.md`** — table: rule id | skill location | corpus cite | type
  (direct / operationalization / sim-constraint / empirical guardrail) | note | since-version.
  Seed with entry-trigger, stop-formula, free-trade, breakout-or-bailout, scale-thirds,
  sub-VWAP re-entry, 5-pillar grade. Mandatory update on every behavioral bump.
- [x] **2D. `batchsim compare --a TAG --b TAG`** — the automated gate. Dedup to one leaf per
  `(ticker,date)` (v2.2.1 batch has 27 dup leaves), pair on shared keys, effective-R,
  mean/median ΔR, sign-test p, top-Δ contributors + tail-guard (>⅓ from ≤3 keys → flag),
  void/stood-down guardrails. Print a clear ACCEPT/REJECT/INVESTIGATE verdict.
- [x] **2E. Experiment log** — `skills/CHANGELOG.md` (or IMPROVING section): version | hypothesis
  | batch tag | paired ΔR | p | decision. So future AIs don't retry dead ends.
- [x] **2F. Dev/holdout scaffolding** — mark `testset_100.json` as the dev set; add
  `batchsim build-set --exclude <keys>` support so a holdout can be carved from disjoint keys
  once `entries.db` grows (see Data expansion). **DONE** — `build_set(exclude=…)` +
  `--exclude <testset.json>` (repeatable) + `_load_keys`; tests
  `test_build_set_exclude_carves_disjoint_holdout`, `test_load_keys_*`.

## TIER 3 — next rule change (drafted; validate via the new gate)

- [x] **3A. Objectify the soft-bailout OR-chain (§B.2)** — all three reviewers name this the next
  "variance dragon": entry/stop are now formulas but the manage-step-2 exit is still a prose
  OR-list ("failed break / lost VWAP / topping tail / MACD rollover / time stop"). Convert to a
  strict priority list of boolean predicates over revealed bars, as crisp as the stop formula.
  Minor bump (2.5.0). **Requires a paid validation batch through `batchsim compare` before promotion.**
  **DRAFTED & SHIPPED as candidate 2.5.0** (4-predicate ladder a–d; MACD off the ladder; new state
  `break_level`/`made_nh_since_entry`; RULE_TRACE `manage.soft_bailout_ladder`; CHANGELOG entry
  marked ⏳ CANDIDATE). Archived. **Superseded by 2.6.0** (external clarity review caught a
  `break_level` bug in the 2.5.0 draft + 13 other ambiguities — see CHANGELOG 2.6.0).
  **VALIDATED 2026-07-09 → ❌ REJECT** (`compare 2.4.0-20260708181528 2.6.0-20260708224608`,
  94 keys: mean ΔR −0.046, median 0, 17/30/47, sign-p 0.079). Avg loser improved ($−15→$−12)
  but stood-down rose (10→14) and the ladder clips runners → net flat-negative.
  **2.4.1 remains the accepted baseline.**
- [~] **3A-follow. Decompose the 2.6.0 REJECT.** The bundle mixed (i) bug fix + de-ambiguification,
  (ii) bailout-ladder objectification, (iii) entry-gate *tightening* (Grade-B thresholds, A+
  `rvol≥2.0`, binary MACD). REJECT was broad-small-negative + more stand-downs. **BUILT off 2.4.1
  (2026-07-09):** **(3A-i = 2.7.0)** exit-side only — bailout ladder + `break_level` bug fix +
  free-trade predicate + runner "prior green" + washout; entry verbatim 2.4.1.
  **(3A-ii = 2.8.0)** entry-side only — exact volume window, `rvol≥1.5`, time ladder + A+ def,
  binary MACD, Grade-B thresholds; manage/exit verbatim 2.4.1. `2.7.0 ⊕ 2.8.0 ≈ 2.6.0`. Both
  archived. **NEXT: §4.1 clarity-review pass on each, then a paid `compare` vs the 2.4.0 baseline
  batch.** Whichever half shows a broad mean ΔR > 0 is the keeper; recombine winners after.
  `break_level` fix is in 2.7.0 (correctness, not a lever). 2.4.1 stays the accepted baseline.
- [ ] **3B.** (candidate, after 3A) objectify free-trade BE timing on the fill bar — agents
  currently freestyle when the stop jumps to break-even.

## V3 PROFITABILITY QUEUE — baseline `3.0.0-20260710201028` (2026-07-10)

The deterministic-execution baseline is **93 trades / $988.08 / effective R 0.247 / zero
voids** on the now-contaminated 100-set dev cohort. It remains the control; do not loosen
its participation cap, stop-gap handling, slippage, commission, buying-power, or $40 risk
controls merely to improve a simulated result. Every item below must be a separately versioned,
paired experiment and then pass the promotion gate above.

- [~] **V3-1. Engine-managed entry brackets (3.1.0 candidate; implement now).** The agent
  opts into a standard +1R / +2R, one-third / one-third scale ladder on `ENTER_CLOSE` or
  `ARM_BUY_STOP`; after the actual fill, the deterministic engine derives exact target prices
  from the actual fill and structural stop, stages them for the next bar, and keeps the
  protective stop live on the remainder. A later break-even update must not delay/cancel a
  target. Preserve next-bar activation, stop-first ambiguous-OHLC resolution, volume caps,
  and all costs. **Evidence:** 30/56 v3 `SCALE_LIMIT` intents were submitted after their
  target had already traded; four missed entirely (TMDE, SST, EPSM, DCX). Simple replacement
  arithmetic is about +$49.53 on the dev batch, but that is diagnostic only—not a certified
  counterfactual. **Type:** execution-interface correction / sim constraint, informed by
  Cameron's scale-in-thirds rule. **Promotion test:** paired 3.0 vs 3.1 batch; no current-bar
  retroactive fills or other execution-model relaxation.

- [ ] **V3-2. One conservative second-leg re-entry (only after V3-1).** Enable at most one
  re-entry after a three-full-bar cooldown and only on (a) a green VWAP reclaim after a
  washout or (b) a fresh clean new-high from a base above VWAP. Require renewed green-volume
  dominance and non-negative MACD, prohibit entries at/after 11:00, and cap re-entry risk at
  $20 plus the session's remaining loss capacity so cumulative planned loss cannot exceed
  $40. Attribute the first and second trades separately. **Evidence:** 29 of 41 protective-stop
  sessions later traded at least +1 original R, but this is hindsight opportunity rather than
  an achievable-profit estimate. **Type:** canon-grounded strategy experiment; high upside and
  high overfit/churn risk.

- [ ] **V3-3. Price-band selection experiment.** Test a hard stand-down below $3 versus
  half-risk sizing from $2 to $3, with every other rule unchanged. On the v3 dev cohort, the
  23 below-$3 trades produced −$45.49 / effective R −0.048, while $3–$5 produced +$360.07 and
  $5–$10 +$402.55. Treat this as an empirical guardrail, not a canon threshold; it may reflect
  penny ticks, commission, spread, and slippage. Validate on a disjoint holdout before any
  promotion.

- [ ] **V3-4. Late-entry time gate experiment.** Test no fresh entry from 11:00 onward. The
  11 post-11:00 setups produced −$20.72 in the dev batch, but the sample is small. Do **not**
  tighten the prime window to 09:45: 09:46–10:29 remained profitable (+$154.66) despite a
  lower win rate. This is an empirical guardrail and must be tested independently.

- [ ] **V3-5. Execution-quality instrumentation before any friction change.** Continue to
  treat v3's no-commission (+$189.96) and no-slippage (+$312.21) attribution profiles as
  theoretical sensitivity bounds, not strategy results. Before changing execution assumptions
  or selecting a broker/routing scheme, record bid/ask, NBBO, quoted/effective spread, order
  type, fill latency, price improvement, and actual commissions by price/liquidity band.
  Consider marketable-limit caps for entry only after those data exist; retain gap-aware stops.

- [ ] **V3-6. Honest holdout before any promotion.** `batch/testset_100.json` is dev-only:
  the leaf inspection that generated V3-1 through V3-4 contaminates it. Expand the historical
  setup pool, build a disjoint temporal/key holdout, and run all surviving candidates there.

- [ ] **Deferred by user: scanner whole-day-volume leakage / point-in-time scan-replay parity.**
  Do not include this in V3 profitability candidates until explicitly resumed. It is a data
  validity task, not a way to inflate current simulated performance.

## DATA EXPANSION (enabling task — user-offered)

- [ ] **DX. Grow `entries.db` beyond 2025.** Currently **414 unique (ticker,date) setups spanning
  2025-01-02 … 2026-06-30** (244 in 2025, 170 in 2026); `testset_100.json` draws 100 of these →
  contaminated dev. Adding earlier-period setups enables: (a) a genuine disjoint-key **holdout**,
  (b) larger paired-comparison N, (c) less tail-fragility.

  **Pipeline — investigated & validated (probe on 2024-11 ran clean):**
  `entries.db` is produced by the scanner `python3 -m trading.llm_trader.runner` (see
  `runner.run_scan` → `store.py` schema/upsert; universe from Finnhub, bars from
  `trading.marketdata`). It upserts by `setup_id`, so re-running never duplicates.

  ```bash
  # from monorepo root; repo-root .env must be loaded for FINNHUB_API_KEY (bars come from marketdata)
  cd /Users/shtylenko/Projects && set -a && . trading/.env && set +a
  python3 -m trading.llm_trader.runner --start 2023-01-01 --end 2024-12-31 --profile small
  #   → appends pre-2025 setups into the SAME data/entries.db (upsert; safe to re-run)
  ```

  Notes / cost: this is a **full-universe × multi-year** scan — hits Finnhub for the universe
  (weekly-cached; currently stale so it refetches) and pulls daily+intraday bars from marketdata
  for every gapper (grows the ~28GB `marketdata/data/` cache). It's the one heavy, network/disk-
  bearing step here — **scope the date range with the user before launching** rather than
  defaulting to a decade. The probe (`--start 2024-11-01 --end 2024-11-08 --max-symbols 40`)
  completed in ~2s and confirmed the pre-2025 path works end-to-end.

  **Then build the holdout** (disjoint from the dev set, now that `--exclude` exists):
  ```bash
  python3 -m trading.llm_trader.batchsim build-set --n 100 --seed 29 \
      --exclude trading/llm_trader/batch/testset_100.json \
      --out trading/llm_trader/batch/testset_holdout.json
  ```

## HOLD / needs explicit decision (do NOT implement silently)

- **Fill-model realism** (slippage, entry latency, volume-liquidity cap on sizing). Legitimate,
  but changes the fill model → **invalidates all prior comparisons** and is a *major* version.
  Quarantine; decide deliberately.
- **Timeframe fork** — Cameron's flagship ACD is 5-min; sim is 1-min ("1-min dialect"). Either
  accept as explicit scope in IMPROVING.md or run a 5-min-gated-entry experiment (major fork).
- **Skill bulk** (~46k chars inlined every run) — possible slim batch projection of the skill.
