# x04 — Value Sleeve (Book-to-Market / Earnings Yield) — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before scoring. Source: `strategies/xsec_momentum/backlog.md` (keyword-report P2 #8
"value+momentum composite — confirmed by Titman", previously data-gated; the EDGAR lift unblocks it).
Companions: `multiday_x03_residmom_preregistration.md`, `multiday_x04_quality_preregistration.md` (the
quality KILL — read its lesson), `data/sec_fundamentals.py`. **Narrow, pre-committed — do NOT widen.**

## Thesis (ex-ante) — and the exact question it settles

Value is the CANONICAL momentum complement. Unlike quality (which we just killed because it shared
momentum's beta), value (cheap stocks) is historically **negatively correlated** with momentum and
shines in the exact regime momentum crashes: 2022 was a banner year for value as growth/momentum fell.
Titman (keyword report): value + momentum "are not that highly correlated… more efficient to combine
them." So value's appeal here is NOT a higher standalone Sharpe — it is **diversification**: a sleeve
that is low/negatively correlated to x03 can raise the BLEND Sharpe even if it is modest alone.

**This settles:** does a PIT value signal on our universe (a) earn a positive, non-beta-artifact
return, and (b) DIVERSIFY x03 — low correlation + a blend that out-Sharpes x03 — making it the first
genuine diversifying sleeve this family has found? (The quality test failed (b) hard: corr 0.67–0.76.)

**Lesson applied from the quality KILL:** judged BETA-ADJUSTED from the start. The quality Stage-0
+0.80 was a raw-return beta mirage. No raw-decile-only gate here — alpha and additivity are the bars.

## Construction (one lever: rank on cheapness; universe/cadence unchanged)

Identical to x01/x03 except the ranking signal: top-50 equal weight, monthly non-overlapping, H=20,
$5/$10M floor, 10 bps cost, SPLIT-adjusted price bars for RETURNS.

- **Market cap (split-safe):** `shares_outstanding(as-reported, filed ≤ d)` × **RAW** close(d) — as-
  reported share counts pair with UNADJUSTED price (validated: NVDA $822.79×2.50B = $2.06T; using the
  split-adjusted price would be 10× wrong). Raw close from `_capture_multiday_2017_2025.parquet`.
- **Ranking signal = `book_to_market` = StockholdersEquity(filed ≤ d) / market_cap.** Rank DESC
  (highest B/M = cheapest = value); long top 50. Pre-committed PRIMARY.
- **Eligibility:** usual price/liquidity floor AND positive book equity (negative-equity names —
  buyback-heavy — have meaningless B/M and are excluded) AND B/M computable (shares+equity known at d).
- **Secondary, DESCRIPTIVE only (not gated):** `earnings_yield` = TTM NetIncome / market_cap.

Leak-safe: all fundamentals as-known-at-d (filed ≤ d), with the adapter's validated PIT/restatement/
implied-quarter fixes. RAW price is observable at d (no look-ahead).

## Windows, metrics, sealed discipline

- Windows: clean **2022–2024** (primary, true PIT) + **2017–2024** (secondary, survivorship-flagged).
  2025 hard-sealed out; 2026 never read. NOTE ex-ante: value was WEAK 2017–2020 (growth dominance),
  STRONG 2022 — so a value sleeve should be POSITIVE in 2022 where momentum crashed (the complementary
  regime that makes it worth holding); a flat-2022 value book would undercut the whole thesis.
- Metrics vs x03 on the SAME periods: beta-adjusted alpha (intercept + t vs SPY), annualized Sharpe,
  realized beta, max drawdown, DSR, decile monotonicity (reported, NOT gated), and the additivity block.

## Decision bar (pre-committed)

**A. Is it REAL (not a beta artifact)?** On clean 2022–2024 (not contradicted on 2017–2024):
1. **beta-adjusted alpha intercept > 0 with t > 0**, AND
2. **annualized Sharpe ≥ 0.3** (deliberately LOWER than quality's 0.5 — value earns its keep via
   diversification, not standalone Sharpe; pre-committed ex-ante, not a post-hoc move), AND
3. **DSR ≥ 0.90**.

**B. Is it ADDITIVE to x03 (the decisive diversifier test)?**
4. **corr(value book, x03 book) per-period < 0.5** (we EXPECT low/negative — the whole point), AND
5. **50/50 x03+value blend annualized Sharpe ≥ x03 alone × 1.10**, with max drawdown no worse than x03.

## Outcomes (pre-committed)

- **PROMOTE-CANDIDATE** — passes A AND B: the family's FIRST diversifying sleeve. Implement immutable
  `x04` (value), run the swing-engine cross-check, EARMARK a ~2027 sealed year (none spent now).
  Deployment becomes an x03+x04 blend.
- **REAL-BUT-NOT-ADDITIVE** — passes A, fails B: value is real but doesn't diversify x03 on our
  universe; record it, bank x03 standalone.
- **KILL** — fails A: value is noise or a wrong-signed beta artifact here; bank x03. The "find a
  diversifier" thread is then exhausted with earned evidence.

## Sealed discipline

In-sample ONLY (both sealed years spent). Lock the signal (`book_to_market`), market-cap construction
(as-reported shares × raw price), eligibility, windows, and A/B bars in THIS file; any change is a new
dated spec. Capture: `scripts/capture_value.py` (FAST — reads cached EDGAR facts + raw parquet, NO new
network fetch). Scoring: `scripts/multiday_value.py`.

---

## RESULT (2026-06-18) — KILL: value is a high-beta tilt on our universe; thesis falsified

PIT value capture (`_capture_value_2017_2024.parquet`, 103k rows / 1557 tickers; book_to_market
coverage 91%) scored by `scripts/multiday_value.py`, beta-adjusted from the start.

**A. IS IT REAL? — FAIL.**

| window | scheme | annSh | β | α% | t(α) | maxDD | DSR |
|---|---|---|---|---|---|---|---|
| clean 2022–24 | x03 resid | +0.71 | 1.06 | +0.47 | +0.76 | −11.4% | 0.80 |
| clean 2022–24 | **x04 book_to_market** | +0.11 | **1.36** | **−0.69** | −1.04 | −27.1% | 0.42 |
| clean 2022–24 | x04 earnings_yield | +0.46 | 1.16 | +0.02 | +0.04 | −20.1% | 0.73 |
| 8yr 2017–24 | **x04 book_to_market** | +0.34 | **1.58** | **−0.69** | −1.20 | **−49.0%** | 0.62 |

**The 2022-positivity check FAILED — the decisive falsification.** The thesis required value to be
POSITIVE in 2022 (the bear where momentum crashed); instead book_to_market was **−1.04%** and
earnings_yield **−0.23%** in 2022 — value's supposed banner year. Beta is HIGHER than momentum
(1.36–1.58), alpha is zero-to-negative.

**B. IS IT ADDITIVE? — FAIL.** The expected low/negative correlation never appeared: corr(value, x03)
= +0.57 to +0.63 (bar < 0.50). The 50/50 blend Sharpe is LOWER than x03 alone everywhere (clean +0.42,
8yr +0.68) with DEEPER drawdown.

**Verdict: KILL (both signals, both windows).** Why the textbook value-complement thesis fails HERE:
our universe is liquid US large/mid-caps with a $5/$10M-ADV floor. On that universe the value spread
(high B/M, high E/P) loads on **distressed/cyclical/high-beta** names (financials, rate-sensitives that
got crushed in the 2022 rate shock), NOT the defensive academic-HML value (which lives partly in small
illiquid names and is value-weighted). So value — like quality (`gp_assets`) and FIP — **collapses to a
high-beta tilt on this universe.** This is now a STRONG meta-finding: NO cross-sectional fundamental or
path signal provides orthogonal alpha or diversification beyond residual momentum here; the UNIVERSE is
the binding constraint (echoes the o03/f-series "setup classes look edgeless on this universe"). x03 is
the ceiling. The find-a-diversifier thread is exhausted with earned evidence → bank x03 standalone.

Reusable kept: `data/sec_fundamentals.py` (now also EQUITY/SHARES + split-safe market cap),
`_capture_value_2017_2024.parquet`, `scripts/{capture_value,multiday_value}.py`.
