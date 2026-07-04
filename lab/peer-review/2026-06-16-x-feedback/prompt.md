# Peer review — `xsec_momentum` (12-1 cross-sectional momentum): signals tested, conclusions, and what's next

You are an adversarial quant reviewer. We have a **long-only, US-equity, multi-day** trading
strategy that has passed our full validation pipeline and is the project's first validated edge.
We have since tried four ways to *improve its profitability* and discarded all four. We want you
to (1) stress-test our methodology and conclusions, (2) tell us if we discarded anything
prematurely, and (3) propose **other signals / constructions we have not tried** that could
plausibly improve risk-adjusted profitability **within our hard constraints**. Be specific and
skeptical — a clean "your edge is what it is, here's why your new ideas won't beat it" is more
useful than optimism.

## Hard constraints (do not propose anything that violates these)

- **Long-only. The trader CANNOT short** (no single-name shorts; the only "short" available is
  buying inverse-index ETFs or index puts).
- **US equities, daily bars.** Multi-day holds (~weeks), not intraday. Monthly-ish rebalance.
- **Point-in-time `liquid_pit` universe** (~2,000 names/year; close ≥ $5, 20-day $-volume ≥ $10M).
- **Anti-overfitting discipline is non-negotiable.** Every idea must survive: broad feature
  capture → pre-registered narrow search → leave-one-year-out walk-forward → PBO (CSCV) →
  Deflated Sharpe (DSR ≥ 0.95) → a *pre-registered, one-shot* sealed-OOS year. We spend sealed
  years sparingly (a shared, depleting resource). Proposals should be testable in this pipeline.
- Solo researcher, modest capital; realistic capacity matters (our book caps ~\$48M AUM).

## The validated edge (baseline — `x01`)

**Rule:** each rebalance (every 20 trading days, non-overlapping), rank eligible names by
`mom_12_1 = close(d−21)/close(d−252) − 1` (12-month return, skip the most recent month), go long
the **top 50 equal-weight**, hold **20 trading days**, 10 bps round-trip cost. UNCONDITIONED.

**Evidence it is real:**
- In-sample 8yr (2017–2024, pre-2022 survivorship-limited): DSR **0.992**, pooled non-overlapping
  t **+2.49**, ann Sharpe **+0.88**, positive in 7/8 leave-one-year-out folds.
- Survivorship-CLEAN 2022–2024 (true PIT): weaker but positive — base equal-weight ann Sharpe
  **~+0.50**, DSR ~0.76; a low-vol-conditioned variant reached DSR ~0.97 (see "discarded" #1).
- Sealed-OOS **2025** (one shot, pre-registered): per-period net **+3.98%**, ann Sharpe **+1.08**,
  **cross-sectional premium +2.78%** (top-50 net − eligible-universe gross → a genuine momentum
  tilt, NOT just 2025 market beta). First sealed-OOS pass in the project.
- Independent re-implementation + the real backtest engine reproduce it (same sign + magnitude).
- A **2026-H1 early partial confirmation** is running now (pre-registered; ~5 effective periods,
  so supportive-at-best; this window is a known "suspected-artifact" period, so the cross-sectional
  premium is a *gating* qualifier there).

**Honest characterization:** a **modest, beta-heavy momentum tilt.** Book beta to SPY ≈ **1.4**
(corr ~0.70). Realistic deployable: ann Sharpe ~**0.7–0.9**, max drawdown **−25% to −38%**,
realistic CAGR **~11–25%** (a 2025 backtest showed +58% but that is an upside-tail year). Turnover
~30% one-way (names persist → real cost ~3 bps/rebalance, not the 10 bps headline). Intrinsic
momentum-crash risk (2021–22).

### Important data-integrity note (already fixed)
The whole pipeline originally used **raw (unadjusted)** daily bars — correct for the intraday
engine but WRONG for multi-day holds: a stock split inside the 252-day lookback corrupts the rank,
and a hold spanning a split books a phantom return (e.g. a 6:1 split showed as a fake −86% / −8.6R
loss). We switched the multi-day path to **split-adjusted** bars. Re-running clean *strengthened*
the edge (DSR 0.94→0.97, PBO 0.48→0.24, WF pick became stable) — the contamination had biased
*against* the strategy. All results above are on clean split-adjusted data. **If you see a similar
latent data issue we've missed, flag it.**

## What we tried to improve profitability — and DISCARDED (challenge these)

All four were pre-registered and tested on the clean split-adjusted ledgers; all failed to beat
plain equal-weight `x01`. We may be wrong — push back if so.

1. **Signal conditioning grid (k≤2 predicates):** liquidity, price floor, low-vol (`calm_vol`),
   multi-horizon confirmation (mom_6_1/mom_3_1 ≥ 0), not-overextended (1-month reversal cap),
   momentum floor, SPY-200d regime overlay. On 3yr a low-vol-conditioned combo looked best
   (DSR 0.97) but on the 8yr sample all ~29 combos collapse to ≈ the base (PBO ~0.92). Regime
   overlay *hurt*. **Conclusion: conditioning is noise; base unconditioned momentum is the edge.**
2. **Vol-scaling / risk-managed momentum (Barroso/Daniel), as `x02`:** V1 inverse-vol weights
   (w ∝ 1/σ), V2 constant-target-vol exposure scaling. 3yr V1 looked better (Sharpe +0.68 vs +0.50,
   fixed the 2022 bear) but on 8yr it vanished (base +0.88, V1 +0.85, V2 +0.89 — indistinguishable);
   V1 even trails base in the 2020 momentum boom (down-weights the high-vol winners that drive
   long-only returns). **Conclusion: vol-scaling helps long/short momentum, not long-only. KILLED.**
3. **Leverage / sizing:** at the realistic Sharpe (~0.5) leverage *reduces* CAGR (vol drag +
   financing: +10.9%→+6.8% from 1.0×→2.0× while max DD −24%→−54%); at the optimistic Sharpe (~0.9)
   it adds return but drawdowns go unholdable (−58% at 1.5×, −73% at 2.0×). **Conclusion: run at
   ~1.0×; leverage only pays after Sharpe rises or drawdown falls.**
4. **Beta-hedge (synthetic short via inverse-S&P ETF / puts):** long book − β·SPY for β∈{0,0.5,1,1.3}.
   Hedging monotonically *lowers* Sharpe on both windows (8yr 0.88→0.78→0.60→0.45); drawdown
   improves <25%. The book's β≈1.4 means it's largely a high-beta tilt and the market-orthogonal
   alpha that survives a full hedge is thin (residual Sharpe ~0.2–0.45). **Conclusion: market beta
   is load-bearing; the alpha is too thin to stand alone. KILLED.**

Also previously discarded: **H=5** (fails the 2022 bear even gross — only H=20 works); **long-only
diversifiers** (low-vol, short-term reversal, near-low, short-momentum — all positively correlated
with momentum via shared market beta, none smooth the book); **defensive-sleeve rotation** to
cash/TLT/GLD on SPY<200d (every rotation *lowered* Sharpe and *deepened* drawdown — whipsaw, and
TLT failed as a hedge in 2022). **Long/short** (D10–D1 Sharpe 0.71–0.89, the genuine higher ceiling)
is OFF the table — cannot short.

## What we want from you

1. **Methodology critique.** Are our gates (LOO-WF, PBO/CSCV, DSR≥0.95, one-shot sealed year) and
   our kills sound? Where are we most likely fooling ourselves — in *either* direction (a false
   kill of a real improvement, or false confidence in the base edge)? Is treating the cross-sectional
   premium as the "is it alpha vs beta" discriminator valid? Any look-ahead/survivorship/cost
   subtleties we've underweighted (esp. the pre-2022 fixed-universe survivorship lift)?

2. **Did we discard anything prematurely?** Especially: (a) does vol-scaling deserve another form
   (e.g. scaling the *whole portfolio's* realized vol with a longer estimator, or only in the worst
   regimes)? (b) is there a beta-hedge construction that would actually help (partial/dynamic β,
   sector hedges, hedging only tail regimes)? (c) is conditioning truly dead, or did the k≤2 grid +
   8yr survivorship confound hide a real conditioner?

3. **New signals / constructions to improve profitability — the main ask.** Within the hard
   constraints (long-only, US equity, daily, multi-day, testable in our pipeline), what would you
   try to raise risk-adjusted return or cut drawdown? Concretely, e.g.:
   - Better momentum formations (residual/idiosyncratic momentum vs CAPM/FF residuals; 52-week-high
     proximity done right; "frog-in-the-pan" path-quality/information-discreteness; time-series vs
     cross-sectional; dual momentum; risk-adjusted momentum).
   - Complementary long-only factors with genuinely *low* momentum correlation that could blend
     (quality/profitability, low-beta done as a sizing not a sleeve, seasonality, post-earnings-drift).
   - Crash/drawdown management that survives walk-forward (we've found regime timing fragile —
     is there a robust version, or is drawdown just the price of the premium?).
   - Anything that exploits the long-only + inverse-ETF toolkit we *do* have.
   For each: the economic rationale, why it should be *orthogonal* to plain 12-1 momentum (not just
   re-packaged beta), the leak-safe feature definition, and how you'd expect it to fail.

4. **Bottom line.** Given all the above, is the right move to (a) keep hunting signal alpha,
   (b) bank x01 as-is and focus on execution/cost realism + the sealed 2nd confirmation, or
   (c) something else? Argue it.

## Deliverable

Prioritized, specific, adversarial. Call out our weakest claim first. For any proposed signal,
give us enough to pre-register and test it in one pass. Reference our findings docs
(`validation/multiday_momentum_findings.md`, the `*_preregistration.md` specs) if useful.
