# Finviz Help Center — Comprehensive Feature Reference

> Compiled from https://finviz.com/help/screener, https://finviz.com/help/technical-analysis/, https://finviz.com/help/faq/, https://finviz.com/elite, https://finviz.com/blog/
> Date collected: 2026-07-12

---

## Table of Contents

1. [Screener — Filters & Signals](#1-screener--filters--signals)
2. [Financial Fundamentals Filters](#2-financial-fundamentals-filters)
3. [Ownership & Trading Data Filters](#3-ownership--trading-data-filters)
4. [Performance & Technical Filters](#4-performance--technical-filters)
5. [Screener Signals](#5-screener-signals)
6. [Chart Patterns](#6-chart-patterns)
7. [Technical Analysis — Introduction](#7-technical-analysis--introduction)
8. [Moving Averages (SMA, EMA)](#8-moving-averages-sma-ema)
9. [Oscillators (MACD, RSI, Stochastics, ADX, CCI, etc.)](#9-oscillators-macd-rsi-stochastics-adx-cci-etc)
10. [Volatility-Based Indicators (Parabolic SAR, ROC, Bollinger Bands)](#10-volatility-based-indicators-parabolic-sar-roc-bollinger-bands)
11. [Volume-Based Indicators (MFI, Force Index)](#11-volume-based-indicators-mfi-force-index)
12. [Charts & Chart Patterns](#12-charts--chart-patterns)
13. [Intraday Timeframes & Advanced Indicators](#13-intraday-timeframes--advanced-indicators)
14. [Finviz Elite Features](#14-finviz-elite-features)
15. [Portfolio & Alerts](#15-portfolio--alerts)
16. [Maps & Groups](#16-maps--groups)
17. [Data & API / Export](#17-data--api--export)
18. [FAQ — Data, Markets, Subscription](#18-faq--data-markets-subscription)

---

## 1. Screener — Filters & Signals

### What Is a Stock Screener?

Stock Screener searches through large amounts of stock data and returns a list of stocks that match one or more selected criteria — called **filters**.

**Core Features:**
- Full integration of fundamental and technical analysis
- Rich-information output, multiple views
- Fast navigation, instant updates as you adjust filters

### Using Filters
Access the screener filters via the **"Filters"** button on the top-right — this expands the list. Filters are organized into tabs:

| Tab | Contents |
|-----|----------|
| **Descriptive** | Exchange, Sector, Industry, Country, Market Cap, Index |
| **Fundamental** | P/E, EPS, ROE, Margins, Dividend Yield, Debt ratios, etc. |
| **Technical** | SMA, RSI, Gap, Performance, Volatility, Volume, Pattern, etc. |

Save filter combinations as **Screener Presets** — you can later quickly access saved 'screens' via the menu.

### Order By
Use the **"Order by"** dropdown at the top of the screener to sort results by various metrics. You can also **click on any column header** in the results table to sort by that column.

### Screener Views
Available views: **Overview, Valuation, Performance, Financial, Ownership, Technical, and Charts**. Custom views are available for ELITE users.

### Historical Screener Data
Finviz does **not** offer historical screener data. Historical data is only available within Charts.

### Descriptive Filters (Overview)
The Screener's power comes from its extensive filter system. Filters are organized into categories:

- **Exchange** — NASDAQ, NYSE, AMEX
- **Index** — S&P 500, DJIA, etc.
- **Sector** — Companies grouped by business activity
- **Industry** — Sub-sector by products/services
- **Country** — Geographic location (US-listed). Includes continents and groups (e.g., BRIC)
- **Market Cap** — Mega ($200B+) / Large ($10B-$200B) / Mid ($2B-$10B) / Small ($300M-$2B) / Micro ($50M-$300M) / Nano (under $50M)

### Exchange Filter
The stock exchange on which a company is listed. Covers NASDAQ, NYSE, AMEX.
- **Sorting:** No | **Export:** No | **Appearance:** Stock Detail

### Index Filter
A stock's membership in a major stock exchange index (e.g., Dow Jones Industrial, S&P 500).
- **Sorting:** No | **Export:** No | **Appearance:** Stock Detail

### Sector
Companies grouped by business activity.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Overview, Snapshot, Stock Detail

### Industry
Companies in a common sector further divided by products/services.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Overview, Snapshot, Stock Detail

### Country
Geographic location of a company listed on US markets. Includes continents, countries, or groups (e.g., BRIC).
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Overview, Snapshot, Stock Detail

### Market Cap
The total dollar value of all of a company's outstanding shares. Market capitalization is a measure of corporate size.

> Market Capital = Current Market Price × Number Of Shares Outstanding
> Shares Outstanding = Total Number Of Shares − Shares Held In Treasury
> Float = Shares Outstanding − Insider Shares − Above 5% Owners − Rule 144 Shares

**Available ranges:** Mega ($200B+) / Large ($10B-$200B) / Mid ($2B-$10B) / Small ($300M-$2B) / Micro ($50M-$300M) / Nano (under $50M)

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Overview, Snapshot, Stock Detail

---

## 2. Financial Fundamentals Filters

### P/E (Price/Earnings)
Popular valuation ratio comparing current share price to per-share earnings (TTM). Low P/E indicates relatively cheap stock.

> P/E = Current Market Price / EPS
> EPS = (Net Income − Dividends On Preferred Stock) / Average Outstanding Shares

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### Forward P/E
Price-to-earnings using forecasted earnings for next fiscal year.

> Forward P/E = Current Market Price / Forecasted EPS

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### PEG
Measures valuation (Forward P/E) against projected 3-5 year growth rate.

> PEG = (Forward P/E) / Annual EPS Growth

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### P/S (Price/Sales)
Value placed on sales by the market. Often used to value unprofitable companies.

> P/S = Current Market Price / Total Revenues Per Share

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### P/B (Price/Book)
Compares market value to book value. Low P/B may indicate undervaluation.

> P/B = Current Market Price / (Total Assets − Total Liabilities)
> P/B = Current Market Price / (Total Common Equity / Total Common Shares Outstanding)

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### Price/Cash
Compares market value to cash assets.

> P/C = Current Market Price / Cash per Share

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### Price/Free Cash Flow
Compares market price to annual free cash flow.

> P/FCF = Current Market Price / Cash Flow per Share

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS (ttm)
Portion of profit allocated to each outstanding share. Key valuation variable.

> EPS = Total Earnings / Total Common Shares Outstanding (TTM)

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS Growth This Fiscal Year (GAAP)
EPS estimate for the current fiscal year.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS Growth Next Fiscal Year (GAAP)
EPS estimate for the next fiscal year.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS Growth Past 5 Years
EPS annual growth over the past 5 fiscal years.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS Growth Next 5 Years
EPS annual long-term estimate.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### EPS Growth Qtr Over Qtr
EPS growth last quarter on a YoY basis.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### Sales Growth Qtr Over Qtr
Total revenues increase last quarter on a YoY basis.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Snapshot, Stock Detail

### Sales Growth Past 5 Years
Annual sales increase over past 5 years.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Stock Detail

### Dividend Yield (Fiscal Year Estimate)
Percentage return paid to shareholders in dividends. Uses forward estimate; TTM if unavailable.

> Dividend Yield = Annual Dividend Per Share / Price Per Share

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Fundamental, Snapshot, Stock Detail

### Return on Assets (ROA)
Profitability relative to total assets. Shows management efficiency.

> ROA = Annual Earnings / Total Assets

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Return on Equity (ROE)
Profit generated with shareholders' invested money.

> ROE = Annual Net Income / Shareholder's Equity

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Return on Invested Capital (ROIC)
Measures capital allocation efficiency.

> ROIC = Net Income / Invested Capital

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Current Ratio
Short-term liquidity measure.

> Current Ratio = Current Assets / Current Liabilities

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Quick Ratio
Short-term liquidity using most liquid assets.

> Quick Ratio = (Current Assets − Inventories) / Current Liabilities

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Long Term Debt/Equity
Financial leverage from long-term debt.

> LT Debt/Equity = Long Term Debt / Shareholder's Equity

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Debt/Equity
Financial leverage from total current liabilities.

> Debt/Equity = Current Liabilities / Shareholder's Equity

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Gross Margin
Revenue retained after direct costs of production.

> Gross Margin = (Total Sales − Costs) / Total Sales

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Operating Margin
Revenue remaining after variable production costs.

> Operating Margin = Operating Income / Net Sales

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Net Profit Margin
Net income per dollar of sales.

> Net Profit Margin = Net Income / Revenues

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

### Payout Ratio
Percentage of earnings paid as dividends.

> Payout Ratio = Dividends / Earnings

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Stock Detail

---

## 3. Ownership & Trading Data Filters

### Insider Ownership
% of shares owned by company management.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Ownership, Snapshot, Stock Detail

### Insider Transactions
% change in total insider ownership (purchases/sales by management).
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Ownership, Snapshot, Stock Detail

### Institutional Ownership
% of shares owned by institutional investors.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Ownership, Snapshot, Stock Detail

### Institutional Transactions
% change in total institutional ownership.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Ownership, Snapshot, Stock Detail

### Short Float
The number of shares short divided by total amount of shares float, expressed in %. Updated based on FINRA reports.

> Short Float = Number of Shares Short / Total Shares Float

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Ownership, Snapshot, Stock Detail

### Analyst Recommendation
Outlook from stock analysts.

> Rating Scale: 1.0 Strong Buy, 2.0 Buy, 3.0 Hold, 4.0 Sell, 5.0 Strong Sell

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Snapshot, Stock Detail

### Option/Short
Stocks with options and/or available to sell short.
- **Sorting:** No | **Export:** No | **Appearance:** Snapshot, Stock Detail

### Earnings Date
The company's nearest earnings-report date.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Financial, Snapshot, Stock Detail

---

## 4. Performance & Technical Filters

### Performance
% rate of return for a stock over a given time frame.

| Period | Trading Days |
|--------|-------------|
| 1 Week | 5 |
| 1 Month | 21 |
| 3 Months | 63 |
| 6 Months | 126 |
| 1 Year | 252 |
| 3 Years | 756 |
| 5 Years | 1260 |
| 10 Years | 2520 |

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### Volatility
Statistical measure of return dispersion. Average daily high/low % range.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### RSI (14)
Relative Strength Index — price strength by comparing upward/downward close-to-close movements. Indicates oversold (buy) and overbought (sell) levels.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Gap
Difference between yesterday's close and today's open. Indicates supply/demand imbalance after major news.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Simple Moving Average (20, 50, 200-Day)
Average of last N-periods.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Change
% difference between current close and previous close price.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Change from Open
% difference between current close and today's open.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### High/Low (20-Day, 50-Day, 52-Week)
Minimum of lows / Maximum of highs. Filter options represent % distance from record high/low.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Pattern
Chart pattern — distinct formation creating a trading signal. (See Section 12 for full pattern list)
- **Sorting:** No | **Export:** No | **Appearance:** Stock Detail

### Candle Stick
OHLC candlestick pattern for given time periods. Detection is algorithmic and identifies the following patterns from real-time price data on daily charts:

| Pattern | Description |
|---------|-------------|
| **White** | Simple bullish candle (close > open, no other pattern detected) |
| **Black** | Simple bearish candle (close < open, no other pattern detected) |
| **Doji** | Open and close are virtually equal — market indecision |
| **Hammer** | Small body at top, long lower shadow — bullish reversal after downtrend |
| **Inverted Hammer** | Small body at bottom, long upper shadow — bullish reversal signal |
| **Spinning Top White** | Small bullish body with upper/lower wicks — indecision but closed higher |
| **Spinning Top Black** | Small bearish body with upper/lower wicks — indecision but closed lower |
| **Marubozu White** | Long bullish body with no (or very short) wicks — strong buying throughout session |
| **Marubozu Black** | Long bearish body with no (or very short) wicks — strong selling throughout session |
| **Long Upper Shadow** | Candle with a significantly long upper wick — rejection of higher prices |

The finviz screener shows the **Candlestick** column in Technical Analysis (TA) view (`v=352`). It's a display-only column — you can sort by it but it's NOT a direct filter in the traditional sense; instead use the **Pattern** filter or watch the **Candlestick** field in results.

- **Sorting:** Yes | **Export:** No | **Appearance:** Technical, Stock Detail

### Beta (5 Years)
Price volatility relative to the market (60-month regression). β=0: no correlation; β>0: follows market; β<0: inversely follows market.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### ATR (Average True Range)
Exponential moving average (14-day) of True Ranges. Measures volatility.

> True Range = max(high, closeprev) − min(low, closeprev)

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Technical, Stock Detail

### Average Volume (3 Month)
Average shares traded per day over recent 3 months.
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### Relative Volume
Ratio between current volume and 3-month average value, intraday adjusted.

> Relative Volume = Current Volume / (3-month Average Volume × Time Coefficient)
> Time Coefficient = 0.05 + (Minutes Since Market Open / Total Market Session Minutes × 0.95)

- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### Current Volume
Total shares traded today (or last session).
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### Price
Current stock price (or close of last session).
- **Sorting:** Yes | **Export:** Yes | **Appearance:** Performance, Snapshot, Stock Detail

### Other Data Fields (non-filter, shown in views)

| Field | Definition |
|-------|-----------|
| **Shares Outstanding** | Total common shares owned by public = Total Shares − Treasury Shares |
| **Shares Float** | Shares available for trading = Outstanding − Insider − 5% Owners − Rule 144 |
| **Target Price** | Analyst price target |
| **IPO Date** | Initial public offering date |
| **Book Value per Share** | (Total Assets − Total Liabilities) / Shares Outstanding |
| **Cash per Share** | Latest quarter's cash per share |
| **Employees** | Company employee count |
| **EV/EBITDA** | Enterprise Value / EBITDA |
| **EV/Sales** | Enterprise Value / Sales |
| **Income** | Net income |
| **Sales** | Total revenues |

---

## 5. Screener Signals

Stocks can be screened by **signals** — special events on which traders usually enter or exit positions.

| Signal | Description | Limit |
|--------|-------------|-------|
| **Top Gainers** | Highest % price gain today | Top 200 |
| **Top Losers** | Highest % price loss today | Top 200 |
| **New High** | Stocks making 52-week high today | Top 200 |
| **New Low** | Stocks making 52-week low today | Top 200 |
| **Most Volatile** | Widest high/low trading range today | Top 200 |
| **Most Active** | Highest trading volume today | Top 200 |
| **Unusual Volume** | Highest relative volume ratio today | Top 200 |
| **Overbought** | Extreme price increase (RSI 14) — may pull back | Top 200 |
| **Oversold** | Extreme price decrease (RSI 14) — potential buying opp | Top 100 |
| **Downgrades** | Stocks downgraded by analysts today | All |
| **Upgrades** | Stocks upgraded by analysts today | All |
| **Earnings Before** | Reporting earnings today, before market open | All |
| **Earnings After** | Reporting earnings today, after market close | All |
| **Major News** | Highest news coverage today | Top 40 |
| **Chart Patterns** | Price near strong chart patterns | Top 100 (by strength) |
| **Recent Insider Buying** | Significant insider purchases | Signal |
| **Recent Insider Selling** | Significant insider selling | Signal |

---

## 6. Chart Patterns

The screener can filter by chart patterns. These are algorithmic pattern detections:

### Trendline-Based Patterns

| Pattern | Type | Description |
|---------|------|-------------|
| **Horizontal S/R** | Support/Resistance | Horizontal support or resistance levels |
| **TL Resistance** | Trendline | Trendline resistance (local highs forming a line) |
| **TL Support** | Trendline | Trendline support (local lows forming a line) |

### Wedge Patterns
Composed of converging trendline support and resistance.

| Pattern | Type |
|---------|------|
| **Wedge Up** | Reversal — upward support and upward resistance |
| **Wedge Down** | Reversal — downward support and downward resistance |
| **Wedge** | Continuation — upward support, downward resistance |

### Triangle Patterns (Continuation)
Converging trendlines where one is horizontal.

| Pattern | Description |
|---------|-------------|
| **Triangle Ascending** | Upward support + horizontal resistance |
| **Triangle Descending** | Horizontal support + downward resistance |

### Channel Patterns (Continuation)
Parallel trendline support and resistance.

| Pattern | Slope |
|---------|-------|
| **Channel Up** | Both trendlines slope upward |
| **Channel** | Both horizontal |
| **Channel Down** | Both slope downward |

### Reversal Patterns

| Pattern | Description |
|---------|-------------|
| **Double Top** | Prior uptrend + 2 equal highs + horizontal support break |
| **Double Bottom** | Prior downtrend + 2 equal lows + horizontal resistance break |
| **Multiple Top** | 3+ equal highs with support break |
| **Multiple Bottom** | 3+ equal lows with resistance break |
| **Head & Shoulders** | 3 distinct highs (left shoulder < head > right shoulder) + support break |
| **Head & Shoulders Inverse** | Opposite — 3 distinct lows + resistance break |

### Common Trading Rules for Reversal Patterns:
- Entry: above break of horizontal resistance (long) / below break of support (short), preferably on volume
- Price target distance = pattern height (resistance − support)
- The broken level may turn into support/resistance post-breakout

---

## 7. Technical Analysis — Introduction

### Key Premises

1. **Prices move in trends** — Upward (bullish), Downward (bearish), Sideways. Trend is in effect until it reverses. Multiple trends exist simultaneously across timeframes.

2. **Price discounts everything** — All relevant information is already reflected in price. Only price and volume data are needed.

3. **History repeats itself** — Based on patterns in human psychology that do not change. Support/resistance dynamics illustrate this: broken resistance becomes support because all trader groups intend to buy near that level.

### Branches of Technical Analysis
- **Chart Analysis (Charting):** Finding patterns in price charts (head & shoulders, double bottoms, etc.)
- **Statistical Approach:** Computing and using technical indicators (moving averages, oscillators, etc.)

### Strengths & Weaknesses
- Highly subjective — two analysts may reach different conclusions
- Often combined with fundamental analysis for entry/exit timing
- Automated trading systems (>50% of orders) amplify trends

---

## 8. Moving Averages (SMA, EMA)

### Simple Moving Average (SMA)
Arithmetic mean of closing prices over a period.

> SMA = sum(closing prices over N days) / N

**Characteristics:**
- Equal weight to all data points in the period
- Ignores data outside the selected period
- Lag increases with longer periods (fewer signals, but fewer false signals)

### Exponential Moving Average (EMA / EWMA)
Solves SMA problems: allocates more weight to recent data; reflects all historical data.

> EMA = Price(t) × multiplier + EMA(prev) × (1 − multiplier)
> multiplier = 2 / (N + 1)

**Trading Signals:**
- Price crossing above/below MA = buy/sell signal
- Multiple MA crossovers reduce false signals (whipsaws)
- Popular combinations: 4-9-18 (futures), 5-21-89 (Fibonacci), 20-50-200 (common)
- Works best in trending markets; poor in sideways/choppy markets

### Key Insight from Finviz Backtests
- SMA: worse than random trading in most cases
- EMA: slightly better than random for 1-day and 20-day holding periods
- **Recommendation:** Combine with trend-strength indicators like ADX

---

## 9. Oscillators (MACD, RSI, Stochastics, ADX, CCI, etc.)

### Common Properties
- Values oscillate in a defined range (typically 0-100)
- Used as **leading indicators** — detect trend changes before they manifest
- Best in sideways markets; unreliable in strong trending markets during breakouts

### Key Concepts
- **Overbought / Oversold levels** — indicate extreme price moves likely to correct
- **Midpoint crossover** — oscillator crossing its midpoint value
- **Divergence** — price and oscillator moving in opposite directions (bearish: price higher high, oscillator lower high; bullish: opposite)

---

### Moving Average Convergence/Divergence (MACD)

> MACD Line = 12-day EMA − 26-day EMA
> Signal Line = 9-day EMA of MACD Line

**Uses:**
- MACD line crossing Signal line = buy/sell signal
- Histogram = difference between the two lines (crosses zero = crossover point)
- Divergence detection with price
- Extremely steep rise/fall indicates overbought/oversold (not standardized)

**Backtest result:** Generally low success rate.

---

### Relative Strength Index (RSI)

> RSI = 100 − (100 / (1 + RS))
> RS = average daily price increase / average daily price decrease

**Standard settings:** 14-day period

**Characteristics:**
- Standardized: values range 0-100
- Overbought at >70 (or >80), Oversold at <30 (or <20)
- Divergence detection
- Midpoint (50) crossover signal

**Backtest result:** Best performing indicator in Finviz tests. Setting 14, 20/80 works best. Problems with short positions held >5 days.

---

### Commodity Channel Index (CCI)

> CCI = (Price − SMA) / (0.015 × Standard Deviation of Price)

**Originally for commodity futures; now used across all markets.**
- Normal range: −100 to +100
- Uses "typical price" (H+L+C)/3 in some markets

---

### Stochastics

> %K = 100 × [(Close − Lowest Low N) / (Highest High N − Lowest Low N)]
> %D = 3-day SMA of %K

**Versions:** Fast, Slow (smoothed), Full (3 lines). Range: 0-100.
- %K crossing above %D = buy; below = sell
- Divergence most reliable in overbought/oversold territory

---

### Average Directional Index (ADX)

> ADX measures trend strength (0-100 range)

**Components:** +DI line (upward trend), −DI line (downward trend)
- Rising ADX = trend gaining momentum
- ADX divergence with price = trend weakening
- +DI crossing −DI = potential trade signal in opposite direction
- Widely used to determine which indicators to use in current market environment

---

### Relative Momentum Index (RMI)
Adjusted RSI: compares current close with close from X days ago (instead of previous day). Reduces false signals.

### Ultimate Oscillator (Larry Williams)

> Buying Pressure = Close − min(Low, Prev Close)
> True Range = max(High, Prev Close) − min(Low, Prev Close)
> Computes 7, 14, and 28-day averages weighted 4:2:1

- Overbought: >70 | Oversold: <30

### Williams %R

> %R = [(Close − N-day Low) / (N-day High − N-day Low)] × 100
> Range: −100 to 0

- Overbought: −20 and higher | Oversold: −80 and lower

### Trix
Based on triple exponentially-smoothed moving average. Filters price noise. Positive and rising = increasing momentum.

### Random Walk Index (RWI)
Assesses whether a statistically significant trend exists vs. random movement.

> RWI max = [Day's High − (Day's Low × N)] / (ATR × N × √N)
> RWI min = [(Day's High × N) − Day's Low] / (ATR × N × √N)

- Short-term: 2-7 days; Long-term: 8-64 days
- RWI > 1 indicates significant trend

---

## 10. Volatility-Based Indicators (Parabolic SAR, ROC, Bollinger Bands)

### Parabolic SAR (Stop And Reverse)
Dots placed above/below price in parabolic shape. Identifies where trend ends/reverses.

> Tomorrow's SAR = Today's SAR + AF × (Extreme Point − Today's SAR)

- Acceleration Factor: starts at 0.02, increases by 0.02 on each new high/low, max 0.20
- Works 30% of the time (per Wilder's estimate); only in trending environments
- Combine with ADX for best results

### Rate of Change (ROC)

> ROC = [(Close − Close N days ago) / Close N days ago] × 100

- Crossing above 0 = buy; below 0 = sell
- Used for divergence detection and chart analysis (trendline breaks)

### Bollinger Bands
Three lines: middle = 20-day SMA; upper/lower = SMA ± 2 standard deviations.

> Price expected inside range ~95% of time

- Price above upper band = overbought; below lower band = oversold
- Used to set exit/target prices
- Band width varies with volatility — widening signals trend end; narrowing signals new trend start

---

## 11. Volume-Based Indicators (MFI, Force Index)

### Money Flow Index (MFI)

> Typical Price = (H + L + C) / 3
> Money Flow = Typical Price × Volume
> Money Ratio = Sum(Positive Money Flow) / Sum(Negative Money Flow)
> MFI = 100 − (100 / (1 + Money Ratio))

- Range: 0-100. Functions like RSI but incorporates volume.
- Divergence detection: price higher high but MFI lower = bearish divergence

### Force Index (Alexander Elder)

> Force Index = (Today's Close − Previous Close) × Today's Volume

- Smoothed with EMA. Plotted as histogram.
- Positive high values = strong buying pressure; negative low = selling pressure
- Most commonly used with moving averages

---

## 12. Charts & Chart Patterns

### Candlestick Charts
Compress open, high, low, close into space-efficient candlesticks.

### Available Screener Pattern Filters
The screener can detect and filter stocks with these active patterns:
- Horizontal S/R
- Trendline Resistance / Support
- Wedge Up / Wedge Down / Wedge
- Triangle Ascending / Triangle Descending
- Channel Up / Channel / Channel Down
- Double Top / Double Bottom
- Multiple Top / Multiple Bottom
- Head & Shoulders / Head & Shoulders Inverse

---

## 13. Intraday Timeframes & Advanced Indicators

> Announced August 2025 — for Elite subscribers.

### Available Intraday Timeframes
- 1-minute
- 5-minute
- 15-minute
- Hourly (and more intraday periods)
- Daily, Weekly, Monthly

### Advanced Technical Indicators (with customizable parameters)
- Relative Strength Index (RSI) — adjustable period
- Moving Average Convergence/Divergence (MACD)
- Average True Range (ATR)
- Money Flow Index (MFI)
- Bollinger Bands (BB)
- Exponential Moving Average (EMA)
- And many more

### How to Use
1. Open Screener → Click **Technical**
2. Click **"+ Filter"** → Choose indicator
3. Set parameters (lookback, smoothing, thresholds)
4. Pick a **timeframe** (1-min to monthly)
5. Apply and see matching stocks

### Benefits
- React faster to market moves
- Filter noise
- Optimize entries and exits with precise technical rules

---

## 14. Finviz Elite Features

### Subscription Tiers

| Feature | Free | Elite |
|---------|------|-------|
| Quotes, Charts, Screener Data | Delayed | Real-time |
| Maps, Groups Data | Delayed | Real-time |
| Intraday Charts | — | Yes |
| Multi-layout Charts & Technical Studies | — | Yes |
| Fundamental Charts (EPS, Sales, Shares) | — | Yes |
| Email Alerts / Push Notifications | Limited | Price, Insider, Ratings, News, SEC |
| Ads | Yes | No |
| Export to Excel / APIs | — | Screener, Portfolio, Groups, Options, News |
| ETFs: Holdings, Performance, Structure | — | Full breakdown |
| Custom Screener Filters, ETF Filters, Stats View | — | Yes |
| Screener Presets | 50 | 200 |
| Items per Page (Table / Charts / Snapshots) | 20/36/10 | Up to 100/120/50 |
| Portfolios | 50 | 100 |
| Tickers per Portfolio | 50 | 500 |
| Statements | 3 Years | 8 Years |
| Correlated Stocks | — | Yes |
| Layout Customization | Limited | Full (Homepage, Portfolio, Signals) |
| Customize Media Sources | — | Yes |
| Early Access to New Features | — | Yes |

### Premium Data
- **Real-time quotes** for NYSE, NASDAQ, AMEX
- **Pre-market data:** 4:00 AM − 9:30 AM ET
- **After-market data:** 4:00 PM − 8:00 PM ET
- **Futures data:** 20-minute delayed (all tiers)
- Fundamentals recalculated hourly

### Pricing
- Monthly: $39.50/month
- Annual: $299.50/year (~$24.96/month)
- Free 7-day trial included

### Finviz Elite Key Capabilities
1. **Interactive Multi-Layout Charts** — Draw patterns, add indicators, switch layouts, auto-save technical studies
2. **Award-Winning Screener** — 20+ advanced customizable filters, personalized views, benchmark insights, automatic pattern recognition
3. **Real-time Data** — Including premarket and after-hours sessions, ad-free
4. **Deep ETF Insights** — Full holdings data (not just top 10), tree map visualization, performance metrics, structural metrics, fund flow data
5. **Unlimited Alerts** — News, ratings, insider trading, SEC filings, price movements; Portfolio and Screener alerts
6. **Export & APIs** — Screener filters, Portfolios, Groups, Options Chain, News → Excel; sample code for Google Sheets, Python, JavaScript
7. **ETF-Specific Screeners** — Single Category, Tags, Total Holdings, AUM, Net Fund Flows (1M/3M/YTD), Net Fund Flows %, Annualized Return (1Y/3Y/5Y), Net Expense Ratio, Active/Passive, Asset Type, Type, Sector/Theme

---

## 15. Portfolio & Alerts

### Portfolio Management
- Track up to 100 portfolios (Elite) / 50 (Free)
- Up to 500 tickers per portfolio (Elite) / 50 (Free)
- 8-year statements (Elite) / 3-year (Free)
- Correlated stocks feature (Elite)

### Alert Types
- **Price alerts** — Stock reaches specified price level
- **Insider trading alerts** — Management buy/sell activity
- **Analyst rating changes** — Upgrades/downgrades
- **News alerts** — Major news coverage
- **SEC filing alerts** — Company filings
- **Screener alerts** — New stocks matching saved screener filters
- **Portfolio alerts** — Changes in portfolio stocks

### Alert Delivery
- **Email alerts** — Unlimited (Elite)
- **Push notifications** — Mobile device
- Configurable per stock or per screener/portfolio

---

## 16. Maps & Groups

### Stock Market Maps (Finviz Maps)
Treemap visualization for browsing, searching, and analyzing large amounts of stock data. Color-coded by performance. Shows sectors/industries as nested rectangles.

### Stock Market Groups (Finviz Groups)
Sector/industry/group aggregation view. Shows performance grouped by category. Supports sorting and filtering.

---

## 17. Data & API / Export

### Export Formats
- **Excel export** for: Screener filters, Portfolios, Groups, Options Chain, News
- **CSV export** of all screener data (available on all pages via link)
- **API access** (Elite): sample code for Google Sheets, Python, JavaScript

### API Capabilities
- Screener data retrieval
- Portfolio data
- Groups data
- Options chain
- News data

### Data Freshness
- **Free tier:** 15-minute delay (NASDAQ), 20-minute delay (NYSE, AMEX)
- **Elite tier:** Real-time stock quotes
- **Futures:** 20-minute delayed (all tiers)
- **Fundamentals:** Recalculated and updated every hour
- **Premarket:** 4 AM − 9:30 AM (Elite)
- **After-hours:** 4 PM − 8 PM (Elite)

---

## 18. FAQ — Data, Markets, Subscription

### Markets Covered
- US markets only: NYSE, NASDAQ, AMEX
- No current plans to expand to other markets
- Can request addition of missing ticker symbols

### Data Limitations
- Raw historical data is NOT sold to third parties
- Stock quotes delayed 15 min (NASDAQ) or 20 min (NYSE/AMEX) for free tier
- Real-time for Elite subscribers
- Futures data delayed 20 minutes for all users

### Subscription Management
- **Free trial:** 7 days, requires credit card
- **Monthly:** $39.50/mo
- **Annual:** $299.50/yr (~$24.96/mo)
- Auto-renews unless cancelled
- Cancel anytime during trial to avoid charges
- **Refund policy:** 30-day refund window upon written request to support@finviz.com
- Data is account-linked (email), preserved across subscription changes

### Account Settings
- Change email/password: Settings → Login (Profile icon, top-right)

### Contact
- support@finviz.com
- Contact form on website
- Include screenshots and clear problem descriptions for technical support

---

## Appendix A: ETF-Specific Filters (Elite)

- ETF Single Category
- ETF Tags
- ETF Total Holdings
- ETF Assets Under Management (AUM)
- Net Fund Flows (1 Month, 3 Month, YTD)
- Net Fund Flows % (1 Month, 3 Month, YTD)
- Annualized Return (1 Year, 3 Year, 5 Year)
- Net Expense Ratio
- Active / Passive
- Asset Type
- Type
- Sector / Theme

## Appendix B: Complete Screener View Appearances

| View | Content |
|------|---------|
| **Overview** | Ticker, company name, sector, industry, country, market cap, P/E, price, change, volume. The default starting view. |
| **Valuation** | P/E, Forward P/E, PEG, P/S, P/B, Price/Cash, P/FCF, EPS (TTM), dividend yield |
| **Financial** | ROA, ROE, ROIC, gross/operating/net margins, current ratio, quick ratio, debt/equity, payout ratio |
| **Performance** | Returns across 1W, 1M, 3M, 6M, 1Y, YTD. Volatility (weekly/monthly), Relative Volume |
| **Technical** | RSI, Gap, SMA (20/50/200), Change, Change from Open, High/Low (20d/50d/52w), Pattern, Candle Stick, Beta, ATR |
| **Ownership** | Insider ownership %, Insider transactions, Institutional ownership %, Institutional transactions, Short Float %, Analyst Recommendation, Shares Outstanding, Shares Float |
| **Snapshot** | Compact view with key metrics from all categories |
| **Charts** | Visual chart view (Elite: custom views available) |
| **Stock Detail** | Full detail page with all available fields |

## Appendix C: Key Technical Indicator Settings (from Backtests)

| Indicator | Best Setting | Notes |
|-----------|-------------|-------|
| **RSI** | 14, 20/80 | Best overall performer; weak for short positions >5 days |
| **MACD** | 12, 26, 9 | Low success rate |
| **SMA** | Any | Worse than random |
| **EMA** | Any | Slightly better than random for short holding periods |
| **ADX** | Standard | Reliable trend strength measurement |
| **MFI** | 14 | Similar to RSI but with volume component |
| **Ultimate Oscillator** | 7, 14, 28 (4:2:1) | Reasonable success |

---

*End of Finviz Help Center Reference Document. Sources: finviz.com/help/screener, finviz.com/help/technical-analysis/, finviz.com/help/faq/, finviz.com/elite, finviz.com/blog/*
