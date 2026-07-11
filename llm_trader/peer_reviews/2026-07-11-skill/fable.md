# TRADE_SIMULATOR — Profitability Gap Analysis vs. Ross Cameron

**Date:** 2026-07-11
**Author:** Claude (Fable 5)
**Skill version reviewed:** 3.2.0 (live), with history back to 2.0.x
**Question:** Why are the simulated trading results "a LOT weaker" than Ross Cameron's,
and where does the skill implementation diverge from what Ross actually does?

---

## TL;DR

The algorithm's **per-trade edge is already in Ross's range** when measured honestly.
The impression that results are "a LOT weaker" comes from three compounding effects,
none of which is a broken strategy:

1. **An inverted trade profile.** Your system runs ~35% win rate with a ~5:1 payoff.
   Ross runs ~55–65% win rate with a ~1:1 payoff. Both produce ~0.2R expectancy per
   trade — but the low-win-rate curve *feels* like losing because you are red on ~2 of
   every 3 trades.
2. **A deliberately pessimistic execution rebaseline (v3.0.0)** that made all v3 numbers
   incommensurate with both the older 2.x numbers *and* Ross's real-world fills.
3. **The layers where Ross's dollars actually come from** — ruthless setup selection,
   pyramiding, day-level sizing (icebreaker), hot/cold adaptation, and compounding — are
   either missing from the implementation or never fire in practice.

**Bottom line:** In R-multiple terms you are close to Ross per-trade. The wealth gap is
in the selection + sizing + compounding scaffolding that sits *on top of* the per-trade
edge, plus a genuine win-rate deficit from confirming entries on the wrong timeframe.

---

## Evidence base

Data pulled 2026-07-11 from the live viewer (`/api/sessions`), the by-version report
(`recorder report --by-version`), the skill text (`trade_skills/3.2.0.md`), the
experiment log (`skills/CHANGELOG.md`), the execution engine (`execution.py`), and a
leaf-level scan of the most recent batch (`20260711092732-BATCH-04015e`, 100 planned /
16 traded leaves examined for exit-reason and pyramiding behavior).

### Per-batch snapshot (recent v3.x batches)

| Batch (date)        | win% | clean R | eff R | PF   | avg win R | avg loss R |
|---------------------|------|---------|-------|------|-----------|------------|
| 2026-07-11 09:27    | 31.2 | 0.202   | 0.188 | 2.22 | 1.22      | −0.24      |
| 2026-07-11 08:39    | 36.3 | 0.230   | 0.209 | 2.56 | 1.07      | −0.23      |
| 2026-07-10 23:07    | 37.7 | 0.259   | 0.178 | 2.78 | 1.07      | −0.23      |
| 2026-07-10 21:11    | 37.1 | 0.236   | 0.210 | 2.52 | 1.05      | −0.25      |
| 2026-07-09 10:25    | 45.6 | 0.614   | 0.537 | 6.01 | 1.68      | −0.39      |

### By-version (paid batches, MIXED rows excluded from ranking)

| version | n   | win% | P&L      | clean R | eff R | MFE capt |
|---------|-----|------|----------|---------|-------|----------|
| 2.4.1   | 182 | 41%  | $3379.64 | 0.46    | 0.42  | 0.39     |
| 2.7.0   | 183 | 43%  | $4097.77 | 0.56    | 0.52  | 0.35     |
| 3.0.0   | 477 | 35%  | $4766.51 | 0.25    | 0.23  | 0.25     |
| 3.1.0   | 89  | 37%  | $838.47  | 0.24    | 0.21  | 0.21     |
| 3.2.0   | 69  | 38%  | $712.86  | 0.26    | 0.18  | 0.21     |

The apparent "collapse" from ~0.5–0.9R (2.x) to ~0.25R (3.x) coincides exactly with the
v3.0.0 execution rebaseline. That is a measurement change, not a strategy regression
(see §2 below).

### Ross's canon numbers (for reference)

| Metric              | Ross (from corpus)                                  |
|---------------------|-----------------------------------------------------|
| Win rate            | 55–65% overall; 75–80% on A-setups in a hot market  |
| Avg win : avg loss  | ~1:1 realized (targets 2:1 as a ceiling)            |
| Hold time           | ~4 min average; 5–60 min range                      |
| Edge source         | **Accuracy > 50%**, not reward-to-risk              |
| Green/red days      | 222 green / 8 red over 230 days (best documented)   |
| Primary chart       | **5-minute** (1-min for fine timing only)           |

---

## Part 1 — Why the numbers look worse than they are

### 1.1 The profile is inverted, but the expectancy is comparable

- A 60% win rate at 1:1 → expectancy ≈ **0.2R**.
- Your v3.x batches → clean expectancy ≈ **0.20–0.26R**.

**You are already at Ross-comparable per-trade expectancy.** The difference is
*distribution*, not *edge*: he wins small and often; you win big and rarely. His curve is
psychologically and mechanically smoother (fewer, smaller drawdowns; compounds cleanly),
but the arithmetic mean per trade is in the same neighborhood.

The wealth gap therefore is **not** primarily a per-trade-alpha problem. It is:
(a) the scaffolding on top (selection, sizing, compounding), and
(b) a real but secondary win-rate deficit from entry-timeframe mismatch (§3.1).

### 1.2 The v3.0.0 rebaseline is deliberately adverse — don't compare across it

From `CHANGELOG.md` (3.0.0): *"all pre-3.0 reported-fill R comparisons are
incommensurate."* Prior to v3, the executing model supplied its own fills, shares, and
stops — which "permits impossible OHLC fills, unbounded participation, and hidden
stop-gap risk." The 2.x 0.9R figures were **inflated by unverified agent arithmetic.**

v3's `execution.py` applies, on every trade (defaults):

| Parameter                | Value      |
|--------------------------|------------|
| entry slippage           | 10 bps     |
| exit slippage            | 10 bps     |
| commission per share     | $0.005     |
| max participation rate   | 10% of bar volume |

Plus **stop-first resolution** on any bar that could hit both a target and a stop, and
**worse-of-open-or-trigger** entry fills. Ross, by contrast, gets wholesaler price
improvement ("7x liquidity vs. displayed quote"), enters intra-bar on hotkeys the moment
the break prints, and uses mental stops he can override. **He would score worse under
your fill model too.** The 0.9R → 0.25R drop is mostly measurement honesty.

**Mitigation:** run one batch at 5bps / midpoint-ambiguity to bound how much of the
2.x→3.x drop is pure fill-model pessimism. If most of it, stop treating v3 as a regression.

### 1.3 The scratch tax

Leaf scan of the latest batch: **38% of traded leaves finished within ±0.15R** (6 of 16).
The +$0.10 break-even rule, combined with stop-first adverse resolution and 10bps each
way, manufactures near-zero outcomes that still count as non-wins. Ross's "free trade"
BE rule works because he re-enters instantly on the tape; your implementation pays
slippage + commission on each scratch and then enforces a 3-bar cooldown before it can
re-enter (§C).

---

## Part 2 — Where the implementation diverges from Ross

### 2.1 Entry confirmation is on the wrong timeframe (highest-impact gap)

Ross's primary chart is the **5-minute**; the 1-minute is explicitly "for fine timing
only" (canon §9, §20.8). Your ENTRY CHECKLIST (skill §A) evaluates its boxes — `new_high`,
green, above-VWAP, volume dominance, candle shape — on **1-minute** bars. Many 1-min
"breakouts" are not 5-min setups at all, so the system takes trades Ross would never see.

This is the most likely driver of the **35% vs. 55–65% win-rate gap.** Notably, the skill
*already* moved the **runner exit** to a rolling 5-min lens (§B.5) for precisely this
reason — "applying his red-candle rule to every 1-min bar sells the runner into one bar of
ordinary noise." The **entry side never received the same fix.**

**Mitigation:** require the 1-min trigger to sit inside a valid 5-min structure (5-min
new high, 5-min green, 5-min above VWAP), or confirm the checklist on the completed 5-min
candle and use the 1-min only to time the fill. This is the single most Ross-faithful
change available and attacks the win-rate deficit directly.

### 2.2 The setup pool is not Ross's setup pool

Ross scans the **entire market** at 5–6am, filters 30–50 gappers down to the top 3–10 by
the 5 Pillars, and trades **only the leading gapper** — "trade the best, leave the rest."
Your batches replay a fixed sample of 100 recorded setups, most of which he'd never touch.

The skill correctly recognizes this: v3.2.0 stood down on **31 of 69** sessions (45%), and
stand-downs drag effective R below clean R (0.26 → 0.18). That is the discipline working —
but it also means the batch is graded against a pool of marginal setups, so the average
looks weaker than a trader who only ever engages the day's single best name.

**Mitigations:**
- Tighten to **A-only** and measure expectancy **per grade**. Grade B currently trades on
  `rvol ≥ 2`, but Ross's *money* is at 5×+, float <10M, gap >10%. If B-grades are
  net-negative after costs, gate them out.
- The $3 price floor added in 3.2.0 was the right instinct (below-$3 trades were −$45.49 /
  −0.048R on the dev baseline). Extend the same empirical-guardrail approach to the other
  soft pillars.

### 2.3 Pyramiding is written but never fires

Leaf scan: **0 multi-fill entries** in the latest batch. Ross's outsized winners come from
the 3-step pyramid (starter → add on confirmation → add on continuation), which is how he
gets "same initial risk, 3x the profit" (canon §10). The skill documents ADD_CLOSE (§B.6)
but it is not being used.

Suspected cause: the **one-intent-per-bar** management contract crowds adds out — the same
defect class that v3.1.0's investigation found for scale intents (*"30/56 scale intents
were placed after their target traded; four never filled"*). If the agent can only log one
intent per bar, protective-stop moves and scale-outs win the slot and the add never gets
placed.

**Mitigation:** make adds **engine-managed**, attached to the entry intent the way v3.1.0
attached brackets — the engine fires the add when its condition (first green bar closing
above entry; fresh new-high continuation with healthy rvol + MACD) is met, independent of
the one-intent-per-bar limit. Ross's 3x-same-risk math is unreachable while adds never
fire.

### 2.4 Runner capture regressed (0.39 → 0.21 MFE capture)

MFE capture fell from **0.39** (v2.4.1) to **0.21** (v3.x). Latest-batch exit reasons:
**10 close-confirmed soft bailouts vs. 6 protective stops** — the soft-bailout ladder is
doing most of the exiting. The 2.6.0 post-mortem already diagnosed this exact pattern:
*"the objectified exits did cut loser size, but ... most damage is the ladder exiting
trades earlier for less R — clipping runners to save on losers, net slightly negative."*

**Mitigation:** audit which soft-bailout predicate (failed-break / lost-VWAP /
topping-tail / MACD / time-stop) is firing on the trades with the largest unrealized MFE.
Ross's final exit is a **5-min** red-candle-closes-below-prior-green-low; make sure no
1-min predicate is pre-empting it on the runner tranche.

### 2.5 Time stop is too fast

Skill §B.2 time-stop = **5 one-minute bars** with no new high. Ross's time stop is
**30–60 minutes** ("if it's just sitting there, I'm out" — canon §4). Five minutes on a
1-min feed exits consolidations that would have resolved. Test paired at ~10–15 bars.

### 2.6 Structurally absent (cannot be fixed in this data model)

- **Level II / Time & Sales** — his primary false-breakout detector and hidden-buyer
  signal (canon §19). The sim has no order-book data.
- **Intra-bar entry** — "the moment the price breaks that candle, I do not wait for the
  candle to close." The armed buy-stop (§A) approximates this, but fills are still
  gap/slippage-adverse rather than at-touch.
- **The morning selection funnel** — picking the single best gapper out of the whole
  market each day. The batch pool is fixed.

These bound how faithfully the sim can ever reproduce him. The realistic target is
matching his **per-trade R profile** (close already) plus adding the scaffolding layers.

---

## Part 3 — The missing day-level / account-level scaffolding

Ross turned $583 → $335K primarily through **compounding and sizing up on hot days**, not
through a higher per-trade R. The implementation trades each setup in isolation with a
fixed **$40 risk budget / $12,000 buying power** and no cross-session state. Missing:

- **Icebreaker sizing** — start each day at 25% size; scale to full only after the first
  profit milestone; stay small all day on cold tape. This is "the single biggest
  contributor to long green streaks" in the canon (§5) and mechanically shrinks red days.
- **Daily loss limit / walk-away rules** — stop after giving back 20% of profit, 3 losses
  in a row, or hitting the daily goal (§4, §6).
- **Hot/cold market gauge** — count of big gappers in the day's pool → aggressiveness. In a
  cold tape, A-setups only and quarter size.
- **Compounding** — risk grows with the account. A fixed $40 budget can never produce a
  Ross-like equity curve even with an identical per-trade edge.

**Mitigation:** if the goal is Ross-*like results* (not just Ross-*like trades*), model a
day as an ordered sequence of setups with icebreaker sizing, a daily loss limit, a breadth
gauge, and compounding in the batch report. This is where his headline dollars live.

---

## Part 4 — Prioritized ideas & mitigations

1. **Rebaseline expectations before changing rules.** Compute a "Ross-equivalent" score
   under your own fill model (60% × 1:1 ≈ 0.2R) and a naive buy-anchor/sell-close baseline
   per setup. Likely finding: you're at per-trade parity and the work is elsewhere.
2. **Friction sensitivity run** (5bps / midpoint) to bound how much of 2.x→3.x is pure
   fill-model pessimism.
3. **A-only selection + per-grade expectancy.** Gate out B-grades if net-negative after
   costs. Extend the 3.2.0 price-floor guardrail method to the other pillars.
4. **Move entry confirmation to the 5-min lens** (or require the 1-min trigger inside a
   valid 5-min structure). Highest-impact win-rate fix; mirrors the runner-exit fix
   already shipped.
5. **Fix pyramiding the 3.1.0 way** — engine-managed adds attached to the entry intent, so
   the one-intent-per-bar contract can't starve them.
6. **Audit the scratch tax** — how many BE-stop exits had first reached +0.8R? Test
   BE-at-+½R or BE-plus-costs instead of +$0.10.
7. **Slow the time stop** to ~10–15 one-minute bars; test paired.
8. **Investigate the MFE-capture regression** (0.39 → 0.21): which soft-bailout predicate
   clips the biggest runners? Ensure the 5-min red-candle rule owns the runner exit.
9. **Add the day-level layer** — icebreaker sizing, daily loss limit, hot/cold breadth
   gauge, compounding in the batch report. Where the actual wealth was built.
10. **Try a stronger executing model, paired.** Everything runs on `deepseek-v4-flash`;
    the discretionary boxes (candle shape, "coiling" bases, arm decisions) are judgment
    calls where model quality plausibly moves win rate. The report already warns "models
    MIXED" — run one clean paired batch, same 100-set, stronger model.
11. **Honor the promotion gate.** 3.0.0 and 3.2.0 are both ⏳ HOLD / unvalidated; you are
    stacking changes on an unvalidated base. Per `IMPROVING.md`: paired compare on the
    pinned 100-set + a disjoint holdout before the next rule change.

---

## Honest caveat

Even with all of the above, the sim will never fully reproduce Ross: no tape reading, no
true intra-bar entries, adverse OHLC resolution, and a fixed setup pool instead of the
whole market's best gapper each day. The realistic goal is to **match his per-trade R
profile** (closer than the headline numbers suggest) and then rebuild the **selection +
sizing + compounding layers** where his wealth was actually generated.

---

*Sources: `library/ross_cameron/all_content_structured.md`,
`library/ross_cameron/ROSS_CAMERON_TRADING_CANON.md`,
`llm_trader/skills/trade_skills/3.2.0.md`, `llm_trader/skills/CHANGELOG.md`,
`llm_trader/execution.py`, `recorder report --by-version`, `/api/sessions`, and a
leaf-level scan of batch `20260711092732-BATCH-04015e`.*
