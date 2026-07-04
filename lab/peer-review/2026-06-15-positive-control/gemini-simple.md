This is a classic, agonizing problem in quantitative engineering. When you build a rigorous validation pipeline with Walk-Forward Optimization, Probability of Backtest Overfitting (PBO) penalties, and a Deflated Sharpe gate, you essentially build a machine designed to destroy noise. The problem is that financial data is 99% noise.

A validator that rejects everything is structurally indistinguishable from a broken validator. You absolutely need a positive control to calibrate the sensitivity of your pipeline.

Here are the direct answers to your two hard questions, followed by the most viable real-world candidates that fit your strict intraday mold.

### 1. Do any robustly-proven equity edges actually fit long-only same-day intraday?

**Candidly: Very few, and they are exceptionally thin.**

Your framework is aimed at a regime where durable, mechanical edges are inherently scarce. By constraining the strategy to **long-only, purely intraday** (no overnight risk), you are structurally locking yourself out of the documented equity risk premium, which overwhelmingly accrues overnight (the overnight drift anomaly). By forbidding shorting, you cannot build true cross-sectional factor portfolios (like momentum or value) which rely on the spread between the long and short legs to neutralize market beta.

What is left in the long-only, strictly intraday space? You are essentially left trying to capture **intraday momentum anomalies** or **liquidity/execution footprints** left by large institutions.

Because of this, it is entirely plausible—even likely—that your pipeline is functioning perfectly. The strategies you’ve tested so far are getting killed because intraday, long-only equities for liquid names is a highly arbitrated arena dominated by HFTs and market makers. The transaction costs, spread crossing, and lack of overnight premium typically grind these strategies to a negative Sharpe out-of-sample.

### 2. The Case for a Synthetic Positive Control

**I strongly recommend a synthetic control as your primary diagnostic tool.** In fact, it is the only way to isolate pipeline mechanics from market efficiency.

If you use a real-world strategy as a control and it fails, you still don't know if the pipeline is too strict or if the "proven" academic edge was just a fabrication of transaction-cost-ignorant academia.

**How to implement it:**
Inject a known, mathematically defined alpha directly into the historical returns of your universe.

1. **The Signal:** Generate a random sequence $S_t \sim N(0,1)$ for each asset.
2. **The Injection:** Modify the actual intraday return of the assets: $R_{modified} = R_{actual} + (\beta \cdot S_{t-1})$.
3. **Calibration:** Tune $\beta$ so that a naive backtest of trading this signal yields a pre-cost, in-sample Sharpe of around $0.8$ or $1.0$.

Run this synthetic strategy through your combinatorial filter, the leave-one-year-out walk-forward, and the Deflated Sharpe gate. **If your pipeline rejects this synthetic strategy, your pipeline is broken.** Your PBO penalties might be too draconian, or your combinatorics are severely overfitting the noise and missing the true injected signal. If it passes the synthetic control but rejects all your real strategies, your pipeline is fine—the market is just hard.

---

### The Real-World Shortlist (Ranked)

If you still want to run a real-world positive control through the system, here are the most robust candidates that fit your exact constraints. I am leaning heavily into well-documented intraday structural dynamics.

#### 1. Intraday Post-Earnings Announcement Drift (PEAD) / "Gap and Go"

* **Mechanism:** When a company releases a massive earnings surprise overnight, institutional managers cannot buy their full desired allocation in the pre-market. They use algorithmic execution (TWAP/VWAP) to scale in throughout the regular session, creating a persistent, predictable intraday buying pressure.
* **The Exact Rule:**
* *Ranking (09:35):* Rank the universe by overnight gap percentage (Open / Prior Close) *multiplied* by pre-market relative volume.
* *Filter:* Only take the top 5-10 names that gapped up > 4%.
* *Entry (09:35):* Go long if the first 5-min bar (09:30-09:35) closes green (Close > Open).
* *Stop:* Low of the opening 5-min bar.
* *Target:* None (let winners run).
* *Time-Exit:* 15:55 ET.


* **Evidence:** PEAD is one of the oldest, most robust anomalies in finance (originally Ball & Brown, 1968). Intraday momentum on earnings days has been widely replicated in market microstructure literature. Effect size is a low win rate (~40-45%) but high R/trade.
* **Failure Modes:** Regime dependence. In heavy bear markets, earnings gaps are often aggressively faded (sold into). Over time, HFTs have compressed the time it takes for prices to adjust, pushing more of the drift into the opening auction.
* **Fit Grade:** **Native.** Fits perfectly into your 09:35 mechanical setup.

#### 2. Conditioned Opening Range Breakout (ORB)

* **Mechanism:** The opening 30 minutes of the market represent intense price discovery. A breakout from this range, specifically when aligned with broader sector strength, signals that directional institutional volume has overwhelmed opening volatility.
* **The Exact Rule:**
* *Ranking (09:35):* Since ORB requires a longer wait, use the 09:35 decision time to simply build the watchlist. Rank names by their 5-min relative volume and sector momentum from the prior day. Select the top 10.
* *Entry (trigger after 10:00):* Wait for the 30-minute High (highest high from 09:30-10:00). Enter a stop-limit buy order $0.01 above this high.
* *Stop:* The VWAP at the time of entry, or the 30-minute Low (wider risk).
* *Target:* 2R or 3R.
* *Time-Exit:* 15:50 ET.


* **Evidence:** Plain ORB strategies decay to zero post-costs. However, *conditioned* ORBs (e.g., trading only the strongest stocks in the strongest sectors on high relative volume) maintain a slight, grinding edge. It is a staple in systematic intraday trend-following.
* **Failure Modes:** False breakouts are the strategy killer. Choppy, range-bound market regimes (like much of 2022) will cause a severe drawdown as breakouts fail and reverse.
* **Fit Grade:** **Minor-adaptation.** The asset selection happens at 09:35, but the actual trade execution is contingent on a price trigger later in the morning.

#### 3. The Midday VWAP Pullback

* **Mechanism:** Institutional execution algorithms are frequently benchmarked to the Volume Weighted Average Price (VWAP). When a stock with a strong morning trend pulls back to its VWAP in the lower-volume midday session, execution algos often step in to buy, providing structural support.
* **The Exact Rule:**
* *Ranking (09:35):* Identify top 10 stocks with the highest pre-market volume and a positive gap.
* *Entry:* Track the asset. If the price remains *above* VWAP for the entire first hour, place a limit buy order at the VWAP price starting at 10:30 ET.
* *Stop:* 1 Average True Range (ATR) below VWAP.
* *Target:* The morning high.
* *Time-Exit:* 15:45 ET.


* **Evidence:** Microstructure research confirms VWAP acts as a significant intraday support/resistance level due to algorithmic participation.
* **Failure Modes:** Very low signal capacity. The bounce off VWAP is often just pennies, meaning slippage and commissions can easily turn a gross-positive system into a net-negative one. It is also highly vulnerable to afternoon market-wide selloffs.
* **Fit Grade:** **Minor-adaptation.** Again, selection at 09:35, but execution is an anchored limit order waiting for a specific midday reversion condition.

**Bottom Line:** Your pipeline is likely doing exactly what it was built to do. If you want to know for sure, build the synthetic control. If you want to test reality, run the Intraday PEAD—if anything survives your Deflated Sharpe gate in a long-only intraday mold, it will be the gap-and-go.