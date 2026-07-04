**No robust, widely replicated academic cross-sectional long-only same-day intraday stock-selection edges cleanly fit your exact mold.** The literature’s strongest, most replicated equity edges (classic cross-sectional momentum, value, PEAD, short-term reversal) predominantly live in overnight, multi-day holding periods, or long/short constructions. Documented intraday effects are thinner, often index-level/time-series, liquidity-driven/short-horizon, or practitioner-oriented with weaker replication pedigrees.

Your strict framework (fixed ~09:35 decision on leak-free daily + ~30 prior intraday sessions + first 5-min bar + SPY/sector data; long-only; same-day close; liquid ~1k–1.5k name universe; mechanical R-multiple rules; capped top-N by ranking; 2022–2024 search + 2025 sealed) sits in a regime where durable, economically meaningful edges are inherently sparse or low-power after realistic costs/slippage/competition. That is likely why everything dies — not (or not only) because the validator is a false-negative machine. A positive control that “should” pass is hard to find in real data; a synthetic one is cleaner for testing detection power.

### Ranked Shortlist (Skeptical, Evidence-Based)

I rank by your criteria (documented/replicated + post-pub OOS survival > practitioner claims; fit to long-only same-day intraday with ~09:35 leak-free data; robust/modest > large/fragile; low cost/capacity sensitivity on liquid names; clear mechanism; implementable mechanically in R).

**1. Market Intraday Momentum (Gao, Han, Li & Zhou, JFE 2018; replications e.g. Li et al. 2022 international evidence)** — Best-documented candidate; modest, regime-aware, survives costs in tests.

- **One-line mechanism**: First-half-hour market return (prev close to ~10:00 ET) positively predicts last-half-hour continuation on the same day. Likely driven by institutional infrequent rebalancing (Bogousslavsky-style) + late-informed trading near close to avoid overnight risk; amplified by liquidity shocks, order-flow imbalances, high-vol/high-volume/news days, and recessions.

- **Exact rule in your mold** (minor adaptation; decision at 09:35 proxy):  
  At 09:35 ET (after first 5-min bar), compute proxy first-period return \( r_{\text{first}} = \frac{\text{SPY (or SPX proxy) close at 09:35}}{\text{prev close}} - 1 \).  
  If \( r_{\text{first}} > 0 \) (or > historical mean or a simple threshold calibrated in walk-forward), go **long-only** a broad liquid equity exposure: either SPY itself or a cap-weighted (or equal-weighted) basket of the top-N most liquid names in your point-in-time universe (e.g., top 50–100 by prior-day dollar volume or a simple liquidity rank). Position size scaled to target risk (e.g., fixed notional or vol-targeted).  
  **Entry**: Market or limit at/after 09:35 signal.  
  **Stop**: None (or very tight time-based/breakeven after 30–60 min to limit tail).  
  **Target**: None (or scale out partial at 1R).  
  **Time-exit**: Mandatory flat by 15:55–16:00 ET (regular close).  
  Outcome in R (risk = e.g. ATR or fixed % of price). Cap at your N (or 1 “name” if using SPY ETF as proxy). Use only data knowable at 09:35 (prior dailies + intraday history + first 5-min bar + SPY). Leak-free by construction. For stricter stock-ranking flavor: rank all names by a neutral signal (e.g., 1 or beta-adjusted) and take top-N **only if** market \( r_{\text{first}} > 0 \); else flat. This captures the documented timing edge while fitting your capped-names format.

- **Evidence it’s real**: JFE 2018 (highly cited); strong in-sample \( R^2 \approx 1.6\% \) (first half-hour alone), up to 2.6% with 12th half-hour; OOS \( R^2 \approx 1.4\% \). Timing strategy (sign of first half-hour): ~6.7% annualized return, SR ≈ 1.08 (vs. buy-and-hold SR 0.29); mean-variance certainty-equivalent gains ~6% p.a. Survives realistic transaction costs/spreads post-decimalization (still positive ~4.5% p.a. net in tests). Stronger on high-vol, high-volume, recession, and macro-news days (e.g., FOMC). Replicated internationally (Li et al. 2022 and others) with similar patterns and economic value. Post-publication replications and extensions exist; not purely in-sample artifact.

- **Known failure modes / regime dependence / decay**: Stronger in high-vol/recession/news regimes; weaker or noisier in calm/low-volume periods. Modest \( R^2 \) means low power in low-signal environments. Potential attenuation from HFT/algos/competition (though replications post-2018 still find it). ETF-level (very liquid, low cost); scales well but is macro, not stock-specific alpha.

- **Fit grade**: **Minor adaptation**. Native for index/ETF timing (same-day long/short or long-only flat-when-negative; close at EOD). For your equity stock-ranking pipeline: use as market filter/overlay or broad-basket long (SPY or liquid names). Proxy first half-hour with your first 5-min bar + overnight (close enough for implementation; exact 10:00 signal is only ~25 min later). Fully mechanical, R-based, leak-free at 09:35 with allowed data.

**2. Intraday Cross-Sectional Patterns / Time-of-Day Momentum (Heston, Korajczyk & Sadka, JF 2010; extensions/replications in other markets)** — Academic, cross-sectional flavor, but more nuanced and lower-power for your exact same-day EOD-exit use case.

- **One-line mechanism**: Stocks exhibit persistent intraday return continuation at half-hour intervals that are exact multiples of a trading day (e.g., performance in a specific 30-min slot today predicts same slot on future days, persisting up to ~40 trading days). Short-term reversal components driven by temporary liquidity imbalances/bid-ask bounce (<1 hr); volume/order-imbalance/volatility/spreads show analogous patterns but do not fully explain returns. Reflects institutional flows/optimal trading timing.

- **Exact rule in your mold** (forced adaptation): At 09:35, rank stocks in your liquid universe by a rolling historical “slot strength” or average return in the remaining trading day (or early-day slots) over prior ~20–40 days (computable from your ~30 prior intraday sessions + dailies). Take top-N by this rank (or a simple first-5-min relative strength or lagged slot autocorrelation proxy). Enter long mechanical (market). Stop: ATR or fixed R-multiple. Target: partial scale-out at 1R or trail. Time-exit: flat by close. Cap N. Use only allowed data. This is a stretch to capture the documented multi-day slot autocorrelation in a single same-day trade.

- **Evidence**: JF 2010 (highly cited); striking cross-sectional predictability at lagged exact half-hour multiples. Replicated/extended in other markets. Economic magnitude modest (typical for intraday cross-section after costs).

- **Known failure modes**: Liquidity-driven components decay fast or reverse intraday; patterns may weaken with competition/HFT. Modest effect sizes; sensitive to exact timing/measurement of “slots.” Not a high-power same-day EOD strategy in backtests of similar ideas.

- **Fit grade**: **Forced**. Native for intraday timing or multi-day slot portfolios; your fixed 09:35 + same-day close + top-N ranking requires significant adaptation and likely dilutes the edge. Still leak-free and mechanical with your data.

**Honorable mention / skeptical practitioner candidate (do not rank highly)**: 5-min Opening Range Breakout (ORB) on “stocks in play” (Zarattini, Barbon & Aziz, 2024 SSRN/practitioner paper). Claims strong performance (high Sharpe/alpha on top-20 filtered names 2016–2023) for long breakouts above first-5-min high, with stops/targets/time exits. Fits your mold *natively* (ranking by “in play” score e.g. gap/rel-volume/news at 09:35; mechanical R; same-day). Mechanism: continuation in high-activity names. **But**: Recent practitioner analysis, limited academic citations/replications, focuses on volatile “in play” names (higher slippage/cost risk), no long post-publication track record. Classic ORB ideas have practitioner popularity but academic skepticism on robustness after costs/data-mining. Use only as robustness check, not primary positive control.

**Bottom line on real candidates**: Gao et al. is the strongest, most replicated documented edge that can be adapted with minimal violence to your constraints (especially as market filter or broad long-only equity timing). It is modest/robust, low-cost (liquid ETF or top liquid names), has clear mechanism, and has survived OOS/replications. Nothing in the literature gives you a high-confidence, purely cross-sectional stock-picking same-day long-only edge with the power and replication pedigree you want. Heston adds cross-sectional flavor but fits worse. ORB fits mechanically but lacks the “proven & replicated” bar.

### Hard Question 1: Do robustly-proven equity edges actually fit long-only same-day intraday?

**Largely no — the bulletproof ones live in regimes your framework structurally cannot express well.** 

- Classic cross-sectional momentum and short-term reversal: Profits overwhelmingly overnight (Lou, Polk & Skouras and follow-ups); intraday component is weaker or reversal/liquidity-driven.
- Value, profitability/quality, many anomalies: Accrue over multi-day or specific intraday windows but not reliably captured by a single 09:35 ranking + same-day close on liquid names.
- PEAD: Multi-day (often weeks) drift; same-day capture at 09:35 is only the initial reaction (if earnings pre-open), not the documented drift.
- Overnight/close-to-open premium and many calendar/institutional-flow effects: Require holding overnight or multi-day.
- High-frequency or order-flow edges: Require tick/microstructure data beyond your daily + ~30 intraday sessions + first 5-min bar.

Documented intraday effects that *do* exist (Gao-style index momentum, Heston-style slot patterns, liquidity reversals) are either index-level, very short-horizon/liquidity, or modest in economic magnitude after costs. Your mold (long-only, same-day close, fixed early decision, capped top-N ranking on liquid universe, strict leak-free data) is a **thin-edge regime**. Durable, replicable edges with enough power to survive combinatorial search + PBO + deflated-Sharpe + sealed year are rare or nonexistent there. This is probably the real finding explaining your pipeline’s rejections — not that the validator is broken, but that the target search space has low signal density. A validator that only ever rejects can still be correctly calibrated if the null is mostly true in that slice of design space.

### Hard Question 2: Synthetic positive control — yes, strongly recommend (primary or at least co-equal with any real one)

**Synthetic is cleaner, more rigorous, and better suited to validating *your validator’s detection power*** than hunting for a real-world control in a regime where few (or no) high-confidence edges exist.

**Arguments for synthetic (stronger here)**:
- **Exact ground truth + controlled calibration**: You inject a known, modest, leak-free predictive signal (e.g., a synthetic feature computable at 09:35 — first-5-min return interacted with a stock characteristic, or a seeded low-rank-correlation alpha added to returns). Vary strength (e.g., rank IC 0.03–0.10 or daily edge 0.2–1% on selected names) and run the full pipeline. See precisely at what power it passes combinatorial filter search, LOO walk-forward, PBO, deflated-Sharpe gate, and sealed 2025 year. This directly measures false-negative risk and sensitivity without ambiguity.
- Resolves identification problems of real edges: “Is Gao (or any candidate) still alive in *your exact* 2022–2025 liquid universe, costs, slippage, and implementation frictions? Was the original publication data-mined or regime-specific?” Synthetic eliminates that.
- Tests the *entire* pipeline fairly: Including whether it can detect modest/stable effects (your preferred) vs. only huge fragile ones.
- Reproducible and falsifiable: You control the injection; others can replicate the test.
- Complements any real control: Run Gao-adapted or Heston-adapted as an ecological/“real data” check alongside synthetics of varying strength.

**Arguments against (weaker in your case)**: A real edge has ecological validity (transaction costs, regime shifts, capacity, behavioral persistence are “real”). If you find/adapt one that passes, it’s more convincing to outsiders. But given the scarcity in your mold, this advantage is limited — and a failing real candidate leaves you uncertain (“edge gone or pipeline too strict?”).

**Recommendation**: Prioritize **synthetic positive control** as the primary validation of the validator. Design a family of injections (modest stable vs. stronger; pure ranking signal vs. with noise). Use Gao et al. (or your adaptation of it) as a secondary real-data benchmark for face validity. If even a well-calibrated synthetic modest edge dies in the pipeline, then the validator *is* overly conservative and needs loosening (e.g., on PBO threshold, deflated-Sharpe, or combinatorial search). If synthetics pass at realistic modest strengths but real candidates die, that confirms your framework is correctly identifying a low-edge-density regime.

This approach is more scientific and less frustrating than endless real-strategy hunting in a sparse space. If you describe your exact synthetic injection plan or pipeline gates in more detail, I can help refine a concrete test design.