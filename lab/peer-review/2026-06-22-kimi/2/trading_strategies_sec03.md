## 3. Core Strategy Toolkit: Mean Reversion

Where momentum strategies seek to harness sustained directional moves, mean reversion strategies profit from the tendency of prices to snap back after short-term dislocations. In long-only equity trading, this principle translates into a straightforward rule: buy temporary weakness within structurally sound uptrends. The research identifies mean reversion as the dominant risk-adjusted approach for long-only equity, producing Sharpe ratios that consistently exceed those of trend-following and breakout alternatives [^403^][^214^]. The reason is structural — equity indices possess an upward drift, which means dips are more likely to recover than extend, provided the broader trend remains intact.

The contrast with momentum is instructive. Where dual momentum strategies posted 15.8-17.4% CAGR in Chapter 2 with moderate but sustained drawdowns, mean reversion systems typically achieve comparable or lower absolute returns with dramatically smaller drawdowns and much lower market exposure. The IBS + Band strategy's 2.11 Sharpe ratio, for instance, exceeds any momentum system reviewed in the preceding chapter [^358^]. For traders who prioritize capital efficiency and psychological durability — the ability to stay with a strategy through losing periods — mean reversion offers compelling advantages.

This chapter examines four categories of mean reversion systems: the RSI(2) method pioneered by Larry Connors, Internal Bar Strength (IBS) strategies, the Mean Reversion Curve portfolio construction technique, and supplementary approaches including Bollinger %B and stochastic oscillator mean reversion. Each system is presented with exact trading rules, backtested performance data, and an honest assessment of edge decay in the modern HFT-dominated landscape.

### 3.1 RSI(2) Mean Reversion: The Connors Framework

#### 3.1.1 Exact Trading Rules

The RSI(2) strategy, introduced by Larry Connors and Cesar Alvarez in *Short Term Trading Strategies That Work* (2008), exploits the extreme sensitivity of a 2-period Relative Strength Index to short-term price movements [^205^][^384^]. The original rules are precise:

**Entry:** Price must close above the 200-day simple moving average (trend filter), and RSI(2) must drop below 5. Buy at the close of the signal day. The 200-day MA filter ensures the strategy only takes trades in established uptrends, avoiding the catastrophic losses that occur when mean reversion is attempted during secular bear markets.

**Exit:** RSI(2) rises above 65. Sell at the close. The exit threshold at 65 — rather than the traditional 70 — captures profits earlier and avoids giving back gains during marginal recoveries.

**Stop Loss:** None in the original system. The 200-day moving average filter provides the sole structural protection [^51^].

A relaxed entry variant uses RSI(2) < 10 instead of < 5, generating more signals at the cost of a modest reduction in per-trade expectancy. The 3-day consecutive variant — requiring RSI(2) < 10 for three consecutive days before entry — filters for genuine capitulation moments and produces the highest win rates (~81%) but at the cost of dramatically fewer trades [^308^]. An alternative exit uses the 5-day moving average crossover instead of the RSI(2) > 65 threshold, which produces a slightly higher win rate but similar overall returns [^45^]. Traders implementing this system should test all three entry variants (5, 10, and consecutive-10) on their target instruments to identify which best balances signal frequency with per-trade expectancy given their capital constraints.

#### 3.1.2 Backtested Performance

The QuantifiedStrategies.com backtest of the original Connors RSI(2) system on QQQ from 1999-2025, including 0.03% commissions and slippage, produced the following results [^403^]:

| Metric | QQQ (1999-2025) | SPY (1993-2025) |
|:---|:---:|:---:|
| Number of Trades | 321 | ~450 |
| Average Gain per Trade | 0.9% | 0.95% |
| Win Rate | 71% | ~76% |
| Profit Factor | 2.1 | ~2.0 |
| CAGR | 10.7% | 6.8% (w/ filter) / 9% (w/o) |
| Exposure (% Time in Market) | 18% | 18% / 28% |
| Max Drawdown | 23% | 31% / 34% |
| Risk-Adjusted Return (CAGR/Exposure) | 58% | — |
| Average Hold Time | 3-5 days | 3-5 days |

The QQQ results are particularly instructive. A 10.7% CAGR with only 18% market exposure implies a time-adjusted return of approximately 58% — a figure that illustrates the extraordinary capital efficiency of the approach [^403^]. The 23% maximum drawdown stands in stark contrast to QQQ's 82% buy-and-hold drawdown during the same period. However, the strategy's absolute CAGR of 10.7% falls below the user's 3% monthly target, underscoring a critical constraint: no single-instrument mean reversion strategy produces sufficient standalone returns. The SPY results reinforce this point — even without the trend filter, the 9% CAGR barely clears 0.7% monthly. This is not a flaw in the strategy but an inherent property of highly selective mean reversion systems: they generate excellent risk-adjusted returns but require either leverage, multi-instrument deployment, or combination with other strategies to reach aggressive absolute return targets. The Cumulative RSI enhancement introduced by Connors addresses this partially — using a 2-day sum of RSI(2) below 10 instead of a single reading below 5 produced 1.0% expected return per trade (vs. 0.6% for vanilla) and a Sharpe ratio of 1.18, though maximum drawdown increased to 37% [^343^][^411^].

#### 3.1.3 The Stop Loss Paradox

Connors and Alvarez's research contains a finding that contradicts conventional risk management wisdom: stop losses hurt mean reversion performance. "The overwhelming evidence from these tests shows that stop-losses, in general, hurt system performance" [^384^]. Independent backtesting on r/algotrading confirmed this result — adding any stop loss made the strategy worse on every metric measured [^45^][^212^].

The mechanism is straightforward. Mean reversion trades require some initial price movement against the position — the very dip that creates the oversold signal often extends briefly before snapping back. A fixed stop loss exits precisely at the point of maximum pain, just before the reversal. The 200-day trend filter serves as the ultimate circuit breaker: if price falls below the long-term average, the strategy simply stops taking new entries, avoiding the worst of bear market drawdowns without the precision-timing risk of per-trade stops.

#### 3.1.4 Trend Filter Impact

The 200-day MA filter is the single most important rule in the Connors framework. Data from SPY backtests illustrates the tradeoff clearly: without the filter, the strategy returns 9% CAGR but suffers a 34% maximum drawdown. With the filter, CAGR drops to 6.8% but maximum drawdown falls to 31% [^51^]. The filter eliminates approximately 35% of potential trades — mostly those occurring during market corrections — and while this reduces absolute returns, it dramatically improves the risk-adjusted profile. For traders prioritizing capital preservation, the filtered version is non-negotiable.

### 3.2 IBS (Internal Bar Strength) Strategies

#### 3.2.1 Formula and Interpretation

Internal Bar Strength ($IBS$) compresses an entire trading day's price action into a single normalized value:

$$IBS = \frac{Close - Low}{High - Low}$$

The indicator ranges from 0 (close at the low of the day) to 1 (close at the high). Values below 0.2 indicate intraday weakness — the market sold off but failed to close at the absolute low, suggesting exhaustion. Values above 0.8 indicate intraday strength. Unlike multi-period oscillators, IBS captures only the current bar's positioning, making it exceptionally responsive [^214^]. The indicator's elegance lies in its parsimony: a single calculation that encodes both volatility information (through the $High - Low$ denominator) and directional positioning (through the $Close - Low$ numerator). This dual capture explains why IBS often outperforms more complex multi-indicator systems — it extracts maximum information from minimal inputs, reducing overfitting risk. Research across 919 SPY trades confirmed that the simplest IBS implementation (single threshold entry/exit) produced 68% win rates and positive expectancy, establishing a robust baseline before any enhancement [^214^].

#### 3.2.2 Single-Indicator IBS Performance

The simplest IBS strategy buys when IBS < 0.2 and sells when IBS > 0.8, with no trend filter. On SPY from 1993 to present, this produced 919 trades with a 68% win rate, 0.41% average gain per trade, and a 12.5% CAGR — outperforming buy-and-hold's 9.9% [^214^]. On QQQ, the same rules generated 742 trades with a 0.56% average gain and 16.6% CAGR versus 9% for buy-and-hold [^214^].

A modified version using IBS as the only indicator with refined thresholds produced the strongest single-indicator results: 74% win rate, 15.3% CAGR, 22% maximum drawdown, and a Sharpe ratio of 1.7 on SPY [^214^].

#### 3.2.3 IBS + Lower Band: The 2.11 Sharpe Strategy

The highest-Sharpe mean reversion strategy identified in this research combines IBS with a dynamic volatility band. The exact rules [^358^]:

1. Compute the 25-day rolling average of $(High - Low)$ as a volatility measure
2. Compute $IBS = (Close - Low) / (High - Low)$
3. Compute lower band = 10-day rolling high minus $2.5 \times$ the 25-day rolling mean of $(High - Low)$
4. **Entry:** Go long when QQQ closes under the lower band AND $IBS < 0.3$
5. **Exit:** Close when QQQ close exceeds the previous day's high
6. **Dynamic Stop:** Close when price falls below the 300-day SMA

The Quantitativo backtest (1999-2024, 25 years) produced the following results [^358^][^369^]:

| Metric | IBS + Lower Band (QQQ) | Buy-and-Hold QQQ |
|:---|:---:|:---:|
| Number of Trades | 414 | — |
| Average Gain per Trade | 0.79% | — |
| Win Rate | 69% | — |
| Profit Factor | 1.98 | — |
| **Sharpe Ratio** | **2.11** | ~0.65 |
| **Annual Return** | **13.0%** | 9.2% |
| **Max Drawdown** | **20.3%** | 83% |
| Max Drawdown Duration | < 1 year | 535 days |
| Trades per Year | ~16 | — |

The robustness of this strategy is noteworthy. A parameter sweep across 1,875 variations produced a mean Sharpe of 1.95-1.99 and mean annual return of 11.8%, confirming the result is not an overfit artifact [^369^]. However, a material caveat exists: the strategy underperformed its benchmark in 7 of the last 10 years, suggesting the edge has compressed significantly in recent market conditions [^358^].

#### 3.2.4 IBS + Second Indicator: Highest Absolute Returns

Combining IBS with a second oversold indicator (exact rules are proprietary) produced the highest absolute returns among IBS variants. On QQQ, this combination generated 232 trades with a 75% win rate, 1.33% average gain per trade, 2.9 profit factor, and 16.6% CAGR with only a 19.5% maximum drawdown [^214^]. On SPY, the same approach produced 278 trades with 0.8% average gain and 78% win rate. The two-indicator filter reduces trade frequency by roughly 30% compared to single-indicator IBS but increases per-trade expectancy by approximately 60% — a favorable exchange for traders with sufficient capital to tolerate lower turnover.

### 3.3 The Mean Reversion Curve Portfolio

#### 3.3.1 Concept and Construction

The Mean Reversion Curve concept, developed by PJ Sutherland and published via Quantitativo [^62^], addresses a fundamental problem in systematic trading: no single parameter set works optimally across all market regimes. Instead of searching for the "best" RSI(2) threshold, the approach runs six parallel portfolios — each using a different RSI(2) entry threshold (5, 10, 15, 20, 25, and 30) — and dynamically reallocates capital among them based on recent Sharpe ratio performance.

All six portfolios share identical exit rules (close > 5-day SMA) and trend filters (price > 200-day SMA). The optimization algorithm looks back 504 trading days (approximately 2 years) and finds the capital allocation across the six parameter sets that would have maximized the Sharpe ratio. This allocation is held fixed for one month, then rebalanced. Monthly rebalancing was selected over weekly to avoid weekend gap risk [^62^].

The portfolio construction resembles Ray Dalio's All-Weather approach applied to parameter space rather than asset classes. In practice, the optimizer selects a single best strategy 43% of the time and allocates to two strategies 40% of the time — genuine diversification across parameter sets occurs in fewer than 20% of periods [^62^].

#### 3.3.2 Performance: Diversified vs. Concentrated

The Quantitativo backtest (2010-2024) produced the following metrics [^62^]:

| Metric | Diversified (Max 10 Positions) | Concentrated (Max 4 Positions) | Benchmark (QQQ) |
|:---|:---:|:---:|:---:|
| CAGR | 25.7% | **34%** | 17.6% |
| Sharpe Ratio | 1.14 | 1.23 | ~0.85 |
| Max Drawdown | 28% | 35% | 36% |
| Expected Return per Trade | +0.40% | +0.55% | — |
| Win Rate | 64.8% | 64.8% | — |
| Trades per Week | ~5 | ~5 | — |
| Positive Months | 66% | 66% | — |
| Best Month | +20.1% | +24.5% | — |
| Worst Month | -15.2% | -18.8% | — |
| Longest Winning Streak | 9 months | 9 months | — |
| Longest Losing Streak | 4 months | 5 months | — |
| Down Years | 2 | 2 | 3 |

The concentrated version's 34% CAGR represents a meaningful improvement over the diversified approach, but the 35% maximum drawdown — approaching the benchmark's 36% — erodes much of the risk-adjusted advantage. The Sharpe ratio improvement from 1.14 to 1.23 is modest, suggesting that while concentration boosts raw returns, it does so at nearly proportional risk increase.

#### 3.3.3 Why Concentration Works

The outperformance of the concentrated portfolio stems from a simple arithmetic truth: when a mean reversion signal fires, it identifies a subset of stocks that are temporarily dislocated. A portfolio cap of 4 positions forces investment only in the highest-conviction setups, while a cap of 10 dilutes capital across marginal signals. The individual RSI(2) threshold results since 2010 validate this intuition — thresholds of 15 and 20 produced 25-28% annual returns, while the most conservative (5) and most aggressive (30) thresholds lagged at 15-18% and 18-22% respectively [^62^]. The optimal threshold shifts over time, which is precisely why the multi-parameter portfolio with dynamic rebalancing outperforms any static choice.

#### 3.3.4 Multi-Instrument Implementation

The Mean Reversion Curve approach is designed to run simultaneously across multiple uncorrelated instruments. The research recommends applying the same six-portfolio framework to QQQ (Nasdaq-100), IWM (Russell 2000), EEM (emerging markets), and sector ETFs. A cross-geographic implementation of a similar IBS+Band strategy across US, Canadian, and Australian markets produced 23.1% annual returns with a Sharpe of 1.76 and only 0.346 market beta, driven by near-zero inter-market correlations (US-Canada: 0.08, Canada-Australia: 0.10) [^370^]. The Fama-French alpha of 15% annualized ($t=5.70$, $p<0.001$) confirms that these returns are not merely compensation for market risk [^370^].

### 3.4 Other Mean Reversion Approaches

#### 3.4.1 Bollinger %B Mean Reversion

Larry Connors' %B strategy, published in *High Probability ETF Trading* (2009), uses a Bollinger Band position indicator: $%B = (Price - Lower Band) / (Upper Band - Lower Band)$. The rules require %B below 0.2 for three consecutive days (with price above the 200-day MA) for entry, and exit when %B closes above 0.8. A portfolio of 25 ETFs from 2000-2020 produced 677 trades with a 75% win rate, 0.76% average gain, and 4.84% CAGR using 5-day Bollinger Bands, or 8.2% CAGR using 10-day bands [^35^][^48^]. The low absolute returns reflect the strategy's extreme selectivity — only 56 trades over 20 years when restricted to SPY/QQQ alone. Third-party backtests on post-2008 data show degraded performance, with win rates falling from 70-82% to 60-70%, confirming edge decay since publication [^48^].

#### 3.4.2 Stochastic Oscillator Mean Reversion

A 5-day Stochastic %K combined with 5-day RSI (both below 20 for entry, exit above 50) produced 556 trades on SPY from 1993-present, averaging 0.57% gain per trade with a profit factor of 2.2 [^353^]. The Stochastic variant outperformed its RSI-only counterpart (7.4% CAGR vs. 3.6%), confirming that the Stochastic's range-based measurement captures different information than RSI's velocity-based calculation. Notably, the St oscillator is effective on stock indices but "disappointing on many commodities" — a market-specificity that traders crossing asset classes must respect [^353^].

#### 3.4.3 Opening Gap Fade

The gap fade strategy exploits overnight dislocations by buying SPY when it gaps down between -0.15% and -0.6%, targeting 75% of the gap size with a same-day close exit. An additional filter — yesterday's close in the lower 25% of the day's range — improves the setup. QuantifiedStrategies.com documented 110 fills from January 2010 to August 2012 with a 89% win rate and 0.19% average gain per fill [^31^].

Despite the astronomical win rate, this strategy carries severe practical limitations. The 0.19% average gain leaves minimal cushion after transaction costs — round-trip commissions and slippage consume 20-80% of the profit. The author explicitly warns that "the window of opportunity is getting smaller with the increased computer power that arbs away the anomalies" [^31^]. Intraday monitoring requirements and HFT competition make this approach unsuitable for systematic long-only trading at the retail level.

### 3.5 Mean Reversion Edge Decay

#### 3.5.1 The Post-2010 Compression

Mean reversion edges have weakened materially since 2010. Quantitativo's analysis found that mean reversion strategies outperformed the S&P 500 every single year from 2000 through 2013, but underperformed in selected years (2014, 2016, 2018) thereafter [^343^]. The IBS+Band strategy with its celebrated 2.11 Sharpe ratio underperformed its benchmark in 7 of the last 10 years [^358^]. Alvarez Quant Trading offered a more measured assessment: "Mean reversion on the index has changed little since the mid-2000s, although year-to-year performance has its ups and downs" [^413^]. The consensus estimate from cross-verified sources: edges have compressed by 30-50% from their pre-2010 levels.

![Mean Reversion Performance by Decade](trading_strategies_chart2.png)

*Figure 3.1: Mean reversion strategy CAGR by decade versus QQQ buy-and-hold. The spread between mean reversion returns and passive benchmarks narrows significantly in the 2020s as HFT competition intensifies. Sources: QuantifiedStrategies.com, Quantitativo backtests (1993-2024).*

The chart illustrates the structural shift. In the 2000s — a decade defined by two major bear markets — IBS+Band on QQQ generated approximately 16.2% annual returns while the index lost 2.5% annually. By the 2020s, the same strategy produced roughly 8.5% annually against QQQ's 15.2% buy-and-hold return. Mean reversion still delivers positive absolute returns, but the alpha over passive investing has compressed dramatically.

#### 3.5.2 The Retail Advantage Zone

Despite compression, the 1-5 day holding period remains the retail trader's structural advantage. High-frequency trading firms operate on microsecond to minute timeframes, exploiting the same overreaction dynamics but at speeds no retail platform can match. Institutional money managers, constrained by liquidity requirements and benchmark tracking, cannot effectively deploy capital on multi-day horizons with small position sizes. The gap between these two competitors — too long for HFTs, too short for institutions — defines the exploitable window [^343^][^62^].

The Connors RSI(2) system's 3-5 day average hold time and the IBS+Band strategy's similar horizon sit squarely in this advantage zone. Both strategies use end-of-day signals, eliminating the need for intraday monitoring while remaining outside the HFT competition perimeter.

#### 3.5.3 Why Edges Persist

The persistence of mean reversion edges, even in degraded form, has roots in human psychology rather than informational inefficiency. Behavioral finance research documents two complementary biases: overreaction to short-term news (causing the initial price dislocation) and herding behavior (amplifying the overshoot). These biases are not arbitrageable by algorithms because they reflect genuine human emotional responses to uncertainty — fear during selloffs and greed during rallies [^384^].

Algorithmic trading can exploit the mechanical consequences of these biases (price dislocations) but cannot eliminate the biases themselves. As long as human decision-makers control capital allocation, short-term overreactions will create snapback opportunities. The HFT impact has been to accelerate the resolution — edges that once played out over 3-5 days may now resolve in 1-3 days — but the underlying phenomenon remains [^343^].

The composition of edge decay deserves closer examination. Not all mean reversion strategies have degraded equally. The simplest, most transparent systems — RSI(2) and basic IBS — have decayed moderately because their edges were never large to begin with and their rules are too well-known to attract arbitrage capital. The more complex, parameterized systems like the IBS + Band approach have decayed more severely because sophisticated quantitative funds can reverse-engineer and trade around the same signals. Paradoxically, this means the Connors RSI(2) system, published in 2008 and widely disseminated, may retain more live edge than ostensibly "secret" quantitative systems — precisely because its simplicity limits the capital that can exploit it before the edge disappears [^51^].

For retail traders, the practical implication is clear: mean reversion strategies remain viable but require realistic expectations. A strategy backtested at 25% CAGR may deliver 12-17% in live trading after accounting for the 30-50% edge decay, transaction costs, and strategy degradation documented in Chapter 2 [^279^]. The Mean Reversion Curve Portfolio's diversified 25.7% CAGR, discounted by 40% for live conditions, yields an estimated 15.4% annually — approximately 1.2-1.3% monthly, within the realistic return framework established in the preceding chapters [^62^]. Combining mean reversion with the momentum systems from Chapter 2, exploiting their historically negative correlation of approximately -0.35, offers the most reliable path to the 1.5-2.5% monthly target [^146^].

The final consideration is implementation infrastructure. All strategies in this chapter can be executed with end-of-day orders using daily chart data, requiring no intraday monitoring. Position holding periods of 1-5 days minimize overnight risk while remaining outside the HFT competition zone. Tax-advantaged accounts (IRA, 401k) are strongly recommended given the high turnover — short-term capital gains at ordinary income rates would consume 25-40% of profits for traders in higher tax brackets. A trader running the IBS + Band strategy on QQQ with $25,000 in a Roth IRA, capturing the estimated live 8-10% annual return, would compound to approximately $54,000 over a decade — a meaningful result from a single, systematically executed strategy requiring fewer than 20 trades per year.
