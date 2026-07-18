# BB squeeze long — cost stress (v0.1.1 rules, same entries)

Resimulate all multi-year entries under higher fee/slip. Gates: pooled effR>0 and ≥2/4 years>0.

| Scenario | fee bps | slip bps | n | win% | effR | pnl | years+ | pass |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 7149 | 46.0 | -0.0107 | $-7648 | 0/4 | N |
| `slip_2x` | 1.0 | 4.0 | 7149 | 44.7 | -0.0302 | $-21562 | 0/4 | N |
| `slip_3x` | 1.0 | 6.0 | 7149 | 43.1 | -0.0496 | $-35493 | 0/4 | N |
| `fee2_slip4` | 2.0 | 4.0 | 7149 | 44.0 | -0.0399 | $-28531 | 0/4 | N |
| `fee2_slip6` | 2.0 | 6.0 | 7149 | 42.2 | -0.0594 | $-42454 | 0/4 | N |
| `fee5_slip5` | 5.0 | 5.0 | 7149 | 40.4 | -0.0789 | $-56373 | 0/4 | N |

Baseline effR = **-0.0107** (already negative).

## Verdict
- **All scenarios FAIL** including baseline.
- Extra costs only deepen the hole; no scenario recovers pooled edge or year breadth.

