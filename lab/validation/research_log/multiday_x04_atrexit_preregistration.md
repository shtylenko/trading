# x04 — ATR / Chandelier Trailing Exit on x03 — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before scoring. Source: `strategies/xsec_momentum/backlog.md` #13 — the only
untested *exit* lever (x03 is pure 20-day time exit). Companions:
`multiday_x03_residmom_preregistration.md`. **Narrow, pre-committed — do NOT widen the grid.**

## Thesis (ex-ante) — and the exact question it settles

x03 holds the top-50 residual-momentum names for a fixed H=20 days and NEVER cuts a losing hold
early. A chandelier exit (Le Beau) trails a stop a multiple of ATR below the position's running peak,
exiting crash-prone names mid-hold. The keyword report found ATR/chandelier exits beat fixed-% stops
on risk-adjusted return across multiple practitioner tests. **This is a RISK lever, not an alpha
lever** — the accumulated evidence says x03 is the alpha ceiling; the open question is narrowly
whether an adaptive trailing exit improves x03's DEPLOYABLE risk profile (shallower drawdown) WITHOUT
surrendering return.

**Settles:** does a chandelier exit on x03 cut drawdown while holding Sharpe ≥ base — i.e. should the
deployed x03 use a trailing exit, or is the pure time exit already optimal?

## Construction (one lever: add a chandelier stop to x03's hold)

Selection unchanged from x03: top-50 by CAPM-residual momentum, monthly non-overlapping, H=20,
$5/$10M floor, 10 bps round-trip, SPLIT-adjusted bars. The ONLY change is the exit:

- For each held name, walk the H=20 daily closes after entry. Track `peak` = max close since entry
  (incl. entry). **Chandelier stop level = peak − k · ATR_proxy(t).**
- **ATR_proxy** = 14-day rolling mean of |close_t − close_{t−1}| (a CLOSE-BASED proxy; our capture
  has no high/low, so true ATR isn't available — documented approximation, computed leak-safe from
  closes through day t).
- Exit on the FIRST day close < stop, at that day's close → the name's realized period return =
  `exit_close/entry_close − 1`; capital then sits in CASH (0 return) to end of the H-window (no mid-
  period replacement — faithful to non-overlapping construction). If never triggered, realized =
  full-hold return (= fwd_20).
- **Cost is unchanged** vs base: still one round trip per name per period (the stop only moves the
  exit earlier; no re-entry) → no extra cost term.
- **Grid (pre-committed, narrow):** k = 3.0 (primary, chandelier standard) + k = 2.5 (secondary,
  sensitivity). ATR window fixed at 14. No other values.

## Windows, metrics, decision bar (pre-committed)

- Windows: clean **2022–2024** (primary) + **8yr 2017–2024** (secondary, survivorship-flagged).
  2025 sealed out.
- Metrics vs base x03 on the SAME periods: annualized Sharpe, **max drawdown**, beta-adjusted alpha
  (intercept + t vs SPY), DSR, and % of name-holds stopped early (to confirm the exit actually fires).
- **ADOPT the chandelier exit into deployed x03 iff** (on clean 2022–24, not contradicted on 8yr):
  1. **max drawdown meaningfully shallower** (≥ 10% relative reduction vs base x03), AND
  2. **annualized Sharpe ≥ base x03** (no return give-up — must be Sharpe-neutral-or-better; a lower-
     DD-but-lower-Sharpe result does NOT qualify, since x03's DD is already structurally modest), AND
  3. **beta-adjusted alpha not worse than base** (the exit must not eat the edge).
- k=2.5 must not be required to beat k=3.0 to claim success — if only the tighter stop "works" via
  one window it's likely noise; the primary is k=3.0.

## Outcomes (pre-committed)

- **ADOPT** (clears 1–3): the deployed x03 uses the chandelier exit; fold into the swing release as an
  exit rule. No sealed year spent (exit overlay on an in-sample-validated ranking; in-sample test).
- **REJECT** (Sharpe drops, or DD not materially cut): pure 20-day time exit is optimal for x03;
  record that the trailing exit adds nothing (whipsaw cost ≈ crash-avoidance benefit on this book) →
  the x03 exit question is settled, productionize x03 as-is.

## Sealed discipline

In-sample ONLY. Lock the stop rule, ATR proxy, k-grid {3.0, 2.5}, window 14, and the bar in THIS
file; any change is a new dated spec. Script: `scripts/multiday_atrexit.py`.

---

## RESULT (2026-06-18) — REJECT: trailing stops destroy momentum (pure time exit is optimal)

`scripts/multiday_atrexit.py`. Both k=3.0 and k=2.5 fail catastrophically, both windows:

| window | scheme | annSh | α% | maxDD | % stopped |
|---|---|---|---|---|---|
| clean 2022–24 | x03 base (time exit) | **+0.71** | +0.47 | **−11.4%** | — |
| clean 2022–24 | x03 + chand k=3.0 | −0.36 | −0.73 | −27.0% | 84% |
| 8yr 2017–24 | x03 base | **+0.95** | +0.75 | **−24.5%** | — |
| 8yr 2017–24 | x03 + chand k=3.0 | +0.32 | −0.16 | −37.5% | 83% |

The chandelier exit not only fails the DD bar — it makes drawdown DEEPER (−11.4%→−27.0% clean) AND
craters Sharpe (+0.71→−0.36) and alpha (+0.47%→−0.73%). 83–84% of holds stop out. **Mechanism:**
momentum names are volatile and whipsaw — the trailing stop sells them at local bottoms just before
they continue; and because a vol spike hits the whole book at once, stop-outs are CORRELATED, so you
systematically sell low across most of the book simultaneously, DEEPENING the drawdown rather than
cutting it. This is the textbook "trailing stops kill momentum" result: **momentum requires sitting
through volatility.** Verdict: **REJECT — pure 20-day time exit is optimal for x03.**

Caveat (does not change the verdict): ATR_proxy = close-based mean|Δclose| understates true (high/low)
ATR, so a real-ATR chandelier might stop somewhat less often — but the failure is so severe (Sharpe
−0.36, DD doubled, 84% stopped) that a looser true-ATR band would not flip it; the direction is the
robust, literature-consistent result. The x03 EXIT question is now SETTLED.
