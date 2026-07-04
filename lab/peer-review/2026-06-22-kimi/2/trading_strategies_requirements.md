# Requirements Analysis: Automated Stock & ETF Trading Strategies

## Explicit Requirements

[P1] **Asset Class Restriction: Stocks & ETFs Only**  
Only strategies involving stocks and exchange-traded funds (ETFs) are acceptable. No other asset classes may be included.

[P1] **Strategy Automation**  
The trading strategies must be fully automated -- capable of running without manual intervention for trade execution, signal generation, or order placement.

[P1] **No Futures Trading**  
Strategies must not involve futures contracts or futures-based instruments under any circumstances.

[P1] **No Short Selling**  
All strategies must be long-only. No short positions, inverse ETFs used for bearish bets, or any mechanism profiting from price declines.

[P1] **No Options Trading**  
Strategies must not incorporate options (calls, puts, spreads, or any options-based structures).

[P1] **Monthly Profitability Threshold: >3%**  
Every strategy must demonstrate a historical or backtested monthly return exceeding 3%. This translates to approximately 42.6% annualized (compounded), setting an extremely high performance bar.

[P1] **Reliability**  
Strategies must produce consistent, dependable results with low variance in monthly performance.

[P1] **Repeatability**  
Strategies must be replicable across different time periods and market conditions, not dependent on one-time anomalies or lucky streaks.

## Implicit Requirements

[P2] **Risk Management Framework**  
Given the aggressive 3%+ monthly return target, the user likely needs clear risk management rules including stop-loss levels, position sizing methodology, maximum drawdown limits, and portfolio-level risk controls to protect capital during losing streaks.

[P2] **Verified Backtesting Results**  
Any claim of reliability and profitability requires statistically significant backtesting across multiple market regimes (bull, bear, sideways) with out-of-sample validation.

[P2] **Automation Platform Specification**  
The user needs to know which platforms or tools can execute these strategies (e.g., Interactive Brokers, Alpaca, TradingView, custom Python scripts, QuantConnect) with implementation details.

[P2] **Capital Requirements**  
The minimum account size necessary to implement strategies while maintaining proper diversification and risk management is essential for feasibility assessment.

[P2] **Drawdown Tolerance & Recovery Metrics**  
Maximum expected drawdown and average recovery time must be defined. A 3%/month strategy likely involves significant drawdowns that the user needs to be prepared for.

[P2] **Holding Period Classification**  
Whether strategies are day trading, swing trading (days to weeks), or longer-term position trading affects suitability, time commitment, and tax treatment.

[P2] **Market Condition Dependency**  
Which market environments the strategies perform in and which they fail in, with clear identification of when to deploy vs. when to stay in cash.

[P2] **Transaction Cost Accounting**  
Net returns after commissions, slippage, bid-ask spreads, and potential fees -- especially critical for high-frequency strategies targeting modest per-trade gains.

[P2] **Tax Efficiency Considerations**  
For retail investors, the holding period (short-term vs. long-term capital gains) significantly impacts after-tax returns. Strategies should address tax implications.

[P2] **Rebalancing & Maintenance Schedule**  
How often strategies require review, parameter adjustment, or rebalancing. True automation should minimize this but some oversight is always necessary.

[P2] **Implementation Complexity Assessment**  
Whether strategies require coding skills, specific software, or can be implemented through no-code platforms. This determines accessibility for the user.

[P2] **Out-of-Sample & Forward-Tested Validation**  
Backtesting alone is insufficient. Evidence of live or paper trading results adds credibility beyond optimized historical performance.

[P2] **Correlation & Diversification Profile**  
How the strategies correlate with broad market indices and with each other. A portfolio of uncorrelated strategies provides smoother equity curves.

## Priority Matrix

| Priority | Requirement |
|----------|-------------|
| P0 (Must-Have) | Stocks & ETFs only (no futures, options, or shorting) |
| P0 (Must-Have) | Fully automated execution |
| P0 (Must-Have) | Monthly profitability exceeding 3% |
| P0 (Must-Have) | Demonstrated reliability and repeatability |
| P1 (Critical) | Risk management with defined stop-losses and position sizing |
| P1 (Critical) | Verified backtesting across multiple market regimes |
| P1 (Critical) | Net returns after transaction costs (commissions, slippage) |
| P1 (Critical) | Maximum drawdown and recovery time metrics |
| P1 (Critical) | Minimum capital requirements |
| P2 (Important) | Automation platform recommendations |
| P2 (Important) | Market condition suitability analysis |
| P2 (Important) | Holding period and tax implications |
| P2 (Important) | Implementation complexity and skill requirements |
| P2 (Important) | Rebalancing and maintenance frequency |
| P2 (Important) | Out-of-sample or live trading validation |
| P2 (Important) | Strategy correlation and portfolio construction guidance |
| P3 (Nice-to-Have) | Source code or pseudocode for strategies |
| P3 (Nice-to-Have) | Paper trading setup instructions |
| P3 (Nice-to-Have) | Regulatory compliance notes (pattern day trading rules) |

## Success Criteria

1. **Profitability Gate**: Every presented strategy must show historical or backtested average monthly returns above 3% on a risk-adjusted basis (Sharpe ratio > 1.0 preferred).
2. **Constraint Adherence Zero-Tolerance**: No strategy may include futures, short positions, or options. Any violation invalidates the deliverable.
3. **Automation Verifiability**: Each strategy must include a clear automation path -- either platform-specific implementation instructions or programmable logic.
4. **Multi-Regime Backtesting**: Backtests must cover minimum 5 years spanning at least one major market correction (e.g., 2020 COVID crash, 2022 bear market).
5. **Risk Transparency**: Maximum drawdown, worst month, and consecutive losing month count must be explicitly disclosed for each strategy.
6. **Net Return Clarity**: All performance figures must be net of estimated transaction costs (commissions + slippage).
7. **Repeatability Evidence**: Strategies must show consistent performance across non-overlapping time periods, not cherry-picked intervals.
8. **Practical Feasibility**: Capital requirements must be realistic for a retail investor (sub-$100K ideally documented).
9. **No Overfitting Indicators**: Excessive parameter optimization red flags (perfect equity curves, unrealistic win rates >80% without context) must be avoided.
10. **Actionable Deliverable**: The user must be able to act on the report -- vague conceptual strategies without implementation detail do not meet requirements.

## Target Audience Profile

**Likely Profile**: A retail investor with moderate trading knowledge seeking passive/semi-passive income through systematic strategies. The specificity of constraints (3% monthly, no derivatives) suggests someone who has researched enough to form opinions about risk instruments but wants to stay within cash equity markets. The expectation of 3%+ monthly returns (42%+ annualized) indicates either an inexperienced investor with unrealistic expectations or a sophisticated one seeking aggressive alpha strategies with full awareness of associated risks. The "reliable and repeatable" language suggests preference for systematic/rule-based approaches over discretionary trading. Likely uses or is willing to learn retail-friendly automation platforms (TradingView, broker APIs, or third-party execution services). The exclusion of shorting, futures, and options points to either risk aversion toward leveraged instruments or regulatory/account limitations (e.g., non-margin account).
