# Candidate-Admission Feature Review

**Reviewer:** Codex
**Date:** 2026-06-14
**Scope:** Leak-free long-only stock/ETF admission features available by 09:35 ET

## Executive Recommendation

Capture broadly, but do not immediately search all captured columns. The best
next additions are the features that normalize today's setup against the
ticker's own history or expose prior-session accumulation:

1. `prior_close_vs_vwap_pct`
2. `prior_opening_30m_range_frac`
3. `prior_late_volume_share`
4. `gap_zscore_60d`
5. `opening_volume_zscore_20d`
6. `first_range_zscore_20d`
7. `prior_range_expansion_14d`
8. `stock_sector_corr_60d`

These are continuous, mostly high-coverage, and less duplicative than adding
more fixed technical thresholds. They should be captured as columns first, then
introduced only through a small pre-registered search grid.

Two implementation details are prerequisites:

- Add a `_prior_intraday_session(hist_5m, trade_date)` helper that explicitly
  removes rows whose local date is on or after `trade_date`. The current
  `_opening_bar_volumes()` trusts runner hydration and does not enforce this
  boundary itself.
- Preserve raw-price consistency and either reject split-like windows before
  using return/volume histories or return `None` when the requested lookback
  crosses a known discontinuity.

The capture release already requests 420 calendar days of daily data and 30
prior intraday sessions. That is enough for every proposal below except the
252-window volatility percentile, which needs approximately 272 valid daily
closes and will be sparse for recent IPOs.

## Shared Intraday Convention

The category-A and historical opening-bar features below assume:

```python
def prior_rth_session(hist_5m, trade_date):
    if hist_5m is None or hist_5m.empty:
        return None
    h = hist_5m.sort_index()
    if h.index.tz is not None:
        h = h.tz_convert("America/New_York")
    h = h[h.index.date < trade_date]
    if h.empty:
        return None
    prior_date = max(h.index.date)
    p = h[h.index.date == prior_date].between_time(
        "09:30", "16:00", inclusive="left"
    )
    return p if not p.empty else None

def bar_vwap(bars):
    volume = bars["volume"].astype(float)
    if volume.sum() <= 0:
        return None
    typical = (
        bars["high"].astype(float)
        + bars["low"].astype(float)
        + bars["close"].astype(float)
    ) / 3.0
    return float((typical * volume).sum() / volume.sum())
```

Early-close sessions should remain valid for full-session VWAP features, but
features requiring a 14:00-16:00 window should return `None`.

## A. Prior-Day Intraday Structure

### Feature: `prior_close_vs_vwap_pct`

- **Category**: A - prior-day intraday structure
- **Primitives used**: `daily`, `hist_5m`
- **Computation**: `100 * (prior_daily_close / prior_session_vwap - 1)`.
- **Thesis**: A close above the prior session's volume-weighted cost basis
  indicates that late holders were profitable rather than trapped. Positive
  values should favor next-day continuation; deeply negative values identify
  overhead supply.
- **Expected non-null rate**: Above 95% when at least one complete prior RTH
  session is hydrated.
- **Prior art**: VWAP is a standard execution benchmark and institutional cost
  basis proxy.
- **Risk of look-ahead**: None if the selected intraday session is strictly
  before `trade_date`. Do not use a provider's current partial session.

### Feature: `prior_opening_30m_range_frac`

- **Category**: A - prior-day intraday structure
- **Primitives used**: `hist_5m`
- **Computation**:

  ```python
  opening = prior.between_time("09:30", "09:59")
  full_range = prior["high"].max() - prior["low"].min()
  value = (
      (opening["high"].max() - opening["low"].min()) / full_range
      if len(opening) >= 6 and full_range > 0 else None
  )
  ```

- **Thesis**: A large fraction means price discovery happened immediately and
  the rest of the session consolidated; a small fraction means the move kept
  expanding after the open. The latter is more compatible with sustained
  momentum.
- **Expected non-null rate**: Above 90% with complete prior 5-minute data.
- **Prior art**: Opening-range and initial-balance analysis.
- **Risk of look-ahead**: None; all bars belong to the prior session.

### Feature: `prior_pm_vs_am_vwap_pct`

- **Category**: A - prior-day intraday structure
- **Primitives used**: `hist_5m`
- **Computation**: Compute separate VWAPs for 09:30-11:59 and 12:00-close;
  return `100 * (pm_vwap / am_vwap - 1)`.
- **Thesis**: Positive values indicate that meaningful afternoon volume
  transacted above the morning cost basis, a cleaner accumulation signal than
  the final print alone.
- **Expected non-null rate**: Above 90%; lower on incomplete sessions.
- **Prior art**: Intraday volume-weighted trend and execution-benchmark
  analysis.
- **Risk of look-ahead**: None. Require positive volume in both windows.

### Feature: `prior_late_volume_share`

- **Category**: A - prior-day intraday structure
- **Primitives used**: `hist_5m`
- **Computation**: `sum(volume from 14:00 to close) / sum(full-session volume)`.
- **Thesis**: High late-day participation combined with a strong close is
  consistent with institutional accumulation and may improve gap continuation.
  Very high values without price progress can instead flag distribution, so
  this feature is best searched jointly with `prior_close_vs_vwap_pct`.
- **Expected non-null rate**: About 90% on regular sessions; `None` on early
  closes or incomplete afternoon histories.
- **Prior art**: The intraday U-shaped volume curve and close-auction
  participation.
- **Risk of look-ahead**: None; use the actual prior session only.

### Feature: `prior_afternoon_return_pct`

- **Category**: A - prior-day intraday structure
- **Primitives used**: `hist_5m`
- **Computation**: `100 * (last_close / first_bar_at_or_after_13_00.open - 1)`.
- **Thesis**: Positive afternoon drift distinguishes a close near the high
  produced by persistent demand from one produced only by an opening spike.
- **Expected non-null rate**: Above 90% on complete regular sessions.
- **Prior art**: Intraday momentum and close-to-close continuation research.
- **Risk of look-ahead**: None. Return `None` if the 13:00 anchor or closing bar
  is unavailable.

### Feature: `prior_gap_fill_fraction`

- **Category**: A/E - prior-day intraday and overnight structure
- **Primitives used**: `daily`
- **Computation**:

  ```python
  gap = prior_open - close_two_days_ago
  value = clip((prior_open - prior_low) / gap, 0.0, 1.0) if gap > 0 else None
  ```

- **Thesis**: Zero means yesterday's gap-up never retraced toward the old close;
  one means it fully filled. Gap holding is evidence of demand and less
  overhead supply for today's long setup.
- **Expected non-null rate**: The fraction is non-null only after prior gap-up
  sessions; usually 40-55% of observations.
- **Prior art**: Common gap-fill/hold classification in gap trading systems.
- **Risk of look-ahead**: None; it describes the completed prior daily bar.

## B. Multi-Timeframe Trend Alignment

### Feature: `close_channel_pos_20d`

- **Category**: B - multi-timeframe trend
- **Primitives used**: `daily`
- **Computation**:

  ```python
  low20 = prior["low"].tail(20).min()
  high20 = prior["high"].tail(20).max()
  value = (prior_close - low20) / (high20 - low20)
  ```

- **Thesis**: Values near one identify established leaders; values near zero
  identify weak names where a gap may be only a countertrend bounce. Unlike
  `dist_from_20d_high_pct`, this normalizes by the full channel width.
- **Expected non-null rate**: Above 98% with 20 sessions of history.
- **Prior art**: Donchian channel position and price momentum.
- **Risk of look-ahead**: None; the channel ends at the prior session.

### Feature: `sma20_vs_sma50_pct`

- **Category**: B - multi-timeframe trend
- **Primitives used**: `daily`
- **Computation**: `100 * (SMA20 / SMA50 - 1)`, both ending at prior close.
- **Thesis**: Measures trend alignment and crossover magnitude continuously.
  It is more informative than a binary golden-cross flag and does not duplicate
  the prior close's distance from either average.
- **Expected non-null rate**: Above 95% with 50 sessions of history.
- **Prior art**: Moving-average crossover systems.
- **Risk of look-ahead**: None.

### Feature: `adx14`

- **Category**: B - multi-timeframe trend
- **Primitives used**: `daily`
- **Computation**: Standard Wilder ADX(14): derive true range and directional
  movements, Wilder-smooth `TR`, `+DM`, and `-DM`, compute `+DI`, `-DI`, `DX`,
  then Wilder-smooth `DX` for the final ADX. Require at least 28 valid bars.
- **Thesis**: A gap in an already directional tape is more likely to continue
  than the same gap in a directionless tape. ADX intentionally measures trend
  strength rather than direction.
- **Expected non-null rate**: Above 95% for established listings.
- **Prior art**: J. Welles Wilder's Directional Movement System.
- **Risk of look-ahead**: None. The implementation must not center or
  backward-fill rolling values.

### Feature: `trend_efficiency_20d`

- **Category**: B - multi-timeframe trend
- **Primitives used**: `daily`
- **Computation**:

  ```python
  net = close.iloc[-1] - close.iloc[-21]
  path = close.tail(21).diff().abs().sum()
  value = net / path if path > 0 else None  # range [-1, 1]
  ```

- **Thesis**: Separates smooth advances from noisy names that reached the same
  20-day return through repeated reversals. Positive, high-efficiency trends
  should be better long continuation candidates.
- **Expected non-null rate**: Above 98% with 21 sessions.
- **Prior art**: Kaufman's efficiency-ratio concept.
- **Risk of look-ahead**: None.

## C. Volatility Regime and Compression

### Feature: `realized_vol_ratio_5_20`

- **Category**: C - volatility regime
- **Primitives used**: `daily`
- **Computation**: `std(last 5 close returns) / std(last 20 close returns)`.
- **Thesis**: Values below one identify short-term compression before the gap;
  values above one identify an already expanding or unstable tape. This is a
  scale-free squeeze/expansion measure.
- **Expected non-null rate**: Above 98% with 21 closes.
- **Prior art**: Volatility clustering and short/long realized-volatility
  ratios; conceptually similar to squeeze indicators.
- **Risk of look-ahead**: None. Return `None` when long-window volatility is
  effectively zero.

### Feature: `realized_vol_percentile_20d_252`

- **Category**: C - volatility regime
- **Primitives used**: `daily`
- **Computation**: Build trailing 20-return standard deviation for each prior
  date. Rank the latest value within the last 252 valid values:
  `mean(reference <= current)`.
- **Thesis**: Converts absolute volatility into the ticker's own regime. A 2%
  daily volatility is extreme for one ETF and ordinary for a biotech stock.
- **Expected non-null rate**: Above 85% for mature S&P 500 names with the
  capture release's 420-calendar-day history; materially lower for recent IPOs.
- **Prior art**: Historical-volatility percentile/regime normalization.
- **Risk of look-ahead**: None. The reference distribution must end at the
  prior close, not at the capture dataset's final date.

### Feature: `prior_range_expansion_14d`

- **Category**: C - volatility regime
- **Primitives used**: `daily`
- **Computation**:

  ```python
  prior_range = high.iloc[-1] - low.iloc[-1]
  baseline = (high - low).iloc[-15:-1].mean()
  value = prior_range / baseline if baseline > 0 else None
  ```

- **Thesis**: A large prior range can signal either fresh information and
  follow-through or exhaustion. As a continuous feature it can test both
  hypotheses without hard-coding a direction.
- **Expected non-null rate**: Above 98% with 15 sessions.
- **Prior art**: Range-expansion/NR-style setups and ATR-normalized range.
- **Risk of look-ahead**: None. Excluding the prior day from the baseline avoids
  mechanically pulling the ratio toward one.

## D. Sector and Market Context

### Feature: `stock_sector_corr_60d`

- **Category**: D - sector context
- **Primitives used**: `daily`, `sector_daily`
- **Computation**: Inner-join stock and sector daily returns by date; return
  Pearson correlation over the latest 60 aligned returns, requiring at least
  30.
- **Thesis**: Low correlation indicates an idiosyncratic story; high
  correlation indicates sector beta. Either regime may work, but this feature
  lets the search distinguish them instead of relying only on relative return.
- **Expected non-null rate**: Same as the sector mapping, high for mapped
  large-cap names and lower in a broad universe.
- **Prior art**: Single-factor market/industry models.
- **Risk of look-ahead**: None. Join on actual dates; do not align by row
  position or forward-fill missing returns.

### Feature: `beta_to_sector_60d`

- **Category**: D - sector context
- **Primitives used**: `daily`, `sector_daily`
- **Computation**: `cov(stock_return, sector_return) / var(sector_return)` over
  the latest 60 aligned returns, requiring at least 30 and nonzero variance.
- **Thesis**: Distinguishes ordinary high-beta sector participation from a move
  that is large after controlling for the stock's normal sensitivity.
- **Expected non-null rate**: Same as `stock_sector_corr_60d`.
- **Prior art**: CAPM-style beta extended to industry factors.
- **Risk of look-ahead**: None.

### Feature: `sector_20d_ret_minus_spy`

- **Category**: D - sector context
- **Primitives used**: `sector_daily`, `spy_daily`
- **Computation**: `sector_20d_return - SPY_20d_return`.
- **Thesis**: A stock gap occurring in a leading sector has a different
  continuation prior from the same stock-specific move in a lagging sector.
  This also disambiguates the existing stock-minus-sector feature.
- **Expected non-null rate**: Same as sector mapping, with more than 95% SPY
  coverage.
- **Prior art**: Sector rotation and relative-strength ranking.
- **Risk of look-ahead**: None.

## E. Overnight Structure

### Feature: `gap_range_frac`

- **Category**: E - overnight structure
- **Primitives used**: `first_bar`, `daily`
- **Computation**:

  ```python
  denom = prior_high - prior_low
  value = (today_open - prior_close) / denom if denom > 0 else None
  ```

- **Thesis**: Measures the overnight move in units of the immediately relevant
  prior-day range. It is more local than `gap_atr` and can distinguish a
  meaningful gap after compression from an ordinary move after a wide session.
- **Expected non-null rate**: Above 99%.
- **Prior art**: Range-normalized gap classification.
- **Risk of look-ahead**: None; today's open is known at 09:30.

### Feature: `consecutive_gap_up_days`

- **Category**: E - overnight structure
- **Primitives used**: `first_bar`, `daily`
- **Computation**: If today's open is not above prior close, return `0`.
  Otherwise return `1` plus the trailing count of prior sessions where
  `open_t > close_(t-1)`.
- **Thesis**: Repeated gap-ups can identify persistent demand, but long streaks
  may flag exhaustion. A numeric streak allows both effects to be tested.
- **Expected non-null rate**: Above 99% with two prior sessions.
- **Prior art**: Gap-sequence and price-persistence rules.
- **Risk of look-ahead**: None; only today's open and completed daily bars are
  used.

### Feature: `gap_zscore_60d`

- **Category**: E/H - overnight and statistical
- **Primitives used**: `first_bar`, `daily`
- **Computation**:

  ```python
  historical_gap_pct = 100 * (open / close.shift(1) - 1)
  ref = historical_gap_pct.dropna().tail(60)
  today_gap = 100 * (today_open / prior_close - 1)
  value = (today_gap - ref.mean()) / ref.std()
  ```

- **Thesis**: A raw 2% gap is routine for some tickers and exceptional for
  others. The z-score measures information surprise in the stock's own
  overnight distribution.
- **Expected non-null rate**: Above 95% with 31-60 prior gaps.
- **Prior art**: Event-study standardization and abnormal-return scoring.
- **Risk of look-ahead**: None. The reference contains only historical gaps and
  excludes today's observation.

## F. Liquidity and Participation

### Feature: `opening_volume_zscore_20d`

- **Category**: F - liquidity/participation
- **Primitives used**: `first_bar`, `hist_5m`
- **Computation**: `(today_first_volume - mean(last 20 historical first-bar
  volumes)) / std(last 20 historical first-bar volumes)`.
- **Thesis**: Complements `rvol_20d` by measuring how many distribution
  standard deviations today's participation is from normal. It separates
  genuinely exceptional opens from modest ratio changes in stable-volume
  names.
- **Expected non-null rate**: Above 90% with 20 valid prior opening bars.
- **Prior art**: Abnormal volume/event-study features.
- **Risk of look-ahead**: None. Historical opening bars must be strictly before
  `trade_date`; return `None` for zero standard deviation.

### Feature: `prior_volume_ratio_20d`

- **Category**: F - liquidity/participation
- **Primitives used**: `daily`
- **Computation**: `prior_day_volume / mean(volume from the 20 sessions before
  the prior day)`.
- **Thesis**: Confirms whether yesterday's move attracted unusual participation.
  This is distinct from today's first-bar RV and can separate a fresh catalyst
  from a continuation of already elevated interest.
- **Expected non-null rate**: Above 98% with 21 sessions.
- **Prior art**: Price-volume confirmation and relative-volume filters.
- **Risk of look-ahead**: None. Exclude prior-day volume from its baseline.

### Feature: `dollar_volume_trend_5_20`

- **Category**: F - liquidity/participation
- **Primitives used**: `daily`
- **Computation**:

  ```python
  dollar_volume = close * volume
  value = dollar_volume.tail(5).mean() / dollar_volume.tail(20).mean()
  ```

- **Thesis**: Values above one identify increasing tradable liquidity and
  attention. Dollar volume is more comparable across price levels than share
  volume alone.
- **Expected non-null rate**: Above 98% with 20 sessions.
- **Prior art**: Liquidity and turnover trend filters.
- **Risk of look-ahead**: None. Raw daily price and volume must be on a
  consistent split basis.

## H. Statistical and Derived Features

### Feature: `prior_return_zscore_60d`

- **Category**: H - statistical
- **Primitives used**: `daily`
- **Computation**: Standardize the latest completed close-to-close return
  against the preceding 60 returns, excluding that latest return from the
  reference mean and standard deviation.
- **Thesis**: Tests whether yesterday was an abnormal momentum event or an
  ordinary fluctuation. It is more comparable across tickers than raw
  `prior_day_return`.
- **Expected non-null rate**: Above 95% with 62 closes.
- **Prior art**: Standardized abnormal returns and event studies.
- **Risk of look-ahead**: None. Excluding the observation being scored also
  avoids mild self-normalization.

### Feature: `first_range_zscore_20d`

- **Category**: H - statistical/opening microstructure
- **Primitives used**: `first_bar`, `hist_5m`
- **Computation**: For each historical first 5-minute bar compute
  `100 * (high - low) / close`. Standardize today's `first_range_pct` against
  the last 20 historical values.
- **Thesis**: Normalizes opening-range expansion to the ticker's own time-of-day
  behavior. It should identify exhausted opening bars more precisely than a
  fixed `first_range_atr_frac` threshold.
- **Expected non-null rate**: Above 90% with 20 valid prior opening bars.
- **Prior art**: Time-of-day volatility normalization and abnormal-range
  scoring.
- **Risk of look-ahead**: None. Use only prior sessions and return `None` for a
  degenerate reference distribution.

### Feature: `excess_return_information_ratio_60d`

- **Category**: H - statistical/relative strength
- **Primitives used**: `daily`, `spy_daily`
- **Computation**: Align 60 stock and SPY daily returns, let
  `excess = stock_return - spy_return`, then return
  `sqrt(252) * mean(excess) / std(excess)`, requiring at least 30 aligned
  observations.
- **Thesis**: Existing relative-return features measure magnitude only. The
  information ratio measures whether outperformance was persistent or came
  from one unstable jump.
- **Expected non-null rate**: Above 95% for established listings when SPY daily
  is hydrated.
- **Prior art**: Active-return information ratio.
- **Risk of look-ahead**: None. Date-align returns and do not forward-fill.

## Features I Would Not Add Yet

- **VWAP-touch count**: Highly sensitive to bar resolution, tolerance choice,
  and whether a bar merely straddled VWAP. It introduces several hidden
  parameters before showing clear incremental information.
- **Sector breadth**: `sector_daily` is one ETF series, not a point-in-time
  panel of sector constituents. Computing breadth from the current contract
  would be mislabeled.
- **Sector momentum rank among all sectors**: Implementable only after
  `compute_candidate_features()` accepts the full `extra_daily` mapping rather
  than one selected sector series.
- **FOMC/earnings/holiday flags**: Leak-free only with a versioned
  point-in-time event calendar. A modern reconstructed calendar can silently
  include rescheduled or revised event knowledge.
- **ETF premium/discount proxy from holdings**: Requires point-in-time holdings,
  weights, and synchronized constituent opens. Current primitives cannot
  compute it honestly.
- **Up/down volume ratio from daily OHLCV**: Daily volume is not classified
  buyer- versus seller-initiated. Labeling all volume on an up-close day as
  "up volume" is a weak proxy and easy to overinterpret.

## Implementation Order

### Phase 1: High coverage, low complexity

Add these first:

```text
gap_range_frac
gap_zscore_60d
prior_range_expansion_14d
opening_volume_zscore_20d
prior_volume_ratio_20d
close_channel_pos_20d
sma20_vs_sma50_pct
trend_efficiency_20d
first_range_zscore_20d
```

### Phase 2: Prior-session intraday structure

Add the strict prior-session helper and then:

```text
prior_close_vs_vwap_pct
prior_opening_30m_range_frac
prior_pm_vs_am_vwap_pct
prior_late_volume_share
prior_afternoon_return_pct
```

### Phase 3: Longer-history and optional-context features

```text
realized_vol_percentile_20d_252
adx14
stock_sector_corr_60d
beta_to_sector_60d
sector_20d_ret_minus_spy
excess_return_information_ratio_60d
```

Every phase should add:

- Keys to `FEATURE_NAMES`.
- Explicit assignments in `compute_candidate_features()`.
- Stable all-`None` behavior for missing inputs.
- Poison-row tests for both daily and historical intraday inputs.
- Degenerate-data tests for zero range, zero volume, zero variance, and
  unaligned stock/benchmark dates.

## Non-Feature Ideas

### Exit Criteria

1. **Break-even activation**: After a completed bar proves `MFE >= X R`, move
   the stop to entry starting on the next bar. This protects right-tail trades
   without using the activating bar's unknown intrabar order.
2. **Prior-N-bar-low trail**: Once `MFE >= X R`, trail at the minimum low of the
   previous `N` completed bars, with the new stop active on the next bar. A
   2- or 3-bar trail is interpretable and less parameter-heavy than indicators.
3. **Failed-breakout exit**: Exit at the next bar's open after one or two
   completed closes back below the opening-range high or first-bar midpoint.
   This directly tests whether the breakout accepted above its trigger.
4. **Partial target plus runner**: Exit a fixed fraction at `+1R`, move the
   remainder to break-even, and trail it. This is strategically promising but
   requires multi-leg P&L accounting and should not be approximated as a
   single fill.

All dynamic stops must be derived from completed bars and become active only on
the following bar. Otherwise the simulator cannot know whether the stop update
or the adverse excursion happened first.

### Signal Metadata

- `entry_deadline`: Cancel a breakout order after a fixed ET time. Opening-drive
  validity decays before position holding necessarily should.
- `breakeven_after_r`: R threshold that activates a break-even stop.
- `trail_activation_r`: R threshold that activates trailing behavior.
- `trail_lookback_bars`: Number of completed bars used for the trailing low.
- `failed_breakout_level`: Explicit price level, normally OR high or OR
  midpoint.
- `failed_breakout_confirm_bars`: Required completed closes below that level.
- `partial_targets`: Structured list such as
  `[{"r": 1.0, "fraction": 0.5}]`; only add with proper multi-leg simulation.

### Ranking and Scoring

Use same-day cross-sectional percentile ranks rather than raw scales. A
reasonable fixed-weight starting score is:

```python
score = (
    0.30 * pct_rank(gap_zscore_60d)
    + 0.25 * pct_rank(opening_volume_zscore_20d)
    + 0.20 * pct_rank(prior_close_vs_vwap_pct)
    + 0.15 * pct_rank(stock_20d_ret_minus_spy)
    - 0.10 * pct_rank(abs(first_range_zscore_20d))
)
```

The exact weights should be pre-registered and perturbed as a robustness test,
not optimized continuously. A simpler alternative is Borda ranking: rank each
candidate on three or four thesis factors, sum ranks, and use gap percentage as
the deterministic tie-break. Borda is easier to audit and less sensitive to
outliers than weighted raw values.

For portfolio selection, add a sector concentration penalty after ranking:
retain score order but reduce a candidate's effective score when higher-ranked
names from the same sector are already selected. This addresses correlated
risk without pretending that ten same-sector trades are ten independent bets.

### New Data Primitives

1. **Point-in-time corporate-action events**: Split and symbol-change records
   with effective dates. This is more reliable than detecting every event from
   a 40% price jump.
2. **Versioned event calendar**: Earnings dates, FOMC decisions, exchange
   holidays, and early closes as they were known before each trade date.
3. **Historical benchmark intraday bars**: Prior 5-minute SPY and sector ETF
   sessions, not only today's SPY and per-ticker history. This enables
   leak-free market autocorrelation, breadth, and relative intraday regime
   features.
4. **Point-in-time sector/industry mapping in `StrategyContext`**: Avoid loading
   a static mapping inside strategy code and make mapping provenance auditable.
5. **Historical NBBO or spread snapshots**: A 09:35 spread/depth primitive would
   materially improve fill-quality and liquidity modeling, but only if the
   historical feed is timestamped and survivorship-safe.
6. **Point-in-time ETF holdings and weights**: Required before implementing
   holdings-implied ETF gap or premium/discount features.

## Final Research Caution

The feature library can safely capture all 25 columns above, but the locked
search should not expand from 9 to 34 independently tunable filters in one
round. The next search should choose a small thesis-coherent block, for example:

```text
gap surprise:
    gap_zscore_60d + gap_range_frac

prior-session accumulation:
    prior_close_vs_vwap_pct + prior_late_volume_share

opening abnormality:
    opening_volume_zscore_20d + first_range_zscore_20d
```

Treat each block as a separately pre-registered round with a small threshold
grid and the existing walk-forward/PBO controls. Capturing columns is cheap;
searching them is where the inferential cost appears.
