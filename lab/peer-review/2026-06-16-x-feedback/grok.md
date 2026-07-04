**Weakest claim first (methodology + conclusions):** The sealed-OOS 2025 result (+3.98% per period net, ann Sharpe +1.08, cross-sectional premium +2.78%) is genuinely encouraging as your *first* one-shot sealed pass, and the cross-sectional premium construction (top-50 net minus eligible-universe gross) is a clean way to isolate the momentum tilt from raw beta/market. However, it rests on roughly 12–15 non-overlapping 20-day periods in a single realization. One favorable year does not yet make the edge “structural” vs. a lucky high-beta tilt in a momentum-friendly regime. The 2026-H1 partial (~5 effective periods, known suspected-artifact window) is supportive-at-best and correctly treated as non-decisive. Pre-2022 survivorship lift in the 8yr in-sample is real but you already mitigated it via split-adjusted bars (which *strengthened* the edge) + clean PIT OOS. Still, early folds carry some residual look-ahead flavor on delistings/universe composition.

Your gates (LOO-WF → PBO/CSCV → DSR ≥ 0.95 → one-shot sealed) are appropriately brutal and correctly conservative for a solo researcher with a depleting sealed-year budget. The four kills are mostly sound: simple k≤2 conditioning collapsed on the long sample (noise or regime-specific only); static beta-hedge monotonically destroyed Sharpe because your alpha *is* partly beta-load-bearing; leverage at realistic Sharpe levels is a bad idea (vol drag + financing); H=5 failed 2022 even gross. Where you are most likely fooling yourself in the *false-kill* direction is vol-scaling (x02) and, to a lesser extent, conditioning—your implementations were reasonable but not exhaustive of the literature variants that matter for long-only.

**Did we discard anything prematurely?**

- **Vol-scaling / risk-managed (x02)**: Partially yes. Your V1 (stock-level inverse-vol weights on the top-50) predictably hurt because long-only momentum winners *are* the high-vol names that drive the premium; penalizing them is self-defeating in a long-only book. V2 (constant-target-vol exposure scaling) is closer to Barroso & Santa-Clara (2015) but appears to have been implemented in a way that did not improve the 8yr sample. For *long-short* momentum the gains from portfolio-level volatility targeting (scale whole-strategy exposure by target_vol / realized_vol_of_the_momentum_portfolio_over_prior_6m or 63–126d) are large because it directly attacks the severe crashes. For long-only the crashes are milder (you correctly note this), so the upside is smaller—but it can still trim max DD without killing too much of the bull-market capture if the target is set conservatively (e.g., your natural portfolio vol). Re-test a clean portfolio-level version (exposure scaled at each rebalance or monthly, using only the *strategy’s own* past realized returns, no stock-level) before fully killing it. It is risk-management, not alpha-chasing, and survives your pipeline easily.

- **Beta-hedge**: Not prematurely killed. Static partial or full hedging monotonically lowered Sharpe; the residual market-orthogonal component is too thin. Dynamic/partial/tail-regime or sector hedges would almost certainly add estimation noise, whipsaw, or complexity that violates capacity and anti-overfit discipline for modest AUM. Inverse-ETF or put overlays are available to you but are costly insurance that usually fails to improve risk-adjusted returns net of premium decay.

- **Conditioning grid (k≤2)**: Not prematurely killed for the *simple predicates* you tested (liquidity/price/vol floors, multi-horizon confirmation, not-overextended, momentum floor, SPY-200d regime). The exhaustive collapse to base on the 8yr sample is evidence those are mostly noise or unstable. However, you did *not* test more structured behavioral constructions such as Frog-in-the-Pan path quality or residual-momentum ranking—these are not simple “k≤2 predicates” and deserve separate pre-registered narrow searches.

**New signals / constructions worth pre-registering and testing (prioritized, within constraints)**

All are long-only, US equity daily bars, multi-day holds, rebalance every 20 trading days non-overlapping, same `liquid_pit` universe, same costs, fully PIT, and narrow enough to pre-register (exact formula, windows, ranking method) then run through your full pipeline (broad capture → narrow pre-reg → LOO-WF → PBO → DSR → one-shot sealed). I only propose things with credible economic rationale from the literature that are plausibly *more orthogonal* to raw 12-1 total-return momentum than the things you already killed.

**1. Highest priority — Residual / idiosyncratic momentum ranking (`x03_resid_mom` or blended with x01)**  
Economic rationale: Conventional 12-1 momentum loads on time-varying systematic exposures (especially beta after strong markets), which produces the well-documented crashes on rebounds. Residual momentum (Blitz, Huij & Martens 2011; Blitz et al. 2020) first strips common-factor returns via rolling regression, then ranks on the *residual* series. It delivers comparable gross returns to total-return momentum but with roughly half the volatility, materially higher Sharpe, far lower crash exposure, and less long-term reversal—because it isolates firm-specific underreaction rather than factor bets. For your documented beta≈1.4 book this is the single most promising way to reduce systematic load *without* hedging (which you correctly showed kills the edge).

Orthogonality: Lower correlation to raw momentum and to the market; the long leg should exhibit lower portfolio beta and milder drawdowns while preserving a genuine cross-sectional tilt.

Leak-safe definition (pre-register exactly these):
- At each rebalance date *d*, for every eligible name with sufficient history:
  - Run rolling OLS over the prior *N* trading days (pre-register *N* = 126 or 252; require ≥ *N*/2 observations):  
    \[
    r_{i,t} = \alpha_i + \beta_i \cdot r_{\text{SPY},t} + \epsilon_{i,t} \quad (t = d-N \dots d-1)
    \]
    (Start with single-factor CAPM for simplicity and data parsimony; FF3 only if you have clean daily PIT factor series.)
  - Compute the residual momentum signal on the residual series, e.g.:
    \[
    \text{mom_resid}_{12\_1,i} = \frac{\sum_{k=22}^{252} \epsilon_{i,d-k}}{231} \quad \text{or} \quad \text{product form or standardized by } \sigma(\epsilon)
    \]
    (Pre-register exact aggregation and any standardization.)
- Rank all eligible names by this signal; long top 50 equal-weight (or test value-weight as robustness).
- Same 20-day hold, rebalance, costs as x01.

Expected failure mode: If your edge is *primarily* a high-beta momentum tilt in certain regimes, residual ranking will dilute the premium and produce lower DSR / sealed Sharpe than base x01. Daily residual estimation adds noise (especially shorter windows). On your strict pipeline this is the one idea worth burning a sealed year on—high ex-ante motivation, directly attacks your documented weakness, and is implementable with only the bars you already have.

**2. Frog-in-the-Pan (continuous information path quality) as filter or composite rank**  
Economic rationale (Da, Gurun & Warachka): Momentum is stronger when information arrives continuously in small increments (investor inattention / underreaction) than in discrete jumps. The “frog in the pan” effect is a distinct behavioral channel from raw past return.

Orthogonality: Adds a *path-quality* dimension orthogonal to level of cumulative return; selects smoother trends that may be less reversal-prone.

Leak-safe definition (pre-register):
- Over the formation window (d-22 to d-252), compute a simple information-discreteness proxy, e.g.:
  - ID = sgn(PRET) × (% negative days − % positive days), or
  - Continuity = |PRET| / Σ |daily r| (lower = more continuous).
- Then either (a) double-sort / filter: among top mom names, prefer low-ID (continuous), or (b) composite rank = rank(mom_12_1) + w × rank(continuity) with small w pre-registered.
- Long top 50 by the chosen rule.

Expected failure mode: Your existing conditioning grid already showed that simple path/confirmation filters add noise on the long sample. This is more structured but still risks collapsing to base or failing DSR. Worth testing only if you have spare pre-reg bandwidth; low incremental expectation.

**3. 52-week high proximity (George & Hwang 2004) as complementary or replacement signal**  
Economic rationale: Investors anchor on the 52-week high; stocks near it continue to outperform as positive information is not fully incorporated.

Orthogonality: Behavioral anchor effect that is empirically distinct from (and often stronger than) raw past-return momentum in many tests.

Leak-safe definition: Signal = close_d / max(high over d-252 … d-1), or distance to high. Rank high proximity (or blended rank with mom_12_1). Same top-50 EW.

Expected failure mode: Likely subsumed by your existing mom_12_1 (the 12-month window already embeds proximity to highs). Recent implementations sometimes show weak incremental value after costs. Easy to test but low conviction for material improvement.

**Lower-priority / quick mentions (probably not worth sealed-year spend):**
- Pure risk-adjusted momentum (mom_12_1 / formation-period realized vol) — similar spirit to your killed V1 but on the *signal*.
- Revisit of clean portfolio-level vol targeting (as discussed above) — more risk overlay than new alpha.
- Nothing on new crash/drawdown timing overlays (your regime-timing kills were correct; for long-only the drawdown is largely the price of the premium, and cheap robust hedges are scarce).

**Bottom line**  
Bank **x01 as-is** (option b) and shift focus to execution realism, realistic cost modeling (your ~3 bps effective one-way is already sensible), capacity stress-testing at $48M AUM, live monitoring with the pre-registered 2026 confirmation, and a second gated sealed year when the budget allows.  

The four improvements you killed were the obvious low-hanging fruit; most “better momentum” ideas in the literature are either long-short-specific, overfit-prone, or add complexity that will not survive your pipeline. Residual momentum (`x03`) is the single exception worth a narrow pre-registered test because it theoretically fixes the exact weakness you documented (beta load) without requiring shorts or costly overlays. Everything else is likely to be noise or marginal at best. Your edge is modest, beta-heavy, and real within the harsh validation you applied—treat it as such rather than chasing incremental alpha that risks false discovery and depletes your sealed-year resource. Simplicity and robustness are features here, not bugs.