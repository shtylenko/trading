# Pre-registration — E0 causal screen audit (micro_pullback)

**Committed before code change and before result-producing re-run.**  
**Date:** 2026-07-18  
**Trigger:** Peer reviews (Fable, Sol) — full-day RVOL look-ahead invalidates prior multi-year PASS.

## Scope

| Item | Value |
|---|---|
| Family | `micro_pullback` only (primary repair candidate) |
| Window | 2022-01-01 → 2025-12-31 (same as prior multi-year) |
| Universe | Same 59 liquid tickers as prior VWAP/micro cohort (`/tmp/liquid59.txt` / sealed list) |
| Detector | **Frozen** — impulse / micro-pb / green break rules unchanged |
| Costs | 1 bps fee + 2 bps slip each way; stress grid unchanged |
| Portfolio packaging | Report both raw and portfolio (3 concurrent / 5 day); NML OFF |
| VWAP / BB | Code fixed for same leak class; **no promotion re-run required** this experiment |

## Causal screen change (ONE frozen definition)

**Old (invalid):**  
`rvol = day_volume / avg_vol` where `day_volume` is **completed session volume** and avg is prior 20 days. Used to admit intraday entries — look-ahead.

**New (causal):**  
```
avg_vol_t = mean(volume_{t-20} … volume_{t-1})   # already shift(1).rolling(20)
rvol_t    = volume_{t-1} / avg_vol_t              # prior-day volume only
```
Keep threshold `rvol_min = 1.2` (same number; different definition).  
Gap, price band, avg_vol min **unchanged**.

No other detector parameter may change in this experiment.

## Gates (kill criteria) — one shot

| Gate | Criterion |
|---|---|
| 1 | Pooled effR > 0 |
| 2 | ≥2 of 4 years with effR > 0 |
| **Kill** | Fail either gate → park entire liquid short-hold track (no further detector retune) |
| Soft note | Day-cluster bootstrap CI reported if feasible; not a hard gate this run |

A pass at **half** the prior contaminated effR still counts as pass (per Fable).  
**Not success:** changing rvol_min / impulse / pb rules after seeing results; subset shopping; fee2+slip4-on-paper ranking.

## What this is / is not

- **Is:** integrity audit of day selection causality.  
- **Is not:** new strategy version for edge hunting; not live promotion; not warrior re-run.

## Outputs

- `batch/micro_pullback/multiyear_causal/RESULTS.md` (+ json)  
- `batch/micro_pullback/multiyear_causal/PAPER_BOOK.md` (portfolio pack)  
- Construction tag in features: `v0.1.0_micro_pullback_causal_e0`

## Post-result policy

| Outcome | Action |
|---|---|
| PASS gates | Candidate for null models + forward shadow only; still no capital |
| FAIL gates | Close liquid short-hold track; keep parks; bank negative integrity result |
