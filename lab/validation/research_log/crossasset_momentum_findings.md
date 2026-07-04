# Cross-asset momentum — Stage-0 findings (2026-06-18)

After the single-stock long-only box was exhausted (x03 = ceiling; every intra-equity signal collapses
to beta), explored 3 genuinely-new long-only directions. **Cross-asset momentum is the first real
diversifier candidate the project has produced.** Scripts: `crossasset_momentum_triage.py`,
`seasonality_triage.py`.

## The 3-way comparison

| Direction | Verdict | Evidence |
|---|---|---|
| **Cross-asset momentum** (GTAA/dual-mom) | **Stage-0 PASS** | see below |
| Seasonality (TOM, Halloween) | **FAIL** | all overlays Sharpe < SPY buy&hold (+0.34/+0.63 vs +0.86); fragile timing class |
| Lead-lag / customer momentum | **DATA-GATED** | needs firm-link / BEA input-output data we don't have; not testable today |

## Cross-asset momentum — the setup

Rank a fixed basket of 13 asset-class ETFs (equity: SPY/QQQ/IWM/EFA/EEM; bonds: TLT/IEF/LQD/HYG/AGG;
real: GLD/DBC/VNQ) by 12-1 TOTAL-RETURN momentum (adjustment="all" — dividends matter for bonds/REITs);
hold top-N equal weight; absolute-momentum filter (only positive-12mo names; empty slots → BIL cash).
Monthly (H=21) rebalance. **Fixed ETF basket = NO survivorship bias** (unlike the stock work).
In-sample 2017–2024; **2025+ reserved as a clean future sealed test (NOT touched).**

## Result (2017–2024, 94 monthly rebalances)

| strategy | annSh | CAGR | maxDD | **βSPY** |
|---|---|---|---|---|
| cross-asset mom (top5) | +0.97 | +9.6% | −13.6% | **+0.46** |
| SPY buy&hold | +1.02 | +15.2% | −21.4% | +1.00 |
| 60/40 SPY/AGG | +1.01 | +9.8% | −18.7% | +0.63 |
| equal-weight all ETFs | +0.79 | +7.2% | −18.9% | +0.55 |

- **βSPY +0.46** — genuinely LOW / time-varying, NOT the +1.1–1.6 every equity signal collapsed to.
  This is the prize: a long-only book with ~half the market exposure.
- **2022 bear test:** −12.0% vs SPY −19.3% (rotated to soften; not positive because 2022 was the rare
  stocks-AND-bonds-down regime, but still cut the loss ~40%).
- **Robust across top-N** (Sharpe 0.79–1.03 for N=3/4/5/6/8; βSPY 0.42–0.46 throughout) — not a
  knife-edge overfit.
- NOT the killed defensive sleeve: that was a forced binary SPY<200d→TLT/GLD switch (TLT failed 2022);
  this is momentum-RANKED, so it never holds a negative-momentum asset (it wouldn't have held TLT in
  2022 — TLT had negative momentum).
- Honest caveats: lower CAGR than SPY; lags sharp bull recoveries (2023 +8% vs +27% — slow re-entry
  after a bear); in-sample window is bull-heavy 2017–2024 so the +1.0 Sharpe is not proof.

## ADDITIVITY TEST (2026-06-18) — NOT additive as-is; corr too high

`scripts/multiday_crossasset_additivity.py`, both books on the SAME rebalance dates (H=21, aligned
forward windows). 2025 EXCLUDED (cross-asset's reserved seal).

| window | corr(x03,CA) | x03 Sharpe/DD | 50/50 blend Sharpe/DD/β |
|---|---|---|---|
| clean 2022–24 (36 per) | **+0.76** | +0.70 / −14.8% | +0.59 / −11.5% / 0.57 |
| 2017–24 (83 per) | **+0.71** | +0.86 / −27.4% | +0.84 / −19.8% / 0.71 |

**Verdict: NOT additive by the pre-registered bar (corr<0.5 AND blend Sharpe ≥ x03 AND DD shallower).**
Both windows: corr +0.71–0.76 (the same level that killed quality/value). On clean 2022–24 the blend
LOWERS Sharpe (+0.70→+0.59); on 2017–24 it's flat (+0.86→+0.84) but DD improves a lot (−27→−20). So
it's a RISK reducer (DD −28%, β 0.96→0.71 at ~flat Sharpe) but NOT a Sharpe-additive diversifier.

**Why corr is high:** cross-asset momentum HOLDS EQUITY ETFs (SPY/QQQ/…) in equity bulls → it's
secretly long-equity right when x03 is. Its standalone +0.97 (2017–24) was bull-period-inflated (rode
equities 2017–21); on clean 2022–24 it's only +0.28. The diversification only fires in the rare
non-equity-trending regimes.

## NON-EQUITY-ONLY sleeve (2026-06-18) — structural fix WORKED but rotation adds nothing over bonds

`--no-equity` (bonds/gold/commodities/REITs only, top-3). Standalone: βSPY +0.13, Sharpe +0.57, 2022
−4.4% vs SPY −19.3% — a genuine low-beta sleeve. Correlation to x03 dropped to **+0.36 (8yr) / +0.47
(clean 2022–24)** — first candidate below the 0.5 bar. Blend cuts drawdown a lot (−27→−15 8yr) and beta
(0.96→0.55) at ~flat Sharpe (8yr +1%, clean −7%). Per-year: helps only in bears (2018/2022), gives up
big return in up years (2020 −38pp, 2024 −16pp) — a DAMPENER (cuts return, cuts vol more).

### DECISIVE benchmark — does the momentum ROTATION beat "just hold bonds"? NO.

50/50 blends with x03 (8yr 2017–24): | sleeve | blend Sharpe | blend maxDD | corr |
- **cross-asset momentum: +0.87 / −15.4% / 0.36**
- static AGG buy&hold: **+0.87 / −18.7% / 0.11**
- static EW non-equity (no momentum): **+0.90 / −17.7% / 0.36**

On Sharpe the rotation TIES static bonds (+0.87) and LOSES to a static EW non-equity basket (+0.90); it
only wins modestly on drawdown, and static AGG is actually LESS correlated to x03 (0.11). **The
diversification comes from HOLDING UNCORRELATED ASSETS, not from the momentum machinery.** Cross-asset
momentum collapses to "just hold bonds" — the campaign's recurring pattern.

## VERDICT — cross-asset momentum CLOSED; but a real deployment takeaway

- **Cross-asset momentum as a STRATEGY: REJECTED.** The rotation/abs-filter/ranking adds nothing over a
  static bond slice. Not worth a sealed test or the complexity.
- **USABLE DEPLOYMENT TAKEAWAY (not alpha, but real):** blending x03 with a STATIC bond/non-equity
  sleeve cuts drawdown −27%→−18% and beta 0.96→0.55 at flat-to-better Sharpe. Standard diversification
  — when x03 is deployed, hold it alongside bonds. (This is portfolio construction, not a new edge.)
- Seasonality FAILED; lead-lag DATA-GATED. The "explore beyond x03" campaign is exhausted: x03 + a
  static bond sleeve for risk management is the end state. No new alpha exists within this mandate.
