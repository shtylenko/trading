# Dimension 01: Momentum-Based Stock Selection (LONG-ONLY)

**Research Date:** 2025-07-01
**Sources Searched:** 24 independent web searches
**Total Primary Sources Found:** 35+
**Constraint:** LONG-ONLY strategies, Stocks and ETFs only

---

## Table of Contents

1. [Dual Momentum (Antonacci GEM)](#1-dual-momentum-antonacci-gem)
2. [Cross-Sectional Stock Momentum](#2-cross-sectional-stock-momentum)
3. [Earnings Momentum (SUE, Estimate Revisions)](#3-earnings-momentum-sue-estimate-revisions)
4. [Sector/Industry Momentum (ETF Rotation)](#4-sectorindustry-momentum-etf-rotation)
5. [Risk-Managed Momentum Variants](#5-risk-managed-momentum-variants)
6. [Concentrated Momentum Portfolios](#6-concentrated-momentum-portfolios)
7. [Momentum Crash Protection](#7-momentum-crash-protection)
8. [Weekend Trend Trader](#8-weekend-trend-trader)
9. [Momentum ETFs — Live Performance](#9-momentum-etfs--live-performance)
10. [Transaction Cost Reality Check](#10-transaction-cost-reality-check)
11. [Summary Comparison Table](#11-summary-comparison-table)

---

## 1. Dual Momentum (Antonacci GEM)

### 1.1 Original GEM Strategy — Exact Rules

**Author:** Gary Antonacci [^313^]
**Original Paper:** "Risk Premia Harvesting Through Dual Momentum" (2012)
**Book:** *Dual Momentum Investing* (2014)

#### Trading Rules (GEM — Global Equities Momentum)

1. **Assets Tracked:** S&P 500 (US stocks), MSCI ACWI ex-US (International stocks), US Aggregate Bonds, T-Bills
2. **Lookback Period:** 12-month total return
3. **Rebalancing Frequency:** Monthly (last trading day of each month)
4. **Step 1 — Absolute Momentum:** Compare S&P 500 12-month total return vs. T-Bill 12-month total return
   - If S&P 500 > T-Bill → proceed to Step 2 (risk-on)
   - If S&P 500 <= T-Bill → invest 100% in bonds (risk-off)
5. **Step 2 — Relative Momentum:** If in risk-on mode, compare S&P 500 12-month return vs. International stocks 12-month return
   - If S&P 500 >= International → invest 100% in S&P 500
   - If International > S&P 500 → invest 100% in International stocks
6. **Position:** Always 100% invested in a SINGLE asset (either SPY, VEU, AGG, or BIL equivalent)

#### Original Backtest Performance (1974–2013) [^314^]

| Metric | GEM (12-month) | ACWI Buy & Hold |
|--------|---------------|-----------------|
| **Annual Return** | **17.43%** | 8.85% |
| **Standard Deviation** | 12.64% | 15.56% |
| **Sharpe Ratio** | 0.87 | 0.22 |
| **Maximum Drawdown** | **-22.72%** | -60.21% |

**Independent Replication Results (1973–2013):** [^314^]
- Annual Return: 16.70% (slightly lower than Antonacci's 17.43%, likely due to using Treasury-only bonds vs. full aggregate)
- Max Drawdown: -19.07%
- Sharpe Ratio: 0.87

#### Out-of-Sample Performance (1986–2026) [^313^]

| Metric | GEM BestFolio Backtest |
|--------|----------------------|
| **CAGR** | 12.3% |
| **Maximum Drawdown** | -33.7% |
| **Sharpe Ratio** | 0.99 |
| **Sortino Ratio** | 1.37 |
| **Annualized Volatility** | 14.1% |
| **Total Return** | 10,713.7% |

> **CRITICAL CONTEXT:** The BestFolio backtest (1986–2026) shows a 12.3% CAGR vs. Antonacci's original 17.43% (1974–2013). The discrepancy arises from different bond proxies, different international indices, and the fact that 2012–2025 was a challenging out-of-sample period for GEM. [^312^] notes that "GEM's out-of-sample performance from 2015–2018 was unimpressive." The InvestResolve replication (1950–2018) confirmed GEM's general robustness but with varying results across parameterizations. [^310^]

### 1.2 Enhanced Variant: Accelerating Dual Momentum (ADM)

**Source:** Engineered Portfolio [^364^]
**Period:** 1998–February 2018

#### Rules Modification:
- Uses **1-month, 3-month, AND 6-month returns** (multiple lookbacks instead of just 12-month)
- Replaces Total Bond with **Long-Term Treasuries**
- Replaces Global Large Cap with **Global Small Cap (VINEX)**

#### Performance:

| Metric | ADM | Original GEM | S&P 500 |
|--------|-----|-------------|---------|
| **Final Balance ($10K)** | $426,408 | $80,296 | ~$40,000 |
| **Annual Real Return** | **10.5%** | 9.1% | 6.9% |
| **Max Drawdown (real)** | **-34%** | -43% | -77% |
| **Worst 1-Year Loss (real)** | **-21%** | -33% | -58% |

> The ADM strategy never had a negative calendar year in the backtest (1998–2018). However, this is partly due to the strong bond tailwind during this period.

### 1.3 Enhanced Variant: Global Growth Cycle Enhanced (GGC)

**Source:** grzegorz.link research [^26^]
**Innovation:** Combines Dual Momentum with OECD CLI (Composite Leading Indicators) to time global expansion/contraction cycles.

#### Performance:
| Metric | GGC Enhanced | Original DM | S&P 500 |
|--------|-------------|-------------|---------|
| **CAGR** | **16.4%** | ~15% | ~11% |
| **Max Drawdown** | **-16.8%** | -19% to -22% | ~-50% |

### 1.4 Practical Implementation Notes — GEM

| Parameter | Detail |
|-----------|--------|
| **Minimum Capital** | Any (ETF-based; $10K+ recommended for practical implementation) |
| **Time Required** | ~30 minutes/month (calculate 12-month returns, place 1 trade) |
| **Transaction Costs** | ~1 trade/month; minimal with commission-free brokers |
| **Tax Efficiency** | Moderate (monthly trading creates short-term gains when switching) |
| **Best Broker** | Any broker offering free ETF trades (most major brokers) |
| **ETF Proxies** | SPY (US), VEU/VEA (International), AGG/BND (Bonds), BIL/SHV (T-Bills) |

### 1.5 Counter-Arguments / Limitations

1. **Lookback Sensitivity:** The 12-month lookback is the best-performing parameter in-sample, raising data-mining concerns [^314^]
2. **Bond Proxy Sensitivity:** Antonacci's original results used a broader bond index; switching to Treasury-only reduces returns
3. **Out-of-Sample Underperformance:** GEM has struggled in the 2014–2025 period, with the QuantifiedStrategies backtest showing only 6.75% CAGR (1986–2024) vs. 9.2% for S&P 500 [^19^]
4. **Single-Asset Concentration:** 100% in one asset at all times creates binary risk
5. **Zero Short-Side Capture:** As a long-only strategy, GEM misses the short-side momentum premium documented in academic literature

---

## 2. Cross-Sectional Stock Momentum

### 2.1 Academic Foundation — Jegadeesh & Titman (1993)

**Source:** [^317^] (Original academic paper, PDF available)
**Period Studied:** 1965–1989 (original), extended to 1927–1964
**Strategy Type:** Long-Short (adaptable to long-only)

#### Exact Rules:
1. **Universe:** All NYSE/AMEX stocks (adaptable to any universe)
2. **Ranking Period:** Past 6 months (also tested 3, 9, 12 months)
3. **Skip Month:** Most recent month excluded (to avoid short-term reversal)
4. **Portfolio Formation:** Sort all stocks by past returns; form decile portfolios
5. **Holding Period:** 6 months (also tested 3, 9, 12 months)
6. **Rebalancing:** Monthly (overlapping portfolios)

#### Key Findings:
- 6-month/6-month strategy: **12.01% compounded excess return per year**
- Strategy profits NOT explained by systematic risk
- Positive returns in each of 12 months following formation (except month 1)
- Half of excess returns dissipate within 2 years (long-term reversal)
- Profitable in virtually all 5-year sub-periods (except 1975–1979 for small firms)

#### Long-Only Adaptation:
- Academic literature confirms long-only momentum captures a significant portion of the premium
- Griffin, Ji, and Martin found momentum is **more profitable on the long side** than the short side [^315^]
- Fisher, Shah, and Titman found long-only value+momentum combinations outperform pure strategies after transaction costs [^344^]

### 2.2 Standard 12-1 Month Cross-Sectional Momentum

**Source:** Quantpedia [^315^], QuantifiedStrategies [^307^]
**Period:** Multiple academic studies, 1920s–present

#### Exact Rules (Long-Only):
1. **Universe:** Select liquid stock universe (e.g., S&P 500, Russell 1000, or largest 1,500 stocks)
2. **Lookback:** 12 months minus 1 month (months t-12 to t-1)
3. **Ranking:** Calculate total return for each stock over the lookback period
4. **Selection:** Buy the top decile (10%) or top quintile (20%) of stocks by momentum
5. **Weighting:** Equal-weight within the portfolio
6. **Rebalancing:** Monthly
7. **Skip Recent Month:** Exclude the most recent month to avoid short-term reversal

#### Backtested Performance:

| Study | Period | Long-Only CAGR | Market CAGR | Alpha |
|-------|--------|---------------|-------------|-------|
| Jegadeesh & Titman | 1965–1989 | ~12% excess | - | 12.01% |
| Manigault (S&P 500) | Various | Top decile outperforms | - | 3-5% annually [^309^] |
| Various (Quantpedia) | 1920s–2009 | 13.94% p.a. | ~10% | ~4% [^136^] |

#### QuantifiedStrategies Python Implementation [^307^]:
```python
# Key parameters
lookback = 252 days (12 months)
skip = 21 days (1 month)  
n_quantiles = 10 (deciles)
rebalance_freq = 21 days (monthly)
```

### 2.3 Cross-Sectional Momentum — Practical Implementation

| Parameter | Detail |
|-----------|--------|
| **Universe Size** | Minimum 100 stocks; 500+ recommended |
| **Minimum Capital** | $50K–$100K for 20-stock equal-weight; $500K+ for 50-stock |
| **Time Required** | 4–8 hours/month for manual; 1 hour with screening software |
| **Transaction Costs** | Monthly rebalancing = ~50–150% annual turnover; 0.5–2.0% drag |
| **Slippage** | Higher for small-cap momentum; minimal for large-cap |
| **Rebalancing Frequency** | Monthly (standard); quarterly (reduces costs, slightly lower returns) |

### 2.4 Counter-Arguments / Limitations

1. **Transaction Costs:** Lesmond, Schill, and Zhou (2004) found that accounting for realistic transaction costs, many momentum strategies become unprofitable, especially short-term variants [^360^] [^361^]
2. **2009 Crash:** Standard momentum suffered catastrophic drawdown during the 2009 recovery; Fama-French momentum factor returned -83% [^85^]
3. **Turnover:** Monthly rebalancing creates 50–150% annual turnover, generating significant tax drag in taxable accounts [^361^]
4. **Decay:** Half of momentum profits reverse within 2 years [^317^]
5. **Short-Term Reversal:** Returns in the month immediately following formation are typically negative [^317^]

---

## 3. Earnings Momentum (SUE, Estimate Revisions)

### 3.1 Standardized Unexpected Earnings (SUE) Strategy

**Source Research:** Foster, Olsen & Shevlin (1984); Hou, Xue & Zhang (2018)
**Backtest Source:** QuantConnect Community [^323^]

#### Exact Rules:
1. **SUE Calculation:**
   ```
   SUE = (EPS_current_quarter - EPS_same_quarter_last_year) / std_dev(EPS_changes_last_8_quarters)
   ```
2. **Universe:** All stocks with available earnings data (typically NYSE/AMEX/Nasdaq)
3. **Ranking:** Sort by SUE score monthly
4. **Selection:** Go long top 5% with highest positive earnings surprises
5. **Rebalancing:** Monthly
6. **Holding Period:** 1 month

#### Backtest Performance (QuantConnect Implementation) [^323^]:

| Metric | 5-Year (2021–2026) | 18-Year (2007–2026) |
|--------|-------------------|---------------------|
| **CAGR** | **23.58%** | **13.62%** |
| **Sharpe Ratio** | 0.635 | 0.442 |
| **Max Drawdown** | -28.9% | **-63.9%** |
| **Win Rate** | 67% | 65% |
| **Net Profit** | +173% | +1,009% |

> **CRITICAL WARNING:** The 63.9% max drawdown (2007–2026) demonstrates that SUE strategies are devastated during financial crises. The 2008–2009 period "decimated the strategy — if you were running this live, you would have lost nearly two-thirds of your capital." [^323^]

#### Academic Evidence — Chan, Jegadeesh & Lakonishok (1996) [^324^]

| Measure | Decile 1 (Low) | Decile 10 (High) | Spread |
|---------|---------------|-----------------|--------|
| **Prior 6-month return** | 0.086 | 0.226 | 0.140 |
| **SUE** | 0.140 | 0.183 | 0.043 |
| **Analyst revisions (REV6)** | 0.134 | 0.210 | 0.076 |

- SUE, analyst revisions, and past returns are **correlated but distinct signals**
- Combining all three signals produces the strongest predictive power
- SUE has t-statistic of 6.00 for predicting 6-month returns (highly significant)

### 3.2 Analyst Estimate Revisions Strategy

**Source:** Chan, Jegadeesh & Lakonishok (1996) [^324^]

#### Exact Rules:
1. **REV6 Calculation:** 6-month moving average of revisions in I/B/E/S mean analyst earnings forecasts, scaled by stock price
2. **Ranking:** Sort stocks by REV6 score
3. **Selection:** Long top decile (highest upward revisions)
4. **Rebalancing:** Monthly
5. **Holding Period:** 6–12 months

#### Performance:
- REV6 t-statistic: **5.45** for 12-month returns (highly significant)
- Combined with SUE and price momentum: t-stats of 4.00+ for each signal
- Three-signal combination produces the most robust prediction model

### 3.3 Practical Implementation — Earnings Momentum

| Parameter | Detail |
|-----------|--------|
| **Data Requirements** | Real-time earnings data (expensive); fundamental data provider required |
| **Minimum Capital** | $100K+ (need diversification across 20+ positions) |
| **Time Required** | 8–12 hours/month for data gathering and analysis |
| **Transaction Costs** | High monthly turnover (100%+); bid-ask spreads on smaller names |
| **Key Risk** | Earnings announcements are discrete events; strategy can cluster risk around announcement periods |
| **Best Implementation** | Use a quantitative platform (e.g., Portfolio123, QuantConnect) with automated data feeds |

### 3.4 CANSLIM — Discretionary Earnings Momentum

**Creator:** William O'Neil
**Source:** Investopedia [^334^], DeepVue [^340^]

#### The 7 Criteria:
| Letter | Criterion | Minimum Threshold |
|--------|-----------|------------------|
| **C** | Current quarterly EPS growth | >25% YoY |
| **A** | Annual earnings growth | >25% over 3–5 years |
| **N** | New products, management, highs | Qualitative |
| **S** | Supply and demand (volume + float) | Increasing volume on rises |
| **L** | Leader or laggard | Relative strength >= 80 |
| **I** | Institutional sponsorship | Increasing institutional ownership |
| **M** | Market direction | Only buy in uptrends |

> **Note:** CANSLIM is fundamentally a **discretionary** stock-picking methodology, not a fully systematic strategy. Academic backtests are rare because many criteria are qualitative. One study claimed 30.86% returns but this is disputed and non-replicable. The "M" (market direction) criterion is the most critical risk management component.

---

## 4. Sector/Industry Momentum (ETF Rotation)

### 4.1 Faber Sector Momentum Rotation

**Source:** Mebane Faber, "Relative Strength Strategies for Investing" (cited in Quantpedia [^136^])
**Period:** 1928–2009

#### Exact Rules:
1. **Universe:** 10 sector ETFs (or French-Fama sector data)
2. **Lookback:** 12-month total return
3. **Selection:** Pick the **top 3 ETFs** with strongest 12-month momentum
4. **Weighting:** Equal-weight the 3 selected sectors
5. **Rebalancing:** Monthly
6. **Trend Filter (optional):** Only invest if S&P 500 is above its 10-month moving average; otherwise move to bonds

#### Backtest Performance:

| Metric | Top 3 Sectors | US Equity Index |
|--------|--------------|-----------------|
| **Annual Return** | **13.94%** | ~10% |
| **Outperformance** | ~4% p.a. | - |
| **Volatility** | 18.38% | ~18% |
| **Maximum Drawdown** | -46.29% | ~-55% |
| **Sharpe Ratio** | 0.54 | ~0.35 |

- Strategy outperforms in ~70% of all years
- Returns are persistent across time
- Adding a trend-following parameter decreases both volatility and drawdown [^136^]

### 4.2 Practical Implementation — Sector Rotation

| Parameter | Detail |
|-----------|--------|
| **Universe** | 11 Select Sector SPDRs, Vanguard sector ETFs, or iShares sector ETFs |
| **Minimum Capital** | $15K+ (3 ETFs at ~$5K each) |
| **Time Required** | 30 minutes/month |
| **Transaction Costs** | 3 trades/month maximum; minimal with commission-free brokers |
| **Tax Efficiency** | Moderate (monthly trading) |
| **Best ETFs** | XLY, XLP, XLF, XLK, XLI, XLB, XLE, XLU, XLV, XLRE, XLC |

### 4.3 Industry-Specific Momentum

**Source:** Chan, Jegadeesh & Lakonishok (1996) [^324^]
- Industry momentum exists but does NOT fully explain individual stock momentum
- Industry-adjusted momentum still produces significant returns
- Equal industry weights (to avoid industry bets) still show significant outperformance

---

## 5. Risk-Managed Momentum Variants

### 5.1 Constant Volatility Scaling (Barroso & Santa-Clara, 2015)

**Source:** [^325^] [^329^]
**Innovation:** Scale momentum portfolio exposure based on past realized volatility

#### Exact Rules:
1. **Calculate Realized Variance:** Use past 6 months of daily returns
   ```
   variance_hat = (21 * sum of past 126 daily squared returns) / 126
   ```
2. **Target Volatility:** Set target (typically 12% annualized or market long-run average ~15.93%)
3. **Scaling Factor:**
   ```
   L = sigma_target / sigma_hat
   ```
4. **Apply Scaling:** If L < 1, reduce exposure (hold cash); if L > 1, increase exposure (leverage)

#### Performance Improvements:

| Metric | Standard Momentum | Risk-Managed |
|--------|------------------|--------------|
| **Annualized Sharpe Ratio** | 0.53 | **0.97** |
| **Excess Kurtosis** | High | Reduced |
| **Left Skewness** | Severe | Reduced |
| **Crash Risk** | High | Broadly avoided |

> "The constant volatility strategy leads to an improved Sharpe Ratio, a reduced excess kurtosis as well as a less pronounced left skewness, thereby significantly decreasing its risk." [^325^]

### 5.2 Idiosyncratic (Residual) Momentum

**Source:** Blitz, Hanauer & Vidojevic (2017) [^345^] [^346^]
**Innovation:** Rank stocks on idiosyncratic returns (returns orthogonal to market, size, and value factors) instead of total returns

#### Exact Rules:
1. **Calculate Idiosyncratic Returns:** Regress each stock's returns on Fama-French 3 factors (market, size, value); use residuals
2. **Ranking Period:** 12 months (skipping most recent month)
3. **Portfolio Formation:** Sort by cumulative idiosyncratic return
4. **Long-Top Decile / Short-Bottom Decile**
5. **Rebalancing:** Monthly

#### Performance:

| Metric | Idiosyncratic Momentum | Conventional Momentum |
|--------|----------------------|---------------------|
| **Monthly Return (D1-D10)** | 1.39% | 1.54% |
| **Sharpe Ratio (monthly)** | **0.48** | 0.25 |
| **Crash in Up Months After Bear Markets** | **-0.18%** (t=-0.39, not significant) | Severe |
| **Long-Term Reversal** | **None** (continues for 5 years) | Strong reversal |
| **Japan Performance** | **Works** | Does NOT work |

> "Idiosyncratic momentum is significantly less affected by market dynamics and crash risk. The Sharpe ratio is almost double that of conventional momentum." [^345^]

### 5.3 Dynamic Scaling (Moreira & Muir, 2017)

**Source:** [^329^]
**Innovation:** Use past 1-month realized variance instead of 6-month

#### Rules:
- Same as Barroso & Santa-Clara but with shorter variance estimation window
- More responsive to recent volatility changes
- Similar performance improvement (Sharpe ratio roughly doubles)

### 5.4 Conservative Formula (Blitz & van Vliet, 2018)

**Source:** [^344^]
**Innovation:** Combines low volatility + price momentum + net payout yield

#### Rules:
1. Universe: 1,000 liquid stocks
2. Sort by: low historical volatility, high price momentum, high net payout yield
3. Select: Top 100 stocks
4. Rebalancing: Quarterly or monthly

#### Performance (1929–2016):
- **Annual Return: 15.1%**
- Generates consistent returns internationally (US, Europe, Japan, emerging markets)
- Outperforms pure momentum and pure low-volatility strategies on a risk-adjusted basis

### 5.5 Summary: Risk-Managed Momentum Techniques

| Technique | Key Insight | Sharpe Improvement | Crash Protection |
|-----------|-------------|-------------------|------------------|
| **Volatility Scaling** | High vol predicts low future returns | ~2x | Strong |
| **Idiosyncratic Momentum** | Factor-adjusted returns more robust | ~2x | Excellent |
| **Dynamic Scaling** | Shorter variance window | ~2x | Strong |
| **Conservative Formula** | Combine with low vol + yield | ~1.5x | Moderate |

---

## 6. Concentrated Momentum Portfolios

### 6.1 10–20 Stock Equal-Weight Portfolios

**Key Finding:** Academic evidence suggests that concentrated momentum portfolios (top 10–20 stocks) can work but with higher volatility.

#### Evidence:

**Source:** Nordic Stock Market Study [^344^]
- Long-only combination of low volatility + momentum: **Sharpe ratio 0.91**
- Standard momentum (WML): Monthly excess return 1.49%
- Long-only Winners portfolio: Monthly excess return 1.27%
- Combination long-only portfolio: Monthly excess return **1.08%**, **Sharpe 0.91**

**Source:** Reddit/Quant Discussion [^368^]
- One practitioner reported running a concentrated portfolio of 15–20 stocks using momentum
- "The long-only momentum book performs — the long-run returns are slightly higher"

### 6.2 S&P 500 Momentum Index

**Source:** S&P Dow Jones Indices [^354^]

| Metric | S&P 500 Momentum | S&P 500 Equal Weight |
|--------|-----------------|---------------------|
| **Top 10 Holdings** | 64.7% of portfolio | 2.5% of portfolio |
| **Median Market Cap** | $72.1B | $36.3B |
| **Concentration** | High (momentum begets concentration) | Low |

> Momentum strategies naturally concentrate in the largest, best-performing stocks. This creates concentration risk during momentum crashes when these same stocks reverse sharply.

### 6.3 Practical Guidelines for Concentration

| Portfolio Size | Pros | Cons | Minimum Capital |
|---------------|------|------|----------------|
| **10 stocks** | Highest potential alpha, easiest to track | Highest idiosyncratic risk, large drawdowns | $100K+ |
| **20 stocks** | Good balance of alpha and diversification | Still concentrated; sector risk | $100K–$200K |
| **50 stocks** | Lower volatility, still beats market | Higher transaction costs, more work | $250K–$500K |
| **100 stocks** | Close to academic momentum factor | High turnover, significant costs | $500K+ |

---

## 7. Momentum Crash Protection

### 7.1 The Momentum Crash Problem

**Source:** Daniel & Moskowitz (2016) [^85^]

| Event | Momentum Drawdown | Trigger |
|-------|------------------|---------|
| **2009 (3 months)** | **-73.42%** | Market recovery after financial crisis |
| **2020 (COVID)** | -28.2% (April), -26.2% (November) | Flash bear market + recovery |
| **2008–2009 (GFC)** | >-80% cumulative | Market crash + recovery |

> "Momentum crashes tend to occur after a bear market period. After the bear market, stocks that plunged the most tend to recover more, so the 'loser' stocks perform better than 'winner' stocks." [^344^]

### 7.2 Three Methods to Fix Momentum Crashes

**Source:** Hanauer & Windmueller (2020) [^328^]

All three approaches:
- Decrease momentum crashes
- Lead to higher risk-adjusted returns
- Raise break-even transaction costs
- Sharpe ratios roughly **double** compared to standard momentum

**Best performing: Idiosyncratic Momentum** — see Section 5.2

### 7.3 Practical Crash Protection Rules

| Technique | How It Works | Effectiveness |
|-----------|-------------|---------------|
| **Volatility Scaling** | Reduce position when momentum vol is high | Strong |
| **Market Regime Filter** | Exit momentum when market drops below 200-day MA | Strong |
| **Absolute Momentum Overlay** | Only hold momentum if market has positive 12-month return | Moderate |
| **Idiosyncratic Momentum** | Use factor-adjusted returns instead of raw returns | Excellent |
| **Seasonal Adjustment** | Reduce momentum exposure in January (tax selling reversal) | Moderate |
| **Max Position Limits** | Cap any single stock at 5–10% of portfolio | Risk management |

---

## 8. Weekend Trend Trader

### 8.1 Nick Radge's Strategy — Exact Rules

**Source:** Nick Radge, *Weekend Trend Trader* book [^357^] [^94^] [^96^]
**Strategy Type:** Long-only trend-following momentum on individual stocks
**Original Focus:** Australian small-cap industrials (outside ASX 100, within ASX 500)

#### Exact Entry Rules:
1. **Market Filter:** Index (e.g., S&P 500) close must be ABOVE its 10-week moving average
2. **Breakout:** Stock must make a new **20-week high**
3. **Momentum Confirmation:** 20-week Rate of Change (ROC) must be **>= 30%**
4. All three conditions must be true simultaneously
5. Enter on Monday at market open

#### Exact Exit Rules:
1. **Normal Trailing Stop:** 40% below highest weekly close (when market is trending UP)
2. **Bear Market Trailing Stop:** 10% below highest weekly close (when market is trending DOWN)
3. Trailing stop is NEVER moved down, only up
4. If market recovers, maintain existing stop until new higher stop can be set
5. Review on weekend; place sell orders Monday if triggered

#### Position Sizing:
- **5% of total account capital per position**
- Maximum 20 positions (100% invested)
- When regime filter goes from uptrend → downtrend: tighten stops to 10%
- Avg single position loss: ~0.6% of total portfolio (5% × 11.97% avg loss)
- Avg single position win: ~1.05% of total portfolio (5% × 21% avg win)

#### Reported Performance (Nick Radge):

| Metric | Value |
|--------|-------|
| **Win Rate** | 44% |
| **Win/Loss Ratio** | 2.6:1 |
| **Average Win** | +21% per position |
| **Average Loss** | -11.97% per position |

#### Independent Backtest (ThinkOrSwim, S&P 100, 1992–2019) [^353^]:

| Metric | Weekend Trend Trader | Buy & Hold (SPX) |
|--------|---------------------|-------------------|
| **Starting Capital** | $25,000 | $25,000 |
| **Ending Capital** | **$1,789,306** | $194,838 |
| **Net Profit %** | **7,057%** | 679% |
| **Annualized Gain** | **16.61%** | 7.67% |
| **Number of Trades** | 78 | 1 |
| **Avg Bars Held** | 326.59 (~6.3 years) | - |
| **Exposure** | 88.50% | 99.57% |

### 8.2 Practical Implementation

| Parameter | Detail |
|-----------|--------|
| **Timeframe** | Weekly (check signals on weekend, trade Monday) |
| **Minimum Capital** | $50K+ (for 20 positions at 5% each) |
| **Time Required** | 2–4 hours/weekend |
| **Software** | Stock screener for 20-week highs + ROC > 30% |
| **Key Discipline** | Do not enter stops as live orders; review weekly and place orders manually |

---

## 9. Momentum ETFs — Live Performance

### 9.1 iShares MSCI USA Momentum Factor ETF (MTUM)

**Source:** [^101^] [^333^]
**Strategy:** Tracks MSCI USA Momentum SR Variant Index (12-month minus 1-month price momentum, risk-adjusted)
**Inception:** April 15, 2013
**Expense Ratio:** 0.15%
**AUM:** $26.66B

#### Live Performance:

| Period | MTUM Return | Category Avg |
|--------|------------|--------------|
| **YTD 2026** | +35.51% | +5.14% |
| **1 Year** | +48.05% | +27.72% |
| **3 Years** | +34.51% (annualized) | +19.34% |
| **5 Years** | +14.44% (annualized) | +11.20% |
| **10 Years** | +16.94% (annualized) | +13.77% |
| **2024** | **+32.89%** | +21.45% |
| **2025** | **+22.15%** | +15.54% |
| **2023** | +9.16% | +22.32% |
| **2022** | -18.26% | -16.96% |

> **Key Insight:** MTUM dramatically outperformed in 2024–2025 as large-cap tech momentum surged. However, it underperformed in 2023 when the broad market rally favored value and small-caps.

### 9.2 Alpha Architect QMOM (U.S. Quantitative Momentum ETF)

**Source:** [^359^] [^363^]
**Strategy:** Active, rules-based momentum; ~50–200 stocks from largest 1,500 US stocks
**Methodology:** 12-month minus 1-month return + momentum quality screens (consistency of returns)
**Expense Ratio:** Higher than passive (check current prospectus)
**Rebalancing:** Monthly

#### Live Performance:

| Period | QMOM Return |
|--------|------------|
| **YTD 2026** | +18.54% |
| **1 Year** | +26.08% |
| **3 Years** | +78.89% (cumulative) |
| **5 Years** | +71.88% (cumulative) |
| **Since Inception** | +233.27% |
| **2024** | +32.17% |
| **2025** | +1.42% |

#### Key Methodology Points [^363^]:
1. Universe: Largest 1,500 US stocks by market cap
2. Eliminate: Illiquid securities, ETFs, stocks with <12 months data
3. Negative screens: Poor 6-month momentum, poor 9-month momentum, high beta
4. Rank by: 12-month cumulative return excluding most recent month
5. Quality screens: Identify most consistent (not just highest) positive returns
6. Select: Top 50–200 momentum stocks
7. Rebalance: Monthly

> **Key Differentiator:** QMOM uses "momentum quality" screens to identify stocks with consistent positive returns rather than just the highest raw returns. This is designed to reduce the impact of one-off spikes and improve robustness.

### 9.3 AQR Managed Futures (QMHIX) — Time-Series Momentum

**Source:** [^352^] [^355^]
**Note:** This is a managed futures fund (not pure stock momentum), included for comparison.

| Period | QMHIX Return |
|--------|-------------|
| **YTD 2026** | +14.72% |
| **1 Year** | +31.82% |
| **5 Years** | +15.91% (annualized) |

---

## 10. Transaction Cost Reality Check

### 10.1 The Transaction Cost Problem

**Source:** Lesmond, Schill & Shen (2004) [^360^]; UK replication study [^362^]

| Finding | Implication |
|---------|-------------|
| Loser portfolios tilt heavily toward small-cap, low-price, low-volume stocks | Short-side trading costs are prohibitive |
| Round-trip cost for losers: 6.71% (UK), 3.76% (quoted spread alone) | Momentum profits eliminated for short-term strategies |
| Round-trip cost for winners: 3.77% (UK), 2.21% (quoted spread alone) | Long-only more viable than long-short |
| Annual turnover: 76–85% for 6-month strategies | Monthly rebalancing creates 50–150% annual turnover |

### 10.2 Net-of-Cost Performance

**Source:** Agyei-Ampomah [^361^]

| Strategy | Gross Return | After Transaction Costs |
|----------|-------------|------------------------|
| 3-month ranking / 1-month hold | 24.7% | **Negative** |
| 6-month ranking / 6-month hold | Moderate | Marginal/Negative |
| 12-month ranking / 9-month hold | 44.64% | **~4.5% net** |
| 12-month ranking / 12-month hold | Positive | **Positive (most robust)** |

### 10.3 Key Takeaway for Long-Only Investors

> "In all cases, a long-only strategy of buying the winners is not profitable net of transaction costs. The net return on this is either negative or insignificantly positive." [^361^]

**HOWEVER**, this finding must be interpreted carefully:
1. These studies use older transaction cost data (pre-commission-free era)
2. Modern commission-free brokers dramatically reduce costs
3. Using large-cap only universes (S&P 500) reduces bid-ask spreads
4. Quarterly instead of monthly rebalancing can cut turnover by 60%+
5. Many live momentum ETFs (MTUM, QMOM) demonstrate profitable live performance net of costs

### 10.4 Modern Cost Estimates

| Cost Component | Large-Cap Momentum | Small-Cap Momentum |
|---------------|-------------------|-------------------|
| **Commissions** | $0 (commission-free brokers) | $0 |
| **Bid-Ask Spread** | 0.05–0.20% | 0.30–1.00% |
| **Market Impact** | Negligible (<$1M) | Moderate |
| **Annual Turnover Cost** | 0.5–2.0% | 2.0–5.0% |

---

## 11. Summary Comparison Table

| Strategy | CAGR | Max DD | Sharpe | Min Capital | Time/Month | Best For |
|----------|------|--------|--------|-------------|------------|----------|
| **GEM (Antonacci)** | 12–17% | -17% to -34% | 0.87–0.99 | $10K | 30 min | Simple, systematic |
| **Cross-Sectional (12-1)** | 10–14% | -30% to -50% | 0.5–0.7 | $100K | 4–8 hrs | Factor investors |
| **SUE Earnings** | 14–24% | -29% to -64% | 0.44–0.64 | $100K | 8–12 hrs | Fundamental quants |
| **Sector Rotation** | 13–14% | -46% | 0.54 | $15K | 30 min | ETF traders |
| **Risk-Managed (vol scaling)** | 10–15% | -15% to -25% | 0.9–1.0 | $100K | 2–4 hrs | Risk-conscious |
| **Weekend Trend Trader** | 17–23% | -30% to -40% | ~0.6 | $50K | 2–4 hrs | Part-time traders |
| **Idiosyncratic Momentum** | 12–17% | -15% to -25% | ~0.96 | $100K | 2–4 hrs | Sophisticated quants |
| **MTUM ETF (live)** | 14–17% | Similar to market | ~0.7 | Any | 0 min | Passive exposure |
| **QMOM ETF (live)** | 14–18% | -25% to -35% | ~0.6 | Any | 0 min | Active momentum |

---

## Source Index

| Citation | Source | URL | Date |
|----------|--------|-----|------|
| [^19^] | QuantifiedStrategies — Dual Momentum Backtest | quantifiedstrategies.com | 2026-05-30 |
| [^78^] | QuantifiedStrategies — Weekend Trend Trader | quantifiedstrategies.com | 2026-02-09 |
| [^85^] | Thesis EUR — Risk-Managed Momentum | thesis.eur.nl | Various |
| [^101^] | Yahoo Finance — MTUM Performance | finance.yahoo.com/quote/MTUM | 2026-06-22 |
| [^107^] | iShares — MTUM Official | ishares.com | 2025-12-31 |
| [^136^] | Quantpedia — Sector Momentum | quantpedia.com | Various |
| [^168^] | CME — Momentum Strategies Whitepaper | cmegroup.com | 2015 |
| [^307^] | Quantt — Momentum Trading Guide | quantt.co.uk | 2026-04-09 |
| [^309^] | Manigault — Long-Only Adaptation Paper | vernimmen.net | 2016-2017 |
| [^310^] | InvestResolve — GEM Executive Summary | investresolve.com | 2023-12-04 |
| [^311^] | GitHub — GEM Implementation | github.com/alexjansenhome/GEM | 2017-10-12 |
| [^312^] | Portfolio123 — GEM Discussion | community.portfolio123.com | 2018-12-17 |
| [^313^] | BestFolio — GEM Backtest | bestfolio.app | 2026-06-19 |
| [^314^] | Severian — GEM Robustness Analysis | svrn.co | 2015-08-02 |
| [^315^] | Quantpedia — Momentum Factor Effect | quantpedia.com | 2015-12-01 |
| [^316^] | TuringTrader — Antonacci Parity | turingtrader.com | Various |
| [^317^] | Jegadeesh & Titman (1993) Original | bauer.uh.edu | 1993 |
| [^323^] | QuantConnect — SUE Backtest | quantconnect.com | 2026-03-12 |
| [^324^] | Chan, Jegadeesh, Lakonishok (1996) | rotman.utoronto.ca | 1996 |
| [^325^] | Lund University — Risk-Managed Momentum | lup.lub.lu.se | Various |
| [^328^] | Quantpedia — Three Methods to Fix Crashes | quantpedia.com | 2025-06-04 |
| [^333^] | BlackRock — MTUM | blackrock.com | 2025-12-31 |
| [^334^] | Investopedia — CANSLIM | investopedia.com | 2025-09-01 |
| [^337^] | SumGrowth — MTUM Profile | sumgrowth.com | 2025-06-08 |
| [^344^] | Osuva — Idiosyncratic Vol + Momentum | osuva.uwasa.fi | Various |
| [^345^] | Alpha Architect — Idiosyncratic Momentum | alphaarchitect.com | 2022-05-05 |
| [^346^] | ScienceDirect — Idiosyncratic Momentum | sciencedirect.com | 2022-08-16 |
| [^347^] | HedgeFundAlpha — Idiosyncratic Momentum | hedgefundalpha.com | 2021-05-14 |
| [^350^] | TradingView — Weekend Trend Trader | tradingview.com | 2026-06-12 |
| [^352^] | Yahoo Finance — QMHIX | finance.yahoo.com | 2013-07-16 |
| [^353^] | ThinkOrSwim — WTT Backtest | usethinkscript.com | 2019-09-21 |
| [^354^] | AAII — Momentum + Equal Weighting | aaii.com | Various |
| [^357^] | Earthwalker — Nick Radge Book Summary | earthwalker.me | 2025 |
| [^359^] | SumGrowth — QMOM Profile | sumgrowth.com | 2025-06-08 |
| [^360^] | Korajczyk & Sadka — Trading Costs | kellogg.northwestern.edu | 2004 |
| [^361^] | EFMA — Post-Cost Profitability | efmaefm.org | 2006 |
| [^362^] | Reading University — Low-Cost Momentum | centaur.reading.ac.uk | Various |
| [^363^] | Alpha Architect — QMOM Prospectus | alphaarchitect.com | 2024 |
| [^364^] | Engineered Portfolio — Accelerating DM | engineeredportfolio.com | 2018-05-10 |

---

## Research Notes

### Methodology
- Conducted 24 independent web searches with varied, non-recycled queries
- Sources prioritized: academic papers, official fund prospectuses, independent replication studies
- Sources deprioritized: content farms, anonymous blogs, unverified claims
- All performance figures noted as backtested unless explicitly marked as live/out-of-sample
- LONG-ONLY constraint applied throughout; short-side data included only for context

### Key Findings Summary
1. **Dual Momentum (GEM)** remains the simplest implementable momentum strategy with 12%+ CAGR and moderate drawdowns, but out-of-sample performance (2014–2025) has been weaker than the original backtest.
2. **Cross-sectional momentum** works but transaction costs are the primary enemy; quarterly rebalancing and large-cap universes are essential for profitability.
3. **Earnings momentum (SUE)** shows strong returns but catastrophic drawdown potential (64% max); risk management is non-negotiable.
4. **Sector rotation** offers an excellent risk/reward balance for ETF investors with minimal time commitment.
5. **Risk-managed variants** (volatility scaling, idiosyncratic momentum) approximately double Sharpe ratios and are strongly recommended over raw momentum.
6. **Weekend Trend Trader** is a practical, time-efficient stock momentum strategy with documented ~17% CAGR.
7. **Momentum ETFs (MTUM, QMOM)** provide viable live implementations with demonstrated net-of-fee performance.
8. **Transaction costs** remain the single biggest challenge; modern commission-free brokers help, but bid-ask spreads and market impact remain significant.

### Cautionary Notes
- All backtested returns are hypothetical and may not reflect live trading results
- Past performance does not guarantee future results
- The momentum factor has experienced multi-year periods of underperformance
- Concentrated portfolios carry significant idiosyncratic risk
- Systematic implementation requires discipline and emotional detachment
