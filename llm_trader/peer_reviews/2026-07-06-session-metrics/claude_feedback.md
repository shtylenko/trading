# Claude Peer Review Feedback: Session Metrics Proposal

**Date:** 2026-07-06
**Reviewer:** Claude (codebase-grounded review)
**Target:** `llm_trader/peer_reviews/2026-07-06-session-metrics/proposal.md`
**Verdict:** Accept the *direction*, re-scope aggressively. ~⅓ of the proposed metrics are strong fits, ~⅓ are the right idea in the wrong mathematical form for this data model, and ~⅓ are premature until a methodology problem (below) is fixed. The single most important change is **not a metric at all** — it's the holdout-contamination risk in §Q7.

---

## TL;DR prioritization

**Ship first (cheap, correct, high-signal — all derivable per-leaf then aggregated):**
1. **Expectancy in R** — reported two ways: *edge* (traded leaves only) and *deployment* (all non-void attempts, stood-down = 0R).
2. **Profit factor** + **payoff ratio** + **avg/median/std of R**.
3. **MAE (max adverse excursion)** per leaf — the missing mirror of MFE, and the correct "drawdown" concept for this system.
4. Promote existing **MFE capture**, **void %**, **traded %** into the top-level view.

**Ship second (needs care):**
5. **Consistency across repeats** (stddev of per-setup outcomes when `--repeats > 1`) — I'd argue this is *the* LLM-reliability metric and the proposal under-weights it.
6. **Cost/token efficiency per run** — a real, currently-absent axis that dominates model selection in practice.

**Reject or heavily reframe:**
7. **Max Drawdown / Calmar / annualized return / equity curve** — ill-defined on this data model (see below). Replace with MAE + a *sorted* R-bar chart.
8. **SQN** — keep as secondary only, with N shown, and understand it penalizes selectivity (see below).

---

## The core mismatch: this is not an equity curve

The proposal repeatedly reaches for **portfolio-time metrics** — Max Drawdown, Calmar, Recovery Factor, "mini equity curve." Those assume a *single sequential, compounding account* traded chronologically. That is not what a batch is.

In `llm_trader` a top-level session is a **fixed stratified holdout of independent (ticker, date) leaves**, each traded in isolation with a **flat per-trade risk budget** (`PROFILE_RISK`, no compounding), across setups spanning *different historical dates in arbitrary order*. There is no chronological account balance, so:

- **Max Drawdown across the batch is undefined** unless you impose an ordering, and any ordering (run time? historical date? testset index?) is arbitrary and gameable. A "drawdown" over independent samples is just "the worst run streak in whatever order you sorted them" — it carries no risk-of-ruin information because the trades were never sequential capital.
- **Calmar / annualized return are meaningless** — there's no elapsed calendar to annualize over, and the holdout deliberately over-samples rare setups (stratification), so any "return rate" is a sampling artifact, not a track record.

**What you actually want instead:**

- **Intra-trade MAE** (well-defined, cheap, currently missing). You already compute MFE (`peak_high_since_entry` vs blended cost). The mirror — the worst `unrealized` the position sat through before exit — is already in `decisions.json` (`timeline_row["unrealized"]`, recorder.py:194). Add `mae_per_share` / `mae_dollars` in `_run_engine` and you get "did this model white-knuckle through −1.8R of heat before its winner, or manage the stop?" That's the survivability signal the proposal wanted from MDD, and it's genuinely diagnostic of LLM stop discipline.
- **Distribution of per-leaf R** (mean, median, std, min/max, sorted bar chart). A sorted R-bar chart communicates everything an equity curve pretends to — tail losers, cluster of scratches, a few big winners — without implying a false time ordering.

If you want *one* portfolio-style number, **Recovery Factor** salvages as `sum(R) / |worst single-leaf R|` (worst *trade*, not worst drawdown) — honest and orderless. Drop Calmar entirely.

---

## Per-trade unit: a leaf is one trade, not one fill

The proposal says expectancy should "aggregate realized deltas from actions." **Don't.** A leaf with ENTER→ADD→SCALE→EXIT is *one* trade (one position lifecycle), not four. `actions.json` / `realized_delta` are fills; treating them as trades will (a) inflate N, (b) double-count, and (c) reintroduce exactly the win-rate-denominator bug just fixed in `list_sessions` / `get_top_session_view` (fills vs sessions).

**Per-trade metrics must key on the leaf**, using the already-correct per-leaf `r_multiple` / `r_multiple_actual` in `pnl.json`. Fills are for *behavioral* metrics only (avg fills/trade, scaling style).

Prefer **`r_multiple_actual`** (realized ÷ risk actually taken at entry) over `r_multiple` (÷ budget) as the expectancy unit — it's the true R and is robust to sizing differences between models. Fall back to budget-R only when no stop was recorded (`initial_risk is None`).

---

## SQN: understand what it rewards before showing it

SQN = `sqrt(N) · mean(R) / std(R)`. Two setup-specific cautions:

1. **N is not fixed across models, so SQN penalizes selectivity.** N = *traded* leaves. A selective model standing down on 20/30 setups has N≈10; an aggressive one has N≈28. SQN gives them different scores for identical per-trade edge purely because one trades less — conflating "quality of the edge" with "how often it fires," the exact two things you want measured *separately*. Report **mean-R, std-R, and traded %** and let the reader combine them.
2. **At N≈10–60, Van Tharp's bands (">2.5 good") are noise** — they assume hundreds of trades. Report a **bootstrap 95% CI on expectancy** instead: statistically honest, trivially cheap at this N, and it directly answers "is version A's edge distinguishable from B's, or sampling luck?" That matters more than any point estimate when versions differ by fractions of an R.

Keep SQN if you like, but secondary, N always adjacent, never a headline badge.

---

## The methodology problem that outranks all metrics (answers Q7)

**You are about to overfit the skill to a frozen holdout.** The harness reuses *one* stratified testset (`batch/testset.json`, seed 13) for every version comparison. The moment you iterate `TRADE_SIMULATOR.md` and keep the version with better expectancy *on that set*, it stops being a holdout — it becomes training data, and reported edge turns optimistic in the way that doesn't survive live.

No new metric fixes this; richer metrics make it *worse* by giving more surfaces to (unconsciously) tune against. Before building expectancy/PF/SQN dashboards, I'd want:

- A **locked validation set** you report on and **never** inspect while iterating, plus a separate **development set** you may look at. Rotate/expand validation periodically from fresh `build-set` draws (different seed, non-overlapping (ticker,date)).
- Every reported number **paired with N and a CI**, and a standing note that selecting versions against the same set inflates edge.
- Ideally **walk-forward by date**: build the holdout only from setups *after* the last date used in development.

This is the highest-leverage item in the proposal's problem space — above every metric on the list.

---

## LLM-specific axes the proposal under-develops

The doc is strong on trader metrics, lighter on the "which *LLM*" half — half the stated goal. Two additions:

- **Cost / token efficiency (absent).** Models differ 10–100× in cost. +0.1R expectancy at 20× cost may be the worse deployment choice. `batchsim` already captures each run's hermes transcript; `hermes sessions export` carries token usage. Surface **$ (or tokens) per run** and **expectancy-per-dollar-of-inference** — arguably the most decision-relevant model metric you don't have.
- **Consistency across repeats (promote to first-class).** With `--repeats > 1`, running the same (setup, version) N times isolates *model stochasticity*: stddev of per-setup R, and **decision-divergence rate** (did it even take the trade on all N repeats?). A model that trades a setup brilliantly 1-in-3 and stands down otherwise is not deployable. Nothing else in the set captures run-to-run instability.

Behavioral adherence beyond voids (Q6): **stop-honoring rate** (did EXIT fills land at/below the logged `stop`, or did it walk stops down?) and **avg bars-held** — both cheap from `actions.json` + `decisions.json`, and better at revealing management-style differences than PnL alone.

---

## Storage & data-flow: compute on read, don't mint `metrics.json`

The proposal offers "enrich `pnl.json` **or** add `metrics.json`." Prefer **neither** for aggregates:

- **Per-leaf primitives** (add `mae_per_share`, `bars_held`, `stop_honored`) → persist in `pnl.json` at `finalize` (they need the sealed bars and are immutable once done).
- **Aggregates** (expectancy, PF, SQN, CIs, distributions) → **compute on read** in `get_top_session_view` / `report_by_version`. N ≤ ~60, so it's microseconds, and it preserves a *single source of truth*. A separate `metrics.json` is a denormalized cache that will silently drift from `pnl.json` the first time a formula changes or a void is re-audited — the same duplication class just removed from this codebase (two `SIM_ROOT` defs, dead batch views). Don't reintroduce it. If aggregate compute ever shows on a profile, cache it behind mtime like `_live_pnl_snapshot` already does — but only then.

---

## Metric-gaming notes (bake these warnings in)

- **Profit factor explodes at small N with few losers** (one 0-loss cohort → PF = ∞). Clamp/annotate; always show alongside N and gross-loss.
- **MFE capture is gameable by micro-scalps** — sell instantly near entry and "capture" reads high on a trade that risked nothing. Weight/segment capture by trade size or R; never rank on capture alone.
- **Expectancy without a CI invites over-reading** fractional-R gaps that are pure sampling noise at holdout N. CI is not optional here.

---

## Answers to the eight review questions

1. **Top 5–7 metrics:** Expectancy-R (edge + deployment), Profit Factor, per-leaf R distribution (mean/median/std), MFE capture, **MAE**, void %, traded %. Deprioritize: Calmar, annualized return, SQN-as-headline, equity-curve MDD.
2. **Missing signals:** cost/token efficiency; run-to-run consistency across repeats; stop-honoring rate; bars-held. Regime/correlation analysis is premature at this N.
3. **Formulas/edge cases:** per-**leaf** unit (not per-fill); `r_multiple_actual` as the R unit with budget-R fallback; two expectancies (traded-only vs all-attempts); bootstrap CI over SQN bands; MAE from the `unrealized` path; PF clamped at N / 0-loss.
4. **UI without overload:** one compact **aggregate strip** on the top-level (tickers) view — Expectancy R (±CI), PF, avg/median R, MFE capture, void%, traded%, N — plus a **sorted per-leaf R bar chart**. No new leaf-detail panels beyond adding MAE next to the existing MFE. Skip the equity curve.
5. **Comparison workflow:** `report --by-version --format json` diff is 80% there; add `batchsim compare --a <tag> --b <tag>` printing per-setup R deltas on the *identical* setups (paired, controlling for setup luck) with a sign test / paired bootstrap. Paired-on-identical-setups is far more powerful than comparing two aggregate means.
6. **LLM reasoning signals:** consistency across repeats, stop-honoring rate, avg fills/trade and bars-held, decision-divergence rate — these separate "reasoning quality" from "got lucky on one path."
7. **Pitfalls:** the holdout-contamination problem above — locked validation set, N+CI on every number, walk-forward by date. Act on this before building dashboards.
8. **References:** the Van Tharp / Brandt framing is fine; add **paired/bootstrap resampling** for small-N significance (more relevant here than any named ratio), and on the agent side **variance-across-seeds** as the reliability primitive (standard in LLM-eval).

---

## Suggested revised phasing

1. **Methodology first:** split development vs locked-validation holdouts; make every reported number carry N + bootstrap CI.
2. **Per-leaf primitives:** add MAE, bars-held, stop-honored to `_run_engine` → `pnl.json` (+ tests, per `test_recorder.py` patterns).
3. **Aggregates on read:** expectancy (both), PF, payoff, R-distribution in `get_top_session_view` / `report_by_version`.
4. **Consistency + cost:** repeats-variance and token/cost-per-run (parse from the hermes export in the audit pass).
5. **UI:** aggregate strip + sorted R-bar chart; MAE beside MFE on leaf detail.
6. **Compare view:** paired per-setup diff between two tags.

Net: the proposal's instinct — "win% and raw PnL are too thin to rank versions and models" — is correct. Trade the portfolio-time metrics for orderless, small-N-honest ones (expectancy±CI, MAE, paired diffs), add the two LLM axes it's missing (cost, repeat-consistency), and fix the holdout methodology *before* the dashboard so the richer numbers are trustworthy rather than just prettier.
