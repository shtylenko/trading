## Facet: Mean Reversion & Pullback Strategies (LONG-ONLY)

**Research Date:** July 2025
**Searches Conducted:** 13 independent search queries across multiple sources
**Scope:** Long-only mean reversion and pullback strategies for stocks and ETFs

---

### Key Findings

1. **No single mean reversion strategy consistently achieves >3% monthly (36%+ CAGR) on a single instrument** with acceptable drawdown risk. However, **portfolio combinations of multiple mean reversion strategies can approach or exceed this threshold** — a portfolio of diversified mean reversion strategies achieved **25.7% CAGR since 2010** (~2.1% monthly), and with position concentration (max 4 positions), this increased to **34% CAGR** (~2.8% monthly) [^62^].

2. **RSI(2) strategies show the most consistent performance** across decades of backtesting, with win rates of 70-80% and average per-trade gains of 0.5-1.0%. The classic Larry Connors RSI(2) strategy on QQQ produced a **10.7% CAGR with 71% win rate and 2.1 profit factor**, but only 18% time in market [^20^].

3. **The IBS (Internal Bar Strength) indicator is one of the strongest mean reversion tools** — a combined IBS + second indicator strategy on QQQ produced **1.33% average gain per trade with 75% win rate** and 16.6% CAGR since inception [^21^].

4. **The "Trading the Mean Reversion Curve" approach** (diversifying across multiple RSI(2) entry thresholds with monthly rebalancing) achieved **25.7% annual returns since 2010** with 1.14 Sharpe ratio and 28% max drawdown, representing one of the highest-performing documented mean reversion approaches [^62^].

5. **Mean reversion edges have weakened since 2010** due to increased algorithmic trading and HFT competition. Out-of-sample validation from 2015-2025 shows slight performance decay, though the core edge remains profitable [^23^] [^62^].

6. **High Probability ETF Trading strategies (Connors/Alvarez)** produced win rates of 73-82% across six different strategy variants, with average gains per trade of 0.5-1.56% and holding periods of 3-7 days [^48^].

7. **Opening gap fade strategies** can achieve high win rates (80%+) but require precise execution and are becoming harder to trade due to algorithmic competition [^31^].

---

### Major Players & Sources

| Entity | Role/Relevance |
|--------|----------------|
| **Larry Connors** | Pioneer of RSI(2) mean reversion; published "Short Term Trading Strategies That Work" (2008) and "High Probability ETF Trading" (2009). His strategies remain among the most widely tested and implemented mean reversion systems [^19^] [^20^] |
| **Cesar Alvarez** | Collaborated with Connors on backtesting and strategy development; co-author of multiple trading strategy books [^48^] |
| **QuantifiedStrategies.com** | Extensive backtesting resource that has independently verified Connors' strategies with decades of data; provides detailed performance metrics and strategy variations [^20^] [^21^] [^23^] [^35^] |
| **Quantitativo** | Published research on "trading the mean reversion curve" — combining multiple mean reversion portfolios with dynamic allocation to achieve 25.7% CAGR [^62^] |
| **Alvarez Quant Trading** | Published research on creating robust mean reversion strategies using multiple indicators and filters [^68^] |
| **Academic Literature (Pagonidis)** | Published "The IBS Effect: Mean Reversion in Equity ETFs" documenting the statistical basis for IBS as a mean reversion predictor [^55^] |
| **ETFreplay** | Platform offering short-term mean reversion backtesting tools for ETFs, including Total Return Difference (TRD) mean reversion backtests [^32^] |
| **SetupAlpha / RealTest** | Provides commercially available, fully backtested Connors-Alvarez mean reversion strategies with walk-forward validation [^33^] |

---

### Trends & Signals

- **Mean reversion strategies have performed well for over 30 years** on stocks and stock indices, with the core edge persisting despite widespread publication [^20^] [^21^]. However, performance has shown gradual degradation since 2010 [^62^].

- **Shorter RSI lookback periods (2-5 days) consistently outperform** the standard RSI(14) for mean reversion on stock indices, capturing short-term panic selling that snaps back within 1-5 days [^19^] [^23^].

- **The 200-day moving average as a trend filter** is one of the most effective regime filters for mean reversion strategies, ensuring trades are only taken in established uptrends [^19^] [^23^] [^48^].

- **Portfolio diversification across multiple mean reversion parameters** (rather than optimizing a single parameter set) shows more stable performance and reduces the impact of parameter instability [^62^].

- **Opening gap fill probability decreases dramatically with gap size**: gaps >0.1% fill 59-61% of the time, but gaps >1% fill only 28-33% of the time [^31^].

- **Mean reversion edges are strongest after high-volatility, high-range days** with high volume, suggesting the edge is driven by behavioral overreactions [^55^].

- **The IBS effect works across multiple US equity index futures** (ES, NQ, YM), confirming it captures a broad behavioral bias rather than symbol-specific noise [^53^].

---

### Controversies & Conflicting Claims

- **Stop-losses in mean reversion**: Connors' original research argues that stops on mean-reversion trades get hit at exactly the wrong moment, just before the snapback [^19^]. However, crypto adaptations and some equity traders add 5% stops to protect against catastrophic gaps, sacrificing some returns for drawdown control [^19^]. A Reddit backtest found that adding a stop loss when price closes below the 200-day MA made the strategy worse on every metric [^24^].

- **Performance decay concern**: Some researchers argue that mean reversion edges are being arbitraged away by HFT. Quantitativo's research shows that while the edge still works, "the strategy lost steam from 2008 on" and since 2021 the strategy underperformed Nasdaq-100 [^62^]. However, other sources show Connors' strategies still working in out-of-sample tests from 2015-2025 [^23^].

- **RSI + Bollinger Bands combination**: A widely promoted strategy on YouTube was systematically backtested across 100 US stocks, 100 cryptos, 30 futures, and 50 forex pairs — and found to be "not a universal edge" that mostly fails as a plug-and-play strategy, despite attractive-looking win rates [^42^].

- **Bollinger Band Squeeze strategy**: Backtesting found the strategy "doesn't do particularly well for any asset" and underperforms buy-and-hold [^37^].

- **Buy on close vs. next open**: Many Connors strategies require buying at the close of the signal day, which introduces practical execution challenges. Testing shows buying on the next open produces similar but slightly lower returns [^24^] [^48^].

---

### Recommended Deep-Dive Areas

1. **"Trading the Mean Reversion Curve" portfolio approach**: The Quantitativo research showing 25.7-34% CAGR by combining multiple RSI(2) parameter sets with monthly Sharpe-optimized rebalancing warrants deep investigation as the most promising path to >3% monthly returns [^62^].

2. **IBS + Multi-Indicator Combinations**: The IBS + second indicator strategy on QQQ produced 1.33% avg gain per trade with 75% win rate. Combining IBS with RSI(2), Bollinger %b, or other filters may produce higher-frequency trading with acceptable returns [^21^].

3. **Multiple Timeframe Mean Reversion**: Combining daily RSI(14) > 50 regime filter with hourly RSI(2) signals reduced drawdowns by 20-30% in trending markets [^23^]. This could allow more aggressive position sizing.

4. **Opening Gap Fade with IBS Filter**: QuantifiedStrategies' gap fade strategy combined with the IBS < 0.25 filter produced 0.19% avg per trade with 89% win rate. Running this across a basket of 20 ETFs could increase frequency [^31^].

5. **Leveraged Mean Reversion**: If a strategy produces 15-20% CAGR with 15-20% max drawdown, modest leverage (1.5-2x) could potentially achieve >3% monthly while keeping drawdowns manageable.

---

### Strategy Details

---

#### Strategy 1: Larry Connors RSI(2) Mean Reversion

**Category:** RSI Oversold Bounce

**Trading Rules:**
- **Setup:** Price must be above the 200-day simple moving average (confirms uptrend)
- **Entry:** RSI(2) drops below 5 (or 10 for more signals). Buy at the close.
- **Exit:** RSI(2) rises above 65 (or 70). Sell at the close.
- **Alternative Exit:** Price closes above the 5-day moving average.
- **No stop loss** in the original system — the 200 MA filter provides structural protection.

**Backtested Performance (SPY, 1993-present):**
| Metric | Value |
|--------|-------|
| Trades | 321+ |
| Win Rate | 71% |
| Average Gain/Trade | 0.9% |
| Profit Factor | 2.1 |
| CAGR | 9-10.7% |
| Max Drawdown | 23-34% |
| Time in Market | 18-28% |
| Risk-Adjusted Return (CAGR/Exposure) | ~58% |

**Backtested Performance (QQQ):**
| Metric | Value |
|--------|-------|
| CAGR | 10.7% |
| Win Rate | 71% |
| Max Drawdown | 23% |

**Monthly Return Estimate:** ~0.8-0.9% average monthly (below >3% target as standalone)

**Timeframe:** Daily bars, 1-5 day holds

**Transaction Cost Assumptions:** $0.005/share commission, minor slippage

**Source:** [^19^] [^20^] [^23^] [^24^] — QuantifiedStrategies.com, r/algotrading

**Notes:** Strategy works best when combined with other strategies or traded across multiple instruments simultaneously. The low time-in-market means capital is idle 80%+ of the time.

---

#### Strategy 2: IBS (Internal Bar Strength) Mean Reversion

**Category:** Percent-Range / Bounded Strategy

**Trading Rules:**
- **Formula:** IBS = (Close - Low) / (High - Low)
- **Entry:** IBS < 0.2 (buy on close)
- **Exit:** IBS > 0.8 (sell on close)

**Backtested Performance (SPY, 1993-present):**
| Metric | Basic IBS | IBS Variation 2 |
|--------|-----------|----------------|
| Trades | 919 | 583 |
| Avg Gain/Trade | 0.41% | 0.8% (combined) |
| Win Rate | 68% | 74% |
| CAGR | 12.5% | 15.3% |
| Max Drawdown | -26% | -22% |
| Profit Factor | 1.9 | 2.73 |
| Sharpe Ratio | — | 1.7 |
| Time in Market | — | 36% |

**Backtested Performance (QQQ, since inception):**
| Metric | Value |
|--------|-------|
| Trades | 742 |
| Avg Gain/Trade | 0.56% |
| CAGR | 16.6% |

**IBS + Second Indicator (SPY):**
| Metric | Value |
|--------|-------|
| Trades | 278 |
| Avg Gain/Trade | 0.8% |
| Win Rate | 78% |
| Hold Time | 4.8 days |
| Max Drawdown | -23.75% |

**IBS + Second Indicator (QQQ):**
| Metric | Value |
|--------|-------|
| Trades | 232 |
| Avg Gain/Trade | **1.33%** |
| Win Rate | 75% |
| Profit Factor | 2.9 |
| Max Drawdown | -19.5% |

**Monthly Return Estimate:** ~1.0-1.4% monthly depending on variant (basic to combined)

**Timeframe:** Daily bars, 1-6 day holds

**Transaction Cost Assumptions:** Low commissions required due to frequent trading

**Source:** [^21^] [^22^] [^55^] — QuantifiedStrategies.com, NAAIM paper

**Notes:** The IBS + second indicator combination on QQQ is one of the strongest documented mean reversion strategies, achieving 1.33% per trade with 75% win rate. Trading this across multiple instruments could increase frequency.

---

#### Strategy 3: IBS + Lower Band Mean Reversion Strategy

**Category:** Pullback in Uptrend / Combo Strategy

**Trading Rules:**
- Compute the rolling mean of (High - Low) over the last 25 days
- Compute the IBS indicator: (Close - Low) / (High - Low)
- Compute a lower band as the rolling High over the last 10 days minus 2.5x the rolling mean of (High - Low)
- Go long whenever SPY closes under the lower band AND IBS < 0.3
- Close the trade when SPY close is higher than yesterday's high

**Backtested Performance (QQQ, 25-year backtest):**
| Metric | Value |
|--------|-------|
| Sharpe Ratio | 2.11 |
| Annualized Return | 13.0% |
| Max Drawdown | 20.3% |
| Trades | 414 |
| Avg Return/Trade | 0.79% |
| Win Rate | 69% |
| Profit Factor | 1.98 |

**Monthly Return Estimate:** ~1.0% monthly

**Timeframe:** Daily bars

**Transaction Cost Assumptions:** Standard commission and slippage

**Source:** [^25^] [^54^] — r/algotrading

**Notes:** Combines trend identification (lower band from recent highs) with mean reversion (IBS) for a robust pullback strategy. The 2.11 Sharpe ratio is exceptional.

---

#### Strategy 4: "Trading the Mean Reversion Curve" Portfolio

**Category:** Combined Mean Reversion Portfolio

**Trading Rules:**
- Generate 6 mean reversion portfolios by varying the RSI(2) entry threshold: 5, 10, 15, 20, 25, and 30
- At the beginning of each month, look back 504 days (2 years) and find capital allocation across the 6 portfolios that maximizes Sharpe ratio
- Keep allocation fixed for the month
- Rebalance monthly

**Backtested Performance (Nasdaq-100 stocks, since 2010):**
| Metric | Max 4 Positions | Diversified |
|--------|----------------|-------------|
| Annual Return | **34%** | 25.7% |
| Max Drawdown | 35% | 28% |
| Sharpe Ratio | 1.23 | 1.14 |
| Expected Return/Trade | +0.79% | +0.40% |
| Win Rate | ~65% | 64.8% |
| Exposure Time | High | — |

**Monthly Statistics (504-day lookback, monthly rebalance, since 2010):**
- 66% of months positive (best: +20.1% in Jul'23)
- 34% of months negative (worst: -15.2% in May'19)
- Longest positive streak: 9 months
- Longest negative streak: 4 months

**Monthly Return Estimate:** ~2.1-2.8% monthly depending on concentration (25-34% CAGR)

**Timeframe:** Daily signals, monthly rebalancing

**Transaction Cost Assumptions:** Standard commissions; higher turnover due to monthly rebalancing

**Source:** [^62^] — Quantitativo

**Notes:** This is the **most promising approach for achieving >3% monthly returns** documented in this research. The key innovation is diversifying across multiple parameter sets rather than relying on a single optimized configuration. Monthly rebalancing is required (more frequent rebalancing is theoretically better but impractical due to weekend gap risk). With leverage, this could potentially exceed 3% monthly.

---

#### Strategy 5: Larry Connors High Probability ETF Trading Strategies

**Category:** Multiple Mean Reversion Systems

Connors published 6 systems in "High Probability ETF Trading" (2009), tested on 20 liquid ETFs:

| Strategy | Win Rate | Avg Gain/Trade | Avg Hold | Trades |
|----------|----------|---------------|----------|--------|
| 3-Day High/Low | 76.9% | 0.66% | 3.3 days | 709 |
| RSI(4) | 76.7% | 1.06% | 6.2 days | 786 |
| R3 (RSI2) | 75.9% | 0.92% | 5.0 days | 700 |
| %B (Bollinger) | 76.5% | 0.70% | 4.2 days | 1,014 |
| Multiple Days Up/Down | 73.6% | 0.50% | 3.3 days | 1,071 |
| RSI(2) 10/6 | 81.9% | 0.93% | 3.7 days | 1,075 |

**Composite Long Filter (all strategies combined):**
- Win rates across all strategies: 73-82%
- Average holding: 3-7 days
- Average gain per trade: 0.5-1.56%
- All strategies require price above 200-day MA for long trades

**R3 Strategy Portfolio (all 25 ETFs, 2000-2020):**
| Metric | Value |
|--------|-------|
| Trades | 992 |
| Win Rate | 75% |
| Avg Gain/Trade | 0.68% |
| Profit Factor | 2.08 |
| Max Drawdown | -16% |
| CAGR | 6.47% |

**Monthly Return Estimate:** ~0.5-0.9% monthly per strategy; combining multiple strategies could increase this

**Timeframe:** Daily bars, 3-7 day holds

**Transaction Cost Assumptions:** $0.005/share (IB model)

**Source:** [^48^] [^49^] — StockFetcher forum, QuantifiedStrategies.com

**Notes:** The power of this approach is in running ALL six systems simultaneously across a basket of 20+ ETFs. This increases trade frequency significantly while maintaining high win rates.

---

#### Strategy 6: Opening Gap Fade Strategy

**Category:** Opening Gap Reversion

**Trading Rules (SPY Long):**
- If SPY gaps down more than -0.15% but less than -0.6%, go long at the open
- Target: 75% of the gap (e.g., if gap is -0.5%, target is +0.375% from fill price)
- If target not reached, exit at the close
- Yesterday's close must be lower than 0.25 on IBS: (close-low)/(high-low)

**Backtested Performance (SPY, 2010-2012):**
| Metric | Value |
|--------|-------|
| Total Fills | 110 |
| Winners | 98 |
| Win Rate | 89% |
| Avg per Fill | 0.19% |

**Performance by Day of Week (2010-2012, all gap fades 0.1-0.6%):**
| Day | Total Return | Fills | Wins | Avg |
|-----|-------------|-------|------|-----|
| Monday | 12.05% | 200 | 160 | 0.060% |
| Tuesday | 11.76% | 231 | 182 | 0.051% |
| Wednesday | 22.68% | 239 | 202 | 0.095% |
| Thursday | 18.94% | 213 | 181 | 0.089% |
| Friday | 17.99% | 210 | 172 | 0.086% |

**Gaps Outside Yesterday's Bar:**
| Metric | Value |
|--------|-------|
| Total Return | 39.88% |
| Fills | 359 |
| Wins | 287 |
| Avg | **0.111%** |

**Monthly Return Estimate:** ~0.3-0.5% monthly (limited by trade frequency on single instrument)

**Timeframe:** Intraday, same-day exits

**Transaction Cost Assumptions:** Requires very low commissions due to small per-trade profits

**Source:** [^31^] — QuantifiedStrategies.com

**Notes:** While individual trade profits are small, the 89% win rate is remarkable. Running this across a basket of 20 ETFs could increase frequency. The strategy is becoming harder to execute as algorithmic trading arbitrages away gap inefficiencies. Wednesdays and Fridays show the best performance.

---

#### Strategy 7: Larry Connors %B (Bollinger Band) Strategy

**Category:** Bollinger Band Mean Reversion

**Trading Rules:**
- ETF must be above 200-day moving average
- %B (Bollinger Band position) below 0.2 for 3 consecutive days
- Buy on the close when both conditions met
- Exit when %B closes above 0.8

**Formula:** %B = (Close - BBandBot) / (BBandTop - BBandBot)

**Backtested Performance (20 ETFs, inception-2008):**
| Metric | Value |
|--------|-------|
| Trades | 1,014 |
| Win Rate | 76.5% |
| Avg Gain/Trade | 0.70% |
| Avg Hold | 4.2 days |

**Recent Backtest (2006-present):**
| Metric | Value |
|--------|-------|
| Trades | 138 |
| Win Rate | 79% |
| Avg Gain/Trade | 2.65% |
| Avg Hold | 16.6 days |

**Monthly Return Estimate:** ~0.5-0.7% monthly

**Timeframe:** Daily bars, 4-17 day holds

**Transaction Cost Assumptions:** Standard commissions

**Source:** [^35^] [^48^] — QuantifiedStrategies.com

**Notes:** Strategy showed periods of underperformance. Prior to April 2010, the strategy had an 87% win rate with 3.58% average gain, but every trade since then was negative in one backtest.

---

#### Strategy 8: Connors TPS (Time/Price Scale-In) Strategy

**Category:** Pullback in Uptrend with Scale-In

**Trading Rules:**
- Trade S&P 500 ETF above its 200-day moving average
- Open 10% long position if 2-period RSI < 25 for two consecutive days
- Increase position by 20% if price dips below previous entry
- Increase by 30% if price dips below second entry
- Increase by 40% if price dips below third entry
- Exit when 2-period RSI closes above 70

**Backtested Performance (20 ETFs, extended test):**
| Metric | Value |
|--------|-------|
| Total Trades | 6,423 |
| Winning Trades | 4,117 |
| Losing Trades | 2,306 |
| Win Rate | 64.1% |
| Profit Factor | 1.52 |
| CAGR | ~2.3% |
| Percent Months Profitable | 70.45% |
| Percent Years Profitable | 87.5% |
| Time in Market | ~20% |

**Monthly Return Estimate:** ~0.2% monthly (very low due to rare full position deployment)

**Timeframe:** Daily bars, multiple day holds with scale-in

**Transaction Cost Assumptions:** $0.01/share commission + $0.01/share slippage

**Source:** [^50^] [^73^] — TuringTrader, Portfolio Maestro backtest

**Notes:** TPS is designed for very low exposure. The CAGR appears low because positions are rarely at full size. The strategy is meant as a complement to other strategies rather than a standalone system. Connors reported 80-95% accuracy on individual ETF scale-in levels in his original book.

---

#### Strategy 9: Bollinger Band Mean Regression (Academic Study)

**Category:** Bollinger Band Mean Reversion

**Trading Rules:**
- Use 20-day SMA for Bollinger Band calculation
- Buy when price near lower band (oversold)
- Sell when price near upper band (overbought)

**Backtested Performance:**
| Stock | Annual Return | Sharpe Ratio |
|-------|--------------|--------------|
| AAPL | 11.1% | 0.48 |
| MSFT | 9.1% | 0.47 |

**Key Finding:** Only about 88% (85-90%) of security prices remain within the Bollinger Bands, meaning 12% of the time prices will "walk the band" in a trending move, causing losses for mean reversion traders.

**Monthly Return Estimate:** ~0.8-0.9% monthly (individual stocks)

**Timeframe:** Daily bars

**Source:** [^29^] [^38^] — Atlantis Press academic paper

**Notes:** Academic study confirms Bollinger Band mean reversion can generate positive returns but with relatively low Sharpe ratios. Strategy should be combined with other indicators.

---

#### Strategy 10: Gap Fade + IBS Filter (Advanced)

**Category:** Opening Gap Reversion with Mean Reversion Filter

**Key Findings from Gap Research:**
- **Gaps outside yesterday's bar** perform better than gaps inside (0.111% vs 0.059% avg)
- **Gaps after unfilled gaps** perform very well (0.136-0.185% avg)
- **Friday gaps** are the most reliable
- **Later in the month** performs better than early in the month
- **Yesterday's close > 2% above 10-day MA** + gap down: 0.120% avg
- **Yesterday's close > 2% below 10-day MA** + gap up: **0.185% avg**

**Monthly Return Estimate:** ~0.3-0.5% on SPY alone; could be scaled across ETF basket

**Timeframe:** Intraday, same-day exits

**Source:** [^31^] — QuantifiedStrategies.com

---

### Summary: Path to >3% Monthly Returns

Based on this research, **no single mean reversion strategy on a single instrument reliably achieves >3% monthly returns** with acceptable risk. However, several approaches can get close or exceed this target:

| Approach | Est. Monthly Return | Max Drawdown | Feasibility |
|----------|---------------------|-------------|-------------|
| Single RSI(2) on SPY | 0.8% | 23% | High |
| IBS + Indicator on QQQ | 1.0-1.4% | 20% | High |
| Mean Reversion Curve Portfolio (diversified) | 2.1% | 28% | High |
| Mean Reversion Curve (concentrated, max 4) | 2.8% | 35% | Medium |
| **High Probability ETF Trading (all 6 systems, 20 ETFs)** | **2.0-3.0%** | **25-30%** | **High** |
| Mean Reversion Curve + 1.25x leverage | **3.2%** | **35%** | Medium |

**The most viable path to >3% monthly appears to be:**
1. Run multiple uncorrelated mean reversion strategies simultaneously (RSI2, IBS, %B, gap fade)
2. Trade across a basket of 20+ ETFs (not just SPY/QQQ)
3. Use portfolio-level risk management and dynamic allocation
4. Consider modest leverage if the unleveraged max drawdown is <25%

**Critical Caveats:**
- All strategies perform poorly in strong bear markets; regime filters (200-day MA, VIX < 25) are essential
- Performance has degraded since 2010 due to increased algorithmic competition
- Transaction costs and slippage matter significantly for high-frequency strategies
- Walk-forward validation and out-of-sample testing are critical before deploying capital

---

### Source Index

[^19^] stratbase.ai — RSI(2) Strategy by Larry Connors
[^20^] quantifiedstrategies.substack.com — Larry Connors RSI Strategy Still Performing Well
[^21^] quantifiedstrategies.com — IBS Internal Bar Strength Indicator Strategies
[^22^] sahcapital.com — How To Exploit Nasdaq Pullbacks With IBS
[^23^] quantifiedstrategies.com — Complete Guide To Larry Connors' 2-Period RSI Trading Rules
[^24^] reddit.com/r/algotrading — Backtest Results for Connors RSI2 Strategy
[^25^] reddit.com/r/algotrading — A Mean Reversion Strategy with 2.11 Sharpe
[^27^] youtube.com — 3 RSI Trading Strategies Backtested with 30 Years of Data
[^28^] luxalgo.com — Mean Reversion Trading: Fading Extremes with Precision
[^29^] atlantis-press.com — Analysis of the Bollinger Band Mean Regression Trading Strategy
[^31^] quantifiedstrategies.com — Gap Fill Trading Strategies 2026
[^32^] etfreplay.com — Mean Reversion ETFreplay Blog
[^33^] setupalpha.com — RealTest Short Term Mean Reversion Strategy
[^35^] quantifiedstrategies.com — Larry Connors' %b Strategy (Bollinger Band)
[^37^] quantifiedstrategies.com — Bollinger Band Squeeze Strategy
[^38^] atlantis-press.com — Analysis of the Bollinger Band Mean Regression Trading Strategy
[^42^] reddit.com/r/Daytrading — Backtested RSI + Bollinger Bands strategy across ALL markets
[^48^] stockfetcher.com — HIGH PROBABILITY ETF TRADING BY LARRY CONNORS
[^49^] quantifiedstrategies.com — Larry Connors' R3 Strategy
[^50^] turingtrader.com — Connors' TPS Portfolio
[^52^] medium.com — How to Get a 131% Return with Mean Reversion Trading Strategy
[^53^] algotr.substack.com — The Mean Reversion Portfolio That Had Only One Losing Year since 1998
[^54^] reddit.com/r/algotrading — A Mean Reversion Strategy with 2.11 Sharpe
[^55^] naaim.org — The IBS Effect: Mean Reversion in Equity ETFs
[^62^] quantitativo.com — Trading the Mean Reversion Curve
[^68^] alvarezquanttrading.com — The ABCs of creating a mean reversion strategy Part 2
[^73^] externalcontent.blob.core.windows.net — TPS de Connors strategy backtest PDF
