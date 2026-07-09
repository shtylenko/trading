# Peer Review Feedback: Playbook for Improving Trading Skill Performance

**Date:** 2026-07-08  
**Reviewer:** Antigravity (AI Coding Assistant)  
**Status:** Completed Review  
**Target Document:** [`llm_trader/skills/MAINTAINING.md`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/MAINTAINING.md)  
**Reference Batch:** `20260708181528-BATCH-023823` (v2.4.0) vs. `20260707225900-BATCH-aca57c` (v2.2.1)

---

## Executive Summary

The proposal to refactor the trading skill iteration process is **strongly endorsed**. The shift from informal tribal knowledge to a structured, reproducible playbook is the single most critical step to prevent model overfitting and statistical illusions. 

The transition in **v2.3.0** and **v2.4.0** from subjective "feel calls" to objective formulas (e.g., objective trigger bars and stop placement formulas in [`skills/TRADE_SIMULATOR.md:382-386`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L382-L382) and [`skills/TRADE_SIMULATOR.md:472`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L472)) has successfully proved that tightening rules reduces decision variance and improves average expectancy.

However, the current iteration loop suffers from **three key bottlenecks**:
1. **Small-sample tail bias** (where single large runs like `CPSH` skew the 30-set stats).
2. **Holdout contamination** (using the same 100-set for both diagnostic tuning and final validation).
3. **Simulated execution friction neglect** (no slippage, bid-ask spreads, or volume-limit checks).

To resolve these, we recommend **splitting the documentation** to keep version control mechanics separate from performance playbook rules, implementing a **non-parametric paired statistical test**, and introducing a **three-tier dataset discipline**.

---

## Top 3 Recommended Changes for Maximum Iteration Impact

### 1. Document Split: Maintain a Lean Mechanics Doc & Create a Performance Playbook
Keep [`skills/MAINTAINING.md`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/MAINTAINING.md) as a short, operational reference focused strictly on **automation mechanics** (versioning, registry updates, and file locks). It is read by AI editors and CI scripts to prevent check-in failures. 

Create a new file, **[`skills/IMPROVING.md`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/IMPROVING.md)**, as the **Performance Improvement Playbook**. This file will guide human and AI researchers through statistical validation, alignment checks, and overfitting guardrails.

### 2. Paired Non-Parametric Significance Testing (The Sign Test)
Averaging R-multiples across different versions is highly vulnerable to right-tail lottery tickets. Since we run the exact same setups across cohorts, we must enforce a **paired sign test** on setup-level mean R-multiples across multiple repeats (e.g., `repeats >= 3`). The sign test counts the number of setups that improved vs. worsened, ignoring the outlier magnitudes. It provides a robust, distribution-free method to check if a rule-set change is a broad-based improvement ($p \le 0.05$).

### 3. Chronological Dataset Split (Tuning, Validation, and Holdout)
Establish a strict division of historical setups to prevent overfitting the LLM to a specific backtest set. Create three distinct files under `batch/`:
- `testset_dev.json` (30 setups): For rapid prototyping, prompt tuning, and leaf-level log inspection.
- `testset_val.json` (100 setups): For candidate evaluation. Run only on Release Candidates. No individual leaf inspection.
- `testset_holdout.json` (50 setups): Completely locked. Run once per major version release to verify out-of-sample generalization.

---

## Detailed Answers to Peer Review Questions

### 1. Structure & Scope
`MAINTAINING.md` should stay a pure versioning/mechanics doc. Introducing a new sibling file, **`IMPROVING.md`**, keeps operational automation separated from complex research methodology.

#### Outline for `skills/IMPROVING.md`
*   **1. Philosophy of Heuristics (Feel-to-Formula)**
    *   The rule of reproducibility: replace all subjective adjectives (e.g., "extended", "clean") with mathematical expressions computed from past and current bar primitives.
*   **2. Dataset Discipline & Chronological Splits**
    *   Dev vs. Validation vs. Holdout set definitions, lock rules, and chronological split rules.
*   **3. Test Rigor & Validation Protocol**
    *   Minimum cohort sizes, repeat requirements, paired setup averaging, and the paired sign test process.
*   **4. Primary & Guardrail Metrics**
    *   Effective Expectancy, Profit Factor, Void rates, and repeat variance benchmarks.
*   **5. Alignment Matrix (Corpus Mapping)**
    *   The citation mapping process to prevent strategy drift from the Ross Cameron canon.
*   **6. Diagnostic Tooling (Disagreement Mining)**
    *   How to run variance decomposition across repeats and path divergence analysis across versions to isolate rule ambiguities.

---

### 2. Test Rigor
Given fat tails and LLM reasoning variance, the minimum defensible protocol to accept a version is defined below:

```markdown
### Validation & Release Protocol Checklist
- [ ] Cohort: Run only on `batch/testset_val.json` (N >= 100 setups).
- [ ] Repeats: Minimum R >= 3 runs per setup to smooth out reasoning noise.
- [ ] Data Aggregation: For each setup i, calculate the average R-multiple over the repeats:
      R_mean_i = (R_run1 + R_run2 + R_run3) / 3
- [ ] Paired Significance: Compute the difference delta_R_i = R_mean_new_i - R_mean_base_i.
- [ ] Run a two-sided Paired Sign Test (ignoring ties):
      - Successes (S) = Count of setups where delta_R_i > 0
      - Trials (T) = Count of setups where delta_R_i != 0
      - Calculate two-sided p-value using binomial distribution: p = 2 * P(X >= S) under H0 (p_coin = 0.5)
- [ ] Significance Bar: Reject the change if p > 0.05.
- [ ] Guardrails: Verify Void Rate <= 5% and Stood Down Rate delta <= 10% absolute.
```

---

### 3. Metric of Record
To evaluate performance, we must prioritize **Effective Expectancy ($E_{R, \text{eff}}$)** over "Clean Expectancy" to prevent survivorship bias from stood-down or voided runs.

#### Metrics Framework
1.  **Primary Metric: Effective Expectancy ($E_{R, \text{eff}}$)**
    $$E_{R, \text{eff}} = \frac{1}{M \times R} \sum_{i=1}^{M} \sum_{j=1}^{R} R_{i, j}$$
    *   Where $M$ is the number of planned setups ($100$), and $R$ is the repeats ($3$).
    *   Traded and non-void runs use their actual `r_multiple`.
    *   Stood-down runs are assigned $R_{i, j} = 0.0$.
    *   Voided runs are heavily penalized at $R_{i, j} = -1.0$ (representing a maximum risk budget loss).
    *   *Why:* This prevents a version from looking highly profitable by standing down on 90% of setups or fumbling/voiding complex setups.
2.  **Guardrail Metrics:**
    *   **Void Rate ($V_R$):** Must be $\le 5\%$. Reject if $> 10\%$.
    *   **Clean Expectancy ($E_{R, \text{clean}}$):** Mean $R$ of traded, non-void runs. Must be $\ge 0.5R$.
    *   **Profit Factor ($PF_R$):** Gross R gains / Gross R losses. Must be $\ge 1.5$.
    *   **Max Adverse Excursion (MAE):** Average MAE per traded setup should be $\le 1.2R$ to ensure stops are being honored.
    *   **Repeat Variance ($\sigma^2_{\text{repeat}}$):** Mean standard deviation of R-multiples across repeats for a single setup should be $\le 0.3R$. High variance points to prompt/rule instability.

---

### 4. Overfitting / Generalization
To prevent holdout set contamination, we must enforce a chronological split where setups are grouped by their historical date.

1.  **Chronological Pipeline:**
    *   **Dev Set (30 setups):** Dates from Jan 1, 2025 to Jun 30, 2025. Used for manual run inspections and rule tuning.
    *   **Validation Set (100 setups):** Dates from Jul 1, 2025 to Dec 31, 2025. Used for candidate significance testing.
    *   **Out-of-Sample Holdout (50 setups):** Dates from Jan 1, 2026 onward. Used *only* for final validation before production deployment.
2.  **Tuning Restriction:**
    *   Never inspect individual leaf logs or view session runs for the Validation or Holdout sets. If a validation run fails, the only allowed action is to inspect the aggregate metrics or generate a dev-set setup with similar characteristics for debugging.

---

### 5. Alignment Enforcement
To ensure rule changes do not drift from Ross Cameron's methodology, the new `IMPROVING.md` playbook should enforce an **Alignment Citation Matrix**. 

At the bottom of `TRADE_SIMULATOR.md`, include a table mapping every operational rule to its structured corpus citation:

| Trade Simulator Section / Line | Operational Rule | Canon Source & Citation | Rationale / Translation |
|---|---|---|---|
| [`TRADE_SIMULATOR.md:406`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L406) | Volume Expansion Check (Green > Red + RVOL 1.5x) | [`all_content_structured.md#L81`](file:///Users/shtylenko/Projects/trading/library/ross_cameron/all_content_structured.md#L81) (§2 RVOL) & [`all_content_structured.md#L418`](file:///Users/shtylenko/Projects/trading/library/ross_cameron/all_content_structured.md#L418) (§9 Vol) | Converts qualitative "buyers in control" to green-bar vs. red-bar volume sums. |
| [`TRADE_SIMULATOR.md:472`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L472) | Stop-loss: `min(trigger bar low, prior low) - $0.01` | [`all_content_structured.md#L79`](file:///Users/shtylenko/Projects/trading/library/ross_cameron/all_content_structured.md#L79) (§1 Stop Placement) | Translates "stop is the low of that pullback" to a precise 1-min two-bar low formula. |
| [`TRADE_SIMULATOR.md:650`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L650) | Re-entry cooldown: 3 bars flat | [`all_content_structured.md#L640`](file:///Users/shtylenko/Projects/trading/library/ross_cameron/all_content_structured.md#L640) (§4 Bailout Cooldown) | Prevents revenge trading by requiring structure to reset over a minimum time-window. |

*Review Gate:* Any modifications to the operational rules in `TRADE_SIMULATOR.md` must be accompanied by an update to this matrix.

---

### 6. Finding the Next Change
We can automate the discovery of the next rule bottleneck using **Divergence Mining**:

1.  **Variance Decomposition (Repeat Noise):**
    *   Run `batchsim` with `--repeats 5` on the dev set.
    *   Sort setups by the standard deviation of their final R-multiples.
    *   A high standard deviation (e.g., $\sigma_R > 0.8R$) identifies setups where the agent's actions are unstable. Inspecting these logs will highlight the exact "feel calls" that need to be replaced with objective formulas.
2.  **Path Disagreement Mining:**
    *   Write a script to compare the `actions.json` of two versions (or repeats of the same version) setup by setup.
    *   Identify the first bar index where their action sequences diverged (e.g., `OBSERVE` vs. `ENTER`).
    *   Output these divergence points as a list of `(ticker, date, bar_index)` to guide the developer directly to the rule discrepancy in the viewer.

---

### 7. The Reproducibility-vs-Upside Trade
Removing the $+30R$ tail by objectifying the stop placement was **absolutely the correct call**.

1.  **Simulation Artifact vs. Real Edge:**
    *   The $+30R$ run in version 2.2.1 was a simulation artifact. In the 1-minute paced simulation, there is no bid-ask spread or execution slippage. 
    *   An entry filled at close with an eyeballed tight stop (e.g., $0.03 stop distance) yields a massive share count due to the sizing formula ([`skills/TRADE_SIMULATOR.md:699`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L699)). If the stock breakout does not tick down, the run prints $+30R$.
    *   In a real market, a $0.03 stop on a volatile low-float stock is guaranteed to be stopped out instantly by normal market spread (often $0.05 - $0.15 on momentum breakouts) and entry slippage. Sizing positions based on an artificially tight stop is a dangerous form of overfitting.
2.  **Corpus Grounding:**
    *   Ross Cameron's strategy is built on structural stops: *"my stop is the low of that pullback, it's as simple as that."* Sizing is adjusted down to accommodate this structural low, rather than tightening the stop to inflate share counts. The v2.4.0 formula ([`skills/TRADE_SIMULATOR.md:472`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L472)) is therefore more canon-aligned.

---

### 8. Blind Spots & Hidden Risks

#### A. MAE Calculation Error in the Codebase
In [`llm_trader/recorder.py:183-186`](file:///Users/shtylenko/Projects/trading/llm_trader/recorder.py#L183-L186), the `worst_price_vs_entry` is updated using the bar's **close**:
```python
if self.shares > 0 and close is not None:
    vs_entry = close - self.avg_entry
    if vs_entry < self.worst_price_vs_entry:
        self.worst_price_vs_entry = vs_entry
```
This is a significant bug in the metrics engine. MAE (Max Adverse Excursion) is defined as the *maximum intra-trade drawdown*. Underestimating this drawdown using the `close` rather than the bar's `low` obscures the true heat the trade experienced. 
*   **Fix:** The `step` signature should receive the bar's `low`, and calculate:
    `vs_entry = low - self.avg_entry`

#### B. Execution Latency
An LLM takes 5-15 seconds to output its thought block and tool calls. In momentum day trading, 10 seconds is the difference between buying the breakout on-time and chasing it $0.50 higher. The simulator currently assumes instant fills at the close price of the trigger bar. We should introduce a **latency penalty** (e.g., entering at the high of the entry bar or adding a $0.05 slippage offset) to ensure our rules are robust to execution delays.

#### C. Volume Liquidity Cap
The sizing formula in `Step 3` ([`skills/TRADE_SIMULATOR.md:699`](file:///Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md#L699)) does not check if the position size is realistic relative to the trading volume. If the agent buys 2,000 shares on a bar with 4,000 shares of total volume, it is trading 50% of the bar's volume. In real markets, this would cause severe market impact. 
*   **Fix:** Add a liquidity cap to the sizing formula:
    `shares = min(..., floor(bar_volume * 0.05))`
