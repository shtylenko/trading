# Strategy Exploration Playbook (0 → 1)

How we take a same-day trading idea from "hunch" to a trustworthy verdict
(promote or retire) **without fooling ourselves**. This is the family-agnostic
process; it was first run end-to-end on the gap-and-go (`d`) family in June 2026
(worked example in §7). Read this before starting work on any new strategy idea.

Companion docs: `feature_search_spec.md` (search mechanics, LOCKED decisions),
`phase_b_oos_preregistration.md` (the OOS test template), `synthetic_control_plan.md`
+ `synthetic_control_results.md` (the meta-validation that the pipeline itself works
— see §6c). Code lives in `research/features.py`, `strategies/*/capture.py`,
`experiments/capture/capture_features.py`, `experiments/harness/feature_search.py`,
`experiments/harness/feature_search_v2.py`, `experiments/harness/synthetic_control.py`, `validation/cscv.py`.

---

## 0. The one thing this process exists to prevent

**Overfitting / self-deception.** This project has been fooled repeatedly: a small
"screen" sample made a strategy look great that the full evaluation then killed; 18
ungated variants across 3 families all looked positive only because of one anomalous
half-year. Every stage below is a guard against a specific way we have actually been
fooled. A clean negative is worth more than a contaminated positive.

Two mantras:
- **Capture broad, search narrow.** Recording a feature is free; searching it costs
  inferential credibility. Lock what you *select over* before you look.
- **The sealed year is the only honest test.** Everything else is fittable.

---

## 1. The pipeline at a glance

```
idea
 └─ Stage 0  BASELINE / TRIAGE    → run the bare minimum-rule strategy (no/few
 │                                   filters) on broad days; get the honest baseline R
 └─ Stage 1  CAPTURE (broad)      → one rectangular ledger: every candidate × all
 │                                   leak-free features + realized R
 └─ Stage 2  SEARCH (narrow)      → score filter combos as subsets of the ledger
 └─ Stage 3  WALK-FORWARD         → pooled / leave-one-year-out selection, OOS folds
 └─ Stage 4  PBO (CSCV)           → is the *selection procedure* overfitting?
 └─ Stage 5  PRE-REGISTER + SEAL  → write pass/fail BEFORE spending the holdout year
 └─ Stage 6  ENGINE CROSS-CHECK   → confirm the offline ledger matches a real backtest
 └─ promote (→ funnel → 2nd sealed OOS) | retire (record the negative)
```

Split the timeline up front: **search years** (used for capture/search/WF/PBO) and a
**sealed OOS year** that NOTHING touches until Stage 5. Never let the sealed year be
the window you most distrust (we sealed 2025, NOT the suspected-artifact 2026H1).

### Tooling per stage (what to actually run)

| Stage | Code / doc | Command (example) |
|---|---|---|
| 0 baseline / triage | a minimum-rule release (e.g. `d01`) + `scripts/backtest.py`; or read the `Baseline (unfiltered …)` line that `feature_search.py` prints | `python3 -m trading.lab.scripts.backtest --release d01 --testset eval_2024_broad` |
| 1 capture | `strategies/<family>/capture.py` (variant) + `research/features.py` (feature lib) + `experiments/capture/capture_features.py` | `python3 -m trading.lab.experiments.capture.capture_features --start 2022-01-01 --end 2025-12-31 --universe liquid_pit --out trading/lab/experiments/_data/_capture_2022_2025.parquet` (add `--resume <run_id>` to continue; `--export-only <run_id>` to re-export) |
| 2–5 search / WF / PBO | **`experiments/harness/feature_search.py`** — THE canonical search: daily-portfolio info-ratio objective, leave-one-year-out walk-forward arbiter, PBO on the same metric (`validation/cscv.py`). Prints a PROMOTE-CANDIDATE / NO-ROBUST-EDGE verdict and nominates the pooled winner. | `python3 -m trading.lab.experiments.harness.feature_search --ledger …/_capture_2022_2025.parquet --top-n 10 --k 2 --seed 7` |
| (optional) deeper diagnostics | `experiments/harness/feature_search_v2.py` — fold-N all-combos table + substitution (roster) check; imports the canonical scoring | `python3 -m trading.lab.experiments.harness.feature_search_v2 --ledger …/_capture_2022_2025.parquet --top-n 10` |
| 5 pre-register + sealed OOS | `validation/research_log/phase_b_oos_preregistration.md` (template). The one-shot test is a short script over the ledger's sealed-year rows (no dedicated CLI — write it from the locked spec, run once). | — |
| 6 engine cross-check | `scripts/backtest.py` (real engine) + `scripts/lifecycle.py` (set disposition) | `python3 -m trading.lab.scripts.backtest --release d15 --testset eval_2025_broad --allow-oos` ; `python3 -m trading.lab.scripts.lifecycle --set d15 --disposition killed --reason "…"` |

`feature_search.py` is the single canonical search (the round-1 single-fold mean-R logic
that produced the false negative has been replaced by the daily-portfolio + leave-one-
year-out approach this playbook describes). A search verdict only NOMINATES a combo for
the sealed-OOS test — it is never a promotion.

---

## 1b. Stage 0 — Baseline / triage (do this BEFORE the expensive capture)

Before committing hours to a feature capture, run the **bare strategy** — minimum
admission rules, **no (or very few) filters** — across broad full-day data, and look
at the honest result. Cheap, and it earns its place three ways:

- **Triage:** is there *any* there there, or is the raw idea hopeless? If the
  unfiltered strategy is catastrophic *and* you have no plausible thesis for which
  sub-population would be different, don't spend the capture.
- **Baseline:** it sets the number every filter combo must beat. (Gap-and-go's bare
  top-10 baseline was **−29R** over 2022–24; that's the bar the search worked against.)
- **Mechanics/data check:** confirms the universe resolves, fills look sane, costs are
  modeled — catch plumbing bugs now, not after a multi-hour capture.

Two rules that keep Stage 0 honest:

- **A negative baseline does NOT kill the idea.** The entire premise is that a *subset*
  of candidates may have an edge the unfiltered whole doesn't — a losing broad strategy
  with a credible filtering thesis is exactly the case worth capturing. (Conversely, a
  broad strategy that's *already* positive is a strong signal — but still must survive
  the same search/OOS discipline.)
- **Do NOT hand-tune the broad strategy until it looks good.** Eyeballing the data and
  adding levers one at a time until the line turns green is the manual overfitting this
  whole process exists to escape (it is how the screen fooled us before). Stage 0 is
  triage + baseline ONLY. The finding happens in the pre-registered systematic search.

Note: the unfiltered baseline reappears later as the `k=0` (empty) combo in the search,
so the search re-measures it on the same footing — Stage 0 is the fast standalone look.

## 2. Stage 1 — Capture (broad)

Replay every search-window day; for every admitted candidate, record its full
leak-free feature vector AND the realized R it would have earned. Output a flat,
rectangular ledger (one row per candidate; fixed feature columns; `None` where
uncomputable).

Rules:
- **Minimum admission only**, run **uncapped** (`candidate_limit=None`). Then every
  stricter filter combination is a pure **row subset** — search becomes a fast scan,
  no per-combo backtests. (Valid only because each trade is simulated independently.)
- **Leak-free contract:** features use only data knowable at decision time (the first
  bar + strictly-prior daily/intraday/benchmark data). Point-in-time universe. Raw
  prices with a split/glitch guard. Enforce the time boundary IN the feature code,
  don't trust hydration.
- **Capture every cheap leak-free feature**, even ones not in the search grid — the
  ledger is a standing asset; you don't want to re-run the (expensive) capture.
- Get the feature layer peer-reviewed before the big run (we caught an ADX scale bug,
  a phantom-gap split hole, and NaN leaks this way). Smoke on one month first.

The ledger (`experiments/_data/_capture_*.parquet`) is reusable for every later search round.

**Leakage checklist (verify on every capture — a single leak invalidates everything):**
- [ ] **Universe is point-in-time as of the morning** — includes then-listed names,
      excludes future listings; liquidity eligibility computed from *prior* data only,
      never future ADV or surviving-symbol lists. **Survivorship note (direction
      matters):** a universe built from *currently-active* symbols misses since-delisted
      names. For a LONG strategy this is OPTIMISTIC (you skip names that went to zero), so
      it inflates backtests → it makes a NEGATIVE verdict *safer* (a real edge must beat
      an even-worse honest universe) but means you must DISTRUST positives, especially in
      older years. Our `liquid_pit` is survivorship-biased pre-2024 (documented in its
      own header) — so our kills are conservative; fixing it would not reveal a hidden
      edge. To trust a *positive*, re-test on a delisting-inclusive universe.
- [ ] **Sector/industry map is effective-dated**, not a current snapshot backfilled onto
      old dates (a stock that changed sectors would leak its modern label).
- [ ] **Split/glitch guard uses only info known at decision time**, and note that dropping
      a whole date can bias the sample (splits cluster after big runs → drops high-vol
      days). Confirm the guard sees today's open vs prior close (catches overnight reverse
      splits), not just prior closes.
- [ ] **Any "average"/RVOL/z-score excludes the current day** and uses the right window
      (opening-bar normalization must not accidentally use full-day volume).
- [ ] **Prior-session intraday features** handle session boundaries, early closes, halts,
      extended hours, and timezone correctly.
- [ ] **Halt / delayed open:** a name halted at the open has no valid first candle — do
      not synthesize one from stale prints.
- [ ] **Capture→ledger join is strict `(date, symbol)`** so outcomes aren't joined across
      ticker changes.

---

## 3. Stage 2 — Search (narrow), LOCKED

- **Pre-register the grid + objective + seed BEFORE scoring**, and do NOT widen it in
  reaction to results — that launders degrees of freedom (the exact thing PBO is meant
  to catch). Budget the number of search *rounds* up front (alpha-spending). Round 1 =
  small `k` (≤ 2 simultaneous filters); escalate only as a *separate* pre-registered
  round.
- **Top-N-after-filter:** re-apply the deployment cap (e.g. top-10/day) AFTER masking,
  so each combo is scored as it would actually trade.
- **Objective = risk-adjusted DAILY-PORTFOLIO return** — group filled trades by day,
  sum the day's capped R, score `mean(daily R) / std(daily R)` (info-ratio / t-stat).
  Do NOT select on mean-R-per-trade: it is a variance maximizer that strips to the
  trade-count floor on a lucky sample. Keep hard floors (min trades total + per
  quarter) so tiny samples are ineligible.
  - **Geometry caveat (from the synthetic control, §6c):** this objective recovers
    **cross-sectional** (within-day) predicates cleanly but **structurally
    under-recovers DAY-LEVEL regime flags** (`spy_/sector_below_50d_sma`). Filtering
    on a regime flag drops *whole days*; the resulting zero-days inflate the daily-R
    denominator, so a planted regime edge isn't recovered even at large doses. A
    regime signal is therefore better expressed as a **daily capital-allocation
    overlay** than as an in-search admission filter (partly explains why regime-gated
    drive variants struggled).
- **Per-combo permutation p is descriptive, NEVER a gate.** Under selection the winner
  of N combos has a small p by construction — this is precisely what fooled us before.
- **Deflated Sharpe Ratio (DSR) is the selection-bias gate** (`validation/deflated_sharpe.py`).
  Best-of-N inflates the winner's Sharpe even at zero true edge (the False Strategy
  Theorem). DSR = P(the winner's daily Sharpe is real) after adjusting for the
  *effective* number of independent trials (participation ratio of the combos' return
  correlations — NOT the raw combo count, which over-penalizes correlated combos),
  the sample length, and non-normality (skew/kurtosis). Require **DSR ≥ 0.95** to
  nominate a combo for the sealed-OOS test. (On gap-and-go the winner scored DSR 0.58 —
  a REVIEW, not a promote — consistent with its later OOS kill; DSR would have caught it
  one stage earlier.)
  - **The 0.95 gate is demanding — know its sensitivity floor.** The synthetic control
    (§6c) measured the minimum edge it admits: DSR clears 0.95 only once the winner's
    annualized daily Sharpe ≈ **3.2** (a per-trade edge of ~0.10R on the gap ledger). A
    *genuinely modest* edge (ann. Sharpe ≈ 1.2) sits at DSR ≈ 0.83 → REVIEW, not PROMOTE.
    This is defensible deflation, but it means a real-but-small intraday edge will land
    in REVIEW with WF + PBO clean — read that combination against this curve rather than
    discarding it, and treat any change to the 0.95 threshold as a code-reviewed,
    re-run-the-control decision (never silently retune it to admit a candidate).

---

## 4. Stage 3 — Walk-forward (the arbiter)

- **Do NOT re-select a fresh combo on each short fold.** Per-fold argmax on a 1-year
  window tests "is the selector stable across regime shifts," not "does an edge exist"
  — it manufactures **false negatives** (see §7). Use **pooled** selection (all search
  years) and **leave-one-year-out** (train on the other years, test the held-out one).
- A combo earns the sealed-OOS test if it is positive across the search years and
  stable under leave-one-year-out (e.g. selected in every LOO fold), and broad (low
  tail share), and substitution-robust (see §5).

---

## 5. Stage 4 — PBO + the two confounds to rule out

- **PBO via CSCV** (`validation/cscv.py`): across many symmetric in/out block splits,
  how often does the in-sample-best combo land in the OOS bottom half? PBO ≳ 0.5 ⇒ the
  *search* is overfitting. **Compute PBO on the SAME daily-portfolio metric the search
  optimizes** (a metric mismatch makes WF and PBO incomparable). An **embargo** (default
  1 row trimmed from both edges of every block) severs boundary autocorrelation between
  adjacent blocks. Caveat: PBO describes the *search*, not a specific combo, and is
  near-0.5 by construction when no edge exists — read it alongside, not instead of, the
  combo's own robustness and DSR. (Purging of overlapping label horizons — the other
  López de Prado guard — is low-value here because our labels are SAME-DAY, resolved by
  the exit, with no multi-day horizon to bleed across folds.)
- **Substitution check** (the top-N "lottery"): a filter that drops high-rank names
  promotes lower-rank bench names into the capped book, and could be credited for their
  luck. Score the candidate combo under two roster modes — `replace` (filter then
  top-N) vs `remove` (top-N then filter) — and confirm they're ~equal. A large gap
  means the "edge" is substitution, not the predicate.

---

## 6. Stage 5–6 — Spend the sealed year, then cross-check the engine

1. **Pre-register** (template: `phase_b_oos_preregistration.md`): fix the exact rule,
   portfolio construction, objective, **minimum effect size**, and binary PASS / REVIEW
   / FAIL criteria. Get sign-off. THEN read the sealed year **exactly once**. The result
   is binding regardless of outcome. A second look burns the holdout.
   - **Cross-family alpha-spending** (`validation/oos_spend_ledger.md`): the sealed years
     are a SHARED, depleting resource across the whole project — every family that tests
     against the same year erodes it (meta-overfitting on the holdout). Discipline:
     (a) only candidates that already clear WF + PBO + **DSR ≥ 0.95 in-sample** may spend
     a year; (b) **rotate** holdout years across families (we have 2025 and the more-
     suspect 2026-H1); (c) **raise the bar on re-query** of a given year (1st DSR ≥ 0.95,
     2nd ≥ 0.975, 3rd ≥ 0.99, then that year is spent); (d) **log every spend** (win or
     lose) in the ledger.
2. **Engine cross-check:** the offline ledger is a fast approximation. Before trusting a
   *promote*, reproduce the number with a real engine backtest (a numbered release on
   the OOS testset). Expect direction/magnitude agreement, NOT bit-identity (the ledger
   and engine differed ~12% on trade count via the RV path). **Ledger for fast search;
   real engine for the final gate.**
3. **Decision:** PASS → freeze as an immutable release, run the normal funnel
   (smoke → screen → broad_is), and only then the *second* sacred OOS (the next year).
   FAIL → record the clean negative in the family backlog + auto-memory and move on.

## 6b. What the verdict covers — and what a PASS still owes

Be precise about what a result *means*, so a PASS isn't over-trusted and a FAIL isn't
over-claimed:

- **The simulation is optimistic — and that asymmetry is load-bearing.** Trades are
  simulated independently, fixed 1%/trade, with NO cross-trade capital or correlation
  constraint. Ten same-morning gap-up longs are highly correlated (one tape); this
  model **overstates return and understates drawdown**. The asymmetry: a **negative**
  verdict is *robust* to this (if it can't make money even optimistically, the real
  portfolio is worse), but a **PASS still owes a portfolio-level re-check** — correlated
  drawdown, a concurrency cap, and capacity/slippage — before any real capital.
- **The construction is fixed.** The pipeline searches *admission filters* on a fixed
  entry/exit (e.g. 1R stop, 1R target, time-exit). It cannot find edges that need a
  different structure (let winners run, trailing stop, different R:R, scale-outs). If
  the thesis needs that, it's a *separate* pre-registered construction, not a filter.
- **Costs.** Fills assume breakout-trigger + a tick; thin books, gap slippage, and queue
  priority are not fully modeled. The pre-registered **minimum effect size must clear
  realistic costs**, not just beat zero.
- **Scope of a negative.** "No edge in *this* grid / *this* construction / *this*
  universe" — not "no edge ever." A family is "exhausted" only after the thesis-backed
  candidates have been tested and killed; say that, not more.

## 6c. Trusting the validator itself — the synthetic positive control

Everything above assumes the pipeline *can* tell a real edge from noise. That
assumption is itself testable, and we test it — otherwise a 100% kill rate is
ambiguous (broken validator vs genuinely thin regime). The **synthetic
dose-response positive control** (`experiments/harness/synthetic_control.py`, plan + results in
`validation/synthetic_control_*.md`) settles it: it injects a *known* edge onto the
**real** ledger — `realized_r_synth = realized_r_real + m·1{opening_rv≥1.5}` — and
runs the full pipeline across a dose grid `m ∈ {0, 0.02, 0.05, 0.10, 0.20}`.

- `m=0` reproduces the real ledger exactly → a free **NULL / false-positive control**.
- `m>0` superimposes a known edge on real noise (preserves fat tails / autocorrelation).
- Deterministic, offline, no DB writes, no engine changes.

Run it: `python3 -m trading.lab.experiments.harness.synthetic_control`.

**Result (2026-06-15): the validator is SOUND.** The NULL is not promoted (DSR 0.58
→ REVIEW, sealed −34.1R = the real gap+rvol kill); detection power is monotone (m↑ ⇒
WF↑, PBO↓, DSR↑, sealed flips positive); minimum detectable edge **m\*=0.10R/trade**
(winner Sharpe ≈ 3.2); planted feature recovered 4/4 doses. ⇒ **prior kills are
trustworthy; the long-only same-day regime is genuinely thin, not a broken pipeline.**

**When to re-run it (it's a standing meta-check, not a one-time thing):** after any
change to the objective, the gates/thresholds (esp. the DSR 0.95 hurdle), the PBO
construction, or the walk-forward selection logic. A change that breaks the dose
curve (null promoted, or m\* blows up) is a regression in the validator itself. It
also yielded two findings that fed back into §3: the DSR sensitivity floor and the
day-level-regime under-recovery.

---

## 7. Worked example — gap-and-go (June 2026), and what each stage caught

- **Capture:** 23,261 candidates × 87 features, 2022–2025, leak-free. Peer review of
  the feature layer caught an ADX 14× scale bug and a phantom-gap split hole pre-run.
- **Search round 1 said "no edge"** — but it used per-fold 1-year-train mean-R argmax.
  Fold 1 (2022 bear) picked a bear-overfit combo that bled in 2023. **This was a FALSE
  NEGATIVE.** Four-model peer review caught it.
- **Phase-A diagnostics** (daily-portfolio objective, leave-one-year-out): the real
  signal `gap≥3% + opening-RV≥1.5` was positive every search year (2022 +3.5, 2023
  +5.6, 2024 +31.8R), selected 3/3 LOO, substitution-robust. Looked genuinely robust.
- **Phase-B pre-registered sealed-2025 test KILLED it:** −34.1R, 1/4 quarters positive.
  **An in-sample-robust combo (even 3/3 LOO) still failed the one untouched year.** The
  sealed year was the only thing that caught it — without it we'd have shipped a loser.
- **Engine cross-check (d15):** −30.1R / 760 trades vs ledger −34.1R / 678 — same
  verdict, confirming the methodology is faithful (and the ledger ≈ engine, not exact).
- **Outcome:** gap-and-go retired with earned evidence, two independent ways.

The meta-lesson: the process worked precisely *because* it was willing to (a) overturn
its own first verdict on peer review, and (b) still kill the resurrected candidate on a
sealed test. Trust the sealed year over every in-sample story, including a compelling one.

---

## 8. Checklist for the next idea

- [ ] Split timeline: search years + ONE sealed OOS year (not the distrusted one).
- [ ] Write a capture variant (min admission, uncapped); declare all data needs.
- [ ] Peer-review the feature layer; smoke one month; then full capture → ledger.
- [ ] Pre-register the search grid + daily-portfolio objective + round budget. LOCK it.
- [ ] Search as subsets; pooled + leave-one-year-out; PBO (with embargo) on the same metric.
- [ ] Gate the winner on **DSR ≥ 0.95** (selection-bias-adjusted) + substitution check.
- [ ] If a candidate clears WF + PBO + DSR: check the **OOS spend ledger** (rotate years,
      raise the bar on re-query), pre-register pass/fail, get sign-off, spend the sealed
      year ONCE, log it, cross-check with the real engine.
- [ ] Record the verdict (backlog + memory) either way. Negatives count.
