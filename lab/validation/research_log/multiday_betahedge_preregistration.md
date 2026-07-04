# Beta-Hedged Momentum — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-16 before scoring. Companions: `multiday_momentum_findings.md` (base edge,
split-adjust re-confirmation, leverage study), `EXPLORATION_PLAYBOOK.md`. **Narrow, pre-committed
test — do NOT widen the hedge-ratio set or re-tune in reaction to results.**

## Thesis (ex-ante)

The validated long-only 12-1 book carries market beta (complement-triage: momentum is positively
correlated with the market; the 2017–2024 returns ride a rising tape). Two consequences we have
already measured: (1) drawdowns are market-driven (−24% clean / −38% 8yr), and (2) the leverage
study showed sizing is *counterproductive* at the realistic Sharpe because vol/drawdown are too
high. The cross-sectional momentum *premium* (the part that is NOT market beta) was +2.78% in the
2025 OOS — a genuine, beta-orthogonal signal. **Hypothesis:** hedging the market beta strips the
beta-driven vol and drawdown, isolates the momentum alpha, and — IF the alpha Sharpe exceeds the
long-only Sharpe — yields a higher risk-adjusted return AND a much shallower drawdown, which in
turn makes leverage productive (the only way the leverage study said more CAGR is reachable).

This is the project's identified higher-ceiling path (long/short D10–D1 Sharpe 0.71–0.89 > long-only
0.7–1.0) adapted to the **no-shorting constraint**: the short leg is a broad-market hedge, not a
single-name short, and is implemented with **buyable** instruments.

## Construction (one lever: market-beta hedge ratio β)

Everything else identical to the validated base x01 rule: top-N by `mom_12_1`, equal weight,
monthly non-overlapping rebalance, H=20, $5/$10M floor, 10 bps cost. Per rebalance period:

    hedged_return(β) = book_return − β · spy_return_over_hold

- `book_return` = equal-weight mean (fwd_H − cost) of the top-N momentum book (x01).
- `spy_return_over_hold` = SPY's split-adjusted forward H-day return over the SAME hold window
  (contemporaneous with the book's hold — the hedge's realized P&L, NOT look-ahead).
- **β = FIXED, pre-committed set {0.0, 0.5, 1.0, 1.3}.** β=0.0 is the unhedged base (the bar).
  No per-period fitting, no optimization of β. We ALSO report the ex-post realized book beta
  (regress book periods on SPY periods) purely as a descriptive check of which fixed ratio best
  neutralizes — it does NOT change the pre-committed set or the decision.

## Hedge instrument & frictions (modeled honestly)

- **Idealized leg (primary):** short SPY total return at ratio β (futures-like, ~frictionless).
  This is the best-case — if the hedge fails even here, it fails.
- **Buyable proxy (sensitivity, REQUIRED to pass):** the user cannot short, so the real hedge is a
  LONG position in an inverse-S&P ETF (e.g. SH = −1×) or index puts. Apply a friction haircut to
  the hedge leg: **0.9%/yr expense** + a **conservative 0.5%/yr path-decay** allowance for the
  daily-reset inverse ETF over ~20-day holds (≈ (0.9+0.5)%·H/252 per period on the |β| exposure).
  A hedge that only works idealized but dies under this haircut does NOT pass.

## Metrics (per β, both windows)

Per-period mean, annualized Sharpe, annualized vol, **max drawdown**, residual beta/correlation to
SPY (confirm neutralization), CAGR. Report idealized AND inverse-ETF-haircut versions.

## Windows & sealed discipline

- Primary: clean **2022–2024** (`_capture_multiday_2022_2025_split.parquet`, survivorship-honest).
- Secondary: **8yr 2017–2024** (`_capture_multiday_2017_2025_split.parquet`, pre-2022 survivorship-lifted).
- **2025 hard-sealed out** (already spent; not a fresh gate). **2026 never read** (the untouched
  2nd-confirmation, data-gated ~early 2027). No new sealed year is created here.

## Decision rule (pre-committed)

A hedge ratio is an IMPROVEMENT only if, vs the unhedged base (β=0), on BOTH windows AND under the
inverse-ETF haircut:
1. **annualized Sharpe is higher**, AND
2. **max drawdown is meaningfully shallower** (≥ ~25% relative reduction), AND
3. residual SPY beta is materially reduced (hedge actually neutralizes).

- If YES → market-neutral momentum is the higher-ceiling deliverable; next step = a pre-registered
  release (longs + inverse-ETF hedge) through the swing engine, THEN re-run the leverage study on
  the hedged (lower-vol) series to see if sizing now adds CAGR. HOLD for the 2026 sealed confirm.
- If NO (Sharpe drops or drawdown doesn't improve enough) → **market beta is load-bearing / the
  momentum alpha is too thin to stand alone**; keep the long-only book at ~1.0×, and treat the
  edge as banked. Record that hedging does not help (a clean negative, like x02/vol-scaling).
- Lock the β set and frictions in THIS file before scoring; any change is a new dated spec.

---

## RESULT (2026-06-16) — beta-hedge does NOT improve; market beta is load-bearing

Run `scripts/multiday_betahedge.py`, H=20, top50, 10bps, 2025 sealed.

Hedging monotonically LOWERS Sharpe on BOTH windows; drawdown improves only marginally (< the
25% bar) and worsens at high β. The book's beta is ~1.4 (corr 0.69–0.71 to SPY) — it is largely a
high-beta tilt; the market-orthogonal momentum alpha that survives a full hedge is thin.

Clean 2022–2024 (idealized): β0 Sh +0.50/DD −24% → β0.5 +0.43/−20% → β1.0 +0.32/−25% → β1.3 +0.22/−28%.
8yr 2017–2024 (idealized): β0 +0.88/−38% → β0.5 +0.78/−34% → β1.0 +0.60/−32% → β1.3 +0.45/−35%.
Inverse-ETF haircut makes every hedged case slightly worse. Residual β neutralizes well
(1.4→0.1 at β=1.3) but the residual Sharpe is low → alpha is mostly beta.

**Verdict per the locked rule:** no β raises Sharpe → **market beta is LOAD-BEARING; the momentum
alpha is too thin to stand alone.** Keep the long-only book at ~1.0×. Clean negative (like
x02/vol-scaling). The hedged sleeve IS a low-market-correlation series (β≈0.1) but at worse
risk-adjusted return — only of interest as a diversifier to OTHER beta holdings, not as a standalone
improvement. CONCLUSION across the whole improvement search: signal conditioning, vol-scaling,
leverage, and beta-hedging all fail to beat the plain equal-weight 12-1 book — the edge is a modest,
beta-heavy momentum tilt (Sharpe ~0.7–0.9, 25–38% DD). Real remaining levers are NOT alpha:
execution/cost realism, and the 2026 sealed 2nd-confirmation (the scientific priority).
