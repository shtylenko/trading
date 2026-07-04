# Cross-Verification Results: Automated Stock & ETF Trading Strategies

## Verification Date: 2026-06-23
## Dimensions Analyzed: 10 (Dim01-Dim10)
## Wide Exploration Files: 6 (Wide01-Wide06)

---

## HIGH CONFIDENCE FINDINGS (Confirmed by ≥2 agents from independent sources)

### HC-01: No Single Long-Only Strategy Consistently Achieves >3% Monthly
**Confirmed by:** Dim01, Dim02, Dim04, Dim05, Dim07, Dim10
**Finding:** Across all 10 research dimensions, no single long-only stock/ETF strategy has demonstrated sustained >3% monthly (36%+ CAGR) returns over multi-decade periods with verified backtests and realistic cost assumptions. The highest verified single-strategy returns are in the 25-34% CAGR range, and these come with significant drawdowns (28-70%).
**Sources:** Antonacci GEM backtests [^18^], Quantitativo mean reversion research [^62^], AQR factor data [^149^], QuantifiedStrategies extensive backtest library [^20^][^21^]

### HC-02: Mean Reversion Strategies Show Strongest Risk-Adjusted Returns for Stocks
**Confirmed by:** Dim02, Dim05, Dim06, Dim07
**Finding:** Mean reversion strategies (RSI-2, IBS, stochastic) consistently outperform trend-following and breakout strategies on stock indices and ETFs, with higher Sharpe ratios and win rates (68-78%). This aligns with the structural upward drift in equities — buying weakness in uptrends captures behavioral overreactions.
**Sources:** Larry Connors research [^19^], QuantifiedStrategies IBS backtests [^21^], Pagonidis academic study [^55^]

### HC-03: Dual Momentum (Antonacci GEM) Provides 12-17% CAGR with Moderate Drawdown
**Confirmed by:** Dim01, Dim03, Wide01
**Finding:** Gary Antonacci's Global Equity Momentum strategy has been independently verified across multiple time periods. Original backtest (1974-2013): 17.43% CAGR, -22.7% max drawdown. Out-of-sample since 2014: performance has been weaker (~12-15% CAGR) but drawdown protection has held. Absolute momentum (cash filter) is the key innovation that reduces drawdowns from -50% to ~-18%.
**Sources:** Antonacci original research [^18^], CXO Advisory live tracking [^117^], multiple replication studies

### HC-04: Leveraged ETF Strategies Can Achieve 3%/Month But With Extreme Risk
**Confirmed by:** Dim04, Wide03
**Finding:** TQQQ with Weekly MACD signals achieved ~36% CAGR (Feb 2010-July 2025). Hedgefundie UPRO/TMF 55/45 achieved 24.6% CAGR with -70.6% max drawdown. These are the ONLY strategies that demonstrably achieve the 3%/month target, but they require: (a) strong bull market in tech, (b) circuit breakers for crash protection, (c) tax-advantaged accounts, (d) high risk tolerance.
**Sources:** Lambros Petrou Weekly MACD research [^118^], Hedgefundie Bogleheads thread [^134^], SSRN academic paper on LETF strategies [^125^]

### HC-05: Transaction Costs Reduce Strategy Returns by 1.5-3% Annually
**Confirmed by:** Dim03, Dim08, Dim10, Wide06
**Finding:** Realistic round-trip costs (commissions + slippage + spread) for retail traders range from 5-60 bps per trade. For a strategy with monthly rebalancing, this translates to 1-2% annual drag. High-turnover strategies (>100% annually) face 2.5-4% cost drag.
**Sources:** J.P. Morgan momentum cost analysis [^168^], IBKR pricing [^244^], slippage estimates [^244^]

### HC-06: Backtest-to-Live Performance Gap is 30-50%
**Confirmed by:** Dim07, Dim10, Wide06
**Finding:** Strategies that show 30% CAGR in backtesting typically deliver 13-17% in live trading due to: overfitting (5% haircut), survivorship bias (1.5%), transaction costs (2%), slippage (1%), strategy decay (3%), and taxes (2-4%).
**Sources:** Quantopian study of 888 strategies [^279^], McLean & Pontiff strategy decay research, Harvey multiple testing framework

### HC-07: Strategy Decay After Publication is 43-58% Sharpe Reduction
**Confirmed by:** Dim01, Dim05, Dim10
**Finding:** Published strategies experience significant decay as more capital pursues the same edge. McLean & Pontiff (2016) found 58% out-of-sample decay. Decay accelerates at ~5 percentage points per year post-publication.
**Sources:** McLean & Pontiff (2016) [^279^], CFM publication decay study, Dimson et al. factor premium research

### HC-08: Multi-Strategy Combination Improves Risk-Adjusted Returns
**Confirmed by:** Dim07, Dim08, Wide06
**Finding:** Combining 3-5 uncorrelated strategies (momentum, mean reversion, factor-based) produces higher Sharpe ratios and smaller drawdowns than any single strategy. Value-Momentum correlation is -0.46; Momentum-Mean Reversion correlation is -0.35.
**Sources:** AQR multi-factor research [^146^], DeMiguel 1/N portfolio study [^661^], D.E. Shaw correlation data [^624^]

### HC-09: Volatility Targeting Improves Sharpe Ratios by 15-50%
**Confirmed by:** Dim01, Dim08, Wide06
**Finding:** Moreira & Muir (2017) demonstrated that scaling exposure inversely to realized volatility produces statistically significant improvements. Man Group case study showed 500bps+ enhancement. Effect is strongest for momentum strategies.
**Sources:** Moreira & Muir (2017) Journal of Finance [^281^], Man Group research [^237^], Bongaerts conditional vol targeting [^288^]

### HC-10: Retail Automation Infrastructure is Mature and Accessible
**Confirmed by:** Dim09, Wide06
**Finding:** Multiple viable platforms exist: Interactive Brokers (professional, $0.005/share), Alpaca (commission-free API), QuantConnect (cloud backtesting), TradingView (webhook automation). Minimum viable capital: $25,000 (PDT rule). Realistic minimum: $50,000-$100,000.
**Sources:** IBKR API docs [^265^], Alpaca API docs [^246^], QuantConnect pricing [^245^], TradingView webhook guides [^239^]

---

## MEDIUM CONFIDENCE FINDINGS (Single authoritative source)

### MC-01: Mean Reversion Curve Portfolio Achieves 25.7-34% CAGR
**Source:** Dim02, Dim07 (both citing Quantitativo)
**Finding:** A portfolio combining 6 RSI(2) parameter sets with monthly Sharpe-optimized rebalancing achieved 25.7% CAGR (diversified) to 34% CAGR (concentrated, max 4 positions) since 2010. Max drawdown: 28-35%.
**Caveat:** Single research source (Quantitativo). Has not been independently replicated. Mean reversion edges have weakened 30-50% since 2010. Live performance likely 12-17% after degradation.

### MC-02: Piotroski F-Score Achieved 23% Annual Outperformance (1976-1996)
**Source:** Dim05 (Joseph Piotroski, Stanford)
**Finding:** High F-Score companies (8-9) outperformed low F-Score (0-1) by 23% annually. More recent performance is lower but F-Score remains one of the most robust single factors.
**Caveat:** Original study period only. Recent performance: ~5-10% outperformance. Requires annual rebalancing in small-cap value universe.

### MC-03: Earnings Momentum (SUE) Achieves 13.6-23.6% CAGR
**Source:** Dim01, Dim05 (Chan/Jegadeesh/Lakonishok 1996)
**Finding:** Combined SUE + earnings surprise + price momentum produced 13.6-23.6% CAGR depending on specification. Three-signal combo most robust.
**Caveat:** Extreme drawdowns (-63.9% in crises). Data intensive (requires earnings surprise data). High turnover.

### MC-04: Weekend Trend Trader Achieves 16-23% CAGR
**Source:** Dim01 (Nick Radge/QuantifiedStrategies)
**Finding:** 20-week breakout system on S&P Midcap 400 produced 22.9% CAGR (1990-present) with 58% max drawdown. S&P 500 version: 16.6% CAGR.
**Caveat:** Requires weekly manual screening (though rules are clear). Drawdown of 58% may be too high for most investors.

### MC-05: O'Shaughnessy Trending Value Achieved 21.1% CAGR (1964-2009)
**Source:** Dim05 (What Works on Wall Street)
**Finding:** Value Composite + 6-month momentum, rebalanced annually. Never had a 5-year losing period over 45 years.
**Caveat:** Requires annual rebalancing. Recent performance (2010-2025) has been lower due to value factor underperformance.

---

## LOW CONFIDENCE FINDINGS (Weak sourcing or unverified claims)

### LC-01: XGBoost ML-Enhanced Factor Strategy Claimed 61% in 7 Months
**Source:** Dim05 (single Chinese market study)
**Finding:** XGBoost multi-factor approach claimed 61% returns in 7 months on CSI 300.
**Caveat:** Extremely short track record. Almost certainly overfitted. No out-of-sample validation.

### LC-02: Enhanced ORB Achieved 433% in One Year
**Source:** Dim06 (single academic paper)
**Finding:** Enhanced Opening Range Breakout on Nasdaq futures achieved 433% in one year.
**Caveat:** Single year. Futures (not stocks). Likely overfitted to specific market conditions.

---

## CONFLICT ZONES (Active disagreements between sources)

### CZ-01: Can 3%/Month Be Achieved Long-Term?
**YES camp:** Dim04 (TQQQ MACD ~36% CAGR), Dim02 (MR Curve 34% CAGR concentrated)
**NO camp:** Dim10 (realistic retail: 5-25% annually), Dim07 (12-17% live after degradation)
**Resolution:** The 3%/month target IS achievable in backtests with specific strategies (TQQQ MACD, concentrated mean reversion portfolios). However, after accounting for backtest degradation (30-50%), strategy decay, taxes, and realistic costs, sustainable live returns for retail traders are likely 1.5-2.5% monthly (18-30% annualized) in favorable conditions. The 3% target should be treated as an aspirational upper bound, not a baseline expectation.

### CZ-02: Do Stop Losses Help or Hurt Systematic Strategies?
**HELP camp:** Wide05 (Dim06 context) — stops reduce catastrophic losses
**HURT camp:** Dim02 (Connors research) — stops get hit at exactly the wrong moment before snapback
**Resolution:** Tight stops (<5%) consistently hurt mean reversion strategies. Wide stops (>7% or ATR-based) can help trend-following strategies. No universal rule — depends on strategy type. For the strategies most relevant to this research (mean reversion), stops generally hurt returns.

### CZ-03: Does Volatility Targeting Always Improve Returns?
**YES camp:** Dim08 (Moreira & Muir 2017, Man Group) — 15-50% Sharpe improvement
**NO camp:** Dim08 (one quant trader) — fixed vol targeting reduced Sharpe from 0.93 to 0.64
**Resolution:** Volatility targeting works best for: (a) momentum strategies, (b) when conditional on forecast strength, (c) during high-vol regimes. It can hurt returns for: (a) mean reversion strategies, (b) when applied mechanically without forecast conditioning. The benefit is regime-dependent.

### CZ-04: Is Factor Investing Still Viable After the "Lost Decade"?
**YES camp:** Dim05 (DFA live fund data shows 2.6pp average outperformance), Dim05 (value spreads have widened)
**NO camp:** Dim05 (Fama-French HML and SMB negative 2010-2019), Wide04 (Allan Roth claimed factor investing "failed miserably")
**Resolution:** Factor investing has experienced prolonged underperformance periods (3-5+ years). However, live fund data from Dimensional shows persistent outperformance net of fees. Quality/profitability has been most consistent. Value has shown signs of recovery since late 2020. Factor investing requires 10+ year horizon.

---

## SUMMARY: STRATEGIES RANKED BY REALISTIC MONTHLY RETURN EXPECTATION

| Rank | Strategy | Backtest CAGR | Realistic Live Monthly | Risk Level |
|------|----------|--------------|----------------------|------------|
| 1 | TQQQ Weekly MACD | ~36% | 1.5-2.5% | EXTREME |
| 2 | Mean Reversion Curve (concentrated) | 34% | 1.4-2.0% | HIGH |
| 3 | Hedgefundie UPRO/TMF | 24.6% | 1.2-1.8% | EXTREME |
| 4 | Mean Reversion Curve (diversified) | 25.7% | 1.3-1.9% | HIGH |
| 5 | Weekend Trend Trader | 22.9% | 1.2-1.7% | HIGH |
| 6 | Trending Value (O'Shaughnessy) | 21.1% | 1.0-1.5% | MEDIUM |
| 7 | IBS + Multi-Indicator | 24% | 1.0-1.5% | MEDIUM-HIGH |
| 8 | ATR Bands Breakout | 12.5% | 0.8-1.1% | MEDIUM |
| 9 | Dual Momentum GEM | 12-17% | 0.8-1.2% | LOW-MEDIUM |
| 10 | RSI(2) Mean Reversion | 10.7% | 0.6-0.9% | LOW-MEDIUM |
| 11 | ETF Sector Rotation | 13% | 0.8-1.1% | MEDIUM |
| 12 | Piotroski F-Score | 10-15% | 0.7-1.1% | MEDIUM |

**Bottom Line:** The 3% monthly target is achievable only with: (a) concentrated high-risk strategies (TQQQ, concentrated mean reversion), (b) favorable market conditions, (c) exceptional execution, and (d) acceptance of 30-50% drawdowns. A realistic sustainable target for retail traders is 1-2% monthly with proper risk management.
