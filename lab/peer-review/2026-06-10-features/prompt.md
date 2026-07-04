# Peer Review: ORB ML Feature Set & Strategy Design

You are a quantitative trading researcher with deep expertise in opening-range breakout (ORB) strategies, machine learning feature engineering for intraday equity signals, and systematic strategy design. I need you to review the following strategy description and feature set, then answer the questions at the bottom.

---

## Strategy: Stocks-in-Play ORB v2 (o03) — ML + Pullback Limit Entry

### Objective
A long-only, same-day mean-reversion-to-momentum strategy on US large-cap equities. The thesis is that stocks exhibiting abnormal opening volume ("Stocks in Play") after a positive first 5-minute candle have institutional momentum that can be captured via a passive pullback entry.

### Research Basis
Based on the SSRN paper *"A Profitable Day Trading Strategy For The U.S. Equity Market"* by Zarattini, Barbon & Aziz (2024), with modifications. The original paper uses stop-order entry at the opening-range high (H). Phase v2 replaces the stop entry with a maker-style limit entry below H after a breach, which flips expected R from negative (~−0.35R) to positive.

### Entry Rules (in order)
1. **Time**: Regular trading hours only (09:30-16:00 ET). All signals expire by 11:00 ET (90 min after open).
2. **SIP filter gauntlet** (all must pass):
   - Opening price > $5.00
   - 14-day average daily volume >= 1,000,000 shares
   - 14-day Wilder ATR > $0.50
   - Green first 5-minute candle (close > open)
   - Relative volume (RV) >= 2.0 (first 5-min volume vs 14-day mean opening volume)
   - No split-like jump (>40% move) in trailing 15-day window (raw-price integrity guard)
3. **Ranking**: Top 10 candidates by LightGBM classifier probability of hitting +2R before stop (fallback: RV ranking).
4. **Trigger**: 1-minute bar closes above the first 5-minute candle high (the "breach").
5. **Entry**: Buy limit order at H − 0.02 × ATR14, working for 30 minutes after the breach (strict fills — order starts the minute *after* breach).

### Exit Rules
- **Stop-loss**: H − 0.10 × ATR14 (this is the risk unit R).
- **No profit target**: hold until forced exit.
- **Time exit**: flatten at 15:59 ET sharp (full day hold).
- **Position sizing**: 1% account risk on the full R distance, hard 4x leverage cap, floor 1 share.

### Known Performance Characteristics (H2 2024 broad universe)
- +34.4R gross, 10.1% win rate, 1.14 profit factor
- Tail-driven: top 10 trades = +153.9R (447% of total); remaining 554 trades net −119.5R
- Daily R std: 6.9R (extreme variance — best day +36.8R, worst ~−8R)
- September 2024 alone: −38.4R
- Research OOS (May-Dec 2024) claimed +183%/yr, Sharpe 2.6, maxDD −11%; engine backtest delivers ~68R/yr with −61.8% compounded DD at 1% risk (2.5-3× gap to reconcile)
- LightGBM (AUC ~0.61) performs comparably to simple RV ranking — ML selection is not yet the edge driver; the pullback entry mechanic is

---

## Current ML Feature Set (18 features)

The LightGBM classifier predicts P(breach → hit +2R target before hitting the stop). Features are computed at the opening-range close (09:35 ET) — all observable at decision time.

### Group 1: Opening Range Structure (from first 5-minute candle)

| # | Feature | Definition | Rationale |
|---|---------|-----------|-----------|
| 1 | `range_width_atr` | (H − L) / ATR14 | Opening range width normalized by recent vol — wide ranges with tight ATR suggest explosive setups |
| 2 | `or_close_pos` | (close − L) / (H − L) | Where price settled inside the range (0=bottom, 1=top) — near-high closes suggest conviction |
| 3 | `f5_body_ratio` | (close − open) / (H − L) | Body-to-total-range ratio — big body = directional strength, small body in wide range = indecision |
| 4 | `f5_ret` | (close − open) / open | Raw return of the first 5-minute candle — momentum intensity |
| 5 | `or_vol_ratio` | first-5m volume / 14-day mean opening volume | Same as RV for this ticker — duplicates #6 but at the OR level |

### Group 2: Ticker-Level Daily Context

| # | Feature | Definition | Rationale |
|---|---------|-----------|-----------|
| 6 | `rv` | first-5m volume / 14-day mean opening volume | Core "Stocks-in-Play" signal — abnormal opening volume = institutional attention |
| 7 | `gap_pct` | (open − prior_close) / prior_close | Overnight move magnitude including direction |
| 8 | `gap_abs` | abs(gap_pct) | Gap magnitude independent of direction |
| 9 | `atr_pct` | ATR14 / prior_close | Per-share volatility as a percentage of price |
| 10 | `log_dollar_vol` | log10(avg_vol_14 × prior_close) | Liquidity tier — larger = better fill quality |
| 11 | `vol_concentration` | first-5m volume / 14-day avg daily volume | How much of the expected daily volume printed in the first 5 minutes — extreme concentration may signal exhaustion |
| 12 | `prior_day_ret` | (close[-1] − close[-2]) / close[-2] | Yesterday's momentum |
| 13 | `dow` | weekday() | Day-of-week pattern (0=Monday) |

### Group 3: Market Context (SPY Features)

| # | Feature | Definition | Rationale |
|---|---------|-----------|-----------|
| 14 | `spy_gap` | SPY overnight gap % | Overall market direction at open |
| 15 | `spy_ret_5m` | SPY first 5-minute candle return | Broad market strength at the open |
| 16 | `spy_vwap_dist` | (close − VWAP) / VWAP of first 5 SPY minutes | Where SPY sits vs its opening VWAP — above = bullish bias |
| 17 | `spy_vr` | ATR5 / ATR20 of SPY daily | Market volatility regime — >1 = expanding vol (higher breakout probability & wider stop-out risk) |

### Group 4: Fixed / Structural

| # | Feature | Definition | Rationale |
|---|---------|-----------|-----------|
| 18 | `window` | 5.0 | Always 5-minute opening range (3m/10m tested in research, production uses 5m only) |

---

## Known Issues & Open Questions (Context for Reviewer)

1. **AUC is low (0.61)** — ML barely beats RV ranking on 2024 data. The pullback entry mechanic, not the ranking, drives PnL.
2. **Tail-dependence** — top 10 trades produce 447% of total PnL. The ML model should ideally find *more* of these tails, not just better average rank.
3. **September collapse** — −38.4R in one month erased five weeks of gains. Mean-reverting tape regime is the leading hypothesis (ORB bleeds when intraday follow-through fails). No regime filter exists yet.
4. **No-fill risk** — 30% of signals never fill (strongest movers don't pull back). These could be the best trades we're systematically missing.
5. **Research/engine gap** — 2.5-3× PnL discrepancy between research simulation and engine backtest. Slippage/fees, ranking inputs, and the stop-fill model are the main suspects.
6. **Only 2024 data** — the model has never been tested on 2022 (bear), 2023 (chop), or 2025+H1 2026 (true OOS).
7. **Raw prices only** — no order-book features, no level-2, no options data, no fundamental data.
8. **Daily ATR uses Wilder smoothing** — the 0.10×ATR stop is coarse; intraday volatility dynamics differ from daily.

---

## Questions for Reviewer

### A. Algorithm Design
1. What structural changes to the strategy (entry, exit, sizing, selection) would you test first, given the known issues above?
2. The pullback limit misses the fastest movers (30% no-fill rate). Is two-tier entry (limit first, market/stop fallback at TTL expiry) worth the added complexity and adverse selection risk?
3. Should the skip/no-fill decision be a separate ML head (nuisance classifier) or handled inside the main model as a 3-class output (skip / pullback-fill / stop-fill)?
4. The daily R std is 6.9R — extreme variance. Beyond a regime filter, what variance-reduction techniques would you recommend for a tail-driven strategy?

### B. Feature Engineering
1. Which of the 18 current features would you remove or transform, and why? (Consider multicollinearity, noise, look-ahead, or irrelevance — e.g. `or_vol_ratio` ≈ `rv`, `window` is constant.)
2. What new features would you add? Consider:
   - **Price action**: intraday ATR decay in the first 5 minutes, opening-range volume profile (were the volume bars front-loaded or distributed?), size of the opening spread, first-minute tick-implied volatility
   - **Market microstructure**: bid-ask spread at trigger (proxy available from 1-min bar range?), trade count vs volume (avg trade size — retail vs institutional signature)
   - **Cross-sectional**: sector ETF relative strength at open (XLK for AAPL, etc.), rank of RV within today's universe (position in the SIP queue)
   - **Temporal**: proximity to earnings, dividend ex-date, options expiry, FOMC days, month-end rebalance — all from a standard calendar
   - **Alternative**: VIX level / VIX futures term structure, sector dispersion (correlation regime), treasury yield change overnight
3. The model currently uses raw (unadjusted) intraday prices but daily ATR. Would split-adjusted daily indicators + raw intraday features cause systematic bias? Should ATE/returns be harmonized?
4. How would you handle the constant `window=5` feature? It adds noise to the model but keeps the feature vector compatible with 3m/10m research forks.

### C. Methodology
1. Walk-forward: the model was trained on sliding 6-month windows of 1 year (2024-only). For a multi-year extension (2022-2026), what window/gap sizes would you recommend, and why?
2. The label is P(hit +2R before stop). Would you consider alternatives: P(positive R at EOD), P(breach), expected R regression, or a multi-class label?
3. Given AUC ~0.61, is LightGBM the right model class? Would logistic regression with interaction terms, gradient-boosted trees with different hyperparameters, or a different architecture be worth testing?
4. How would you design a permutation/randomization test to validate that the ML ranking actually adds value beyond RV ranking (controlling for multiple-testing)?

---

Please provide your feedback organized by section (A, B, C). For each recommendation, include the expected impact (high/medium/low), the implementation cost (lines of code, data dependencies), and any pitfalls to watch for. Be specific — "use sector ETF relative strength" is less useful than "compute [ticker_sector_ret / xlk_ret] at 09:35, shifter by one day; expect weak signal unless sector-wide catalyst is present."
