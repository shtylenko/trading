# Overnight Premium — Stage-0 / Stage-0.5 findings

Research thread opened 2026-06-16 (the "relax flat-overnight" structural pivot —
option 1 of the post-intraday-momentum plan). Premise: ~all of the long-run equity
risk premium accrues CLOSE-TO-OPEN, the window the strategy_lab mold skips. Measured
OFFLINE on daily bars before any engine work (per EXPLORATION_PLAYBOOK §1b).

Scripts (offline, no engine change):
- `scripts/overnight_premium_baseline.py` — buy at close, sell next open, equal-weight;
  PIT membership; split/glitch guard (drop |overnight| > 35%). Writes per-name-night
  ledgers `validation/_overnight_{etf,stocks}_2022_2025.parquet`.
- `scripts/overnight_regime_probe.py` — conditions the hold on a leak-safe SPY regime
  flag (known at the close) and sweeps round-trip cost (bps). Capital-overlay framing
  (gated-off nights = flat).

## Stage 0 — bare overnight premium, gross (2022–2025)

| | Stocks (liquid_pit, 1.32M name-nights) | ETFs (etf_liquid_pit, 26k) |
|---|---|---|
| 4yr sum (equal-weight nightly) | +16.5% | +18.0% |
| annualized Sharpe | +0.34 | +0.46 |
| 2022 (bear) | **−15.6%** | **−11.5%** |
| 2023 | +4.2% | +3.1% |
| 2024 | +20.7% | +17.9% |
| 2025 | +7.2% | +8.5% |

**First positive Stage-0 in the project**, and the two independent universes (one
survivorship-optimistic, one ~unbiased) agree on both magnitude AND the regime
structure → the effect is real, not a survivorship artifact. The premium is strongly
regime-conditional: deeply negative in the 2022 bear, positive 2023–2025. Every
badly-negative quarter is a known risk-off window (all of 2022, 2023-Q1 SVB,
2025-H1 selloff).

## Stage 0.5 — regime gate + cost sensitivity (the decisive triage)

Holding overnight only when **SPY > its 200-day SMA** (leak-safe trend filter):

| Round-trip cost | ETF spy_above_200d (4yr sum / Sharpe) | Stocks spy_above_200d |
|---|---|---|
| 0 bps (gross) | +26.0% / **+1.03** | +28.9% / **+0.91** |
| **2 bps** | +11.6% / +0.46 | +14.5% / +0.46 |
| 5 bps | −10.0% / −0.40 | −7.1% / −0.22 |
| 10 bps | −46.1% / −1.82 | −43.2% / −1.35 |

- **The regime gate works as theorized**: 200d trend filter ~doubles gross Sharpe
  (0.46→1.03 ETF; 0.34→0.91 stocks) and cuts the 2022 bleed by ~60% (it sits out
  the bear). `spy_above_50d` similar; `spy_5d_up` weaker.
- **The effect is COST-FRAGILE**: tradeable only if round-trip cost ≤ ~2–3 bps.
  Survives ~2 bps at a modest Sharpe ≈ 0.46; dead by 5 bps. 2 bps is plausible for
  the most liquid ETFs (penny spreads) but optimistic for market-on-open fills
  (which pay the opening-auction imbalance); 5–10 bps is realistic for the broad
  equal-weight stock book → the **equal-weight-all stock version is likely dead net**.

## Verdict & what's unexplored

Stage 0 PASSES triage (first real positive, robust, mechanically sensible regime
structure) — BUT the unconditional / equal-weight-all version is cost-fragile. The
**unexplored lever that could change the verdict is cross-sectional SELECTION**:
hold only the *subset* of names with the strongest close-knowable overnight edge
(short-term reversal, size, low price, sector, calendar/turn-of-month, post-earnings
drift), not all names — a larger per-name edge clears costs better. That is exactly
what a full leak-free overnight capture + the trusted search (WF→PBO→DSR→sealed) is
for, with the SPY-regime gate used as a **capital overlay** (the use the synthetic
control showed day-level regime signals are best suited to — see
[[synthetic-positive-control]]).

**Minimum effect size (pre-commit before the search):** the daily-portfolio edge
must clear a realistic round-trip cost — **≥ ~5 bps for stocks, ≥ ~3 bps for liquid
ETFs** — not merely beat zero. A search winner that only works at 0–2 bps is a fail.

## Stage 1–2 — stock cross-sectional capture + search (2026-06-16): KILLED

Built the overnight capture (`scripts/capture_overnight.py` → 1.32M name-nights ×
leak-free close-knowable features; leak verified: future R corr with every feature
< 0.01) and the cost-aware search (`scripts/overnight_search.py`, pre-registered
grid in `overnight_search_spec.md`). Ran the pre-committed matrix:

| Run | WF folds+ | PBO | DSR | verdict |
|---|---|---|---|---|
| 5 bps, no overlay | 0/3 | 0.79 | 0.67 | NO EDGE |
| 5 bps, regime overlay | 0/3 | 0.88 | 0.73 | NO EDGE |
| **0 bps (GROSS)** | **0/3** | **0.60** | 0.96 | **NO EDGE** |

**Decisive: even GROSS (zero cost) the cross-sectional selection fails leave-one-
year-out 0/3 folds, PBO 0.60.** The pooled in-sample looks spectacular (gross IR
+0.74, +650%) but every held-out year flips negative — the selected subset is
in-sample noise that doesn't generalize. So it is NOT a cost problem: cross-
sectional SELECTION over the overnight premium is overfitting. (The Stage-0 top-20
tail diagnostic — rsi2-oversold +7 bps gross — was real but tiny and regime-/year-
unstable; the quintile sort was non-monotonic. Both are consistent with "no stable
cross-sectional alpha".)

**Reconciliation (the real shape of this effect):**
- The equal-weight overnight premium (NO selection) is real but regime-conditional
  and thin (Stage 0).
- The SPY>200d-gated equal-weight version (a CAPITAL OVERLAY, not selection) is the
  genuine robust effect (Stage 0.5) — it ~doubles gross Sharpe and sits out the bear.
- Cross-sectional SELECTION on top adds NOTHING robust — it overfits (WF 0/3, PBO
  0.6–0.88) even gross.
⇒ The tradeable form is a **regime-conditioned equal-weight BETA OVERLAY**, not a
cross-sectional alpha. And the simple version is cost-fragile (≤2–3 bps), so it is
viable on **liquid ETFs**, not the broad stock book.

## Stage 3 — ETF regime overlay validation (2026-06-16): does NOT clear the bar

`scripts/overnight_overlay_validate.py` tested the one robust remnant — equal-weight
ETFs held overnight only when SPY > long SMA — as a fixed rule (no searched params,
so PBO/DSR N/A; the tests are consistency / threshold-robustness / significance /
mechanism).

SPY>200d overlay, net of cost:
| cost | cal sum | cal Sharpe | active-night t | per-year (net) |
|---|---|---|---|---|
| 2 bps | +11.6% | +0.46 | **+0.92** | 2022 −4.8, 2023 −3.9, 2024 +12.8, 2025 +7.5 |
| 3 bps | +4.4% | +0.18 | **+0.35** | 2022 −5.2, 2023 −6.1, 2024 +10.3, 2025 +5.4 |

- ROBUST + mechanism sound: 50d/100d/200d all similar (not a knife-edge); the
  regime-OFF nights (SPY<200d) it avoids average −4.86 bps (t −0.90) — the gate
  genuinely sidesteps the bad nights.
- BUT statistically INSIGNIFICANT (t ≈ 0.9 at 2 bps, 0.35 at 3 bps; need ~2) and
  NOT consistent — 2 of 4 years (2022, 2023) are NEGATIVE net; the positive sum is
  carried by 2024+2025.

**VERDICT — overnight thread CLOSED, negative.** The overnight premium is real but is
thin BETA that does not survive realistic costs into a significant, consistent edge,
and there is NO cross-sectional alpha on top of it (the selection overfits even
gross). The regime overlay is the best form and it is a weak, insignificant
beta-timing rule carried by two good years — below the bar to trade. Per the
pre-committed plan ("PASS at the overlay → build the overnight-hold engine path"),
it did NOT pass, so no engine work is warranted. Artifacts kept: ledgers
`_overnight_{etf,stocks}_2022_2025.parquet`, capture
`_overnight_capture_stocks_2022_2025.parquet`, scripts, `overnight_search_spec.md`.

## Next steps (pending direction)

1. Build the overnight capture: per name-night, close→open R + features knowable AT
   THE CLOSE (leak-safe). Reuse the feature library where applicable; add overnight-
   specific ones (short-term reversal, turn-of-month, days-to/from-earnings, intraday
   return today, close-vs-VWAP, size/price buckets). The Stage-0 ledgers are the seed.
2. Run the canonical search (LOO-WF → PBO → DSR → sealed 2025) on close→open R, with
   a cost charge baked into the objective and the regime gate as an overlay.
3. Only if a candidate clears the cost-aware gates → build the overnight-hold
   execution path in the engine for the cross-check (the one real engine change).

Open strategic fork: ETF-only (cleaner costs, lower capacity) vs stock cross-sectional
(worse costs, but selection upside + capacity) vs both.
