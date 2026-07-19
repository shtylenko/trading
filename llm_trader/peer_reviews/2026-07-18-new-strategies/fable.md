# Peer review — 2026-07-18 new strategies

**Reviewer:** Claude Fable 5 (independent; did not implement).
**Evidence base:** all §9 artifacts read; detector/packaging code read; paper-book JSONs re-analyzed (t-stats, day-clustered bootstrap, per-trade risk); git history inspected; short-hold test suites re-run (20/20 pass).

## Executive verdict (10 lines max)

1. The **negative** results (multi-day TA park, BB squeeze park, warrior FAIL, NML-as-implemented OFF) are trustworthy and correctly frozen.
2. The **positive** results (micro, VWAP) are **contaminated by a confirmed look-ahead**: the daily screen's RVOL uses **full-day volume** (`strategies/micro_pullback/patterns.py:65`, `vwap_pullback/patterns.py:61`, `bb_squeeze_long/patterns.py:61`), unknowable at 09:45–14:00 entries. Every PASS is unproven until re-run with a causal screen.
3. The reported effR is denominated in a **fictional $100 risk**: the $5k notional cap binds on ~100% of trades (median actual risk $26 micro / $18 VWAP). The economic edge is ~**6 bps of notional per round trip** — equal to the modeled cost. This is a cost-model artifact zone, not an edge zone.
4. Statistically, micro is the only candidate: day-clustered bootstrap P(effR≤0)≈0.007 (naive t=2.71); but after ~7 family/version tests that is marginal, and it sits on top of the leak. VWAP (P≈0.018, t=2.29) does not survive multiple-testing correction; 208/972 (21%) of micro paper trades share ticker-day with the VWAP book anyway.
5. "Pre-registration" is asserted but **not verifiable**: PREREG.md, code, and RESULTS all landed in a single commit (`486de00`, 2026-07-18 18:38). The BB "bugfix" also bundled a silent retune (pctile 0.20→0.25, lookback 48→36).
6. The NML A/B rejects the **rolling-24-bar operationalization**, not Lance's thesis — the ROADMAP itself sketched "box after a directional leg" and the code shipped something else. Applying it to VWAP reclaim was a predictable category error.
7. The freeze is directionally right but **too generous to micro/VWAP**: "paper-optional" on a leaked screen is a soft promotion. Verdict: fix the leak, run the free 2026-H1 holdout, then decide. Do not paper-trade anything yet.

## Gate / method scorecard

| Claim | Trust (H/M/L) | Why |
|---|---|---|
| Multi-day TA FAIL → park (trend_pullback, BFP, right_side_v) | **H** | Large-n, uniform, pre-gate FAILs; any screen optimism would only make the true result worse. Artifacts match prompt. |
| bb_squeeze_long FAIL → park | **H** | n=7149, 0/4 years, all cost points fail; not sparsity. The bundled retune (see Integrity #4) failed anyway, which strengthens the park. |
| micro_pullback multi-year PASS (+0.029, 4/4) | **L→M** | Numbers verified against artifacts and JSON; statistics genuinely better than VWAP (bootstrap CI [+0.007,+0.056] day-clustered). But the RVOL day-selection leak (Integrity #1) can plausibly account for a thin momentum-continuation edge; unproven until causal re-run. |
| micro paper book fee2+slip4 pass (+0.0022) | **L** | A +0.002 effR margin is ~$0.22/trade — sign-flip noise vs the raw set's −0.0001. Do not use this to rank micro over VWAP. |
| vwap_pullback thin PASS (+0.024, 3/4) | **L** | Same leak; weaker year breadth; fails fee2+slip4; does not survive a ×7 multiple-testing correction (P≈0.018 uncorrected). |
| NML OFF as default gate | **M–H** | A/B numbers verified; conclusion valid **for nml_v0.1.0 as implemented** (rolling window). It is not evidence against a post-leg-box NML. |
| Portfolio packaging keep | **M** | Harmless caps; but the effR "improvement" (+0.0292→+0.0315) is an incidental selection artifact, not validation. Fine as desk realism only. |
| Warrior micro probe FAIL | **H** | 1/2 years, n=140, current-snapshot float, cached universe, **all** cost scenarios fail. Correctly not promoted; the 2026 +0.158 reading is unusable (see Q13). |
| "Pre-registered" gates | **L** | Single-commit history (`486de00`); no independent trail that PREREG preceded results. Likely honest, but unverifiable — which is the point of pre-registration. |

## Answers to hard questions (§7)

### 7.1 Validity of the sim

**1. Is the 5m path sim upward-biased at 1–2 bps slip?**
Modestly, yes — the mechanics are more honest than most (signal at bar close → next-bar-open fill; stop checked before targets intrabar, which is conservative). Residual optimism: (a) target limit fills assumed at exact touch when `hi >= t1` — real fills need trade-through, worth ~1–2 bps; (b) stops filled exactly at stop ± 2 bps — gap-through on momentum reversals costs more on the ~46% of trades that stop; (c) skipping trades where next open ≤ stop (`micro/patterns.py:374`) is a small favorable filter, though defensible as "don't enter a dead setup." **Mark-down before trusting paper: 2–4 bps per round trip ≈ 0.01–0.02 effR.** That takes micro +0.031 → +0.01–0.02 and VWAP +0.026 → ≈0. The far bigger validity issue is the screen leak (Integrity #1), which is not a mark-down — it invalidates the sample.

**2. Does half-at-1R / rest-at-2R with stop-first bar logic create option-like path bias?**
No material one. Stop-first ordering is the conservative resolution of intrabar ambiguity; a bar touching both stop and T1 books the full loss. The genuine residual is target-touch fill optimism (Q1a). One real distortion: targets are anchored to the **signal-bar close** while fills happen at next open, so after a strong green break T1 sits <1R from the actual fill and the stop >1R — the "1R/2R" labels aren't literally true per trade. Effect is roughly symmetric on PnL but makes exit-count interpretation mushy.

**3. Multi-day FAIL vs short-hold PASS — apples-to-oranges?**
Yes as an *economic* comparison: same-day books never pay overnight gap risk, and they also never earn overnight drift (which is where most large-cap long return lives — so flat-EOD long-only is fighting the base rate, which makes the thin positives mildly more interesting, not less). But the mandate explicitly prefers flat-EOD, so the comparison is decision-relevant even if not like-for-like. What the campaign showed is "this multi-day mold failed and this same-day mold thinly passed," not "short-hold > multi-day."

**4. Is sizing realistic?**
It is inconsistent rather than unrealistic. The $100 risk budget is **unachievable** under the 50× notional cap: with median stop distance 0.54% (micro) / 0.36% (VWAP), risking $100 needs ~$19–28k notional; the cap forces ~$5k, so **~100% of trades are capped** and median actual risk is $26/$18. Per-trade participation ($5k against 10M+ share ADV large-caps) is trivially fine. For warrior $2–20 low-floats, $5k is executable but the 2 bps slip assumption is fantasy — spreads alone run 10–50 bps there, so the warrior probe's cost grid is miscalibrated at every point. Fix: report **bps of notional per trade** and actual-risk R alongside effR; the current headline (+0.03 "R") overstates what a desk would recognize as ~6 bps/trade net.

### 7.2 Gates and multiple testing

**5. Does "pooled>0 and ≥2/4 years" control family fishing across ~7 tests?**
No. The gate controls *within-family* regime cherry-picking (it correctly killed n30 optimism) but nothing across families. Rough correction: micro's day-clustered P≈0.007 × 7 tests ≈ 0.05 — the single best result in the campaign is *borderline* after selection, before the leak. Demanded holdout: (a) an untouched **time** holdout — 2026 H1 liquid data exists (the warrior probe used it) and was never consumed by selection; run frozen detectors on it; (b) pre-registered family cap per campaign with the correction written into the gate ("with k families tested, pooled edge must clear the k-adjusted bootstrap bar").

**6. Is micro's +3¢/$1 distinguishable from noise given overlapping days/correlated names?**
Borderline-real by the data's own account: n=972 across 497 distinct days, 59 tickers; day-clustered bootstrap 95% CI [+0.007, +0.056], P(effR≤0)=0.007. The clustering concern is legitimate (top names AMD/INTC/NVDA/TSLA/QCOM are one momentum complex — 5 tickers = 187/972 trades) but day-clustering already absorbs most of it. The honest statement: **statistically distinguishable from zero in-sample; not distinguishable from "artifact of a leaked, selected screen"** until E1/E2 below run.

**7. Equal-weighted years vs trade-weighted pooled?**
Keep both, fail-if-either-fails, as currently done. Year gates are a crude regime-robustness check, not statistics; pooled is the estimate. No change needed — but add the day-clustered bootstrap CI as a third, explicitly reported gate. Sign-of-year on n≈250 subsamples is nearly a coin flip at these effect sizes; treat 3/4 vs 4/4 as weak evidence, not a ranking criterion (see Q16).

**8. BB 0.20→0.25 / 48→36 — bugfix or silent retune?**
**Both, bundled — and that's the problem.** The start-index fix (loop began at `bb_period+lookback` ≈ 15:10, after the 14:30 window end → n=0) is a legitimate bugfix. The lookback change is defensible-adjacent (the config comment admits 36 was chosen so signals fit the window — that is fitting the detector to the window, i.e., design, not repair). The pctile loosening 0.20→0.25 has no recorded justification and is a retune. Because v0.1.1 **failed anyway**, no promotion bias resulted, and re-running frozen 0.20/48 would only produce a smaller failing sample. Don't re-run; do record the precedent as an anti-pattern (a bugfix that had *passed* under loosened params would have been unusable).

### 7.3 NML A/B

**9. Evidence against Lance, or against the operationalization?**
Against the operationalization. Lance's NML is a **consolidation box that forms after a leg and pullback** with edges as defined-risk levels; the shipped `nml_v0.1.0` is a **rolling 24-bar high-low window with position-in-range**, which is a different object — ROADMAP line 91 even sketches "consolidation box after a directional leg" and the code shipped the rolling window. A rolling-range filter structurally penalizes *pullback* entries (you buy pullbacks mid-range by construction). The A/B result is real and useful — this mechanical gate destroys these two families — but it licenses "park nml_v0.1.0," not "Lance NML is false."

**10. Was NML-on-VWAP a category error?**
Yes, and it was foreseeable: an 18% keep rate is the filter announcing that it contradicts the setup definition (VWAP reclaim ≈ mid-session-range by construction). A stricter pre-reg would have declared VWAP out-of-scope for NML *a priori* and tested NML only on micro/breakout-shaped entries. Cost was low (compute only), but the "NML kills VWAP" headline is a tautology, not a finding.

**11. Is "effR ≥ baseline − 0.005" too harsh/lenient?**
Reasonable as a floor, but it measures the wrong axis alone. A risk filter that cuts 35% of trades at flat effR *adds* value (capital and slot efficiency under `max_concurrent=3`) which this criterion ignores; conversely at these tiny effR levels 0.005 is well inside noise, so single-run deltas can't resolve keeps near the boundary anyway. For future filter A/Bs: require the delta on a day-clustered bootstrap CI, and evaluate per-slot-hour return, not just per-trade effR. Immaterial here — NML failed by 5–13× the tolerance.

### 7.4 Universe and data

**12. Is the edge SPY-regime beta? What control falsifies it?**
Partially testable already: micro made **+0.040 in 2022** — its best year was the bear year — which argues against simple long-SPY beta (VWAP also survived 2022). But regime beta isn't the sharpest null; **day-selection beta** is: the screen (leaked RVOL + gap + morning impulse) picks strong momentum days, and *any* long entry on those days with a trailing-stop-shaped exit may earn the same 6 bps. Falsifier (E3): same candidate days and tickers, entry at a random bar inside the entry window, identical stop/target/EOD engine, 1,000 draws → micro must beat the 95th percentile of the null distribution. Also note: the 59-name list is a current snapshot recycled into 2022 (survivorship); the repo already contains PIT-universe infrastructure that rejects current snapshots (`strategies/cup_handle/research_universe.py`) and the short-hold track didn't use it.

**13. Is warrior's 2026 positive reading unusable even as a hint?**
Yes. n=58 in the positive half-window; float is today's snapshot (selects names that *stayed* small — classic survivorship in exactly the universe where dilution/blowups drive float); the universe is a 420-name cache, not a rescan; nine tickers dropped on NA gaps; and **every** cost scenario fails including baseline. The only legitimate reading: the detector doesn't obviously break on small caps mechanically. Nothing more.

**14. Did 2022–23 5m coverage create survivorship of bars?**
Unknown — and that's the finding: **there is no coverage accounting.** `_rth_5m` returns `None` on missing/short days (micro `patterns.py:107-108` requires ≥20 bars) and candidates silently vanish; nothing distinguishes "no setup" from "no data." The warrior SPEC (§ provider-credential note, diagnosed 2026-06-30) says deep-history intraday (>12 months back) was offline pending a key regeneration — the multi-year runs postdate that note, but nothing in the artifacts certifies coverage was restored for 2022–23. Per-year n is roughly uniform (290/294/263/255 micro), which is mildly reassuring, but a per-candidate coverage ledger (screened day → bars present y/n → traded y/n) must exist before any sealed multi-year claim. Cheap to add; currently absent.

### 7.5 Promotion policy

**15. Is "paper-optional / no live size" coherent?**
As currently written, it's a soft way to keep a weak result alive — "optional" with no entry criteria, no duration, no success/kill gate is a zombie state. It becomes coherent with three additions: (a) prerequisite — the leak-fixed re-run (E1) and holdout (E2) must pass first; (b) a purpose — paper trading here should be framed as **cost-model calibration** (measure realized slippage vs the 2 bps assumption), which is the actual unknown, not more effR estimation; (c) pre-registered exit — e.g., 3 months or 100 fills, then promote/park by criteria written today.

**16. Micro over VWAP — justified or overfit to packaging?**
The *ranking* is right; one of the two stated reasons is bad. Micro genuinely dominates on sample size, bootstrap significance, both-books-overlap (VWAP's book shares 21% of micro's ticker-days — it is partly the same trades, so "second book" adds less than it appears). But "fee2+slip4 passes on the paper book" is a +0.0022 sign-flip on a re-selected subset versus −0.0001 raw — pure noise, and leaning on it is overfitting to packaging. Similarly 4/4-vs-3/4 year breadth at n≈250/year is weak evidence. Rank micro first for the defensible reasons; drop the other two from the narrative.

**17. Stop short-hold R&D given 3× slip fragility?**
Not yet — but stop *expanding* it. The honest picture: gross edge ≈ 2× modeled costs, dead at 3× slip, and the binding uncertainty is the **real** cost level, which no amount of additional backtesting resolves. The next unit of effort has exactly three justified targets: fix the leak (E1), run the free holdout (E2), and measure real fills at tiny size (E6). If E1 kills micro, stop the track and bank the negative result. Starting an eighth family before those three is the one clearly wrong move.

**18. If only one book may be paper-traded: micro, VWAP, neither, combined?**
**Neither, today** — paper-trading a book whose screen contains a confirmed leak produces numbers you can't interpret. After E1+E2 pass: **micro alone**, hard caps ($5k notional/trade, 3 concurrent, flat EOD, auto-stop at 100 fills or 3 months), run explicitly as a slippage-measurement exercise. Not combined: the 21% overlap means a combined book needs a shared-concurrency layer that hasn't been built or A/B'd, and VWAP adds correlated exposure with weaker statistics and a failing fee2+slip4.

### 7.6 Multi-day FAIL interpretation

**19. right_side_v: different construction, or thesis dead on liquid large-caps?**
Park it — "try different targets" is precisely the parameter nibble the mandate bans, and 68% WR with pooled −0.03 across 877 trades (worst in 2022: −0.09, −$18.3k) says the *geometry* (small winners, occasional full-R losers) is intrinsic to buying confirmed reclaims late: by the time the right side is "confirmed" on a daily-bar liquid large-cap, the move is priced. The scan being loose (1168 setups) is secondary. If the thesis returns at all, it should be as a *different pre-registered object* (e.g., intraday right-side-of-V where confirmation lag is minutes, not days) — not new targets on this one.

**20. What sampling policy prevents the n30-optimism failure mode?**
Adopt as standing policy: (i) smoke/n30 runs are **code-validation only** — no effR from them may appear in any decision document or be compared against gates; (ii) a family's first evidentiary run is the **full pre-registered multi-year window** with year gates — no interim peeks that could steer iteration; (iii) any sample whose date distribution is not approximately proportional to the target window's is labeled non-evidentiary by the tooling itself (the runner can enforce this mechanically); (iv) version bumps get one evidentiary run each — no re-rolls.

## Integrity findings

1. **[Critical] Full-day RVOL look-ahead in all three short-hold screens.** `df["rvol"] = df["volume"] / df["avg_vol"]` uses the same day's **total** volume, then filters `rvol >= rvol_min` (micro 1.2, VWAP 1.2, BB 1.15, warrior 2.0) for entries taken 09:45–14:00 (`micro/patterns.py:65`, `vwap_pullback/patterns.py:61`, `bb_squeeze_long/patterns.py:61`). Day selection conditions on post-entry information; high full-day-volume days are big-range days, which plausibly manufactures a thin momentum-continuation edge. BB failing despite the same leak shows the leak isn't sufficient for a pass — but micro/VWAP's margins (~6 bps/trade) are small enough that the leak could be the entire edge. **Every short-hold PASS is unproven until re-run with a causal screen.**
2. **[High] effR denominator fiction.** The 50× notional cap ($5k) binds on ~100% of trades (median actual risk: micro $26, VWAP $18 — computed from PAPER_BOOK.json `shares × (entry−stop)`), because median stop distance is 0.54%/0.36%. Reported "+0.03 effR" is ≈ $3/trade on $5k notional ≈ **6 bps net per round trip**, i.e., equal to the modeled 6 bps RT cost. Not a simulation error (internally consistent), but the headline metric materially flatters the result and hides that the intended $100 risk is unachievable under the cap.
3. **[High] Pre-registration is unverifiable.** PREREG.md, NML/portfolio params, detector code, and all RESULTS landed in **one commit** (`486de00`, 2026-07-18 18:38) — there is no independent trail that any "frozen" parameter preceded any result, and no trace of BB v0.1.0's claimed 0.20/48. Pre-registration that can't be audited is a narrative device. (The A/B conclusions happen to be *negative*, which limits the damage this time.)
4. **[Medium] Bugfix bundled with retune** (BB v0.1.0→v0.1.1): start-index fix + lookback 48→36 + pctile 0.20→0.25 in one step; the config comment concedes lookback was chosen so signals fit the entry window. Harmless here only because the result failed.
5. **[Medium] No data-coverage accounting.** `_rth_5m` silently drops days with missing/short 5m data; warrior SPEC documents a deep-history intraday provider outage (diagnosed 2026-06-30) with no artifact certifying 2022–23 coverage for the multi-year runs. Survivorship-of-bars cannot be ruled out from the sealed artifacts.
6. **[Medium] Book overlap misrepresented as diversification.** 208/972 micro paper trades (21%) share ticker-day with the VWAP book; 262 of the trading days overlap. Running both is substantially doubling down on the same days.
7. **[Low] Universe drift in sealed docs.** "59" vs "60 liquid large-caps" across artifacts (VWAP/trend/BFP RESULTS say 60; PREREG and paper books say 59; paper JSONs contain 59 tickers). Also the list itself is a current snapshot recycled to 2022 — while the repo's own `cup_handle/research_universe.py` exists precisely to reject that.
8. **[Verified clean]** Timezone handling (UTC-fetch → ET normalize → RTH slice), session VWAP causality (cumulative, used at bar close), stop-before-target intrabar ordering, portfolio overnight-clear (bug fixed; regression test `tests/test_admission.py:83` present and passing), portfolio/paper counts (1102→972 / 506→494 reproduce), and scoreboard-vs-artifact consistency all check out. Note session VWAP is RTH-only (no premarket) — a deviation from Ross's usage worth documenting, not a bug.

## Disagreements with implementer freeze

- **"PASS" language for micro/VWAP is premature.** Decision 3 (promote to research/paper-optional) treats leaked-screen results as validated-but-thin. They are unvalidated. The freeze should read: "candidate pending causal-screen re-run and 2026-H1 holdout."
- **Decision 6 (freeze detector retuning) — agree, but it's frozen on the wrong baseline.** The E1 re-run is not a retune; it's a correction of an invalid measurement and must be exempted from the freeze.
- **"NML rejected despite Lance narrative" overclaims.** What was rejected is a rolling-window operationalization the ROADMAP itself didn't sketch. One faithful post-leg-box version (E5) is a legitimate, bounded follow-up — not parameter nibble.
- **Portfolio packaging "slightly better effR" should not be cited as support.** It's incidental selection; keep the caps for realism and stop quoting the delta.
- **The micro-over-VWAP rationale needs rewriting** (drop fee2+slip4-on-paper and 4/4-vs-3/4 as reasons; keep n, bootstrap strength, and overlap).
- Everything else — parking multi-day TA, BB, warrior; no live size; no capital stacking — **endorsed as-is**.

## Pre-registered next experiments (if any)

| ID | Hypothesis | Kill criteria |
|---|---|---|
| **E1 — Causal screen re-run** (highest priority) | Micro/VWAP edges survive replacing day-RVOL with a causal filter. Freeze ONE definition before running (recommend: drop RVOL entirely, keep gap+avg_vol; alternative: RVOL of 09:30–09:45 volume vs 20-day same-window average). Same universe, window, detector, costs. | Micro pooled effR ≤ 0 **or** <2/4 years **or** day-clustered bootstrap P(≤0) > 0.10 → park the entire short-hold track. A pass at half the current effR counts as pass, not as license to iterate. |
| **E2 — 2026-H1 liquid holdout** | Frozen (E1-corrected) detectors are positive on 2026-01-01→2026-06-30 liquid data, a window never touched by selection. One run, no re-rolls. | effR ≤ 0 on the holdout → park. Small n is acknowledged; sign + CI reported, no year gate. |
| **E3 — Random-entry null** | Micro's edge exceeds day-selection beta: same candidate days/tickers, uniform-random entry bar in window, identical stop/target/EOD engine, 1,000 draws. | Micro effR below the 95th percentile of the null → reclassify edge as day-selection, park detector. |
| **E4 — PIT universe manifest** | The 59-name cohort's 2022–2023 membership/liquidity holds point-in-time (reuse `cup_handle/research_universe.py` machinery; also emit the per-candidate-day bar-coverage ledger from Integrity #5). | Any year's effective universe shrinks >15% under PIT membership, or coverage ledger shows >5% silent candidate loss → re-run E1 on corrected panel before any promotion. |
| **E5 — NML v0.2.0 post-leg box** (optional, low priority, micro only) | A Lance-faithful box (leg → pullback → consolidation box; admit only at upper edge/breakout of the box) does not destroy micro's edge, unlike the rolling window. Params frozen in a committed PREREG **before** results. | Same criterion as v0.1.0 pre-reg (effR ≥ baseline − 0.005 on day-clustered CI). Fail → NML closed permanently for short-holds. |
| **E6 — Live-fill cost calibration** (only after E1+E2 pass) | Realized one-way slippage on ~30–100 tiny live/paper fills of real signals ≤ 2.5 bps. This is the binding unknown; no backtest can answer it. | Median realized one-way slip > 4 bps → short-hold track dead by the existing stress grid; park regardless of backtest results. |

What would **not** count as success anywhere above: a pass obtained by adjusting any detector parameter, screen threshold, window, or cost assumption after seeing results; a pass on a re-selected subset (the fee2+slip4-on-paper pattern); or a warrior-universe positive without PIT float.

## Recommendations to human operator

1. **Paper-trade nothing yet.** The RVOL look-ahead (Integrity #1) means today's PASSes are unproven. E1 is days of work and decisive — run it first, then E2. If micro survives both, paper-trade **micro only** at hard caps ($5k notional/trade, max 3 concurrent, flat EOD, auto-stop at 100 fills or 3 months), framed as slippage measurement (E6), with promote/park criteria written before the first order.
2. **Ignore VWAP** as a book (21% overlap with micro, weaker statistics, fails modest cost stress). Keep the detector on the shelf; it costs nothing.
3. **Keep every park** (multi-day TA, BB squeeze, warrior micro). Warrior stays closed until a point-in-time float source exists — no exceptions for a 58-trade positive half-year.
4. **Recalibrate expectations:** the best candidate here earns ~6 bps of notional per trade before real-world frictions beyond the modeled 6 bps. Even a full pass of E1/E2/E6 yields a small, cost-dominated book — worth running as research discipline, not as income.
5. **Process fixes to demand from the implementing agent:** commit PREREG files *before* result-producing runs (separate commits — pre-registration must be auditable); never bundle parameter changes with bugfixes; report bps-of-notional and actual-risk R alongside effR; add the candidate-day coverage ledger; n30/smoke numbers banned from decision documents.
6. If E1 kills micro: accept "no deployable short-hold edge found; molds, gates, and tooling validated" as the campaign's result and stop this track. That is a good research outcome, and considerably cheaper than a thin false positive traded at size.
