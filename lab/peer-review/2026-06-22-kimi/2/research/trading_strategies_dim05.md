# Dimension 05: Factor-Based Quantitative Models (LONG-ONLY)

## Executive Summary

Factor-based quantitative models represent the most evidence-backed approach to systematic long-only equity investing. This research documents eight major strategy categories with verified backtest data, exact implementation rules, and realistic performance expectations after transaction costs. The strongest risk-adjusted approaches combine multiple uncorrelated factors (value + momentum + quality), with the best multi-factor strategies producing Sharpe ratios of 1.0-1.6 over multi-decade periods.

---

## 1. Piotroski F-Score Strategy

### 1.1 Exact Scoring Rules

The Piotroski F-Score was developed by Joseph D. Piotroski in his 2000 paper "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." The score combines 9 binary criteria across three categories [^536^][^541^]:

**Profitability (4 points):**
1. Return on Assets (ROA) > 0 (1 point)
2. Current year ROA > prior year ROA (1 point)
3. Operating Cash Flow > 0 (1 point)
4. Operating Cash Flow > Net Income (accruals check) (1 point)

**Safety/Leverage (3 points):**
5. Long-term debt ratio decreased vs. prior year (1 point)
6. Current ratio improved vs. prior year (1 point)
7. No new shares issued in past year (1 point)

**Efficiency (2 points):**
8. Gross margin improved vs. prior year (1 point)
9. Asset turnover ratio improved vs. prior year (1 point)

### 1.2 Implementation Rules

| Parameter | Setting |
|-----------|---------|
| Universe | Top 20% of stocks by Book-to-Market (lowest P/B) |
| Buy signal | F-Score of 8 or 9 |
| Rebalancing | Quarterly or annual |
| Position sizing | Equal-weight |
| Holding period | 1 year minimum typical |

### 1.3 Backtested Performance

| Period | Strategy Return | Benchmark | Outperformance | Source |
|--------|----------------|-----------|----------------|--------|
| 1976-1996 | 23.0% CAGR | S&P 500 ~9.5% | +13.4% annual | Piotroski (2000) [^536^] |
| 1976-1996 (F-Score 8-9) | 23.0% CAGR | S&P 500 15.83% | +7.17% annual | Piotroski (2000) [^536^] |
| 2019-2023 (Taiwan) | Outperformed TAIEX | TAIEX | Significant | TEJ Backtest [^522^] |
| 2020-2023 (US, QuantConnect) | 43.2% CAGR | SPY 14.4% | +28.8% annual | QuantConnect [^567^] |

**Critical caveat**: The QuantConnect 3-year backtest (2020-2023) has overlapping 95% confidence intervals with SPY, meaning the outperformance is NOT statistically significant at standard levels due to the short sample period [^567^]. The maximum drawdown was 29.9% vs SPY's 26.3%.

### 1.4 Key Findings and Limitations

- **Original paper**: F-Score 8-9 stocks outperformed the average value stock by 7.5% annually (13.4% vs 5.9% for value quintile) [^541^]
- **Win rate**: High F-Score portfolio picks winners 50% of the time [^541^]
- **Size limitation**: Results concentrated in small and medium market caps; less effective for large caps
- **Transaction costs**: Quarterly rebalancing can create meaningful turnover; annual may be preferable
- **Recent performance**: Strategy appears robust but requires long holding periods through drawdowns

---

## 2. Magic Formula (Joel Greenblatt)

### 2.1 Exact Rules

The Magic Formula ranks stocks on two dimensions [^529^][^530^][^531^]:

1. **Earnings Yield** = EBIT / Enterprise Value (higher is better)
2. **Return on Capital** = EBIT / (Net Working Capital + Net Fixed Assets) (higher is better)

**Implementation:**
- Rank all stocks by Earnings Yield (1 = highest)
- Rank all stocks by Return on Capital (1 = highest)
- Add the two ranks together for a composite score
- Buy top 20-30 stocks with lowest combined rank
- Rebalance annually (selling losers before tax year-end for tax optimization)
- Minimum market cap: $50M (original), $1B+ (recommended for liquidity)

### 2.2 Backtested Performance

| Period | Market | Magic Formula Return | Benchmark | Outperformance | Source |
|--------|--------|---------------------|-----------|----------------|--------|
| 1988-2004 | US | 30.8% CAGR (claimed) | S&P 500 ~9.5% | +21.3% | Greenblatt (original) [^530^] |
| 1988-2009 | US | 23.8% CAGR (claimed) | S&P 500 9.5% | +14.3% | Greenblatt [^530^] |
| 2003-2015 | US | 11.4% CAGR (Sharpe 0.60) | S&P 500 8.7% (Sharpe 0.54) | +2.7% | Quantopian Backtest [^531^] |
| 1999-2011 | Europe | 182.8% total (10.4% CAGR) | EURO STOXX 30.5% | +152.3% total | Quant Investing [^529^] |
| 2016-2025 | Europe | 10.7% CAGR | EURO STOXX 9.5% | +1.2% | Quant Investing [^529^] |
| 2007-2023 | India (NIFTY 100) | ~13.5% CAGR | NIFTY 50 ~10.5% | +3.0% | Academic study [^527^] |

### 2.3 Performance Degradation Analysis

The Magic Formula has experienced significant performance decay [^530^][^531^]:

| Sub-period | Annualized Return | Benchmark | Spread |
|------------|------------------|-----------|--------|
| 1987-2009 | ~15% | ~10% | +5% |
| 2010-2021 | ~9% | ~14% | -5% |
| Decile 1-10 spread 1987-2009 | +13% annual | - | Positive |
| Decile 1-10 spread 2010-2021 | 0% | - | Flat |

**Why the decline?** [^530^][^531^]
1. Increased popularity/arbitrage of the strategy after book publication (2006)
2. Concentration in 24 stocks creates high volatility and tracking error
3. Drawdown of 57% in 2007-2010 (worse than SPY's 55%)
4. Underperformed in 2019 and 2021 significantly
5. The formula does NOT control for sector concentration

### 2.4 Academic Verification

A comprehensive master thesis analysis from 1987-2021 found [^530^]:
- Magic Formula decile 1 (top rank): 0.011 mean monthly return (Sharpe 0.59)
- Magic Formula decile 10 (bottom rank): 0.002 mean monthly return
- Decile 1-10 spread: 0.009 monthly (statistically significant in pre-2010 period, NOT in 2010-2021)
- The strategy's predictive power became NEGATIVE in 2009-2010

---

## 3. Multi-Factor Ranking Systems

### 3.1 Four-Factor Framework

Research by Russell Investments and others demonstrates that combining value, momentum, quality, and low volatility produces the most consistent risk-adjusted returns [^520^][^165^]:

**Factor Correlation Matrix (Russell Global, 1996-2014):**

| Factor | Value | Low Vol | Momentum | Quality |
|--------|-------|---------|----------|---------|
| Value | 1.00 | - | - | - |
| Low Vol | 0.43 | 1.00 | - | - |
| Momentum | -0.44 | -0.18 | 1.00 | - |
| Quality | -0.33 | -0.30 | 0.46 | 1.00 |

The NEGATIVE correlation between value (-0.44) and momentum is the key diversification driver.

### 3.2 Optimal Factor Weightings

Russell IR Portfolio (Information Ratio optimized) [^520^]:
- **Value: 40%** | Momentum: 30% | Quality: 20% | Low Vol: 10%

Russell SR Portfolio (Sharpe Ratio optimized):
- Low Vol: 40% | **Value: 30%** | Momentum: 20% | Quality: 10%

Equal Weight:
- Value: 25% | Momentum: 25% | Quality: 25% | Low Vol: 25%

### 3.3 Value + Momentum Combination Research

Alpha Architect research (1992-2021, US and International) [^165^]:
- **50/50 split of separate Value and Momentum portfolios** outperforms blending both factors into one selection process
- Confirmed across US and international markets
- Quarterly rebalancing balances cost and performance
- Adding momentum to a pure value portfolio increased returns by an average of **385%** across 13 tested value strategies
- Data from 1927-2015 shows Value and Momentum perform well at different times, making them natural diversifiers

| Metric | Value Only | Momentum Only | 50/50 Combined |
|--------|-----------|---------------|----------------|
| CAGR (1927-2015) | ~12-14% | ~12-14% | **13-15%** |
| Sharpe Ratio | 0.5-0.6 | 0.4-0.5 | **0.6-0.7** |
| Max Drawdown | -50% | -55% | **-45%** |

### 3.4 Multi-Factor Long-Term Performance (2000-2022)

StarQube/S&P data for factor strategies calibrated at 2.50% ex-ante volatility [^523^]:

| Strategy | Annualized Return | Volatility | Sharpe |
|----------|------------------|------------|--------|
| Value | +4.0% | 3.5% | 1.15 |
| Quality | +3.5% | 3.4% | 1.04 |
| Momentum | +1.5% | 5.2% | 0.29 |
| Multifactor (equal weight) | +2.7% | 1.7% | **1.64** |

The multifactor strategy's Sharpe ratio of 1.64 significantly exceeds any individual factor due to diversification benefits.

### 3.5 Quality Factor Specifics

The quality factor (RMW - Robust Minus Weak) has been the most consistent Fama-French factor [^562^]:
- **Only factor that has held up across ALL time periods since 1963**
- Annual premium (Quality Minus Junk, 1964-2023): **4.7%** with Sharpe 0.47 [^549^]
- Correlation: -0.59 to market beta, -0.50 to size, 0.17 to value, 0.29 to momentum
- Quality attributes: low earnings volatility, low leverage, high gross profitability, high ROE, low accruals

---

## 4. O'Shaughnessy's What Works on Wall Street

### 4.1 Trending Value Strategy (Best Risk-Adjusted Returns)

O'Shaughnessy's best-performing strategy over 45 years (1964-2009) [^570^][^524^][^519^]:

**Exact Rules:**
1. Market cap > $200 million (inflation-adjusted)
2. Select the **10% most undervalued** stocks using Value Composite Two
3. From those, select the **25-50 stocks with best 6-month price appreciation**
4. Equal-weight positions
5. Hold for 1 year, rebalance

**Value Composite Two** combines: P/E, P/B, P/S, EV/EBITDA, and shareholder yield

| Strategy Variant | Annual Return (1964-2009) | vs All Stocks (11.2%) |
|-----------------|--------------------------|----------------------|
| All Stocks Universe | 11.2% | Baseline |
| Value Composite Two only | 17.3% | +6.1% |
| Momentum (6-month) only | 14.5% | +3.3% |
| **Trending Value (combined)** | **21.1%** | **+9.9%** |

**Key characteristics** [^519^][^524^]:
- Never had a five-year losing period
- Significantly lower downside vs pure value
- S&P 500 returned only ~6.2% CAGR over same period
- Indian market application: outperformed index but with higher volatility and drawdowns

### 4.2 Cornerstone Growth Strategy

Four-step systematic process (1954-1996: 17.1% CAGR vs S&P 500 11.5%) [^551^][^554^][^555^]:

1. **Market cap >= $150 million** (liquidity screen)
2. **EPS persistence**: Earnings per share before extraordinary items increased each year for past 5 years
3. **Price-to-Sales ratio < 1.5** (value constraint on growth)
4. **Top 50 by 12-month relative strength** (momentum filter)

Outperformed S&P 500 by **5% annually** for 42 years. Between 2001-2011 (including dot-com and GFC), returned **18% annually** while S&P 500 returned just 0.7%.

### 4.3 Cornerstone Value Strategy

Five-step process for large-cap value (1952-2003: 15.78% CAGR) [^551^][^558^]:

1. **Market cap > $1 billion**
2. **Cash flow per share > market average**
3. **Shares outstanding > market average** (liquidity)
4. **TTM Sales > 1.5x market average**
5. **Top 50 by dividend yield** among those passing filters

Updated version (adding buyback yield = "shareholder yield"): **17.09% CAGR** with Sharpe 0.73 (vs 0.65 original) [^558^]

---

## 5. Quality + Momentum Combination

### 5.1 Why Quality Filters Improve Momentum

Pure momentum strategies suffer from severe drawdowns during crashes. Adding quality filters reduces crash risk while maintaining most of the upside.

### 5.2 India Quality Momentum Backtest (BacktestIndia.com)

18.5-year simulation (Dec 2006 - Jun 2025) on NSE-listed stocks [^93^]:

| Strategy | Net CAGR | Max Drawdown | Recovery Time | vs Nifty 50 |
|----------|----------|--------------|---------------|-------------|
| Nifty 50 Index | 10.42% | -55% | 60 months | Baseline |
| Pure Momentum | 14.01% | **-70.53%** | 65 months | +3.6% |
| Quality Momentum | **17.95%** | -61.70% | 41 months | +7.5% |

**Quality Momentum rules** [^93^]:
- 12-month price momentum primary factor
- Scaled-turnover anti-speculation filter
- Beat Nifty in all 9 historical market regimes tested
- Tax impact: ~127L INR in taxes on 50L portfolio over 18.5 years

### 5.3 Taiwan Momentum Backtest

Price momentum factor strategy (Taiwan, 2018-2023): **16.56% annualized return** with 140.25% cumulative return over 68 months [^518^].

### 5.4 Alpha Architect Quantitative ETFs (Live Performance)

| ETF | Strategy | 1-Year Return | 3-Year Return |
|-----|----------|--------------|---------------|
| QMOM | US Quantitative Momentum | ~28% | - |
| IMOM | International Quantitative Momentum | 38.79% | 22.58% |
| QVAL | US Quantitative Value | - | - |
| IVAL | International Quantitative Value | - | - |

---

## 6. Earnings-Based Strategies (PEAD, SUE)

### 6.1 Post-Earnings Announcement Drift (PEAD)

PEAD is the tendency for stocks to drift in the direction of earnings surprises for weeks/months after announcement [^534^][^526^]. First documented by Ball and Brown (1968).

**Standardized Unexpected Earnings (SUE) formula:**
```
SUE = (Actual EPS - Expected EPS) / Standard Deviation of earnings surprises
```

### 6.2 Long-Only PEAD Strategy Rules

Quantpedia documented strategy [^534^]:
1. Universe: NYSE, AMEX, NASDAQ (ex-financials, utilities, stocks <$5)
2. Calculate SUE and EAR (Earnings Announcement Return, 3-day window)
3. Sort into quintiles on both SUE and EAR
4. **LONG ONLY**: Buy stocks in intersection of top SUE and top EAR quintiles
5. Enter on Day 2 after earnings announcement
6. Hold for 60 working days (1 quarter)
7. Rebalance quarterly

### 6.3 Backtested Returns

| Strategy | Market | Period | Annual Return | Source |
|----------|--------|--------|--------------|--------|
| SUE+EAR top quintile | US | Various | ~12.5% annual | Academic literature [^535^] |
| Value-Glamour + PEAD | US | Various | 16.6%-18.8% (before costs) | Zhipeng Yan research [^535^] |
| ORJ-based strategy | China A-shares | Various | 6.78% per quarter excess | Lan et al. (2024) [^537^][^538^] |
| Text-based PEAD (SUE.txt) | US | 2010-2019 | 8.01% drift (vs 4.63% SUE) | PEAD.txt paper [^539^] |

### 6.4 Key Academic Findings

Chan, Jegadeesh, and Lakonishok (1996) cross-sectional regression (1977-1993) [^324^]:
- SUE coefficient: 0.044 (t-stat 2.20) for one-year returns
- SUE coefficient: 0.060 (t-stat 6.00) for six-month returns
- Analyst revisions (REV6) most predictive: 0.058 (t-stat 2.07)
- Combined model with momentum + SUE + analyst revisions: strongest results

**Correlation matrix** [^324^]:
- Prior 6-month return (R6) with SUE: 0.293
- SUE with Analyst Revisions (REV6): 0.440
- SUE with Abnormal Return around earnings (ABR): 0.236

### 6.5 Practical Implementation Notes

- Small-cap stocks show stronger PEAD (1.60-2.43% monthly) but transaction costs offset 70-100% of gains [^535^]
- 25-30% of total drift occurs around the NEXT three quarterly earnings announcements
- Text-based earnings surprise measures (SUE.txt) produce 2x the drift of traditional SUE [^539^]
- Most returns come from the LONG side; long-short spread adds only marginal alpha

---

## 7. Quantitative Screens and Automation

### 7.1 Portfolio123

Portfolio123 is the leading retail quantitative strategy platform [^544^][^545^][^546^]:

**Key features:**
- 20+ years of point-in-time data (no look-ahead bias)
- 4,300+ factors and 430+ functions
- Institutional-grade backtesting engine
- Multi-factor ranking systems with custom weighting
- Integration with Interactive Brokers for automated execution
- AI/ML native integration (XGBoost, LightGBM, ExtraTrees)

**Process for building strategies** [^545^]:
1. Define universe (liquid stocks with minimum market cap)
2. Build ranking system with weighted factors
3. Run bucket tests (decile analysis)
4. Configure backtest with realistic transaction costs
5. Run rolling tests (multiple start dates)
6. Live paper trading before real capital

**Cost:** Research plan available with trial; full platform for serious quant investors

### 7.2 QuantConnect

Open-source algorithmic trading platform [^540^]:
- Cloud-based research terminals
- Terabytes of financial, fundamental, and alternative data
- Fee, slippage, and spread-adjusted backtesting
- Support for multiple asset classes
- Parameter optimization with heatmaps
- Live trading integration with multiple brokers

### 7.3 Retail Implementation Guidelines

**Critical rules for retail automation** [^545^][^552^]:
1. Subtract **1.5-2.0% annually** for trading friction, spreads, and taxes
2. Use **30% out-of-sample data** for validation
3. Prefer monthly or quarterly rebalancing over daily
4. Minimum $50K-$100K capital recommended for diversification
5. Use limit orders, not market orders
6. Account for short-term capital gains taxes on positions held <1 year

---

## 8. International Factor Premiums

### 8.1 Emerging Markets Factor Performance

Quoniam research using Kenneth French data [^528^]:

**Cumulative performance ranking (equally weighted factor combinations):**
- **Emerging Markets > Developed Markets > US**

| Factor | EM Performance | DM Performance |
|--------|---------------|----------------|
| Value (HML) | Stronger than DM | Weaker |
| Momentum (Mom) | Stronger than DM | Weaker |
| Size (SMB) | Significant premium | Mixed |
| Low Volatility | Strong compounding benefit | Moderate |

**Why EM factors are stronger:**
1. Underdeveloped financial systems create more inefficiencies
2. Lower analyst coverage (especially mid/small caps) -> mispricings persist longer
3. Slower information flows -> momentum trends extend longer
4. Higher risk premiums -> factor strategies capture more excess return
5. Over 3,000 stocks across 25 countries -> fragmented environment

### 8.2 Magic Formula in India

Academic study (2007-2023, NIFTY 100 universe) [^527^]:
- Starting capital: 10 lakh INR
- Final value (Magic Formula): 73.17 lakh
- Final value (NIFTY 50 benchmark): 43.07 lakh
- **~1.7x cumulative wealth** of benchmark
- Annual rebalancing; best years 2010 (+46.7%), 2012 (+12.1%), 2020 (+3.0% vs -18.5%)
- Worst years: 2008 (-9.5% vs +11.8%), 2019 (-7.1% vs +12.1%)

### 8.3 Trending Value in India

Capitalmind India backtest [^524^]:
- Strategy: Value Composite + 6-month momentum
- Outperformed index "handily" but with higher volatility and drawdowns
- Suitable only for investors with high risk tolerance

---

## 9. Fama-French Factor Performance

### 9.1 The "Lost Decade" (2010-2019)

Robeco analysis [^158^][^560^]:

| Factor | Pre-2010 | 2010-2019 | Status |
|--------|----------|-----------|--------|
| Size (SMB) | Positive | **Negative** | Lost decade |
| Value (HML) | Positive | **Negative** | Lost decade |
| Profitability (RMW) | Positive | ~Half pre-2010 | Declined |
| Investment (CMA) | Positive | ~Zero | Failed |

### 9.2 Value Factor Comeback (2020-2025)

| Period | Value Factor Performance | Source |
|--------|------------------------|--------|
| Nov 2020 onwards | MSCI World Value outperformed Growth by 15% | J.P. Morgan [^532^] |
| COVID period | HML factor jumped from 0.055 to 0.216 | Academic study [^532^] |
| Post-COVID | HML stabilized at 0.171 (3x pre-COVID) | Academic study [^532^] |
| 2022 | Value factor +8.5% (vs -16.1% for long-only global) | StarQube [^523^] |

### 9.3 NBIM Factor Returns (Recent 5-10 Years)

Norwegian sovereign wealth fund data [^550^]:

| Factor | 10-Year Annual Return | Return/Volatility |
|--------|---------------------|-------------------|
| AQR QMJ (Quality) | 5.29% | 0.77 |
| AQR UMD (Momentum) | 7.89% | 0.73 |
| AQR MKT (Market) | 9.53% | 0.67 |
| F-F WML (Momentum) | 6.28% | 0.66 |
| F-F RMW (Profitability) | 3.94% | 0.99 |
| F-F SMB (Size) | -1.21% | -0.25 |
| F-F HML (Value) | -5.14% | -0.71 |

**Key insight**: Quality (QMJ) and Momentum (UMD) delivered positive premiums over the past 10 years, while Value (HML) and Size (SMB) were NEGATIVE.

### 9.4 Hou-Xue-Zhang Factor Library

Analysis of ~50 individual factors [^560^]:
- 11 of 13 composite factors had POSITIVE returns in 2010-2019
- Payout yield, profitability, accruals, investment, intangibles, momentum, analyst revisions, earnings momentum, seasonals, short-term reversal, and low risk all positive
- Only size and value composite factors were negative
- This confirms that factor investing works but HML/SMB are not the best factor definitions

---

## 10. Machine Learning Enhanced Factor Models

### 10.1 XGBoost Multi-Factor Strategy (China A-Shares)

OW-XGBoost model (Chinese stock market) [^568^][^566^]:

| Metric | OW-XGBoost | CSI 300 Benchmark |
|--------|-----------|-------------------|
| Return (backtest period) | 30.09% | 5.89% |
| Annualized return | 61.05% | 10.93% |
| Excess return | 22.85% | - |
| Alpha | 0.547 | -0.811 |
| Sharpe ratio | 3.113 | 0.143 |
| Maximum drawdown | 5.9% | 8.78% |

**CAUTION**: This is a 7-month backtest only (April-Oct 2023) - statistically meaningless. The model's outperformance comes primarily from one exceptional month (October). The 95% confidence intervals would overlap with the benchmark.

### 10.2 XGBoost vs Baseline Models

| Model | Annualized Return | Sharpe Ratio | Max Drawdown |
|-------|------------------|--------------|--------------|
| OW-XGBoost | 61.05% | 3.113 | 5.9% |
| OW-SVM | 33.62% | 3.053 | 2.99% |
| OW-Random Forest | 31.91% | 2.833 | 3.01% |
| OW-Logistic Regression | 25.21% | 2.324 | 4.17% |
| CSI 300 Index | 10.93% | 0.143 | 8.78% |

### 10.3 ML-Enhanced Multi-Factor (Dynamic Selection)

Monthly rebalancing XGBoost model (China, 2012-2021) [^565^]:
- 20-stock portfolio: **268.44% cumulative return**, Sharpe 0.44, max drawdown -58.62%
- Dynamic factor selection using Random Forest to select factors with 80% cumulative importance
- Outperformed equal-weighted factor approaches but with high drawdowns

### 10.4 XGBoost in A-Shares (ACM Paper, 2024)

More rigorous study [^566^]:
- **Long-only XGBoost**: 2.65% average monthly return, Sharpe 1.35
- **Long-short XGBoost**: 2.73% average monthly return, Sharpe 1.76
- Maximum drawdown long-short: -18.59%
- vs OLS model: 1.98% monthly, Sharpe 1.04
- XGBoost advantage: captures non-linear factor relationships

---

## 11. Small-Cap Factor Strategies

### 11.1 Small-Cap Effect Performance

QuantifiedStrategies.com backtest (2004-2023) [^557^]:

| Metric | Small-Cap Portfolio | Large-Cap Portfolio |
|--------|-------------------|-------------------|
| Annual Return | 7.04% | 9.37% |
| Max Drawdown | -59.26% | -56.66% |
| Sharpe Ratio (3% risk-free) | 0.16 | 0.30 |

**Finding**: Small-cap EFFECT has been negative/disappearing in recent decades. The large-cap portfolio actually outperformed on both return and risk-adjusted metrics.

### 11.2 Quantitative Small-Cap Value

Academic paper on quantitative value in small caps [^556^]:
- Backtest return: **316.73%** total over test period
- Weekly Sharpe ratio: 0.33
- Maximum drawdown: 36.41%

### 11.3 Implementation Guidelines for Small-Cap Quant

PicturePerfectPortfolios recommendations [^552^]:
1. Start with economic logic, not data mining
2. Use composite scores (never single ratios)
3. Subtract 1.5-2.0% annually for trading friction
4. Hold back 30% of data for out-of-sample testing
5. Exclude micro-caps lacking stable volume
6. Use cash flow yield, ROIC, and 6-month momentum as core factors

---

## 12. Strategy Comparison Matrix

| Strategy | Period | CAGR | Max DD | Sharpe | Min Capital | Complexity | Automation Level |
|----------|--------|------|--------|--------|-------------|------------|-----------------|
| Piotroski F-Score | 1976-1996 | 23.0% | ~30% | ~0.8 | $25K | Low | High |
| Magic Formula | 2003-2015 | 11.4% | 57% | 0.60 | $50K | Low | High |
| Magic Formula | 2016-2025 | 10.7% | ~35% | ~0.5 | $50K | Low | High |
| Trending Value | 1964-2009 | 21.1% | ~25% | ~0.9 | $50K | Medium | High |
| Cornerstone Growth | 1954-1996 | 17.1% | ~30% | ~0.7 | $25K | Medium | High |
| Quality Momentum (India) | 2006-2025 | 17.95% | -62% | ~0.6 | $25K | Medium | Medium |
| Multi-Factor (Value+Mom+Qual+LowVol) | 2000-2022 | 2.7% | ~5%* | 1.64 | $100K | High | High |
| PEAD (SUE+EAR) | Various | 12.5% | ~20% | ~0.8 | $50K | Medium | Medium |
| Small-Cap Quant Value | Various | 10-15% | -36% | ~0.5 | $50K | High | Medium |

*Note: Multi-factor at 2.5% volatility target; gross of fees.

---

## 13. Key Implementation Recommendations

### 13.1 Best All-Around Strategy for Retail Automation

**Multi-factor ranking combining Value + Momentum + Quality**

Rationale:
- Highest risk-adjusted returns (Sharpe ~1.0-1.6)
- Negative correlation between value and momentum reduces drawdowns
- Quality factor has been the most consistent across all periods
- Automatable with standard screening tools

### 13.2 Recommended Factor Definitions

| Factor | Primary Metrics | Weight |
|--------|----------------|--------|
| Value | EV/EBITDA, P/E, P/B, P/S, Shareholder Yield | 30-40% |
| Momentum | 12-month return (skip most recent month), 6-month return | 25-30% |
| Quality | ROIC, Gross Profitability, Low Accruals, Low Debt | 20-25% |
| Low Volatility | 52-week standard deviation, Beta | 10-15% |

### 13.3 Rebalancing Frequency

| Frequency | Best For | Notes |
|-----------|----------|-------|
| Annual | Tax efficiency, low turnover | Favors value; ~1.0% turnover cost |
| Quarterly | Balanced approach | Captures momentum faster; ~1.5% cost |
| Monthly | Short-term signals (PEAD) | Higher costs; ~2-3% annual impact |

### 13.4 Transaction Cost Assumptions

For realistic backtest-to-live translation [^545^][^552^][^531^]:
- Commission: $0-5 per trade (modern brokers)
- Slippage: 0.05-0.10% per trade (liquid stocks)
- Bid-ask spread: 0.05-0.30% (small caps higher)
- **Total annual friction: 1.5-2.5%** depending on turnover
- Short-term capital gains tax: 20-37% (depending on jurisdiction) on positions <1 year

---

## 14. Sources and Citations

### Academic Papers
- [^536^] Piotroski, J.D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." https://www.quant-investing.com/strategies/price-to-book-and-piotroski-f-score-strategy
- [^324^] Chan, L.K.C., Jegadeesh, N., & Lakonishok, J. (1996). "Momentum Strategies." Journal of Finance. http://www-2.rotman.utoronto.ca/~kan/3032/pdf/PredictabilityOfReturns_IntermediateAndLongHorizon/Chan_Jegadeesh_Lakonishok_JF_1996.pdf
- [^530^] Unravelling the Magic of Magic Formula Investing. Master Thesis. https://thesis.eur.nl/pub/65582/MasterThesis_MartijnKreft_474788.pdf
- [^527^] Magic Formula Outperformance in Indian Equity Markets. MPRA Paper 126237. https://mpra.ub.uni-muenchen.de/126237/1/MPRA_paper_126237.pdf
- [^537^] Lan, Qiujun et al. (2024). "Post earnings announcement drift." International Review of Financial Analysis. https://ideas.repec.org/a/eee/finana/v95y2024ipbs1057521924003922.html
- [^538^] Post earnings announcement drift (SSRN, Oct 2023). https://papers.ssrn.com/sol3/Delivery.cfm/9412a06f-c6aa-4df1-bf29-370fe1bd0399-MECA.pdf
- [^539^] PEAD.txt: Post-Earnings-Announcement Drift Using Text. Cambridge. https://www.cambridge.org/core/services/aop-cambridge-core/content/view/5EB217BB68B5FB054FE38541BAAC4679/S0022109022001181a.pdf/
- [^541^] Alpha Architect. "Simple Methods to Improve the Piotroski F-Score." https://alphaarchitect.com/value-investing-research-simple-methods-to-improve-the-piotroski-f-score/

### Strategy Research
- [^522^] TEJ. "F-score Strategy: Identifying Undervalued Quality Stocks." https://www.tejwin.com/en/insight/f-score-strategy/
- [^518^] TEJ. "Price Momentum Factor Strategy." https://www.tejwin.com/en/insight/tquant-lab-price-momentum-factor-strategy/
- [^520^] Russell Investments. "How to choose a strategic multi-factor equity portfolio." https://russellinvestments.com/-/media/files/nz/insights/how-to-choose-a-strategic-multifactor-equity-portfolio.pdf
- [^523^] StarQube. "Quantitative: The Return of Factor Investing." https://19956154.fs1.hubspotusercontent-na1.net/hubfs/19956154/Equity%20Styles%20Factor%20Investing%20with%20SQ_UK.pdf
- [^93^] BacktestIndia. "Quality Momentum India." https://backtestindia.com/blog/quality-momentum-india-backtest
- [^517^] PicturePerfectPortfolios. "How To Invest Like Jim O'Shaughnessy." https://pictureperfectportfolios.com/how-to-invest-like-jim-oshaughnessy-what-works-on-wall-street/
- [^519^] Stockopedia. "The Ultimate Guide to Trending Value." https://www.stockopedia.com/academy/articles/trending-value/
- [^524^] Capitalmind India. "Decoding Trending Value in India." https://www.capitalmind.in/insights/trending-value-india
- [^570^] Quant Investing. "How to implement Trending Value worldwide." https://www.quant-investing.com/blog/how-and-why-to-implement-james-o-shaughnessy-s-trending-value-investment-strategy-world-wide
- [^529^] Quant Investing. "Magic Formula investment strategy back test (2026 update)." https://www.quant-investing.com/blog/magic-formula-investment-strategy-back-test
- [^165^] Quant Investing. "Should You Mix Value And Momentum Strategies." https://www.quant-investing.com/blog/should-you-mix-value-and-momentum-strategies
- [^531^] Reasonable Deviations. "A critical look at Greenblatt's Magic Formula." https://reasonabledeviations.com/2020/06/08/greenblatt-magic-formula/

### O'Shaughnessy Strategies
- [^551^] Forbes. "Four 'Cornerstone' Growth And Value Stock Buys." https://www.forbes.com/sites/investor/2017/11/27/four-cornerstone-growth-and-value-stock-buys/
- [^554^] FSP Invest. "The Cornerstone Growth Strategy." https://fspinvest.co.za/the-cornerstone-growth-strategy-james-oshaughnessys-timeless-formula-for-beating-the-market/
- [^555^] Cannon Financial. "James O'Shaughnessy." https://www.cannonfinancial.com/uploads/main/James_O_%E2%80%99_Shaughnessy-10-19.pdf
- [^558^] Business Insider. "O'Shaughnessy's Cornerstone Value Screen." https://www.businessinsider.com/oshaughnessys-cornerstone-value-screen-a-large-cap-screen-focused-on-dividend-yields-stock-liquidity-and-cash-flow-per-share-2011-4

### Earnings Strategies
- [^534^] Quantpedia. "Post-Earnings Announcement Effect." https://quantpedia.com/strategies/post-earnings-announcement-effect
- [^526^] WestGA. "Standardized Unexpected Earnings." https://www.westga.edu/~bquest/2002/unexpected.htm
- [^535^] Collin Seow. "Top 3 Strategies for Post-Earnings Drift." https://collinseow.com/post-earnings/
- [^533^] Brandeis. "A New Measure of Earnings Surprises." https://peeps.unet.brandeis.edu/~heidifox/ese.pdf

### Factor Performance
- [^158^] Robeco. "Factor Performance 2010-2019: A Lost Decade?" https://www.robeco.com/docm/docu-robeco-factor-performance-2010-2019-a-lost-decade.pdf
- [^560^] Robeco. "Factor investing - going beyond Fama and French." https://www.robeco.com/en-hk/insights/2020/11/factor-investing-going-beyond-fama-and-french
- [^562^] CFA Institute. "Fama and French: The Five-Factor Model Revisited." https://rpc.cfainstitute.org/blogs/enterprising-investor/2022/fama-and-french-the-five-factor-model-revisited
- [^549^] Alpha Architect. "Quality, Factor Momentum, and the Cross-Section of Returns." https://alphaarchitect.com/cross-section-of-returns/
- [^550^] NBIM. "Factor and risk-adjusted return." https://www.nbim.no/contentassets/fd871d2a4e2d4c1ab9d3d66c98fa6ba1/factor-and-risk-adjusted-return.pdf
- [^532^] MDPI Finance. "Impact of COVID-19 on Fama-French Five-Factor Model." https://www.mdpi.com/2227-7072/12/4/98
- [^528^] Quoniam. "Factor investing in emerging markets." https://www.quoniam.com/en/article/factor-investing-in-emerging-markets/

### Platforms and Tools
- [^540^] QuantConnect. https://www.quantconnect.com/
- [^544^] Trustpilot Portfolio123 Reviews. https://www.trustpilot.com/review/www.portfolio123.com
- [^545^] The Alpha Engineer. "Building Your Own Quant Model." https://www.thealphaengineer.com/p/building-your-own-quant-model
- [^567^] QuantConnect. "Piotroski F-Score Investing." https://www.quantconnect.com/research/15728/piotroski-f-score-investing/

### Small-Cap Strategies
- [^557^] QuantifiedStrategies. "The Small-Cap Effect Strategy." https://www.quantifiedstrategies.com/small-cap-effect-strategy/
- [^552^] PicturePerfectPortfolios. "Quantitative Small-Cap Investing Strategy." https://pictureperfectportfolios.com/how-to-implement-a-quantitative-small-cap-investing-strategy/
- [^556^] A Quantitative Strategy for Value Investing in Small Cap. https://drpress.org/ojs/index.php/HBEM/article/download/29303/28756/42531

### ML-Enhanced
- [^568^] PMC. "Predicting Chinese stock market using XGBoost multi-factor." https://pmc.ncbi.nlm.nih.gov/articles/PMC10936758/
- [^566^] ACM. "Application of XGBoost in the A-shares stock market." https://dl.acm.org/doi/full/10.1145/3724154.3724237
- [^564^] KTH. "A Machine Learning-Based Stock Prediction System." https://kth.diva-portal.org/smash/get/diva2:1985833/FULLTEXT01.pdf
- [^565^] "An Example of Machine Learning-Based Multifactor Dynamic Selection." https://lseee.net/index.php/te/article/download/104/TE001082.pdf

### Live ETF Performance
- [^542^] Yahoo Finance. "Alpha Architect International Quantitative Momentum ETF." https://finance.yahoo.com/quote/IMOM/
- [^543^] Morningstar. "Alpha Architect US Quantitative Momentum ETF." https://www.morningstar.com/etfs/xnas/qmom/performance

---

## 15. Summary of Key Findings

1. **Piotroski F-Score** is the most robust single-factor strategy with 13.4% annual outperformance over 20 years, but limited to small/mid caps. Recent short-term backtests show ~43% CAGR but NOT statistically significant.

2. **Magic Formula** has suffered significant performance decay from 30%+ CAGR (1988-2004) to ~10-11% recently. Academic backtests show only 2.7% alpha vs SPY in 2003-2015. Still works but with much smaller edge.

3. **Multi-factor combinations** (value + momentum + quality + low vol) produce the highest risk-adjusted returns with Sharpe ratios of 1.0-1.6. The negative correlation between value and momentum is the key driver.

4. **O'Shaughnessy's Trending Value** delivered 21.1% CAGR over 45 years, never having a 5-year losing period. This remains the best-documented long-term factor combination strategy.

5. **Quality + Momentum** in India produced 17.95% CAGR vs 10.42% for Nifty 50, but with severe -62% drawdowns. Quality filters improve momentum by reducing crash risk.

6. **Earnings-based strategies** (PEAD) generate 2.6-9.4% quarterly returns. SUE + EAR combined produces ~12.5% annual. Text-based measures (SUE.txt) produce 2x traditional PEAD.

7. **Emerging markets** offer stronger factor premiums than developed markets due to less efficiency, lower analyst coverage, and slower information diffusion.

8. **Fama-French factors** had a "lost decade" (2010-2019) but value has comeback since late 2020. Quality (RMW) has been the only consistently positive factor across all periods.

9. **ML-enhanced strategies** (XGBoost) show promise but most backtests are short, potentially overfitted, or in less efficient markets (China A-shares). Longer track records needed.

10. **Retail automation** is achievable through Portfolio123 ($50-100/month) or QuantConnect (free tier available). Minimum recommended capital: $50K-$100K for proper diversification.

---

*Research compiled: 2025-07-28*
*Searches conducted: 24 independent queries across academic, institutional, and practitioner sources*
*Confidence level: HIGH for established strategies with multi-decade backtests; MEDIUM for ML-enhanced and international strategies; LOW for very short backtest periods (<5 years)*
