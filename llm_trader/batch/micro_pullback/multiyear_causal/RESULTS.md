# Micro-pullback multi-year — E0 causal RVOL audit

**Pre-reg:** `PREREG_CAUSAL_E0.md` (written before this run).
**Change:** daily RVOL uses **prior-day** volume only (was full-session look-ahead).
**Detector / universe / costs:** frozen identical to contaminated baseline otherwise.
**Construction:** `v0.1.0_micro_pullback_causal_e0`

## Gates (kill criteria)

| Gate | Result |
|---|---|
| Pooled effR > 0 | **FAIL** (-0.0345) |
| ≥2/4 years > 0 | **FAIL** (0/4) |
| **Overall** | **FAIL — park liquid short-hold track** |

**Raw pooled:** n=813 · win% 38.0 · effR **-0.0345** · pnl $-2,801
**Entries:** 813 · **Trades:** 813

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 242 | 36.8 | -0.0389 | $-942 |
| 2023 | 189 | 42.9 | -0.0175 | $-331 |
| 2024 | 181 | 39.2 | -0.0071 | $-128 |
| 2025 | 201 | 33.8 | -0.0696 | $-1,400 |

## Cost stress (raw sealed set)

| Scenario | fee | slip | n | win% | effR | years+ | pass |
|---|---:|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 813 | 38.0 | -0.0345 | 0/4 | N |
| `slip_2x` | 1.0 | 4.0 | 813 | 37.4 | -0.0539 | 0/4 | N |
| `slip_3x` | 1.0 | 6.0 | 813 | 37.0 | -0.0735 | 0/4 | N |
| `fee2_slip4` | 2.0 | 4.0 | 813 | 37.1 | -0.0636 | 0/4 | N |
| `fee2_slip6` | 2.0 | 6.0 | 813 | 36.8 | -0.0832 | 0/4 | N |
| `fee5_slip5` | 5.0 | 5.0 | 813 | 36.3 | -0.1026 | 0/4 | N |

## Portfolio packaging (3 concurrent / 5 day)

n taken=729 skipped=84 effR=-0.0355 years+=0/4 pass=False

## Comparison to contaminated baseline

| | Contaminated (full-day RVOL) | Causal E0 |
|---|---:|---:|
| n | 1102 | 813 |
| effR | +0.0292 | -0.0345 |
| years+ | 4/4 | 0/4 |

## Verdict

**FAIL gates** under causal RVOL. Per PREREG: **park liquid short-hold track** (no detector retune). Negative integrity result banks the leak finding.

