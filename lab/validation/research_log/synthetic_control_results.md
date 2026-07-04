# Synthetic Dose-Response Positive Control — RESULTS

Run 2026-06-15 on the real capture ledger (`_capture_2022_2025.parquet`, 23,261
rows / 18,712 filled, 2022–2025). Harness: `scripts/synthetic_control.py`
(reuses `feature_search` / `cscv` / `deflated_sharpe` verbatim; no DB writes, no
engine changes). Plan: `synthetic_control_plan.md`. Reproduce:

```bash
python3 -m trading.lab.scripts.synthetic_control
```

Injection (deterministic): `realized_r_synth = realized_r_real + m·1{opening_rv≥1.5}`.
`m=0` reproduces the real ledger exactly (the NULL / false-positive control);
`m>0` superimposes a known per-trade edge on real noise.

## Dose-response power curve (plant = `rvol_min_1_5`, 46% of filled rows)

| m | winner | found | WF sumR | pos folds | PBO | DSR | ann. dSR | sealed-2025 | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0.00 (NULL) | gap_floor_3+rvol_min_1_5 | YES | +40.9 | 3/3 | 0.39 | 0.58 | +0.70 | −34.1 | **REVIEW** |
| 0.02 | gap_floor_3+rvol_min_1_5 | YES | +71.2 | 3/3 | 0.43 | 0.83 | +1.22 | −20.5 | REVIEW |
| 0.05 | gap_floor_3+rvol_min_1_5 | YES | +87.3 | 2/3 | 0.14 | 0.98 | +1.99 | −0.2 | NO-EDGE |
| 0.10 | rvol_min_1_5 | YES | +189.9 | 3/3 | 0.00 | 1.00 | +3.26 | +127.6 | **PROMOTE** |
| 0.20 | rvol_min_1_5 | YES | +651.7 | 3/3 | 0.00 | 1.00 | +6.44 | +263.2 | **PROMOTE** |

## Verdict: the validator is SOUND

1. **False-positive control PASSES.** The NULL (m=0, = the real ledger) is NOT
   promoted: WF passes but DSR=0.58 ⇒ REVIEW. This is exactly the gap+rvol REVIEW
   the real search produced — and the sealed-2025 of −34.1R is the real
   sealed-year kill (see [feature-search-harness-and-verdict]). The pipeline does
   not bless real noise as an edge.
2. **Detection power CONFIRMED, monotone.** As `m` rises, WF sumR ↑, PBO ↓, DSR ↑,
   sealed-year flips strongly positive. The gates respond to a real planted edge
   exactly as designed.
3. **Minimum detectable edge `m* = 0.10 R/trade`** (winner annualized daily Sharpe
   ≈ **+3.26** at the crossing). This is the pipeline's **sensitivity floor**.
4. **Feature recovery 4/4** positive doses recovered the planted `rvol_min_1_5`.

⇒ **Prior kills are trustworthy. The long-only same-day regime is genuinely thin**
(the structural finding from the 5-model consensus), not a broken validator.

## Gate-calibration note (DSR≥0.95 is demanding)

The DSR gate only clears once the *winner's* annualized daily Sharpe reaches ≈3.2
(m=0.10). A genuinely modest edge — m=0.02, ann. Sharpe ≈ **+1.2** — sits at DSR
0.83 ⇒ REVIEW, and m=0.05 (Sharpe ≈ 2.0) actually drops to NO-EDGE on a 2/3 WF
fold. So **the pipeline confirms only fairly strong edges** (Sharpe ≳ 3 at the
selection winner); a true Sharpe-~1 intraday edge would land in REVIEW, not
PROMOTE. This is *defensible* (selection-bias deflation across ~46 combos is
supposed to be punitive) but it is the binding constraint. **No change made** —
recorded as proposal-only per the plan. If a future real candidate sits in REVIEW
with WF+PBO clean, this curve is the evidence for whether to trust it.

## Feature-geometry finding (recovery is not uniform across the grid)

The robustness replant exposed a real property of the daily-portfolio IR objective:

- **Cross-sectional (within-day) predicates are recovered cleanly.** Replanting on
  `close_pos_max_0_9` → recovered at m=0.10 (PROMOTE); `atr_frac_max_0_5` at m≥0.20.
- **Day-level regime flags are structurally UNDER-recovered.** Replanting on
  `spy_weak_regime` (42% of rows — *equally* selective as rvol) is **never**
  recovered, even at m=0.70. Reason: a regime flag is identical for every
  candidate on a day, so filtering on it drops *whole days*; the resulting
  zero-days inflate the IR denominator (mean/std of daily R), so the IR objective
  cannot isolate a per-trade edge that lives on a day-level axis.

**Implication:** the `spy_weak_regime` / `sector_weak_regime` grid predicates are
at an inherent recovery disadvantage under this objective — a regime edge of a
given per-trade size scores worse than the same edge on a cross-sectional feature.
This partially explains why regime-gated drive variants (d11/d14) struggled: the
selection objective itself underweights day-level gates. A regime signal is better
expressed as a *daily capital-allocation* overlay than as a within-search admission
filter. (The default robustness check uses `close_pos_max_0_9` so it is conclusive;
pass `--no-replant` to skip, or re-plant via the helper to reproduce the regime case.)

## Scope (what this does and does NOT validate)

- **Validates:** the stats/selection machinery — search → LOO walk-forward → PBO →
  DSR → sealed year (funnel stages 2–5).
- **Does NOT validate:** the capture/feature engine (stage 1) or execution
  (stage 6) — covered by the feature tests and the d15 engine cross-check — nor
  edges *outside* the pre-registered grid.
