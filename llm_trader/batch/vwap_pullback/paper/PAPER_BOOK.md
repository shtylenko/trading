# VWAP pullback paper book (`vwap_pullback_paper_book_v0.1.0`)

**Status:** research_paper_optional
**Completed:** 2026-07-18T23:31:35+00:00

## Packaging

- NML gate: **OFF** (structural A/B reject)
- Portfolio: `{'max_concurrent': 3, 'max_per_day': 5, 'version': 'port_v0.1.0'}`
- Costs: fee=1.0 bps + slip=2.0 bps each way
- Risk budget / trade: $100.0

## Gates (paper book)

| | Raw (ungated sim) | Paper (portfolio) |
|---|---:|---:|
| n | 506 | 494 |
| win% | 46.8 | 47.2 |
| effR | +0.0236 | **+0.0256** |
| pnl | $+1,194 | **$+1,267** |
| years+ | 3/4 | **3/4** |
| pass | True | **True** |

Portfolio skipped: **12** candidates

### By year (paper)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 130 | 45.4 | +0.0336 | $+437 |
| 2023 | 136 | 50.7 | +0.0261 | $+354 |
| 2024 | 110 | 42.7 | -0.0059 | $-65 |
| 2025 | 118 | 49.2 | +0.0458 | $+540 |

## Cost stress (re-sim taken set; no re-portfolio)

| Scenario | fee | slip | n | win% | effR | pass |
|---|---:|---:|---:|---:|---:|:---:|
| `baseline_1f_2s` | 1.0 | 2.0 | 494 | 47.2 | +0.0256 | Y |
| `slip_2x` | 1.0 | 4.0 | 494 | 47.2 | +0.0061 | Y |
| `slip_3x` | 1.0 | 6.0 | 494 | 47.0 | -0.0134 | N |
| `fee2_slip4` | 2.0 | 4.0 | 494 | 47.2 | -0.0037 | N |
| `fee2_slip6` | 2.0 | 6.0 | 494 | 47.0 | -0.0231 | N |
| `fee5_slip5` | 5.0 | 5.0 | 494 | 46.2 | -0.0426 | N |

## Promotion bar

Thin multi-year edge under portfolio packaging; more cost-fragile than micro_pullback. Do not live-size. NML gate remains OFF (A/B hard fail).

- Live size: **no**
- Paper / tiny size: optional if operator accepts cost fragility
- Detector retune: **no** (edge is structural packaging only)

Full trade list: `PAPER_BOOK.json` (`trades` array, n=494).

