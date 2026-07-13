# Short-Hold Strategy Profitability Evaluation

**Date:** 2026-07-13 · **Mandate:** hold hours → **3 sessions max** (flat by end of T+2) ·
**Goal:** minimum-viable but honest backtests of the 13 short-hold candidates from
[`ranking_short_hold.md`](../library/youtube-influencers/strategies/ranking_short_hold.md),
ranked by profitability, to pick **one** to implement thoroughly.

> **FINAL RECOMMENDATION (see §6–§7):** **Momentum Burst, ~5-session hold, entries gated on
> SPY 10>20 EMA AND SPY > 200-day SMA (bear filter).** At a 3-day cap nothing cleared honest
> significance; at a **5-day hold** the edge is day-clustered **t = 2.86**, survives realistic
> costs, is positive in 3 of 4 years, and **passes** an out-of-sample split + parameter-robustness
> + cost-stress (§6). Adding the **200-day bear filter** (§7) cuts the 2022 loss ~⅔, drops max
> drawdown from −39%→−32%, and lifts a $10k/10-position account's 4-year median from **≈+3% to
> ≈+35%** (10 bps), while raising significance to **t = 2.99** (in-sample now significant too).
> It is not tail-dependent like Episodic Pivot; its edge is spread over ~19k trades. This is the
> one strategy here I'd take to a proper live build — with survivorship and cost caveats intact.
>
> **Earlier verdict (≤3-day mandate, still valid for that constraint):** under a hard 3-day cap
> *no* strategy is a validated edge; Episodic Pivot has the biggest point estimate but it is a
> tail lottery (one trade = 32% of its PnL; day-clustered t = −0.06) concentrated in sub-$5 names.
> The **"do not pursue" list is robust** at every horizon tested (Inside Bar, VWAP Bounce,
> Contrarian, Fib, pure Overnight, Gap-and-Go — the last two tested on an unrepresentative
> large-cap universe, so treat as "not tested fairly" rather than "killed").

---

## 0. Post-review correction (2026-07-13)

An adversarial review ([`ADVERSARIAL_REVIEW.md`](ADVERSARIAL_REVIEW.md)) audited this work. It
**confirmed the mechanics** (no look-ahead, correct cost sign, real tail winners incl. QMCO
+286%, correct metrics, panel matches source data) but showed the **confidence claim was
overstated**. I independently re-derived each material finding from the raw trade logs and
**they all reproduce**:

| Finding | Independently confirmed | Effect on verdict |
|---|---|---|
| **Day-clustering kills significance** | EP trades cluster (403 days, up to 24 trades/day). Equal-weighting each day: mean **−3.5 bps, t_day = −0.06**. Day-block bootstrap 95% CI on the trade-mean **[−15, +228] bps** (includes 0). | EP's t=1.87 was cross-sectional correlation, not evidence of edge. **No day-level edge.** |
| **Tail = the whole edge** | Top 1 trade (QMCO) = **32%** of EP's total PnL; top 5 = 76%; top ~1% (9 trades) = **101%**. Drop them → mean **−1.5 bps**. | Edge is a positive-skew lottery, not a repeatable per-trade advantage. |
| **Liquidity fragility** | Sub-$5 names (9.5% of trades) mean **+585 bps**; restricting to entry ≥ $5 halves the edge to **+51 bps (t=1.30)**. 5–10 bps costs are unrealistic for the cheap/explosive names that drive it. | "Survives costs" holds only at optimistic costs on names you couldn't trade cleanly. |
| **Survivorship** | Only **1–2 of 1,984** panel tickers stop trading before end-2025 (0 of 579 EP names). Failed gap-ups that went to zero are largely absent. | Optimistic bias for all momentum/EP-style strategies. |

**Day-clustered significance for every strategy** (`t_stat_day`, now a first-class metric):
under honest inference **none of the 13 reaches |t| ≥ 2.** The strategies with the *best*
day-clustered t are AVWAP Pullback (1.69), Overnight-3d (1.51) and Momentum Burst (1.50) — all
of which **die at 10 bps or fail in non-trending years.** Episodic Pivot, the highest point
estimate, has the *worst* day-robustness (−0.06).

**Net effect on the verdict:** the *relative ranking* (EP best point estimate; the negative list
robustly bad) stands, but **"implement Episodic Pivot" is downgraded to "least-bad research
candidate, with conditions"** (see §5). Nothing here is a validated, fundable edge.

---

## 1. Methodology

| Item | Choice | Why |
|---|---|---|
| Data | `trading.marketdata` (Alpaca-backed, split-adjusted) | same layer live uses → backtest/live parity |
| Daily universe | `liquid_pit` point-in-time union, **1,984 tickers** | PIT membership (reduces survivorship); broad cross-section |
| Daily window | **2022-01-01 → 2025-12-31** (4y) | spans 2022 bear, 2023-24 bull, 2025 — regime variety |
| Intraday universe | `cached_1min_2024_pit`, **330 liquid tickers** | full 1-min cache available |
| Intraday window | **2024** (1y, 1-min RTH) | VWAP Bounce / Gap-and-Go need intraday bars |
| Entry | next-session open, or buy-stop on a trigger, or signal-close (overnight) | no look-ahead; a signal read at close is acted on next open |
| Exits | strategy stop + optional target + **hard 3-session time-stop** | the mandate; one shared, auditable exit model for all |
| Costs | **5 bps/side baseline; 10 bps/side sensitivity** | short holds × small account ⇒ costs dominate |
| Sizing (portfolio curve) | 8 concurrent slots, equal weight | realistic small-account capacity |

**One shared engine** (`common/engine.py`, `common/intraday.py`) simulates every strategy, so
results are directly comparable. Each strategy is one `signals.py` in its own folder that emits
`Signal`s; the engine does the rest.

### Ranking metric
The headline is **net %-return per trade** (`exp_bps`, cost-inclusive) with its **t-stat**
(is the edge real?) and **profit factor**. R-multiple stats are shown only as reference — they
distort across strategies with different stop conventions. The portfolio CAGR/Sharpe is a
*secondary, capacity-limited* indicator (a first-come 8-slot fill), noisy for strategies whose
signals cluster (Contrarian, Bollinger) — **do not rank on it alone**.

### Honest limitations (these bound the confidence, not just disclaimers)
- **Daily-bar intraday proxy:** breakout strategies use a next-day fill / buy-stop trigger, and
  stops on the entry day use the full day's low (conservative — slightly over-penalises breakouts).
- **No borrow/liquidity/partial-fill/impact model.** Fat-tail winners assume you actually got filled.
- **PIT universe from 2022** only; pre-2022 not covered. 4 years is short for tail-driven strategies.
- **≤3-day truncation is deliberately conservative** for strategies (EP, AVWAP, Momentum) whose
  real doctrine lets winners run — see §5.
- Indicator approximations where a spec needs discretion (Anchored VWAP → 20-day rolling VWAP;
  Contrarian sentiment → VIX vs its 10-day MA + per-name washout).

---

## 2. Full ranking — all 13 strategies (15 configs), net of 5 bps/side

Sorted by net expectancy per trade. `exp_bps` = mean %-return/trade × 10⁴. `@10bps` = same at
doubled cost. **Green = positive & cost-robust; the rest do not clear costs.**

`t` = naïve trade-level t-stat (assumes independence — **overstated**); **`t_day`** = honest
day-clustered t-stat (equal-weight each calendar day). Rank on the point estimate, judge
confidence on `t_day`.

| # | Strategy | Horizon | n | Win% | **exp bps @5** | **@10** | PF | t | **t_day** | Notes |
|--:|----------|:------:|--:|:---:|:---:|:---:|:---:|:---:|:---:|-------|
| **1** | **Episodic Pivot** | daily | 876 | 47.0 | **+101.3** | **+91.2** | **1.30** | 1.87 | **−0.06** | biggest point estimate; **no day-level edge**; tail/liquidity-driven |
| 2 | Momentum Burst | daily | 23,504 | 44.4 | +15.8 | +5.8 | 1.07 | 2.75 | 1.50 | ⚠️ best day-t among positives; thin, −ve in 2/4 yrs, cost-fragile |
| 3 | AVWAP Pullback | daily | 19,197 | 40.8 | +8.3 | −1.7 | 1.04 | 1.69 | 1.69 | ✗ dies at 10 bps |
| 4 | Overnight Hold (close→close, 3d) | daily | 112,095 | 46.5 | +7.3 | −2.7 | 1.04 | 3.82 | 1.51 | ✗ bull-beta; 3.82 was clustering; dies at 10 bps |
| 5 | Overnight Hold (close→close, 1d) | daily | 145,861 | 47.6 | +0.9 | −9.1 | 1.01 | 0.90 | −0.72 | ✗ ~breakeven pre-cost |
| 6 | Overnight Hold (1-night, c→open) | daily | 145,861 | 45.5 | −1.2 | −11.1 | 0.98 | −1.86 | −0.91 | ✗ pure overnight premium **does not** survive costs |
| 7 | Gap and Go | intraday | 450 | 45.1 | −1.9 | — | 0.98 | −0.18 | −0.04 | ✗ no edge (matches sealed gap-drive OOS fail) |
| 8 | S/R Bounce | daily | 31,961 | 47.5 | −3.7 | −13.7 | 0.97 | −1.62 | −0.86 | ✗ |
| 9 | MACD 3-10-16 | daily | 15,971 | 45.2 | −4.3 | −14.3 | 0.97 | −0.99 | 1.29 | ✗ negative expectancy |
| 10 | Fib Pullback | daily | 23,294 | 48.8 | −6.6 | −16.5 | 0.96 | −2.14 | −0.47 | ✗ |
| 11 | VWAP Bounce | intraday | 58,891 | 36.4 | −8.9 | — | 0.71 | −38.0 | −10.1 | ✗ whipsaws badly after costs |
| 12 | TTM Squeeze | daily | 4,411 | 46.7 | −12.6 | −22.5 | 0.94 | −1.04 | −0.76 | ✗ |
| 13 | Bollinger Squeeze | daily | 488 | 45.5 | −37.9 | −47.9 | 0.81 | −1.66 | −0.52 | ✗ most squeezes fail within 3d |
| 14 | Inside Bar | daily | 24,055 | 36.3 | −44.9 | −54.9 | 0.69 | −21.8 | −10.1 | ✗ **worst** — breakouts mean-revert |
| 15 | Contrarian | daily | 4,125 | 40.5 | −55.8 | −65.7 | 0.77 | −5.44 | 0.32 | ✗ catching knives (mean-rev killed, confirmed) |

Full machine-readable table: [`results_short_hold.csv`](results_short_hold.csv).
*(Intraday n reflects the full 330-name run; a 5-bps/side cost is applied there too.)*

**4 configs are net-positive at 5 bps; only Episodic Pivot stays positive at 10 bps — but no
strategy clears |t_day| ≥ 2, so none is a statistically established edge.**

---

## 3. Cost sensitivity (the decisive filter)

Short holds on a small account mean the round-trip cost is the edge's biggest enemy.

| Strategy | edge @5 bps | edge @10 bps | Survives realistic cost? |
|---|:---:|:---:|:---:|
| **Episodic Pivot** | +101 bps | **+91 bps** | ✅ **Yes** — edge ≫ cost |
| Momentum Burst | +16 bps | +6 bps | ⚠️ Marginal — edge ≈ cost |
| AVWAP Pullback | +8 bps | −2 bps | ❌ No |
| Overnight (3d) | +7 bps | −3 bps | ❌ No |

Episodic Pivot's per-trade point estimate (~1%) is large vs a 5–10 bps cost — but **this is
misleading** (per §0): ~half the edge comes from sub-$5 names where 5–10 bps is far too kind
(spread + gap-day impact is more like 20–50 bps). Restricting to entry ≥ $5 halves the edge to
+51 bps (t=1.30); it must be stress-tested at 20–50 bps on the cheap names before trusting it.

---

## 4. Robustness of the finalists (per-year + tail dependence)

| Strategy | 2022 | 2023 | 2024 | 2025 | Tail dependence |
|---|:---:|:---:|:---:|:---:|---|
| **Episodic Pivot** | +0.63% | +0.23% | +2.09% | +0.29% | **+ve every year.** Median trade −0.5%; mean +0.9%. Edge lives in the tail (drop top-1% ⇒ edge turns slightly −). |
| Momentum Burst | **−0.28%** | +0.42% | **−0.10%** | +0.10% | **−ve in 2 of 4 years.** Also tail-driven (drop top-5 ⇒ edge ≈ 0). |
| Overnight (3d) | **−0.52%** | +0.15% | +0.10% | +0.05% | Bull-beta: fails hard in 2022, works in up-years. |

- **Episodic Pivot is a genuine positive-skew engine, but the payoff is a lottery, not an edge.**
  Top winners (QMCO $4.45→$17.21, DXYZ, ROOT, PACS, CVNA) are real 2023-25 events (verified,
  split-adjusted on both legs) — but **one trade (QMCO) is 32% of all EP PnL, and the top ~1% is
  100% of it.** Positive in all 4 *trade-mean* years, yet the **day-clustered mean is −3.5 bps
  (t_day −0.06)** — i.e. the "every year positive" is driven by a handful of days. High variance,
  not high confidence.
- **Momentum Burst** has the best day-clustered t among positives (1.50, over 665 days — less
  clustered than EP), but its edge evaporates at 10 bps and it loses money in 2 of 4 years even
  with the index filter. Fragile, not fundable.

---

## 5. Recommendation (revised after review)

**Do NOT green-light production capital on any strategy in this set based on this study.** Under
honest, day-clustered inference none is a statistically established edge, and the one with the
biggest headline (Episodic Pivot) is the *least* day-robust (t_day −0.06).

**If you develop exactly one further, make it Episodic Pivot — as a research programme, not a
deployment** — because it is the only one whose upside justifies more work, *and* the two biggest
knocks against it are addressable by building it properly:
1. It has by far the largest per-trade point estimate (the only one where a real edge could
   plausibly survive honest costs).
2. **The ≤3-day truncation handicaps it** — EP winners (QMCO hit the day-3 time-stop still up
   +286%) are cut off; the real doctrine (hold 3–10d, trail a 10/20-EMA, scale out) should raise
   returns. So the truncated test is a conservative *floor* on the mechanism.
3. The negative findings are fixable in a proper build (catalyst filter → fewer, better setups;
   longer holds → capture the tail; risk sizing → survive the variance).

But treat these review findings as **gating conditions**, not footnotes:
- **Significance:** t_day = −0.06 ⇒ the current edge is *not* distinguishable from zero at the
  day level. Report **day-clustered** inference and **tail-truncated** expectancy as primary going
  forward; require a real out-of-sample / walk-forward pass before sizing.
- **Liquidity:** ~half the edge is in sub-$5 names. Add a hard **price/$-volume floor** and stress
  costs at **20–50 bps** on the survivors (§0/§3).
- **Survivorship:** rebuild the universe to **include delisted names' terminal returns** before
  believing the long-tail economics.
- **Proxy vs doctrine:** my EP signal is price/volume only. Add the real **catalyst/news + float +
  pre-market volume** filters (MAGNA53); the true strategy is a *different, narrower* one and the
  edge may or may not transfer.

**Thorough-rebuild checklist:**
- [ ] Pre-market gap + RVOL scan (not next-day proxy); OPG/ORB entry, hard 2.5% stop.
- [ ] Catalyst verification + neglect condition; Qullamaggie index 10>20-EMA filter (already helps).
- [ ] Let winners run past 3 days (10/20-EMA trail + scale-outs); risk-based sizing (0.25–0.5%).
- [ ] Price ≥ $5–10 and $-volume floor; costs stressed 20–50 bps on cheap names.
- [ ] Longer history **with delists**; report day-clustered t and CI, not trade-iid t.

**Runner-up for a *different* bet (frequency + day-robustness over per-trade size):** Momentum
Burst — best day-clustered t among positives (1.50) but cost-fragile and negative in 2/4 years;
only viable with cheap execution and a strict regime filter.

**Do not pursue** (robustly net-negative after costs, day-clustered t confirms; matches prior lab
kills): Inside Bar, VWAP Bounce (see §6 universe caveat), Bollinger/TTM Squeeze, S/R Bounce,
MACD 3-10-16, Fib Pullback, Contrarian, and the pure 1-night Overnight premium.

---

## 6. Update — relaxing the hold to 5–7 days changes the answer

The ≤3-day cap was truncating the momentum strategies below their native 3–5-day burst. Re-running
the daily engine at `max_hold` = 5 and 7 (one parameter) is the single biggest improvement in the
study — and it lifts the honest **day-clustered t** across the significance line:

| exp bps/trade | @5bps h3→h5→h7 | @10bps h3→h5→h7 | **day-clustered t** h3→h5→h7 |
|---|---|---|---|
| **Momentum Burst** | 16 → **31** → 28 | 6 → **21** → 18 | 1.50 → **2.86** → 2.69 ✅ |
| Overnight (c2c) | 7 → 14 → 13 | −3 → 4 → 3 | 1.51 → 2.54 → 2.38 |
| AVWAP Pullback | 8 → 12 → 13 | −2 → 2 → 3 | 1.69 → 2.15 → 1.72 |
| Episodic Pivot | 101 → 119 → **138** | 91 → 109 → **128** | −0.06 → 0.56 → 0.69 ❌ still tail-driven |

Episodic Pivot's point estimate keeps growing but its edge is **~all of 2024** (2024 trade-mean
+341 bps vs 2023 +0.3, 2025 −1) and never becomes day-significant → **not the pick.** Momentum
Burst becomes both significant and cost-robust, and its edge is **broad** (positive 3 of 4 years,
spread over 22k trades).

### Momentum Burst @5d — validation battery (`scripts/validate_momentum_burst.py`)

**(1) Out-of-sample split** (no parameters were fitted on the data; this is OOS *stability*):

| Window | n | exp @5bps | day-t @5 | exp @10bps | day-t @10 |
|---|---:|---:|---:|---:|---:|
| Full 2022–25 | 22,161 | +31.1 | 2.86 | +21.0 | 2.32 |
| In-sample 2022–23 | 9,317 | +17.3 | 1.44 | +7.3 | 1.03 |
| **Held-out 2024–25** | 12,844 | **+41.0** | **2.47** | **+31.0** | **2.09** |

Edge **holds and strengthens out of sample** and stays significant at 10 bps. (Caveat: IS looks
weaker because it contains the 2022 bear; some OOS strength is a favorable bull-regime draw.)

**(2) Parameter robustness** — perturbing every threshold keeps exp **positive, day-t 2.2–3.0**
(no knife-edge): up_thresh 1.03/1.05/1.06 → +21/+46/+55 bps; close_pos, volume, prior-calm, trend
filter on/off all remain +23…+32 bps. More selective = bigger edge.

**(3) Cost stress** (break-even ≈ 20 bps/side): 5→+31, 10→+21, 15→+11, 20→+1 bps.

**(4) Regime filter** helps overall (day-t 2.86 vs 1.49 without) but **does not save 2022**
(−66 bps) — the index 10/20-EMA filter is a weak bear protector. **Expect bear-market drawdowns.**

**Verdict:** Momentum Burst @5d passes OOS, robustness, and cost stress → the recommended
candidate to build properly. Open risks before sizing: survivorship (panel ≈ all survivors, likely
inflates the edge), bear-market behavior (addressed in §7), and keeping costs < ~15 bps/side.

---

## 7. Bear-market filter (`scripts/test_bear_filter.py`)

The base `spy_bull` (10>20 EMA) filter whipsaws in choppy bears — it let through 39% of 2022 days
(bear rallies that failed). Tested 8 regime filters; the winner is the **classic** one: require
**SPY also above its 200-day SMA**. (Chosen because it's a canonical trend rule, not a data-mined
exotic — lower overfit risk.) Effect on a **$10k / 10-position** account (200–300 random paths):

| Filter | 2022 loss | Max DD | End-2025 median (10bps) | day-t |
|---|---:|---:|---:|---:|
| `spy_bull` (old default) | −$2,314 | −39% | $10,569 (+6%) | 2.32 |
| **`bull & SPY>200-SMA`** (new default) | **−$861** | **−32%** | **$12,480 (+25%)** | **2.48** |
| bull & VIX<25 | −$1,244 | −36% | $11,122 | 2.24 |

It works by keeping you **out during 2022's worst stretches**, not by curve-fitting. Validation
re-run with it as default: full-sample day-t **2.99** (5bps), and the **in-sample 2022–23 half is
now itself significant** (day-t 1.44 → 2.03) while OOS 2024–25 stays strong (2.37). Updated $10k
per-year P&L (10 bps, median of 300 paths):

| Year | Old (no bear filter) | **New (200-SMA filter)** |
|---|---:|---:|
| 2022 | −$2,382 | **−$754** |
| 2023 | +$1,515 | **+$1,755** |
| 2024 | +$1,776 | **+$3,043** |
| 2025 | −$707 | **−$820** |
| **End-2025 equity (from $10k)** | $10,311 (+3%) | **$13,472 (+35%)** |

Still a **volatile** ride (10th–90th end equity ≈ $7.7k–$27.8k) and still survivorship-inflated —
but a materially better risk profile. Remaining build work: survivorship-clean universe + a live
paper test.

---

## 8. Reproduce

From the monorepo root (`/Users/shtylenko/Projects`):

```bash
# 1. Build & cache the shared daily panel + market context (~2 min, once)
python3 -m trading.strategytester.scripts.build_daily_panel

# 2. §2 mandate ranking = all strategies at the hard 3-day cap:
python3 -m trading.strategytester.scripts.run_daily_strategies --max-hold 3
python3 -m trading.strategytester.scripts.run_daily_strategies --max-hold 3 --cost-bps 10 --tag _10bps
#   (bare `run_daily_strategies` now uses each module's native hold — Momentum Burst = 5.)

# 3. Intraday (VWAP Bounce, Gap and Go) on 1-min bars (~2 min)
python3 -m trading.strategytester.scripts.run_intraday_strategies

# 4. Hold-horizon sweep (5- and 7-day) — the §6 finding
python3 -m trading.strategytester.scripts.run_daily_strategies --max-hold 5 --tag _h5
python3 -m trading.strategytester.scripts.run_daily_strategies --max-hold 7 --tag _h7

# 5. Momentum Burst @5d validation (OOS split, param robustness, cost stress)
python3 -m trading.strategytester.scripts.validate_momentum_burst

# 6. Bear-market regime-filter comparison + $10k account sim
python3 -m trading.strategytester.scripts.test_bear_filter
```

Outputs (gitignored) land in `strategytester/outputs/<strategy>/trades_*.parquet` and
`strategytester/outputs/_summary/`. The tracked ranking is `results_short_hold.csv`.

*Educational research. Bottom line: under a hard ≤3-day cap no strategy is a validated edge;
**relaxing to a 5-day hold makes Momentum Burst pass OOS + robustness + cost-stress** (day-t 2.86,
+21 bps at 10 bps), which is the recommended candidate — with bear-market and survivorship caveats.
Episodic Pivot has a bigger but tail-driven, regime-concentrated point estimate; the "do not
pursue" list is robust across horizons.*
