# Feature-Search Spec — walk-forward combinatorial admission-filter selection

Status: PROPOSED (2026-06-14). Owner: research. Target family: `post_gap_opening_drive`
(`d`), but the harness is family-generic.

## 0. Why this exists

We want to ask "which combination of candidate-admission filters gives gap-and-go a
real, cross-year edge?" **combinatorially** rather than one hand-picked lever at a
time — but combinatorial search over one dataset is a multiple-comparisons machine
and is exactly the project anti-goal ("filter-until-zero", the overfit trap). d11/
d13/d14 already showed the failure: a 2-lever combo looked clean on the 108-day
screen (d14 p=0.017) and was KILLED on the full-day broad eval (eval_2022 −6.8R,
eval_2023 −16.2R). The screen flattered it via a 24-day/yr sampling fluke.

So this harness is built to make combinatorial selection *honest*: a single
feature-capture run, an offline subset search, **walk-forward** out-of-sample
evaluation (defends temporal/regime generalization), and a **PBO** statistic
(defends against selection/overfitting). The expected, acceptable outcome is a
clean negative that retires the family with evidence.

## 1. Scope

IN scope — **candidate-admission filters** (they only ADMIT/REJECT a candidate, so
every combination is a monotone SUBSET of one maximal-recall capture run; no
re-running per combo):

| feature | source | thesis / prior release |
|---|---|---|
| `gap_pct_vs_prior_high` (band: floor & ceiling) | first 5m + prior daily | d07 ceiling |
| `first_close_pos` = (close−low)/(high−low) | first 5m | d13/d14 |
| `first_range_atr_frac` = (high−low)/ATR14 | first 5m + daily | d09/d10 |
| `opening_rv` = first_vol / mean(prior opening-bar vol) | hist 5m | d02 |
| `first_open` (price floor/band) | first 5m | d01 ≥ $5 |
| `avg_daily_volume` (liquidity floor) | daily | filters.min_avg_daily_volume |
| `spy_below_50d_sma` (day-level) | SPY daily | d11 |
| `sector_below_50d_sma` (day-level, SPY fallback) | sector map + ETF daily | d12 |
| `rel_spy_gap` = gap / SPY_gap | SPY 5m+daily | d08 |

OUT of scope — filters that change a trade's REALIZED R rather than admit/reject it,
because they break the subset invariant and need their own runs: uncapped target
(d03), VWAP-entry gate (d06), exit-time/hold window (d04). Handle these by running a
few base variants separately, NOT inside the combinatorial search.

All features above are leak-free: computable by 09:35 ET from the prior-day daily bar
and the first regular 5m candle. No same-day forward bars.

## 2. Stage 1 — Feature-capture run

Goal: one run that emits, per candidate, the full admission feature vector AND the
realized R it would earn if admitted.

- **Release/mode**: a capture variant with d01's *minimum* admission (gap > 1% above
  prior high, green first candle, ≥ $5, breakout-of-first-high entry) that annotates
  each candidate with EVERY feature in §1 (compute RV/ATR-frac/SPY/sector/rel-gap
  even though it does not filter on them). Reuse `DriveVariant` plumbing + d12's
  sector map + d11's SPY hydration.
- **No candidate cap**: run with `candidate_limit=None`. The subset trick is only
  valid if the captured set is the complete admissible universe per day; a top-N cap
  would let a cut candidate re-enter when a filter removes a higher-ranked one.
- **Independence**: the engine simulates each candidate's R independently (per-ticker,
  1%-risk model, no shared capital cap), so removing candidates never changes the R
  of the survivors. Verified against `runner/pipeline.py` (per-candidate signal/fill).
- **Testsets**: `eval_2022_broad`, `eval_2023_broad`, `eval_2024_broad`,
  `eval_2025_broad` (full days). 2026 is NEVER captured here — it stays sacred OOS.
- **Feature computation**: IMPLEMENTED (2026-06-14) as the reusable, family-agnostic
  `research/features.py` — `compute_candidate_features(...)` (pure) / `features_from_
  context(context, ticker)` (adapter). The full ⊕ set is `research.features.FEATURE_
  NAMES` (41 features, A–F); leak-free by construction + tested
  (`tests/test_features.py`). The capture variant just calls this per candidate.
- **Output**: a flat capture ledger (parquet under `validation/` or a `search_*`
  table) with one row per candidate-that-produced-a-trade:
  `trade_date, ticker, <feature columns…>, filled (bool), realized_r`.
  Candidates that did not fill (no breakout / no-fill) carry `realized_r = NULL` and
  contribute 0 to every subset (consistent across combos).

## 3. Stage 2 — Subset search engine (offline, no backtests)

- **Grid (pre-registered, thesis-bounded)**: each feature gets a SMALL, fixed set of
  cut points + direction, frozen with a seed before running. Example:
  `gap_floor ∈ {1,2,3}`, `gap_ceil ∈ {8,12,∞}`, `close_pos_max ∈ {0.75,0.9,∞}`,
  `atr_frac ∈ {[0.3,∞),[0,0.5],∞}`, `rv_min ∈ {1,2,∞}`, `price_min ∈ {5,10,∞}`,
  `adv_min ∈ {1e6,∞}`, `spy_gate ∈ {on,off}`, `sector_gate ∈ {on,off}`.
- **Complexity budget**: cap simultaneously-active filters at **k ≤ 3** (degrees of
  freedom control — the dominant overfit lever is # filters, not # cut points). Record
  total combos N tried; N feeds the PBO/penalty.
- **Deployment cap (IMPORTANT):** the broad eval deploys with `candidate_limit: 10`
  (top-10 by gap/day). The capture is UNCAPPED, so each combo must, after masking,
  RE-APPLY the top-N per day using the stored `score` (gap %) before scoring — a pure
  subset that ignores the cap would not match how the strategy actually trades. The
  ledger stores `score`/`rank` precisely so this top-N re-ranking is reconstructable
  offline. (Make N a search parameter; default 10 to match the eval testsets.)
- **Per-combo metrics** (masked ledger → per-day top-N → score): trades, sum R, mean R,
  win%, profit factor, top-5 tail share, trades/quarter. Pure pandas; ~seconds for N
  combos in the hundreds.

## 4. Stage 3 — Walk-forward evaluation (the arbiter)

Expanding window, time-ordered, refit each step:

| fold | train (select combo) | test (score OOS) |
|---|---|---|
| 1 | 2022 | 2023 |
| 2 | 2022–2023 | 2024 |

**2025 is held OUT of walk-forward as the primary clean OOS** (full, normal-regime
year nothing touched). 2026H1 is NOT used as the sacred holdout — it is the suspected
artifact window (the cross-family 2026H1 finding) and is partial; it is kept only as a
secondary sanity check we explicitly distrust. So: capture spans 2022–2025 (§2), WF
selects/scores on 2022–2024, and 2025 is the final arbiter, with 2026H1 secondary.

- **Selection rule** inside each train window: pick the combo maximizing the
  objective (§6) subject to constraints (min total trades; ≥ 20 trades/qtr on TRAIN).
- **Scoring**: apply that train-selected combo to the held-out test year; record test
  sum R, mean R, trades/qtr.
- **Pass criteria** (all required):
  1. aggregate OOS sum R across folds > 0,
  2. positive in ≥ 2 of 3 test folds,
  3. ≥ 20 trades/quarter on every test fold (the count floor that d14 only failed on
     the screen — verify it holds on full days),
  4. low PBO (§5).
- **Stability diagnostic**: log the combo selected per fold. If it changes every fold,
  that itself is evidence of no stable edge (report, don't hide).

## 5. Stage 4 — PBO via CSCV (overfitting guard)

Combinatorially-Symmetric Cross-Validation (López de Prado) → Probability of Backtest
Overfitting:

- Split the pooled pre-OOS days into **S** even, contiguous blocks (S=16). Form all
  `C(S, S/2)` partitions into IS/OOS halves.
- For each partition: rank all N combos by IS objective; take the IS-best; find its
  rank among the same combos on the OOS half. Map OOS rank to logit; **PBO** =
  fraction of partitions where the IS-best falls in the bottom half OOS.
- **Purge/embargo**: 1-day embargo between adjacent IS/OOS blocks (the only temporal
  overlap is prior-day daily context; day-trades carry no multi-day label, so leakage
  is otherwise nil).
- **Interpretation**: PBO ≳ 0.5 ⇒ the search is overfitting; NO combo is trustworthy
  regardless of its headline R. Report PBO as a first-class output next to WF R.

## 6. Objective & the multiple-testing stance

- **Objective** (per combo, per window): mean R, with hard constraints (min trades,
  min trades/qtr). Tie-break by lower top-5 tail share (prefer broad over tail-driven).
- **Explicitly NOT a gate**: the per-combo sign-flip permutation p. Under selection it
  is meaningless (the winner of N combos has a small p by construction). The honest
  gates are WF OOS positivity (§4) + low PBO (§5). We keep the sign-flip p only as a
  descriptive column on the final, single chosen combo.

## 7. Decision rule

- **Promote** iff WF passes (all of §4.1–4.4) AND PBO is low. Then: freeze the combo
  as a pre-registered immutable `dNN`, run the normal funnel (smoke → screen →
  broad_is), and ONLY THEN the one-shot sacred 2026 OOS (`eval_2025_broad`/
  `eval_2026_h1_broad`, `--allow-oos` after stage 2 clears). The OOS year was never in
  capture, search, WF, or PBO.
- **Otherwise**: record the clean negative in the family backlog and auto-memory.
  Given d11/d13/d14 + the cross-family 2026H1 finding, this is the likely outcome and
  is a real result — it retires gap-and-go with evidence instead of one more lever.

## 8. Storage (reuse existing schema)

- `search_runs`: `search_id, release_id (capture variant), testset (capture set),
  objective, config_json (feature grid + cut points + WF scheme + S + seed), status`.
  Config is PRE-REGISTERED (written before scoring) so the grid can't be tuned post-hoc.
- `search_results`: one row per combo — `filters_json, trade_count, total_pnl_pct,
  profit_factor, win_rate, metrics_json (WF per-fold R, aggregate OOS R, top-5 share,
  trades/qtr)`. Plus a run-level PBO stored on `search_runs.config_json`/metrics.

## 8b. Feature locking — capture broad, search narrow

Two different objects, locked differently:

- **Capture set (§2): NOT locked — capture broadly.** Recording a column has zero
  inferential cost; the capture run is the expensive part we don't want to repeat.
  Record every cheap, leak-free signal computable by 09:35, even ones not (yet) in the
  search grid.
- **Search grid + objective + WF/PBO config + seed (§3–§6): LOCKED before any scoring,
  and NOT expanded in reaction to results.** Every feature/threshold added after
  peeking is a laundered degree of freedom that inflates the true PBO and burns the
  holdout — the exact mechanism behind d14's misleading p=0.017.
- **Alpha-spending:** budget the NUMBER of pre-registered search rounds up front. One
  round is clean; "search → peek → tweak grid → re-search" manufactures overfits.
  Plan: round 1 at k≤2; escalate to k=3 only as a SEPARATE pre-registered round if
  round 1 yields a live candidate.
- **Contamination note:** `gap`, `rv`, `atr_frac`, `price`, `adv`, `spy_gate`,
  `sector_gate`, `rel_spy_gap` are prior-thesis features (pre-existing releases).
  `first_close_pos` is DATA-DERIVED (reverse-engineered from the 2022–2026 d11 screen),
  so it carries mild in-sample contamination; only the untouched OOS redeems it.

## 9. Anti-overfitting guardrails (summary)

1. k ≤ 3 simultaneous filters (DoF budget).
2. Thesis-only features (§1) — no "throw every column in".
3. Pre-registered grid + seed, written before scoring.
4. Walk-forward, time-ordered, refit per fold — not a single split.
5. PBO over the whole search — the selection-aware honesty metric.
6. 2026 OOS sacred and single-shot, behind the existing CLI `--allow-oos` guardrail.
7. Per-combo p is descriptive, never a gate.

## 10. Build plan

| file | role |
|---|---|
| capture variant (e.g. `strategies/post_gap_opening_drive/capture.py`, NOT a numbered release) | d01 min-admission + full feature annotation; `candidate_limit=None` |
| `scripts/capture_features.py` | run the capture variant over the broad evals → capture ledger |
| `scripts/feature_search.py` | build grid, enumerate k≤3 combos, subset-score, walk-forward select/score, write `search_*` |
| `validation/cscv.py` | PBO/CSCV implementation (pure numpy) |
| reuse `validation/run_stats.py`, `validation/walkforward.py` | metrics + WF scaffolding |
| `tests/test_feature_search.py` | subset-invariance on a synthetic ledger; PBO on known over/under-fit fixtures; WF fold boundaries |

## 11. Locked decisions (2026-06-14)

- **Capture**: broad/unlocked; record all leak-free features in §1 over 2022–2025.
- **Search grid**: locked + pre-registered; coarse cut points (2–3 per feature).
- **Round 1 at k ≤ 2**; k = 3 only as a separate pre-registered round 2 if round 1
  yields a live candidate (alpha-spending budget: small number of rounds).
- **WF over 2022–2024** (2 folds); **2025 held out as the primary clean OOS**; 2026H1
  secondary and explicitly distrusted (artifact window).
- **S (CSCV) = 16; trades/qtr floor = 20.**
- **Per-combo permutation p is descriptive, never a gate** (selection invalidates it).
