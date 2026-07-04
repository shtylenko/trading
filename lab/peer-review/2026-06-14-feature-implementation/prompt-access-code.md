# Feature Implementation Review — 2026-06-14 Peer-Review Feature Additions

**For**: AI model with read access to this codebase. Execute this review by reading
the referenced files and producing structured findings.

**Scope**: The 2026-06-14 feature expansion added ~26 new features and 6 new helper
functions to `research/features.py`, growing it from 315 lines (41 original features)
to 649 lines (~67 total features). Tests were expanded from 143 to 230 lines. The
capture variant was updated. `filters.py` and `signal_helpers.py` are unchanged.

**Goal**: Find bugs, look-ahead leaks, formula errors, edge-case crashes, naming
inconsistencies, and test-coverage gaps. Do NOT propose new features — this is a
correctness audit of what was already implemented.

---

## 1. Files to Review (in order)

| File | Lines | What changed |
|------|-------|-------------|
| `trading/lab/research/features.py` | 1–649 | Full file. New helpers (`_ny`, `_before`, `_prior_session_5m`, `_session_vwap`, `_adx14`, `_third_friday`, `_opening_bar_ranges_pct`, `_opening_bar_volumes` signature change). New `FEATURE_NAMES` entries (lines 59–83). New computation blocks (lines 410–627). |
| `trading/lab/research/filters.py` | 1–139 | Unchanged — verify no regression. In particular `has_split_like_jump` is now imported by features.py (line 33); confirm it wasn't modified. |
| `trading/lab/research/signal_helpers.py` | 1–55 | Unchanged — verify no regression. |
| `trading/lab/tests/test_features.py` | 1–230 | Added: `_daily_noisy`, `_hist_5m`, `_spy_5m_bar` helpers. Added tests: `test_new_features_coverage_rich_inputs`, `test_new_features_leak_free_hist_5m`. Updated `test_stable_key_set` for `days_since_opex`. |
| `trading/lab/strategies/post_gap_opening_drive/capture.py` | 1–60 | Lookback bumped to 420 days, `extra_daily_symbols` set to `_SPDR_ETFS`. Verify the capture variant wires sector symbols correctly into `features_from_context`. |
| `trading/lab/scripts/capture_features.py` | 1–189 | Unchanged — verify it still works with the expanded `FEATURE_NAMES` (it reads `FEATURE_NAMES` at line 39 and reindexes to it at line 91). |

---

## 2. Review Dimensions

For each dimension below, read the relevant code sections and produce findings
organized as: **severity** (HIGH/MEDIUM/LOW), **file:line**, **description**,
**fix** (concrete code change).

---

### 2A. Leak-Free Guarantee (HIGH priority)

The contract: every feature must be computable from data available at 09:35 ET on
`trade_date`. The ONLY intraday bar allowed is the first 5m candle. All daily and
hist_5m data must be sliced strictly before `trade_date`.

**Checklist** — verify each of these:

1. `_opening_bar_volumes` (line 144–153): was modified to accept `trade_date` and
   slice via `_before()`. Verify both call sites (line 337 for C section, line 563
   for F2 section) pass `trade_date`. Verify `_before()` (line 133–141) cuts
   strictly `< trade_date`.

2. `_opening_bar_ranges_pct` (line 156–167): uses `_before()`. Only called at line
   610 (H2 section). Verify `trade_date` is passed to `_before()` — wait, the
   function signature takes `trade_date` but line 610 calls it as
   `_opening_bar_ranges_pct(hist_5m, trade_date)`. Verify the `_before()` inside
   correctly cuts.

3. `_prior_session_5m` (line 170–178): takes `trade_date`, calls `_before()`.
   Called at line 418. Verify `_before()` cuts strictly. In particular: `last =
   max(h.index.date)` — is `max()` called after the `< trade_date` filter? Yes,
   `_before()` does the filtering, then `max()` is on the filtered frame. Good.
   But verify: what if `trade_date` is None? The `_prior_session_5m` function
   signature says `trade_date: date | None` — is it ever called with None? Check
   the call site.

4. **`consecutive_gap_up_days`** (lines 542–553): this walks backward through
   `pdf["open"]` and `pdf["close"]` comparing `opens[i] > cls[i-1]`. The `pdf`
   variable is sliced via `_prior(daily, trade_date)` at line 273 — so it only
   contains bars before `trade_date`. **Verify**: the loop walks from the last
   element backward. Does the streak count include the prior day (`i = len-1`)
   comparing `opens[-1] > cls[-2]`? On line 546, `if o > pc:` checks today's open
   vs prior close — this gates whether the streak starts at 1 or 0. Then the loop
   on lines 548–552 walks `range(len(cls)-1, 0, -1)`. This is correct for
   leak-free (uses prior bars only), but **verify the indexing**: does the loop
   correctly count the prior day's gap and then walk further back?

5. **`gap_zscore_60d`** (lines 594–601): computes historical gaps as
   `(open_i - high_{i-1}) / high_{i-1}` from `pdf`. The `ph_series.shift(1)`
   shifts highs FORWARD by 1 — so at index i, `ph_series.shift(1).iloc[i]` is
   `ph_series.iloc[i-1]`. Then `pdf["open"].iloc[i] - ph_series.shift(1).iloc[i]`
   = `open_i - high_{i-1}`. **Verify**: the `.dropna()` after `.tail(60)` — does
   the shift create NaN in the first position? Yes, it does. `.dropna()` removes
   it. **Verify**: does the `tail(60)` include bars up to AND INCLUDING the prior
   day? If `pdf` has N bars and we take `tail(60)`, we get the last 60. The
   `iloc[-1]` of pdf is the prior day's bar. So the histogram includes the prior
   day's own gap. Is this correct? The prior day's gap is computable at 09:35
   today (prior day's open and the day-before-prior's high are both historical).
   So yes, leak-free. But **verify**: does this inclusion bias the z-score toward
   0? If the prior day had a large gap, it's in the reference distribution AND
   it's being scored. This makes large gaps look less unusual than they are.

6. **`prior_return_zscore_60d`** (lines 602–608): `ref_r = rr.tail(61).iloc[:-1]`
   explicitly EXCLUDES the latest return from the reference distribution. Good.
   But **verify**: `rr` is computed from `closes_p` which is from `_prior(daily,
   trade_date)`. Is the "latest return" in `rr` the prior day's return? Yes —
   `closes_p.pct_change().dropna().iloc[-1]` is the last close-to-close change
   which is the prior day's return. The reference uses the 60 returns BEFORE that.
   Correct.

7. **All hist_5m-based features** (lines 418–446, 563–567, 610–614): verify every
   access path goes through `_before()` or `_prior_session_5m(trade_date)`. Check:
   - Line 418: `_prior_session_5m(hist_5m, trade_date)` ✓
   - Line 563: `_opening_bar_volumes(hist_5m, trade_date)` ✓
   - Line 610: `_opening_bar_ranges_pct(hist_5m, trade_date)` ✓

8. **`has_split_like_jump` calls** (lines 414–415): verify the `trade_date`
   parameter is passed so the function slices daily bars before `trade_date`.
   `has_split_like_jump` accepts `trade_date` as 2nd positional arg — verify
   it's passed at both call sites.

---

### 2B. Formula Correctness (HIGH priority)

For each new feature, verify the mathematical formula against its stated intent.

1. **`prior_pm_am_range_ratio`** (lines 424–430): AM is `between_time("09:30",
   "12:00", inclusive="left")`. PM is `between_time("12:00", "16:00",
   inclusive="both")`. **Verify**: does the 12:00 bar appear in BOTH AM and PM?
   `inclusive="left"` on AM means 09:30 is included, 12:00 is excluded. PM with
   `inclusive="both"` includes 12:00. So the 12:00 bar is ONLY in PM. This looks
   correct — no double-counting. **BUT verify**: is the 16:00 bar (closing bar)
   in PM? `between_time("12:00", "16:00", inclusive="both")` includes 16:00.
   The 16:00 bar is the closing bar — should it be in PM range? Yes, it's part of
   the afternoon session.

2. However, check the **AM boundary**: `between_time("09:30", "12:00",
   inclusive="left")`. The 09:30 bar is included (left boundary). But should the
   09:30 bar be in the AM range? It's the opening bar — yes. But the 12:00 bar is
   excluded from AM and included in PM. Is this the intended split? A trader
   would typically say "morning = 09:30–12:00" and "afternoon = 12:00–16:00" —
   the 12:00 bar is the crossover. Putting it in PM only is reasonable but should
   be consistent with other AM/PM features.

3. **`prior_opening_30m_range_frac`** (lines 442–446): `between_time("09:30",
   "10:00", inclusive="left")` — the 09:30 bar is included, 10:00 is excluded.
   So this captures bars at 09:30, 09:35, 09:40, 09:45, 09:50, 09:55 — six bars.
   The divisor is `full_rng = psess["high"].max() - psess["low"].min()`. This is
   the 30m opening range as a fraction of the full-day range. **Verify**: is
   `op30.empty` properly guarded? Line 444: `if not op30.empty and full_rng > 0:`.
   Yes.

4. **`prior_gap_fill_fraction`** (lines 455–459): computes `gap = po - ptp_close`
   where `po` = prior open, `ptp_close` = day-before-prior close. If `gap > 0`
   (prior day gapped up), the fill fraction = `(po - pl) / gap`. **Verify**:
   - `po - pl` = how far the prior day's low traded below its open. If pl < po,
     some of the gap was filled. If pl >= po, nothing was filled (fraction 0).
   - The clamp `min(1.0, max(0.0, (po - pl) / gap))` — if pl went below
     ptp_close, the numerator `po - pl` could exceed the gap, giving >1.0.
     Clamping to 1.0 is correct: the gap was fully filled (and then some).
   - **But**: what about gap-down days (`gap < 0`)? The feature is only computed
     when `gap > 0`. For gap-down days, the feature stays None. Is this
     intentional? The name `prior_gap_fill_fraction` doesn't specify direction.
     It should probably also handle gap-down days (using `ph` instead of `pl`).
   - **Verify**: the `ptp_close` computation at line 456 uses
     `pdf["close"].iloc[-2]`. But `pdf` was sliced via `_prior(daily, trade_date)`,
     so `pdf.iloc[-1]` is the prior day. `pdf.iloc[-2]` is the day before the
     prior. Correct.

5. **`trend_efficiency_20d`** (lines 476–480): `net = closes_p.iloc[-1] -
   closes_p.iloc[-21]` and `path = closes_p.tail(21).diff().abs().sum()`.
   - `closes_p.iloc[-1]` = prior close
   - `closes_p.iloc[-21]` = close 20 days before prior close
   - `net` = total price change over 20 days
   - `path` = sum of absolute day-to-day changes over 21 bars (20 changes)
   - `net / path` ∈ [-1, 1]. 1 = straight line up. -1 = straight line down.
     Near 0 = choppy.
   - **Verify**: the denominator uses `closes_p.tail(21).diff().abs().sum()`.
     `tail(21)` gives 21 bars. `.diff()` on 21 bars gives 20 differences.
     This is correct for a 20-day window.

6. **`adx14`** (line 475, computed via `_adx14` lines 192–222): **Verify** the
   Wilder smoothing implementation against the canonical ADX formula:
   - `tr = max(H-L, |H-prevC|, |L-prevC|)` — lines 197–198. Correct.
   - `+DM = H-prevH if H>prevH and H-prevH > prevL-L else 0` — line 200. Correct.
   - `-DM = prevL-L if prevL>L and prevL-L > H-prevH else 0` — line 201. Correct.
   - Wilder smoothing: `smooth[i] = smooth[i-1] - smooth[i-1]/period + raw[i]`.
     The implementation (lines 207–211):
     ```python
     out[period-1] = x[:period].sum()  # initial value = sum of first N
     for i in range(period, len(x)):
         out[i] = out[i-1] - out[i-1]/period + x[i]
     ```
     Wait — this is `out[i] = out[i-1] * (1 - 1/N) + x[i]`. The canonical Wilder
     smoothing is `out[i] = out[i-1] * (N-1)/N + x[i]`. Expanding:
     `out[i] = out[i-1] - out[i-1]/N + x[i]`. **CORRECT**. 
   - **But verify the initial value**: Wilder's original method uses a simple
     average of the first N values as the initial smoothed value. The code uses
     `x[:period].sum()` — that's a SUM, not an average. This makes the initial
     value N× too large. **THIS IS A BUG**.
   - Wait, let me re-read: `out[period-1] = x[:period].sum()`. For period=14,
     this sums 14 values. The canonical initial value is the MEAN of the first 14,
     not the sum. So the initial smoothed ATR/ADX value would be 14× too large.
   - **But** — the final ADX value uses the SAME smoothing function for ATR, +DM,
     and -DM. Since all three are inflated by the same factor at initialization,
     the ratios (+DI, -DI) might partially cancel out. But the smoothing error
     propagates differently through the three series because they have different
     input values. **Verify**: does the initial-value error matter after 14+
     periods of smoothing? The error decays as `(1 - 1/14)^n`. After 14 periods,
     ~36% of the initial error remains. After 28 periods, ~13%. So for stocks
     with just enough history (28 bars), the ADX could be off by ~10-15%.

7. **`realized_vol_percentile_252`** (lines 499–502): 
   ```python
   roll = rets.rolling(20).std().dropna().tail(252)
   f["realized_vol_percentile_252"] = float((roll <= float(roll.iloc[-1])).mean())
   ```
   - `roll.iloc[-1]` is the CURRENT 20d vol (the last value in the distribution).
   - The percentile is computed IN-SAMPLE (current value in the reference set).
   - Minimum possible percentile: 1/len(roll).
   - Maximum: 1.0.
   - **Verify**: is `len(roll) >= 50` guard (line 501) sufficient for meaningful
     percentiles? With only 50 values, granularity is 2% per rank. Reasonable
     minimum.

8. **`excess_return_information_ratio_60d`** (lines 615–622):
   ```python
   ex = j.iloc[:, 0] - j.iloc[:, 1]  # stock_ret - spy_ret
   f["excess_return_information_ratio_60d"] = float((252**0.5) * ex.mean() / ex.std())
   ```
   - This is annualized IR = sqrt(252) * mean(excess) / std(excess).
   - **Verify**: the `ex.std()` is the denominator. If std is 0 (stock perfectly
     tracks SPY), this divides by zero. The code checks `if float(ex.std()) > 0`
     at line 621 — correct.

9. **`max_drawdown_20d`** (lines 623–625):
   ```python
   w = closes_p.tail(20); peak = w.cummax()
   f["max_drawdown_20d"] = float(((w - peak) / peak).min()) * 100.0
   ```
   - This returns a NEGATIVE number (e.g., -5.3 for a 5.3% drawdown).
   - **Verify**: is a negative drawdown consistent with the rest of the feature
     set? Features like `dist_from_20d_high_pct` also return negative numbers
     (distance below the high). So negative is consistent. But the name
     "max_drawdown" typically implies a positive magnitude. This is a naming
     issue, not a formula bug.

---

### 2C. Definition Consistency (MEDIUM priority)

Several features compute "gaps" but use different definitions of "gap":

1. **Gap vs prior HIGH** (lines 189, 306): `gap_pct_vs_prior_high = (open -
   prior_high) / prior_high * 100`. This is the canonical gap-and-go definition
   from d01.

2. **Gap vs prior CLOSE** (lines 191, 307): `gap_pct_vs_prior_close = (open -
   prior_close) / prior_close * 100`. Different definition.

3. **`gap_range_frac`** (line 541): `(o - pc) / (ph - pl)` where `pc` = prior
   close, `ph` = prior high, `pl` = prior low. Uses gap-vs-close as numerator
   but prior range as denominator. Consistent with its stated thesis (gap relative
   to prior day's action).

4. **`consecutive_gap_up_days`** (lines 542–553): uses `opens[i] > cls[i-1]`
   which is a gap-vs-CLOSE definition. **BUT** the A-section gap features and
   the d-family strategies define gaps as open-vs-prior-HIGH. **This is an
   inconsistency**. A day where `open > prior_close` but `open < prior_high`
   would be counted as a "gap up" by this feature but would NOT be a gap-up
   candidate for the d-family strategies. **Verify**: is this intentional or a
   bug?

5. **`gap_vs_spy_gap_diff`** (lines 554–559): computes `(o - pc) / pc * 100` for
   the stock and compares to `(spy_open - spy_prior_close) / spy_prior_close *
   100` for SPY. Both use gap-vs-CLOSE. But the A-section `rel_spy_gap` (line
   391) uses gap-vs-HIGH. **Two different "relative gap" definitions exist in
   the same feature set — this is confusing**.

6. **`gap_zscore_60d`** (lines 594–601): historical gaps are computed as
   `(open - prior_high) / prior_high` — matches `gap_pct_vs_prior_high`. Good.
   Consistent with the primary gap definition.

7. **AM/PM boundary conventions** (see 2B.1–2B.2): different `between_time`
   calls use different `inclusive` settings. Map all of them:
   - Line 424: AM `("09:30", "12:00", inclusive="left")` — includes 09:30, excludes 12:00
   - Line 425: PM `("12:00", "16:00", inclusive="both")` — includes 12:00, includes 16:00
   - Line 433: first_hour `("09:30", "10:30", inclusive="both")` — includes both
   - Line 435: late `("14:00", "16:00", inclusive="both")` — includes both
   - Line 437: afternoon `("13:00", "16:00", inclusive="both")` — includes both
   - Line 442: opening_30m `("09:30", "10:00", inclusive="left")` — includes 09:30, excludes 10:00
   - Is there a reason for the inconsistent use of `"left"` vs `"both"`?
     `"left"` for AM boundaries seems intended to avoid double-counting the
     12:00 bar with PM. But `"left"` for opening_30m means the 10:00 bar is
     excluded — is that correct? The 09:30–10:00 window with `"left"` includes
     09:30, 09:35, 09:40, 09:45, 09:50, 09:55 — six bars. With `"both"`, it
     would include 10:00 as well — seven bars. Which is intended?

8. **Z-score reference windows**: 
   - `gap_zscore_60d` uses 60-day tail, current value IN the distribution
   - `prior_return_zscore_60d` uses 60-day tail, current value NOT in distribution
   - `first_range_zscore_20d` uses 20-day tail, current value IN the distribution
   - `opening_volume_zscore_20d` uses 20-day tail, current value IN the distribution
   - **This inconsistency in whether the current value is in the reference set
     matters for outlier detection**. A value in its own distribution will never
     have a z-score beyond `(n-1)/sqrt(n)` ≈ 4.36 for n=20. This is acceptable
     for feature engineering (we're not doing hypothesis testing), but the
     inconsistency should be documented.

---

### 2D. Edge Cases & Crash Safety (HIGH priority)

Trace each code path where inputs can be None, empty, or have insufficient data:

1. **`_adx14`** (line 192): `if pdf is None or len(pdf) < 2 * period + 2`. For
   period=14, this requires 30 bars minimum. **Verify**: is this sufficient?
   Wilder ADX needs 2×14=28 bars (14 for initial smoothing + 14 for ADX
   smoothing). The `+2` gives a small buffer. After `dropna()` on TR, +DM, -DM
   (each has one leading NaN from shift), the effective minimum is ~29 bars.
   **Verify**: does `_adx14` correctly handle the case where all +DM or all -DM
   are zero? Lines 215-217 use `np.where(atr == 0, np.nan, atr)` to avoid
   division by zero in +DI/-DI. And `np.where((pdi + mdi) == 0, np.nan, pdi+mdi)`
   for DX. Then DX is filtered with `~np.isnan(dx)`. If all DX values are NaN
   (e.g., no directional movement at all), `len(dx) < period` returns None.
   **This is correct but verify the edge case**.

2. **`_session_vwap`** (line 181–189): `vol.sum() <= 0` returns None. **Verify**:
   what if `typ` has Inf or NaN? `(typ * vol).sum()` would be NaN → `vol.sum()` > 0
   but result is NaN. **Add a NaN check on the final value**.

3. **`prior_close_vs_vwap_pct`** (lines 419–423): checks `if vwap and vwap > 0`
   before computing. But `vwap` is a float, not Optional[bool]. `if vwap` is
   falsy for 0.0 but truthy for negative values. Hmm, actually `if vwap and vwap >
   0` — if vwap is None, `if None` is falsy, short-circuits. If vwap is NaN, `if
   NaN` is falsy, short-circuits. If vwap is negative, `if vwap` is truthy (non-zero
   float), then `vwap > 0` is False, short-circuits. **This is correct but subtle**.

4. **`prior_pm_am_range_ratio`** (line 424–430): checks `if not am.empty and not
   pm.empty`. But what if `am_rng == 0` (all morning bars had same high/low)?
   Division by zero at line 430 — `pm_rng / am_rng` would be `inf`.
   **Add a guard: `if am_rng > 0`**.

5. **`prior_first_hour_vol_frac`** (lines 432–434): `if tot_v > 0` guard on
   total volume. Then `fh["volume"].sum() / tot_v`. If `fh` is empty (all first-
   hour bars missing), `fh["volume"].sum()` is 0.0. **Verify**: can `fh` be
   empty? `between_time("09:30", "10:30", inclusive="both")` on a full session
   should always return bars. But for a partial session (early close), it might
   not. The `if tot_v > 0` guard covers the division but doesn't distinguish
   "zero first-hour volume" from "first hour missing". Both give 0.0.

6. **`prior_afternoon_return_pct`** (lines 437–441): takes `aft["open"].iloc[0]`
   without checking that `aft` has rows. The `between_time` call at line 437 uses
   `("13:00", "16:00", inclusive="both")`. If the session has no bars after 13:00
   (e.g., half-day), `aft` would have 0 rows. Then `.iloc[0]` raises
   `IndexError`. **This is a crash bug**. **Fix**: add `if not aft.empty`
   before accessing `.iloc[0]`. Or at minimum, the existing `if not aft.empty`
   check at line 438 should come BEFORE line 439.

   Wait — line 438 IS `if not aft.empty:` before line 439. So this IS guarded.
   OK, good.

7. **`prior_open_to_close_conviction`** (lines 453–454): `abs(pc - po) / (ph -
   pl)`. Guarded by `if ph - pl > 0`. **Verify**: what if `pc == po` (doji day)?
   The result is 0.0, which is correct (no conviction). What if the prior day's
   range is 0 (ph == pl, flat day)? Guarded by `ph - pl > 0`. Good.

8. **`sma20_vs_sma50_pct`** (lines 468–470): `(s20 / s50 - 1.0) * 100.0`. Guard:
   `if s50 > 0`. **Verify**: what if s50 is negative? Then `s50 > 0` is False,
   feature stays None. But SMAs of positive prices are always positive, so this
   is fine.

9. **`sma50_vs_sma200_pct`** (lines 471–474): same pattern with `s200 > 0`.
   Requires 200 bars. If `daily_lookback_days` is less than ~320 calendar days,
   all tickers return None. The capture variant sets `daily_lookback_days = 420`,
   so this is covered for the capture path but not for arbitrary strategy usage.

10. **`opening_volume_zscore_20d`** (lines 563–567): guarded by `sd > 0`. If all
    20 prior opening volumes are identical (sd=0), z-score is undefined → None.
    Correct.

11. **`dollar_volume_trend_5_20`** (lines 573–577): `dv.tail(5).mean() / d20`.
    Guarded by `d20 > 0`. If d20 is 0 (all zero volume in last 20 days?), feature
    stays None. Realistic only for delisted/error tickers.

12. **`is_first_trading_day_of_month`** (lines 580–583): compares `last_dt.month
    != trade_date.month or last_dt.year != trade_date.year`. `last_dt` is
    `pdf.index[-1]` — the last daily bar before trade_date. If the last trading
    day was in a different month/year than trade_date, today is the first trading
    day of the month. **Verify**: what if there's a multi-day gap (e.g., Monday
    after a holiday weekend, or the ticker wasn't traded for a week)? The feature
    would still be 1.0 because the last bar's month differs. This is correct
    behavior for "first trading day of month" — it's about whether this IS the
    first day, not whether yesterday was the last day of the previous month.
    Actually, wait: if the ticker didn't trade for the last 3 days of March and
    today is April 3, `last_dt` would be March 28 (if that was the last trading
    day). Then `last_dt.month (3) != trade_date.month (4)` → True → feature is
    1.0. But April 3 is NOT the first trading day of April (April 1 was, even if
    this ticker didn't trade). **This is a bug for tickers with gaps in their
    trading history**. The feature should check against a trading calendar, not
    the ticker's own sparse history. For the SP500 universe this is minor
    (tickers trade every day), but for smaller universes or ETFs it could be
    wrong.

13. **`days_since_opex`** (lines 584–591): uses `_third_friday` to find the
    reference opex date. The computation: if trade_date > this month's 3rd Friday,
    use this month's; otherwise use last month's. Then `(trade_date - ref).days`
    gives CALENDAR days, not trading days. **This is documented in the prompt
    proposals as "trading days since opex" but the implementation gives calendar
    days**. Is this intentional? Calendar days is simpler and still captures the
    opex-proximity signal. But the variable name `days_since_opex` doesn't
    specify calendar vs trading. Minor naming issue.

14. **`gap_zscore_60d`** (line 596–601): `hist_gap = ((pdf["open"].astype(float) -
    ph_series.shift(1)) / ph_series.shift(1) * 100.0).dropna().tail(60)`.
    **Verify**: the `ph_series` is `pdf["high"].astype(float)`. `ph_series.shift(1)`
    shifts the series by 1 — the first element becomes NaN. Then the division
    `pdf["open"] / ph_series.shift(1)` has NaN in position 0. `.dropna()` removes
    it. Then `.tail(60)` takes the last 60 (non-NaN) values. **But**: does
    `.tail(60)` take the last 60 elements of the ENTIRE `hist_gap` series (after
    dropna), or the last 60 rows of the original DataFrame alignment? It takes
    the last 60 elements of the dropped series, which is correct. **Verify**: the
    alignment of `pdf["open"]` and `ph_series.shift(1)` — they share the same
    index since both come from `pdf`. pandas aligns by index automatically.
    Correct.

---

### 2E. Performance (LOW priority)

1. **`_opening_bar_volumes` called twice** (lines 337 and 563): both calls
   `groupby` + `between_time` on the same `hist_5m`. The second call could reuse
   the first result. Not a bug, but ~2× redundant work for the GroupBy.

2. **`_opening_bar_ranges_pct`** (line 156–167): also does `groupby` +
   `between_time`. If both `_opening_bar_volumes` and `_opening_bar_ranges_pct`
   are called (which they are), we do the same `between_time` + `groupby` twice.
   Could unify into a single helper that returns both volume and range series.

3. **`_adx14`** (lines 192–222): the `wsmooth` inner function is redefined on
   every call. **Move it to module level or use `@staticmethod` pattern**. Not a
   correctness issue but slightly wasteful.

4. **`compute_candidate_features`** now does ~650 lines of computation. With
   ~500 tickers × ~250 days = 125,000 calls in a capture run, even small
   inefficiencies compound. The double-`_opening_bar_volumes` call alone is
   ~250,000 GroupBy operations.

---

### 2F. Test Coverage (MEDIUM priority)

Read `trading/lab/tests/test_features.py` lines 1–230.

1. **`test_new_features_coverage_rich_inputs`** (line 190–200): asserts all
   features in `_NEW_FEATURES` are non-null with rich inputs. Good smoke test.
   **But**: this only tests the "happy path" — all inputs present, healthy data.
   **No tests for**: zero denominators, empty hist_5m, single-bar daily, missing
   sector_daily, missing spy_daily, split-like jumps (`split_63`/`split_252`),
   ADX with flat price series, VWAP with all-zero volume.

2. **`test_new_features_leak_free_hist_5m`** (line 203–217): poisons hist_5m
   with a bar dated on trade_date, verifies 4 features unchanged. Good.
   **But**: only checks 4 features. Should check at least all A2-group features
   (prior_close_vs_vwap_pct, prior_pm_am_range_ratio, etc.) plus F2
   (opening_volume_zscore_20d) plus H2 (first_range_zscore_20d).

3. **Untested features (no dedicated test)**: `adx14`, `trend_efficiency_20d`,
   `stock_sector_corr_60d`, `beta_to_sector_60d`, `sector_20d_return`,
   `sector_20d_ret_minus_spy`, `gap_range_frac`, `consecutive_gap_up_days`,
   `gap_vs_spy_gap_diff`, `prior_volume_ratio_20d`, `dollar_volume_trend_5_20`,
   `is_first_trading_day_of_month`, `gap_zscore_60d`, `prior_return_zscore_60d`,
   `excess_return_information_ratio_60d`, `max_drawdown_20d`,
   `realized_vol_percentile_252`, `vol_ratio_5d_20d`, `prior_range_expansion_14d`,
   `spy_realized_vol_20d`, `spy_20d_return`, `close_channel_pos_20d`,
   `sma20_vs_sma50_pct`, `sma50_vs_sma200_pct`, `roc_5d`, `roc_20d`,
   `consecutive_down_days`, `prior_open_to_close_conviction`,
   `prior_gap_fill_fraction`, `prior_late_volume_share`,
   `prior_afternoon_return_pct`, `prior_opening_30m_range_frac`,
   `opening_volume_zscore_20d`, `prior_volume_ratio_20d`,
   `dollar_volume_trend_5_20`, `gap_zscore_60d`, `prior_return_zscore_60d`,
   `first_range_zscore_20d`, `excess_return_information_ratio_60d`,
   `max_drawdown_20d`.

   That's ~37 features with no dedicated correctness test. They're only tested
   for "non-null with rich inputs" which is a smoke test, not a correctness test.

4. **`test_leak_free_future_rows_ignored`** (line 117–131): tests daily bar
   leak. **Does NOT test leak via hist_5m with future 5m bars that are dated on
   trade_date** — this IS tested in `test_new_features_leak_free_hist_5m` but only
   for 4 features.

5. **Test fixtures `_daily_noisy` and `_hist_5m`**: use random number generators
   with fixed seeds. Good for reproducibility. **But**: random data can
   accidentally produce degenerate cases (e.g., all returns positive, zero
   variance). With seed=1 and 300 bars, this is unlikely but not impossible.
   Consider adding assertions on the generated data properties.

---

### 2G. Integration & Wiring (MEDIUM priority)

1. **Capture variant** (`capture.py` line 49–60): `build_candidates` calls
   `super().build_candidates(context)` (d01's logic), then for each candidate
   calls `features_from_context(context, c.ticker, sector_symbol=etf)`.
   **Verify**: `sector_map.get(c.ticker)` at line 55 — what if the ticker is NOT
   in the sector map? It returns None. Then `features_from_context` is called
   with `sector_symbol=None`. The adapter at line 640: `sector_daily =
   context.extra_daily.get(sector_symbol) if sector_symbol else None`. When
   `sector_symbol` is None, `sector_daily` is None. All sector-dependent features
   return None. This is correct and graceful. **But verify**: does this mean ~20%
   of tickers (those not in SPDR sectors) get None for all D2 features?

2. **`FEATURE_NAMES` ordering** (lines 38–83): the capture script at
   `capture_features.py` line 91 does `feats.reindex(columns=list(FEATURE_NAMES))`.
   If a feature key is in `FEATURE_NAMES` but NOT computed in
   `compute_candidate_features()`, it appears as a column of all-NaN. If a feature
   is computed but NOT in `FEATURE_NAMES`, it's silently dropped from the capture
   ledger. **Verify**: every key in `FEATURE_NAMES` has a corresponding
   `f["key"] = ...` assignment, and vice versa. Walk the entire
   `compute_candidate_features()` body and compare against `FEATURE_NAMES`.

3. **`has_split_like_jump` import** (line 33): this is now imported from
   `filters`. Verify the function wasn't modified during the feature expansion
   (it wasn't — filters.py is unchanged). Check that the function handles the new
   call signature `has_split_like_jump(daily, trade_date, lookback=63)` correctly.
   The 2nd positional arg is `trade_date`, and `lookback=63` is a keyword. In
   `has_split_like_jump`, `trade_date` is used to slice daily bars before
   `trade_date` at line 119. With `lookback=63`, it checks the trailing 63 bars
   for >40% close-to-close jumps. Good.

4. **`_opening_bar_volumes` signature change**: was `(hist_5m)`, now
   `(hist_5m, trade_date=None)`. The `trade_date` parameter is optional with
   default None for backward compatibility. **Verify**: no external callers
   (outside features.py) call this function without `trade_date`. grep for
   `_opening_bar_volumes` or `opening_bar_volumes` in the full codebase.

---

### 2H. regressions in Original Features (MEDIUM priority)

The original 41 features are in lines 266–408. Verify they weren't accidentally
changed:

1. **`_opening_bar_volumes` now takes `trade_date`** (line 144). The call at
   line 337 passes `trade_date`. Before the change, the function didn't filter
   by date — it used whatever `hist_5m` contained. If `hist_5m` previously
   included bars on or after `trade_date` (which it shouldn't have in the
   standard hydration path), the behavior changed: those bars are now filtered
   out. **Verify**: the `historical_5m_lookback_days` hydration in
   `pipeline.py:_load_context` (lines 976–983) uses `_trading_days(...,
   trade_date - timedelta(days=1))` — so prior sessions only, ending the day
   before trade_date. So this is a no-op change. Safe.

2. **`first_regular_5m_candle` import** (line 31): still imported and used at
   lines 235, 394, 555. Unchanged.

3. **`_spy_gap_pct`** (lines 232–242): unchanged. Still computes `open - prior_high`.

4. **`_ret_pct`** (lines 96–103): unchanged.

5. **`_sma_dist_pct`** (lines 106–112): unchanged.

6. **`_below_sma`** (lines 115–126): unchanged.

---

## 3. Review Output Format

After reading all files, produce findings in this structure:

### Executive Summary
One paragraph: total bugs found, worst severity, overall assessment.

### HIGH Severity (crashes, look-ahead leaks, formula errors that invert signals)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | features.py:XXX | ... | ... |

### MEDIUM Severity (inconsistencies, edge-case None handling gaps, performance)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | ... | ... | ... |

### LOW Severity (naming, documentation, minor optimization)

| # | File:Line | Description | Fix |
|---|-----------|-------------|-----|
| 1 | ... | ... | ... |

### Test Coverage Gaps
List features with zero correctness tests, ranked by complexity (most complex = highest priority to test).

### FEATURE_NAMES vs compute_candidate_features Cross-Reference
List any keys in FEATURE_NAMES that are never assigned (missing features), and any features computed but not in FEATURE_NAMES (orphan computations).

### Unresolved Questions
Questions the reviewer cannot answer without running the code or asking the author.

---

## 4. How to Execute This Review

1. Read `features.py` in full. Build a mental map of every `f["key"] = ...` assignment and every helper function.
2. Read `test_features.py` in full. Note what's tested and what's not.
3. Read `capture.py` to understand the integration path.
4. For each HIGH-priority checklist item in §2A–§2D above, find the exact lines and verify the logic.
5. Run `grep` / `search_files` across the codebase to find callers of modified functions (`_opening_bar_volumes`, `has_split_like_jump`).
6. Cross-reference `FEATURE_NAMES` (lines 38–83) against all `f["..."] =` assignments (lines 267–625).
7. Run the existing test suite: `PYTHONPATH=engine python3 -m pytest trading/lab/tests/test_features.py -x -q`. Report pass/fail.
8. Write findings in the output format above.
