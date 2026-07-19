# llm_trader — Strategy Implementation Roadmap

**Purpose:** List strategy families and entry patterns that are **not yet implemented**
in `llm_trader` (and not already exhausted as near-identical molds in `lab`), based on
the Lance Breitstein strategy inventory (`library/lance/lance_strategies.md`) vs current
coverage in `llm_trader` + `lab`.

**Constraints (product mandate):** long-only equities · no shorting · no futures · no options
(options path optional later under Opportunity F — not default).

**Broker default (research economics):** **WeBull US long equity** — $0 commission on
stocks/ETFs; mandatory sell-side regulatory pass-through only; **slippage/spread is the
real cost.** Model: `costs/webull.py`. Free commission does **not** revive E0-failed
liquid micro/VWAP.

**Active focus (2026-07+):** **Opportunity track** after liquid short-hold integrity kill
(E0 causal RVOL FAIL). Hunt where WeBull economics + selection + harder venues can pay.
Do **not** resurrect parked leak-contaminated or E0-failed detectors via retunes.

**How to add a family:** follow [`MULTI_STRATEGY.md`](MULTI_STRATEGY.md). Pre-register
before any result-producing run. Causal screens only. Report notional bps + actual-risk R.

**Related docs:**
- Short-hold freeze / E0: [`batch/SHORT_HOLD_PAPER.md`](batch/SHORT_HOLD_PAPER.md),
  [`batch/micro_pullback/PREREG_CAUSAL_E0.md`](batch/micro_pullback/PREREG_CAUSAL_E0.md)
- Peer reviews: `peer_reviews/2026-07-18-new-strategies/`
- Platform backlog: [`BACKLOG.md`](BACKLOG.md)
- Lab kills: `../lab/validation/STRATEGY_SYNTHESIS.md`
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
| **Status** | **PARKED** — contaminated thin PASS invalidated (full-day RVOL); not re-promoted after E0. See multiyear + peer reviews |

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
| **Micro-pullback long** | Short-hold continuation after first pause | **Shipped → PARKED** after E0 causal FAIL (−0.035, 0/4). Contaminated PASS invalid. See `multiyear_causal/RESULTS.md` |
| **VWAP reclaim after washout** | Overlaps `vwap_pullback` | PARKED with VWAP book (leak class) |
| **Flat-top / multi-bar base** beyond single ACD | Still long breakout, better structure | Thin / partial |

Optional later: port `micro_pullback` detector onto warrior small-cap gap screen once
point-in-time float multi-year is available.

---

## Active opportunity track (post-E0 — execute this)

**Context:** Liquid take-all short-holds died under causal screens. Traders still make
money elsewhere (selection, harder venues, risk premium, process). WeBull $0 commission
helps high-turnover longs; **slip still binds**. Free commission does not un-kill E0.

**Rules for this track:**
1. Pre-reg before runs; one evidentiary shot per version  
2. Causal features only (no full-day volume for intraday admission)  
3. WeBull cost model default; slip stress by liquidity tier  
4. No resurrecting parked families via threshold nibble  
5. Smoke/n30 = code validation only — not promotion evidence  

### Opp A — `costs/webull` research default (Phase 0) — **EXECUTE FIRST**

| | |
|---|---|
| **Thesis** | Judge ideas on *your* friction: $0 commission, tiny sell regulatory, tiered slip |
| **Deliverable** | `costs/webull.py` (+ stress grid helpers); all new families import it |
| **Kill / success** | Success = module + tests + documented defaults. Not a PnL gate |
| **Status** | **DONE** — `costs/webull.py` + tests |

### Opp B — Selection layer (not take-every-setup)

| | |
|---|---|
| **Thesis** | Scanners lose because they force all hits; edge may live in top-quantile days only |
| **Ideas (pre-register one)** | Causal time-of-day RVOL; max 1–2 names/day; SPY regime admission; first signal only |
| **Attach to** | New families (e.g. Opp C), not retune of parked micro |
| **Status** | Not started — after Opp C base exists |

### Opp C — `inplay_continuation` (harder venue / gap in-play) — **Phase 1 AFTER A**

| | |
|---|---|
| **Thesis** | Edge is in catalyst/gap small–mid caps, not mega-cap liquid take-all |
| **Window** | Rolling ~12 months only (current float OK with warrior-style caveat) |
| **Screen** | Gap ≥ 5%, price $2–50, ADV floor, **causal** prior-day or time-of-day RVOL |
| **Pattern (v0.1.0 one only)** | Opening impulse → 1–3 bar micro-pb holding VWAP → green break (same geometry as micro, **new universe + WeBull costs + high slip stress**) |
| **Costs** | WeBull commission 0 + sell regulatory; slip baseline **15 bps** one-way (small/mid); stress 30 / 50 |
| **Gates** | Pooled effR > 0; ≥2 calendar periods > 0 if multi-period; fail if only works at fantasy 2 bps slip |
| **Status** | **Probe PASS (thin)** — n=87, effR +0.076 @ slip15; **2025 −0.12 / 2026 +0.29** (unstable). Slip30 ~0. See `batch/inplay_continuation/probe_12m/RESULTS.md`. **No capital**; next Opp B selection or kill if selection fails |
| **Do not** | Claim multi-year without PIT float; claim Ross validation without catalyst feed |

### Opp D — Overnight / multi-day with *new* thesis (not failed TA scanners)

| | |
|---|---|
| **Thesis** | Overnight equity risk premium / event drift can pay; failed scanners were loose take-all mega-cap TA |
| **Candidates** | Earnings/gap-hold; sparse weekly trend + regime; ETF relative (later) |
| **Status** | Backlog — after Opp C probe result |
| **Still parked** | `trend_pullback`, `breakout_first_pullback`, multi-day `right_side_v` as shipped |

### Opp E — Boring baseline (process scoreboard)

| | |
|---|---|
| **Thesis** | Clever systems must beat a simple long process under WeBull costs |
| **Example** | Rules-based liquid ETF hold / trend with hard daily loss and trade caps |
| **Status** | Backlog — define after cost module ships |

### Opp F — Options (WeBull)

| | |
|---|---|
| **Thesis** | Defined-risk long premium or spreads — different skill tree |
| **Note** | Verify contract/exchange fees even if “$0 commission”; bid/ask brutal |
| **Status** | Explicitly **deferred** — not next |

### Opp G — Process automation (risk / stand-down)

| | |
|---|---|
| **Thesis** | Enforce max loss/day, max trades, no revenge size — process edge without holy grail pattern |
| **Status** | Cross-cutting; attach to any live/paper path later |

### Execution order (binding)

```text
Phase 0  Opp A   WeBull cost model + tests
Phase 1  Opp C   inplay_continuation 12m probe (causal + WeBull + high slip)
Phase 2  Opp B   selection filters on C if base not dead
Phase 3  Opp E   boring baseline scoreboard
Phase 4  Opp D   only with new structural multi-day thesis + pre-reg
Defer    Opp F   options
Always   Opp G   process caps when any paper path exists

PARKED forever without new thesis: liquid micro/VWAP/BB take-all, multi-day TA as shipped
```

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
=== CLOSED CAMPAIGN (2026-07) ===
DONE  multi-day TA FAIL park (trend / BFP / RSV)
DONE  bb_squeeze FAIL park; NML v0.1.0 OFF; portfolio packaging keep
DONE  E0 causal RVOL → micro FAIL → park liquid short-hold take-all
DONE  code: prior-day RVOL; VWAP causal morning; peer-review trail

=== ACTIVE (WeBull opportunity track) ===
DONE  Opp A  costs/webull.py
DONE  Opp C  inplay 12m probe PASS thin (unstable years) — see probe_12m/
NEXT  Opp B  selection layer on inplay (pre-reg) OR park C if year split unfixable
THEN  Opp E  boring baseline
LATER Opp D  new multi-day thesis only
DEFER Opp F  options
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
| **0** | `costs/webull` | **Opp A** | **DONE** — `costs/webull.py` |
| **0** | `inplay_continuation` | **Opp C** | **Probe PASS thin** (+0.076 @15bps; 2025 red). No capital. Next: Opp B or park |
| **0** | selection layer | **Opp B** | pending (after C base) |
| **0** | boring baseline | **Opp E** | pending |
| **0** | process caps | **Opp G** | pending paper path |
| 1 | `right_side_v` | multi-day | **PARKED** FAIL (−0.03) |
| 1 | `vwap_pullback` | short-hold | **PARKED** leak + not re-promoted post-E0 |
| 1 | `bb_squeeze_long` | short-hold | **PARKED** FAIL (−0.011; 0/4) |
| 1 | `micro_pullback` | short-hold | **PARKED** E0 causal FAIL (−0.035; 0/4) |
| 1 | `no_mans_land` | filter | shipped; default OFF for short-holds |
| 2 | `trend_pullback` | swing | **PARKED** FAIL (−0.02) |
| 2 | `breakout_first_pullback` | swing | **PARKED** FAIL |
| 2 | `anchored_vwap` | swing | not started (Opp D-adjacent) |
| 2 | `multi_tf_trend` | gate | not started |
| 3 | options path | **Opp F** | deferred |
| 3 | `offer_take_scalp` | L2 | parked |
| 3 | `news_reaction` | news | parked |
| 3 | `ipo_suite` | data | parked |

---

*Updated 2026-07-19: opportunity track + WeBull economics after E0 integrity kill.
Source: Lance inventory, peer reviews 2026-07-18, operator broker = WeBull.*
