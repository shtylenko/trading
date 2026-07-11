# Why 3.0.0 Looks Weaker Than Ross — Analysis & Mitigations

**Date:** 2026-07-11  
**Author:** Grok  
**Skill version reviewed:** 3.0.0 (base)  
**Scope:** skill `3.0.0`, canon in `library/ross_cameron/all_content_structured.md`, stamped batch `3.0.0-20260710201028`, experiment log / backlog, and cross-check against peer reviews in this folder.

---

## TL;DR

You are **not** failing at a “broken MACD threshold.” You are running a **different system** that shares Ross’s vocabulary (ACD, VWAP, scale-thirds, bailout) but **drops most of where his dollars actually come from**.

| Layer | Your 3.0.0 | Ross (canon) | Gap size |
|---|---|---|---|
| Per-trade edge (R) | ~**0.19–0.25R** effective | ~**0.2R** at 55–65% × ~1:1 | **Similar mean R** |
| Win-rate shape | ~**35–38%** win, ~**4–5:1** payoff | ~**55–65%** win, ~**1:1** payoff | **Inverted profile** |
| Selection | Fixed 100-setup pool; 4 measurable pillars | Whole market → top 3–10; **5 pillars incl. news** | **Huge** |
| Entry timeframe | 1-min checklist | **5-min primary** | **Huge** |
| Sizing / day stack | Flat **$40** / setup, isolated | Icebreaker → full size; daily walk-away | **Huge** |
| Scaling in | Written, almost never fires | Central edge on hot tape | **Huge** |
| Execution | Adverse OHLC + 10 bps + $0.005/sh + 10% participation | Hotkeys, price improvement, mental stops | **Large (measurement)** |

**Bottom line:** Expectancy per *accepted setup* is already in Ross’s neighborhood. The “a lot weaker” feeling is mostly (1) inverted win-rate psychology, (2) a deliberately pessimistic v3 fill model, and (3) missing selection/sizing/pyramiding scaffolding — not a missing candle rule.

---

## 1. What the numbers actually say

### Stamped v3 control (`3.0.0-20260710201028`, 100 RTH setups)

| Metric | Value |
|---|---:|
| Trades | 93 |
| Win rate | **37.6%** |
| Net P&L | **$988** |
| Effective R | **+0.247** |
| Avg win / avg loss $ | ~$44.6 / ~$9.9 → **~4.5:1** |

Ross’s taught edge: **accuracy > 50%** with **~1:1** winners and losers. Same ~0.2R math, **opposite distribution**.

### Friction sensitivity (same control batch, attribution)

| Assumption | Win% | Eff R | P&L |
|---|---:|---:|---:|
| Full v3 costs | 37.6% | 0.247 | $988 |
| No commission | 37.6% | 0.294 | $1,178 |
| No slippage | 45.2% | 0.325 | $1,300 |
| Frictionless | **65.2%** | **0.468** | **$1,854** |

Costs alone swing win rate from ~38% → ~65%. Comparing v3 to v2.x ~0.5–0.9R (agent-reported fills) is **invalid** — CHANGELOG already calls 3.0.0 a major rebaseline.

### Profile inversion (why it *feels* bad)

- Ross-like: 60% × 1R − 40% × 1R ≈ **+0.2R**, red ~2 of 5 trades
- You: ~37% × ~1.1R − 63% × ~0.24R ≈ **+0.2R**, red ~2 of 3 trades

Same mean R; much worse **psychological / equity-curve shape**.

### By-version snapshot (mixed rows — commentary only, not ranking)

| version | n | win% | P&L | clean R | eff R | MFE capt |
|---------|-----|------|----------|---------|-------|----------|
| 2.4.1 | 182 | 41% | $3379.64 | 0.46 | 0.42 | 0.39 |
| 3.0.0 | 477 | 35% | $4766.51 | 0.25 | 0.23 | 0.25 |
| 3.1.0 | 89 | 37% | $838.47 | 0.24 | 0.21 | 0.21 |
| 3.2.0 | 69 | 38% | $712.86 | 0.26 | 0.18 | 0.21 |

The 2.x → 3.x drop coincides with the deterministic-execution rebaseline, not a pure strategy regression. Rank versions only via `batchsim compare`.

---

## 2. Fidelity map: what 3.0.0 gets right vs wrong

### Faithful (or close)

| Area | Status |
|---|---|
| Long-only momentum morning bias | Yes |
| Price / float / RVOL / gap as selection filters | Partial (scanner + Grade A/B/C) |
| Breakout-or-bailout philosophy | Yes (failed break, lost VWAP, time stop) |
| Free-trade BE (~+$0.10) | Yes |
| Scale out in thirds (+1R / +2R / runner) | Written; execution often late (see below) |
| Runner exit on **5-min** red-candle rule | Yes (§B.5) — good fix |
| Structural stop formula | Operationalization of “stop at pullback low” |
| Risk = $ risk ÷ stop distance | Yes (engine-owned in v3) |
| Optional sub-VWAP / second-leg re-entry | Written (§C); often **off** in control (`reentry: false`) |

### Material divergences (ranked by impact)

### A. Selection is not Ross’s selection

| Ross | 3.0.0 |
|---|---|
| **News catalyst required** (pillar 5) | **No news layer** — gap/RVOL proxy only |
| Scans whole market; trades **leading** gapper(s) | Replays a fixed 100-set of historical ACD/ORB hits |
| Hot market: float <20M, B/C can work; cold: float <5M, **A only** | Grades A/B/C **per setup**, no market-breadth state |
| Prefers 5× RVOL; min 2× | Grade A needs rvol≥5; **Grade B trades rvol 2–5** |

Control batch: **65/100 B-grade**, 60 of them traded. That is “trade the rest,” not “trade the best.”

### B. Entry is on the wrong primary timeframe

- Ross: **5-min** ACD is the pattern; 1-min is timing only.
- Skill §A: full entry checklist on **1-min** bars (`new_high`, green, VWAP, volume, wick, MACD).
- Scanner *detects* on 5-min, then replay *manages* entry criteria on 1-min — a dialect mismatch.

This is the most plausible driver of **35% vs 55–65% win rate**. The *exit* side was already moved to 5-min; the *entry* side never got the same treatment.

### C. Hours / session model diverge

- Ross: **7:00–9:30 is best**; regular open is secondary.
- `entries.db` has many premarket setups; batch builder defaults to **≥09:30**.
- Scanner uses extended 5-min bars; replay/indicators often **RTH-only** → premarket structure can select a setup that then “disappears” from VWAP/session-high context.

### D. Scaling *in* is almost absent

- Ross: starter ⅓ → add on hold → add on continuation; “same initial risk, 3× profit.”
- 3.0.0: engine typically consumes **full risk budget** on first fill; leaf scans show ~0 multi-add winners.
- One-intent-per-bar starves ADD vs SET_STOP / SCALE_LIMIT (same class of defect that killed simple 3.1.0 brackets: mean ΔR −0.037).

### E. Day-level risk stack is missing entirely

Ross’s 76-day green streak machine:

1. **Icebreaker** 25% size until first profit milestone
2. Daily max loss / give-back half / 3 losses → walk away
3. Hot/cold aggressiveness
4. Compounding risk with account

3.0.0: every leaf risks **$40** independently. You can never reproduce his **equity curve** even with identical per-trade R.

### F. Information set is thinner

Missing by design: Level II, Time & Sales, halt reopen tape, true intra-bar path, wholesaler price improvement. Armed buy-stop approximates “don’t wait for close,” but fills are still **worse-of-open-or-trigger + slippage**, stop-first on ambiguous bars.

### G. Data-validity issues (fix these *before* chasing alpha)

Already in BACKLOG / sol review — they mostly **inflate** apparent edge:

1. **Whole-day RVOL leakage** — selection uses full-day volume for a morning entry
2. **Premarket selected with later RTH open** for gap/price
3. **5-min breakout bar already “succeeded”** when replay starts at its open
4. **Float / universe are current-snapshot**, not point-in-time
5. Dev **100-set is contaminated** (used to design v2.3/v2.4 rules)

Honest improvement may *lower* reported R first — that’s the right direction.

---

## 3. Ideas & mitigations (prioritized)

### Tier 0 — Reset expectations (do this week, zero rule risk)

| # | Idea | Mitigation / action | Expected effect |
|---|---|---|---|
| 0.1 | Stop comparing to Ross’s **gross dollars / green-day streak** | Compare **effective R under same capital, hours, costs** | Removes false “failure” signal |
| 0.2 | Score a “Ross-equivalent” bar under *your* model | 60% × 1:1 ≈ **0.2R**; you’re already ~there | Reframes work as **shape + scaffolding** |
| 0.3 | Friction bound run | One batch at 5 bps / midpoint ambiguity | Bounds how much of 2.x→3.x is measurement |
| 0.4 | Honor promotion gate | 3.0.0 is still ⏳ HOLD; 3.1 REJECT; 3.2 unvalidated | Don’t stack rules on unvalidated base |

### Tier 1 — Highest fidelity / expectancy levers

| # | Idea | Mitigation | Why it should work |
|---|---|---|---|
| **1.1** | **5-min entry structure** | Require 1-min trigger inside valid **completed 5-min** structure (5-min new high / green / above VWAP), or run checklist on 5-min and use 1-min only for arm/fill | Directly mirrors canon §9; same logic that fixed runner exits; targets win-rate gap |
| **1.2** | **Catalyst layer** | Timestamped headlines before entry; exclude offerings/dilution/RS; LLM only classifies news | Ross pillar you fully omit — likely largest *selection* alpha hole |
| **1.3** | **A-only + per-grade expectancy** | Report clean/eff R by Grade A vs B; if B ≤ 0 after costs, hard-gate B (or only in “hot” regime) | Aligns with “trade the best”; control traded mostly B |
| **1.4** | **Hot/cold breadth gauge** | Morning count of +20%/+50%/+100% names → size + allow B only when hot | Canon §7; currently every day trades the same |
| **1.5** | **Engine-managed pyramid** | Starter = ⅓ risk; engine fires ADD#2/#3 on hold/continuation with total open-risk cap | Written rule never fires; 3.1-style engine ownership without replaying fixed +1R/+2R brackets |
| **1.6** | **Compound management intents** | Allow `SET_STOP` + live scale targets in one bar (or multi-intent log) | Fixes “scale after target already traded” without re-running REJECTED 3.1 brackets |

### Tier 2 — Management / capture improvements

| # | Idea | Mitigation | Notes |
|---|---|---|---|
| 2.1 | **MFE capture regressed** (0.39 → ~0.21–0.25) | Audit which soft-bailout clause kills largest MFE runners; ensure **runner tranche** is only exited by 5-min red rule / hard BE | 2.6.0 already showed objectified exits clip R |
| 2.2 | **Time stop too fast** | Skill: 5×1-min bars; Ross: **30–60 min**. Paired test at 10–15 or 30 bars | Exits consolidations that still resolve |
| 2.3 | **Scratch tax** | Many BE exits after +$0.10, then costs + stop-first make ±0.15R “losses.” Test BE at **½R** or **entry + costs** | Ross re-enters instantly; you pay 3-bar cooldown |
| 2.4 | **Scale-out resistance objectivity** | Objectify “first clear resistance” (pm_high, round $0.50, prior day high) | Still a feel-call (IMPROVING.md) |
| 2.5 | **Re-entry properly enabled** | V3-2 in BACKLOG: 1 second leg after 3-bar cooldown, half risk, attribute trades separately | 29/41 stop-outs later ran +1R *in hindsight* — treat as experiment, not free money |
| 2.6 | **MFE metric fix** | Measure MFE **while in position**, not through EOD after exit | Current metric makes management look worse (median full-day MFE ~3.45× in-trade) |

### Tier 3 — Day-level / account scaffolding (where wealth is built)

| # | Idea | Mitigation |
|---|---|---|
| 3.1 | **Icebreaker day model** | Batch report: ordered multi-setup day; start 25% risk; unlock full after first green; stay small if cold |
| 3.2 | **Daily walk-away** | Max loss, give-back 20% of open P&L, 3 consecutive losses, hit daily goal → stop |
| 3.3 | **Compounding report** | Risk scales with equity; report equity curve not only sum of isolated $40 R |
| 3.4 | **Premarket cohort (separate)** | Own testset + wider spreads / lower participation / halt gaps — do **not** merge with RTH metrics |

### Tier 4 — Validity / infrastructure (required for honest promotion)

| # | Idea | Mitigation |
|---|---|---|
| 4.1 | **As-of RVOL** | Cumulative vol to signal time / expected TOD profile — not full-day volume |
| 4.2 | **Premarket gap at evaluation time** | Price vs prior close at scan ts, not later 09:30 open |
| 4.3 | **No breakout look-ahead** | Reveal pre-signal context; detect breakout online; decision after 5-min close *or* true armed break |
| 4.4 | **One session policy** | Scanner indicators = replay indicators (extended vs RTH) |
| 4.5 | **Disjoint holdout** | Expand `entries.db` pre-2025; `build-set --exclude testset_100.json` |
| 4.6 | **Broker-calibrated fills** | Fit slippage/spread/participation from real paper fills before changing execution knobs |
| 4.7 | **Deterministic core** | Code predicates for entry/stop/scale/exit; LLM for news classification + journal only | Two identical v3 batches already differed ~0.06R mean |

### Tier 5 — Empirical guardrails already in flight (keep, don’t over-stack)

| Version | Idea | Status |
|---|---|---|
| 3.1.0 | Fixed +1R/+2R engine brackets | **REJECT** — do not retry as-is |
| 3.2.0 | Stand down `entry_px < $3` | Candidate (dev-only evidence); needs holdout |
| V3-4 (BACKLOG) | No fresh entry after 11:00 | Small sample (−$20.72); test alone |
| 2.7 / 2.8 | Exit-only vs entry-only objectification | Still unvalidated vs 2.4.1 |

---

## 4. Suggested sequence (so you don’t thrash)

```text
1. Freeze 3.0.0 as v3 control (already mostly true)
2. Tier 0: Ross-equivalent bar + friction sensitivity (1–2 batches)
3. Tier 4.1–4.3: fix the worst data leaks (expect reported R to drop)
4. Tier 1.1: 5-min entry structure (paired compare vs 3.0.0)
5. Tier 1.3 + 1.4: A-only / hot-cold (paired)
6. Tier 1.5 + 1.6: real pyramiding + multi-intent management
7. Tier 3: icebreaker multi-setup day model (new report, not per-leaf only)
8. Catalyst layer + premarket cohort when data is ready
9. Only then: holdout promotion of any surviving rule
```

One hypothesis per minor bump; always `batchsim compare` on the 100-set; no promotion without holdout (`IMPROVING.md`).

---

## 5. What *not* to do

1. **Don’t loosen v3 friction** (participation, stop-first, slippage) just to match old 2.x R or Ross’s marketing P&L.
2. **Don’t re-ship 3.1.0 brackets** unchanged (already REJECT).
3. **Don’t rank from mixed `report --by-version`** (3.0.0 shows 7 batches MIXED).
4. **Don’t treat win-rate alone as the goal** without fixing selection + 5-min structure — tightening exits already clipped runners (2.6.0).
5. **Don’t expect the sim to “be Ross”** without tape, whole-market morning selection, and day-level sizing. Ceiling is **his R profile + your scaffolding**, not his audited multi-million equity curve.

---

## 6. Direct answer to “is the skill different from what Ross uses?”

**Yes — substantially.**

3.0.0 is a solid **operational subset** of his risk language (bailout, free trade, thirds, structural stop, small-account $ risk) running on a **1-min discretionary agent** over a **pre-filtered ACD/ORB library**, with **no catalyst, no market regime, no icebreaker day, almost no pyramiding-in, and adverse OHLC fills**.

It is **not** a full port of:

- 5-pillar **news-first** selection
- whole-market “trade the best” funnel
- 5-min primary entry
- premarket primacy
- icebreaker / walk-away / hot-cold
- scale-in edge on hot days
- Level II / tape confirmation

So weaker *headline* results vs his public track record are expected even when **per-trade R is already comparable**.

---

## 7. If you only do three things

1. **5-min structural entry filter** (win-rate shape).
2. **A-only (or hot/cold-gated B) + per-grade reporting** (selection quality).
3. **Engine-owned starter/add plan + multi-intent management** (unlock convex winners without gambling fills).

Plus, treat data-leak fixes as non-optional so the next win is real.

---

## Sources

- `library/ross_cameron/all_content_structured.md`
- `library/ross_cameron/ROSS_CAMERON_TRADING_CANON.md`
- `llm_trader/skills/trade_skills/3.0.0.md`
- `llm_trader/skills/RULE_TRACE.md`
- `llm_trader/skills/CHANGELOG.md`
- `llm_trader/skills/IMPROVING.md`
- `llm_trader/BACKLOG.md`
- `llm_trader/execution.py`, `config.py`, `screen.py`, `patterns.py`
- `recorder report --by-version`
- Stamped batch `3.0.0-20260710201028`
- Peer reviews in this folder (`fable.md`, `sol.md`) for cross-check of batch metrics
