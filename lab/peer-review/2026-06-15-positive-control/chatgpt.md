## Bottom line

**Yes, a few real equity effects partially fit your mold. But no, I would not trust any of them as a clean “known-good” validator control in the exact form you described.** The strongest classic equity anomalies mostly live in **overnight**, **multi-day**, or **long/short cross-sectional** space. Your framework — long-only, same-day, liquid names, 09:35 decision, stop/target/time exit — is aimed at a thin and noisy part of the market.

So my recommendation is:

**Use a synthetic positive control as the primary validator test, and use one or two real-world controls as secondary sanity checks.** If your synthetic edge fails, the validator is broken or underpowered. If a real-world control fails, that is informative but not decisive.

---

## Ranked real-world shortlist

| Rank | Candidate                                                                      | Fit grade                                          | My confidence as positive control                                                                                                                  |
| ---: | ------------------------------------------------------------------------------ | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 | **Overnight-to-intraday reversal: buy large overnight losers**                 | **Native / minor adaptation**                      | Best real-world fit, but published edge is mostly long-short/open-to-close; your 09:35 long-only version may be much weaker.                       |
|    2 | **Heston-Korajczyk-Sadka intraday periodicity: same time-of-day continuation** | **Minor adaptation**                               | Very well documented, individual-stock, intraday, leak-free. But the natural trade is time-slot-specific, not necessarily 09:35-to-close.          |
|    3 | **Market intraday momentum: first half-hour predicts last half-hour**          | **Forced unless you allow 10:00/15:30 ETF timing** | Strong evidence, replicated internationally, but it is mainly index/ETF timing, not top-10 individual-stock selection at 09:35.                    |
|    4 | **5-minute Opening Range Breakout on “stocks in play”**                        | **Native mechanically, weak evidentially**         | Fits your mold almost perfectly, but it is not yet a battle-tested academic anomaly. Good engineering test, not a “known-good” scientific control. |

---

# 1. Overnight-to-intraday reversal: buy large overnight losers

**Mechanism:** overnight price pressure / overreaction gets partially reversed during regular trading as liquidity providers and active traders absorb the imbalance. This connects to the broader short-term-reversal-as-liquidity-provision literature; Nagel argues short-term reversal returns proxy for liquidity-provision compensation and rise sharply when liquidity is scarce. ([SSRN][1])

### Rule in your mold

**At 09:35 ET**, for each stock in the liquid point-in-time universe:

```text
overnight_to_0935_return = price_09:35 / prior_close - 1
score = - overnight_to_0935_return / ATR20_percent
```

Admission filters:

```text
price > $10
20-day median dollar volume > $20M or your liquidity threshold
first 5-min dollar volume above stock’s own 30-day 09:30–09:35 median
spread proxy acceptable
score > 0, meaning stock is down from prior close
```

Ranking:

```text
rank descending by score
buy top 10
```

Entry:

```text
09:35 marketable limit, or VWAP/limit through 09:36
```

Stop:

```text
stop = min(opening_range_low - 0.05 * ATR20, entry - 0.50 * ATR20)
R = entry - stop
```

Target:

```text
target = entry + 1.0R
```

Time exit:

```text
exit all remaining shares at 15:55–15:59 ET
```

A cleaner validator version is even simpler: **no profit target, wide emergency stop, time-exit only.** Stops and targets can destroy a mean-reversion edge by cutting off exactly the trades that need time to recover.

### Evidence it is real

The “Overnight-Intraday Reversal Everywhere” paper documents buying assets with the lowest overnight returns and selling those with the highest overnight returns, reporting that this generates intraday Sharpe ratios “two to five times larger” than traditional reversal strategies, with robustness across asset classes and out-of-sample evidence. ([SSRN][2])

A related market-closure reversal paper explicitly defines a close-to-open signal followed by an open-to-close trading period, which is very close to your desired causal structure: the signal is known at/near the open and the payoff is realized intraday. ([cicfconf.org][3])

### Why it may fail in your pipeline

The published version is usually **long-short** and often **open-to-close**. Your version is **long-only**, enters after the first 5-minute bar, and uses stops/targets. That means you may miss part of the rebound and keep only the more dangerous leg: stocks down overnight can be down for good reasons.

Also, a lot of the impressive published effect sizes are gross or portfolio-spread effects. If your universe is Russell-1000-like and you use realistic slippage, the long-only top-10 version may become modest. That does not necessarily mean the pipeline is broken.

**Fit grade:** Native if you allow “buy overnight losers after the open.” Minor adaptation because the literature’s cleanest form is open-to-close and long-short.

---

# 2. HKS intraday periodicity: same time-of-day continuation

**Mechanism:** institutional flows and repeated intraday trading patterns create predictable continuation at the same intraday time intervals across days.

### Rule in your mold

Divide each day into half-hour buckets:

```text
b1 = 09:30–10:00
b2 = 10:00–10:30
...
b13 = 15:30–16:00
```

At 09:35, for each stock, compute:

```text
predicted_remaining_day_return =
    sum over future buckets b2..b13 of
    EWMA_20( stock residual return in bucket b over prior 20–40 sessions )
```

Use residual returns, not raw returns:

```text
residual_bucket_return =
    stock_bucket_return - universe_median_bucket_return
```

Ranking:

```text
score = predicted_remaining_day_return / predicted_intraday_vol
rank descending
buy top 10 positive scores
```

Entry:

```text
09:35 marketable limit
```

Stop:

```text
stop = entry - 0.50 * ATR20
R = entry - stop
```

Target:

```text
target = entry + 1.0R or 1.5R
```

Time exit:

```text
15:55 ET
```

The more faithful version is **bucket-trading**: only enter a stock at the start of the specific future half-hour bucket where it has a positive same-time historical signal, then exit at the end of that bucket. But your framework can approximate it by summing expected remaining buckets at 09:35.

### Evidence it is real

Heston, Korajczyk, and Sadka document a “striking pattern” of return continuation at half-hour intervals that are exact multiples of a trading day, lasting at least 40 trading days; they also report that volume/order imbalance/spread patterns do not explain the return pattern. ([IDEAS/RePEc][4])

There is post-publication international evidence. A 2025 Review of Quantitative Finance and Accounting paper examines HKS outside the US and finds the pattern in the UK and Brazil, while China is weaker/lacklustre, which is exactly the kind of partial replication you should prefer over a one-paper miracle. ([Springer Link][5])

### Why it may fail in your pipeline

This is probably the **most academically respectable individual-stock intraday candidate**, but the edge is naturally a **time-bucket edge**, not necessarily a 09:35-to-close top-10 daily swing. If your framework forces all trades at 09:35 and holds until close, you are blending predicted good buckets with noisy or bad buckets.

Also, this effect may be small in liquid names after costs. It is excellent for proving that your feature capture can detect intraday structure, but it may be too weak to pass a harsh Deflated-Sharpe gate over only 2022–2024.

**Fit grade:** Minor adaptation. Native only if you allow scheduled intraday bucket entries/exits.

---

# 3. Market intraday momentum: first half-hour predicts last half-hour

**Mechanism:** early-day information, institutional rebalancing, and late-day informed trading can align, causing the first half-hour market move to predict the last half-hour move.

### Rule in your mold

Strict version requires relaxing the decision time from 09:35 to 10:00.

At 10:00:

```text
market_signal = SPY_10:00 / prior_SPY_close - 1
```

Admission:

```text
market_signal > 0
SPY first-half-hour volume or realized volatility above median
sector ETF return positive for the stock’s sector
```

Ranking among individual stocks:

```text
score = beta_to_SPY * stock_09:30_to_10:00_return * sector_09:30_to_10:00_return
buy top 10 positive scores
```

Entry:

```text
preferred: 15:30 entry, because the documented effect is last-half-hour
forced version: 10:00 entry, but that is less faithful
```

Stop:

```text
stop = entry - 0.25 * ATR20
```

Target:

```text
target = entry + 1.0R
```

Time exit:

```text
15:55–15:59
```

### Evidence it is real

Gao, Han, Li, and Zhou document that the S&P 500 ETF’s first half-hour return, measured from the previous day’s close, predicts the last half-hour return; they report that the effect is statistically and economically significant, stronger on volatile/high-volume/recession/macro-news days, and present in other actively traded ETFs. ([IDEAS/RePEc][6])

International evidence also supports the pattern. Li et al. find significant first-half-hour to last-half-hour predictability in 12 of 16 developed markets, with formal out-of-sample forecasting evidence and annual alpha estimates for timing strategies. ([CentAUR][7])

A newer Management Science paper finds intraday market return predictability using high-frequency factor-zoo information and reports an annualized transaction-cost-adjusted SPY Sharpe of 1.37 versus 0.09 for passive intraday SPY over the out-of-sample period. ([Duke Economics][8])

### Why it may fail in your pipeline

This is **not naturally a top-10 individual-stock strategy**. It is mostly a **market/ETF timing effect**. Forcing it into individual names introduces extra idiosyncratic noise. Also, your 09:35 decision time is too early for the published first-half-hour signal.

**Fit grade:** Forced for your exact mold. Good if you allow a 10:00 decision and SPY/ETF trades; weaker if converted to individual stock selection.

---

# 4. 5-minute Opening Range Breakout on stocks in play

**Mechanism:** abnormal early volume plus directional opening pressure can reflect news/institutional imbalance that continues intraday.

### Rule in your mold

At 09:35:

```text
opening_range_high = high_09:30_to_09:35
opening_range_low  = low_09:30_to_09:35
first5_return = close_09:35 / open_09:30 - 1
relative_volume_5m = volume_09:30_to_09:35 / median_30d_volume_same_window
score = relative_volume_5m * max(first5_return, 0) / ATR20_percent
```

Admission:

```text
first5_return > 0
relative_volume_5m > 3
opening range width < 0.75 * ATR20
price > $10
liquid universe only
```

Entry:

```text
buy stop at opening_range_high + 1 tick after 09:35
```

Stop:

```text
opening_range_low
R = entry - stop
```

Target:

```text
2R target
```

Time exit:

```text
15:55 ET
```

### Evidence it is real

A 2024 SSRN paper studies 5-minute ORB strategies on more than 7,000 US stocks from 2016–2023 and claims that restricting to “stocks in play” materially improves results after transaction costs, with the top-20 stocks-in-play portfolio reporting Sharpe 2.81 and annualized alpha of 36%. ([SSRN][9])

### Why it may fail in your pipeline

This one fits your mechanics beautifully, but it is not as evidentially strong as HKS, Gao, or the reversal literature. It is newer, likely more implementation-sensitive, and could be vulnerable to data-mined filters, borrow/news effects, fill assumptions, and opening-spread/slippage problems.

**Fit grade:** Native mechanically, but weak as a “known-good” scientific positive control.

---

## Rejected or poor-fit “famous” edges

These are robust in broader equity literature but mostly do **not** fit your mold:

| Effect                                                   | Why it fails your mold                                                                                                                                    |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cross-sectional momentum**                             | Needs weeks/months and usually long-short.                                                                                                                |
| **Value / quality / profitability / investment factors** | Slow horizon; mostly overnight/close-to-close factor premia.                                                                                              |
| **Post-earnings-announcement drift**                     | Needs event/fundamental data and multi-day holding; daily bars alone are not enough.                                                                      |
| **Overnight premium / close-to-open premium**            | Directly violates no-overnight. Recent work also emphasizes that much of US equity gains have historically accrued overnight, not intraday. ([arXiv][10]) |
| **Classic short-term reversal**                          | More naturally close-to-close or multi-day, often long-short; intraday version is cost-sensitive and partly bid-ask bounce.                               |
| **End-of-day reversal**                                  | Natural decision time is late day, not 09:35.                                                                                                             |

This matters. McLean and Pontiff find that published cross-sectional predictors decay out-of-sample and especially post-publication, with average portfolio returns 26% lower out-of-sample and 58% lower post-publication. ([SSRN][11]) So even “real” anomalies are not guaranteed to survive your harsh modern, liquid, long-only, same-day constraints.

---

# Hard question 1: do any robustly proven equity edges truly fit?

**Yes, but only barely.**

The closest true fits are:

1. **Overnight-to-intraday reversal**
   This is the best match to “known by 09:35, trade intraday, close by close.” But the clean literature version is usually open-to-close and long-short.

2. **HKS same-time intraday continuation**
   This is the best match to “individual stocks, intraday bars, point-in-time, leak-free.” But its native expression is bucket-specific, not necessarily one 09:35 daily top-10 portfolio.

Everything else is either weaker evidence or requires more structural relaxation.

So if your validator kills all same-day long-only liquid-stock ideas, that may not mean it is broken. It may mean you are searching in a regime where **durable public alpha is thin, microstructure-heavy, and easily consumed by costs**.

---

# Hard question 2: should you use a synthetic positive control?

**Yes. I would make the synthetic control mandatory.**

A real-world control cannot give you exact ground truth. If overnight-intraday reversal fails, maybe your implementation is wrong, maybe the effect decayed, maybe 2022–2025 was hostile, maybe long-only destroys it, maybe stops hurt it, or maybe your DSR/PBO gates are too strict. You still do not know.

A synthetic positive control answers a cleaner question:

> “Given a leak-free signal of known strength injected into the data, can my validator recover it and pass it through the full pipeline?”

That is the exact question your current setup cannot answer.

## Synthetic control design I would use

Use a **dose-response synthetic alpha**, not a single injected edge.

### Step 1 — choose a leak-free signal visible at 09:35

Example:

```text
s_i,t = rank-normalized negative overnight_to_0935_return
```

or use a deterministic random signal:

```text
s_i,t = hash(stock_id, date, seed)
```

The first tests whether your pipeline can recover a realistic-looking feature. The second tests pure detection power without relying on real market structure.

### Step 2 — do not alter anything before 09:35

Keep prior daily bars, prior intraday history, and the first 5-minute bar untouched.

### Step 3 — inject drift only after 09:35

For selected stock-days, modify post-09:35 returns:

```text
r_synthetic_i,t,k = r_real_i,t,k + lambda * s_i,t * w_k
```

Where:

```text
k = post-09:35 5-minute bars
w_k sums to 1 across the remaining day
lambda = desired total injected edge
```

Run several doses:

```text
lambda = 0 R/day   null control
lambda = 0.03 R/trade
lambda = 0.05 R/trade
lambda = 0.10 R/trade
lambda = 0.20 R/trade
```

The pipeline should fail the null and increasingly pass as lambda rises. That gives you a **power curve**, not a vague pass/fail.

### Step 4 — preserve OHLC consistency

If you mutate raw bars, propagate adjusted close-to-close paths forward and adjust OHLC bars consistently. Do not just alter final trade PnL unless you only want to test the statistical gates. If you want to test the full feature/entry/stop/target engine, mutate the post-signal price path.

### Step 5 — inject into 2022–2025, but keep the process sealed

For validator testing, it is legitimate to inject into the sealed year because you are testing whether the system detects a known artificial world. But the injection recipe, seed, and lambda schedule must be frozen before the run.

### Step 6 — test both discovery and confirmation

You want three expected outcomes:

```text
null synthetic: should fail
moderate synthetic: should pass search and walk-forward
sealed 2025 synthetic: should pass if same lambda persists
```

If lambda = 0.10R/trade fails, your validator is probably too conservative or your implementation is losing the signal. If lambda = 0.03R/trade fails, that may simply mean your sample is underpowered.

This ties directly to why DSR/PBO are useful but dangerous if treated as magic. PBO/CSCV was designed as a model-free way to estimate overfitting risk in investment simulations, and DSR corrects Sharpe for selection bias, multiple testing, and non-normal returns.  ([SSRN][12]) But neither can create statistical power from a short, noisy sample.

---

## What I would actually run

Run these in this order:

1. **Synthetic null and synthetic dose-response control**
   This tests the validator.

2. **Overnight-to-intraday reversal, long-only loser leg**
   This tests whether a plausible real intraday liquidity edge survives your implementation.

3. **HKS same-time intraday periodicity**
   This tests whether the feature pipeline can detect subtle intraday structure.

4. **ORB stocks-in-play**
   This tests whether your execution engine handles a mechanically natural day-trading setup, but I would not treat it as a scientific known-good control.

The most important interpretation rule:

**If synthetic passes but real-world controls fail, your pipeline may be fine and the strategy space may just be thin. If synthetic fails, stop testing real strategies and debug the validator.**

[1]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1988706 "Evaporating Liquidity by Stefan Nagel :: SSRN"
[2]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2730304 "Overnight-Intraday Reversal Everywhere by Chun Liu, Yang Liu, Tianyu Wang, Guofu Zhou, Yingzi Zhu :: SSRN"
[3]: https://www.cicfconf.org/sites/default/files/paper_357.pdf?utm_source=chatgpt.com "Market Closure and Short-Term Reversal∗"
[4]: https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1369-1407.html "Intraday Patterns in the Cross‐section of Stock Returns"
[5]: https://link.springer.com/article/10.1007/s11156-024-01319-8 "Investor clientele and intraday patterns in the cross section of stock returns | Review of Quantitative Finance and Accounting | Springer Nature Link"
[6]: https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html "Market intraday momentum"
[7]: https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf "Intraday Time Series Momentum: International Evidence "
[8]: https://public.econ.duke.edu/~boller/Papers/MS_2025.pdf "Intraday Market Return Predictability Culled from the Factor Zoo"
[9]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284 "A Profitable Day Trading Strategy For The U.S. Equity Market by Carlo Zarattini, Andrea Barbon, Andrew Aziz :: SSRN"
[10]: https://arxiv.org/html/2507.04481v1?utm_source=chatgpt.com "Does Overnight News Explain Overnight Returns? †"
[11]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623 "Does Academic Research Destroy Stock Return Predictability? by R. David McLean, Jeffrey  Pontiff :: SSRN"
[12]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality by David H. Bailey, Marcos Lopez de Prado :: SSRN"
    