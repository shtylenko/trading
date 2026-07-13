# Top 5 Long-Only Swing Strategies Using Finviz Elite — Claude's Proposal

**Author:** Claude (Fable 5, Anthropic)
**Date:** 2026-07-12
**Universe:** US stocks + ETFs (NYSE/NASDAQ/AMEX), long only
**Hold window:** hours → ≤ 10 trading days
**Excluded:** options, futures, shorting, leveraged/inverse ETFs (see S4 note)

**Mandate confirmed with user:**

| Parameter | Setting |
|---|---|
| Account | Margin, ≥ $25k → **no PDT constraint**; same-day exits fully usable |
| Risk per trade | 0.5–1.0% of equity |
| Profile | Balanced (~45–75% win rate depending on sleeve, blended ~2R winners) |
| Style | **Mechanical-first**: exact filter strings, objective triggers/exits, minimal chart discretion, automatable via Elite CSV export / API |
| Source of truth | `swing_screener/library/finviz-help-center.md` |

---

## 0. Honest expectations (read before the strategies)

Three calibration points, so the word "highly profitable" means something:

1. **Screeners select, they don't predict.** Finviz Elite's edge is *speed and breadth of selection* (real-time RelVol, premarket data, custom-period indicators, alerts, export). The profit comes from the trade management wrapped around the selection.
2. **Finviz's own indicator backtests** (help doc, Appendix C) rank RSI, ADX(14)≥40, Ultimate Oscillator, RMI, and MFI as the only indicators that beat benchmark *for longs* — and that test is 1995–2009, no commissions. Treat it as directional evidence for "oversold-in-context and strong-trend filters work for longs," not as a promised return.
3. **External evidence is consistent but modest.** Post-earnings drift is real but weaker once microcaps are excluded (UCLA replication, t-stat 1.43 ex-microcaps; other 2024–25 papers still find ~5% risk-adjusted over 3 months on SUE-sorted portfolios). Connors RSI(2) mean reversion still shows 65–79% win rates in recent backtests but small average wins (~0.5–1% per trade). Sources at the bottom.

**Expectancy target per sleeve** (balanced book):

```
E = W × avgWin(R) − (1−W) × 1R
```

- Mean-reversion sleeves (S2, S4): W ≈ 65–75%, avgWin ≈ 0.7–1.0R → E ≈ +0.2–0.4R/trade, high frequency
- Momentum/event sleeves (S1, S3, S5): W ≈ 40–50%, avgWin ≈ 2–3R → E ≈ +0.3–0.7R/trade, lower frequency

At 0.75% average risk and ~15–25 trades/month across the book, a **good** realistic outcome is **+2–4% per month blended, with 5–10% drawdowns along the way**. Anyone promising more from a screener is selling something.

---

## 1. Shared operating system (applies to all five)

### 1.1 Universe hygiene (always on)

| Filter | Setting | Finviz UI location |
|---|---|---|
| Country | USA | Descriptive |
| Market Cap | +Small (over $300M) | Descriptive |
| Price | Over $10 (S1–S3, S5); ETFs exempt (S4) | Descriptive |
| Average Volume | Over 500K (over 1M for S2/S5) | Descriptive |
| Industry | Stocks only (ex-ETF) for S1–S3, S5; ETFs only for S4 | Descriptive |

Base URL fragment (verify once in UI, then save as preset — the address bar shows the canonical string; the **Elite API accepts the identical `f=` parameters**):

```
geo_usa, cap_smallover, sh_price_o10, sh_avgvol_o500, ind_stocksonly
```

### 1.2 The earnings rule (important Finviz quirk)

Finviz's Earnings Date filter only *selects* dates (Today, Yesterday After Close, Next 5 Days, This Week…); there is **no native "NOT within N days" exclusion**. So:

- **S1 deliberately selects** earnings names — that's the strategy.
- **S2, S3, S4-stock-proxies: never hold a position through an earnings report.** Mechanically: add the **Earnings Date column to a Custom view** (Elite), export it with every scan, and drop any candidate reporting within your intended hold window. If already in a trade, exit by the close before the report. (In an automated pipeline this is one line of filtering on the exported CSV.)

### 1.3 Regime dial (2 minutes, before any scan)

Mechanical, no chart-reading:

| Check | How | Gate |
|---|---|---|
| SPY vs SMA50 / SMA200 | SPY quote page technicals | Defines regime row below |
| Sector leadership | Groups → Sector → sort Perf 1W / 1M | New longs only in top-half sectors (S3/S5 especially) |
| Breadth proxy | Screener: `ta_sma50_pa` count vs total (save both as presets, ratio from result counts) | < 30% above SMA50 = defensive regime |

| Regime | Definition | Active sleeves |
|---|---|---|
| **Bull-quiet** | SPY > SMA50 > SMA200 | S1 S2 S3 S5 full size; S4 as signals occur |
| **Bull-volatile** | SPY > SMA200 but < SMA50 | S1 S4 full; S2 half-size; S3/S5 only A+ triggers |
| **Correction** | SPY < SMA200 | **S4 only, half-size**; everything else flat. Cash is a position |

### 1.4 Position sizing and book limits

```
shares = (equity × risk%) / (entry − stop)
```

| Rule | Limit |
|---|---|
| Risk per trade | 0.5% (S1, S5 — event/fast sleeves), 0.75–1.0% (S2, S3, S4) |
| Max notional per name | 20% of equity (ETFs in S4: 30%) |
| Max concurrent open risk | 3% of equity |
| Max positions | 6 (max 2 per sector; S4 ETF counts as its sector) |
| Liquidity cap | Position ≤ 1% of the name's average daily dollar volume |
| Hard time stop | Every trade has one (per-strategy below); nothing sees day 11 |
| Circuit breaker | −2R realized in a day → no new entries until next session |

### 1.5 The five presets (create once, name exactly)

Elite gives 200 presets; you need 7 (five strategies + two breadth counters). Naming: `SW1_EARNGAP`, `SW2_PULLBACK`, `SW3_BREAKOUT` (+ `SW3_TRIGGER`), `SW4_ETF_MR`, `SW5_PREMKT`.

---

## 2. The five strategies

### Strategy map

| # | Name | Edge type | Hold | Runs at | Freq (est.) | W% / avg win |
|---|---|---|---|---|---|---|
| S1 | Earnings Gap-and-Go (PEAD rider) | Event drift | 1–8 days | 8:30 + evening | 2–6/wk in season | ~45% / 2–2.5R |
| S2 | Leader Pullback (RSI-2 dip) | Trend + mean reversion | 2–5 days | 15:45 or EOD | 3–8/wk | ~65–70% / 0.8–1R |
| S3 | 52-Week-High Base Breakout | Momentum continuation | 3–10 days | weekend + alerts | 1–3/wk | ~40–45% / 2.5–3R |
| S4 | Liquid ETF Oversold Snapback | Index mean reversion | 1–5 days | 15:45 | 2–6/mo | ~70–75% / 0.7–1R |
| S5 | Premarket Catalyst Momentum | Intraday→overnight momentum | hours–3 days | 8:00–9:25 | 2–5/wk | ~45% / 1.5–2R |

Deliberately non-redundant: two mean-reversion sleeves (single-stock vs index-level), two momentum sleeves (multi-day breakout vs same-day catalyst), one event sleeve. Hold durations span the full "hours → 10 days" mandate. S4 is the all-weather sleeve that keeps working when the other four go quiet.

---

### S1 — Earnings Gap-and-Go (PEAD rider)

**Thesis.** Stocks that gap up on a genuine earnings beat tend to keep drifting in the gap direction for days (post-earnings-announcement drift). The gap day itself filters for surprise; relative volume filters for institutional participation. This is the best-documented event edge available to a screener-driven trader, and Finviz Elite is unusually well suited to it: real-time premarket quotes, Earnings Date filter, Gap filter, and the stock page's earnings-surprise history.

**Screen** (`SW1_EARNGAP`) — run **8:30–9:15 ET** and again as an **evening scan** for after-close reporters:

| Filter | Setting | Why |
|---|---|---|
| Earnings Date | Yesterday After Market Close *(morning run)* / Today Before Market Open *(same-morning run)* | The event |
| Gap | Up 4%+ | Real surprise, not noise |
| Price | Over $10 | Base hygiene |
| Average Volume | Over 500K | Exit liquidity |
| Market Cap | +Small (over $300M) | **PEAD ex-microcaps is weaker but cleaner**; microcap drift is mostly untradeable spread |
| Relative Volume | Over 2 (Elite real-time; premarket-adjusted) | Participation confirmation |
| EPS growth qtr/qtr | Positive (secondary check — fundamentals recalc hourly, may lag the report) | Beat quality |

URL fragment: `earningsdate_yesterdayafter, ta_gap_u4, sh_price_o10, sh_avgvol_o500, cap_smallover, sh_relvol_o2` — sort by Relative Volume desc.

**Manual check (2 min/name, still objective):** on the quote page, confirm (a) actual EPS **and** revenue beat (surprise history table), (b) no simultaneous offering/guidance-cut headline in the news column. Skip biotech binary events and gaps > 15% (exhaustion statistics turn against you).

**Entry (mechanical).** Buy stop at the **premarket high**, active 9:35–11:00 only. Not triggered by 11:00 → cancel, name dead. (No PDT constraint, so a failed same-day exit is always available.)

**Risk.**
- Stop: low of the opening range (first 30 min), or entry − 1.25×ATR(14), whichever is tighter. Risk 0.5%.
- If the gap fills intraday (price < prior close), you're out — no exceptions.

**Exits.**
- Sell ½ at +2R.
- Runner: trail at the lower of (3-day low, SMA5). PEAD drift is strongest days 1–5.
- Time stop: close of **day 8**.

**Failure modes.** Gap-and-crap mornings (that's what the OR-low stop is for); crowded mega-cap reports where the move is done in one bar; Fed-day afternoons. Skip entries on FOMC days after 13:30.

---

### S2 — Leader Pullback (RSI-2 dip in an uptrend)

**Thesis.** The classic Connors finding, still the highest-win-rate mechanical long edge in recent backtests: liquid stocks **above their 200-day SMA** that get short-term oversold snap back within days. We restrict it to genuine leaders so we're buying dips in strength, not falling knives. Finviz Elite's **custom-period technical filters** (Aug 2025 feature) let you screen RSI(2) directly — this is the strategy that most benefits from Elite vs free.

**Screen** (`SW2_PULLBACK`) — run **15:30–15:50 ET** (enter same close; real-time Elite makes this valid) or EOD for next-morning limit orders:

| Filter | Setting | Why |
|---|---|---|
| Market Cap | +Mid (over $2B) | Mean reversion works best in institutional names |
| Price | Over $20 | Spread/noise control |
| Average Volume | Over 1M | You will exit into strength; make it cheap |
| SMA200 | Price above SMA200 | The non-negotiable trend gate |
| SMA50 | Price above SMA50 | Leader, not laggard |
| **RSI(2), daily** | **Below 10** (Elite custom technical filter) | The trigger |
| *(fallback if custom filter unavailable)* | RSI(14) below 40 + Perf Week down | Same idea, blunter |
| Performance Half Year | Over 10% | Confirms "leader" |

URL fragment (fallback form): `cap_midover, sh_price_o20, sh_avgvol_o1000, ta_sma200_pa, ta_sma50_pa, ta_rsi_os40` + custom RSI(2)<10 added via Elite "+ Filter". Sort by Perf Half-Year desc, take top 5 max.

**Earnings gate:** drop anything reporting within 6 trading days (custom-view Earnings Date column).

**Entry (mechanical).** Buy at the close of the signal day (15:55 market-on-close), **or** next-day limit at signal close − 0.3×ATR(14) for a better fill (accept ~40% no-fill rate).

**Risk.** Mean reversion dies by a thousand tight stops — the exit is time- and signal-based, the stop is a disaster stop:
- Disaster stop: entry − 2×ATR(14) (or −8%, whichever is tighter). Size at 0.75% risk **to that stop**.

**Exits.**
- Primary: first close with RSI(2) > 65, or first close above SMA5 — whichever comes first. Typically day 2–4.
- Scale rule: if RSI(2) < 5 on day 2 and SPY regime is still bull, one add of half-size is allowed (total risk ≤ 1.1%).
- Time stop: close of **day 5**. No bounce in five days = thesis wrong.

**Failure modes.** The filter's blind spot is stock-specific bad news masquerading as a dip — the 2-minute news-column check on the quote page is mandatory. Halve size in bull-volatile regime; flat in correction regime (single-stock mean reversion below SMA200 is where accounts die).

---

### S3 — 52-Week-High Base Breakout

**Thesis.** Stocks consolidating within 10% of a 52-week high, that then break out **on expanding relative volume**, continue — the 52-week-high momentum effect plus volume confirmation. This is the slowest, highest-R sleeve. It's built as a two-stage machine: a weekend watchlist screen and an intraday trigger screen wired to **Finviz screener alerts** so the breakout comes to you.

**Stage 1 — Watchlist screen** (`SW3_BREAKOUT`), run **weekend/evening**:

| Filter | Setting | Why |
|---|---|---|
| Market Cap | +Small (over $300M) | Room to allow mid-cap leaders |
| Price | Over $10 | Hygiene |
| Average Volume | Over 500K | Hygiene |
| 52-Week High/Low | 0–10% below High | The base, near highs |
| SMA50 / SMA200 | Price above both | Trend stack |
| Performance Half Year | Over 30% | Momentum leadership |
| Volatility Month | Under 4% *(tightness proxy)* | Coil, not a rollercoaster |
| Float | Under 100M (preference, not gate) | Faster continuation |

URL fragment: `cap_smallover, sh_price_o10, sh_avgvol_o500, ta_highlow52w_b0to10h, ta_sma50_pa, ta_sma200_pa` + Perf/Volatility from dropdowns. Switch to **Charts view** (Elite: 120/page), keep only clean flat bases: 2–6 weeks sideways, contracting range, no earnings inside the next 10 days. Watchlist = 5–15 names, each with a written trigger price (the base high).

**Stage 2 — Trigger.** Two redundant mechanisms:
1. **Finviz price alerts** on each watchlist name at trigger − 1%.
2. Intraday trigger screen (`SW3_TRIGGER`): your watchlist tickers + `ta_highlow52w_nh, sh_relvol_o1.5` with a **screener alert** — Finviz notifies when a name *enters* the saved screen (new 52-week high on ≥1.5× relative volume).

**Entry (mechanical).** Buy stop at base high + 0.2%. Valid only if RelVol ≥ 1.5 at trigger time (real-time column). No volume = no trade, alert or not.

**Risk.** Stop below the breakout day's low or entry − 1.5×ATR(14), whichever is tighter. Risk 0.75–1%.

**Exits.**
- Sell ⅓ at +2R.
- Trail remainder at SMA10 close-basis (or 5-day low — pick one, keep it fixed for 30 trades before judging).
- Time stop: close of **day 10** (the mandate's edge). A breakout that goes nowhere for two weeks is dead momentum.

**Failure modes.** Buying breakouts in a weak tape (regime gate handles this — S3 is off below SMA50); low-volume fakeouts (RelVol gate); extended entries (never chase > 3% past trigger — cancel and wait for the retest or drop it).

---

### S4 — Liquid ETF Oversold Snapback (the all-weather sleeve)

**Thesis.** Index-level short-term mean reversion is the most persistent version of the RSI(2) effect — broad ETFs above their SMA200 that flush to RSI(2) < 10 bounce with 70%+ historical win rates. No earnings risk, no single-stock news risk, effectively unlimited capacity, and it produces signals exactly when the stock sleeves go quiet (pullbacks/panics). This is the sleeve that keeps the book earning in chop.

**Universe (fixed list, no discovery needed):** SPY, QQQ, IWM, DIA + the 11 SPDR sectors (XLK XLF XLV XLE XLI XLY XLP XLU XLB XLRE XLC) + SMH, XBI, ITB, KRE. **Unleveraged only** — no 2x/3x (volatility drag turns a mean-reversion edge into a decay bet). Maintain it as a Finviz **portfolio** so the screen below runs against it.

**Screen** (`SW4_ETF_MR`) — run **15:30–15:50 ET**:

| Filter | Setting | Why |
|---|---|---|
| Industry | Exchange Traded Fund | ETF universe |
| Asset/Type (Elite ETF filters) | Equity, non-leveraged; AUM over $1B | Quality + capacity |
| Average Volume | Over 1M | Hygiene |
| SMA200 | Price above SMA200 | Trend gate |
| **RSI(2), daily** | Below 10 (Elite custom filter; fallback RSI(14) below 30) | Trigger |

Cross-check against the fixed list; anything outside it is ignored (the ETF screener will surface exotica — don't trade it).

**Entry (mechanical).** Market-on-close on the signal day. If RSI(2) < 5 at the next day's close, add a second half-unit (planned scale-in, not averaging down ad hoc).

**Risk.** Disaster stop − 1.5×ATR(14) (≈ 3–5% on sector ETFs). Size at 1% total risk across both units. Index ETFs gap small; this is the one sleeve where a wider soft stop is statistically justified.

**Exits.**
- Primary: first close with RSI(2) > 65 or first close above SMA5. Typically day 1–4.
- Time stop: close of **day 5**.

**Failure modes.** Trend changes disguised as dips — the SMA200 gate is the defense; in correction regime this sleeve stays on but at **half size**, and only on SPY/QQQ (sector ETFs below SMA200 are excluded by the gate anyway). Expect the occasional −1.5R loser in a waterfall; the 70%+ win rate pays for it.

---

### S5 — Premarket Catalyst Momentum (the "hours" sleeve)

**Thesis.** A stock gapping on a real non-earnings catalyst (FDA news, contract win, guidance raise, analyst upgrade) with heavy premarket volume tends to continue after the open if it holds its opening range. With ≥ $25k margin there's no PDT constraint, so this sleeve fully exploits the "hours" end of the mandate: paid same day when it works fast, held 1–3 days when it trends. Finviz Elite's real-time **premarket screening (from 4:00 ET)** and intraday screener timeframes are the enabling features.

**Screen** (`SW5_PREMKT`) — run **8:00–9:25 ET** with real-time data:

| Filter | Setting | Why |
|---|---|---|
| Change / Gap | Up 5%+ premarket | The move |
| Signal cross-check | Top Gainers + Unusual Volume signals | Confirmation lists |
| Price | Over $10 | Skip the pump-zone |
| Market Cap | +Small (over $300M) | Balanced profile — no nano-float lottery tickets |
| Average Volume | Over 1M | Someone must be on the other side of your exit |
| Relative Volume | Over 3 | Serious premarket participation |
| News check | Major News signal / quote-page headline | **Named catalyst required** — no news = no trade |
| Earnings Date | NOT today/yesterday (those belong to S1) | Keeps sleeves non-overlapping |

URL fragment: `sh_price_o10, cap_smallover, sh_avgvol_o1000, sh_relvol_o3` + Top Gainers signal (`s=ta_topgainers`), sort by Change desc. Shortlist ≤ 3 names by 9:20 with premarket high/low marked.

**Entry (mechanical).** Opening-range breakout: buy stop at the **5-minute opening-range high**, active 9:35–10:30. Require price above VWAP at trigger (Elite intraday chart overlay). Not triggered by 10:30 → cancel.

**Risk.** Stop = OR low, or VWAP − 0.5×ATR(5m), whichever is tighter. Risk **0.5%** (this sleeve has the fattest left tail). One entry per name per day; max 2 S5 positions simultaneously.

**Exits.**
- Sell ½ at +1.5R (often within the first hour).
- Runner: hold **overnight only if** the close is in the top 25% of the day's range **and** closing RelVol ≥ 2. Otherwise flat by 15:55.
- Overnight runner: trail at prior-day low; time stop close of **day 3**.

**Failure modes.** Fade-at-open reversals (the 9:35 wait + OR structure is the defense); chasing extended (never enter > 2% above OR high); no-catalyst sympathy movers (the named-catalyst rule); low-float squeezes that halt (the $300M cap floor and $10 price floor remove most).

---

## 3. Weekly rhythm (time-boxed)

| When | What | Sleeves |
|---|---|---|
| Sunday, 45 min | Regime dial; run SW3 watchlist; set week's alert grid; review open journal | S3, book |
| Daily 8:00–9:25 | SW5 premarket scan; SW1 morning run (in season) | S1, S5 |
| Daily 9:35–10:30 | Execute pending S1/S5 triggers; nothing else | S1, S5 |
| Daily 15:30–15:55 | SW2 + SW4 scans; MOC entries; earnings-window check on all open positions | S2, S4 |
| Evening, 15 min | SW1 after-close reporters for tomorrow; journal fills; export CSVs (below) | S1, book |

Total: ~1.5 focused hours per day plus Sunday. If a day's slot is missed, that day's signals are skipped — never entered late.

---

## 4. Automation path (this is a `swing_screener` project, after all)

1. **Presets + alerts first.** All seven presets saved in Elite; screener alerts on `SW3_TRIGGER`; price alerts on the S3 watchlist. This alone makes the system run on ~90 min/day.
2. **Daily export cron.** Finviz **does not offer historical screener data** (help doc §1) — whatever you don't save is gone. From day one, hit the Elite export API (same `f=` filter strings as the UI URLs) for all five screens + the two breadth counters after each scheduled run and archive to something like `swing_screener/data/finviz/{screen}/{YYYY-MM-DD}.csv`. Within months you own a **point-in-time candidate dataset** that Finviz itself cannot sell you — and the lab's funnel can then backtest *these exact screens* instead of approximations.
3. **Journal as data.** Log per trade: strategy ID, signal date, entry/stop/exit, R result, regime state, and screen-rank of the candidate. Per-strategy expectancy is the only number that decides anything (see §5).
4. **Later:** entry/exit automation through the broker API with Finviz as the signal layer. Not needed to start; the edges here survive manual execution.

**Caveat on URL codes:** the `f=` fragments above follow Finviz's standard conventions (`cap_midover`, `ta_sma200_pa`, `sh_relvol_o2`, `earningsdate_yesterdayafter`, …) but a few codes (performance buckets, ETF-specific filters, custom-period indicators) should be captured from the address bar after building each screen once in the UI. The UI URL is the canonical spec; the API consumes the same string.

---

## 5. Measurement and kill criteria

| Rule | Threshold |
|---|---|
| Minimum evaluation sample | 30 trades per strategy before any rule change |
| Strategy pause | Rolling 20-trade P&L < −8R → sleeve to half size; < −12R → sleeve off, post-mortem |
| Book pause | Account drawdown 8% from high-water mark → everything to half size; 12% → flat, full review |
| Review cadence | Monthly: per-sleeve W%, avg win/loss R, expectancy, regime attribution |
| Rule changes | Written, dated, and only at review time — never mid-drawdown |

The most likely real-world failure is not any single screen being wrong — it's sleeve discipline eroding (S5 trades taken at 11:40, S2 dips bought below the SMA200, stops widened "just this once"). The kill criteria exist to make that visible in R terms before it's visible in the account balance.

---

## 6. Convergence note (vs `grok_top5_long_swing.md`)

Per the agreed protocol I chose my five independently, then compared. The overlap is substantial — and that's signal, not redundancy: **uptrend pullback, volume-confirmed breakout near highs, trend-filtered oversold reversion, and catalyst gap continuation are the four edges any competent analysis of a screener-driven, long-only, ≤10-day mandate lands on.**

Material differences worth noting when you reconcile the two files:

| Topic | Grok | This proposal |
|---|---|---|
| Account assumption | Under $25k, PDT-constrained | **≥ $25k margin** (your updated answer) — same-day exits are unrestricted, which S1/S5 exploit |
| Earnings events | Generic gap continuation | **Earnings-specific PEAD sleeve** with multi-day drift hold, separated from non-earnings catalysts (S5) |
| ETF sleeve | Sector-leadership/flow momentum | **Oversold snapback** — deliberately anti-correlated with the momentum sleeves; fires in chop when they're silent |
| Oversold trigger | RSI(14) < 30 | **RSI(2) < 10 via Elite custom-period filters** — sharper, better-evidenced trigger the Elite tier specifically enables |
| Operations | Evening-scan centric | Alert-driven triggers (screener alerts on SW3) + **daily CSV archiving to build a point-in-time dataset** for the lab to backtest |

If you want a combined book later, the natural merge is: my S1/S2/S4/S5 + Grok's sector-leadership sleeve as a sixth, since ETF-flow momentum is the one edge type my five don't cover.

---

## Sources

- `swing_screener/library/finviz-help-center.md` — filter/signal inventory, Elite features (real-time premarket, custom-period technical filters, ETF filters, screener alerts, export/API), §24 practitioner workflows, Appendix C indicator backtests (1995–2009 caveat noted).
- [UCLA Anderson Review — Is Post-Earnings Announcement Drift a Thing? Again?](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/) — PEAD weak ex-microcaps in 2001–2024 replication.
- [Alpha Architect — New Facts on Post-Earnings Announcement Drift](https://alphaarchitect.com/new-facts-for-post-earnings-announcement-drift/) and [Wikipedia — Post-earnings-announcement drift](https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift) — the effect and its academic history.
- [QuantifiedStrategies — RSI 2 Strategy: Larry Connors' 2-Period RSI Rules](https://www.quantifiedstrategies.com/rsi-2-strategy/) and [StratBase — RSI(2) Strategy](https://stratbase.ai/en/blog/rsi-2-strategy-larry-connors) — recent RSI(2) win-rate/expectancy evidence and the SMA200 filter effect.
- [DayTrading.com — PEAD Trading Strategy](https://www.daytrading.com/post-earnings-announcement-drift-pead-strategy) — practitioner implementation notes.

*This document is a research proposal, not financial advice. Every number labeled "expected" is an estimate to be validated against your own journal and the archived screen exports — not a promise.*
