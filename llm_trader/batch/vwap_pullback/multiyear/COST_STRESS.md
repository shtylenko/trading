# VWAP pullback — cost stress (v0.1.0 rules, same entries)

Resimulate all multi-year entries under higher fee/slip. Gates: pooled effR>0 and ≥2/4 years>0.

| Scenario | fee bps | slip bps | n | win% | effR | pnl | years+ | pass |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 506 | 46.8 | +0.0236 | $+1194 | 3/4 | Y |
| `slip_2x` | 1.0 | 4.0 | 506 | 46.8 | +0.0041 | $+207 | 3/4 | Y |
| `slip_3x` | 1.0 | 6.0 | 506 | 46.6 | -0.0155 | $-782 | 0/4 | N |
| `fee2_slip4` | 2.0 | 4.0 | 506 | 46.8 | -0.0057 | $-288 | 2/4 | N |
| `fee2_slip6` | 2.0 | 6.0 | 506 | 46.6 | -0.0251 | $-1272 | 0/4 | N |
| `fee3_slip5` | 3.0 | 5.0 | 506 | 46.6 | -0.0251 | $-1272 | 0/4 | N |
| `fee5_slip5` | 5.0 | 5.0 | 506 | 45.8 | -0.0446 | $-2257 | 0/4 | N |

Baseline effR = **+0.0236**.

## Verdict
- Still pass: `baseline_1f_2s`, `slip_2x`
- Fail: `slip_3x`, `fee2_slip4`, `fee2_slip6`, `fee3_slip5`, `fee5_slip5`
- Edge survives **2× slip** but not **3×** — fragile.
