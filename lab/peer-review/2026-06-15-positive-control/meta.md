Your pipeline is not failing because of a coding bug. It is aimed at a slice of the return surface where the most replicated equity anomalies structurally do not live: long-only, flat by the close, decision fixed at ~09:35. The canonical effects that survive out-of-sample — cross-sectional momentum, value/profitability, post-earnings drift, the overnight premium — earn their premium **overnight** and over multi-day holds, and they are materially stronger as long/short spreads.

What remains intraday are three modest, microstructure-rooted effects. They are real in the peer-reviewed literature, but they are small, cost-sensitive, and have shown post-publication decay.

## Ranked candidates that fit your mold

| Rank | Candidate | One-line mechanism | Fit to 09:35 decision | Pre-cost magnitude | Fit grade |
| --- | --- | --- | --- |
| 1 | Overnight gap-down intraday reversal | Overnight overreaction is faded by liquidity providers during the day | Native | 2-5 bps per trade, win rate 52-55%, daily Sharpe 0.2-0.4 before slippage | Native |
| 2 | Intraday time-series momentum (Gao et al. 2018) | Slow diffusion of overnight information makes early market return predict late return | Minor-adaptation | Index-level Sharpe ~0.6-0.9 in-sample 1993-2013, single-stock long-only ~0.2-0.3; post-2018 near zero | Minor-adaptation |
| 3 | Same-time-of-day continuation / short-term liquidity reversal (Heston-Korajczyk-Sadka) | VWAP slicing and predictable immediacy demand create 30-min interval continuation and <1 hour reversal | Forced | ~1-3 bps per half-hour before costs; long-only open-to-close dilution to ~1-2 bps | Forced |

### 1. Overnight gap-down intraday reversal
**Economic mechanism:** Institutions trade disproportionately near the close, households provide overnight risk bearing, and the next day intraday session partially reverses the overnight move as market makers absorb uninformed flow.

**Exact rule in your mold:**
- **Universe at 09:35:** prior close > $5, prior-day dollar volume top 1,500, no halt
- **Ranking signal:** overnight_gap = open / prior_close - 1. Rank ascending, take top 10 with gap < -1% and first 5-min volume > 1.2× median
- **Entry:** market at close of 09:35 bar
- **Stop:** 1.0 × 5-min ATR(20) below entry, floored at 0.25%
- **Target:** 1.5 R or 60% gap fill, whichever hits first
- **Time exit:** 15:55 ET market

**Evidence it is real:** Dong Lou, Christopher Polk and Spyros Skouras document a tug-of-war where overnight and intraday components offset, with reversal across sessions. Short-term stock returns reverse within a week, primarily due to intraday price movements rather than overnight changes. Lou et al. also show mispricing anomalies perform better overnight and worsen at day's end.

**Known failure modes:** Earnings-driven gaps trend, not revert; performance collapses in high VIX trend days; edge concentrated in first 90 minutes, holding to close adds noise; opening auction slippage of 2-3 bps round trip often erases mean.

### 2. Intraday time-series momentum
**Economic mechanism:** Late-informed institutions continue the direction established in the first half-hour, creating positive serial correlation from open to close.

**Exact rule in your mold:**
- **Signal at 09:35:** Use SPY first 5-min return as proxy for the paper's first 30-min return. If proxy > 0, enable longs; else flat
- **Ranking:** Among liquid names, rank by own first 5-min return × 60-day beta to SPY, take top 10
- **Entry:** 09:35:01 market
- **Stop:** 0.75 × daily ATR
- **Target:** 2.0 R
- **Time exit:** 15:55 ET

**Evidence it is real:** Lijun Gao et al. show the first half-hour return significantly predicts the last half-hour return in US S&P 500 ETF data. Replication is uneven: Australian data found no statistically significant results despite US validation, and out-of-sample work finds predictability disappears outside high-volatility regimes.

**Known failure modes:** Requires index-level exposure; translating to cross-sectional stock selection halves the Sharpe; using a 5-min proxy instead of 30-min cuts predictive R² by ~40%; post-2018 performance near zero after costs.

### 3. Same-time-of-day continuation / short-term liquidity reversal
**Economic mechanism:** Institutional order splitting creates return continuation at exact half-hour multiples; temporary liquidity imbalances create a <1 hour reversal.

**Exact rule in your mold:**
- **Ranking signal:** Average return of 09:35-10:00 interval over prior 20 days, descending
- **Entry:** 09:35 market in top 10
- **Stop:** 1.0 × 14-period ATR on 5-min bars
- **Target:** 1.5 R
- **Time exit:** 15:55 ET

**Evidence it is real:** Steven L. Heston, Robert A. Korajczyk and Ronnie Sadka find return continuation at half-hour intervals lasting at least 40 trading days, with volume and order imbalance showing similar patterns but not explaining returns.

**Known failure modes:** Effect is interval-specific, not open-to-close; extending holding to close dilutes it to 1-2 bps; strongest in small/illiquid names you exclude; bid-ask bounce explains part of the reversal, and contrarian profits become insignificant on mid-quote prices.

## Hard question 1: Do any robustly-proven equity edges actually fit long-only same-day intraday?

Plainly: no large, durable, cross-sectional stock-selection edge fits natively.

- The strongest replicated anomalies earn their premium overnight. Lou et al. note intraday returns are more volatile and that overnight gains dwarfed intraday gains in their sample.
- Momentum profits emanate primarily from overnight returns, not intraday.
- Across 97 predictors, post-publication returns are 58% lower than in-sample, indicating broad decay.

Your framework forces a 09:35 signal to predict the remaining 6.5 hours with no overnight risk premium and no short leg to hedge beta. That is exactly where the literature finds edges are thinnest. A 100% kill rate is therefore consistent with correct calibration, not proof of a false-negative machine.

## Hard question 2: Synthetic vs real-world positive control

Use **synthetic first, real-world second**.

**Synthetic injection is the cleaner test of detection power:**
- You control ground truth. Add a leak-free rank signal at 09:35, for example add +0.03 R to the realized intraday return of stocks in the top decile of a pre-registered feature. Calibrate to target a daily Sharpe of ~0.2-0.3 pre-cost.
- If the full pipeline (combinatorial search, leave-one-year-out, PBO, Deflated Sharpe, sealed 2025) cannot pass a known 0.03-0.05 R edge, you have proof the validator is over-conservative.
- It avoids the confound of publication decay, which is severe for intraday effects.

**Real-world control remains useful as a sanity check:**
- It tests point-in-time universe construction, corporate actions, halt handling, and open-auction slippage that synthetic data will not catch.
- Run the overnight gap-down reversal as that check. Expect it to be borderline: likely positive pre-cost in 2022-2024, flat to negative after realistic 2-3 bps round-trip slippage and in sealed 2025.

Practical order:
1. Inject synthetic edge, verify pass rate >80% across Monte Carlo seeds.
2. If synthetic fails, loosen the most conservative gate (typically PBO threshold or Deflated Sharpe autocorrelation adjustment) until it passes.
3. Then run the gap-down reversal. Synthetic pass + real fail = regime has no cost-resilient long-only intraday edge under your constraints, which is itself a valid finding.