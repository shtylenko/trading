# Candidate-Feature Library — Self-Contained Implementation Reference

**Audience:** an AI model with **no access to the codebase**. This document fully
specifies every feature currently implemented, the data primitives they are
computed from, the leak-free contract, and the shared helper definitions, so you
can reason about the features, audit them, or propose new ones without seeing any
source code.

---

## 1. Domain context

We research **long-only, same-day (intraday) US stock/ETF trading strategies**.
The flagship family is **"gap-and-go"**: each morning, admit tickers that gapped
up (today's open above yesterday's high) with a green first 5-minute candle, then
enter long on a breakout above that first candle's high, with a stop at its low
(= 1R of risk), a 1R profit target, and a forced exit by late morning. Outcomes
are measured in **R** (multiples of the risk taken): +1R = hit target, −1R =
hit stop.

A **candidate-admission feature** is any number describing a candidate *at the
moment we decide whether to admit it* — **09:35 ET**, i.e. immediately after the
first 5-minute candle (09:30–09:35) has closed, before the breakout entry. These
features feed an offline search that looks for filter combinations producing a
robust, multi-year edge. Because the strategy admits or rejects candidates, every
filter combination is a **subset** of one max-recall capture run, which is why we
capture a broad feature vector once and search narrow subsets later.

**The cardinal rule is no look-ahead (leak-free):** a feature may only use
information knowable by 09:35 ET on the trade date. Concretely, it may use the
first 5-minute candle and any *prior* day's data, but never any regular-session
bar after 09:35 of the trade date, and never the trade date's own daily bar.

---

## 2. Data primitives available at decision time

A feature function receives these inputs (any may be missing → the feature is
`None`). All price/volume data is **raw / unadjusted** (not split-adjusted), and
all intraday timestamps are **America/New_York**.

| Primitive | Type | Description |
|---|---|---|
| `trade_date` | date | The session being traded. |
| `first_bar` | OHLCV record | The **first regular 5-minute candle** (09:30–09:35) of the trade date: `open`, `high`, `low`, `close`, `volume`. Fully closed at 09:35, so leak-free. |
| `daily` | daily OHLCV series | The ticker's **daily** bars. Internally sliced to **strictly before `trade_date`** before any use (`prior daily bars` below). Indexed by date. Deep history (~420 calendar days ≈ up to ~290 trading days) is provided so 200-day averages compute. |
| `hist_5m` | 5-minute OHLCV series | The ticker's **prior** trading sessions of regular-hours 5-minute bars (~30 prior sessions). Used for opening-bar statistics and prior-session intraday structure. Sliced to strictly before `trade_date`. |
| `spy_daily` | daily OHLCV series | SPY (S&P 500 ETF) daily bars, prior to `trade_date`. The broad-market proxy. |
| `spy_5m` | 5-minute OHLCV series | SPY's trade-date 5-minute bars (its first candle is used, same 09:35 cutoff). |
| `sector_daily` | daily OHLCV series | The candidate's **matched sector ETF** daily bars (one of the 11 SPDR sector ETFs: XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLRE, XLU, XLC), prior to `trade_date`. |

**Conventions used throughout:**
- *"prior daily bars"* = `daily` rows with date `< trade_date`. *"prior close/
  high/low/open"* = the values of the **most recent** prior daily bar (yesterday).
- *"prior session"* (intraday) = the most recent date `< trade_date` present in
  `hist_5m`; *"prior-session VWAP/range"* are computed over that day's 5m bars.
- A feature returns `None` whenever an input is missing, history is too short for
  the stated window, or a denominator is zero/degenerate (e.g. zero range, zero
  variance). The output is a **flat, fixed-key record**: every feature key always
  present, value `None` if uncomputable — so a capture across many tickers/days is
  a rectangular table.
- **Split guard:** features over long raw-price windows (≥60 trading days) are set
  to `None` if the window likely spans a stock split or data glitch — detected as
  any close-to-close absolute move > 40% in the trailing window, or an open-vs-
  prior-close move > 40%. (Raw prices across a split mix two price scales and
  would corrupt returns/volatility/beta.) Two guards are used: a 63-day window
  (`split_63`) for 60-day stats, and a 252-day window (`split_252`) for the
  1-year volatility percentile.

---

## 3. Shared helper definitions

These are the building blocks referenced by the feature formulas below.

- **ATR14** (Average True Range, Wilder, 14): over prior daily bars, true range
  `TR_t = max(high−low, |high−prev_close|, |low−prev_close|)`; ATR is Wilder's
  smoothed TR (seed = mean of first 14 TRs, then
  `ATR_t = (ATR_{t-1}·13 + TR_t)/14`). Needs ≥ 15 prior daily bars; else `None`.
- **SMA_n**: simple mean of the last `n` prior daily closes.
- **`ret_pct(series, n)`**: percent return over the last `n` steps =
  `(close[-1] / close[-(n+1)] − 1) · 100`. Needs ≥ `n+1` points.
- **`sma_dist_pct(series, n)`**: `(close[-1] − SMA_n) / SMA_n · 100`. Needs ≥ `n`.
- **prior session 5m**: the most recent date `< trade_date` in `hist_5m`, all its
  5-minute bars.
- **session VWAP(bars)**: volume-weighted average price =
  `Σ(typical·volume) / Σ(volume)`, where `typical = (high+low+close)/3`. `None`
  if total volume ≤ 0.
- **opening-bar series**: for each prior session in `hist_5m`, the 09:30–09:35
  bar. *opening-bar volumes* = that bar's volume per day; *opening-bar range %* =
  `(high−low)/close·100` of that bar per day.
- **ADX14** (Wilder Average Directional Index, 14): standard directional-movement
  system on prior daily bars — compute +DM/−DM and TR, Wilder-smooth each over 14,
  `+DI = 100·smooth(+DM)/smooth(TR)`, `−DI` likewise, `DX = 100·|+DI−−DI|/(+DI+−DI)`,
  `ADX = Wilder-smooth(DX, 14)`. Needs ≥ 30 prior daily bars; else `None`.
- **SPY gap % (vs prior high)**: `(spy_first_open − spy_prior_high)/spy_prior_high·100`.
- **third Friday(year, month)**: the monthly options-expiration ("opex") date.

---

## 4. The features (87)

Format per feature: **`name`** *(units / range)* — formula — *null when* —
**thesis** (why it might predict follow-through).

### A — Gap / overnight structure

- **`gap_pct_vs_prior_high`** *(%)* — `(first_open − prior_high)/prior_high·100`.
  The defining gap-and-go signal: how far the open is above yesterday's high.
  **Thesis:** a gap above the prior high is a relative-strength / breakout event.
- **`gap_pct_vs_prior_close`** *(%)* — `(first_open − prior_close)/prior_close·100`.
  The classic overnight gap. **Thesis:** raw overnight demand/supply imbalance.
- **`gap_atr`** *(ATR multiples)* — `(first_open − prior_close)/ATR14`. *null if
  ATR unavailable.* **Thesis:** volatility-normalized gap — a 3% gap means
  different things for a calm vs a wild name.
- **`gap_vs_20d_high_pct`** *(%)* — `(first_open − max(high, last 20 prior))/that·100`.
  **Thesis:** is the open breaking a multi-week base, or merely yesterday's high?
- **`prior_day_return`** *(%)* — `(prior_close − close_2_days_ago)/close_2_days_ago·100`.
  *needs ≥2 prior bars.* **Thesis:** gapping off strength vs off a weak close.
- **`prior_day_close_pos`** *(0–1)* — `(prior_close − prior_low)/(prior_high − prior_low)`.
  Where yesterday closed within its range. **Thesis:** a close near the high =
  buyers in control into the gap.
- **`consecutive_up_days`** *(count)* — trailing run of prior days where
  `close_t > close_{t-1}`. **Thesis:** persistence vs exhaustion into the gap.

### B — First-candle (opening-range) microstructure

All from `first_bar` (`o,h,l,c,v`), range `= h − l`.

- **`first_open`** *(price)* — `o`. The opening price level (also a price-tier proxy).
- **`first_close_pos`** *(0–1)* — `(c − l)/range`. *null if range 0.* **Thesis:**
  closing at the high (→1) is exhaustion — the breakout chases an extended move;
  closing lower but still reclaiming the high shows real demand. (This feature was
  empirically derived from prior loss analysis; see §6 contamination note.)
- **`first_range_pct`** *(%)* — `range/c·100`. Opening-bar size relative to price.
- **`first_range_atr_frac`** *(ATR multiples)* — `range/ATR14`. **Thesis:** a 1R
  target on a huge first bar may be unreachable; tiny bars give noisy stops.
- **`first_body_frac`** *(0–1)* — `|c − o|/range`. Conviction of the opening bar.
- **`first_upper_wick_frac`** *(0–1)* — `(h − max(o,c))/range`. Selling rejection.
- **`first_lower_wick_frac`** *(0–1)* — `(min(o,c) − l)/range`. Dip absorption.
- **`first_return`** *(%)* — `(c − o)/o·100`. Opening-drive strength/direction.
- **`breakout_distance`** *(%)* — `(h − o)/o·100`. How far above the open the entry
  trigger sits.
- **`open_pos_in_first`** *(0–1)* — `(o − l)/range`. Open-drive vs dip-and-reclaim shape.

### C — Volume / participation

- **`first_volume`** *(shares)* — `v`. Raw opening-bar participation.
- **`first_dollar_volume`** *($)* — `v·c`. Liquidity/impact at entry.
- **`first_vol_frac_of_prior_day`** *(ratio)* — `v / prior_day_volume`. Fraction of
  a normal full day already trading in the first 5 minutes (climax proxy).
- **`opening_rv`** *(ratio)* — `v / mean(all prior opening-bar volumes)`. *needs ≥10
  prior opening bars.* **Thesis:** relative-volume "in play" gate.
- **`rvol_20d`** *(ratio)* — `v / mean(last 20 prior opening-bar volumes)`. Shorter-
  baseline RV.
- **`avg_daily_volume`** *(shares)* — mean of last 14 prior daily volumes. Liquidity.

### D — Stock's own trend / volatility

- **`close_vs_own_50d_sma`** *(%)* — `sma_dist_pct(closes, 50)`. *needs 50 bars.*
- **`close_vs_own_200d_sma`** *(%)* — `sma_dist_pct(closes, 200)`. *needs 200 bars.*
- **`stock_above_own_50d`** *(0/1)* — `1` if `prior_close > SMA50` else `0`.
- **`adr_pct`** *(%)* — `ATR14 / prior_close · 100`. The name's intrinsic daily range.
- **`dist_from_20d_high_pct`** *(%, ≤0 typ.)* — `(prior_close − max(high,20))/that·100`.
- **`realized_vol_20d`** *(%)* — stdev of the last 20 prior daily percent returns ·100.

### E — Relative strength / market & sector

- **`rel_spy_gap`** *(ratio)* — `gap_pct_vs_prior_high / SPY_gap_pct_vs_prior_high`.
  *null if SPY gap ≈ 0 (within 1e-9).* **Thesis:** idiosyncratic move vs market beta.
  (Unstable near zero — see `gap_vs_spy_gap_diff` for the stable variant.)
- **`stock_5d_ret_minus_spy`** *(% pts)* — `ret_pct(stock,5) − ret_pct(SPY,5)`.
- **`stock_20d_ret_minus_spy`** *(% pts)* — `ret_pct(stock,20) − ret_pct(SPY,20)`.
- **`rel_sector_momentum_20d`** *(% pts)* — `ret_pct(stock,20) − ret_pct(sector,20)`.
- **`spy_first_return`** *(%)* — SPY first 5m candle `(close−open)/open·100`. Is the
  market itself driving at the open?
- **`spy_first_close_pos`** *(0–1)* — SPY first candle `(close−low)/(high−low)`.
- **`beta_60d`** *(ratio)* — `cov(stock_ret, SPY_ret)/var(SPY_ret)` over the last 60
  aligned daily returns. *needs ≥30 aligned.* Lower beta → more idiosyncratic.
- **`spy_below_50d_sma`** *(0/1)* — `1` if SPY prior close < its 50-day SMA. Broad-
  market regime gate (a weak tape favors relative-strength gaps).
- **`sector_below_50d_sma`** *(0/1)* — same, for the candidate's sector ETF.

### F — Calendar / seasonality (always computable from `trade_date`)

- **`day_of_week`** *(0–6, Mon=0)*.
- **`month`** *(1–12)*.
- **`is_month_end`** *(0/1)* — `1` if day-of-month ≥ 25.
- **`is_quarter_end_month`** *(0/1)* — `1` if month ∈ {3,6,9,12}.
- **`is_opex`** *(0/1)* — `1` if Friday and day-of-month ∈ [15,21] (monthly opex).

### A2 — Prior-day full intraday structure (from the prior 5m session)

- **`prior_close_vs_vwap_pct`** *(%)* — `(prior_session_close − prior_session_VWAP)/
  VWAP·100`. **Thesis:** a close above yesterday's volume-weighted cost basis =
  late holders profitable, not trapped → continuation bias.
- **`prior_pm_am_range_ratio`** *(ratio)* — `pm_range / am_range`, where
  am = 09:30–12:00, pm = 12:00–16:00, range = `high.max − low.min`. *null if am
  range 0.* **Thesis:** which session block controlled price discovery.
- **`prior_first_hour_vol_frac`** *(0–1)* — `vol(09:30–10:25 bars, i.e. the true
  first 60 min)/total_session_vol`. **Thesis:** opening-hour urgency.
- **`prior_late_volume_share`** *(0–1)* — `vol(14:00–16:00)/total_session_vol`.
  **Thesis:** late-day participation = accumulation (or distribution) into the close.
- **`prior_afternoon_return_pct`** *(%)* — `(session_close − open_of_first_bar_≥13:00)/
  that_open·100`. **Thesis:** persistent afternoon demand vs a one-off opening spike.
- **`prior_opening_30m_range_frac`** *(0–1)* — `range(09:30–10:00) / full_session_range`.
  **Thesis:** small fraction = the move kept expanding after the open (momentum).

### A3 — Prior-day daily-only structure

- **`prior_open_to_close_conviction`** *(0–1)* — `|prior_close − prior_open|/
  (prior_high − prior_low)`. Marubozu-like directional conviction of yesterday.
- **`prior_gap_fill_fraction`** *(0–1)* — for a prior **gap-up** day (prior_open >
  close_2_days_ago): `clip((prior_open − prior_low)/(prior_open − close_2_days_ago),
  0, 1)`. *null if yesterday did not gap up* (≈40–60% non-null). **Thesis:** 0 = a
  gap that never retraced (strong demand); 1 = fully filled (indecision).

### B2 — Trend / momentum

- **`close_channel_pos_20d`** *(0–1)* — `(prior_close − min(low,20))/(max(high,20) −
  min(low,20))`. Donchian-channel position. **Thesis:** near 1 = established leader.
- **`sma20_vs_sma50_pct`** *(%)* — `(SMA20/SMA50 − 1)·100`. Continuous trend alignment.
- **`sma50_vs_sma200_pct`** *(%)* — `(SMA50/SMA200 − 1)·100`. Golden/death-cross
  magnitude. *needs 200 bars.*
- **`adx14`** *(0–100)* — Wilder ADX(14). **Thesis:** trend *strength*; a gap in an
  already-directional tape is likelier to continue.
- **`trend_efficiency_20d`** *(−1..1)* — `(close[-1] − close[-21]) / Σ|daily diff|
  over last 21`. Kaufman efficiency ratio. **Thesis:** smooth advance vs noisy chop.
- **`roc_5d`** *(%)* — `ret_pct(close, 5)`. Short-term momentum.
- **`roc_20d`** *(%)* — `ret_pct(close, 20)`. ~1-month momentum.
- **`consecutive_down_days`** *(count)* — trailing run of `close_t < close_{t-1}`.
  **Thesis:** a gap-up after several down days = potential reversal/short-cover.

### C2 — Volatility regime

- **`vol_ratio_5d_20d`** *(ratio)* — `std(last 5 daily returns) / std(last 20)`.
  **Thesis:** < 1 = short-term compression before the gap (squeeze).
- **`realized_vol_percentile_252`** *(0–1)* — current 20-day realized vol's rank
  within its own trailing 252 daily values. *needs ≥272 returns and no split.*
  **Thesis:** turns absolute vol into the ticker's own regime.
- **`prior_range_expansion_14d`** *(ratio)* — `prior_day_range / mean(prior 14 daily
  ranges, excluding yesterday)`. **Thesis:** expansion day = fresh information.
- **`spy_realized_vol_20d`** *(%, annualized)* — `std(SPY last 20 daily returns)·
  √252·100`. A fast VIX-like macro-volatility proxy.
- **`spy_20d_return`** *(%)* — `ret_pct(SPY close, 20)`. Broad-market momentum backdrop.

### D2 — Sector & market context

- **`stock_sector_corr_60d`** *(−1..1)* — Pearson correlation of stock vs sector-ETF
  daily returns over the last 60 aligned. *needs ≥30 aligned and no split.*
  **Thesis:** low correlation = idiosyncratic story; high = sector beta.
- **`beta_to_sector_60d`** *(ratio)* — `cov(stock, sector)/var(sector)`, same window.
- **`sector_20d_return`** *(%)* — `ret_pct(sector close, 20)`. Sector momentum tailwind.
- **`sector_20d_ret_minus_spy`** *(% pts)* — `sector_20d_return − spy_20d_return`.
  Sector leadership vs the broad market (sector rotation).

### E2 — Overnight structure

- **`gap_range_frac`** *(ratio)* — `(first_open − prior_close)/(prior_high − prior_low)`.
  Overnight move in units of yesterday's range. **Thesis:** > 1 = the gap skipped a
  full day's range (a genuine shock), more local than `gap_atr`.
- **`consecutive_gap_up_days`** *(count)* — if today gapped up (`first_open >
  prior_high`): `1 +` trailing run of prior days with `open_t > high_{t-1}`; else
  `0`. Uses the prior-**high** gap definition (consistent with
  `gap_pct_vs_prior_high` and strategy admission). **Thesis:** 1st gap =
  initiation; long streak = exhaustion.
- **`gap_vs_spy_gap_diff`** *(% pts)* — `(first_open − prior_close)/prior_close·100 −
  (spy_first_open − spy_prior_close)/spy_prior_close·100`. The **arithmetic**
  stock-minus-market gap. **Thesis:** clean idiosyncratic overnight move; unlike
  `rel_spy_gap` (a ratio), it does not blow up when the market gap is near zero.

### F2 — Liquidity / participation

- **`opening_volume_zscore_20d`** *(z-score)* — `(first_volume − mean(last 20 opening-
  bar volumes)) / std`. *needs ≥20 and std>0.* How many SDs abnormal today's open is.
- **`prior_volume_ratio_20d`** *(ratio)* — `prior_day_volume / mean(the 20 daily
  volumes before yesterday)`. **Thesis:** did yesterday's move draw unusual volume?
- **`dollar_volume_trend_5_20`** *(ratio)* — `mean(last 5 daily $volume)/mean(last 20)`.
  **Thesis:** rising tradable liquidity/attention.

### G2 — Calendar

- **`is_first_trading_day_of_month`** *(0/1)* — `1` if the most recent prior trading
  day's month (or year) differs from `trade_date`'s. **Thesis:** turn-of-month flows.
- **`days_since_opex`** *(days)* — **calendar** days since the most recent monthly
  opex (3rd Friday; this month if on/after it — so opex day itself = 0 — else last
  month's). **Thesis:** post-opex dealer-hedging/gamma unwind cycle position.

### H — Statistical / derived

- **`gap_zscore_60d`** *(z-score)* — today's `gap_pct_vs_prior_high` standardized
  against the last 60 days' own gap distribution (each historical
  `gap_i = (open_i − high_{i-1})/high_{i-1}·100`). *needs ≥30 and no split.*
  **Thesis:** a 2% gap is routine for some names, a shock for others.
- **`prior_return_zscore_60d`** *(z-score)* — `prior_day_return` standardized against
  the prior 60 daily returns (excluding the value being scored). *needs ≥60 and no
  split.* **Thesis:** was yesterday an abnormal momentum event?
- **`first_range_zscore_20d`** *(z-score)* — `first_range_pct` standardized against the
  last 20 prior opening-bar range %s. *needs ≥20 and std>0.* **Thesis:** opening-bar
  expansion vs the ticker's own time-of-day norm.
- **`excess_return_information_ratio_60d`** *(annualized ratio)* — `√252 ·
  mean(stock_ret − SPY_ret)/std(stock_ret − SPY_ret)` over 60 aligned days. *needs
  ≥30 and no split.* **Thesis:** persistence of outperformance, not just magnitude.
- **`max_drawdown_20d`** *(%, ≤0)* — `min((close − running_max)/running_max)` over the
  last 20 prior closes ·100. **Thesis:** a gap-up despite a recent deep drawdown =
  potential dead-cat-bounce / squeeze.

### I — Advanced range-based volatility & inferred microstructure

All over a 20-day window of prior daily OHLC (vol estimators) or the prior 5m
session (Roll / autocorrelation). Range/OHLC estimators are far more statistically
efficient than close-to-close because they use the intraday path.

- **`parkinson_vol_20d`** *(%, annualized)* — `√(mean(ln(H/L)²)/(4·ln2))·√252·100`.
  High-low range volatility (~5× more efficient than close-to-close).
- **`garman_klass_vol_20d`** *(%, annualized)* — uses O,H,L,C:
  `√(mean(0.5·ln(H/L)² − (2ln2−1)·ln(C/O)²))·√252·100` (~7× efficiency).
- **`yang_zhang_vol_20d`** *(%, annualized)* — overnight variance + k·open-to-close
  variance + (1−k)·Rogers-Satchell, `k = 0.34/(1.34 + (N+1)/(N−1))`. The only
  estimator that captures **overnight gap** variance — directly relevant here.
- **`yang_zhang_to_cc_ratio_20d`** *(ratio)* — `yang_zhang_vol / close_to_close_vol`.
  **Thesis:** > 1 ⇒ the asset's variance is dominated by overnight gaps (a true
  "gapper") vs continuous intraday drift.
- **`roll_spread_pct`** *(%)* — Roll's effective spread inferred from the prior
  session's 5m price changes: `2·√(−cov(Δp_t, Δp_{t-1}))/mean_price·100`, `0` when
  the serial covariance is non-negative. A leak-free liquidity/execution-cost proxy
  (no Level-2/NBBO data). **Thesis:** wide inferred spread eats the tight 1R edge.
- **`prior_intraday_autocorr_5m`** *(−1..1)* — first-order autocorrelation of the
  prior session's 5m returns. **Thesis:** positive = trending microstructure (the
  breakout is likelier to sustain); negative = mean-reverting (fades intraday).

---

## 5. Feature count by category

| Category | Count |
|---|---|
| A — Gap / overnight | 7 |
| B — First-candle microstructure | 10 |
| C — Volume / participation | 6 |
| D — Own trend / volatility | 6 |
| E — Relative strength / market & sector | 9 |
| F — Calendar | 5 |
| A2 — Prior-day intraday structure | 6 |
| A3 — Prior-day daily-only | 2 |
| B2 — Trend / momentum | 8 |
| C2 — Volatility regime | 5 |
| D2 — Sector / market context | 4 |
| E2 — Overnight structure | 3 |
| F2 — Liquidity | 3 |
| G2 — Calendar | 2 |
| H — Statistical / derived | 5 |
| I — Advanced vol / microstructure | 6 |
| **Total** | **87** |

---

## 6. Notes for reasoning about / extending these features

- **Leak-free is non-negotiable.** Any proposed feature must be computable strictly
  from: the first 5-minute candle, prior daily bars (< trade_date), prior 5-minute
  sessions (< trade_date), and prior SPY/sector series. Do not use the trade date's
  own daily bar, nor any regular-session bar after 09:35 ET. Calendar facts (opex
  dates, holidays) are known in advance and are leak-free.
- **Degenerate handling.** Return `None` (not 0, not NaN) on missing inputs, too-
  short history, or zero denominators (zero range, zero variance, near-zero market
  gap). Consumers expect a fixed key set with `None` holes.
- **Raw prices + splits.** All data is unadjusted. Trailing return/vol/beta/SMA
  features are guarded against split-like jumps (>40% close-to-close **or** today's
  open vs the prior close — the latter catches an overnight reverse split) and
  return `None` when their window spans one. Guards are window-matched (~21/63/272
  bars). The capture run additionally **drops candidates** whose trade date is a
  split/glitch event, so phantom gaps never enter the ledger.
- **Output integrity.** A final pass coerces any non-finite float (NaN/±inf from a
  constant series or zero variance) to `None`, so the ledger never contains NaN.
- **`adx14`** is canonical Wilder ADX on a **0–100** scale.
- **Collinearity.** Several features intentionally measure similar things multiple
  ways (e.g. `gap_pct_vs_prior_high`, `gap_pct_vs_prior_close`, `gap_atr`,
  `gap_range_frac`, `gap_zscore_60d`). Capturing near-duplicates is cheap and fine;
  but a *search* over them should avoid spending degrees of freedom on duplicates.
- **Contamination caveat.** Most features encode a prior thesis. One —
  `first_close_pos` — was reverse-engineered from in-sample loss analysis, so it is
  mildly contaminated; only out-of-sample validation can redeem it. Treat any
  data-derived feature with the same suspicion.
- **Known data we deliberately do NOT use yet** (would require new feeds and were
  excluded as not currently leak-free or unavailable): VIX series, earnings/FOMC
  calendars, pre-market (04:00–09:30) bars, point-in-time ETF holdings, NBBO/spread
  snapshots, and a point-in-time sector-constituent panel (so true sector *breadth*
  cannot be computed — only single sector-ETF series). Also intentionally excluded
  as unreliable: up/down volume split from daily OHLCV (volume is not buyer/seller-
  classified), and VWAP-touch counts (too sensitive to bar resolution and tolerance).
- **Downstream use (so you know the bar these must clear).** Features are captured
  once into a rectangular ledger (one row per admitted candidate, with its realized
  R outcome). An offline search then evaluates filter combinations as subsets of
  that ledger, validated with **walk-forward** out-of-sample folds and a **PBO**
  (probability-of-backtest-overfitting) statistic — never a single in-sample
  metric. A good new feature is leak-free, high-coverage, continuous, and carries a
  thesis distinct from the existing 81.
