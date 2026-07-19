# Micro-pullback paper book (`micro_pullback_paper_book_v0.1.0`)

**Status:** research_paper_optional
**Completed:** 2026-07-19T00:41:32+00:00

## Packaging

- NML gate: **OFF** (structural A/B reject)
- Portfolio: `{'max_concurrent': 3, 'max_per_day': 5, 'version': 'port_v0.1.0'}`
- Costs: fee=1.0 bps + slip=2.0 bps each way
- Risk budget / trade: $100.0

## Gates (paper book)

| | Raw (ungated sim) | Paper (portfolio) |
|---|---:|---:|
| n | 813 | 729 |
| win% | 38.0 | 38.0 |
| effR | -0.0345 | **-0.0355** |
| pnl | $-2,801 | **$-2,591** |
| years+ | 0/4 | **0/4** |
| pass | False | **False** |

Portfolio skipped: **84** candidates

### By year (paper)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 202 | 35.1 | -0.0465 | $-940 |
| 2023 | 171 | 43.9 | -0.0089 | $-152 |
| 2024 | 167 | 40.1 | -0.0050 | $-83 |
| 2025 | 189 | 33.9 | -0.0749 | $-1,416 |

## Cost stress (re-sim taken set; no re-portfolio)

| Scenario | fee | slip | n | win% | effR | pass |
|---|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 729 | 38.0 | -0.0355 | N |
| `slip_2x` | 1.0 | 4.0 | 729 | 37.6 | -0.0550 | N |
| `slip_3x` | 1.0 | 6.0 | 729 | 37.2 | -0.0745 | N |
| `fee2_slip4` | 2.0 | 4.0 | 729 | 37.3 | -0.0647 | N |
| `fee2_slip6` | 2.0 | 6.0 | 729 | 36.9 | -0.0842 | N |
| `fee5_slip5` | 5.0 | 5.0 | 729 | 36.4 | -0.1037 | N |

## Promotion bar

Thin multi-year edge under portfolio packaging; cost-fragile (see stress). Do not live-size. NML gate remains OFF.

- Live size: **no**
- Paper / tiny size: optional if operator accepts cost fragility
- Detector retune: **no** (edge is structural packaging only)

Full trade list: `PAPER_BOOK.json` (`trades` array, n=729).

