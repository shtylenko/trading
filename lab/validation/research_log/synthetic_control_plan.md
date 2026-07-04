# Implementation Plan — Synthetic Dose-Response Positive Control

Status: PROPOSED (2026-06-15). Build only after sign-off. Purpose: prove the
validation pipeline has **detection power** (can confirm a true edge) and
**false-positive control** (rejects pure noise), and **calibrate** whether the
DSR ≥ 0.95 / PBO gates are appropriate for the intraday Sharpe scale. Motivated by
the unanimous 5-model recommendation (peer-review/2026-06-15-positive-control/).

## 1. What it tests (and what it does NOT)

- **Tests:** search → LOO walk-forward → PBO → DSR → sealed-year **stats/selection
  machinery** (pipeline stages 2–5), on the capture ledger.
- **Does NOT test:** the capture/feature engine (stage 1) or the execution engine
  (stage 6) — those were validated separately (feature tests; the d15 engine
  cross-check). Nor does it test whether the search can find edges *outside* the
  pre-registered grid (a known, separate limitation). State these in the output.

## 2. The injection (ground truth)

Reuse the **real** capture ledger (`_capture_2022_2025.parquet`) — real features,
dates, tickers, `score` (gap), `filled` flag — and **superimpose a known edge on
the real `realized_r`** of filled trades:

```
realized_r_synth(i) = realized_r_real(i) + m · 1{ opening_rv(i) ≥ 1.5 }
```

- **Why add to real R rather than synthesize noise:** it preserves the true return
  distribution (fat tails, autocorrelation, regime structure) and the real
  cross-sectional/temporal dependence. The **null (m = 0) is literally the real
  ledger** — which we know the pipeline KILLS — so the null is a perfect, free
  false-positive control. Increasing `m` superimposes a *known* edge on real noise.
  Deterministic given `m` (no RNG, fully reproducible).
- **Why `opening_rv ≥ 1.5`:** it's a real, leak-free feature AND it aligns exactly
  with a grid predicate (`rvol_min_1_5`), so a working search MUST recover it. This
  makes "did it find the right filter?" a crisp check.
- **Leak-free:** `opening_rv` is known at 09:35 (prior-session baseline), so a world
  where it predicts R is legitimate — no look-ahead introduced.
- Injected into **all years incl. sealed 2025** — legitimate for a synthetic world
  (the recipe is frozen here, pre-run); the sealed-year step then tests that the
  WF-selected combo also pays in 2025-synthetic (i.e. the WF→OOS plumbing is sound,
  no structural break/leak).

## 3. Dose-response sweep (the power curve)

Frozen dose grid, per-trade mean edge on the good subset:

```
m ∈ { 0.00 (NULL), 0.02, 0.05, 0.10, 0.20 }   R per qualifying trade
```

For each `m`, run the **full** pipeline and record:
1. **winning combo** — does the search recover `rvol_min_1_5` (or a combo containing
   it)? (discovery)
2. **WF** — LOO aggregate sumR, positive folds, pass/fail
3. **PBO** (with embargo)
4. **DSR** of the pooled winner + the implied daily-portfolio Sharpe of the planted
   subset (so the dose is interpretable on a Sharpe scale)
5. **sealed-2025-synth** — the WF-selected combo's R on injected 2025 (confirmation)
6. **overall verdict** (PROMOTE / REVIEW / NO-EDGE) from the canonical gates

Output = a dose → gates table. Expected shape:
- `m = 0`: NO-EDGE (reproduces the real kill). ← false-positive control passes.
- `m` rising: WF flips positive, PBO drops, **DSR crosses 0.95 at some m\***, sealed
  year passes. `m\*` = the **minimum detectable edge** and its Sharpe = the
  pipeline's sensitivity floor.

## 4. Robustness checks (cheap, deterministic)

- **Right-feature recovery:** repeat at one moderate `m` planting the edge on a
  *different* grid feature (e.g. `price_min_10` or `spy_weak_regime`) and confirm
  the search recovers THAT feature, not `rvol` — proves it isn't just always
  picking rvol.
- **(Optional) synthetic-noise Monte Carlo:** a variant that replaces real noise
  with fat-tailed (Student-t, df≈4) draws over N seeds, reporting pass-RATE per
  dose. Deferred unless the deterministic run is ambiguous.

## 5. Interpretation → action (decided before the run)

- **Null rejected AND signal passes at a modest `m` (Sharpe ≈ 1)** → validator is
  sound; prior kills are trustworthy; the regime is just thin. Record `m\*`.
- **Signal fails even at large `m` (Sharpe ≳ 1.5)** → gates are over-conservative
  for the horizon. Identify the binding gate (almost certainly DSR threshold or the
  effective-trials estimate) and **propose** a recalibration — do NOT silently
  change it; surface the number and the rationale, then re-run.
- **Null PASSES (pure real ledger blessed as an edge)** → a false-positive bug;
  stop and debug the gates.

## 6. Build (the actual work)

- **`scripts/synthetic_control.py`** — one script that:
  1. loads the real ledger once,
  2. for each dose `m`: builds `realized_r_synth`, then calls the **existing**
     `feature_search` functions in-process (`enumerate_combos`, `daily_portfolio`,
     `walk_forward`, `build_perf_matrix`, `pbo_from_matrix`, `deflated_sharpe_ratio`,
     `effective_n_trials`) — no shelling out, no DB writes,
  3. runs the sealed-2025-synth check on the WF-selected combo,
  4. prints the dose-response table + the `m\*` / Sharpe-floor readout, and the
     gate-calibration verdict.
- Reuses everything; ~one new file, no engine changes. Fast (offline subset scans).
- **Tests** (`tests/test_synthetic_control.py`): injection is deterministic;
  `m = 0` reproduces the real ledger's R exactly; a large `m` makes the rvol combo
  the pooled winner and passes WF. Keep light.
- No changes to `feature_search.py`/`cscv.py`/`deflated_sharpe.py` unless step 5
  concludes a gate needs recalibration (separate, signed-off change).

## 7. Open decisions to confirm before building

1. **Planted feature = `opening_rv ≥ 1.5`** (grid-aligned). OK, or prefer another?
2. **Real-noise additive injection** (deterministic) vs synthetic-noise + MC seeds.
   Recommend real-noise as primary; MC optional.
3. **Dose grid** `{0, 0.02, 0.05, 0.10, 0.20}` R/trade. OK?
4. **Inject into sealed 2025 too** (needed to test WF→OOS plumbing). OK?
5. **Gate recalibration is proposal-only** (no silent change). OK?
