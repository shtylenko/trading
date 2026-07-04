# post_gap_opening_drive (d-series) — Backlog

Updated 2026-06-15.

## PHASE-B CONFIRMATORY OOS (2026-06-15): FAIL/KILL — gap-and-go RETIRED

Ran the pre-registered one-shot test (`validation/research_log/phase_b_oos_preregistration.md`)
of `gap_floor_3 + rvol_min_1.5` on the SEALED 2025 year. Result (binding):
- **2025 sumR = −34.1R** over 678 trades, meanR −0.050, daily IR −1.44.
- Only **1 of 4 quarters positive** (Q1 +4.5; Q2 −17.0, Q3 −5.7, Q4 −16.0).
- Locked criterion sumR ≤ 0 → **FAIL/KILL.** (It DID halve the unfiltered −66.8R
  2025 baseline — the filters remove some bad trades — but "loses less" ≠ edge.)

**The 2022–2024 positivity (every year, 3/3 leave-one-year-out, substitution-robust)
did NOT generalize to the one untouched year.** This is the methodology working: an
in-sample-robust combo still failed a clean holdout. Without the sealed 2025 we would
have promoted a money-loser to a release. gap-and-go (d-family) is retired with earned
evidence. No further 2025 tests are budgeted (a second look would burn the holdout).

**ENGINE CROSS-CHECK (2026-06-15): d15 = real backtest of the combo on eval_2025_broad,
to validate the offline subset-ledger vs the live engine.** Engine: **−30.1R / 760
trades, 1/4 quarters positive** (Q1 +1.0, Q2 −10.8, Q3 −1.9, Q4 −18.3) vs ledger −34.1R
/ 678 / 1-of-4. **Same sign, magnitude, quarterly shape, and KILL verdict** → the search
methodology is faithful. NOT bit-identical (~12% more trades; likely the RV computation
path: feature-lib `opening_rv` vs variant `opening_relative_volume` near the 1.5 boundary
+ fill timing). CALIBRATION: ledger is direction/magnitude-faithful → fine for fast
search/screening, but run the REAL engine for any final promote gate. d15 lifecycle =
killed.

## PHASE-A DIAGNOSTICS (2026-06-15): ROUND-1 VERDICT WAS A FALSE NEGATIVE (but see Phase B)

4-model peer review (peer-review/2026-06-15-evaluation/) unanimously flagged the
round-1 walk-forward as a selection artifact, not an edge test. Phase-A diagnostics
(`experiments/harness/feature_search_v2.py`, daily-portfolio IR objective, 2022–2024 ONLY, 2025
untouched) confirm it:
- **Fold-1 all-combos:** thesis combo `gap_floor_3+rvol_min_1.5` was POSITIVE in 2023
  (+5.6R, #3/46) — it just wasn't what 2022-alone selected (`spy_weak_regime+adv`,
  −24.9R, classic bear overfit). The "FAIL" was the 1-year-train argmax, not the edge.
- **Fixed thesis combo positive EVERY search year:** 2022 +3.5R, 2023 +5.6R, 2024
  +31.8R (IR +0.19/+0.30/+1.50). Cross-regime non-negative.
- **Substitution check (replace vs remove roster):** ~identical (40.9 vs 45.1R) → the
  edge is the predicate removing bad trades, NOT the top-10 substitution lottery.
- **Leave-one-year-out:** picks gap+rvol in 3/3 folds, 3/3 positive, +40.9R aggregate.
- **PBO (consistent daily-portfolio metric) = 0.32** — the lone caveat; it measures the
  SEARCH, not the specific combo. Combo's own robustness (3/3 LOO, +every year,
  substitution-robust, tail 0.11–0.12 broad) is the relevant evidence.
- Tempering: only 2024 is individually significant (t +1.49); 2022/23 positive-but-not
  (+0.19/+0.29). Edge is modest, trend-leaning. gap+rvol uses NEITHER the contaminated
  first_close_pos NOR the sector map; opening_rv baseline is prior-sessions-only (leak-free).
- **CONCLUSION: gap-and-go is NOT retired.** `gap_floor_3+rvol_min_1.5` earns ONE
  pre-registered confirmatory test on the sealed 2025 OOS (Phase B). NOT goalpost-moving:
  the combo + objective + pass/fail are pre-specified before 2025 is read.

## FEATURE SEARCH ROUND 1 VERDICT (2026-06-15, SUPERSEDED — see Phase-A above): NO ROBUST EDGE

Ran the pre-registered combinatorial search (`experiments/harness/feature_search.py`, k≤2,
9 thesis-bounded predicates → 46 combos) over the full 2022–2025 capture ledger
(`experiments/_data/_capture_2022_2025.parquet`, 23,261 candidate rows, 87 features),
deployment-realistic top-10/day, walk-forward (train 2022→test 2023; train
2022-23→test 2024), PBO via CSCV (S=16, 12,870 splits). 2025 sealed as OOS.
`search_id=fsearch_20260615_154316_535403`.

- **Baseline** (unfiltered top-10, 2022–24): −29.1R / 4000 trades, meanR −0.007.
- **Best in-sample combo**: `gap_floor_3 + rvol_min_1.5` → +40.9R / 1517, meanR
  +0.027, tail-share 0.12 (broad, not tail-driven). Looks like an edge IN-SAMPLE.
- **WALK-FORWARD: FAIL.** Fold 1 (train 2022) selected `spy_weak_regime+adv_min_1m`
  → 2023 test **−24.9R**. Fold 2 (train 2022-23) selected `gap_floor_3+rvol_min_1.5`
  → 2024 test **+31.8R**. Aggregate OOS +6.9R but only **1/2 folds positive** and
  the **pick is unstable** (different combo each fold) → fails the all-folds-positive
  criterion. **PBO=0.32** (below 0.5 — the search isn't egregiously overfit; the
  killer is selection instability across regimes, not pure data-mining).
- **Verdict: no promotable combo.** Consistent with d11/d13/d14 and the cross-family
  2026H1 finding: gap-and-go on this universe has no admission-filter subset with a
  stable cross-year edge. A clean negative — the family is retired with evidence,
  not one more hand-picked lever. 2025 OOS was NOT touched (still available).
- **One thread (NOT promoted, would need a SEPARATE pre-registered round):**
  `gap_floor_3 + rvol_min_1.5` is the top in-sample combo AND the fold-2 pick that
  delivered +31.8R OOS — the most consistent signal seen. But it lost fold 1 to a
  different combo, so the locked procedure does not promote it. Chasing it now would
  be goalpost-moving (the exact overfit trap the harness exists to prevent).

## PRE-REGISTERED (2026-06-14): d13/d14 — first-bar close-position gate

Frozen together BEFORE running, from a loser diagnostic on the d11 screen
ledger (`run_d11_screen_2022_2026_sampled_20260614_034220_1e68be`, 376 filled).
Slicing by where the first 5m candle closed within its own range,
`close_pos = (close − low) / (high − low)`, gave a monotonic mean-R gradient:

| close_pos | n | mean R | win% |
|---|---:|---:|---:|
| < 0.5 (lower half) | 59 | +0.30 | 66 |
| 0.5–0.9 | 221 | +0.11 | 58 |
| ≥ 0.9 (at the high) | 96 | −0.03 | 47 |

Thesis: a first bar that closes AT its high is exhaustion — the breakout entry
above it chases an extended move; a bar that closes lower but reclaims its high
to trigger shows real demand. New lever (not d07's gap cap nor d09/d10's ATR
band). On the d11 screen, dropping the top decile lifted meanR +0.106→+0.153 on
96 fewer trades and held ex-2026H1 (+32.5→+34.9R, 6/8 half-year buckets +).
Tightening to 0.75 over-filtered (cut winners, sumR +31.5) → threshold = 0.9.

- **d13** `max_first_close_pos=0.9` on the plain d01 baseline (NO regime gate) —
  isolates whether the geometry edge stands alone.
- **d14** d11's SPY<50d regime gate + `max_first_close_pos=0.9` — tests whether
  regime and geometry stack. Predicted ≈ +42.8R / 280 trades on the screen.

The comparison is the point: if d13 ≈ d14, geometry is the real edge and the
regime gate is secondary; if d14 clearly beats both, they are complementary.
Run: `for r in d13 d14; do python3 -m trading.lab.scripts.backtest --release $r --testset screen_2022_2026_sampled; done` then validate_run each.

**d13 VERDICT (2026-06-14): screen-survives but 2026H1-CARRIED → not a standalone
edge.** N=824, sumR +16.1, meanR +0.020, win 51.3%, perm p=0.332, top-5 share 31%
(R-ex-top5 +11.2 — not tail-driven). Gate passes (sumR≥0, p≤0.5). BUT ex-2026H1 =
**−17.8R**, only 5/9 half-year buckets positive; 2026H1 alone is +34R and carries
everything (2023H1 −9, 2023H2 −6, 2024H2 −5, 2025H2 −10). The geometry lever cleans
up the d01 baseline (meanR +0.004→+0.020, bleed shrinks) but does NOT generalize on
its own — confirms the pre-registered hypothesis that geometry needs a regime gate.
Contrast d11 (regime, no geometry): ex-2026H1 +32.5R, 6/8 buckets +.

**d14 VERDICT (2026-06-14): SURVIVES, levers STACK — keeper, advance to broad_is.**
N=309, sumR +48.7, meanR +0.158, win 59.5%, perm p=0.017, top-5 share 10%
(R-ex-top5 +43.8 — not tail-driven), ex-2026H1 **+38.2R**, 6/8 buckets +. d14
dominates d11 (regime only: +39.9R, meanR +0.106, p=0.051, ex-2026H1 +32.5) on
every axis — geometry strips the exhaustion losers that survive the regime gate.
Three-way conclusion (ON THE SCREEN): geometry alone (d13) fails 2026-carried;
regime alone (d11) robust; regime+geometry (d14) complementary and best.

**d14 STAGE-2 VERDICT (2026-06-14): KILLED on the broad eval — screen edge did NOT
generalize.** Full-day broad eval refutes the screen:
- eval_2022_broad: N=647, sumR **−6.8**, meanR −0.010, win 51.3%, p=0.587.
- eval_2023_broad: N=314, sumR **−16.2**, meanR −0.052, win 49.7%, p=0.830.
Both negative, both p>0.5 → stage-2 KILL. NOT a trade-count or universe artifact:
trades/qtr healthy (90–208, no thin quarters), avg universe ~1200–1360 tickers/
session (≈ the screen's 1360). The screen's positive 2022/2023 buckets (2022H1 +6,
2023H1 +16) were a **24-sampled-days-per-year fluke** — across all ~250 days/yr the
sign flips negative. Classic screen→broad collapse; d11's own docstring warned "the
broad eval, not this screen sample, is the real arbiter," and it arbitrated against
d14. The whole regime+geometry "ex-2026H1 robustness" was a sampling artifact.
NOTE: d11 and d13 were NEVER run on the broad eval — so "regime gate breaks the
2026H1 carry" is now UNPROVEN (it rested on the same flawed screen). **NEXT to settle
it: run d11 (regime only) on eval_2022/2023_broad. If d11 also fails broad, the
regime-gate conclusion was screen noise and the d-family is exhausted (again); if
d11 passes broad but d14 fails, geometry HURTS on full days.**

## SCREEN VERDICT (2026-06-13): d01/d03 survive (marginally), d02/d04 killed

d01 baseline + three one-lever variants on `screen_2022_2026_sampled` (108 days),
sign-flip gate (kill: sum R < 0 OR pooled p > 0.5):

| Rel | Lever | Trades | Sum R | p | ex-top-5 | Gate |
|---|---|---:|---:|---:|---:|:--:|
| d01 | baseline | 1049 | +4.5 | 0.47 | −0.5 | survives |
| d02 | RV ≥2 in-play filter | 678 | −18.8 | 0.73 | −23.8 | KILL |
| d03 | uncapped (drop 1R) | 1049 | +5.0 | 0.47 | −19.1 | survives |
| d04 | full-session hold (15:55) | 1095 | −14.6 | 0.64 | −19.6 | KILL |

**No improvement beat the d01 baseline:** RV filter HURT (removed good trades),
full-session hold HURT (gap drives fade after 11:30 — the early exit was right),
uncapping (d03) ≈ d01 net with more variance (top-5 = 483% of total). The simple
gap-and-go is already at its frontier; the obvious levers don't help.

**Survival is fragile — same 2026H1 dependence as every family.** d01's +4.5R is
entirely 2026H1 (+36.1R); 2022–2025 sum to −31.6R, and p=0.47 is a coin flip.
Across all 18 releases in 3 families, the ONLY consistently positive bucket is
2026H1. That is now a pattern → likely a regime or data/universe artifact in the
most-recent `liquid_pit` snapshot, flattering momentum AND mean-reversion alike.

**Next (pre-registered funnel — survivors get the full eval gauntlet):** run d01 on
eval_2022/2023/2024_h1/2025/2026_h1_broad. Honest expectation: fails the gate like
o03 (positive 2026H1, negative elsewhere). The eval also answers the real question —
is 2026H1 trustworthy? Do NOT promote d03 over d01 (no better, just noisier).

## Status (historical): Deferred

The d-series (gap-and-go) strategy work was **deferred until the o-series plan resolved**.

- `d01` — initial gap-and-go release (exists as code).
- `d02` (gap threshold + premarket volume filters) — folded into stocks_in_play_orb C12 feature engineering.
- `d03` (2R scale-out + 9 EMA trail) — folded into stocks_in_play_orb B7 exit ablations.

## Improvement backlog — from 2026-06-13 Gemini peer review

Source: `feedback/2026-06-13-d01-d04/{prompt.md,gemini.md}`. The review proposed
10 ideas. Triaged below against our engine, our constraints, and what's already
been killed. **One lever per release, pre-registered, same screen funnel + kill
rule.** Two reviewer factual errors to record so we don't act on them blindly:

- **Gemini's central data-mismatch thesis is WRONG for our lab.** It assumes
  split-*adjusted* daily vs *unadjusted* intraday. We use **raw/unadjusted on both
  sides** (`fetch_daily_context` default), so that mismatch cannot occur. BUT the
  conclusion partially survives: raw prices DO jump on split days (a reverse split
  = artificial gap-UP), and `research.filters.has_split_like_jump` (used by the ORB
  family) is **absent from the entire d-family** → d01 can buy reverse-split
  artifacts. So d05 below is worth doing, but as a known-guard backfill, not the
  fix Gemini imagined.
- Minor: review assumed candidate_limit=10 on the screen; it was 25 (eval uses 10).
- Astute and correct: losing money on a survivorship-biased (favorable) universe
  pre-2026 is itself a bad sign for intrinsic edge (review §4).

### DIAGNOSTIC RESULT (2026-06-13): contamination REJECTED
Read-only inspection of `run_d01_..._164145_7d80d7`: gap% across 1343 trades has
median 2.2%, max **33.2%**, **zero >40%** (nothing trips the 40% split guard). The
worst 2024-H2 losers are tiny price moves (−0.1% to −0.7%) that became ≈−1R via the
tight first-candle-low stop — i.e. **normal noise clip-outs, not split blow-ups.**
⇒ **d05 (split-jump gate) is a no-op for this family — DROP it.** The pre-2026 bleed
is genuine negative edge (same microstructure clip that killed ORB), not a data
artifact. 2026-H1 dominance is therefore macro-regime or survivorship → **d08
(relative-SPY gap) is now the key remaining diagnostic.**

### DIAGNOSE 2026-H1 FIRST (highest priority — most ideas are moot if it's an artifact)
Before polishing filters, resolve why every family is positive only in 2026-H1.
Cheap diagnostics, do these first:
- **Inspect the top-5 2024-H2 losers in d01** (`run_d01_..._164145_7d80d7`): were they
  split / corporate-action / huge-raw-gap days? If yes → contamination; d05 fixes it.
- d05 (split-jump gate) and d08 (relative-to-SPY gap) are themselves diagnostics:
  if pre-2026 stabilizes after d05 → contamination; if d08 kills the 2026-H1 bucket
  → it was macro beta, not idiosyncratic alpha.

### BUILT 2026-06-13 — quick screen batch (d05–d10), awaiting screen run
Six one-lever variants, all pre-registered, screen-runnable:
- **d05** split/glitch guard (`split_guard=True`, has_split_like_jump). CONTROL —
  expected ~no-op (diagnostic found 0 gaps >40%); run to confirm empirically.
- **d06** VWAP confluence (`require_above_vwap=True`). Needed an engine change:
  `simulate_long_breakout` now computes session VWAP and rejects (NO_FILL) a
  breakout that triggers at/below VWAP — gated by the `require_above_vwap`
  metadata flag (no-op for all other strategies; ORB/flip regressions confirm).
- **d07** gap ceiling: 1% ≤ gap ≤ 8% (`max_gap_pct=8.0`).
- **d08** relative-SPY gap ≥ 2× (`min_rel_spy_gap=2.0`, `requires_spy_daily`). 2026-H1 diagnostic.
- **d09** first-candle range ≤ 0.5×ATR14 (`max_candle_atr_frac=0.5`).
- **d10** first-candle range ≥ 0.3×ATR14 (`min_candle_atr_frac=0.3`) — anti-clip, diagnostic-driven (NOT from Gemini; from the tight-stop finding). Paired with d09 to bracket candle size.
Run: `for r in d05 d06 d07 d08 d09 d10; do python3 -m trading.lab.scripts.backtest --release $r --testset screen_2022_2026_sampled; done` then validate_run each.

### TIER 1 — implement now (cheap, no engine work; includes the diagnostics)
- **d05 — split-jump hygiene gate** [Idea 1, reframed]. Add `has_split_like_jump`
  (raw-price guard, the ORB family already uses it) to `build_candidates`; discard
  any name whose trailing window or open shows a >40% jump. Attacks: artificial
  reverse-split gap-ups; the pre-2026 bleed. Data: daily only.
- **d06 — VWAP confluence** [Idea 3]. Require first-candle close > running VWAP AND
  entry_trigger > VWAP at the breakout. Don't buy a "gap-up" that's already below
  the day's institutional cost basis (trapped supply). Attacks: low-conviction
  entries / continuous bleed. Data: 5m only.
- **d07 — gap magnitude band** [Idea 4]. Replace `gap ≥ 1%` with `3% ≤ gap ≤ 10%`:
  cut sub-noise gaps and >10% exhaustion gaps. Attacks: trade count / quality. NOTE:
  ORB's o05 (≥3% floor) died, so the *ceiling* is the novel part — consider testing
  the ceiling alone (e.g. `1% ≤ gap ≤ 8%`) as the cleaner one-lever.
- **d08 — relative-strength gap vs SPY** [Idea 10]. Require `gap_pct ≥ 2 × SPY_gap_pct`
  (needs `requires_spy_daily` + spy_5m). Isolates idiosyncratic catalyst from macro
  beta. **Directly targets the 2026-H1 macro-melt-up hypothesis.** Data: SPY daily+5m.
- **d09 — ATR-normalized first-candle cap** [Idea 5]. Reject setups where first-candle
  range > 0.5 × ATR14, so the 1R target stays reachable and we skip already-exhausted
  opens. Attacks: the unreachable-1R / inverted-payoff problem. Data: daily ATR
  (have `daily_atr_14`). (Entry *gate* on candle/ATR ratio — distinct from ORB's stop
  *widening* lever.)

### TIER 2 — implement next (needs extended-hours 1m bars: `requires_extended_1m`)
- **d10 — pre-market volume conviction** [Idea 2]. Require cumulative 04:00–09:30
  premarket volume above a floor / percentile. Distinguishes genuine overnight
  catalysts from spread-drift. Differs from the failed d02 (which used *regular-hours*
  opening-bar RV and was anti-selective — that volume is MOO-imbalance distribution).
- **d12 — pre-market-high trigger** [Idea 7]. `entry_trigger = max(first_candle.high,
  premarket_high)`. Don't breakout-buy into unbroken premarket overhead supply.

### TIER 3 — needs engine support (defer; flag potential)
- **d11 — entry-window TIF (cancel after 10:00)** [Idea 9]. Only fill the breakout if
  it triggers before 10:00 ET; an opening drive that takes until mid-morning is just
  chop. Small simulator addition: honor an `entry_deadline` in signal metadata (mirror
  of the `max_hold_bars` hook we already added). Distinct from d04 (exit timing) — this
  is entry validity.
- **SWEEP-AND-RECLAIM ENTRY** [Idea 6]. Enter long only after price sweeps below
  first-candle low then reclaims first-candle open; stop = sweep low. Needs a new
  conditional entry paradigm (current sim only does breakout_stop / pullback_limit) →
  new `entry_style` + simulator path. High effort, but the most original idea —
  turns the "stopped out then it ran" failure into the entry.
- **FRACTIONAL SCALE-OUT + TRAIL** [Idea 8]. Sell 50% at +1R, move stop to breakeven,
  trail the rest on prior-5m-low to the cutoff. Needs partial-exit + trailing-stop
  support in the simulator (today: single stop/target/cutoff/time-stop). Directly
  fixes both d01's clipped tail and d03's round-trips — high value, real engine work.

### NOT pursuing
- None outright rejected, but d07's gap *floor* alone repeats o05 (dead); lead with
  the ceiling. d10/d12 share the premarket-data dependency — load it once.

## Open

- Pending d01 full-eval gauntlet (user to run): eval_2022/2023/2024_h1/2025/2026_h1.
- After diagnostics (d05/d08 + manual 2024-H2 loser inspection), build the Tier-1
  batch as a pre-registered `variants.py` (DriveVariant already exists) and screen.

## Decisions

- `d01` was a first release alongside `o01`.

## Audit follow-up (2026-06-18 codebase review) — needs fix-forward releases / doc updates

From the 2026-06-18 whole-tree audit. Immutable code (`variants.py`, shipped releases)
→ fix forward or doc-only-in-a-new-release, never in place. (Audit was only ~half-
reliable; items tagged with check status. All LOW/MEDIUM here — the d-family is
effectively retired, so these are housekeeping for any future drive release.)

- **M7 — undocumented ATR-availability gate** (`variants.py:126-130`). When
  `max_candle_atr_frac` / `min_candle_atr_frac` is set, candidates lacking enough daily
  history for ATR14 are silently skipped. Behaviour is CORRECT (no ATR → can't apply the
  filter), but neither d09 nor d10 docstrings mention the implicit dependency. Document
  it in the next release that uses the lever.
- **M8 — `historical_5m_lookback_days` declared on leaves, not the `DriveVariant` base**
  (`d02.py:23`, `d15.py`, `capture.py`). Only the releases that need it set it; a future
  variant that needs RV history but forgets to set it would silently default to 0.
  Discoverability nit — consider hoisting a documented default onto the base in a new
  release.
- **L4 / L6 — stale docstrings.** `variants.py:1` says "d02–d04 / three pre-registered"
  but now backs d02–d15. d01/d11/d12/d14 "Next intended releases" sections predict
  follow-ons that were built differently or not at all. Docstrings are immutable bytes
  too (they feed the code signature), so correct them only via a new release or leave as
  historical record — do NOT edit the shipped files in place.
