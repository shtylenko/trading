# Facet: Momentum & Trend-Following Strategies (LONG-ONLY)

## Key Findings Summary

1. **No widely-documented, long-only momentum strategy consistently achieves >3% monthly (~36% CAGR) over multi-decade backtests.** The highest verified long-only momentum returns are in the 17-23% CAGR range for stock-level systems (Weekend Trend Trader on Midcaps: 22.9%; Alpha Architect 50-stock momentum: 17.36% gross 1970-2016; CANSLIM screener: 30.86% in one 1998-2005 study). [^78^] [^83^] [^65^]

2. **Gary Antonacci's Dual Momentum (GEM)** is the most-cited academic momentum system: 17.43% annualized over 39 years (1974-2013) with max drawdown of only 22.7%, using just two equity ETFs and an absolute momentum cash filter. Monthly rebalancing. [^18^] [^19^]

3. **The Weekend Trend Trader by Nick Radge** produced the strongest stock-level backtest results: 22.9% CAGR on S&P Midcap 400 (1990-present), though with 58% max drawdown. Uses weekly 20-week breakout + 40% trailing stop. [^78^]

4. **Wilcox & Crittenden's "Does Trend Following Work on Stocks?" (2005, updated 2025)** is the definitive academic work on long-only stock trend following. Gross CAGR of 15.19% (1991-2024) with 6.18% annualized alpha. **However**, net-of-fees the strategy is not viable below $1M AUM due to high daily turnover. Their "Turnover Control" algorithm makes it viable for smaller portfolios. [^23^] [^25^]

5. **Jegadeesh-Titman (1993, 2001) momentum** is the foundational academic paper showing ~1% per month (12% annualized) from buying past winners and selling past losers. The long-only version of this strategy historically yields about 0.7-1.0% monthly. [^68^] [^64^]

6. **Risk-managed momentum (Barroso & Santa-Clara 2015)** reduces crash risk by volatility-scaling, nearly doubling the Sharpe ratio, but at the cost of lower raw returns. Traditional momentum can crash 34.7% in a single month during panic states. [^85^] [^86^]

7. **A momentum strategy on Taiwan stocks achieved 31.1% annualized (~2.6% monthly)** with beta 0.79, confirming that momentum effects are stronger in less efficient markets. [^1^]

8. **Concentrated, high-turnover momentum on select tech-stock universes** has shown 30-52% CAGR in recent backtests (2017-2026), but these are likely overfitted to the strong tech bull market and suffer from selection bias. [^95^] [^92^]

---

## Major Players & Sources

| Entity | Role/Relevance |
|--------|----------------|
| **Gary Antonacci** | Creator of Dual Momentum; Harvard MBA; Wagner Award winner. His GEM model is the simplest implementable dual momentum system. Website: optimalmomentum.com [^18^] |
| **Nick Radge** | Australian money manager; author of "Weekend Trend Trader." Developed the 20-week breakout system for part-time traders. [^78^] |
| **Cole Wilcox & Eric Crittenden** | Authored "Does Trend Following Work on Stocks?" (2005); updated by Zarattini, Pagani & Wilcox (2025). Foundational research on all-time-high breakout systems. [^23^] [^25^] |
| **Meb Faber** | Cambria Investment Management; popularized the Ivy Portfolio and GTAA 13 tactical asset allocation using 10-month moving averages. [^55^] [^77^] |
| **Jim O'Shaughnessy** | Author of "What Works on Wall Street"; documented four key factors (value, size, momentum, quality) with multi-decade backtests showing momentum's persistence. [^37^] |
| **Jegadeesh & Titman** | Published the seminal "Returns to Buying Winners and Selling Losers" (1993), establishing momentum as a premium factor. [^68^] |
| **Mark Minervini** | Stock-specific momentum trader; developed the 8-point "Trend Template" combining moving average alignment with earnings growth. No verified CAGR data. [^106^] |
| **Barroso & Santa-Clara** | Pioneered risk-managed momentum (2015), showing volatility scaling virtually eliminates crash risk. [^85^] |

---

## Trends & Signals

- **Momentum factor has persisted for 200+ years across global markets**, documented by Geczy & Samonov (2015) in "215 Years of Global Multi-Asset Momentum: 1800-2014" [^27^]
- **Sector rotation using 12-month momentum** on US sector ETFs produced 13.94% annualized from 1928-2009 with lower drawdowns than buy-and-hold [^70^]
- **Enhanced Dual Momentum with Global Growth Cycle** (OECD CLI data) improved CAGR from 14.8% to 16.4% and reduced max drawdown from -20.5% to -16.8% [^26^]
- **Risk-managed momentum strategies** (volatility targeting, conditional volatility) are becoming standard, as traditional momentum's crash risk is now well-documented [^85^] [^86^]
- **Alternative momentum definitions** (residual momentum, analyst forecast revisions, news sentiment) provide similar long-term returns with lower crash severity [^87^]

---

## Controversies & Conflicting Claims

1. **Raw returns vs. net-of-fees**: The Wilcox/Crittenden trend-following system shows exceptional gross returns (15.19% CAGR, 6.18% alpha) but the paper explicitly states "the base trend-following approach is not viable for smaller portfolios (AUM less than $1M) due to the dampening effect of trading costs." [^25^] This is a critical caveat for retail traders.

2. **Momentum crash risk**: Traditional momentum can lose 34.7% in a single month during panic states [^85^]. The 2008 GFC and 2020 COVID crashes destroyed years of momentum gains. Long-short momentum has conditional negative beta that causes crashes during sharp rebounds. Long-only versions are less affected but still suffer.

3. **Lookback period cherry-picking**: The "Dual Momentum - Global Growth Cycle Enhanced" strategy conveniently finds that 12 months is the best lookback period [^26^]. Many published strategies optimize on the best parameter without robustness testing.

4. **Selection bias in tech-stock momentum**: A Reddit user posted a 52.53% CAGR momentum strategy (2017-2026) on a universe of 30 hand-picked tech stocks [^95^]. This coincides with the strongest tech bull market in history and is almost certainly overfitted.

5. **Golden Cross underperformance in bull markets**: While the Golden Cross achieves 79% win rate and limits drawdowns to 33%, it only returns 6.8% CAGR (price-only) vs. 7.2% for buy-and-hold, and badly underperforms during strong bull runs due to whipsaws [^38^].

6. **CANSLIM claims of 30.86% annualized** from one study (Schadler & Cotton, 1998-2005) [^65^] are contradicted by other CANSLIM backtests showing only 13.3% in single-year tests [^62^] and 14.21% in a 1999-2013 test [^65^]. The extremely high returns may be data mining.

7. **The 200-day moving average as a trend filter works well for defense but hurts offense**: Adding a 200-day MA filter to an RSI strategy cut CAGR from 8.7% to 7.1% but reduced max drawdown from 29% to 14% [^20^].

---

## Recommended Deep-Dive Areas

1. **Weekend Trend Trader on S&P Midcap 400 (22.9% CAGR)**: The highest-verified long-only stock strategy found. Worth investigating whether trailing stop optimization (20% vs 40%) can push returns above 30% CAGR in smaller-cap segments. [^78^]

2. **Concentrated 10-20 stock momentum in less efficient markets**: The Taiwan momentum strategy achieved 31.1% annualized. Similar approaches in emerging markets or small-cap US stocks may approach the 3% monthly target. [^1^]

3. **CANSLIM-style earnings momentum**: The combination of technical price momentum with accelerating earnings (EPS growth >25%) showed 30.86% in one study. Rigorous backtesting with realistic slippage is needed. [^65^]

4. **Risk-managed momentum with higher target volatility**: Barroso & Santa-Clara's risk-managed momentum used 12% target volatility. Raising the target could increase raw returns while maintaining crash protection. [^85^]

5. **Weekly-rebalanced concentrated momentum on liquid growth stocks**: The SimFin strategy achieved 30% CAGR with weekly rebalancing. This high-frequency approach may be viable for traders who can automate execution. [^92^]

6. **Multi-factor combination (momentum + quality)**: BacktestIndia's "Quality Momentum" approach achieved 17.95% net CAGR with lower drawdowns than pure momentum. The quality filter removes speculative names that cause the worst crashes. [^93^]

---

## Strategy Details

---

### Strategy 1: Gary Antonacci's Dual Momentum (Global Equity Momentum)

**Type**: Dual Momentum (Relative + Absolute) | ETF-based

**Trading Rules**:
1. At the end of each month, compare the past 12-month total returns of:
   - US Stocks (S&P 500 / SPY)
   - International Stocks (MSCI EAFE / EFA or ACWI ex-US)
2. **Relative Momentum step**: Select the asset with the higher 12-month return
3. **Absolute Momentum step**: If the selected asset's return is positive (> T-bills), invest 100% in it. If negative, move 100% to intermediate-term bonds (AGG/TLT)
4. Hold for one month, then repeat the assessment

**Performance**:
| Metric | GEM Strategy | Benchmark (ACWI) |
|--------|-------------|-----------------|
| CAGR (1974-2013) | **17.43%** | 8.85% |
| Max Drawdown | **-22.7%** | -60.21% |
| Sharpe Ratio | ~0.90 | ~0.38 |
| Trades per year | ~1.5 (very low turnover) |

**Caveats**: A more recent ETF-based backtest (2005-present) showed only 6.75% CAGR with 30% max drawdown, failing to beat SPY's 9.2% CAGR [^19^]. The discrepancy highlights that Antonacci's longer-term index-based results are better than recent ETF-based implementations.

**Achieves >3% monthly?** No. Averages ~1.45% monthly over 39 years.

**Sources**: [^18^] [^19^] [^27^]

---

### Strategy 2: Weekend Trend Trader (Nick Radge)

**Type**: Weekly trend-following breakout | Stock-based

**Trading Rules**:
1. **Universe**: S&P Midcap 400 or S&P 500 stocks (liquid, large-cap)
2. **Market Regime Filter**: Underlying index must be above its 10-week/50-day moving average
3. **Entry**: Stock makes a new 20-week high AND 20-week Rate of Change > 30% (strong acceleration)
4. **Position Sizing**: Equal-weight positions (e.g., 5-10% of capital per position, max 10-20 positions)
5. **Initial Stop Loss**: 40% trailing stop below the highest close (adjusted to 10% when market filter turns bearish)
6. **Exit**: Price closes below trailing stop (reviewed weekly on Friday after market close)
7. **Execution**: Scan on weekend, place orders for Monday open

**Performance across different universes**:
| Index | CAGR | Max Drawdown | # Trades (since 1990) | Avg Hold |
|-------|------|-------------|----------------------|----------|
| S&P 100 (OEX) | 14.9% | -51% | 217 | 65 weeks |
| S&P 500 (SPX) | 19.9% | -43% | 248 | 103 weeks |
| Nasdaq 100 (NDX) | 16.5% | -55% | 286 | 72 weeks |
| **S&P Midcap 400 (MID)** | **22.9%** | **-58%** | **303** | **121 weeks** |
| S&P Smallcap 600 (SML) | 9.1% | -69% | 377 | 121 weeks |
| Russell 2000 (RUT) | 0.1% | -81% | 675 | 100 weeks |

**Key Insights**: Midcaps significantly outperform both large and small caps. The 40% trailing stop (not 20%) is critical for midcaps to avoid whipsaws. Russell 2000 performs terribly (likely due to mean-reversion characteristics).

**Transaction Costs**: Not included in backtest. Commissions assumed low due to low trade frequency.

**Achieves >3% monthly?** No. Midcap version averages ~1.9% monthly. The highest-performing variant.

**Sources**: [^78^] [^94^] [^96^]

---

### Strategy 3: All-Time-High Trend Following (Wilcox & Crittenden)

**Type**: Long-only stock trend following | Daily rebalancing

**Trading Rules**:
1. **Universe**: All liquid US stocks (Russell 3000), price > $10, 42-day avg dollar volume > $1M (inflation-adjusted)
2. **Entry**: Buy at market open when a stock closes at or above its prior all-time highest close
3. **Exit**: 10x ATR(20) trailing stop (Chandelier-style: highest close since entry minus 10x ATR). Exit on next day's open after stop breach.
4. **Position Sizing**: Volatility-based, risk ~1% of equity per trade, max leverage 200%
5. **Re-entry**: Allowed on new all-time highs

**Performance (1991-2024)**:
| Metric | Gross | Net (after costs) |
|--------|-------|-------------------|
| CAGR | **15.19%** | Varies by AUM |
| Annualized Alpha | **6.18%** | - |
| Max Drawdown | -33.74% | - |
| Sharpe Ratio | 1.24 | - |

**Critical Caveat**: High daily turnover makes this expensive for small accounts. Not viable below $1M AUM without the "Turnover Control" algorithm introduced in the 2025 update. With Turnover Control, the strategy becomes attractive across all portfolio sizes even after fees. [^25^]

**Transaction Costs**: 0.5% round-trip (25 bps per side) assumed in backtest

**Achieves >3% monthly?** No. Gross ~1.26% monthly. Net would be lower.

**Sources**: [^23^] [^25^] [^80^]

---

### Strategy 4: 200-Day Moving Average Crossover System

**Type**: Simple trend-following | Index/ETF-based

**Trading Rules**:
1. Buy when S&P 500 closing price crosses above the 200-day SMA
2. Sell when closing price crosses below the 200-day SMA
3. Hold cash (T-bills) when below the 200-day MA

**Performance (S&P 500, 1960-present)**:
| Metric | 200-MA Strategy | Buy & Hold |
|--------|-----------------|------------|
| CAGR (price only) | 6.75% | 7.0% |
| Max Drawdown | **-28%** | -56% |
| # Trades | 199 | 1 |
| Win Rate | ~50% | N/A |
| Avg Gain/Trade | 2.4% | N/A |

**Key Insights**: The strategy keeps pace with buy-and-hold while cutting drawdowns by half. However, it underperforms badly during bull markets (CAGR only 8.5% vs 12.8% for buy-and-hold from March 2009). Whipsaws in 2010 caused 7 trades with only 1 winner. Best used as a defensive overlay rather than a return generator.

**Transaction Costs**: Low (only ~2.4 trades per year)

**Achieves >3% monthly?** No. Averages ~0.56% monthly.

**Sources**: [^20^]

---

### Strategy 5: Golden Cross (50/200 MA Crossover)

**Type**: Moving average crossover | Index/ETF-based

**Trading Rules**:
1. Buy when 50-day SMA crosses above 200-day SMA
2. Sell when 50-day SMA crosses below 200-day SMA (Death Cross)
3. Remain in cash during death cross periods

**Performance (S&P 500, 1960-present)**:
| Metric | Golden Cross | Buy & Hold |
|--------|-------------|------------|
| CAGR (price only) | 6.8% | 7.2% |
| Time in Market | 70% | 100% |
| Max Drawdown | **-33%** | -56% |
| Win Rate | **79%** | N/A |
| Avg Gain/Trade | 15.8% | N/A |
| Risk-Adj Return | **9.6%** | 6.9% |
| # Trades | 33 | 1 |

**Key Insights**: The Golden Cross is a defensive strategy. It doesn't beat buy-and-hold in raw returns but has dramatically better risk-adjusted returns and a 79% win rate. The low trade count (33 trades in 66 years) means minimal transaction costs.

**Transaction Costs**: Negligible (0.5 trades per year)

**Achieves >3% monthly?** No. Averages ~0.57% monthly.

**Sources**: [^38^] [^45^]

---

### Strategy 6: Sector Momentum Rotation (Top 3 Sectors)

**Type**: Cross-sectional momentum | ETF-based

**Trading Rules**:
1. Universe: 10 US sector ETFs
2. At each month-end, rank sectors by 12-month total return
3. Buy the top 3 sectors, equal-weighted
4. Hold for one month, then rebalance
5. Optional: Go to cash/T-bills if top sectors have negative absolute momentum

**Performance (1928-2009)**:
| Metric | Sector Momentum | Buy & Hold (US Equity) |
|--------|----------------|----------------------|
| CAGR | **13.94%** | ~10% |
| Annual Volatility | 18.38% | ~18% |
| Max Drawdown | **-46.29%** | ~57% |
| Sharpe Ratio | 0.54 | ~0.35 |
| Outperformance | +3.94% annually | - |

**Key Insights**: A simple, robust strategy with nearly a century of out-of-sample data. The 12-month lookback is standard in academic literature. Drawdowns are still significant (~46%) but 10% less than buy-and-hold.

**Transaction Costs**: Low (monthly rebalancing of 3 ETFs)

**Achieves >3% monthly?** No. Averages ~1.16% monthly.

**Sources**: [^70^] [^13^]

---

### Strategy 7: ETF Rotation (SPY, EEM, TLT - Monthly Momentum)

**Type**: Cross-sectional momentum | ETF-based

**Trading Rules**:
1. Universe: SPY (S&P 500), EEM (Emerging Markets), TLT (Treasury Bonds)
2. At month-end, rank the 3 ETFs by past 1-month or 3-month performance
3. Invest 100% in the top-performing ETF
4. Repeat monthly

**Performance**:
| Lookback | CAGR | Max Drawdown |
|----------|------|-------------|
| 1-month (2003-2022) | 9.4% | -44% (2022) |
| 3-month (2003-2022) | **11.5%** | **-32%** |

**Key Insights**: The 3-month lookback significantly outperforms the 1-month version (11.5% vs 9.4% CAGR) with lower drawdowns. The strategy was severely hurt in 2022 (-44% using 1-month lookback) when all three assets declined simultaneously.

**Transaction Costs**: Minimal (1 trade per month)

**Achieves >3% monthly?** No. 3-month version averages ~0.96% monthly.

**Sources**: [^13^]

---

### Strategy 8: Meb Faber's Global Tactical Asset Allocation (GTAA 13)

**Type**: Trend-following asset allocation | ETF-based

**Trading Rules**:
1. Universe: 13 ETFs across global equities, bonds, commodities, REITs
2. At month-end, check if each asset is above its 10-month SMA
3. **Absolute momentum filter**: Hold only assets above their 10-month SMA
4. **Relative momentum**: If multiple assets are above SMA, hold those with highest relative momentum
5. Move to cash (BIL) for assets below their 10-month SMA
6. Equal-weight among qualifying assets

**Performance (1970-2026)**:
| Metric | GTAA 13 | Buy & Hold 60/40 |
|--------|---------|-----------------|
| CAGR | **9.4%** | ~9.0% |
| Max Drawdown | **-12.5%** | -29.7% |
| Sharpe Ratio | **0.70** | 0.51 |
| Profitable Months | 68.9% | 63.2% |
| Worst Year | -8.3% | -18.3% |

**Key Insights**: The primary value is **drawdown reduction** (max -12.5% vs -29.7%), not return enhancement. The strategy roughly halved drawdowns while matching returns. Safe withdrawal rate of 8%+ over 25+ years. The trade-off: holding cash during bullish periods causes underperformance in strong bull markets.

**Transaction Costs**: Low (monthly review, not always trades)

**Achieves >3% monthly?** No. Averages ~0.78% monthly.

**Sources**: [^55^] [^77^] [^57^]

---

### Strategy 9: Jim O'Shaughnessy's Multi-Factor Momentum

**Type**: Multi-factor stock selection | Stock-based

**Trading Rules**:
1. Universe: All US stocks with sufficient liquidity
2. **Value filter**: Rank on P/E, P/B, EV/EBITDA, shareholder yield
3. **Size filter**: Favor small/mid caps (exclude micro-caps)
4. **Momentum filter**: Rank on total return over 6-12 months, **skip the most recent month** to avoid short-term reversal
5. **Quality filter**: ROE/ROC, gross profitability, stable margins, low leverage
6. Buy top 25-75 names on composite score
7. Rebalance quarterly or semi-annually

**Performance**:
- Pure momentum (50-stock, value-weight, monthly rebalanced, 1970-2016): **17.36% CAGR gross** [^83^]
- Multi-factor composite (Trending Value): Historically beats S&P 500 across most market cycles
- O'Shaughnessy's models show consistent outperformance compared to broader market

**Key Insights**: The 6-12 month momentum window (skipping month 1) is the classic academic approach. Monthly rebalancing of 50 stocks yields 17.36% gross but would incur significant transaction costs. Annual rebalancing of 500 stocks yields 10.89% gross [^83^].

**Transaction Costs**: Significant for concentrated monthly strategies; lower for quarterly/semi-annual

**Achieves >3% monthly?** No. Pure momentum averages ~1.45% monthly gross.

**Sources**: [^37^] [^46^] [^83^]

---

### Strategy 10: CANSLIM (O'Neil's Growth/Momentum Strategy)

**Type**: Fundamental + Technical momentum | Stock-based

**Trading Rules** (Simplified version):
1. **C**urrent quarterly EPS growth > 25% YoY
2. **A**nnual EPS growth > 20% over 5 years
3. **N**ew products, management, or price highs
4. **S**hares outstanding: favor smaller companies (under 20-25M shares)
5. **L**eader: Relative Strength >= 80
6. **I**nstitutional sponsorship: increasing ownership
7. **M**arket direction: trade in sync with major trend (index above 200-day MA)
8. Additional: Stock within 10% of 52-week high

**Performance**:
| Study | Period | CAGR | Notes |
|-------|--------|------|-------|
| Schadler & Cotton (AAII screener) | 1998-2005 | **30.86%** | S&P 600 benchmark: 9.49% [^65^] |
| OPBM II (modified CANSLIM) | 1999-2013 | 14.21% | Max DD: -71.88% [^65^] |
| MarketInOut backtest | 2026 (YTD) | 13.3% | Single year only [^62^] |
| Stock Rover screener | 5-Year | ~35.2% (176% total) | Outperformed S&P's 68.3% [^69^] |

**Key Insights**: The 30.86% figure from AAII is the most promising for the >3% monthly target, but it covers a short period (1998-2005) that included the dot-com bubble - favorable for growth stocks. The max drawdown of -71.88% in another study shows extreme risk.

**Transaction Costs**: Moderate (annual rebalancing in simplified versions)

**Achieves >3% monthly?** Potentially (30.86% = ~2.6% monthly in the AAII study), but not consistently across all studies and time periods.

**Sources**: [^65^] [^62^] [^69^]

---

### Strategy 11: Mark Minervini's Trend Template (SEPA)

**Type**: Stock-specific technical momentum | Stock-based

**Trading Rules** (8-point Trend Template):
1. Price > 50-day MA
2. Price > 150-day MA
3. Price > 200-day MA
4. 50-day MA > 150-day MA
5. 150-day MA > 200-day MA
6. 200-day MA trending up for at least 1 month
7. Price within 25% of 52-week high
8. Relative Strength rating >= 70 (ideally 90+)
9. **Plus fundamental**: Quarterly EPS growth > 20%, Revenue growth > 15%, expanding margins

**Entry**: Look for Volatility Contraction Pattern (VCP) after stock passes Trend Template
**Exit**: Violation of trailing stop (10-day MA on heavy volume, or 50-day MA break)

**Performance**: No verified long-term backtest data available. Minervini claims exceptional personal performance but no systematic backtest results have been published.

**Transaction Costs**: Moderate (daily/weekly monitoring, position turnover as stocks fall off screen)

**Achieves >3% monthly?** Unknown - no verified data.

**Sources**: [^106^] [^102^] [^108^]

---

### Strategy 12: ADX + Moving Average Trend System

**Type**: Trend strength | Stock/Index-based

**Trading Rules**:
1. ADX(14) must be above 25 (strong trend)
2. Entry: ADX line crosses above 25 (no DI crossover needed)
3. Optional 200 EMA filter improves drawdown but reduces trades
4. Stop Loss: 1.5x ATR
5. Take Profit: 3.5:1 reward-to-risk ratio (5.25x ATR)

**Performance**: No specific CAGR data in the backtest [^53^]. The author reports "good return, low drawdown, poor win rate but high R:R makes up for it." No verified numbers available.

**Transaction Costs**: Not included in the reported backtest

**Achieves >3% monthly?** Unknown - no verified data.

**Sources**: [^53^]

---

### Strategy 13: On-Balance Volume (OBV) + RSI Strategy

**Type**: Volume-confirmed momentum | Stock/Index-based

**Trading Rules**:
1. Calculate N-day RSI of the OBV indicator (not of price)
2. Buy when RSI of OBV drops below threshold (e.g., 30) and then recovers
3. Sell when close > yesterday's high
4. Parameters: 5-day RSI, buy threshold 30

**Performance (SPY backtest)**:
| Metric | Value |
|--------|-------|
| # Trades | 369 |
| Avg Gain/Trade | 0.6% |
| Win Rate | 75% |
| Max Drawdown | 24% |
| Profit Factor | 2.01 |
| CAGR | ~6-7% |

**Key Insights**: OBV-based strategies show reasonable win rates (75%) but small average gains. Better used as a confirmation tool for other momentum strategies rather than a standalone system.

**Transaction Costs**: Moderate (369 trades over multi-year period)

**Achieves >3% monthly?** No. Averages ~0.5-0.6% monthly.

**Sources**: [^54^] [^52^]

---

### Strategy 14: Alpha Architect QMOM (US Quantitative Momentum ETF)

**Type**: Concentrated momentum factor | ETF (managed fund)

**Trading Rules** (Systematic implementation):
1. Universe: All US stocks with sufficient liquidity
2. Rank stocks by 12-month momentum (excluding most recent month)
3. Apply "momentum quality" filter: prefer stocks with smoother, steadier price appreciation
4. Select ~40-50 highest pure momentum stocks
5. Equal-weight portfolio
6. Rebalance quarterly

**Performance**:
| Period | Return |
|--------|--------|
| Since Inception (Dec 2015) | ~236.86% total |
| 1-Year (as of Jun 2026) | 26.07% |
| 3-Year | 21.26% |
| 5-Year | 67.15% |
| 2024 | 32.17% |
| YTD 2026 | 20.71% |

**Key Insights**: QMOM takes a more concentrated approach than MTUM (fewer holdings, stronger momentum signal). It has outperformed MTUM in recent years. The quarterly rebalancing is more frequent than some passive momentum ETFs.

**Transaction Costs**: Built-in 0.28-0.49% expense ratio

**Achieves >3% monthly?** No. Recent strong years (26% in 2024, 20% YTD 2026) average ~1.7-2.2% monthly, but 5-year CAGR of ~10.8% is only ~0.9% monthly.

**Sources**: [^59^] [^63^] [^67^]

---

### Strategy 15: Risk-Managed Momentum (Barroso & Santa-Clara)

**Type**: Volatility-targeted momentum | Stock-based (long-short)

**Trading Rules**:
1. Form standard momentum portfolio (12-month return, skip 1 month)
2. Forecast volatility using 6-month (126-day) realized variance
3. Scale portfolio exposure to maintain constant 12% target volatility
4. When forecasted volatility is high: reduce exposure (sell stocks)
5. When forecasted volatility is low: increase exposure (buy stocks)

**Performance (1972-2020)**:
| Metric | Traditional Momentum | Risk-Managed (12% vol) |
|--------|---------------------|----------------------|
| Avg Annual Return | Higher raw | Lower raw |
| Sharpe Ratio | ~0.35 | **~0.70** (nearly doubled) |
| Max Single-Month Loss | -34.7% | **-14.9%** |
| Max Drawdown | -70.4% | **-27.7%** |

**Key Insights**: Risk-managed momentum virtually eliminates crash risk and nearly doubles the Sharpe ratio. However, the trade-off is lower raw returns during normal markets. The strategy requires periodic capital inflows/outflows when scaling, which is implementable for institutional investors but challenging for retail.

**Transaction Costs**: Estimated at 40% higher than traditional momentum (still manageable given the improved risk profile)

**Achieves >3% monthly?** No. Raw returns are lower due to volatility scaling. Target is 12% annualized volatility, not 36%+ returns.

**Sources**: [^85^] [^86^]

---

### Strategy 16: Taiwan Momentum Factor Strategy

**Type**: Cross-sectional momentum | Stock-based (Taiwan market)

**Trading Rules** (from TEJ landscape scan):
1. Universe: Taiwan-listed stocks
2. Rank stocks by momentum factor (likely 12-month return)
3. Buy highest-momentum stocks
4. Daily rebalancing

**Performance**:
| Metric | Value |
|--------|-------|
| Annualized Return | **31.1%** |
| Monthly Return | ~2.6% |
| Beta | 0.79 |
| Volatility | 26.1% |
| Sortino Ratio | 1.17 |

**Key Insights**: Momentum effects are stronger in less efficient markets like Taiwan (higher retail participation ~40% vs ~20-25% in US). The 31.1% annualized return is one of the highest verified for a systematic momentum strategy. However, this was during a specific 57-month period (2019-2024) and may not persist.

**Achieves >3% monthly?** Close - ~2.6% monthly. This is one of the closest to the target.

**Sources**: [^1^]

---

### Strategy 17: BacktestIndia Quality Momentum

**Type**: Momentum + quality filter | Stock-based (India NSE)

**Trading Rules**:
1. Universe: Top 200 NSE stocks by market cap
2. Select top 60 by 12-month price momentum
3. Filter to top 30 with lowest "Scaled Turnover" (anti-speculation filter)
4. Equal-weight, semi-annual rebalancing

**Performance (Dec 2006 - Jun 2025, 18.5 years)**:
| Metric | Quality Momentum | Pure Momentum | Nifty 50 |
|--------|-----------------|--------------|----------|
| Net CAGR | **17.95%** | 14.01% | 10.42% |
| Max Drawdown | -61.70% | -70.53% | -55.12% |
| Sharpe Ratio | **0.86** | ~0.58 | ~0.57 |
| Terminal Wealth (Rs 50L) | **Rs 10.56 Cr** | Rs 5.64 Cr | Rs 3.33 Cr |

**Key Insights**: The anti-speculation filter (low scaled turnover) simultaneously improved returns AND reduced risk. Recovery from 2008 GFC was 41 months vs 65 months for pure momentum. The quality filter works by removing speculative stocks that create the worst crash outcomes.

**Transaction Costs**: 0.11% per trade + 0.05% slippage + full tax treatment

**Achieves >3% monthly?** No. Averages ~1.5% monthly.

**Sources**: [^93^]

---

### Strategy 18: Concentrated Weekly Momentum (Tech Stock Universe)

**Type**: High-frequency momentum | Stock-based

**Trading Rules** (from SimFin backtest):
1. Universe: Liquid stocks with strong volume and price trends
2. Filter: Specific price range, favorable volume patterns
3. Rebalance weekly (vs monthly)
4. Momentum criteria: Price + volume confirmation

**Performance (Oct 2007 - present)**:
| Rebalancing | CAGR | vs SPY |
|-------------|------|--------|
| Monthly | ~18% | +11% vs SPY |
| Weekly | **30%** | +23% vs SPY |

**Reddit momentum strategy (similar concept, 2017-2026)**:
| Metric | Value |
|--------|-------|
| CAGR | **52.53%** |
| Max Drawdown | -42.44% |
| Sharpe Ratio | 1.51 |
| Win Rate | 72.87% |
| Universe | 30 tech stocks (NVDA, TSLA, AMD, etc.) |

**Key Insights**: The 30% CAGR from weekly rebalancing and 52.53% from the tech-stock strategy are the highest reported. However, these are **almost certainly overfitted** to the 2017-2026 period - the strongest tech bull market in history. The 52.53% strategy uses a hand-picked universe of 30 stocks that happen to be the biggest winners of the decade.

**Transaction Costs**: High for weekly rebalancing. The Reddit strategy had $63,248 in costs on $100K initial capital.

**Achieves >3% monthly?** Yes (the Reddit strategy averages ~4.4% monthly), but with extreme survivorship bias and selection bias. NOT recommended as a systematic approach.

**Sources**: [^92^] [^95^]

---

## Summary: Which Strategies Come Closest to >3% Monthly?

| Strategy | Verified CAGR | Monthly Avg | Drawdown | Confidence |
|----------|--------------|-------------|----------|------------|
| Taiwan Momentum Factor | 31.1% | ~2.6% | High | Medium |
| CANSLIM (AAII study) | 30.86% | ~2.6% | -71.88% | Low (short period) |
| Weekend Trend Trader (Midcap) | 22.9% | ~1.9% | -58% | High |
| Wilcox/Crittenden Trend Following | 15.19% | ~1.26% | -33.74% | High |
| Dual Momentum (Antonacci) | 17.43% | ~1.45% | -22.7% | High |
| Alpha Architect 50-stock Momentum | 17.36% | ~1.45% | Unknown | Medium |
| Quality Momentum (India) | 17.95% | ~1.5% | -61.70% | Medium |
| Concentrated Weekly (Tech bias) | 30-52% | ~2.5-4.4% | -42% | Very Low |

**Honest Assessment**: No well-documented, long-only momentum strategy consistently achieves >3% monthly (36%+ CAGR) over multi-decade periods with verified backtests. The highest **verified** long-only results are in the 22-31% range, and those come with severe drawdowns (55-71%).

To achieve 36%+ annualized returns long-only, a trader would likely need to:
1. Focus on less efficient markets (emerging markets, small caps)
2. Use concentrated portfolios (10-20 positions max)
3. Rebalance frequently (weekly to capture momentum faster)
4. Combine momentum with quality filters (earnings growth, low speculation)
5. Accept very high drawdowns (50%+)
6. Consider that past results may not be replicable

---

## Sources Index

[^1^]: TEJwin - "Trend-Following Strategy: A Trading Method Used by Fund Managers" - Taiwan momentum factor 31.1% annualized
[^18^]: Quant-Investing.com - "How much can dual momentum increase your investment returns" - Antonacci 39-year backtest
[^19^]: QuantifiedStrategies.com - "Dual Momentum Trading Strategy (Gary Antonacci)" - ETF implementation backtest
[^20^]: QuantifiedStrategies.com - "200 Day Moving Average Trading Strategy" - S&P 500 backtest 1960-present
[^23^]: Quantpedia.com - "Trend-following Effect in Stocks" - Wilcox & Crittenden strategy details
[^25^]: SSRN - "Does Trend Following Still Work on Stocks?" (Zarattini, Pagani, Wilcox, 2025) - 66,000 trades, 1950-2024
[^26^]: Grzegorz.link - "Dual Momentum & Global Growth Cycle Enhanced" - Enhanced DM CAGR 16.4%
[^27^]: RobotWealth.com - "Dual Momentum Investing: A Quant's Review" - Sector rotation implementation
[^37^]: PicturePerfectPortfolios.com - "How To Invest Like Jim O'Shaughnessy"
[^38^]: QuantifiedStrategies.com - "Golden Cross Trading Strategy" - S&P 500 backtest since 1960
[^45^]: StockCharts.com - "Quantifying the Golden Cross for the S&P 500" - Arthur Hill analysis
[^46^]: Portfolio123.com blog - "Did What Works on Wall Street Stop Working?"
[^52^]: ForexTester.com - "On-Balance Volume (OBV): The Ultimate Guide"
[^53^]: Reddit r/algotrading - "Backtest results for an ADX trading strategy"
[^54^]: QuantifiedStrategies.com - "On-Balance Volume (OBV): Trading Strategy"
[^55^]: PortfolioDB.com - "Global Tactical Asset Allocation 13 (GTAA 13) by Meb Faber"
[^59^]: Yahoo Finance - QMOM performance data
[^62^]: MarketInOut.com - "CANSLIM System" backtest
[^63^]: SumGrowth.com - QMOM ETF profile and performance
[^65^]: NA Business Press - "OPBM II: An Interpretation of the CAN SLIM Investment Strategy" (Lutey, 2014)
[^67^]: AlphaArchitect.com - "QMOM Investment Case"
[^68^]: Bauer.uh.edu - Jegadeesh & Titman (1993) original momentum paper
[^69^]: GreatWorkLife.com - "Rethinking CAN SLIM: Strategies for Better Returns"
[^70^]: Quantpedia.com - "Sector Momentum - Rotational System" (1928-2009)
[^77^]: Freenance.io - "The Ivy Portfolio Strategy"
[^78^]: QuantifiedStrategies.com - "The Weekend Trend Trader Strategy - 22% Annual Return"
[^80^]: QuantifiedStrategies.com - "A Trend Following Strategy for Stocks" (Wilcox/Crittenden review)
[^83^]: AlphaArchitect.com - "How Portfolio Construction Affects Momentum Funds"
[^85^]: EUR.nl thesis - "The performance of (risk-managed) momentum strategies" (Rickenberg)
[^86^]: AlphaArchitect.com - "Avoiding Momentum Crashes"
[^87^]: Robeco.com - "Quant chart: taming momentum crashes"
[^92^]: SimFin.com - "Momentum Trading Strategy: Investing in Stocks with Volume and Price Criteria"
[^93^]: BacktestIndia.com - "Momentum Investing India: Complete Guide"
[^94^]: GitHub - "weekend-backtrader: Implementation of the weekend trader strategy"
[^95^]: Reddit r/algotrading - "Rate this momentum strategy (CAGR: 52.53%)"
[^96^]: UseThinkScript.com - "Weekend Trend Trader by Nick Radge Strategy for ThinkorSwim"
[^98^]: DRPress.org - "Research on the momentum effect in the US stock market"
[^100^]: QuantifiedStrategies.com - "Momentum Trading Strategy (Backtested)"
[^101^]: Yahoo Finance - MTUM performance data
[^102^]: TradingView - "Mark Minervini Trend Template Criteria"
[^106^]: FinerMarketPoints.com - "Mark Minervini Stock Screener: Trend Template Criteria & VCP Scanner Guide"
[^108^]: TrendSpider.com - "Minervini Trend Template"
