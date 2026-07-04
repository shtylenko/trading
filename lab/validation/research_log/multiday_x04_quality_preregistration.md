# x04 — Quality (Gross-Profitability) Sleeve — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before the full capture/scoring. Source: `strategies/xsec_momentum/backlog.md` #7
+ the PIT-fundamentals data lift (SEC EDGAR, option 2) and its Stage-0 PASS. Companions:
`multiday_x03_residmom_preregistration.md`, `data/sec_fundamentals.py`. (The x04 number was freed when
overlapping-construction x04 and FIP-x04 were both REJECTED without shipping.) Narrow, pre-committed —
do NOT widen the variant set or re-tune after seeing results.

## Thesis (ex-ante) — and the exact question it settles

Every long-only diversifier we have tried (low-vol, st-reversal, near-low, short-mom, defensive
sleeves) shared market beta with momentum and failed to smooth the book. **Gross profitability**
(Novy-Marx 2013) is the one remaining untested orthogonal channel: high-GP firms earn higher returns,
the effect is roughly value-neutral, and it historically held up in down markets. Its Stage-0 was the
first new signal this campaign to PASS — D10−D1 positive all three years (pooled spearman +0.80) and,
critically, **positive in the 2022 bear** where momentum/beta struggled. That bear-year-positive shape
is the ex-ante reason to believe it may be REGIME-COMPLEMENTARY rather than another shared-beta tilt.

**This settles two questions:** (1) is GP a REAL signal on our universe (positive beta-adjusted alpha
that survives WF/PBO/DSR), or a low-vol/large-cap beta artifact like the killed diversifiers? and
(2) if real, is it ADDITIVE to x03 — low-correlation + a blend that out-Sharpes x03 alone — i.e. the
first genuine diversifying sleeve this family has found?

## Construction (one lever: rank on quality instead of momentum)

Everything except the ranking signal is identical to x01/x03: top-50 equal weight, monthly
non-overlapping rebalance, H=20, $5/$10M eligibility floor, 10 bps cost, SPLIT-adjusted price bars.

- **Ranking signal = `gp_assets`** (PIT): (TTM revenue − TTM COGS) / total assets, all as KNOWN at the
  rebalance date (`filed <= d`), from `data/sec_fundamentals.py`. Rank eligible names DESC, long top 50.
- Eligible = the usual price/liquidity floor AND `gp_assets` is computable (non-financials with
  reported revenue, COGS, assets known at d). Financials/REITs (no COGS) are excluded — a documented
  coverage limitation (~68% of names), not a leak.
- **Secondary, DESCRIPTIVE only (not gated):** `ni_yoy` (TTM net-income YoY, earnings momentum) — the
  Stage-0-borderline signal; report its standalone metrics + corr, but the promote/kill decision is on
  `gp_assets`.

Leak-safe: PIT by construction (filed≤asof, with the restatement/implied-quarter fixes validated in
the adapter). Names without ≥ the fundamentals history needed for a TTM are excluded.

## Windows, metrics, sealed discipline

- Windows: clean **2022–2024** (primary, true PIT) + **2017–2024** (secondary, survivorship-flagged —
  the price-ledger universe is Alpaca's active list, optimistic pre-2024; treat as upper bound). 2025
  hard-sealed out; 2026 never read.
- Headline metric = **beta-adjusted alpha** (intercept + t of book per-period returns regressed on
  SPY) — the discriminator between real signal and shared beta (the §6b lesson). Also: annualized
  Sharpe, realized beta, max drawdown, DSR, decile monotonicity, and the additivity block below.
- Full pipeline: LOO walk-forward (each year held out), PBO via CSCV, DSR. Same machinery as x03.

## Decision bar (pre-committed)

**A. Is it REAL?** On clean 2022–2024 (not contradicted on 2017–2024):
1. **beta-adjusted alpha intercept > 0 with t materially above 0** (ideally |t| > 2 pooled), AND
2. **annualized Sharpe ≥ +0.5**, AND
3. **DSR ≥ 0.95** on clean 2022–2024.

**B. Is it ADDITIVE to x03?** (the decisive diversifier test — a quality sleeve earns its place by
COMPLEMENTING momentum, not by beating it standalone):
4. **corr(quality book, x03 book) per-period < 0.6**, AND
5. **a 50/50 x03+quality blend has annualized Sharpe ≥ x03 alone × 1.10** (≥10% Sharpe lift), with
   max drawdown no worse than x03.

## Outcomes (pre-committed)

- **PROMOTE-CANDIDATE** — passes A AND B: implement immutable `x04` (quality sleeve), run the
  swing-engine cross-check, and EARMARK a future sealed year (~2027 — both 2025 and 2026-H1 spent; NO
  sealed data spent now). This would be the family's FIRST diversifying sleeve → the deployment becomes
  an x03+x04 blend, not x03 alone.
- **REAL-BUT-NOT-ADDITIVE** — passes A, fails B: quality is a real signal but too correlated/
  non-complementary to improve the book; record it, do not ship a sleeve, bank x03 standalone.
- **KILL** — fails A: GP is a beta/low-vol artifact on our universe, like every prior long-only
  diversifier; the Stage-0 +0.80 was shared exposure, not alpha. Bank x03; fundamentals direction
  closed (modulo the `ni_yoy`/earnings-momentum re-look if it surprises descriptively).

## Sealed discipline

In-sample ONLY (both sealed years spent). Lock the ranking signal (`gp_assets`), the windows, the
pipeline, and the A/B bars in THIS file; any change is a new dated spec. Capture:
`scripts/capture_fundamentals.py` (the long EDGAR fetch — run manually). Scoring:
`scripts/multiday_quality.py` (fast, reads the capture parquet).

---

## RESULT (2026-06-18) — KILL: gross profitability is pure beta on our universe

Full PIT capture (`_capture_fundamentals_2017_2024.parquet`, 172,508 rows / 1,708 tickers; gp_assets
coverage 53%, ni_yoy 73%) scored by `scripts/multiday_quality.py`.

**A. IS IT REAL? — FAIL on every cut.** Beta-adjusted, top-50 EW book:

| window | scheme | annSh | β | α% | t(α) | maxDD | DSR |
|---|---|---|---|---|---|---|---|
| clean 2022–24 | x03 resid | +0.71 | 1.06 | +0.47 | +0.76 | −11.4% | 0.79 |
| clean 2022–24 | **x04 gp_assets** | +0.14 | 1.13 | **−0.54** | **−1.55** | −25.5% | 0.43 |
| clean 2022–24 | x04 ni_yoy | +0.17 | 1.14 | −0.48 | −0.96 | −29.3% | 0.46 |
| 8yr 2017–24 | x03 resid | +0.95 | 1.11 | +0.75 | +1.43 | −24.5% | 0.99 |
| 8yr 2017–24 | **x04 gp_assets** | +0.69 | 1.20 | **+0.00** | **+0.00** | −35.7% | 0.93 |

The 8yr gp_assets alpha is **exactly 0.00 (t 0.00)** — zero market-orthogonal alpha over 8 years; the
book is pure beta. Clean 2022–24 is worse (NEGATIVE alpha, t −1.55). Both signals, both windows: FAIL.

**B. IS IT ADDITIVE TO x03? — FAIL.** corr(x04, x03) = +0.67 (clean) / +0.76 (8yr), above the 0.60 bar;
the 50/50 blend Sharpe is LOWER than x03 alone (clean +0.48 vs +0.71; 8yr +0.88 vs +0.95) with DEEPER
drawdown. Not a diversifier — it's correlated, lower-Sharpe beta.

**Verdict: KILL.** Gross profitability (and earnings momentum) on our universe is a beta/growth tilt,
not orthogonal alpha — like every prior long-only diversifier. **Why the Stage-0 +0.80 was a mirage:**
that triage measured decile monotonicity of RAW forward returns (not beta-adjusted), and the
top-50-by-GP book across the FULL universe selects the most extreme gross-profitability names —
asset-light, high-multiple growth/software — which is a high-beta growth tilt that fell hard in 2022,
NOT the defensive "quality" the literature describes. Bar A (beta-adjusted alpha) was built precisely
to catch this, and did. The §6b lesson again: raw decile monotonicity can be beta; only beta-adjusted
alpha counts. **The PIT-fundamentals direction is CLOSED.** x03 (residual momentum) remains the
family's only validated edge; no long-only diversifier exists for it. Bank x03 standalone.

Reusable assets kept: `data/sec_fundamentals.py` (validated true-PIT EDGAR adapter),
`_capture_fundamentals_2017_2024.parquet`, `scripts/{capture_fundamentals,multiday_quality,
multiday_fundamentals_triage}.py` — available if a future fundamentals idea (value composite, proper
defensive-quality QMJ via low accruals/leverage, not GP) is ever pre-registered.
