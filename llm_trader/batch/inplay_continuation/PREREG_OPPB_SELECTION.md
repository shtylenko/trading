# Pre-registration — Opp B selection on `inplay_continuation` v0.1.0

**Before selection A/B results.** Date: 2026-07-19.  
**Base:** Sealed Opp C entries (`entries.db`, n=87, construction `v0.1.0_inplay_continuation`).  
**No detector retune.** Selection only. WeBull costs unchanged (slip 15 baseline).

## Motivation

Opp C pooled positive but **year-unstable** (2025 ≪ 0, 2026 ≫ 0).  
Hypothesis: take-all in-play hits are noisy; **admission filters** can remove low-quality tails without changing geometry.

## Frozen variants (evaluate all; no post-hoc add)

| Id | Rule | Thesis |
|---|---|---|
| `baseline` | All sealed trades | Control |
| `morning_only` | `time_et` &lt; **11:00** | Morning continuation cleaner than midday chase |
| `gap_band` | **5% ≤ gap ≤ 15%** | Exclude extreme lottery gaps |
| `rvol_strict` | prior-day **rvol ≥ 3.0** | Stronger in-play only |
| `shallow_pb` | `depth_frac` ≤ **0.40** | True micro-pb, not deep wash |
| `first_per_day` | Earliest `time_et` per calendar day only | Avoid stacking correlated names |
| **`select_A`** | **morning_only ∧ gap_band ∧ rvol_strict** | Primary “A+” stack (pre-registered) |

Optional report only (not primary kill): `select_A ∧ shallow_pb`, `select_A ∧ first_per_day`.

## Costs / packaging

- Baseline slip **15 bps** one-way WeBull model  
- Also report slip **30** on each variant (no re-selection)  
- Portfolio 3/5 applied **after** selection  

## Gates (kill / keep)

| Gate | Criterion |
|---|---|
| **Primary keep** | Variant `select_A` has pooled effR > 0 **and** **both** 2025 and 2026 effR > 0 @ slip15 |
| Soft positive | Any single filter achieves both years > 0 @ slip15 → promote that filter to v0.1.1 admission (new pre-reg version, not nibble) |
| Kill Opp C track | **No** variant achieves both years > 0 @ slip15 → park inplay for selection failure; do not invent more filters on this sample |
| Cost | `select_A` (or soft winner) at slip30: effR > −0.05 |

**Not success:** Adding a 4th filter after seeing these results; picking a variant that only works in 2026; changing gap/rvol thresholds after the run.

## Outputs

- `batch/inplay_continuation/selection_b/RESULTS.md` (+ json)
