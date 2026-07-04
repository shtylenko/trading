# Feature Ideation Prompt — Candidate Admission Features for Long-Only Stock/ETF Strategies

**For**: AI model with read access to this codebase  
**Goal**: Propose 15–30 new candidate-admission features that are NOT yet implemented  
**Constraint**: Leak-free (computable by 09:35 ET from prior daily + first 5m candle + SPY/sector context). Long-only stocks & ETFs only.

---

## 1. What We Have Now — The Existing Feature Library

The feature library lives at `trading/lab/research/features.py`. It computes **41 features** across 6 categories, all leak-free. Here is the exact feature key set from `FEATURE_NAMES` (lines 37–58):

```
# A — gap / overnight structure (7 features)
gap_pct_vs_prior_high      # open vs prior day's high, %
gap_pct_vs_prior_close     # open vs prior day's close, %
gap_atr                    # (open - prior_close) / ATR14
gap_vs_20d_high_pct        # open vs 20-day high, %
prior_day_return           # prior day's close-to-close return %
prior_day_close_pos        # prior close position within prior day's range (0-1)
consecutive_up_days        # streak of higher closes leading into today

# B — first-candle (opening-range) microstructure (10 features)
first_open                 # absolute open price (raw, not log)
first_close_pos            # (close-low)/(high-low), location of close in bar range
first_range_pct            # (high-low)/close × 100
first_range_atr_frac       # (high-low) / ATR14
first_body_frac            # |close-open| / (high-low), candle body fraction
first_upper_wick_frac      # (high - max(open,close)) / range
first_lower_wick_frac      # (min(open,close) - low) / range
first_return               # (close-open)/open × 100, first-bar return %
breakout_distance          # (high-open)/open × 100, distance to breakout level
open_pos_in_first          # (open-low)/(high-low), open position in bar

# C — volume / participation (5 features)
first_volume               # raw first-bar volume (shares)
first_dollar_volume        # first_volume × first_close
first_vol_frac_of_prior_day  # first_vol / prior day's total volume
opening_rv                 # first_vol / mean(prior opening-bar volume)
rvol_20d                   # first_vol / mean(last 20 days' opening-bar volume)
avg_daily_volume           # mean daily volume (14-day)

# D — stock's own trend / volatility (5 features)
close_vs_own_50d_sma       # (prior_close - SMA50) / SMA50 × 100
close_vs_own_200d_sma      # (prior_close - SMA200) / SMA200 × 100
stock_above_own_50d        # 1 if prior_close > SMA50, else 0
adr_pct                    # ATR14 / prior_close × 100 (Average Daily Range %)
dist_from_20d_high_pct     # (prior_close - 20d_high) / 20d_high × 100
realized_vol_20d           # std(20d daily returns) × 100, annualized-style

# E — relative strength / market & sector (9 features)
rel_spy_gap                # gap_pct_vs_prior_high / SPY's gap %
stock_5d_ret_minus_spy     # stock 5d return - SPY 5d return
stock_20d_ret_minus_spy    # stock 20d return - SPY 20d return
rel_sector_momentum_20d    # stock 20d return - sector ETF 20d return
spy_first_return           # SPY's first-bar return %
spy_first_close_pos        # SPY's first-bar close position
beta_60d                   # stock daily returns vs SPY daily returns (60d)
spy_below_50d_sma          # 1 if SPY prior_close < SMA50
sector_below_50d_sma       # 1 if sector prior_close < SMA50

# F — calendar / seasonality (5 features)
day_of_week                # 0=Mon..4=Fri
month                      # 1..12
is_month_end               # 1 if day >= 25
is_quarter_end_month       # 1 if month in (3,6,9,12)
is_opex                    # 1 if 3rd Friday of month
```

And the existing shared filters at `trading/lab/research/filters.py`:

```
min_price(daily, threshold=5.0)       # prior close ≥ $5
min_avg_daily_volume(daily, 1M, 14)   # 14-day ADV ≥ 1M shares
green_first_candle(bars_5m)           # first 5m close > open
daily_atr_14(daily, 14)               # Wilder ATR(14) — numeric, used by features
first_regular_5m_bar(bars_5m)          # extract first 09:30 bar (index, Series)
has_split_like_jump(daily, 15, 0.40)  # guard: >40% jump in trailing window
```

Plus `trading/lab/research/signal_helpers.py`:
```
breakout_signal_params(bars_5m)  # first bar OHLCV → {first_ts, high, low, risk, open, close, volume}
```

---

## 2. Available Primitives at Admission Time (09:35 ET)

This is the full information universe the feature function receives (see `compute_candidate_features` signature, line 130–138 of `features.py`):

| Argument | Type | Description |
|----------|------|-------------|
| `trade_date` | `date` | Today's date |
| `first_bar` | `pd.Series` or None | First regular 5m candle (open/high/low/close/volume), fully closed at 09:35 |
| `daily` | `pd.DataFrame` or None | Ticker's daily OHLCV bars. Sliced to strictly `< trade_date` inside the function via `_prior()` |
| `hist_5m` | `pd.DataFrame` or None | Ticker's historical 5m bars across prior sessions. Used to compute opening-bar volume statistics |
| `spy_daily` | `pd.DataFrame` or None | SPY daily bars, same slicing |
| `spy_5m` | `pd.DataFrame` or None | SPY 5m bars for today |
| `sector_daily` | `pd.DataFrame` or None | Matched sector-ETF daily bars (e.g., XLK, XLF) |

These are delivered via the `StrategyContext` dataclass (`core/models.py` lines 37–50):

```python
@dataclass
class StrategyContext:
    trade_date: date
    bars_5m: dict[str, pd.DataFrame]       # ticker → today's 5m RTH bars
    daily: dict[str, pd.DataFrame]         # ticker → daily bars
    historical_5m: dict[str, pd.DataFrame] # ticker → prior 5m bars
    spy_5m: pd.DataFrame | None            # SPY 5m bars
    spy_daily: pd.DataFrame | None         # SPY daily bars
    extra_daily: dict[str, pd.DataFrame]   # extra symbols (sector ETFs, etc.)
    bars_1m: dict[str, pd.DataFrame]       # optional 1m bars
```

The thin adapter `features_from_context()` at line 296–315 pulls primitives from this context and calls `compute_candidate_features()`.

**Key constraint**: Features must be computable with NO access to:
- Current-day bars beyond the first 5m candle (09:35)
- Future daily bars (on or after `trade_date`)
- Any non-public information like earnings announcements, analyst ratings, news sentiment
- The ticker's same-day VWAP (not computable yet — only 1 bar of volume exists)

**Available but NOT yet exploited in the feature library**:
- `hist_5m` contains ALL 5m bars from prior sessions — currently only used for opening-bar volume. This is a rich, largely untapped signal source (prior-day VWAP, prior-day ranges, intraday patterns from similar-time windows in prior sessions).
- `sector_daily` exists but only 2 of the 41 features touch it (`rel_sector_momentum_20d`, `sector_below_50d_sma`).
- `bars_1m` is available to strategies that declare `requires_rth_1m = True` — currently used for fill simulation fidelity, not for feature computation.
- `extra_daily` can carry ETN/ETF series for multi-factor regime context (breadth, realized correlation, VIX proxy).

---

## 3. How Features Are Consumed by Strategies

Each `Candidate` object carries a `features: dict[str, Any]` (see `core/models.py` line 55–59). Strategies populate this in `build_candidates()` and can gate on it in either:

1. **build_candidates()** — admission/ranking. Example: `variants.py` (post_gap_opening_drive) lines 90–153 read `f.get("gap_pct_vs_prior_high")`, `f.get("first_close_pos")`, `f.get("first_volume")` etc. to filter candidates.

2. **build_signal()** — per-candidate signal construction. Example: `variants.py` lines 156–165 adjust `target_price` and `metadata["require_above_vwap"]` based on variant knobs.

3. **Offline combinatorial search** — the `validation/feature_search_spec.md` defines a capture→search→walk-forward pipeline where ALL 41 features are captured per candidate, then scored in subset combinations. The combinatorial search tests admission filters without re-running backtests.

---

## 4. What Strategies Exist and What Features They Use

Four strategy families in `trading/lab/strategies/`:

| Family | Dir | Description | Key features consumed |
|--------|-----|-------------|---------------------|
| **o** (stocks_in_play_orb) | `stocks_in_play_orb/` | Opening-range breakout with RV gate, ATR stop, 1% risk. 11 releases (o01–o11). | `gap_pct_vs_prior_high`, `first_volume`, RV, ATR, SPY ATR regime (o07/o11), ML ranking (o03) |
| **d** (post_gap_opening_drive) | `post_gap_opening_drive/` | Gap-and-go: gap > 1% above prior high, green first candle, breakout of first-candle high. 14 releases (d01–d14). | `gap_pct_vs_prior_high`, `first_close_pos`, `first_range_atr_frac`, `opening_rv`, `rel_spy_gap`, sector 50d SMA, SPY 50d SMA |
| **f** (dominance_flip_reversal) | `dominance_flip_reversal/` | Capitulation-reversal: z-score extremes, volume climax, SMA divergence. 7 releases (f01–f07). | `spy_above_200sma` (f02), warm start from historical 5m (f03) |
| **s** (smma_atr_breakout) | `smma_atr_breakout/` | Smoothed MA + ATR breakout. 1 release (s01). | Daily trend, ATR, SMMA crossover |

The f and s families do NOT use the research features library yet — they compute features inline. Only o and d families route through `research/features.py`.

---

## 5. What We're Looking For — Feature Categories to Mine

Given the above, here are the **lacunae** — areas where the feature library has no coverage yet. Each is a category where you should propose concrete features:

### 5A. Prior-Day Intraday Structure (via `hist_5m`)

The 41 features have ZERO features derived from prior-day intraday patterns beyond opening-bar volume. Yet `hist_5m` contains the full 5m OHLCV history for each prior session. Ideas:

- Prior-day VWAP vs prior-day close (overnight conviction)
- Prior-day afternoon range / morning range ratio (who controlled the session)
- Prior-day close location within the day's range (high-of-day close vs low-of-day close — continuation signal)
- Prior-day volume profile shape (U-shaped = distribution, J-shaped = accumulation)
- Number of VWAP touches in prior session (institutional activity proxy)
- Prior-day gap fill behavior (did yesterday's gap fill or hold?)
- Prior-day 9:30–10:00 range vs full-day range (opening-hour conviction)

### 5B. Multi-Timeframe Trend Alignment

The feature library has daily SMAs and 20d realized vol. Missing:

- Rate-of-change features (5d, 10d, 21d ROC of the prior close)
- Moving average cross states (20/50 cross, 50/200 cross — golden cross / death cross) 
- Donchian channel position (prior_close within N-day high-low channel)
- ADX / trend strength from daily bars (the 14-period ADX uses ATR-like TR already available)
- Consecutive down days (mirror of `consecutive_up_days`)
- Prior day's intraday high vs prior day's high (breakout follow-through or failure)
- 5-day high/low relative position

### 5C. Volatility Regime & Compression

- Historical volatility percentile (current 20d vol vs its own 1-year distribution)
- Volatility expansion/contraction ratio (short-term vol / long-term vol — Bollinger Band squeeze proxy)
- Prior-day range vs average range (range expansion day → higher probability of follow-through)
- VIX proxy or SPY realized vol percentile (available via `spy_daily`)

### 5D. Sector & Cross-Asset Context (deeper than 2 features)

The `sector_daily` and `extra_daily` inputs are almost entirely unused:

- Sector relative strength percentile (stock's 20d return rank within its sector peers)
- Sector breadth (% of sector members above their 20d SMA — needs breadth data in `extra_daily`)
- Dollar/rates regime from ETF proxies (e.g., UUP, TLT in `extra_daily`)
- Correlation of stock returns to sector returns over recent window
- Sector rotation signal: sector momentum rank among all sectors
- Stock's beta to sector (not just SPY)
- Inter-market divergence (stock up 5d but sector down → idiosyncratic story)

### 5E. Overnight & Pre-Market Structure

The gap features (A1–A7) cover overnight structure basics. Missing:

- Overnight range as % of prior day's range (gap magnitude relative to recent volatility)
- Gap direction streak (consecutive gap-up days — momentum vs exhaustion)
- Prior close vs prior VWAP (was yesterday's close above or below institutional cost basis?)
- Gap type classification (common gap / breakaway gap / exhaustion gap — needs pattern recognition over 3-5 days)

### 5F. Liquidity & Market Microstructure

- Spread proxy: prior day's (high-low)/close as % vs 20d average (wide spread = illiquid day)
- Dollar volume trend: 5d ADV vs 20d ADV (increasing/decreasing interest)
- Volume climax detection: today's first-bar volume vs distribution of prior first-bar volumes (z-score, not just ratio)
- Prior-day volume vs its own 20d average (volume confirmation of prior move)
- Up/down volume ratio over prior N days

### 5G. Calendar & Seasonality (deeper than 5 features)

- Days since last opex (positioning unwind effects)
- Days into quarter (institutional rebalancing flows)
- Is FOMC week (from a calendar lookup — pre-known, not leaked)
- Earnings within N days (from a pre-built earnings calendar — pre-known)
- Is Monday/Friday (weekend gap risk asymmetry)
- First trading day of month / last trading day of month (window dressing flows)
- Holiday-shortened week flag

### 5H. Statistical & Derived Features

- Z-score of gap vs its own 1-year distribution (is this an unusually large gap?)
- Z-score of first-bar range vs its own distribution
- Prior-day return z-score (was yesterday an outlier move?)
- Max drawdown from recent peak (prior_close / 20d high - 1)
- Upside/downside capture ratio vs SPY over 60d
- Information ratio: excess return over SPY / tracking error over 60d
- Sortino-style: return / downside deviation over 60d

### 5I. ETF-Specific Features (for when the universe includes ETFs)

- Premium/discount to NAV proxy: ETF's gap vs the weighted gap of its top holdings
- ETF flow proxy: prior day's dollar volume spike relative to 20d (creation/redemption activity)
- ETF's correlation to SPY over 60d (sector ETFs: XLF ≈ 0.85, XLK ≈ 0.95, GLD ≈ 0.05)

---

## 6. Constraints & Design Rules

When proposing a new feature, it MUST satisfy ALL of these:

1. **Leak-free**: Computable from primitives that exist at 09:35 ET on `trade_date`. Test: can a human trader compute this value at 09:35 using only a daily chart and the first 5m candle? If yes, it's leak-free.

2. **Pure function**: The feature should be computable given the primitives in §2. No network calls, no database access, no random state.

3. **Same-day VWAP is NOT available**: With only 1 bar of volume, the session's cumulative VWAP is trivially the first bar's OHLC average — not useful. Prior-day VWAP IS available (via `hist_5m`).

4. **Long-only relevance**: The feature should help answer "should I buy this stock/ETF today?" Not "should I short it?" Directional asymmetry is fine — features that only matter for longs are in-scope.

5. **Return None gracefully**: If input data is insufficient (too few bars, missing `sector_daily`, no `hist_5m`), the feature should return `None` rather than raise. The existing pattern: `_ret_pct()`, `_sma_dist_pct()`, `_below_sma()` all return `None` on insufficient data (see `features.py` lines 63–101).

6. **Stable key set**: Every new feature must be added to `FEATURE_NAMES` (the capture ledger columns) and computed in `compute_candidate_features()` as `f["new_feature_name"] = ...`. The capture run expects a rectangular output.

7. **No same-day multi-bar patterns**: Features like "opening drive: first 3 bars all green" require bars 2 and 3 which don't exist at 09:35. The ONLY intraday bar available is the first 5m candle.

---

## 7. Output Format

For each proposed feature, provide:

```markdown
### Feature: `snake_case_name`

- **Category**: [A–I from §5 above, or a new category]
- **Primitives used**: [e.g., `first_bar`, `daily`, `hist_5m`, `spy_daily`]
- **Computation**: Pseudocode or Python showing the exact formula
- **Thesis**: Why would this discriminate good long entries from bad ones?
- **Expected non-null rate**: [e.g., ">95% for S&P 500 with 60d+ history", "requires sector_daily, ~80% coverage"]
- **Prior art**: [If this feature appears in academic literature, existing trading systems, or prior releases]
- **Risk of look-ahead**: [Explain why it's leak-free, or flag a subtle concern]
```

Organize proposals by category. Aim for 15–30 proposals total, spread across categories. Prioritize categories 5A (intraday structure), 5E (overnight structure), and 5H (statistical) as they are the richest unexploited seams.

---

## 8. Code Reference Index

Key files to read for context:

| File | What it contains | Key lines |
|------|-----------------|-----------|
| `trading/lab/research/features.py` | All 41 existing features + FEATURE_NAMES | Full file (315 lines) |
| `trading/lab/research/filters.py` | Shared filters (min_price, daily_atr_14, etc.) | Full file (139 lines) |
| `trading/lab/research/signal_helpers.py` | breakout_signal_params | Full file (55 lines) |
| `trading/lab/core/models.py` | StrategyContext, Candidate, Signal, SimulatedTrade | All (95 lines) |
| `trading/lab/core/execution.py` | Trade simulators (breakout + pullback) | Lines 43–189 (long breakout), 295–412 (pullback limit) |
| `trading/lab/strategies/base.py` | StrategyRelease ABC | Full file (60 lines) |
| `trading/lab/strategies/post_gap_opening_drive/variants.py` | d-family variant with feature consumption examples | Lines 90–153 (build_candidates filtering) |
| `trading/lab/strategies/dominance_flip_reversal/variants.py` | f-family variants (warm_start, spy_above_200sma) | Lines 37–53 (spy_above_200sma), 95–124 (build_candidates) |
| `trading/lab/runner/pipeline.py` | Context loading (_load_context), run loop, DB writes | Lines 964–1056 (_load_context), 567–745 (run_backtest_for_date) |
| `trading/lab/scripts/capture_features.py` | Feature-capture driver | Full file (189 lines) |
| `trading/lab/validation/feature_search_spec.md` | Combinatorial search spec with in/out of scope | Full file (215 lines) |
| `trading/lab/tests/test_features.py` | Feature unit tests — shows expected behavior patterns | Full file (143 lines) |
| `trading/lab/research/backlog.md` | Research tool backlog (GA optimizer etc.) | Full file (57 lines) |

---

## 9. Bonus: Non-Feature Ideas

Beyond admission features, we're also interested in ideas for:

1. **New exit criteria** — the execution engine supports: STOP_LOSS, TARGET, TIME_EXIT, TIME_STOP (time+min-R gate), TIME_DECAY (N-bar abort), VWAP_BREAK. What other exit conditions could improve R distribution without adding overfit risk?

2. **New signal metadata keys** — `Signal.metadata` is a dict that flows into the simulator. Current keys: `time_stop_at`, `time_stop_min_r`, `max_hold_bars`, `require_above_vwap`, `pullback_limit`, `pullback_ttl_min`, `target_price`, `direction`, `shares`. What other metadata could alter simulation behavior in useful ways?

3. **New ranking/scoring functions** — currently candidates are ranked by `gap_pct_vs_prior_high` (d family) or `abs(z_min)` (f family). What multi-factor scoring (without ML) could improve rank-ordering of candidates?

4. **New data primitives** — what data should the runner hydrate into `StrategyContext` that isn't there yet? The contract supports `extra_daily` for arbitrary symbols and `bars_1m` when `requires_rth_1m = True`. What else?

If you have ideas in these categories, include them in a separate "Non-Feature Ideas" section at the end of your response.
