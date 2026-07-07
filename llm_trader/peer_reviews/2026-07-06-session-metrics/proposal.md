# Proposal: Enhanced Metrics for Comparing Trading Sessions (Skills + LLMs)

**Date:** 2026-07-06 (Updated 2026-07-06 after peer review)  
**Status:** Synthesized Draft v2 (incorporating feedback from Claude, Codex, Gemini)  
**Location:** `llm_trader/peer_reviews/2026-07-06-session-metrics/proposal.md`

---

## Executive Summary (Post-Review)

The direction of the original proposal is **strongly endorsed**. Current reliance on raw P&L, win%, and basic R-multiples is insufficient for reliably ranking skill versions and LLMs on the fixed stratified holdout.

**Key synthesized changes from peer feedback (Claude, Codex, Gemini):**
- **Observation unit = one leaf (finalized setup)**, not fills from `actions.json`. This preserves the existing "trades vs fills" discipline in `list_sessions` / win-rate calculations.
- **Two flavors of key metrics**: "clean" (traded + non-void only) and "effective" (all planned setups; stood-down = 0R, voids penalized e.g. -1R).
- **Reframe risk metrics**: Drop or heavily de-emphasize portfolio-time concepts (Max Drawdown, Calmar, annualized return, equity curve) for batches. These are ill-defined because a batch is independent parallel leaves (no sequential compounding portfolio). Replace with:
  - Per-leaf **MAE (Max Adverse Excursion)** — the missing mirror to existing MFE.
  - **Sequence drawdown** (explicit deterministic ordering, e.g. testset order).
  - Sorted R-bar chart + distribution stats (mean/median/std/p10/p90).
- **Add LLM-specific axes** that were under-developed: cost/token efficiency, consistency across repeats (`--repeats`), stop-honoring discipline, bars-held.
- **Methodology is priority #1** (not a metric): Holdout contamination risk. Locked validation set + dev set, N+CI on every number, explicit warnings.
- **SQN secondary** only, with strong N caveats (penalizes selectivity; small-N noise).
- **Compute on read** for aggregates (in `get_top_session_view`, `report_by_version`). Persist only true per-leaf primitives in `pnl.json`.
- **UI**: Compact aggregate strip + sorted R histogram/bar chart. MAE beside MFE. No overload.

**Prioritized core set (first pass)**:
1. Expectancy (R) — clean + effective.
2. Profit Factor (R + $).
3. R distribution (mean/median/std, p10/p90) + sorted bars.
4. MAE (per leaf) + MFE capture.
5. Void rate, stood_down rate, forced_exit rate.
6. Cost/token efficiency + expectancy-per-dollar.
7. Repeat consistency (stddev of outcomes + decision divergence when `--repeats > 1`).

This yields trustworthy, small-N-honest comparisons without weakening the deterministic recorder, PositionEngine, or no-look-ahead guarantees.

---

## Background and Current State

(See original for full details. Key reminder: top-level sessions are virtual groupings by `"session"`/`"batch"` field. Leaves are independent `(ticker, date)` setups with flat per-trade risk budget. No compounding portfolio clock.)

Current metrics (recorder `pnl.json`, reports, UI) are solid foundations:
- `realized_pnl`, `r_multiple` (budget), `r_multiple_actual` (initial risk), win, MFE capture, n_fills, traded/stood_down/forced_exit.
- Aggregates: total pnl, win%, avg R, n_void, n_trades.

**Gaps identified across reviews**:
- Unit confusion (fills vs leaves).
- Missing mirrors (MAE) and efficiency (profit factor, expectancy).
- Weak LLM axes (cost, repeatability).
- Over-reliance on portfolio metrics inappropriate for this data model.
- No statistical honesty (CIs, N, effective vs clean).
- Holdout methodology risk.

---

## Core Methodology Guardrails (Highest Priority Feedback)

**This must be addressed before (or alongside) any new dashboard.**

1. **Holdout contamination**: The same stratified testset is reused for iteration. Richer metrics make overfitting easier. Solution:
   - Locked validation set (report on it, never inspect during dev).
   - Separate dev set for prompt/skill iteration.
   - Every number carries **N + bootstrap 95% CI on expectancy**.
   - Standing note on reports: "Selected against this set → optimistic bias possible."
   - Consider walk-forward by historical date in future `build-set`.

2. **Effective vs clean metrics**: Always show both. Voids/stood-down must not create survivorship bias (a model that voids losers looks perfect on clean-only stats).

3. **Unit is the leaf**: One finalized setup = one observation. Use `pnl.r_multiple*` per leaf. Fills (`actions.json`) are for *behavioral* metrics only (avg fills/trade, scaling style).

4. **Explicit ordering for any batch-level "drawdown"**: Testset order (or testset + repeat index). Never wall-clock `real_run_ts`.

---

## Proposed Metrics (Synthesized & Prioritized)

### 1. Profitability & Edge (Leaf-level, R-normalized)
- **Expectancy_R (clean + effective)**:
  - Clean: `mean(r_multiple)` over traded + non-void leaves.
  - Effective: mean over *all planned* with stood-down=0R, void=-1R (configurable penalty).
  - Also report `expectancy_actual_R` using `r_multiple_actual`.
  - **Why**: The single best "long-term edge" signal. Two versions prevent gaming.
- **Profit Factor (R and $)**:
  - `sum(max(R,0)) / abs(sum(min(R,0)))` over leaves (or realized deltas for $ version).
  - Clamp/annotate at small N or 0 losses.
- **Payoff Ratio**: mean(win R) / abs(mean(loss R)).
- **Distribution**: mean/median R, std(R), p10/p90, min/max. Sorted R bar chart (visual tail behavior).

### 2. Risk & Survivability (Orderless + Per-Leaf)
- **MAE (Max Adverse Excursion) per leaf** (new primitive):
  - Worst `unrealized` (negative) during the trade relative to entry or risk.
  - Mirror to existing MFE. Critical for "did the LLM manage heat?"
  - Compute from `decisions.json` timeline `unrealized` path.
- **Sequence Drawdown_R** (batch only):
  - Peak-to-trough on cumulative effective R in deterministic testset order.
- **Recovery Factor_R**: total effective R / abs(worst single R or sequence DD).

**Deprioritize/Reframe**: Portfolio Max Drawdown, Calmar, annualized return, full equity curve on batches (ill-defined without a real sequential account). Use the above + sorted R bars instead.

### 3. Statistical Quality & Robustness
- **SQN** (secondary):
  - `sqrt(N) * mean(R) / std(R)` (independent setups preferred).
  - Gate: null if N < 10; warning if N < 30.
  - Show N prominently. Understand it penalizes selectivity (lower N for stand-down-heavy models).
- Always pair with N + CI.

### 4. Behavioral, Discipline & LLM Reliability (High Value for Model Selection)
- Void rate, stood_down rate, forced_exit rate.
- Avg fills per traded leaf, avg bars_held.
- **Repeat consistency** (when `--repeats > 1`): stddev of per-setup R + decision divergence rate.
- **Stop discipline** (new): stop_widening_events (stop moved worse), stop_honoring_rate (fills at/below logged stop).
- Cost/token efficiency (new, from hermes metadata): tokens/run, expectancy per $ of inference.

### 5. Comparative
- Paired per-setup deltas (same (ticker,date) across versions/models).
- Effective expectancy deltas.
- Setup-bucket breakdowns (float, entry time, etc.).

---

## UI Recommendations (Compact, Non-Overwhelming)

When opening a top-level session (`get_top_session_view`):

**Header / Aggregate Strip** (always visible):
- Total Realized PnL, Clean Effective Expectancy_R (±CI), Profit Factor, Avg/Median R, Void%, Stood Down%, Traded N / Planned N.
- Skill version + model + hash drift warning.

**Analytics Panel** (collapsible):
- Sorted R-bar chart / histogram (bins or per-leaf bars).
- Sequence equity line (in R, explicit order).
- Reliability table: voids, stood-down, forced, avg fills, avg bars.
- MAE avg + MFE capture (promoted).
- Cost summary (if available).

**Ticker Table**:
- Add columns: R (actual), MFE Capture, MAE, Fills, Outcome vs group.

**Leaf Detail View**:
- R (budget + actual), MFE + MAE side-by-side, bars held, fills, stop discipline flags.
- "Contribution to parent batch" context.

**General**:
- Tooltips with short definitions + benchmarks (e.g., "PF > 1.5 healthy").
- Bootstrap CIs and small-N warnings.
- No hard ranking badges until sufficient local baselines.
- JSON export of the full metrics object.
- Future: `/compare?tags=...` or paired diff view; leaderboard with composite score.

For pure leaves: lighter view, focus on per-trade quality.

---

## Implementation Path (Synthesized from Reviews)

1. **Methodology & Guardrails** (do first):
   - Document locked vs dev holdouts.
   - Add N + bootstrap CI helpers.
   - Update reports with explicit warnings.

2. **Backend (recorder.py)**:
   - Pure helpers: `_compute_leaf_metrics(leaf_dir, pnl)`, `_aggregate_batch_metrics(leaf_rows)`.
   - Add per-leaf primitives to `finalize` → `pnl.json`: `mae_per_share`, `bars_held`, `stop_honored` (from decisions/actions + unrealized path).
   - Expose `metrics` object from `get_top_session_view`, `list_sessions`, `report_by_version(json)`.
   - Two expectancies (clean/effective), PF, distribution stats, sequence_drawdown, repeat-consistency (if metadata present).
   - Compute on read for aggregates. Use mtime cache if hot.

3. **Batchsim / Reports**:
   - Enhance CLI + JSON with new fields.
   - Add `batchsim compare --a TAG --b TAG` (paired per-setup diffs + sign test).

4. **Tests** (critical):
   - Edge cases: N=0, all wins, all losses, zero variance, voids, stood-down, repeats, small N.
   - Match existing patterns in `test_recorder.py`.

5. **UI (viewer/app.js + style)**:
   - New compact strip + analytics panel.
   - Sorted R chart (lightweight-charts or SVG).
   - MAE next to MFE.
   - Update `renderSessionTickers`, header, etc.

6. **Later**:
   - Persisted top-level `metrics.json` only if needed for perf/export.
   - Cost parsing from hermes exports in audit.
   - Stop discipline deeper analysis.
   - Leaderboard / compare views.

**Storage**: Minimize `pnl.json` changes to leaf-local fields. Aggregates live in memory/views.

---

## Peer Feedback Synthesis Summary

**Strong consensus**:
- Expectancy (R, dual clean/effective), Profit Factor, distributions, MAE (add), void/stood-down rates, MFE promotion, repeat consistency, cost efficiency.
- Leaf = unit. Effective metrics for voids.
- Reframe/reject batch MDD/Calmar/annualized/equity-curve (use MAE + sequence DD + sorted bars).
- SQN secondary + N caveats.
- Compute on read.
- Methodology (holdout + CI) before fancy dashboards.
- UI: compact + visuals (histogram, not overload).
- LLM angles: cost, repeatability, stop discipline.

**Differences addressed**:
- Claude: Heavy on methodology, MAE over MDD, cost, no new files.
- Codex: Leaf unit emphasis, synthetic ordering, effective metrics, behavior from current artifacts.
- Gemini: Positive on visuals/histograms, cost, stop widening, composite scores, UI panels.

All three agree the original instinct is correct but needs tighter definitions, small-N honesty, and LLM axes.

**Remaining open questions for further review** (if needed):
- Exact void penalty value (e.g. -1R)?
- Preferred ordering for sequence DD?
- Thresholds for badges (or keep soft)?
- When to add token metadata to batch artifacts?

---

## Next Steps

1. Circulate this v2 for any final comments.
2. Implement per the phased path above, starting with methodology + leaf primitives + pure helpers + tests.
3. Update `SIMULATION_VIEWER_SPEC.md` and `COMMANDS.md`.
4. Bump version and add to changelog once stable.

This synthesized proposal preserves the strengths of the original while incorporating rigorous, codebase-aware feedback to make comparisons reliable and decision-useful.

**End of updated proposal.**