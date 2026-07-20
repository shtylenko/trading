# Opp B selection A/B — inplay_continuation

**Pre-reg:** `batch/inplay_continuation/PREREG_OPPB_SELECTION.md`
**Base sealed n:** 87
**WeBull:** slip 15 baseline / 30 stress; no detector retune

## Gates

| Gate | Result |
|---|---|
| `select_A` both years > 0 & pooled > 0 @15 | **PASS** |
| Any soft winner (both years) | **YES** ['select_A', 'select_A_shallow', 'select_A_first'] |
| `select_A` slip30 not catastrophe | **PASS** |
| **Primary pass** | **PASS** |

## Variants @ slip 15

| Variant | n | win% | effR | 2025 | 2026 | both+ | primary |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| `baseline` | 87 | 41.4 | +0.0756 | -0.123 | +0.288 | N | N |
| `morning_only` | 35 | 40.0 | +0.0036 | -0.223 | +0.244 | N | N |
| `gap_band` | 56 | 42.9 | +0.0934 | -0.010 | +0.213 | N | N |
| `rvol_strict` | 51 | 37.3 | +0.0456 | -0.359 | +0.466 | N | N |
| `shallow_pb` | 42 | 42.9 | +0.0938 | -0.032 | +0.198 | N | N |
| `first_per_day` | 68 | 41.2 | +0.0903 | -0.119 | +0.287 | N | N |
| `select_A` | 15 | 46.7 | +0.2707 | +0.014 | +0.399 | Y | Y |
| `select_A_shallow` | 11 | 45.5 | +0.2329 | +0.096 | +0.311 | Y | Y |
| `select_A_first` | 14 | 42.9 | +0.1902 | +0.014 | +0.288 | Y | Y |

## Slip 30 (catastrophe check)

| Variant | n | effR | > −0.05 |
|---|---:|---:|:---:|
| `baseline` | 87 | -0.0134 | Y |
| `morning_only` | 35 | -0.0728 | N |
| `gap_band` | 56 | -0.0130 | Y |
| `rvol_strict` | 51 | -0.0284 | Y |
| `shallow_pb` | 42 | +0.0019 | Y |
| `first_per_day` | 68 | +0.0005 | Y |
| `select_A` | 15 | +0.1764 | Y |
| `select_A_shallow` | 11 | +0.1332 | Y |
| `select_A_first` | 14 | +0.0955 | Y |

## Verdict

**KEEP `select_A` provisionally** as research admission `v0.1.1` candidate (still **no live capital**).

### Honesty constraints (do not skip)
- **n=15** is tiny — both-years+ can be luck; treat as **hypothesis**, not edge proof.
- Stacked filters on n=87 after seeing Opp C year split is still one campaign; need **forward** confirmation.
- Slip30 for `select_A` must stay non-catastrophic (see table).
- **Do not** add more filters on this sample.
- **Do not** trade WeBull size on n=15.

### Next (only)
1. Freeze `select_A` into detector/admission code as v0.1.1  
2. Forward shadow log (zero capital) on new days only  
3. Or Opp E boring baseline as scoreboard  

---

## `select_A` definition (frozen)

`time_et < 11:00` **and** `5% ≤ gap ≤ 15%` **and** `prior-day rvol ≥ 3.0`

