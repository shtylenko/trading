## 4. High-Octane Strategies: Approaching the 3% Target

The core momentum and mean reversion strategies examined in Chapters 2 and 3 — Dual Momentum GEM at 15.8–17.4% CAGR, RSI(2) mean reversion at 10.7%, and the Mean Reversion Curve at 25.7% — deliver respectable risk-adjusted performance but generally fall short of the 3% monthly (36% annualized) target. This chapter examines the only strategy class that has demonstrably reached that threshold: leveraged, concentrated, and regime-dependent approaches. The framing, stated upfront, is that none of these strategies are suitable as standalone core holdings. They are satellite allocations at best, supported by quantitative evidence that carries existential caveats.

### 4.1 Leveraged ETF Strategies

Leveraged exchange-traded funds (LETFs) use derivatives — typically total return swaps — to deliver a multiple of the daily return of an underlying benchmark. This daily reset creates volatility decay, a structural drag that erodes returns over multi-day holds in choppy markets. Despite this headwind, several systematic LETF strategies have produced backtested CAGRs above 30%, placing them alone in the 3%-per-month territory.

#### 4.1.1 TQQQ Weekly MACD: The Highest-Verified LETF Strategy

The TQQQ Weekly MACD strategy, developed by Lambros Petrou and grounded in Michael Gayed and Charlie Bilello's 2016 Charles H. Dow Award-winning paper "Leverage for the Long Run," is the highest-performing verified LETF system in the research literature [^118^]. The approach uses weekly MACD zero-line crossovers on the unleveraged QQQ to time entries and exits in the 3x leveraged TQQQ.

The rules are mechanical. Entry requires the MACD line (12-period EMA minus 26-period EMA) to cross above the zero line on the weekly QQQ chart. A modified 5-period EMA signal line (shortened from the standard 9) provides re-entry signals when MACD is already above zero. Two consecutive rising weeks act as confirmation. Exits trigger on any of three conditions: MACD crossing below zero; a dynamic stop at 30% below the highest close (with a 2% buffer); or an entry-level stop at 10% below the entry price. The active stop is the maximum of the entry and dynamic stops [^118^].

From February 2010 through July 2025, the TQQQ variant returned +11,194%, approximately 36% CAGR [^118^]. The same methodology applied to EQQQ with NDX signals from 2005–2025 avoided the 2008 crash with only an -11% losing trade, and an AVGO variant achieved +6,000% with a 100% win rate [^118^]. A simpler 40-week SMA crossover alternative delivered +2,800%, though it trailed the MACD version significantly [^118^]. The strategy exited during the 2022 bear market, avoiding the -81.7% drawdown that TQQQ buy-and-hold suffered. The existential limitation: TQQQ did not exist during the 2000–2002 dot-com crash, and the strategy's performance is inseparable from the longest technology bull market in history.

#### 4.1.2 Hedgefundie Adventure: Leveraged Risk Parity

The Hedgefundie Excellent Adventure, proposed on the Bogleheads forum in February 2019, holds 55% UPRO (3x S&P 500) and 45% TMF (3x long-term Treasuries), rebalanced quarterly [^135^]. The core assumption is negative stock-bond correlation (historically ~-0.5), so Treasury gains cushion equity drawdowns. Simulated backtests to 1987 produced a 24.63% CAGR with a -70.58% maximum drawdown [^134^]. The Sharpe ratio of 0.73 matched the S&P 500 itself — the excess return came purely from additional risk.

Live tracking since February 2019 tells a more instructive story: a $100k portfolio peaked at $250k in January 2022 (+150%), then collapsed to $86k by October 2022 as both stocks and bonds fell together during rate hikes [^137^]. Full-year 2022 delivered -57.50%, the worst on record, because the foundational assumption broke precisely when needed [^513^]. Recovery to $237k by April 2025 does not erase the psychological toll of watching two-thirds of capital evaporate.

#### 4.1.3 LETF Risk Management: Crash Filters and Circuit Breakers

Without rigorous risk management, LETF strategies are not investments — they are lottery tickets. Several protective mechanisms have been empirically tested. The single-day crash filter, formalized in Lewis Glenn's SSRN paper (2020), exits immediately to IEF (7–10 year Treasury ETF) if TQQQ drops 20%+ in a single session, with re-entry only after TQQQ recovers above its pre-crash price [^125^]. This filter triggered during the March 2020 COVID crash and preserved capital. A VIX-based circuit breaker exits when VIX sustains readings above 40 for three or more days. Maximum drawdown exits (40–50% portfolio-level stops) act as the final backstop. The TQQQ/TMF 50/50 strategy with bimonthly rebalancing and this crash filter produced a 23.83% CAGR with a -38.65% maximum drawdown from January 2010 through October 2025 — the highest MAR ratio (0.62) among all LETF approaches [^125^].

#### 4.1.4 Volatility Decay: The Mathematical Drag

Volatility decay is the central mathematical reality of LETF investing. The daily return reset means that a 3x LETF does not deliver 3x the index return over any holding period longer than one day. The drag can be approximated as:

$$\text{Drag} \approx -0.5 \times L \times (L - 1) \times \sigma^2$$

where $L$ is the leverage factor and $\sigma$ is the daily volatility of the underlying index [^501^] [^507^]. For TQQQ ($L = 3$) with a 2% daily volatility, the daily drag is approximately -0.12%, which compounds to roughly -26% annually in a choppy market.

Critically, decay is not always negative. In strong trending markets, compounding works in the LETF's favor and it can deliver *more* than 3x the index return. The table below tracks TQQQ's actual performance against its theoretical 3x target:

| Year | QQQ Return | TQQQ Actual | Theoretical 3x | Tracking Error |
|------|-----------|-------------|----------------|----------------|
| 2017 | +32.68% | +118.06% | +98.04% | **+20.02%** (positive) |
| 2020 | +48.63% | +110.05% | +145.89% | **-35.84%** (negative) |
| 2022 | -32.49% | -79.08% | -97.47% | **+18.39%** (positive) |
| 2023 | +54.76% | +198.26% | +164.28% | **+33.98%** (positive) |
| 2025 | +20.77% | +34.37% | +62.31% | **-27.94%** (negative) |

In the choppy, high-volatility environments of 2020 and 2025, TQQQ underperformed its 3x target by 27–36 percentage points. In trending years like 2023, it outperformed by 34 percentage points. The asymmetry is punishing: a -33% drop requires a +50% gain to recover, and the 3x structure amplifies both directions.

![TQQQ Tracking Error](fig_tqqq_tracking_error.png)

*Source: QuantFlowLab, Yahoo Finance. Tracking error = TQQQ actual return minus theoretical 3x QQQ return.*

The tracking error ranged from -35.8% to +34.0% across these five years, with an absolute average of 27.2%. An investor who assumes TQQQ will deliver 3x the QQQ return over any multi-month horizon will be systematically disappointed in volatile markets. LETF strategies are not merely "the index with leverage" — they are distinct instruments with their own risk characteristics.

### 4.2 Concentrated Factor Approaches

Factor-based strategies select securities based on characteristics that have historically delivered excess returns. When applied with concentration, the annualized returns can approach the 3% monthly threshold. Three approaches stand out: Piotroski's F-Score, O'Shaughnessy's Trending Value, and Nick Radge's Weekend Trend Trader.

#### 4.2.1 Piotroski F-Score: Fundamental Quality Screening

The Piotroski F-Score, introduced by Joseph Piotroski in his 2000 Stanford paper, assigns one point for each of nine binary criteria across profitability, leverage, and efficiency dimensions [^536^]. Profitability criteria include positive return on assets (ROA), improving ROA, positive operating cash flow, and cash flow exceeding net income (an accruals check). Leverage criteria reward declining debt ratios, improving current ratios, and no share dilution. Efficiency criteria capture improving gross margin and asset turnover [^541^].

In Piotroski's original test from 1976–1996, stocks with the highest F-Scores (8–9) within the lowest price-to-book quintile delivered a 23.0% CAGR, outperforming the S&P 500 by 13.4 percentage points annually [^536^]. The high-F-Score portfolio picked winners 50% of the time — a coin-flip hit rate that nonetheless produced massive alpha because the average winner gained far more than the average loser declined. The strategy is easily screenable using free tools like Portfolio123 or Finviz, though results are concentrated in small and mid-cap stocks where liquidity constraints limit scalability. A recent QuantConnect backtest from 2020–2023 showed 43.2% CAGR versus SPY's 14.4%, though the three-year window with overlapping confidence intervals means this outperformance is not statistically significant at conventional levels [^567^].

#### 4.2.2 O'Shaughnessy Trending Value: The 45-Year Record

James O'Shaughnessy's Trending Value strategy, documented in *What Works on Wall Street*, combines deep value screening with intermediate-term momentum. The exact rules are: select the 10% most undervalued stocks by Value Composite Two (a composite of P/E, P/B, P/S, EV/EBITDA, and shareholder yield), then from that value pool select the 25–50 stocks with the best 6-month price appreciation [^570^] [^524^]. Positions are equal-weighted and held for one year before rebalancing.

From 1964 through 2009 — a 45-year span encompassing twelve economic cycles — the strategy produced a 21.1% CAGR versus 11.2% for the all-stock universe and approximately 6.2% for the S&P 500 [^519^]. It never experienced a five-year losing period, a distinction shared by few other high-return strategies. The key insight is that combining value and momentum captures two distinct behavioral anomalies: investor overreaction to negative news (value) and underreaction to positive trends (momentum). The negative correlation between these factors smooths the return path relative to either factor in isolation. However, the strategy's reliance on the value factor meant significant underperformance during the 2010–2019 "lost decade" for value, and recent performance has been more modest.

#### 4.2.3 Weekend Trend Trader: Breakout Momentum on Individual Stocks

Nick Radge's Weekend Trend Trader (WTT) applies classic trend-following principles to individual stocks with a mechanical weekend review process. The strategy demands that the broad market index close above its 100-day (or 10-week) moving average before any new positions are initiated. Individual stocks must simultaneously hit a 20-week high and exhibit a 20-week rate of change (ROC) of at least 30%. Entries occur at Monday's open following a weekend signal scan [^357^] [^94^].

The WTT's risk management is equally disciplined. A 40% trailing stop below the highest weekly close protects positions during uptrends; this tightens to 10% when the market index falls below its 10-week average. Stops are never lowered, only raised. Position sizing allocates 5% of capital per position with a maximum of 20 positions, keeping the portfolio fully invested during qualifying markets. Over 33 years of backtesting on Australian and U.S. mid-cap universes, the strategy produced a 22.9% CAGR with a 44% win rate and a 2.6:1 win-to-loss ratio [^78^]. The low win rate is more than compensated by the magnitude of winners — the average winning trade gains 21% while the average loser surrenders 11.97%.

### 4.3 Weekend Trend Trader Deep Dive

The Weekend Trend Trader exemplifies the paradox of high-return strategies: a sub-50% win rate can produce 20%+ annualized returns when winners substantially outsize losers. This is the mathematics of trend-following, and it runs counter to the intuition that "being right" is what matters.

#### 4.3.1 Exact Trading Rules

Entry requires four simultaneous conditions. First, the reference market index — translatable to the S&P Midcap 400 ($MID) for U.S. implementation — must be above its 100-day simple moving average. This regime filter eliminates roughly 30–40% of potential entries and keeps the strategy out during the deepest drawdowns. Second, the individual stock must register a 20-week high (the highest weekly close over the preceding 20 weeks). Third, the 20-week rate of change must exceed 30%, ensuring the breakout is backed by genuine momentum [^357^]. Entry executes at the following Monday's open.

Exits are equally mechanical. During uptrends (index above 10-week MA), a 40% trailing stop below the highest weekly close protects positions. During downtrends (index below 10-week MA), this tightens to 10%. The stop level is never reduced; it only rises as the stock makes new highs [^94^]. Review occurs exclusively on weekends, with orders placed for Monday execution.

#### 4.3.2 Position Sizing and Capital Deployment

The WTT uses a fixed fractional approach: 5% of capital per position, maximum 20 positions. When the regime filter shifts from uptrend to downtrend, existing positions are not liquidated; instead, trailing stops tighten from 40% to 10%. The average single-position loss is approximately 0.6% of total portfolio (5% × 11.97% average loss), while the average gain contributes 1.05% (5% × 21%) [^96^]. This asymmetry — small losses on most trades, outsized winners on the remainder — drives the strategy's returns.

#### 4.3.3 Backtest Results: Why a 44% Win Rate Produces 22.9% CAGR

An independent backtest on the S&P 100 from 1992–2019 produced 78 trades: 44% winners averaging +21%, 56% losers averaging -11.97%. The expectancy per trade is:

$$\text{Expectancy} = (0.44 \times 21\%) - (0.56 \times 11.97\%) = 9.24\% - 6.70\% = +2.54\%$$

With 20 positions deployed and an average holding period of ~6.3 years, compounding this positive expectancy drives the 16.6–22.9% CAGR range [^353^]. A ThinkOrSwim backtest starting with $25,000 in 1992 grew to $1,789,306 by 2019 — a 7,057% total return versus 679% for buy-and-hold [^353^].

The 44% win rate is not a bug; it is the defining feature. Trend-following strategies capture the fat right tail of equity returns — the small number of stocks that produce 100–500% gains over multi-year holds. The 40% trailing stop ensures these outliers contribute disproportionately to portfolio growth. The mathematics of compounding makes the occasional 3x–5x winner more valuable than dozens of 10% gains.

### 4.4 The Honest Assessment of High-Octane Approaches

The strategies presented in this chapter share three attributes that distinguish them from the core approaches in Chapters 2 and 3: concentration, elevated volatility, and regime dependence. Understanding these shared characteristics is essential for any investor considering allocation to high-return strategies.

#### 4.4.1 Common Features: Concentration, Volatility, and Regime Dependence

Every strategy that approaches the 3% monthly target accepts significant drawdowns as the price of admission. The TQQQ Weekly MACD strategy, despite its impressive +11,194% total return, carries an entry-level stop of 10% and a dynamic trailing stop of 30% — meaning any single position can lose nearly a third of its value before the exit trigger fires [^118^]. The Hedgefundie Adventure's -70.58% maximum drawdown is not a tail-risk scenario; it is the *tested* historical worst case [^134^]. The Weekend Trend Trader's 40% trailing stop implies that individual positions routinely decline 20–35% before recovering or exiting. These drawdowns are not aberrations; they are built into the strategies' mechanics.

Regime dependence is equally pronounced. The TQQQ MACD strategy requires a sustained Nasdaq 100 bull market to function. In a prolonged tech bear market comparable to 2000–2002, the weekly MACD signals would generate a sequence of losing trades as the strategy attempts to buy declining rallies. O'Shaughnessy's Trending Value suffered through the 2010–2019 value factor drought. The Hedgefundie Adventure breaks when stock-bond correlations turn positive — as they did in 2022. No high-octane strategy works across all market environments; each is a specialized tool that functions only when its underlying assumptions hold.

#### 4.4.2 TQQQ MACD: Leveraged Concentration, Not Pure Alpha

The TQQQ Weekly MACD strategy's ~36% CAGR must be understood for what it is: a leveraged bet on continued technology sector outperformance [^118^]. The MACD signal contributes timing value — it avoided the 2022 bear market and captured most of the 2023–2024 rally — but the bulk of the return comes from holding 3x leveraged exposure to the best-performing major index during the best-performing period in its history. If an investor had simply bought and held TQQQ from February 2010 through July 2025, the CAGR would have been approximately 42% with a maximum drawdown of -81.6% [^482^]. The MACD timing filter reduced the CAGR to ~36% but also reduced the maximum drawdown to roughly 30–40% through its dual stop-loss system. The "alpha" of the strategy is not the return itself; it is the risk reduction relative to buy-and-hold.

This is a critical distinction. Pure systematic alpha — returns derived from a rules-based edge that is independent of market direction — would produce positive returns in any sufficiently long period. The TQQQ MACD strategy would likely have produced catastrophic losses if applied to the Nasdaq 100 during 2000–2002, when the index fell 78% over 31 months. The absence of this period from the backtest is not a minor gap; it is a blind spot that could encompass the strategy's failure mode.

#### 4.4.3 Risk-Reward Framework: Satellite Allocations Only

None of the strategies in this chapter are suitable as standalone core holdings for risk-averse investors. The appropriate framework is a core-satellite structure, where 80–95% of capital is deployed in diversified, lower-volatility strategies (Dual Momentum GEM, multi-factor equity, broad index funds) and 5–20% is allocated to high-octane approaches as return enhancers. Even the strategy's originators acknowledge this: Hedgefundie himself called the approach a "lottery ticket" and recommended implementation in a Roth IRA with money one can afford to lose entirely [^135^].

The following table summarizes the key LETF strategies examined in this chapter:

| Strategy | CAGR (Backtested) | Max Drawdown | Sharpe | Win Rate | 2022 Performance | Complexity |
|----------|------------------|--------------|--------|----------|-----------------|------------|
| TQQQ Weekly MACD | ~36% [^118^] | ~30–40%* | High | ~85% | Avoided bear market | Medium |
| Hedgefundie 55/45 | 24.6% [^134^] | -70.6% [^134^] | 0.73 | N/A | -57.5% [^513^] | Low |
| TQQQ/TMF 50/50 + Crash Filter | 23.8% [^125^] | -38.7% [^125^] | 0.95 | 74% | Filter triggered | Low |
| VIX-Filtered UPRO/TQQQ | 24.4% [^120^] | -54% [^120^] | — | — | -48% [^120^] | High |
| 200-SMA TQQQ Filter | ~28% [^482^] | -57% [^482^] | Higher | — | Partially avoided | Very Low |
| Weekend Trend Trader | 22.9% [^78^] | -30% to -58% | ~0.6 | 44% | Regime-dependent | Medium |

*MACD strategy drawdown is controlled by dual stop losses; actual maximum depends on stop parameters and path dependency.*

The table reveals a clear trade-off. The highest-return strategies (TQQQ MACD at ~36%) come with the largest implicit risks — concentration in a single leveraged asset, untested in a secular tech bear market. The most robust risk-adjusted approach (TQQQ/TMF 50/50 with crash filter at 0.95 Sharpe) sacrifices roughly 12 percentage points of CAGR for a drawdown that is 32 percentage points smaller. The Hedgefundie Adventure sits at the extreme end of the risk spectrum: its 24.6% CAGR is impressive, but the -70.6% drawdown tested in simulation would wipe out two-thirds of invested capital — a loss from which many investors would never recover psychologically.

The realistic framing for a retail investor is that these strategies can deliver 1.5–2.5% monthly in favorable conditions after accounting for backtest degradation (30–50%), strategy decay (5%+ annually post-publication), and execution slippage. The 3% target remains an aspirational upper bound achievable only during strong trending markets with perfect execution and no major drawdowns. The path to sustainable high returns lies not in doubling down on a single high-octane strategy but in combining multiple uncorrelated approaches — the subject of Chapter 5.
