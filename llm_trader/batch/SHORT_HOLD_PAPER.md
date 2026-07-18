# Short-hold paper freeze (2026-07-18)

Liquid multi-year track (59 names, 2022–2025). Same packaging for both books:
**portfolio max 3 concurrent / 5 per day; NML OFF.**

| Book | Role | Paper n | Paper effR | years+ | 2× slip | fee2+slip4 | 3× slip |
|---|---|---:|---:|---:|:---:|:---:|:---:|
| **micro_pullback** | **Primary** | 972 | **+0.032** | **4/4** | Y | Y | N |
| **vwap_pullback** | Second | 494 | **+0.026** | 3/4 | Y | N | N |

Artifacts:
- `batch/micro_pullback/paper/PAPER_BOOK.md`
- `batch/vwap_pullback/paper/PAPER_BOOK.md`
- Structural A/B: `batch/admission/structural_ab/RESULTS.md`

## Promotion

- Live size: **no**
- Paper / tiny size: optional; prefer **micro** only if running one book
- Do not enable NML on either
- Do not stack full capital on both without a combined portfolio layer
- Detector retune: stop (freeze)

## Warrior small-cap micro probe (not multi-year)

| | |
|---|---|
| Window | 2025–H1'26 only (current-snapshot float) |
| n | 140 |
| Pooled effR | +0.021 |
| years+ | **1/2 FAIL** (2025 −0.076 / 2026 +0.158) |
| Artifact | `batch/micro_pullback/warrior_probe/RESULTS.md` |

**Do not promote** warrior micro over liquid micro paper book. No PIT float ⇒ no multi-year warrior seal.

## Parked (do not reopen without structural pre-reg)

- `bb_squeeze_long`, multi-day TA scanners (trend / BFP / right_side_v)
- Warrior multi-year micro (blocked on PIT float)
