# Strategy Synthesis — where could a durable edge live? (2026-06-16)

A deliberate step-back after five families/ideas were killed or downgraded. Purpose:
turn the accumulated kills into an explicit map of where edge could plausibly remain,
so the next bet is made on evidence, not vibes. Sources: the family backlogs and the
auto-memory (orb-v2, dominance-flip, feature-search, intraday-momentum,
synthetic-positive-control, cross-family-2026h1, overnight-premium).

## 1. What we've tested, and what each kill actually proved

| Family / idea | Mold | Verdict | What it proved |
|---|---|---|---|
| **o** SIP-ORB | long, same-day, intraday | EXHAUSTED | opening-range breakout has no edge under cost drag on liquid names |
| **d** gap-and-go | long, same-day, intraday | RETIRED (earned) | a 3/3-LOO in-sample edge (+40.9R) still failed sealed-2025 (−34R); opening drives fade after 11:30 |
| **f** dominance-flip / mean-rev | long, same-day, intraday | KILLED | reversal/mean-reversion setup classes edgeless long-only on this universe |
| **m** intraday momentum (ETFs) | long, same-day, intraday | EXHAUSTED @ Stage 0 | BOTH Gao predictors (r1, r12) gross-negative; the effect is decayed / index-level / not-long-only-same-day |
| **overnight** premium | long, overnight hold | CLOSED, below bar | premium is REAL but thin regime BETA; no cross-sectional alpha (overfits even gross); overlay insignificant (t<1), 2/4 yrs negative net |

**Meta-result (the load-bearing one):** the validator is PROVEN SOUND (synthetic
dose-response control — it confirms a planted edge monotonically and rejects the
null; it killed a +650% in-sample overnight mirage on walk-forward, gross). So the
~100% kill rate is NOT a broken pipeline. **The binding constraint is the MOLD, not
the machinery.**

## 2. The mold, decomposed — five constraints, ranked by how much they bind

The current engine imposes five constraints simultaneously. The evidence says some
are far more binding than others:

1. **Same-day / flat overnight** (intraday horizon). ← *most binding.* Four intraday
   families dead; and we now know WHY structurally — ~all the equity premium accrues
   overnight, the window same-day skips. Intraday long-only liquid is a near-zero-sum
   slice after costs.
2. **Long-only** (no short leg). ← *highly binding.* The most robust equity anomalies
   (short-term reversal, cross-sectional spreads) need a short side; we even SAW
   reversal in the overnight tail (rsi2-oversold +7bps gross) but couldn't express it
   profitably long-only.
3. **Fixed construction** (breakout-stop, 1R stop, time exit). Moderately binding —
   the search only tunes admission, not structure (let-winners-run, trailing, R:R).
4. **Liquid US stocks** (cost-bearing, efficient). Binding via costs (overnight died
   on 2-3bps fragility) but the universe itself isn't the problem (ETF≈stock results).
5. **Independent 1%/trade sim** (no portfolio correlation). A measurement caveat, not
   a source of edge; makes negatives SAFE and positives owe a portfolio re-check.

## 3. Where edge could plausibly still live (ranked by evidence × EV ÷ effort)

### A. Multi-day swing, LONG-ONLY (relax constraint #1 — RECOMMENDED next bet)
Hold days-to-weeks instead of intraday. Rationale, strongest of any option:
- **The evidence already lit this up.** We just proved the overnight premium is real;
  a multi-day hold *harvests that premium across many nights* plus any drift — it
  goes WITH the grain the data revealed, not against it.
- **Long-expressible anomalies with real OOS track records live here**: post-earnings-
  announcement drift (PEAD), cross-sectional / 52-week-high momentum, time-series
  momentum. None need a short leg.
- **Lowest marginal engine cost.** The overnight capture I built is daily-bar,
  leak-safe features — 90% of a swing capture. The only change is the LABEL:
  `close(d+H)/close(d) − 1` instead of `open(d+1)/close(d) − 1`. The whole trusted
  search (LOO-WF → PBO → DSR → sealed) applies unchanged. Days, not weeks, of work.
- **Honest caveat:** multi-day holds carry overnight gap risk and need real position
  management for the engine cross-check; and PEAD needs an earnings calendar (data we
  must source). But Stage 0/1/2 (capture + offline search) need NEITHER — daily bars
  + (for PEAD) an earnings date list.

### B. Long/SHORT cross-sectional (relax constraint #2 — highest ceiling, most work)
Enable a short leg → express short-term reversal and cross-sectional spreads (the
most academically robust anomalies). Highest theoretical ceiling. But: needs real
engine work (short execution, borrow/locate/hard-to-borrow costs), and shorting adds
its own cost/risk/squeeze hazards. Better as the SECOND structural step, after a
long-only multi-day result tells us whether the cross-sectional signals even exist on
our universe.

### C. Different construction on a surviving signal (relax constraint #3)
Re-express a signal that had a real in-sample edge (gap+rvol) with a different
structure (let-winners-run, trailing stop, asymmetric R:R) as a pre-registered NEW
construction. Cheap-ish, but lower EV — the sealed-2025 kill of gap+rvol suggests the
signal itself decayed, not just its packaging.

### D. Out of current scope: options/vol, futures, crypto, intraday HF. Different
engine/data entirely — park unless we decide to widen the platform.

## 4. Recommendation

**Take the multi-day swing, long-only path (A) as the next bet**, starting with the
single strongest long-expressible anomaly we can get clean data for. It is the
highest expected value PER UNIT OF EFFORT: it relaxes the most-binding constraint in
the exact direction the overnight evidence already pointed, it's long-expressible (no
short engine needed yet), it targets anomalies with the best out-of-sample records,
and it reuses the daily-bar capture + the trusted search almost verbatim (new label,
same pipeline). Hold long/short (B) in reserve as the bigger, costlier second move.

Concrete first step (Stage 0, cheap, offline): pick the horizon (e.g. H = 5 and 20
trading days) and the first signal class — **52-week-high / cross-sectional momentum**
(no extra data needed; pure daily bars) is the cleanest start; **PEAD** is stronger
but needs an earnings calendar. Measure the bare multi-day forward return by signal
decile (the Stage-0 triage), exactly as we did for overnight, before any search.

## 5. Discipline carried forward (unchanged)

Capture broad / lock search narrow; daily-portfolio IR objective + LOO-WF; PBO + DSR
≥ 0.95; pre-registered minimum effect size that clears realistic costs; spend the
sealed year ONCE (rotate years across families — see oos_spend_ledger); the sealed
year is the only honest test; a clean negative beats a contaminated positive. The
synthetic control remains the standing meta-check — re-run it if the objective/gates
change for the multi-day label.
