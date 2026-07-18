# BB squeeze long — multi-year short-hold (v0.1.1)

**Universe:** 59 liquid large-caps (same cohort as VWAP multi-year). **Window:** 2022–2025.
**Method:** 5m RTH path sim (entry next open after expand signal; stop / 1R-half / 2R / EOD).
**Costs:** 1 bps fee + 2 bps slip each way.

## Detection fix (v0.1.0 → v0.1.1)

v0.1.0 multi-year returned **n=0**: loop started at `bb_period + squeeze_lookback` (bar ~68 ≈ 15:10 ET),
after `entry_window_end` 14:30. v0.1.1 starts once mid-band exists, uses causal strict-`<` width
percentile (plateau-safe), lookback 36, pctile max 0.25.

## Gates (same bar as other families)

| Gate | Result |
|---|---|
| Pooled effR > 0 | **FAIL** (-0.0107) |
| ≥2 of 4 years > 0 | **FAIL** (0 of 4) |
| **Overall** | **FAIL** |

**Pooled:** n=7149 · win% 46.0 · **effR -0.0107** · pnl $-7,648
**Exits:** STOP 3184 · TARGET2 1466 · EOD 2499 (T1 is scale-half, not full exit)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 1710 | 46.8 | **-0.0032** | $-550 |
| 2023 | 1784 | 46.4 | **-0.0159** | $-2,839 |
| 2024 | 1904 | 45.6 | **-0.0123** | $-2,333 |
| 2025 | 1751 | 45.4 | **-0.0110** | $-1,926 |

## Cost stress

See `COST_STRESS.md`. **All grid points FAIL** (baseline already negative).

## Caveats / interpretation

- Large sample (n≈7k) — not a sparsity fail; edge is simply negative.
- ~45–47% WR with 1R/2R targets and ~45% stop rate is slightly worse than coin-flip after costs.
- Intraday BB squeeze→expand on liquid large-caps appears **non-predictive** under this long-only short-hold packaging (same conclusion as many vol-breakout toys after frictions).
- Offline 5m sim ≠ sealed 1m LLM batch path.

## Verdict

**PARKED / FAIL.** Do not promote. Do not iterate parameters to chase a thin positive —
year-by-year is uniformly negative. Prefer orthogonal short-hold ideas (e.g. warrior micro-pullback)
over retuning BB width thresholds.

