## 6. Risk Management & Position Sizing

Position sizing decisions explain more of the variance in trader outcomes than entry or exit timing [^696^]. A trader with a mediocre edge and impeccable risk control will survive and compound; a trader with a brilliant edge and poor sizing will eventually suffer a catastrophic drawdown. The preceding chapters established that individual strategies — from the Mean Reversion Curve Portfolio at 25.7–34% CAGR [^62^] to the Weekend Trend Trader at 19.9% on the S&P 500 — can deliver attractive returns in backtests. This chapter provides the risk management framework that determines whether those backtested returns survive contact with live markets.

The framework below is designed for retail implementation: no proprietary data feeds, no PhD-level mathematics, and no leverage beyond what a standard margin account provides. Every rule is expressible as a simple calculation or conditional statement suitable for automation.

### 6.1 Position Sizing Methods

#### 6.1.1 Fixed Fractional: The Professional Standard

Fixed fractional position sizing risks a constant percentage of account equity on each trade, regardless of the specific setup. The formula is straightforward:

$$\text{Position Size} = \frac{\text{Account Value} \times \text{Risk \%}}{\text{Entry Price} - \text{Stop Price}}$$

This method is the most widely adopted professional approach for three reasons [^677^][^678^]. First, it auto-compounds: position sizes grow naturally as the account appreciates and shrink during drawdowns, mechanically enforcing the dictum to "let winners run and cut losers short." Second, it requires no estimate of strategy edge — unlike the Kelly criterion, fixed fractional needs only a risk percentage and a stop distance. Third, it is psychologically tractable: the trader knows in advance exactly what each trade can cost, eliminating the emotional position-sizing decisions that derail discretionary traders.

The standard risk band for long-only stock and ETF strategies is **1–2% of equity per trade**. At 1%, a $100,000 account risks $1,000 per position; at 2%, $2,000. Monte Carlo simulations by Vince (1992) demonstrate the trade-off clearly: over 100 trades from a $10,000 starting balance, fixed fractional at 2% produced an expected 32% return with ~11% maximum drawdown, while the same approach at 0.5% returned only ~16% with ~6% drawdown [^691^]. The 2% level captures meaningful compounding without exposing the account to recovery-threatening losses.

| Method | Expected Return (100 trades) | Max Drawdown | Sharpe (est.) | Edge Estimate Required | Best For |
|:---|:---:|:---:|:---:|:---:|:---|
| Fixed Fractional 0.5% | ~16% [^691^] | ~6% | Medium | No | Large accounts; risk-averse traders |
| Fixed Fractional 1.0% | ~24% [^691^] | ~8% | Medium-High | No | Proven systems with 300+ trades |
| Fixed Fractional 2.0% | ~32% [^691^] | ~11% | High | No | **Default recommendation** for retail |
| Quarter-Kelly | ~45% [^691^] | ~18% | Medium | Yes (win rate, payoff ratio) | Experienced traders with stable stats |
| Half-Kelly | ~74% [^691^] | ~22% | Low-Medium | Yes | Aggressive growth seekers |
| Full Kelly | ~121% [^691^] | ~38% | Very Low | Yes (precise) | Theoretical only |

The comparison reveals why fixed fractional at 1–2% is the default recommendation. Quarter-Kelly and half-Kelly offer higher expected returns but require accurate, stable estimates of win rate and payoff ratio — estimates that are rarely available to retail traders with limited trade history. Overestimating edge while using Kelly produces "catastrophic outcomes" [^691^]; when one trader's assumed win rate dropped from 64% to 52%, their half-Kelly positions generated a 23% drawdown [^691^]. Fixed fractional eliminates this estimation risk entirely.

![Position Sizing Methods: Return-Drawdown Trade-off](fig_position_sizing_tradeoff.png)

The scatter plot above places each method in return-drawdown space. The "Recommended Zone" — return above 15% with drawdown below 15% — contains only fixed fractional variants. Kelly-based methods sit in the "Danger Zone" where drawdowns exceed 25%, requiring recovery gains of 33% or more just to return to breakeven.

#### 6.1.2 Kelly Criterion: Theoretically Optimal, Practically Dangerous

The Kelly criterion, derived by J.L. Kelly (1956) and popularized by Ed Thorp, computes the optimal fraction of capital to risk as:

$$K\% = W - \frac{1 - W}{R}$$

where $W$ is the win rate and $R$ is the average win-to-loss ratio. For a strategy with 55% win rate and 1.5:1 payoff ratio, full Kelly allocates 25% of capital to each trade — a level that produces maximum drawdowns of 40–60% even with positive-expectancy strategies [^276^][^691^]. Gehm (1983), publishing in the *Journal of Futures Markets*, documented that full Kelly betting routinely generates drawdowns exceeding 50% while the trader remains "technically optimal" [^691^].

The practical solution, nearly universal among professionals, is **fractional Kelly**: quarter-Kelly or half-Kelly [^282^]. Thorp (2008) recommends this approach because it "captures most of the growth benefits while dramatically reducing drawdown risk" [^691^]. MacLean, Ziemba & Blazenko (1992) confirmed that half-Kelly drawdowns approximate 75% of full Kelly levels, while quarter-Kelly reaches roughly 50% [^691^].

A retail implementation should follow four rules: (1) calculate full Kelly from rolling 6-month performance statistics, not backtest projections; (2) use 25–33% of the Kelly suggestion; (3) never exceed 5% risk per trade regardless of Kelly output; and (4) if drawdown exceeds 15%, automatically revert to fixed fractional at 2% until the account recovers to a new equity high [^691^].

#### 6.1.3 Volatility Targeting: Scaling to Market Conditions

Moreira & Muir (2017) demonstrated that scaling portfolio exposure inversely to realized volatility produces statistically significant improvements in risk-adjusted returns [^233^]. The core insight is that changes in volatility are not offset by proportional changes in expected returns — high-volatility periods offer worse risk-adjusted opportunities, so exposure should be reduced [^233^].

The implementation formula is simple:

$$\text{Position Scale} = \frac{\text{Target Volatility}}{\text{Realized Volatility}}$$

For a 10% annualized volatility target, if the S&P 500's 20-day realized volatility is 20%, position sizes are halved. If realized volatility drops to 8%, positions scale to 125% of baseline (with leverage capped at 2x) [^287^][^705^].

Documented improvements are substantial. Man Group research across 60+ assets from 1926 onward found Sharpe ratio enhancements of 15–50% for equity and credit strategies [^237^][^670^]. Bongaerts, Kang & van Dijk (2020) found that conditional volatility targeting — scaling only during high-volatility regimes — improved momentum strategy Sharpe by 0.23 and reduced maximum drawdown by 20.1% (from 54.1% to 34.0%) [^705^]. Nucera & Uhl (2022), publishing in the *Journal of Asset Management*, reported that volatility-scaled factor portfolios delivered 7.5% returns versus 5.1% for buy-and-hold, with Sharpe improving from 0.65 to 0.90 [^695^].

Critical counter-evidence comes from Cederburg et al. (2020) in the *Journal of Financial Economics*. Across 103 equity strategies, volatility-managed portfolios outperformed unmanaged versions in only 53 of 103 cases, and out-of-sample versions "generally earn lower certainty equivalent returns and Sharpe ratios" [^672^][^717^]. The benefits are concentrated in momentum, profitability, and betting-against-beta strategies; mean-reversion strategies show little improvement from volatility scaling [^723^]. Retail traders should apply volatility targeting selectively — primarily to momentum and trend-following allocations — rather than as a blanket portfolio overlay.

### 6.2 Portfolio-Level Risk Controls

#### 6.2.1 Portfolio Heat Cap

Portfolio heat is the total maximum loss across all open positions if every trade simultaneously hits its stop. It is the single most important risk metric for multi-position portfolios [^700^][^697^]:

$$\text{Portfolio Heat (\%)} = \frac{\sum [(\text{Entry Price} - \text{Stop Price}) \times \text{Shares}]}{\text{Account Equity}} \times 100$$

The professional ceiling is **8–10% of equity** at risk across all open positions. The original Turtle Traders, operating one of the most famous systematic trading programs in history, capped portfolio heat at 10–12 units with each unit risking ~1% of equity per adverse ATR (Average True Range) move [^700^][^709^]. Despite these controls, the Turtles still experienced 30–40% portfolio drawdowns in practice — evidence that heat caps limit but do not eliminate drawdown risk [^700^].

![Drawdown Recovery Math](fig_drawdown_recovery.png)

The asymmetric recovery function illustrates why heat control is non-negotiable. A 10% drawdown requires only 11.1% to recover; a 25% drawdown requires 33.3%; a 50% drawdown demands a 100% gain [^678^]. The curve accelerates exponentially — each additional percentage point of loss demands a disproportionately larger gain. The portfolio heat cap exists to keep the account on the left side of this chart where recovery remains achievable within months rather than years.

#### 6.2.2 Drawdown Ladders: Graduated Response

A drawdown ladder is a pre-committed, rules-based protocol that progressively reduces exposure as losses accumulate. The framework transforms drawdown from "an emotional problem into an engineering problem" [^698^]:

| Drawdown Level | Position Size Change | New Entries | Action |
|:---:|:---:|:---:|:---|
| -5% | Reduce to 70% of base | Allowed | Decrease per-trade risk to 70% of normal; tighten selection criteria |
| -8% | Reduce to 50% of base | Restricted | Only highest-conviction setups; no correlated additions |
| -10% | Halt new entries | **Stopped** | Close weakest 50% of open positions; review all active strategies |
| -15% | Move to cash | **Stopped** | Liquidate to cash or short-term Treasuries; mandatory strategy review period |
| -20% | Full halt | **Stopped** | Complete trading cessation; minimum 1-week cooling-off; reassess edge validity [^680^] |

The ladder operates on two principles. First, it never increases size during a drawdown — attempting to "trade your way out" with larger positions is the most common path to account destruction [^680^]. Second, size increases only after the account reaches a new equity high (5–10% above the previous peak), ensuring that confidence is earned through performance, not assumed during recovery [^680^].

An alternative formulation scales risk continuously rather than in discrete steps:

$$\text{New Risk \%} = \text{Base Risk \%} \times \frac{\text{Current Equity}}{\text{Peak Equity}}$$

With base risk at 1% and equity dropping from $55,000 to $50,000 (9.1% drawdown), the new risk per trade becomes 0.91% — a modest reduction that compounds protection across all positions without requiring manual intervention [^680^].

The drawdown ladder connects directly to the portfolio heat cap. A trader with 6 open positions at 1.5% heat each has 9% total heat — already at the acceptable ceiling. If drawdown reaches 5%, reducing position sizes to 70% drops heat to 6.3%, creating breathing room. At 10% drawdown with no new entries, heat naturally declines as positions close, forcing the portfolio into a defensive posture precisely when the trader's psychological impulse is to trade more aggressively.

#### 6.2.3 Circuit Breakers: Automatic Trading Halts

Circuit breakers are automatic trading stops triggered by predefined risk thresholds. They operate at multiple time horizons:

**Equity-based halts.** The daily loss limit is 2% of account equity; if hit, no new positions for the remainder of the day. The weekly limit is 4%; if breached, no new entries for the rest of the week with mandatory review of all open positions. The maximum drawdown limit is 10% from peak equity, triggering a halt of all trading and a mandatory strategy review period [^698^].

**Market condition halts.** When the VIX exceeds 40 — indicating extreme fear and dislocation — all new entries halt and existing position sizes reduce by 50% [^698^]. The China Financial Futures Exchange (CFFEX) implemented similar circuit breakers in 2015 at 5% and 7% index move thresholds, demonstrating that even regulatory bodies treat volatility spikes as systematic risk events requiring mandatory cooling-off periods [^706^].

**Strategy performance halts.** A consecutive loss limit of 5 losing trades triggers a 24-hour pause and signal generation review. If 30-day win rate drops below 30%, the strategy allocation reduces to 50% pending performance review [^698^][^680^].

A proper kill-switch system does three things: monitors equity and limits continuously, detects hostile conditions (spread spikes, volatility regimes, correlation breakdowns), and forces a freeze with no exceptions [^698^]. The key principle: the circuit breaker stops trading *before* the rule violation becomes catastrophic, not after the damage is done.

### 6.3 Correlation and Concentration Limits

#### 6.3.1 Sector and Cluster Limits

Correlation is the silent killer of risk management. A portfolio with ten positions at 2% risk each appears to have 20% heat — but if those positions are correlated at 0.85, a single sector event can trigger near-simultaneous losses across most holdings [^697^][^700^].

The Turtle Traders addressed this with a three-tier limit system: maximum 4 units per single market, 6 units per correlated sector, and 10–12 units across the entire portfolio [^709^][^700^]. For equity portfolios, this translates to practical rules: no more than 3 positions from any single sector; apply a 1.5x heat multiplier to positions within correlated clusters (e.g., large-cap tech); and maximum 2 positions from any sub-cluster with pairwise correlation exceeding 0.85 [^704^].

Trailing stops to breakeven after a 1R move reduce a position's heat contribution to zero, effectively removing it from the portfolio heat calculation. Scaling out at 1R profit — exiting 50% of the position — cuts the remaining heat in half [^704^]. These techniques allow a portfolio to maintain more open positions without violating the 8–10% heat cap.

#### 6.3.2 The Illusion of ETF Diversification

The correlation between SPY (S&P 500) and QQQ (Nasdaq-100) is approximately 0.93. Holding both provides almost no diversification benefit — during market stress, that correlation spikes toward 1.0, transforming what appears to be a two-position portfolio into a single concentrated bet on U.S. large-cap equities [^697^]. The same applies to sector ETFs with overlapping constituents: XLK (Technology) and QQQ share roughly 40% of their holdings by weight.

The momentum-mean reversion pair discussed in Chapter 5 — with a correlation of approximately -0.35 [^647^] — represents genuine diversification because the strategies exploit different market phenomena. D.E. Shaw research confirmed that daily pairwise correlations across more than 20 alternative investment strategies remained below 0.1 even through the Global Financial Crisis [^624^]. The lesson for retail traders: diversify across *strategies*, not across instruments that move together.

The most dangerous aspect of correlation is its regime-dependent nature. Correlations that average 0.3 in calm markets spike to 0.8 or higher during crises [^697^]. Portfolio heat must be stress-tested with crisis-level correlations, not historical averages. A portfolio that survives a backtest with average correlations may still experience catastrophic losses when correlations converge to 1.0.

#### 6.3.3 The Simplicity Premium

Across every strategy category examined in this report, the simplest implementation with the fewest parameters consistently outperforms more complex variants out-of-sample. Nick Radge's Weekend Trend Trader uses one parameter — a 20-week breakout — and achieves 22.9% CAGR on the S&P MidCap 400. The IBS mean-reversion indicator requires a single calculation, $(\text{Close} - \text{Low}) / (\text{High} - \text{Low})$, yet outperforms multi-indicator systems. This "simplicity premium" is the inverse of overfitting: each additional parameter introduces estimation error that compounds in live trading.

The implication for risk management is direct: the most robust risk controls are simple, rules-based, and parameter-light. A drawdown ladder with five levels and clear thresholds outperforms a Hidden Markov Model with 12 transition probabilities that require continuous recalibration. The HMM regime filter did reduce maximum drawdown from 56% to 24% in S&P 500 backtests (2005–2014) [^682^], but it also eliminated 10 of 41 trades — including profitable ones during regime transitions. The filter's out-of-sample performance degrades because state transition probabilities are non-stationary [^682^].

Strategies with three or fewer parameters should be the default for retail automation. The fixed fractional sizing formula has one parameter (risk %). The drawdown ladder has five thresholds, each with a single action. The portfolio heat cap is one number. These controls can be implemented in a dozen lines of code and will behave predictably across market regimes. Complex risk models with many parameters may optimize beautifully in backtests but fail precisely when protection is most needed — during unprecedented market conditions that lie outside the model's training distribution.

The risk management framework presented in this chapter — fixed fractional sizing at 1–2%, portfolio heat capped at 8–10%, graduated drawdown ladders, and multi-horizon circuit breakers — is deliberately simple. It does not require forecasting market direction, estimating strategy edge, or calibrating regime-switching models. It requires only the discipline to follow rules that are computationally trivial but psychologically demanding. Chapter 7 will connect these rules to the automation platforms that enforce them without human intervention.
