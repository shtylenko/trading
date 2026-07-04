# Response to x03/x04 peer feedback (2026-06-21 / 2026-06-22 round)

Five reviews total: `gemini.md`, `grok.md`, `metaai.md`, and two free-text quant memos
(2026-06-21 batch + a sharper 2026-06-22 memo that challenged the score definition).
This file is the consolidated response and the record of what we tested as a result.

**Bottom line:** across all five reviews, **zero new profitability levers** surfaced, and
**one new robustness confirmation** was earned. The improvement search remains exhausted —
x03 is the validated keeper; x04 (top-35) is the pre-registered, not-yet-promoted challenger
awaiting the forward-sealed 2026 read (~2027).

---

## What the reviewers liked (confirmatory — agreed)

All five converged on the same praise, and we agree it reflects the design intent:

- **Residual (idiosyncratic) momentum is well-engineered momentum**, not a new anomaly —
  it strips the time-varying beta bet that drives momentum crashes (Daniel-Moskowitz),
  consistent with Blitz-Huij-Martens (2011).
- **`mean(ε)/std(ε)` (information ratio) selects for *smooth* idiosyncratic trends**, not
  volatile headline jumps.
- **Skip-month (252-21)** is textbook — avoids short-term reversal.
- **Equal-weight top-N + pure time-based exit, no stops/targets** avoids overfitting.
- **Honest OOS framing** — the family has sealed-OOS evidence (incl. 2025); x03 the *variant*
  does not yet have its own untouched sealed year. Correct framing.
- The **modest** improvement (Sharpe 0.81→0.89, beta 1.45→1.08, DD −36%→−23%) is itself a
  credibility signal — a 2.0 Sharpe claim would be the red flag.

## Challenges — mapped onto our kill-table

| Reviewer challenge | Status | Notes |
|---|---|---|
| **CAPM too simple → FF3/FF5/sector-neutral residual** (all 5) | **KILLED** | FF3/size-factor residual (`multiday_x04_ff3resid_preregistration.md`) was strictly worse — beta went UP 1.06→1.14, alpha t −2.22 (sig. negative). ETF-proxy SMB/HML inject regression noise. CAPM single-factor is the sweet spot. |
| **Turnover / execution drag / cost** (gemini, grok, metaai) | **MEASURED — non-binding** | Turnover ~30–40% one-way, ~3bps/rebalance; net Sharpe ≈ gross, flat to ~$250M AUM. Cost is **not** the leak. |
| **Turnover buffer / rank hysteresis** (gemini, grok) | **KILLED (2026-06-21)** | `multiday_residmom_buffer.py`. GROSS-vs-NET gap only 0.02–0.03 Sharpe; net effect flips sign across windows = regime luck. Hard top-N is correct. |
| **Param sensitivity (top-50 vs other widths)** (grok, 2026-06-22 memo) | **DONE → shipped x04** | `multiday_residmom_absthresh.py`. Concentration is the real lever (not cash-timing). Only window-robust slice = gentle trim to top-35 → shipped **x04** as single-lever challenger, not promoted. |
| **Signal definition: why `mean(ε)/std(ε)` vs Σε / t-stat / Π(1+ε)?** (2026-06-22 memo — NEW) | **ROBUSTNESS PASS (2026-06-22)** | See below — the one genuinely new test this round. |
| **Cadence: does it survive 30/40-day holds?** (2026-06-22 memo) | **NOT fragile** | Folded into the same run — Sharpe holds at H=30/40. |
| **Sector/industry concentration** (2026-06-22 memo, grok) | Diagnostic, not a return lever | Worth producing for the deployment memo; doesn't change the strategy. |
| **Extended risk metrics (Sortino/Ulcer/downside capture/rolling Sharpe)** (2026-06-22 memo) | Reporting completeness | Describes the strategy, doesn't improve it. |
| **Factor attribution study** ("biggest ask", all memos) | Planned, pre-deployment | If excess disappears into the momentum factor, x03 is "cleaner momentum, not new alpha" — which is exactly how we describe it. Lowers deployment risk; no strategy change. |
| **Vol-scaled / crash-aware overlay** (metaai) | **KILLED** | `multiday_x02_volscaled` / defensive sleeve — lowered Sharpe and deepened drawdown (whipsaw; TLT failed 2022). |
| **Survivorship-free data** (all) | Known validation gap | Pre-2022 YF is survivorship-lifted; clean delisting-inclusive rebuild is the right non-research next step. |
| **Sealed OOS for x03 specifically (~2027)** (all) | Planned | Both prior sealed years (2025, 2026-H1) already spent; next clean test is forward-sealed 2026+. |
| **Lookahead / leakage audit** | Confirmed clean | Skip-month + split-adjusted bars + 2025 hard-seal verified. |

---

## The one new test: signal-definition robustness (2026-06-22 memo)

The 2026-06-22 reviewer was the only one to challenge the score definition itself: why the
"residual Sharpe / information ratio" `mean(ε)/std(ε)` rather than cumulative residual return
`Σε`, residual t-stat, or compounded residual alpha `Π(1+ε)−1`? His concern: the denominator
rewards consistency but might (a) discard the strongest *volatile* genuine winners and (b) add
estimation noise via unstable `std(ε)`.

Test: `scripts/multiday_residmom_scoredef.py` — scores all four definitions on the existing
capture ledgers (no new data), reports beta-adjusted alpha + Sharpe + beta + maxDD, the mean
per-period Spearman rank-correlation vs the live score, and repeats at cadence H ∈ {20,30,40}.
2025 hard-sealed.

### Result — design choice CONFIRMED (both ledgers, all 3 cadences)

**2022–2024 (split-adjusted), H=20:**

| score | Sharpe | beta | alpha% | t(α) | maxDD | ρ vs sharpe |
|---|---|---|---|---|---|---|
| **sharpe** (live x03) | **+1.66** | **+1.24** | +0.08 | +0.11 | **−7.9** | — |
| sum   | +1.15 | +1.97 | −0.89 | −0.71 | −18.8 | +0.97 |
| tstat | +1.66 | +1.23 | +0.09 | +0.13 | −7.8 | +1.00 |
| cum   | +1.26 | +1.75 | −0.45 | −0.37 | −15.8 | +0.96 |

**2009–2016 (YF, survivorship-lifted), H=20:**

| score | Sharpe | beta | alpha% | t(α) | maxDD | ρ vs sharpe |
|---|---|---|---|---|---|---|
| **sharpe** (live x03) | **+1.30** | **+0.92** | **+0.79** | **+2.33** | **−14.5** | — |
| sum   | +1.11 | +1.33 | +0.66 | +1.57 | −22.5 | +0.97 |
| tstat | +1.29 | +0.92 | +0.78 | +2.31 | −14.7 | +1.00 |
| cum   | +1.05 | +1.22 | +0.52 | +1.31 | −23.3 | +0.97 |

(H=30 and H=40 reproduce the same ordering in both ledgers — Sharpe holds, `sharpe` stays best.)

**Findings:**

1. **`sharpe` (the live score) is the best of the four in every one of the 6 blocks** —
   lowest beta, shallowest drawdown, highest Sharpe; on 2009–16 it posts the only clearly
   significant beta-adjusted alpha (t +2.33 / +2.00 / +1.43).
2. **`tstat` ≡ `sharpe`** (ρ = 1.00, identical book — n_obs is near-constant across the
   universe). The most defensible alternative gives the same answer → robust.
3. **Dropping the denominator (`sum`, `cum`) strictly hurts** — beta jumps (0.92→1.33,
   1.24→1.97) and drawdown deepens (−14.5→−23, −7.9→−18.8). The reviewer's worry is backwards:
   the denominator isn't discarding winners, it's screening out the high-beta vol names —
   which is the entire purpose of x03.
4. **Cadence is not fragile** — the edge survives H=30/40; no knife-edge at 20 days.

**Honest caveat (unchanged):** on the clean 2022–24 data the beta-adjusted *alpha* is ~0 even
for the winning form — x03 is better-risk-engineered *beta* (lower beta, shallower DD, higher
Sharpe), not a fat new alpha source. The 2009–16 t=2.3 alpha is on survivorship-lifted data and
is discounted; the *relative* ranking across definitions is unaffected by survivorship.

---

## Net conclusion

The five reviews are strong, convergent, and confirm the design choices and the stated
limitations. For the actual question — *improve profitability* — the round produced **no new
levers**: everything raised is already killed, already measured, already done, or is validation
rigor rather than a return lever. The single new test (signal-definition robustness) **raised**
confidence rather than denting it.

Remaining high-value work is **non-research**: factor-attribution write-up and a
survivorship-free (delisting-inclusive) validation rebuild before deploying capital, then the
forward-sealed 2026 read (~2027) as x03's own clean holdout.
