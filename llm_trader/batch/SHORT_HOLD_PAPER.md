# Short-hold paper freeze (updated 2026-07-19 after E0)

## E0 causal RVOL audit — **FAIL → track parked**

Peer reviews (Fable/Sol) found full-day RVOL look-ahead. Pre-reg:
`batch/micro_pullback/PREREG_CAUSAL_E0.md`. One-shot re-run with **prior-day RVOL only**:

| | Contaminated (invalid) | **Causal E0** |
|---|---:|---:|
| n | 1102 | **813** |
| effR | +0.029 | **−0.035** |
| years+ | 4/4 | **0/4** |
| Overall | was “PASS” | **FAIL** |

Artifact: `batch/micro_pullback/multiyear_causal/RESULTS.md`

**Per PREREG kill criteria: park liquid short-hold track.** No detector retune.
No capital. Contaminated multi-year / paper books are **not** promotion evidence
(historical only, labeled invalid).

## Prior contaminated books (do not trade)

| Book | Role | Note |
|---|---|---|
| micro paper | was primary | invalidated by E0 |
| VWAP paper | was second | same RVOL leak + morning look-ahead fix in code; not re-promoted |

Structural A/B (NML/portfolio): `batch/admission/structural_ab/RESULTS.md` still
valid for **overlay** conclusions on contaminated entries; not for edge claims.
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
