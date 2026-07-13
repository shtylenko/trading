# Consolidated Top 3 + All-Weather Satellite — Long Swing Strategies, Finviz Elite

**Date:** 2026-07-12  
**Sources analyzed:**
| File | Author | Strategies |
|------|--------|------------|
| `claude_top5_long_swing.md` | Claude | S1 PEAD earnings gap · S2 RSI(2) leader pullback · S3 52w base breakout · S4 ETF oversold · S5 premarket catalyst |
| `codex.md` | Codex | S1 PEAD gap-and-hold · S2 quality 52w high · S3 orderly pullback · S4 vol-contraction · S5 ETF oversold |
| `grok_top5_long_swing.md` | Grok | S1 uptrend pullback · S2 mom breakout · S3 trend oversold · S4 premarket gap · S5 sector ETF leadership |

**Mandate:** Long-only US stocks + unlevered equity ETFs · hold hours → ≤ 10 trading days · no options / futures / shorts  
**This document:** ranks every candidate across the three proposals, then specifies the **top 3** as one operational playbook, plus a small **all-weather satellite sleeve (C4)** that runs alongside them at half risk.

---

## 1. Cross-file analysis

### 1.1 Full inventory (15 → clusters)

| Cluster | Claude | Codex | Grok | Appearances |
|---------|--------|-------|------|-------------|
| **Uptrend / leader pullback** | S2 RSI(2) leader dip | S3 orderly pullback reclaim | S1 pullback continuation | **3/3** |
| **52w / base / momentum breakout** | S3 52w base breakout | S2 quality 52w high | S2 high-tight mom breakout | **3/3** |
| **Earnings / PEAD gap** | S1 earnings gap-and-go | S1 earnings surprise gap-and-hold | — (partial: generic gap) | **2/3 strong** |
| **Premarket / catalyst gap** | S5 premarket catalyst | — | S4 premarket gap continuation | 2/3 |
| **ETF oversold snapback** | S4 liquid ETF MR | S5 liquid ETF snapback | — (stock oversold instead) | **2/3** |
| **Stock oversold bounce** | — (folded into S2) | — | S3 RSI oversold + SMA200 | 1/3 |
| **Vol-contraction coil** | — (inside S3 base) | S4 coil expansion | — (inside S2) | 1/3 explicit |
| **Sector leadership / fund flow** | — | — | S5 sector ETF leadership | 1/3 |

### 1.2 Scoring rubric

Each cluster scored 1–5 on five dimensions (higher = better for this mandate):

| Dimension | Meaning |
|-----------|---------|
| **Consensus** | How many independent proposals chose a version of it |
| **Evidence** | Academic / practitioner support + author confidence labels |
| **Finviz fit** | How cleanly Elite filters/signals/premarket implement it |
| **Risk clarity** | Objectivity of stop, time stop, skip rules (small-account friendly) |
| **Book role** | Diversifies hold time / edge type vs other top picks |

| Cluster | Consensus | Evidence | Finviz fit | Risk clarity | Book role | **Total /25** |
|---------|----------:|---------:|-----------:|-------------:|----------:|--------------:|
| **Leader pullback** | 5 | 4 | 5 | 5 | 5 | **24** |
| **52w / base breakout** | 5 | 5 | 5 | 4 | 5 | **24** |
| **PEAD earnings gap** | 4 | 5 | 5 | 4 | 5 | **23** |
| ETF oversold snapback | 4 | 4 | 5 | 4 | 4 | 21 |
| Premarket catalyst gap | 3 | 3 | 5 | 3 | 4 | 18 |
| Vol-contraction coil | 2 | 3 | 3 | 4 | 3 | 15 |
| Stock oversold (no leader filter) | 2 | 3 | 5 | 3 | 2 | 15 |
| Sector fund-flow leadership | 1 | 3 | 5 | 3 | 3 | 15 |

### 1.3 Why these three win

1. **Leader pullback** — Unanimous “core” sleeve. Best win-rate profile for a balanced book. Claude’s RSI(2) + SMA200 refinement, Codex’s reclaim trigger, and Grok’s volume-dry-up checklist are complementary, not competing.
2. **Quality 52-week-high / base breakout** — Unanimous momentum sleeve. Codex ranks it A− with George–Hwang 52w-high literature; Claude and Grok add RelVol + base tightness so it is not “buy every New High.”
3. **Earnings surprise gap-and-hold (PEAD)** — Best-documented *event* edge; Claude and Codex both put it in their top tier. It uniquely uses Elite premarket + earnings calendar + gap/RelVol, and fills the hours→few-days end of the mandate. Grok’s generic gap play is absorbed as non-earnings **skip** (those stay out of this book to avoid overlap).

### 1.4 What was cut (and why)

| Cut | Reason |
|-----|--------|
| ETF oversold snapback → **kept as live satellite C4** | Not cut after review. Shares mean-reversion DNA with pullback but fires in **complementary regimes** — shocks/chop, exactly when C1/C2 are gated off; signal overlap in time is near zero. Running cost ~15 min/day against a fixed universe, 2–6 signals/month. See C4 section. |
| Premarket non-earnings catalyst | Higher left-tail, more discretion on “is the news real?”; PEAD is the cleaner event sleeve. |
| Standalone coil / VCP | Already embedded as *structure requirement* inside breakout. |
| Stock RSI oversold without leadership | Inferior to leader pullback; knife risk. |
| Sector fund-flow ETF momentum | Useful top-down **context** for the three winners; weak as a third standalone edge given only 1/3 authors proposed it as a full strategy. |

### 1.5 Source-file tensions resolved

| Topic | Resolution in this playbook |
|-------|----------------------------|
| Account size (Grok &lt;$25k vs Claude ≥$25k) | **Confirmed: margin ≥ $25k — no PDT constraint.** Same-day exits are unrestricted; C3's gap-fill exit stays same-day and unconditional. (Sub-$25k guidance remains in the source files if ever needed.) |
| Risk per trade (Codex 0.35% vs others 0.5–1%) | **Default 0.5–0.75%**; use 0.35–0.5% on PEAD until slippage is known. |
| RSI(2) vs RSI(14) | **RSI(2) &lt; 10 preferred** (Elite custom period); fallback RSI(14) 35–50 on pullbacks. |
| Liquidity floor | Consolidated: **price ≥ $10**, **avg vol ≥ 500K** (prefer 1M), **mcap ≥ $300M** (prefer $2B+ for PEAD/pullback). |
| Earnings | PEAD *selects* earnings names. Pullback and breakout **never hold through a report**. |

---

## 2. Shared operating system

### 2.1 Universe gates (always on)

| Filter | Setting | Purpose |
|--------|---------|---------|
| Country | USA | Clean US listings |
| Exchange | NYSE / NASDAQ / AMEX | Finviz coverage |
| Market Cap | Over $300M (prefer Mid+ $2B for C1/C2) | Quality / tradability |
| Price | Over $10 | Noise / spread control |
| Average Volume | Over 500K (prefer 1M+) | Exit liquidity |
| Security | Common stocks (C1–C3); no leveraged/inverse/single-stock ETFs | Mandate hygiene |

**Liquidity size cap (sub-$25k–friendly):**

```text
max_position_$ ≤ 0.01 × price × average_volume
```

Skip if a full 0.5–0.75% risk position would exceed ~1–2% of ADV.

### 2.2 Position sizing

```text
shares = floor( equity × risk_fraction / (entry − stop) )
1R = entry − stop   (per share)
```

| Rule | Limit |
|------|-------|
| Risk per trade | 0.50–0.75% equity (PEAD: 0.35–0.50% until live fills known) |
| Max notional / name | 15–20% equity |
| Max open initial risk | 2.5–3.0% equity |
| Max positions | 3–5 total; ≤ 2 same sector |
| Never | Average down; widen stop; hold past day 10 |

### 2.3 Regime gate (2 minutes, before scanning)

Use Finviz **Maps**, **Groups**, and SPY/QQQ daily technicals:

| Regime | Practical definition | Allowed |
|--------|----------------------|---------|
| **Risk-on** | SPY above SMA50 (and preferably SMA200); map mostly constructive | All four sleeves (C4 at its fixed satellite sizing) |
| **Mixed** | SPY above SMA200 but choppy vs SMA20/50 | Pullback + PEAD normal/half; breakout only A+ RS names; C4 normal |
| **Risk-off** | SPY below falling SMA50 or below SMA200 with broad weakness | Cash default; PEAD only exceptional beats at half risk; no routine breakouts; **C4 stays active — SPY/QQQ only, half size** |

Prefer candidates in **top-half sectors** on Groups (1W / 1M).

### 2.4 Elite workspace

Save presets:

| Preset | Role |
|--------|------|
| `C1_PULLBACK` | Leader pullback candidates |
| `C2_BREAKOUT` | 52w / base candidates |
| `C2_TRIGGER` | Optional: New High + RelVol ≥ 1.5 on watchlist |
| `C3_PEAD` | Earnings gap candidates |
| `C4_ETF_MR` | ETF oversold snapback (runs against fixed ETF portfolio) |

Custom view columns (minimum):

`Ticker, Price, Sector, Industry, Market Cap, Avg Volume, Rel Volume, Gap, Change, Change from Open, Perf Week, Perf Month, Perf Quarter, SMA20, SMA50, SMA200, RSI(14), ATR, 52W High, Earnings Date, Pattern`

Charts layout: **daily** (structure) + **15m/hourly** (trigger: VWAP, opening range).

### 2.5 Default exit skeleton (tuned per strategy)

| Milestone | Action |
|-----------|--------|
| Stop hit | Full exit; no same-day revenge re-entry |
| +1R | Optional: scale ⅓–½; stop → breakeven |
| Strategy target | See each strategy (typically 2–2.5R or structure) |
| Time stop | Hard exit by stated day; absolute day 10 |
| Thesis break | Exit even if stop not hit (support lost, gap fill, sector collapse) |

---

## 3. The top 3 strategies + the C4 satellite

---

# C1 — Leader Pullback Reclaim  
### Core book · high win-rate sleeve

**Also known as:** Grok S1 · Claude S2 · Codex S3  
**Edge type:** Trend + short-horizon mean reversion into strength  
**Typical hold:** 2–7 trading days  
**Best regime:** Risk-on and mixed (bull structure)

### Thesis

Liquid leaders in an intact intermediate uptrend often dip 2–5 sessions on **contracting volume**. Buying either the **statistical extreme at the close** (Variant MR below) or the **reclaim** (Variant PB below) captures continuation toward the prior high with favorable R. This is the highest-consensus, highest-quality core edge across all three source files.

### Finviz candidate screen — `C1_PULLBACK`

Run after the close (or 15:30–15:50 with Elite real-time).

| Filter | Setting | Why |
|--------|---------|-----|
| Market Cap | Over $2B preferred (floor $300M) | Mean reversion cleaner in institutional names |
| Price | Over $10 (prefer $20+) | Spread control |
| Average Volume | Over 500K (prefer 1M) | Cheap exit into strength |
| SMA200 | Price above SMA200 | **Non-negotiable** trend gate |
| SMA50 | Price above SMA50 | Leader, not laggard |
| SMA20 | Price near / slightly below / ≤ ~3% above SMA20 | Pullback zone (confirm visually) |
| RSI | **Elite custom RSI(2) &lt; 10** preferred; fallback RSI(14) **35–50** | Short-term oversold in trend |
| Performance Month | Positive (or Half Year &gt; 10%) | Confirms leadership |
| Performance Week | Down / mild negative | Recent dip |
| Relative Volume | Prefer &lt; 1.0 on pure pullback days | Quiet selling / dry-up |

**Sort:** Perf Month (or Half Year) desc, then RSI asc.

**Hard exclude:** Earnings within next **6–7** trading days (export Earnings Date column; Finviz has no native “NOT earnings” filter).

### Chart qualification (Charts view → ticker)

Require **all**:

- Rising SMA50; higher high within last ~20 sessions  
- Pullback = 2–5 overlapping/smaller bars — **not** a single news collapse  
- Volume contracts into the low (vs the prior advance)  
- Tests aligned support: EMA20 / SMA20, rising SMA50, prior breakout pivot, or clear shelf  
- Has **not** closed below the prior structural swing low  
- Sector Map / Group neutral-to-green  
- No adverse headline (offering, guidance cut, fraud, failed trial)

### Two variants — trigger, entry, and stop are bound together (pick ONE, fix for 30 trades)

The two triggers in the screen belong to **different edges** and must not be mixed and matched. The RSI(2) evidence is measured *entering on the weak close* with time/signal exits and a wide disaster stop — the first leg of the bounce is most of the per-trade edge, and the pullback low is routinely retested intraday before the bounce. The reclaim entry belongs to the RSI(14) pullback-zone trade, which earns its tight structural stop. Applying the tight stop to the RSI(2) close entry destroys the win rate that funds this sleeve.

**Variant MR — RSI(2) mean reversion (Claude / Connors evidence)**

| Parameter | Rule |
|-----------|------|
| Trigger | Daily RSI(2) &lt; 10 (Elite custom filter); SMA200/50 gates hold |
| Entry | MOC on signal day (15:55, Elite real-time confirms filter still true), or next-day limit at signal close − 0.3×ATR(14) (accept ~40% no-fills) |
| Stop | **Disaster stop only:** entry − 2×ATR(14) or −8%, whichever is tighter; size to this stop |
| Risk fraction | 0.75% |
| Exit | First close with RSI(2) &gt; 65 **or** first close above SMA5 — whichever comes first (typically day 2–4) |
| Add rule | Optional half-size add if RSI(2) &lt; 5 on day 2 and regime still risk-on; total risk still capped |
| Time stop | Day **5** |

**Variant PB — pullback reclaim (Codex / Grok)**

| Parameter | Rule |
|-----------|------|
| Trigger | RSI(14) **35–50** in the pullback zone at aligned support |
| Entry | 15m close above VWAP **and** above first-30m high with RelVol ≥ 1.2 (Codex); or buy stop 1–2% above prior day high after a bullish reversal day (Grok) |
| Stop | 0.10 ATR below pullback low / structural support — the level that *invalidates* the setup; **skip if stop &gt; ~1.25 ATR from entry** — do not invent a tighter stop to force size |
| Risk fraction | 0.75% |
| Target | Prior swing high first; require **≥ ~1.75–2R** to that high or skip |
| Scale / trail | At +1R optional scale; trail under prior 2-day low or EMA10; hard take-profit **2–2.5R** |
| Time stop | Day **7**; if no higher close within **2** days of entry, exit early |

**Skip (both variants):** Gap open &gt; ~0.75 ATR above planned entry (chase). Invalid if price closes below SMA50 on expanding volume.

### Failure modes

- Distribution: volume **rises** into the low  
- Stock weak while sector/market strong (negative RS — not a bargain)  
- Stock-specific news dip misread as “healthy pullback”  
- Buying below SMA200 (account-killer zone)

### Expectancy role in the book

Highest frequency of the four; often **higher win rate, smaller average R**. Funds the book’s stability while breakouts and PEAD supply the fat right tail.

### Codex review comments

> These comments do not change C1's priority or its existing rules; they identify items to resolve during validation.

- **Treat the two variants as separate systems.** RSI(2) close-entry mean reversion and pullback reclaim have different signals, entries, stops, and expected return distributions. Use separate presets/journal tags (for example, `C1_MR` and `C1_PB`) and never pool their results, even though they remain grouped under C1 in this document.
- **The optional add conflicts with the shared “never average down” rule.** A preplanned second unit is still additional exposure after an adverse move. Disable it until a point-in-time portfolio backtest demonstrates that it improves expectancy and drawdown after costs; if retained, define the entire two-unit risk at the first entry.
- **Define same-close execution without look-ahead.** Confirming RSI at 15:55 and assuming an MOC fill at the official close is not generally executable as written: NYSE's normal MOC cutoff is 15:50 and Nasdaq's is 15:55, with broker cutoffs potentially earlier. Either calculate the signal by a fixed pre-cutoff time and submit an eligible MOC/LOC order, or enter next session; backtest the exact choice. See the [NYSE closing-process fact sheet](https://www.nyse.com/publicdocs/nyse/NYSE_Auctions_Closing_Process_Fact_Sheet.pdf) and [Nasdaq Closing Cross FAQ](https://www.nasdaqtrader.com/content/ProductsServices/Trading/Crosses/openclose_faqs.pdf).
- **Do not assume the win-rate label.** “High win-rate sleeve” is a hypothesis until the exact universe, entry variant, stop, slippage, and time exit pass out-of-sample testing. Report expectancy and drawdown alongside win rate.
- **Codex preference inside C1:** use Variant PB as the core implementation and keep Variant MR experimental until the same-close mechanics and RSI(2) evidence are reproduced locally. This does not change C1's position in the consolidated order.

---

# C2 — Quality 52-Week-High Base Breakout  
### Momentum / expansion sleeve · highest R potential

**Also known as:** Claude S3 · Codex S2 · Grok S2  
**Edge type:** Price/industry momentum + volume-confirmed range expansion  
**Typical hold:** 2–8 trading days (up to 10)  
**Best regime:** Persistent risk-on; exceptional RS only in mixed

### Thesis

Names near a 52-week high that form a **tight base**, then break the pivot on **elevated RelVol**, attract trend-following capital. The edge is **not** “every New High”; it is base quality + volume + sector confirmation + fast failure recognition. Codex rates this A− on evidence; Claude and Grok supply the operational RelVol and extension skips.

### Finviz candidate screen — `C2_BREAKOUT`

Run evening / weekend.

| Filter | Setting | Why |
|--------|---------|-----|
| Market Cap | Over $300M (prefer $2B+) | Tradability |
| Price | Over $10 (prefer $15+) | Hygiene |
| Average Volume | Over 500K (prefer 1M) | Institutional capable |
| SMA20 / SMA50 / SMA200 | Price above all three | Trend stack |
| 52-Week High | 0–10% below high (tighten 0–3% for higher grade) or New High signal | Near-high base |
| Performance Quarter | Over 10% | Momentum |
| Performance Month | Positive (prefer ~3–15%, not parabolic) | Orderly strength |
| RSI(14) | 50–70 (skip new entries if &gt; 75) | Trending, not exhausted |
| Relative Volume | ≥ 1.0 on candidate scan; **≥ 1.5 at trigger** | Participation |
| Volatility / range | Prefer low monthly vol or tight 20d range | Coil proxy |
| Quality (rank or filter) | EPS/sales growth Q/Q positive; ROE &gt; 15%; D/E sensible | Codex quality layer |
| Float | Under 100M preference | Torque (optional) |

**Sort:** RelVol desc among names nearest the high.

**Hard exclude:** Earnings inside next **7–10** trading days.

### Chart qualification

Require **all**:

- 5–20 day base (or 2–6 week flat base) under a clear horizontal pivot — reject one-day vertical spikes  
- Base depth roughly ≤ 2.5 ATR; no wide distribution bars  
- Volume contracts on the right side of the base  
- Stock outperforms SPY ~1M; industry/group positive 1W and 1M  
- Not already &gt; ~10% above SMA20 or &gt; ~20% above SMA50 without a fresh base  
- Sector Map leadership preferred  

**Rank survivors by:** proximity to pivot, 1M RS vs SPY, RelVol, growth quality, base tightness — **not** raw % gain alone.

### Entry

Two-stage (Claude + Codex):

1. **Watchlist:** 5–15 names with written pivot price; Finviz price alerts at pivot − 1%.  
2. **Trigger:** 15m or hourly close above pivot with **RelVol ≥ 1.5**; enter on first shallow retest of pivot **or** stop-limit ≤ ~0.10 ATR above pivot.  
3. **Cancel** if price already &gt; ~0.50 ATR above pivot (Claude: never chase &gt; ~3% past trigger).

**Intraday alternative (Grok):** hold above VWAP / opening-range high 15–30+ min on breakout day.

### Risk and exits

| Parameter | Rule |
|-----------|------|
| Stop | Below pivot/retest low − 0.10 ATR, or breakout-day low, or coil low — whichever is structural; **max ~1.25 ATR risk** |
| If stop would be &gt; 6–8% of price | Pass (small-account sizing fails) |
| Risk fraction | 0.5–0.75% |
| Failed breakout | Daily close back inside base **or** breakdown through pivot on expanding volume → exit |
| Profit | Scale at +1R or +2R; trail under prior 2-day low / EMA10; hard exit **2.5–3R** or measured move (base height) |
| Exhaustion | RelVol &gt; 3 with weak close in bottom quarter of day → tighten / exit |
| Time stop | Day **8** (Claude allows 10); if still &lt; +0.5R after **3** closes → exit or breakeven only |

### Failure modes

- Low-volume fakeouts (RelVol gate)  
- Breakouts in weak tape (regime gate — C2 mostly off in risk-off)  
- Chasing midday extensions (hand off to C1 pullback later)  
- Bull trap: break high, close back inside → exit on close back inside  

### Expectancy role in the book

Lower win rate (~40–50%) than C1; larger winners. **Do not overtrade** — selectivity is the edge.

### Codex review comments

> These comments do not change C2's priority or its existing rules; they identify items to resolve during validation.

- **Separate base discovery from breakout confirmation.** Requiring candidate RelVol ≥ 1.0 conflicts with the requirement that volume contract on the right side of the base. Use the existing `C2_BREAKOUT` preset for structure with no RelVol minimum (or a dry-up preference such as ≤ 0.8), then reserve `C2_TRIGGER` for RelVol ≥ 1.5 after the pivot breaks.
- **Rank quiet candidates by structure, not current RelVol.** Before the breakout, prioritize distance to pivot, base depth/tightness, relative strength versus SPY, sector strength, and growth quality. Relative Volume becomes decisive on the trigger day.
- **Treat Float &lt; 100M as optional risk, not automatic quality.** Lower float may increase movement, but it can also increase gaps, spreads, and slippage. It should not outrank dollar liquidity or clean base structure.
- **The cited 52-week-high evidence uses a much longer horizon.** The classic research generally forms monthly portfolios and holds for months, so it motivates the candidate feature but does not prove this 2–8 day breakout implementation. The exact pivot/RelVol/time-stop rules still require independent testing; see [George and Hwang](https://doi.org/10.1111/j.1540-6261.2004.00695.x).
- **Choose one profit-management variant per test.** Scaling at +1R, scaling at +2R, a measured-move target, and an EMA10 trail produce different expectancy. Do not select among them after observing the trade; preassign and journal the tested exit policy.

---

# C3 — Earnings Surprise Gap-and-Hold (PEAD rider)  
### Event / drift sleeve · hours to ~5 days

**Also known as:** Claude S1 · Codex S1 (ranked #1 by Codex) · absorbs Grok S4 tactics for *hold/fade* rules  
**Edge type:** Post-earnings underreaction + institutional demand after a verified beat  
**Typical hold:** Intraday confirmation → 1–5 days (Claude allows to day 8)  
**Best regime:** Any except disorderly risk-off; strongest when sector is flat-to-green

### Thesis

A genuine positive earnings surprise is often not fully priced in the opening gap. The trade **never** buys before the print. It buys only after the market **accepts** the gap (RelVol, VWAP, opening-range hold). This is the best-documented event edge available to a Finviz-driven long-only swing trader and uniquely leverages Elite real-time/premarket + earnings calendar.

### Finviz candidate path — `C3_PEAD`

**Morning (8:30–9:15 / 9:45–10:15 ET):** Earnings Before + prior evening Earnings After list.

| Filter | Setting | Why |
|--------|---------|-----|
| Earnings Date | Yesterday after close **or** today before open | The event |
| Gap | Up **4%+** (or ≥ 1×ATR(14)-in-% for high-vol names); avoid &gt; ~15% exhaustion | A 2–4% gap on a $2B+ name is inside normal daily noise (ATR often 2–3%); drift evidence concentrates in larger surprises |
| Price | Over $10 | Hygiene |
| Average Volume | Over 500K (prefer 1M) | Exit liquidity; PEAD costs kill thin names |
| Market Cap | Over $300M (prefer $2B+) | Cleaner, more tradeable drift |
| Relative Volume | Over **2.0** | Institutional participation |
| Change from Open | Positive (post-open confirmation) | Acceptance, not fade |
| SMA50 / SMA200 | Above (pre-report structure on chart) | Avoid dead-cat names. *Known cost:* excludes turnaround beats, where underreaction is often strongest — a deliberate balanced-profile trade-off |
| EPS / Sales growth Q/Q | Positive when field has updated | Beat quality proxy |

**Sort:** Relative Volume descending.

### Mandatory fundamental / news check (2 minutes — objective)

On quote page earnings history + news + SEC:

- Actual **EPS beat** and **revenue** at or above consensus  
- Guidance maintained or raised — reject EPS beat + clearly cut guidance  
- No secondary offering, accounting issue, or misleading one-time item  
- Prefer industry/sector ETF flat or green that day  
- Skip pure biotech binary lottery prints you cannot underwrite  

### Entry (mechanical opening-range framework)

Merged from Claude + Codex (best of both):

1. **No entry in the first 30 regular-session minutes** (observe 9:30–10:00).  
2. Mark opening-range high/low (first 30m).  
3. Require price **above VWAP**, a 15m close **above OR high**, and RelVol still **≥ ~2**.  
4. Enter with marketable limit just above breakout/retest.  
5. **Do not chase** if fill would be &gt; ~0.50 ATR above OR high or grossly extended vs VWAP.

**Mutually exclusive alternative (Claude variant):** buy stop at the **premarket high**, active only **9:35–11:00**; cancel if not triggered. This *replaces* steps 1–4 — it enters earlier, accepting more gap-and-crap risk in exchange for a better average fill on true runners. The two frameworks conflict on timing (9:35 vs post-10:00); pick one, journal it, and do not switch mid-sample.

**Immediate failure:** Gap fills (price &lt; prior close) → exit, no exceptions. Or 15m close below VWAP with heavy sell volume; or day-one close in bottom third of range.

### Risk and exits

| Parameter | Rule |
|-----------|------|
| Stop | OR low − 0.10 ATR, **or** entry − 1.25×ATR(14), whichever is tighter |
| Skip if risk &gt; ~1.25 ATR | Pass |
| Risk fraction | **0.35–0.50%** until slippage known; then up to 0.5–0.75% |
| Profit | Sell ½ at +2R (Claude); trail runner under prior day low / EMA10; full exit **2–2.5R**, daily close below EMA10, or gap-fill below pre-earnings close |
| Time stop | Prefer **day 5** (Codex); absolute **day 8** (Claude). If not +0.5R by close of **day 2**, exit early — drift did not appear |
| Macro | Skip new entries on FOMC days after 13:30 when index-sensitive |

### Failure modes

- Gap-and-crap opens (OR structure is the defense)  
- Crowded mega-cap where the move completes in one bar  
- Headline beat that is actually a guidance disaster  
- Trading extended hours solely because Elite shows prints (spreads/depth worse — prefer regular session)  

### Expectancy role in the book

Event-driven, seasonal frequency (earnings weeks). Lower correlation with pure technical C1/C2. Supplies **hours→multi-day** trades with a clear catalyst narrative for the journal.

### Codex review comments

> These comments do not change C3's priority or its existing rules; they identify items to resolve during validation.

- **A 4% gap is a routing signal, not the earnings surprise itself.** PEAD research usually ranks unexpected earnings relative to analyst forecasts. Prefer gap/ATR as the price-reaction filter and separately record actual-versus-consensus EPS, revenue surprise, and guidance. Do not infer that the literature validates the exact 4% cutoff; see [Livnat and Mendenhall](https://doi.org/10.1111/j.1475-679X.2006.00196.x).
- **Keep the stop structural.** If the valid stop below the opening-range low is farther than 1.25 ATR, skip the trade. Replacing it with the tighter `entry − 1.25 ATR` level can put the stop inside the opening range without invalidating the setup.
- **Measure the two entry frameworks separately.** The post-10:00 opening-range confirmation and the 9:35 premarket-high break have different fill quality and gap-and-fade exposure. The existing instruction to pick one is correct; give them distinct journal tags and do not combine their results.
- **The research horizon is not the playbook horizon.** Published PEAD is commonly measured over weeks or months. It supports post-announcement underreaction as a hypothesis, but the five-day exit, OR/VWAP trigger, liquidity filters, and long-only selection need their own out-of-sample evidence.
- **Preserve conservative initial risk.** Earnings gaps can pass through stops overnight. Keep C3 at the lower risk tier until observed slippage and gap losses—not just win rate—support an increase.

**Scope note:** Non-earnings premarket catalysts (Claude S5 / Grok S4) are **out of this consolidated book** to keep the event sleeve clean. Revisit on a **time basis** — after ~4 weeks of clean C1–C4 execution — not after 30 trades per sleeve, which would take months at C2/C3 signal frequencies. (The ETF snapback, previously also reserved, now runs live as C4 below.)

---

# C4 — Liquid ETF Oversold Snapback
### All-weather satellite sleeve · half risk · the only sleeve that fires in risk-off

**Also known as:** Claude S4 · Codex S5 (2/3 consensus; scored #4 at 21/25 in §1.2 — three points above the next candidate)
**Edge type:** Index-level short-horizon mean reversion
**Typical hold:** 1–5 days
**Best regime:** Shocks and chop — precisely when C1/C2 are gated off. Active in **all** regimes (risk-off: SPY/QQQ only, half size).

### Why it runs live instead of sitting in reserve

C1 and C4 share mean-reversion DNA but fire in **complementary regimes**: C1 needs bull-quiet structure; C4 fires on panic flushes and chop. Signal overlap in time is near zero. Without it, the book is 100% cash by rule in corrections and accumulates no sample for months — while its running cost is ~15 minutes at 15:30 against a fixed universe, 2–6 signals/month.

### Universe (fixed list — no discovery)

SPY, QQQ, IWM, DIA + the 11 SPDR sectors (XLK XLF XLV XLE XLI XLY XLP XLU XLB XLRE XLC) + SMH, XBI, ITB, KRE. **Unleveraged only** — no 2x/3x, no inverse, no single-stock / volatility / crypto / commodity / fixed-income ETPs, even if they pass the screen. Maintain as a Finviz portfolio; the screen runs against it.

### Screen — `C4_ETF_MR` (run 15:30–15:50 ET)

| Filter | Setting |
|--------|---------|
| Industry / Asset Type | Exchange Traded Fund; equity; non-leveraged; AUM over $1B (Elite ETF filters) |
| Average Volume | Over 1M |
| SMA200 | Price above SMA200 (**risk-off exception:** SPY/QQQ only, half size) |
| RSI | **Daily RSI(2) ≤ 10** (Elite custom filter; fallback RSI(14) &lt; 30) |
| Net Fund Flows | Positive 1–3M preferred — ranking aid only (Codex) |

### Entry, risk, exits (bound like C1 Variant MR — this IS a close-entry mean-reversion trade)

| Parameter | Rule |
|-----------|------|
| Entry | MOC on signal day. Planned scale-in: add second half-unit if RSI(2) &lt; 5 at the next close |
| Entry (conservative alternative, Codex) | Next session: 15m close above VWAP + first-30m high, marketable limit on retest — more confirmation, gives up the bounce's first leg. Pick one style, fix for 30 trades |
| Stop | **Disaster stop only:** entry − 1.5×ATR(14) (≈ 3–5% on sector ETFs); size to it |
| Risk fraction | **0.5% total across both units** (half of C1 — satellite status) |
| Exit | First close with RSI(2) &gt; 65 **or** first close above SMA5 |
| Failure | SPY closes below SMA200 in a *fresh* breakdown after entry → exit next open |
| Time stop | Day **5**. This is a snapback, not an investment |

### Skip conditions

- Persistent macro repricing still unfolding (surprise Fed / credit / geopolitical event)
- Sector ETF whose industry has a new structural shock and keeps underperforming SPY
- Spread visibly wide or poor depth (rare in this universe)

### Codex review comments

> These comments do not change C4's priority or satellite designation; they identify items to resolve during validation.

- **The risk-off exception is the largest unresolved concern.** Evidence for stronger reversal returns during high-VIX periods generally comes from diversified cross-sectional reversal portfolios, not from buying a single falling SPY or QQQ position below its SMA200. Until this exact long-only rule passes regime-stratified testing, require both the selected ETF and SPY to be above SMA200; otherwise cash remains the default. See [Nagel, “Evaporating Liquidity”](https://www.nber.org/papers/w17653).
- **The current exception and failure rule conflict.** If C4 enters SPY/QQQ while already below SMA200, “SPY closes below SMA200 in a fresh breakdown after entry” is ambiguous. Define a fully objective below-SMA200 entry and failure rule if the exception survives testing.
- **Cap correlated exposure at the sleeve level.** A broad selloff can trigger SPY, QQQ, IWM, and several sector ETFs together. The 0.5% risk limit should apply to all simultaneous C4 positions combined, with at most one representative ETF per highly correlated cluster.
- **The planned second unit is still averaging down.** Disable it until portfolio-level testing shows improved expectancy and acceptable waterfall losses. If retained, calculate total risk for both units before the first entry.
- **Resolve the same-close execution issue described under C1.** A signal calculated from the official close cannot also assume a fill at that close. Use a fixed pre-auction snapshot/order cutoff or next-session execution and reproduce it exactly in the backtest.
- **Treat “all-weather,” “near-zero overlap,” and ~70% win-rate language as hypotheses.** C1 and C4 may trigger together during a broad but temporary selloff, and historical practitioner win rates do not establish current net expectancy. Measure signal overlap, regime results, gap loss, and correlation locally before relying on C4 during corrections.

---

## 4. How the four work as one book

| | C1 Pullback | C2 Breakout | C3 PEAD | C4 ETF Snapback |
|--|-------------|-------------|---------|-----------------|
| Edge | Dip in strength | Expansion from base | Event drift | Index snapback |
| Typical W% | Higher | Lower | Medium | Highest (~70%) |
| Typical R | ~1–2R | ~2–3R | ~2–2.5R | ~0.7–1R |
| Hold | 2–7d | 2–8d | hours–5d | 1–5d |
| Scan time | EOD / late day | EOD + alerts | Premarket + open | 15:30 EOD |
| When dominant | Quiet bull | Strong risk-on | Earnings season | Shocks / chop / risk-off |

### Suggested risk budget (of total open risk)

| Strategy | Share | Notes |
|----------|------:|-------|
| C1 Pullback | 35–45% | Core |
| C2 Breakout | 25–30% | Selective |
| C3 PEAD | 20–25% | Smaller % risk per trade |
| C4 ETF Snapback | 10–15% | Satellite; fixed 0.5% per trade; often the only open risk in risk-off |

**Priority if multiple signals fire:** higher book alignment with regime → better R to real resistance → lower correlation with open positions → tighter spread.

---

## 5. Daily / weekly workflow

### Sunday (~30–45 min)

- Regime dial (SPY/QQQ/IWM + Maps + Groups)  
- Run `C2_BREAKOUT`; Charts cull; write pivots; set price alerts  
- Review open journal and next week’s earnings calendar  

### Daily premarket / open (~20–40 min in earnings weeks)

- Run `C3_PEAD`; news/EPS check; mark OR after 9:30  
- Execute only defined triggers after 10:00 (or 9:35–11:00 Claude window)  
- Cancel plans invalidated by adverse index gap or new filings  

### Late day / evening (~25–35 min)

- Run `C1_PULLBACK`; Charts cull; set reclaim alerts or MOC plans  
- Run `C4_ETF_MR` against the ETF portfolio; MOC entry if a signal fires (15 min, fully mechanical)  
- Refresh C2 watchlist if new bases appear  
- Journal fills; export Elite CSV for any scan you care about historically (Finviz has **no** historical screener replay)

### Intraday discipline

- Manage open risk vs prewritten stops only  
- C2: act on alerts; do not invent midday thesis  
- Circuit breaker: **−2R day** → no new entries until next session  

---

## 6. Measurement and promotion

| Rule | Threshold |
|------|-----------|
| Min sample before rule changes | 30 trades **per** strategy |
| Sleeve pause | Rolling 20-trade P&amp;L &lt; −8R → half size; &lt; −12R → off + post-mortem |
| Book pause | ~8% drawdown from HWM → half size; ~12% → flat + full review |
| Success metric | Mean R after costs, not win rate alone |

**Validation reality (all three source files agree):** Finviz is discovery/monitoring, not a point-in-time backtest database. Before scaling capital, reconstruct rules with `trading.marketdata` + `trading.lab` (or at least paper-trade 60 signals / 3 months) with spreads, slippage, and gap-through-stop stress.

---

## 7. Finviz preset checklist

1. `C1_PULLBACK`  
2. `C2_BREAKOUT`  
3. `C2_TRIGGER` (optional alert screen)  
4. `C3_PEAD`  
5. `C4_ETF_MR` (runs against the fixed ETF portfolio)  
6. Optional: `UNIVERSE_BASE` (`geo_usa`, mcap floor, price, avg vol) to layer signals  

---

## 8. One-line summary

| ID | Strategy | One line |
|----|----------|----------|
| **C1** | Leader Pullback Reclaim | Buy quiet dips in SMA200/50 leaders only after buyers reclaim control. |
| **C2** | Quality 52w Base Breakout | Buy tight bases near 52-week highs only on RelVol-confirmed pivot breaks. |
| **C3** | Earnings Gap-and-Hold | After a verified beat, buy gap acceptance (OR + VWAP + RelVol); ride short drift; never buy pre-print. |
| **C4** | Liquid ETF Oversold Snapback | Buy RSI(2) panic closes in broad unlevered ETFs above SMA200; exit the snapback within days. |

---

## 9. Reserve list (not in top 3; promote later if needed)

1. **Premarket non-earnings catalyst** (Claude S5 / Grok S4) — hours sleeve once the PEAD process is stable. Promotion is **time-based** (~4 weeks of clean C1–C4 execution), not 30-trades-per-sleeve, which would take months at C2/C3 frequencies.  
2. **Sector leadership via fund flows** (Grok S5) — use as **context** for C1/C2 sector filter first.  
3. **Standalone VCP/coil** (Codex S4) — already inside C2 structure rules.  

*(The liquid ETF oversold snapback was promoted from this list to live satellite sleeve **C4**.)*

---

## 10. Source attribution

| Consolidated rule family | Primary contributors |
|--------------------------|----------------------|
| Shared risk / regime / honesty about expectancy | All three |
| RSI(2) + SMA200 leader pullback mechanics | Claude S2, Codex S3, Grok S1 |
| 52w base + quality + RelVol breakout | Claude S3, Codex S2, Grok S2 |
| PEAD OR/VWAP/RelVol framework + earnings hygiene | Claude S1, Codex S1 |
| C4 ETF snapback (fixed universe, MOC + scale-in, RSI(2) exits, macro skip rules) | Claude S4, Codex S5 |
| Premarket gap hold/fade heuristics inside PEAD | Grok S4 |
| Academic PEAD / 52w / volume-momentum citations | Codex §10 |
| Automation / CSV archive / kill criteria | Claude §4–5 |
| Sub-$25k ADV and notional caps | Grok shared OS |

---

*This consolidated playbook is a research synthesis of the three strategy proposals, not financial advice. “Top 3 + satellite” means best-supported candidates for testing and paper trading under the stated mandate — not guaranteed profitability.*
