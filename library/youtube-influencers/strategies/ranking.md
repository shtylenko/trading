# Strategy Rankings — YouTube Influencer Collection

Scored July 2026 against the `trading` lab stack and a ~$2–5k long-only US stock/ETF account.

**Sources:** the 25 files in this directory; lab synthesis (`lab/validation/STRATEGY_SYNTHESIS.md`); xsec momentum backlog (`lab/strategies/xsec_momentum/`).

---

## Scoring scale (1–5, higher better)

| Factor | Higher means… |
|--------|----------------|
| **Expected return** | Realistic systematic edge / CAGR after costs (not influencer claims) |
| **# setups** | More valid opportunities per unit time |
| **Confidence** | Trust the edge exists — academic + your funnel + rule clarity |
| **Backtest fit** | Can test with `marketdata` + `lab` (daily/1‑min bars, PIT universes) |
| **$2–5k fit** | Economically workable at small size |

### PDT note

FINRA PDT minimum is treated as **~$2k** (not $25k). Same-day / multi-round-trip strategies are **not** penalized for PDT. Small-account scores still reflect **cost drag**, **risk unit** (~1% of $3k ≈ $30), and **book width** (top‑20/50 books need concentration).

### Expected return anchors (from your lab)

| Score band | Meaning for this project |
|------------|--------------------------|
| 5 | Strong durable alpha (rare as pure alpha in this list) |
| 4 | Real anomaly / high expectancy if executed well; residual momentum lives here |
| 3 | Modest / regime-dependent (typical good breakout systems) |
| 2 | Thin, cost-fragile, or mostly beta |
| 1 | Likely zero/negative for your mold (lab-killed or noise) |

Lab anchors: residual momentum (x03) ≈ **4**; same-day gap/ORB/mean-rev ≈ **1**; overnight standalone ≈ **2**.

---

## Full ranking table

| # | Strategy | Exp. return | # setups | Confidence | Backtest fit | $2–5k fit | **Sum** |
|---|----------|:-----------:|:--------:|:----------:|:------------:|:---------:|:-------:|
| 01 | Momentum Burst | 3 | 4 | 2 | 3 | 4 | **16** |
| 02 | Episodic Pivot | 4 | 1 | 2 | 2 | 4 | **13** |
| 03 | SEPA / VCP | 4 | 2 | 3 | 3 | 4 | **16** |
| 04 | Weekly Breakout Consolidation | 3 | 2 | 3 | 4 | 4 | **16** |
| 05 | Anchored VWAP Pullback | 3 | 3 | 2 | 2 | 4 | **14** |
| 06 | MACD 3-10-16 | 2 | 3 | 2 | 3 | 4 | **14** |
| 07 | Bull Flag Continuation | 3 | 3 | 2 | 2 | 4 | **14** |
| 08 | Concentrated High Conviction | 3 | 1 | 1 | 1 | 5 | **11** |
| 09 | 9/21 EMA Trend Following | 2 | 4 | 2 | 5 | 4 | **17** |
| 10 | Contrarian Swing | 1 | 3 | 1 | 4 | 3 | **12** |
| 11 | Gap and Go Momentum | 1 | 4 | 1 | 3 | 3 | **12** |
| 12 | Support / Resistance Bounce | 2 | 3 | 2 | 2 | 3 | **12** |
| 13 | Range Breakout + Volume | 3 | 3 | 4 | 5 | 3 | **18** |
| 14 | Pocket Pivot | 3 | 3 | 2 | 3 | 3 | **14** |
| 15 | Inside Bar Breakout | 2 | 4 | 2 | 5 | 4 | **17** |
| 16 | SMA Trend Structure | 3 | 3 | 3 | 5 | 4 | **18** |
| 17 | Fibonacci Pullback | 2 | 3 | 2 | 3 | 3 | **13** |
| 18 | Bollinger Band Squeeze | 2 | 3 | 2 | 5 | 4 | **16** |
| **19** | **RS Rotation (→ residual mom / x03)** | **4** | **3** | **5** | **5** | **3** | **20** |
| 20 | Institutional Accumulation | 2 | 3 | 2 | 3 | 3 | **13** |
| 21 | DCA Growth ETFs | 2 | 5 | 5 | 5 | 5 | **22** |
| 22 | TTM Squeeze Breakout | 2 | 3 | 2 | 4 | 4 | **15** |
| 23 | VWAP Bounce / Trend | 2 | 4 | 2 | 3 | 4 | **15** |
| 24 | Overnight Hold Swing | 2 | 4 | 2 | 4 | 4 | **16** |
| 25 | Breakout-Retest Swing | 3 | 2 | 3 | 3 | 4 | **15** |

**Sums are unweighted.** #21 wins the sum because it is reliable market beta, not trading alpha. For *edge search*, read columns separately.

---

## Sorted by sum (descending)

| Rank | # | Strategy | Sum |
|-----:|---|----------|----:|
| 1 | 21 | DCA Growth ETFs | 22 |
| 2 | 19 | RS Rotation → residual mom | 20 |
| 3 | 13 | Range Breakout + Volume | 18 |
| 3 | 16 | SMA Trend Structure | 18 |
| 5 | 09 | 9/21 EMA Trend | 17 |
| 5 | 15 | Inside Bar Breakout | 17 |
| 7 | 01 | Momentum Burst | 16 |
| 7 | 03 | SEPA / VCP | 16 |
| 7 | 04 | Weekly Breakout Consolidation | 16 |
| 7 | 18 | Bollinger Squeeze | 16 |
| 7 | 24 | Overnight Hold | 16 |
| 12 | 22 | TTM Squeeze | 15 |
| 12 | 23 | VWAP Bounce | 15 |
| 12 | 25 | Breakout-Retest | 15 |
| 15 | 05 | Anchored VWAP | 14 |
| 15 | 06 | MACD 3-10-16 | 14 |
| 15 | 07 | Bull Flag | 14 |
| 15 | 14 | Pocket Pivot | 14 |
| 19 | 02 | Episodic Pivot | 13 |
| 19 | 17 | Fibonacci Pullback | 13 |
| 19 | 20 | Institutional Accumulation | 13 |
| 22 | 10 | Contrarian Swing | 12 |
| 22 | 11 | Gap and Go | 12 |
| 22 | 12 | S/R Bounce | 12 |
| 25 | 08 | Concentrated High Conviction | 11 |

---

## Column leaders

| Factor | Best in list | Notes |
|--------|--------------|-------|
| Expected return | #02 EP, #03 SEPA, #19 RS/x03 | Only **#19** already OOS-validated in your lab |
| # setups | #21 DCA; then #01, #09, #15, #23, #24 | Frequency ≠ edge |
| Confidence | #19 (alpha); #21 (beta) | Sealed residual momentum; market return is certain |
| Backtest fit | #13, #16, #09, #15, #18, #19 | Pure OHLCV + rules |
| $2–5k fit | #21, #08; many swing systems at 4 | PDT no longer separates day vs swing |

---

## Recommended Top 3 (edge-first, not sum-first)

Calibrated to multi-day long-only mold, lab evidence, and systematizability.

| Rank | Strategy | ER | Setups | Conf. | Backtest | $2–5k | Sum | One-line |
|-----:|----------|:--:|:------:|:-----:|:--------:|:-----:|:---:|----------|
| 1 | **#19 RS → residual mom (x03)** | 4 | 3 | 5 | 5 | 3 | 20 | Only sealed-OOS edge; use **top 3–5** or sector ETFs at $2–5k, not top‑50 |
| 2 | **#13 Range / weekly Donchian** | 3 | 3 | 4 | 5 | 3 | 18 | Best systematic *new* multi-week system; concentrate book |
| 3 | **#04 Weekly breakout consolidation** | 3 | 2 | 3 | 4 | 4 | 16 | Best small-account *ops* of the three; codify “tight box” |

### Stack sketch

```text
Core alpha
  └─ #19 as x03 residual momentum (concentrated for $2–5k)

Challenger sleeve
  └─ #13 weekly Donchian (Stage-0 vs x03; expect high corr)

Optional timing layer
  └─ #04 weekly consolidation breakout on RS/x03 leaders
```

---

## Pareto tiers

| Tier | Strategies | Profile |
|------|------------|---------|
| **A — research + deploy** | #19, #13, #16, #04 | Momentum/trend, multi-day/weekly, codable |
| **B — small-account swing craft** | #03 (trend template), #25, #15, #09 | More setups or tighter R:R; lower confidence |
| **C — high expectancy if caught** | #02 EP | Great concentration fit; few setups; weak backtest; gap family failed sealed OOS |
| **D — foundation, not alpha** | #21 DCA | Wins small-account survival + confidence; not a strategy search |
| **Avoid as primary for you** | #10, #11; #24 as standalone | Mean-rev / gap-and-go killed or overnight below bar |

---

## $2–5k constraints (PDT-independent)

1. **Max 2–4 positions** typically. Rewrite 20–50 name books as top‑N = 3–5 or liquid ETFs.
2. **Risk ~0.5–1%** → ~$15–50 risk/trade. A 6% stop → position roughly **$250–$800**.
3. Prefer **liquid names / QQQ / sector ETFs** so fills and spreads do not dominate P&L.
4. **Fewer, better setups** often beat high frequency — costs and one bad stop matter more.
5. Day-trading is **allowed** at this size; still deprioritize pure same-day systems because of **lab results and costs**, not regulation.

---

## Why famous strategies are not Top 3

| Strategy | Why it drops for this project |
|----------|-------------------------------|
| #02 Episodic Pivot | Gap-drive family failed sealed 2025; catalyst quality hard to backtest |
| #01 Momentum Burst | ~H=5 horizon weak in lab; heavy situational discretion |
| #03 full VCP | Trend template is good; hand-drawn VCP is not predictable |
| #11 Gap & Go | Directly contradicted by retired **d** family |
| #24 Overnight | Premium real but closed as below bar standalone |
| #10 Contrarian | Long-only mean-rev killed (incl. ETF RSI-2 in 2022) |
| #21 DCA | Good core beta, not trading alpha |
| #08 Concentrated conviction | Path-dependent research process, not a backtestable signal |

---

## Factor definitions (detail)

### 1) Expected return

Realistic systematic edge after costs for a long-only liquid US book.

### 2) Number of setups

| Score | Rough cadence |
|------:|---------------|
| 5 | Continuous / every rebalance period |
| 4 | Many per week |
| 3 | Several per month |
| 2 | Few per month / highly selective |
| 1 | ~10–20 per year |

### 3) Perceived confidence

| Score | Meaning |
|------:|---------|
| 5 | Already OOS-validated here, or pure market return |
| 4 | Multi-decade systematic evidence + clean rules |
| 3 | Plausible; not fully proven on this stack |
| 2 | Mostly discretionary / thin evidence |
| 1 | Contradicted by project research |

### 4) Backtest fit with existing tools

| Score | Meaning |
|------:|---------|
| 5 | Pure OHLCV + simple rules; fits multiday mold |
| 4 | Same + light feature engineering |
| 3 | Weekly resample, volume rules, or patterns that can be simplified |
| 2 | Needs news/earnings/analysts or ambiguous anchors |
| 1 | Not a backtestable signal |

### 5) $2–5k fit

| Score | Meaning |
|------:|---------|
| 5 | Natural for tiny accounts (ETF DCA; 1–3 name conviction) |
| 4 | 2–5 swing/intraday names; fractionals OK; costs manageable |
| 3 | Works if concentrated (drop wide diversification) |
| 2 | Cost-sensitive or needs many names / awkward sizing |
| 1 | Broken at this size (reserved for structural failure; not used for PDT) |

---

*Educational ranking for research prioritization. Past performance and influencer track records do not guarantee future results.*
