# x04 — FF3 / Size-Factor Residual Momentum — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before scoring. Source: `strategies/xsec_momentum/backlog.md` (the last untested
x03 refinement; x03's own docstring earmarks "x04+: FF3 / size-factor residual"). Companions:
`multiday_x03_residmom_preregistration.md`, `multiday_betahedge_preregistration.md` (the beta-hedge
KILL — its lesson frames the expectation). **Narrow, pre-committed — do NOT widen.**

## Thesis (ex-ante) — and the exact question it settles

x03 ranks on the CAPM (market-only) residual momentum — it strips SPY beta from the ranking but still
carries β≈1.06–1.20 and a documented small-cap/value loading. A multi-factor residual (market + size +
value) strips those too, so the ranking is purer idiosyncratic momentum. **Honest prior (LOW):** the
beta-hedge kill established *"beta is load-bearing on this book — stripping it monotonically lowers
Sharpe."* FF3-residual is a softer version of that, so the likely outcome is a LOWER-beta, LOWER-Sharpe
variant, not an improvement. We run it to settle the last open question with evidence, not hope.

**Settles:** does residualizing momentum on size+value (beyond market) HOLD Sharpe while cutting beta
(a real improvement → adopt as the deployed ranking), or trade Sharpe for beta (a lower-beta variant
only), or do nothing? Either way the x03 ranking question is then fully closed.

## Construction (one lever: 3-factor residual instead of CAPM)

Identical to x03 except the residualization factor set: top-50 EW, monthly non-overlapping, H=20,
$5/$10M floor, 10 bps, SPLIT-adjusted bars, formation `[d−252, d−21]`, signal = mean(ε)/std(ε).

- **Factor set (pre-committed):** market = SPY; **SMB-proxy = IWM − SPY** (small minus big); **HML-proxy
  = IWD − IWF** (value minus growth) — daily split-adjusted ETF returns, observable (leak-safe).
- At rebalance d: regress each eligible name's daily return on `[1, SPY, SMB, HML]` over the formation
  window (shared residual-maker `M = I − X(XᵀX)⁻¹Xᵀ` applied to all names at once). Residual-momentum
  signal = mean(ε)/std(ε) over the window; rank DESC; long top 50 EW. Same eligibility/coverage rules
  as x03 (≥126 window obs).
- Reference arms: x03 (CAPM residual) + x01 (raw mom_12_1) recomputed on the SAME periods.

ETF-proxy caveat (documented, not a leak): IWM−SPY / IWD−IWF are *proxies* for academic SMB/HML, not
the Ken-French factors (which are long/short, breakpoint-constructed). They capture the bulk of the
size/value exposure for a residualization purpose; a clean FF factor series would be a later refinement.

## Windows, metrics, decision bar (pre-committed)

- Windows: clean **2022–2024** (primary) + **8yr 2017–2024** (secondary, survivorship-flagged). 2025
  sealed out.
- Metrics vs x03 on the SAME periods: annualized Sharpe, realized beta (expect LOWER), beta-adjusted
  alpha (intercept + t), max drawdown, DSR, corr to x03.
- **ADOPT FF3-residual as the deployed x03 ranking iff** (clean 2022–24, not contradicted on 8yr):
  1. **annualized Sharpe ≥ x03**, AND
  2. **realized beta materially lower than x03** (the point of the exercise), AND
  3. **beta-adjusted alpha ≥ x03** (cleaner edge, not just lower vol).

## Outcomes (pre-committed)

- **ADOPT** (clears 1–3): FF3-residual is a strictly better-engineered x03 → deploy it as the ranking.
- **LOWER-BETA VARIANT** (beta lower but Sharpe < x03): records a Sharpe-for-beta trade — keep x03
  (CAPM) as the deployed default; FF3-residual is an available lower-beta/lower-return option only.
- **NO-OP / REJECT** (no meaningful beta cut or worse on all axes): x03 CAPM residual is optimal; the
  ranking question is closed. (Confirms the beta-hedge lesson at the ranking level.)

## Sealed discipline

In-sample ONLY (both sealed years spent). Lock the factor set (SPY + IWM−SPY + IWD−IWF), formation
window, signal form, and bar in THIS file; any change is a new dated spec. Script:
`scripts/multiday_ff3resid.py`.

---

## RESULT (2026-06-18) — REJECT: extra factors inject noise; CAPM residual (x03) is optimal

`scripts/multiday_ff3resid.py`. FF3-residual is strictly WORSE than x03 on every axis, both windows —
and it FAILED its own stated goal (beta went UP, not down):

| window | scheme | annSh | β | α% | t(α) | maxDD | DSR |
|---|---|---|---|---|---|---|---|
| clean 2022–24 | x03 CAPM resid | **+0.77** | 1.06 | **+0.56** | +0.94 | −11.6% | 0.75 |
| clean 2022–24 | **x04 FF3 resid** | −0.10 | **1.14** | **−0.91** | **−2.22** | −27.6% | 0.21 |
| 8yr 2017–24 | x03 CAPM resid | **+0.88** | 1.08 | +0.57 | +1.16 | −22.6% | 0.97 |
| 8yr 2017–24 | x04 FF3 resid | +0.52 | 1.26 | −0.30 | −0.94 | −34.5% | 0.82 |

corr(FF3, x03) = +0.78. Adding size (IWM−SPY) + value (IWD−IWF) to the residualization did NOT lower
beta (1.06→1.14 clean, 1.08→1.26 8yr) and crushed Sharpe (+0.77→−0.10) and alpha (+0.56%→−0.91%, t
**−2.22** significantly negative). **Verdict: REJECT.** The ETF-proxy SMB/HML factors inject estimation
noise into the per-name formation-window regression (4 params on noisy proxies) that CORRUPTS the
residual-momentum signal more than it purifies — and they don't even achieve the lower-beta goal.
**CAPM single-factor (x03) is the sweet spot:** enough to strip dominant market exposure, not so many
params that the residual becomes noise. The x03 RANKING question is now fully closed — CAPM residual
momentum is optimal. (Caveat: ETF proxies ≠ clean Ken-French factors; a true FF series might behave
differently, but the magnitude of failure + the beta-went-up direction make that re-test low-value.)
