# Micro-pullback paper book (`micro_pullback_paper_book_v0.1.0`)

**Status:** research_paper_optional
**Completed:** 2026-07-18T23:27:31+00:00

## Packaging

- NML gate: **OFF** (structural A/B reject)
- Portfolio: `{'max_concurrent': 3, 'max_per_day': 5, 'version': 'port_v0.1.0'}`
- Costs: fee=1.0 bps + slip=2.0 bps each way
- Risk budget / trade: $100.0

## Gates (paper book)

| | Raw (ungated sim) | Paper (portfolio) |
|---|---:|---:|
| n | 1102 | 972 |
| win% | 46.2 | 46.5 |
| effR | +0.0292 | **+0.0315** |
| pnl | $+3,214 | **$+3,065** |
| years+ | 4/4 | **4/4** |
| pass | True | **True** |

Portfolio skipped: **130** candidates

### By year (paper)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 255 | 45.5 | +0.0436 | $+1,111 |
| 2023 | 247 | 50.2 | +0.0319 | $+787 |
| 2024 | 229 | 47.6 | +0.0394 | $+903 |
| 2025 | 241 | 42.7 | +0.0110 | $+264 |

## Cost stress (re-sim taken set; no re-portfolio)

| Scenario | fee | slip | n | win% | effR | pass |
|---|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 972 | 46.5 | +0.0315 | Y |
| `slip_2x` | 1.0 | 4.0 | 972 | 46.1 | +0.0120 | Y |
| `slip_3x` | 1.0 | 6.0 | 972 | 45.7 | -0.0075 | N |
| `fee2_slip4` | 2.0 | 4.0 | 972 | 46.0 | +0.0022 | Y |
| `fee2_slip6` | 2.0 | 6.0 | 972 | 45.4 | -0.0173 | N |
| `fee5_slip5` | 5.0 | 5.0 | 972 | 44.8 | -0.0369 | N |

## Promotion bar

Thin multi-year edge under portfolio packaging; cost-fragile (see stress). Do not live-size. NML gate remains OFF.

- Live size: **no**
- Paper / tiny size: optional if operator accepts cost fragility
- Detector retune: **no** (edge is structural packaging only)

Full trade list: `PAPER_BOOK.json` (`trades` array, n=972).

