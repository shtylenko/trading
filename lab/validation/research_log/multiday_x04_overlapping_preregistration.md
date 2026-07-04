# x04 — Overlapping-Portfolio Construction (Jegadeesh-Titman) — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before scoring. Source: `strategies/xsec_momentum/backlog.md` #9 (top of the
re-prioritized Tier-1 from `peer-feedback/2026-06-17-keyword-research/report.md`). Companions:
`multiday_x03_residmom_preregistration.md` (the ranking this builds on), `multiday_momentum_findings.md`.
**Construction change, NOT a new ranking signal → NO sealed year is spent** (validated on clean 2022+
in-sample + the already-spent 2025 OOS as a reproduction). Narrow, pre-committed — do NOT widen.

## Thesis (ex-ante) — and the exact question it settles

x01/x03 use **non-overlapping** construction: every H=20 trading days the *entire* book is rebalanced
(sell all 50, buy the new top 50). Jegadeesh-Titman (1993) instead run **K overlapping sub-portfolios**:
a fresh sleeve of the top-50 is formed each step, each sleeve is held H days, and the live book is the
equal-weight average of the K = H/step sleeves currently inside their hold. With step = 1 trading day,
K = 20 sleeves; ~1/20 of capital rolls each day.

**Honest framing of the benefit (corrected from the backlog's first draft):** overlapping does NOT
reduce capital turnover *per unit time* — you still roll the whole book over H days either way, so the
linear (spread) cost per unit time is ≈ unchanged. The two genuine wins are:

1. **Variance reduction (Sharpe).** Averaging K staggered sleeves removes the single-rebalance-date
   timing luck (the "you happened to reconstitute on a bad day" risk) and smooths the equity curve.
   Same expected gross return, lower vol → higher gross Sharpe. This is a pure construction effect.
2. **Capacity (peak participation).** The binding real-world limit (portfolio review: ~$48M at ≤5% ADV)
   is set by the *lumpy* rebalance day, when you trade a full AUM/50 clip per name at once. Overlapping
   trades only (AUM/K)/50 per name per day → **peak participation drops ~K×**, so the same ≤5%-ADV cap
   supports materially higher AUM, and the convex market-impact term is paid on much smaller clips.

**This test settles:** does overlapping construction, applied to the x03 residual ranking, improve
gross Sharpe (variance reduction) AND raise net-of-cost capacity, enough to adopt it as x04?

## Construction (one lever: overlapping sleeves; ranking + universe unchanged)

Everything except construction is identical to x03: rank on **CAPM-residual momentum** (`mean(ε)/std(ε)`,
formation `[d−252, d−21]`, SPY market leg), top-50 equal weight, H=20 hold, $5/$10M eligibility floor,
SPLIT-adjusted bars. The ONLY change is non-overlapping → overlapping.

- **Sleeve cadence:** step = 1 trading day → **K = 20** overlapping sleeves (pre-committed primary).
  Secondary descriptive: step = 5 (K = 4) to show the K-vs-smoothing tradeoff. No other step values.
- **Book daily return** on day j = mean over the sleeves with `form_idx < j ≤ form_idx + H` of that
  sleeve's equal-weight one-day return. Aggregated to a daily series, annualized with √252.
- **Reference arms (same ranking, same window):** (a) non-overlapping x03 (H-block), (b) non-overlapping
  x01 (raw mom_12_1) — so we see construction effect separate from the ranking effect.
- Leak-safe: each sleeve's ranking uses only data through its own `d−21`; daily returns are realized
  forward. Names with < 126 formation obs excluded (same coverage limitation as x03).

## Cost / capacity model (pre-committed) — the "extended cost curve"

Per-name one-way cost in bps as a function of participation (convex impact, the report's formula):

    cost_bps(p) = SPREAD_BPS/2 + IMPACT_BPS · √(p),   p = clip_notional_per_name / name_20d_$ADV

Pre-committed constants: **SPREAD_BPS = 5**, **IMPACT_BPS = 10** (√-law coefficient; a name traded at
100% of ADV pays ~10 bps impact). Charged round-trip (entry + exit). Per-name clip:
- non-overlapping: full position `AUM/50`, traded on the rebalance day (peak participation).
- overlapping (K): only the rolling sleeve trades, clip `= (AUM/K)/50` per name per roll.

Report the **net annualized Sharpe vs AUM curve** for AUM ∈ {5, 10, 25, 50, 100, 250}M, both
constructions, on the clean 2022–2024 window (primary) and 8yr 2017–2024 (survivorship-flagged
secondary). Also report, descriptively: peak participation per construction at each AUM, the AUM at
which net Sharpe falls 10% below gross ("practical capacity"), and gross Sharpe of each arm.

## Decision bar (pre-committed)

x04 (overlapping on x03 ranking) is **ADOPTED as the deployment construction** if, vs non-overlapping
x03 on the SAME periods:

1. **gross annualized Sharpe ≥ non-overlapping x03** (variance reduction is real, not a return give-up;
   a small gross improvement is expected, flat is acceptable — overlap must not *hurt* gross), AND
2. **practical capacity (net-Sharpe-within-10%-of-gross AUM) is ≥ 2× the non-overlapping value** — the
   capacity win is the decision-critical one; if overlap doesn't buy materially more tradeable AUM it
   isn't worth the construction complexity, AND
3. **net Sharpe at the binding AUM (the non-overlap practical capacity, ~$48M) is ≥ non-overlap's** —
   i.e. at the AUM where non-overlap is already cost-stressed, overlap is strictly better.

## Outcomes (pre-committed)

- **ADOPT → implement immutable `x04`** (`SwingStrategyRelease` with overlapping construction; the swing
  runner gains an `overlapping`/`sleeve_step` construction mode). This becomes the deployment form of
  the residual-momentum edge. No sealed year spent; earmark the ~2027 holdout for the *next ranking*
  signal, not for x04.
- **REJECT / informative negative** (gross Sharpe drops, or capacity doesn't ≥2×): non-overlapping
  stays the construction; record that overlapping's textbook benefit doesn't materialize on our
  universe/horizon (likely because residual momentum is already low-turnover and H=20 is short enough
  that single-date timing luck is small). Either way the cost curve tells us the true tradeable AUM.

## Sealed discipline

In-sample + spent-2025 reproduction ONLY. **No sealed year is consumed** (construction change, not a
new signal). Lock the sleeve cadence (K=20 primary), ranking (= x03, frozen), cost constants, and AUM
grid in THIS file; any change is a new dated spec. Script: `scripts/multiday_overlapping.py`.

---

## RESULT (2026-06-18) — REJECT (keep non-overlapping); informative negative

Run `scripts/multiday_overlapping.py --ledger ..._capture_multiday_2017_2025_split.parquet
--start-year 2022 --end-year 2024` (clean PIT, 2025 sealed). x03 residual ranking, top-50 EW, H=20,
daily-overlap K=20.

**1. Variance reduction — FAILS bar #1.** gross annualized Sharpe: non-overlap **+0.78** (maxDD −19.5%)
vs overlap **+0.73** (maxDD −20.5%). Overlapping slightly HURTS both Sharpe and drawdown. Mechanism:
at H=20 with a sticky residual ranking (~39% turnover/roll), single-rebalance-date timing luck is
already small, so the averaging buys little vol reduction — while the overlapping book always carries
sleeves formed up to 19 days ago on *stale* rankings, diluting the freshest signal. Non-overlap, by
re-ranking the whole book each block, always holds the freshest top-50. Net: mean return drops more
than vol does.

**2. Capacity win is real but MOOT.** Overlap's ~K× smaller clips do crush peak participation (at
$250M: 2.3% of ADV vs non-overlap's 45.9%). But under the locked cost model (spread 5bps + 10bps·√p,
round-trip), non-overlap is **not cost-stressed at realistic AUM**: net Sharpe holds +0.77→+0.76
across $5M→$250M (peak participation only 9.2% at $50M). So the "overlap unlocks more tradeable AUM"
thesis has no bite here — there is no AUM in the realistic range where non-overlap's cost has degraded
enough for overlap's capacity advantage to matter. Bars #2 and #3 therefore cannot be met (overlap is
strictly ≤ non-overlap at every AUM tested).

**Verdict: REJECT.** Non-overlapping stays the deployment construction. The textbook Jegadeesh-Titman
benefit does not materialize on our universe/horizon — precisely because residual momentum is already
low-turnover and H=20 is short enough that reconstitution-date luck is negligible. No release shipped,
no sealed year spent. Caveats: (a) the cost constants are deliberately moderate; if real impact is
much higher (the portfolio-review worry of 15–30bps all-in), non-overlap *would* eventually stress and
the capacity channel could revive overlap — but that is a cost-assumption question, settle it with a
live-fill study before revisiting, not by adopting overlap speculatively. (b) This also makes #14
(H=63 turnover-light variant) lower priority — turnover/cost is not the binding leak the report
implied. **The real lever for this family remains the ranking signal, not the construction.**
