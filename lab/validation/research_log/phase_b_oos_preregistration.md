# Phase B — Pre-Registration of the Confirmatory 2025 OOS Test

Status: PROPOSED (2026-06-15). **Not yet executed.** This document fixes the rule,
construction, objective, minimum effect size, and binary pass/fail criteria BEFORE
the sealed 2025 data is read for this combo. Spending 2025 is gated on explicit
sign-off. Written per the unanimous peer-review recommendation
(peer-review/2026-06-15-evaluation/) and the Phase-A diagnostics that flipped the
round-1 verdict (a false negative).

## Hypothesis (economic thesis, not a search winner)

A post-gap opening-drive long, admitted only when **the gap is ≥ 3% above the prior
day's high AND the opening 5-minute relative volume is ≥ 1.5×**, has a positive,
cross-regime edge. Thesis: a meaningful (not marginal) gap *confirmed by real
opening participation* is a genuine in-play breakout; gaps without volume fade.

This combo (`gap_floor_3 + rvol_min_1.5`) was the strongest, most stable signal in
the 2022–2024 search: positive every year (2022 +3.5R, 2023 +5.6R, 2024 +31.8R),
selected by leave-one-year-out in 3/3 folds, substitution-robust, broad (tail 0.11–
0.12). It uses neither the contaminated `first_close_pos` nor the sector map;
`opening_rv`'s baseline is prior-sessions-only (leak-free).

## Test data (the one-shot holdout)

- The **2025 rows of the capture ledger** (`validation/_capture_2022_2025.parquet`).
  2025 was captured but NEVER read by the search, walk-forward, PBO, or Phase-A
  diagnostics. This is its first and only use for this combo.
- One shot. If we run it, the result is binding regardless of outcome.

## Construction (deployment-faithful)

- Admit ledger candidates passing the two predicates, then take each day's **top 10
  by gap** (the deployment cap). Score **filled** trades' realized R.
- **Daily-portfolio R** = sum of the day's traded realized R; the daily series spans
  every 2025 opportunity-day (0 on no-trade days). This is the objective the search
  *should* have used (per peer review), so the test matches selection.
- Acknowledged limitation (does NOT change pass/fail): trades are simulated
  independently at 1%/trade with no cross-trade capital/correlation constraint. This
  biases toward optimism, so it makes a PASS harder to trust and a FAIL more
  damning — conservative for a confirmatory gate.

## Pre-specified metrics (report all)

Full-year 2025: trade count, trades/quarter (min), sum R, mean R/trade, daily-
portfolio info ratio (annualized), per-quarter sum R, win rate, top-5 tail share.

## Pass / fail criteria (LOCKED — decided before reading 2025)

**PASS** (all four required):
1. 2025 sum R **> +10 R** (a meaningful, not merely non-negative, edge — the combo
   averaged ~+13.6 R/yr in 2022–2024; the unfiltered baseline was −67 R in 2025).
2. Positive in **≥ 3 of 4** quarters (cross-quarter consistency, not one lucky run).
3. **≥ 20 trades/quarter** every quarter (the meaningfulness floor).
4. Top-5 tail share **< 0.5** (not outlier-driven).

**REVIEW** (manual): sum R in (0, +10R], OR positive but fails the quarter-
consistency or tail test. A genuine-but-weak signal — judged, not auto-promoted.

**FAIL / KILL**: 2025 sum R ≤ 0. The thesis does not survive a clean holdout; the
gap-and-go family is retired with an earned verdict.

## What a PASS buys (and does NOT)

A PASS does **not** auto-deploy. It promotes the combo to a new immutable release
(e.g. `d15`, `gap≥3 + opening-RV≥1.5`) which then runs the **normal evaluation
funnel** (smoke → screen → broad_is) like any release, and only later the separate
sacred 2026 OOS via the existing `--allow-oos` guardrail. The Phase-B test is a
single honest gate — "does the thesis survive one clean holdout at all" — not the
final promotion.

## Alpha-spending note

This spends one confirmatory test on 2025 for ONE pre-registered combo. It is NOT
goalpost-moving: the combo, construction, objective, and pass/fail are fixed here,
before the data is read, and were independently nominated by the Phase-A diagnostics
and all four external reviewers. No further 2025 tests of other combos are budgeted
in this round — a second look would require a fresh pre-registration and would
degrade the holdout.
