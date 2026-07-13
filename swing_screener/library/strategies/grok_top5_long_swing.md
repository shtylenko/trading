# Top 5 Long-Only Swing Strategies Using Finviz Elite

**Author:** Grok (xAI)  
**Date:** 2026-07-12  
**Universe:** US stocks + ETFs, long only  
**Hold window:** hours → ≤ 10 trading days  
**No:** options, futures, shorting  

**Account assumptions (from you):**
| Parameter | Setting |
|-----------|---------|
| Capital | Under $25k |
| Risk per trade | 0.5–1.0% of equity |
| Profile | Balanced (~45–55% win rate, ~2R targets) |
| Workflow | Mix of EOD evening scans + premarket/same-day swings |
| Liquidity floor | Price ≥ $5, avg volume ≥ 300K–500K, market cap ≥ $300M (quality small-cap allowed) |
| Style mix | Diversified edges, realistic risk rules |

**Primary source:** `swing_screener/library/finviz-help-center.md` (Elite screener, signals, maps/groups, ETF filters, alerts, premarket).  
**Design goal:** five *different* edges that can coexist in one book, each implementable end-to-end with Finviz Elite alone (plus your broker for execution).

---

## Important realism note (read first)

No Finviz screen “prints money.” Elite gives **selection power + timing data** (real-time, RelVol, gaps, fund flows, maps, alerts). Profitability comes from:

1. **Hard risk rules** (stop, max hold, max concurrent risk)  
2. **Market regime filter** (trade *with* the tape when possible)  
3. **Volume confirmation** (RelVol is the swing trader’s best single filter)  
4. **Skipping** earnings landmines and extended names  

Expectancy framing used below (balanced book):

\[
E = (W \times R) - (1-W) \times 1R
\]

With ~50% win rate and average winner ≈ 2R: \(E \approx +0.5R\) per trade before friction. At 0.75% risk on a $20k account, that is ~$75 theoretical edge *per trade* if rules are followed — not per day, and not without drawdowns.

**Sub-$25k constraint:** prefer names where your full position is ≤ ~1–2% of average daily dollar volume so exits don’t slip badly. Rule of thumb:

\[
\text{Max position \$} \approx 0.01 \times \text{Price} \times \text{Avg Volume}
\]

If avg volume is 500K at $20 → ~$100k ADV; 1% of ADV = $1k position — fine for a small account. Skip thin names even if the chart is pretty.

---

## Shared operating system (applies to all five)

### Core universe filters (always on unless noted)

| Filter | Setting | Why |
|--------|---------|-----|
| Country | USA | Clean US listings |
| Market Cap | +Small (over $300M) | Avoid nano junk; allow quality small-cap |
| Price | Over $5 (prefer Over $10 for strategies 1–2, 5) | Less noise / wider spreads under $5 |
| Average Volume | Over 300K (prefer Over 500K) | Liquidity for multi-day holds |
| Float | Under 100M when available/relevant | Faster movers for small accounts |
| Earnings Date | Not this week (hard rule for holds ≥ 1 day) | Gap risk is not optional risk |

### Position sizing (0.5–1% risk)

\[
\text{Shares} = \frac{\text{Account equity} \times \text{risk\%}}{\text{Entry} - \text{Stop}}
\]

Example: $20,000 × 0.75% = $150 risk. Entry $48, stop $45 → $3 risk/share → **50 shares** (~$2,400 notional ≈ 12% of account). Cap single-name notional at **15–20% of equity** even if stop is tight.

### Portfolio risk budget

| Rule | Limit |
|------|-------|
| Max concurrent open risk | 3–4% of equity total (e.g. 4 × 0.75% or 3 × 1%) |
| Max correlated theme | 2 positions in same sector/industry |
| Max open trades | 3–5 (small account attention limit) |
| Hard time stop | Exit by close of day **10** (or earlier if thesis dead) |
| Daily loss circuit breaker | Stop new entries after −2R day |

### Market regime filter (Maps + Groups — Elite real-time)

Before scanning names:

1. Open **Maps** (sector/industry heat). Prefer long setups when **SPY/QQQ trend is up** or at least not in a multi-day waterfall.  
2. Prefer candidates in **green / leading sectors** on the map.  
3. Use **Groups** performance (1W / 1M) to confirm leadership.  
4. In broad risk-off (most sectors red, VIX spike, indexes below SMA50):  
   - Prefer Strategy 3 only on quality names above SMA200, or  
   - Prefer Strategy 5 liquid sector ETFs that *are* holding up, or  
   - Sit in cash (valid edge).

### Elite tools you will actually use

| Tool | Use |
|------|-----|
| Screener presets (Elite: 200) | One preset per strategy |
| Charts view (up to 120) | Kill messy structure fast |
| Signals: Unusual Volume, New High, Oversold, Major News, Insider Buying | Catalyst / confirmation layer |
| Premarket / after-hours quotes | Strategy 4 |
| Alerts (price, news, screener) | Hands-off entry triggers |
| ETF filters: Net Fund Flows, AUM, Category | Strategy 5 |
| Correlated stocks | Avoid stacking the same bet |
| Export CSV | Optional trade journal backlog |

### Default R-multiple exits (balanced)

| Outcome | Action |
|---------|--------|
| +1R | Optional: sell 1/3–1/2, move stop to breakeven |
| +2R | Default full exit (core target) |
| Runner (only Strategies 1 & 2) | Trail under prior day low or SMA20; still hard-exit by day 10 |
| Stop hit | Exit; no revenge re-entry same day |
| Thesis break (support fails, RelVol dies, sector flips) | Exit even if stop not hit |

---

## Strategy map (why these five)

| # | Strategy | Edge type | Typical hold | Best regime | Primary Finviz levers |
|---|----------|-----------|--------------|-------------|------------------------|
| 1 | Uptrend Pullback Continuation | Trend + mean reversion to MA | 2–7 days | Bull / quiet uptrend | SMA, RSI 40–55, Perf Week down, RelVol |
| 2 | High-Tight Momentum Breakout | Momentum / expansion | 1–5 days | Strong bull, risk-on | New High, RelVol, SMA stack, Perf |
| 3 | Trend-Filtered Oversold Bounce | Mean reversion | 1–5 days | After sharp selloff in bull | RSI < 30, Oversold, SMA200, RelVol |
| 4 | Premarket Gap Continuation | Catalyst / event drift | Hours–3 days | Any, news-driven | Gap, Unusual Volume, premarket, News |
| 5 | Sector Leadership ETF / Proxy Swing | Relative strength / flow | 2–8 days | Rotation markets | Maps, Groups, ETF fund flows, Perf |

These are deliberately **non-redundant**: pullback ≠ chase breakout ≠ bounce ≠ gap ≠ sector flow.

---

# Strategy 1 — Uptrend Pullback Continuation  
### “Buy strength on sale”

### Thesis
Stocks already in a confirmed intermediate uptrend often pull back for 2–5 sessions on *declining* volume, then resume. Entering on the pullback (not the spike) improves R-multiple vs chasing highs. This is the highest-quality **core** swing edge for a small account.

### Why Finviz is enough
SMA20/50/200 position, RSI band, weekly performance, RelVol, and Charts view implement the classic “uptrend + pullback + volume dry-up” checklist documented in the Finviz swing section.

### Screener preset: `S1_Pullback_Uptrend`

| Filter | Setting | Reason |
|--------|---------|--------|
| Market Cap | Over $300M (prefer Mid+) | Quality floor |
| Price | Over $10 | Cleaner swings |
| Average Volume | Over 500K | Liquidity |
| SMA20 | Price above SMA20 | Short-term structure intact *or* just tagging it — see note |
| SMA50 | Price above SMA50 | Medium-term uptrend |
| SMA200 | Price above SMA200 | Long-term bullish regime for the name |
| RSI (14) | 40–55 | Pulled back, not broken |
| Performance Week | Down *or* −5% to 0% if available | Recent weakness inside strength |
| Performance Month | Up *or* Over +5% | Larger trend still up |
| Relative Volume | Under 1.2 on pullback days (scan EOD) | Prefer quiet pullbacks; entry day may expand |
| EPS Growth This Year | Positive / Over 10% (optional quality) | Fundamental wind at back |
| Analyst Rec | — | Optional; avoid Strong Sell pile-ups |

**Note on SMA20:** On the *scan evening*, many ideal names sit **near** SMA20/50. If Finviz only offers “Price above SMA20,” keep it; visually require touch/approach of SMA20 or SMA50 within ~3%.

**Sort:** Performance Month descending, then RSI ascending (deeper pullback first among strong names).

### Chart review checklist (Charts view → ticker page)

- Weekly chart: higher highs / higher lows intact  
- Daily: orderly pullback (not a gap-crash), volume **contracts** into the low  
- Distance from SMA50: ideally **not** >15–20% extended before the pullback  
- Clear horizontal support or rising trendline  
- **No earnings** in next 5–7 trading days  
- Sector on Maps is neutral-to-green  

### Entry (mix of EOD plan + next-day execution)

| Mode | Trigger |
|------|---------|
| **Preferred** | Buy stop 1–2% above prior day high *after* a bullish reversal day (hammer / engulfing / wide-range up) at support |
| **Aggressive** | Limit near SMA50 / prior support if volume still declining and RSI holds >40 |
| **Invalid** | Closes below SMA50 on expanding volume |

### Stop / target / time

| Parameter | Rule |
|-----------|------|
| Stop | Below pullback swing low, or 1×ATR below support (use ATR column/view) |
| Target | Prior swing high first; scale at +2R; optional trail under SMA20 |
| Max hold | 7 trading days (extend to 10 only if still above entry MA and sector strong) |
| Expected R | 1.5–2.5R typical |

### Failure modes

- “Pullback” is actually distribution (volume **rises** into the low)  
- Market regime flips risk-off mid-hold → respect stop, don’t average  
- RSI < 35 and still falling → wait for Strategy 3 rules instead  

### Example risk (illustration only)

Equity $20k, risk 0.75% = $150. Entry $62, stop $59.50 ($2.50) → 60 shares. Target prior high $67 → ~1.8R; take full or scale.

---

# Strategy 2 — High-Tight Momentum Breakout  
### “Institutional expansion, not random noise”

### Thesis
When a liquid name in an uptrend compresses, then breaks a range or 52-week high on **elevated RelVol**, short-term trend followers and funds add risk. Many breakouts fail (~half+); edge comes from **volume filter + tight stop under the range + fast time stop**.

### Why Finviz is enough
Signals: **New High**, **Unusual Volume**, **Top Gainers**; filters: SMA stack, RelVol, volatility/range, pattern (Channel Up / Horizontal / Triangle if available).

### Screener preset: `S2_Mom_Breakout`

| Filter | Setting | Reason |
|--------|---------|--------|
| Market Cap | Over $300M | Avoid death-by-spread |
| Price | Over $10 | Prefer cleaner momentum |
| Average Volume | Over 500K (1M+ ideal) | Institutional-capable liquidity |
| SMA20 | Price above SMA20 | Momentum alignment |
| SMA50 | Price above SMA50 | Trend |
| SMA200 | Price above SMA200 | Bullish backdrop |
| RSI (14) | 50–70 | Trending, not yet absurd (skip >75–80 for *new* entries) |
| Performance Week | Up | Short-term thrust |
| Performance Month | Up / Over +10% | Established momentum |
| Relative Volume | Over 1.5 (Over 2.0 preferred on trigger day) | Real participation |
| 20-Day High/Low | Near high *or* New High signal | Breakout context |
| Float | Under 50–100M when possible | Torque for small accounts |

**Alternate signal path (same day):** Signal = **New High** or **Unusual Volume**, then apply SMA + price + volume filters.

**Sort:** Relative Volume descending.

### Chart review

- Prior 5–15 days: **tight coil / flag / flat base** (Strategy 2 loves compression *before* expansion)  
- Breakout day: range expands **up**, closes in upper third of the day  
- RelVol ≥ 1.5–2.0; prefer multi-day buildup of interest  
- Not already +25% above SMA50 without a base (too extended)  
- Sector leadership on Maps  
- Avoid first green day after a multi-month collapse (that’s Strategy 3 / trap territory)

### Entry

| Mode | Trigger |
|------|---------|
| **EOD plan** | Identify resistance / 52w high; buy stop 0.5–1.5% above level for next session |
| **Intraday (Elite)** | Once level breaks with RelVol expanding and price holds above VWAP/opening range high 15–30+ min |
| **Skip** | Breakout on RelVol < 1.2, or wide spread open that never holds |

### Stop / target / time

| Parameter | Rule |
|-----------|------|
| Stop | Below coil/flag low, or breakout-day low (whichever is tighter *and* ≥ 0.8R sensible distance) |
| If stop would be > 6–8% from entry | Pass — too wide for 0.5–1% risk sizing on small account |
| Target | +2R default; partial at measured move (base height) |
| Time stop | If not +1R within **3** sessions, tighten stop to breakeven or exit |
| Max hold | 5–7 days (10 only if strong trend continuation) |

### Failure modes

- Bull trap: breaks high, closes back inside range → exit on close back inside  
- Earnings/news gap against you next morning → honor stop; no “it’ll fill”  
- Chasing midday +8% extensions — wait for first orderly pullback (hand off to Strategy 1)

---

# Strategy 3 — Trend-Filtered Oversold Bounce  
### “Panic in a bull structure”

### Thesis
Short-term oversold conditions (RSI) mean-revert often on liquid US equities, especially when the **longer-term trend is still up** (price above SMA200). Finviz’s own historical indicator ranking places **RSI** among the best long-biased tools on multi-day holds; pure catch-a-falling-knife without a trend filter is much weaker.

### Why Finviz is enough
**Oversold** signal, RSI(14) filter, Performance Month down, RelVol, SMA200, optional hammer-like structure via Charts, **Recent Insider Buying** as soft confirmation.

### Screener preset: `S3_Oversold_TrendFilter`

| Filter | Setting | Reason |
|--------|---------|--------|
| Price | Over $5 | Floor |
| Average Volume | Over 300K (500K better) | Exit liquidity on bounce |
| Market Cap | Over $300M | Quality |
| RSI (14) | Oversold / under 30 | Primary signal |
| Performance Month | Down | Confirms genuine pressure |
| SMA200 | Price above SMA200 | **Critical** trend filter |
| Relative Volume | Over 1.0 (prefer >1.5 on capitulation day) | Forced selling / climax often prints volume |
| Beta | Over 1.0 (optional) | Larger bounce amplitude |
| Short Float | Over 5% (optional fuel) | Squeeze assist — not required |

**Signal shortcut:** Signal = **Oversold**, then force SMA200 above + liquidity filters.

**Sort:** RSI ascending, then RelVol descending.

### Chart review

- Locate **prior support** (prior swing low, gap fill, horizontal shelf)  
- Prefer **capitulation**: wide-range down day then reversal candle, or positive RSI divergence if you eyeball it  
- Avoid names in structural downtrends (lower lows on weekly) even if RSI < 30  
- Prefer sector not in freefall on Maps (or bounce with sector turn)  
- Fundamental death (fraud, secondary, continuous guidance cuts): skip  

### Entry

| Mode | Trigger |
|------|---------|
| **Conservative (recommended)** | Wait for **confirmation**: next-day higher low + reclaim of prior day mid/high, or close back above SMA20 |
| **Aggressive** | Buy near support on hammer/engulfing with RelVol > 1.5 **only** if SMA200 holds |
| **Never** | Market-on-close into a free-fall with no level |

### Stop / target / time

| Parameter | Rule |
|-----------|------|
| Stop | Below capitulation day low / support (hard invalidation) |
| Target 1 | SMA20 |
| Target 2 | SMA50 or +2R (take majority off) |
| Max hold | **5** trading days default (mean reversion decays); absolute 10 |
| Do not pyramid | One unit only — this edge dies if you average down |

### Failure modes

- RSI oversold in a **breakdown** below SMA200 → different market; skip or wait for reclaim  
- Bounce fails at SMA20 with volume → exit; failed bounce often continues lower  
- Holding through earnings “because it’s oversold” → forbidden  

### Expectancy notes
Win rate can run **higher** than Strategy 2, but average winner is often **smaller** (fade into SMA20). Still aim for **≥1.5–2R** by requiring tight stops under a clear low — if stop is mushy, pass.

---

# Strategy 4 — Premarket Gap Continuation  
### “Elite real-time edge: hours to few days”

### Thesis
Gaps reflect overnight information. When a stock gaps **up** on clear catalyst + **unusual premarket volume**, and then **holds the gap / opens and goes**, momentum often persists into the regular session and 1–3 follow-through days. This is your **hours-to-days** sleeve — not a 2-week position thesis.

### Why Finviz Elite specifically
- Premarket quotes **4:00–9:30 ET**  
- Real-time RelVol / volume  
- Signals: **Major News**, **Earnings Before**, **Unusual Volume**, **Top Gainers**  
- Gap filter + Charts  
- Alerts for price/news  

Without Elite, this strategy is materially worse (delayed data).

### Screener / workflow: `S4_Gap_Continuation`

**Premarket routine (20–30 min):**

1. Signals → **Top Gainers** + **Major News** + **Unusual Volume** (premarket-aware with Elite).  
2. Filter mentally/with screener:

| Filter | Setting | Reason |
|--------|---------|--------|
| Price | Over $5 (prefer $10–$100 for spreads) | Avoid junk gaps |
| Average Volume | Over 500K | Can exit if thesis fails |
| Gap | Up (e.g. >2–3% if filter granularity allows) | Overnight demand |
| Relative Volume | High (premarket volume vs typical — use Unusual Volume + tape) | Real interest |
| Market Cap | Over $300M | Reduce manipulation risk |
| Change | Strong green premarket | Momentum |

3. Open news headline: **must** understand catalyst in one sentence (upgrade, product, guidance, sector news, etc.).  
4. Skip: pure dilution rumors you don’t understand, sub-$5 runners, low float chaos you can’t size risk on.

### Chart / level review (5 min per name)

- Gap type: **full gap** above prior day high (cleaner) vs partial  
- Premarket high / low range: prefer orderly lift, not ±15% whipsaw  
- Prior daily trend: continuation gaps in uptrends > gap-and-crap in downtrends  
- Mark: premarket high, prior day high, gap-fill level (prior close)

### Entry

| Mode | Trigger |
|------|---------|
| **A — Open drive** | After 5–15 min, price holds above premarket VWAP/mid and prior day high; enter on continuation |
| **B — Pullback hold** | First pullback that **does not fill the gap** (holds above prior close / gap zone) then turns up |
| **C — Avoid** | Fades back through gap fill in first 30–60 min on heavy volume |

### Stop / target / time

| Parameter | Rule |
|-----------|------|
| Stop | Below gap-hold level (prior close or premarket low — pick one *before* entry) |
| Target | +1R scale, +2R default full exit; rarely trail beyond day 3 |
| Max hold | **1–3 trading days** typical; absolute **5** for this strategy (edge is event drift, not multi-week trend) |
| Same-day option | Fully valid: enter 10:00, exit EOD if extension stalls |

### Small-account specifics

- Premarket spreads can be wide: prefer **regular-hours confirmation** entry (Strategy 4B) unless name is highly liquid.  
- Size with the **wider** of technical stop vs “I misread the news” stop — never risk >1%.  
- One gap trade at a time until consistent.

### Failure modes

- Gap fill = thesis fail more often than not for *continuation* entries  
- “News” is secondary offering / bad dilution → gap up can reverse violently  
- Holding multi-day into **next** catalyst you didn’t plan  

---

# Strategy 5 — Sector Leadership ETF / Proxy Swing  
### “Trade the river, not every fish”

### Thesis
For a sub-$25k account, liquid **sector / thematic ETFs** (and the strongest large-cap proxy in a leading industry) often deliver cleaner swings than obscure single names: tighter spreads, clearer trends, Elite **fund flow** and **Maps** context. Money rotates; you ride the leading sleeve for several days when flows and price confirm.

### Why Finviz Elite specifically
- **Maps** & **Groups**: see leadership instantly  
- **ETF filters**: AUM, category/tags, **Net Fund Flows** (1M / 3M / YTD), expense, holdings  
- Performance views on groups  
- Correlated stocks: avoid owning XLE + 3 energy names as “diversification”

### Screener / workflow: `S5_Sector_Leadership`

**Step A — Top-down (10 min, EOD or weekend):**

1. Maps: which sectors/industries are strongest 1W and 1M?  
2. Groups: sort by Performance Week / Month.  
3. Pick **1–2 leading sectors** only.

**Step B — ETF screen (Elite ETF filters):**

| Filter | Setting | Reason |
|--------|---------|--------|
| Asset type / Category | Equity sector or theme ETFs | Stay in scope |
| AUM | Higher (e.g. larger funds) | Liquidity / tracking |
| Net Fund Flows (1M) | Positive / strong inflows | Capital confirming price |
| Performance Week | Up | Near-term leadership |
| Performance Month | Up | Not a one-day wonder |
| Average Volume | Over 500K (many sector ETFs far higher) | Easy entry/exit |
| Price vs SMA20/50 | Above | Trend alignment |
| RSI (14) | 50–70 | Momentum without blow-off |

Examples of vehicles (illustrative, not recommendations): XLK, XLF, XLE, XBI, SMH, ARKK-style only if liquid and fits rules — **always re-check current flows/liquidity**.

**Step C — Optional single-name proxy (same sector):**

If you prefer stocks: from the leading industry, take the **highest RelVol + above SMA50/200 + liquid** name — but ETF is default for this strategy’s risk budget.

### Entry

| Mode | Trigger |
|------|---------|
| **Breakout** | ETF clears 5–10 day high on RelVol > 1.3 with sector map still green |
| **Pullback** | Leader pulls to SMA20 with flows still positive — Strategy 1 logic applied to ETF |
| **Skip** | Sector already parabolic vertical on Map with RSI > 75 on daily — wait for pullback |

### Stop / target / time

| Parameter | Rule |
|-----------|------|
| Stop | Below SMA20 or last swing low on daily (ETFs — use structure, not arbitrary %) |
| Target | +2R or opposite end of recent range; trail if sector remains #1 on Groups |
| Max hold | 5–10 trading days (this sleeve can use the full 10) |
| Rotation exit | If Maps leadership flips and ETF loses SMA20 → exit even before stop |

### Failure modes

- Buying laggard “because it’s cheap” inside a weak sector — this strategy is **leadership only**  
- Holding through FOMC / CPI if you don’t want gap risk (ETFs still gap)  
- Stacking correlated ETFs (e.g. SMH + SOXX + NVDA) as three “ideas”

---

## Combined weekly playbook (practical)

### Evening (4:30–5:30 PM ET) — ~45–60 min

| Time | Action |
|------|--------|
| 0:00 | Regime check: Maps + SPY/QQQ vs SMA50 |
| 0:10 | Run `S1_Pullback_Uptrend` → Charts view cull → 2–4 candidates |
| 0:25 | Run `S2_Mom_Breakout` / New High + Unusual Volume → 1–3 candidates |
| 0:35 | Run `S3_Oversold_TrendFilter` only if market had a down day / RSI opportunity |
| 0:45 | Run `S5_Sector_Leadership` top-down + ETF list |
| 0:55 | Build watchlist **max 5** names total across strategies; write entry / stop / target |
| 1:00 | Set Finviz price alerts at entries |

### Premarket (8:30–9:35 AM) — ~20–30 min when active

| Time | Action |
|------|--------|
| 8:30 | `S4_Gap_Continuation` scan: Top Gainers + News + Unusual Volume |
| 8:50 | Rank by liquidity + catalyst clarity; pick **0–1** A+ gap |
| 9:35–10:15 | Execute confirmed gap holds / planned breakouts; cancel stale alerts |

### During day

- Strategy 4 management only if in a gap trade  
- Otherwise **do not** stare; alerts + end-of-day review  
- Check open positions once midday for thesis breaks  

### Risk allocation across strategies (suggested)

| Strategy | Share of risk budget | Notes |
|----------|----------------------|-------|
| S1 Pullback | 30–40% | Core |
| S2 Breakout | 20–25% | Selective; lower win rate |
| S3 Oversold | 15–20% | Only with SMA200 filter |
| S4 Gap | 10–20% | Smaller size if stop wide |
| S5 Sector ETF | 15–25% | Stabilizer / cleaner trend |

If market is choppy: overweight S1 + S5, underweight S2/S4.  
If strong trend day: overweight S2 + S4.  
If washout day in bull market: S3 becomes primary.

---

## What “highly profitable” means under these rules

With disciplined execution on a small account:

| Metric | Realistic target band |
|--------|------------------------|
| Trades / month | 6–15 (quality over quantity) |
| Win rate (blended) | ~45–55% |
| Average R | ~+0.3R to +0.6R after friction if selective |
| Monthly return | Highly variable; process > projection |
| Max strategy DD (personal) | Plan for **−10% to −20%** equity if rules slip or regime shifts |

Anything promising “steady 10% a month” from Finviz screens alone is marketing. These five maximize **positive expectancy per unit of risk** given Elite data and your constraints — not fantasy CAGR.

---

## Finviz preset checklist (create these in Elite)

1. `S1_Pullback_Uptrend`  
2. `S2_Mom_Breakout`  
3. `S3_Oversold_TrendFilter`  
4. `S4_Gap_Continuation` (often signal-driven; save base liquidity filters)  
5. `S5_Sector_Leadership` (ETF view + flows)  

Optional sixth preset: `UNIVERSE_BASE` (USA, >$300M, >$5, >300–500K vol) to layer signals on top.

---

## Journal fields (keep it simple)

For every trade log (CSV export helps):

- Date, ticker, strategy ID (S1–S5)  
- Entry, stop, targets, shares, risk $  
- RelVol at entry, RSI, sector Map color  
- Exit date, exit reason (target / stop / time / thesis)  
- R-multiple realized  
- Screenshot or Finviz chart link optional  

Review every 20 trades: kill the strategy with negative expectancy; double down on the one working in the *current* regime.

---

## Explicit non-goals (so the book stays clean)

- No options overlays  
- No shorting weak names (even if Finviz short float looks juicy as a *short*)  
- No holding >10 trading days “because it’s almost there”  
- No averaging down  
- No trading the first week of a brand-new IPO / sub-liquidity names that violate ADV rules  

---

## Summary: the five in one line each

1. **S1 Pullback** — Buy ordered dips in uptrends at SMA/support with quiet volume.  
2. **S2 Breakout** — Buy high-tight range/52w breaks only with RelVol expansion.  
3. **S3 Oversold** — Buy RSI panic only when SMA200 still supports the structure.  
4. **S4 Gap** — Trade premarket catalyst gaps that hold, for hours to a few days.  
5. **S5 Leadership** — Ride sector/ETF flows and Map leadership instead of random tickers.

---

## Suggested next steps (when you want to operationalize)

1. Create the five Elite presets and paper-trade 20 signals.  
2. Define exact numeric gap % / RelVol thresholds that match *your* broker fills.  
3. Optionally wire Elite export/API into `swing_screener` for repeatable scans.  
4. Backtest rules where possible (note: Finviz screener has **no full historical screener replay** — use chart history / external data for validation).

---

*Proposal tailored to Finviz Elite capabilities described in `finviz-help-center.md` and your constraints (sub-$25k, 0.5–1% risk, long-only, hours–10 days, diversified edges, realistic risk framing).*
