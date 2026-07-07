# Codex Peer Review Feedback: Session Metrics Proposal

**Date:** 2026-07-06  
**Reviewer:** Codex  
**Target:** `llm_trader/peer_reviews/2026-07-06-session-metrics/proposal.md`  
**Status:** Review complete

---

## Summary

The proposal is directionally sound and worth implementing, especially the shift toward R-normalized expectancy, profit factor, distributions, void rate, and repeat consistency. The largest implementation risk is metric definition drift: the current code is careful that top-level counts are over leaf sessions, not fills, while the proposal sometimes says to aggregate `actions.json` fill deltas. For strategy comparison, the atomic unit should be one finalized leaf run / setup, not one blotter fill.

Recommended first milestone: add a backend-only aggregate metrics helper, expose it from `get_top_session_view`, add JSON report output, and defer most UI work until the definitions settle.

---

## Findings

### 1. Expectancy and profit factor should be computed from leaf outcomes, not fill deltas

Proposal lines 93 and 97-99 suggest aggregating `realized_delta` from `actions.json`. That will distort results for scaled trades because buys have `realized_delta = 0`, partial sells split one trade's outcome across multiple rows, and forced exits add another row. The current recorder already treats `n_trades` and win rate as finalized leaf sessions, not fills, in `list_sessions` and `get_top_session_view`.

Recommendation:

- For batch/top-level metrics, use one observation per leaf session: `pnl.r_multiple`, `pnl.r_multiple_actual`, and `pnl.realized_pnl`.
- Compute `expectancy_r = mean(r_multiple)` over traded, non-void leaves.
- Compute `profit_factor = sum(max(r, 0)) / abs(sum(min(r, 0)))` over leaf R outcomes, plus a dollar variant from `realized_pnl`.
- Keep fill-level stats only for behavior metrics such as `avg_fills_per_trade`, scale frequency, and churn.

This should be a hard definition in the spec because otherwise the UI, CLI report, and future compare view will disagree.

### 2. Batch drawdown needs a synthetic ordering policy, not just per-bar equity

Proposal lines 109-113 define MDD from realized plus marked unrealized timeline values. That works for a single leaf, but a batch is a collection of independent replay sessions, often run in parallel and potentially repeated on the same setup. There is no real portfolio clock unless the system chooses one.

Recommendation:

- Leaf metric: `max_adverse_excursion_r` or `max_open_drawdown_r` from the decision timeline during that one trade.
- Batch metric: `max_sequence_drawdown_r` from cumulative finalized leaf R values in a deterministic order.
- Make the ordering explicit: preferably testset order, then repeat index, then ticker/date. Do not use wall-clock `real_run_ts`, because parallel execution order is incidental.
- Name it `sequence_drawdown_r` unless a true portfolio simulation with overlapping capital is added.

Calmar should stay deferred. A non-annualized `recovery_factor_r = total_r / abs(sequence_drawdown_r)` is clearer for this test harness.

### 3. Void handling must be part of ranking, not only a side metric

The proposal correctly highlights void rate, but implementation needs to avoid survivorship bias. Current `report_by_version` excludes voids from P&L/R/win calculations. That is useful for diagnosing clean runs, but a leaderboard that ranks only clean traded leaves could favor a model that voids difficult sessions.

Recommendation:

- Report two versions of key metrics:
  - `clean_expectancy_r`: traded, non-void leaves only.
  - `effective_expectancy_r`: all planned setups, with stood-down = `0R` and voids penalized by a configured value such as `-1R`.
- Always show denominator fields: `n_planned`, `n_complete`, `n_traded`, `n_stood_down`, `n_void`.
- For ranking, use effective metrics or a visible composite penalty such as `clean_expectancy_r * clean_run_rate`.

### 4. SQN is useful, but should be gated and labeled cautiously

Proposal lines 122-126 are reasonable, but SQN can look precise when the sample is small. The default testset mentioned in `COMMANDS.md` is 30 setups, and repeats can make N look larger without adding independent market examples.

Recommendation:

- Compute SQN only on independent setup outcomes by default.
- If repeats are included, expose both `sqn_setups` and `sqn_runs`, or mark repeated observations as repeated.
- Return `null` for `N < 10`; show a warning for `10 <= N < 30`; treat `N >= 30` as acceptable for comparison but still not conclusive.
- Use sample standard deviation. If standard deviation is zero, return `null` plus a reason instead of infinity.

### 5. Store aggregate metrics at the top-session/report layer first

Proposal lines 195-197 leave open whether to enrich `pnl.json` or add `metrics.json`. Since top-level sessions have no dedicated directory today and are grouped by `session`/`batch`, top-level aggregate metrics cannot naturally live beside a top-level `session.json` unless the project introduces a group artifact directory.

Recommendation:

- Add pure helper functions in `recorder.py` first, e.g. `_leaf_metric_row(sdir, session, pnl)` and `_aggregate_metric_rows(rows)`.
- Return `metrics` from `get_top_session_view(sess_id)`.
- Include the same aggregate fields in `list_sessions()` and `report_by_version(..., format=json)`.
- Keep per-leaf `pnl.json` changes minimal at first, adding only fields that are truly leaf-local.
- Introduce persisted top-level `metrics.json` later only if performance or export requirements demand it.

### 6. Some proposed LLM metrics require data the artifacts do not currently capture

Cost/token efficiency, reasoning complexity, tool-call correctness, and repeat consistency are good ideas, but they need stable inputs. Current artifacts include decisions and thoughts, but not token counts, model pricing, command traces, audit failure reasons, or repeat grouping in a normalized schema.

Recommendation:

- First add low-cost behavior metrics derivable from current artifacts:
  - `avg_bars_held`
  - `avg_fills_per_traded_leaf`
  - `forced_exit_rate`
  - `stand_down_rate`
  - `entry_latency_bars`
  - `stop_missing_on_entry_rate`
  - `stop_widening_events` where stop snapshots are available
- Add token/cost metrics only after batch metadata records provider, model, input tokens, output tokens, and price table/version.
- Add repeat consistency only if batch metadata stores setup identity and repeat index explicitly.

---

## Prioritized Metric Set

For the first implementation pass, I would ship these 7:

1. `expectancy_r`: mean final R per traded, non-void leaf.
2. `effective_expectancy_r`: mean R over planned setups with stood-down = `0R` and void = configured penalty.
3. `profit_factor_r`: gross positive leaf R divided by absolute gross negative leaf R.
4. `median_r` plus `p10_r` / `p90_r`: distribution visibility without overfitting to a mean.
5. `sequence_drawdown_r` and `recovery_factor_r`: deterministic batch-sequence risk proxy.
6. `void_rate`, `stand_down_rate`, `forced_exit_rate`: reliability and discipline.
7. `avg_mfe_capture_winners` and `avg_bars_held`: management quality.

SQN is valuable, but I would ship it in the second pass after the denominator and repeat semantics are nailed down.

---

## Formula Recommendations

Use these as exact backend definitions:

```text
clean_rows = complete leaves where not void and pnl.traded
planned_rows = every leaf expected by the batch metadata if available, else every member leaf

expectancy_r = mean(row.r_multiple for row in clean_rows)
expectancy_actual_r = mean(row.r_multiple_actual for row in clean_rows where not null)

profit_factor_r =
  sum(r for r in clean_rows if r > 0) / abs(sum(r for r in clean_rows if r < 0))
  null if there are no losses

payoff_ratio_r =
  mean(r for r in clean_rows if r > 0) / abs(mean(r for r in clean_rows if r < 0))
  null unless at least one win and one loss

effective_r(row):
  void -> -1.0 by default
  stood_down -> 0.0
  traded -> row.r_multiple

effective_expectancy_r = mean(effective_r(row) for row in planned_rows)

sequence_drawdown_r =
  max peak-to-trough decline of cumulative effective_r in deterministic testset order

recovery_factor_r =
  total_effective_r / abs(sequence_drawdown_r)
  null if sequence_drawdown_r == 0
```

For UI display, show both budget R and actual R on leaf detail. For top-level comparison, budget R should be primary because it captures the skill's sizing discipline against the configured risk budget; actual R can be a secondary diagnostic.

---

## UI Feedback

The proposed UI sections are useful, but the first version should be compact:

- Top-session header: PnL, effective expectancy R, clean expectancy R, profit factor, win rate, void rate, N.
- One expandable analytics panel: R histogram, sequence equity line in R, reliability counts.
- Ticker table: add `R`, `mfe_capture`, `fills`, and `forced_exit`, but avoid more than 3-4 new default columns.
- Leaf view: do not show SQN or batch-only metrics; show the leaf's R, MFE capture, MAE/open drawdown, bars held, and parent batch contribution.

Avoid hard green/red benchmark badges for SQN/PF until enough local baseline data exists. Early thresholds should be text labels or tooltips, not ranking logic.

---

## Implementation Path

1. Add tested pure metric helpers in `recorder.py`.
2. Teach `get_top_session_view()` to return a `metrics` object.
3. Extend `report_by_version()` JSON output with the same fields; keep the table modest.
4. Add tests for no trades, all wins, all losses, voids, stood-down rows, repeated setups, and zero variance.
5. Add the compact viewer panel once backend definitions are stable.
6. Only then consider persisted `metrics.json` and compare/leaderboard routes.

---

## Bottom Line

Accept the proposal with revisions. The most important change is to define the observation unit as a finalized leaf run for performance metrics, reserve `actions.json` for execution-behavior metrics, and introduce effective metrics that penalize voids. With that adjustment, this will make skill-version and model comparisons much more reliable without weakening the existing deterministic recorder design.
