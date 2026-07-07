# Peer Review Feedback: Enhanced Metrics for Comparing Trading Sessions (Skills + LLMs)

**Date:** 2026-07-06  
**Reviewer:** Antigravity (AI Coding Assistant)  
**Status:** Completed Review  
**Target Proposal:** `llm_trader/peer_reviews/2026-07-06-session-metrics/proposal.md`  

---

## Executive Summary

The proposal to expand trading session metrics is **strongly endorsed**. Relying on raw P&L and Win % is a well-known pitfall in quantitative trading, especially for short-horizon momentum strategies where return distributions are heavily skewed (e.g., many small losses and a few outsized winners).Surfacing R-normalized metrics, drawdown/consistency statistics, and LLM-specific execution reliability is essential for selecting the optimal combination of skill version + LLM model.

Below is structured feedback addressing each of the **8 Peer Review Questions** raised in the proposal.

---

## Detailed Feedback on Peer Review Questions

### 1. Prioritization (Valuable vs. Deprioritized Metrics)
In the high-volatility, low-float momentum context of `llm_trader`, we recommend prioritizing the following **6 Core Metrics**:

1. **Expectancy (in R-units)**: 
   * **Priority:** Critical (Rank 1)
   * **Rationale:** Since position sizing is risk-budget based, Expectancy in R ($E_R = \text{mean}(R\_multiples)$) is the single most important metric. It represents the expected return of the strategy per trade in units of risk, allowing apples-to-apples comparisons across different stock prices, sizes, and market regimes.
2. **Profit Factor (PF)**: 
   * **Priority:** Critical (Rank 2)
   * **Rationale:** Defined as `gross_profits / |gross_losses|`. It is highly robust, less sensitive to win-rate noise, and represents the literal payout efficiency of the system.
3. **Void / Unverifiable Rate**: 
   * **Priority:** Critical (Rank 3)
   * **Rationale:** A model with 2.0R expectancy but a 30% void rate (due to rule violations or formatting errors) is unusable. This is a primary proxy for agent reliability and prompt safety.
4. **Max Drawdown (MDD) & Recovery Factor (RF)**: 
   * **Priority:** High (Rank 4)
   * **Rationale:** Recovery Factor ($\text{Net PnL} / \text{Max Drawdown}$) measures how efficiently the strategy recovers from its worst equity drawdown. A strategy with a high RF is much easier to trade and scale.
5. **System Quality Number (SQN)**: 
   * **Priority:** High (Rank 5)
   * **Rationale:** Van Tharp's SQN evaluates the quality of the distribution. It rewards systems that produce consistent, low-variance wins, which is crucial for leverage/sizing.
6. **MFE Capture %**: 
   * **Priority:** Medium-High (Rank 6)
   * **Rationale:** Measures trade management quality (exit timing). It isolates the *execution/management* skill of the LLM from the *entry* quality.

**To Deprioritize:**
* **Win %**: In momentum trading, Win % is often a lagging or misleading indicator. A 35% win-rate strategy with a 3:1 payoff ratio is highly profitable, whereas a 70% win-rate strategy with a 1:3 payoff ratio is a slow leak.
* **Calmar Ratio (Annualized)**: Annualizing returns for intraday morning momentum runs over short, discrete sessions introduces unnecessary assumptions and noise. Use **Recovery Factor (in R)** instead.

---

### 2. Missing Metrics
We recommend adding the following metrics to capture LLM-specific trade-offs and trading behavior:

* **LLM Cost & Token Efficiency (ROI of Intelligence)**:
  * *Metrics:* `cost_per_trade_usd` and `pnl_to_llm_cost_ratio`.
  * *Why:* A model like GPT-4o or Claude 3 Opus might perform slightly better than Gemini 1.5 Flash but cost 100x more in tokens. If the LLM cost eats a significant portion of the P&L, it is economically unviable.
* **Capital Efficiency / Duration**:
  * *Metric:* `average_bars_held` or `minutes_in_trade`.
  * *Why:* Speed is critical in momentum. Capital tied up in stagnant setups increases opportunity cost.
* **Execution slippage sensitivity**:
  * *Metric:* `slippage_risk_score` (calculated as `shares_traded / bar_volume` at fill time).
  * *Why:* If the model scales in with large size on low-volume bars, slippage will decimate real-world performance.

---

### 3. Formulas & Edge Cases

* **SQN with Small N:**
  * **Rule:** SQN should *only* be calculated and shown when $N \ge 30$ (statistically significant sample size).
  * **Fallback:** For $N < 30$, display the raw Sharpe-like ratio of trades: $\frac{\text{mean}(R)}{\text{std}(R)}$ alongside a visual warning label ("Small Sample Size").
* **Drawdown on Single-Day Sessions (Leaves):**
  * For a single leaf, compute **Max Open Drawdown** as the peak-to-trough paper loss relative to either the initial risk or the cost basis during the life of the trade.
* **Synthetic Portfolio Equity Curve for Batches:**
  * Walk the sessions chronologically by historical trade date/time, simulating a portfolio starting capital (e.g., $100,000) where each session takes a fixed risk budget (e.g., 1% or $1,000). Max Drawdown is then computed on this cumulative equity curve.
* **Handling Stood-Down Runs:**
  * Exclude stood-down sessions from trade metrics (Expectancy, PF, SQN, Payoff Ratio) to avoid diluting the stats of active trading behavior.
  * However, track `stood_down_rate = n_stood_down / total_setups` separately as a behavioral discipline signal.

---

### 4. UI/UX Recommendations

To avoid overwhelming the existing chart and timeline views:

* **Collapsible Performance Dashboard:** Add an expandable/collapsible bottom or side panel called **"Session Analytics"** or **"Quant Metrics"**.
* **Visualizing the Equity Curve:** Render a clean, lightweight SVG or lightweight-charts line chart showing the cumulative P&L (in $ or R) over the course of the batch.
* **R-Multiple Distribution Histogram:** A small, interactive bar chart showing the distribution of trade outcomes (e.g., bins: `<-1R`, `[-1R, 0R)`, `[0R, 1R)`, `[1R, 2R)`, `[2R, 5R)`, `>5R`). This immediately reveals if the strategy relies on a few massive winners or consistent small gains.
* **Metric Badges with Hover Explanations:** Display metrics like Expectancy and SQN as color-coded badges (e.g., Green for SQN > 2.5, Yellow for 1.5 - 2.5, Red for < 1.5) with tooltips explaining the math and standard benchmarks.

```
+--------------------------------------------------------+
| [Batch Overview: v2.0.5 - Claude-3.5-Sonnet]           |
|                                                        |
| +----------------+ +----------------+ +--------------+ |
| | Expectancy:    | | Profit Factor: | | SQN:         | |
| | +0.42R [Good]  | | 1.84 [Healthy] | | 2.85 [Good]  | |
| +----------------+ +----------------+ +--------------+ |
|                                                        |
|  Equity Curve (R-units)             R-Hist             |
|   /---\                             |   _              |
|  /     \                            |  | |   _         |
| /       \___                        |  | |  | |        |
|             \                       +--+-+--+-+--->    |
|                                       -1R  0R  2R      |
+--------------------------------------------------------+
```

---

### 5. Comparison Workflow

* **Side-by-Side Batch Compare View:**
  * Implement a route `/compare?sessions=id1,id2,id3` in the SPA.
  * Render a tabular matrix comparing all 6 Core Metrics plus a combined multi-line equity curve chart mapping the performance of each model/version over the exact same testset.
* **Leaderboard Page:**
  * Add a `/leaderboard` view in the viewer.
  * Rank combinations of `[skill_version, model]` using a composite score, e.g.:
    $$\text{Score} = \text{Expectancy}_R \times (1 - \text{Void Rate}) \times \min\left(1, \frac{N}{30}\right)$$
  * This score penalizes small sample sizes and high void rates while rewarding expectancy.

---

### 6. LLM-Specific Angles
To evaluate the *reasoning and execution safety* of LLM agents:

* **Stop-Loss Discipline (Trailing Stop Rules):**
  * *Metric:* `stop_widening_events`.
  * *Why:* Moving a stop-loss away from the current price (widening the stop) is a critical error in momentum trading. The system should flag and penalize any turn where `stop_{t} < stop_{t-1}` (for long trades).
* **Decision Consistency / Repeatability:**
  * When running with `--repeats > 1`, compute the standard deviation of decisions at each bar. A robust agent should make the same decision given the same state history. High decision variance indicates prompt instability.
* **Reasoning Density:**
  * *Metric:* `avg_thought_token_count`.
  * *Why:* Check if longer, more detailed reasoning correlates with better exit quality (MFE capture) or if concise models perform similarly.

---

### 7. General Pitfalls & Guardrails

* **Testset Overfitting:**
  * **Guardrail:** Emphasize that the stratified holdout set should only be used for final evaluations. Introduce a "Validation" set for prompt engineering and iterative testing.
* **Void Rate Survivorship Bias:**
  * **Guardrail:** If we simply ignore void sessions when calculating expectancy, a model that voids all its losing trades would appear to have a perfect expectancy. 
  * **Solution:** In any comparative reports or leaderboards, treat voided runs as a **-1.0R loss** (maximum budget loss) or discount the aggregate expectancy score proportionally.
* **Drift Warning:**
  * Ensure the viewer displays a prominent warning badge if the skill content hash does not match the pinned archive version hash, as this invalidates comparisons.

---

### 8. References
* **Van Tharp, *Trade Your Way to Financial Freedom*:** Incorporate his framework for SQN bands:
  * 1.6 – 1.9: Poor but tradeable
  * 2.0 – 2.4: Average
  * 2.5 – 2.9: Good
  * 3.0 – 4.9: Excellent
  * 5.0 – 6.9: Superb
* **Agent Evals (Trajectory Matching):** Treat trading as a trajectory-based agent task. Evaluate LLMs on *decision similarity* compared to a validated golden baseline run (human or optimal solver).

---

## Suggested Next Steps

1. **Backend Integration (`recorder.py`):**
   * Implement helper functions for R-Expectancy, Profit Factor, and Recovery Factor.
   * Add a `metrics.json` file inside the session artifacts directory to store pre-computed stats during `recorder.finalize`.
2. **Batch Reporting:**
   * Update `batchsim.py` and `recorder.report_by_version` to display the new prioritized metrics in the CLI stdout report.
3. **Frontend Integration (Viewer):**
   * Build the "Session Analytics" panel in the SPA viewer.
   * Add support for the multi-session comparison view and leaderboard.
