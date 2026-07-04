# x04 — Top-35 Concentration Variant of x03 — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-21 before any sealed read. Source: the exploratory threshold study
`scripts/multiday_residmom_absthresh.py` (run on 2022–24 split + 2009–16 YF). Companion:
`multiday_x03_residmom_preregistration.md` (the ranking this inherits unchanged).
**Narrow, single-lever, pre-committed — do NOT widen or re-tune after seeing results.**

> x04-number lineage: six prior x04 *candidates* (FIP, FF3-residual, ATR-exit, value,
> overlapping, quality/GP) were each pre-registered and KILLED before shipping (see the
> `backlog.md` kill-table). The id was freed on every rejection. This concentration variant
> is the first x04 candidate to survive to a shipped release, so it keeps the number.

## Thesis (ex-ante) — and the exact question it settles

x03 holds the relative **top-50** by residual-momentum score (mean(ε)/std(ε)). That book
carries a weak-score tail. A threshold study asked whether requiring stronger names improves
risk-adjusted return, and separated the two possible mechanisms:

- **NOT a cash-timing artifact.** `%cash ≈ 0` at every useful width → the effect is genuine
  CONCENTRATION, not a disguised 2022 cash-dodge (the regime-overlay family we already killed).
- **Absolute score cutoff REJECTED as the mechanism.** It is regime-fragile (score
  distributions drift, so a fixed cutoff swings the held count and forces cash in calm regimes)
  and the winning cutoff is cherry-picked. Relative top-N auto-normalizes — the right lever.
- **The concentration curve is non-monotonic and DISAGREES across windows** (2022–24 favored
  ~top-15, 2009–16 favored ~top-35; BOTH dipped at top-10; top-5 is a lottery-ticket artifact
  with deep drawdowns). The ONLY width both windows agree improves on top-50 is a gentle trim
  to **~top-35** — hence the single pre-committed value 35 (no sweep, no re-tune).

**Settles:** does a modest trim (top-50 → top-35), holding the x03 ranking fixed, HOLD or
improve Sharpe/alpha out-of-sample (→ adopt the concentrated book), or is the ~0.1-Sharpe
in-sample edge a non-robust sweep artifact that fails forward (→ keep x03, the wider/more
diversified default)?

## Construction (one lever: top_n 50 → 35)

Identical to x03 in every other respect: CAPM-residual ranking mean(ε)/std(ε), formation
`[d−252, d−21]`, monthly non-overlapping H=20, equal weight, $5/$10M floor, 10 bps, SPLIT-
adjusted daily bars, SPY market leg. Only `top_n = 35`.

## Pre-registered in-sample diagnostics (already observed, exploratory — NOT the test)

| window | top-50 Sharpe | top-35 Sharpe | top-50 α-t | top-35 α-t |
|---|---|---|---|---|
| 2022–24 (split)      | +1.59 | +1.70 | −0.03 | +0.20 |
| 2009–16 (YF, surv.)  | +1.18 | +1.23 | +1.20 | +1.39 |

Both windows: %cash = 0 at top-35; mild improvement on Sharpe and alpha-t. Magnitude small
(~0.1 Sharpe), optimum regime-unstable — this is the honest prior (LOW conviction it separates).

## Decision rule (pre-committed)

x04 is a CHALLENGER to x03, not a replacement. It is adopted over x03 ONLY if, on the next
fresh sealed read (forward 2026+, ~2027 — both 2025 and 2026-H1 are already spent), it
**(a)** beats x03 on net Sharpe AND **(b)** does not deepen max drawdown materially. If the
sealed read does not separate them, **x03 is the default keeper** (wider book = more
diversification, fewer single-name shocks). No sealed year is spent now; this is the
pre-registration only.

## Status

- 2026-06-21: release created, registered, engine-loads with top_n=35 (registry + tests green).
  In-sample diagnostics above. NOT promoted, NOT sealed-tested. Awaiting forward holdout.
