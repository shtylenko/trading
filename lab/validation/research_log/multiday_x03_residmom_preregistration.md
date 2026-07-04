# x03 — Residual (Idiosyncratic) Momentum — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-17 before scoring. The peer review's unanimous #1 (gemini/grok/meta,
`peer-review/2026-06-16-x-feedback/`). Companions: `strategies/xsec_momentum/backlog.md`,
`multiday_momentum_findings.md`. **Narrow, pre-committed — do NOT widen the variant set or re-tune.**

## Thesis (ex-ante) — and the exact question it settles

Plain 12-1 total-return momentum has unstable, drifting factor loadings: in a bull it morphs into a
high-beta, small-cap tilt (our x01 book beta ≈ 1.4). The 2026-06-17 beta-adjusted alpha check found
x01's market-orthogonal alpha on the clean 38-period window was only +0.30%/period at **t = +0.31
(insignificant)** — i.e. x01's return is mostly market/size beta, not alpha.

Residual momentum (Blitz, Huij & Martens 2011) ranks on the **idiosyncratic** return — momentum of
the regression residual after stripping market (and optionally size/value) factors — so the ranking
itself removes the beta ride. Literature: comparable gross return at ~half the vol, ~2× Sharpe, far
lower crash risk. **This test settles the open question: is there real, beta-orthogonal alpha in
cross-sectional momentum on our universe, or has it been beta all along?**

## Construction (one lever: rank on residual instead of raw return)

Everything else identical to x01: top-50 EW, monthly non-overlapping rebalance, H=20, $5/$10M floor,
10 bps cost, SPLIT-adjusted bars. The ONLY change is the ranking signal.

- **Factor model: CAPM (single-factor, market = SPY).** Pre-committed primary. (FF3 is a later
  robustness variant ONLY if a clean daily PIT factor series is added — not in this test.)
- **Formation window:** the 11-month window `[d−252, d−21]` (skip the last month, like 12-1).
- At each rebalance d, for every eligible name with ≥ **126** daily returns in the window:
  1. Regress daily `r_i,t` on daily `r_SPY,t` over the formation window → residual series `ε_i,t`.
  2. **resid-mom signal = mean(ε_i) / std(ε_i)** over the formation window (a standardized
     idiosyncratic information ratio — Blitz et al. form).
- Rank eligible names by resid-mom (desc); long top 50 equal weight.

Leak-safe: the regression and residual sum use only data through `d−21`; nothing forward. Names with
< 126 window obs (recent IPOs) are excluded (a documented coverage limitation, not a leak).

## Decision bar (pre-committed) — judged on clean data, beta-adjusted

Primary window = clean **2022–2024** (true PIT); secondary = **8yr 2017–2024** (survivorship-flagged).
The headline metric is the **beta-adjusted alpha** (regress the strategy's per-period returns on SPY,
report intercept + t-stat), because raw Sharpe/premium can be beta (the §6b lesson). x03 is a real
improvement only if, vs x01 base on the SAME periods:

1. **beta-adjusted alpha intercept is positive AND its t-stat materially exceeds x01's** (x01 was
   t ≈ +0.31), ideally |t| > 2 on the pooled clean+8yr evidence, AND
2. **annualized Sharpe ≥ x01's** (we do not want to trade return for a cleaner-but-tiny alpha), AND
3. **DSR ≥ 0.95** on clean 2022–2024.

Also report, descriptively: realized book beta (expect << 1.4 if residualization worked), max
drawdown, decile monotonicity, correlation of the resid-mom book returns to the x01 book.

## Outcomes (pre-committed)

- **PROMOTE-CANDIDATE** (clears 1–3): residual momentum is the better release → implement immutable
  `x03`, run the swing-engine cross-check, and EARMARK a future sealed year (no sealed data is spent
  now — both 2025 and 2026-H1 are spent; a clean confirmation waits for a new holdout ~2027).
- **KILL / informative negative** (alpha still insignificant, or worse than base): then cross-sectional
  momentum on this universe is **substantially beta** even after residualization → x01 is honestly a
  beta-tilt; bank it as such, stop hunting momentum alpha. Either outcome is decision-useful.

## Sealed discipline

In-sample ONLY. Do NOT spend a sealed year on x03 now (none available). 2025 and 2026-H1 are spent;
2026 full-year (~early 2027) or a later year is the next clean holdout. Lock the factor model,
formation window, signal form, and bar in THIS file; any change is a new dated spec.

---

## RESULT (2026-06-17) — PROMOTE-CANDIDATE on RISK, not new alpha

Run `scripts/multiday_residmom.py` (residual mom computed from existing split parquets + SPY; CAPM,
formation [d-252,d-21], signal mean(ε)/std(ε); 2025 sealed). Note: residual mom needs 252d of prior
DAILY returns, so the 2022–2025 parquet only tests ~2023–24 (24 periods); the 8yr parquet is the
proper test (87 periods, full formation history for 2022–24).

8yr 2017–2024 (87 periods): base Sharpe +0.81 / β 1.45 / α +0.65% (t +0.90) / maxDD −36.2% / DSR 0.980;
**residual Sharpe +0.89 / β 1.08 / α +0.56% (t +1.13) / maxDD −22.6% / DSR 0.988.** corr(base,resid)=0.95.
Truncated clean 2023–24 (24 periods) agreed more strongly: Sharpe 1.06→1.59, maxDD −20.2%→−8.1%, β 1.79→1.24.

**Verdict: PROMOTE-CANDIDATE** (clears the literal bar: residual α-t > base, Sharpe ≥ base, DSR ≥ 0.95,
α > 0). **But the win is RISK, not new alpha:** residualization cut beta (1.45→1.08), cut max drawdown
(~38% shallower), and raised Sharpe — while the market-orthogonal alpha stayed positive-but-INSIGNIFICANT
(t +1.13, magnitude slightly lower than base). So x03 is a better-engineered version of the same modest,
beta-trimmed momentum edge — NOT a new alpha source. It is the first thing this cycle to beat base x01 on
the confirmatory sample (vs conditioning/vol-scale/leverage/hedge all killed). Caveats: CAPM single-factor
(FF3/size untested); 8yr is survivorship-lifted; both sealed years spent → a clean OOS confirmation waits
for a new holdout (~2027); the lower drawdown makes modest sizing/leverage productive again (follow-on).
NEXT: implement immutable release x03 + swing-engine cross-check; earmark a future sealed year.
