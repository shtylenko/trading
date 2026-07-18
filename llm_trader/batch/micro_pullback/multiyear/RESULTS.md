# Micro-pullback short-hold multi-year (v0.1.0)

**Universe:** 59 liquid large-caps (same cohort as VWAP multi-year). **Window:** 2022–2025.
**Method:** 5m RTH path sim (entry next open after green break of micro-pb high; stop / 1R-half / 2R / EOD).
**Costs:** 1 bps fee + 2 bps slip each way.
**Pattern:** Ross/warrior phase-2 — morning impulse → 1–3 bar shallow VWAP-held pullback → first green break.

## Gates (same bar as other families)

| Gate | Result |
|---|---|
| Pooled effR > 0 | **PASS** (+0.0292) |
| ≥2 of 4 years > 0 | **PASS** (4 of 4) |
| **Overall** | **PASS** |

**Pooled:** n=1102 · win% 46.2 · **effR +0.0292** · pnl $+3,214
**Exits:** STOP 583 · TARGET2 380 · EOD 139 (T1 is scale-half, not full exit)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 290 | 44.5 | **+0.0396** | $+1,148 |
| 2023 | 294 | 49.0 | **+0.0270** | $+795 |
| 2024 | 263 | 47.5 | **+0.0332** | $+874 |
| 2025 | 255 | 43.5 | **+0.0156** | $+398 |

## Cost stress

See `COST_STRESS.md`. Summary:

| Scenario | slip | effR | pass |
|---|---:|---:|:---:|
| baseline (1f+2s) | 2 | **+0.029** | Y |
| 2× slip | 4 | **+0.010** | Y |
| 3× slip | 6 | **-0.010** | N |
| fee2+slip4 | 4 | **-0.000** | N |

## Caveats

- Edge is **small** (~3¢ per $1 risk). Sensitive to costs/slippage.
- Liquid large-caps only — not warrior small-cap gappers (no multi-year float).
- Offline 5m sim ≠ sealed 1m LLM batch path.
- Stronger year breadth than VWAP (4/4 vs 3/4) on same universe.

## Verdict

Multi-year gate **PASS** at baseline; **cost-fragile** (2× slip barely; 3× fail).
**Research / paper-optional** — same promotion bar as VWAP. Prefer over BB squeeze
(which failed) as a second short-hold idea alongside VWAP; do not stack full capital
on both without portfolio rules.

