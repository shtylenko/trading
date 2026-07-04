# Multi-Day Momentum — Stage-0 triage findings (2026-06-16)

The recommended next bet from STRATEGY_SYNTHESIS.md §4 (multi-day swing, long-only):
does a cross-sectional momentum signal predict forward H-day returns on our universe?
Measured OFFLINE on daily bars (`scripts/multiday_momentum_triage.py`), no engine
change. Cross-sectional decile of forward H-day return, NON-overlapping rebalance
(every H trading days → honest, non-overlap-inflated Sharpe). Search years 2022–2024
only; 2025 SEALED.

## Result — 12-1 momentum (mom_12_1) is a clean, monotone, every-year-positive signal

`mom_12_1 = close(d−21)/close(d−252) − 1` (12-month return skipping the last month).

| | H=5d (151 rebal) | H=20d (38 rebal) |
|---|---|---|
| decile monotonicity (Spearman, rank vs fwd) | **+0.96** | **+0.90** |
| top-decile long-only mean | +0.30%/period | +0.95%/period |
| top-decile long-only ann. Sharpe | +0.62 | +0.55 |
| top-decile hit rate | 57% | 63% |
| top-decile by year | 2022 +0.02, 2023 +0.30, 2024 +0.59 | 2022 +0.14, 2023 +0.97, 2024 +1.82 |
| D10−D1 spread ann. Sharpe (L/S potential) | +0.71 | +0.89 |

- **Near-perfect decile monotonicity** (+0.96 / +0.90): forward return rises almost
  monotonically from bottom decile (−0.56% at H=20) to top (+0.93%). A real
  cross-sectional relationship across ~1,750 names, not a lucky tail.
- **Positive in EVERY search year, incl. the 2022 bear** — the first signal in the
  project to manage this (o/d/f/m/overnight all died in 2022).
- **Costs are a non-issue** (unlike overnight): +0.95%/rebalance at H=20 with ~12
  rebalances/yr dwarfs ~10–20 bps turnover. The cost-fragility that killed overnight
  does not bind here.
- **Long/short > long-only** (spread Sharpe 0.89 vs 0.55), as momentum theory
  predicts — flags long/short as a strong later extension, but the long-only tilt is
  already a real, tradeable edge.

## Other signals tested (weaker — mom_12_1 is the clear winner)

- `mom_6_1` (6-month, skip 1m): monotone-ish (+0.76/+0.66) but weaker, negative in
  2022 (−0.35/−1.33). The 12-month formation is materially better.
- `prox_52w` (George–Hwang 52-week-high proximity): DISAPPOINTING — monotonicity
  +0.07 at H=5 (top decile actually negative). Does not work cleanly here.
- `rev_1m` (1-month reversal sanity): top decile ~flat; the long/short is mildly
  positive but it's a different (reversal) effect, noisy at these horizons.

## Verdict & next step

**Stage 0 PASSES decisively** — `mom_12_1` is a genuine, monotone, cost-robust,
every-year-positive cross-sectional momentum signal. This is the first project result
that looks like real ALPHA (a monotone cross-sectional relationship), not beta or a
tail fluke. It warrants the full pipeline.

## Stage 1–2 — capture + pre-registered search (2026-06-16): first REVIEW in the project

Built `scripts/capture_multiday.py` (1.9M name-days, 1.3M eligible, leak-safe) and
`scripts/multiday_search.py` (reuses the trusted scoring; pre-registered grid in
`multiday_search_spec.md`). Ran the pre-committed matrix (top-N=50, score=mom_12_1):

| Run | WF | PBO | DSR | verdict |
|---|---|---|---|---|
| H=5, 10 bps, no overlay | 2/3 (2022 fails) | 0.21 | 0.90 | NO EDGE |
| **H=20, 10 bps, no overlay** | **3/3 PASS** | **0.48** | **0.94** | **REVIEW** |
| H=5, 10 bps, regime overlay | 1/3 | 0.54 | 0.74 | NO EDGE |
| H=5, 0 bps (gross ref) | 2/3 | 0.21 | 0.94 | NO EDGE |

**H=20 (monthly) momentum on liquid + low-vol names (`liquid_50m+calm_vol`) reaches
REVIEW — the FIRST time anything in this project cleared WF + PBO.**
- WF PASS 3/3 folds positive INCLUDING the 2022 bear (+204% / +990% / +1486%) — the
  only strategy to survive every search year.
- PBO 0.48 (not overfitting; borderline under 0.5).
- DSR 0.94 — just short of the 0.95 gate (per-period SR 0.27, ann ≈ 0.96, n=38).

Readings:
- **H=20 works, H=5 doesn't**: the 5-day horizon can't get past 2022 even gross (WF
  2/3). Momentum needs the monthly horizon to express; the weekly is too noisy.
- **The regime overlay HURTS** (PBO 0.54, DSR 0.74): unlike overnight (a beta-timing
  play), momentum is NOT beta — gating on SPY trend just thins the sample and the few
  surviving 2022 uptrend windows were bad for momentum. Confirms momentum ≠ beta.
- **`calm_vol` (low-volatility) is the value-add conditioning**: the WF winner pairs
  liquidity with low idiosyncratic vol — consistent with the documented "momentum is
  stronger / less crash-prone among low-vol, high-quality names."
- Honest caveats: n=38 non-overlapping rebalances is SMALL (PBO 0.48 / DSR 0.94 are
  fragile there); WF picks not combo-stable. It's a REVIEW, not a PROMOTE.

**Verdict: REVIEW — a real, modest, multi-year-robust long-only momentum edge that
just misses the demanding DSR gate.** The best lead the project has produced. Per
discipline it does NOT clear promotion (DSR < 0.95), so the sealed 2025 year is NOT
spent. Open decision (genuine fork): (a) accept as REVIEW, bank it, don't spend the
holdout; (b) pursue the LONG/SHORT version (Stage-0 D10−D1 Sharpe 0.71–0.89 ≫ the
long-only 0.55 — the higher-ceiling path, needs a short-leg engine); (c) improve the
small-sample power as a NEW pre-registered round (e.g. multi-phase overlapping
rebalances with an H-day embargo) before any sealed-year decision. Do NOT silently
re-tune to nudge DSR over 0.95 (gate-calibration is a code-reviewed change, per the
synthetic-control discipline).

## Stage 2.5 — power / robustness round (2026-06-16): REAL but MARGINAL on 3 years

`scripts/multiday_power.py` — (1) full search at all 20 rebalance-phase offsets
(phase robustness, no fake power), (2) HAC (Newey-West, lag H−1) significance of the
pre-specified winner on the daily-formation overlapping cohort series. Honest ceiling
stated up front: 3 years ≈ 38 independent 20-day periods; overlap improves estimate
STABILITY, not degrees of freedom.

- **Phase robustness:** WF PASS in **13/20** phases (65%); DSR across phases median
  **0.96** (11/20 ≥ 0.95), PBO median 0.44 (17/20 < 0.5). BUT the exact combo
  (`liquid_50m+calm_vol`) wins in only **5/20** phases — several near-equivalent
  liquid/calm/price conditioners trade places (the conditioning isn't pinned down,
  though SOME conditioned momentum book passes WF in most phases).
- **HAC significance:** per-cohort mean net +1.60%/20d, annualized Sharpe **+0.86**,
  Newey-West t = **+1.96** — significant but EXACTLY at the boundary (naive t +6.63
  was the overlap illusion; HAC deflated it ~3.4×, sound).

**Readout: the long-only 12-1 momentum edge is REAL but MARGINAL on 2022–2024** —
every gate lands right at threshold (DSR ~0.95 median, HAC t ~1.96) and the exact
conditioning combo is phase-unstable. It did NOT clear "cleanly". Per discipline +
cross-family alpha-spending, this does NOT warrant burning the one-shot sealed 2025
holdout. **Honest path to a decisive verdict (recommended): EXTEND in-sample history
pre-2022** (e.g. 2010–2021 → ~120 independent monthly periods vs 38) for a decisive,
non-marginal DSR/HAC read BEFORE spending 2025; OR pursue the higher-Sharpe LONG/SHORT
version (Stage-0 D10−D1 0.71–0.89). Do NOT re-slice these 3 years further (diminishing,
and risks fishing).

## Stage 2.6 — extended history 2017–2024 (8-fold LOO, 2026-06-16): edge CONFIRMED real, conditioning dead, magnitude modest

Captured 2017–2021 via `capture_multiday --fixed-universe-asof 2022-01-03` (the 2022
liquid_pit ticker set applied pre-2022 with rule eligibility — SURVIVORSHIP-limited,
optimistic for long). Concatenated with 2022–2025 → `_capture_multiday_2017_2025.parquet`.
Ran `multiday_search --all-pre-oos-years` (H=20): 8-fold leave-one-year-out, 2025 sealed.

- **DSR = 0.997** (was 0.94 on 3yr — more data made it decisive), pooled non-overlapping
  **t = +2.61** (winner +2.81), annualized Sharpe ≈ 1.0, **6/8 LOO years positive**.
- **WF verdict FAIL, PBO 0.92** — BUT both are artifacts of the CONDITIONING SEARCH,
  not the edge: all 29 combos are near-identical "top-50 momentum + tiny filter", so
  (a) PBO 0.92 = picking the best conditioner is pure overfitting (the conditioners
  are noise — confirms the power round's 5/20 combo-instability), and (b) the WF
  all-folds-positive rule collides with momentum's DOCUMENTED crash years (2021 ≈flat,
  2022 negative). The base UNCONDITIONED momentum is the signal; conditioning adds
  nothing → drop the grid.
- **Survivorship confound:** the 8-yr strength is partly inflated — 2017–2021 uses the
  survivorship-limited fixed universe (winners survived → optimistic). The
  survivorship-CLEAN evidence is still 2022–2024 (true PIT) = the marginal REVIEW
  (DSR 0.94, Sharpe ~0.86). So the honest magnitude is MODEST; the extension confirmed
  the SIGN/REALITY decisively but not a large clean Sharpe.

**Verdict: 12-1 long-only momentum is CONFIRMED a real edge** (decisively significant
across 8 years incl. survivorship-clean 2022–2024; matches 50yr literature; sign +
significance robust), **but (a) the edge is the BASE unconditioned rule — the
conditioning grid is dead (PBO 0.92), and (b) its survivorship-honest magnitude is
modest (Sharpe ~0.86) with intrinsic momentum-crash risk (2021–22).** This is the
project's FIRST confirmed-real alpha. The candidate for the sealed-2025 test is the
PRE-SPECIFIED BASE rule (long-only top-50 12-1 momentum, monthly rebalance, $10/$10M
liquidity floor) — NOT a searched combo (so ~no selection bias to deflate). 2025 is a
survivorship-honest PIT year → the clean confirmatory test.

## Stage 5 — SEALED-OOS 2025 confirmatory test (2026-06-16): PASS

Pre-registered (`multiday_oos_preregistration.md`), read once. Base rule (top-50 12-1
momentum, monthly, $10/$10M floor, 10bps), survivorship-honest 2025 PIT:
- per-period net **+3.98%**, annualized **Sharpe +1.08** (≥0.5) → **PASS**.
- cross-sectional premium **+2.78%** (top-50 net vs eligible-universe gross) → genuine
  momentum tilt, NOT 2025 beta. Decile monotonicity +0.56 (holds). HAC t +1.31 (weak —
  one year, color only, pre-registered as such).

**12-1 long-only momentum is the project's FIRST end-to-end validated edge: confirmed
in-sample (8yr, DSR 0.997, t+2.61, 6/8 yrs) AND out-of-sample (2025 PASS, +2.78%
cross-sectional premium).** A real, MODEST edge (Sharpe ~1.0) with intrinsic crash risk.
2025 now 2/3 spent. Next: multi-day-hold ENGINE cross-check → normal funnel → 2026-H1
sealed year for the 2nd independent confirmation. The long/short version (D10−D1 Sharpe
0.71–0.89) is the higher-ceiling extension. Simulation is optimistic → owes a
portfolio/capacity/borrow review before capital.

## Stage 6 — independent cross-check (2026-06-16): REPRODUCES (pipeline sound)

`scripts/multiday_engine_xcheck.py` — a ground-up daily-bar backtest that recomputes
momentum, eligibility, forward returns and cost from FRESHLY-FETCHED raw closes, with
NO reuse of the capture parquet or search code (the engine proper is intraday-only; a
full multi-day StrategyRelease is deferred until we commit to trading). 2025:

| metric | offline pipeline | independent cross-check |
|---|---|---|
| per-period net | +3.98% | +3.46% |
| ann Sharpe | +1.08 | +0.92 |
| cross-sectional premium | +2.78% | +2.12% |

Same sign + magnitude; the small gap is the expected sampling difference (OOS used
daily-formation overlapping cohorts; cross-check uses 13 non-overlapping phase-0
rebalances) — analogous to the d-family's ~12% ledger-vs-engine gap. **No look-ahead /
join / shift / cost bug → the capture→search→OOS pipeline is validated.**

## STATUS: momentum validated Stage 0 → 5 + an INDEPENDENT cross-check. NOT yet
## through the real engine (Stage 6 proper). Remaining:
- **Real engine Stage-6 is NOT done.** The cross-check above is a separate hand-written
  daily-bar re-implementation, NOT a run through `core/execution.py` + `runner/pipeline.py`
  + the DuckDB ledger. The engine is session-isolated (per-trade-date, intraday cutoff)
  and CANNOT hold a position across days as-is → a real multi-day StrategyRelease is a
  major engine refactor (runner loop + simulator + models + trades schema). Deferred:
  build it only when committing toward trading, AFTER the 2026-H1 confirmation.
- 2026-H1 sealed year = independent 2nd confirmation (earmarked, oos_spend_ledger) —
  cheap, offline, same pipeline. The real next validation gate.
- Long/short version (D10−D1 Sharpe 0.71–0.89) = higher-ceiling extension.
- Portfolio/capacity/borrow review before any capital (the simulation is optimistic).

## Complement triage (2026-06-16): NO long-only equity factor diversifies momentum

`scripts/multiday_complement_triage.py` (offline, 2017–2024, H=20). Sought a long-only
daily signal to smooth momentum (project goal: complementary regime biases). Books:
momentum (top-50 mom_12_1) vs low_vol (bottom-50 vol_20d), st_reversal (bottom-50
rev_1m), near_low (bottom-50 prox_52w), short_mom (top-50 mom_3_1).

| book | standalone Sharpe | corr w/ momentum | 50/50 combo Sharpe |
|---|---|---|---|
| momentum | +0.92 | 1.00 | +0.92 |
| low_vol | +0.37 | +0.56 | +0.85 |
| st_reversal | +0.51 | +0.78 | +0.76 |
| near_low | +0.55 | +0.69 | +0.77 |
| short_mom | +0.90 | +0.86 | +0.94 (≈ more momentum) |

**Finding: no long-only equity signal diversifies momentum.** All correlations are
POSITIVE (+0.56…+0.86 — shared market beta), and no 50/50 blend beats momentum alone
(+0.92); the least-correlated (low_vol) is too weak standalone to help. Structural
consequence of NO SHORTING: long-only equity factors are all long the market →
intra-equity factor diversification is fundamentally limited. Real smoothing must come
from (a) a NON-EQUITY defensive sleeve (bonds/gold/cash) rotated in risk-off, or (b) a
REGIME/TREND overlay that moves momentum to cash when the trend breaks (cut drawdowns).
Both are capital overlays (consistent with the overnight regime-overlay finding).
Bonus: the UNCONDITIONED momentum book was positive every year 2017–2024 incl. 2022
(+1.3%) — the 2022 weakness was specific to CONDITIONED variants; the base rule is more
robust than first characterized (pre-2022 survivorship-lifted, treat as upper bound).

## Defensive-sleeve rotation (2026-06-16): does NOT smooth — momentum best standalone

`scripts/multiday_defensive_sleeve.py` — risk-on (SPY>200d) hold momentum, risk-off
rotate to cash/TLT/GLD. 2017–2024, H=20, 10bps.

| strategy | Sharpe | maxDD | total |
|---|---|---|---|
| ALWAYS momentum | +0.92 | −31.1% | +543% |
| mom⇄cash | +0.80 | −37.9% | +295% |
| mom⇄TLT | +0.69 | −49.3% | +227% |
| mom⇄GLD | +0.83 | −40.8% | +321% |
| mom⇄TLT+GLD | +0.76 | −45.0% | +272% |

**Every rotation LOWERED Sharpe AND DEEPENED max drawdown.** Why: (1) the SPY<200d
trigger whipsaws — only 18/101 risk-off periods, and exiting momentum on them hurt; in
2022 always-momentum was +1.3% but every rotation went NEGATIVE (the flag pulled out
right as momentum recovered); (2) TLT failed as a hedge in 2022 (rate shock → stocks
AND bonds fell together, stock-bond corr flipped positive) — the diversifier broke in
the one regime it was needed.

## Stage 6 PROPER — REAL engine cross-check (2026-06-16): REPRODUCES

After 3-model peer review (peer-review/2026-06-16-swing-engine/, synthesis.md) of the
additive swing engine path (core/execution.simulate_daily_hold, SwingStrategyRelease,
x01, runner/swing_pipeline.py — intraday engine untouched), ran x01 on
`momentum_swing_2025` through the REAL engine + DuckDB ledger. Gross run + −10bps
additive (matching offline costs). 13 rebalances, 650 trades, all TIME_EXIT, 50/rebalance,
0 drops.

| metric | offline OOS | independent re-impl | REAL engine |
|---|---|---|---|
| per-period net | +3.98% | +3.46% | +3.46% |
| ann Sharpe | +1.08 | +0.92 | +0.92 |

Engine ≈ independent re-impl exactly (same non-overlapping grid); both just under the
offline OOS (daily-overlapping-cohort sampling, slightly higher) — the benign gap the
reviewers predicted. **The offline pipeline is now validated through the production
engine — the genuine Stage 6.** Peer-review fixes applied: liquidity filter fail-CLOSED;
swing runner skips the intraday-tuned funnel auto-eval (calls summarize_run only).

## Portfolio / capacity review (2026-06-16, `scripts/multiday_portfolio_review.py`)

The "simulation is optimistic" gate (EXPLORATION_PLAYBOOK §6b), offline on the
survivorship-honest 2022–2024 PIT window:
- **Turnover 30% one-way** — ~70% of the top-50 persist month-to-month (momentum is
  sticky). So the 10-bps headline (which assumed 100% turnover) OVER-charges; realistic
  turnover-scaled cost ≈ **3 bps/rebalance** → net Sharpe (0.69) ≈ gross (0.70). The
  cost-fragility concern is resolved: momentum is cheap to run.
- **Drawdown −20.2% max** (worst rebalance −15.2%, 58% positive periods) — the risk to
  size against.
- **Capacity ~$48M median AUM** (10th pct $30M) at ≤5% of each name's 1-day $-volume
  (least-liquid name binds); scales ~linearly if entries are spread over the 20-day hold.
  Fine for small/mid AUM, a real ceiling for large.
- **HONEST MAGNITUDE:** on the clean 2022–2024 PIT window alone, net Sharpe is **~0.69** —
  MORE MODEST than the ~1.0 headline, which was lifted by survivorship-optimistic
  pre-2022 + the strong 2025. The deployable edge is Sharpe ~0.7 with ~20% drawdowns.
- Still owes live borrow/slippage validation (broker data) before capital.

## CONCLUSION (diversification path closed): MOMENTUM IS BEST DEPLOYED STANDALONE.
No long-only smoother helps — equity factors all share market beta (complement triage),
and defensive-sleeve/regime rotations hurt Sharpe and drawdown (whipsaw + bonds failing
in 2022). Given the no-shorting constraint, intra-long-only portfolio smoothing is
structurally blocked. The validated deliverable is the STANDALONE momentum book
(top-50 12-1, monthly): real, modest (~1.0 Sharpe, survivorship-lifted), confirmed
in-sample 2017–2024 + sealed-OOS 2025. Realistic next steps: (a) productionize via the
multi-day engine refactor when moving toward trading; (b) bank and await 2026 data for
the 2nd sealed confirmation (~early 2027). [caveat: triggers/sleeves not exhaustively
searched — but over-tuning a regime trigger would be fishing; the TLT-2022 failure and
factor-beta correlation are structural, not tuning artifacts.]

## (original Stage-0 next-step note, now superseded by the runs above)
Next (Stage 1–2): build the multi-day capture (it's ~the panel this triage already
computes — daily leak-safe features + forward-H label) and run the trusted search
(LOO-WF → PBO → DSR → sealed-2025) over a PRE-REGISTERED momentum grid:
formation window (12-1 confirmed best; test 6-1 as a band), holding horizon (5 vs 20),
plus conditioning predicates (liquidity, price, idiosyncratic vol, a market-regime
overlay). Honest expectation: the long-only top-decile Sharpe (~0.55–0.62 gross) is
modest — it will need to clear DSR (demanding) and the realistic-cost minimum effect
size; the long/short version is the higher-ceiling follow-on once a short leg exists.
Caveat: H=20 has only 38 rebalances in 2022–2024 — the search must respect the small
non-overlapping sample (favor H=5 for statistical power, or pool horizons).

---

## Split-adjustment bug + clean re-confirmation (2026-06-16)

**Bug.** The entire offline pipeline (capture_multiday, multiday_engine_xcheck) and the
swing engine (runner/swing_pipeline) fetched daily bars with the intraday convention
`adjustment="raw"`. Raw is correct only for *same-day* intraday trades (which can never
straddle a split); a multi-day momentum hold CAN cross a split, and a split inside the
252-day lookback corrupts the rank. Symptom: SEZL (6:1 split 2025-03-31) booked a phantom
−86% / −8.6R hold in the x01 engine run; split-adjusted it is the true −16.8% / −1.68R.

**Fix.** `SwingStrategyRelease.daily_adjustment="split"` (threaded through
swing_pipeline._load_daily_bars); `capture_multiday --adjustment split` (default);
multiday_engine_xcheck split-adjusted. New ledgers: `_capture_multiday_2022_2025_split.parquet`,
`_capture_multiday_2017_2021_split.parquet`, concatenated `_capture_multiday_2017_2025_split.parquet`.

**Re-confirmation (multiday_search, H=20, top50, 10bps, 2022–2024; 2025 sealed-in-script).**
Clean data STRENGTHENS the edge — the raw contamination was biasing *against* it:

| gate | RAW | SPLIT (clean) |
|---|---|---|
| WF (LOO) | PASS 3/3 | PASS 3/3, pick-STABLE (liquid_50m+calm_vol all folds) |
| WF agg net | +2680% | +3385% |
| PBO | 0.483 | 0.236 |
| DSR | 0.941 (REVIEW) | 0.968 (clears 0.95) |
| winner per-period SR | +0.270 / ann +0.96 | +0.321 / ann +1.14 |
| verdict | REVIEW | PROMOTE-CANDIDATE |

**Honest caveats.** (1) 2025 is NOT a fresh sealed test — already spent on the raw version
+ re-seen in the x01 engine run; clean evidence is in-sample 2022–2024 only. (2) The base
UNCONDITIONED book got slightly WEAKER on clean data (per-period t +1.14→+0.86); the clean
"promote" rests on the `calm_vol` (low-volatility) conditioning — this partially revises the
earlier "conditioning is noise" conclusion, which was drawn on contaminated data. On 38
periods some of this can still be selection noise. (3) Magnitudes still modest (ann Sharpe ~1).
**Implication for x02:** volatility management (calm_vol is now load-bearing) is the indicated
refinement → motivates a vol-scaled / risk-managed momentum x02, pre-registered against the
clean base 12-1 baseline. The x01 engine re-run on split bars: sum_R 231→286 (ranking changed,
not just SEZL) — corrected accounting, still independent-trade sim.

## x02 vol-scaled momentum — KILLED (2026-06-16)

Pre-registered `multiday_x02_volscaled_preregistration.md` (LOCKED, σ_target Option B), run via
`scripts/multiday_volscale.py`. V1 inverse-vol weights, V2 constant-target-vol scaling, vs base
equal-weight. Clean 2022–2024: V1 looked better (Sharpe +0.68 vs +0.50, flips 2022 bear) but
missed DSR 0.95. Clean 8yr (101 periods, confirmatory): base +0.88/DSR 0.992, V1 +0.85/0.990,
V2 +0.89/0.992 — indistinguishable; the 3yr V1 lift was small-sample (2022-specific). VERDICT:
x02 KILLED — vol-scaling adds nothing to LONG-ONLY momentum (it helps long/short, whose crashes
are high-vol short rebounds; long-only earns FROM high-vol winners). Equal-weight x01 stays the
deliverable. Base unconditioned 12-1 momentum IS the edge — neither conditioning nor vol-sizing
beats it on clean, powered data. No sealed data spent.

## Leverage / sizing study (2026-06-16, `scripts/multiday_leverage.py`)

Pure risk dial on the fixed equal-weight base book (NOT an alpha change), net of 6% APR
financing on the borrowed fraction, 2025 sealed-out. Clean 2022–2024 (honest, Sharpe ~0.50):
CAGR +10.9%/maxDD −24% at 1.0×, FALLING to +6.8%/−54% at 2.0× — leverage HURTS CAGR (volatility
drag: geometric return ≈ arithmetic − ½σ², and at Sharpe 0.5/vol 29% the variance+financing
penalty dominates). 8yr 2017–2024 (survivorship-lifted, Sharpe ~0.88): leverage adds return
(+25%→+34% at 2×) but drawdown explodes (−38%→−73%); marginal return flattens past 1.5×.
VERDICT: run the standalone book at ~1.0× — leverage is counterproductive at the realistic edge
and unholdable at the optimistic one. Leverage only becomes productive AFTER raising Sharpe or
cutting drawdown → reinforces the beta-hedge / market-neutral path as the real profitability lever.
Realistic standalone CAGR ≈ 11% (honest) to 25% (optimistic), 24–38% drawdowns; 2025 +58% was a
tail year.

## Beta-hedge study — KILLED; market beta is load-bearing (2026-06-16, `scripts/multiday_betahedge.py`)

Pre-registered `multiday_betahedge_preregistration.md`. Long 12-1 book − β·SPY_fwd, β∈{0,0.5,1,1.3},
idealized + inverse-ETF haircut, 2025 sealed. Hedging LOWERS Sharpe monotonically on both windows
(8yr: 0.88→0.78→0.60→0.45; clean: 0.50→0.43→0.32→0.22); drawdown improves <25% bar. Book beta ≈1.4
(corr ~0.70) — the strategy is largely a high-beta tilt; the beta-orthogonal momentum alpha is thin
(residual Sharpe ~0.2–0.45). VERDICT: market beta load-bearing, keep long-only at ~1.0×.
**Improvement search now exhausted:** conditioning grid, vol-scaling (x02), leverage, and beta-hedge
ALL fail to beat the plain equal-weight 12-1 book. The edge is a modest beta-heavy momentum tilt
(Sharpe ~0.7–0.9, 25–38% DD, realistic CAGR ~11–25%). Remaining real levers are non-alpha:
execution/cost realism + the 2026 sealed 2nd-confirmation. Bank and confirm, don't keep tuning.

## Residual momentum — robustness on EARLIER history 2009–2016 (2026-06-17, YFinance)

Extended-history robustness read (NOT clean OOS). Discovered the marketdata harness has a YFinance
provider (deep history, max_lookback=None) behind Alpaca (2016 floor) — captured 2008–2016 via
`MARKETDATA_PROVIDERS=yfinance capture_multiday --fixed-universe-asof 2022-01-03`
(`_capture_multiday_2009_2016_yf.parquet`, 1.55M eligible name-days). Residual-momentum test (55 periods):
base Sharpe +1.15/β1.26/maxDD−20.7/α t+1.10/DSR0.984; **residual +1.18/β1.07/maxDD−14.8/α t+1.20/DSR0.989**;
corr 0.95 → PROMOTE-CANDIDATE. SAME SIGNATURE as 2017–2024 (beta-trimmed, lower DD, ~same modest
insignificant alpha) on INDEPENDENT data/regimes (2011 EU crisis, 2015–16 selloffs) + a different
provider → the residualization effect is regime-robust, not a 2017–24 artifact. CAVEATS: heavily
SURVIVORSHIP-FLATTERED (2022 roster applied to 2009–2016 — GFC/crisis blowups absent, which is why DD
looks tame); YFinance is free/split-only/unofficial. Robustness COLOR, not clean validation. Clean
confirmation still = forward sealed 2026+ (~2027) or a survivorship-free source (Norgate/CRSP).
