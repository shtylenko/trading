# Feature Implementation Review — 2026-06-14 Peer-Review Feature Additions

**Reviewer**: smartypants (DeepSeek v4 pro)  
**Date**: 2026-06-14  
**Tests**: 10/10 passed (`pytest trading/lab/tests/test_features.py -x -q`)

---

## Executive Summary

10/10 tests pass. The expansion is structurally sound — all features are leak-free,
the `_before()`/`_prior()` slicing pattern was correctly applied to every new data
path, and the FEATURE_NAMES cross-reference is clean (81 names, 79 unique
assignments with 2 set via variable-key loop, 0 missing, 0 orphaned, 0 duplicates).

**Two HIGH-severity bugs** found: an ADX formula error from using `sum` instead of
`mean` for Wilder initialization (inflates ADX by ~10–15% for short histories), and
`days_since_opex` returning calendar days instead of trading days as specified.

**Seven MEDIUM-severity issues**: two gap-definition inconsistencies
(`consecutive_gap_up_days` and `gap_vs_spy_gap_diff` use gap-vs-close while the
d-family uses gap-vs-high), z-score reference-window inconsistency (some features
include the current value in the reference distribution, `prior_return_zscore_60d`
correctly excludes it), `is_first_trading_day_of_month` false-positives for tickers
with sparse trading history, `prior_gap_fill_fraction` ignoring gap-down days,
double `_opening_bar_volumes` call (~250K redundant GroupBy operations in a capture
run), and `wsmooth` inner function redefined on every `_adx14` call.

**37 of ~67 features** have no dedicated correctness test beyond the rich-input
smoke test in `test_new_features_coverage_rich_inputs`.

---

## HIGH Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | features.py:208 | **`_adx14` initial value uses SUM instead of MEAN**. `out[period-1] = x[:period].sum()` makes the initial smoothed value 14× too large. Wilder's canonical method (1978) uses `x[:period].mean()`. All three series (ATR, +DM, -DM) are affected. The ratios `+DI = 100 * smooth(+DM) / smooth(ATR)` partially cancel the error at initialization, but the decay paths diverge because each series has different input values. For short histories (< 60 daily bars), ADX is off by ~10–15%. For long histories (200+ bars), the error decays below 1%. The `wsmooth` function is also redefined inside `_adx14` on every call (see MEDIUM #7). | `out[period - 1] = x[:period].mean()` |
| 2 | features.py:591 | **`days_since_opex` returns CALENDAR days, not trading days**. The proposal doc specified "trading days since opex" but the implementation computes `(trade_date - ref).days` which gives calendar days. If `trade_date` is Monday and the reference opex Friday was 3 calendar days ago, the feature returns 3 — but 0 trading days have passed. This inflates values by ~1.4× on average and creates a sawtooth pattern (Mon=3, Tue=4, Wed=5, Thu=6, Fri=0). | Either: (a) rename to `calendar_days_since_opex` and document the sawtooth, or (b) use the marketdata trading calendar (`trading_days_in_range(ref + 1d, trade_date)`) to count actual trading days. |

---

## MEDIUM Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | features.py:542–553 | **`consecutive_gap_up_days` uses gap-vs-CLOSE, inconsistent with d-family's gap-vs-HIGH**. The loop checks `opens[i] > cls[i-1]` (open > prior close), but the d-family strategies and `gap_pct_vs_prior_high` define gaps as open > prior HIGH. A day where `open > prior_close` but `open < prior_high` would be counted as a "gap up" by this feature but would NOT be a gap-up candidate for d-family strategies. The feature still has signal value (it measures open-vs-close streaks — a different concept), but the name `consecutive_gap_up_days` is misleading alongside `gap_pct_vs_prior_high`. | Either rename to `consecutive_open_above_close_days` or change the condition to `opens[i] > pdf["high"].astype(float).values[i-1]` (needs high series extracted from pdf). |
| 2 | features.py:554–559 | **`gap_vs_spy_gap_diff` uses gap-vs-CLOSE while `rel_spy_gap` uses gap-vs-HIGH**. Two different "relative gap" concepts coexist: `rel_spy_gap = gap_vs_prior_high / SPY_gap_vs_prior_high` (line 391) vs `gap_vs_spy_gap_diff = gap_vs_prior_close - SPY_gap_vs_prior_close` (line 559). Same "gap" prefix, different denominators. A stock with a 2% gap-vs-close but only 0.5% gap-vs-high would show strong `gap_vs_spy_gap_diff` but weak `rel_spy_gap`. | Document both definitions explicitly in FEATURE_NAMES comments. Consider `_vs_close` suffix for close-based gap features. |
| 3 | features.py:499–502, 594–601, 602–608, 563–567, 609–614 | **Z-score reference window inconsistency across 5 z-score features**. `prior_return_zscore_60d` (line 605: `iloc[:-1]`) correctly EXCLUDES the current value from the reference distribution. `gap_zscore_60d`, `first_range_zscore_20d`, `opening_volume_zscore_20d`, and `realized_vol_percentile_252` all INCLUDE the current value. A 3σ gap might appear as 2.8σ or 3.5σ depending on convention. In-sample percentiles are defensible for feature engineering, but the inconsistency should be resolved. | Pick one convention. Recommend excluding current value (matches `prior_return_zscore_60d`) for true "how unusual is today?" semantics. For percentiles, rename to `_pct_rank` to distinguish from z-scores. |
| 4 | features.py:580–583 | **`is_first_trading_day_of_month` false-positive for tickers with trading gaps**. Uses `last_dt.month != trade_date.month` where `last_dt` is the ticker's last daily bar from `pdf.index[-1]`. If a ticker didn't trade for the last 3 days of March and today is April 3, the feature returns 1.0 — but April 3 is NOT the first trading day of the month. Triggers for tickers with sparse history (small caps, low-volume ETFs, delisted/relisted periods). For SP500 it's harmless. | Use the marketdata trading calendar: check if any trading day exists between `last_dt.date()` and `trade_date` that falls in the same month as `trade_date`. Or accept the approximation and document the limitation. |
| 5 | features.py:455–459 | **`prior_gap_fill_fraction` only handles gap-up days**. When `gap = po - ptp_close <= 0` (prior day gapped down or flat), the feature stays None. Gap-down fill (upside fill toward prior close) is never measured. The feature name doesn't specify direction. | Handle both: `if gap > 0: fill = (po - pl) / gap` (downside fill). `elif gap < 0: fill = (ph - po) / abs(gap)` (upside fill). Clamp to [0, 1] in both cases. |
| 6 | features.py:337, 563 | **`_opening_bar_volumes` called twice** with identical arguments. First at line 337 (C section, for `opening_rv`/`rvol_20d`), second at line 563 (F2 section, for `opening_volume_zscore_20d`). Both do `_before()` + `between_time()` + `groupby()`. In a 125K-call capture run (~500 tickers × ~250 days), this is ~250K redundant GroupBy operations. Not a correctness issue but measurable overhead. | Compute once, store in a local variable. The two call sites differ only in which statistics they extract (mean_all, mean_20, z-score stats) — all derivable from the same series. |
| 7 | features.py:207–211 | **`wsmooth` inner function redefined on every `_adx14` call**. Defined inside `_adx14` at line 207, recreated as a new closure on each invocation. Called 3× per `_adx14` call (for ATR, +DM, -DM). ~375K function object allocations in a capture run. Not a correctness issue. | Move to module level as `def _wilder_smooth(x: np.ndarray, period: int) -> np.ndarray`. |

---

## LOW Severity

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | features.py:424, 425, 442 | **Inconsistent `inclusive` convention in `between_time` calls**. `"left"` used for AM (line 424) and opening_30m (line 442). `"both"` used everywhere else (lines 425, 433, 435, 437). The `"left"` on AM correctly avoids double-counting the 12:00 bar with PM. But `"left"` on opening_30m means the 10:00 bar is excluded, giving 6 bars (09:30–09:55) instead of 7 (09:30–10:00). | If 10:00 should be included, change to `"both"`. If the intent is "exactly the first 30 minutes (six 5m bars)", document it. |
| 2 | features.py:623–625 | **`max_drawdown_20d` returns NEGATIVE values** (e.g., -5.3 for a 5.3% drawdown). Consistent with `dist_from_20d_high_pct` (also negative: distance below the high). But the name "max_drawdown" typically implies a positive magnitude in finance literature (e.g., "max drawdown was 5.3%", not "-5.3%"). | Document the sign convention in the FEATURE_NAMES comment block: "negative = drawdown depth". Alternatively, negate to positive and rename to `max_drawdown_pct_20d`. |
| 3 | features.py:499–502 | **`realized_vol_percentile_252` minimum possible value is `1/len(roll)`, not 0**. Current value is in its own reference distribution, so the minimum percentile is `1/N` (e.g., 2% for N=50, 0.4% for N=252). Documented behavior but worth a code comment. | Add comment: "in-sample percentile rank; minimum = 1/len(roll)". |
| 4 | features.py:181–189 | **`_session_vwap` returns NaN if input has NaN prices but non-zero volume**. `vol.sum() > 0` guard passes, but `(typ * vol).sum()` produces NaN. `if vwap and vwap > 0` at line 422 correctly rejects NaN (NaN is falsy in Python), so no crash or wrong value — just a silent None. | Explicit NaN check for clarity: `result = float((typ * vol).sum() / vol.sum()); return None if np.isnan(result) else result`. |
| 5 | features.py:414–415 | **`has_split_like_jump` return type is `bool` but assigned to `split_63`/`split_252` used in boolean context**. `has_split_like_jump` returns `True`/`False` (declared `-> bool`). `split_63 = has_split_like_jump(...)` is correct. Used as `if not split_63:` at lines 518, 594, 602, 615 — `not False` = True (don't skip). Correct. No issue. | — |

---

## Test Coverage Gaps

37 of ~67 features have zero dedicated correctness test beyond the non-null smoke
test in `test_new_features_coverage_rich_inputs`. Ranked by implementation
complexity:

| Priority | Feature | Complexity | Risk |
|----------|---------|------------|------|
| 1 | `adx14` | Very high (60-line Wilder smoothing + 3-series ratio + multi-stage NaN filtering) | Formula bug already found (HIGH #1) |
| 2 | `excess_return_information_ratio_60d` | High (60d join + annualization sqrt(252)) | Zero-division guarded; join alignment untested |
| 3 | `stock_sector_corr_60d` / `beta_to_sector_60d` | High (60d join + corr + cov, same pattern as `beta_60d`) | Alignment with sector_daily index untested |
| 4 | `gap_zscore_60d` | Medium (`shift(1)` alignment + `tail(60)` + z-score) | Shift creates leading NaN; tail boundaries |
| 5 | `realized_vol_percentile_252` | Medium (`rolling(20).std()` + percentile rank) | Percentile boundary correctness |
| 6 | `trend_efficiency_20d` | Medium (`tail(21).diff().abs().sum()`) | Off-by-one on window size (21 bars → 20 diffs) |
| 7 | `consecutive_gap_up_days` | Medium (backward loop + gap-definition mismatch) | Loop bounds verified; gap definition MEDIUM #1 |
| 8 | `prior_return_zscore_60d` | Medium (`iloc[:-1]` exclusion pattern) | Exclusion verified correct |
| 9 | `vol_ratio_5d_20d` | Low | Simple ratio of two stdevs |
| 10–37 | Remaining 28 features | Low | Simple formulas with existing-guard patterns from original features |

Additionally:

- **No test for `split_63`/`split_252` gate behavior**. The gates at lines 414–415
  suppress features when raw daily data spans a split. A synthetic fixture with a
  >40% close-to-close jump would verify: (a) that `has_split_like_jump` detects
  it, and (b) that features guarded by `not split_63`/`not split_252` correctly
  return None.
- **No test for edge cases**: zero denominators, empty hist_5m, single-bar daily,
  missing sector_daily/spy_daily, ADX with flat prices, VWAP with all-zero volume,
  all-identical opening volumes (sd=0 for z-score), single-element distributions.
- **Leak-free test only covers 4/37 new features**. `test_new_features_leak_free_hist_5m`
  verifies `prior_close_vs_vwap_pct`, `prior_first_hour_vol_frac`,
  `opening_volume_zscore_20d`, `first_range_zscore_20d`. Should cover at minimum
  all A2-group features (6 total) plus all hist_5m-dependent features (9 total).

---

## FEATURE_NAMES vs `compute_candidate_features` Cross-Reference

- **81 names in FEATURE_NAMES** (lines 38–83)
- **79 unique keys assigned** via `f["key"] = ...` (77 literal + 2 variable-key via loop)
- **0 missing features** (all 81 names have assignments)
- **0 orphan computations** (all 79 assigned keys appear in FEATURE_NAMES)
- **0 duplicate names**
- **False positive explanation**: `stock_5d_ret_minus_spy` and `stock_20d_ret_minus_spy`
  are assigned via `f[key] = sr - mr` in the loop at line 370–373. A literal-string
  regex scan misses them. Verified by reading line 370: they are correctly assigned.

---

## Leak-Free Verification Summary

All 8 checklist items from §2A verified:

| # | Check | Result |
|---|-------|--------|
| 1 | `_opening_bar_volumes` call sites pass `trade_date` | ✓ Lines 337, 563 both pass `trade_date` |
| 2 | `_opening_bar_ranges_pct` `_before()` correctly cuts | ✓ Line 610 passes `trade_date`; `_before()` at line 158 |
| 3 | `_prior_session_5m` `_before()` cuts strictly | ✓ Line 418; `_before()` at line 173 |
| 4 | `consecutive_gap_up_days` loop indexing | ✓ Uses `_prior()`-sliced `pdf`; backward loop verified |
| 5 | `gap_zscore_60d` reference distribution | ✓ All bars in `pdf` are pre-`trade_date`; shift/dropna correct |
| 6 | `prior_return_zscore_60d` exclusion pattern | ✓ `iloc[:-1]` excludes current; leak-free |
| 7 | All hist_5m paths go through `_before()` or `_prior_session_5m(trade_date)` | ✓ Lines 418, 563, 610 all verified |
| 8 | `has_split_like_jump` calls pass `trade_date` | ✓ Lines 414, 415 both pass `trade_date` as positional arg |

**No look-ahead leaks found.**

---

## External Caller Impact

- **`_opening_bar_volumes`**: Called only from features.py lines 337 and 563. No
  external callers. Signature change (`trade_date=None` added as optional 2nd
  param) is backward-compatible.
- **`has_split_like_jump`**: Now called from features.py lines 414–415 with
  `lookback=63` and `lookback=252` as keyword args. Existing callers in
  `variants.py:104` and `common.py:76` are unaffected. The function is unchanged
  since the pre-expansion codebase.

---

## Unresolved Questions

1. **`consecutive_gap_up_days` close-vs-high gap definition**: Was this intentional
   (capturing a different phenomenon than d-family gaps) or a copy-paste error?
   The proposals doc (prompt.md §5E) described "consecutive gap-up days" without
   specifying which gap definition.

2. **`between_time` `"left"` on opening_30m**: Is the 10:00 bar excluded
   intentionally (6 bars = exactly 30 minutes of the opening range) or should it
   be `"both"` (7 bars = 35 minutes, capturing the full opening half-hour
   inclusive of the 10:00 bar)?

3. **`days_since_opex` calendar vs trading**: Was the calendar-day implementation
   intentional (simpler, avoids trading-calendar dependency) or should it use the
   marketdata calendar for trading-day precision as the proposals doc specified?

4. **`realized_vol_percentile_252` minimum history**: The `len(roll) >= 50` guard
   allows percentile computation with as few as 50 rolling 20d-vol windows (70
   trading days of history). Is 2% granularity sufficient for meaningful regime
   classification, or should the minimum be higher (e.g., 100 or 200)?
