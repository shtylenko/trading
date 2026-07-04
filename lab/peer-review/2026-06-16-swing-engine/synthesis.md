# Peer-review synthesis — swing engine (codex / deepseek / gemini + claude)

Reconciled 2026-06-16. Governing lens: this is an ENGINE CROSS-CHECK whose job is to
**faithfully reproduce the offline multi-day ledger**, not to be the most realistic
backtest possible. So the key question for each finding is "does it make the engine
DIVERGE from the offline, or is it shared by both?" Findings shared by both don't block
the cross-check (they're real caveats already carried by the offline result).

## Unanimous / clear

- **Cost-model mismatch.** Offline = flat 10 bps round-trip; engine default ≈5 bps.
  ALL reviewers + claude. **ACTION:** run with `ExecutionConfig(entry_slippage_bps=5,
  exit_slippage_bps=5, fees_bps_per_side=0)` = exactly 10 bps baked in. Also capture a
  gross run for reference.
- **No selection look-ahead.** codex + deepseek confirm the `<= rebal_ts` slice and the
  momentum index `c.iloc[-22]/c.iloc[-253] == close[d-21]/close[d-252]`. ✓
- **Rebalance-phase sensitivity.** All: offline `all_days[::20]` vs engine
  `trading_days[::20]` can shift the grid → ±0.5–1.5% annualized. Not a bug; the single
  most likely source of a benign divergence. **ACTION:** log the engine's exact
  rebalance dates so any gap is attributable, not mysterious.

## ACTIONED code fixes (improve faithfulness or robustness)

1. **Liquidity fail-open (codex).** x01 skipped the $-vol filter if `volume` missing and
   passed on NaN dvol. Fixed to fail CLOSED (require finite volume + dvol, NaN-safe `>=`).
   This also tightens the match to the offline (which dropped NaN dollar-vol rows).
2. **Drop intraday-tuned funnel auto-eval (codex + claude).** Swing runner now calls
   `summarize_run` (populates release_metrics for the dashboard) but NOT
   `_auto_evaluate_lifecycle` — the funnel gates are per-trade-R intraday thresholds and
   would mislabel a 20-day book. Funnel placement for swing is manual.

## Real concerns that are SHARED with the offline → not cross-check blockers (documented)

- **Survivorship via silent end-of-data drops (gemini #1, claude #3).** `i+H >= len(bars)
  → None` drops a name whose series ends mid-hold (delisting). REAL survivorship
  optimism — BUT (a) `liquid_pit` is built from currently-active assets, so since-delisted
  names are mostly absent from the universe ENTIRELY (a known, documented caveat), and
  (b) the OFFLINE `fwd_20 = close.shift(-20)` produces NaN and is dropped IDENTICALLY. So
  the engine matches the offline; both share the optimism. gemini's "exit at last price +
  recovery rate" fix would make the engine MORE conservative than the offline → BREAK the
  comparison; rejected for the cross-check (noted as a future production hardening).
  **ACTION:** quantify dropped rebalances/names in 2025 and confirm it's small.
- **Stock-time vs market-time exit (gemini #2).** `exit_j = i+H` uses the name's own bar
  index (halts → later calendar exit). The offline `shift(-20)` is ALSO per-ticker
  stock-time → identical. Negligible on a $10M-liquidity universe. No action.
- **Split-adjustment look-ahead (gemini #3).** Premise is FALSE for our data: the harness
  uses RAW/unadjusted prices by default (`fetch_daily_range(adjustment="raw")`), so the $5
  filter isn't retroactively contaminated. Raw prices do inject a phantom return if a
  split lands inside a hold — but that hits the OFFLINE capture identically (same raw
  `shift(-20)`), so it's shared, small, and a known project-wide convention. No action.
- **2025→2026 boundary crossing (codex HIGH).** The last Dec-2025 rebalance's 20-day hold
  exits in early Jan 2026. The OFFLINE OOS test did the same (its `fwd_20` for late-Dec
  used Jan-2026 closes). To reproduce faithfully I must let it cross — prefiltering would
  break the match. **ACTION:** document that the final hold reaches ~mid-Jan 2026
  (minimal, ~10 trading days; consistent with the offline OOS spend).
- **MOC same-bar decide/execute (all).** Entry at the close used to rank. Optimistic but
  identical in offline and engine. Known limitation, not a divergence.

## Already-correct (confirmed, no action)

- **Stop-loss (gemini #4):** x01 sets `use_close_stop=False` and the offline had no stop →
  the nominal 10% stop never triggers. Confirmed.
- **`get_loc` type guard (claude):** widened to accept `np.integer`; verified returns a
  Python int on the deduped unique index anyway.
- **normalize() on the runner slice (deepseek):** `b.index` is already
  `.normalize().tz_localize(None)` in `_load_daily_bars` and `rebal_ts` is tz-naive →
  the `<=` compare is safe. Left as-is.

## Reporting (codex #3) — handled in the comparison, not the engine

`total_pnl_pct` sums per-name trades; the offline metric is the EQUAL-WEIGHT
rebalance-mean return. **ACTION:** the cross-check query computes mean(pnl_pct) per
rebalance date, then aggregates period mean / Sharpe / cross-sectional premium — matching
the offline construction.

## Decision

Cleared to run the cross-check AFTER: matched costs (10 bps), gross reference, logged
rebalance dates, and quantified drops. Expect direction + magnitude agreement (net
positive, Sharpe ≈ 0.8–1.1, premium ≈ +2–3.5%), NOT bit-identity. A NEGATIVE result or a
vanished premium = a real divergence to hunt (prime suspects: PIT-universe mismatch or an
entry-date off-by-one) — none found in review, so not expected.

## DISPOSITION (run 2026-06-16, post-fix) — REPRODUCES (cross-check PASS)

Ran `x01` on `momentum_swing_2025` through the REAL engine (core/execution +
swing runner + DuckDB), ExecutionConfig(0,0,0) gross, then −10 bps additive in analysis
(exactly the offline cost treatment). 13 rebalances, 650 trades, ALL TIME_EXIT, 50
names/rebalance, ZERO no-fill/drop rows (the survivorship silent-drop concern was
negligible in 2025, as expected). Logged rebalance dates: 2025-01-02 … 2025-12-17 (last
hold exits ~mid-Jan 2026, matching the offline OOS).

| metric | offline OOS | independent re-impl | REAL engine |
|---|---|---|---|
| per-period net | +3.98% | +3.46% | **+3.46%** |
| ann Sharpe | +1.08 | +0.92 | **+0.92** |

Engine ≈ independent re-impl to 2 decimals (same 13 non-overlapping phase-0 rebalances);
both just under the offline OOS, whose daily-overlapping-cohort sampling runs slightly
higher — exactly the benign sampling gap reviewers predicted. **VERDICT: faithful
reproduction → the offline multi-day momentum pipeline is validated through the real
engine.** No fixes beyond the two actioned (liquidity fail-closed, drop intraday funnel
auto-eval). Cross-sectional premium (alpha-vs-beta) was already established by the offline
(+2.78%) and independent (+2.12%) runs; the engine reproduces the corresponding top-50
book return that those premia were measured against.
