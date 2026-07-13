# Adversarial Review — Short-Hold Backtest / Episodic Pivot Recommendation

**Reviewer role:** adversarial quant (do not trust prior model)  
**Date:** 2026-07-13  
**Scope:** `REPORT_SHORT_HOLD.md`, `results_short_hold.csv`, shared engine, 13 strategy modules, cached panel + trade logs  
**Question:** Is implementing **Episodic Pivot** justified, or is the edge an artifact of data errors, look-ahead, or overstated significance?

---

## Executive verdict

| Claim from prior report | Independent finding |
|---|---|
| EP: n=876, win 47.0%, **+101.3 bps @5**, +91.2 @10, PF 1.30, t=1.87 | **Confirmed arithmetically** at trade level (re-ran from panel+signals). |
| QMCO +286% and other tail winners are real | **Confirmed** via independent `fetch_bars` under **both** `split` and `raw`. Not adjustment glitches. |
| Engine free of look-ahead; costs signed correctly | **Mostly confirmed** (see minor engine notes). |
| “Only strategy with a positive edge that **survives** costs” as *implement now* | **Not justified at the confidence claimed.** Ranking of *point estimates* is fine; **statistical edge is not established** once cross-sectional dependence and tail concentration are treated honestly. |
| t=1.87 ⇒ meaningful evidence of edge | **Overstated.** Day-equal mean ≈ **−3.5 bps**, t_day ≈ **−0.06**, P(day-mean>0)≈**0.47**. Day-block bootstrap of trade mean: 95% CI **[−13, +224] bps** includes zero. |

### One-line answer

**Do not treat “implement Episodic Pivot” as a validated production recommendation.**  
The backtest is **not** primarily a look-ahead or split-artifact fraud — the code and big winners check out — but the EP “edge” is a **positive-skew lottery**: median trade **negative**, **top 1% of trades ≈ 100% of total PnL**, and **calendar-day clustering kills significance**. Relative ranking among the 13 (EP best point estimate; Inside Bar / Contrarian / VWAP Bounce clearly bad) is directionally fine for *what not to build*.

---

## Headline numbers: confirm or refute

### Independent recompute (from panel + `signals.py`, not prior `metrics.py` alone)

| Strategy | Cost | n | Win% | mean bps | median bps | PF | t (trade-iid) | day-eq mean bps | t (day-eq) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Episodic Pivot** | 5 | 876 | 47.03 | **+101.3** | −44.5 | **1.299** | **1.87** | **−3.5** | **−0.06** |
| Episodic Pivot | 10 | 876 | 46.69 | **+91.2** | −54.5 | 1.265 | 1.69 | −13.5 | −0.23 |
| Momentum Burst | 5 | 23,504 | 44.35 | **+15.8** | −62.7 | 1.071 | **2.75** | +20.0 | 1.50 |
| Inside Bar | 5 | 24,055 | 36.30 | **−44.9** | −123.6 | 0.688 | **−21.77** | −52.6 | −10.1 |
| Overnight 1-night (from saved metrics) | 5 | 145,861 | 45.5 | **−1.2** | — | 0.978 | −1.86 | — | — |
| VWAP Bounce (trade log) | 5 | 58,891 | 36.4 | **−8.9** | −41.7 | 0.71 | −38.0 | −9.3 | −10.1 |
| Contrarian (trade log @10bps on disk) | — | 4,126 | 39.6 | −65.7 | — | 0.73 | −6.4 | — | — |

**Report’s 5 bps table matches a clean re-run.**  
**On-disk `outputs/*/trades_*.parquet` currently store the 10 bps run** (entry/open implies exactly **10.00 bps** cost). That is a pipeline hygiene issue: `--cost-bps 10` overwrote trade files; `daily_metrics.csv` (5 bps) and `daily_metrics_10bps.csv` still agree with recompute.

---

## PRIORITY 1 — Falsify the top conclusion

### 1. Tail winners: real or adjustment artifacts?

**Verdict: REAL moves. Not split artifacts.**

Independently re-fetched OHLC for top trades via `fetch_bars(..., adjustment="split")` and `"raw"`:

| Ticker | Signal → entry → exit | Claimed | Independent (split) | Raw prices | Notes |
|---|---|---:|---:|---|---|
| **QMCO** | 2024-11-21 → 11-22 → 11-26 | +286% | open 4.45 → close 17.23, **~+287%** | **Same** OHLCV (no split in window) | Path: 4.45→9.13→21.77→17.23. Gap day low 3.04 = stop. |
| **HYPD** | 2025-06-03 → 06-04 → 06-06 | +139% | **matches** | matches | Thin: entry-day $vol ≈ **$2.7M** |
| **DXYZ** | 2024-11-06 → 11-07 → 11-11 | +95% | matches | matches | Liquid |
| **ROOT** | 2024-02-22 → 02-23 → 02-27 | +84% | matches | matches | Liquid |
| **PACS** | 2025-11-17 → 11-18 → 11-20 | +70% | matches | matches | OK |
| **CVNA** | 2023-01-31 → 02-01 → 02-03 | +43% | split px ~2.02→2.89 | raw ~10.1→14.45 | **Returns match**; level differs by reverse-split factor. Not an artifact. |

**QMCO specifically:** I re-fetched QMCO; the **+286% move is real** under both adjustments because prices are identical in that window (no corporate action distorting the path). Entry open 4.45 and exit close 17.23 are live market prints, not a restatement glitch.

Panel OHLC for AAPL/QMCO/CVNA/MSFT/TSLA **exact-match** independent `fetch_bars(..., adjustment="split")`.

### 2. Independent expectancy (from scratch)

EP @5 bps (876 trades):

- mean = **+101.3 bps** (report: 101.3)  
- median = **−44.5 bps** (report says −0.5% — **matches**)  
- PF = **1.299** (report 1.30)  
- trade-iid t = **1.87** (report 1.87)  
- drop top **1%** (k=9): mean → **−1.5 bps**, t → −0.04  
- drop top 1 / 5 / 10: **+68.6 / +24.2 / −6.2 bps**

**Tail contribution to total PnL sum:**

| Drop / keep | Share of total Σ pnl | Residual mean |
|---|---:|---:|
| Top 1 trade (QMCO) | **32%** of all strategy PnL | +68.6 bps |
| Top 5 | **76%** | +24.2 bps |
| Top 9 (≈1%) | **101%** | **−1.5 bps** |

Fragility claim in the report is **true and under-emphasized for a “go implement” call**.

Momentum Burst @5: **+15.8 bps**, t=2.75 — matches report. Drop top 1% → **−30 bps**.  
Inside Bar @5: **−44.9 bps**, t=−21.8 — matches; robustly bad.

### 3. Statistical-significance honesty (cross-sectional correlation)

Trades are **not** iid. EP has up to **24 entries on one calendar day** (2024-11-07); mean ~2.2 trades/day.

| Test | EP @5 bps | Interpretation |
|---|---|---|
| Trade-iid t-stat | 1.87 | Marginal; assumes independence (false) |
| Mean of **per-day average** returns | **−3.5 bps**, t=**−0.06** | Equal-weight days: **no edge** |
| P(day-eq mean > 0) bootstrap | **≈0.47** | Coin flip |
| Day-block bootstrap of **trade mean** | 95% CI **[−13, +224] bps**, P>0≈0.95 | Point estimate positive but **CI includes 0** |
| 8-slot day portfolio proxy | +23.6 bps, t≈1.47 | Still **not** conventional significance |

**Severity: BLOCKER for “edge is real / implement with confidence.”**  
The report’s t=1.87 **overstates** confidence. It does disclose marginal t and tail dependence, but still concludes EP is the strategy to implement as the only surviving edge. After clustering, that conclusion does not hold as a *validated* edge — only as “best among a set of mostly negative point estimates.”

Momentum Burst day-eq t≈1.50, block-boot P(mean>0)≈0.89 — also not solid; report correctly calls it fragile.

---

## PRIORITY 2 — Look-ahead / causality

### 4. `common/engine.py` — **PASS (with notes)**

| Check | Result |
|---|---|
| `next_open` / `buy_stop` enter at session **i+1** | Yes (`ei = si + 1`) |
| `signal_close` exposure starts **next** session | Yes (`scan_start = ei + 1`) |
| Exit priority stop → target → time | Yes; unit-checked same-bar stop before target |
| Gap-through at open | Handled when `open <= stop` **after** entry is accepted |
| `buy_stop` same-day low stop | **Conservative** (full-day low can stop a path where stop printed before trigger) |

**Minor / design (not look-ahead):** if `next_open` opens **below** stop, `risk = entry - stop ≤ 0` → trade **skipped** (no loss logged). That is slightly **optimistic** vs “enter and immediately stop at open,” but is defensible as cancel-invalid. Not a ranking-changer.

### 5. `common/indicators.py` — **PASS**

- `rolling_swing_low/high`: at bar `i`, pivot index `p = i - right`, window ends at `i` — **causal** (unit-tested).  
- `ttm_momentum`: window `delta[i-n+1:i+1]` — causal (perturb last bar → past unchanged).  
- `bb_width_min126`, `hh252`: standard rolling, causal on past bars.

### 6. Signals + market filter — **PASS**

- EP: `gap = open[i]/close[i-1]-1` (known at open of i, confirmed by close filters same day); entry `next_open` at i+1.  
- MB: ret/volume at i, entry i+1.  
- `aligned(ctx, df, "spy_bull")`: same-date reindex; SPY 10/20 EMA at close of signal day is known before next open. Default `False` on missing dates is conservative.

---

## PRIORITY 3 — Costs, metrics, data plumbing

### 7. Cost sign — **PASS**

```text
entry = raw * (1 + bps/1e4)
exit  = raw * (1 - bps/1e4)
pnl_pct = exit/entry - 1   # net of costs
```

Verified on trade log: entry/open and close/exit imply **exactly 10 bps** on current parquet files.

### 8. Metrics — **PASS**

- `avg_ret_net = mean(pnl_pct)` ✓  
- `profit_factor = sum(wins)/|sum(losses)|` ✓  
- `t_stat = mean / (std/√n)` with sample std ✓  
- Portfolio: greedy 8-slot, equal weight 1/8, exit-order compounding, no leverage ✓  
- Report correctly treats CAGR/Sharpe as **secondary** (EP portfolio CAGR 12.5%, Sharpe_m 0.51, max DD −35% — noisy).

### 9. Panel integrity — **PASS**

Spot checks AAPL/QMCO/CVNA/MSFT/TSLA: panel OHLCV **exact match** to `fetch_bars(..., "1day", adjustment="split")`. Index: tz-naive, normalized session dates. Gap formula matches `open/close.shift(1)-1`.

### 10. Intraday VWAP — **PASS**

`session_vwap` is cumulative within the bar frame; `run_intraday` groups by day before calling it → **resets each session**. Manual typical-price cumulative matches. Gap uses prior daily close map.

### 11. Universe / survivorship — **MAJOR**

- `liquid_pit` is point-in-time **union** (~1,984 tickers) — report states this.  
- Snapshots show membership churn (`only_early`≈157, `only_late`≈587).  
- **But** panel end-dates: only **1** ticker ends before 2025-06 (CCXI). Almost all series run to 2025-12-31.  
- Interpretation: delisted / failed names are largely **absent from the price panel** (fetch gaps), so the backtest is closer to a **survivors-heavy** cross-section than true PIT with dead names’ terminal losses.

Report says “PIT membership (reduces survivorship)” — **partially true for membership, overstated for return bias**. Failed gap names that went to zero are underrepresented → **optimistic bias** for momentum/EP-style strategies.

**Severity: MAJOR** (does not alone invent EP’s mean, but inflates confidence that the edge is tradable history).

---

## PRIORITY 4 — Reproduce

Re-ran EP / Momentum Burst / Inside Bar from cached panel:

- EP/MB/IB @5 bps match `daily_metrics.csv` / report within rounding.  
- Full script re-run of all 11 daily + intraday not required for the EP conclusion; trade files on disk = 10 bps overwrite (see above).

**Minor pipeline issue:** `run_daily_strategies --cost-bps 10` writes `trades_{name}.parquet` without a cost tag → destroys 5 bps trade logs. Summary CSVs are dual; trade artifacts are not.

---

## Additional material issues (EP-specific)

### A. Edge lives in cheap, explosive names — **MAJOR**

| Filter | n | mean bps | t |
|---|---:|---:|---:|
| All EP | 876 | 101.3 | 1.87 |
| Entry open **≥ $5** | 793 | **50.7** | **1.30** |
| Entry open **≥ $10** | ~79% of trades | **~54** (cohort mean from price split) | weaker |
| Entry $vol ≥ $5M / $10M | 847 / 822 | 101 / 106 | ~1.9 |

Sub-$5 entries: **9.5% of trades**, mean **~585 bps**.  
Top winners include HYPD (~$2 open, thin $vol), QMCO/OPEN/IVVD/CCCC/CVNA at low dollar prices in the split history.  

**5–10 bps/side is optimistic** for these names (spread + impact on gap days). Report lists this as future work; it should have **demoted** the implement recommendation, not just footnoted it.

### B. Stop distance often huge — **MINOR/MAJOR for sizing**

Median risk (open−stop)/open ≈ **8.3%**; 18% of trades have risk >15%. With fixed %-of-equity risk, position sizes shrink — portfolio CAGR in the report assumes equal-weight slots, **not** risk-equalized EP sizing. Secondary metric even noisier for real EP implementation.

### C. Proxy vs doctrine — **disclosed, still important**

EP signal is price/volume only (gap≥10%, relvol≥2, close_pos, SMA50, neglect, spy_bull). No catalyst/news. Report discloses this. Implementing “real EP” is a **different** strategy; current edge may not transfer.

### D. Panel ghosts (split-adjusted microprices)

Unfiltered simulate can emit absurd prices on ancient split-adjusted history (e.g. TNXP entry ~9e5 in warmup). Eval window filter (2022–2025) removes them from metrics. **Minor** if filters stay on; dangerous if someone analyzes raw trade dumps without date filter.

---

## Issue register

| # | Severity | Location | What’s wrong | Changes top pick / ranking? |
|---|---|---|---|---|
| 1 | **BLOCKER** (for “validated edge”) | Report §2–5; `metrics.py` t_stat | Trade-iid t-stat ignores same-day cross-sectional correlation. Day-eq mean **negative**; clustered CI includes 0. | EP remains **best point estimate**, but **not** a proven edge. Implement-as-alpha unjustified. |
| 2 | **BLOCKER**/MAJOR | Report fragility paragraph | Top 1% trades = **all** of EP’s mean; disclosed but incompatible with strong “only surviving edge → implement” language. | Same. |
| 3 | **MAJOR** | EP trade distribution / costs | Edge concentrated in sub-$5 / explosive names; 5–10 bps cost model too kind; open≥$5 mean falls to **~51 bps**, t=1.3. | Weakens EP vs “robust after costs.” |
| 4 | **MAJOR** | `universe.py` + panel | Survivorship: PIT membership claimed; panel almost lacks delists. Optimistic bias. | May inflate all long-momentum variants. |
| 5 | **MINOR** | `run_daily_strategies.py` L74–75 | 10 bps run overwrites trade parquets; disk trades ≠ report’s 5 bps column. | No ranking change if using summary CSVs; confuses audit. |
| 6 | **MINOR** | `engine.py` risk≤0 skip | Gap-through open below stop → skip, not realized stop_gap loss. Slightly optimistic. | Unlikely to reorder EP vs others. |
| 7 | OK | Tail winners / panel OHLC | Not adjustment artifacts. | Supports data integrity. |
| 8 | OK | Look-ahead (engine, indicators, EP/MB, spy_bull) | Causal. | — |
| 9 | OK | Cost sign, PF, portfolio leverage | Correct. | — |
| 10 | OK | Inside Bar / VWAP / Contrarian / overnight 1n | Deeply negative or ~0 after costs — **confirmed**. | “Do not pursue” list stands. |

---

## What the prior model got right

1. Shared engine, causal indicators, correct cost **sign**.  
2. Arithmetic ranking and year table for EP trade-means (all four years positive at trade level).  
3. Tail fragility (drop top 1%) and cost sensitivity structure.  
4. Inside Bar as worst among dailies; mean-reversion / pure overnight premium die after costs — consistent with lab prior.  
5. QMCO-class winners are real market events, not data bugs.

## What it got wrong or oversold

1. **“Edge survives and is the one to implement”** — oversells a **non-significant, tail-lottery** point estimate.  
2. **t=1.87 as supporting evidence** without day-clustering.  
3. **Survivorship comfort** from PIT union without checking panel death dates.  
4. **Cost robustness** without liquidity/price-tier stress (sub-$5 filter halves the edge).  
5. Artifact hygiene: trade logs left at 10 bps while report headlines 5 bps.

---

## Independent EP numbers (side-by-side)

| Metric | Report | This review |
|---|---:|---:|
| n | 876 | 876 |
| win rate @5 | 47.0% | 47.03% |
| mean @5 bps | +101.3 | **+101.3** |
| mean @10 bps | +91.2 | **+91.2** |
| PF @5 | 1.30 | **1.299** |
| t trade-iid @5 | 1.87 | **1.87** |
| median @5 | −0.5% | **−0.445%** |
| drop top 1% mean | “slightly −” | **−1.5 bps** |
| day-eq mean @5 | *(not reported)* | **−3.5 bps**, t=−0.06 |
| day-block 95% CI on trade mean | *(not reported)* | **[−13, +224] bps** |
| mean if entry open ≥ $5 | *(not reported)* | **+50.7 bps**, t=1.30 |

---

## Final recommendation (adversarial)

1. **Do not green-light production capital** on Episodic Pivot based on this study alone.  
2. **Do** keep EP as the **least-bad research candidate** among the 13 for a *longer* hold / catalyst-complete rebuild — if and only if you:  
   - size by risk, not equal weight;  
   - require catalyst + liquidity floors;  
   - report **day-clustered** inference and **tail-truncated** expectancy as primary;  
   - stress costs at 20–50 bps on sub-$10 names;  
   - extend history and include delist returns.  
3. **Do not** reverse the “kill” list for Inside Bar, VWAP Bounce, Contrarian, pure overnight, Gap-and-Go without new evidence — those negatives reproduced cleanly.  
4. Treat Momentum Burst as **second** only in sample size/t-stat theater; it fails years and dies under modest costs — report was fairer here than on EP.

**Bottom line:** The recommendation to implement Episodic Pivot is **not** mainly an artifact of look-ahead or split bugs. It **is** an artifact of **over-interpreting a tail-driven, cross-sectionally dependent, liquidity-fragile mean**. Ranking: EP still tops the *point-estimate* table. Science: **edge not established.**
