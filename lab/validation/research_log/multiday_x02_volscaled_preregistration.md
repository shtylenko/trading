# x02 — Vol-Scaled / Risk-Managed Momentum — PRE-REGISTERED spec (LOCKED)

Drafted 2026-06-16; **LOCKED 2026-06-16 before scoring** (σ_target rule = Option B, below).
Do NOT change the variant set, the bar, or σ_target in reaction to results — any change is a
new dated spec. Companions: `multiday_momentum_findings.md` (base edge + split-adjust
re-confirmation), `multiday_search_spec.md` (the base 12-1 search), `EXPLORATION_PLAYBOOK.md`
(capture broad / lock search narrow). **This is the narrow, pre-committed test — do NOT widen
the variant set or re-tune in reaction to results.**

## Why this hypothesis (motivation, ex-ante)

Two independent reasons, neither from inspecting which x01 trades lost:

1. **Literature.** Risk-managed momentum (Barroso–Santa-Clara 2015; Daniel–Moskowitz 2016):
   scaling momentum exposure inversely to its recent volatility raises the Sharpe and cuts the
   crash tail, because momentum's worst drawdowns cluster in high-volatility "panic→rebound"
   regimes. A structural, theory-motivated change applied uniformly — not a loss-exclusion filter.
2. **Our clean data points the same way.** After the split-adjustment fix, the conditioning that
   becomes load-bearing on clean 2022–2024 is `calm_vol` (select low-volatility names): the
   base *unconditioned* book actually got slightly weaker clean (per-period t +1.14→+0.86) while
   `liquid_50m+calm_vol` clears DSR 0.97. Vol-*scaling* (weight by 1/σ) is the smooth structural
   version of the `calm_vol` (binary low-σ filter) that is already winning.

## What x02 changes vs x01 (one lever: position weighting)

Everything else identical to the validated base rule: rank top-N by `mom_12_1`, monthly
non-overlapping rebalance, H=20 hold, $5/$10M eligibility floor, 10 bps round-trip cost.
The ONLY change is how the top-N book is weighted. Two pre-committed variants (both leak-safe;
σ from `vol_20d`, close-knowable through the rebalance date):

- **V1 — inverse-vol weights.** Within the top-N book, weight name i by `w_i ∝ 1/σ_i`,
  normalized to sum 1 (long-only, fully invested). Tilts toward lower-vol winners.
- **V2 — constant-target-vol scaling.** Keep equal weights inside the book, but scale the
  book's *gross exposure* by `min(1, σ_target / σ_book,t)`, where `σ_book,t` is the trailing
  realized vol of the equal-weight momentum book and `σ_target` is a single pre-fixed constant.
  Residual capital sits in cash (0 return). This is the canonical Barroso construction.
  - **σ_target rule = OPTION B (LOCKED, no look-ahead):** σ_target = the mean of `σ_book,t`
    over the **FIRST search year (2022) ONLY**, computed once and then held fixed for all
    later dates (2023, 2024, and the 8yr secondary). No full-window normalization, no per-year
    re-fit — early dates are never informed by later data. Report the resulting constant.
    Exposure is capped at 1.0 (long-only, never levered above fully-invested).

No grid over σ_target, no per-year tuning, no blend weights searched. V1 and V2 are the entire
variant set (2 variants). σ_target is fixed once by Option B, reported, never swept.

## Baseline to beat (the bar)

x02 must beat the **clean base 12-1 EQUAL-WEIGHT book** (x01's construction on split-adjusted
data) on a like-for-like basis — same universe, horizon, cost, periods. Beating the *conditioned*
`calm_vol` combo is NOT the bar (that would double-count the vol effect). Concretely, PROMOTE-
CANDIDATE only if BOTH:
- DSR(x02) ≥ 0.95 **and** DSR(x02) > DSR(base equal-weight) on clean 2022–2024, and
- annualized Sharpe(x02) > Sharpe(base equal-weight) by a margin that survives the phase round
  (WF passes in ≥60% of the H=20 rebalance phases, per `multiday_power.py` convention).
If x02 only matches the base, the simpler equal-weight x01 wins (parsimony) — vol-scaling ships
ONLY if it earns its added complexity.

## Data / objective / gates (reused verbatim, no new knobs)

- Ledgers: `_capture_multiday_2022_2025_split.parquet` (clean PIT core, primary) and
  `_capture_multiday_2017_2025_split.parquet` (8yr, survivorship-limited pre-2022, secondary).
- Objective = daily-portfolio IR; arbiter = leave-one-year-out walk-forward; gates = PBO
  (CSCV+embargo) and Deflated Sharpe ≥ 0.95 — identical to the base search. Requires a weighted
  variant of `feature_search.daily_portfolio` (the only new code; weights are an input, the
  metric/gate math is unchanged).
- Report base-equal-weight, V1, V2 side by side on the SAME periods + phases.

## Sealed-data discipline (critical)

- **2026 is the untouched sealed 2nd-confirmation** (data-gated ~early 2027). x02 design and
  in-sample evaluation must NOT read 2026 in any form. Spend it once, later, on whichever of
  {base, x02} is the chosen deployable.
- **2025 is already spent** (raw sealed-OOS PASS + re-seen in the x01 engine run). It may be
  shown as already-revealed context but is NOT a fresh gate for x02 and cannot re-bless a promote.
- Clean confirmatory evidence for x02 is therefore **in-sample 2022–2024** (+ 8yr secondary,
  survivorship-flagged) until 2026 accrues. No new sealed year is created by this work.

## Leakage checklist (must hold)

- `vol_20d` and `mom_12_1` use data THROUGH the rebalance close only (already enforced in capture).
- Weights/exposure computed from σ knowable at rebalance; no forward σ. σ_target uses Option B
  (2022-only mean, fixed forward) so NO later-year data informs earlier exposure — zero look-ahead.
- Cost charged per held name per rebalance as in the base search.

## Decision rule (pre-committed)

1. If neither variant beats base-equal-weight on DSR AND Sharpe (clean 2022–2024, phase-robust):
   **x02 KILLED** — equal-weight x01 is the deliverable; record that vol-scaling adds nothing here.
2. If a variant clears the bar: **PROMOTE-CANDIDATE** → implement as immutable release `x02`,
   run through the swing engine (split-adjusted) as the Stage-6 cross-check, then HOLD for the
   2026 sealed 2nd-confirmation. Do NOT claim a fresh OOS pass off 2025.
3. Lock σ_target and the variant set in THIS file before scoring; any change is a new, dated spec.

---

## RESULT (2026-06-16) — x02 KILLED: vol-scaling adds nothing on the confirmatory sample

Run `scripts/multiday_volscale.py` on the clean split parquets, H=20, top50, 10bps, σ_target
Option B (2022-only mean book vol, fixed forward = 3.89%/day).

**Clean 2022–2024 (38 periods, primary):** V1 inverse-vol LOOKED better — Sharpe +0.68 vs base
+0.50, DSR 0.846 vs 0.764, and flipped the 2022 bear (−3.0%→+3.4%); V2 marginal (+0.55). But
NONE cleared the absolute DSR≥0.95 gate.

**Clean 8yr 2017–2024 (101 periods, confirmatory):** the V1 edge EVAPORATES. base Sharpe +0.88 /
DSR 0.992; V1 +0.85 / 0.990; V2 +0.89 / 0.992 — statistically indistinguishable. V1 even trails
base in the 2020 momentum boom (+84% vs +103%) because inverse-vol weighting down-weights the
high-vol winners that drive long-only momentum returns.

**Verdict per the locked decision rule:** neither variant beats base on the higher-power 8yr
sample → **x02 KILLED**. Equal-weight x01 remains the deliverable. The 2022–2024 V1 advantage was
a 38-period small-sample effect (specific to the 2022 bear), not a real improvement.

**Why (economics):** Barroso/Daniel vol-scaling helps the LONG/SHORT momentum factor, whose
crashes are violent short-side rebounds in high-vol regimes. LONG-ONLY momentum has a milder
crash profile and earns much of its return FROM the high-vol winners — so trimming them (V1) or
scaling out in storms (V2) costs more than it saves. Reaffirms the core finding: base
unconditioned 12-1 momentum IS the edge; neither conditioning (the 29-combo grid) nor vol-sizing
beats it on clean, statistically-powered data. No sealed data spent.
