# Feature Ideation Proposals — Candidate Admission Features

This document proposes 25 new candidate-admission features for the long-only stock/ETF strategy engine. All features are designed to be strictly **leak-free**—computable using only the primitives available at 09:35 ET (`trade_date`, `first_bar`, `daily` strictly < `trade_date`, `hist_5m`, `spy_daily`, `spy_5m`, and `sector_daily`). 

They are organized into the lacunae categories identified in the prompt.

---

## 5A. Prior-Day Intraday Structure (via `hist_5m`)

### Feature: `prior_day_vwap_dist_pct`
- **Category**: A. Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`, `daily`
- **Computation**: 
  ```python
  # Filter hist_5m to exactly prior_date
  # prior_vwap = sum(volume * close) / sum(volume) for prior_date
  # return (prior_close - prior_vwap) / prior_vwap * 100.0
  ```
- **Thesis**: Measures whether institutional buying or selling dominated late in the day. A positive distance indicates strong late-day conviction, favoring continuation on the long side.
- **Expected non-null rate**: >95% (requires at least one prior day of `hist_5m` with volume).
- **Prior art**: Institutional cost basis analysis; VWAP anchoring.
- **Risk of look-ahead**: None. Strictly uses only the prior session's 5m bars.

### Feature: `prior_morning_vs_afternoon_range`
- **Category**: A. Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  ```python
  # prior_am_bars = hist_5m prior_date between 09:30 and 12:00
  # prior_pm_bars = hist_5m prior_date between 12:00 and 16:00
  # am_range = am_bars.high.max() - am_bars.low.min()
  # pm_range = pm_bars.high.max() - pm_bars.low.min()
  # return pm_range / am_range if am_range > 0 else None
  ```
- **Thesis**: If the afternoon range is significantly wider than the morning range, it implies a late-day directional conviction shift. Coupled with a strong close, it's a powerful momentum setup.
- **Expected non-null rate**: >95%.
- **Prior art**: "Who controlled the afternoon" setups; afternoon breakout strategies.
- **Risk of look-ahead**: None.

### Feature: `prior_open_to_close_conviction`
- **Category**: A. Prior-Day Intraday Structure
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # return abs(prior_close - prior_open) / (prior_high - prior_low)
  ```
- **Thesis**: Measures how directional the prior day was. A value near 1.0 means the stock opened near its low and closed near its high (or vice-versa). A high green conviction day strongly suggests momentum follow-through.
- **Expected non-null rate**: >99%.
- **Prior art**: Marubozu candlestick detection; price action expansion.
- **Risk of look-ahead**: None.

### Feature: `prior_vwap_touches`
- **Category**: A. Prior-Day Intraday Structure
- **Primitives used**: `hist_5m`
- **Computation**:
  ```python
  # Calculate cumulative VWAP at each 5m bar for prior_date
  # Count number of times bar low <= VWAP <= bar high (after 10:00 AM)
  # return float(touches)
  ```
- **Thesis**: Measures how highly contested the institutional baseline was. Frequent touches with a close above VWAP implies accumulation and successful defense of support.
- **Expected non-null rate**: >95%.
- **Prior art**: VWAP bounce setups; mean reversion profiling.
- **Risk of look-ahead**: None.

---

## 5B. Multi-Timeframe Trend Alignment

### Feature: `roc_5d`
- **Category**: B. Multi-Timeframe Trend Alignment
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # return _ret_pct(closes, 5)
  ```
- **Thesis**: Short-term Rate of Change (momentum). Gap strategies often work best when aligned with a strong short-term upward thrust, minimizing the risk of fading resistance.
- **Expected non-null rate**: >98% (requires 6 days history).
- **Prior art**: Standard momentum screening; CANSLIM short-term strength.
- **Risk of look-ahead**: None.

### Feature: `sma_20_vs_50_cross`
- **Category**: B. Multi-Timeframe Trend Alignment
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # sma_20 = closes.tail(20).mean()
  # sma_50 = closes.tail(50).mean()
  # return 1.0 if sma_20 > sma_50 else 0.0
  ```
- **Thesis**: Basic trend alignment state. A stock in a short-term trend (20 SMA) above its medium-term trend (50 SMA) has wind at its back, making breakouts more likely to hold.
- **Expected non-null rate**: >95% (requires 50 days history).
- **Prior art**: Golden cross derivatives; dual moving average crossovers.
- **Risk of look-ahead**: None.

### Feature: `donchian_pos_20d`
- **Category**: B. Multi-Timeframe Trend Alignment
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # high_20 = daily['high'].tail(20).max()
  # low_20 = daily['low'].tail(20).min()
  # return (prior_close - low_20) / (high_20 - low_20)
  ```
- **Thesis**: Indicates relative position within the recent one-month trading channel. Buying near 1.0 is a breakout play; buying near 0.2 may be a reversion play. It normalizes trend context across different volatility profiles.
- **Expected non-null rate**: >98%.
- **Prior art**: Stochastic Oscillator over long periods; Donchian Breakout systems (Turtle Traders).
- **Risk of look-ahead**: None.

### Feature: `consecutive_down_days`
- **Category**: B. Multi-Timeframe Trend Alignment
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # Iterate backwards checking if close[i] < close[i-1]
  # return float(streak)
  ```
- **Thesis**: The direct mirror to `consecutive_up_days`. A gap up following 3-4 consecutive down days is highly indicative of a dominance flip/capitulation reversal.
- **Expected non-null rate**: >99%.
- **Prior art**: Connors RSI; standard mean reversion setups.
- **Risk of look-ahead**: None.

---

## 5C. Volatility Regime & Compression

### Feature: `vol_contraction_ratio_5d_20d`
- **Category**: C. Volatility Regime & Compression
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # vol_5d = closes.pct_change().tail(5).std()
  # vol_20d = closes.pct_change().tail(20).std()
  # return vol_5d / vol_20d
  ```
- **Thesis**: Proxies a "squeeze". If the ratio is < 0.5, the stock has been unusually quiet for the past week compared to the month. A breakout from this compression has high expected value.
- **Expected non-null rate**: >98% (requires 21 days history).
- **Prior art**: Bollinger Band Squeeze (John Carter); volatility contraction patterns (VCP - Minervini).
- **Risk of look-ahead**: None.

### Feature: `prior_range_vs_atr`
- **Category**: C. Volatility Regime & Compression
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # prior_range = prior_high - prior_low
  # return prior_range / atr_14
  ```
- **Thesis**: Identifies if yesterday was an expansion day (>1.5x ATR) or a compression day (<0.5x ATR). An expansion day followed by a gap up is a strong continuation signal.
- **Expected non-null rate**: >95%.
- **Prior art**: Range expansion breakout systems.
- **Risk of look-ahead**: None.

### Feature: `vix_proxy_10d`
- **Category**: C. Volatility Regime & Compression
- **Primitives used**: `spy_daily`
- **Computation**:
  ```python
  # return spy_daily['close'].pct_change().tail(10).std() * sqrt(252) * 100
  ```
- **Thesis**: Provides a fast-moving, localized proxy for the VIX. Knowing the broader market volatility regime helps size risk and gate aggressive gap strategies (which fail in high-vol whipsaw regimes).
- **Expected non-null rate**: >98%.
- **Prior art**: VIX filtering; volatility-adjusted position sizing.
- **Risk of look-ahead**: None.

---

## 5D. Sector & Cross-Asset Context

### Feature: `stock_vs_sector_20d_beta`
- **Category**: D. Sector Context
- **Primitives used**: `daily`, `sector_daily`
- **Computation**:
  ```python
  # Same as beta_60d but using sector_daily returns over 20 days instead of SPY over 60 days
  ```
- **Thesis**: Better isolates idiosyncratic risk. A low beta to its sector means the stock is trading on its own fundamental catalyst, which is highly desirable for gap-and-go plays.
- **Expected non-null rate**: ~80% (requires matched `sector_daily`).
- **Prior art**: Statistical arbitrage; alpha isolation.
- **Risk of look-ahead**: None.

### Feature: `stock_5d_ret_minus_sector`
- **Category**: D. Sector Context
- **Primitives used**: `daily`, `sector_daily`
- **Computation**:
  ```python
  # stock_5d = _ret_pct(daily['close'], 5)
  # sector_5d = _ret_pct(sector_daily['close'], 5)
  # return stock_5d - sector_5d
  ```
- **Thesis**: Short-term relative strength. Isolates whether the stock's recent run-up is a market tide lifting all boats, or true idiosyncratic alpha. 
- **Expected non-null rate**: ~80% (requires matched `sector_daily`).
- **Prior art**: Relative strength screening (IBD).
- **Risk of look-ahead**: None.

### Feature: `sector_10d_roc`
- **Category**: D. Sector Context
- **Primitives used**: `sector_daily`
- **Computation**:
  ```python
  # return _ret_pct(sector_daily['close'], 10)
  ```
- **Thesis**: Absolute sector momentum. Buying a breakout in a stock where the sector is also breaking out (sector momentum > 0) has a significantly higher win rate.
- **Expected non-null rate**: ~80%.
- **Prior art**: Top-down trading; sector rotation.
- **Risk of look-ahead**: None.

---

## 5E. Overnight & Pre-Market Structure

### Feature: `overnight_range_vs_prior_range`
- **Category**: E. Overnight Structure
- **Primitives used**: `first_bar`, `daily`
- **Computation**:
  ```python
  # overnight_diff = abs(first_open - prior_close)
  # prior_range = prior_high - prior_low
  # return overnight_diff / prior_range if prior_range > 0 else None
  ```
- **Thesis**: Measures the impact of the overnight news relative to standard intraday noise. A ratio > 1.0 means the gap skipped over an entire day's worth of typical trading range (true price shock).
- **Expected non-null rate**: >99%.
- **Prior art**: Gap shock value measurements.
- **Risk of look-ahead**: None.

### Feature: `gap_direction_streak`
- **Category**: E. Overnight Structure
- **Primitives used**: `daily`, `first_bar`
- **Computation**:
  ```python
  # Look back over recent daily bars. A gap up is open_t > close_{t-1}
  # Count consecutive gap up days leading into today (today is first_open > prior_close)
  # return float(streak)
  ```
- **Thesis**: Three or more consecutive gap-ups usually signals exhaustion, whereas a first or second gap-up suggests initiation/momentum. Highly discriminative for gap-and-go vs gap-and-fade.
- **Expected non-null rate**: >99%.
- **Prior art**: Three white soldiers; exhaustion gap detection.
- **Risk of look-ahead**: None.

### Feature: `gap_vs_spy_gap_diff`
- **Category**: E. Overnight Structure
- **Primitives used**: `first_bar`, `daily`, `spy_5m`, `spy_daily`
- **Computation**:
  ```python
  # stock_gap = gap_pct_vs_prior_close
  # spy_gap = (spy_first_open - spy_prior_close) / spy_prior_close * 100.0
  # return stock_gap - spy_gap
  ```
- **Thesis**: Unlike `rel_spy_gap` (which is a ratio and blows up near 0), a simple arithmetic difference cleanly measures how much "extra" gap the stock generated independent of the broad market overnight futures move.
- **Expected non-null rate**: >95%.
- **Prior art**: Beta-adjusted gap fades.
- **Risk of look-ahead**: None.

---

## 5F. Liquidity & Market Microstructure

### Feature: `first_vol_zscore_20d`
- **Category**: F. Liquidity & Market Microstructure
- **Primitives used**: `first_bar`, `hist_5m`
- **Computation**:
  ```python
  # ob_vols = _opening_bar_volumes(hist_5m).tail(20)
  # return (first_vol - ob_vols.mean()) / ob_vols.std()
  ```
- **Thesis**: While `rvol_20d` gives a ratio, a z-score normalizes for the stock's opening volume variance. A z-score > 3.0 proves statistically significant institutional participation right out of the gate.
- **Expected non-null rate**: >95%.
- **Prior art**: Standardized volume climax analysis.
- **Risk of look-ahead**: None.

### Feature: `prior_day_spread_proxy`
- **Category**: F. Liquidity & Market Microstructure
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # true_range_pct = (high - low) / close
  # current = true_range_pct.iloc[-1]
  # avg_20d = true_range_pct.tail(20).mean()
  # return current / avg_20d
  ```
- **Thesis**: Proxy for localized liquidity shifts. If yesterday's high-low spread was remarkably tight relative to its average, it signals liquidity presence and compression, ready for expansion.
- **Expected non-null rate**: >98%.
- **Prior art**: Bid-ask spread proxies using OHLC data (Roll measure variations).
- **Risk of look-ahead**: None.

### Feature: `volume_trend_5d_vs_20d`
- **Category**: F. Liquidity & Market Microstructure
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # vol_5 = daily['volume'].tail(5).mean()
  # vol_20 = daily['volume'].tail(20).mean()
  # return vol_5 / vol_20
  ```
- **Thesis**: Rising volume over the last week validates the recent trend. If volume trend is > 1.2, interest in the stock is accelerating, supporting breakout continuation.
- **Expected non-null rate**: >98%.
- **Prior art**: Accumulation/Distribution lines; VPA.
- **Risk of look-ahead**: None.

---

## 5G. Calendar & Seasonality

### Feature: `is_first_trading_day_of_month`
- **Category**: G. Calendar & Seasonality
- **Primitives used**: `trade_date`, `daily`
- **Computation**:
  ```python
  # true if trade_date.month != prior_date.month
  # return 1.0 if true else 0.0
  ```
- **Thesis**: Captures beginning-of-month institutional capital deployment flows, which creates a structurally bullish, low-volatility drift favoring breakouts.
- **Expected non-null rate**: 100%.
- **Prior art**: Turn of the month effect.
- **Risk of look-ahead**: None.

### Feature: `days_since_opex`
- **Category**: G. Calendar & Seasonality
- **Primitives used**: `trade_date`
- **Computation**:
  ```python
  # Calculate date of last 3rd Friday.
  # return (trade_date - last_opex).days
  ```
- **Thesis**: The Monday/Tuesday following Opex often feature vanna/charm unwind and forced dealer repositioning. Normalizing "days since opex" maps this structural flow cycle.
- **Expected non-null rate**: 100%.
- **Prior art**: Option dealer hedging flow seasonality.
- **Risk of look-ahead**: None.

---

## 5H. Statistical & Derived Features

### Feature: `prior_day_return_zscore`
- **Category**: H. Statistical
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # rets = closes.pct_change().dropna().tail(60)
  # return (prior_day_return - rets.mean()) / rets.std()
  ```
- **Thesis**: Highly statistically rigorous. If yesterday was a +3 standard deviation move, a gap-up today represents extreme over-extension, raising the probability of a dominance flip or mean reversion.
- **Expected non-null rate**: >98% (requires 60 days history).
- **Prior art**: Statistical arbitrage bounds.
- **Risk of look-ahead**: None.

### Feature: `max_drawdown_20d`
- **Category**: H. Statistical
- **Primitives used**: `daily`
- **Computation**:
  ```python
  # rolling_max = closes.tail(20).cummax()
  # drawdowns = (closes.tail(20) - rolling_max) / rolling_max
  # return drawdowns.min() * 100.0  # Returns a negative %
  ```
- **Thesis**: Indicates how painful the recent path was. A stock that gaps up despite a recent severe drawdown is a strong "dead cat bounce" or short squeeze candidate.
- **Expected non-null rate**: >98%.
- **Prior art**: Drawdown profile clustering.
- **Risk of look-ahead**: None.

### Feature: `gap_zscore_60d`
- **Category**: H. Statistical
- **Primitives used**: `first_bar`, `daily`
- **Computation**:
  ```python
  # historical_gaps = (daily['open'] - daily['close'].shift(1)) / daily['close'].shift(1)
  # hist_gaps_60 = historical_gaps.tail(60)
  # return (gap_pct_vs_prior_close - hist_gaps_60.mean()) / hist_gaps_60.std()
  ```
- **Thesis**: Determines if *this specific gap* is unusually large for *this specific stock's* historical behavior. A +4 Z-score gap is highly likely to fade compared to a +1 Z-score gap.
- **Expected non-null rate**: >95%.
- **Prior art**: Statistical gaps.
- **Risk of look-ahead**: None.

---

## 9. Bonus: Non-Feature Ideas

### New Exit Criteria
1. **`TRAILING_PROFIT_STOP`**: Instead of a hard target, once the PnL reaches `+2R`, activate a trailing stop (e.g., trail by `1R` or close below 5m 20-SMA). This lets winners run while preventing deep retracements.
2. **`VWAP_TIME_STOP`**: If the position is open for `N` bars and the current price is strictly below today's cumulative VWAP, exit immediately.
3. **`RELATIVE_WEAKNESS_EXIT`**: If the stock drops > 1% while SPY rises > 0.5% over the same holding window, abort. The stock has decoupled from positive market beta.

### New Signal Metadata Keys
1. **`scale_out_frac`**: e.g., `0.5`. Tells the execution engine to sell half the position at `1R` and hold the rest to `target_price`. Improves psychological R-distribution smoothing.
2. **`max_slippage_bps`**: Allows high-volume setups to accept worse fills than low-volume setups, dynamically relaxing the limit order conditions in `pullback_limit`.
3. **`cancel_if_gap_filled`**: A boolean flag. If `True`, the simulation engine immediately cancels pending pullback limits if the low of the current bar breaks the prior day's close.

### New Ranking/Scoring Functions
1. **Composite Z-Scoring**: Instead of ranking solely by `gap_pct_vs_prior_high`, rank by: `(0.5 * gap_zscore) + (0.5 * first_vol_zscore)`. This combines price extreme and volume validation into a single dimensionless score.
2. **Sector-Adjusted Rank**: Rank candidates relative to other candidates *in the same sector*, picking the best 2 candidates per sector to enforce portfolio diversification, rather than blindly picking the top N overall.

### New Data Primitives for `StrategyContext`
1. **`VIX_5m` or `VIX_daily`**: Extremely useful for intra-day hazard states. If the VIX is spiking intraday, long breakouts fail at an alarming rate.
2. **`bars_premarket`**: Provide aggregated 04:00-09:30 volume and high/low ranges. This allows features like "premarket volume vs 20d ADV" to predict opening bell liquidity without waiting for the 09:35 close.
3. **`earnings_dates`**: A simple map of `{ticker: date}` for next/prior earnings. The feature library could seamlessly compute `days_until_earnings` or `days_since_earnings`, gating setups that are purely pre-earnings implied volatility pumps.
