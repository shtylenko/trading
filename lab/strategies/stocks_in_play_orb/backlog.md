# stocks_in_play_orb — Backlog

Updated 2026-06-13.

## ⛔⛔ FAMILY VERDICT (2026-06-13): EXHAUSTED — all variants killed

o04–o09 (five pre-registered hypotheses + the wide-stop follow-up) ran on the
108-day stratified screen `screen_2022_2026_sampled` at corrected 1-minute
fidelity. Pre-registered kill rule (sum R < 0 OR pooled sign-flip p > 0.5):
**all seven negative, all killed.**

| Rel | Hypothesis | Trades | Sum R | p | Gate |
|---|---|---:|---:|---:|:--:|
| o03 | prior baseline | 777 | −41.0 | 0.71 | KILL |
| o04 | paper-faithful | 1792 | −679.3 | 1.00 | KILL |
| o05 | extreme gappers | 365 | −108.9 | 0.95 | KILL |
| o06 | SPY-green gate | 908 | −426.4 | 1.00 | KILL |
| o07 | SPY-ATR-hot gate | 968 | −350.0 | 1.00 | KILL |
| o08 | noon time-stop | 1792 | −683.4 | 1.00 | KILL |
| o09 | wide stop | 1792 | −32.5 | 0.64 | KILL |

Two findings confirmed prior analysis:
- **o04 = −679.3R vs the −682R 1-min resim prediction** — the 1-min stop-out
  fix is correct; o03/o04 genuinely lose, the old inflated 5m number hid nothing.
- **o09's wide stop validated the noise-clip diagnosis but found no edge.** Same
  1,792 entries as o04; only the stop width differs. Exit mix flips from 89%
  STOP_LOSS (o04) to 65% TIME_EXIT (o09), cutting the loss 95% (−679R → −32.5R) —
  but it converges to ≈0, not above. No alpha under the cost drag, just the
  removal of a self-inflicted wound. By-bucket R is noise around zero (positive in
  4/9 half-years); the two obvious regime gates (o06/o07) made it *worse*.

**Conclusion: the SIP-ORB family is done.** Every distinct hypothesis tested and
explained. Move research effort to a different strategy family (d/f or new).

---

## ⛔ A-1 GATE VERDICT (2026-06-12): FAILED — Phase B/C cancelled

Multi-year engine evals on the rule-based `liquid_pit` universe (2022/2023 with
`O03_DISABLE_ML=1` to avoid model look-ahead):

| Period | sum R | PF | perm p | status |
|---|---|---|---|---|
| 2022 | +10.2R | 1.14 | 0.48 | regime diversity (RV-only) |
| 2023 | +28.7R | 0.98 | 0.41 | regime diversity (RV-only) |
| 2024 H1 | **−38.0R** | 0.93 | 0.68 | in-tuning year, honest universe |
| 2025 | +27.6R | 1.00 | 0.42 | true OOS |
| 2026 H1 | **−86.2R** | 0.80 | 0.92 | true OOS |

Pre-registered gate ("positive sum-R with comparable PF in ≥3 of 4 added periods"):
**not met in any period.** No period distinguishable from noise; every period is
carried by ≤5 trades (all are −100R..−160R without their top-5).

Root-cause hypothesis: the original +34.4R H2-2024 result was computed on
`cached_1min_2024_pit` — names selected *with hindsight* (cached because they were
in play in 2024). The negative 2024-H1 result on the honest universe points to a
**universe-selection artifact**, not alpha. Decisive control (cheap, not yet run):
`eval_2024_h2` re-defined on `liquid_pit`.

Per the plan's own sequencing rule: **stop here; rethink the strategy, don't tune
it.** Phases B and C below are retained for reference but are cancelled for o03.

---

The plan below was the active o03 optimization backlog before the verdict,
written after `run_o03_eval_2024_h2_broad_20260610_061426_e54a42`.

---

# stocks_in_play_orb (o03) — Optimization Plan

## Context / current state

- Engine backtest H2 2024 (128 days, broad universe): **+34.4R**, 564 fills + 241 no-fills,
  10.1% WR, PF 1.14, best trade +27.2R, worst −1.8R.
- Monthly R: Jul −1.6 · Aug +19.0 · **Sep −38.4** · Oct −6.6 · Nov +43.7 · Dec +18.3.
- Returns are tail-driven: top 10 trades = +153.9R (447% of total); the other 554 trades net −119.5R.
- Daily R: mean +0.27R, **std 6.9R** (best day +36.8R, worst ~−8R).
- CAGR math (from the actual daily R series):
  - Fixed-dollar 1% risk (additive): pace ≈ **68R/yr** → already beats a 40R/yr (=40%) target.
  - Fixed-fractional 1% risk (compounded): only **~+14.6% CAGR**, max DD −61.8% — volatility drag.
  - To hit **40% CAGR compounded** we need either **~88R/yr at current volatility**, or
    **~68R/yr with roughly half the daily R std**. Optimal fixed fraction today is ~0.6% risk
    → max ~23% CAGR at *any* size. Variance reduction is worth as much as adding winners.
- Edge source (2024 walk-forward research): the **pullback limit entry**
  (limit at ORH − 0.02·ATR14, strict fills, 30m TTL), not ML selection (LightGBM ≈ RV, AUC 0.61).
  Never cap winners; breadth helps (top-10 > top-5). Exit slippage >5–10 bps kills the edge.
- **All of the above is calibrated on 2024 only.** A strategy this tail-dependent can look
  great or terrible for a half-year purely by luck.

The plan splits into **trust** (is the edge real?) and **performance** (more R, smoother R).
Trust comes first: nothing downstream is worth doing if the edge doesn't survive other years.

## Phase A — Trust

### 1. Extend the dataset to 2022–2023 and 2025 (+H1 2026); re-run eval and ablations

**Impact: highest — validates or kills everything else. Cost: moderate (data fetch is now fast).**

- We are in mid-2026: 2025 + H1 2026 are *true out-of-sample* (never touched by any tuning).
  2022 (bear) and 2023 (chop) add regime diversity that 2024 (trend) lacks.
- Steps:
  1. Fix the gap-through-stop bug in `strategies/stocks_in_play_orb/research/build_dataset.py:222-226`
     first (post-fill stop exit uses `f_exit = stop` without the `min(o[i], stop)` gap guard —
     research-only optimism; the production engine is already correct). Required so the rebuilt
     research dataset matches the engine.
  2. Prefetch + cache 1-min/5-min/daily data for the SIP universe, 2022-01 → 2026-06
     (the bulk prefetch pass in `runner/pipeline.py` makes this tractable).
  3. Define new testsets (e.g. `eval_2022_broad`, `eval_2023_broad`, `eval_2025_broad`,
     `eval_2026_h1_broad`) and run o03 on each.
  4. Re-run `research/ablations.py` on the extended dataset; check the pullback-entry edge,
     the "never cap winners" result, and ML-vs-RV hold up per-year.
- Add **permutation/Monte-Carlo tests** (Neurotrader-style, carried over from the old backlog)
  once a candidate passes walk-forward — especially important given tail-driven returns.
- Success criterion: positive sum-R with comparable PF in ≥3 of 4 added periods.
  If the edge is 2024-only → stop; rethink the strategy, don't tune it.

### 2. Reconcile the research-sim vs engine gap

**Impact: high — either recovers R (engine bug) or recalibrates expectations (research optimism).
Cost: low-moderate.**

- Research OOS (May–Dec 2024) claimed **+183%/yr, Sharpe 2.6, maxDD −11%**; the engine backtest
  delivers **~68R/yr** with −61.8% compounded DD at 1% risk. That's a ~2.5–3× gap.
- Run `research/train_and_simulate.py` and the engine on identical days/universe and diff
  trade-by-trade: candidate lists, fills vs no-fills, fill prices, exits, slippage/fees.
- Known suspects: the build_dataset stop bug (A1.1), universe construction differences,
  slippage model, ranking input differences, no-fill handling.
- Deliverable: a written list of divergences, each classified "engine bug" / "research
  optimism" / "intentional"; fix engine bugs, document the rest.

### 3. Data harmonization: split-adjusted daily vs raw intraday prices

**Impact: critical (prevents silent data corruption). Cost: low (~30 LOC, requires split-ex-date flags).**

- Daily ATR/volume indicators currently use split-adjusted historical data from the provider,
  but intraday prices are raw/unadjusted. When a stock undergoes a 4:1 split, the 14-day ATR
  crossing the split date is divided by 4, but the intraday stop calculation uses raw prices
  → stop distances are catastrophically wrong (4× too wide or tight depending on direction).
- Fix: either (a) fetch unadjusted daily data for all indicators, or (b) programmatically skip
  any ticker that experienced a split/dividend/corporate action within the 14-day lookback.
  Option (b) is simpler and sufficient given the 40% jump filter already in place.
- This is a latent bug, not confirmed triggered — but the damage is severe enough to warrant
  fixing before the A1 multi-year extension (more years = more corporate actions).

## Phase B — Performance

### 4. Diagnose September (−38.4R) and test a regime filter

**Impact: high — attacks both sum-R and variance at once. Cost: moderate.**

- One month erased five weeks of gains. Hypotheses to test against the trade log + market data:
  - Market regime: SPY vs 20d MA, SPY above VWAP / first-candle direction (old-backlog shared
    regime-filter ideas fold in here), VIX level/spike, % of universe above 20d MA (breadth).
  - Structural: ORB strategies bleed in mean-reverting tape — measure intraday follow-through
    (e.g., ORH-breach continuation rate) per month.
- Candidate gate: skip new entries (or halve size) when the regime indicator is hostile.
- Guard against overfitting: the gate must be a *simple, pre-registered* rule validated on the
  extended dataset from A1, not fitted to September 2024 specifically.
- Halving daily R std at the same 68R/yr pace takes 1%-risk CAGR from ~15% to ~50%.

### 5. Counterfactual analysis of the 241 no-fills

**Impact: potentially high (could add tail R) or zero (closes the question). Cost: low.**

- 30% of signals never filled (price didn't pull back to the limit). Risk: the strongest movers
  are exactly the ones that don't pull back → we systematically miss the best tails.
- Compute counterfactual R for every no-fill under a fallback entry, e.g. market entry at TTL
  expiry if price still above ORH (with realistic slippage and a worse effective R denominator).
- If counterfactual R is strongly positive → design a two-tier entry (limit first, fallback
  stop/market second) and ablate it. If negative → the limit entry is doing its job; close.

### 6. Daily-loss circuit breaker (left-tail variance reduction)

**Impact: medium-high for CAGR (cuts daily σ without touching winners). Cost: very low.**

- Worst days are ~−8R from many concurrent losers. Test: stop opening new positions once the
  day's realized+open R reaches −3R / −4R / −5R.
- First pass needs **no re-simulation**: replay existing trade logs, drop trades entered after
  the threshold was hit, recompute daily R series, σ, compounded CAGR, max DD.
- Consistent with "never cap winners" — this only trims the left tail.
- Also check the converse (a daily *win* lockout) — expected to hurt (tail-driven), but cheap
  to confirm on the same replay.

### 7. Exit ablations: overnight hold on runners; breakeven ratchet

**Impact: medium, double-edged (research showed exit tinkering usually hurts). Cost: moderate.**

- Everything currently exits 15:59. The +27R/+54R tails suggest momentum that may continue.
- Ablations (each with a kill criterion, on the extended dataset):
  - Hold trades that are above +2R at 15:55 overnight; exit next open / next-day trail.
  - Ratchet stop to breakeven after +1R (shrinks the sub-−1R gap-through left shoulder).
  - Re-confirm EOD exit beats fixed targets (already established; re-check on new years).
  - Scale-out / EMA-trail variants (old-backlog `d03` idea) — same kill criterion.
- Reject any variant that reduces total R on the extended dataset, even if it smooths 2024.

### 8. Intraday volatility decay stop-loss

**Impact: medium-high (aligns risk with actual intraday mechanics). Cost: moderate (~100 LOC).**

- The current stop is 0.10 × ATR14 (daily Wilder-smoothed). But intraday volatility follows
  the well-known "smile": exponentially higher in the first hour, decaying into the midday
  doldrums, then picking up into the close. A fixed ATR fraction means stops are too tight
  during the opening vol expansion (premature stop-outs) and unnecessarily wide later.
- Compute the historical average 5-minute true range specifically for the 09:30–10:00 window
  and use that as the R denominator instead of daily ATR14. Alternatively, fit a simple
  exponential decay curve to intraday TR by 30-minute bucket and scale stops dynamically.
- Test as an ablation against the fixed 0.10×ATR14 baseline on the extended dataset.
- Pitfall: overfitting the decay curve to 2024 only. Validate the shape holds across years.

### 9. Cross-sectional correlation caps in top-N selection

**Impact: medium (variance reduction via genuine diversification). Cost: low (~50 LOC).**

- "Stocks-in-Play" cluster by sector/theme. If 8/10 selected candidates are semiconductors
  (NVDA, AMD, AVGO, …), the portfolio carries 8% risk to a single factor, not 8 independent
  1% units. This inflates daily σ without adding expected R.
- Compute a rolling 14-day correlation matrix of 1-min or 5-min returns among triggered
  candidates. When selecting top-N, penalize candidates that have ρ > 0.7 with an
  already-selected candidate (e.g., halve their selection score).
- Forces the model to pick diverse alpha streams; cheap post-processing on the existing
  candidate list. Test on the H2 2024 log first (replay), then on the extended dataset.

### 10. Two-stage nuisance classifier for no-fill probability

**Impact: medium-high (cleaner directional signal). Cost: high (~150 LOC, two model instances).**

- Currently the LightGBM predicts P(hit +2R before stop) but 30% of signals never fill.
  The features that predict "will this limit order fill?" (microstructure, spread, tick vol)
  are completely different from those that predict "will this stock run +2R?" (RV, sector
  strength, macro regime). Jamming both into one model dilutes both signals.
- Architecture: Model A (Execution Head) predicts P(fill | breach) using microstructure +
  short-term liquidity features. Model B (Directional Head) predicts P(+2R | fill) using
  structural/volume/macro features. Final ranking = P(fill) × P(+2R | fill).
- Decouples execution friction from directional alpha; each model specializes. The directional
  head gets a cleaner label (conditioned on actual fills).
- Pitfall: needs enough fill-events to train Model A reliably. Worth it only after A1 confirms
  the edge and B5 quantifies the no-fill opportunity cost.

### 11. Expected-R regression with Huber loss (replace binary +2R classification)

**Impact: highest — aligns ML objective with what we actually care about. Cost: moderate
(~50 LOC config change + retraining pipeline).**

- The current binary label P(hit +2R before stop) throws away massive information. A trade that
  hits +1.9R then stops out is labeled 0 — indistinguishable from a trade that instantaneously
  gapped to −1R. The model learns arbitrary threshold boundaries, not the physics of momentum.
- Replace the label with the continuous realized R at exit (capped at some ceiling to prevent
  a single +27R trade from dominating). Train with `objective='huber'` in LightGBM: Huber loss
  behaves like MSE for small residuals (fine-grained optimization) but transitions to MAE for
  large residuals (robust to the extreme tails that drive PnL).
- The model's ranking becomes "expected R" instead of "probability of +2R" — directly
  interpretable and aligned with portfolio construction. The Huber delta parameter should be
  tuned: start at δ=1.0 (1R) and sweep [0.5, 1.5, 2.0].
- Pitfall: the label distribution is extremely skewed (10% positive, most near −1R). Test
  log-transform or quantile-binning as alternatives if Huber alone isn't enough.
- This is the single most impactful methodological change from the peer review. Binary
  classification at an arbitrary threshold makes no sense for a continuous-outcome strategy.

## Phase C — Optional / last

### 12. Feature engineering improvements

**Impact: low expected (selection is not where the edge lives; AUC plateau at 0.61). Cost: high
for the feature work, low for the breadth test.**

- Cheap first: top-15 instead of top-10 (breadth has helped before). Watch concurrency/capital limits.
- **Feature pruning (near-zero cost, do immediately):**
  - Remove `window=5.0` (constant, zero information gain; store window as metadata in model
    artifact name instead, e.g. `orb_lgbm_v2_5m.pkl`).
  - Remove `or_vol_ratio` (semantically identical to `rv`; collinear features destabilize
    tree importance metrics and promote overfitting).
- **Feature transformations (cheap, ~50 LOC):**
  - Transform `gap_pct` → `gap_zscore` = raw gap / rolling-14d std of overnight gaps.
    A 2% gap in TSLA is noise; a 2% gap in KO is a 5-sigma event. Scale-invariant.
  - Transform `log_dollar_vol` → daily cross-sectional percentile rank (0–1) within the
    SIP universe. Absolute dollar volume drifts with inflation and index appreciation;
    percentile is stationary across years.
- **New features (only after A1, on ≥3 years of data):**
  - Volume Profile Point of Control (`poc_position`): disaggregate the 5-min OR bar into
    1-min volume bins; compute (POC price − L) / (H − L). If POC is near the bottom but
    close is near the top → early selling was absorbed → conviction signal.
  - Sector relative strength: map each ticker to its SPDR sector ETF (AAPL→XLK, JPM→XLF),
    compute `f5_ret(ticker) − f5_ret(sector_ETF)` at 09:35. Isolates stock-specific
    catalyst from sector beta.
  - Also: earnings/news-catalyst flags, short interest, pre-market range / gap+premarket-volume
    filters (old-backlog `d02` idea).
- Also re-test whether ML beats plain RV at all on the extended dataset; if not, consider
  dropping LightGBM from the production path for simplicity.

### 13. Model architecture baselines (robustness check)

**Impact: low (safety net, not an edge driver). Cost: low (~100 LOC).**

- LightGBM with AUC 0.61 on high-noise data is susceptible to fitting residual noise. Before
  committing to the LGBM pipeline for multi-year training, benchmark two alternatives:
  - **ElasticNet logistic regression** (L1+L2 penalties): linear models ignore spurious
    non-linear interactions that fail to generalize. Manually engineer key interaction terms
    (e.g. `rv × gap_zscore`, `rv × spy_vr`) before feeding to the linear model.
  - **Random Forest with aggressive regularization**: max_depth=3–4, min_samples_leaf=5%
    of dataset. Bagging inherently reduces variance vs boosting's sequential error correction.
- Both are cheap to run on the existing feature matrix. If neither beats LightGBM, confidence
  in LGBM increases. If either does, switch — simpler is better.
- Run this comparison on the extended multi-year dataset (after A1), with the expected-R
  regression label (after B11).

## Sequencing

1. **A1 → A2 → A3** (trust + data integrity). Hard gate: if the edge doesn't survive 2022–2025, stop here.
2. **B4 + B6 + B11** in parallel (regime filter, circuit breaker, and expected-R regression
   are all independent; B11 path needs A1 data but the code change is orthogonal).
3. **B8 + B9** together (both are stop/sizing layer changes; test as a combined config).
4. **B5**, then **B10** (B5 counterfactual analysis informs whether B10's nuisance classifier
   is worth the complexity).
5. **B7** (exit ablations — lowest priority among B items; research history says exit tinkering
   usually backfires, so only after the higher-impact items are exhausted).
6. **C12 + C13** only if A/B leave us short of the ~88R/yr (or half-σ) target.

## Framing for the 40% CAGR goal

- A1/A2/A3 tell us whether ~68R/yr is real at all and the data is sound.
- B4/B6 attack the **variance** side (regime filter + circuit breaker; half the daily σ ≈ 50% CAGR at 1% risk).
- B5/B7/B8/B9 attack the **sum-R** side (no-fill capture + exit ablations + vol-decay stops + correlation caps → toward ~88R/yr at current σ).
- B11 (expected-R regression) is a force multiplier for everything above — better ranking makes every other improvement more effective.
- B10 (nuisance classifier) depends on B5 results; C12/C13 are long shots. Sizing alone cannot reach 40%: at current volatility the best any fixed fraction achieves is ~23% CAGR (at ~0.6% risk/trade).

## Done

- `o02` (relative-volume ranking) and `o03` (ATR stop, EOD exit, no fixed target) — shipped.
- `o01` — baseline ORB strategy.

## Open (absorbed or deferred)

- Shared market-regime filters (SPY above VWAP, first-candle green, opening-drive strength) → folded into B4.
- Gap threshold + premarket volume filters (`d02`) → folded into C12.
- 2R scale-out + 9 EMA trail (`d03`) → folded into B7 ablations.
- Common liquidity filters (min price, ADV, ATR, first-bar range) → partially shipped in SIP filters; revisit during C12.
- Neurotrader permutation tests → folded into A1 validation.

## Decisions

- Engine directory: `strategy_lab`.
- Database: DuckDB.
- First releases: `o01` (baseline ORB), `o02` (RV ranking), `o03` (ATR stop + ML).
- Testsets are owned by `strategy_lab`.
- Universe model includes point-in-time snapshots from day one.
- Paper trading belongs to P2.

## Audit-driven releases (2026-06-13) — UNRUN

From the 3-reviewer codebase audit (`peer-review/2026-06-13-codebase/`). Both
were added without editing the frozen o03/o07 (immutability), so each is a NEW
release, not a mutation:

- **o10** (audit M14): o03 mechanics, but the LightGBM ranker auto-disables
  (RV fallback) on trade dates before its 2024 training year — removes the o03
  pre-2024 look-ahead foot-gun without manual `O03_DISABLE_ML`. On 2024+ dates
  it equals o03-with-model. Run o10 (not o03) for any multi-year / pre-2024 eval.
- **o11** (audit L4): o07's exact frozen volatility-regime rule (SPY 14d ATR%
  above its 1-yr median), but sourced from runner-hydrated `context.spy_daily`
  instead of a direct `fetch_daily_context` call in strategy code. Same data,
  same rule → "o07 done within the StrategyContext contract".

Neither has been through the screen funnel yet.

## Audit follow-up (2026-06-18 codebase review) — needs fix-forward releases

From the 2026-06-18 whole-tree audit. These live in IMMUTABLE code (`common.py`,
`variants.py`, shipped releases) so they are fixed forward with new releases, never
in place. (Caveat: that audit was only ~half-reliable — three of its other findings
were false on verification — so each item below is tagged with its check status.)

- **H1 — NaN slips the RV gate then crashes sizing** (VERIFIED, plausible edge).
  `common.py:107` `rv = first_vol / mean_opening_volume`: a present-but-NaN
  `first_vol` makes `rv` NaN, and `NaN < min_rv` is `False`, so the candidate
  PASSES the relative-volume gate with `rv=NaN`. Then `variants.py:142` `risk_per_share
  = abs(NaN)` passes the `<= 0` guard and `int(qty)` (`variants.py:~150`) raises
  `ValueError` (caught at session level — loud, isolated, not silent corruption).
  *Partial mitigation already shipped:* an engine-level finite guard now drops
  signals with non-finite entry/stop/target before simulation (`runner/pipeline.py`,
  2026-06-18) — family-agnostic, handles the phantom-trade half. *Deep fix →
  proposed `o12`* (off o11): `if not math.isfinite(rv): return None` after the RV calc
  and `if not math.isfinite(risk_per_share): return None` before `int(qty)`.
- **H3 — `spy_atr_regime_hot()` direct provider call** (CORROBORATED; o11 already the
  forward fix). `variants.py:179-207` computes the SPY ATR-regime from
  `fetch_daily_context()` in strategy code instead of `context.spy_daily`. o11 is the
  contract-compliant forward path; o07 stays on the direct-fetch path indefinitely.
  No new release needed beyond o11 — listed for traceability only.
- **H4 — o10 `_gate_year` signature contamination** (PLAUSIBLE; not deep-verified).
  `o10.py:57-60` sets `_gate_year` lazily inside `build_candidates`; at
  `compute_code_signature` time it is still `None`, so `signature_inputs()` always
  folds the ML-model hash in — pre-2024 RV-fallback runs share a signature with
  2024+ ML runs, so the dashboard's fresh/stale badge mislabels them. *Proposed
  `o13`* (off o11): resolve the gate year inside `signature_inputs()` from the model
  artifact's train-end date (or fold the model hash only when ML is actually active).
- **M5 — sizing rounding inconsistency.** o02 `int(round(qty))` vs o04–o09 `int(qty)`
  (floor). For qty≈2.5 that's 3 vs 2 shares (~20% on small positions). Pick one in
  any future o-release; harmonize via the variant base.
- **M9 — `allow_short` doubles work + long-first bias** (VERIFIED). When
  `allow_short=True`, `variants.py:61` runs `build_sip_base` per direction (the
  expensive hist-volume/ATR/split work twice per ticker) and `break`s at line 104 after
  the first qualifying direction — long is always tried first, so a ticker that
  qualifies both ways is only ever admitted long. Perf + selection-bias note for the
  next short-capable release.
- **M11 — `avg_vol_14` on <14 daily bars** (`common.py:117`). `tail(14).mean()`
  averages whatever exists; `min_hist_days=10` guards only the 5m history, not daily
  volume, so a name with ~5 daily bars passes on a noisy average. Add a daily-bar count
  guard in a future release.
- **L2 — o01 uses the deprecated `first_regular_5m_candle`** (`o01.py:65`). Can't be
  removed until o01's consumer is migrated; needs a fix-forward release, not an edit.
- **L12 — `risk_per_share = abs(entry_trigger - stop_price)`** (`variants.py:142`)
  masks a `stop > entry` logic error for longs (would surface as a guard rather than a
  silent abs). Consider an explicit `entry > stop` check in a future release.
