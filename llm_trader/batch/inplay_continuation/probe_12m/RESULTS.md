# In-play continuation — 12m probe v0.1.0 (Opp C)

**Pre-reg:** `batch/inplay_continuation/PREREG_v010.md`
**WeBull costs:** commission 0; baseline slip **15.0 bps** one-way (SMALL).
**Window:** 2025-07-01 → 2026-06-30
**Construction:** `v0.1.0_inplay_continuation`

## Gates

| Gate | Result |
|---|---|
| Pooled effR > 0 @ slip15 | **PASS** (+0.0756) |
| ≥1 year > 0 | **PASS** (1/2) |
| Slip30 not catastrophe (effR > −0.05) | **PASS** |
| **Overall** | **PASS** |

**Raw:** n=87 win%=41.4 effR=+0.0756 pnl=$+657
**Paper portfolio:** n=87 skipped=0 effR=+0.0756

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2025 | 45 | 35.6 | -0.1229 | $-553 |
| 2026 | 42 | 47.6 | +0.2882 | $+1,210 |

## Cost stress (WeBull slip grid)

| Scenario | slip | n | win% | effR | pass |
|---|---:|---:|---:|---:|:---:|
| `baseline_slip15` | 15.0 | 87 | 41.4 | +0.0756 | Y |
| `slip_10` | 10.0 | 87 | 42.5 | +0.1060 | Y |
| `slip_20` | 20.0 | 87 | 40.2 | +0.0455 | Y |
| `slip_30` | 30.0 | 87 | 40.2 | -0.0134 | N |
| `slip_50` | 50.0 | 87 | 40.2 | -0.1217 | N |
| `mega_slip2_ref` | 2.0 | 87 | 47.1 | +0.1541 | Y |

## Verdict

PASS — candidate for Opp B selection layer; still no live capital.

Caveat: current-snapshot float / cached universe; not multi-year PIT.

