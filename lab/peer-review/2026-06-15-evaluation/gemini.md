Used tool: manage_task

This is an exceptionally well-constructed evaluation pipeline, but it has several structural vulnerabilities that could lead you to prematurely kill a real edge or mathematically hallucinate a fake one. 

Here is the adversarial review you requested, targeting the specific failure modes, hidden assumptions, and statistical traps in your methodology.

### 1. The False Negative Vector (Why you likely killed a real edge)
Your pipeline forces a **regime-brittle dynamic selection policy** and conflates it with the existence of a global edge. By using a 1-year lookback (Fold 1: 2022) to select a single "argmax" combo, you mathematically guarantee the selection of a regime-overfit model (`spy_weak_regime` is textbook bear-market overfitting). When you apply that to 2023 (a completely different macro regime), it violently fails.

You concluded "gap-and-go has no robust edge," but you actually proved "a 1-year trailing argmax selector cannot survive a macro regime shift." The fact that `gap_floor_3 + rvol_min_1_5` was the best in-sample across all three years (2022-2024) and worked brilliantly in Fold 2 (when trained on a blended 2022-2023 regime) suggests a structurally robust edge *does* exist. Your demand that a dynamically selected parameter must be positive in *every* test fold—when those folds represent diametrically opposed market regimes—creates an astronomically high false-negative rate.

### 2. The False Positive Vector (The Substitution Lottery)
If this pipeline *had* passed, I would immediately suspect the **Top-10-after-filter Substitution Lottery**.
When a filter excludes Stock A, it doesn't just save Stock A's PnL; it promotes Stock K (the 11th highest gap) into the active portfolio. Your optimizer credits the *filter* for Stock K's PnL, even though the filter evaluated Stock A, not Stock K. 

With 46 combos, an optimizer will easily find a spurious filter whose sole actual effect is benching stocks on the exact days that the 11th/12th bench-players happen to have 5R outlier right-tail moves. This introduces a chaotic, non-monotonic variance vector that the optimizer will ruthlessly fit to, blessing a combo that has zero predictive power but happened to unlock lucky bench substitutions.

### 3. PBO=0.32 alongside WF-Fail: A Coherent Diagnosis
This is not a paradox; it is an exact diagnosis of your problem.
- **PBO < 0.5** proves your performance matrix has genuine structural signal. The in-sample hierarchy of these 46 combos has predictive power for their out-of-sample hierarchy on average. It is not pure noise.
- **WF-Fail** proves that your specific extraction mechanism (a short-window trailing argmax on disjoint regimes) destroys that signal.

PBO says the alpha is there globally. Walk-Forward proves you cannot harvest it by aggressively chasing the most recent 12-month regime peak. The gates are misaligned: PBO evaluates the landscape, while WF evaluates a specific (and flawed) dynamic trading policy.

### 4. Attack on the Objective Function (Mean R)
Your objective function (`Mean R - 0.02 * tail_share`) is a **Variance Maximizer**.
Because you use a hard floor (50 trades/window) rather than a continuous risk penalty, the optimizer will strip away trades until it hits the floor with a lucky, high-variance sample. If Combo X has 1000 trades at 0.03 Mean R, and Combo Y has 55 trades at 0.08 Mean R, the objective picks Y. But Y's 0.08 is purely standard error noise. The 0.02 tail penalty is mathematically microscopic (a 50% tail share only deducts 0.01 R). By not dividing by standard deviation, you systematically force the optimizer to prefer small, fragile, lucky subsets over broad, reliable edges.

### 5. Attack on the Top-10-after-filter Mechanic
As noted in #2, this mechanic mathematically breaks the isolation of your features. The "alpha" of your filter becomes heavily confounded by the cross-sectional distribution of the day's baseline gap sizes. If you want to evaluate if a filter *predicts* performance, you must evaluate it on a fixed roster. Scoring it *after* the cap means you are optimizing the interaction effect of the filter AND the gap-size ranking, which launders a massive degree of freedom directly into the objective function.

### 6. Attack on the Subset Invariant (Independent Simulation)
Assuming independent execution with a fixed 1% risk per trade is a fatal simplification for risk management. 10 gap-up longs on the same day are highly correlated. If the SPY drops violently at 10:00 AM, all 10 positions will likely get stopped out in the same minute. Your per-trade independence assumes a smooth Gaussian distribution of returns, masking the massive left-tail portfolio drawdowns (e.g., a sudden -10R day). 

It also assumes infinite instantaneous liquidity—if 5 breakouts trigger at exactly 09:35:01, can your capital fill all 5 without fatal slippage? The invariant holds for *row-masking speed*, but it produces a wildly distorted view of portfolio-level reality.

### 7. Missed Leakage Vectors
- **The Halt / Delayed Open Leak:** A stock gaps up 10% but is halted for volatility and doesn't print its first trade until 09:43. If your data blindly builds a "09:30-09:35 candle" using the previous day's close or late prints, you are evaluating an impossible trade.
- **Slippage on the Breakout:** You enter on the "breakout above the first candle's high". Order books on gap-and-go micro-caps (even >$10, 1M adv) are incredibly thin right at the breakout penny. Your simulator assumes you get filled at exactly `high + $0.01`. In reality, the next print might be 2% higher, instantly destroying your 1R math (your stop distance is now larger, and target harder to reach).
- **The Reverse-Split Trap:** You drop split dates, but what if your corporate action database misses one? An unadjusted 1:10 reverse split creates an artificial 900% gap, bypassing `gap_floor_3` and guaranteeing a top-10 spot based on data error, not market reality.

### 8. The ONE Additional Pre-Registered Experiment
**Run a Global Pooled Holdout.**
Bypass the regime-brittle fold selection. Train on the *entire* pooled 2022-2024 dataset. Select the single best combo (which is highly likely `gap_floor_3 + rvol_min_1_5`). Test exactly that combo on the sealed 2025 dataset.

*Why this isn't goalpost-moving:* You already established via PBO that the IS matrix has structure. The failure was the fold design. Testing the global 3-year winner on a completely unseen 1-year holdout is the most academically standard test of a global edge. If it fails 2025, the family is truly dead. If it passes, your edge is real but requires long-term pooled training to stabilize.

### 9. The Single Highest-Leverage Fix
Change the objective function to a **Risk-Adjusted Daily Portfolio Metric** (e.g., Daily Portfolio Information Ratio or t-statistic of daily returns).

Instead of summing independent R's, group the filtered trades by day, sum the R for that day (up to 10), and calculate the mean and standard deviation of those *daily portfolio returns*. Optimize for `Mean(Daily R) / StdDev(Daily R)`. 

This single change fixes three problems at once: it heavily penalizes low trade counts (zero-trade days drag down the mean and increase variance), it penalizes highly correlated stop-outs (which create massive daily variance), and it stops the optimizer from chasing the substitution lottery.