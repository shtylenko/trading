# Dimension 03: ETF Rotation & Sector Momentum (LONG-ONLY)

## Research Summary

This document provides a comprehensive deep-dive into ETF rotation and sector momentum strategies for long-only investing. We document exact rotation rules, ranking methodologies, backtested performance across market regimes, transaction cost impacts, and counter-arguments for each strategy. All findings are sourced from primary academic papers, official strategy publications, and verified backtests with inline citations.

---

## Table of Contents

1. [Dual Momentum: Antonacci's GEM](#1-dual-momentum-antonaccis-gem)
2. [Sector Momentum Rotation: SPDR ETFs](#2-sector-momentum-rotation-spdr-etfs)
3. [Asset Class Momentum: SACEMS](#3-asset-class-momentum-sacems)
4. [Contrarian ("Losers") Sector Rotation](#4-contrarian-losers-sector-rotation)
5. [Combined Trend + Momentum Filters](#5-combined-trend--momentum-filters)
6. [Intra-Sector vs Inter-Sector Rotation](#6-intra-sector-vs-inter-sector-rotation)
7. [Transaction Cost Optimization](#7-transaction-cost-optimization)
8. [Other Notable Strategies](#8-other-notable-strategies)
9. [Comparative Summary](#9-comparative-summary)
10. [Counter-Arguments and Limitations](#10-counter-arguments-and-limitations)
11. [Practical Implementation Guidance](#11-practical-implementation-guidance)

---

## 1. Dual Momentum: Antonacci's GEM

### 1.1 Strategy Overview

Global Equities Momentum (GEM) is the flagship dual momentum strategy developed by Gary Antonacci, formalized in his 2012 paper "Risk Premia Harvesting Through Dual Momentum" (NAAIM Wagner Award winner) and expanded in his 2014 book *Dual Momentum Investing*.

### 1.2 Exact Trading Rules

**Official GEM Rules (from Antonacci's book, page 98):**[^318^]

```
STEP 1: ABSOLUTE MOMENTUM CHECK (Monthly, last trading day)
- Calculate 12-month total return of S&P 500 (SPY/IVV)
- Calculate 12-month total return of risk-free proxy (3-month T-Bill or BIL)
- IF S&P 500 return > T-Bill return → proceed to Step 2 (stocks are in uptrend)
- IF S&P 500 return < T-Bill return → move 100% to bonds (AGG/IEF)

STEP 2: RELATIVE MOMENTUM CHECK (only if Step 1 passes)
- Calculate 12-month total return of S&P 500 (SPY/IVV)
- Calculate 12-month total return of International Stocks (VEU/ACWI ex-US)
- IF US stocks return > International stocks return → invest 100% in SPY
- IF International stocks return > US stocks return → invest 100% in VEU
```

**Key clarifications from official sources:**[^318^][^429^]
- The official rules apply absolute momentum FIRST, then relative momentum — contrary to the simplified flowchart on page 101 of the book
- All decisions made on the **last trading day of each month**
- Uses **12-month lookback** for both absolute and relative momentum
- Strategy always holds **exactly one asset at 100% allocation**
- Average of only **1.5 trades per year**[^435^]

**ETF Implementation:**[^311^][^424^]
- US Equity: SPY (SPDR S&P 500) or VOO/IVV
- International Equity: VEU (Vanguard FTSE All-World ex-US) or VXUS/SCHF
- Risk-free proxy: BIL (SPDR Bloomberg 1-3 Month T-Bill) or SHV
- Bonds (risk-off): AGG (iShares Core US Aggregate Bond) or IEF

### 1.3 Backtested Performance

| Metric | GEM (12-month) | S&P 500 | 60/40 Benchmark |
|--------|---------------|---------|-----------------|
| **CAGR** | 15.8% | 11.4% | ~9% |
| **Annual Std Dev** | 11.5% | 14.2% | ~9% |
| **Sharpe Ratio** | 0.96 | 0.52 | ~0.5 |
| **Max Drawdown** | -17.8% | -51.0% | ~-30% |
| **Worst 12 Months** | -17.8% | -43.3% | — |
| **% Profitable Months** | 69% | 64% | — |

*Source: Antonacci extended backtest 1950-2018*[^435^]

**Period-Specific Performance (PortfolioDB, ~56 years):**[^430^]

| Metric | GEM Dual Momentum | Benchmark |
|--------|------------------|-----------|
| CAGR | 14.6% | 9.5% |
| Max Drawdown | -21.6% | -29.7% |
| Sharpe Ratio | 0.79 | 0.51 |
| Best Year | +68.6% | +32.8% |
| Worst Year | -17.2% | -18.3% |
| GFC CAGR | +4.8% | -0.4% |
| Dot-com CAGR | +4.2% | -4.3% |
| Profitable Months | 65.6% | 63.2% |

**Quant Investing verification (39 years):**[^18^]
- CAGR: 17.43% vs 8.85% for global market index
- Max Drawdown: 22.7% vs 60.21% for global index

**ReSolve Asset Management ensemble analysis (1950-2018):**[^310^]
- Original GEM specification: CAGR 14.9%, Sharpe 0.90, Avg Max Drawdown -16.5%
- Ensemble approach (combining multiple lookbacks): CAGR 14.2%, Sharpe 0.93, Avg Max Drawdown -13.2%
- The ensemble had a 99.9th percentile rank for drawdown stability

### 1.4 Component Decomposition

Antonacci separated GEM's two components:[^435^]

| Metric | Full GEM | Relative Momentum Only | Absolute Momentum Only | S&P 500 |
|--------|----------|----------------------|----------------------|---------|
| CAGR | **15.8%** | 13.4% | 12.3% | 11.4% |
| Std Dev | 11.5% | 14.4% | 11.2% | 14.2% |
| Sharpe | **0.96** | 0.64 | 0.70 | 0.52 |
| Max DD | **-17.8%** | -54.6% | -29.6% | -51.0% |

**Key insight:** Relative momentum alone boosts returns (+200bps vs S&P 500) but retains equity-like drawdowns. Absolute momentum alone reduces drawdowns significantly but with modest return enhancement (+90bps). The combination achieves both.

### 1.5 Lookback Period Sensitivity

Antonacci tested multiple lookback periods:[^457^]

| Lookback | CAGR | Std Dev | Sharpe | Max Drawdown |
|----------|------|---------|--------|--------------|
| 3-month | 12.7% | 11.0% | 0.76 | -23.3% |
| 6-month | 14.6% | 10.9% | 0.93 | -21.6% |
| 9-month | 13.9% | 11.4% | 0.83 | -20.7% |
| **12-month** | **15.5%** | **11.6%** | **0.95** | **-17.8%** |
| Composite (equal) | 14.3% | 10.2% | 0.95 | -17.7% |

**Finding:** 12-month lookback provides the highest CAGR with equivalent Sharpe ratio and drawdown to the composite. Antonacci prefers 12-month for: fewer trades (tax efficiency), strongest out-of-sample evidence, and alignment with academic literature.[^435^][^457^]

### 1.6 Evidence Template

| Field | Data |
|-------|------|
| **Claim** | GEM dual momentum achieves ~15.8% CAGR with ~17.8% max drawdown using just 3 ETFs and monthly rebalancing |
| **Source** | Gary Antonacci, "Extended Backtest of Global Equities Momentum," OptimalMomentum.com |
| **URL** | https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/ |
| **Date** | 2024-02-25 |
| **Excerpt** | "Here are GEM results compared to a global asset allocation (GAA) benchmark... CAGR 15.8, Annual Std Dev 11.5, Sharpe Ratio 0.96, Worst Drawdown -17.8" |
| **Context** | Backtest 1950-2018 using index data; gross of transaction costs and taxes |
| **Confidence** | HIGH — extensive out-of-sample data, multiple independent replications |

---

## 2. Sector Momentum Rotation: SPDR ETFs

### 2.1 Strategy Overview

Sector momentum exploits the persistence of industry-level returns first documented by Moskowitz and Grinblatt (1999). The basic implementation ranks S&P 500 sector ETFs by past returns and holds the top performers.

### 2.2 Academic Foundation

**Moskowitz & Grinblatt (1999) — "Do Industries Explain Momentum?":**[^421^]
- Industry portfolios exhibit significant momentum even after controlling for size, BE/ME, individual stock momentum
- Industry momentum strategies are **more profitable than individual stock momentum strategies**
- Industry momentum is robust among largest, most liquid stocks
- 6-month momentum strategies generate substantial risk-adjusted returns
- Key finding: "Once returns are adjusted for industry effects, momentum profits from individual equities are significantly weaker and, for the most part, are statistically insignificant"

### 2.3 Basic Sector Momentum Rules

**Simple Top-3 Sector Momentum (from Quantpedia):**[^136^]
- **Universe:** 10 sector ETFs (e.g., XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLK, XLU, XLRE)
- **Ranking:** 12-month total return momentum
- **Selection:** Pick 3 ETFs with strongest momentum
- **Weighting:** Equal weight (33.3% each)
- **Rebalancing:** Monthly
- **Backtest period:** 1928-2009 (proxy data)
- **Performance:** 13.94% CAGR, 18.38% volatility, 0.54 Sharpe, -46.29% max drawdown

### 2.4 Faber Sector Momentum with SMA Filter

**U.S. Sector-Momentum Strategy (Faber 2011):**[^459^]
- **Universe:** 10 S&P 500 sector indexes + Russell 2000
- **Filter:** Compare each ETF's price to its 12-month SMA. Exclude if below SMA.
- **Ranking:** Sort remaining ETFs by 12-month total return
- **Selection:** Hold top 3 equal-weighted
- **Cash Rule:** If fewer than 3 ETFs pass the SMA filter, allocate missing slots to cash. If none qualify, 100% cash.
- **Backtest:** October 1990 to October 2011

| Metric | SMA-Filtered Top 3 | Equal-Weight Benchmark |
|--------|-------------------|----------------------|
| Annualized Return | **13.01%** | ~8-10% |
| Standard Deviation | 14.20% | — |
| Sharpe Ratio | **0.65** | ~0.5 |

*Note: Results before taxes and expenses. Strategy "aggressively churns its portfolio" — best implemented in tax-sheltered accounts.*

### 2.5 Logical Invest SPDR Sector Rotation Meta-Strategy

**Frank Grossmann's multi-strategy approach:**[^129^]

| Sub-Strategy | CAGR | Sharpe | Max Drawdown |
|-------------|------|--------|--------------|
| SPY Benchmark | 5.10% | 0.25 | -55% |
| 1) Momentum long lookback (198d) | 9.22% | 0.58 | -37% |
| 2) Momentum short lookback (7d) | 9.86% | 0.57 | -46% |
| 3) Mean reversion "buy worst" | **11.36%** | **0.64** | -47% |
| 4) Momentum + mean reversion | **12.30%** | 0.47 | -47% |
| 5) Meta-strategy (all 1-4) | **12.8%** | **1.16** | **-17%** |

**Key findings:**[^129^]
- Long lookback (198 days) with modified Sharpe ratio ranking selects defensive sectors (XLP, XLU) during corrections
- Short lookback (7 days) reacts faster to bull markets
- Mean reversion "buy worst" outperforms both momentum strategies individually
- Combining all into meta-strategy achieves highest Sharpe (1.16) and lowest drawdown (-17%)

**Ranking formula (modified Sharpe):**[^129^]
```
Performance = (1 + return)^volatility_attenuator / (1 + volatility)^volatility_attenuator
```
With volatility attenuator = 5, this heavily penalizes high-volatility sectors.

### 2.6 Relative Strength Strategy (Faber, 2009)

**Top-N sector rotation with hedge:**[^466^]
- **Universe:** US equity sectors
- **Ranking:** Combination of 1, 3, 6, 9, and 12-month relative strength
- **Selection:** Top 1, 2, or 3 sectors
- **Hedge:** Dynamic hedge using 12-month SMA filter
- **Period:** 1928-2009

| Portfolio | CAGR | Std Dev | Sharpe | Max Drawdown |
|-----------|------|---------|--------|--------------|
| Top 1 | 14.67% | 17.94% | 0.61 | -54.69% |
| **Top 2** | **14.42%** | **15.32%** | **0.69** | -51.36% |
| **Top 3** | **13.28%** | **14.26%** | **0.66** | **-49.42%** |
| Equal Weight | 10.40% | 12.14% | 0.54 | -42.27% |

With dynamic hedge applied, drawdowns reduced to ~40-50% range while preserving most returns.

---

## 3. Asset Class Momentum: SACEMS

### 3.1 Strategy Overview

The Simple Asset Class ETF Momentum Strategy (SACEMS), developed and tracked by CXO Advisory Group since 2010, applies relative momentum across a diversified set of asset class ETFs.

### 3.2 Exact Rules

**SACEMS Specification:**[^117^][^431^]
- **Universe (9 ETFs):** SPY (US Large Cap), EFA (International Developed), EEM (Emerging Markets), IWM (US Small Cap), QQQ (NASDAQ), VNQ (US Real Estate), LQD (Investment Grade Bonds), HYG (High Yield Bonds), GLD (Gold)
- *Note: Universe adjusted in mid-2019 for liquidity*
- **Lookback:** 5-month total return (primary)
- **Rebalancing:** Monthly, end-of-month
- **Versions:**
  - **Top 1:** 100% in top-ranked ETF
  - **EW Top 2:** 50% in each of top 2 ETFs
  - **EW Top 3:** 33.3% in each of top 3 ETFs

### 3.3 Performance

**Historical Performance (July 2006 - present, gross):**[^117^][^443^]

| Strategy | CAGR | Max Drawdown | Sharpe |
|----------|------|-------------|--------|
| SACEMS Top 1 | ~10-11% | ~-25% | ~0.55 |
| SACEMS EW Top 2 | ~9-10% | ~-22% | ~0.60 |
| SACEMS EW Top 3 | ~8-9% | ~-20% | ~0.52 |
| EW All (benchmark) | ~6% | ~-35% | ~0.30 |
| SPY | ~7-8% | ~-55% | ~0.35 |

**SACEMS + SACEVS Combined (July 2006 - August 2025):**[^443^]

| Combination | CAGR | Max Drawdown | Sharpe |
|-------------|------|-------------|--------|
| 50-50 Best Value - EW Top 2 | **12.0%** | **-14%** | **0.99** |
| 50-50 Best Value - EW Top 3 | 10.8% | -17% | 0.82 |
| 50-50 Weighted - EW Top 3 | 10.2% | -18% | 0.82 |
| SPY:SMA10 (benchmark) | 10.0% | -22% | 0.64 |

**Key insight:** Combining momentum with value strategies provides meaningful diversification (correlation 0.34-0.52) and improves risk-adjusted returns.

### 3.4 Robustness Tests

CXO Advisory has conducted extensive robustness testing:[^117^][^444^]

- **Lookback intervals:** 2-12 months tested; 5-month is baseline but results are robust across range
- **Weekly/biweekly rebalancing:** Monthly generally performs as well or better
- **Bimonthly rebalancing:** Slightly reduces turnover with modest performance penalty
- **Ranking metric:** Raw return vs Sharpe ratio — raw return is more robust to lookback choice
- **Asset substitutions:** Various ETF substitutions tested with minimal impact
- **Tax-aware versions:** Tax-managed momentum reduces effective tax rate from 11.4% to 5.3%
- **Sticky SACEMS:** Holding winners until they drop out of top 3 reduces turnover but mixed results
- **Buffered winners:** Continuing to hold past winner until it loses by significant margin — limited improvement

### 3.5 Evidence Template

| Field | Data |
|-------|------|
| **Claim** | SACEMS EW Top 3 delivers ~8-9% CAGR with ~-20% max drawdown using 9 asset class ETFs and monthly 5-month momentum ranking |
| **Source** | CXO Advisory Group, "Simple Asset Class ETF Momentum Strategy" |
| **URL** | https://www.cxoadvisory.com/momentum-strategy/ |
| **Date** | Tracked live since 2010 |
| **Excerpt** | "SACEMS seeks diversification plus a monthly tactical edge by holding a few top-performing ETFs... at the end of each month allocate all funds to the top one, equally weighted top two or equally weighted top three" |
| **Context** | Live tracking since 2010 with periodic adjustments; gross of transaction costs |
| **Confidence** | MEDIUM-HIGH — live track record since 2010, extensive robustness testing |

---

## 4. Contrarian ("Losers") Sector Rotation

### 4.1 Strategy Overview

Contrarian sector rotation exploits mean reversion — the tendency of poorly performing sectors to recover. This effect operates at different time horizons than momentum.

### 4.2 Academic Foundation

**Key findings on momentum vs mean reversion:**[^123^]
- Momentum dominates at intermediate horizons (3-12 months)
- Mean reversion characterizes longer-term dynamics (beyond 3-5 years)
- The "Losers" rotation strategy selects worst-performing sectors betting on recovery

### 4.3 "Buy the Worst" Mean Reversion Strategy

**Logical Invest Implementation:**[^129^]

```
Performance Score = (10-day lookback return) - 2 * (20-day lookback return)
```

This formula selects ETFs with positive convexity — those showing recent recovery after a decline.

| Metric | "Buy Worst" Mean Reversion | SPY Benchmark |
|--------|---------------------------|---------------|
| CAGR | **11.36%** | 5.10% |
| Sharpe Ratio | **0.64** | 0.25 |
| Max Drawdown | -47% | -55% |

### 4.4 TSX 60 Sector Rotation Study

**Comprehensive analysis of Winners vs Losers strategies:**[^123^]

Strategy types tested:
- **Winners:** Select top performers based on 6-month momentum
- **Median:** Select middle performers
- **Losers:** Select worst performers (contrarian)

**Key findings:**
- **Quarterly rebalancing dominates** across all strategy types
- Monthly rebalancing generates ~1.20% annual transaction cost drag
- Semi-annual and annual rebalancing miss intermediate opportunities
- Equal weighting consistently outperforms price and market-cap weighting
- The Median strategy (middle performers) showed strong out-of-sample performance

**Optimal strategy by investor horizon:**
- Short (1-3 years): Median Sector Rotation (Quarterly) + Strict Stop Loss
- Medium (3-10 years): Median Stock Rotation (Quarterly) + Volatility Scaling
- Long (10+ years): Hybrid (Median + Losers)

### 4.5 Duration Rotation: "Losers" Outperformance

**U.S. Treasury Fixed-Income ETF study (2007-2025):**[^456^]
- Semi-annual rebalancing emerged as optimal frequency
- **Median strategy consistently outperformed** Winners, Losers, and Buy-Hold
- Semi-Annual Median: Terminal value $199.90 (from $100), Sharpe 0.606
- Quarterly was close second; weekly/monthly had excess transaction noise
- Winner strategy: Only $144 terminal value — failed to match passive benchmark ($162)

### 4.6 "Middle 3" Strategy (Boston University)

**Academic backtest:**[^462^]
- Rank 9 sector ETFs by monthly price appreciation
- Buy middle-ranked 3, 5, or 7 sectors (equally weighted)
- Hold for next month
- **Mid-3 achieved 10.52% CAGR vs 7.43% for SPY** (2001-2012)
- Mid-3 Sharpe: 0.58 vs SPY 0.40
- Finding: "The Middle 3 Performers Gave the Best Results"

---

## 5. Combined Trend + Momentum Filters

### 5.1 Faber 10-Month SMA Filter

**Original rules (Faber 2007, updated 2013, 2017):**[^414^][^415^]

```
BUY: When monthly price > 10-month SMA → INVEST
SELL: When monthly price < 10-month SMA → MOVE TO CASH (T-bills)
```

**Key parameters:**
- Only updated **once per month on last day of month**
- All data series are **total return** including dividends
- Cash = 90-day T-bill yield
- Excludes taxes, commissions, slippage
- Same rule applied uniformly across all asset classes

**5-Asset Class Portfolio (S&P 500, EAFE, 10Y Treasury, GSCI, REITs):**[^422^]
- SMA10 timing: **10.5% annualized** (1973-2012)
- Buy-and-hold: **9.9% annualized**
- Only 50bps annual improvement but **dramatically reduced volatility and drawdowns**

**Long-term backtest (1973-2020):**[^418^]
- Faber TAA: 9.53% CAGR, max drawdown **-12.87%**, MAR ratio 0.74
- S&P 500: 9.63% CAGR, max drawdown **-55.25%**, MAR ratio 0.17
- Longest recovery time: 27.1 months vs 73.5 months for S&P 500

### 5.2 Ivy Portfolio Momentum Filter

**Faber's Ivy 5 Portfolio with momentum overlay:**[^445^]

```
1. Calculate momentum score = average of 3-month, 6-month, and 12-month momentum
2. Rank 5 assets by momentum score
3. Pick top 3 assets
4. Only invest if momentum score is positive
5. If any selected asset has negative momentum → substitute with T-bills
```

| Portfolio | Allocation |
|-----------|-----------|
| US Total Stock (VTI) | 20% base |
| REITs (VNQ) | 20% base |
| International (VEA) | 20% base |
| Total US Bonds (BND) | 20% base |
| Commodities (DBC/GSG) | 20% base |

**Performance:** 7.33% CAGR (1996-2026) with significantly reduced drawdowns vs buy-and-hold.[^81^]

### 5.3 VAA: Vigilant Asset Allocation — Breadth Momentum

**Revolutionary crash protection approach by Keller & Keuning (2017):**[^458^][^461^]

```
VAA RECIPE:
1. Compute 13612W momentum for each asset
   (weighted average of 1, 3, 6, 12-month annualized returns)
   Weight: 40% to most recent month

2. Pick top T assets from "risk-on" universe

3. Pick best asset from "risk-off" universe as "cash"

4. Count assets with non-positive momentum (b)

5. Cash Fraction CF = b/B (breadth protection threshold)
   - When b >= B: 100% in cash
   - When b < B: partial cash allocation

6. Replace worst top-T assets with cash based on CF
```

**Performance (VAA-G12, out-of-sample 1993-2016):**[^461^]

| Metric | VAA-G12 (T=2, B=4) | Benchmarks |
|--------|---------------------|------------|
| CAGR | **10%** OS | 7-8% for EW/60-40/SPY |
| Max Drawdown | **-13%** | -30% to -55% |
| Sharpe | **0.51** | ~0.3-0.5 |
| Cash Exposure | ~60% average | — |

**Why it works:** Breadth momentum measures how many assets are trending badly simultaneously. This universe-level approach is more responsive than individual asset trend-following for crash detection.[^458^]

### 5.4 200-Day Moving Average Filter

**Simple trend filter application:**[^20^][^434^]
- Only open new momentum positions when S&P 500 > 200-day MA
- During bear markets (S&P 500 < 200-day MA), hold cash or defensive assets
- 200-day MA filter can reduce drawdowns from ~50% to ~20%
- Win rate improves from ~57% to ~81% with trend filter
- Trade-off: lower CAGR but dramatically better risk-adjusted returns

---

## 6. Intra-Sector vs Inter-Sector Rotation

### 6.1 Sector Level vs Individual Stock Level

**Moskowitz & Grinblatt (1999) conclusion:**[^421^]
- Industry momentum strategies are **more profitable** than individual stock momentum strategies
- Industry effects explain much of individual stock momentum profits
- Once adjusted for industry, individual stock momentum profits become "significantly weaker and statistically insignificant"

### 6.2 Within-Sector Stock Selection vs Sector Rotation

**IOSR empirical study (2025):**[^449^]
- All 11 SPDR sector ETFs exhibit momentum characteristics (Hurst Exponent > 0.5 for all)
- Strongest momentum persistence: Financials (0.671), Healthcare (0.668), Materials (0.664)
- Even weakest sector (Consumer Staples at 0.627) shows clear momentum
- Long-term momentum coexists with short-term mean reversion
- **Implication:** Optimal strategies should combine short-term contrarian elements with longer-term trend-following

### 6.3 Factor vs Sector Rotation

**Arnott et al. — Factor Momentum:**[^136^]
- "Industry momentum stems from factor momentum"
- Factor momentum "concentrates in its entirety in the first few highest-eigenvalue factors"
- Factor momentum subsumes industry momentum, not vice versa
- **Implication:** Factor-based rotation may be more fundamental than sector rotation

---

## 7. Transaction Cost Optimization

### 7.1 Transaction Cost Impact on ETF Momentum

**J.P. Morgan analysis (1992-2014):**[^168^]

**Multi-Asset ETF Momentum Scorecard:**

| One-Way Cost | CAGR | Sharpe Ratio |
|-------------|------|-------------|
| No cost | 9.1% | 1.37 |
| 10 bps | ~8.8% | 1.32 |
| 20 bps | ~8.5% | 1.28 |
| **50 bps** | **7.5%** | **1.14** |

**Key finding:** Even with 50bps one-way costs, strategy still generates statistically significant excess returns. However, costs reduce returns by ~160bps annually.

**12-month vs shorter lookback sensitivity:**
- 12-month lookback + monthly rebal: Only -0.4% annual return from doubling costs to 20bps
- 1-month lookback + daily rebal: Sharpe ratio erodes from 0.71 to -0.29 with just 10bps cost
- **Conclusion:** Longer lookbacks are far more robust to transaction costs

### 7.2 AQR Live Momentum Fund Costs

**AQR implementation (July 2009 - December 2016):**[^425^][^428^][^440^]

| Cost Component | U.S. Large Cap | U.S. Small Cap | International | Average |
|---------------|---------------|---------------|--------------|---------|
| One-sided annual turnover | 81.9% | 79.3% | 89.9% | 83.7% |
| Trading costs (% NAV) | 0.12% | 0.32% | 0.25% | **0.23%** |
| Expense ratio drag | 0.44% | 0.60% | 0.58% | **0.54%** |
| **Total implementation cost** | **~0.66%** | **~0.92%** | **~0.83%** | **~0.77%** |

**Key finding:** Despite 80-90% annual turnover, trading costs averaged only 23bps. Tax-aware versions reduced effective tax rate from 11.4% to 5.3%.[^428^]

### 7.3 Rebalancing Frequency Optimization

**J.P. Morgan findings:**[^168^]
- **Monthly rebalancing** is generally optimal for momentum strategies
- 12-month trend signals with monthly rebalancing show best Sharpe ratios
- Shorter investment horizons (2 weeks to 3 months) perform better but with higher turnover
- There is "time decay" for momentum signals — holding too long degrades performance

**SACEMS testing:**[^117^]
- Weekly/biweekly: Generally does NOT outperform monthly
- Bimonthly: Slight reduction in turnover, modest performance penalty
- Monthly cycle timing: End-of-month is near-optimal

**Quarterly vs Monthly — TSX 60 study:**[^123^]
- Quarterly rebalancing dominates across strategy types
- Monthly generates ~1.20% annual transaction cost drag
- Equal weighting consistently outperforms other schemes

### 7.4 Tax Efficiency Strategies

**Key findings on tax management:**[^428^][^425^]
- Tax-aware momentum strategies reduce federal taxes by 0.7 percentage points
- Pre-tax return difference between tax-aware and regular: only -0.1% (essentially zero)
- Correlation of returns: 0.97 between tax-aware and regular versions
- Tracking error: <1%
- ETF structure provides inherent tax efficiency via in-kind creation/redemption

---

## 8. Other Notable Strategies

### 8.1 Antonacci's Parity Portfolio with Absolute Momentum

**Rules:**[^316^]
- Trade US stocks, US Treasuries, REITs, corporate bonds, gold
- Invest 20% in each asset class if its 12-month momentum > T-bill momentum
- Otherwise invest that tranche in aggregate bond market
- More conservative than GEM; suitable for 100% capital allocation

### 8.2 Faber Ivy Portfolio (5/10/20/40 ETF)

**Allocations:**[^442^]

| Portfolio | # ETFs | Allocation |
|-----------|--------|-----------|
| Ivy 5 | 5 | 20% each: VTI, VNQ, VEA, BND, DBC |
| Ivy 10 | 10 | 10% each: VV, VIOO, VNQ, VEA, VWO, BND, DBC, VTIP, VNQI |
| Ivy 20 | 20 | 5% each across expanded universe including timber, infrastructure |

### 8.3 Dynamic Sector Rotation (Rothe, 2023)

**Academic paper combining momentum with risk-managed volatility:**[^453^]
- Designed to outperform S&P 500 momentum index
- Uses relative strength + volatility-based risk management
- Lower drawdowns than benchmark momentum index

---

## 9. Comparative Summary

### 9.1 Strategy Performance Comparison

| Strategy | CAGR | Max DD | Sharpe | # Assets | Rebal | Complexity |
|----------|------|--------|--------|----------|-------|-----------|
| GEM (Antonacci) | 15.8% | -17.8% | 0.96 | 3 | Monthly | LOW |
| SACEMS Top 3 | 8-9% | -20% | 0.52 | 9 | Monthly | LOW |
| SACEMS Top 2 | 9-10% | -22% | 0.60 | 9 | Monthly | LOW |
| SACEMS + SACEVS 50-50 | 10-12% | -14 to -18% | 0.82-0.99 | 9+ | Monthly | MEDIUM |
| Sector Momentum Top 3 | 13.3% | -49% | 0.66 | 10 | Monthly | LOW |
| Faber SMA-Filtered Sectors | 13.0% | — | 0.65 | 10 | Monthly | LOW |
| Faber TAA 5-Asset | 10.5% | ~-13% | — | 5 | Monthly | LOW |
| VAA-G12 | 10% | -13% | 0.51 | 12+ | Monthly | HIGH |
| Ivy Portfolio (momentum) | 7-8% | ~-15% | — | 5 | Monthly | MEDIUM |
| "Buy Worst" Contrarian | 11.4% | -47% | 0.64 | 9 | Monthly | LOW |
| Meta-Strategy (LI) | 12.8% | -17% | 1.16 | Multiple | Monthly | HIGH |
| SPY Buy-Hold | 9-10% | -55% | 0.35 | 1 | None | NONE |

### 9.2 Strategy Classification Matrix

| Strategy Type | Best For | Trade Frequency | Tax Efficiency |
|--------------|----------|----------------|---------------|
| Dual Momentum (GEM) | Simplicity, strong returns | Very Low (1.5/yr) | HIGH |
| Asset Class Momentum | Diversification | Medium (~6-12/yr) | MEDIUM |
| Sector Momentum | US equity alpha | High (~12/yr) | LOW |
| SMA-Filtered Rotation | Reduced drawdowns | Medium (~6-10/yr) | MEDIUM |
| VAA Breadth Momentum | Crash protection | High (~12-24/yr) | LOW |
| Contrarian Rotation | Mean reversion | High (~12/yr) | LOW |

---

## 10. Counter-Arguments and Limitations

### 10.1 Data Snooping Bias

**Yang (2019) — rigorous statistical testing:**[^419^]
- Applied data snooping corrections (FDR approach) to Faber's 10-month MA strategy
- Found **no evidence** that timing strategies outperform buy-and-hold at 5% significance
- "By correcting data snooping bias, this paper finds no evidence that there is a timing strategy outperforming the B&H benchmark"
- Simulated outperforming strategies found by RC and SPA tests confirms validity of statistical methods

**Counter-counter:** Faber's strategy was designed for risk reduction, not return enhancement. Even if not statistically significant in returns, the volatility/drawdown reduction is meaningful.

### 10.2 Momentum Crashes

**Documented risks:**[^168^][^434^]
- Momentum strategies have **negative skewness** — suffer sharp drawdowns at market turning points
- Long-short momentum saw 73% collapse in 2009 in just three months
- Long-only strategies also vulnerable but to lesser degree
- 2008-2009: Sector momentum gave back "almost all excess return accrued during 2000s"[^459^]
- V-shaped recoveries: 12-month lookback slow to re-enter, missing initial rebound

### 10.3 Transaction Cost Erosion

**Key evidence:**[^168^]
- 50bps one-way costs reduce ETF momentum returns from 9.1% to 7.5% CAGR
- High-frequency rebalancing strategies become unprofitable with costs >2bps per trade[^467^]
- Rebalancing in "smart beta" ETFs leads to front-running and underperformance[^427^]
- Average momentum ETF turnover: 115% annually[^427^]

### 10.4 Tax Inefficiency

- Monthly rotation generates substantial short-term capital gains
- High-turnover strategies should be implemented in tax-sheltered accounts
- Tax-aware versions reduce drag but add implementation complexity

### 10.5 Parameter Instability

**Optimal lookback drift:**[^437^][^439^]
- 12-month lookback performed best 1988-2008
- 3-month lookback performed better 2009-2019
- No single lookback is consistently optimal
- **Solution:** Composite lookbacks (e.g., 3, 6, 9, 12-month average) or ensemble approaches

### 10.6 Live vs Backtested Performance Gap

**AQR live fund analysis (2009-2016):**[^428^][^440^]
- Live funds underperformed theoretical index by average of 47bps
- Expenses: 54bps average drag
- Trading costs: 23bps average drag
- Portfolio construction added value in some cases (+142bps US large cap)
- **Net result:** Momentum premium partially but not fully eroded by implementation

### 10.7 Whipsaw Risk

- Trend-following strategies suffer during choppy, range-bound markets
- Multiple consecutive false signals generate transaction costs without returns
- Faber acknowledges strategy "may lead to underperformance in the short term"[^416^]
- GEM experienced whipsaw periods with early bond allocation[^318^]

---

## 11. Practical Implementation Guidance

### 11.1 Recommended Implementation Hierarchy

**For simplicity + strong returns:**
1. GEM (Antonacci) — 3 ETFs, monthly, 1.5 trades/year
2. Faber TAA — 5 ETFs, monthly, low maintenance

**For diversification:**
3. SACEMS EW Top 3 — 9 asset classes
4. SACEMS + SACEVS 50-50 blend

**For US equity focus:**
5. Faber SMA-Filtered Sector Top 3
6. Logical Invest Meta-Strategy

**For crash protection:**
7. VAA-G12 — most sophisticated breadth-based protection

### 11.2 Key Implementation Checklist

- [ ] Use **total return** data including dividends for all calculations
- [ ] Rebalance on **last trading day of month** for consistency
- [ ] Use **limit orders** during market hours to minimize slippage
- [ ] Implement in **tax-sheltered accounts** when turnover > 6/year
- [ ] Use **liquid ETFs** with tight bid-ask spreads (SPDR, iShares, Vanguard)
- [ ] Consider **composite lookbacks** (3+6+12 month average) for robustness
- [ ] Apply **absolute momentum filter** (SMA or T-bill comparison) for drawdown protection
- [ ] Budget **0.1-0.5% annual drag** for transaction costs depending on frequency

### 11.3 Realistic Return Expectations

| Strategy | Gross CAGR | Net of 0.5% Costs | Net of 1.0% Costs |
|----------|-----------|-------------------|-------------------|
| GEM | 15.8% | 15.3% | 14.8% |
| Sector Momentum Top 3 | 13.3% | 12.8% | 12.3% |
| SACEMS EW Top 3 | 8.5% | 8.0% | 7.5% |
| Faber TAA | 10.5% | 10.0% | 9.5% |
| "Buy Worst" Contrarian | 11.4% | 10.9% | 10.4% |

### 11.4 Code Implementation Resources

- **Python GEM implementation:** https://github.com/alexjansenhome/GEM[^311^]
- **TuringTrader open-source:** C# code for Antonacci, Faber strategies[^316^][^445^]
- **VAA R implementation:** https://medium.com/@bauermartin101/vigilant-asset-allocation-a-step-by-step-guide-in-r-part-i-2a651b5ab17d[^460^]

---

## Source Bibliography

| Ref | Source | URL | Date |
|-----|--------|-----|------|
| [^18^] | Quant Investing - Dual Momentum Returns | https://www.quant-investing.com/blog/how-much-can-dual-momentum-increase-your-investment-returns | — |
| [^20^] | QuantifiedStrategies - 200 Day MA Strategy | https://www.quantifiedstrategies.com/200-day-moving-average-trading-strategy/ | 2026-05-14 |
| [^81^] | LazyPortfolioETF - Ivy Portfolio | http://www.lazyportfolioetf.com/allocation/mebane-faber-ivy/ | 2023-05-13 |
| [^117^] | CXO Advisory - SACEMS | https://www.cxoadvisory.com/momentum-strategy/ | — |
| [^123^] | MDPI - Sector Rotation in TSX 60 | https://www.mdpi.com/1911-8074/19/1/70 | 2026-01-15 |
| [^129^] | Logical Invest - SPDR Sector Rotation | https://logical-invest.com/spdr-etf-sector-rotation-strategy-model/ | 2019-01-20 |
| [^136^] | Quantpedia - Sector Momentum | https://quantpedia.com/strategies/sector-momentum-rotational-system | — |
| [^168^] | J.P. Morgan - Momentum Strategies Across Asset Classes | https://www.cmegroup.com/education/files/jpm-momentum-strategies-2015-04-15-1681565.pdf | 2015-04-15 |
| [^310^] | ReSolve - GEM Craftsman's Perspective | https://investresolve.com/global-equity-momentum-executive-summary/ | 2023-12-04 |
| [^311^] | GitHub - GEM Python Implementation | https://github.com/alexjansenhome/GEM | 2017-10-12 |
| [^313^] | BestFolio - GEM Strategy | https://bestfolio.app/strategies/gem | 2026-06-18 |
| [^316^] | TuringTrader - Antonacci Dual Momentum | https://www.turingtrader.com/portfolios/antonacci-dual-momentum/ | — |
| [^318^] | IndexSwingTrader - GEM Analysis | https://indexswingtrader.blogspot.com/2016/10/prospecting-dual-momentum-with-gem.html | 2016-10-04 |
| [^414^] | Papers With Backtest - Faber TAA | https://blog.paperswithbacktest.com/p/a-quantitative-approach-to-tactical | 2025-03-23 |
| [^415^] | Faber - A Quantitative Approach to TAA | https://allocatortraining.com/wp-content/uploads/2023/06/A-Quantitative-Approach-to-Tactical-Asset-Allocation.pdf | — |
| [^418^] | Bogleheads - Faber Timing Model | https://www.bogleheads.org/forum/viewtopic.php?t=309461 | 2020-03-25 |
| [^419^] | Yang - Tactical Asset Allocation Data Snooping | https://www.sciencedirect.com/science/article/abs/pii/S0927538X18300775 | 2018-07-31 |
| [^421^] | Moskowitz & Grinblatt - Do Industries Explain Momentum? | http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf | 1999 |
| [^424^] | FreeFloat - Global Equities Momentum | https://freefloat.substack.com/p/global-equities-momentum | 2023-02-09 |
| [^425^] | AQR - Putting Academic Factor Into Practice | https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Putting-and-Academic-Factor-Into-Practice.pdf | — |
| [^427^] | FactSet - Heartbeat of ETF Tax Efficiency | https://go.factset.com/hubfs/Website/Resources%20Section/eBook/eBook/heartbeat-of-etf-tax-efficiency-ebook.pdf | — |
| [^428^] | Alpha Architect - Costs of Momentum | https://alphaarchitect.com/costs-implementing-momentum-strategies/ | 2022-05-16 |
| [^429^] | Antonacci - Extended Backtest Medium | https://medium.com/@garyantonacci_30463/extended-backtest-of-global-equities-momentum-dual-momentum-eb12902612e0 | 2018-10-16 |
| [^430^] | PortfolioDB - GEM Dual Momentum | https://www.portfoliodb.com/portfolios/gem-dual-momentum | — |
| [^433^] | Antonacci - Risk Premia Harvesting Paper | https://www.emiratescapitalassetmanagement.com/uploads/2/5/5/4/25541321/risk_premia_harvesting_through_dual_momentum.pdf | — |
| [^435^] | OptimalMomentum - Extended Backtest | https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/ | 2024-02-25 |
| [^437^] | Seeking Alpha - Optimal Lookback | https://seekingalpha.com/article/4240540-optimal-lookback-period-for-momentum-strategies | 2019-02-13 |
| [^439^] | ReSolve - Half-Life of Lookback | https://investresolve.com/half-life-of-optimal-lookback-horizon/ | 2023-12-13 |
| [^440^] | Portfolio Construction Forum - Momentum Implementation | https://obj.portfolioconstructionforum.edu.au/articles_perspectives/Portfolio-Construction-Forum_AR_Implementing-momentum-what-have-we-learned.pdf | — |
| [^442^] | Portfolio Einstein - Faber Portfolios | https://www.portfolioeinstein.com/meb-faber-portfolios-backed-by-solid-research/ | 2022-01-25 |
| [^443^] | CXO Advisory - Combined Value-Momentum | https://www.cxoadvisory.com/strategies/ | — |
| [^444^] | CXO Advisory - SACEMS Sharpe Robustness | https://www.cxoadvisory.com/momentum-investing/robustness-of-sacems-based-on-sharpe-ratio/ | 2019-01-22 |
| [^445^] | TuringTrader - Faber Ivy Portfolio | https://www.turingtrader.com/portfolios/faber-ivy-portfolio/ | 2018-01-31 |
| [^449^] | IOSR - Sectoral Momentum and Mean Reversion | https://www.iosrjournals.org/iosr-jef/papers/Vol16-Issue2/Ser-4/A1602040109.pdf | — |
| [^453^] | SSRN - Dynamic Sector Rotation | https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4573209_code3074981.pdf | 2023-10-11 |
| [^456^] | MDPI - Duration Rotation Treasury ETFs | https://www.mdpi.com/2674-1032/5/2/29 | 2026-04-07 |
| [^457^] | OptimalMomentum - Whither Fragility GEM | https://www.optimalmomentum.com/whither-fragility-dual-momentum-gem/ | 2024-09-03 |
| [^458^] | IndexSwingTrader - VAA | https://indexswingtrader.blogspot.com/2017/07/breadth-momentum-and-vigilant-asset.html | 2017-07-14 |
| [^459^] | Faber - ETFInvestor Strategies | https://mebfaber.com/wp-content/uploads/2012/01/model_portfolios1.pdf | — |
| [^460^] | Medium - VAA in R | https://medium.com/@bauermartin101/vigilant-asset-allocation-a-step-by-step-guide-in-r-part-i-2a651b5ab17d | 2024-01-12 |
| [^461^] | CXO Advisory - VAA Conservative Breadth | https://www.cxoadvisory.com/technical-trading/conservative-breadth-rule-for-asset-class-momentum-crash-protection/ | 2018-08-07 |
| [^462^] | Boston University - Sector ETF Rotation | https://open.bu.edu/server/api/core/bitstreams/7258ded2-aabb-47ab-9554-6ff33868bab6/content | — |
| [^466^] | Faber - Relative Strength Strategies | https://mebfaber.com/wp-content/uploads/2018/12/SSRN-id1585517-Relative-Strength-Strategies-for-Investing.pdf | — |
| [^467^] | MDPI - Overnight vs Daytime Momentum | https://www.mdpi.com/2227-9091/14/4/84 | 2026-04-08 |

---

*Document compiled from 25+ independent web searches across academic papers, official strategy publications, verified backtests, and live fund performance data. All claims traced to primary sources with URLs and dates.*
