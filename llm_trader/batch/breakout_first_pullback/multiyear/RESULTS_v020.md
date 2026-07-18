# Multi-year validation — breakout_first_pullback 0.2.0

**Structural package (pre-registered vs 0.1.0):**
- Trigger = **breakout level** (not setup high)
- Name + SPY **above SMA200**
- Breakout vol **1.5×**, clear **0.30%**
- Tighter retest / extension; pullback tag vol < breakout vol

**Gates:** pooled effR > 0 AND ≥2 of 4 years effR > 0.

## Verdict: **FAIL — worse than 0.1.0**

| Gate | Result |
|---|---|
| Pooled effR > 0 | **FAIL** (−0.12) |
| ≥2 of 4 years > 0 | **FAIL** (0 of 4) |

## Numbers

| Cohort | Setups | Traded | Win% | **effR** | P&L | Stood down | Tag |
|---|---:|---:|---:|---:|---:|---:|---|
| 2022 | 9 | 6 | 17% | **−0.44** | −$2.0k | 3 | `bfp-v020-y2022` |
| 2023 | 40 | 15 | 13% | **−0.14** | −$2.9k | 25 | `bfp-v020-y2023` |
| 2024 | 58 | 28 | 39% | **−0.06** | −$1.7k | 30 | `bfp-v020-y2024` |
| 2025 | 38 | 18 | 44% | **−0.11** | −$2.1k | 20 | `bfp-v020-y2025` |
| **Pooled** | **145** | **67** | **33%** | **−0.12** | **−$8.7k** | **78** | `bfp-v020-2022-2025` |
| 0.1.0 pooled (ref) | 419 | 296 | 56% | −0.02 | −$4.2k | 123 | `bfp-v010-2022-2025` |

**Note:** High stand-down rate (78/145) — breakout-level buy-stop often never fills after the retest day. Filters cut sample (419→145) and **hurt** expectancy.

## Decision

**Park family.** Structural package rejected. Do not run 0.3.0 without a new thesis (not more filters on the same mold).
