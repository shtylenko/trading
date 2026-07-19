# Peer review request — new strategy families (2026-07-18)

**To:** Independent AI reviewer (second model)  
**From:** Implementing agent (Grok / llm_trader short-hold + multi-day track)  
**Date:** 2026-07-18  
**Repo root:** `/Users/shtylenko/Projects/trading/llm_trader`  
**Goal of this document:** Give you enough primary evidence to critique methodology, results interpretation, promotion decisions, and next steps — without trusting the implementer’s narrative.

---

## 0. Your role

You are a **hostile-but-fair quant / research reviewer**. You did not implement these strategies. Your job is to:

1. Reconstruct what was tested from **artifacts and code**, not from marketing language.  
2. Challenge **selection bias, look-ahead, cost realism, gate design, and promotion policy**.  
3. Decide whether the implementer’s freeze (paper-optional micro + VWAP; park the rest) is justified.  
4. Propose **further improvements** only if they are structural and pre-registrable — not parameter nibble.  
5. Answer the **hard questions** in §7 explicitly (yes/no/insufficient with reasoning).

**Do not** rewrite the strategies. **Do not** propose “just tighten X by 10%” without a falsifiable structural hypothesis and a holdout protocol.

---

## 1. Mandate (user constraints that bound the work)

| Constraint | Meaning |
|---|---|
| Long-only equities | No shorting, futures, options |
| Short-hold preferred after multi-day FAIL | Same-day flat EOD preferred over multi-day residual packaging |
| No x03 residual momentum packaging | Explicit user reject |
| Lance / Ross source material | `library/lance/lance_strategies.md`, Ross Cameron canon / warrior SPEC |
| Common multi-year gates | Pooled effR > 0 **and** ≥2 of 4 calendar years > 0 (unless noted) |
| Cost model (short-hold offline) | 1 bps fee + 2 bps slip **each way** baseline; stress grid up to 3× slip / higher fees |
| Universe (liquid multi-year) | ~59 liquid large-caps, shared cohort with VWAP (2022–2025) |

Roadmap / freeze summary:

- `ROADMAP.md`
- `batch/SHORT_HOLD_PAPER.md`

---

## 2. Methodology (what “a test” means here)

### 2.1 Two execution molds

| Mold | Families | Bars | Execution | Notes |
|---|---|---|---|---|
| **A — Multi-day sealed batch** | `trend_pullback`, `breakout_first_pullback`, `right_side_v` | Daily + batchsim auto-arm | Sealed skill / deterministic policy; leaf sim | Tags under `batchsim`; 100% policy ok claimed |
| **B — Offline same-day 5m path sim** | `vwap_pullback`, `bb_squeeze_long`, `micro_pullback` | 5m RTH | Next-bar open entry; stop / 1R half / 2R / EOD 15:55 | **Not** the LLM sealed 1m paper path |

**Critical:** Positive short-hold results are **offline 5m sim only**. They are **not** yet validated on the sealed 1-minute LLM batchsim / recorder path used for warrior.

### 2.2 Gates (pre-registered style)

For multi-year liquid books:

1. Pooled average R-multiple (`effR`) > 0  
2. At least 2 of 4 years (2022–2025) have effR > 0  
3. Cost stress: same entries re-sim under higher fee/slip; same gates  

For structural A/B (NML / portfolio), parameters were written **before** looking at outcomes:

- `batch/admission/PREREG.md`

### 2.3 What “effR” is

Approximate: total PnL / risk_budget, averaged per trade, with fixed risk budget (typically $100) and half-scale at 1R then 2R remainder. **T1 is not a full exit** in exit counts (scale-half).

### 2.4 Packaging overlays (structural, not detector retune)

| Overlay | Code | Default on paper |
|---|---|---|
| No Man’s Land (long edge / breakout only) | `admission/no_mans_land.py` | **OFF** after A/B |
| Portfolio concurrency | `admission/portfolio.py` | **ON** (max 3 concurrent, max 5 new/day) |
| Paper book builder | `admission/short_hold_paper.py` | Used by micro + VWAP |

---

## 3. Inventory of families tested (this session + same-day track)

### 3.1 Scoreboard (implementer claims — verify against artifacts)

| Family | Horizon | Multi-year / probe | Overall | Primary artifact |
|---|---|---|---|---|
| `trend_pullback` 0.4.0 | multi-day | 2022–25 liquid | **FAIL** pooled −0.02 | `batch/trend_pullback/multiyear/RESULTS.md` |
| `breakout_first_pullback` 0.1.0 / 0.2.0 | multi-day | 2022–25 | **FAIL** (−0.02; 0.2.0 worse −0.12) | `batch/breakout_first_pullback/multiyear/RESULTS*.md` |
| `right_side_v` 0.1.0 | multi-day | 2022–25 | **FAIL** −0.03; high WR | `batch/right_side_v/multiyear/RESULTS.md` |
| `vwap_pullback` 0.1.0 | same-day 5m | 2022–25 liquid | **PASS thin** +0.024; 3/4 years | `batch/vwap_pullback/multiyear/RESULTS.md` |
| `bb_squeeze_long` 0.1.1 | same-day 5m | 2022–25 liquid | **FAIL** −0.011; **0/4** years; n=7149 | `batch/bb_squeeze_long/multiyear/RESULTS.md` |
| `micro_pullback` 0.1.0 | same-day 5m | 2022–25 liquid | **PASS** +0.029; **4/4** years | `batch/micro_pullback/multiyear/RESULTS.md` |
| micro paper book | packaged | same entries + portfolio | **PASS** +0.032; 4/4 | `batch/micro_pullback/paper/PAPER_BOOK.md` |
| VWAP paper book | packaged | same + portfolio | **PASS** +0.026; 3/4 | `batch/vwap_pullback/paper/PAPER_BOOK.md` |
| NML A/B | structural | sealed micro/VWAP | **NML hurts / kills VWAP** | `batch/admission/structural_ab/RESULTS.md` |
| micro warrior probe | same-day 5m | 2025–H1’26 small-cap | **FAIL** years+ (1/2) | `batch/micro_pullback/warrior_probe/RESULTS.md` |

---

## 4. Detailed results (copy from artifacts)

### 4.1 Multi-day TA (PARKED) — Lance “millions” core

**Shared lesson claimed:** Small recent samples / n30 looked better than full 2022–25; 2022 (and often 2023) destroy pooled edge.

#### `trend_pullback` 0.4.0 — SMA50 pullback  
Ref: `batch/trend_pullback/multiyear/RESULTS.md`, `PREREG.md`

| Year | Traded | effR |
|---|---:|---:|
| 2022 | 14 | −0.09 |
| 2023 | 91 | −0.17 |
| 2024 | 133 | +0.08 |
| 2025 | 93 | +0.00 |
| **Pooled** | **331** | **−0.02** |

Earlier n30 A/B (~+0.07–0.09) was **mostly recent-regime sample** — multi-year rejects promotion.

#### `breakout_first_pullback` 0.1.0  
Ref: `batch/breakout_first_pullback/multiyear/RESULTS.md`

| | Traded | effR |
|---|---:|---:|
| n30 | 18 | +0.05 (optimistic) |
| Pooled 2022–25 | 296 | **−0.02** |
| 2022 alone | 35 | **−0.24** |

Structural 0.2.0 claimed **worse** (−0.12) — see `RESULTS_v020.md`.

#### `right_side_v` 0.1.0  
Ref: `batch/right_side_v/multiyear/RESULTS.md`

| | Traded | Win% | effR |
|---|---:|---:|---:|
| Pooled | 877 | **68%** | **−0.03** |

High win rate, negative R — classic “winners too small / losers too large” or loose scan (1168 setups claimed).

---

### 4.2 Short-hold offline 5m (active track)

#### `vwap_pullback` — morning above VWAP → touch + green reclaim  
Code: `strategies/vwap_pullback/`  
Refs: `batch/vwap_pullback/multiyear/RESULTS.md`, `COST_STRESS.md`, `paper/PAPER_BOOK.md`

| Year | n | effR |
|---|---:|---:|
| 2022 | 133 | +0.034 |
| 2023 | 139 | +0.027 |
| 2024 | 112 | **−0.004** |
| 2025 | 122 | +0.034 |
| **Pooled** | **506** | **+0.0236** |

Cost stress (raw 506): 2× slip barely pass; 3× and fee2+slip4 **fail**.  
Paper book (portfolio): n=494, effR +0.0256, still 3/4 years; fee2+slip4 still fails.

#### `bb_squeeze_long` — BB width squeeze → long expansion only  
Code: `strategies/bb_squeeze_long/`  
Ref: `batch/bb_squeeze_long/multiyear/RESULTS.md`

**Bug (v0.1.0):** Detection started at bar `bb_period + lookback` ≈ 15:10 ET, after entry window end 14:30 → **n=0**.  
**Fix (v0.1.1):** Earlier start; strict-`<` width percentile; lookback 36; pctile max 0.25.

| Year | n | effR |
|---|---:|---:|
| 2022 | 1710 | −0.003 |
| 2023 | 1784 | −0.016 |
| 2024 | 1904 | −0.012 |
| 2025 | 1751 | −0.011 |
| **Pooled** | **7149** | **−0.0107** |

**0/4 years positive.** Large sample → not sparsity. All cost scenarios fail. **PARKED.**

#### `micro_pullback` — impulse → 1–3 bar shallow VWAP-held pullback → green break of pb high  
Code: `strategies/micro_pullback/`  
Refs: multiyear + paper + warrior_probe under `batch/micro_pullback/`

**Liquid multi-year (primary claim):**

| Year | n | effR |
|---|---:|---:|
| 2022 | 290 | +0.040 |
| 2023 | 294 | +0.027 |
| 2024 | 263 | +0.033 |
| 2025 | 255 | +0.016 |
| **Pooled** | **1102** | **+0.0292** |

**4/4 years positive** — best year breadth of the short-hold set.

Cost stress (raw): 2× slip pass; fee2+slip4 ~0 / fail depending on table; 3× fail.  
Paper book: n=972, effR **+0.0315**, 4/4; fee2+slip4 **passes** on taken set (+0.002).

**Warrior small-cap probe (not multi-year):**  
`probe_warrior.py`, window 2025–H1’26, gap≥5%, float&lt;20M **current snapshot**, 420 cached low-float names.

| Year | n | effR |
|---|---:|---:|
| 2025 | 82 | **−0.076** |
| 2026 H1 | 58 | **+0.158** |
| Pooled | 140 | +0.021 |

**FAIL** years+ (1/2). Implementer verdict: do not promote over liquid micro.

---

### 4.3 Structural A/B — No Man’s Land + portfolio  
Refs: `batch/admission/PREREG.md`, `structural_ab/RESULTS.md`  
Code: `admission/no_mans_land.py`, `admission/portfolio.py`, `admission/structural_ab.py`

**Pre-registered NML:** lookback 24 bars; mid-range (0.30, 0.70) reject; long only if position ≥ 0.70 or breakout.  
**Portfolio:** max 3 concurrent, max 5 new entries/day; chronological; overnight flat.

| Family | baseline effR | nml_only | portfolio_only | nml keep rate |
|---|---:|---:|---:|---:|
| micro | +0.0292 | **+0.0056** | +0.0315 | 64.8% |
| VWAP | +0.0236 | **−0.0381 FAIL** | +0.0256 | 18.0% |

**Implementer conclusions:**

- NML as mechanical gate: **do not default ON** (destroys micro edge; kills VWAP because reclaim is often mid-range).  
- Portfolio caps: **keep as packaging** (slightly better/flat effR, lower n).  
- Paper path: portfolio ON, NML OFF.

**Bug found during A/B:** Portfolio concurrency originally did not clear overnight (positions blocked next days). Fixed before final numbers; see `tests/test_admission.py`.

---

## 5. Source theses (external references)

| Idea | Source | How operationalized |
|---|---|---|
| No Man’s Land | Lance — `library/lance/lance_strategies.md` §1 | Mid-range reject; upper edge / breakout long only |
| Right side of V | Lance §2 | Multi-day reclaim family (FAILED multi-year) |
| Trending pullback / MA | Lance swing content | `trend_pullback` (FAILED) |
| Breakout first pullback | Lance swing | `breakout_first_pullback` (FAILED) |
| BB squeeze long expansion | Lance BB edge (long only) | `bb_squeeze_long` (FAILED after fix) |
| VWAP support / reclaim | Lance + Ross | `vwap_pullback` (thin PASS) |
| Micro-pullback | Ross canon §3.2; warrior SPEC phase-2 deferred | `micro_pullback` (liquid PASS; warrior probe FAIL years+) |

Warrior original SPEC defers VWAP-bounce / micro-pullback:  
`strategies/warrior/SPEC.md` (patterns table).

---

## 6. Implementer decisions (under review)

1. **Park** all multi-day TA scanners after multi-year FAIL; no further parameter iteration without structural pre-reg.  
2. **Park** `bb_squeeze_long` after large-n uniform negative years.  
3. Promote only to **research / paper-optional**, never live size, for micro (primary) and VWAP (second).  
4. **Reject NML** as default gate on these two short-holds despite Lance narrative.  
5. **Accept portfolio packaging** as desk realism, not edge creation.  
6. **Freeze detector retuning** on liquid short-holds.  
7. Warrior micro is a **probe only** until PIT float exists.  
8. Explicitly **not** stacking full capital on micro + VWAP without a combined portfolio layer.

Artifacts claiming freeze:

- `batch/SHORT_HOLD_PAPER.md`
- `ROADMAP.md` checklist rows

---

## 7. Hard questions (answer each)

### 7.1 Validity of the sim

1. Is next-bar-open + 5m OHLC stop/target path sim **upward-biased** for liquid names at 1–2 bps slip? By how much would you mark the edge before trusting paper?  
2. Does half-at-1R / rest-at-2R with stop-first bar logic create **option-like path bias** that real fills would not get?  
3. Same-day strategies never paid the overnight gap risk multi-day faces — is comparing multi-day FAIL vs short-hold PASS **apples-to-oranges** on economic opportunity set?  
4. Risk budget $100/trade with notional cap ~50× risk — is sizing realistic vs ADV/participation for $10–1000 large-caps? For $2–20 warrior names?

### 7.2 Gates and multiple testing

5. With ~6–8 families / versions tested in one campaign, does “≥2/4 years and pooled > 0” adequately control **family fishing**? What holdout would you demand?  
6. Micro “wins” with +3¢ per $1 risk. Is that distinguishable from **noise** given n≈1100 but highly overlapping market days / correlated names?  
7. Should year gates be **equal-weighted years** vs trade-weighted pooled? (Implementer uses both; fail if either fails.)  
8. BB squeeze after a detection bug fix used slightly **looser** pctile (0.20→0.25) and lookback (48→36). Is that legitimate bugfix or **silent retune**? Would you re-run with frozen 0.20/48 after the start-index fix only?

### 7.3 NML A/B

9. Implementer concludes Lance NML “hurts” these setups. Is that evidence against Lance, or evidence that **operationalization is wrong** (lookback 24 too short; session range better; should be box after leg not rolling window)?  
10. VWAP reclaim is definitionally often mid-day-range — was applying NML to VWAP a **category error** that should have been pre-registered as “not applicable”?  
11. Success criterion “effR ≥ baseline − 0.005” — is that too harsh / too lenient for keeping a risk filter?

### 7.4 Universe and data

12. Liquid 59-name list is recycled across families — is the edge **SPY-regime beta** rather than setup edge? What control (e.g. random entry same days) would falsify that?  
13. Warrior probe uses **current float** and **cached** low-float tickers only — is any positive pooled reading in 2026 unusable for promotion even as “hint”?  
14. Intraday data coverage older than ~1 year has had provider issues historically (warrior SPEC). Did multi-year 2022–23 5m coverage create **survivorship of bars** or silent missing days?

### 7.5 Promotion policy

15. Is “paper-optional / no live size” coherent, or is it a soft way to keep a weak result alive?  
16. Prefer micro over VWAP: justified by 4/4 years + fee2+slip4 on paper book — or **overfit to packaging**?  
17. Should the project **stop short-hold R&D** entirely given cost fragility at 3× slip?  
18. If only one strategy may be paper-traded next, would you pick micro, VWAP, neither, or a **combined** book with hard capital limits?

### 7.6 Multi-day FAIL interpretation

19. High WR / negative R on `right_side_v` — is the correct next step different construction (targets), or is the thesis dead on liquid large-caps?  
20. n30 optimistic vs multi-year pessimistic: what **sampling policy** should be mandatory going forward so this failure mode cannot recur?

---

## 8. Requested feedback (improvements)

Please structure feedback as:

### A. Methodological verdict
- Which results are **trustworthy**, **weak**, **invalid**?  
- Rank confidence (high/med/low) in: multi-day FAIL park; micro paper-optional; VWAP second; NML OFF; warrior FAIL.

### B. Bugs / integrity risks
- Look-ahead, leakage (whole-day volume in daily screen, etc.), timezone, stop/target order, portfolio double-count, sealed-entry reuse.

### C. Better structural next experiments (pre-registerable)
For each proposal: hypothesis, frozen params, universe, window, gates, **kill criteria**, and what would **not** count as success.

Examples of areas to consider (you may reject all):

- Combined micro+VWAP portfolio with shared concurrency  
- SPY/regime gate as admission module (not retune of impulse_min_pct)  
- Sealed 1m LLM path parity for micro paper book  
- PIT float source for warrior multi-year  
- Alternative NML definition (post-leg box only) as **new** pre-reg version  
- Random-entry / time-of-day null models  
- Cost model calibrated to real broker fills  

### D. What the implementer should stop doing
- Concrete anti-patterns observed in this campaign.

### E. One-page recommendation to the human operator
- What to paper-trade (if anything), size, and what to ignore.

---

## 9. File map (read these first)

### Must-read results
```
batch/SHORT_HOLD_PAPER.md
batch/micro_pullback/multiyear/RESULTS.md
batch/micro_pullback/paper/PAPER_BOOK.md
batch/micro_pullback/warrior_probe/RESULTS.md
batch/vwap_pullback/multiyear/RESULTS.md
batch/vwap_pullback/paper/PAPER_BOOK.md
batch/bb_squeeze_long/multiyear/RESULTS.md
batch/admission/PREREG.md
batch/admission/structural_ab/RESULTS.md
batch/trend_pullback/multiyear/RESULTS.md
batch/breakout_first_pullback/multiyear/RESULTS.md
batch/right_side_v/multiyear/RESULTS.md
ROADMAP.md
```

### Must-read code (detectors + packaging)
```
strategies/micro_pullback/patterns.py
strategies/micro_pullback/config.py
strategies/micro_pullback/paper.py
strategies/micro_pullback/probe_warrior.py
strategies/vwap_pullback/patterns.py
strategies/bb_squeeze_long/patterns.py
admission/no_mans_land.py
admission/portfolio.py
admission/structural_ab.py
admission/short_hold_paper.py
```

### Source theses
```
library/lance/lance_strategies.md
library/ross_cameron/ROSS_CAMERON_TRADING_CANON.md
strategies/warrior/SPEC.md
```

### Tests (for integrity claims)
```
tests/test_admission.py
tests/test_micro_pullback.py
tests/test_micro_pullback_paper.py
tests/test_bb_squeeze_long.py
tests/test_vwap_pullback.py
```

---

## 10. Implementer self-critique (do not rubber-stamp)

The implementer already admits:

- Edges are **tiny** and **cost-fragile**.  
- Offline 5m ≠ sealed LLM path.  
- Multi-day FAIL may be mold/universe, not “Lance is wrong” globally.  
- NML operationalization may be wrong rather than Lance.  
- Warrior probe is underpowered and float-contaminated.  
- Family fishing risk exists across the day’s campaign.  
- “Paper-optional” is a soft promotion that needs external challenge.

**Your job is to go harder than this list.**

---

## 11. Output format (please follow)

```markdown
# Peer review — 2026-07-18 new strategies

## Executive verdict (10 lines max)

## Gate / method scorecard
| Claim | Trust (H/M/L) | Why |

## Answers to hard questions (§7)
### 7.1 ...
(number each answer)

## Integrity findings
- ...

## Disagreements with implementer freeze
- ...

## Pre-registered next experiments (if any)
| ID | Hypothesis | Kill criteria |

## Recommendations to human operator
1. ...
```

---

## 12. Context one-liner for the human

Today’s work closed a short-hold research loop: multi-day Lance scanners FAIL multi-year; BB squeeze FAIL after bugfix; VWAP and micro PASS thinly offline; NML mechanical gate rejected; portfolio packaging kept; warrior micro probe fails year breadth; freeze on detector retunes with micro as primary paper-optional book.

**Challenge that freeze.**
