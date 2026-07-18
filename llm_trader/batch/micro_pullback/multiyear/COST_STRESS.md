# Micro-pullback — cost stress (v0.1.0 rules, same entries)

Resimulate all multi-year entries under higher fee/slip. Gates: pooled effR>0 and ≥2/4 years>0.

| Scenario | fee bps | slip bps | n | win% | effR | pnl | years+ | pass |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 1102 | 46.2 | +0.0292 | $+3214 | 4/4 | Y |
| `slip_2x` | 1.0 | 4.0 | 1102 | 45.7 | +0.0096 | $+1061 | 3/4 | Y |
| `slip_3x` | 1.0 | 6.0 | 1102 | 45.3 | -0.0100 | $-1098 | 1/4 | N |
| `fee2_slip4` | 2.0 | 4.0 | 1102 | 45.6 | -0.0001 | $-12 | 2/4 | N |
| `fee2_slip6` | 2.0 | 6.0 | 1102 | 45.0 | -0.0197 | $-2172 | 0/4 | N |
| `fee5_slip5` | 5.0 | 5.0 | 1102 | 44.5 | -0.0392 | $-4322 | 0/4 | N |

Baseline effR = **+0.0292**.

## Verdict
- Still pass: `baseline_1f_2s`, `slip_2x`
- Fail: `slip_3x`, `fee2_slip4`, `fee2_slip6`, `fee5_slip5`
- Edge survives **2× slip** but not **3×** — similar cost-fragility to VWAP; slightly stronger baseline.

