# **Diagnostic Evaluation of Systematic Intraday Equity Pipelines: Empirical and Synthetic Positive Controls**

The implementation of a deliberately strict validation pipeline—incorporating leak-free feature capture, pre-registered combinatorial filter search, leave-one-year-out walk-forward optimization, Probability of Backtest Overfitting (PBO) assessment, Deflated Sharpe Ratio (DSR) gating, and a sealed out-of-sample holdout—represents the gold standard in modern quantitative strategy research1. However, a validation architecture that uniformly rejects every candidate strategy presents an epistemological crisis. It becomes impossible to distinguish between a search space genuinely devoid of alpha and a Type II error (false-negative) machine calibrated with overly punitive statistical hurdles. In quantitative finance, a pipeline without a calibrated detection threshold is functionally indistinguishable from a random number generator that only outputs zeroes.  
To diagnose this structural failure, a positive control is mandatory. This report provides an exhaustive architectural review of your specific trading constraints, directly answers your two core structural questions regarding the nature of intraday equity edges, and provides a ranked shortlist of empirical and synthetic positive controls designed specifically to test the sensitivity and validity of your pipeline.

## **Part I: The Structural Reality of the Intraday Framework (Hard Question 1\)**

The first fundamental question to address is whether robustly-proven equity edges actually fit a long-only, same-day intraday mold, or if the "bulletproof" effects live in holding-period or long/short regimes that your framework structurally cannot express.  
The analytical conclusion is unequivocal: the vast majority of bulletproof, robustly-proven equity edges cannot be expressed within a long-only, same-day intraday framework. Your validation pipeline is pointed at a microstructural regime where durable, risk-adjusted edges are inherently thin, fleeting, and highly susceptible to transaction costs. The fact that your pipeline kills every strategy is likely an accurate reflection of financial reality, compounded by a statistical hurdle (the Deflated Sharpe Ratio) that is mathematically mismatched to the capacity of the intraday time horizon. If you demand a Deflated Sharpe Ratio designed to filter out monthly rebalanced portfolio noise, but apply it to intraday noise, no valid intraday edge will survive2.  
To understand why your framework is systematically starved of edge, we must dissect the empirical literature surrounding overnight versus intraday returns, institutional flow, and the segmentation of classic market anomalies.

### **The Overnight Premium and Intraday Reversal**

The most critical headwind your framework faces is the phenomenon documented extensively in asset pricing literature as the "Tug of War" between heterogeneous investor clienteles4. Research covering the past thirty years demonstrates that nearly 100% of the historical equity premium in the United States stock market has been earned overnight, specifically from the market close to the subsequent market open7. In stark contrast, the average intraday return (from open to close) for the broader market has historically been flat or slightly negative7.  
By restricting your strategy to long-only intraday executions, you are structurally excluding the entirety of the equity risk premium. You are initiating trades in a time window where the unconditional expected return of the market is zero. Furthermore, the overnight and intraday periods are dominated by different participants. Overnight price action is heavily influenced by retail attention, public news dissemination, and sentiment, which frequently results in gap-ups at the open8. However, the intraday session is dominated by institutional arbitrageurs and market makers who actively trade against this overnight price pressure, resulting in persistent daytime reversals11. Because your framework prohibits short selling, you are mathematically barred from capitalizing on the most robust intraday phenomenon: the institutional fading of retail-driven overnight gap-ups. You are forced to either buy the top of a gap-up (fighting the structural reversal) or buy overnight losers (attempting to catch a falling knife)8.

### **The Segregation of Classic Anomalies**

When classic, bulletproof anomalies—such as Cross-Sectional Momentum, Value, Profitability, and Post-Earnings Announcement Drift (PEAD)—are decomposed into their intraday and overnight components, it becomes clear that these factors are entirely incompatible with your execution constraints.

| Anomaly Factor | Dominant Return Period | Intraday Behavior | Compatibility with Framework |
| :---- | :---- | :---- | :---- |
| **Cross-Sectional Momentum** | Overnight | Negative (Reversal) | **Incompatible.** Momentum profits accrue entirely overnight. Intraday, momentum exhibits a negative premium4. |
| **Value & Profitability** | Intraday | Positive (Accrual) | **Incompatible.** While they accrue gradually over the trading day, they incur massive negative returns overnight, requiring long-term holds to capture the net premium15. |
| **Short-Term Reversal** | Overnight | Positive (Fading) | **Incompatible.** Short-term reversal strategies generate their profits entirely overnight as liquidity providers are compensated for absorbing closing imbalances4. |

If you attempt to trade traditional momentum long-only on an intraday basis, you are trading directly against the structural mean-reversion of institutional order flow4. The market makers who provided liquidity at the open spend the remainder of the day unwinding their inventory, dragging the price back toward its fundamental anchor8.

### **Intraday Reversals and Limit-to-Arbitrage**

Individual equities exhibit sharp intraday return reversals, particularly in the final thirty minutes of the trading day. A stock that experiences positive price pressure early in the day is statistically highly likely to fade into the close13. This "end-of-day reversal" is robust across various market capitalizations and liquidity profiles. It is driven by attention-induced purchases by retail investors early in the day, followed by risk management and inventory offloading by short-sellers and market makers as the session concludes13.  
Consequently, your pipeline is not necessarily broken. It is operating with high fidelity by rejecting strategies that lack sufficient edge to overcome the microstructural friction of the intraday regime. Intraday long-only equity trading on liquid names is a zero-sum environment dominated by high-frequency market makers capturing the bid-ask spread. For an edge to survive your combinatorial search, walk-forward out-of-sample validation, and the Deflated Sharpe gate, it would need a sustained, pre-cost annualized Sharpe ratio of roughly 1.5 to 2.5. Such sustained, low-volatility Sharpe ratios rarely exist in directional, long-only intraday trading without massive leverage, which your ![][image1]\-multiple risk metric inherently throttles1.  
The finding that "everything gets killed" is, in itself, an accurate empirical discovery regarding the viability of systematic long-only intraday trading on generic feature sets.

## **Part II: The Case for a Synthetic Positive Control (Hard Question 2\)**

The second fundamental question asks whether a synthetic positive control—injecting a known, modest, leak-free predictive signal into the historical dataset—should be utilized to verify the pipeline's detection power.  
The unequivocal recommendation is **yes**. A synthetic positive control is the only mathematically sound methodology to test the Type II error rate (False Negative rate) of a highly constrained validation pipeline. Relying solely on empirical controls is dangerous because financial markets are non-stationary; if an empirical control fails your pipeline, you cannot definitively know if the pipeline's mathematics are flawed, or if the empirical edge simply decayed during your 2022-2024 search window due to alpha decay16.  
By injecting a synthetic alpha into the data, you establish an absolute, irrefutable ground truth. You control the exact effect size, the win rate, the holding period, and the heteroskedasticity of the returns.

### **Diagnostic Capabilities of the Synthetic Injection**

**1\. Calibrating the Deflated Sharpe Ratio (DSR)** The DSR formula is designed to penalize the maximum observed Sharpe ratio based on the number of independent trials conducted during your combinatorial search2. If your pre-registered combinatorial filter evaluates 10,000 parameter combinations, the expected maximum Sharpe under the null hypothesis (pure luck) is inherently high. If you inject a synthetic signal with a true, verifiable out-of-sample Sharpe of 1.2, your DSR gate might still reject it because the multiple-testing penalty is calibrated too severely for the intraday domain. A synthetic control allows you to tune the DSR threshold so that it accepts mathematically valid, modest edges without demanding impossibly high returns3.  
**2\. Evaluating the False Discovery Rate (FDR)** The False Discovery Rate measures the proportion of strategy configurations selected as "good" that are actually false positives resulting from data mining3. By mixing synthetic "true" signals with pure noise features, you can empirically verify if your combinatorial filter accurately isolates the injected signal without overfitting to the noise3. If your pipeline selects a noise feature over the injected true signal, your feature selection algorithm is structurally flawed.  
**3\. Sanity-Checking Walk-Forward Integrity** Walk-forward optimization is notoriously difficult to implement without introducing subtle look-ahead biases or index-shifting errors19. If you inject a regime-independent, stationary signal into the 2022-2024 dataset, and the pipeline fails to pass it through to the sealed 2025 holdout year, you instantly know your walk-forward optimization logic contains a structural flaw. Conversely, if the synthetic signal survives the entire pipeline and matches your theoretical expectation in the sealed holdout, you have definitive proof that the pipeline is mechanically sound17.

### **Implementation Methodology for the Synthetic Control**

To ensure the synthetic control respects your strict execution mold (09:35 entry, EOD exit), it must be constructed carefully to avoid structural data leakage.

1. **Perturbation of Returns:** Do not alter the actual OHLCV data of the equities, as this will destroy the covariance matrix and market beta of the universe17. Instead, create a synthetic technical indicator. Let ![][image2] be the realized open-to-close return of a stock on day ![][image3]. Create a synthetic feature ![][image4] such that ![][image5], where ![][image6] is normally distributed noise with mean zero and variance ![][image7].  
2. **The Mechanical Rule:** The strategy logic dictates that if ![][image4] (which is "calculated" at 09:35 using the synthetic historical data) exceeds a threshold ![][image8], the system buys at 09:35 and holds to the regular session close.  
3. **Signal Calibration:** Adjust the variance of the noise parameter ![][image6] until the strategy yields a pre-cost Sharpe ratio of exactly 1.5 across the 2022-2024 period. This represents a robust but highly realistic modest edge.  
4. **Pipeline Execution:** Feed this synthetic feature alongside dozens of actual noise features (e.g., standard moving averages, RSI) into your combinatorial search.  
5. **Interpretation:** If your pipeline rejects a mathematically guaranteed Sharpe 1.5 strategy, your validation gates—specifically the Probability of Backtest Overfitting (PBO) and the Deflated Sharpe Ratio—are calibrated for a theoretical market that does not exist in intraday equities. You must lower the DSR penalty or restrict the size of your combinatorial search space to reduce the family-wise error rate penalty2.

## **Part III: Empirical Positive Controls (Ranked Shortlist)**

If you must test the pipeline against financial reality rather than a synthetic injection, the following effects represent the most robust, documented anomalies that fit—or can be minimally adapted to—your long-only, 09:35 execution, same-day intraday mold.  
These strategies are ranked strictly by their ability to survive the structural disadvantages of intraday trading outlined in Part I. They focus heavily on limits to arbitrage, liquidity provision, and slow information diffusion, which are the only mechanisms capable of sustaining an intraday edge.

### **1\. Relative Volume Opening Range Breakout (RVOL-ORB) on "Stocks in Play"**

This is the absolute strongest empirical candidate for your specific constraints. Standard Opening Range Breakouts (ORB) applied universally to the equity market fail because they lack statistical significance; the opening range is mostly noise20. However, isolating the ORB solely to stocks exhibiting massive idiosyncratic relative volume (RVOL) captures a structural limit-to-arbitrage21. When major fundamental news hits, institutional capital cannot fulfill its entire order block at the open without causing massive, unacceptable price impact. This creates a directional intraday imbalance as institutions algorithmically slice their orders (e.g., TWAP or VWAP execution) throughout the day, creating a persistent trend from the open to the close22.

| Feature | Detailed Specification |
| :---- | :---- |
| **Name** | Relative Volume Opening Range Breakout (RVOL-ORB) |
| **Economic Mechanism** | Institutional volume constraints and slow information digestion following fundamental catalyst shocks. Massive order imbalances prevent immediate price discovery, resulting in a persistent intraday trend22. |
| **Fit Grade** | **Native**. Perfectly matches the 09:35 decision time, the long-only restriction, and the End-of-Day (EOD) time-exit constraints. |
| **Evidence & Size** | Documented comprehensively by Zarattini, Barbon, and Aziz (2024, Swiss Finance Institute). The study achieved an annualized alpha of 36% and a post-cost Sharpe ratio of 2.81 (2016-2023) on a highly liquid universe22. It is entirely uncorrelated to the S\&P 500\. |
| **Failure Modes** | Susceptible to execution slippage on stop-market entry orders. Prone to failure in low-VIX, low-volume market regimes where early morning "fake-outs" trigger entries before reversing into mean-reverting chop20. |

**The Exact Rule in Your Mold:** The strategy relies on isolating stocks that detach from the broader market index due to high relative volume, ensuring the price action is driven by idiosyncratic order flow rather than broader market beta.

* **Admission/Ranking Signal (Computable at 09:35):**  
  * *Universe:* Point-in-time US equities (NYSE and NASDAQ).  
  * *Filters:* Prior day Close \> $5; 14-day Average Daily Volume \> 1,000,000 shares; 14-day Average True Range (ATR) \> $0.5021.  
  * *Signal (RVOL):* Calculate the total volume traded during the first 5-minute bar (09:30-09:35). Divide this by the 14-day rolling average of the volume traded specifically in the 09:30-09:35 window21.  
  * *Ranking:* Rank the filtered universe by RVOL descending. Select the top 10 stocks where RVOL ![][image9] 1.5 (150% of normal opening volume).  
* **Directional Filter:** The 09:30-09:35 candle *must* be bullish (Close \> Open). If it is bearish, the stock is discarded for the day. This filter satisfies your hard constraint of long-only trading21.  
* **Entry Trigger:** Place a Buy Stop order exactly at the High of the 09:30-09:35 candle. The trade is executed mechanically if the price breaks the high during the remainder of the session22.  
* **Stop Loss:** Placed at the entry price minus (0.10 ![][image10] 14-day ATR). This tight, volatility-adjusted stop allows for highly asymmetrical risk-to-reward ratios22.  
* **Target:** None. The strategy relies on letting profits run to capture fat-tailed intraday trends.  
* **Time-Exit:** Market-on-Close (MOC) at 16:00 ET.

### **2\. The Intraday Reversal of Overnight Noise (Negative Gap Fade)**

Because your long-only constraint prevents you from shorting irrational gap-ups, you must focus on buying gap-downs. However, buying all gap-downs indiscriminately is a recipe for disaster, as many are driven by severe fundamental downgrades. The alpha exists in buying gap-downs driven by *uninformed overnight retail noise* or inventory imbalances, which are subsequently corrected by daytime institutional arbitrageurs providing liquidity8.

| Feature | Detailed Specification |
| :---- | :---- |
| **Name** | Overnight-Intraday Reversal (Long Leg) |
| **Economic Mechanism** | Liquidity provision. Market makers taking on inventory during the highly illiquid overnight and pre-market sessions demand a premium. As regular hours volume enters and liquidity deepens, the price reverts to fair fundamental value8. |
| **Fit Grade** | **Minor Adaptation**. The academic effect is typically traded as a Long/Short portfolio. Adapted here to exclusively trade the Long leg by buying overnight losers that show stabilization. |
| **Evidence & Size** | Documented by Lou, Polk, and Skouras (2019) and Wang et al. (2020). The overnight-intraday reversal yields Sharpe ratios 2 to 5 times larger than standard short-term reversal strategies across multiple asset classes9. |
| **Failure Modes** | "Catching a falling knife." If the overnight gap down is driven by a material SEC filing, an earnings miss, or an FDA trial rejection, the stock will continue to trend downward intraday, ignoring the reversal effect. |

**The Exact Rule in Your Mold:** To filter out fundamental disasters and isolate liquidity-driven gaps, the strategy requires confirmation of price stabilization at the open.

* **Admission/Ranking Signal (Computable at 09:35):**  
  * *Universe:* S\&P 1500 constituents. This ensures a high level of institutional presence and baseline liquidity, which is required for the reversal to materialize.  
  * *Filters:* The stock must exhibit an overnight gap down (Open price vs. prior day Close) between \-2% and \-5%. Gaps smaller than 2% are market noise; gaps larger than 5% are almost exclusively fundamental news events. *Crucial leak-free constraint:* Exclude any stock with an earnings announcement scheduled in the prior 24 hours.  
  * *Signal (Stabilization):* Intraday price action must show immediate stabilization. The 09:30-09:35 candle must be bullish (Close \> Open) or form a Doji, indicating that the pre-market selling pressure has exhausted and buyers are stepping in.  
  * *Ranking:* Rank eligible candidates by the magnitude of the negative gap (largest gap down ranked first). Select the top 5\.  
* **Entry Trigger:** Market Buy at 09:35:01.  
* **Stop Loss:** Placed at the Low of the 09:30-09:35 candle minus 1 cent. The outcome is measured strictly in ![][image1].  
* **Target:** The previous day's regular session closing price (commonly referred to as the "Gap Fill" in technical literature)20.  
* **Time-Exit:** Market-on-Close (MOC) if the target is not hit during the session.

### **3\. Intraday Systematic Risk Momentum**

At a daily or monthly frequency, standard asset pricing anomalies perform well. However, traditional momentum fails utterly on an intraday basis due to the dominance of reversal effects30. However, recent research uncovers that the *systematic risk component* of stocks—rather than their idiosyncratic returns—exhibits strong intraday momentum due to slow information diffusion and the synchronized rebalancing of institutional arbitrageurs across common factors30.

| Feature | Detailed Specification |
| :---- | :---- |
| **Name** | Intraday Systematic Factor Momentum |
| **Economic Mechanism** | Slow information diffusion and arbitrageur synchronization. Common macro or factor-level news (e.g., a rapid rotation into Value or out of Momentum) is priced into the market gradually over the day as institutional capital rebalances across highly correlated assets31. |
| **Fit Grade** | **Forced Adaptation**. Academics calculate this using cross-sectional regressions every 30 minutes. Adapted here to use proxy factor ETFs to measure the dominant factor trend in the first 5 minutes of the day. |
| **Evidence & Size** | Gao et al. (2024). Systematic return momentum holds intraday and yields significantly higher returns and Sharpe ratios than traditional Jegadeesh and Titman (JT) momentum strategies30. |
| **Failure Modes** | Highly susceptible to midday macroeconomic data releases (e.g., 10:00 AM Consumer Confidence, 14:00 FOMC rate decisions) which can instantly invert previously established factor trends. |

**The Exact Rule in Your Mold:** Because running rolling cross-sectional regressions on 1,500 stocks at 09:35 is computationally heavy and prone to look-ahead bias if not implemented flawlessly, we use liquid factor ETFs as a proxy for the systematic component.

* **Admission/Ranking Signal (Computable at 09:35):**  
  * *Signal Construction:* Calculate the 09:30-09:35 return of major US factor ETFs (e.g., MTUM for Momentum, VLUE for Value, QUAL for Quality, SIZE for Small Cap). Identify the highest-performing factor ETF in that 5-minute window.  
  * *Universe:* Pre-calculate the 30-day trailing beta of all 1,500 universe stocks strictly against the winning factor ETF using prior daily closing data.  
  * *Ranking:* Rank the universe stocks by their beta to the winning factor. Select the top 10 highest-beta stocks.  
  * *Filter:* The individual stock must also have a positive absolute return in the 09:30-09:35 window to confirm it is participating in the systemic move.  
* **Entry Trigger:** Market Buy at 09:35:01.  
* **Stop Loss:** 1.5 ![][image10] 14-day ATR below the entry price to allow for intraday volatility while capping tail risk.  
* **Target:** None. Capture the full systematic trend.  
* **Time-Exit:** Market-on-Close (MOC).

### **4\. Post-Earnings Announcement Drift (Intraday Accumulation Phase)**

Post-Earnings Announcement Drift (PEAD) is arguably the most extensively documented anomaly in accounting and finance literature, characterized by the tendency of a stock's cumulative abnormal returns to drift in the direction of an earnings surprise for weeks or months33. While traditionally a multi-day hold, the highest velocity portion of the drift often occurs on "Day 1" (the first regular trading session following an overnight or pre-market earnings release), as institutions accumulate positions33.

| Feature | Detailed Specification |
| :---- | :---- |
| **Name** | Intraday Post-Earnings Announcement Drift (PEAD) |
| **Economic Mechanism** | Investor underreaction to earnings news. Behavioral biases (conservatism) and limits to arbitrage prevent the market from instantaneously pricing in the full magnitude of the earnings surprise at the open, leading to persistent daytime buying pressure34. |
| **Fit Grade** | **Minor Adaptation**. Standard PEAD holds the asset for 60 days. This adaptation isolates the "Day 1" intraday return exclusively33. |
| **Evidence & Size** | Ball and Brown (1968), Bernard and Thomas (1989), and thousands of subsequent replications. The anomaly is universally recognized. While the Day 1 intraday component is smaller than the 60-day drift, it exhibits a highly reliable win rate due to institutional accumulation33. |
| **Failure Modes** | Severe capacity sensitivity. Spreads are exceptionally wide at the open following an earnings release. High institutional algorithmic participation means the alpha decays rapidly in the first 30 minutes of trading36. |

**The Exact Rule in Your Mold:**

* **Admission/Ranking Signal (Computable at 09:35):**  
  * *Universe:* Point-in-time US equities.  
  * *Filters:* The stock must have reported earnings between the previous day's close (16:00 ET) and the current day's open (09:30 ET).  
  * *Signal (Standardized Unexpected Earnings \- SUE):* Calculate the earnings surprise. The stock must fall into the top quintile of SUE for the current earnings season33.  
  * *Filter:* The 09:30-09:35 candle must be bullish, confirming that the market is actively pricing the positive surprise higher, rather than fading it.  
  * *Ranking:* Rank by the magnitude of the SUE. Select the top 5\.  
* **Entry Trigger:** Market Buy at 09:35:01.  
* **Stop Loss:** Low of the 09:30-09:35 candle.  
* **Target:** None.  
* **Time-Exit:** Market-on-Close (MOC).

## **Part IV: Pipeline Diagnostics and Execution Realities**

If you implement the **RVOL-ORB** strategy (Candidate 1\) and your validation pipeline still rejects it, you have successfully isolated the error. The problem does not lie in the lack of an empirical edge; rather, the problem is rooted in the pipeline's statistical calibration and execution assumptions.  
To resolve the issue of the pipeline acting as a false-negative machine, you must examine three specific failure modes endemic to strict validation architectures:  
**1\. The Combinatorial Penalty is Disproportionately High** If your "pre-registered combinatorial filter search" tests thousands of parameter variations (e.g., optimizing the ATR stop multiplier from 0.1 to 3.0 in increments of 0.1), your Deflated Sharpe Ratio (DSR) gate will demand an astronomically high in-sample Sharpe to pass the strategy to the out-of-sample holdout2. Intraday edges on liquid equities rarely exceed a true out-of-sample Sharpe of 1.5 to 2.0. If the DSR penalizes the strategy for exploring a massive search space, it will reject a valid 1.5 Sharpe. *Recommendation: Severely restrict your hyperparameter search space to no more than 10 to 20 logically distinct variations prior to running the walk-forward optimization. This minimizes the family-wise error rate penalty.*  
**2\. Inaccurate Slippage and Spread Modeling** Intraday strategies live or die by their execution assumptions. At 09:35 ET, the bid-ask spread on a highly volatile "Stock in Play" is exceptionally wide. If your backtesting pipeline assumes execution at the exact high of the 5-minute bar for a stop order, or assumes a fixed 1-cent slippage across all volatility regimes, the results will be wildly inaccurate. Conversely, if your pipeline applies a punitive 5 to 10 basis points of slippage to a strategy that only generates 15 basis points of alpha per trade, the pipeline will correctly kill it. Ensure your slippage models are dynamically tied to the ATR and volume of the asset at the specific time of execution.  
**3\. Regime Non-Stationarity (The Holdout Problem)** Your search window encompasses 2022 (a brutal, high-VIX bear market with high correlation), 2023 (a narrow, mega-cap-driven recovery), and 2024 (a broader bull market). If your walk-forward optimization requires a parameter set to be consistently profitable across all three radically different macroeconomic and volatility regimes, it will almost certainly fail20. Intraday dynamics are heavily dependent on market-wide Gamma exposure and the VIX. *Recommendation: Allow your pipeline to pass strategies that are conditionally profitable in specific, mathematically definable regimes (e.g., only trading RVOL-ORB when VIX \> 15), rather than demanding unconditional, all-weather performance across the entire 2022-2024 sample.*

### **Conclusion**

Your initial step should be to implement the **Synthetic Signal Injection**. This will immediately verify whether your Deflated Sharpe and Probability of Backtest Overfitting thresholds are mathematically achievable within the confines of intraday noise. If the pipeline successfully passes the synthetic control, you can proceed to implement the **RVOL-ORB** empirical strategy to test the pipeline's handling of real-world noise, transaction costs, and fat-tailed intraday distributions. If RVOL-ORB is rejected, your pipeline is correctly identifying that the transaction costs and microstructural friction of the long-only intraday regime are too severe for directional alpha to survive without alternative data or high-frequency latency advantages.
