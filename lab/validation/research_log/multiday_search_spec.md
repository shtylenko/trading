# Multi-Day Momentum Search — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-16 BEFORE scoring (EXPLORATION_PLAYBOOK §3: capture broad / lock
search narrow). Companions: `multiday_momentum_findings.md` (Stage 0),
`scripts/capture_multiday.py` (ledger), `scripts/multiday_search.py`. Do NOT widen
this grid in reaction to results.

## Thesis

Stage 0 showed 12-1 cross-sectional momentum is a clean, monotone, every-year-positive
signal (decile monotonicity +0.96/+0.90). The strategy: each rebalance, hold the
top-N highest-12-1-momentum names, equal weight, for H trading days. The search asks
whether CONDITIONING that book (liquidity, price, volatility, momentum-confirmation,
not-overextended, market regime) produces a robust net edge that clears the gates.

## Structure (fixed, not searched)

- Ranking score = `mom_12_1` (the Stage-0 winner). Deployment cap = top-N by score.
- Rebalance NON-OVERLAPPING every H trading days (independent periods → honest
  Sharpe; PBO/DSR computed per-period). Horizons tested: **H = 5 (primary, 151
  periods) and H = 20 (secondary, 38 periods — small, read with caution)**.
- Outcome per name-period = forward H-day return MINUS a round-trip cost charged per
  held name per rebalance (`--cost-bps`, default 10 bps; conservatively assumes ~full
  turnover — a name retained in the book isn't really re-traded, so this is an upper
  bound on cost).
- Objective / arbiter / gates: reused verbatim from feature_search — daily-portfolio
  IR objective, leave-one-year-out walk-forward, PBO (CSCV+embargo), Deflated Sharpe
  (DSR ≥ 0.95). 2025 SEALED.

## Pre-registered minimum effect size

Momentum is a slow signal; the long-only top-decile Stage-0 Sharpe was modest
(~0.55–0.62 gross). A PASS must clear WF + PBO + DSR ≥ 0.95 NET of the 10 bps cost.
Because the cost is small relative to H-day moves (unlike overnight), the binding gate
will be DSR (selection-bias) and the small-sample WF, not cost.

## The grid (LOCKED, k ≤ 2) — conditioning predicates on the top-N momentum book

| Predicate | Feature | Cut | Rationale |
|---|---|---|---|
| liquid_50m | dollar_vol_20d | ≥ $50M | tradeable, lower-impact names |
| price_min_10 | log_close | ≥ ln(10) | ≥ $10 (avoid low-price noise) |
| calm_vol | vol_20d | ≤ 4%/day | momentum is stronger among lower-vol names (avoid lottery/reversal) |
| confirm_6_1 | mom_6_1 | ≥ 0 | 6-month momentum also positive (multi-horizon confirmation) |
| confirm_3_1 | mom_3_1 | ≥ 0 | 3-month momentum also positive (faster confirmation) |
| not_overextended | rev_1m | ≤ 0.20 | exclude names already +20% in the last month (1-month reversal risk) |
| mom_floor | mom_12_1 | ≥ 0 | only genuine winners (positive 12-1) enter the book |

Same-feature pairs excluded by the enumerator. mom_12_1 appears both as the ranking
score AND as the `mom_floor` predicate (a floor on the ranked variable — allowed,
analogous to feature_search's gap floor+ceiling band).

## Regime overlay (NOT a searched predicate)

`spy_above_200d` applied as a fixed CAPITAL OVERLAY (`--regime-overlay`), identically
across all combos — day-level regime flags under-recover as in-search predicates
(synthetic-control finding); they belong as an overlay. Report with and without.

## Run matrix (pre-committed)

1. H=5, cost=10bps, no overlay (primary — most periods).
2. H=20, cost=10bps, no overlay (secondary — small sample).
3. H=5, cost=10bps, regime overlay ON.
4. H=5, cost=0 reference (gross — to size cost erosion; NOT a pass criterion).

A PASS (WF + PBO + DSR≥0.95 net) in run 1 or 3 → pre-register the sealed-2025 test,
then build the multi-day-hold engine path for the cross-check. Long/short is the
higher-ceiling follow-on once a short leg exists (Stage-0 D10−D1 Sharpe 0.71–0.89).
