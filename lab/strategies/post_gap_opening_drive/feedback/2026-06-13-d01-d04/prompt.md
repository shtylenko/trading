# Peer review request: "Post-Gap Opening Drive" intraday strategy (d01–d04)

You are an expert quantitative trading researcher. I'm building a long-only
US-equity intraday strategy and have hit a wall. Below is the **complete**
specification of the current implementation and its full backtest results —
everything you need is in this document; no codebase access required. At the
end I ask you for **at least 10 concrete, testable ideas to improve the logic.**
Please be specific and skeptical.

---

## 1. The environment and hard constraints

- **Account is LONG-ONLY.** No shorting, ever. (Ideas requiring shorts are out.)
- **Instruments:** US common stocks (NYSE/NASDAQ/AMEX/ARCA/BATS).
- **Bars:** regular-hours (09:30–16:00 ET) OHLCV. Default decision/simulation
  granularity is **5-minute** bars. **1-minute** RTH bars are available if a
  strategy opts in. **Extended-hours (premarket/after-hours) 1-minute** bars
  are available if a strategy opts in (currently unused by this family).
  Daily bars (raw/unadjusted) are available for context/filters.
- **Same-day only:** every position is flattened by end of day; no overnight holds.
- **Position sizing:** fixed **1% account risk per trade**. "1R" = the planned
  risk = `|entry_trigger − stop_price|` per share × shares; at 1% risk, **1R ≈ 1%
  of account** (≈ $1,000 on $100k). All performance below is in **R units**, which
  are directly comparable across trades and strategies (dollar-normalized to risk).
  There is a 4× gross leverage cap on position size.
- **Universe — `liquid_pit` (rule-based, point-in-time):** common stocks with
  prior-close ≥ $5 and 20-day median dollar volume ≥ $25,000,000, snapshotted
  quarterly. IMPORTANT CAVEAT: it is built from the *currently-active* asset list,
  so pre-2024 snapshots miss since-delisted names → **survivorship bias; treat
  early-year (2022–2024) results as optimistic upper bounds.**

---

## 2. The strategy thesis

A classic **gap-and-go** / opening-drive momentum play. When a stock *opens
materially above the prior day's entire range* (overnight news: earnings, upgrade,
guidance, sector catalyst), and buyers remain aggressive in the first minutes,
the stock often *continues* to drive higher through the morning. We try to ride
that opening momentum and exit before it fades. (This is a momentum/continuation
bet — the opposite of mean-reversion.)

---

## 3. d01 — the baseline (exact logic)

**Entry candidate selection** (evaluated at the open, per stock):
1. The first regular-hours 5-minute candle (09:30–09:35) must exist.
2. **Gap filter:** `opening_price ≥ prior_day_daily_high × (1 + 0.01)` — i.e. the
   stock opens **≥ 1% above the prior trading day's HIGH** (not just prior close).
3. **Green first candle:** the first 5-min candle closes ≥ its open (buyers in control).
4. **Price filter:** latest daily close ≥ $5. (No relative-volume filter in d01.)
5. Surviving candidates are **ranked by gap size** (largest gap first); the testset
   keeps the top N (N=25 in screening, N=10 in the full eval).

**Signal / order geometry** (all from the FIRST 5-min candle):
- `entry_trigger = first_candle.high`  → a **stop-buy**: fill only if price later
  trades up through the first candle's high (breakout to new high-of-day).
- `stop_price   = first_candle.low`    → exit if price falls back below the candle low.
- `risk_per_share = high − low` (the first candle's range).
- `target_price = entry_trigger + risk_per_share` → a **fixed 1R target** (symmetric
  1:1 reward:risk).
- `exit_cutoff = 11:30 ET` → flatten any still-open position late morning.

Exact candidate/signal code (Python):

```python
# build_candidates: for each ticker with 5m bars
first = first_regular_5m_candle(bars)              # 09:30-09:35 bar
if first is None or daily is None or len(daily) < 2: continue
if not min_price(daily, 5.0, trade_date):          continue   # last close >= $5
if not green_first_candle(bars):                   continue   # close >= open
prior = daily[daily.index.date < trade_date].iloc[-1]         # prior session
gap_pct = (first.open - prior.high) / prior.high * 100.0
if gap_pct < 1.0:                                  continue   # >= 1% above prior HIGH
# score = gap_pct ; rank desc ; testset keeps top N

# build_signal:
high, low = first.high, first.low
risk = high - low
if risk <= 0: return None
entry_trigger = high
stop_price    = low
target_price  = high + risk            # 1R
# exit_cutoff = 11:30 ET
```

---

## 4. d02–d04 — the three one-lever variants

Each changes exactly ONE thing vs d01 (everything else identical), to isolate
the effect:

- **d02 — relative-volume "in-play" filter.** Additional gate: the opening 5-min
  bar's volume must be **≥ 2×** the stock's own 14-session average opening-bar
  (09:30–09:35) volume. Rationale: a gap on quiet volume isn't a real "in-play"
  catalyst. (Removes candidates; everything else as d01.)
- **d03 — uncapped winners.** Remove the 1R target entirely (`target = None`);
  let winners run to the 11:30 cutoff (or the stop). Rationale: gap-and-go is
  tail-driven (a few big runners pay for many small losers); a symmetric 1R cap
  clips exactly that right tail.
- **d04 — full-session hold.** Move the time exit from **11:30 → 15:55 ET** (keep
  the 1R target and the first-candle stop). Rationale: maybe drives keep trending
  into the afternoon.

---

## 5. Simulation & validation methodology (so you can trust/critique the numbers)

**Fill model (conservative, 5-minute bars):**
- The signal is defined on the first 5-min candle; the simulator fills **only on
  bars strictly AFTER the signal bar** (no same-bar look-ahead).
- Stop-buy entry fills at `max(bar_open, trigger)` on the first later bar whose
  high ≥ trigger.
- **Same-bar ambiguity is resolved pessimistically:** if a bar's range spans both
  the stop and the target, the **stop** is assumed hit first. Gap-through the stop
  fills at the bar open (worse than the stop).
- **Costs baked into fills:** entry slippage 2 bps, exit slippage 2 bps, fees
  0.5 bps/side → ≈ **5 bps round-trip** cost. (The d-family stop = the *full*
  first-candle range, which is wide relative to a 5-min bar, so the conservative
  same-bar rule does NOT materially over-state losses here — 1-minute fidelity is
  not required for this family.)
- `realized_R = (exit_price − entry_price) / |entry_trigger − stop_price|`.

**Screening funnel (cheap pre-filter before the expensive eval):**
- `screen_2022_2026_sampled`: a **stratified sample of 108 trading days** — 12
  random days from each of the 9 half-year buckets spanning 2022-H1 … 2026-H1
  (seed 7), `candidate_limit = 25`/day. It's an unbiased estimator of full-period
  behavior at ~11% of the cost.
- **Pre-registered KILL rule:** `sum R < 0` **OR** pooled **sign-flip permutation
  p > 0.5`. Survivors graduate to the full contiguous-year eval gauntlet
  (`eval_2022/2023/2024_h1/2025/2026_h1_broad`, `candidate_limit = 10`).
- **Sign-flip permutation test:** take the per-day total-R series; randomly flip
  the sign of each day's R; recompute the sum; repeat 10,000×. One-sided
  p = fraction of permutations whose sum R ≥ the real sum R. **p ≈ 0.5 ⇒ the
  result is indistinguishable from a coin flip / no edge.**

---

## 6. RESULTS

### 6.1 Screen summary (108-day stratified sample, 2022–2026)

| Rel | Lever | Trades | Sum R | Sign-flip p | Daily R std | Top-5 trades | Sum R **ex-top-5** | Annualized R (95% CI) | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|:--:|
| **d01** | baseline | 1049 | **+4.5** | 0.471 | 4.03R | +5.0R (110% of total) | **−0.5** | +10.5 (−179.5 … +205.6) | **survives** |
| d02 | RV ≥2 filter | 678 | −18.8 | 0.733 | 2.98R | +5.0R | −23.8 | −43.9 (−192.0 … +95.3) | KILL |
| **d03** | uncapped | 1049 | **+5.0** | 0.474 | 5.97R | +24.1R (483% of total) | **−19.1** | +11.7 (−269.8 … +296.4) | **survives** |
| d04 | full session (15:55) | 1095 | −14.6 | 0.639 | 4.14R | +5.0R | −19.6 | −34.0 (−226.6 … +160.3) | KILL |

Notes: d01 and d03 are the only two of these (and the only two across THREE
strategy families we've tested — see §7) to pass the screen's kill rule. But both
have p ≈ 0.47 (essentially a coin flip), and both depend heavily on a few trades.

### 6.2 Per-half-year-bucket R (the critical diagnostic)

| Bucket | d01 | d02 | d03 | d04 |
|---|---:|---:|---:|---:|
| 2022 H1 | −0.9 | 2.3 | 8.3 | −0.2 |
| 2022 H2 | 2.9 | −1.0 | 4.3 | 0.4 |
| 2023 H1 | −7.2 | −9.3 | −0.6 | −13.7 |
| 2023 H2 | −3.8 | −0.2 | −13.0 | −8.5 |
| 2024 H1 | 3.4 | −4.9 | −0.2 | −1.3 |
| 2024 H2 | **−19.6** | −9.0 | **−25.4** | **−18.8** |
| 2025 H1 | −11.3 | 2.0 | −0.5 | −7.8 |
| 2025 H2 | 4.9 | −4.9 | −5.5 | 9.8 |
| **2026 H1** | **+36.1** | +6.2 | **+37.5** | +25.3 |
| **TOTAL** | **+4.5** | −18.8 | **+5.0** | −14.6 |

**Read this carefully:** d01's entire positive result is the **2026-H1 bucket
(+36.1R)**; the other eight buckets (2022–2025) sum to **−31.6R**. Same for d03
(2026-H1 = +37.5R; rest ≈ −32.5R). 2024-H2 is a consistent disaster for everything.

### 6.3 What the variants taught us
- **d02 (RV filter) HURT** (−18.8R): requiring climactic opening volume removed
  trades that were net winners — the filter is anti-selective here.
- **d04 (full-session hold) HURT** (−14.6R): holding past 11:30 gives back gains;
  the opening drive fades by late morning, so the early exit was correct.
- **d03 (uncapped) ≈ d01 in net** (+5.0 vs +4.5R) but with **50% higher daily R
  volatility** (5.97 vs 4.03) and an extreme tail dependence (top-5 = 483% of
  total; the "body" is −19.1R). Uncapping amplified variance without adding net edge.
- **No variant beat the simple d01 baseline.** The basic form is at its frontier;
  the obvious exit/quality levers don't help.

---

## 7. Cross-family context (important for idea quality)

This d-family is the third strategy family tested on the SAME universe, funnel,
and kill rule. The other two were **killed entirely**:
- **Opening-Range Breakout (ORB), 7 releases:** all net-negative. Diagnosed: a
  tight (~0.10×ATR ≈ 32 bps) stop sits inside opening-hour noise → ~90% of
  breakouts get clipped, and fixed ~5 bps costs + slippage are large relative to
  the tiny risk. Widening the stop 3× cut the loss 95% but only reached breakeven
  (no edge underneath). Regime gates (only-trade-when-SPY-green; only-when-SPY-
  ATR-elevated) and a noon time-stop all FAILED or made it worse.
- **Capitulation mean-reversion ("dominance flip"), 5 releases:** all net-negative.
  A 200-day-SMA macro trend filter removed ~95% of the loss (confirmed it was
  catching falling knives) but again only reached **breakeven-by-luck**.

**The dominant cross-family pattern:** across all **18 releases in 3 families
(momentum AND mean-reversion alike), the ONLY consistently positive half-year
bucket is 2026-H1.** A single recent half-year flattering every strategy type is
suspicious — it smells like a **regime peculiarity or a universe/data artifact in
the most-recent `liquid_pit` snapshot** (2026-H1 = Jan–Jun 2026, the freshest,
least-survivorship-biased slice), rather than genuine strategy alpha. Keep this in
mind: an "improvement" that merely amplifies 2026-H1 is probably not real.

**Levers already tried (don't re-propose verbatim):** relative-volume gate,
uncapped/let-winners-run exit, full-session hold, SPY-green-day regime gate, SPY-
ATR-regime gate, fixed time-stop, ATR-based stop widening, RV ranking.

---

## 8. YOUR TASK

Propose **at least 10 distinct, concrete, testable improvement ideas** for the
post-gap-opening-drive logic, respecting the constraints in §1 (long-only,
same-day, 5-min default, `liquid_pit` universe, 1% risk sizing). For **each idea**,
give:

1. **Name & one-line hypothesis** — what edge it tries to capture and *why it
   should work mechanically* (microstructure/behavioral reasoning, not just "try X").
2. **Exact rule change** — the precise, implementable modification (thresholds,
   formulas, which bar/level), so it could be coded as a one-lever variant.
3. **Which weakness it attacks** — tie it to a specific result above (e.g. the
   2024-H2 −19.6R bleed, the tail-dependence, the 1:1 R:R, the entry timing).
4. **Data/inputs required** — does it need premarket/extended bars, intraday 1-min,
   additional daily history, SPY/sector context, fundamentals, etc.?
5. **Expected effect & how you'd falsify it** — what bucket/metric should move, and
   what result would prove it doesn't work.
6. **How it differs** from the already-tried levers in §7.

Then **rank your ideas** by expected impact-to-effort, and call out any that you
think would specifically help diagnose or neutralize the **2026-H1 dependence**
(§6.2, §7) versus merely amplifying it.

Span several dimensions in your set — e.g. **entry quality/selection** (which gaps
to take), **entry timing/trigger** (when/how to get in), **stop placement**,
**exit/target/trade-management**, **regime/market-context filters**, **risk
sizing/portfolio construction**, and **the gap definition itself**. Favor ideas
with a clear economic rationale over parameter tweaks. Be explicit about which
ideas you are *least* confident in and why.
