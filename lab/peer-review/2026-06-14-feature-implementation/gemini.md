# Feature Implementation Review — 2026-06-14 Additions

## Executive Summary
This review covers the ~26 new features and 6 helper functions added to `trading/lab/research/features.py`. The overall architecture is sound and successfully maintains the leak-free guarantee by meticulously isolating historical dependencies. However, **2 High-Severity bugs** were identified: a mathematical error in the initial Wilder smoothing value for ADX, and a potential zero-division crash in the AM/PM range ratio. Several Medium-Severity definitional inconsistencies regarding AM/PM bar boundaries and gap definitions were also identified. A significant test coverage gap exists for the correctness logic of the new features.

---

## HIGH Severity (crashes, look-ahead leaks, formula errors)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `features.py:208` | **Formula Error (ADX Smoothing)**: The Wilder smoothing initialization uses `x[:period].sum()` instead of the mean. This inflates the initial True Range and Directional Movement by a factor of 14, causing massive distortion in ADX values for tickers with limited history (e.g., <50 days) since the error decays slowly. | Change `out[period - 1] = x[:period].sum()` to `out[period - 1] = x[:period].mean()` |
| 2 | `features.py:429-430` | **Crash Safety (Zero Division)**: `prior_pm_am_range_ratio` computes `pm_rng / am_rng` but lacks a guard for `am_rng == 0`. If the morning bars are completely flat (high==low for all morning bars, which can occur on low-volume halted/resume days), this divides by zero and throws `ZeroDivisionError`, crashing the feature extraction pipeline. | Add a guard: `if am_rng > 0:` before assigning `f["prior_pm_am_range_ratio"]`. |

---

## MEDIUM Severity (inconsistencies, edge-case None handling, performance)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `features.py:433` | **Inconsistent Time Boundaries (65-minute hour)**: `psess.between_time("09:30", "10:30", inclusive="both")` includes the 10:30 bar. For 5m bars, this captures 13 bars (65 minutes), not 60 minutes. Similarly, `late` ("14:00" to "16:00", both) captures 25 bars (125 minutes). By contrast, `opening_30m` uses `inclusive="left"` (6 bars = 30 minutes). | Standardize on `inclusive="left"` for duration-specific boundaries (e.g., `first_hour`, `opening_30m`) to accurately match the intended minute-durations. |
| 2 | `features.py:548-552` | **Inconsistent Gap Definition**: `consecutive_gap_up_days` defines a gap as `open > prior_close`. However, the core strategy logic (d-family) and original A-section gap features define a gap as `open > prior_high`. This causes the streak feature to score "close-gaps" as true gaps, misaligning with strategy admission conditions. | Change the logic to compare `opens[i] > highs[i - 1]` to match the canonical gap-vs-high definition used elsewhere. |
| 3 | `features.py:558-559` | **Inconsistent Relative Gap**: `gap_vs_spy_gap_diff` uses `gap_vs_close` for both the stock and SPY. However, the original `rel_spy_gap` feature uses `gap_vs_high`. Having two different "relative gap" derivations referencing different baselines is confusing. | Update `gap_vs_spy_gap_diff` to use `f["gap_pct_vs_prior_high"]` and SPY's `open vs prior_high`. |
| 4 | `features.py:582` | **First Trading Day Semantic Gap**: `is_first_trading_day_of_month` compares `last_dt.month != trade_date.month`. If a stock simply doesn't trade for a few days mid-month and resumes, this feature evaluates to `0.0`, which is correct. But if it misses the first 3 days of a new month, its first resumption day will evaluate to `1.0`. | Acceptable for SP500, but for sparse ETFs, compare `trade_date` against a universal market calendar instead of the stock's own history. |
| 5 | `features.py:337, 563` | **Performance**: `_opening_bar_volumes` is called twice for the exact same `hist_5m` frame (in C and F2 sections), running the same `between_time` and `groupby` operations redundantly. | Call `_opening_bar_volumes` once and store the result in a local variable, or combine volume and range extraction. |

---

## LOW Severity (naming, documentation, minor optimization)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `features.py:591` | **Naming (Trading vs Calendar Days)**: `days_since_opex` computes calendar days, but the implicit convention for "days since" in market contexts is trading days. | Document that the metric returns calendar days, or rename it to `calendar_days_since_opex`. |
| 2 | `features.py:207-212` | **Optimization**: The `wsmooth` inner function inside `_adx14` is redefined on every single candidate evaluation. | Move `wsmooth` to the module scope or define it as a static helper to avoid function reallocation overhead. |

---

## Test Coverage Gaps

The test suite (`test_features.py`) provides smoke tests (`test_new_features_coverage_rich_inputs`) ensuring features populate under ideal conditions. However, **~37 new features have no correctness assertions** validating their mathematical outputs against hand-figured fixtures. 

**Highest Priority for Correctness Tests:**
1. **`adx14`**: Complex iterative smoothing logic highly susceptible to off-by-one or initialization errors.
2. **`gap_zscore_60d` & `prior_return_zscore_60d`**: Requires validation of whether the current value is correctly included/excluded from the rolling reference distribution.
3. **`stock_sector_corr_60d` & `beta_to_sector_60d`**: Needs alignment testing on the inner-joined `pd.concat` to ensure missing bars don't skew variance/covariance calculations.
4. **`consecutive_gap_up_days`**: Needs exact boundary testing for the streak counter (e.g., ensuring day 0 is counted correctly).

---

## `FEATURE_NAMES` vs `compute_candidate_features` Cross-Reference

- **Missing Features**: None. Every key defined in `FEATURE_NAMES` (lines 59-82) has a corresponding assignment inside `compute_candidate_features`.
- **Orphan Computations**: None. All new dictionary keys assigned inside the computation block explicitly map to predefined `FEATURE_NAMES`. The `sector_etf` key is injected safely downstream in `capture.py`, adhering to the boundary logic.

---

## Unresolved Questions

1. **AM/PM Segmentation Strategy**: The boundaries use a mix of `inclusive="left"` and `inclusive="both"`. Was the 12:00 bar intentionally included in the PM range but excluded from the AM range? And should the 16:00 close bar truly be incorporated into the PM range for features tracking intraday momentum, given closing auction dynamics often distort the final print?
2. **Gap Down Fill Fraction**: `prior_gap_fill_fraction` only computes on gap-up days. Should it be symmetrical to track gap-down recoveries, or is the null-return strictly intentional to cater solely to the long-bias d-family strategies?
