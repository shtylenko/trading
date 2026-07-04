## 2. Core Strategy Toolkit: Momentum

Momentum investing — the systematic practice of buying assets that have risen recently and avoiding those that have fallen — stands as one of the most extensively validated anomalies in financial economics. First documented by Jegadeesh and Titman in their landmark 1993 study, the momentum premium has persisted across asset classes, geographies, and time periods spanning nearly a century [^317^]. Assets that outperformed over the past 3–12 months tend to continue outperforming over the subsequent 1–6 months, generating excess returns unexplained by traditional risk factors.

The momentum toolkit encompasses four implementations. *Dual momentum* rotates between asset classes using trend filters. *Cross-sectional momentum* ranks individual stocks and holds the top performers. *Sector and ETF momentum* applies the same ranking logic to broad groups. *Earnings momentum* combines price trends with fundamental surprise signals. Each variant carries a different risk-return profile, capital requirement, and implementation complexity.

### 2.1 Dual Momentum (Gary Antonacci GEM)

#### 2.1.1 Exact Rules

Gary Antonacci's Global Equities Momentum (GEM) strategy, formalized in his 2012 NAAIM Wagner Award paper, remains the simplest systematically implementable momentum strategy for retail traders [^313^] [^318^]. GEM operates on two distinct momentum concepts applied sequentially on the last trading day of each month.

**Step 1 — Absolute Momentum:** Calculate the 12-month total return of the S&P 500 (SPY) and compare it to the 12-month total return of a risk-free proxy (3-month T-Bill via BIL). If S&P 500 > T-Bill, proceed to Step 2. If S&P 500 ≤ T-Bill, move 100% to intermediate-term bonds (AGG or IEF) [^318^].

**Step 2 — Relative Momentum:** Only if Step 1 signals risk-on, compare 12-month returns of SPY versus international developed equities (VEU or VXUS). Invest 100% in whichever has outperformed. The strategy always holds exactly one asset, averaging only 1.5 trades per year [^435^].

The sequential logic is the key innovation: absolute momentum eliminates the worst drawdowns by moving to bonds during sustained bear markets, while relative momentum tilts toward the stronger equity region during bull markets.

#### 2.1.2 Backtested Performance

Antonacci's original backtest covering 1974–2013 reported a 17.43% CAGR with a Sharpe ratio of 0.87 and a maximum drawdown of -22.72%, compared to 8.85% CAGR and -60.21% maximum drawdown for a global market buy-and-hold portfolio [^314^]. Independent replication studies confirmed the general robustness of these findings. A comprehensive analysis by Severian (2015) using slightly different bond proxies found a 16.70% CAGR and -19.07% maximum drawdown over the same period, with a Sharpe ratio of 0.87 [^314^].

An extended backtest from Antonacci covering 1950–2018 showed a 15.8% CAGR, 11.5% annualized standard deviation, 0.96 Sharpe ratio, and -17.8% maximum drawdown [^435^]. The component decomposition reveals why the combination works: relative momentum alone produced a 13.4% CAGR but retained equity-like drawdowns of -54.6%, while absolute momentum alone produced a 12.3% CAGR with a much smaller -29.6% drawdown. Only the combination of both filters achieved the 15.8% CAGR with the -17.8% drawdown [^435^].

| Period | Source | CAGR | Max Drawdown | Sharpe Ratio |
|--------|--------|------|-------------|--------------|
| 1974–2013 (Original) | Antonacci [^314^] | 17.43% | -22.72% | 0.87 |
| 1973–2013 (Replication) | Severian [^314^] | 16.70% | -19.07% | 0.87 |
| 1950–2018 (Extended) | Antonacci [^435^] | 15.80% | -17.80% | 0.96 |
| ~56 years | PortfolioDB [^430^] | 14.60% | -21.60% | 0.79 |
| 1986–2026 | BestFolio [^313^] | 12.30% | -33.70% | 0.99 |

The performance range across these studies — 12.3% to 17.43% CAGR — reflects differences in bond proxies, international index definitions, and the inclusion of more challenging recent periods. The original 1974–2013 period benefited from strong bond tailwinds during equity drawdowns; the 1986–2026 period includes the more difficult 2014–2025 out-of-sample years.

#### 2.1.3 Out-of-Sample Performance Since 2014

The post-publication record reveals the pattern common to all published strategies: meaningful but reduced out-of-sample performance. GEM has struggled during the 2014–2025 period, with the QuantifiedStrategies backtest showing only 6.75% CAGR for 1986–2024 versus 9.2% for the S&P 500 over the same span [^19^]. ReSolve Asset Management's ensemble analysis (1950–2018) found the original GEM specification at 14.9% CAGR with 0.90 Sharpe, while their ensemble approach (combining multiple lookback periods) produced 14.2% CAGR with 0.93 Sharpe and an average maximum drawdown of only -13.2% [^310^].

The weaker out-of-sample results stem from two factors. First, the 2012–2025 period was challenging for trend-following strategies because major equity drawdowns (COVID-19 crash in March 2020) were sharp but short-lived, reversing before the 12-month lookback could exit equities. Second, bond returns were muted during this period, reducing the protective value of the risk-off allocation [^312^]. Despite these headwinds, GEM's drawdown protection has held: the strategy avoided much of the 2022 decline by rotating into bonds when absolute momentum turned negative.

#### 2.1.4 Why It Works

Absolute momentum is the critical innovation that separates GEM from simpler relative-strength approaches. By requiring the broad market to have positive 12-month returns before any equity exposure, the strategy systematically avoids the worst bear market drawdowns. Historical analysis shows that all major equity crashes — 1929–1932, 1973–1974, 2000–2002, 2008–2009, and 2022 — were preceded by negative 12-month returns that would have triggered the bond allocation [^318^]. The cost of this protection is whipsaw risk: during choppy, range-bound markets, the strategy may produce false signals that generate modest losses relative to buy-and-hold. Over complete market cycles, however, the protection more than compensates for the whipsaw costs.

### 2.2 Cross-Sectional Stock Momentum

#### 2.2.1 Jegadeesh-Titman Foundation

Jegadeesh and Titman's 1993 study, covering 1965–1989, found that a strategy buying the top decile of performers and shorting the bottom decile generated 12.01% in compounded excess returns annually, with positive profits in virtually every 5-year sub-period [^317^]. The key methodological detail for long-only implementation is the *skip month*: the most recent month's return is excluded from the ranking calculation to avoid contamination by short-term reversal effects [^317^]. The standard approach uses a 12-month lookback minus the most recent month ("12-1 month momentum"), ranks all stocks by this return metric, and goes long the top decile or quintile.

The long-only adaptation captures a significant portion of the full premium. Griffin, Ji, and Martin found momentum is more profitable on the long side than the short side, and Fisher, Shah, and Titman confirmed that long-only value-plus-momentum combinations outperform pure strategies after transaction costs [^315^] [^344^].

#### 2.2.2 Long-Only Implementation

The exact rules for long-only cross-sectional momentum are: (1) define a liquid universe (S&P 500 minimum), (2) calculate total return for each stock over months t-12 to t-1, (3) sort and select the top decile or quintile, (4) equal-weight positions, (5) rebalance monthly [^307^]. Quantpedia's compilation found 13.94% annualized returns for long-only momentum versus ~10% for the market benchmark from the 1920s through 2009 [^136^], while Manigault's work found the top decile outperformed by 3–5% annually on the S&P 500 [^309^]. These figures are gross of transaction costs.

Lesmond, Schill, and Zhou (2004) found that accounting for realistic transaction costs, many momentum strategies become unprofitable net-of-fees [^360^] [^361^]. A UK replication found round-trip costs of 3.77% for winner portfolios, implying a 2–4% annual drag at 100%+ turnover [^362^]. Modern commission-free brokers eliminate commissions, but bid-ask spreads and market impact remain significant. The realistic net-of-cost expectation is approximately 0.7–1.0% monthly for S&P 500 implementations, with drawdowns of 30–50% during momentum crash periods.

#### 2.2.3 Risk-Managed Momentum (Barroso & Santa-Clara)

The primary weakness of standard momentum is its severe left-tail risk. Daniel and Moskowitz documented that momentum strategies can crash catastrophically — the Fama-French momentum factor lost 73% in just three months during the 2009 recovery as beaten-down stocks rebounded sharply [^85^]. This crash risk is not a rare anomaly but a structural feature: momentum strategies are short volatility, and this exposure becomes most dangerous during market turning points.

Barroso and Santa-Clara (2015) introduced a risk-managed approach that nearly doubles the Sharpe ratio of standard momentum by scaling portfolio exposure based on past realized volatility [^325^]. Their method calculates the realized variance over the past 6 months (126 trading days), sets a target volatility (typically 12% annualized or the market's long-run average of approximately 15.93%), and scales the momentum portfolio's exposure proportionally: $L = \sigma_{target} / \hat{\sigma}$, where $L$ is the leverage factor. When realized volatility is high, the strategy reduces exposure (or holds cash); when volatility is low, it increases exposure.

The performance improvement is substantial. Standard momentum produced a Sharpe ratio of 0.53, while the constant-volatility scaled version achieved 0.97 — an 83% improvement in risk-adjusted returns [^325^]. Beyond the Sharpe improvement, volatility scaling dramatically reduces excess kurtosis and left skewness, making the return distribution far more palatable for investors who cannot tolerate the occasional -50% drawdowns of raw momentum. Moreira and Muir (2017) extended this work using a shorter 1-month variance estimation window and found similar results: Sharpe ratios roughly double across multiple asset classes [^329^].

| Technique | Standard Momentum Sharpe | Risk-Managed Sharpe | Improvement | Crash Protection |
|----------|------------------------|---------------------|-------------|------------------|
| Constant Volatility Scaling (Barroso & Santa-Clara) [^325^] | 0.53 | 0.97 | +83% | Strong |
| Dynamic Scaling (Moreira & Muir) [^329^] | 0.53 | ~1.06 | +100% | Strong |
| Idiosyncratic Momentum (Blitz, Hanauer & Vidojevic) [^345^] | 0.25 | 0.48 | +92% | Excellent |
| Conservative Formula (Blitz & van Vliet) [^344^] | 0.40 | ~0.60 | +50% | Moderate |
| Meta-Strategy + Mean Reversion [^129^] | 0.54 | 1.16 | +115% | Strong |

Hanauer and Windmueller (2020) tested three approaches to fixing momentum crashes — volatility scaling, idiosyncratic momentum, and dynamic scaling — and found that all three approximately doubled Sharpe ratios compared to standard momentum while significantly decreasing crash risk [^328^]. The idiosyncratic momentum variant developed by Blitz, Hanauer, and Vidojevic is particularly noteworthy: by ranking stocks on returns orthogonal to the Fama-French market, size, and value factors (residual returns) rather than raw total returns, the strategy produces a Sharpe ratio of 0.48 versus 0.25 for conventional momentum, with essentially zero exposure to momentum crash risk following bear markets [^345^].

For retail traders, the practical implication is clear: *any* momentum implementation should include a volatility-scaling overlay or an equivalent risk-management rule. The simplest approach is to reduce position size by 50% whenever the VIX exceeds 25, or to exit momentum positions entirely when the S&P 500 falls below its 200-day moving average. The cost of this insurance is modest — typically 0.5–1.5% of annual return — while the benefit is protection against the catastrophic drawdowns that destroy compounding.

![Momentum Strategies: Return vs. Risk Profile](momentum_comparison_chart.png)

*Source: Compiled from academic backtests and strategy research. CAGR figures are gross of transaction costs. SUE Earnings Momentum CAGR represents the midpoint of the 13.6–23.6% range reported across studies.*

### 2.3 Sector & ETF Momentum

#### 2.3.1 Top-3 SPDR Sector Rotation

Moskowitz and Grinblatt (1999) first documented that industry portfolios exhibit significant momentum even after controlling for size, book-to-market, and individual stock effects, finding that industry momentum strategies are more profitable than individual stock momentum [^421^].

The simplest implementation ranks the 10 Select Sector SPDR ETFs by 12-month total return and holds the top 3 equal-weight, rebalancing monthly. Faber's backtest from 1928–2009 found a 13.94% CAGR with 0.54 Sharpe and -46.29% maximum drawdown — still severe but roughly 9 percentage points better than buy-and-hold [^136^]. Adding a trend-following filter — only holding sectors above their 10-month moving average — further reduces volatility and drawdown [^136^]. Faber's SMA-filtered variant (1990–2011) produced 13.01% annualized returns with a 0.65 Sharpe ratio [^459^].

#### 2.3.2 SACEMS (Simple Asset Class ETF Momentum)

The Simple Asset Class ETF Momentum Strategy (SACEMS), publicly tracked by CXO Advisory Group since 2010, applies relative momentum across nine asset class ETFs: SPY, EFA, EEM, IWM, QQQ, VNQ, LQD, HYG, and GLD [^117^]. SACEMS uses a 5-month lookback and monthly rebalancing. Three variants are tracked: Top 1 (100% in highest-ranked), EW Top 2, and EW Top 3. The EW Top 3 variant has delivered approximately 8–9% CAGR with a -20% drawdown and 0.52 Sharpe since July 2006, while the Top 1 variant reaches 10–11% CAGR with a -25% drawdown [^117^] [^443^].

SACEMS compensates for lower raw returns with greater diversification and a shorter lookback that responds faster to regime changes. Its live tracking record since 2010 provides genuine out-of-sample validation. Combining SACEMS with its value counterpart (SACEVS) in a 50-50 blend produces 12.0% CAGR with -14% drawdown and 0.99 Sharpe, demonstrating that momentum and value signals are genuinely complementary [^443^] [^444^].

#### 2.3.3 Logical Invest Meta-Strategy

Frank Grossmann's Logical Invest approach combines four sub-strategies into a meta-strategy selecting SPDR sector ETFs: (1) long-lookback momentum (198-day), (2) short-lookback momentum (7-day), (3) mean reversion "buy worst," and (4) a combined momentum-plus-mean-reversion signal [^129^]. The individual sub-strategies produced CAGRs of 9.22%, 9.86%, 11.36%, and 12.30% respectively, with Sharpe ratios between 0.47 and 0.64. The meta-strategy, dynamically allocating across all four, achieved 12.8% CAGR with a 1.16 Sharpe ratio and only -17% maximum drawdown — the best risk-adjusted performance of any momentum variant in this chapter. A modified Sharpe ranking formula penalizes high-volatility sectors, tilting allocations defensively during corrections.

The meta-strategy's success highlights a core principle: combining uncorrelated signals within a momentum framework produces substantially better risk-adjusted returns than any single momentum signal alone.

### 2.4 Earnings Momentum

#### 2.4.1 SUE + Earnings Surprise + Price Momentum Three-Signal Combo

Earnings momentum strategies exploit the *post-earnings announcement drift* (PEAD) — the tendency for stocks reporting positive earnings surprises to continue drifting upward for weeks or months after the announcement. First documented by Ball and Brown in 1968, PEAD remains one of the most persistent anomalies in finance.

The core metric is *Standardized Unexpected Earnings* (SUE): $SUE = (EPS_{current\ quarter} - EPS_{same\ quarter\ last\ year}) / \sigma(EPS\ changes)$, where $\sigma$ is the standard deviation of earnings changes over the prior eight quarters [^323^]. Chan, Jegadeesh, and Lakonishok (1996) demonstrated that combining SUE with analyst estimate revisions and prior price momentum produces the strongest predictive model, with SUE t-statistics of 6.00 for 6-month returns and analyst revisions (REV6) at 5.45 for 12-month returns [^324^]. The three signals are correlated but distinct (SUE correlates with prior returns at 0.293 and with analyst revisions at 0.440), identifying stocks where the fundamental narrative and market narrative are aligned.

A QuantConnect implementation from 2007–2026 found 13.62% CAGR over the full period, with a 5-year subset (2021–2026) showing 23.58% CAGR and 65–67% win rates [^323^]. Academic literature reports 13.6% to 23.6% CAGR for combined SUE, earnings announcement return (EAR), and price momentum strategies depending on specification [^324^] [^323^].

| Strategy | Period | CAGR (Gross) | Sharpe | Max Drawdown | Min Capital | Monthly Time |
|----------|--------|-------------|--------|-------------|-------------|-------------|
| GEM Dual Momentum [^435^] | 1950–2018 | 15.8% | 0.96 | -17.8% | $10K | 30 min |
| Cross-Sectional 12-1 [^136^] | 1920s–2009 | 13.9% | 0.54 | -46.3%* | $100K | 4–8 hrs |
| Sector Rotation Top-3 [^136^] | 1928–2009 | 13.9% | 0.54 | -46.3% | $15K | 30 min |
| SACEMS EW Top-3 [^117^] | 2006–present | 8.5% | 0.52 | -20.0% | $15K | 30 min |
| SUE Earnings Mom. [^323^] | 2007–2026 | 13.6% | 0.44 | -63.9% | $100K | 8–12 hrs |
| Risk-Managed (Vol Scaling) [^325^] | Multi-decade | 12.0% | 0.97 | -20.0% | $100K | 2–4 hrs |
| Logical Invest Meta [^129^] | Multi-decade | 12.8% | 1.16 | -17.0% | $25K | 2–4 hrs |

*Cross-sectional max drawdown reflects top-decile long-only without risk management overlays. Volatility scaling reduces this to approximately -20%.*

The comparison reveals a clear trade-off structure. GEM and the Logical Invest Meta-Strategy occupy the efficient frontier, delivering strong returns with contained drawdowns below -18%. Raw cross-sectional and sector rotation approaches offer similar CAGRs but with 2–3× the drawdown risk. SACEMS sacrifices raw returns for diversification and genuine multi-asset exposure. SUE earnings momentum stands alone as an outlier — the highest potential returns paired with the most extreme risk, requiring sophisticated risk overlays to be investable. For retail traders operating without institutional-grade risk management infrastructure, the strategies in the left half of this table represent realistic starting points, while SUE and unconstrained cross-sectional momentum should be approached only after building significant quantitative infrastructure.

#### 2.4.2 Critical Limitations

The SUE strategy's 63.9% maximum drawdown during 2007–2026 renders it unsuitable as a standalone approach for most investors [^323^]. The QuantConnect backtest showed that the 2008–2009 crisis "decimated the strategy — if you were running this live, you would have lost nearly two-thirds of your capital." This occurs because earnings momentum strategies load heavily on cyclical companies that report the largest surprises during expansions but suffer devastating revisions during contractions.

Three practical limitations further constrain accessibility. Data intensity: real-time earnings and analyst revision data require expensive subscriptions ($500–$2,000/month). High turnover: monthly rebalancing generates 100%+ annual turnover with significant tax drag. Clustering risk: earnings announcements concentrate in the weeks following quarter-end, exposing the portfolio to concentrated event risk.

Earnings momentum works as a signal but fails as a standalone strategy without robust risk management. Combining SUE ranking with a volatility-scaling overlay and an absolute momentum market filter could capture much of the predictive power while containing drawdowns. Even then, the data requirements place this strategy firmly in the domain of committed quantitative investors.

The momentum toolkit spans simplicity to sophistication. GEM requires 30 minutes and a single trade monthly. Sector rotation adds modest complexity across three ETFs. Cross-sectional momentum demands more capital but accesses the deepest academic evidence. Earnings momentum offers the highest raw returns but the most extreme risks. The common thread is that momentum is a family of approaches sharing a behavioral foundation: investors underreact to new information, and prices adjust gradually. This underreaction creates persistent trends that momentum strategies exploit — but the same persistence also creates the occasional catastrophic reversal that makes risk management essential rather than optional.
