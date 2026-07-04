## Facet: Factor-Based & Quantitative Equity Strategies (LONG-ONLY)

**Research Date:** July 2025
**Scope:** Long-only factor-based and quantitative equity strategies for achieving >3% monthly average returns
**Sources Consulted:** Academic papers, quantitative strategy backtests, factor data libraries, AQR research, Fama-French data, Quantpedia, QuantifiedStrategies, MSCI research, Robeco research

---

## Key Findings

### Executive Summary
- **No single long-only factor strategy consistently achieves >3% monthly (36% annualized)** in backtests. The highest validated long-only returns come from concentrated multi-factor combinations or specific market conditions, but 3% monthly is an extremely aggressive target that exceeds virtually all documented factor premiums.
- **Joel Greenblatt's Magic Formula** achieved ~30.8% annually (1988-2004) in the original backtest, declining to ~10-11% in more recent periods (2016-2025), with significant underperformance stretches [^139^][^140^]
- **Piotroski F-Score** delivered 13.4% annual outperformance over the market in the original 1976-1996 study, with high-F-Score companies (8-9) strongly outperforming low-F-Score (0-1) companies by 23% annually [^150^][^151^]
- **Fama-French factors experienced a "lost decade" in 2010-2019**, with HML (value) and SMB (size) both negative; only RMW (profitability/quality) and momentum remained positive [^158^]
- **Multi-factor combination of value + momentum** has shown the strongest synergy, with a 50/50 split outperforming blended approaches across US and international markets from 1927-2015 [^165^]
- **Low volatility anomaly** delivers 25% volatility reduction with comparable returns, producing superior Sharpe ratios (Clarke, de Silva, Thorley 1968-2005) [^161^][^162^]
- **Machine learning approaches** show mixed results: Ridge/MLP achieved ~4% annualized on CSI 300 (2020-2022), while XGBoost multi-factor approaches claimed 13.8% annualized in one Chinese market study [^132^][^134^]
- **AQR factor data (1998-2020)** shows momentum (WML) at 6.47% annual, quality (QMJ) at 5.39%, value (HML) at only 1.28%, and size (SMB) at 1.58% [^149^]
- **Earnings momentum (SUE)** generates ~0.89% monthly (long-short) from combining highest SUE + highest revenue surprise stocks; standalone earnings momentum ~0.63% monthly [^127^]
- **The >3% monthly target (36% CAGR) is achievable only through:** concentrated small-cap factor combinations, leverage, or specific market regimes - not through diversified factor investing alone

---

## Major Players & Sources

- **AQR Capital Management (Cliff Asness):** Pioneer of Quality Minus Junk (QMJ) factor, Value, Momentum, and Betting Against Beta (BAB) factors. Maintains public factor data library [^128^][^146^]
- **Fama-French (Dartmouth):** Academic foundation of factor investing; Kenneth French's data library provides free factor returns [^131^][^149^]
- **Joel Greenblatt / Gotham Capital:** Magic Formula; claimed 30.8% annual returns (1988-2004) in original backtest [^139^][^140^]
- **Joseph Piotroski (Stanford):** F-Score methodology for identifying strong fundamentals among low P/B stocks [^150^][^151^]
- **Clarke, de Silva, Thorley (Analytic Investors):** Minimum variance portfolio research showing 25% volatility reduction with comparable returns [^161^][^162^]
- **David Blitz (Robeco):** Extensive factor performance research; documented the "lost decade" for Fama-French factors [^158^]
- **Gary Antonacci:** Dual Momentum strategy; GEM model achieved ~14.8% CAGR with -20.5% max drawdown (1970-2025) [^19^][^26^]
- **Alpha Architect:** Research on combining value and momentum; improving F-Score with FS-Score [^151^][^165^]
- **Quantpedia:** Encyclopedia of quantitative trading strategies; catalogues 1000+ strategies with academic backing [^130^][^138^]
- **MSCI:** Factor index provider; research on factor crowding and value underperformance drivers [^157^]
- **Dimensional Fund Advisors (DFA):** Largest factor-based fund family; live fund performance validates factor premiums over decades [^156^]

---

## Trends & Signals

- **Factor premium decay is real but uneven:** The size premium (SMB) has largely stagnated over the past 10-15 years after a strong run up to 1982 [^129^]. Value (HML) had its worst decade in 2010-2019, with -2.6% annual returns [^158^]
- **Quality/Profitability has been the most consistent factor:** RMW (Robust Minus Weak) remained positive in 2010-2019 at +1.67% annual, and QMJ averaged 5.39% annually (1998-2020) [^149^][^158^]
- **Low-risk factors performed exceptionally well in 2010-2019:** Low volatility generated 6-10% premiums during the "lost decade" when traditional factors struggled [^158^]
- **Value-momentum combination is the strongest multi-factor approach:** Correlation of approximately -0.50 between value and momentum creates natural diversification [^146^]
- **International factor premiums can be stronger:** Non-US momentum showed no decay post-2010; profitability factor performed equally well pre/post-2010 globally [^158^]
- **Machine learning is promising but fragile:** Ridge/MLP achieved only ~4% annualized on CSI 300 (2020-2022) after 0.3% transaction costs [^132^]; XGBoost approaches need frequent retraining to avoid overfitting [^133^][^134^]
- **Magic Formula has underperformed since ~2014:** European Magic Formula + Momentum underperformed market in 2018, 2019, 2022-2024 [^140^]
- **Factor investing requires minimum 5-10 year horizon:** Any single factor can underperform for 3-5 years or more [^153^]

---

## Controversies & Conflicting Claims

- **"Factor investing has failed miserably" vs. "factor investing works":** Allan Roth claimed failure, but live Dimensional fund data shows average outperformance of 2.6 percentage points vs. Vanguard index funds across 9 fund categories [^156^]
- **Has popularity destroyed the value premium?** No evidence found - valuation spreads between growth and value have actually widened, not narrowed. Only 7 of 2,657 funds have BtM scores in the top quintile; most "value" funds hold more low-BtM (growth) stocks than high-BtM stocks [^156^]
- **Magic Formula's claimed 30.8% returns are disputed:** Independent backtests (2003-2015) found only 11.4% annualized vs. S&P 500's 8.7% - significant outperformance but nowhere near Greenblatt's claim [^141^]. Transaction costs and small-cap bias explain much of the difference [^139^]
- **Momentum crashes:** Momentum lost 73% in three months in 2009, leading to existential questioning of the factor [^158^]. Momentum works best when combined with other factors
- **Size premium existence questioned:** Clifford Asness argues "There Is No Size Effect" - SMB performed well only until 1982, then reversed [^129^]
- **Value is dead vs. value is poised for comeback:** GMO research argues value's underperformance came entirely from falling relative valuations, not weaker fundamentals. Value is now "priced to win" at near-record discounts [^159^]
- **ML backtest Sharpe ratios have near-zero predictive power for live returns:** Quantopian study of 888 algorithms found backtest Sharpe had near-zero correlation with live performance (context from Phase 1)
- **Transaction costs significantly reduce net returns:** A combined ML approach with 0.3% transaction cost rate saw Ridge return only 3.98% annualized [^132^]; high-turnover strategies see 80% of backtested profits destroyed in live trading (context from Phase 1)

---

## Recommended Deep-Dive Areas

- **Multi-factor integrated scoring (value + momentum + quality):** Research confirms 50/50 separate portfolios outperform blended selection; quarterly rebalancing optimal. Needs deeper implementation analysis for automated systems [^165^]
- **Piotroski F-Score + Earnings Yield combination:** This combination showed 400%+ return improvement in European backtests; warrants detailed rule specification [^150^]
- **Dual Momentum (Gary Antonacci) with factor overlays:** GEM model achieves 14.8% CAGR with only 1.5 trades/year; adding value/quality factor screening to momentum selection could enhance returns [^19^][^26^]
- **Low volatility + trend filter:** Low vol anomaly provides superior risk-adjusted returns but requires trend filter to avoid value traps; Clarke et al. research provides foundation [^161^][^162^]
- **Machine learning factor combination with regularization:** NYU Stern study found adaptive strategies with regularization provide superior risk-adjusted returns (context from Phase 1); Ridge/MLP with dynamic factor selection warrants exploration [^132^]
- **Earnings momentum (SUE + revenue surprise combination):** Combined SUE + SURGE strategy generates 0.89% monthly with strong statistical significance; pure long-side implementation needs specification [^127^]

---

## Strategy Details

### Strategy 1: Joel Greenblatt's Magic Formula

**Factor Definitions:**
- Return on Invested Capital (ROIC) = EBIT / (Net Working Capital + Net Fixed Assets) - measures quality
- Earnings Yield (EY) = EBIT / Enterprise Value - measures value/cheapness
- Magic Formula Rank = Rank by ROIC + Rank by EY (lowest combined rank = best)

**Ranking Methodology:**
1. Rank all stocks by ROIC (1 = highest)
2. Rank all stocks by Earnings Yield (1 = highest)
3. Add the two rankings together
4. Select top 20-30 stocks with lowest combined rank

**Backtested Performance:**
| Period | CAGR | Benchmark | Outperformance |
|--------|------|-----------|----------------|
| 1988-2004 (Greenblatt) | 30.8% | 12.4% (S&P 500) | +18.4% |
| 1988-2004 (top 30 of 3,500) | 30.8% | 12.4% | +18.4% |
| 1988-2004 (top 30 of 2,500) | 23.7% | 12.4% | +11.3% |
| 1988-2004 (top 30 of 1,000) | 22.9% | 12.4% | +10.5% |
| 2003-2015 (independent) | 11.4% | 8.7% (S&P 500) | +2.7% |
| 1999-2023 (Portfolio123) | ~10% | ~5% (S&P 500) | ~+5% |
| 2016-2025 Europe | 10.7% | 9.5% (EURO STOXX) | +1.2% |

**Monthly Return Assessment:** Original period (~2.3% monthly average) exceeds 3% in some years; recent periods (~0.8-0.9% monthly) do NOT achieve >3% monthly

**Universe Definition:** US stocks excluding financials, utilities, ADRs; minimum market cap $50M-$100M
**Rebalancing Frequency:** Annual (can adjust to quarterly)
**Transaction Cost Assumptions:** Not explicitly included in original backtests; independent studies suggest ~1-2% annual drag
**Max Drawdown:** Varies by period; 1999-2023 backtest showed higher drawdown than S&P 500 during underperformance periods (2014-2020)

**Source Citations:** [^139^] QuantifiedStrategies; [^140^] Quant-Investing; [^141^] Investopedia; [^142^] Thesis EUR (Indonesian market)

---

### Strategy 2: Piotroski F-Score

**Factor Definitions (9 binary criteria):**
- **Profitability (4 points):**
  - ROA > 0 (+1)
  - Operating Cash Flow > 0 (+1)
  - ROA this year > ROA last year (+1)
  - CFO > Net Income (accruals check) (+1)
- **Leverage/Liquidity (3 points):**
  - Long-term debt ratio decreased (+1)
  - Current ratio increased (+1)
  - No new equity issued (+1)
- **Operating Efficiency (2 points):**
  - Gross margin increased (+1)
  - Asset turnover increased (+1)

**Ranking Methodology:**
1. Start with low price-to-book stocks (cheapest 20%)
2. Calculate F-Score (0-9) for each stock
3. Buy stocks with F-Score of 8 or 9 (strongest fundamentals among cheap stocks)

**Backtested Performance:**
| Period | Strategy | Market | Outperformance |
|--------|----------|--------|----------------|
| 1976-1996 (Piotroski) | +13.4% vs market | - | 13.4% annual outperformance |
| 1976-1996 (Long-Short, High-Low) | +23.0% vs market | - | 23.0% annual spread |
| 2005-2020 (Python backtest) | 14.84% CAGR | 11.38% (S&P 500) | +3.46% |
| 2020-2023 (QuantConnect) | 43.2% CAGR | 14.4% (SPY) | +28.8% |
| 2020-2023 Taiwan | 27.83% annual | - | Sharpe 1.38 |
| 1974-2014 FS-Score | 13.3% CAGR | 11.2% (S&P 500) | +2.1% |

**Key Finding by Company Size (1976-1996):**
- Small companies: High F-Score outperformed low by 23.0% annually
- Medium companies: High F-Score outperformed low by 17.5% annually  
- Large companies: High F-Score outperformed low by 15.8% annually

**Monthly Return Assessment:** ~1.1-1.8% monthly for long-only high F-Score; does NOT consistently achieve >3% monthly except in concentrated small-cap implementations

**Universe Definition:** Low P/B stocks (cheapest 20% by book-to-market)
**Rebalancing Frequency:** Annual (or quarterly)
**Transaction Cost Assumptions:** Slippage model applied in QuantConnect backtest; 0.3% commission in Taiwan study
**Max Drawdown:** 29.9% (2020-2023 QuantConnect backtest)

**Source Citations:** [^147^] QuantConnect; [^148^] TEJ Win; [^150^] Quant-Investing; [^151^] Alpha Architect; [^152^] Python Plain English

---

### Strategy 3: Multi-Factor Combination (Value + Momentum)

**Factor Definitions:**
- **Value:** EBIT/TEV (Earnings Yield) or Book-to-Market
- **Momentum:** 12-month price return excluding most recent month (12-1 momentum)

**Ranking Methodology:**
- **Separate Portfolio Approach (recommended by research):**
  - Build separate value portfolio (top decile by EBIT/TEV)
  - Build separate momentum portfolio (top decile by 12-1 momentum)
  - Allocate 50% to each portfolio
  - Rebalance quarterly or annually
- **Alternative - Blended Approach:** Rank stocks on both factors simultaneously and select top combined ranking

**Backtested Performance (50/50 Value + Momentum, 1927-2015):**
| Metric | 50/50 Combined | S&P 500 |
|--------|---------------|---------|
| CAGR | ~12-14% | ~10% |
| Sharpe Ratio | 0.52+ | 0.35-0.40 |
| Max Drawdown | Lower than market | -50%+ |

**Key Research Finding:** Adding momentum to pure value increased returns by an average of 385% across 13 tested value strategies in European markets (1999-2011) [^165^]

**Monthly Return Assessment:** ~1.0-1.2% monthly; does NOT achieve >3% monthly as long-only diversified strategy

**Universe Definition:** Large and mid-cap stocks (US and international)
**Rebalancing Frequency:** Quarterly recommended (balances cost and performance)
**Transaction Cost Assumptions:** 0.25% annual for value (annual rebalance); 3.0% annual for momentum (monthly rebalance) - net of fees in Alpha Architect study [^165^]

**Source Citations:** [^146^] TradeAlgo; [^153^] Quantt; [^165^] Quant-Investing/Alpha Architect

---

### Strategy 4: Fama-French Factor Implementation (Long-Only)

**Factor Definitions:**
- **SMB (Small Minus Big):** Return spread between small-cap and large-cap stocks
- **HML (High Minus Low):** Return spread between high book-to-market (value) and low book-to-market (growth) stocks
- **RMW (Robust Minus Weak):** Return spread between high and low profitability stocks
- **CMA (Conservative Minus Aggressive):** Return spread between low and high investment ratio stocks
- **WML (Winners Minus Losers):** Momentum factor - return spread between past winners and losers

**Factor Premiums (Annual, Various Periods):**
| Factor | 1998-2020 | Last 10 Years | Last 5 Years |
|--------|-----------|---------------|--------------|
| HML (Value) | 1.28% | -5.14% | -8.26% |
| SMB (Size) | 1.58% | -1.21% | -0.83% |
| RMW (Quality) | 4.14% | 3.94% | 3.65% |
| CMA (Investment) | 1.92% | -1.81% | -4.05% |
| WML (Momentum) | 6.47% | 6.28% | 3.35% |
| QMJ (Quality-Junk) | 5.39% | 5.29% | 2.88% |
| MKT (Market) | 6.72% | 10.05% | 11.96% |

**Factor Premiums by Decade (US, 1963-2019):**
| Decade | HML | SMB | RMW | CMA |
|--------|-----|-----|-----|-----|
| 1963-1969 | 2.39% | 9.49% | 1.28% | -0.58% |
| 1970-1979 | 8.10% | 4.86% | -0.51% | 6.25% |
| 1980-1989 | 6.05% | -0.31% | 4.83% | 5.74% |
| 1990-1999 | -0.13% | -2.11% | 2.22% | -0.04% |
| 2000-2009 | 7.74% | 7.27% | 8.54% | 6.76% |
| 2010-2019 | -2.60% | -0.39% | 1.67% | 0.22% |

**Monthly Return Assessment:** Individual factors alone do NOT achieve >3% monthly. Even combining top factors (momentum + quality) yields ~0.8-1.0% monthly

**Universe Definition:** All stocks in CRSP/Compustat merged database
**Rebalancing Frequency:** Monthly for factor portfolios
**Transaction Cost Assumptions:** Not typically included in academic factor returns; real-world implementation 0.5-2% annual drag

**Source Citations:** [^129^] CFA Institute; [^131^] Investopedia; [^149^] NBIM; [^158^] Robeco (David Blitz)

---

### Strategy 5: Quality Minus Junk (QMJ) - AQR Factor

**Factor Definitions (Asness et al., 2014):**
Quality is defined using four components:
- **Profitability:** Gross profits/assets, ROE, ROA, cash flow/assets
- **Growth:** Growth in profitability metrics
- **Safety:** Low beta, low idiosyncratic volatility, low leverage, low bankruptcy risk
- **Payout:** Net equity issuance, total net payouts over profits

**Ranking Methodology:**
1. Calculate z-scores for each of the four quality components
2. Average component z-scores to get overall quality score
3. Long high-quality stocks, short low-quality (junk) stocks

**Backtested Performance:**
| Period | QMJ Annual Return | Volatility | Return/Vol |
|--------|-------------------|------------|------------|
| 1998-2020 | 5.39% | 8.01% | 0.67 |
| Last 10 years | 5.29% | 6.86% | 0.77 |
| Last 5 years | 2.88% | 6.89% | 0.42 |

**Key Finding:** High price of quality predicts low future QMJ returns (time variation documented) [^128^]. Quality factor has been the most consistent performer across periods.

**Monthly Return Assessment:** ~0.2-0.4% monthly for long-only quality tilt; does NOT achieve >3% monthly

**Universe Definition:** Global stocks (US and international)
**Rebalancing Frequency:** Monthly
**Transaction Cost Assumptions:** Academic factor returns; real-world costs ~0.5-1.5% annually

**Source Citations:** [^128^] Asness et al. NHH Paper; [^146^] TradeAlgo; [^149^] NBIM factor report

---

### Strategy 6: Earnings Momentum / SUE Strategy

**Factor Definitions:**
- **SUE (Standardized Unexpected Earnings):** (Actual EPS - Expected EPS) / Standard Deviation of earnings surprises
  - Expected EPS from seasonal random walk model with drift
- **EAR (Earnings Announcement Return):** Abnormal return over 3-day window around earnings announcement
- **Revenue Surprise (SURGE):** Similar to SUE but using revenue

**Ranking Methodology:**
1. Calculate SUE for all stocks using most recent earnings announcement
2. Sort stocks into deciles/quintiles based on SUE
3. Buy stocks in top SUE quintile (especially those also with high EAR)
4. Hold for 1-6 months

**Backtested Performance (Combined Strategies, 1974-2007):**
| Strategy | Monthly Return | Significance |
|----------|---------------|--------------|
| Standalone earnings momentum (SUE) | 0.63% | t-stat > 5 |
| Standalone revenue momentum (SURGE) | 0.49% | t-stat > 5 |
| Price-Earnings combined | 1.33% | t-stat = 6.39 |
| Earnings-Revenue combined | 0.89% | t-stat = 6.81 |
| Price-Revenue combined | 0.95% | t-stat = 7.58 |

**Key Finding:** Combined strategies (using two information sources) significantly outperform standalone strategies. Price-Earnings combined momentum generates 1.33% monthly (long-short). Long-only implementation generates approximately half the long-short spread. [^127^]

**Momentum Strategy (China, 2018-2022):** Average monthly return 1.55%, cumulative return 40%, max drawdown -8.52% [^126^]

**Monthly Return Assessment:** ~0.5-0.8% monthly for long-only earnings momentum; does NOT achieve >3% monthly. Combined price + earnings momentum long-only may reach ~0.7-1.0%

**Universe Definition:** NYSE, AMEX, NASDAQ; exclude financials, utilities, stocks <$5
**Rebalancing Frequency:** Monthly or quarterly (after earnings announcements)
**Transaction Cost Assumptions:** PEAD strategy rebalanced quarterly; assume 0.5-1.0% annual drag
**Max Drawdown:** -8.52% (China momentum backtest 2018-2022)

**Source Citations:** [^124^] Quant-Investing (momentum 150 years); [^125^] Cornell; [^126^] Atlantis Press; [^127^] Rutgers/Taipei; [^130^] Quantpedia (PEAD)

---

### Strategy 7: Low Volatility Anomaly

**Factor Definitions:**
- **Low Volatility:** Stocks with lowest historical return volatility (typically over 1-5 year trailing period)
- **Minimum Variance Portfolio:** Portfolio optimized for lowest possible variance using covariance matrix

**Ranking Methodology:**
1. Calculate trailing volatility (standard deviation of returns) for each stock
2. Rank stocks by volatility (lowest = best)
3. Buy lowest-volatility quintile/decile
4. Alternative: Construct minimum variance portfolio using optimization

**Backtested Performance:**
| Strategy | Period | Return | Volatility | Sharpe | vs Market |
|----------|--------|--------|------------|--------|-----------|
| Low-Vol Quintile | 1968-2008 | 4.86% excess | 12.74% | 0.38 | +0.62% |
| Min Var (Diagonal) | 1968-2008 | 6.42% excess | 15.93% | 0.40 | +2.18% |
| Min Var (Full Risk) | 1968-2008 | 5.41% excess | 11.50% | 0.47 | +1.17% |
| Levered Min Var | 1968-2008 | 8.82% excess | 18.80% | 0.47 | +4.58% |
| Clarke et al. | 1968-2005 | Comparable to market | -25% vs market | Superior | Match |
| Low Vol (Global) | Long-term | Slightly above market | ~2/3 of market | Superior | D1-D10 spread: 5.9% |

**Key Finding:** Low-volatility stocks achieve comparable returns with ~25% less risk, producing superior risk-adjusted returns (Sharpe ratios). The effect is global and persistent. [^161^][^162^]

**Monthly Return Assessment:** ~0.3-0.7% monthly excess return; does NOT achieve >3% monthly. Strength is risk reduction, not return maximization

**Universe Definition:** Top 1,000 US stocks by market cap (Clarke et al.); or broad market
**Rebalancing Frequency:** Monthly
**Transaction Cost Assumptions:** Monthly rebalancing incurs costs; weight constraints 0-3% per stock
**Max Drawdown:** Significantly lower than market (low vol = defensive)

**Source Citations:** [^138^] Quantpedia; [^139^] NYU Stern; [^161^] Robeco (Blitz & van Vliet); [^162^] Roger Clarke et al.; [^163^] Nasdaq Baltic

---

### Strategy 8: Machine Learning Enhanced Factor Strategy

**Factor/Model Definitions:**
- **Features:** 17-24 factors from CNE5 model or traditional factors (P/E, P/B, momentum, ROE, etc.)
- **Models:** Ridge Regression, MLP Neural Network, Random Forest, XGBoost
- **Methodology:** Rolling 12-month training window; 1-month prediction; dynamic factor selection

**Backtested Performance:**
| Model | Period | Annualized Return | Sharpe | Max DD |
|-------|--------|-------------------|--------|--------|
| Ridge (single) | 2020-2022 (China) | 3.98% | 0.20 | 48.7% |
| MLP (single) | 2020-2022 (China) | 3.88% | 0.18 | 53.7% |
| Random Forest (single) | 2020-2022 (China) | 2.20% | 0.01 | 74.3% |
| IC-Mean Combined | 2020-2022 (China) | 13.80% | 0.56+ | - |
| XGBoost (top 20 stocks) | 2012-2021 (China) | 32.5% | 0.85 | 32.8% |
| Decision Tree (ensemble) | 2012-2021 (China) | 28-33% | 0.26-0.85 | 24-33% |
| Linear Regression | US study | 54.63% | 1.41 | 12.0% |
| XGBoost | US study | 10.71% | 0.46 | 12.5% |
| S&P 500 ML (tree-based) | 14-year backtest | Beat index | - | Higher risk |

**Key Finding:** Single ML algorithms perform modestly; ensemble/dynamic approaches significantly better. XGBoost with 20-stock portfolio showed best performance in Chinese market. Linear regression unexpectedly outperformed complex models in one US study, likely due to mean-reversion effects. [^132^][^134^][^135^][^140^]

**Monthly Return Assessment:** Best results show ~1.0-2.7% monthly (XGBoost China, top 20 stocks); some studies claim higher but with significant overfitting risk. The IC-Mean combined approach at 13.8% annualized = ~1.1% monthly

**Universe Definition:** CSI 300 constituents (China); S&P 500 (US studies)
**Rebalancing Frequency:** Monthly
**Transaction Cost Assumptions:** 0.3% total cost rate in China study [^132^]
**Max Drawdown:** 24-75% depending on model and concentration

**Important Caveats:**
- ML backtests suffer from overfitting; live performance typically 50-80% of backtest
- Quantopian study: 888 algo strategies' backtest Sharpe had near-zero predictive power for live returns
- Model decay: factor importance changes over time; requires frequent retraining [^140^]

**Source Citations:** [^132^] Arxiv (combined ML); [^133^] BSIC (S&P 500 ML); [^134^] LSEEE journal (XGBoost); [^135^] ACM proceedings (multi-factor rotational); [^140^] ScienceDirect (S&P 500 ML)

---

### Strategy 9: Dual Momentum (Gary Antonacci)

**Factor Definitions:**
- **Absolute Momentum:** Asset's own return over lookback period vs. risk-free rate (T-Bills)
- **Relative Momentum:** Asset's performance vs. other candidate assets over lookback period

**Ranking Methodology:**
1. Check absolute momentum of primary asset (e.g., S&P 500) vs. T-Bills over 12 months
2. If absolute momentum negative -> move to bonds (risk-off)
3. If absolute momentum positive -> compare S&P 500 vs. international stocks; buy stronger performer
4. Hold until next monthly signal

**Backtested Performance:**
| Metric | Original DM (1970-2025) | S&P 500 Buy&Hold | Enhanced DM (GGC) |
|--------|------------------------|------------------|-------------------|
| CAGR | 14.8% | 11.2% | 16.4% |
| Max Drawdown | -20.5% | -50.1% | -16.8% |
| Sharpe/MAR | 0.72 | - | 0.98 |
| Trades/Year | ~1.5 | - | ~1.5 |

**Dual Momentum with Different Bond Proxies (1970-2025):**
| Bond Proxy | CAGR | Max DD |
|------------|------|--------|
| TLT (20+ yr) | 14.65% | -29.14% |
| IEF (7-10 yr) | 14.80% | -20.47% |
| SHY (1-3 yr) | 14.30% | -19.76% |
| BIL (T-Bills) | 13.44% | -22.97% |

**Monthly Return Assessment:** ~1.1-1.2% monthly (14.8% CAGR / 12); does NOT achieve >3% monthly as standalone strategy. Lower drawdowns are the primary advantage

**Universe Definition:** ETFs tracking major indices (SPY, EFA/VEU, AGG/IEF/BIL)
**Rebalancing Frequency:** Monthly
**Transaction Cost Assumptions:** Minimal (~1.5 trades/year); transaction costs negligible in modern ETF environment
**Max Drawdown:** -16.8% to -29% depending on bond proxy

**Source Citations:** [^19^] QuantifiedStrategies; [^26^] Grzegorz.link (enhanced); [^27^] Robot Wealth

---

## Critical Assessment: Can Factor Strategies Achieve >3% Monthly?

### Honest Conclusions

1. **3% monthly (36% CAGR) is an extremely aggressive target** that exceeds the documented performance of virtually all diversified long-only factor strategies. Even the legendary Magic Formula achieved "only" ~2.6% monthly in its best period.

2. **Strategies that have historically exceeded 3% monthly (36% annualized):**
   - Greenblatt's Magic Formula (1988-2004 only): ~2.6% monthly on average
   - Piotroski F-Score long-short (1976-1996): ~1.9% monthly spread (long-only would be ~1.1%)
   - XGBoost 20-stock concentrated China portfolio (2012-2021): ~2.7% monthly (likely overfitted)
   - ML combined IC-Mean (China 2020-2022): ~1.1% monthly

3. **Realistic long-only factor returns:**
   - Single factor: 0.2-0.8% monthly (2-10% annual premium over market)
   - Multi-factor (value + momentum): 0.8-1.2% monthly (10-15% annual)
   - Concentrated quality + momentum: 1.0-1.5% monthly (12-18% annual)
   - With leverage: potentially 1.5-2.5% monthly (but with proportional risk increase)

4. **Path to potentially achieve >3% monthly:**
   - Use concentrated portfolios (10-20 stocks, not 50-100+)
   - Combine multiple uncorrelated factors (value + momentum + quality)
   - Focus on small/mid-cap universe where premiums are larger
   - Add trend filter / absolute momentum overlay (avoid bear markets)
   - Consider modest leverage (1.5-2x) on low-volatility factor portfolios
   - Apply monthly rebalancing with transaction cost control
   - Use machine learning for dynamic factor weighting

5. **Risk warnings:**
   - Factor strategies can underperform for 3-5+ years
   - Value factor was negative for the entire 2010-2019 decade
   - Momentum can crash (73% loss in 3 months in 2009)
   - Transaction costs reduce net returns by 0.5-3% annually
   - Overfitting is rampant in ML backtests
   - Live performance typically 30-80% of backtested results

---

## References

[^123^] Ryan O'Connell Finance - Fama-French Three-Factor Model Calculator
[^124^] Quant-Investing - "Momentum Investing Strategy Backtested Over 150 Years"
[^125^] Cornell eCommons - "Memory vs Momentum" paper
[^126^] Atlantis Press - "Momentum Strategy Based on Stock Returns"
[^127^] Rutgers/Taipei - "Price, Earnings, and Revenue Momentum Strategies"
[^128^] Asness, Frazzini, Pedersen - "Quality Minus Junk" (NHH working paper)
[^129^] CFA Institute - "Fama and French: The Five-Factor Model Revisited"
[^130^] Quantpedia - "Post-Earnings Announcement Effect" strategy
[^131^] Investopedia - "Fama French Three Factor Model"
[^132^] Arxiv - "Combined machine learning for stock selection strategy based on dynamic weighting methods" (2025)
[^133^] BSIC - "Machine Learning Models for S&P 500 Trading"
[^134^] LSEEE - "An Example of Machine Learning-Based Multifactor Dynamic Strategy"
[^135^] ACM Proceedings - "Multi-Factor Rotational Stock Selection Strategy using ML"
[^138^] Quantpedia - "Low Volatility Factor Effect in Stocks"
[^139^] NYU Stern / Wurgler - "Understanding the Low Volatility Anomaly"
[^139^] QuantifiedStrategies - "The Magic Formula Strategy: Backtest & Performance"
[^140^] Quant-Investing - "Magic Formula investment strategy back test (2026 update)"
[^141^] Investopedia - "Magic Formula Investing Explained"
[^142^] Thesis EUR - "Backtesting Adaptations of Greenblatt's Magic Formula on Indonesian Stock Market"
[^143^] Reddit r/SecurityAnalysis - "Backtesting Greenblatt's Magic Formula"
[^146^] TradeAlgo - "Factor Investing Guide: How Value, Momentum, Quality, and Size Factors Drive Returns"
[^147^] QuantConnect - "Piotroski F-Score Investing"
[^148^] TEJ Win - "F-score Strategy: Identifying Undervalued Quality Stocks"
[^149^] NBIM - "Factor and risk-adjusted return" research
[^150^] Quant-Investing - "Piotroski F-Score's Back-Tested Triumph"
[^151^] Alpha Architect - "Simple Methods to Improve the Piotroski F-Score"
[^152^] CxO Advisory - "Trend Factor and Future Stock Returns"
[^153^] Quantt - "Factor Investing: What It Is & How Works"
[^155^] NEPC - "What is Factor Investing?"
[^156^] Alpha Architect - "The Failure of Factor Investing was Predictable"
[^157^] MSCI - "Factors behind value's underperformance"
[^158^] Robeco / David Blitz - "Factor Performance 2010-2019: A Lost Decade?"
[^159^] GMO - "Beyond the Factor: GMO's Approach to Value Investing"
[^160^] SSRN - "Understanding the Performance of the Equity Value Factor"
[^161^] Robeco - "The Volatility Effect" (Blitz & van Vliet)
[^162^] Clarke, de Silva, Thorley - "Minimum-Variance Portfolio Composition"
[^163^] Nasdaq Baltic - "Performance of Minimum Variance Portfolios"
[^165^] Quant-Investing - "Should You Mix Value And Momentum Strategies"
[^19^] QuantifiedStrategies - "Dual Momentum Trading Strategy (Gary Antonacci)"
[^26^] Grzegorz.link - "Dual Momentum & Global Growth Cycle Enhanced"
[^27^] Robot Wealth - "Dual Momentum Investing: A Quant's Review"
[^132^] ScienceDirect - "S&P 500 stock selection using machine learning classifiers" (2024)
[^134^] KTH - "A Machine Learning-Based Stock Prediction System"
[^135^] Medium/TEJ - "Stock Selection by Random Forest Algorithm"
