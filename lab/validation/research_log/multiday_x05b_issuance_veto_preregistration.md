# x05b — Issuance-Veto on x03, RE-SPECIFIED decision rule — PRE-REGISTERED (LOCKED)

Locked 2026-06-24. **This is a re-specification of x05 Arm B after observing the 2022–24 result**
(`multiday_x05_residual_purification_preregistration.md` addendum + `backlog.md`). Integrity note
up front, because re-spec-after-seeing-results is the classic forking-paths trap:

## Why a re-spec, and the integrity guardrails

The x05 decision rule required **β to fall** (it was written for Arm A, "purify the residual /
attack β≈1.08"). The issuance veto is a *different mechanism* — drop the heaviest share-diluters
among residual winners — which should improve **quality/alpha**, not β. On 2022–24 it did exactly
that: Sharpe 0.79→0.86, α-t 0.98→1.22, maxDD −11.6→−10.5, CAGR 15.1→16.3 — all favorable — but
**β rose** (1.05→1.07), tripping the old rule's β-fall KILL trigger. The old rule mis-fit the
mechanism. Hence a corrected, β-neutral rule.

**Guardrails against fitting the rule to the data:**
1. **2022–24 is now SPENT — motivating / in-sample ONLY.** It cannot count as confirmatory. I have
   seen its numbers; using them to confirm would be circular.
2. The corrected rule is justified by **mechanism stated ex-ante** (a dilution veto is an
   alpha/quality lever, β-orthogonal), NOT reverse-engineered to pass 2022–24. To prove that, a
   **β-blowup guard** is added (Δβ ≤ +0.10): the veto may be β-neutral but must NOT become a beta
   play — which would be the failure mode the old β-fall rule was guarding against.
3. **Confirmation requires a window I have NOT optimized on:** 2009–16 (fresh for issuance).
   Promotion to a sealed-2027 read requires the corrected rule to hold there too.
4. The 2022–24 effect was **within noise** (corr 0.99, α-t still < 2). So the bar is consistency
   across BOTH windows, not magnitude on one. A single-window result does NOT pass.

## Hypothesis (ex-ante)

Among x03 residual-momentum winners, names that have heavily issued shares in the trailing 12m are
disproportionately late-stage / dilutive / "junk-rally" names that mean-revert; excluding them
raises risk-adjusted return and idiosyncratic alpha **without** raising market β.

## Construction (frozen — identical to x05 Arm B)

Within the **top-90 by x03 IR**, exclude the **top quintile** (≥80th pct) by split-adjusted 12m net
share issuance (`_capture_issuance_*.parquet`, NSI winsorized to (−0.45,+0.85) — split-artifact
clean, conservative), take **top-50 EW**. Missing-NSI names KEPT; backfill down IR if < 50. Baseline
= x03 top-50. Scripts: `experiments/multiday/multiday_residpurify_veto.py` (+ `capture_issuance.py`).

## CORRECTED decision rule (LOCKED) — β-neutral, both windows

For the veto vs baseline, on **2009–16** (confirmation) — and reported but NOT counted on 2022–24
(spent) — require ALL of:
1. **Sharpe higher** (any positive margin), AND
2. **α-t not worse** than baseline, AND
3. **maxDD not deeper** than baseline, AND
4. **CAGR not collapsing** (≥ baseline − 1pp), AND
5. **β-blowup guard: Δβ ≤ +0.10** (β-neutral allowed; a beta play is NOT).

**PASS** (→ a single pre-registered sealed-2027 read, the only thing that could promote it): 2009–16
meets all five **and** 2022–24 (motivating) was directionally consistent (it was). **KILL:** 2009–16
fails any of 1–4, or β blows up (Δβ > +0.10), or the 2009–16 NSI coverage is too thin to form a real
veto (< ~50% of pool-periods have ≥10 NSI-scored names → INCONCLUSIVE, treat as no-evidence → bank).
No sealed year is spent by this in-sample test; a PASS only *earns the right* to propose the 2027 read.

## Known limitation (stated ex-ante)

Pre-2012 SEC **XBRL coverage is thin** (XBRL phased in ~2009–2012), so DEI cover-page shares — and
thus NSI — may be sparse early in the 2009–16 window. If coverage is too low the window is
**inconclusive, not a pass** (rule 5b above). The 2009–16 ledger is also survivorship-lifted (YF),
so even a clean read is secondary evidence; the real test is the sealed forward year.
