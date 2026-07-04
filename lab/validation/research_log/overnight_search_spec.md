# Overnight Cross-Sectional Search — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-16 BEFORE scoring, per EXPLORATION_PLAYBOOK §3 (capture broad /
lock search narrow). Companion: `overnight_premium_findings.md` (Stage 0/0.5),
`scripts/overnight_search.py` (implementation), `scripts/capture_overnight.py`
(ledger). Do NOT widen this grid in reaction to results — that is exactly what PBO
and DSR are meant to catch.

## Thesis being tested

The overnight (close→open) premium is real but cost-fragile equal-weight (Stage
0.5). The hypothesized tradeable edge is **cross-sectional selection**: hold only
the subset of names whose close-knowable state predicts a larger overnight bounce —
specifically **short-term reversal** (oversold names mean-revert overnight) on
**liquid, non-distressed** names, plus the **turn-of-month** calendar premium.

## Outcome & objective

- Outcome per name-night = close→open return, MINUS a round-trip cost charge
  (`--cost-bps`, default 5 bps for stocks). Everything (objective/WF/PBO/DSR) runs
  on NET return.
- Objective = annualized daily-portfolio info ratio (mean/std of nightly summed
  top-N net R), reusing `feature_search.daily_portfolio` verbatim.
- Deployment cap: top-N names/night by `score = -ret_5d` (most oversold first).
- Arbiter = leave-one-year-out walk-forward (2022/2023/2024). PBO via CSCV. DSR.
- 2025 SEALED (never read by the search).

## Pre-registered minimum effect size

A PASS must clear gates **at a realistic cost: ≥ 5 bps round-trip for stocks**
(≥ 3 bps for liquid ETFs). A combo that only works at 0–2 bps is a FAIL — record it
as cost-fragile, do not promote.

## The grid (LOCKED, k ≤ 2)

| Predicate | Feature | Cut | Rationale |
|---|---|---|---|
| rev_5d_oversold | ret_5d | ≤ −3% | 5-day losers bounce overnight (short-term reversal) |
| rev_rsi2_oversold | rsi_2 | ≤ 10 | Connors RSI(2) oversold (reversal, faster) |
| weak_close_today | ret_intraday | ≤ −1% | closed soft today → overnight stabilization |
| not_falling_knife | dist_52w_high | ≥ −25% | exclude distressed/in-liquidation names |
| liquid_20m | dollar_vol_20d | ≥ $20M | only cost-bearing names |
| price_min_10 | log_close | ≥ ln(10) | ≥ $10 (sub-$10 spread drag) |
| calm_vol | vol_20d | ≤ 4%/day | avoid the most volatile (overnight gap risk) |
| turn_of_month | is_turn_of_month | = 1 | turn-of-month calendar premium |

Same-thesis pair allowed together: {rev_5d_oversold, rev_rsi2_oversold} (a
reversal-confirmation pair). All other same-feature pairs excluded by the enumerator.

## Regime overlay (NOT a searched predicate)

SPY > 200-day SMA is applied as a fixed CAPITAL OVERLAY (`--regime-overlay`), held
identically across all combos, NOT optimized in the grid — because day-level regime
flags under-recover under the daily-IR objective (synthetic-control finding); they
belong as an overlay, not an admission filter. Report both with and without.

## Run matrix (pre-committed)

1. cost=5bps, no overlay (pure cross-sectional, realistic stock cost).
2. cost=5bps, regime overlay ON.
3. cost=0bps reference (gross — to see how much cost erodes; NOT a pass criterion).

A PASS in run 1 or 2 at 5 bps → pre-register the sealed-2025 test, then build the
overnight-hold engine path for the cross-check.
