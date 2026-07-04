**Peer review — xsec_momentum 12-1**

You asked for adversarial, so start with the bruise: your "validated" edge is mostly a high-beta tilt running on data that was not clean until 2022. Everything else follows from that.

## 1) Methodology — where you are fooling yourself

**Weakest claim first: DSR 0.992 on 2017–2024.** That 8-year window is 5 years of a fixed, survivorship-limited universe plus 3 years of true PIT. You note it, then you still use the 8-year number to kill ideas. Survivorship lifts Sharpe by removing delisted losers from the eligible pool and from the rank denominator. The fact that fixing splits *raised* DSR from 0.94 to 0.97 is a red flag — cleaning data should usually hurt, not help, unless the original error was correlated with losers you were already missing.

Your gates are directionally right, but the implementation undercounts trials:
- DSR corrects for selection bias and non-normality, but you feed it ~29 conditioning combos. The true trial count includes H=5, H=20, vol-scaling V1/V2, leverage grids, beta-hedge grids, defensive sleeves, and the diversifiers you mention. That's >100 correlated tests. DSR≥0.95 with the real N would be far lower.
- PBO via CSCV measures how often in-sample winners underperform out-of-sample. You report PBO 0.24 after cleaning. With only 29 highly correlated variants, CSCV has little variation to split — PBO is mechanically optimistic. It is not a green light.

**Cross-sectional premium is not a clean alpha test.** You compute top-50 net minus eligible-universe gross. Two problems:
1. Costs are asymmetric (you subtract costs only from the long leg).
2. You do not beta-adjust. Your book beta ≈1.4. In 2025, subtracting a 1.0-beta universe leaves ~0.4 beta embedded in the "premium." A real test is: alpha = r_long – β_hat * r_SPY, where β_hat is trailing 252-day regression of the strategy on SPY, computed PIT.

**Cost realism.** You assume 10 bps round-trip, then claim effective 3 bps because names persist. With liquid_pit ($10M 20-day dollar volume), a $48M book puts ~$960k per name. Trading 15 names per rebalance is ~15% of ADV on the low end of your universe. Real all-in (spread + impact + fees) is 15–30 bps one-way for those names, not 1.5 bps. Your 2022–2024 Sharpe ~0.50 would be ~0.30–0.35 after realistic costs.

**Other look-ahead risks you haven't closed:**
- Universe filter timing: ensure $5 price and $10M volume are computed on data through d-21, not d. Otherwise you peek into the skip month.
- Delisting returns: split-adjusted bars fix splits, but CRSP delisting returns (-30% to -100%) must be applied on the exit date. If missing, your 2021–22 crash is understated.
- Corporate actions beyond splits (special dividends, spin-offs) still distort 252-day returns if not total-return adjusted.

**LOO-WF 7/8 positive sounds strong, but 2022 is the tell.** A momentum strategy that fails the one true bear in sample is not regime-robust. Your sealed 2025 (+3.98% per period, Sharpe 1.08) is one year, one market regime — strong bull, low vol. It does not validate crash behavior.

## 2) Did you discard prematurely?

**(a) Vol-scaling — yes, you killed the wrong version.** Barroso-Santa Clara scaling works for long-short because it cuts both legs in high-vol months. For long-only, inverse-vol *weights* punish the high-vol winners that drive returns — exactly what you saw in 2020. That does not mean vol management is dead.

Try this instead, pre-registerable:
- Keep equal-weight stock selection.
- Scale *portfolio* exposure, not stock weights: target_vol = 15% annualized. Compute realized vol of x01 returns over prior 63 trading days (slow). Next-period exposure = min(1, target_vol / realized_vol). Never lever above 1. Use SH (inverse S&P ETF) for the residual cash when scaling down. This preserves winners, only de-levers in 2022-type regimes.

Also test idiosyncratic-vol scaling: rank by mom_12_1, then weight by 1/σ_idio where σ_idio is residual vol from FF3 regression. This keeps beta exposure but avoids lottery stocks.

**(b) Beta-hedge — static hedge was correctly killed, dynamic deserves one test.** Always-on β=1 hedge turns a beta-tilt into a thin residual (Sharpe 0.2–0.45). That's expected. What you haven't tested: hedge only in left-tail regimes, using the inverse-ETF toolkit you allow.

Pre-register: at rebalance, if SPY mom_12_1 < 0 *and* VIX > 25, hold 50% x01 + 50% SH. Otherwise 100% x01. This is two predicates, not a grid, and directly targets momentum crashes which cluster when market trend is down.

**(c) Conditioning — you likely killed it with contaminated data.** Your low-vol conditioner hit DSR ~0.97 in the clean 2022–2024 window, then collapsed when pooled with 2017–2021 survivorship data. That is exactly what happens when a real conditioner works in PIT data but looks average in a biased backtest. Do not discard. Re-test calm_vol *only* on 2022+ PIT, with a single pre-registered rule: eligible if 63-day realized vol < universe median at d-21.

## 3) New constructions that fit your constraints

All are long-only, daily bars, monthly rebalance, testable in your pipeline. I give leak-safe definitions, not code.

### 1. Residual (idiosyncratic) momentum
- **Rationale:** Blitz et al. show raw 12-1 has time-varying factor exposure; sorting on FF3 residuals halves volatility and doubles Sharpe from 0.45 to 0.90.
- **Definition:** For each stock at d-21, regress excess returns on MKT/SMB/HML over prior 756 days (min 126 obs). Compute residual return over t-252 to t-21 as sum of ε_t. Rank descending, long top 50 equal-weight.
- **Why orthogonal:** Removes market beta by construction, directly attacks your 1.4 beta problem.
- **Expect to fail:** In strong beta-driven bulls (2020–21, 2025), residual will lag raw momentum because you strip the beta premium.

### 2. 52-week high proximity
- **Rationale:** George-Hwang find price-level proximity to 52-week high predicts returns beyond past returns, driven by anchoring.
- **Definition:** proximity = close(d-21) / max(close[d-252:d-21]). Rank top 50.
- **Why orthogonal:** Correlation with 12-1 ~0.6–0.7 in US data, captures different behavioral bias.
- **Expect to fail:** During sharp V-recoveries, laggards far from highs rebound faster.

### 3. Frog-in-the-pan (information discreteness)
- **Rationale:** Da, Gurun, Warachka show investors underreact to continuous small news; momentum is stronger for stocks with smooth paths.
- **Definition:** ID = proportion of days in past 252 where |ret| > 90th percentile of that stock's absolute daily returns. Select stocks in top quintile of mom_12_1 *and* bottom tercile of ID. Hold 50 names.
- **Why orthogonal:** Filters out lottery-type winners that cause crashes, without changing the momentum signal.
- **Expect to fail:** In news-driven markets (earnings seasons), discrete jumps are real alpha.

### 4. Risk-adjusted momentum (not vol-weighting)
- **Definition:** score = mom_12_1 / σ_252 where σ_252 is realized vol from d-252 to d-21. Rank top 50 equal-weight.
- **Why orthogonal:** Selects smooth winners ex-ante, avoids post-selection down-weighting that killed your V1.
- **Expect to fail:** In low-vol grinds, score converges to raw momentum.

### 5. Quality-profitability blend
- **Rationale:** Novy-Marx gross profitability is negatively correlated with high-beta junk momentum, and is PIT-available quarterly.
- **Definition:** At rebalance, compute GP = (Revenue – COGS) / Assets from latest filing lagged 63 days. Rank momentum and GP separately, composite = 0.7*rank_mom + 0.3*rank_GP. Long top 50.
- **Why orthogonal:** Adds a fundamental anchor that held up in 2022.
- **Expect to fail:** In speculative rallies where unprofitable high-beta names lead.

### 6. Dual momentum filter using inverse ETF
- **Definition:** Compute SPY mom_12_1 at d-21. If <0, allocate 50% capital to x01 (top 25 names) and 50% to SH. If ≥0, 100% x01.
- **Why fits constraints:** Uses only long positions and an allowed inverse-index ETF, no single-name short.
- **Expect to fail:** Whipsaw in 2015–16 and 2018; you trade some upside for crash mitigation.

All six can be pre-registered with one parameter set each. Run them through your exact pipeline: LOO-WF on 2022–2024 PIT only first (do not mix pre-2022), then if DSR≥0.95, spend *one* sealed year — not six.

## 4) Bottom line

**Bank x01 as-is for now, but do not call it alpha.** It is a tradable, beta-heavy momentum tilt with realistic Sharpe ~0.5–0.7 after costs, not 0.88. Your sealed 2025 confirms it works in a bull, not that it survives a crash.

**Do not spend sealed years on marginal tweaks to 12-1.** Vol-scaling, static hedges, and k≤2 conditioning grids are unlikely to raise risk-adjusted return because they fight the very beta that generates your return.

**The only path to higher Sharpe within long-only is to reduce beta without killing return.** That points to residual momentum, 52-week high, and frog-in-the-pan — all shown to lower factor exposure and crash risk. Test those three on clean PIT data only, with realistic costs (20 bps one-way minimum), delisting returns, and proper trial-count for DSR.

If none pass DSR≥0.95 on 2022+ data, accept that your edge is modest and focus on execution: capacity limits at $48M, borrow costs for SH, tax efficiency of monthly rebalancing, and preparing the second sealed confirmation. Hunting further signals without fixing survivorship and cost assumptions is just overfitting with better math.