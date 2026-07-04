# 2026-H1 EARLY PARTIAL Confirmation — Multi-Day Momentum — PRE-REGISTERED (LOCKED)

LOCKED 2026-06-16 BEFORE reading any 2026 data. This is the SECOND sealed confirmation of the
12-1 momentum edge ([[multiday-momentum-stage0]]), taken EARLY and PARTIAL by explicit choice —
the user accepts that this spends the 2026-H1 seal and forgoes the cleaner full-year test that
would have been available ~early 2027. The printed verdict is binding regardless of outcome.
Companion: `multiday_oos_preregistration.md` (the 2025 first confirmation, mirrored here);
`oos_spend_ledger.md` (records the spend).

## Why this is an EARLY PARTIAL read (and its limits, stated up front)

- Only ~5.5 months of 2026 exist (through 2026-06-16). With H=20 and the forward-return label,
  the last usable formation is ~20 trading days before the data edge → roughly **5 independent
  non-overlapping periods** (~94 overlapping daily cohorts, but only ~5 effective degrees of
  freedom). This is **less than half** the power of the 2025 read (~12 periods) and CANNOT by
  itself confirm or kill the edge — it is directional evidence only.
- **2026-H1 is the DISTRUSTED window.** The cross-family finding ([[cross-family-2026h1-artifact]])
  is that 2026-H1 was the ONLY positive bucket across 18 ungated releases — i.e. this window has a
  history of spurious positivity. A raw-positive momentum read here is therefore NOT enough; it
  must be a genuine cross-sectional MOMENTUM tilt, not the window's broad beta artifact.
- Spends the 2026-H1 seal (1st query of 2026-H1). Momentum qualifies: 8yr in-sample DSR 0.997
  clears the 1st-query bar (≥0.95). After this, 2026-H1 is consumed for the momentum family.

## The EXACT rule (identical to the 2025 confirmation; nothing tuned to 2026)

- Data: **SPLIT-ADJUSTED** daily bars (the raw-bar bug is fixed — `_capture_multiday_2026h1_split.parquet`).
- Universe: `liquid_pit` PIT as of each rebalance date in 2026-H1.
- Eligibility: close ≥ $5 AND 20-day dollar-volume ≥ $10M.
- Signal: `mom_12_1` = close(d−21)/close(d−252) − 1.
- Selection: long the **top 50** eligible names by mom_12_1, equal weight, UNCONDITIONED.
- Rebalance: monthly, H = 20 trading days. Metrics use the daily-formation overlapping cohort
  series + Newey-West HAC (phase-independent), exactly as the 2025 script.
- Cost: 10 bps round-trip per held name per rebalance.

## Pre-committed criteria (decided before the read)

PRIMARY (tradeability, net of cost) — same thresholds as 2025:
- **PASS-primary** if per-period net mean > 0 AND annualized Sharpe ≥ 0.5.
- **REVIEW-primary** if net > 0 but Sharpe in [0, 0.5).
- **FAIL** if net mean ≤ 0.

DISTRUST OVERLAY (this window only — the gating qualifier):
- The cross-sectional premium (top-50 net mean − eligible-universe gross mean) MUST be > 0 for a
  PASS to stand. **A PASS-primary with premium ≤ 0 is DOWNGRADED to REVIEW** — in the suspected-
  artifact window, positive return without a momentum tilt is most likely the 2026-H1 beta
  artifact, not our edge. (In 2025 the premium was color; here it is a gate.)

FINAL VERDICT mapping:
- **CONFIRM** = PASS-primary AND premium > 0.
- **REVIEW** = (net > 0 but Sharpe < 0.5) OR (PASS-primary but premium ≤ 0).
- **FAIL** = net mean ≤ 0.

Reported alongside (color, not gates): decile monotonicity, HAC t-stat (expected very weak on
~5 periods — explicitly NOT a gate), period count and effective n.

## What each outcome means (pre-committed interpretation)

- **CONFIRM:** the second sealed confirmation holds even on the distrusted window — strengthens
  the body of evidence (8yr in-sample + 2025 OOS + 2026-H1). Still owes live-cost/borrow validation
  before capital; a 5-period CONFIRM is supportive, not decisive.
- **REVIEW:** ambiguous — consistent with a real-but-noisy edge on a tiny sample, or with the
  window artifact. Does not strengthen; momentum stays "real but modest, 2nd confirmation inconclusive."
- **FAIL:** the edge did not show in 2026-H1. Given the tiny sample this is not fatal on its own,
  but it is recorded as a failed confirmation and lowers confidence; the body of evidence reverts
  to 8yr in-sample + the single 2025 OOS pass.

## Disposition

After the ONE read: record the verdict here and in `oos_spend_ledger.md` (2026-H1 spent on the
momentum family, win or lose). No second look at 2026-H1 for momentum.

---

## DISPOSITION (read 2026-06-17, ONE SHOT, binding)

**VERDICT: CONFIRM.** (94 daily cohorts, 2026-01-02 → 2026-05-18; ≈5 effective independent periods.)
- PRIMARY: per-period net mean **+5.58%**, annualized **Sharpe +1.77** (≥ 0.5) → PASS-primary.
- DISTRUST OVERLAY (the gate): cross-sectional premium (top-50 net − universe gross) = **+4.56%**
  → POSITIVE = genuine momentum tilt, NOT just the 2026-H1 beta artifact. Gate passed.
- COLOR: decile monotonicity **+1.00** (perfect, holds OOS); HAC t **+1.42** (weak by design on
  ~5 periods — color, not a gate).

**Reading:** the second sealed confirmation HOLDS even on the distrusted window, with a strong
positive cross-sectional premium that allays the artifact concern. Body of evidence now = 8yr
in-sample (survivorship-lifted) + clean 2022–2024 PIT + sealed-2025 PASS + sealed-2026-H1 CONFIRM.
**Calibration caveats (binding, stated up front):** (1) ~5 effective periods → SUPPORTIVE /
directional, NOT decisive — a strong half-year is one draw. (2) The premium is NOT beta-adjusted;
with book β≈1.4 in a positive-market half-year, some of the +4.56% is mechanical beta (per the
2026-06-16 peer review). The beta-adjusted alpha check (backlog #1) should run next to size the
true alpha. (3) Still a modest, beta-heavy edge; this does not raise the deployable magnitude. No
second look at 2026-H1 for momentum.
