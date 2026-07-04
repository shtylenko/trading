# Feature Implementation Review

**Reviewer:** Codex
**Date:** 2026-06-14
**Scope:** `research/features.py`, feature tests, and capture integration

## Executive Summary

I found **2 HIGH**, **10 MEDIUM**, and **2 LOW** issues. The strict
`< trade_date` boundary is correctly enforced for daily data and all new
historical 5-minute access paths; I found no same-day bar look-ahead in those
paths. The most serious defect is `adx14`: every value is exactly 14 times
canonical ADX, so the documented 0-100 feature is emitted on a 0-1400 scale.
The capture path also remains vulnerable to current-day split/reverse-split
scale discontinuities and can record manufactured gaps as real candidates.

The requested test command passes: **10 passed, 2 warnings**. Those tests are
mostly non-null smoke coverage and do not detect the defects below. The
existing smoke parquet confirms the ADX defect in actual capture output:
`adx14` ranges from approximately 189 to 494.

## HIGH Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `research/features.py:207-222` | **`adx14` is scaled 14x too high.** Using a sum as the Wilder seed is correct for smoothed TR and DM because their ratio cancels the scale. It is not correct for the final ADX return: `wsmooth(dx)[-1]` is a smoothed **sum**, not an average. Deterministic comparisons produced `327.32` vs canonical `23.38`, `140.20` vs `10.01`, and `184.37` vs `13.17`, all exactly 14x. | Implement a separate Wilder-average smoother for DX, or return `wsmooth(dx)[-1] / period`. Add a reference-series test and assert `0 <= adx14 <= 100`. |
| 2 | `strategies/post_gap_opening_drive/capture.py:49-59`, `research/features.py:414-415` | **Current-day splits/reverse splits can be admitted as genuine gaps and poison the capture ledger.** The new split checks inspect only prior closes and do not pass today's `first_open` to `has_split_like_jump`. The capture release inherits unguarded `d01` admission. A synthetic 2:1 reverse split produced `gap_pct_vs_prior_high=102.97%`, `gap_range_frac=52.5`, and `gap_zscore_60d=5070`, while `has_split_like_jump(..., open_price=205)` correctly flags it. | Before retaining a capture candidate, call `has_split_like_jump(daily, trade_date, lookback=252, open_price=first_open)` and reject/mark invalid rows. Also include `open_price` when deriving split flags in `compute_candidate_features`. Document that this intentionally excludes data-integrity events from the d01 subset universe. |

## MEDIUM Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `research/features.py:584-591` | **`days_since_opex` is wrong on opex day.** The condition uses `trade_date > tf_this`; when the date equals the third Friday it selects the previous month's opex. On June 21, 2024, `is_opex=1` but `days_since_opex=35` instead of `0`. | Change the condition to `trade_date >= tf_this`. Add before/on/after and January rollover tests. |
| 2 | `research/features.py:499-502`, `research/features.py:415` | **The 252-day split guard does not cover the feature's full input window.** Producing 252 rolling 20-return volatilities consumes 271 returns/272 closes, but `has_split_like_jump(..., lookback=252)` checks only the final 252 closes. A discontinuity in the oldest 20 required bars is missed and the percentile remains numeric. | Use at least `lookback=272` for this feature, preferably derive the guard length from `252 + 20`. |
| 3 | `research/features.py:412-415`, `research/features.py:461-507`, `research/features.py:568-577`, `research/features.py:623-625` | **Split protection is incomplete across new trailing features.** Even when `split_63` or `split_252` is true, features such as ROC, trend efficiency, volatility ratio, SMA 50/200 spread, max drawdown, and volume/dollar-volume trends still emit values from discontinuous raw series. These can invert rankings around corporate actions. | Centralize window-integrity checks and null every feature whose source window crosses a split. Use separate guards matched to each lookback rather than protecting only selected correlation/z-score features. |
| 4 | `research/features.py:523-527` | **`stock_sector_corr_60d` can be `NaN` rather than `None`.** A constant stock-return series makes `Series.corr()` return NaN; the code assigns it directly, violating the stable-output contract and potentially writing non-standard JSON/NaN to the ledger. | Assign only when `np.isfinite(corr)`, otherwise leave `None`. Apply a final non-finite normalization pass to every feature value. |
| 5 | `research/features.py:181-189` | **VWAP silently misweights rows with invalid OHLC.** Pandas skips NaN numerator terms but the denominator still includes their volume. One valid 100-price row plus one NaN-price row with equal volume returns VWAP 50 instead of 100 or `None`. | Build one finite mask over typical price and volume, require positive finite volume, and use the same masked rows in numerator and denominator. Return `None` for a non-finite result. |
| 6 | `research/features.py:170-178`, `research/features.py:419-446` | **Incomplete prior sessions produce plausible false values.** `_prior_session_5m` selects the latest date without sorting or checking required windows. An afternoon-only partial session yields `prior_first_hour_vol_frac=0.0` and `prior_late_volume_share=0.0` rather than `None`; `last_close` may also not be the chronological close if input is unsorted. | Sort by index, constrain to RTH, and validate each required window before computing. Missing first-hour/late/session-close coverage should yield `None`, not zero. |
| 7 | `research/features.py:433-434` | **`prior_first_hour_vol_frac` includes 65 minutes on left-labeled bars.** `between_time("09:30", "10:30", inclusive="both")` includes the 10:30 bar, which represents 10:30-10:35. A regular 78-bar session counts 13 bars instead of the 12 bars in `[09:30, 10:30)`. | Use `inclusive="left"` for a true first-hour interval, or rename/document the feature as a through-10:30-bar measure. |
| 8 | `research/features.py:580-583` | **`is_first_trading_day_of_month` depends on ticker data completeness, not the exchange calendar.** If a ticker has no April 1-2 rows, April 3 is incorrectly marked as the first trading day because its last observed row is in March. | Determine the first XNYS session of the month from the market calendar and compare it directly with `trade_date`. |
| 9 | `strategies/post_gap_opening_drive/capture.py:53-56`, `strategies/post_gap_opening_drive/d12.py:38-41` | **Historical sector features use a June 2026 current-snapshot sector map.** Applying that map to 2022-2025 capture dates is a documented but real point-in-time leak when companies change classification. | Use a versioned, effective-dated sector map or explicitly mark these columns as non-PIT and exclude them from decision-grade historical search. |
| 10 | `strategies/post_gap_opening_drive/capture.py:59`, `scripts/capture_features.py:89-92` | **`sector_etf` is not preserved in the exported ledger despite the capture comment saying it is kept for traceability.** `export_ledger()` reindexes feature JSON to `FEATURE_NAMES`, silently dropping `sector_etf`. | Add `sector_etf` as an explicit non-feature ledger column before reindexing, or maintain a separate ordered metadata-column list. |

## LOW Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | `research/features.py:337`, `research/features.py:563`, `research/features.py:610` | Historical opening bars are filtered/grouped three times per candidate: opening volume twice and opening range once. This compounds over large capture runs. | Compute one per-session opening-bar frame and reuse its volume/range series. |
| 2 | `research/features.py:38-83`, review prompt | The implemented schema is materially larger than described: `FEATURE_NAMES` contains **81** keys, with **38** additions over the prior 43, not approximately 67 total/~26 new. Incorrect schema counts make capture validation and review checklists unreliable. | Generate feature counts from `FEATURE_NAMES` in documentation/tests instead of maintaining manual totals. |

## Verified Non-Issues

- `_before()` filters strictly with `index.date < trade_date`.
- Both `_opening_bar_volumes()` call sites pass `trade_date`.
- `_opening_bar_ranges_pct()` and `_prior_session_5m()` pass through `_before()`.
- Every new `hist_5m` feature path is therefore protected from current/future
  rows.
- `consecutive_gap_up_days` indexing correctly counts today first, then the
  prior day's `open > previous close`, and walks backward.
- `prior_gap_fill_fraction` is intentionally gap-up-only according to the
  implementation specification.
- Gap definitions differ intentionally: `gap_vs_spy_gap_diff` and streaks use
  prior close, while `gap_zscore_60d` and d-family admission use prior high.
- The prompt's suggested ADX seed diagnosis is not the actual bug. Sum seeding
  is valid for Wilder-smoothed TR/DM totals; failure to divide the final
  smoothed DX by 14 is the defect.
- Filters and signal helpers are unchanged in the working diff.
- Capture sector-symbol wiring is graceful: unmapped symbols pass
  `sector_daily=None`, leaving sector features null.

## Test Coverage Gaps

Ranked by priority:

1. **ADX reference correctness**: Compare against a hand-calculated or trusted
   Wilder ADX series; assert range 0-100, flat-series `None`, and short-history
   behavior.
2. **Corporate-action integrity**: Test a split inside each relevant lookback
   and a split/reverse split between prior close and today's open. Assert
   affected features are null or the capture candidate is rejected.
3. **Calendar boundaries**: Test `days_since_opex` before, on, and after third
   Friday, January rollover, and `is_first_trading_day_of_month` against an
   exchange calendar with sparse ticker rows.
4. **Prior-session intraday formulas**: Hand-calculate all six A2 features from
   a small ordered fixture. Test unsorted rows, missing morning/afternoon
   windows, early close, zero volume, NaN OHLC, and partial latest sessions.
5. **Sector statistics**: Test exact correlation/beta on aligned dates,
   mismatched calendars, constant stock returns, constant sector returns, and
   missing sector history.
6. **Statistical features**: Exact tests for `gap_zscore_60d`,
   `prior_return_zscore_60d`, `realized_vol_percentile_252`,
   `first_range_zscore_20d`, information ratio, and max drawdown, including
   zero-variance and non-finite inputs.
7. **Trend/volatility formulas**: Exact tests for channel position, SMA
   spreads, trend efficiency, ROC, down-day streak, volatility ratio, and
   prior range expansion.
8. **Liquidity formulas**: Exact tests for opening-volume z-score, prior-volume
   ratio, and dollar-volume trend with zero/NaN volume.
9. **Full intraday leak test**: The current poison test checks only four keys.
   Compare every A2, F2, and H2 intraday-derived key before and after current
   and future poison rows.
10. **Capture export integration**: Assert every feature column is exported,
    `sector_etf` traceability survives, and no numeric column contains
    non-finite values.

All 38 new features currently rely primarily on
`test_new_features_coverage_rich_inputs`, which proves non-null availability
but not formula correctness. Only `days_since_opex` has one exact assertion,
and that assertion does not cover opex day.

## FEATURE_NAMES vs compute_candidate_features Cross-Reference

- `FEATURE_NAMES`: **81 keys, 81 unique**.
- Literal `f["..."]` assignments: 79 unique keys.
- The apparent missing keys, `stock_5d_ret_minus_spy` and
  `stock_20d_ret_minus_spy`, are assigned dynamically through `f[key]` in the
  `(n, key)` loop at lines 370-373.
- **Keys never assigned:** none.
- **Computed feature keys absent from `FEATURE_NAMES`:** none.
- **Duplicate feature names:** none.
- `sector_etf` is intentional candidate metadata rather than a declared
  feature, but the current export path drops it.

## Test Execution

Command:

```text
PYTHONPATH=projects/trading_strategy_finder python3 -m pytest \
  projects/trading_strategy_finder/trading/lab/tests/test_features.py -x -q
```

Result:

```text
10 passed, 2 warnings in 0.11s
```

`compileall` and `git diff --check` also passed for the reviewed Python files.

## Unresolved Questions

1. Should `capture_d_features` preserve d01's split artifacts for strict subset
   identity, or should data-integrity events be excluded before capture? The
   latter is safer, but it changes the stated "exactly what d01 admits"
   contract.
2. Is the 10:30 bar intentionally included in
   `prior_first_hour_vol_frac`, despite left-labeled 5-minute bars making that
   a 65-minute interval?
3. Are current-snapshot sector classifications accepted as exploratory-only,
   or are sector features expected to satisfy the same strict point-in-time
   standard as prices?
