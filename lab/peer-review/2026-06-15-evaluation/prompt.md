# Peer Review Request — Feature-Capture & Combinatorial-Search Evaluation Pipeline

**You are reviewing a quantitative research methodology, not code.** You have NO
access to the codebase. This document is self-contained: it specifies the entire
pipeline — feature capture, the search, walk-forward validation, and the
overfitting guard — in enough detail to audit the *statistics and methodology*.

We want your hardest, most skeptical review. The pipeline just returned a
**negative result** ("no robust edge"), and we are about to treat that as a
trustworthy verdict that retires a strategy family. Before we do, we want you to
attack it: where could this pipeline produce a **false negative** (kill a real
edge) or a **false positive** (bless an overfit one)? What are we assuming
without realizing it?

A companion document, `prompt-self-sustained.md` (in the sibling
`2026-06-14-feature-implementation/` folder), specifies all 87 features in full.
This document summarizes the feature layer and focuses on the **evaluation
methodology**, which is what we most want stress-tested.

---

## 0. What we want back

1. **The 5–10 toughest questions** you would ask before trusting this pipeline's
   verdict. Prioritize ones that could change the conclusion.
2. **Hidden assumptions** we are making (statistical, structural, market) that we
   have not stated or examined.
3. **Specific failure modes**, ranked by severity, for both directions:
   - false negative (a real edge this design would miss/kill), and
   - false positive (an overfit combo this design would wrongly bless).
4. **Statistical-validity critique** of the walk-forward + PBO construction
   specifically (multiple testing, selection bias, the PBO interpretation, fold
   design, the objective function).
5. **Leakage vectors** we may have missed.
6. **What single change** would most improve the rigor of the verdict.

Be concrete and adversarial. "This is reasonable" is not useful; "here is the
exact scenario where this misleads you" is.

---

## 1. Research goal and the enemy

We search for **long-only, same-day (intraday) US stock trading strategies** with
a **positive, statistically reliable edge across multiple years and market
regimes** (2022 bear, 2023 chop, 2024 trend, 2025 mixed). Edge is measured in
**R** = multiples of risk per trade (+1R = target hit, −1R = stop hit).

**The enemy is overfitting.** This project has repeatedly been fooled by it:
- A small stratified "screen" (108 sampled days) made a 2-lever strategy (d14)
  look excellent — sign-flip permutation p=0.017, positive across years
  ex-2026 — and the full-day evaluation then **killed it** (negative in 2022 and
  2023). The screen flattered it via a ~24-day/year sampling fluke.
- Across 18 ungated strategy variants in 3 families, the ONLY consistently
  positive half-year was 2026-H1 — suspected to be a universe/data artifact, not
  alpha.

So this pipeline was built specifically to **not be fooled again**. Its entire
reason for existing is to make combinatorial filter search honest. Your job is to
find where it still could be fooled.

---

## 2. The strategy under study ("gap-and-go")

Each trading morning, for each stock in a point-in-time liquid universe (~1,300
names/day):
- **Admission (the minimum rule):** the stock's open is **> 1% above the prior
  day's high** (a gap-up breakout), the first 5-minute candle (09:30–09:35 ET) is
  green (close > open), and price ≥ $5.
- **Entry:** breakout above that first candle's high.
- **Risk:** stop at the first candle's low (= 1R), target at +1R, hard time-exit
  late morning (11:30 ET).
- **Outcome:** realized R per trade from a bar-by-bar execution simulator
  (includes fees/slippage).

In live deployment the strategy trades only the **top 10 candidates per day by gap
size** (a capital/attention cap). This top-10 cap is central to the evaluation
(see §5).

**Prior belief going in:** the unfiltered version of this strategy is a known
loser; the open question is whether some *subset* of candidates — selected by
admission filters on features known at 09:35 — has a durable edge.

---

## 3. Stage 1 — Feature capture (building the dataset)

**Goal:** replay every trading day 2022–2025, record every admitted candidate's
feature vector AND the realized R it would have earned, into one flat table.

**Key design choice — the subset invariant.** The capture admits *exactly* the
minimum rule (gap>1%, green, ≥$5) and applies **no further filter**, and it is run
**uncapped** (no top-10 cap). Therefore:
- Every more-restrictive admission-filter combination is a pure **row subset** of
  this one table.
- Because each candidate's trade is simulated **independently** (per-ticker, fixed
  1%-risk model, no shared capital constraint between candidates), removing
  candidates never changes the realized R of the ones that remain.
- So the entire combinatorial search becomes a **fast offline row-masking scan** —
  no backtests are re-run per filter combination.

**Leak-free contract (enforced in the feature layer):** a feature may use only
information knowable by **09:35 ET** on the trade date — the first 5-minute candle
and any *strictly prior* daily bar / prior 5-minute session / prior SPY & sector
data. Never the trade date's own daily bar, never any regular-session bar after
09:35. The universe is point-in-time (the membership that existed on each date),
so survivorship/look-ahead in universe selection is avoided. Prices are raw
(unadjusted); features over long windows are nulled if the window spans a >40%
jump (split/glitch guard); split/glitch trade-dates are dropped from capture.

**The captured ledger (the dataset under review):**
- **23,261 rows** (one per admitted candidate), 2022-01-03 → 2025-12-31, 970
  trading days with ≥1 candidate.
- Columns: `trade_date`, `ticker`, `score` (= gap %, used for the top-10 ranking),
  `filled` (did the breakout trigger and produce a trade), `realized_r` (the
  outcome; null if unfilled), `sector_etf`, + **87 leak-free features**.
- 80% of admitted candidates fill (18,712 trades).

**The 87 features (summary; full spec in the companion doc).** Grouped:
gap/overnight structure (7), first-candle microstructure (10), volume/participation
(6), the stock's own trend/volatility (6), relative strength vs SPY/sector (9),
calendar (7), prior-day full intraday structure from prior 5-min sessions (8),
trend/momentum incl. ADX & Kaufman efficiency (8), volatility regime incl.
realized-vol percentile (5), sector/market context (4), overnight structure (3),
liquidity (3), statistical z-scores & info ratio (5), and advanced range-based
volatility (Parkinson/Garman-Klass/Yang-Zhang) + inferred Roll spread +
prior-session return autocorrelation (6). All continuous or binary, all leak-free.

---

## 4. The baseline numbers (context for the search)

Deployment-realistic baseline = unfiltered admission, **top-10 by gap per day**,
realized R of filled trades:

| Year | trades | sum R | mean R | role |
|---|--:|--:|--:|---|
| 2022 | 1,223 | −46 | −0.038 | search |
| 2023 | 1,323 | −18 | −0.013 | search |
| 2024 | 1,454 | **+35** | +0.024 | search |
| 2025 | 1,576 | −67 | −0.042 | **OOS (sealed)** |

Search-window (2022–24) total: **−29 R**. The unfiltered strategy is a mild loser;
only 2024 (a trend year) is positive. **This is the baseline a filter combo must
beat to be interesting.**

---

## 5. Stage 2 — The combinatorial search

**Pre-registered filter grid (LOCKED before any scoring; this is round 1).** Nine
one-sided, thesis-bounded predicates, each a single cut on a single feature:

| predicate | rule (keep candidate when) | thesis |
|---|---|---|
| `gap_floor_3` | gap % vs prior high ≥ 3 | skip marginal gaps |
| `gap_ceiling_12` | gap % vs prior high ≤ 12 | skip exhaustion gaps |
| `rvol_min_1_5` | opening relative volume ≥ 1.5 | "in play" participation |
| `atr_frac_max_0_5` | first-candle range ≤ 0.5 × ATR14 | keep 1R reachable |
| `close_pos_max_0_9` | first-candle close in lower 90% of its range | anti-exhaustion |
| `spy_weak_regime` | SPY < its 50-day SMA | gap-up = relative strength when tape weak |
| `sector_weak_regime` | sector ETF < its 50-day SMA | same, per sector |
| `price_min_10` | first open ≥ $10 | avoid microcaps |
| `adv_min_1m` | 14-day avg daily volume ≥ 1e6 | liquidity floor |

- **Combinatorial size k ≤ 2** (round 1): the unfiltered baseline + all single
  predicates + all valid pairs = **46 combos**. (Two predicates on the same
  feature are disallowed except the gap floor+ceiling band.) k=3 is reserved for a
  *separately pre-registered* future round.
- **Top-N-after-filter:** for each combo, after row-masking, we re-apply the day's
  **top-10 by gap** before scoring — so each combo is measured exactly as it would
  trade in deployment, not as an unbounded basket.
- **Per-combo metrics:** trades, sum R, mean R, win rate, top-5 tail share
  (share of total R from the 5 best trades), min trades/quarter.
- **Constraints** (a combo is ineligible if it fails either): ≥ 50 total trades in
  the window AND ≥ 20 trades per quarter (the "enough trades to be meaningful"
  floor — single-digit-trade combos are statistically meaningless here).
- **Objective:** mean R, minus a small tail-share penalty (0.02 × top-5 share) as
  a tie-break that prefers broad edges over tail-driven ones. Ineligible combos
  get −∞.

**Explicitly NOT a gate: per-combo permutation p-value.** Under selection across
46 combos, the winner's individual sign-flip p is meaningless (the best of 46 has
a small p by construction). It was the exact thing that fooled us before. The
honest gates are walk-forward (§6) and PBO (§7).

---

## 6. Stage 3 — Walk-forward (the arbiter)

Expanding-window, time-ordered, refit each fold:

| fold | train (select the best combo) | test (score that combo, untouched) |
|---|---|---|
| 1 | 2022 | 2023 |
| 2 | 2022–2023 | 2024 |

**2025 is held entirely OUT** of capture-search/WF/PBO as the primary clean
out-of-sample year (a full normal-regime year nothing has touched). 2026-H1 is
deliberately NOT the holdout (it is the suspected-artifact window).

- **Selection** inside each fold: pick the combo maximizing the objective on the
  TRAIN window (subject to the constraints).
- **Scoring:** apply that train-selected combo to the held-out test year; record
  test sum R, mean R, trades/quarter.
- **Pass criteria (all required):** aggregate OOS sum R > 0; positive in **every**
  test fold; ≥ 20 trades/quarter on every test fold; and low PBO (§7).
- **Stability diagnostic:** log the combo selected per fold. If it changes every
  fold, that itself is evidence of no stable edge (reported, not hidden).

---

## 7. Stage 4 — PBO via CSCV (the overfitting guard)

**Probability of Backtest Overfitting** via Combinatorially-Symmetric
Cross-Validation (López de Prado, 2014):

- Build a performance matrix M of shape (T trading-days × N combos), where each
  cell is that combo's top-10 summed realized R on that day, over the search
  window (2022–2024 only; 2025 excluded).
- Slice the T days into **S = 16** equal contiguous blocks. Enumerate all
  C(16,8) = **12,870** ways to split blocks into an in-sample half (8 blocks) and
  the complementary out-of-sample half.
- For each split: rank all 46 combos by IS mean performance; take the IS-best;
  find its OOS relative rank `w ∈ (0,1)`; map to logit `λ = ln(w/(1−w))`.
- **PBO = fraction of splits where λ < 0** (the IS-best lands in the OOS bottom
  half). PBO ≳ 0.5 ⇒ the *selection procedure* is overfitting and no combo it
  picks is trustworthy, regardless of headline R.

---

## 8. Decision rule and discipline

- **Promote a combo** ONLY IF walk-forward passes (all criteria) AND PBO is low.
  Then it is frozen as a new immutable strategy release and run through the normal
  evaluation funnel, and only after that is the sealed OOS spent.
- **Otherwise:** record the clean negative; do not chase the best in-sample combo.
- **Alpha-spending:** the number of pre-registered search rounds is budgeted up
  front. "Search → peek at results → widen the grid → re-search" is forbidden — it
  launders degrees of freedom and is exactly what PBO is meant to catch. Round 1
  is k≤2 with the 9-predicate grid above; any expansion is a separate round.

---

## 9. The actual round-1 result (please sanity-check our reading)

- **Best IN-SAMPLE combo** (full 2022–2024): `gap_floor_3 + rvol_min_1_5` →
  1,517 trades, mean R **+0.027**, sum R +40.9, tail-share 0.12 (broad, not
  tail-driven). It beats the −29R baseline and looks like a real edge in-sample.
- **Walk-forward: FAIL.**
  - Fold 1 (train 2022 → test 2023): the 2022-selected combo was
    `spy_weak_regime + adv_min_1m`; on 2023 it returned **−24.9 R** (mean −0.074).
  - Fold 2 (train 2022–23 → test 2024): selected combo was
    `gap_floor_3 + rvol_min_1_5`; on 2024 it returned **+31.8 R** (mean +0.052).
  - Aggregate OOS +6.9 R, but only **1 of 2** test folds positive, and the
    selected combo was **different in each fold** (unstable).
- **PBO = 0.32** over 12,870 CSCV splits — below 0.5, so the search is *not*
  egregiously data-mining; the failure driver is **selection instability across
  regimes**, not pure noise-fitting.
- **Verdict: NO ROBUST EDGE.** We are treating this as: gap-and-go on this universe
  has no admission-filter subset (within this grid) with a stable cross-year edge.
  2025 OOS was not spent.

We see one thread we are deliberately NOT chasing: `gap_floor_3 + rvol_min_1_5` is
both the top in-sample combo and the fold-2 pick that delivered +31.8R OOS — the
most consistent signal in the run. The locked rule does not promote it (it lost
fold 1 to a different combo). Chasing it would be goalpost-moving.

---

## 10. Limitations we already see (extend / challenge these)

- Only **2 walk-forward folds** (3 search years) — thin. The "positive in every
  fold" rule is strict on 2 folds.
- Each fold **re-selects from scratch**; the "best on train" can be a different
  combo each fold (and was). Is that the right selection model, or should
  selection be pooled / shrunk?
- The grid is **9 hand-chosen predicates with fixed cut points**. Coarse by design
  (degrees-of-freedom control), but the thresholds (3%, 12%, 1.5, 0.5, 0.9, $10,
  1e6) are judgment calls.
- One feature in the broader set (`first_close_pos`, used by `close_pos_max_0_9`)
  was **reverse-engineered from in-sample loss analysis** — mildly contaminated.
- Trades are simulated **independently** with a fixed 1%-risk model and **no
  cross-trade capital constraint or correlation** — the subset invariant depends on
  this, but it also means portfolio-level effects (10 correlated same-day longs)
  are not modeled.
- The universe is **survivorship-aware point-in-time but liquidity-filtered** ("the
  liquid names that existed then") — results may still be an upper bound.
- PBO uses **contiguous** time blocks (regime-structured), not random — intentional
  (preserves autocorrelation/regime structure) but worth challenging.

---

## 11. The explicit asks (please answer directly)

1. Given the goal is a **trustworthy negative**, what is the strongest argument
   that this pipeline produced a **false negative** — i.e., there IS an edge here
   and the design hid it? (Consider: 2-fold thinness, per-fold re-selection
   discarding a combo that's good in 2 of 3 windows, the top-10 cap interacting
   with filters, the strict all-folds-positive rule, regime confounding where each
   test year is a different regime.)
2. Conversely, if we HAD gotten a "pass," what false-positive paths would still
   worry you? Is k≤2 over 9 predicates (46 combos) + PBO actually enough multiple-
   testing protection?
3. Is **PBO=0.32 with WF-fail** a coherent state, or does it reveal a tension in
   how we're combining the two gates? What does PBO<0.5 alongside an unstable,
   failing walk-forward actually tell us?
4. Attack the **objective function** (mean R with a 0.02 tail penalty, hard trade-
   count floor): what does it over/under-select for? Should it be risk-adjusted
   (Sharpe-like / per-quarter consistency) rather than mean R?
5. Attack the **top-10-after-filter** mechanic: a filter that removes high-gap
   names changes which candidates the top-10 cap admits — is scoring a combo this
   way sound, or does it create interactions that confound the per-combo edge?
6. Is the **subset invariant** (independent per-trade simulation) a fatal
   simplification for a strategy that would hold up to 10 correlated longs at once?
7. Leakage: any vector we missed — in the universe construction, the sector map,
   the prior-session features, the split guard, or the capture→ledger join?
8. If you had to defend this family as still potentially alpha-bearing, what ONE
   additional pre-registered experiment would you run, and why would it not just
   be goalpost-moving?
9. The single highest-leverage change to make the verdict more trustworthy.

Tell us where we are fooling ourselves.
