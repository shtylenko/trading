# Multi-year validation results — trend_pullback 0.4.0

**Frozen rules:** SMA50 pullback, tight admission, setup_high, prior-high targets, SPY>SMA50.  
**Universe:** 60 liquid large-caps. **Window:** 2022-01-01 → 2025-12-31.  
**Method:** all scanner setups per year + pooled; deterministic auto-arm; independent leaf sim (no portfolio concurrency).

## Pre-registered gates (from PREREG.md)

| Gate | Criterion | Result |
|---|---|---|
| 1 | Pooled effR > 0 | **FAIL** (−0.02) |
| 2 | effR > 0 in ≥2 of 4 years | **FAIL** (only 2024 > 0; 2025 ≈ 0) |
| 3 | Tail flag | 2023 alone is large negative; 2024 does not carry pooled positive |

**Verdict: FAIL — park family as tradable edge. Keep 0.4.0 only as research baseline / negative evidence.**

## Numbers

| Cohort | Setups | Traded | Win% | cleanR | **effR** | P&L | Stood down | Tag |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2022 | 29 | 14 | 36% | −0.18 | **−0.09** | −$1,281 | 15 | `tp-v040-y2022` |
| 2023 | 117 | 91 | 49% | −0.22 | **−0.17** | −$9,977 | 26 | `tp-v040-y2023` |
| 2024 | 162 | 133 | 57% | +0.10 | **+0.08** | +$6,752 | 29 | `tp-v040-y2024` |
| 2025 | 109 | 93 | 55% | +0.00 | **+0.00** | +$233 | 16 | `tp-v040-y2025` |
| **Pooled 2022–25** | **417** | **331** | **53%** | **−0.03** | **−0.02** | **−$4,273** | **86** | `tp-v040-2022-2025` |

All batches: 100% policy ok, 0 audit voids.

## Reconciliation with n30 A/B

Earlier n30 A/B (effR +0.09 / +0.07) sampled **mostly 2024–2025 unique-ticker most-recent dates** — the only non-negative regime. Multi-year full-setup sim shows those years do not overcome 2022–2023 losses.

## Decision

- **No promotion.**  
- **No 0.5.0** without a new structural hypothesis.  
- Bank insight: SMA50 > EMA20 on recent liquid samples, but **not multi-year robust** under this long-only mold.
