# Multi-year validation — breakout_first_pullback 0.1.0

**Frozen rules:** multi-week base → volume breakout → first pullback holds base high.  
**Universe:** 60 liquid large-caps. **Window:** 2022–2025.  
**Method:** all scanner setups; deterministic auto-arm; independent leaf sim.

## Pre-registered gates

| Gate | Criterion | Result |
|---|---|---|
| 1 | Pooled effR > 0 | **FAIL** (−0.02) |
| 2 | effR > 0 in ≥2 of 4 years | **PASS** (2023 +0.02, 2025 +0.03) |
| 3 | Tail flag | 2022 is the large hole (−$6k); does not dominate a *positive* pool |

**Verdict: FAIL overall** (gate 1 required). Park or only revisit with a pre-registered structural change — not parameter nibble.

## Numbers

| Cohort | Setups | Traded | Win% | cleanR | **effR** | P&L | Stood down | Tag |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Smoke n10 | 10 | 6 | 83% | +0.36 | +0.22 | +$1,096 | 4 | `bfp-smoke-v010` |
| n30 unique | 30 | 18 | 61% | +0.09 | +0.05 | +$777 | 12 | `bfp-v010-n30` |
| 2022 | 51 | 35 | 49% | −0.34 | **−0.24** | −$6,030 | 16 | `bfp-v010-y2022` |
| 2023 | 120 | 85 | 53% | +0.03 | **+0.02** | +$1,324 | 35 | `bfp-v010-y2023` |
| 2024 | 154 | 114 | 60% | −0.01 | **−0.01** | −$678 | 40 | `bfp-v010-y2024` |
| 2025 | 94 | 62 | 56% | +0.04 | **+0.03** | +$1,173 | 32 | `bfp-v010-y2025` |
| **Pooled** | **419** | **296** | **56%** | **−0.03** | **−0.02** | **−$4,210** | **123** | `bfp-v010-2022-2025` |

All multi-year batches: 100% policy ok, 0 voids.

## Notes

- Small n30 looked mildly positive; multi-year flattens to slightly negative.
- 2022 bear kills the strategy; recent years are only ~breakeven-to-thin-plus.
- Same pattern as `trend_pullback`: recent samples optimistic vs full 2022–25.

## Decision

**No promotion.** Optional later: tighter admission + multi-year retest as **new version**, or park and move on.
