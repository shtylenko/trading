# intraday_momentum (letter `m`) — research log

**Thesis:** Market intraday momentum (Gao, Han, Li & Zhou, RFS 2018) — the first
half-hour return predicts the last half-hour return. Long-only, same-day,
hold-into-the-close; documented strongest at the index/sector-ETF level. Chosen as
a **real-world positive control** for the validation pipeline (the synthetic
control already proved the machinery sound — see
`validation/research_log/synthetic_control_results.md`), and as the first of two structural
pivots away from the exhausted single-stock gap mold (next: relax flat-overnight).

Why this is NOT the d04 kill: d04 showed the *opening gap drive* fades after 11:30.
This signal is the *morning return predicting the close* — holding to 15:55 is the
thesis, not a refuted lever.

## Releases

| Release | One-liner | Universe | Status |
|---|---|---|---|
| m01 | P0 baseline: first-30m return > 0 → enter ~10:00, ride to 15:55, stop at morning low | etf_liquid_pit | Stage 0 — KILLED (all-day hold, unfaithful) |
| m02 | faithful Gao r1: first-30m return > 0 → enter ~15:30, hold last half-hour to 15:55 | etf_liquid_pit | Stage 0 — NEGATIVE (gross-negative) |
| m03 | Gao r12: penultimate-half-hour (15:00–15:30) return > 0 → enter ~15:30, hold to 15:55 | etf_liquid_pit | Stage 0 — NEGATIVE (gross-negative) |

## Log

- **2026-06-15 — family created.** m01 baseline + `etf_liquid_pit` universe (26
  liquid ETFs) + `mom_etf_2024_broad` / `mom_etf_smoke_april_2024` testsets.
  Stage-0 plan per EXPLORATION_PLAYBOOK §1b: smoke → unfiltered 2024 baseline R.

- **2026-06-15 — m01 Stage-0 baseline (2024): −206.4R**, 2218 trades, 39.3% win,
  all 4 quarters red. Only large-cap/tech ETFs (SMH/QQQ/XLK) mildly positive. But
  m01 holds 10:00→close (5.5h) — UNFAITHFUL to the effect (Gao: first-half-hour
  predicts *last* half-hour, a 30-min late-session phenomenon). Superseded by m02.

- **2026-06-15 — m02 faithful Stage-0 baseline (2024): −117.1R**, 2155 trades,
  44.2% win, all 4 quarters red (−20/−15/−28/−54). Faithful hold (enter 15:30,
  flatten 15:55; far stop → 2111/2155 TIME_EXIT) HALVED the m01 bleed but is still
  clearly negative. DECISIVE: **negative even GROSS** (avg gross −0.034%/trade,
  sum gross −72%, every quarter negative) — not a cost-drag artifact, the raw
  r1→last-30m continuation is absent/slightly-reversed on these ETFs in 2024. No
  ETF meaningfully positive (best SMH +2.5R). Matches the 5-model consensus
  (intraday momentum decayed post-2018, index-level, weak long-only same-day).

- **2026-06-15 — m03 r12 Stage-0 baseline (2024): −321.3R**, 1910 trades, 39.6%
  win, **gross sum −75%** (gross-negative in Q1/Q3/Q4; only Q2 barely +0.6%). The
  larger R magnitude vs m02 is just the tighter r12-window risk unit — the gross %
  read is the clean signal, and it's negative. Only XLV/XLI marginally positive.

  **FAMILY VERDICT — EXHAUSTED at Stage 0 (2026-06-15).** Both published intraday-
  momentum predictors — first-half-hour (r1, m02) AND penultimate-half-hour (r12,
  m03) — are NEGATIVE EVEN GROSS (before fees/slippage), long-only same-day, on 26
  liquid ETFs in 2024, every/most quarters, no meaningfully positive name. This is
  not a cost-drag artifact and not an unfaithful-construction artifact (m02/m03 are
  faithful to the paper; the far stop → mostly TIME_EXIT, so R measures the
  predicted move). Confirms the 5-model consensus: intraday momentum has decayed
  post-2018 and is an index-level / not-long-only-same-day phenomenon. No broad
  capture spent (correctly — Stage 0 triaged it out). Caveat: 2024 only; not
  re-tested across regimes — but a gross-negative every-quarter result on the
  marquee predictor is sufficient to stop. → pivot to the overnight-premium
  structural change (relax flat-overnight).

## Audit follow-up (2026-06-18 codebase review)

- **L9 — duplicate `_first_half_hour` helper** (`m01.py:64-71`, `m02.py:60-67`).
  Identical module-level function copy-pasted across two releases. Cosmetic only, and
  both files are immutable — if a third m-release ever needs it, lift it into a shared
  `common.py` then rather than re-copying. Family is EXHAUSTED (Stage 0), so this is
  unlikely to matter; noted for completeness.
