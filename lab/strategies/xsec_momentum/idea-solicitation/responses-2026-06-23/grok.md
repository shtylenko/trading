**8 novel, testable ideas to improve residual-momentum risk-adjusted returns**

I reviewed your full spec, including the exhaustive Section 7 dead-ends and the hard constraint that the *ranking/selection signal* is the only reliable lever. All proposals below are deliberately upstream refinements to how you compute or filter the residual IR scores (or a minimal hybrid gate), using only your existing daily price + SPY + point-in-time quarterly fundamentals data. None touch portfolio overlays, stops, timing, hedging, weighting schemes, or universe changes.

I ranked them by conviction (highest first) based on: (a) how cleanly they target a specific, unexploited weakness in the current equal-weighted residual IR, (b) structural distance from every entry in Section 7, and (c) ease + robustness of backtesting. Expected effect sizes are modest but potentially robust — think +0.05–0.12 Sharpe or equivalent drawdown compression if any one works — because you have already extracted most of the obvious edge. Prioritize the top 4 for the first research sprint.

### 1. Recency-weighted residual IR (EWMA)
**Idea:** Recency-weighted residual IR (EWMA version)

**Mechanism / thesis:** The current `mean(ε)/std(ε)` treats every day in the 252-day formation window as equally informative. Older stock-specific drifts have less predictive power once news has been incorporated or regimes have shifted. Replacing the equal-weighted moments with exponentially weighted ones (higher weight on recent residuals) produces a score that emphasizes *fresher* idiosyncratic momentum while the single-factor residualization against SPY continues to strip market beta.

**Closest dead-end it avoids:** “longer cadences” and “score definition variants (sum of residuals, residual t-stat, compounded residual return)”. Those alter total window length or the aggregation formula across the whole window; this keeps the exact same ~252-day (skip-21) window and only changes the *temporal weighting inside it*.

**Why it survives my failure modes:** Pure upstream change to residual-score calculation on the identical regression output. No new cross-sectional factor is added that could proxy beta or styles. Basket construction, equal weighting, and 20-day time exit remain untouched, so the low-beta / shallower-DD character of residual momentum is preserved or strengthened.

**How to test it:** Compute rolling EWMA mean and EWMA std of the residual series (e.g., half-life 40–80 trading days; one hyper-parameter to sweep). Form score = EWMA_mean(ε) / EWMA_std(ε). Run identical top-35 equal-weight monthly rebalance backtest. Data needed: daily prices + SPY only. Decisive metric: walk-forward Sharpe and max-DD vs baseline residual IR (target ≥ +0.05 Sharpe or ≥ 3–4 pp shallower DD at similar gross return).

**What would kill it:** Walk-forward Sharpe flat or lower; optimal half-life highly unstable across sub-periods; or correlation to plain total-return momentum rises above ~0.96.

### 2. Multi-horizon residual IR ensemble
**Idea:** Multi-horizon residual IR ensemble

**Mechanism / thesis:** A single 11-month formation window is noisy because of intra-window regime shifts or transitory stock-specific events. Computing residual IR on three complementary horizons (e.g., 63 d, 126 d, 252 d, all skipping the most recent 21 d) and ranking on the average (or rank-sum) of the three scores selects names whose *stock-specific* momentum is consistent across time scales. Each horizon is still fully residualized against SPY, so market beta remains stripped.

**Closest dead-end it avoids:** “longer cadences” (single longer window) and “overlapping portfolios (Jegadeesh-Titman style)”. Overlapping portfolios diversify *holding periods* across time; this diversifies *formation lookbacks at a single rebalance decision* to create a more robust ranking signal.

**Why it survives my failure modes:** Ensemble of residual-based scores only. No new primary factor, no change to position sizing, holding period, or any exit rule. The market-neutral character of each component carries through to the composite, avoiding the high-beta collapse pattern.

**How to test it:** For every stock/month compute three residual IRs (63 d, 126 d, 252 d skip-21). Composite = average of cross-sectionally z-scored IRs (or average rank). Select top 35 by composite. Full backtest vs single 252 d baseline. Data: daily prices + SPY. Decisive metric: walk-forward Sharpe + Calmar ratio; also check whether ensemble reduces performance dispersion across sub-periods.

**What would kill it:** Composite no better than the best single horizon (or worse); correlation to baseline residual momentum > 0.97 with no risk-adjusted gain; or horizon weights extremely unstable.

### 3. Equal-weighted liquid-universe factor residualization
**Idea:** Equal-weighted liquid-universe factor residualization

**Mechanism / thesis:** SPY is cap-weighted and mega-cap dominated. Your tradable universe (≥ $5, ≥ $10 M ADV) contains a broader mix of mid- and large-caps. Regressing on SPY therefore leaves some common “market” variation that is actually large-cap-specific inside the residuals. Replacing the single factor with the daily equal-weighted return of all currently eligible liquid stocks produces residuals that are orthogonal to the *average stock you can actually trade*, yielding cleaner stock-specific momentum scores.

**Closest dead-end it avoids:** “multi-factor (Fama-French 3-factor / size) residual momentum”. FF3 *adds* SMB and HML as extra regressors (and performed worse). This remains strictly single-factor but upgrades the definition of that one factor to a point-in-time, equal-weighted proxy matched to the exact investment universe.

**Why it survives my failure modes:** Still single-factor residual IR ranking. The only change is the market-proxy series used in the regression. No new style factors are introduced, so the low-beta property should be retained or improved. No portfolio-construction or overlay changes.

**How to test it:** Pre-compute (or rolling) daily equal-weighted return of all stocks meeting eligibility gates that day (lag universe definition by one day to avoid look-ahead). Regress each stock on this custom `r_EW` series instead of `r_SPY`, obtain new residuals and IR, then run identical top-35 strategy. Data: daily prices only (SPY optional for comparison). Decisive metric: strategy beta to SPY, Sharpe, and correlation to plain momentum vs baseline.

**What would kill it:** New strategy shows higher beta to SPY or materially worse risk-adjusted returns; or the custom `r_EW` series is > 0.95 correlated with SPY (little incremental information).

### 4. Low R² idiosyncratic-purity filter / adjustment
**Idea:** Low R² idiosyncratic-purity filter / adjustment

**Mechanism / thesis:** Some stocks with high residual IR still have high R² in the market regression — their returns remain largely systematic even after the adjustment. Their “momentum” score therefore partly reflects leveraged or correlated market exposure rather than pure stock-specific drift. Preferring or up-weighting names with *low R²* (truly idiosyncratic movers) inside the residual-mom ranking produces a basket whose selected momentum is more genuinely orthogonal to the market.

**Closest dead-end it avoids:** “risk-adjusted momentum (return/vol)” and “multi-factor residual momentum”. Risk-adjusted uses *total* volatility; multi-factor adds extra regressors. This uses the regression diagnostic R² itself (proportion of variance still explained by the single market factor) as a post-estimation quality filter or score modifier.

**Why it survives my failure modes:** Operates entirely inside the existing residual pipeline as a selection or scoring tweak based on how cleanly the market adjustment worked. Favors stocks where residuals capture more of the action → reinforces (does not undermine) the low-beta character. Pure ranking/selection change; no overlays.

**How to test it:** From each formation regression extract R². Options: (a) hard filter — rank residual IR only among stocks with R² < 0.25 (or below median), or (b) adjusted score = residual_IR × (1 − R²). Top-35 equal-weight backtest. Data: daily prices + SPY (R² already produced by the regression). Decisive metric: reduction in strategy beta to SPY or improvement in information ratio (α / residual vol); also full Sharpe and max DD.

**What would kill it:** Low-R² filter shrinks the candidate pool too much and hurts gross return without commensurate risk-adjusted gain; or adjusted scores increase correlation to plain momentum or worsen drawdowns.

### 5. Beta stability / precision filter
**Idea:** Beta stability / precision filter

**Mechanism / thesis:** The residual IR assumes a reliable β. Stocks with noisy or unstable β estimates (high standard error or large |β_first_half − β_second_half|) produce contaminated residuals and unreliable momentum rankings. Filtering or down-weighting such names before or within the top residual-IR ranking improves signal quality by keeping only stocks where the market adjustment itself is trustworthy.

**Closest dead-end it avoids:** “multi-factor residual momentum” and “risk-adjusted momentum (return/vol)”. This targets *reliability of the single CAPM β estimate* (regression diagnostics), not addition of extra factors or use of total risk.

**Why it survives my failure modes:** Refinement of which residual scores are trusted, using internal regression quality metrics. Avoids noisy-β names → cleaner low-beta portfolio. Selection step only; no sizing, timing, or exit changes.

**How to test it:** Run OLS, extract se(β) and/or split-window β stability metric. Filter top residual IR to names with stability above threshold, or adjusted_score = residual_IR × stability. Full backtest. Data: daily prices + SPY. Decisive metric: improved walk-forward consistency (lower performance dispersion across regimes) and/or higher Sharpe.

**What would kill it:** Filter too aggressive → excessive concentration or lower returns; or stability metric has no predictive power for out-of-sample performance.

### 6. Robust regression residual momentum (Theil-Sen)
**Idea:** Robust regression residual momentum (Theil-Sen)

**Mechanism / thesis:** Daily returns contain jumps and outliers that distort OLS β and therefore pollute the residuals used for scoring. Theil-Sen (median pairwise slope) is highly robust to outliers. Using it yields residuals that better reflect typical stock-specific drift, producing a ranking less contaminated by one-off events and potentially more persistent out-of-sample.

**Closest dead-end it avoids:** “path quality / frog-in-the-pan information-discreteness” and score-definition variants. Frog-in-pan operates on discreteness of the *raw* return path after OLS residuals are already formed. This changes the *market-model estimation step itself* before any scoring.

**Why it survives my failure modes:** Pure change in how residuals are generated inside the single-factor framework. Still produces residual IR ranking → preserves market adjustment and low beta. No new signal class or portfolio overlay.

**How to test it:** Replace OLS with Theil-Sen (or statsmodels RLM Huber) for each stock/month regression → obtain robust β and residuals → compute mean(res)/std(res). Identical top-35 backtest. Data: daily prices + SPY. Decisive metric: Sharpe and alpha t-stat improvement; check sensitivity to outlier days.

**What would kill it:** Negligible performance difference (outliers not first-order issue) or materially worse results; or computational cost becomes prohibitive for production (monthly is fine).

### 7. Residual autocorrelation persistence scorer
**Idea:** Residual autocorrelation persistence scorer

**Mechanism / thesis:** Current score captures *average level* of stock-specific drift but ignores whether that drift is serially persistent versus choppy or mean-reverting inside the formation window. Ranking (or blending) on lag-1 autocorrelation of the residual series identifies stocks where idiosyncratic returns show positive serial correlation — ongoing stock-specific momentum rather than a one-time shift — which may be more likely to continue.

**Closest dead-end it avoids:** “path quality / frog-in-the-pan information-discreteness”. Frog-in-pan measures continuity vs discreteness on *raw* returns. This measures *serial dependence specifically on the residual (market-stripped) series* and was never tested in residual space.

**Why it survives my failure modes:** New quantification of momentum applied directly to the idiosyncratic component. Positive residual autocorr is an idio property → unlikely to reintroduce systematic beta. Ranking-signal change only.

**How to test it:** Compute acf = corr(ε_t, ε_{t-1}) on the residual series. Blended score = residual_IR × max(0, acf) or simple z-score average of IR and acf. Top-35 backtest. Data: daily prices + SPY (full residual series needed). Decisive metric: improvement in subsequent realized residual returns or overall Sharpe; check reversal behavior of high-acf names.

**What would kill it:** Autocorrelation too noisy on ~230 observations (weak incremental signal); or high overlap with plain residual IR and no added value.

### 8. Low asset-growth sustainability gate
**Idea:** Low asset-growth sustainability gate

**Mechanism / thesis:** Among names with strong residual (stock-specific) momentum, those that have recently grown total assets aggressively are more likely to be over-investing high-beta growth stories whose momentum proves less sustainable. Gating the residual-mom basket to names with below-median (or negative) point-in-time YoY/QoQ asset growth selects “leaner” momentum names where the price drift is accompanied by more conservative capital allocation, potentially reducing exposure to momentum-crash reversals.

**Closest dead-end it avoids:** “quality / gross-profitability (Novy-Marx GP/Assets)”, “value (book-to-market, earnings-yield)”, and “earnings momentum (TTM net-income YoY)”. Those were used primarily as *standalone or primary ranking signals* and collapsed to high-beta tilts. This uses a distinct fundamental dimension (investment/asset growth) strictly as a *secondary binary or soft gate* applied *after* residual-mom ranking.

**Why it survives my failure modes:** Core ranking remains residual price momentum (already low beta). The gate is a slow-moving, point-in-time fundamental applied as a filter on an already market-adjusted universe. Because asset growth often loads neutrally or negatively on momentum names, it is less likely to flip the book into a high-beta tilt than using it as a primary signal. Selection refinement only.

**How to test it:** After computing residual IR, calculate asset_growth = (assets_t − assets_{t-4}) / assets_{t-4} (point-in-time). Select top residual-IR names that also satisfy asset_growth < cross-sectional median (or < 0). Or light blended rank. Full backtest. Data: daily prices + SPY + point-in-time quarterly total assets. Decisive metric: similar/higher return with lower max DD (especially in known momentum-reversal windows); check factor loadings.

**What would kill it:** Gate reduces gross return without offsetting DD or Sharpe improvement; or filtered basket shows higher beta or starts behaving like a value/quality tilt with negative alpha in some regimes.

### Summary triage table

| Idea | Mechanism class | Data needed | Cheap to test? | Conviction (H/M/L) | Closest dead-end avoided |
|------|------------------|-------------|----------------|--------------------|--------------------------|
| Recency-weighted residual IR (EWMA) | Signal refinement – temporal weighting of residuals | Daily prices + SPY | Yes | H | Longer cadences / score variants |
| Multi-horizon residual IR ensemble | Signal ensemble – multi-formation residual scores | Daily prices + SPY | Yes | H | Longer cadences / overlapping portfolios |
| Equal-weighted liquid-universe factor residualization | Signal refinement – custom single-factor proxy | Daily prices | Yes | H | Multi-factor (FF3/size) residual |
| Low R² idiosyncratic-purity filter | Selection filter – regression fit quality (R²) | Daily prices + SPY | Yes | H | Risk-adjusted mom / multi-factor residual |
| Beta stability / precision filter | Selection filter – beta estimate reliability | Daily prices + SPY | Yes | M | Multi-factor residual / risk-adjusted mom |
| Robust regression residual momentum (Theil-Sen) | Signal refinement – robust estimation of market model | Daily prices + SPY | Yes | M | Path quality / frog-in-pan / score variants |
| Residual autocorrelation persistence scorer | Signal refinement – serial correlation of residuals | Daily prices + SPY | Yes | M | Path quality / frog-in-pan |
| Low asset-growth sustainability gate | Hybrid selection – residual mom + fundamental investment gate | Daily prices + SPY + quarterly assets (PIT) | Yes | M | Quality / value / earnings momentum (as primary signals) |

**Implementation notes & research priority**  
All ideas are deliberately cheap (pandas + statsmodels/scipy per stock per month is trivial). Start with 1, 3, 4, and 5 — they require zero new data and are the cleanest extensions of your existing residual pipeline. Run them with the same walk-forward + held-out 2025/early-2026 protocol you already use. If any survives with a clean, regime-robust improvement, it is worth a deeper robustness sweep (parameter stability, sub-periods, transaction-cost sensitivity).

These are not guaranteed winners — they are the sharpest, non-overlapping angles I see given everything you have already ruled out. Happy to iterate on any that show promise in your first backtests or to help refine the exact implementation details (e.g., exact EWMA span, stability metric definition, or asset-growth calculation).