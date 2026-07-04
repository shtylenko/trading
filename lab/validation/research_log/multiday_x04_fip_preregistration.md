# x04 — Frog-in-the-Pan / Information-Discreteness Momentum — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-18 before scoring. Source: `strategies/xsec_momentum/backlog.md` #5 (the most
ORTHOGONAL remaining ranking idea — path quality, not return level). Companions:
`multiday_x03_residmom_preregistration.md`, `multiday_momentum_findings.md`. (Note: the x04 release
number is now free — the overlapping-construction x04 was REJECTED 2026-06-18 without shipping a
release, `multiday_x04_overlapping_preregistration.md`.) Narrow, pre-committed — do NOT widen.

## Thesis (ex-ante) — and the exact question it settles

Da, Gurun & Warachka (2014), "Frog in the Pan": momentum is stronger and more persistent when the
formation-period information arrived **continuously** (many small same-direction days) rather than in
**discrete jumps** (a few big moves). Investors under-react to a steady drip ("frog in slowly heating
water") but over-react to salient jumps, which then reverse. Their proxy is **information discreteness**:

    ID = sgn(PRET) · ( %neg_days − %pos_days )   over the formation window

where PRET = formation return, %pos/%neg = fraction of daily returns > 0 / < 0. A *smooth* winner
(steady up-drift) has %pos high → ID **low/negative**; a *jumpy* winner (few big up days) has ID
**high/positive**. Low-ID winners continue; high-ID winners fade and carry crash-prone lottery risk.

**This is an orthogonal BEHAVIORAL channel (path, not level)** — distinct from x01 (return level) and
x03 (beta-stripped level). **The question it settles:** does filtering to the smoothest winners add
risk-adjusted value beyond plain/residual momentum on our universe — i.e. is there a path-quality
premium we are leaving on the table, or is it subsumed by the return-level signals?

## Construction (one lever: an ID filter on the momentum ranking)

Everything except the selection rule is identical to x01/x03: top-50 equal weight, monthly
non-overlapping rebalance, H=20, $5/$10M floor, 10 bps cost, SPLIT-adjusted bars, formation window
`[d−252, d−21]` (skip-month). The ONLY change is a double-sort:

1. **Momentum pre-cut:** rank eligible names by `mom_12_1` (raw 11-month return, faithful to the
   paper's PRET) and keep the **top 150** (= 3× TOP_N — the "winners" pool).
2. **ID select:** within those 150, compute ID over the formation window and take the **50 lowest-ID**
   (smoothest) names → the book, equal weight.

Pre-committed: pre-cut = 150, output = 50. No grid over pre-cut size, ID definition, or window.

- **Faithful arm (primary):** ID double-sort on RAW `mom_12_1` (as above) — head-to-head vs **x01**.
- **Residual arm (secondary, descriptive):** same ID double-sort but the momentum pre-cut ranks on
  x03's residual-momentum signal — head-to-head vs **x03**, to see if path-quality adds on top of the
  beta-stripped ranking we already prefer.

Leak-safe: ID and the daily-return counts use only data through `d−21`; nothing forward. Names with
< 126 formation obs (recent IPOs) excluded (same coverage limitation as x03).

## Windows, metrics, sealed discipline

- Windows: clean **2022–2024** (primary, true PIT) + **8yr 2017–2024** (survivorship-flagged
  secondary, the powered series since ID needs 252d of prior daily returns). 2025 hard-sealed out;
  2026 never read.
- Headline metric = **beta-adjusted alpha** (intercept + t of book per-period returns on SPY), per the
  §6b lesson that raw Sharpe/premium can be beta. Also report: annualized Sharpe, realized beta, max
  drawdown, DSR, decile monotonicity of ID, and correlation of the FIP book to x01 and x03.

## Decision bar (pre-committed) — judged on clean data, beta-adjusted

FIP is a real improvement only if, vs its head-to-head base (x01 for the faithful arm) on the SAME
periods, on the clean 2022–2024 window and not contradicted on 8yr:

1. **beta-adjusted alpha t-stat materially exceeds the base's** (x01 was t ≈ +0.31; x03 reached only
   t ≈ +1.13) — ideally |t| > 2 pooled, AND
2. **annualized Sharpe ≥ the base's**, AND
3. **DSR ≥ 0.95** on clean 2022–2024.

Also descriptively: if the FIP book is < ~0.9 correlated with x03 AND beats it, it is a genuinely
additive sleeve (rare — would be the first diversifier this family has found).

## Outcomes (pre-committed)

- **PROMOTE-CANDIDATE** (clears 1–3 on the faithful arm): implement immutable `x04` (FIP double-sort),
  run the swing-engine cross-check, EARMARK a future sealed year (~2027 — both 2025 and 2026-H1 are
  spent; NO sealed data spent now). If the residual arm also clears and is low-corr to x03, note the
  potential x05 = residual+FIP composite.
- **KILL / informative negative** (alpha still insignificant or ≤ base): path quality is subsumed by
  the return-level signals on our universe → record it; the ranking-signal lever is then effectively
  exhausted for the no-new-data ideas, and the honest move is to bank x03 and pause to 2027. Either
  outcome is decision-useful.

## Sealed discipline

In-sample ONLY. Do NOT spend a sealed year on FIP now (none available). Lock the ID definition, the
momentum pre-cut (150), the output size (50), the formation window, and the bar in THIS file; any
change is a new dated spec. Script: `scripts/multiday_fip.py`.

---

## RESULT (2026-06-18) — KILL: path quality is subsumed by return-level momentum

Run `scripts/multiday_fip.py`, clean 2022–2024 (38 non-overlapping periods, 2025 sealed). Per-period
net (10bps), beta-adjusted:

| scheme | annSh | β | α% | t(α) | maxDD | DSR |
|---|---|---|---|---|---|---|
| x01 base (mom top-50) | +0.40 | 1.41 | −0.03 | −0.03 | −25.5% | 0.65 |
| **x03 resid (top-50)** | **+0.77** | 1.06 | **+0.56** | **+0.94** | **−11.6%** | **0.85** |
| fip faithful (mom→low-ID) | +0.44 | 1.07 | −0.02 | −0.03 | −19.6% | 0.67 |
| fip residual (resid→low-ID) | +0.54 | 0.98 | +0.11 | +0.25 | −15.9% | 0.73 |

corr(fip_faithful, x01)=+0.88; corr(fip_residual, x03)=+0.95; corr(fip_faithful, x03)=+0.92.

**Verdict: KILL.** The faithful FIP arm fails every bar: beta-adjusted alpha is ~zero (t −0.03, NOT >
x01's), Sharpe barely above x01 (+0.44 vs +0.40 — within noise), DSR 0.67 ≪ 0.95. The residual FIP arm
is strictly INFERIOR to plain x03 (Sharpe +0.54 < +0.77, alpha +0.11 < +0.56). High correlation to the
bases (+0.88/+0.95) → not a diversifier either. The smoothest-winners filter does buy a shallower
drawdown vs x01 (−25.5%→−19.6%) but surrenders return to get it, and adds nothing over x03 — whose
residualization already trims the crash-prone names FIP was meant to catch. Path quality is subsumed by
the return-level signal on our universe (consistent with the conditioning-grid kill: path/quality
filters fade pooled). **x03 remains the best release; no x04 shipped; no sealed year spent.**

Strategic consequence (per the pre-committed KILL outcome): the no-new-data ranking-signal lever is now
effectively exhausted (residual = best; conditioning, vol-scale, leverage, hedge, FIP, risk-adj-mom-≈-residual
all ≤ it). Remaining ideas are data-gated (quality/earnings, #7/#16) or timing-class (dual-mom-to-cash
#12 — twice-confirmed fragile). **Honest move: bank x03 as the validated deployment form and pause to
the ~2027 sealed year**, unless we invest in the PIT-fundamentals data lift to open the quality/earnings
composite (#7/#16) — the only untested *orthogonal* signal class left.
