# xsec_momentum (`x`) — research backlog

Running research log for the cross-sectional momentum family. **Read this before proposing new
work.** Companions: `validation/research_log/multiday_momentum_findings.md` (full evidence), the
`validation/research_log/multiday_*_preregistration.md` specs, peer reviews in
`peer-review/2026-06-16-x-feedback/`. Discipline: every new candidate goes through the pipeline
(broad capture → pre-registered narrow test → LOO-WF on clean 2022+ PIT → PBO → DSR ≥ 0.95 →
one-shot sealed year). New ranking signals each need their OWN sealed-year spend — do NOT spend
2026-H1 (earmarked/being spent on the base rule) on them.

## Current state

- **x01** = base 12-1 cross-sectional momentum (top-50 EW, monthly, H=20, $5/$10M floor),
  UNCONDITIONED. Validated Stage 0→6: 8yr in-sample DSR 0.99 (survivorship-lifted pre-2022),
  clean 2022–2024 base-EW Sharpe ~0.50 / DSR 0.76, sealed-OOS 2025 PASS (+3.98%/period, Sharpe
  +1.08, premium +2.78%), real-engine cross-check reproduces. 2026-H1 early partial confirmation
  pending (`multiday_2026h1_preregistration.md`).
- **Honest characterization:** a modest, BETA-HEAVY momentum tilt (book β≈1.4 to SPY, corr ~0.70).
  Realistic Sharpe ~0.7–0.9 (lower after realistic costs), max DD −25% to −38%, CAGR ~11–25%
  (2025 +58% was a tail year). Intrinsic momentum-crash risk.
- **META-FINDING (2026-06-18, after exhaustive search):** on THIS long-only liquid universe ($5/$10M-ADV
  floor), EVERY cross-sectional signal tested beyond residual momentum — price-path (FIP), quality
  (gross profitability), value (B/M, E/P) — COLLAPSES TO A HIGH-BETA TILT (β 1.1–1.6, α≈0, corr 0.6–0.9
  to the momentum book, NOT additive). The liquid universe is the binding constraint: the value/quality
  spreads load on distressed/cyclical/high-multiple-growth high-beta names, not the defensive academic
  factor. **x03 (residual momentum) is the CEILING; no long-only diversifier exists for it here.** Also
  settled: construction (overlapping), sizing (leverage, vol-target), EXITS (ATR/chandelier KILLED
  2026-06-18 — trailing stops destroy momentum, pure time exit optimal), timing (defensive sleeve) all
  fail. FF3/size-residual momentum (the LAST untested idea) KILLED 2026-06-18 — strictly worse than
  x03, β went UP not down, α t −2.22; CAPM single-factor is the sweet spot. **THE BACKLOG IS NOW
  EXHAUSTED — every ranking, exit, sizing, construction, hedge, diversifier, and universe idea has been
  tested with earned evidence. x03 (CAPM residual momentum, top-50 EW, monthly non-overlapping, H=20,
  pure time exit, 1.0×) is the FULLY-MAPPED optimum.** Honest stance: bank x03. The only paths to a
  genuinely new edge require a MANDATE CHANGE (shorting — blocked; or a different/illiquid universe —
  data says no), not another variant. Next move is PRODUCTIONIZE x03, not more search.
  **QUALIFIER (2026-06-23):** the "exhausted" claim covered *new ranking signals, overlays, and
  universe tweaks*. A 4-AI idea sweep (see the dated section below) surfaced ONE class the prior
  search did NOT cover: **purifying the EXISTING CAPM residual** (β-estimate cleaning, downside-asymmetry
  scoring, residual de-crowding) + **secondary fundamental VETOES on already-selected momentum winners**
  (net-share-issuance, accruals) — distinct from the killed *primary* fundamental sleeves. These are
  cheap, in-mandate, and aim at the β≈1.08 leak. NOT promising enough to delay productionizing x03, but
  a legitimate fresh batch — backlog is "exhausted *of new factors*," not of residual-purification.
- **OPTION-1 (small-cap universe) CHECKED & CLOSED (2026-06-18, `experiments/multiday/multiday_liquidity_tiers.py`).**
  Liquidity-tier gradient (3 tiers by 20d $vol, beta-adjusted top-50/tier, 2022–24): the premise
  "factors strengthen toward smaller/less-liquid names" is FALSIFIED. value α flat ≈−0.47 in EVERY tier
  (β~1.2); quality α negative everywhere (worst, t−2.08, in the small tier); momentum α DECAYS +0.70
  (liquid $328M) → −0.65 (small $40M) — our edge is a LIQUID-name phenomenon. Asymmetry seals it:
  survivorship bias INFLATES the small tier (only survivors present), so clean survivorship-free
  small-cap data would make these WORSE, not better → NOT worth a paid micro-cap data source. (Caveat:
  floor ~$10–25M ADV; tier 2 is mid-cap not micro — but no upturn is starting, and micro-caps are where
  survivorship/cost are most lethal.) Genuine new edge would require shorting (blocked) or a wholly
  different mandate, not a universe tweak within reach.

## Tried & KILLED (do not repeat without a new angle)

| Idea | Verdict | Evidence |
|---|---|---|
| Conditioning grid (k≤2: liquidity/price/calm_vol/confirm/not-overextended/mom-floor/SPY-regime) | DEAD | ≈base on 8yr (PBO 0.92); calm_vol looked good 3yr but collapsed pooled. `multiday_search_spec.md` |
| Vol-scaling x02 (V1 inverse-vol weights, V2 target-vol exposure) | KILLED | 8yr base 0.88 ≈ V1 0.85 ≈ V2 0.89. `multiday_x02_volscaled_preregistration.md`. **Caveat: V2 used mean-of-name-vols, NOT strategy's own realized vol — see backlog #4.** |
| Leverage / sizing | KILLED | At Sharpe ~0.5 leverage REDUCES CAGR (vol drag); at ~0.9 drawdowns go unholdable (−73% at 2×). Run ~1.0×. `multiday_leverage.py` |
| Beta-hedge (synthetic short via inverse-ETF/puts), static β∈{0,.5,1,1.3} | KILLED | Hedging monotonically lowers Sharpe (8yr 0.88→0.45); residual alpha thin. Beta is load-bearing. `multiday_betahedge_preregistration.md` |
| H=5 horizon | DEAD | Fails 2022 even gross; only H=20 works |
| Long-only diversifiers (low-vol, st-reversal, near-low, short-mom) | DEAD | All +corr with momentum (shared beta); none smooth the book |
| Index-level short-horizon mean-reversion ETF sleeve (IBS / RSI-2 dip-buy, 200d-uptrend filter, 12 liquid ETFs) | KILLED (2026-06-22) | `experiments/meanrev/etf_meanrev_triage.py` + `experiments/meanrev/etf_meanrev_bearcheck.py`. From the Kimi research bundles — the ONE untested non-momentum direction (prior MR kill was cross-sectional STOCK setups; this is index dip-buying, a different mechanism). IBS<0.2/0.3: +ret but **corr +0.53/0.57** to x03 → shared beta, blend Sharpe DROPS = another beta sleeve. RSI2<5 LOOKED like a pass on the triage (2023-24 only, ledger formation eats 2022): corr −0.02, blend Sharpe 1.66→1.78, maxDD −7.9→−4.2 → I wrongly called it CONDITIONAL PASS. The pre-registered **2022 bear-window check KILLED it**: clean full warmup (yfinance --force; Alpaca SIP is history-gated + the first bearcheck was WARMUP-CONTAMINATED, suppressing 2022 entries and hiding the knife) → RSI2<5 **2022 −3.1% Sharpe −1.26**, full-cycle Sharpe **NEGATIVE −0.15** (rsi2<10: −0.00); trades 135/258 so NOT a sample kill — real falling-knife economics (dip-buying gets run over as the bear opens). The triage's smoother-look was a pure BULL-WINDOW artifact. LESSON: (a) never read a 2-yr no-bear window as a diversifier verdict; (b) the warmup-contamination guard (`df.index < cal[0]` count <SMA_N) earned its keep — caught a flattering false positive twice. **META-FINDING STANDS with earned evidence: even index-level short-horizon mean reversion fails on this universe — no deployable long-only diversifier for x03 exists.** |
| Defensive-sleeve rotation (SPY<200d → cash/TLT/GLD) | DEAD | Every rotation LOWERED Sharpe AND deepened DD (whipsaw; TLT failed 2022) |
| 52-week-high proximity (`prox_52w`, George-Hwang) | DEAD at Stage 0 | decile monotonicity +0.07 (disappointing); likely subsumed by 12-1 |
| Long/short (D10–D1 Sharpe 0.71–0.89, higher ceiling) | BLOCKED | User cannot short |
| Frog-in-the-Pan / information-discreteness (path quality, top-150 mom → 50 lowest-ID) | KILLED (2026-06-18) | `multiday_x04_fip_preregistration.md`. Clean 2022–24: faithful arm Sharpe +0.44≈x01 +0.40 but α t −0.03, DSR 0.67≪0.95; residual arm +0.54 < x03 +0.77 (strictly worse). corr +0.88/+0.95 to bases (not a diversifier). Path quality SUBSUMED by return-level momentum; x03's residualization already trims the crash-prone names FIP targets. x03 remains best |
| FF3/size-factor residual momentum (SPY+IWM−SPY+IWD−IWF) | KILLED (2026-06-18) | `multiday_x04_ff3resid_preregistration.md`. Strictly WORSE than x03 (CAPM) on every axis + FAILED its own goal: β went UP 1.06→1.14 (not down), Sharpe +0.77→−0.10, α +0.56→−0.91 (t −2.22 sig. negative), DSR 0.75→0.21. ETF-proxy SMB/HML inject regression noise that corrupts the residual signal. CAPM single-factor is the sweet spot — x03 ranking question CLOSED |
| ATR/chandelier trailing exit on x03 (k=3.0 & 2.5) | KILLED (2026-06-18) | `multiday_x04_atrexit_preregistration.md`. DESTROYS x03: Sharpe +0.71→−0.36, maxDD −11.4%→−27.0% (DEEPER), alpha +0.47→−0.73, 84% of holds stopped. Trailing stops whipsaw momentum names (sell at local bottoms pre-recovery) + CORRELATED stop-outs in vol spikes deepen DD. "Momentum requires sitting through volatility." Pure 20-day TIME EXIT is optimal — x03 exit question SETTLED |
| Value sleeve (book-to-market / earnings-yield, PIT via EDGAR) | KILLED (2026-06-18) | `multiday_x04_value_preregistration.md`. The textbook momentum complement, FALSIFIED on our universe: 2022-positivity check FAILED (B/M −1.04%, E/P −0.23% in 2022 — value's banner year), β 1.36–1.58 (HIGHER than momentum), α zero-to-negative, DSR 0.42/0.62. corr to x03 +0.57–0.63 (expected NEGATIVE), blend Sharpe < x03 everywhere. On a liquid $10M-ADV universe, high-B/M = distressed/cyclical high-beta junk, NOT defensive HML value. Same collapse-to-beta as quality+FIP |
| Overlapping-portfolio construction (Jegadeesh-Titman, x04, daily K=20) | KILLED (2026-06-18) | `multiday_x04_overlapping_preregistration.md`. Gross Sharpe +0.78→**+0.73** (slightly HURTS) — residual mom already low-turnover (39%/roll) + H=20 short → reconstitution-date luck negligible, and overlap carries stale sleeves. Capacity win real (peak partic. 45.9%→2.3% @ $250M) but MOOT: non-overlap not cost-stressed at realistic AUM under spread+√impact (net Sharpe flat to $250M). Construction is NOT the leak; the ranking signal is the lever. Corrects the "95% turnover cut" claim — capital turnover/unit-time is identical |
| Turnover buffer / rank hysteresis (keep holding until rank falls past band B) | KILLED (2026-06-21) | `experiments/multiday/multiday_residmom_buffer.py`. Peer-suggested (Gemini, Grok) to cut churn. CONFIRMS cost is not the leak: GROSS-vs-NET gap only 0.02–0.03 Sharpe at hard-50/40%-turnover, widening band to 100 (turnover→21%) saves ~0.01 more = negligible. Net effect is just the GROSS wobble of holding staler names, and it FLIPS sign across windows (2022–24 band-65 NETsh 1.64→1.82 *gross-driven*; 2009–16 1.22→1.15, HURTS). Same non-robust regime-luck as the concentration sweep. x03 hard top-N is correct |
| Signal-DEFINITION robustness — mean(ε)/std(ε) vs Σε vs t-stat vs Π(1+ε) (+ cadence H=20/30/40) | ROBUSTNESS PASS (2026-06-22), design choice CONFIRMED | `experiments/multiday/multiday_residmom_scoredef.py`. Peer-suggested (2026-06-22 reviewer): is the live "information-ratio" score arbitrary? Answer NO — `sharpe`(=live) is best of 4 in **every** of 6 blocks (both ledgers × H∈{20,30,40}): lowest β, shallowest DD, highest Sharpe, and on 2009–16 real α t **+2.33/+2.00/+1.43**. `tstat`≡`sharpe` (ρ=1.00, identical book — n_obs ≈ const). Dropping the denominator (`sum`,`cum`) STRICTLY HURTS: β↑ (0.92→1.33, 1.24→1.97) & DD↑ (−14.5→−23, −7.9→−18.8) — reviewer's worry backwards, the denom screens out high-β vol names (x03's whole point), not winners. Cadence NOT fragile (Sharpe holds at 30/40). Caveat unchanged: clean-2022–24 α≈0 (better-risk-engineered β, not new alpha); 2009–16 α is survivorship-lifted YF (relative ranking unaffected). x03 score definition SETTLED |
| Absolute score threshold vs relative top-N (book width) | SHIPPED as **x04** challenger (2026-06-21), NOT promoted | `experiments/multiday/multiday_residmom_absthresh.py` + `multiday_x04_concentration_preregistration.md`. %cash≈0 → genuine CONCENTRATION, not cash-timing. ABSOLUTE cutoff rejected (regime-fragile, cherry-picked); relative top-N is the lever. Curve non-monotonic + DISAGREES across windows (2022–24 wants ~15, 2009–16 ~35, both dip at 10, top-5 = lottery). Only robust slice both windows agree = gentle trim top-50→**top-35** (Sharpe 1.59→1.70 / 1.18→1.23). Shipped x04=top-35 as a single-lever challenger to x03; edge small (~0.1 Sh) + regime-unstable optimum → awaits forward-sealed 2026 (~2027); if it doesn't separate, x03 (wider) is the keeper |
| x05 Arm A — β-estimate cleaning (split-half \|Δβ\| / se(β) pre-filter, drop worst 20%, top-50 width fixed) | KILLED (2026-06-24) | `experiments/multiday/multiday_residpurify.py` + `research_log/multiday_x05_residual_purification_preregistration.md`. The 4/4-AI-convergent, zero-data, highest-conviction sweep idea — attack the β≈1.08 by excluding names whose CAPM β estimate is untrustworthy. LOCKED primary (split-half β-instability filter) FAILS both windows: **2022–24** only β falls (1.05→0.92) but DD −1.1pp DEEPER, Sharpe −0.09, α-t 0.98→0.73, CAGR −3.8pp; **2009–16** β doesn't even fall (1.07→**1.08**), DD −2.1pp deeper, α-t 1.20→0.51, CAGR −3.6pp. The se(β) robustness variant LOOKED better (β↓ both, Sharpe ↑/flat both, α-t ↑ both) BUT fails the CAGR guardrail (−2.3/−3.7pp): dropping the 20% highest-residual-variance names is a disguised **LOW-VOL tilt** (already killed as a diversifier) — the exact confound the guardrail was pre-registered to catch. Per the locked rule the PRIMARY decides → KILL (se(β) NOT promoted; that would be the forking-paths cherry-pick the prereg exists to block). **LESSON: the β≈1.08 is NOT a fixable estimation artifact — the unstable-β / high-idio-vol names ARE the momentum; filtering them buys ~3pp CAGR-for-vol, not alpha. The "purify the residual" half of the 2026-06-23 sweep META-FINDING is now WEAKENED.** No sealed year spent (in-sample 2022–24 + 2009–16). |
| x05 Arm B — net-share-issuance veto (top-90 IR → drop top-quintile split-adj 12m NSI → top-50) | KILLED (2026-06-24) | `experiments/multiday/multiday_residpurify_veto.py` + `capture/capture_issuance.py` + `research_log/multiday_x05_residual_purification_preregistration.md` (addendum) + `multiday_x05b_issuance_veto_preregistration.md`. The 2nd surviving sweep direction (drop heavy diluters among residual winners). **2022–24 LOOKED like a mild positive** — Sharpe 0.79→0.86, α-t 0.98→1.22, maxDD −11.6→−10.5, CAGR +1.3pp — but β ROSE 1.05→1.07 (failed the x05 β-fall rule) and it was within noise (corr 0.99, α still insig). Given it improved alpha-not-β, RE-SPEC'd as **x05b** with a principled β-neutral rule (Sharpe↑ AND α-t≥ AND DD≤ AND CAGR≥−1pp AND Δβ≤+0.10), with 2022–24 demoted to SPENT/motivating and **2009–16 (fresh for issuance) as the real confirmation**. **2009–16 does NOT confirm:** Sharpe FLAT 1.18→1.18 (fails rule-1), α flat (0.42→0.39, t 1.20→1.22), DD +0.8pp, corr 0.99, avg 9.2 names vetoed → the veto barely moves anything. **The 2022–24 lean did NOT replicate out-of-sample → it was regime/noise, not an effect.** Both-windows discipline + the re-spec gave it every fair chance and it honestly failed. Data caveat (pre-committed): 2009–16 issuance coverage thin pre-2012 (2009 0%, 2012+ 66–87%, overall 55%) + survivorship-lifted — secondary evidence, but the null is clear. NSI split-adjustment was correctness-critical (yfinance split events + (−0.45,+0.85) winsorize for the irreducible SEC end-date/value basis ambiguity); the veto is conservative (can miss a genuine heavy-issuer-that-also-split, never falsely vetoes). No sealed year spent. **x05 id FREED (both arms killed).** |
| Score-TILT weighting (rank-based, top→1+s / bottom→1−s, vs equal-weight) | KILLED (2026-06-22) | `experiments/multiday/multiday_residmom_scoretilt.py`. Operator-posed: mildly overweight higher-scored names (~±10–15%)? NO. The book is too diversified for a mild tilt to register — corr(EW, even extreme s=0.50) = **+0.995/+0.997**, so at the proposed s≈0.125 the portfolio is ~99.9% identical to EW (numbers flat to 2 dp). To the extent it DOES change anything it tilts toward the highest-score = highest-β/most-crash-prone names: 2017–24 flat-to-trivially-negative (top35 Sh 0.85→0.84, maxDD −24.3→−25.6 @ s=0.5); **2009–16 monotonically HURTS** (top35 α-t 1.39→1.31→1.06, Sh 1.23→1.14, maxDD −11.9→−14.2 as s 0→0.125→0.5). Same give-back-the-risk-improvement failure as ATR-exit/leverage. Flat cost FAVORS the tilt → robust non-win. EW confirmed correct; score is a RANK to select top-N, not a weight. No sealed year spent (in-sample diagnostic, nothing cleared) |

## BACKLOG — practical ideas to test (prioritized)

Sourced from the 2026-06-16 peer review (gemini/grok/meta — all three independently). Status =
`idea` until pre-registered.

### Tier 1 — high conviction / decision-critical

1. **Beta-adjusted alpha check** *(validation fix, not a new signal)* — status: idea, NEXT.
   The cross-sectional premium (top-50 − universe) is NOT beta-adjusted; with β≈1.4 an up-year
   mechanically produces a positive premium even at zero alpha (meta + gemini). Compute proper PIT
   beta-adjusted alpha: regress strategy per-period returns on SPY (trailing-PIT β), read the
   intercept; report on 2025 OOS + clean 2022–2024. Cheap, no new data. Recalibrates how much
   "alpha" we actually have vs beta. *Caveat: gemini's exact arithmetic assumes universe β=1.0 vs
   SPY (too low for equal-weight liquid names) → real leakage smaller than they claim, but do the
   test.*

2. **Residual / idiosyncratic momentum → `x03`** — status: idea, the one real improvement shot.
   UNANIMOUS #1 across all three reviewers. Rank on the residual of a rolling regression of each
   name's returns on the market (CAPM, single-factor, uses SPY we already have) — FF3 later if a
   clean daily PIT factor series is added. Pre-register: at rebalance d, rolling OLS over prior
   N∈{126,252,756} days (≥N/2 obs) of r_i on r_SPY; residual-momentum = standardized sum of ε over
   d-252..d-21 (skip month); rank desc, top-50 EW, same hold/cost. Rationale: total-return momentum
   has unstable, drifting factor loadings → crashes; residual momentum strips beta by construction
   (~½ vol, ~2× Sharpe, lower crash in the literature). Directly attacks our β≈1.4 weakness; it is a
   NEW RANKING SIGNAL, NOT covered by the conditioning kill. Clean either way: beats x01 = real
   improvement; lags badly = strong evidence the edge is mostly beta → bank x01 as a beta-tilt.
   Failure mode: lags raw momentum in strong beta-driven bulls (2020–21, 2025); daily residual
   estimation adds noise; needs ≥36mo history (drops recent IPOs).

3. **Realistic cost / capacity curve** *(tradeability gate)* — status: idea.
   Our 10bps headline / ~3bps turnover-adjusted may both be optimistic (meta): a $48M book in
   $10M-ADV names is ~15% of ADV → real all-in ~15–30bps one-way, which could cut clean Sharpe
   ~0.50 → ~0.30–0.35. Build a cost-vs-AUM curve (extend `multiday_portfolio_review.py`): per-name
   participation, spread+impact model, net Sharpe at AUM ∈ {5,10,25,48}M. Decides whether any of
   this is tradeable net before spending more research.

### Tier 2 — test only if Tier 1 (esp. residual momentum) is encouraging

4. **Portfolio-level vol targeting DONE RIGHT** — status: idea.
   All three: we killed the wrong version. Re-test target-vol exposure scaling using the STRATEGY's
   OWN trailing realized return vol (prior 63–126d), NOT the mean of constituent vols (what V2 used,
   which ignores diversification). exposure = min(1, target_vol / realized_strategy_vol), never
   lever >1, park residual in cash (or SH). Pure risk management; de-levers only in 2022-type
   regimes; survives the pipeline. Cheap (modify `multiday_volscale.py`). Modest expected upside.

5. **Frog-in-the-Pan / information discreteness (Da-Gurun-Warachka)** — **KILLED 2026-06-18** (see kill
   table + `multiday_x04_fip_preregistration.md`). In-sample 2022–24: faithful arm α t −0.03 / DSR 0.67,
   residual arm strictly worse than x03. Path quality subsumed by return-level momentum; the
   "conditioning grid suggests path filters fade" caveat held. NOT a diversifier (corr +0.88/+0.95).
   Original idea below for the record:
   Path-quality: among high-momentum names prefer SMOOTH trends over jumpy/lottery ones. ID proxy =
   %positive-days − %negative-days over the formation window (or |PRET|/Σ|daily r|). Double-sort:
   top momentum decile, then lowest-ID (most continuous), hold 50. Orthogonal behavioral channel
   (path, not level); filters crash-prone lottery winners. Medium conviction (our conditioning grid
   suggests path filters fade, but FIP is more structured). Needs total-return-clean daily bars.

6. **Risk-adjusted momentum (signal = mom_12_1 / σ_252)** — status: idea.
   Rank on return/vol instead of return; selects smooth winners EX-ANTE (avoids the post-selection
   down-weighting that killed V1). Cheap cousin of residual momentum; test alongside it.

### Tier 3 — low priority / gated

7. **Quality-profitability blend (Novy-Marx gross profitability)** — status: idea, DATA-GATED.
   composite = 0.7·rank(mom) + 0.3·rank(GP), GP=(Rev−COGS)/Assets from lagged filings. Adds a
   fundamental anchor that held up in 2022. Needs PIT quarterly fundamentals we don't currently
   ingest — a heavier data lift before it's testable.

8. **Dynamic / tail-regime hedge (VIX>25 & SPY mom<0 → 50% SH; or correlation-crowding gate)** —
   status: idea, LOW PRIORITY. Targets momentum crashes with the inverse-ETF toolkit. HIGH overfit
   risk in the trigger; our regime-timing kills (defensive sleeve) show this class is fragile; grok
   agrees skip. Only revisit if a robust, pre-registered trigger is justified ex-ante.

## BACKLOG — from 2026-06-17 keyword research (`peer-feedback/2026-06-17-keyword-research/report.md`)

377 YouTube transcripts across 25 keywords (Titman / Wes Gray / Antonacci / Barroso-Grobys /
transaction-cost lecture). Cross-referenced against the kills above. Most P0/P1 report items map
to ideas already listed (vol-targeting #4, risk-adj-mom #6, FIP #5, quality-blend #7, tail-hedge
#8) or already KILLED (52w-high, defensive-sleeve). Below = the genuinely NEW / re-prioritized.

**KEY STRATEGIC INSIGHT (drives the ordering):** items 9–11 below are *construction / cost / risk
engineering changes, NOT new ranking signals* → they do **not** require a fresh sealed year (both
2025 and 2026-H1 are spent until ~2027). They can be validated on clean 2022+ in-sample and the
already-spent OOS as a *reproduction*. Everything that is a new ranking/timing signal (#6 risk-adj
mom, #5 FIP, #12 dual-mom-to-cash, factor-momentum) still costs a ~2027 sealed year — so the
construction changes jump the queue.

### Tier 1 (re-prioritized) — construction/cost changes, NO sealed year needed

9. **Overlapping portfolios (Jegadeesh-Titman construction)** — **KILLED 2026-06-18** (see kill table
   + `multiday_x04_overlapping_preregistration.md`). Pre-registered and tested as x04 on the x03
   ranking: gross Sharpe slightly WORSE (+0.78→+0.73), and the capacity benefit is moot because
   non-overlap isn't cost-stressed at realistic AUM under the locked cost model. The "cuts turnover
   ~95%" framing was wrong — overlap changes *names per observation*, not *capital turnover per unit
   time* (identical). Lesson: construction is not the leak for this low-turnover family; the **ranking
   signal is the lever**.

10. **Realistic cost / capacity curve** — (was Tier-1 #3; **partially DONE** via
    `experiments/multiday/multiday_overlapping.py`'s AUM curve, 2026-06-18). Finding: under spread 5bps + 10bps·√p
    round-trip, net Sharpe is flat from $5M→$250M (peak participation only 9% at $50M) — i.e. cost is
    NOT the binding leak at the moderate constants. **Open caveat (decision-critical before scaling):**
    those constants may be optimistic vs the portfolio-review worry of 15–30bps all-in in $10M-ADV
    names; settle the true impact with a **live-fill study**, not more modeling. Until then, treat the
    edge as cost-robust at the AUM we'd actually run.

11. **Vol-targeting DONE RIGHT** — **ALREADY DONE & KILLED 2026-06-17** (`multiday_x03_voltarget`,
    `multiday_x03_voltarget_preregistration.md`). The "done right" version (scaled by x03's OWN
    realized vol, K=6, σ_target=18.6%, L∈{1.0,1.5}) was tested on 8yr and FAILED the bar: Sharpe
    +0.88→+0.79 (L=1.0) / +0.73 (L=1.5), drawdown only ~7% shallower (< 15% bar), L=1.5 < L=1.0.
    Cause: trailing-vol on sparse 20-day periods is LAGGY — de-risks after vol already spiked, near
    bottoms, missing rebounds. **x03 deploys at constant 1.0×.** Both sizing directions now settled
    (static leverage hurt x01; vol-target doesn't help x03). x03's low drawdown is STRUCTURAL (from
    residualization), not from any overlay. Confirms the broader pattern: TIMING/SIZING overlays are
    fragile on this strategy → the lever is the RANKING signal, not risk-engineering.

### Tier 2 (re-prioritized) — new ranking/timing signals (each costs a ~2027 sealed year)

12. **Absolute-momentum overlay to CASH (Antonacci dual momentum)** — status: idea. **Distinct from
    the KILLED defensive sleeve:** gates on SPY trailing-12mo *momentum* (not the 200d-MA that
    whipsawed) and exits to **cash / T-bills** (not TLT/GLD, which *failed* in 2022). "Relative mom
    says what to buy; absolute mom says when." Antonacci 1973–2013: 17.7% vs 13.6% CAGR, DD −19.8%
    vs −50.8%. Directly targets our intrinsic momentum-crash risk. **Caveat:** regime-timing is our
    most fragile class — pre-register the trigger ex-ante or it's overfit bait; and an absolute gate
    only helps if it fires in a sealed crash year we haven't spent.

13. **ATR-based dynamic trailing exit** — status: idea, NEW (only the *fixed* 15% stop was killed as
    redundant). x03 is pure time-exit; test a chandelier/3×ATR(14)-from-peak trailing exit *as an
    overlay on the H=20 base* (keep time exit as the floor). Report: ATR/chandelier beat fixed-% on
    risk-adjusted return across multiple practitioner tests (Riley Coleman, Jason McIntosh, SMB).
    Medium conviction — may just duplicate the time exit; cheap to test.

14. **Quarterly horizon H=63 (turnover-light variant)** — status: idea, NEW. x01/x03 use H=20 (~1mo),
    unusually short vs the Jegadeesh-Titman H=6mo origin; the report notes monthly rebalancing was a
    *convenience*, not evidence. H=63 (or H=126) cuts turnover further and may survive net-of-cost
    even if gross is a touch lower. **Caveat:** H=5 already DIED; the momentum→long-term-reversal
    boundary (De Bondt-Thaler) caps useful holds at ≲12mo, so test H∈{63,126} only, not beyond. Note
    this is *redundant with #9* if overlapping construction already solves the turnover problem —
    test whichever is cleaner, not both. **DOWNGRADED 2026-06-18:** the #10 cost curve shows cost is
    NOT the binding leak at realistic AUM, so H=63's turnover-reduction rationale is weak; only worth
    testing if the live-fill study (see #10) finds real costs are much higher than modeled.

15. **Factor momentum everywhere** — status: idea, NEW, lower conviction. Apply momentum to each
    name's *factor exposures* (value/quality/size loadings) rather than only its price return, as a
    co-ranking signal. Different class of signal; needs the factor series we don't yet have cleanly
    (overlaps with the FF3-residual lift behind x03→x04 and the quality-blend #7 data gate).

16. **Earnings momentum as a second leg (price + earnings)** — status: **Stage-0 BORDERLINE**
    (2026-06-18). Chan, Jegadeesh & Lakonishok (1996) + Titman: price + earnings momentum have
    *independent* predictive power. Now testable — the PIT-fundamentals data lift is DONE (see below).
    Triage `ni_yoy` (TTM net-income YoY): pooled spearman +0.52 but D10−D1 BREAKS in the 2023 chop
    year (−0.95); positive 2022/2024. Weaker than quality once breadth added → secondary, not primary.

## PIT-FUNDAMENTALS DATA LIFT — DONE 2026-06-18 (user picked SEC EDGAR; option 2)

Built `data/sec_fundamentals.py` — the project's only fundamentals source: SEC EDGAR XBRL
`companyfacts`, TRUE point-in-time (uses each fact's `filed` date; at rebalance d only facts with
`filed <= d` are visible), survivorship-free (delisted filings persist), free. Cached per-CIK JSON +
rate-limited (≤8/s) + retry. Four real PIT bugs found & fixed (each would have silently corrupted a
backtest): (a) XBRL tag drift → union tag variants; (b) restatement broke PIT → filter filed≤asof
BEFORE dedup-to-latest; (c) split-sensitive EPS → use net-income TTM; (d) implied-Q4/YTD-cumulative
gaps → reconstruct discrete quarters by differencing YTD cumulatives. Validated: NVDA NI YoY +581%,
XOM −35%, AAPL TTM rev $385.7B — all economically correct as-known-at-date. Scripts:
`experiments/multiday/multiday_fundamentals_triage.py` (Stage-0). Signals: `gp_assets` (Novy-Marx GP/Assets),
`ni_yoy` (TTM net-income YoY). Caveat: the JOIN inherits the price ledger's pre-2024 survivorship
bias (Alpaca active-list universe) — same limitation as all our 2022–24 work, not worse.

### Stage-0 triage (800 liquid names) → looked like a PASS but was a MIRAGE

`gp_assets` Stage-0: D10−D1 positive all 3 years, pooled spearman +0.80 (raw decile monotonicity).
`ni_yoy` borderline (2023 flip). LOOKED like the first orthogonal signal to clear Stage-0 — but the
triage measured RAW (not beta-adjusted) returns. The full beta-adjusted test killed it (below).

### FULL pre-registered RESULT (2026-06-18) — KILLED (`multiday_x04_quality_preregistration.md`)

Full PIT capture (`_capture_fundamentals_2017_2024.parquet`, 172k rows / 1708 tickers) scored by
`experiments/multiday/multiday_quality.py`. **gp_assets top-50 EW book: beta-adjusted α = +0.00% t +0.00 on 8yr
(EXACTLY zero idiosyncratic alpha — pure beta), −0.54% t −1.55 on clean 2022–24 (negative).** Sharpe
+0.14 (clean) / +0.69 (8yr) < x03 everywhere; DSR 0.43 clean. NOT additive: corr to x03 +0.67/+0.76
(> 0.60 bar), 50/50 blend Sharpe LOWER than x03 alone with deeper DD. ni_yoy same story (α −0.48%
t −0.96). **VERDICT KILL on both signals, both windows, both bars.** Why the Stage-0 +0.80 was a
mirage: top-50-by-GP across the full universe selects the most extreme gross-profitability names
(asset-light high-multiple growth/software) = a high-BETA growth tilt that fell hard in 2022, NOT
defensive quality; raw decile monotonicity captured that beta. Bar A (beta-adjusted alpha) was built
to catch exactly this — the §6b lesson again. **PIT-FUNDAMENTALS DIRECTION CLOSED.** x03 remains the
only validated edge; no long-only diversifier exists for it → bank x03 standalone.

Reusable kept: `data/sec_fundamentals.py` (validated true-PIT EDGAR adapter), the capture parquet, and
the 3 scripts — for any FUTURE pre-registered fundamentals idea (a value composite, or a proper
defensive-quality QMJ via low accruals/leverage rather than gross profitability).

## BACKLOG — external AI idea sweep (2026-06-23, `idea-solicitation/responses-2026-06-23/`)

Ran the `strategy-evolution-prompt` skill on x04 → solicited ideas from 4 frontier AIs
(ChatGPT, Gemini, Grok, Meta). Full responses + my dedup/triage in
`idea-solicitation/responses-2026-06-23/SYNTHESIS.md`. **~40 raw ideas → 9 themes → a ≤2-arm
Sprint-1.** Nothing here is tested yet; all are `idea` status. These do NOT delay
productionizing x03 — they are a cheap, in-mandate batch aimed at the β≈1.08 leak.

**META-FINDING of the sweep:** with the kill-ledger in front of them, ALL FOUR models
independently refused to propose "another factor" and converged on the same two directions —
(1) *purify the residual we already compute*, (2) apply a *secondary fundamental veto* on
already-selected momentum winners (NOT a primary sleeve). Not one re-proposed a killed primary
factor. That 4/4 convergence is the strongest evidence in the batch. Response quality:
**Grok best-fit** (100% upstream, most honest on magnitude), ChatGPT best framing + the two
sharpest novel selection ideas (residual de-crowding, cross-sectional purification), Meta best
calibration ("honest base rate: none likely +0.3 Sharpe; H-conviction ideas shave 3–5pp DD at
flat return"), Gemini deepest theory but broke its own constraints (proposed killed
overlay/timing classes — momentum-gap scaling, January seasonality → SKIP).

**Pre-registered Sprint plan (batch + lock decision rule BEFORE running — this is a 40-idea
forking-paths minefield; pick ≤2 survivors, THEN spend the ~2027 sealed year ONCE):**

- **SPRINT 1 RESULT (2026-06-24): BOTH P0 ARMS KILLED → sweep exhausted, BANK x03.** The two
  4/4-convergent directions were the sweep's best shot and both honestly failed with earned
  evidence (see kill-table). x05 id freed. The 2026-06-23 "fresh batch" qualifier is now RESOLVED:
  residual-purification AND issuance-veto are dead; the β≈1.08 is structural and no fundamental
  veto adds robust alpha on this universe. **The META-FINDING stands fully reinforced — x03 is the
  ceiling. Next move is PRODUCTIONIZE x03, not more search.** Remaining sweep P1/P2 themes (residual
  persistence, downside-asymmetry, EW-universe factor, lottery/MAX veto, CGO) are LOWER-prior than
  the two just-killed and are NOT worth a research cycle ahead of productionizing — leave logged.
- **Sprint 1 — P0 (4/4 convergence, zero/owned data, targets β=1.08 directly):**
  - **A. β-estimate cleaning** — **KILLED 2026-06-24 (see kill-table).** Locked primary failed
    both windows; se(β) variant's β↓/Sharpe↑ was the low-vol-tilt confound (CAGR guardrail
    caught it). The β≈1.08 is intrinsic, not an estimation artifact. Purify-residual prior down.
  - **B. Issuance veto** — **KILLED 2026-06-24 (see kill-table).** 2022–24 within-noise lean did
    NOT replicate on 2009–16 even under a generous re-spec'd β-neutral rule (x05b). Bank x03.
  - ~~A/B original ideas~~ (for the record below): — stale/noisy single-β leaks market exposure into the residual.
    Cheap canonical: split-half β-stability (or se(β)) filter — drop top-20% most-unstable
    within top-70 by IR, take 35. (Theil-Sen robust regression & Kalman time-varying β are the
    same theme — test the cheap split-half FIRST; escalate only if it shows signal.)
  - **B. Secondary fundamental veto on winners** — within top-70 IR, exclude top-quintile by
    **net-share-issuance** (12m %Δ shares, 4 models) and/or **accruals** (Sloan, 3 models),
    take 35. Distinct from the KILLED value/quality/NI-YoY *primary* sleeves (applied as a
    post-selection exclusion, not a ranking factor). PIT-EDGAR adapter already built.
- **Sprint 2 — P1 (only if Sprint 1 encouraging), one clean form each:** C. residual
  persistence `min(IR_h1, IR_h2)`; D. downside-semivariance denominator (Sortino-style IR);
  E. EW-liquid-universe factor in place of cap-weighted SPY (single-factor swap, ≠ FF3).
- **P2 / speculative (1–2 models):** lottery/MAX veto, cross-sectional β/raw-mom purification
  (risk: strips the actual edge — the FF3 "extra regression = noise" lesson), capital-gains-
  overhang disposition gate.
- **SKIP (killed classes in disguise):** momentum-gap concentration scaling (= top-N sweep +
  sizing overlay), January seasonality (= fragile timing).

**Guardrails (where these usually die — all three are prior backlog lessons):**
1. **Judge on beta-adjusted alpha, NOT raw decile/return spread** — every fundamental sleeve so
   far (value, GP, NI-YoY) looked good raw and died beta-adjusted (the §6b Stage-0-mirage). Apply
   Bar A from the first cut.
2. **A "filter" that improves DD only by collapsing return is a FAIL, not a win** — a disguised
   low-vol tilt gives back the same risk-improvement that killed ATR-exit/leverage/vol-target.
   Require the DD/Sharpe gain at ~FLAT gross return. (Watch theme D especially.)
3. **Theme C is residual-space path-quality** — FIP was killed because residualization already
   trims jumpy names. Test C as a FALSIFICATION ("is anything left to smooth in the residual?"),
   kill on corr >0.97 to baseline + no crash-month gain.

## Methodology fixes to adopt (cheap, improve integrity)

- Compute kills/verdicts on **clean 2022+ PIT only**; treat 8yr DSR 0.99 as survivorship-inflated
  secondary evidence (we already lean this way; be strict about it).
- Use **beta-adjusted alpha** (backlog #1) as the alpha-vs-beta discriminator going forward, not
  the raw cross-sectional premium.
- Confirm **delisting-return** handling (apply delisting return at exit; matters more for distressed
  names that can enter via reverse-split) and consider **total-return (dividend) adjustment** for
  the 252-day formation (splits already fixed; dividends are a smaller distortion for momentum).
- Optionally add a strict **rolling/expanding walk-forward** as a robustness cross-check alongside
  LOO (gemini's "LOO leaks" is overstated for our fixed-rule use — we don't fit params to the
  held-out year — but a rolling WF is cheap and silences the objection).

## Reviewer bottom-lines (for context)

grok + meta: **bank x01, don't spend sealed years on marginal 12-1 tweaks**; residual momentum is
the single exception worth a narrow test. gemini: **don't bank as alpha — keep hunting**, residual
momentum + FIP + tail-gating, and fix the premium/validation. Net: residual momentum is the
consensus next test; cost realism + beta-adjusted alpha decide whether the edge is worth scaling.
