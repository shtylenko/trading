# Micro-pullback warrior-universe probe (v0.1.0)

**Contract:** `micro_pullback_warrior_probe_v0.1.0`
**Window:** 2025-01-01 → 2026-06-30 (warrior float-caveat window only).
**Universe:** 420 cached low-float names (<20M current snapshot); not full exchange rescan.
**Screen:** gap≥5%, RVOL≥2, price $2–20, ADV≥500k, float<20M (current yfinance).
**Detector:** same liquid micro_pullback 5m rules (impulse → 1–3 bar VWAP-held pb → green break).
**Packaging:** portfolio 3 concurrent / 5 day; NML OFF.

## Gates (same bar as liquid multi-year)

| Gate | Result |
|---|---|
| Pooled effR > 0 | **PASS** (+0.0208) |
| ≥2 years > 0 | **FAIL** (1/2) |
| **Overall** | **FAIL** |

**Paper:** n=140 · win% 44.3 · effR **+0.0208** · pnl $+291
**Raw:** n=140 (portfolio skipped 0)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2025 | 82 | 41.5 | -0.0763 | $-626 |
| 2026 | 58 | 48.3 | +0.1580 | $+916 |

## Cost stress (taken set)

| Scenario | effR | pass |
|---|---:|:---:|
| `baseline_1f_2s` | +0.0208 | N |
| `slip_2x` | +0.0124 | N |
| `slip_3x` | +0.0044 | N |
| `fee2_slip4` | +0.0083 | N |
| `fee2_slip6` | +0.0002 | N |
| `fee5_slip5` | -0.0081 | N |

## Caveats

1. **Not multi-year sealed** — only ~18 months; float is **current snapshot**, not PIT.
2. Universe is **cached** low-float names (420), not a full Finnhub rescan + yfinance refresh.
3. Nine tickers failed screen on NA gaps (fixed for next run); incomplete coverage.
4. Year breadth gate uses calendar years in window (2025, 2026 only).

## Verdict

**FAIL overall gate** (years+ < 2) despite thin positive pooled effR. Does **not** promote warrior micro over liquid micro paper book. Liquid multi-year micro remains the primary short-hold research baseline.

**Do not** retune detector on this probe. Optional later: full float refresh + full exchange universe inside 2025–2026H1 only, still not multi-year.

