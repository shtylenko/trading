# Idea-solicitation synthesis — x04 residual momentum (2026-06-23)

Four external AIs (ChatGPT, Gemini, Grok, Meta) returned ~40 ideas against the x04 brief.
Below: deduped into 9 themes, scored by **cross-model convergence** (independent
re-discovery = signal of obviousness/robustness), **cost**, and **overlap-risk vs the
kill-table**. The point of this doc is to feed a *single pre-registered Stage-0 triage*, not
to test 40 things.

## Meta-finding (the most useful takeaway)

**Every model independently refused to propose "another factor."** With the kill-ledger in
front of them, all four converged on the same two directions:
1. **Purify the residual signal we already have** — clean the β estimate, reward *steady*
   idiosyncratic drift, penalize downside/lottery tails. (Pure ranking change, price+SPY only.)
2. **Apply a *secondary* fundamental veto AFTER momentum selection** — issuance / accruals /
   asset-growth as an exclusion on already-chosen winners, NOT as a primary signal.

That convergence is itself evidence: the genuine frontier here is **signal purification +
event/quality vetoes**, not new signals. It also validates the prompt — the "closest
dead-end it avoids" field forced every idea to differentiate from value/quality/FF3/path-quality,
and none re-proposed a killed primary factor.

## Theme table (priority order)

| # | Theme | Models | Cheapest canonical test | Data | Overlap-risk vs kills | Priority |
|---|---|---|---|---|---|---|
| A | **β-estimate cleaning** (stale/noisy β leaks the 1.08) | **4/4** | split-half β-stability filter: drop top-20% unstable within top-70 IR, take 35 | price+SPY | LOW (cleans the existing CAPM, adds no factor) | **P0** |
| B | **Fundamental veto on momentum winners** (issuance / accruals / asset-growth) | **4/4** | within top-70 IR, exclude >5% 12m net issuers (and/or top-quintile accruals), take 35 | PIT fundamentals (have) | LOW-MED (distinct anomalies, applied as veto not primary) | **P0** |
| C | **Residual persistence / consistency** (reward steady drift, not one jump) | **4/4** | rank by `min(IR_firsthalf, IR_secondhalf)` instead of full-window IR | price+SPY | **MED** (residual-space twist on the KILLED path-quality/FIP — test ONE, not the cluster) | P1 |
| D | **Downside-asymmetry residual** (semivariance / skew / down-day IR) | 3/4 | replace std(ε) denom with downside semi-deviation (Sortino-style) | price+SPY | MED (could collapse to low-vol tilt — watch) | P1 |
| E | **Hidden theme / crowding de-correlation** (CAPM removes SPY, not shared themes) | 2-3/4 | replace SPY with EW-liquid-universe factor; OR cluster-cap the book at ≤25%/cluster | price(+SPY) | LOW-MED (single-factor swap ≠ FF3; cluster-cap ≠ top-N sweep) | P1 |
| F | **Lottery / MAX / attention veto** (exclude squeeze & lottery names) | 2/4 | exclude top-decile by single-day MAX return (or idiosyncratic-skew) before ranking | price+volume | MED (distinct from path-quality, but near theme D) | P2 |
| G | **Cross-sectional β/raw-mom purification** (strip the part of IR tied to beta & raw mom) | 2/4 | regress IR on {raw 12-1, β, vol, logADV}; rank residual `u_i` | price+SPY | **MED-HIGH** (risk: strips the actual edge — FF3 "extra regression = noise" lesson) | P2 |
| H | **Capital-gains-overhang / disposition gate** (buy only where holders sit on gains) | 1/4 | gate out names with price < 252d volume-weighted cost basis, then rank IR | price+volume | LOW (novel, distinct from 52w-high) | P2 (speculative) |
| I | **Seasonality / regime-concentration overlays** | 1/4 | — | — | **HIGH — these are the killed classes in disguise** | **SKIP** |

## What to actually do (recommended Stage-0 plan)

These are **selection/ranking changes**, so each is free to triage in-sample (clean 2022–24
+ 2009–16) but a survivor still costs the ~2027 sealed year. So: **batch, pre-register, pick
≤2 survivors, then spend the year once.** Two sprints:

- **Sprint 1 (P0, zero/owned data, highest convergence, directly targets the β=1.08 weakness):**
  - **A — β-stability cleaning.** All 4 models; the single most-convergent idea. Canonical
    test: split-window β stability (or se(β)) filter within the top-IR pool. Robust-regression
    (Theil-Sen) and Kalman β are the same theme — test the *cheap* version (split-half) first;
    only escalate to Kalman if the cheap one shows signal.
  - **B — fundamental veto.** Also 4/4. The two most-differentiated, most-convergent sub-vetoes
    are **net-share-issuance** (4 models) and **accruals/Sloan** (3 models) — both distinct from
    the KILLED value/quality/earnings-momentum *primary* signals, and the PIT-EDGAR lift that
    makes them testable is already done. Asset-growth is a weaker cousin; fold it in as a third
    arm, not its own sprint.

- **Sprint 2 (P1, only if Sprint 1 is encouraging):** one clean test each of **C**
  (`min(IR1,IR2)`), **D** (downside semivariance denom), **E** (EW-universe factor swap).

## Guardrails (this is where these usually die — heed the backlog's own lessons)

1. **Multiple-testing / forking paths.** 40 ideas → ~9 themes → ≤2 survivors. Pre-register the
   batch and the decision rule BEFORE running; do NOT post-hoc cherry-pick the best filter
   (this is exactly the per-fold-argmax / d14-screen artifact the backlog already booked).
2. **Judge on beta-adjusted alpha, not raw decile/return spread.** Every fundamental sleeve so
   far (value, GP, NI-YoY) looked good on raw spreads and died on the beta-adjusted bar
   (the §6b "Stage-0 mirage" lesson). Apply Bar A from the start.
3. **The recurring kill-condition all four models named themselves:** a "filter" that improves
   drawdown only by *collapsing return* (a disguised low-vol tilt) is a FAIL, not a win — it
   gives back the same risk-improvement that killed ATR-exit/leverage/vol-target. Require the
   drawdown/Sharpe gain at **roughly flat gross return**.
4. **Theme C overlap.** Path-quality/FIP was killed because residualization *already* trims the
   jumpy names; the residual-space persistence twist is genuinely untested but plausibly
   redundant. Test it as a falsification ("is there anything LEFT to smooth in the residual?"),
   not with optimism — one canonical form, kill on corr >0.97 to baseline + no crash-month gain.

## Per-theme source map (for the backlog kill/triage entries)

- **A:** ChatGPT#5 (β-instability+downside-β), Gemini#5 (Kalman), Grok#5 (se β stability),
  Grok#6 (Theil-Sen), Meta#2 (split-half β-stability).
- **B:** ChatGPT#7/#8 (accel/accounting veto), Gemini#7 (asset-growth+issuance), Gemini#8
  (accruals), Grok#8 (asset-growth gate), Meta#3 (issuance purge), Meta#7 (Sloan accruals),
  Meta#10 (margin Δ), ChatGPT#6 & Meta#6 (filing-reaction/earnings-jump purity — a price×event
  variant, cheaper than full fundamentals).
- **C:** Grok#1 (EWMA recency), Grok#2 (multi-horizon ensemble), Grok#7 & Meta#8 (residual
  AR(1)), Meta#1 (split-half min-IR), Meta#5 (vol compression), Meta#9 (residual MDD),
  ChatGPT#10 (signal-age/lifecycle).
- **D:** Gemini#2 (downside semivariance), ChatGPT#9 (residual CVaR), Meta#4 (residual skew),
  ChatGPT#1 (down-day residual IR).
- **E:** Grok#3 (EW-universe factor), Grok#4 (low-R² purity), ChatGPT#4 (residual-cluster
  de-crowding), ChatGPT#12 (peer-cluster residualization).
- **F:** Gemini#3 (idiosyncratic asymmetry), Gemini#4 (MAX penalty), ChatGPT#11 (abnormal-volume).
- **G:** ChatGPT#3 (cross-sectional purification), Gemini#1 (beta-neutral double-residual/BAB).
- **H:** Gemini#6 (capital-gains-overhang).
- **I (SKIP):** Gemini#9 (momentum-gap → widen 35→75 = concentration sweep + sizing overlay,
  killed-adjacent), Gemini#10 (January seasonality = timing class, fragile).
