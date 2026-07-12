# Finviz Help Center — Complete Reference

> Compiled from finviz.com/help/, finviz.com/knowledge-base/, finviz.com/elite, finviz.com/blog/
> Date: 2026-07-12

---

## Table of Contents

1. Screener — Filters & Signals
2. Financial Fundamentals Filters
3. Ownership & Trading Data Filters
4. Performance & Technical Filters
5. Screener Signals
6. Screener Filter Logic & Advanced Features
7. Sample Screens / Strategy Templates
8. Chart Patterns
9. Technical Analysis — Introduction
10. Moving Averages (SMA, EMA)
11. Oscillators (MACD, RSI, Stochastics, ADX, CCI, etc.)
12. Volatility-Based Indicators (Parabolic SAR, ROC, Bollinger Bands)
13. Volume-Based Indicators (MFI, Force Index)
14. Charts & Chart Patterns
15. Intraday Timeframes & Advanced Indicators
16. Charts & Technical Analysis — Platform Features
17. Stock Research
18. Insider Trading
19. Calendars
20. Maps & Groups
21. Portfolio & Alerts
22. Trading Strategies
23. How To Guides
24. Swing Trading with Finviz — Strategies, Setups & Screens
25. Learn & Reference — Technical Analysis
26. API & Data Sources
27. Finviz Elite Features
28. FAQ — Data, Markets, Subscription

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
Average of last N-periods. Shows price position relative to the average.
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
Chart pattern — distinct formation creating a trading signal. (See Section 8 for full pattern list)
- **Sorting:** No | **Export:** No | **Appearance:** Stock Detail

### Candle Stick
A candlestick pattern is a distinct formation of the Open, High, Low, and Close prices for given periods of time on a stock chart that creates a trading signal, or a sign of future price movements.

Detected patterns on daily charts:
- **White** — Simple bullish candle (close > open)
- **Black** — Simple bearish candle (close < open)
- **Doji** — Open ≈ Close — market indecision, potential reversal
- **Hammer** — Small body at top, long lower shadow — bullish reversal after downtrend
- **Inverted Hammer** — Small body at bottom, long upper shadow — bullish reversal signal
- **Spinning Top White** — Small bullish body with wicks — indecision but closed higher
- **Spinning Top Black** — Small bearish body with wicks — indecision but closed lower
- **Marubozu White** — Long bullish body with no wicks — strong buying all session
- **Marubozu Black** — Long bearish body with no wicks — strong selling all session
- **Long Upper Shadow** — Significantly long upper wick — rejection of higher prices

The Candlestick column appears in the TA view (`v=352`). Sortable but not a direct dropdown filter.
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

### Other Data Fields (shown in views, not filterable)

| Field | Definition |
|-------|-----------|
| **Shares Outstanding** | Total common shares owned by public |
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

## 6. Screener Filter Logic & Advanced Features

### Filter Logic
Screener filters use AND logic by default — all selected criteria must match. Multiple values within a single filter use OR logic (e.g., Sector = Technology OR Healthcare).

### Saving Screens
1. Set your desired filters
2. Click "Save As" in the preset dropdown
3. Name your screen
4. Access saved screens from the preset menu

Free users get 50 presets; Elite users get 200.

### Export Options
- **CSV Export**: Full screener data available on every page via "Export All Screener Data (CSV)" link
- **Excel Export (Elite)**: Screener filters, Portfolios, Groups, Options Chain, News
- **API (Elite)**: Programmatic access via REST endpoints

### Intraday Timeframes & Advanced Filters (Elite)
Announced August 2025. Available timeframes: 1-minute, 5-minute, 15-minute, hourly, daily, weekly, monthly.

Advanced technical indicators with customizable parameters:
- RSI (adjustable period)
- MACD
- ATR
- MFI
- Bollinger Bands
- EMA
- And more

### Top Lists & Presets
Pre-built screens accessible from the Signal dropdown:
- Top Gainers, Top Losers, New High, New Low
- Most Volatile, Most Active, Unusual Volume
- Overbought, Oversold
- Upgrades, Downgrades
- Earnings Before/After
- Major News
- Chart Patterns
- Recent Insider Buying/Selling

---

## 7. Sample Screens / Strategy Templates

### Value Stocks
Screens for undervalued companies with strong fundamentals.

**Typical Filters:**
- P/E Low (under 15)
- P/B Low (under 1.5)
- Dividend Yield > 1%
- EPS Growth Past 5Y positive
- Market Cap > Mid

### Oversold Bounce
Find stocks that have dropped sharply and may rebound.

**Typical Filters:**
- Oversold signal (RSI 14 under 30)
- Performance 1 Month negative (under -10%)
- Price above $5
- Average Volume over 100K
- Option/Short: Optionable

### 52-Week Highs
Stocks breaking out to new highs, often continuing higher.

**Typical Filters:**
- New High signal
- Average Volume over 100K
- Relative Volume > 1.0 (above average volume)
- Option/Short: Optionable

### Moving Average Crossover
Stocks where price crosses key moving averages.

**Typical Filters:**
- SMA 50-Day: Price above SMA50 (bullish) or below SMA50 (bearish)
- SMA 200-Day: Price above SMA200
- Performance 1 Month positive
- Average Volume over 100K

### Trend Following Setup
Stocks in established uptrends with momentum.

**Typical Filters:**
- SMA 50-Day: Price above SMA50
- SMA 200-Day: Price above SMA200
- Performance 3 Months > 10%
- Performance 1 Year > 20%
- Relative Volume > 0.8
- Price above $5

---

## 8. Chart Patterns

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

## 9. Technical Analysis — Introduction

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

## 10. Moving Averages (SMA, EMA)

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

**Backtest Results:**
- SMA: worse than random trading in most cases. Useless.
- EMA: better than random for 10/20-day sell signals, but still generates losses. Not suitable for trading.

---

## 11. Oscillators (MACD, RSI, Stochastics, ADX, CCI, etc.)

### Common Properties
- Values oscillate in a defined range (typically 0-100)
- Used as **leading indicators** — detect trend changes before they manifest
- Best in sideways markets; unreliable in strong trending markets during breakouts

### Key Concepts
- **Overbought / Oversold levels** — indicate extreme price moves likely to correct
- **Midpoint crossover** — oscillator crossing its midpoint value
- **Divergence** — price and oscillator moving in opposite directions (bearish: price higher high, oscillator lower high; bullish: opposite)

### Moving Average Convergence/Divergence (MACD)

> MACD Line = 12-day EMA − 26-day EMA
> Signal Line = 9-day EMA of MACD Line

**Uses:**
- MACD line crossing Signal line = buy/sell signal
- Histogram = difference between the two lines (crosses zero = crossover point)
- Divergence detection with price

**Backtest result:** Generally low success rate. Not reliable.

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

### Commodity Channel Index (CCI)

> CCI = (Price − SMA) / (0.015 × Standard Deviation of Price)

Originally for commodity futures. Normal range: −100 to +100.

**Backtest result:** Lags benchmark. If it beats, still generates losses.

### Stochastics

> %K = 100 × [(Close − Lowest Low N) / (Highest High N − Lowest Low N)]
> %D = 3-day SMA of %K

**Versions:** Fast, Slow (smoothed), Full (3 lines). Range: 0-100.
- %K crossing above %D = buy; below = sell

**Backtest result:** Beats benchmark for 5-day short positions but still not profitable.

### Average Directional Index (ADX)

> ADX measures trend strength (0-100 range)

**Components:** +DI line (upward trend), −DI line (downward trend)
- Rising ADX = trend gaining momentum
- ADX divergence with price = trend weakening
- +DI crossing −DI = potential trade signal

**Backtest result:** With setting ADX(14) >= 40, highly successful for long positions.

### Relative Momentum Index (RMI)
Adjusted RSI: compares current close with close from X days ago. Reduces false signals.

**Backtest result:** Works well with setting (20, 3) 20/80 for long positions. Not profitable for short sales.

### Ultimate Oscillator (Larry Williams)

> Buying Pressure = Close − min(Low, Prev Close)
> True Range = max(High, Prev Close) − min(Low, Prev Close)
> Computes 7, 14, and 28-day averages weighted 4:2:1

- Overbought: >70 | Oversold: <30

**Backtest result:** Works reliably for long positions with (7,14,28) 20/80 and (7,14,28) 25/75.

### Williams %R

> %R = [(Close − N-day Low) / (N-day High − N-day Low)] × 100
> Range: −100 to 0

**Backtest result:** Not persuasive. Results comparable to random trading.

### Trix
Based on triple exponentially-smoothed moving average. Filters price noise.

**Backtest result:** Beats benchmark in short sales but still generates losses.

### Money Flow Index (MFI)

> MFI = 100 − (100 / (1 + Money Ratio))
> Money Flow = Typical Price × Volume

**Backtest result:** Significantly beats benchmark with settings (28) 20/80 and (50) 20/80 for long positions. Generates losses for short positions.

### Force Index (Alexander Elder)

> Force Index = (Today's Close − Previous Close) × Today's Volume

**Backtest result:** In most cases less successful than random trading.

### Random Walk Index (RWI)
Assesses whether statistically significant trend exists vs. random movement. Short-term: 2-7 days. Long-term: 8-64 days. RWI > 1 = significant trend.

---

## 12. Volatility-Based Indicators

### Parabolic SAR (Stop And Reverse)

> Tomorrow's SAR = Today's SAR + AF × (Extreme Point − Today's SAR)

- AF starts at 0.02, increases by 0.02 per new high/low, max 0.20
- Works ~30% of the time; only in trending environments

**Backtest result:** Very poor results alone. With settings (0.02,0.2) and (0.05,0.5) combined with ADX, beats benchmark for long positions.

### Rate of Change (ROC)

> ROC = [(Close − Close N days ago) / Close N days ago] × 100

- Crossing above 0 = buy; below 0 = sell

### Bollinger Bands
Three lines: middle = 20-day SMA; upper/lower = SMA ± 2 standard deviations.

> Price expected inside range ~95% of time

- Price above upper band = overbought; below lower band = oversold
- Band widening = trend end; narrowing = new trend start

**Backtest result:** Beats benchmark in buy-and-hold for 5 days with setting (50, 3).

---

## 13. Volume-Based Indicators

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
- Positive = buying pressure; negative = selling pressure

---

## 14. Charts & Chart Patterns

### Candlestick Charts
Compress open, high, low, close into space-efficient candlesticks.

### Chart Patterns (from Learn & Reference)

**Support & Resistance:**
- Support: Price level where buying pressure prevents further decline
- Resistance: Price level where selling pressure prevents further rise
- Broken support becomes resistance; broken resistance becomes support
- Stronger levels are touched more times and by higher volume

**Trend Lines & Channels:**
- Uptrend line connects rising lows; downtrend line connects declining highs
- The more touch points, the stronger the trend line
- A trend line break on high volume signals a potential reversal
- Channels: parallel support/resistance lines containing price action

**Key Chart Patterns:**
- Head & Shoulders — reversal after uptrend
- Double Top/Bottom — reversal after trend
- Triangles (ascending, descending, symmetrical) — continuation
- Flags and Pennants — short-term continuation
- Wedges — can be reversal or continuation

**Volume Analysis:**
- Rising volume confirms trends; declining volume suggests weakness
- Volume should expand in the direction of the trend
- Divergence: price rising but volume declining = trend weakening
- Unusual volume spikes often precede major price moves

---

## 15. Intraday Timeframes & Advanced Indicators

> Announced August 2025 — for Elite subscribers.

### Available Intraday Timeframes
- 1-minute, 5-minute, 15-minute, hourly
- Daily, Weekly, Monthly

### Advanced Technical Indicators (customizable parameters)
- RSI (adjustable period)
- MACD
- ATR
- MFI
- Bollinger Bands
- EMA
- And more

### How to Use
1. Open Screener → Click **Technical**
2. Click **"+ Filter"** → Choose indicator
3. Set parameters (lookback, smoothing, thresholds)
4. Pick a **timeframe** (1-min to monthly)
5. Apply and see matching stocks

---

## 16. Charts & Technical Analysis — Platform Features

### Introduction to Charts
Finviz charts display price and volume data with extensive customization. Chart types include: **Candles, Line, Area, Hollow Candle, Heikin Ashi, Bar.**

### Extended Hours
Charts show pre-market (4 AM − 9:30 AM ET) and after-hours (4 PM − 8 PM ET) data. Elite subscribers can view extended hours trading.

### Compare Performance of Multiple Stocks
Overlay multiple tickers on a single chart to compare relative performance over time.

### Drawing Tools
- Trend lines, horizontal lines, ray lines
- Fibonacci retracements and extensions
- Channels, pitchforks
- Text labels and annotations
- Drawings persist across sessions when saved

### Chart Layouts
- Single chart, 2-layout split, 4-layout grid
- Each pane can display different tickers, timeframes, and indicators
- Layouts are saved automatically for Elite users

### Setup Multiple Charts
Open multiple tickers simultaneously in a grid layout. Each chart can have independent timeframes and indicators.

### Price Alerts from Charts
Right-click on a price level on the chart to set a price alert without navigating to the alerts page.

### Overlays (on the chart)
- SMA, EMA (multiple periods)
- Bollinger Bands
- Parabolic SAR
- VWAP
- Keltner Channels
- Ichimoku Cloud

### Indicators (in separate pane below chart)
- RSI, MACD, Stochastics
- Volume, Volume SMA
- ATR, ADX, CCI
- MFI, ROC, Williams %R
- OBV, Chaikin Money Flow

### Technical Indicators Explained
The knowledge-base includes detailed articles on each indicator's calculation, interpretation, and common trading strategies. See the `/help/technical-analysis/` reference for full formulas.

---

## 17. Stock Research

### Stock Page Overview
The stock detail page (e.g., `finviz.com/quote.ashx?t=AAPL`) provides a comprehensive view of a single company:

**Sections:**
- **Overview:** Current price, change, volume, day range, 52-week range
- **Fundamentals:** Market cap, P/E, EPS, dividend yield, revenue, net income
- **Financials:** Balance sheet, income statement, cash flow data
- **Technical Indicators:** RSI, SMA, ATR, Beta, volatility
- **Chart:** Interactive chart with full customization
- **News:** Latest headlines related to the ticker
- **Insider Trading:** Recent insider transactions
- **SEC Filings:** Recent company filings
- **Options Chain:** Available options with pricing
- **Peers:** Similar companies for comparison

### Stock Compare Tool
Compare up to 10 tickers side-by-side on fundamental metrics, performance, and technical indicators.

### Fundamentals Tab
Deep dive into a company's financial health:
- Revenue, net income, operating income
- EPS, diluted EPS
- Book value per share, cash per share
- Dividend yield, payout ratio
- Shares outstanding, float

### Financials Tab
Structured financial statements:
- **Income Statement:** Revenue, COGS, gross profit, operating expenses, net income
- **Balance Sheet:** Assets, liabilities, shareholder equity
- **Cash Flow:** Operating, investing, financing activities
- Quarterly and annual data available

### Earnings Forecasts & Revisions
- Consensus EPS estimates for upcoming quarters
- Earnings surprise history (actual vs. estimated)
- Analyst revisions (upgrades/downgrades)
- Revenue estimates

### Price Performance Before/After Earnings
Historical stock price behavior around earnings dates:
- Price change in days leading up to earnings
- Price gap and movement immediately after earnings
- Post-earnings drift

### Analyst Data
- Consensus rating (Strong Buy to Strong Sell)
- Price targets (high, median, low)
- Number of analysts covering
- Rating history and changes

### Options Tab
- Options chain with calls and puts
- Strike prices, expiration dates
- Last price, bid, ask, volume, open interest
- Implied volatility

---

## 18. Insider Trading

### Introduction to Insider Trading
Insider transactions (purchases and sales by executives and major shareholders) are required to be reported to the SEC. Insider buying can signal confidence; insider selling can be for many reasons (diversification, liquidity) and is less predictive alone.

### Insider Data
**Screener Filters:**
- Insider Ownership: % of shares owned by management
- Insider Transactions: % change in total insider ownership

**Stock Page Data:**
- Recent insider transactions with date, type (buy/sell), price, and number of shares
- Insider ownership summary
- Fund manager portfolios

### Fund Manager Portfolios & Insider Trades
Track holdings of major fund managers (13F filings). See what fund managers are buying and selling each quarter.

---

## 19. Calendars

### Calendar Overview
The Calendar page consolidates key upcoming market events into a single view: earnings reports, economic releases, and dividend dates.

### Earnings Calendar
- Upcoming and past earnings report dates
- Ticker, company name, EPS estimate, reporting time (before/after market open)
- Historical EPS surprise data
- Consensus estimates and actual results

### Economic Calendar
- Scheduled economic releases (CPI, GDP, employment data, Fed announcements)
- Date, time, forecast, prior value
- Impact rating (high/medium/low)

### Dividend Calendar
- Ex-dividend dates, payable dates
- Dividend amount and yield
- Historical dividend payments

---

## 20. Maps & Groups

### Introduction to Maps
Market maps provide visual representation of the market. Each rectangle represents a stock — sized by market cap, colored by performance.

### Map Types
- **S&P 500:** 500 largest U.S. companies
- **Full Market:** All stocks across NYSE, NASDAQ, AMEX
- **World:** International companies listed on U.S. exchanges
- **ETF:** ETF-focused view

### Map View
Stocks displayed as rectangles. Color coding: green (up) / red (down). Sizing: market cap. Hover for details — ticker, price, change, volume.

### Bubble View
Alternative visualization showing stocks as bubbles. Bubble size = market cap. Position on X/Y axes can be customized.

### Groups Introduction
Groups organize stocks by sector, industry, country, or market cap, showing aggregate performance data.

### Group Types
- **Sector:** 11 major sectors (Technology, Healthcare, Financial, etc.)
- **Industry:** 150+ specific industries within sectors
- **Country:** Geographic groupings (USA, China, Canada, etc.)
- **Market Cap:** Mega/Large/Mid/Small/Micro/Nano

### Group Views & Performance
- **Grid View:** Tabular data with sortable columns
- **Spectrum View:** Performance heat map
- Performance across timeframes (daily, weekly, monthly, quarterly, yearly)
- Fundamental aggregates (P/E, market cap, dividend yield)

---

## 21. Portfolio & Alerts

### Introduction to Portfolio
Create and manage portfolios to track investment positions. Add tickers with cost basis and quantity to monitor real-time performance and P&L.

### Portfolio Features
- **Default Table:** Positions with current price, change, gain/loss, total value, day P&L
- **Portfolio Map:** Heatmap of holdings sized by position value
- **Multiple Portfolios:** Up to 100 (Elite) / 50 (Free)
- **Tickers per Portfolio:** Up to 500 (Elite) / 50 (Free)
- **Statements:** Up to 8 years (Elite) / 3 years (Free)
- **Correlated Stocks:** See stocks that move with your positions (Elite)

### Create Portfolio
1. Navigate to the Portfolio page
2. Click "New Portfolio"
3. Give it a descriptive name (e.g., "Tech Portfolio", "Swing Trades")
4. Add tickers with optional cost basis and quantity

### Adding Positions
- Enter a ticker symbol and click Add
- Optionally add cost basis (purchase price) and quantity (shares) to track P&L
- Leave blank to use the portfolio as a watchlist

### Alerts Overview
Stay informed with timely alerts for stocks, including news, ratings, insider trading, SEC filings, and price movements. All alert types are ELITE features.

### Ticker Alerts
Set custom alerts for specific tickers:
- **Price:** Above/below a threshold
- **Percentage Change:** Exceeding a threshold
- **Volume Spike:** Unusual volume detection
- **Technical:** RSI overbought/oversold, SMA crossovers
- **New High/Low:** 52-week high/low

### Custom Alerts Setup
1. Navigate to the Alerts page
2. Select alert type (price, change, volume, technical, new high/low)
3. Set trigger conditions
4. Choose delivery method (email, push notification)
5. Save alert

### Push Notifications
Alerts delivered to mobile device via browser push notifications or the Finviz mobile interface. Covers all alert types.

### Portfolio Alerts
Set alerts for stocks in your portfolio:
- Price alerts (above/below threshold)
- Percentage change alerts
- Volume alerts
- Earnings date alerts
- Portfolio-wide or per-holding

### Screener Alerts
Set notifications when new stocks match your saved screener filters. Get alerted when a stock enters one of your saved screens.

---

## 22. Trading Strategies

### Day Trading with Finviz
Focus on intraday price movements. Key tools:
- **Screener:** Use intraday timeframes (1m, 5m, 15m), Top Gainers, Most Volatile signals
- **Charts:** 1-minute and 5-minute charts with VWAP, RSI, Volume indicators
- **Signals:** Unusual Volume, Overbought/Oversold for short-term reversals
- **News:** Major News signal for catalysts
- **Pre-market/After-hours:** Extended hours data for gap analysis

### Swing Trading with Finviz
Hold positions for days to weeks. Key tools:
- **Screener:** Daily timeframe filters, chart patterns (Double Bottom, Channel Up), RSI, SMA
- **Signals:** Chart Patterns, Unusual Volume, Oversold, New High
- **Technicals:** RSI(14) overbought/oversold for entry timing, SMA 20/50 for trend
- **Sample Screen:** Oversold Bounce strategy
- **Earnings:** Avoid trading into earnings or use earnings plays

### Long-Term Investing with Finviz
Hold positions for months to years. Key tools:
- **Screener:** Fundamental filters (low P/E, low P/B, dividend yield, EPS growth)
- **Sample Screen:** Value Stocks screen
- **Financials:** Balance sheet health, profit margins, ROE, debt/equity
- **Charts:** Weekly and monthly timeframes for long-term trends
- **Dividends:** Dividend Calendar for income planning

### Risk Management
- **Position Sizing:** Never risk more than 1-2% of capital on a single trade
- **Stop Losses:** Set stop-losses at key technical levels (below support, below moving averages)
- **Diversification:** Use sector/industry filters to avoid overconcentration
- **Correlation:** Check correlated stocks feature (Elite) to understand portfolio overlap
- **Risk/Reward:** Look for setups with at least 2:1 reward-to-risk ratio

### Position Sizing
Formulas and approaches:
- **Fixed Percentage:** Risk fixed % of capital per trade (e.g., 1%)
- **Kelly Criterion:** Optimal size based on win rate and average win/loss
- **Equal Weight:** Same dollar amount per position
- Use average volume filter to ensure sufficient liquidity for your position size

### Market Psychology
- Markets oscillate between fear (overselling, panic) and greed (overbuying, euphoria)
- Oversold conditions on RSI and extreme negative sentiment often mark buying opportunities
- Overbought conditions can persist during strong trends
- Use volume to gauge conviction behind price moves

---

## 23. How To Guides

### Find Trade Ideas
1. Start with a signal: Top Gainers, Unusual Volume, or Chart Patterns
2. Apply filter: Set minimum price ($5+), minimum volume (100K+)
3. Switch to a visual view (Charts or Snapshot) to scan quickly
4. Look for clean technical setups: clear support/resistance, trending SMA alignment
5. Check news for catalysts

### Scan the Market
1. Use Screener to apply your preferred filters
2. Save common scans as presets for quick access
3. Start broad (e.g., all stocks), then narrow with additional filters
4. Use Group views to identify which sectors are leading/ lagging
5. Check Maps for visual sector/industry rotation

### Research a Stock
1. Start on the Stock Page (quote.ashx)
2. Check Fundamentals: P/E, EPS growth, profit margins, debt levels
3. Review the Chart: long-term trend, key support/resistance levels
4. Check Technical Indicators: RSI, SMA position, volume trends
5. Read Latest News for catalysts
6. Check Insider Trading and Institutional Ownership
7. Review Earnings Dates and history
8. Compare with Peers using Stock Compare

### Find Earnings Plays
1. Use Earnings Calendar to identify upcoming reports
2. Use Earnings Before/After signals on the day
3. Screen for: high earnings surprise history, positive earnings revisions
4. Use options chain for straddles/strangles if expecting big moves
5. Check price performance before/after prior earnings for patterns

### Spot Unusual Activity
1. Use Unusual Volume signal — stocks with highest relative volume
2. Combine with: news catalysts, insider buying, earnings dates
3. Look for: volume spikes without clear news (informed trading)
4. Check options: unusual options volume can signal directional bets
5. Verify on the chart: heavy volume at key support/resistance levels

---

## 24. Swing Trading with Finviz — Strategies, Setups & Screens

This section consolidates best practices from professional swing traders using Finviz. Swing trading typically involves holding positions for 2-10 days, catching intermediate moves between support and resistance levels.

### Core Swing Trading Workflow

1. **Evening scan (after market close):** Run saved Finviz screens to generate a candidate list
2. **Sort & filter results:** Sort by Relative Volume (descending) to see stocks with unusual activity first
3. **Switch to Charts view:** Visually scan 20+ daily charts at once — the fastest way to eliminate bad setups
4. **Manual chart review:** Open individual ticker pages. Look for clean technical structure: clear support/resistance, trending SMA alignment, volume confirmation
5. **Build a watchlist:** Select 5-10 best candidates. Define entry price, stop loss, and profit target for each
6. **Set alerts:** Use Finviz alerts or a secondary platform (TradingView) to be notified when entry triggers
7. **Manage the trade:** Check 10 minutes daily. Let the setup play out unless the thesis invalidates

### Why Screening for Swing Trading Differs from Day Trading

| Aspect | Day Trading | Swing Trading |
|--------|-------------|---------------|
| **Timeframe** | 1m-15m charts | Daily charts |
| **Scan timing** | Market open, 10 AM | After close, weekends |
| **Key filter** | Pre-market gap, intraday volume | RSI, SMA position, patterns |
| **Data delay tolerance** | Needs real-time (Elite) | Free tier OK (end-of-day) |
| **Holding period** | Minutes to hours | 2-10 days |
| **Price range** | $5-$50 | $5-$300 |
| **Volume minimum** | 1M+ shares | 300K-500K shares |

### Strategy A: Momentum Breakout (Uptrend Continuation)

**Goal:** Catch stocks in a confirmed uptrend that are showing renewed buying pressure.

**Finviz Screener Settings:**
| Filter | Setting | Reason |
|--------|---------|--------|
| Market Cap | Mid ($2B+) or Large ($10B+) | Avoid illiquid micro-caps |
| Price | Over $10 (or $15 for tighter list) | Filter out penny stocks |
| Average Volume | Over 500K (1M+ for high liquidity) | Ensures easy entry/exit |
| EPS Growth This Year | Over 20% | Earnings support |
| EPS Growth Next Year | Over 15% | Forward-looking momentum |
| Return on Equity | Over 15% | Quality screen |
| SMA 20-Day | Price above SMA20 | Short-term uptrend |
| SMA 50-Day | Price above SMA50 | Medium-term uptrend |
| RSI (14) | Between 50 and 70 | Trending but not overbought |
| Performance (Week) | Up | Short-term momentum confirmation |
| Relative Volume | Over 1.0 (or 1.5 for tighter) | Above-average participation |

**Sort by:** Relative Volume descending, then Performance (Week)

**Post-Screen Chart Review:**
- Check the stock is above both SMA50 and SMA200
- Look for orderly pullbacks within the uptrend (not wild spikes)
- Volume should expand on up days and contract on pullbacks
- Avoid stocks with earnings in the next 5 days (gap risk)
- Define entry: 1-2% above recent high/resistance
- Stop loss: below the most recent swing low or below SMA50
- Target: next resistance level or 2:1 reward-to-risk

**When to skip:**
- Stock is extended more than 20% above SMA50
- RSI above 80 (overbought in a strong trend can persist, but entry risk is higher)
- Earnings within the week
- Low volume breakout (RelVol < 1.0)

---

### Strategy B: Pullback / Bounce Setup

**Goal:** Find stocks in an established uptrend that have pulled back to a support level (SMA, trendline, or Fib retracement).

**Finviz Screener Settings:**
| Filter | Setting | Reason |
|--------|---------|--------|
| Market Cap | Over $1B (Mid+) | Quality filter |
| Price | Between $10 and $300 | Tradeable range |
| Average Volume | Over 500K | Liquidity |
| SMA 20-Day | Price above SMA20 | Still in short-term uptrend |
| SMA 50-Day | Price above SMA50 | Medium-term trend intact |
| RSI (14) | Between 40 and 55 | Pulled back but not broken down |
| Change from Open | Negative (optional) | Pulling back today |
| Performance (Week) | Negative or Neutral | Recent pullback |

**Post-Screen Chart Review:**
- Confirm the stock is in a clear uptrend on the weekly chart
- Look for pullback to SMA50 or a prior resistance-turned-support level
- Volume should be declining during the pullback (sellers exhausting)
- The pullback should not break below the prior swing low
- Entry: at the support level or on a reversal candle (hammer, bullish engulfing)
- Stop loss: below the pullback low
- Target: the prior high or next resistance level
- Ideal risk/reward: at least 2:1

**Key insight from practitioners:** A stock trading above SMA20, SMA50, AND SMA200 with declining volume on the pullback is one of the highest-probability swing setups.

---

### Strategy C: Oversold Bounce / Reversal

**Goal:** Catch short-term bounces from oversold conditions, typically after an overreaction.

**Finviz Screener Settings:**
| Filter | Setting |
|--------|---------|
| Price | Over $5 |
| Average Volume | Over 300K |
| RSI (14) | Oversold (below 30) |
| Performance (Month) | Down (confirms recent decline) |
| Relative Volume | Over 1.5 (reversal should have volume) |
| SMA 200-Day | Price above SMA200 (optional — keeps in long-term uptrend) |

**Post-Screen Chart Review:**
- Look for a bullish reversal candle (hammer, doji, bullish engulfing) near a known support level
- Check for positive divergence on RSI (price lower low but RSI higher low)
- Avoid stocks with earnings in the next week
- Check for a fundamental catalyst (news, insider buying)
- Entry: on confirmation (next day follow-through, not the first green candle)
- Stop loss: below the recent swing low
- Price target: nearest resistance (SMA20, then SMA50)

**Source variation — additional filters some traders use:**
- Sales Growth QoQ > 20% (fundamental confirmation)
- Short Float > 5% (potential short squeeze fuel on the bounce)
- Beta ≥ 1 (bigger bounces in a recovery)

---

### Strategy D: Compression / Coil Breakout

**Goal:** Find stocks consolidating in a tight range with declining volume, setting up for a breakout.

**Finviz Screener Settings:**
| Filter | Setting | Reason |
|--------|---------|--------|
| Price | $5 to $100 | Capture mid-range names |
| Average Volume | Over 500K | Enough liquidity for 2-5 day holds |
| RSI (14) | Between 40 and 60 | Middle zone — not yet committed |
| Volatility | Low (or declining ATR) | Captures coiling/compression |
| SMA 50-Day | Price above SMA50 | Ensures overall trend is up |
| SMA 200-Day | Price above SMA200 | Long-term trend confirmation |
| 20-Day High/Low Range | Less than 10% (narrow range) | Tight consolidation |

**Post-Screen Chart Review:**
- **The Coil:** Price should be in a narrow range for at least 7-14 days
- **Volume dry-up:** Volume during compression should be declining (50-70% of 20-day average)
- **Trend context:** Stock should be above rising SMA50 and SMA200 (bullish structural trend)
- **The breakout trigger:** Volume spike to 2x+ average on the breakout day
- Entry: 1-2% above the top of the compressed range (confirmation)
- Stop loss: below the bottom of the compressed range
- Target: next major resistance or 2:1 reward-to-risk

**Why this works:** During the coiling phase, sellers exhaust (volume drys up). When the breakout comes on high volume, it has institutional participation — not just retail chasing.

---

### Strategy E: High Short Float / Squeeze Potential

**Goal:** Find stocks with elevated short interest that could squeeze higher on positive momentum.

**Finviz Screener Settings:**
| Filter | Setting |
|--------|---------|
| Market Cap | Over $300M |
| Price | Over $5 |
| Average Volume | Over 500K |
| Short Float | High (over 10% or 20%) |
| Relative Volume | Over 1.0 |
| SMA 20-Day | Price above SMA20 (momentum confirmation) |
| Performance (Month) | Up (already showing strength) |

**Post-Screen Chart Review:**
- Rising price + high short float = squeeze potential
- Check for recent insider buying (confirms management confidence)
- Look for a catalyst: earnings beat, new product, analyst upgrade
- Entry: on a volume day with strong price action
- Risk: short squeezes reverse fast. Tight stop losses are essential.

---

### Strategy F: Value with Earnings Support

**Goal:** Find fundamentally cheap stocks with earnings growth.

**Finviz Screener Settings:**
| Filter | Setting |
|--------|---------|
| Market Cap | Mid ($2B+) or Large ($10B+) |
| Price | Over $10 |
| Average Volume | Over 500K |
| P/E | Under 15 |
| Forward P/E | Under 12 |
| EPS Growth This Year | Over 10% |
| ROE | Over 15% |
| Debt/Equity | Under 0.5 |
| Price vs SMA50 | Above SMA50 (technical confirmation) |

**Post-Screen Chart Review:**
- Check for insider ownership over 10% (aligned incentives)
- Review the PEG ratio (under 2 is reasonable for quality)
- Scan news for any recent negative developments
- Enter on technical pullback to SMA50 or a support level

---

### The 5-Core Filters That Matter Most for Swing Trading

Across all strategies, these filters eliminate ~85% of the market:

1. **Average Volume > 500K** — Liquidity. Prevents getting trapped in illiquid names.
2. **Price > $5 (or $10)** — Avoids penny stocks and erratic price action.
3. **Relative Volume > 1.0 (ideally > 1.5)** — Confirms something is happening. The most important filter for finding setups.
4. **Price above SMA20** — Short-term trend filter. You want momentum with the trend, not against it.
5. **Float** — Under 100M shares (smaller floats move faster).

### Market Condition Adjustments

| Market Environment | Adjustments |
|-------------------|-------------|
| **Strong bull market** | Loosen RelVol to 1.2x; broaden price range; more stocks show momentum |
| **Choppy / range-bound** | Tighten RelVol to 2.0x+; focus on quality names ($20-$100 range) |
| **Bear market / risk-off** | Shift to $20-$100 range; avoid sub-$10 stocks (random volatility); use short screens |
| **Low volatility environment** | Use Compression/Coil screens; tighten range filters |
| **High volatility environment** | Widen ATR filters; use wider stops |

### Common Mistakes in Swing Trading with Finviz

| Mistake | Fix |
|---------|-----|
| Over-filtering (0-2 results) | Start broad (5-8 filters max). Tighten incrementally |
| Ignoring the "Charts view" | Always switch to Charts view — visual scanning catches what numbers miss |
| Trading into earnings | Check Earnings Date filter. Avoid holding through unknown events |
| Chasing extended stocks | Skip stocks more than 20% above SMA50. Wait for pullback |
| No defined stop loss | Define entry, stop, and target before clicking buy |
| Using too many patterns | Pick 2-3 patterns you understand best. Master those |
| Screening during market hours | Swing scans work best after close. Intraday scans = noise |
| Not checking sector context | Use Maps to see if the sector is leading or lagging |

### Sample Evening Routine (30 minutes)

| Time | Action |
|------|--------|
| 4:30 PM (after close) | Run your primary swing screen (e.g., Momentum Breakout) |
| 4:35 PM | Sort by Relative Volume descending. Note the top 10-15 names |
| 4:40 PM | Switch to Charts view. Scan 20 daily charts at once. Eliminate messy setups |
| 4:50 PM | Open individual ticker pages for survivors. Check fundamentals, news, support/resistance |
| 5:00 PM | Build watchlist of 3-5 stocks. Define entry/stop/target for each |
| 5:10 PM | Check Maps for sector context. Are your stocks in leading sectors? |
| 5:15 PM | Set alerts at entry levels. Done. |

---

## 25. Learn & Reference — Technical Analysis

### Support & Resistance
- **Support:** Price level where buying pressure prevents further decline
- **Resistance:** Price level where selling pressure prevents further rise
- A level's strength increases with: number of touches, volume at the level, timeframe (weekly > daily)
- Once broken, support becomes resistance and vice versa
- Round numbers often act as psychological support/resistance

### Trend Lines & Channels
- **Uptrend line:** Connects two or more rising lows. More touch points = stronger
- **Downtrend line:** Connects two or more declining highs
- **Breakouts:** A close above/below a trend line on higher volume confirms the break
- **Channels:** Two parallel trend lines. Price bounces between them. Breakout signals trend acceleration

### Chart Patterns
- **Head & Shoulders:** Top = bullish-to-bearish reversal. Inverse = bearish-to-bullish reversal
- **Double Top/Bottom:** After trend, two equal tests of support/resistance. Break of the middle confirms
- **Triangles:** Ascending (bullish), Descending (bearish), Symmetrical (breakout direction unclear)
- **Flags/Pennants:** Sharp trend followed by consolidation = continuation

### Volume Analysis
- Volume confirms price action: rising price + rising volume = healthy trend
- Divergence: price up, volume down = weakening trend
- Climax volume after long trend = potential exhaustion
- Breakout on low volume = more likely to fail
- Unusual Volume signal catches stocks with volume far above normal

### Market Breadth & Sentiment
- **Advance/Decline:** More stocks advancing than declining = broad strength
- **New Highs vs New Lows:** More new highs = bullish environment
- **Overbought/Oversold signals:** Gauge short-term extremes
- **Fear & Greed cycles:** Extreme readings often precede reversals

---

## 26. API & Data Sources

### API Access & Authentication (Elite)
The Finviz API provides endpoints for screener data, quote data, and portfolio management.

**Access:** Settings → API section in user menu. API key generated per account.

**Screener Endpoint:** Pass screener filter parameters to retrieve matching stocks. Supports all filter criteria available in the Screener UI.

**Rate Limits:** Usage limits apply based on subscription tier. Details in Settings → API.

### Data Providers
Finviz aggregates data from:
- Exchange data feeds (NYSE, NASDAQ, AMEX) for real-time quotes
- SEC EDGAR for fundamental data and filings
- FINRA for short interest data
- Third-party data providers for estimates, analyst ratings, and corporate actions

### Update Frequency
- **Stock Quotes:** Free: 15-min delay (NASDAQ), 20-min (NYSE/AMEX). ELITE: real-time
- **Futures Quotes:** 20-min delayed (all tiers)
- **Fundamentals:** Recalculated hourly with latest data
- **Short Interest:** Updated semi-monthly based on FINRA reports
- **Insider Trading:** Updated daily from SEC filings
- **Analyst Ratings:** Updated as new ratings are published
- **News:** Continuously updated throughout the day

### Real-Time vs Delayed Data
- **Free (delayed):** Quotes 15-20 minutes behind. Adequate for long-term investors
- **Elite (real-time):** Streaming quotes during market hours (9:30 AM − 4:00 PM ET)
- **Extended Hours (Elite):** Premarket 4 AM − 9:30 AM, After-hours 4 PM − 8 PM ET
- **Historical Data:** Only available within Charts, not as raw data export

### Performance Calculations
- **Daily Return:** (Current Close − Previous Close) / Previous Close
- **Multi-period Returns:** Compounded daily returns over the period
- **Volatility:** Average of daily high/low percentage ranges
- **Beta:** Slope of 60-month regression line of stock % change vs index % change

---

## 27. Finviz Elite Features

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

### Elite Key Capabilities
1. **Interactive Multi-Layout Charts** — Draw patterns, add indicators, switch layouts
2. **Award-Winning Screener** — 20+ advanced customizable filters, benchmarks, pattern recognition
3. **Real-time Data** — Including premarket and after-hours, ad-free
4. **Deep ETF Insights** — Full holdings data, tree map, performance metrics, fund flows
5. **Unlimited Alerts** — News, ratings, insider, SEC, price; Portfolio and Screener alerts
6. **Export & APIs** — Excel, Google Sheets, Python, JavaScript
7. **ETF-Specific Screeners** — Category, Tags, Holdings, AUM, Fund Flows, Expense Ratio, etc.

---

## 28. FAQ — Data, Markets, Subscription

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
- **Monthly:** $39.50/mo | **Annual:** $299.50/yr
- Auto-renews unless cancelled
- Cancel anytime during trial to avoid charges
- **Refund policy:** 30-day refund window upon written request to support@finviz.com
- Data is account-linked (email), preserved across subscription changes

### Account Settings
- Change email/password: Settings → Login (Profile icon, top-right)

### Market Hours
- **Regular:** 9:30 AM − 4:00 PM ET, Mon-Fri
- **Premarket (Elite):** 4:00 AM − 9:30 AM ET
- **After-hours (Elite):** 4:00 PM − 8:00 PM ET
- Closed on weekends and market holidays

### Contact
- support@finviz.com
- Contact form on website

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
| **Overview** | Ticker, company name, sector, industry, country, market cap, P/E, price, change, volume |
| **Valuation** | P/E, Forward P/E, PEG, P/S, P/B, Price/Cash, P/FCF, EPS (TTM), dividend yield |
| **Financial** | ROA, ROE, ROIC, gross/operating/net margins, current ratio, quick ratio, debt/equity, payout ratio |
| **Performance** | Returns across 1W, 1M, 3M, 6M, 1Y, YTD. Volatility (weekly/monthly), Relative Volume |
| **Technical** | RSI, Gap, SMA (20/50/200), Change, Change from Open, High/Low (20d/50d/52w), Pattern, Candle Stick, Beta, ATR |
| **Ownership** | Insider ownership %, Insider transactions, Institutional ownership %, Institutional transactions, Short Float %, Analyst Recommendation, Shares Outstanding, Shares Float |
| **Snapshot** | Compact view with key metrics from all categories |
| **Charts** | Visual chart view (Elite: custom views available) |
| **Stock Detail** | Full detail page with all available fields |

## Appendix C: Indicators Ranked by Backtest Performance

| Rank | Indicator | Best Setting | Performance |
|------|-----------|-------------|-------------|
| 1 | **RSI** | 14, 20/80 | Best overall. Profitable long. Weak for short >5 days |
| 2 | **ADX** | ADX(14) >= 40 | Highly successful for long positions |
| 3 | **Ultimate Oscillator** | (7,14,28) 20/80 | Reliable long positions |
| 4 | **RMI** | (20,3) 20/80 | Good profits long; not profitable short |
| 5 | **MFI** | (28) 20/80 | Beats benchmark long; losses short |
| 6 | **Bollinger Bands** | (50,3) | Beats benchmark buy&hold 5d |
| 7 | **Parabolic SAR + ADX** | (0.02,0.2) + ADX | Beats benchmark long with ADX |
| 8 | **TRIX** | 14-day | Beats benchmark short sales |
| 9 | **Stochastics** | — | Beats 5d short; still unprofitable |
| 10 | **EMA** | — | Slightly better than random |
| 11 | **MACD** | — | Generally low success rate |
| 12 | **CCI** | — | Lags benchmark |
| 13 | **Williams %R** | — | Comparable to random |
| 14 | **Force Index** | — | Worse than random |
| 15 | **SMA** | — | Useless. Worse than random |
| — | **Parabolic SAR alone** | — | Very poor alone |

Test period: Jan 1, 1995 to Jul 17, 2009. Universe: 16,954 US stocks (price >$1, volume >100K). Exit after 5/10/20 days. No commissions included.

---

*End of Finviz Help Center Complete Reference.*
*Sources: finviz.com/help/, finviz.com/knowledge-base/, finviz.com/elite, finviz.com/blog/*

*Raw knowledge-base dump also available at: swing_screener/library/finviz_knowledge_base_full.md*
