# Automated Stock & ETF Trading Strategies: A Research-Based Guide to Systematic Long-Only Investing

## Executive Summary
### Key Findings
#### >3% monthly is an aspirational upper bound — realistic sustainable returns are 1.5-2.5% monthly after costs and degradation
#### Mean reversion strategies dominate risk-adjusted returns for long-only equity trading
#### Multi-strategy combination with volatility targeting is the institutional-grade approach for retail traders
#### Tax-advantaged accounts are non-negotiable for any strategy with >100% annual turnover
#### Minimum $50,000 capital required for meaningful multi-strategy automation

## 1. The Reality Check: Can 3% Monthly Be Achieved? (~2500 words, 2 tables, 1 chart)
### 1.1 The Math Behind the Target
#### 1.1.1 3% monthly compounds to ~42.6% annually — nearly 4x the S&P 500 historical average of ~10-11%
#### 1.1.2 After accounting for backtest-to-live degradation (30-50%), transaction costs (1-3%), taxes (2-8%), and strategy decay, a 36% backtest becomes 12-20% live
#### 1.1.3 Cost stack analysis: transaction fees, slippage, survivorship bias, overfitting haircut, tax drag (table: layer-by-layer degradation)
### 1.2 What the Research Actually Shows
#### 1.2.1 Only two strategy categories achieve 3%/month in verified backtests: TQQQ Weekly MACD (~36% CAGR) and concentrated mean reversion curve portfolios (34% CAGR)
#### 1.2.2 Both require extreme risk tolerance (30-70% max drawdown) and favorable market conditions
#### 1.2.3 No single long-only strategy has sustained >3% monthly over multi-decade periods with realistic costs (chart: strategy CAGR vs max drawdown scatter)
### 1.3 Setting Realistic Expectations
#### 1.3.1 Evidence-based monthly return targets by risk profile: conservative 0.8-1.2%, moderate 1.2-2.0%, aggressive 2.0-2.5%
#### 1.3.2 The critical distinction between backtested and live performance — why most traders fail to bridge the gap

## 2. Core Strategy Toolkit: Momentum (~3000 words, 2 tables)
### 2.1 Dual Momentum (Gary Antonacci GEM)
#### 2.1.1 Exact rules: 12-month absolute momentum (SPY vs T-bills) then relative momentum (US vs International), monthly rebalancing
#### 2.1.2 Backtested performance: 15.8-17.4% CAGR depending on period, max drawdown 17.8-22.7%, Sharpe 0.87-0.99
#### 2.1.3 Out-of-sample performance since 2014: ~12-15% CAGR, drawdown protection has held
#### 2.1.4 Why it works: absolute momentum eliminates the worst drawdowns by moving to cash during bear markets
### 2.2 Cross-Sectional Stock Momentum
#### 2.2.1 Jegadeesh-Titman foundation: rank stocks by 12-month returns (excluding most recent month), go long top decile
#### 2.2.2 Long-only implementation: ~0.7-1.0% monthly with significant transaction costs
#### 2.2.3 Risk-managed momentum (Barroso & Santa-Clara): volatility scaling nearly doubles Sharpe from 0.53 to 0.97
### 2.3 Sector & ETF Momentum
#### 2.3.1 Top-3 SPDR sector rotation: 13.3% CAGR (1928-2009), lower drawdown than buy-and-hold
#### 2.3.2 SACEMS (Simple Asset Class ETF Momentum): 9 ETF universe, 5-month lookback, monthly rebalance
#### 2.3.3 Logical Invest meta-strategy: combining momentum + mean reversion signals, 12.8% CAGR, 1.16 Sharpe
### 2.4 Earnings Momentum
#### 2.4.1 SUE (Standardized Unexpected Earnings) + earnings surprise + price momentum three-signal combo: 13.6-23.6% CAGR
#### 2.4.2 Critical limitation: extreme drawdowns (-63.9% in crises), data-intensive, high turnover

## 3. Core Strategy Toolkit: Mean Reversion (~3500 words, 3 tables, 1 chart)
### 3.1 RSI(2) Mean Reversion (Larry Connors)
#### 3.1.1 Exact rules: buy when RSI(2) < 5 (or < 10 for more signals), sell when RSI(2) > 50 or after N days, 200-day MA trend filter
#### 3.1.2 Backtested performance: 10.7% CAGR on QQQ, 71% win rate, 2.1 profit factor, only 18% time in market
#### 3.1.3 Key insight: Connors found stops hurt mean reversion — they get hit at exactly the wrong moment before snapback
#### 3.1.4 Trend filter impact: 200-day MA filter cuts CAGR from 8.7% to 7.1% but reduces max drawdown from 29% to 14%
### 3.2 IBS (Internal Bar Strength) Strategies
#### 3.2.1 Formula: (Close - Low) / (High - Low), single calculation that captures intraday positioning
#### 3.2.2 IBS + lower band on QQQ: 2.11 Sharpe ratio, 13.0% CAGR, 20.3% max drawdown vs 83% for buy-and-hold
#### 3.2.3 IBS + second indicator: 1.33% average gain per trade on QQQ, 75% win rate, 16.6% CAGR
### 3.3 The Mean Reversion Curve Portfolio
#### 3.3.1 Concept: combine 6 RSI(2) parameter portfolios with monthly Sharpe-optimized rebalancing
#### 3.3.2 Performance: 25.7% CAGR diversified (max 10 positions), 34% CAGR concentrated (max 4 positions)
#### 3.3.3 Why concentration works: fewer positions = higher per-position conviction = higher average returns (table: diversified vs concentrated metrics)
#### 3.3.4 Implementation: run simultaneously on QQQ, IWM, EEM, and sector ETFs for multi-instrument diversification
### 3.4 Other Mean Reversion Approaches
#### 3.4.1 Bollinger %B mean reversion: 8.2% CAGR, 75% win rate
#### 3.4.2 Stochastic oscillator mean reversion: 556 trades, 0.57% avg gain, profit factor 2.2
#### 3.4.3 Opening gap fade: 89% win rate but 0.19% average gain — limited scalability due to HFT competition
### 3.5 Mean Reversion Edge Decay
#### 3.5.1 Edges have weakened 30-50% since 2010 due to HFT proliferation
#### 3.5.2 The 1-5 day holding period remains the retail advantage zone — too long for HFTs, too short for institutions
#### 3.5.3 Why edges persist: behavioral biases (overreaction, herding) are rooted in human psychology, not arbitrageable by algorithms (chart: mean reversion performance by decade)

## 4. High-Octane Strategies: Approaching the 3% Target (~3000 words, 2 tables)
### 4.1 Leveraged ETF Strategies
#### 4.1.1 TQQQ Weekly MACD: exact rules from Lambros Petrou — QQQ weekly chart MACD signal to trade TQQQ, 40-week SMA filter, 2% exit buffer, +11,194% from Feb 2010-July 2025
#### 4.1.2 Hedgefundie Adventure (UPRO/TMF 55/45): quarterly rebalanced leveraged risk parity, 24.6% CAGR, -70.6% max drawdown
#### 4.1.3 LETF risk management: crash filters (20% single-day drop), VIX > 40 circuit breakers, max 40% drawdown exits
#### 4.1.4 Volatility decay: why 3x LETFs underperform 3x the index over multi-day holds — the mathematical drag (table: TQQQ vs 3x QQQ tracking error)
### 4.2 Concentrated Factor Approaches
#### 4.2.1 Piotroski F-Score: 9-point fundamental scoring system, 23% annual outperformance (1976-1996), easily screenable
#### 4.2.2 O'Shaughnessy Trending Value: Value Composite + 6-month momentum, 21.1% CAGR over 45 years, never had a 5-year loss
#### 4.2.3 Weekend Trend Trader (Nick Radge): 20-week high breakout + 40% trailing stop on S&P Midcap 400, 22.9% CAGR
### 4.3 Weekend Trend Trader Deep Dive
#### 4.3.1 Exact trading rules: 20-week high breakout, ROC > 30%, market index above 100-day MA, 40% trailing stop
#### 4.3.2 Position sizing: 20% risk per position, max 5 positions, 100% capital deployment
#### 4.3.3 Backtest results: 303 trades over 33 years, 44% win rate, 2.6:1 win/loss ratio — proof that low win rate can still produce high returns
### 4.4 The Honest Assessment of High-Octane Approaches
#### 4.4.1 All high-return strategies share common features: concentration, higher volatility, and regime dependence
#### 4.4.2 TQQQ MACD is really a leveraged bet on continued tech outperformance — not pure systematic alpha
#### 4.4.3 Risk-reward framework: none of these strategies are suitable as standalone core holdings for risk-averse investors

## 5. The Multi-Strategy Portfolio Framework (~3000 words, 2 tables, 1 chart)
### 5.1 Why Strategy Combination Works
#### 5.1.1 D.E. Shaw: inter-strategy correlations below 0.1 even during GFC — true diversification exists at the strategy level
#### 5.1.2 Key correlation pairs: momentum-mean reversion (-0.35), value-momentum (-0.46) — natural diversifiers
#### 5.1.3 DeMiguel (2009): equal-weighting (1/N) outperforms complex optimization for retail investors
### 5.2 A Practical Retail Multi-Strategy Portfolio
#### 5.2.1 Core allocation: 30% RSI(2) mean reversion on QQQ, 30% Dual Momentum, 20% IBS + lower band on IWM, 20% ATR Bands breakout on sector ETFs
#### 5.2.2 Volatility targeting: scale all positions by 50% when VIX > 30, resume full size when VIX < 20
#### 5.2.3 Expected performance: 15-20% CAGR, 15-20% max drawdown, Sharpe ~1.0-1.2 (table: strategy weights and expected contributions)
### 5.3 Regime Detection and Strategy Switching
#### 5.3.1 VIX regime indicator: mean reversion works better when VIX > 20; momentum works better in low-vol trending markets
#### 5.3.2 200-day moving average as trend filter: only take momentum trades when index is above 200-day MA
#### 5.3.3 ADX > 25 confirms trending conditions — switch from mean reversion to momentum when ADX rises above threshold
#### 5.3.4 HMM (Hidden Markov Model) regime filter reduced max drawdown from 56% to 24% in backtests (chart: regime-based allocation vs static allocation)
### 5.4 Tax-Efficient Strategy Placement
#### 5.4.1 Tax-advantaged accounts (IRA/401k): high-turnover strategies — mean reversion, ETF rotation, LETF
#### 5.4.2 Taxable accounts: low-turnover strategies — trend following with annual rebalancing, dual momentum
#### 5.4.3 Tax-loss harvesting adds 0.5-2% annually in taxable accounts — automate year-round, not just year-end

## 6. Risk Management & Position Sizing (~2500 words, 2 tables)
### 6.1 Position Sizing Methods
#### 6.1.1 Fixed fractional (1-2% risk per trade): the professional standard, auto-compounds, no edge estimates needed
#### 6.1.2 Kelly criterion: theoretically optimal but full Kelly produces 40-60% drawdowns — use quarter-Kelly or half-Kelly only
#### 6.1.3 Volatility targeting (Moreira & Muir): scale exposure inversely to realized vol, improves Sharpe 15-50%
### 6.2 Portfolio-Level Risk Controls
#### 6.2.1 Portfolio heat cap: max 8-10% of equity at risk across all open positions
#### 6.2.2 Drawdown ladders: at -5% reduce size 30%, at -10% halt new entries, at -15% move to cash
#### 6.2.3 Circuit breakers: daily (2%), weekly (4%), monthly (8%) loss limits; VIX > 40 full halt
### 6.3 Correlation and Concentration Limits
#### 6.3.1 Max 3 positions per sector; apply 1.5x heat multiplier to correlated clusters
#### 6.3.2 SPY-QQQ correlation of 0.93 provides almost no diversification — avoid holding both
#### 6.3.3 The "simplicity premium": strategies with ≤3 parameters outperform complex systems out-of-sample

## 7. Automation Platforms & Implementation (~2500 words, 1 table)
### 7.1 Platform Comparison
#### 7.1.1 Interactive Brokers: professional-grade API, $0.005/share, Portfolio Margin at $110K — best for serious automation
#### 7.1.2 Alpaca: commission-free API-first, Python-native, paper trading sandbox — best for beginners and testing
#### 7.1.3 QuantConnect: cloud-based LEAN engine, extensive data library — best for research and backtesting
#### 7.1.4 TradingView + webhooks: Pine Script strategies, visual backtesting — best for strategy development (table: platform comparison matrix)
### 7.2 Getting Started: A Step-by-Step Roadmap
#### 7.2.1 Phase 1 ($0-$5K): Paper trade 1 strategy on TradingView, validate rules, build confidence
#### 7.2.2 Phase 2 ($25K-$50K): Alpaca API with 1-2 strategies, commission-free, focus on ETFs
#### 7.2.3 Phase 3 ($50K-$100K): IBKR API with 3-4 strategies, add position sizing automation, begin tax-loss harvesting
#### 7.2.4 Phase 4 ($100K+): Portfolio Margin for 1.5-2x leverage, multi-strategy ensemble with regime detection
### 7.3 Data, Costs, and Infrastructure
#### 7.3.1 Minimum monthly costs: $0 (Alpaca) to $183 (QuantConnect Research + live node)
#### 7.3.2 Slippage reality: retail traders underestimate by 50-70% — budget $0.05/share for liquid stocks
#### 7.3.3 Security essentials: API key rotation every 90 days, IP whitelisting, 2FA, never hardcode credentials

## 8. Recommended Practical Portfolios (~2000 words, 3 tables)
### 8.1 Conservative Portfolio: "Steady Compound" ($50K minimum)
#### 8.1.1 Allocation: 50% Dual Momentum (SPY/EFA/AGG), 50% IBS + lower band on SPY
#### 8.1.2 Expected: 10-14% CAGR, 12-15% max drawdown, ~1.0% monthly average
#### 8.1.3 Automation: TradingView alerts → manual execution or simple webhook (table: monthly rebalancing checklist)
### 8.2 Moderate Portfolio: "Balanced Alpha" ($75K minimum)
#### 8.2.1 Allocation: 30% RSI(2) on QQQ, 30% Dual Momentum, 25% IBS + band on IWM, 15% sector momentum
#### 8.2.2 Expected: 15-18% CAGR, 18-22% max drawdown, ~1.3-1.5% monthly average
#### 8.2.3 Automation: IBKR API with Python, daily signal generation, end-of-day execution
### 8.3 Aggressive Portfolio: "Maximum Growth" ($100K minimum)
#### 8.3.1 Allocation: 25% Mean Reversion Curve (concentrated), 25% TQQQ MACD, 25% Weekend Trend Trader, 25% multi-factor quant
#### 8.3.2 Expected: 20-28% CAGR, 25-35% max drawdown, ~1.7-2.3% monthly average
#### 8.3.3 Risk management: mandatory circuit breakers, VIX-based position scaling, max 25% drawdown hard stop
### 8.4 Final Recommendations
#### 8.4.1 Start with paper trading for 3-6 months before deploying real capital
#### 8.4.2 Begin with 1 strategy, add others only after 6+ months of profitable live performance
#### 8.4.3 The honest bottom line: 1.5-2.0% monthly is an excellent, sustainable target for dedicated retail systematic traders

# References
## trading_strategies.agent.outline.md
- **Type**: Report outline
- **Description**: This outline file
- **Path**: /mnt/agents/output/trading_strategies.agent.outline.md

## Research Artifacts
- **Type**: Deep research outputs
- **Description**: 10 dimension files, cross-verification, insights, 6 wide exploration files
- **Path**: /mnt/agents/output/research/trading_strategies_*
