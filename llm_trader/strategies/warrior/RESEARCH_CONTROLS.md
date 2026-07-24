# Warrior research controls

## What historical results mean

Every existing Warrior historical scanner/replay panel is **exploratory only**.
The low-float gate was computed from a retrieval-time yfinance snapshot; it can
also fall back to `sharesOutstanding`. Neither value is a point-in-time float
for the historical market date. Historical P&L may be used to test plumbing,
execution accounting, and failure modes, but it must not be used to select,
promote, or estimate the edge of a strategy version.

The daily-screen field historically named `rvol` is now described precisely as
`prior_day_volume_ratio`: previous full-day volume divided by the trailing
baseline. It is causal for the following session but is not an intraday RVOL
signal. Breakout-bar volume receives its own availability flag.

## Retired panels

These panels have been inspected/tuned/replayed and are permanently spent for
model selection or holdout claims:

- `batch/warrior/testset_100u.json` and `testset_100.json` — development.
- `batch/warrior/testset_5x_holdout_27.json` — former holdout, subsequently
  reused during v5 iteration.
- `batch/warrior/testset_5x_causal_oos_12.json` — causal-wiring smoke only;
  its one trade is not out-of-sample validation.
- `batch/warrior/testset-DRUG-2024-10-15.json`, `testset_mini.json`, and
  `testset_isolation_smoke_10u.json` — implementation/isolation smoke panels.

No threshold, pattern-score weight, entry cutoff, or exit rule may be chosen
from any of these outcomes.

## Frozen forward-shadow protocol

1. Before the market scan, choose a ledger path and a calendar end date. Do not
   inspect or tune version rules until the window closes.
2. Run the scanner with `--forward-shadow-ledger <path>`. The append-only JSONL
   ledger records every daily-gap candidate, prior-day-volume inputs, a forced
   float retrieval source/fallback/timestamp, float gate result, and a content
   hash.
3. Retain raw minute bars and the selected skill hash for each ledger candidate.
   Run the deterministic policy in shadow mode with v5.14's completed-bar /
   next-open contract; record fills and rejects, including open-at-stop rejects.
4. Pre-specify the cohort, execution/slippage assumptions, success metrics, and
   stop date. Review results only after the frozen window completes.
5. A forward ledger is necessary but not sufficient: its float is
   contemporaneously captured, not a vendor-certified historical float. Label
   its research tier `forward_shadow_pending_outcomes` until the outcome window
   and audit are complete.

## v5.14 execution contract

The scanner event for a left-labelled `09:35` five-minute candle becomes known
only after the `09:39` one-minute close. v5.14 begins watching then; it does not
manufacture an entry. A later qualifying candle-pattern trigger queues
`ENTER_NEXT_OPEN`, whose earliest fill is the following minute's open after
adverse slippage/capacity. It cancels an entry that opens at or below its
structural stop. Same-close confirmation fills are prohibited.
