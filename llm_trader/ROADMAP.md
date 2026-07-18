# llm_trader — Strategy Implementation Roadmap

**Purpose:** List strategy families and entry patterns that are **not yet implemented**
in `llm_trader` (and not already exhausted as near-identical molds in `lab`), based on
the Lance Breitstein strategy inventory (`library/lance/lance_strategies.md`) vs current
coverage in `llm_trader` + `lab`.

**Constraints (product mandate):** long-only equities · no shorting · no futures · no options.

**Active focus (2026-07):** **short-hold / same-day only.** Multi-day Lance scanners
(`trend_pullback`, `breakout_first_pullback`, multi-day `right_side_v`) are **PARKED**
after multi-year FAILs. Do not prioritize new multi-day TA families unless evidence changes.

**How to add a family:** follow [`MULTI_STRATEGY.md`](MULTI_STRATEGY.md) (symmetric
`strategies/<id>/` layout, skills tree, batch holdouts). Do not fold new patterns into
`warrior` or `cup_handle` unless they are true variants of those canons.

**Related docs:**
- Platform backlog (skill methodology, not new strategies): [`BACKLOG.md`](BACKLOG.md)
- Implemented families: `warrior`, `cup_handle` (see README)
- Lab kills / promotes (do not re-spend sealed years): `../lab/validation/STRATEGY_SYNTHESIS.md`,
  family `backlog.md` files under `../lab/strategies/`

---

## Already implemented (out of roadmap)

| Family / mold | Where | Notes |
|---|---|---|
| Gap-up ACD / ORB momentum (Ross-style) | `warrior` | Core pattern only; phase-2 patterns still open below |
| Cup-and-handle swing | `cup_handle` | One base-breakout pattern; not Lance “first pullback after breakout” |
| SIP ORB (rule + ML) | `lab` `stocks_in_play_orb` | **Exhausted / killed** — do not reimplement as a new family |
| Post-gap opening drive | `lab` `post_gap_opening_drive` | **Retired** on sealed 2025 |
| Dominance-flip / flush reversal | `lab` `dominance_flip_reversal` | **Killed** (knife-catch / left-side-of-V) |
| Gao intraday momentum | `lab` `intraday_momentum` | **Exhausted** Stage 0 |
| Cross-sectional residual momentum | `lab` `xsec_momentum` (x03) | Promoted elsewhere; not an llm_trader scanner family |
| Breakout first pullback | `llm_trader` `breakout_first_pullback` | **v0.1.0** smoke only |
| Trend pullback SMA50 | `llm_trader` `trend_pullback` | **PARKED** multi-year FAIL |

---

## Priority 1 — Implement next (short-hold long, under-tested)

These are Lance-shaped (or peer-endorsed microstructure) ideas that **do not**
duplicate a killed lab family and fit sealed scan + paper-trade in this package.

### 1. `right_side_v` — Confirmed reversal long (right side of the “V”)

| | |
|---|---|
| **Lance ref** | Right Side of the “V” |
| **Thesis** | Same price ≠ same EV. Do **not** buy the dump (left side). Wait for selloff → **structure confirms** (higher low, reclaim of key level / short MA) → long with stop under the turn low. |
| **Why not done** | Lab `f*` bought stretch/capitulation (closer to left side) and died. Confirmed-turn entry was never a family. |
| **Horizon** | Same-day preferred; optional overnight if reclaim is late-day |
| **Scanner sketch** | Prior sharp down leg → pivot low → reclaim trigger (e.g. prior bar high or VWAP/EMA) with volume confirmation; liquid universe |
| **Skill focus** | Entry only after confirmation; hard invalidation under pivot; no averaging down into the left side |
| **Status** | **PARKED** — multi-year FAIL (pooled effR −0.03). See `batch/right_side_v/multiyear/RESULTS.md` |

### 2. `vwap_pullback` — Trend-day VWAP pullback / reclaim long

| | |
|---|---|
| **Lance ref** | Anchored / institutional VWAP edge (session VWAP as first cut); peer “midday VWAP pullback” |
| **Thesis** | Morning uptrend / hold above VWAP → pullback to session VWAP (or reclaim after shallow dip) → long; stop under VWAP or pullback low. |
| **Why not done** | Warrior SPEC explicitly **defers** VWAP-bounce / micro-pullback (phase 2). Lab only used VWAP as a feature/gate, not as the setup. |
| **Horizon** | Same-day |
| **Scanner sketch** | RVOL + gap or trend filter → first clean VWAP touch/reclaim in defined window (e.g. 10:00–14:00) |
| **Skill focus** | One primary entry; no chase far above VWAP; flatten EOD |
| **Status** | **Research only** — multi-year PASS thin (+0.024); **fails cost stress** at 3× slip / fee2+slip4. See multiyear RESULTS + COST_STRESS |

### 3. `bb_squeeze_long` — Bollinger squeeze → long expansion only

| | |
|---|---|
| **Lance ref** | Bollinger Band Edge (contraction → expansion; **not** shorting upper-band stretch) |
| **Thesis** | Band width compresses → break of mid/upper band with volume → long continuation. Never fade “crazy can get crazier” on the long side by shorting; this family is long-only expansion. |
| **Why not done** | Appears only as a peer-review feature idea; no family in lab or llm_trader. |
| **Horizon** | Same-day (intraday bands) or multi-day (daily bands) — pick one horizon per release |
| **Scanner sketch** | Width percentile low → directional break + RVOL; SPY regime optional |
| **Skill focus** | Enter on expansion confirmation; stop mid-band or squeeze low; no mean-revert shorts |
| **Status** | **PARKED** — v0.1.1 multi-year FAIL (pooled effR −0.011; **0/4** years > 0; n=7149). Cost stress all fail. See `batch/bb_squeeze_long/multiyear/RESULTS.md` |

### 4. `no_mans_land` filter family (or shared admission module)

| | |
|---|---|
| **Lance ref** | No Man’s Land Trading |
| **Thesis** | Only trade **edges** of a defined range: long range-high reclaim or long from support with invalidation. Skip mid-range chop. |
| **Why not done** | Concept never codified as scanner rules or a reusable filter used by multiple families. |
| **Horizon** | Cross-cutting — module first, optional thin family later |
| **Implementation sketch** | Detect consolidation box after a directional leg; emit only edge events; attach as gate to `vwap_pullback` / `right_side_v` / warrior variants |
| **Status** | **Shipped as shared module** `admission/no_mans_land.py` + portfolio overlay. Structural A/B on sealed micro/VWAP: **NML hurts** (micro effR +0.029→+0.006; VWAP FAIL). **Do not enable as default.** Portfolio concurrency **keep** as packaging. See `batch/admission/structural_ab/RESULTS.md` + `PREREG.md`. |

### 5. Warrior phase-2 patterns (extend `warrior`, not a new family id unless needed)

| Pattern | Lance / Ross adjacency | Status |
|---|---|---|
| **Micro-pullback long** | Short-hold continuation after first pause | **Shipped as `micro_pullback` family** — multi-year PASS (+0.029; 4/4 years); cost-fragile. See `batch/micro_pullback/multiyear/RESULTS.md`. Liquid-universe gate (not warrior pennies). |
| **VWAP reclaim after washout** | Overlaps `vwap_pullback` — prefer one shared pattern module | Covered by `vwap_pullback` research baseline |
| **Flat-top / multi-bar base** beyond single ACD | Still long breakout, better structure | Thin / partial |

Optional later: port `micro_pullback` detector onto warrior small-cap gap screen once
point-in-time float multi-year is available.

---

## Priority 2 — Multi-day / swing (Lance “millions” core; not short-hold)

Highest Lance parity for **swing** content. Better economic fit with lab evidence
(multi-day edge exists; same-day liquid breakout mold exhausted). Implement as new
`strategies/<id>/` families with daily (or multi-day) replay profiles.

### 6. `trend_pullback` — Trending pullback to 20 EMA / 50 SMA

| | |
|---|---|
| **Lance ref** | Swing #1 Trending Pullback; Qullamaggie / MA reaction content |
| **Thesis** | Daily uptrend (price above rising MA) → pullback into 20 EMA or 50 SMA → exhaustion / reclaim → long; stop under pullback low; target prior high / measured move. |
| **Why not done** | No family. `cup_handle` is a different geometry. Lab `x03` is monthly residual **rank**, not MA pullback entries. |
| **Horizon** | Multi-day (days–weeks) |
| **Status** | **Implemented → multi-year FAIL → PARKED** (`trend_pullback` 0.4.0) |

### 7. `breakout_first_pullback` — Breakout continuation on first retest

> **v0.1.0 implemented** — smoke `bfp-smoke-v010` (10/10 ok, n=6 traded, effR +0.22 — tiny sample).

| | |
|---|---|
| **Lance ref** | Swing #2 Breakout Continuation |
| **Thesis** | Multi-week base break on volume → **wait for first pullback** to breakout level as support → long on hold; tighter stop than chase. |
| **Why not done** | `cup_handle` is one base pattern with handle arm; not the generic “break then first retest” rule. |
| **Horizon** | Multi-day |
| **Status** | **PARKED** — 0.1.0 multi-year FAIL (−0.02); 0.2.0 structural **worse** (−0.12). See multiyear RESULTS*.md |

### 8. `anchored_vwap` — Event-anchored VWAP pullback

| | |
|---|---|
| **Lance ref** | Anchored VWAP Edge (Brian Shannon) |
| **Thesis** | Anchor VWAP to earnings, IPO day, or major pivot; in an uptrend, long pullbacks to AVWAP as institutional cost-basis support. |
| **Why not done** | Only **session** VWAP exists in indicators. No event anchors (earnings calendar / pivot catalog). |
| **Horizon** | Multi-day (primary); optional intraday once anchors exist |
| **Data dependency** | Earnings (or other event) dates; split-aware bars |
| **Status** | Not implemented |

### 9. `multi_tf_trend` — Multi-timeframe alignment gate + lower-TF entry

| | |
|---|---|
| **Lance ref** | Multi-Timeframe Analysis |
| **Thesis** | Weekly + daily uptrend required; enter only on lower-TF (daily/intraday) pullback that agrees. Standalone family or **hard gate** on `trend_pullback` / `breakout_first_pullback`. |
| **Why not done** | Partial regime gates only (e.g. SPY SMA); no systematic weekly→daily→entry stack. |
| **Status** | Not implemented (prefer as shared gate after #6/#7) |

---

## Priority 3 — Optional / low priority (data or automation weak)

| Id | Lance ref | Why parked | When to open |
|---|---|---|---|
| `offer_take_scalp` | Scalping #1 Offer-take | Needs Level 2 / tape; bar OHLC insufficient | Only if L2/time-and-sales feed is added |
| `news_reaction` | News & event-driven | Historical news feed missing (already blocked warrior catalyst) | If a PIT news store is available |
| `ipo_suite` | Four IPO strategies | Small sample, auction/IPO data, limited history | After event calendar + IPO list pipeline |
| `macd_divergence` | MACD (divergence only) | Confirmation tool, weak standalone; MACD already in warrior indicators | Only as filter on another family |
| `trendline_bounce` | Trendline trading | Algorithmic line drawing brittle / overfit-prone | After pivot engine proves stable OOS |
| `fib_50` | Fib (Lance skeptical; 50% only) | Soft edge; confluence only | As zone tag on #6/#7, not a family |

**Explicitly out of scope (mandate):** breakdown short scalp, options selling, naked short momentum, prediction-market book, futures.

---

## Lab-proposed, not Lance — track only if orthogonal

These exist as **lab backlogs without a full llm_trader family**. Not required for Lance
parity; list so they are not confused with the above.

| Idea | Location | Note |
|---|---|---|
| SMA mean reversion | `lab/strategies/sma_mean_reversion` | Opposite of trend pullback; long-only MR |
| SMMA + ATR breakout | `lab/strategies/smma_atr_breakout` | Proposed `s01`, not run |
| Liquidation cascade reversal | `lab/strategies/liquidation_cascade_reversal` | Overlaps killed `f*` thesis risk |
| Momentum burst (StockBee) | `lab/strategies/momentum_burst` | Multi-day range expansion; possible future family if not folded into #7 |

---

## Suggested implementation order

```text
DONE  micro_pullback     multi-year PASS thin (+0.029; 4/4); cost-fragile
DONE  vwap_pullback      multi-year PASS thin (+0.024; 3/4); cost-fragile
DONE  bb_squeeze_long    multi-year FAIL (−0.011; 0/4) — PARKED
DONE  right_side_v / trend_pullback / breakout_first_pullback — multi-year FAIL PARKED

Structural gates (done):
5. no_mans_land A/B                                  NML: do not default-on; portfolio: keep packaging

Paper path (done):
6. micro_pullback paper book                         `batch/micro_pullback/paper/PAPER_BOOK.md` (primary)
7. vwap_pullback paper book                          `batch/vwap_pullback/paper/PAPER_BOOK.md` (2nd)

Warrior port (done as limited probe):
8. micro_pullback warrior probe 2025–H1'26             **FAIL** years+ (2025 −0.08 / 2026 +0.16); not multi-year; current float only. See `batch/micro_pullback/warrior_probe/RESULTS.md`

Freeze liquid short-hold track:
9. prefer micro paper book; VWAP optional second; no more detector retunes

Swing (parked unless structural change):
9. trend_pullback / BFP / anchored_vwap / multi_tf_trend
```

Each new family should ship with:

1. `SPEC.md` + mechanical entry/exit rules  
2. Scanner → `entries` DB (strategy column)  
3. Sealed skill `0.1.0` (or deterministic policy like cup_handle 0.7)  
4. `batch/<id>/` smoke + holdout sets  
5. Promotion discipline from family `IMPROVING.md` / batchsim compare  

Do **not** re-open SIP-ORB, gap-and-go, or dominance-flip under new names without a
**pre-registered structural difference** and a fresh sealed holdout budget.

---

## Checklist (status board)

| Priority | Id | Type | Status |
|:--:|---|---|---|
| 1 | `right_side_v` | new family | **PARKED** multi-year FAIL (−0.03) |
| 1 | `vwap_pullback` | new family | **Paper-optional (2nd book)** — multi-year PASS thin; paper book + portfolio; more cost-fragile than micro |
| 1 | `bb_squeeze_long` | new family | **PARKED** — multi-year FAIL (−0.011; 0/4 years); n=7149 |
| 1 | `micro_pullback` | new family (warrior phase-2) | **Paper-optional (liquid)** — multi-year PASS + paper book; warrior probe **FAIL** years+ (see warrior_probe/) |
| 1 | `no_mans_land` | shared module / filter | **Shipped** — A/B: NML hurts micro/VWAP; **default OFF**; portfolio caps **keep** |
| 1 | warrior VWAP reclaim | warrior pattern | deferred (prefer `vwap_pullback`) |
| 2 | `trend_pullback` | new family (swing) | **PARKED** — multi-year FAIL (−0.02) |
| 2 | `breakout_first_pullback` | new family (swing) | **PARKED** — 0.1.0 FAIL (−0.02); 0.2.0 worse (−0.12) |
| 2 | `anchored_vwap` | new family | not started |
| 2 | `multi_tf_trend` | gate / family | not started |
| 3 | `offer_take_scalp` | blocked (L2) | parked |
| 3 | `news_reaction` | blocked (news) | parked |
| 3 | `ipo_suite` | blocked (data) | parked |
| 3 | `macd_divergence` | filter only | parked |
| 3 | `trendline_bounce` | low priority | parked |
| 3 | `fib_50` | confluence only | parked |

---

*Source analysis: Lance inventory + audit of `llm_trader` (`warrior`, `cup_handle`) and
`lab` strategy families / research logs (2026-06…2026-07). Update this file when a family
ships or a Stage-0 kill retires a row.*
