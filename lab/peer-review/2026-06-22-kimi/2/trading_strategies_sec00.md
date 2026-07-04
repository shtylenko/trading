## Executive Summary

This report examines whether automated long-only stock and ETF trading strategies can deliver sustained monthly returns above 3%. Across ten research dimensions and cross-verification from academic journals to live fund data, the conclusion is uniform: **>3% monthly is an aspirational upper bound, not a sustainable baseline**. After accounting for transaction costs, taxes, strategy decay, and backtest-to-live degradation, realistic returns fall in the 1.5–2.5% monthly range (18–30% annualized) for well-constructed multi-strategy portfolios [^279^][^792^].

### Key Findings

**Realistic returns are 1.5–2.5% monthly after all costs.** Backtests overstate live performance by 30–50% [^279^]. Published strategies experience 43–58% Sharpe ratio decay post-publication as more capital competes for the same edge [^792^][^794^]. Transaction costs (commissions, slippage, spreads) extract 1.5–3% annually for high-turnover strategies [^168^]. Short-term capital gains tax at ordinary income rates (up to 40.8% federal including NIIT) can consume a third of gross profits for taxable accounts [^786^]. Only two long-only strategies demonstrate >3% monthly in backtests — TQQQ Weekly MACD at ~36% CAGR and a concentrated mean reversion curve at ~34% CAGR — both carry extreme drawdown risk (28–70%) and depend on specific market regimes [^118^][^62^].

**Mean reversion strategies dominate risk-adjusted returns for long-only equity trading.** RSI(2) mean reversion on QQQ achieves a 71% win rate with 10.7% CAGR [^403^]. IBS (Internal Bar Strength) combined with a lower Bollinger Band produces a 2.11 Sharpe ratio and 13.0% CAGR with only 20.3% maximum drawdown [^358^]. These strategies exploit the structural upward drift in equities combined with behavioral overreactions that resolve over 1–5 day holding periods — a timeframe too long for high-frequency traders yet too short for slow-moving institutional capital [^55^]. Mean reversion edges have weakened 30–50% since 2010 as HFT compressed resolution times, but the alpha persists in range-bound and elevated-volatility regimes [^21^].

**Multi-strategy combination with volatility targeting is the institutional-grade approach for retail traders.** Combining 3–5 uncorrelated strategies produces higher risk-adjusted returns than any single strategy. Momentum and mean reversion exhibit approximately -35% correlation, making them natural diversifiers [^146^]. Institutional multi-strategy funds (AQR, D.E. Shaw) maintain inter-strategy correlations below 0.1, with 73% of individual segments underperforming the combined portfolio [^624^]. Volatility targeting — scaling exposure inversely to realized volatility — improves Sharpe ratios by 15–50% [^281^]. A practical retail implementation allocates across mean reversion, dual momentum, factor-based, and breakout strategies with equal weighting and monthly rebalancing, targeting 15–20% CAGR with 15–20% maximum drawdown.

**Tax-advantaged accounts are non-negotiable for any strategy with >100% annual turnover.** A strategy showing 25% CAGR in backtesting becomes 15–18% after taxes for high-bracket investors in taxable accounts — effectively erasing the edge over buy-and-hold [^786^]. Tax-advantaged accounts (IRA, 401k, HSA) retain the full pre-tax return. Strategy selection should be tiered by account type: high-turnover mean reversion and ETF rotation in tax-advantaged accounts; low-turnover trend following with annual rebalancing in taxable accounts [^829^].

**Minimum $50,000 capital is required for meaningful multi-strategy automation.** Professional risk management demands 1–2% risk per trade; at $50,000 this provides $500–$1,000 risk capital per trade — sufficient for meaningful position sizes in liquid stocks and ETFs [^696^]. Dividing $50,000 across 4 strategies yields $12,500 per strategy, or approximately $2,500 per position when holding 5 positions — the minimum where slippage does not dominate returns [^791^]. Portfolio Margin (for modest 1.5–2x leverage) requires $110,000 minimum [^244^].

### Three Portfolio Options

| Metric | Conservative | Moderate | Aggressive |
|--------|:---:|:---:|:---:|
| Monthly Return Target | ~1.0% | ~1.3–1.5% | ~1.7–2.3% |
| Annualized Return (Est.) | 12–15% | 18–22% | 22–30% |
| Max Drawdown (Est.) | 10–15% | 15–20% | 25–35% |
| Capital Required | $25,000 | $50,000 | $75,000+ |
| Strategy Count | 1–2 | 3–4 | 4–6 |
| Primary Strategies | Dual Momentum GEM [^18^] | RSI(2) MR [^403^], IBS+Band [^358^], Dual Momentum | MR Curve [^62^], ATR Breakout, Sector Rotation, Concentrated MR |
| Turnover | ~50–100%/yr | ~150–300%/yr | ~300–500%/yr |
| Account Type | Taxable OK | Tax-advantaged required | Tax-advantaged essential |
| Volatility Targeting | No | Yes | Yes + circuit breakers |
| Leverage | None | None | 1.5–2x (Portfolio Margin) |

The Conservative portfolio centers on Gary Antonacci's Global Equities Momentum (GEM), which historically delivered 12–17% CAGR with -22.7% maximum drawdown [^18^]. GEM's absolute momentum filter — the cash-equivalent exit rule — limits drawdowns during bear markets. Low turnover makes this suitable for taxable accounts.

The Moderate portfolio represents the optimal risk-adjusted choice for most retail traders. It combines three to four uncorrelated long-only strategies — mean reversion on major ETFs, dual momentum for trend exposure, and volatility-scaled position sizing — within a tax-advantaged account. The negative correlation between momentum and mean reversion provides genuine diversification that persists during market stress [^146^].

The Aggressive portfolio pushes toward the 2% monthly ceiling by concentrating in the highest-Sharpe mean reversion setups, adding modest leverage via Portfolio Margin, and employing portfolio-level circuit breakers (halt trading at 15% drawdown). This demands disciplined automation and acceptance of 25–35% drawdowns during adverse regimes. It is appropriate only for traders with $75,000+ capital and high risk tolerance.
