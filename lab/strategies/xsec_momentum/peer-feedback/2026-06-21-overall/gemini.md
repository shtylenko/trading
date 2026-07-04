This is an exceptionally well-framed strategy document. It reads exactly like a professional quantitative research memo — intellectually honest, deeply rooted in established financial literature, and refreshingly clear about its limitations.

The shift from naive momentum to residual momentum is a classic, institutionally sound evolution. You are directly addressing the "momentum crash" phenomenon (as famously documented by Daniel and Moskowitz) where naive momentum portfolios inadvertently load up on high-beta names in bull markets and get crushed when the market sharply rebounds.

Here is an objective breakdown of the strategy's strengths, along with a few structural vulnerabilities you should stress-test before scaling.

## What Works Exceptionally Well

* **The Signal Design:** Using the information ratio of the residual `mean(ε) / std(ε)` is excellent. Standard momentum just looks at the endpoint. By scaling the idiosyncratic drift by its volatility, you are essentially selecting for "smooth" stock-specific trends rather than volatile, headline-driven jumps.
* **The Skip-Month:** Excluding the most recent 21 days is a textbook best practice to avoid the short-term mean reversion anomaly. Including it would have introduced negative edge into your signal.
* **No Stop-Losses:** Avoiding arbitrary stops and profit targets shows strong quantitative discipline. Price-based stops on time-based anomalies usually just destroy the statistical edge and introduce backtest overfitting.
* **The Honest Framing:** Setting the expectation at a ~1.0 Sharpe and acknowledging the lack of a "sealed" out-of-sample (OOS) test for this specific variant is the mark of a rigorous researcher. You aren't fooling yourself with a 2.5 Sharpe pipe dream.

---

## Vulnerabilities & Areas for Refinement

While the logic is sound, the execution mechanics of this strategy introduce some friction points that the backtest might not fully capture.

### 1. High Turnover & Execution Drag

A 50-name equal-weight portfolio rebalanced every 20 trading days implies massive turnover. If your rank correlation from month to month is low, you might be replacing 15 to 25 names every month.

* **The Risk:** At 300%+ annual turnover, slippage and bid-ask spreads will eat heavily into that 1.0 Sharpe. The $10M average daily volume filter ensures you *can* trade them, but it doesn't mean trading them is cheap.
* **The Fix:** You might want to test a **turnover buffer** (e.g., if a current holding drops to rank 60, don't sell it to buy the new rank 50).

### 2. The Tax Hammer

Unless this strategy is being run inside a tax-advantaged account (like an IRA), it will generate almost exclusively short-term capital gains. A ~1.0 Sharpe strategy can quickly become a ~0.6 Sharpe strategy after taxes, making buy-and-hold index investing mathematically superior on an after-tax basis.

### 3. The CAPM Limitation (Single Factor)

You correctly identified this in your risk section. By only stripping out SPY (market beta), your "idiosyncratic" residual might just be secretly loading up on other known risk factors.

* **The Risk:** If small-cap value is having a massive year, your screener might just fill up with small-cap value stocks because their sector momentum is bypassing your CAPM filter.
* **The Fix:** Moving to a multi-factor regression (like the Fama-French 3-factor model, adding Size and Value) would give you a much purer stock-specific residual.

### 4. The Survivorship Caveat

You mentioned that pre-2022 data is partly survivorship-lifted. For a strategy buying the top 50 stocks out of thousands, survivorship bias is fatal in backtesting. Bankrupt or delisted companies often had high volatility and momentum right before they died; if they aren't in your historical data set, your backtest is artificially avoiding landmines. You must secure a clean, delisting-inclusive dataset before trusting the pre-2022 numbers.

---

## The Verdict

As a concept, **x03 is robust, academically validated, and well-constructed.** It successfully isolates the core behavioral anomaly (investors slowly pricing in good news) from the market noise.

Your next big hurdle isn't finding a better signal—it's proving that execution costs, turnover, and taxes won't bleed the alpha dry in a live environment.