# Micro-pullback warrior-universe probe (`micro_pullback_warrior_probe_v0.1.0`)

**Status:** research_paper_optional

## Probe caveats (read first)

- Contract: `micro_pullback_warrior_probe_v0.1.0`
- **Float is current snapshot, not PIT** — same limit as warrior SPEC
- Window: 2025-01-01 → 2026-06-30
- Screen: price $2.0–20.0, gap≥5.0%, rvol≥2.0, float<20M
- Detector: same micro_pullback 5m rules as liquid book
- This does **not** replace liquid multi-year PASS; separate universe
**Completed:** 2026-07-18T23:36:11+00:00

## Packaging

- NML gate: **OFF** (structural A/B reject)
- Portfolio: `{'max_concurrent': 3, 'max_per_day': 5, 'version': 'port_v0.1.0'}`
- Costs: fee=1.0 bps + slip=2.0 bps each way
- Risk budget / trade: $100.0

## Gates (paper book)

| | Raw (ungated sim) | Paper (portfolio) |
|---|---:|---:|
| n | 140 | 140 |
| win% | 44.3 | 44.3 |
| effR | +0.0208 | **+0.0208** |
| pnl | $+291 | **$+291** |
| years+ | 1/2 | **1/2** |
| pass | False | **False** |

Portfolio skipped: **0** candidates

### By year (paper)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2025 | 82 | 41.5 | -0.0763 | $-626 |
| 2026 | 58 | 48.3 | +0.1580 | $+916 |

## Cost stress (re-sim taken set; no re-portfolio)

| Scenario | fee | slip | n | win% | effR | pass |
|---|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 140 | 44.3 | +0.0208 | N |
| `slip_2x` | 1.0 | 4.0 | 140 | 42.9 | +0.0124 | N |
| `slip_3x` | 1.0 | 6.0 | 140 | 42.1 | +0.0044 | N |
| `fee2_slip4` | 2.0 | 4.0 | 140 | 42.9 | +0.0083 | N |
| `fee2_slip6` | 2.0 | 6.0 | 140 | 42.1 | +0.0002 | N |
| `fee5_slip5` | 5.0 | 5.0 | 140 | 42.1 | -0.0081 | N |

## Promotion bar

Warrior-universe probe only (current-snapshot float). Not multi-year sealed. Do not promote to liquid multi-year bar.

- Live size: **no**
- Paper / tiny size: optional if operator accepts cost fragility
- Detector retune: **no** (edge is structural packaging only)

Full trade list: `PAPER_BOOK.json` (`trades` array, n=140).

