## 8. Recommended Practical Portfolios

This final chapter assembles the building blocks from preceding chapters — momentum and mean reversion strategies, risk management frameworks, and automation infrastructure — into three complete portfolio blueprints. Each includes exact allocations, realistic return expectations after backtest-to-live degradation, and step-by-step implementation guidance. Return projections incorporate a 30–50% haircut to backtested figures, consistent with the finding that strategies showing 30% CAGR in backtesting typically deliver 13–17% live once overfitting, costs, slippage, and decay are applied [^279^].

![Three Recommended Portfolio Profiles: Expected Return vs. Drawdown Risk](fig8_portfolio_profiles.png)

The bar chart above summarizes expected CAGR and drawdown ranges for each tier. All three portfolios are designed for tax-advantaged accounts (IRA, 401k rollover, or HSA), where short-term capital gains — taxed at ordinary income rates up to 40.8% for high earners [^786^] — do not erode compounding.

### 8.1 Conservative Portfolio: "Steady Compound" ($50,000 Minimum)

The conservative portfolio targets capital preservation with moderate growth, suitable for traders new to systematic strategies or those within 10 years of retirement. It combines Dual Momentum's absolute momentum cash filter with the IBS (Internal Bar Strength) mean reversion system. The $50,000 minimum reflects the retail capital floor identified in Chapter 7: at this level, fixed fractional risk of 1% per trade yields $500 risk capital per position, sufficient for meaningful position sizing in liquid ETFs with slippage below 5 bps per trade [^244^].

**Table 8.1 — "Steady Compound" Portfolio: Allocation, Expected Returns, and Implementation**

| Component | Allocation | Backtested CAGR | Realistic Live CAGR | Max Drawdown | Instruments | Rebalancing |
|-----------|-----------|-----------------|---------------------|--------------|-------------|-------------|
| Dual Momentum (Antonacci GEM) | 50% ($25K) | 12.3–17.4% [^18^] | 8–10% | –17.8% [^435^] | SPY, VEU, AGG | Monthly |
| IBS + Lower Band Mean Reversion | 50% ($25K) | 13.0% [^358^] | 8–10% | –20.3% [^358^] | SPY | Variable (signal-driven) |
| **Portfolio Total** | **100%** | **12–15%** | **10–14%** | **–12 to –15%** | — | Monthly review |

The Dual Momentum component follows Antonacci's exact rules: compare 12-month total return of the S&P 500 against US Aggregate Bonds; if stocks outperform, hold the better of US (SPY) or international (VEU) equities; otherwise, move 100% to bonds (AGG). Antonacci's original backtest (1974–2013) reported 17.43% CAGR with –22.72% max drawdown [^314^], while out-of-sample (1986–2026) shows 12.3% CAGR [^313^]. The 8–10% live estimate blends these periods plus a degradation buffer. The absolute momentum filter — which moved to bonds before the 2008 and 2022 drawdowns — is the critical risk management feature.

The IBS + Lower Band component uses a two-parameter system: entry when IBS = (Close – Low)/(High – Low) falls below 0.2 and price touches the lower Bollinger Band (20-period, 2 standard deviation), exit when IBS rises above 0.8 or after a 5-day holding period. QuantifiedStrategies backtests on SPY show 13.0% CAGR, 2.11 Sharpe ratio, and 75% win rate with an average hold of 3–4 days [^358^]. Because this strategy is in the market only 20–25% of the time, its correlation with the Dual Momentum component is low, providing genuine diversification. The monthly review involves checking whether any IBS positions remain open and rebalancing the Dual Momentum sleeve on the last trading day.

**Automation approach.** The Dual Momentum sleeve can be implemented with TradingView alerts set to trigger on the last trading day of each month, calculating 12-month returns and emailing a buy/sell/hold signal. The IBS sleeve requires either TradingView Pine Script alerts or a daily scan after market close; trades execute at the next open. Total estimated time commitment: 30–60 minutes monthly. For traders comfortable with modest scripting, TradingView webhooks [^239^] can push alerts to a broker API for semi-automated execution. Total round-trip costs at IBKR Pro Fixed pricing ($0.005/share) amount to roughly $2–4 per month given the low trade frequency of both strategies [^724^].

### 8.2 Moderate Portfolio: "Balanced Alpha" ($75,000 Minimum)

The moderate portfolio captures the institutional insight that combining momentum and mean reversion — which exhibit approximately –0.35 correlation [^146^] — produces superior risk-adjusted returns to either style alone. D.E. Shaw demonstrated that pairwise correlations between 20+ strategies remained below 0.1 even during the GFC [^624^], while AQR's work confirms equal-weight allocation across uncorrelated strategies outperforms complex optimization [^146^]. The $75,000 minimum provides $15,000–$25,000 per strategy, enough to run four systems without positions falling below slippage thresholds.

**Table 8.2 — "Balanced Alpha" Portfolio: Allocation, Expected Returns, and Implementation**

| Component | Allocation | Backtested CAGR | Realistic Live CAGR | Max Drawdown | Instruments | Holding Period |
|-----------|-----------|-----------------|---------------------|--------------|-------------|----------------|
| RSI(2) Mean Reversion on QQQ | 30% ($22.5K) | 10.7% [^403^] | 6–8% | –23% [^403^] | QQQ | 3–5 days |
| Dual Momentum (Antonacci GEM) | 30% ($22.5K) | 12.3–17.4% [^18^] | 8–10% | –17.8% [^435^] | SPY, VEU, AGG | 1–2 trades/year |
| IBS + Band on IWM | 25% ($18.75K) | 26.4% [^369^] | 10–13% | –28% [^369^] | IWM | 3–5 days |
| Sector Momentum (Top-1 SPDR) | 15% ($11.25K) | 13% [^20^] | 7–9% | –25% | Sector SPDRs | Monthly |
| **Portfolio Total** | **100%** | **14–19%** | **15–18%** | **–18 to –22%** | — | — |

The RSI(2) component follows Connors' rules: buy QQQ when the 2-period RSI falls below 5 while price stays above the 200-day moving average; sell when RSI(2) rises above 65 [^205^]. QuantifiedStrategies' backtest (1999–2025) reports 10.7% CAGR, 71% win rate, and 0.9% average gain per trade with only 18% market exposure [^403^]. The 200-MA filter prevents catching falling knives during secular bear markets. Independent Reddit replication over 34 years confirmed the strategy "holds up" but produces infrequent trades, reinforcing the multi-instrument approach [^45^].

The IBS + Band on IWM uses the same mechanics as the conservative portfolio's SPY sleeve but targets the Russell 2000, which exhibits higher volatility and stronger mean reversion due to its smaller-cap composition. Quantitativo's multi-instrument IBS+Band portfolio achieved 26.4% CAGR with 149 trades per year and a 62% win rate [^369^]. The concentrated allocation to IWM captures this edge while the RSI(2) on QQQ provides exposure to a different market cap segment with a different parameter set, reducing the risk that both mean reversion strategies fail simultaneously.

The Sector Momentum sleeve allocates monthly to the top-performing SPDR sector ETF by 12-month total return, a proven approach with 13% historical CAGR [^20^]. This adds a trend-following component that prospers during sustained economic expansions when sector leadership persists — precisely the conditions under which mean reversion strategies tend to underperform.

**Automation approach.** This portfolio requires the Interactive Brokers API with Python. The recommended stack uses `ib_insync` [^742^] for order management, with a daily script that: (1) downloads end-of-day data at 4:05 PM, (2) generates signals for all four strategies, (3) queues market-on-close orders for execution by 4:10 PM. The Dual Momentum component runs only on the last trading day of each month; the RSI(2) and IBS components scan daily; the Sector Momentum component runs monthly on the same schedule as Dual Momentum. An EC2 t3.micro instance ($7.50/month) suffices to host the script [^709^], and IBKR Pro tiered pricing ($0.0035/share) keeps costs at roughly $15–25/month given ~20–40 trades monthly [^724^].

### 8.3 Aggressive Portfolio: "Maximum Growth" ($100,000 Minimum)

The aggressive portfolio is designed for experienced systematic traders with high risk tolerance, a 10+ year horizon, and the emotional discipline to withstand 25–35% drawdowns. It allocates equally across four high-return strategies identified in preceding chapters, each targeting a different source of alpha: concentrated mean reversion, leveraged momentum, long-term trend following, and multi-factor quant selection. The $100,000 minimum provides $25,000 per strategy — enough to withstand the inevitable 20% drawdown in any single component without impairing the overall portfolio. This allocation also crosses the Portfolio Margin threshold at most brokers ($110K recommended), enabling modest leverage if desired.

**Table 8.3 — "Maximum Growth" Portfolio: Allocation, Expected Returns, and Risk Controls**

| Component | Allocation | Backtested CAGR | Realistic Live CAGR | Max Drawdown | Risk Control |
|-----------|-----------|-----------------|---------------------|--------------|--------------|
| Mean Reversion Curve (concentrated) | 25% ($25K) | 34.0% [^62^] | 14–18% | –35% | Max 4 positions, 2% risk/trade |
| TQQQ Weekly MACD | 25% ($25K) | ~36% [^118^] | 15–20% | –45%* | 30% dynamic stop, 10% entry stop |
| Weekend Trend Trader | 25% ($25K) | 22.9% [^21^] | 10–14% | –58% | 20-week high exit rule |
| Multi-Factor Quant (Piotroski + SUE) | 25% ($25K) | 23% [^279^] | 10–13% | –35% | Annual rebalance, 20-stock max |
| **Portfolio Total** | **100%** | **25–34%** | **20–28%** | **–25 to –35%** | VIX scaling + circuit breakers |

*TQQQ strategy was not tested in the 2000–2002 dot-com crash as the ETF launched in 2010.

The Mean Reversion Curve component, sourced from Quantitativo's research, combines six RSI(2) parameter sets with monthly Sharpe-optimized rebalancing. The concentrated variant (maximum four simultaneous positions) achieved 34% CAGR in backtests since 2010, compared to 25.7% for the diversified version [^62^]. Live expectations of 14–18% reflect the documented 30–50% weakening of mean reversion edges since 2010 as HFTs compressed short-term alphas [^279^]. Position sizing uses fixed fractional 2% risk per trade with a portfolio heat cap of 8% (no more than four correlated positions open simultaneously) [^700^].

The TQQQ Weekly MACD component uses Lambros Petrou's system: weekly MACD signals on unleveraged QQQ to time entries in 3x leveraged TQQQ [^118^]. A dual stop-loss (10% entry stop + 30% dynamic trailing stop) provided crash protection during the 2022 bear market, exiting before TQQQ's –81.7% drawdown. However, this is fundamentally a leveraged bet on Nasdaq 100 outperformance, not diversified alpha. If the Nasdaq 100 enters a prolonged bear market, this allocation could lose 60–70% before stops trigger; the 25% portfolio cap limits this to a 15–17% portfolio-level hit.

The Weekend Trend Trader follows Nick Radge's 20-week breakout system on the S&P Midcap 400, producing 22.9% CAGR since 1990 [^21^]. The multi-factor quant sleeve combines Piotroski F-Score with standardized unexpected earnings (SUE) momentum, a pairing that historically produced 23% annual outperformance [^279^].

**Mandatory risk management.** The aggressive portfolio requires three circuit breakers, without which it should not be deployed. First, a portfolio-level hard stop at 25% drawdown: if the total account declines 25% from its high-water mark, all strategies halt and the portfolio moves to 100% cash until the trader manually restarts. Second, VIX-based position scaling: reduce all position sizes by 50% when VIX closes above 30, and pause new entries when VIX exceeds 35. Volatility targeting of this form has been shown to improve Sharpe ratios by 15–50% [^281^] and would have significantly reduced losses during the March 2020 crash. Third, a strategy-level kill switch: any individual strategy that draws down 20% from its own equity curve is deactivated for 30 days. Hidden Markov Model regime filters demonstrated the capacity to cut max drawdown from 56% to 24% in backtests [^682^], and while HMMs require statistical expertise to implement, the VIX + hard stop combination approximates their protective effect.

**Automation approach.** This portfolio requires a fully automated stack: IBKR Pro API with `ib_insync` [^742^], hosted on an AWS t3.small instance ($15/month), with daily signal generation at 3:55 PM. The TQQQ MACD sleeve trades weekly but its stop-loss monitoring runs daily. A monitoring script checks portfolio heat, VIX levels, and drawdown every 15 minutes during market hours with SMS alerts for circuit breaker triggers. Total infrastructure cost: $30–50/month; commissions: $40–80/month [^724^].

### 8.4 Final Recommendations

The portfolio blueprints above represent endpoints, not starting points. Every trader should begin with paper trading for 3–6 months, running the complete strategy stack on a simulated account to verify signal generation, execution timing, and emotional response to drawdowns. The Quantopian study of 888 algorithms found that even rigorously backtested strategies commonly fail in live trading due to behavioral deviation from systematic rules [^279^]. Paper trading does not perfectly simulate slippage or emotional pressure, but it eliminates the costly mistake of discovering a strategy is mis-implemented after deploying real capital.

Start with one strategy. Chapter 7's automation roadmap outlined a four-phase progression from manual to fully automated; the conservative portfolio's Dual Momentum sleeve is the ideal starting point — a single, monthly-rebalanced strategy with 1.5 trades per year [^435^] that requires minimal infrastructure and teaches the discipline of following systematic rules. Only after 6+ months of profitable live performance should a trader add a second strategy. Adding all four components of the aggressive portfolio on day one virtually guarantees that execution errors, correlation surprises, and compound drawdowns will derail the system before it has time to work.

The honest bottom line: a dedicated retail systematic trader who follows the frameworks in this report — simple strategies with few parameters, strict risk management, tax-advantaged accounts, and patient compounding — can realistically target 1.5–2.0% monthly (19–27% annualized) over multi-year periods. This exceeds the historical S&P 500 return by approximately 5–10 percentage points annually, which represents genuine alpha. Strategies that promise 3% monthly (36% annually) sustained over decades either carry hidden risks that manifest catastrophically or rely on backtests that degrade 30–50% in live trading [^279^]. The 1.5–2.0% target is not exciting, but it is achievable, sustainable, and — when compounded in a tax-advantaged account over 10–20 years — transformative for a retail portfolio.
