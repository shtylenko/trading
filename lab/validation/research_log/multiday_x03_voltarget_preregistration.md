# x03 + Vol-Target Sizing — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-17 before scoring. A portfolio-level sizing OVERLAY on the residual-momentum book
(x03), motivated by the leverage study: leverage was counterproductive on x01 because its vol/drawdown
were too high — but x03 cut beta (1.45→1.08) and drawdown (−36%→−23%), which may make modest sizing
productive. Companions: `multiday_x03_residmom_preregistration.md`, `multiday_leverage.py` (why static
leverage failed), the killed `multiday_x02_volscaled_preregistration.md` (V2 used the WRONG vol
estimator — mean-of-constituent-vols; this uses the STRATEGY's own realized vol, per the peer review).

## Thesis (ex-ante)

Barroso/Daniel risk-managed momentum: scale the whole book's exposure inversely to the *strategy's own*
recent realized volatility, so the book de-risks in turbulent regimes (where momentum crashes cluster)
and holds full size in calm ones. On x03 (already beta- and drawdown-reduced) this should shave the
residual drawdown further and, if it does so without surrendering much return, lift the Sharpe — the one
honest way the leverage study said more risk-adjusted return is reachable.

## Construction (one lever: a vol-target exposure multiplier)

Base = x03 per-period net returns `r_t` (residual momentum, top-50 EW, H=20, 10 bps). Overlay:

    exposure_t = min(L_max, σ_target / σ̂_t)          (residual capital in cash, 0 return)
    scaled_t   = exposure_t · r_t

- **σ̂_t = annualized realized vol of x03's OWN prior-K non-overlapping period returns** (K = 6,
  pre-committed), known at rebalance t → leak-safe. (NOT constituent vols — that was V2's error.)
- **σ_target = OPTION B:** mean of σ̂_t over the FIRST search year only, fixed forward (no look-ahead).
- **L_max ∈ {1.0, 1.5}** — the entire variant set:
  - **L_max = 1.0** ("defensive" / de-lever-only): never leveres above fully-invested; only cuts to
    cash when realized vol exceeds target. Pure crash defense — immune to the leverage-drag trap.
  - **L_max = 1.5** ("modest leverage"): allows up to 1.5× in calm regimes; 6% APR financing on the
    borrowed fraction. Tests whether x03's lower vol now makes modest leverage pay.

No grid over K, σ_target, or L_max beyond the two pre-committed caps.

## Windows, metrics, sealed discipline

- Windows: **8yr 2017–2024** (primary here — residual momentum needs 252d of prior daily returns, so
  the clean 2022–2025 parquet only yields ~2023–24; the 8yr gives the full, powered series) +
  clean-subset for color. 2025 hard-sealed out; 2026 never read.
- Metrics vs x03 unscaled: annualized Sharpe, CAGR, **max drawdown**, beta-to-SPY, beta-adjusted alpha
  (intercept + t), and average/min exposure (to confirm "modest").

## Decision bar (pre-committed)

A variant IMPROVES x03 only if, on the 8yr (and not contradicted on the clean subset):
1. **annualized Sharpe ≥ x03 unscaled**, AND
2. **max drawdown meaningfully shallower** (≥ ~15% relative reduction), AND
3. it does not depend on leverage drag (the L_max=1.5 case must also beat L_max=1.0 to justify the
   borrow + risk; otherwise the defensive 1.0 version wins on parsimony).

- **YES** → fold vol-targeting into x03 deployment as a sizing overlay (or ship as `x04` = x03 +
  defensive sizing); re-run drawdown/capacity with the overlay. Earmark a future sealed year.
- **NO** → x03 is deployed at constant 1.0×; record that even on the lower-vol residual book,
  vol-targeting does not add risk-adjusted value (sizing is a risk-tolerance choice, not alpha).
- In-sample ONLY (both sealed years spent). Lock K, σ_target rule, and L_max set here before scoring.

---

## RESULT (2026-06-17) — KILL: vol-targeting does not improve x03

Run `scripts/multiday_x03_voltarget.py`, 8yr, σ_target=18.6%/yr (2018-only, fixed), K=6. x03 unscaled
Sharpe +0.88/CAGR +19.2%/maxDD −22.6%. voltarget L=1.0: +0.79/+14.6%/−20.9% (drawdown only ~7% shallower
< 15% bar, Sharpe DROPS). L=1.5: +0.73/+14.7%/−24.9% (worse everywhere; leverage deepened DD). **Verdict:
KILL** — fails the bar (Sharpe must be ≥ unscaled; drawdown reduction marginal; L=1.5 < L=1.0). Cause: the
trailing-vol signal on sparse 20-day periods is LAGGY — de-risks after vol already spiked (near bottoms,
missing rebounds), diluting returns (avg exposure 0.83) without cleanly dodging crashes; x03's drawdown is
already moderate so little to cut. Consistent with prior regime-timing kills (timing fragile on this
strategy). **x03 deploys at constant 1.0×** (static leverage hurt x01; vol-target doesn't help x03 — both
ways settled). x03's lower drawdown is STRUCTURAL (from residualization), not from any sizing overlay.
