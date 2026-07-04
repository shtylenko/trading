# Feature Proposals — 27 New Candidate-Admission Features

Response to `prompt.md`. Each proposal is implementable in `research/features.py`
given the existing primitives. None duplicate existing 41 features.

───

## 5A — Prior-Day Intraday Structure (via `hist_5m`)

ZERO of the 41 existing features use prior-day 5m bars beyond opening-bar volume.
These 7 features mine the prior session's full OHLCV structure — all leak-free
because the prior session closed yesterday.

The shared helper needed (not a feature, just DRY):

```python
def _prior_session_5m(hist_5m: pd.DataFrame | None) -> pd.DataFrame | None:
    """Most recent prior session's 5m RTH bars. None if history absent/empty."""
    if hist_5m is None or hist_5m.empty:
        return None
    h = hist_5m.tz_convert("America/New_York") if hist_5m.index.tz is not None else hist_5m
    grouped = h.groupby(h.index.date)
    dates = sorted(grouped.groups.keys())
    if not dates:
        return None
    return grouped.get_group(dates[-1])
```

### Feature: `prior_vwap_close_loc_pct`

- **Category**: 5A — Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)` → None if missing
  2. Compute prior-day VWAP: `typ = (H+L+C)/3`, `vwap = cumsum(typ*vol) / cumsum(vol)`, take final value
  3. `prior_close = prior_5m["close"].iloc[-1]`
  4. `(prior_close - vwap) / vwap * 100`
- **Thesis**: A stock that closed above yesterday's VWAP found institutional support at the cost-basis level and is more likely to continue upward today. Closing below VWAP = distribution, lower probability of follow-through. This is distinct from `prior_day_close_pos` (which uses the day's high-low range, not VWAP).
- **Expected non-null rate**: >95% when `historical_5m_lookback_days >= 1` (just needs yesterday). Fails only when yesterday's 5m data is missing or all-zero volume.
- **Prior art**: VWAP close-location is a standard institutional flow indicator (Brian Shannon, Andrew Aziz).
- **Risk of look-ahead**: None. Prior session is fully closed.

### Feature: `prior_pm_am_range_ratio`

- **Category**: 5A — Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. `am = prior_5m.between_time("09:30", "12:00", inclusive="both")`
  3. `pm = prior_5m.between_time("12:00", "16:00", inclusive="both")`
  4. `am_range = am["high"].max() - am["low"].min()`
  5. `pm_range = pm["high"].max() - pm["low"].min()`
  6. `pm_range / am_range` (None if am_range == 0)
- **Thesis**: Ratio > 1.5 = afternoon took control (distribution or late-day surge → higher uncertainty for gap-and-go continuation). Ratio < 0.5 = morning drove the session, afternoon was rotational drift → morning conviction may carry into today.
- **Expected non-null rate**: >95% with 1 day of hist_5m.
- **Prior art**: Volume-weighted average price (VWAP) traders track session control (morning vs afternoon); the ratio quantifies which session block dominated.
- **Risk of look-ahead**: None.

### Feature: `prior_first_hour_vol_frac`

- **Category**: 5A — Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. `first_hour = prior_5m.between_time("09:30", "10:30", inclusive="both")`
  3. `first_hour_vol = first_hour["volume"].sum()`
  4. `total_vol = prior_5m["volume"].sum()`
  5. `first_hour_vol / total_vol` (None if total_vol == 0)
- **Thesis**: High first-hour volume fraction (>40%) = institutional urgency (accumulation or distribution in the opening hour). Low fraction (<25%) = slow grind, lower conviction. For gap-and-go, high first-hour vol yesterday suggests real demand that may continue.
- **Expected non-null rate**: >95% with 1 day of hist_5m.
- **Prior art**: Standard market-microstructure metric (first-hour volume concentration).
- **Risk of look-ahead**: None.

### Feature: `prior_open_gap_filled`

- **Category**: 5A — Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`, `daily`, `trade_date`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`; `pdf = _prior(daily, trade_date)`
  2. The "day before yesterday" close is the last daily bar before the prior session: from `pdf`, take `pdf.iloc[-1]["close"]` (this is the close of the day before the prior session — wait, need to check). Actually: `pdf` is daily bars before `trade_date`. The prior session date is `prior_5m.index[0].date()`. The close before that session is the daily bar with `index.date < prior_session_date`. The prior day's open is `prior_5m["open"].iloc[0]`.
  3. `prior_open_gap = prior_open - prior_to_prior_close` (could be positive or negative)
  4. If `prior_open_gap > 0` (gap up): did any bar's low trade <= prior_to_prior_close? If so, gap filled.
  5. If `prior_open_gap < 0` (gap down): did any bar's high trade >= prior_to_prior_close? If so, gap filled.
  6. Return `1.0` if filled, `0.0` if held.
- **Thesis**: Unfilled gaps signal conviction — yesterday's gap-up that never filled means buyers controlled the entire session (no sellers could push back to prior close). This is the strongest continuation signal. Filled gaps = indecision, lower follow-through probability today.
- **Expected non-null rate**: ~90% (needs 2 days of daily data + 1 day hist_5m).
- **Prior art**: Gap-fill probability is a core concept in technical analysis (Bulkowski's gap statistics: 60-70% of gaps fill within 3 days; unfilled gaps have strong directional bias).
- **Risk of look-ahead**: None — uses only prior session's bars and pre-trade-date daily data.

### Feature: `prior_range_zscore`

- **Category**: 5C — Volatility Regime (also 5A — computed from hist_5m + daily)
- **Primitives used**: `hist_5m`, `daily`, `trade_date`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. `prior_range = prior_5m["high"].max() - prior_5m["low"].min()`
  3. From daily bars (`_prior(daily, trade_date)`): compute the 20 prior daily ranges (high-low), get mean and std
  4. `(prior_range - mean_20d_range) / std_20d_range`
- **Thesis**: Z-score > 2 = yesterday was an expansion day — high probability of follow-through (trend days cluster). Z-score < -1 = compression day — potential for breakout today. This is distinct from `realized_vol_20d` which measures close-to-close return volatility, not intraday range.
- **Expected non-null rate**: >90% (needs 20+ daily bars + hist_5m).
- **Prior art**: Range expansion/contraction is a core concept in Market Profile and auction theory (Dalton, Steidlmayer).
- **Risk of look-ahead**: None.

### Feature: `prior_vwap_touch_count`

- **Category**: 5A — Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. Compute prior-day VWAP series (same as `prior_vwap_close_loc_pct`)
  3. Count how many 5m bars had `low <= vwap <= high` (touched VWAP)
  4. Return as integer count (capped at e.g. 20 to avoid outliers dominating)
- **Thesis**: High VWAP touch count (>15 in a session) = heavy institutional activity (algorithms referencing VWAP for execution). These stocks are "in play" — liquidity is high, spreads are tight, breakouts are more likely to be real. Low touch count (<3) = one-sided trend day, less rotational activity. This is a known midcap-VWAP strategy signal (see `midday_vwap_pullback` in the sibling engine).
- **Expected non-null rate**: >95% with 1 day of hist_5m.
- **Prior art**: The midday VWAP pullback strategy family in this very repo uses VWAP touch counting extensively.
- **Risk of look-ahead**: None.

### Feature: `prior_range_vs_atr`

- **Category**: 5A / 5C — Prior-Day Intraday Structure + Volatility
- **Primitives used**: `hist_5m`, `daily`, `trade_date`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. `prior_range = prior_5m["high"].max() - prior_5m["low"].min()`
  3. `atr = daily_atr_14(daily, 14, trade_date)`
  4. `prior_range / atr`
- **Thesis**: Ratio > 1.5 = yesterday's range exceeded the average true range (expansion day → momentum). Ratio < 0.5 = inside day (compression → breakout setup). This is a simpler version of `prior_range_zscore` using ATR as the denominator instead of a rolling std — more robust to distribution shifts.
- **Expected non-null rate**: >90% (needs 15 daily bars for ATR + hist_5m).
- **Prior art**: Inside day / NR7 (narrowest range in 7 days) is a classic Toby Crabel / Linda Raschke breakout setup.
- **Risk of look-ahead**: None.

───

## 5B — Multi-Timeframe Trend Alignment

The existing D features cover static SMA distances but lack momentum rates-of-change
and MA crossover states.

### Feature: `roc_5d`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**: `_ret_pct(pdf["close"].astype(float), 5)` — reuses existing `_ret_pct` helper (line 71)
- **Thesis**: 5-day rate of change captures short-term momentum. Strong positive ROC (+3%+) = the stock is already moving, gap-and-go benefits from existing momentum. Negative ROC = counter-trend gap, lower probability of follow-through.
- **Expected non-null rate**: >95% (needs 6 daily bars).
- **Prior art**: ROC is one of the oldest momentum metrics (technical analysis canon).
- **Risk of look-ahead**: None — `_ret_pct` uses `iloc[-(n+1)]` which is strictly before `trade_date`.

### Feature: `roc_21d`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**: `_ret_pct(pdf["close"].astype(float), 21)` — same pattern as `roc_5d`
- **Thesis**: 21-day (~1 month) momentum captures the intermediate trend. Gap-and-go in a stock already up 10%+ in the last month is chasing; gap-and-go in a stock flat or slightly down = early in the move. Positive but not extreme = sweet spot.
- **Expected non-null rate**: >90% (needs 22 daily bars).
- **Prior art**: Monthly momentum is a well-documented factor (Jegadeesh & Titman 1993).
- **Risk of look-ahead**: None.

### Feature: `ma_20_above_50`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `closes = pdf["close"].astype(float)`
  2. `sma20 = closes.tail(20).mean()`; `sma50 = closes.tail(50).mean()`
  3. `1.0 if sma20 > sma50 else 0.0`
- **Thesis**: SMA20 > SMA50 = short-term trend is above intermediate trend (bullish alignment). This is a cleaner signal than `stock_above_own_50d` (which is close vs SMA, a single-point check). A crossover state captures trend direction, not just today's position.
- **Expected non-null rate**: >90% (needs 50 daily bars).
- **Prior art**: MA crossover is one of the most common trend-following signals.
- **Risk of look-ahead**: None.

### Feature: `ma_50_above_200`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `closes = pdf["close"].astype(float)`
  2. Needs 200 bars → `daily_lookback_days` must be ≥ ~320. Return None if insufficient.
  3. `sma50 = closes.tail(50).mean()`; `sma200 = closes.tail(200).mean()`
  4. `1.0 if sma50 > sma200 else 0.0`
- **Thesis**: Golden cross / death cross — the canonical long-term trend indicator. Long-only strategies should bias toward stocks above their 200d SMA; a 50/200 bull cross confirms trend alignment. f02 applies this to SPY as a regime gate; this brings it to individual stocks.
- **Expected non-null rate**: ~70% (needs 200 daily bars; many tickers with shorter histories return None).
- **Prior art**: Golden cross / death cross; f02 release uses SPY > 200d SMA as regime gate.
- **Risk of look-ahead**: None — all closes are strictly before `trade_date`.

### Feature: `consecutive_down_days`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**: Mirror of `consecutive_up_days` (lines 204–212) but counting `closes[i] < closes[i-1]` instead of `>`.
- **Thesis**: A gap-up after 3+ consecutive down days is a potential reversal — the gap may be short-covering or bargain hunting rather than genuine demand. A gap-up after 0–1 down days = trend continuation, higher conviction. Complements `consecutive_up_days` for full streak context.
- **Expected non-null rate**: >95% (needs 2 daily bars).
- **Prior art**: Consecutive-streak context; pairs with existing `consecutive_up_days` for full picture.
- **Risk of look-ahead**: None.

### Feature: `donchian_position_20d`

- **Category**: 5B — Multi-Timeframe Trend
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`
  2. `high20 = pdf["high"].tail(20).max()`; `low20 = pdf["low"].tail(20).min()`
  3. `prior_close = pdf["close"].iloc[-1]`
  4. `(prior_close - low20) / (high20 - low20)` — a 0–1 value
- **Thesis**: Position near 1.0 = stock is at 20-day highs (extended, pullback risk for gap-and-go entry). Position near 0.0 = stock is at 20-day lows (potential reversal, higher risk for a gap-up being a dead-cat bounce). Position in 0.5–0.8 = constructive uptrend with room to run.
- **Expected non-null rate**: >90% (needs 20 daily bars).
- **Prior art**: Donchian channels (Richard Donchian, the "father of trend following").
- **Risk of look-ahead**: None. Distinct from `dist_from_20d_high_pct` which is one-sided (only vs high), while this is a position within the full channel.

───

## 5C — Volatility Regime & Compression

### Feature: `realized_vol_percentile_1y`

- **Category**: 5C — Volatility Regime
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; needs ~252+ bars → `daily_lookback_days` ≥ 400
  2. Compute rolling 20d realized vol for each window in the trailing ~252 days
  3. Current 20d vol rank within that distribution → percentile (0–1)
  4. Use `pd.Series.rank(pct=True)` on the trailing vol series
- **Thesis**: High vol percentile (>0.8) = turbulent regime, wider stops needed, gap-and-go breakouts more likely to fail. Low vol percentile (<0.2) = quiet regime, tight stops work, breakouts have higher success rate. SPY vol percentile is also useful (see `spy_realized_vol_percentile_1y` below).
- **Expected non-null rate**: ~60% (needs ~252 daily bars). Returns None gracefully for shorter histories.
- **Prior art**: Volatility regime classification is standard in quantitative finance (Regime Switching models, GARCH families).
- **Risk of look-ahead**: None — all rolling windows are strictly before `trade_date`.

### Feature: `vol_ratio_5d_20d`

- **Category**: 5C — Volatility Regime
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `rets = pdf["close"].pct_change().dropna()`
  2. `vol5 = rets.tail(5).std()`; `vol20 = rets.tail(20).std()`
  3. `vol5 / vol20`
- **Thesis**: Ratio > 1.3 = short-term vol expanding (breakout/breakdown in progress → gap-and-go benefits from expansion). Ratio < 0.7 = vol contracting (Bollinger Band squeeze → potential explosive move ahead). This is the poor man's Bollinger Band width indicator.
- **Expected non-null rate**: >90% (needs 21 daily bars).
- **Prior art**: Bollinger Band squeeze (Bollinger 2001); Keltner channel / BB width ratio.
- **Risk of look-ahead**: None.

### Feature: `adx_14`

- **Category**: 5B / 5C — Trend Strength
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  Wilder's ADX(14) from daily bars using the existing ATR pattern:
  1. `pdf = _prior(daily, trade_date)`; needs 28+ bars (14 for ADX + 14 for smoothing)
  2. `tr = max(H-L, |H-prevC|, |L-prevC|)` — same as `daily_atr_14` line 86–90
  3. `+DM = H - prevH if H>prevH and H-prevH > prevL-L else 0`
  4. `-DM = prevL - L if prevL>L and prevL-L > H-prevH else 0`
  5. Smooth +DM, -DM, TR with Wilder's smoothing (same pattern as `daily_atr_14` lines 95–98)
  6. `+DI = 100 * smooth(+DM) / smooth(TR)`; `-DI = 100 * smooth(-DM) / smooth(TR)`
  7. `dx = 100 * abs(+DI - -DI) / (+DI + -DI)`
  8. `adx = Wilder_smooth(dx, 14)`
- **Thesis**: ADX > 25 = strong trend (gap-and-go wants trending stocks). ADX < 20 = ranging/choppy (gap-and-go breakouts fail more often in trendless markets). This is a continuous measure, better than binary trend filters.
- **Expected non-null rate**: ~85% (needs ~28 daily bars).
- **Prior art**: Welles Wilder's ADX (1978) is the standard trend-strength indicator.
- **Risk of look-ahead**: None — all Wilder smoothing uses only bars before `trade_date`.

### Feature: `spy_realized_vol_percentile_1y`

- **Category**: 5C — Volatility Regime (macro)
- **Primitives used**: `spy_daily`, `trade_date`
- **Computation**: Same as `realized_vol_percentile_1y` but on SPY's daily bars.
- **Thesis**: SPY vol regime dominates individual stock vol. When SPY vol is in the top quartile (VIX > 25 equivalent), ALL breakout strategies underperform. This gates the entire session, not per-candidate. o07/o11 already gate on SPY ATR regime; this is a cleaner, percentile-based version.
- **Expected non-null rate**: ~90% (SPY has long history; `spy_daily_lookback_days` must be ≥ 400 for this feature to compute).
- **Prior art**: o07/o11 SPY ATR regime gate; VIX percentile regime classification.
- **Risk of look-ahead**: None.

───

## 5D — Sector & Cross-Asset Context

Only 2 of 41 existing features touch `sector_daily`. These 4 deepen sector context.

### Feature: `stock_corr_to_sector_60d`

- **Category**: 5D — Sector Context
- **Primitives used**: `daily`, `sector_daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `spdf = _prior(sector_daily, trade_date)`
  2. `sr = pdf["close"].pct_change().dropna().tail(60)`
  3. `kr = spdf["close"].pct_change().dropna().tail(60)`
  4. Join inner, Pearson correlation of the overlapping returns
  5. Return None if < 30 overlapping observations
- **Thesis**: Low correlation to sector (< 0.5) = idiosyncratic story (stock moving on its own fundamentals, not sector flows). High correlation (> 0.9) = pure sector beta play. For gap-and-go, idiosyncratic gaps are more likely to sustain (not just sector rotation noise).
- **Expected non-null rate**: ~70% (needs `sector_daily` + 60 days of overlapping data).
- **Prior art**: Correlation to sector/market is standard in factor models (Barra, Axioma).
- **Risk of look-ahead**: None — same pattern as `beta_60d` (lines 257–264) but vs sector instead of SPY.

### Feature: `sector_momentum_20d`

- **Category**: 5D — Sector Context
- **Primitives used**: `sector_daily`, `trade_date`
- **Computation**: `_ret_pct(spdf["close"].astype(float), 20)` — the sector's own 20d return
- **Thesis**: Strong sector momentum (+5% in 20d) = tailwind for all stocks in the sector. Weak sector (-3%) = headwind, even good stock setups fail. This is the sector's raw return, distinct from `rel_sector_momentum_20d` which is stock minus sector.
- **Expected non-null rate**: ~70% (needs `sector_daily` + 21 bars).
- **Prior art**: Sector momentum is a top-level factor in cross-sectional models.
- **Risk of look-ahead**: None.

### Feature: `stock_sector_trend_alignment`

- **Category**: 5D — Sector Context
- **Primitives used**: `daily`, `sector_daily`, `trade_date`
- **Computation**:
  1. Stock: `stock_above_20d = prior_close > sma20` (binary)
  2. Sector: `sector_above_20d = sector_close > sector_sma20` (binary)
  3. `1.0` if both above, `0.0` if stock above but sector below, `-1.0` if stock below
  (actually, since we exit gracefully, use 0.0/1.0: 1.0 = aligned bullish)
- **Thesis**: Long when BOTH stock and sector are above their 20d SMA = trend alignment. Stock above but sector below = fighting the sector tide, lower win rate. This was a key finding in d12 (sector context improved SP500 signals).
- **Expected non-null rate**: ~70% (needs `sector_daily` + 20 bars each).
- **Prior art**: d11/d12 SPY/sector 50d SMA gates; multi-timeframe alignment (Murphy, Elder).
- **Risk of look-ahead**: None.

### Feature: `spy_20d_return`

- **Category**: 5D — Market Context
- **Primitives used**: `spy_daily`, `trade_date`
- **Computation**: `_ret_pct(spy_pdf["close"].astype(float), 20)` — SPY's 20d return
- **Thesis**: SPY regime is the single biggest factor in individual stock breakouts. SPY up 3%+ in 20d = bullish backdrop (gap-and-go breakouts have higher success). SPY down 3%+ = risk-off, breakouts fail. This is distinct from `spy_below_50d_sma` (a static level check); this captures momentum.
- **Expected non-null rate**: >90% when `requires_spy_daily` is set.
- **Prior art**: Market regime is the first filter in almost every trading system (Minervini, O'Neil, IBD).
- **Risk of look-ahead**: None — reuses existing `_ret_pct` with SPY data.

───

## 5E — Overnight & Pre-Market Structure

### Feature: `overnight_range_frac`

- **Category**: 5E — Overnight Structure
- **Primitives used**: `first_bar`, `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `prior = pdf.iloc[-1]`
  2. `overnight_move = abs(first_open - prior["close"])`
  3. `prior_day_range = prior["high"] - prior["low"]`
  4. `overnight_move / prior_day_range` (None if prior_day_range == 0)
- **Thesis**: High ratio (>1.0) = the overnight move exceeds yesterday's entire range — a genuine gap event, not noise. These are the gaps that gap-and-go strategies target. Low ratio (<0.3) = open near prior close, no gap conviction. This normalizes the gap by recent volatility, making it comparable across stocks.
- **Expected non-null rate**: >95% (needs 1 daily bar + first_bar).
- **Prior art**: Gap magnitude relative to prior range is standard in gap-trading systems.
- **Risk of look-ahead**: None — all inputs known at 09:35.

### Feature: `consecutive_gap_up_days`

- **Category**: 5E — Overnight Structure
- **Primitives used**: `first_bar`, `daily`, `trade_date`, `hist_5m`
- **Computation**:
  1. Count consecutive prior days where `open > prior_high` (a gap-up day)
  2. Need `hist_5m` for prior opens. For each prior session: first bar's open vs prior daily high.
  3. Walk backward through sessions until a non-gap-up day is found.
- **Thesis**: 3+ consecutive gap-up days = exhaustion (buyers have pushed every morning; the easy money is made). 1st gap-up day after a non-gap = fresh initiation, higher probability of continuation. This tells us where we are in the gap cycle.
- **Expected non-null rate**: ~85% (needs hist_5m with at least a few prior sessions).
- **Prior art**: Gap exhaustion patterns; three-gap rule in Japanese candlestick analysis.
- **Risk of look-ahead**: None — counts prior sessions only.

### Feature: `prior_close_vs_prior_vwap_pct`

- **Category**: 5E — Overnight Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  1. `prior_5m = _prior_session_5m(hist_5m)`
  2. Compute prior VWAP (same helper as `prior_vwap_close_loc_pct`)
  3. `(prior_close - prior_vwap) / prior_vwap * 100`
- **Thesis**: Prior close above VWAP + today's gap up = continuation of institutional buying (the close confirmed the VWAP support). Prior close below VWAP + today's gap up = potential false breakout (yesterday's close was below cost basis, today's gap may fade). This pairs with `prior_vwap_close_loc_pct` to give both prior-close and today-open context.
- **Expected non-null rate**: >90% with 1 day of hist_5m.
- **Prior art**: VWAP close analysis (Brian Shannon's "anchored VWAP").
- **Risk of look-ahead**: None.

───

## 5F — Liquidity & Market Microstructure

### Feature: `first_vol_zscore`

- **Category**: 5F — Liquidity
- **Primitives used**: `first_bar`, `hist_5m`
- **Computation**:
  1. `ob = _opening_bar_volumes(hist_5m)` — existing helper, line 104
  2. If `len(ob) < 20`: return None
  3. `mean_vol = ob.mean()`; `std_vol = ob.std()`
  4. `(first_volume - mean_vol) / std_vol`
- **Thesis**: Z-score > 2 = today's opening volume is an outlier — genuine urgency (institutional participation in the gap). Z-score < 0 = below-average opening interest, gap may be noise. This is a cleaner signal than `opening_rv` (ratio to mean) because it accounts for the volatility of opening volumes. A stock with erratic opening volumes may have high RV by chance; z-score distinguishes signal from noise.
- **Expected non-null rate**: ~85% (needs 20+ prior opening bars).
- **Prior art**: Volume z-score / volume climax detection in VSA (Volume Spread Analysis, Tom Williams).
- **Risk of look-ahead**: None — uses prior opening bars only, same pattern as `opening_rv`.

### Feature: `prior_vol_vs_20d_avg`

- **Category**: 5F — Liquidity
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`
  2. `prior_vol = pdf["volume"].iloc[-1]`
  3. `avg_vol = pdf["volume"].tail(21).head(20).mean()` — 20d avg excluding the prior day
  4. `prior_vol / avg_vol`
- **Thesis**: Prior day volume > 1.5× average = volume confirmation of yesterday's move (the move was "real"). Gap-and-go today on top of a high-volume prior day = continuation with conviction. Low prior volume = yesterday's move was low-conviction, today's gap may reverse.
- **Expected non-null rate**: >95% (needs 21 daily bars).
- **Prior art**: Volume confirmation is a Dow Theory principle.
- **Risk of look-ahead**: None.

### Feature: `up_down_vol_ratio_20d`

- **Category**: 5F — Liquidity
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; needs 20 bars
  2. `rets = pdf["close"].pct_change().dropna().tail(20)`
  3. `up_days_vol = pdf["volume"].iloc[-20:][rets > 0].sum()`
  4. `down_days_vol = pdf["volume"].iloc[-20:][rets < 0].sum()`
  5. `up_days_vol / down_days_vol` (None if down_days_vol == 0)
- **Thesis**: Ratio > 1.5 = more volume on up days than down days (accumulation bias). Ratio < 0.7 = more volume on down days (distribution bias). Long-only strategies want accumulation. This is a continuous version of the Arms Index (TRIN) applied to a single stock.
- **Expected non-null rate**: >90% (needs 20 daily bars with at least 1 up and 1 down day).
- **Prior art**: Up/down volume ratio is a standard Wyckoff accumulation/distribution metric.
- **Risk of look-ahead**: None.

───

## 5G — Calendar & Seasonality

### Feature: `days_since_opex`

- **Category**: 5G — Calendar
- **Primitives used**: `trade_date`, `daily` (to count trading days back)
- **Computation**:
  1. Find the most recent opex Friday before `trade_date` (3rd Friday of the month)
  2. Count trading days between that Friday and `trade_date` (exclusive of `trade_date`)
  3. Use `daily` index or a trading calendar to count trading days (not calendar days)
  4. If no daily data, fall back to calendar days / 7 * 5 approximation
- **Thesis**: Opex weeks have unusual gamma-driven flows (dealer hedging, pin risk). The week after opex typically sees reduced volatility as gamma positions roll off. Days 0–3 after opex = post-opex drift potential. Days 10+ after opex = pre-opex gamma build. This affects gap sustainability.
- **Expected non-null rate**: >95% (always computable from `trade_date` alone; trading-day precision needs `daily` data).
- **Prior art**: Gamma exposure / opex effects (SpotGamma, SqueezeMetrics); CBOE opex calendar effects.
- **Risk of look-ahead**: None — opex dates are pre-known from the calendar.

───

## 5H — Statistical & Derived Features

### Feature: `gap_zscore_1y`

- **Category**: 5H — Statistical
- **Primitives used**: `first_bar`, `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; needs ~252 bars for 1yr
  2. For each prior day, compute what the gap WOULD HAVE BEEN (open vs prior_high)
  3. Build a distribution: for day i, `gap_i = (open_i - high_{i-1}) / high_{i-1} * 100`
  4. Today's `gap_pct_vs_prior_high` vs that distribution → z-score
  5. If insufficient history, return None
- **Thesis**: Z-score > 3 = this is a 3-sigma gap — extremely unusual. These gaps are either: (a) news-driven and likely to sustain (earnings, FDA approval), or (b) mean-reverting within the session. The z-score alone doesn't distinguish, but it's a powerful flag for the combinatorial search to interact with volume/trend features.
- **Expected non-null rate**: ~60% (needs ~252 daily bars for the distribution).
- **Prior art**: Gap z-scores appear in quantitative gap-trading literature; pairs with `gap_pct_vs_prior_high` (the raw value) for normalized context.
- **Risk of look-ahead**: None — all gap values in the distribution are from prior days.

### Feature: `prior_return_zscore_20d`

- **Category**: 5H — Statistical
- **Primitives used**: `daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `rets = pdf["close"].pct_change().dropna()`
  2. `mu = rets.tail(20).mean()`; `sigma = rets.tail(20).std()`
  3. `(prior_day_return - mu) / sigma`
- **Thesis**: Z-score > 2 = yesterday was a 2-sigma up day (outlier). Gap-ups after outlier up days tend to mean-revert (the move was overdone). Z-score between -1 and +1 = yesterday was normal, today's gap is the initiation — higher continuation probability.
- **Expected non-null rate**: >90% (needs 21 daily bars).
- **Prior art**: Return z-score is used in mean-reversion strategies; here it contextualizes gap continuation probability.
- **Risk of look-ahead**: None.

### Feature: `upside_capture_ratio_60d`

- **Category**: 5H — Statistical
- **Primitives used**: `daily`, `spy_daily`, `trade_date`
- **Computation**:
  1. `pdf = _prior(daily, trade_date)`; `spdf = _prior(spy_daily, trade_date)`
  2. `sr = pdf["close"].pct_change().dropna().tail(60)`
  3. `mr = spdf["close"].pct_change().dropna().tail(60)`
  4. `up_mask = mr > 0`
  5. If `up_mask.sum() == 0`: return None
  6. `stock_up_return = sr[up_mask].mean()`; `spy_up_return = mr[up_mask].mean()`
  7. `stock_up_return / spy_up_return` (annualize-style: this is a ratio, not %)
- **Thesis**: Ratio > 1.2 = stock captures 120% of SPY's upside — high beta to rallies (bull market leader). Ratio < 0.8 = stock lags on up days — defensive or broken. For gap-and-go, stocks with high upside capture benefit more from bullish market days. This is distinct from `beta_60d` which measures linear sensitivity to both up and down moves; upside capture isolates participation in rallies.
- **Expected non-null rate**: ~75% (needs SPY daily + 60d overlapping, with at least some up days).
- **Prior art**: Upside/downside capture ratios are standard in managed-futures and hedge fund analysis (Morningstar, BarclayHedge).
- **Risk of look-ahead**: None — same pattern as `beta_60d` computation.

───

## 5I — ETF-Specific

(Useful when the universe includes ETFs like SPY, QQQ, IWM, XLF, XLK.)

### Feature: `etf_spy_corr_60d`

- **Category**: 5I — ETF-Specific
- **Primitives used**: `daily`, `spy_daily`, `trade_date`
- **Computation**: Identical pattern to `stock_corr_to_sector_60d` but vs SPY. For an ETF ticker, `daily` IS the ETF's bars.
- **Thesis**: Sector ETF correlation to SPY reveals its diversification value and behavior regime. XLF at 0.85 is normal; XLF at 0.40 is a regime break (financials decoupling). Low correlation gaps in sector ETFs are more likely to be sector-specific news, not broad market moves.
- **Expected non-null rate**: ~75% (needs SPY daily + 60d overlapping).
- **Prior art**: ETF-SPY correlation is standard in portfolio risk (tracking error, active share).
- **Risk of look-ahead**: None.

───

## Feature Count Summary

| Category | Features | Count |
|----------|----------|-------|
| 5A — Prior-Day Intraday Structure | prior_vwap_close_loc_pct, prior_pm_am_range_ratio, prior_first_hour_vol_frac, prior_open_gap_filled, prior_vwap_touch_count, prior_range_vs_atr | 6 |
| 5B — Multi-Timeframe Trend | roc_5d, roc_21d, ma_20_above_50, ma_50_above_200, consecutive_down_days, donchian_position_20d | 6 |
| 5C — Volatility Regime | realized_vol_percentile_1y, vol_ratio_5d_20d, adx_14, spy_realized_vol_percentile_1y, prior_range_zscore | 5 |
| 5D — Sector Context | stock_corr_to_sector_60d, sector_momentum_20d, stock_sector_trend_alignment, spy_20d_return | 4 |
| 5E — Overnight Structure | overnight_range_frac, consecutive_gap_up_days, prior_close_vs_prior_vwap_pct | 3 |
| 5F — Liquidity | first_vol_zscore, prior_vol_vs_20d_avg, up_down_vol_ratio_20d | 3 |
| 5G — Calendar | days_since_opex | 1 |
| 5H — Statistical | gap_zscore_1y, prior_return_zscore_20d, upside_capture_ratio_60d | 3 |
| 5I — ETF | etf_spy_corr_60d | 1 |
| **TOTAL** | | **32** |

(Note: `prior_range_zscore` and `prior_range_vs_atr` are counted in 5A/5C.)

32 is above the 15–30 target range; the weakest candidates to drop would be
`spy_realized_vol_percentile_1y` (redundant with o07/o11 SPY regime), and/or
`etf_spy_corr_60d` (narrow use case). Trim to 30 by dropping those two.

───

## Non-Feature Ideas

### New Exit Criteria

1. **TRAILING_VWAP_STOP**: After entry, trail the stop at `session_VWAP - k*ATR` (or `EMA9 - k*ATR` as in v06). The exit engine already computes session VWAP inside `simulate_long_breakout` (lines 87–91). Exposing this as a first-class exit reason (alongside STOP_LOSS, TIME_EXIT) would allow strategies to declare "I exit when price closes below VWAP" without encoding it in `should_exit_vwap_break` per-release.

2. **MOMENTUM_STOP**: Exit when `close < EMA(N)` after M bars — a time-gated momentum stop. Similar to the v09 9-EMA exit but parameterized in signal metadata rather than hardcoded per release.

3. **VOLUME_STOP**: Exit when a bar's volume exceeds N× the running average volume (climax exit). Volume climax after a run = potential exhaustion.

### New Signal Metadata Keys

1. **`trailing_stop_ema_period`** / **`trailing_stop_atr_mult`**: Parameterize the trailing stop in metadata instead of per-release `manage_active_trade` overrides. Current approach requires a new release for every stop variant.

2. **`entry_delay_bars`**: Wait N bars after signal before making the order active. Some strategies benefit from letting the first-bar excitement settle.

3. **`partial_scale_pct`**: Currently scale-out is hardcoded at 50% in midday_vwap_pullback v06. Let strategies declare scale fraction in metadata.

### New Ranking Functions

1. **Composite z-score ranking**: Rank candidates by average z-score across N features (e.g., `(gap_z + rv_z + trend_z) / 3`). Simpler than ML (o03's LightGBM) but more robust than single-feature ranking.

2. **Risk-adjusted gap ranking**: `gap_pct / adr_pct` — normalize the gap by the stock's typical daily range. A 1% gap on a stock that moves 0.5%/day is more significant than a 2% gap on a stock that moves 3%/day.

### New Data Primitives

1. **Pre-built earnings calendar**: A lookup table of `(ticker, earnings_date)` accessible via `context.earnings_calendar`. Feature: `days_to_earnings` / `days_since_earnings`. Earnings proximity dramatically affects gap behavior. Pre-known (not leaked — earnings dates are scheduled in advance).

2. **FOMC calendar**: Same pattern — pre-built calendar of FOMC dates. Feature: `is_fomc_day` / `days_since_fomc`. FOMC days have distinct intraday patterns (drift into 2pm, vol spike at 2pm, reversal or trend post-announcement).
