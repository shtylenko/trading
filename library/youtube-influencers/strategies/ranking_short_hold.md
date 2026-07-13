# Strategy Rankings — Short Hold Only (Hours → 3 Days Max)

Companion to [`ranking.md`](ranking.md). Same 25 strategies, **re-scored for a hard hold mandate:**

> Hold from a few hours up to **3 calendar/trading days maximum**.  
> Strategies that *need* multi-week or multi-month holds are **deprioritized**.

**Sources:** strategy files in this directory; lab synthesis (`lab/validation/STRATEGY_SYNTHESIS.md`); short-horizon kills (ORB, gap-drive, dominance-flip, overnight-as-primary, H=5 multiday).

---

## Mandate rules

| Rule | Detail |
|------|--------|
| **Min hold** | Intraday OK (minutes–hours) |
| **Max hold** | **3 days** (hard time stop if still open) |
| **Deprioritize** | Designed hold typically **>3 days**, or edge depends on multi-week drift |
| **PDT** | Not a penalty (min ≈ $2k); costs and lab edge still apply |
| **Account** | ~$2–5k long-only US stocks/ETFs |

### How scoring differs from `ranking.md`

| Factor | Change under short-hold mandate |
|--------|----------------------------------|
| **Hold fit** | **New primary filter** (1–5). Wrong-horizon strategies capped hard. |
| **Expected return** | Scored for a **≤3d truncated** version of the strategy, not the full multi-week book. Multi-month systems collapse. |
| **Confidence** | Your lab is harsh on this mold: same-day families mostly **killed**; overnight **thin**; H=5 multiday **dead**. |
| **# setups** | Short-horizon scanners often produce *more* candidates — that does not raise confidence. |
| **Backtest fit** | Intraday entries need 1‑min / RTH bars; daily-only systems that force a 3d exit are still testable but may not be *the* strategy. |
| **$2–5k** | Same as general ranking (PDT not docking day trades). |

### Lab anchors for this mold (honest)

| Finding | Implication for short-hold ranking |
|---------|-------------------------------------|
| SIP-ORB exhausted | Pure opening-range breakout edge ~0 after costs |
| Gap-drive sealed 2025 fail | Gap-and-go / EP open-print style deprioritized on confidence |
| Dominance-flip / mean-rev killed | Bounce / contrarian short holds weak |
| Overnight premium real but below bar | #24 gets hold-fit credit, not high ER/confidence |
| Multiday H=5 dead; H=20 works | Forcing 3d max on swing systems **destroys** residual-mom / weekly BO economics |
| x03 residual mom (monthly) | **Wrong horizon** under this mandate despite being best long-hold edge |

**Meta:** under a ≤3d max hold, **no strategy in this list scores as a proven OOS alpha for you**. Rankings prioritize *relative* fit, testability, and truncated realism — not “this is validated.”

---

## Scoring scale (1–5)

| Factor | Higher means… |
|--------|----------------|
| **Hold fit** | Designed / naturally works hours → ≤3 days |
| **Exp. return** | Realistic edge **if forced to exit by day 3** |
| **# setups** | Opportunity frequency under short horizon |
| **Confidence** | Belief edge survives costs + your short-horizon evidence |
| **Backtest fit** | Testable with existing marketdata/lab tooling |
| **$2–5k fit** | Workable at small size (costs, concentration) |

### Hold fit bands

| Score | Meaning |
|------:|---------|
| 5 | Native: hours to 1–2 days; 3d is a long hold for it |
| 4 | Typical 1–3 days; hard 3d time stop is natural |
| 3 | Often 3–5+ days; 3d stop is early but usable |
| 2 | Typical week+; 3d truncation is a different strategy |
| 1 | Multi-week / multi-month core; **deprioritize** |

**Composite:** `Sum = Hold + ER + Setups + Confidence + Backtest + $2–5k` (max 30).

**Hard filter:** strategies with **Hold fit ≤ 2** are **deprioritized** (listed in a separate table). Primary ranking = **Hold fit ≥ 3**.

---

## Primary ranking — Hold fit ≥ 3 (short-hold compatible)

| # | Strategy | Native hold (docs) | Hold | ER | Setups | Conf. | Backtest | $2–5k | **Sum** |
|---|----------|--------------------|:----:|:--:|:------:|:-----:|:--------:|:-----:|:-------:|
| **23** | **VWAP Bounce / Trend** | Intraday–1–5d | **5** | 2 | 4 | 2 | 3 | 4 | **20** |
| **11** | **Gap and Go** | Hours–1–3d | **5** | 1 | 4 | 1 | 3 | 3 | **17** |
| **24** | **Overnight Hold Swing** | 1–5d (core 1–3) | **4** | 2 | 4 | 2 | 4 | 4 | **20** |
| **06** | **MACD 3-10-16** | 2–5d (30–120m entries) | **4** | 2 | 3 | 2 | 3 | 4 | **18** |
| **01** | **Momentum Burst** | 3–5d (time-stop at 3d) | **3** | 3 | 4 | 2 | 3 | 4 | **19** |
| **15** | **Inside Bar Breakout** | 3–8d (exit by 3d) | **3** | 2 | 4 | 2 | 5 | 4 | **20** |
| **18** | **Bollinger Squeeze** | 3–10d (early exit) | **3** | 2 | 3 | 2 | 5 | 4 | **19** |
| **22** | **TTM Squeeze** | 3–10d (early exit) | **3** | 2 | 3 | 2 | 4 | 4 | **18** |
| **12** | **S/R Bounce** | 3–10d (scalp–swing) | **3** | 2 | 3 | 2 | 2 | 3 | **15** |
| **10** | **Contrarian Swing** | 3–14d (early exit) | **3** | 1 | 3 | 1 | 4 | 3 | **15** |
| **05** | **Anchored VWAP Pullback** | 3–10d | **3** | 2 | 3 | 2 | 2 | 4 | **16** |
| **17** | **Fibonacci Pullback** | 3–10d | **3** | 2 | 3 | 2 | 3 | 3 | **16** |
| **02** | **Episodic Pivot** | 3–10d avg (often >3) | **3** | 3 | 1 | 1 | 2 | 4 | **14** |

### Sorted by sum (primary only)

| Rank | # | Strategy | Sum | One-line |
|-----:|---|----------|----:|----------|
| 1 | 23 | VWAP Bounce | 20 | Best *native* short-hold structure; edge thin after costs |
| 1 | 24 | Overnight Hold | 20 | Best lab-aligned short idea (premium real); still below bar alone |
| 1 | 15 | Inside Bar | 20 | Most backtestable short-hold pattern; modest expectancy |
| 4 | 01 | Momentum Burst | 19 | Closest “famous” fit; force exit day 3; situational filter critical |
| 4 | 18 | Bollinger Squeeze | 19 | Clean daily features; many squeezes fail within 3d |
| 6 | 06 | MACD 3-10-16 | 18 | Intraday→swing timing; needs multi-TF bars |
| 6 | 22 | TTM Squeeze | 18 | Same family as BB squeeze; slightly more proprietary |
| 8 | 11 | Gap and Go | 17 | Perfect hold fit; **your sealed OOS killed the cousin** |
| 9 | 05 | AVWAP Pullback | 16 | Good R:R stories; anchors hard to systematize |
| 9 | 17 | Fib Pullback | 16 | Common; weak unique edge |
| 11 | 12 | S/R Bounce | 15 | Discretionary levels; MR-adjacent |
| 11 | 10 | Contrarian | 15 | Hold-compatible; **mean-rev killed** in lab |
| 13 | 02 | Episodic Pivot | 14 | High *claimed* ER; many winners need >3d; gap entry weak for you |

---

## Deprioritized — Hold fit ≤ 2 (need >3 days)

These are **not** primary candidates under the short-hold mandate. Scores show what happens if you force a 3d exit (usually: ER and confidence collapse).

| # | Strategy | Native hold | Hold | ER (≤3d) | Setups | Conf. | Backtest | $2–5k | Sum | Why deprioritized |
|---|----------|-------------|:----:|:--------:|:------:|:-----:|:--------:|:-----:|:---:|-------------------|
| 03 | SEPA / VCP | 2–8 **weeks** | 1 | 1 | 2 | 1 | 3 | 4 | 12 | Edge is multi-week Stage‑2 trend |
| 04 | Weekly Breakout Consol. | 4–12 **weeks** | 1 | 1 | 2 | 1 | 4 | 4 | 13 | Weekly system; 3d exit ≠ the system |
| 07 | Bull Flag | 5–15 **days** | 2 | 2 | 3 | 2 | 2 | 4 | 15 | Flags often resolve over a week+ |
| 08 | Concentrated Conviction | **Months–years** | 1 | 1 | 1 | 1 | 1 | 5 | 10 | Investing, not short hold |
| 09 | 9/21 EMA Trend | 5–20 **days** | 2 | 2 | 4 | 2 | 5 | 4 | 19 | Pullback trend-follow needs room |
| 13 | Range BO / Donchian | 2–8 **weeks** | 1 | 1 | 3 | 2 | 5 | 3 | 15 | Classic multi-week TS momentum |
| 14 | Pocket Pivot | 5–20 **days** | 2 | 2 | 3 | 2 | 3 | 3 | 15 | Accumulation → multi-day/week |
| 16 | SMA Trend Structure | 2–6 **weeks** | 1 | 1 | 3 | 2 | 5 | 4 | 16 | Stage trading is not a 3d trade |
| **19** | **RS / residual mom** | **1–3 months** | **1** | **1** | 3 | 2 | 5 | 3 | 15 | **Best long-hold edge; wrong mold here** |
| 20 | Inst. Accumulation | 2–6 **weeks** | 1 | 1 | 3 | 2 | 3 | 3 | 13 | Confirmation for longer swings |
| 21 | DCA Growth ETFs | **Years** | 1 | 1 | 5 | 5 | 5 | 5 | 22 | Sum inflated by beta; not a short hold |
| 25 | Breakout-Retest | 1–3 **weeks** | 2 | 2 | 2 | 2 | 3 | 4 | 15 | Retest structure targets week+ moves |

**Note on #19 / #13 / #04:** high scores in [`ranking.md`](ranking.md) do **not** transfer. Under ≤3d max they are **explicitly deprioritized**.

**Note on #21:** sum looks high because DCA always “fits” small accounts and is high-confidence *beta*. It fails the hold mandate entirely — ignore for short-hold selection.

---

## Short-hold Top 3 (under this mandate)

Given lab evidence, “top” means **best research/ops candidates**, not proven profitable.

| Rank | Strategy | Why | Main risk |
|-----:|----------|-----|-----------|
| **1** | **#24 Overnight Hold** (1–3 nights, hard exit) | Only short-hold theme your lab found *real* (overnight premium); daily-bar friendly; low screen time | Thin / cost-fragile; closed as below-bar *standalone*; needs strict filters |
| **2** | **#01 Momentum Burst** (enter day 1, exit ≤ day 3) | Native multi-day burst window overlaps 3d max; scannable; high setup count | Win rate low; situational market filter; your H=5 multiday was weak |
| **3** | **#15 Inside Bar** *or* **#23 VWAP Bounce** | #15: most mechanical daily backtest. #23: best pure hours-hold structure if you have 1‑min data | Both: modest/no proven edge after costs on liquid names |

### Explicitly not Top 3 here (despite fame or long-hold rank)

| Strategy | Reason under short-hold |
|----------|-------------------------|
| #19 RS / x03 | Needs ~month hold; 3d truncation kills the anomaly |
| #13 Donchian weekly | Multi-week trend system |
| #04 Weekly breakout | Same |
| #11 Gap and Go | Hold fit perfect; **confidence 1** after gap-drive OOS fail |
| #02 EP | Winners often 5–10d+; open entries costly |

---

## Suggested short-hold research order

```text
1. #24 Overnight (time-stop ≤3 sessions)
   - Stage-0: close→open / close→close(d+1..3) with your existing overnight capture

2. #01 Momentum Burst truncated
   - 4% range-expansion day, volume, exit at min(stop, day-3 close)
   - Market filter required (index 10/20 EMA or equivalent)

3. #15 Inside Bar (daily) hard exit day 3
   - Highest backtest cleanliness among patterns

4. Optional intraday: #23 VWAP (needs 1‑min)
   - Only after daily short-hold Stage-0s; cost model must be honest

Skip for this mandate: #19, #13, #04, #03, #08, #16, #21 as primaries
```

---

## Practical rules if you adopt this mandate

1. **Hard time stop:** flat by end of day **T+2** (entry day = T+0 → max 3 sessions) or calendar 3 days — pick one definition and keep it.
2. **Do not “let winners run” past 3d** — that is a different strategy and reintroduces multi-day books you said you do not want.
3. **Expect lower ER** than multi-week momentum: your own funnel already showed the multi-day premium lives at longer horizons.
4. **Cost model:** short holds × small account = spread/slippage dominate; prefer liquid names / ETFs.
5. **PDT OK** at ~$2k — still size so 1% risk ≈ $20–50 does not force illiquid junk.

---

## Quick reference — hold fit for all 25

| # | Strategy | Hold fit | Bucket |
|---|----------|:--------:|--------|
| 01 | Momentum Burst | 3 | Primary (borderline) |
| 02 | Episodic Pivot | 3 | Primary (borderline) |
| 03 | SEPA / VCP | 1 | **Deprioritized** |
| 04 | Weekly Breakout | 1 | **Deprioritized** |
| 05 | AVWAP Pullback | 3 | Primary |
| 06 | MACD 3-10-16 | 4 | Primary |
| 07 | Bull Flag | 2 | **Deprioritized** |
| 08 | Concentrated Conviction | 1 | **Deprioritized** |
| 09 | 9/21 EMA | 2 | **Deprioritized** |
| 10 | Contrarian | 3 | Primary (low conf.) |
| 11 | Gap and Go | 5 | Primary (low conf.) |
| 12 | S/R Bounce | 3 | Primary |
| 13 | Range BO / Donchian | 1 | **Deprioritized** |
| 14 | Pocket Pivot | 2 | **Deprioritized** |
| 15 | Inside Bar | 3 | Primary |
| 16 | SMA Structure | 1 | **Deprioritized** |
| 17 | Fibonacci | 3 | Primary |
| 18 | BB Squeeze | 3 | Primary |
| 19 | RS / residual mom | 1 | **Deprioritized** |
| 20 | Inst. Accumulation | 1 | **Deprioritized** |
| 21 | DCA ETFs | 1 | **Deprioritized** |
| 22 | TTM Squeeze | 3 | Primary |
| 23 | VWAP Bounce | 5 | Primary |
| 24 | Overnight Hold | 4 | Primary |
| 25 | Breakout-Retest | 2 | **Deprioritized** |

---

## Relation to general ranking

| File | Mandate | Best alpha-shaped pick |
|------|---------|------------------------|
| [`ranking.md`](ranking.md) | Any hold | #19 residual mom, #13 Donchian, #04 weekly BO |
| **This file** | Hours → **3 days max** | #24 overnight, #01 burst (≤3d), #15 / #23 patterns |

These rankings intentionally **conflict**. That is correct: the hold constraint changes which anomalies are even expressible.

---

*Educational ranking for research prioritization under a short-hold constraint. Lab history on this mold is mostly negative; treat high “sum” as relative fitness, not a green light to size up.*
