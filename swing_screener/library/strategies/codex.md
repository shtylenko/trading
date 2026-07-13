# Finviz Elite Long Swing Playbook — Five Research Candidates

**Author:** Codex  
**Prepared:** 2026-07-12  
**Instruments:** Long U.S.-listed common stocks and long, unlevered U.S. equity ETFs  
**Holding period:** Hours to 10 trading days; no options, futures, shorts, inverse ETFs, or leveraged ETFs

> **Important:** These are the five strategies I would test first, not five strategies already proven profitable in this exact form. No screener setting can promise “highly profitable returns.” Finviz does not provide historical screener snapshots, and the rules below have not yet been tested point-in-time with costs. The right claim is: these are five economically distinct, Finviz-native candidates with sensible evidence, explicit triggers, and controlled downside. Backtest and paper-trade them before risking capital.

## Executive recommendation

Ranked by a combination of empirical rationale, fit with a 0–10 day holding period, Finviz observability, liquidity, and ease of defining risk:

| Rank | Strategy | Primary edge being tested | Typical hold | Best environment | Evidence confidence* |
|---:|---|---|---:|---|---|
| 1 | Earnings Surprise Gap-and-Hold | Post-earnings underreaction plus institutional demand | Intraday–5 days | Any tape except disorderly risk-off | A− |
| 2 | Quality 52-Week-High Breakout | Price/industry momentum with quality and volume confirmation | 2–8 days | Broad, persistent uptrend | A− |
| 3 | Orderly Uptrend Pullback Reclaim | Buy temporary weakness inside an intact trend | 2–7 days | Normal bull trend or range with leading groups | B+ |
| 4 | Volatility-Contraction Expansion | Enter after supply dries up and range expansion begins | 1–6 days | Quiet or improving market | B |
| 5 | Liquid ETF Oversold Snapback | Short-horizon reversal after a liquidity-driven selloff | Hours–3 days | Bull regime with a brief shock | B |

\*Confidence describes the strength of the underlying idea, **not** the expected return of these exact rules. Published effects often weaken out of sample and after publication; the exact implementations must earn their rank in a current, cost-aware test.

The strategies complement each other. Strategies 1 and 2 seek continuation, Strategy 3 buys a controlled retracement, Strategy 4 waits for volatility to re-expand, and Strategy 5 seeks mean reversion in diversified instruments. Do not run all five at full risk when they point to the same sector or market factor.

## 1. Common operating rules

### 1.1 Eligible universe

Unless a strategy states otherwise, apply these gates first:

| Finviz field | Stock rule | ETF rule | Purpose |
|---|---|---|---|
| Exchange | NASDAQ, NYSE, AMEX | NASDAQ, NYSE, AMEX | Finviz-covered U.S. listings |
| Country | USA | Not applicable | Avoid unrelated country/ADR event risk |
| Security type | Common stocks only | Long-only, unlevered U.S. equity ETFs | Keep the mandate clean |
| Price | At least $10 | At least $20 | Reduce low-price noise |
| Market cap / AUM | At least $2B | At least $1B AUM | Tradability and information quality |
| Average volume | At least 1M shares/day | At least 1M shares/day | Lower spread and exit risk |
| Approx. average dollar volume | Prefer at least $25M/day | Prefer at least $50M/day | Confirm manually as price × average volume |
| Bid/ask spread at entry | No more than 0.15% | No more than 0.08% | Control implicit cost |

Manually exclude closed-end funds, preferreds, warrants, SPAC units, leveraged/inverse ETFs, single-stock ETFs, and exchange-traded notes. For Strategy 5, also exclude commodity, volatility, crypto, and fixed-income products: the proposal is for U.S. equity exposure.

### 1.2 Market-regime gate

Check the Finviz daily charts for SPY, QQQ, IWM and the candidate’s sector ETF before taking a signal:

| Regime | Practical definition | Action |
|---|---|---|
| Risk-on | SPY above rising 20- and 50-day averages; most major index/sector maps are constructive | All strategies allowed |
| Mixed | SPY above the 200-day average but chopping around the 20/50-day averages | Strategies 1 and 3 at normal or reduced risk; 2 and 4 need exceptional relative strength; 5 allowed only after confirmation |
| Risk-off | SPY below a falling 50-day average, or below the 200-day average with broad New Lows | Cash is a valid position. Skip routine breakouts and pullbacks; only exceptional post-earnings signals at half risk |

This gate is intentionally simple. A long-only trader’s largest advantage in a hostile regime is the ability not to trade.

### 1.3 Risk unit and portfolio limits

Define before entry:

```text
E = planned entry price
S = initial invalidation/stop price
1R per share = E - S
shares = floor(account_equity × risk_fraction / (E - S))
```

Initial research settings:

- Risk **0.35% of account equity per trade**. Use 0.20% for earnings gaps and half-size/risk-off exceptions until live slippage is known.
- Cap a single position at 15% of account equity even if the risk formula permits more.
- Cap total open initial risk (“portfolio heat”) at 1.25%.
- Hold no more than three positions from one sector, and treat highly correlated ETFs/stocks as one risk cluster.
- Never widen a stop or add to a losing position.
- Close every remaining position by 3:50 p.m. ET on trading day 10. Most strategies below have a shorter time stop.
- Skip the trade if a technically valid stop is farther than 1.25 daily ATR from entry; do not shrink the stop artificially just to increase size.

A stop price is not a guaranteed fill. Overnight gaps can make a realized loss larger than 1R. Stop-limit orders constrain price but may not execute; ordinary stop orders can execute far from the trigger in fast markets.

### 1.4 Finviz Elite workspace

Create a custom screener view with:

`Ticker, Price, Market Cap/AUM, Sector, Industry, Avg Volume, Current Volume, Relative Volume, Gap, Change, Change from Open, Perf Week, Perf Month, Perf Quarter, SMA20, SMA50, SMA200, RSI(14), ATR, 20D High, 50D High, 52W High, Pattern, Earnings Date`.

Use a four-chart layout:

1. Daily: candles, EMA10/20/50, SMA200, ATR, volume.
2. Hourly: EMA20, VWAP, volume.
3. 15-minute: VWAP, opening range, volume.
4. Weekly: major support/resistance and trend context.

Save one **candidate** preset and one **trigger** preset per strategy. Candidate scans find structure after the close; trigger scans use Elite’s real-time/intraday data and Relative Volume. Create screener alerts for new matches and price alerts at the actual entry and stop levels.

---

## 2. Strategy 1 — Earnings Surprise Gap-and-Hold

### Thesis

A genuinely positive earnings event can be incorporated gradually rather than instantaneously. The trade does **not** buy before earnings. It buys only after the report, after the market has shown that the gap is being accepted rather than immediately sold.

This is ranked first because the catalyst is observable, the setup occurs frequently, the invalidation is clear, and the holding window fits the documented post-announcement-drift hypothesis. Transaction costs and crowding can materially reduce the anomaly, so liquidity is part of the signal rather than an afterthought.

### Candidate preset: `C1_PEAD_LONG`

For an after-market report, build the candidate list from the Earnings After calendar, news, and extended-hours chart; the `Gap` field will not represent the next session's opening gap until that session opens. Apply the full screen from 9:45–10:15 a.m. ET after either an after-market or before-market report.

| Finviz filter | Setting |
|---|---|
| Market Cap | Mid or larger ($2B+) |
| Country | USA |
| Price | Over $10 |
| Average Volume | Over 1M |
| Gap | Up 2% to 10% using an Elite custom range |
| Relative Volume | Over 2.0 |
| Change from Open | Positive |
| SMA50 | Price above SMA50 before the report, checked on chart |
| SMA200 | Price above SMA200 |
| EPS growth Q/Q | Positive; prefer over 10% |
| Sales growth Q/Q | Positive; prefer over 5% |
| Signal / Calendar | Earnings Before or the prior evening’s Earnings After list |

Do not mechanically trust the gap. On the Finviz earnings, forecasts, news, and SEC views, require:

- Reported EPS above consensus **and** revenue at or above consensus.
- Guidance maintained or raised; reject an EPS “beat” paired with clearly lowered guidance.
- No announced secondary offering, accounting issue, regulatory shock, or one-time item that makes the headline misleading.
- Prefer positive estimate revisions and a prior history of constructive post-earnings behavior.
- Prefer the stock’s industry and sector ETF to be flat or positive that day.

### Trigger and entry

1. Do not enter in the first 30 regular-session minutes.
2. Mark the 9:30–10:00 opening-range high and low.
3. Require price above VWAP, a 15-minute close above the opening-range high, and intraday Relative Volume at least 2.0.
4. Enter with a marketable limit just above the breakout/retest. Do not chase if the fill would be more than 0.50 ATR above the opening-range high or more than roughly 1.5 ATR above VWAP.

### Risk and exits

- **Initial stop:** 0.10 ATR below the opening-range low. Skip if that produces more than 1.25 ATR of risk.
- **Immediate failure:** Exit if the breakout fails and a 15-minute bar closes below VWAP with heavy sell volume, or if day one closes in the bottom third of its range.
- **Profit management:** At +1R, trail under the prior day’s low or daily EMA10, whichever is tighter without sitting inside ordinary noise. Exit all at 2.5R, on a daily close below EMA10, or on a gap-fill below the pre-earnings close.
- **Time stop:** Exit by day 5. If the trade has not reached +0.5R by the close of day 2, exit early; the expected drift did not appear.

### Skip conditions

- Gap above 10% with no multiweek base, or a parabolic pre-earnings run.
- First 30-minute low under the prior close.
- Conference-call/news details contradict the headline beat.
- Spread above 0.15%, trading halt, or irregular prints.
- Major macro release or Fed decision is due while the position would be open and the stock is highly index-sensitive.

---

## 3. Strategy 2 — Quality 52-Week-High Breakout

### Thesis

Stocks near a 52-week high have demonstrated persistent relative strength. The strategy demands an orderly base, fundamental quality, sector confirmation, and new volume at the pivot; simply buying every New High is not the strategy.

### Candidate preset: `C2_QHIGH_BASE`

Run after the close.

| Finviz filter | Setting |
|---|---|
| Market Cap | Mid or larger ($2B+) |
| Country | USA |
| Price | Over $15 |
| Average Volume | Over 1M |
| SMA20 / SMA50 / SMA200 | Price above all three |
| 52-Week High | 0–3% below high, or New High signal |
| Performance Quarter | Over 10% |
| Performance Month | Positive, preferably 3–15% |
| RSI(14) | 55–70 |
| EPS growth Q/Q | Over 15% |
| Sales growth Q/Q | Over 10% |
| ROE | Over 15% |
| Debt/Equity | Under 1.0; compare sensibly within Financials |
| Relative Volume | Over 1.0 for candidate scan |

If the full fundamental screen returns too few names, retain the technical/liquidity rules and use EPS, sales, ROE and leverage as a ranking score rather than progressively loosening them without recording the change.

### Chart qualification and ranking

Require all of the following:

- A 5–20 day base below a clear horizontal pivot; reject a one-day vertical spike.
- Base depth no more than roughly 2.5 ATR and no wide distribution bars.
- Up-volume stronger than down-volume; ideally volume contracts near the right side of the base.
- The stock outperforms SPY over one month and its Finviz industry/group is positive over one week and one month.
- No earnings within the next 7 trading days.

Rank survivors by: proximity to the pivot, one-month relative performance versus SPY, Relative Volume, sales/EPS growth, and base tightness. Do not rank on raw percentage gain alone.

### Trigger and entry

1. Set a price alert at the base pivot.
2. Require a 15-minute or hourly close above the pivot with Relative Volume at least 1.5.
3. Enter on the first shallow retest that holds the pivot, or with a stop-limit no more than 0.10 ATR above it.
4. Cancel the entry if price is already more than 0.50 ATR above the pivot.

### Risk and exits

- **Initial stop:** Below the pivot/retest low minus 0.10 ATR, no farther than 1.25 ATR from entry.
- **Failed breakout:** Exit on a daily close back inside the base or an intraday breakdown through the pivot on expanding volume.
- **Profit management:** Once +1R is achieved, trail under the prior two-day low or EMA10. Exit at 3R, on a daily close below EMA10, or if Relative Volume exceeds 3 while price closes weakly in the bottom quarter of the day (possible exhaustion).
- **Time stop:** Day 8; exit sooner if still below +0.5R after three closes.

### Skip conditions

- RSI above 75 before entry.
- Price more than 10% above SMA20 or 20% above SMA50.
- Breakout occurs on Relative Volume below 1.2.
- Sector ETF is below its 50-day average or the industry group is among the week’s weakest.
- Earnings or a binary regulatory decision falls inside the intended hold.

---

## 4. Strategy 3 — Orderly Uptrend Pullback Reclaim

### Thesis

Strong stocks rarely rise in a straight line. This strategy waits for a low-volume, 2–5 day retracement toward support and enters only when buyers regain control. The edge being tested is not “RSI is low”; it is the combination of intact trend, controlled selling, a logical support zone, and a confirmed reclaim.

### Candidate preset: `C3_PULLBACK_CANDIDATE`

Run after the close.

| Finviz filter | Setting |
|---|---|
| Market Cap | Mid or larger ($2B+) |
| Country | USA |
| Price | Over $10 |
| Average Volume | Over 1M |
| SMA200 | Price above SMA200 |
| SMA50 | Price above SMA50 |
| SMA20 | Price below SMA20 or no more than 3% above it |
| Performance Month | Positive |
| Performance Week | Down 1–5% using a custom range |
| RSI(14) | 35–50 |
| Relative Volume | Under 1.0 on the pullback |
| EPS growth Q/Q / Sales growth Q/Q | Positive |

### Chart qualification

- SMA50 is visibly rising and the stock made a higher high within the previous 20 sessions.
- Pullback consists of 2–5 overlapping/smaller bars, not a single news-driven collapse.
- Pullback volume contracts; the average volume of the pullback bars should be below the prior advance’s average.
- Price is testing one or more aligned supports: EMA20, rising SMA50, prior breakout pivot, or uptrend line.
- The pullback has not closed below the prior structural swing low.
- No earnings within 7 trading days and no adverse company-specific catalyst.

### Trigger and entry

Use a separate real-time trigger view. Enter only after one of these occurs with Relative Volume at least 1.2:

1. A 15-minute close above VWAP **and** above the first 30-minute high; or
2. A break above the prior day’s high following a bullish rejection candle at support.

Use a marketable limit on the first controlled retest. Do not buy a gap that opens more than 0.75 ATR above the planned support-zone entry.

### Risk and exits

- **Initial stop:** 0.10 ATR below the pullback low or structural support, whichever actually invalidates the setup.
- **Profit management:** First objective is the prior swing high. If that is less than 1.75R away, skip the trade. Above the old high, trail beneath EMA10 or the prior two-day low; hard exit at 2.5R.
- **Failure:** Exit on a close below the pullback low or if the reclaim day closes back below VWAP.
- **Time stop:** Day 7. Exit if there is no higher close within two trading days after entry.

### Skip conditions

- Pullback is caused by earnings, fraud/accounting, an offering, a failed trial, litigation, or a guidance cut.
- Down-volume expands on consecutive days.
- Stock is weak while its sector and market are strong; that is negative relative strength, not a bargain.
- Support is obvious only after drawing many subjective lines.

---

## 5. Strategy 4 — Volatility-Contraction Expansion

### Thesis

After a prior advance, a narrowing price range and falling volume can indicate temporary balance and reduced supply. The trade is entered only when price leaves that balance upward with renewed participation. A “coil” by itself has no direction; the volume-backed upward break supplies the direction.

### Candidate preset: `C4_COIL_CANDIDATE`

| Finviz filter | Setting |
|---|---|
| Market Cap | Mid or larger ($2B+) |
| Country | USA |
| Price | Over $10 |
| Average Volume | Over 1M |
| SMA20 / SMA50 / SMA200 | Price above all three |
| RSI(14) | 45–65 |
| 20-Day High | 0–5% below high |
| 20-Day High/Low range | Under 10% if available as a custom filter |
| Volatility Week | Under 3% |
| Relative Volume | Under 0.80 during the candidate phase |
| Pattern | Ascending Triangle, Channel, or TL Resistance as an optional aid |

Elite’s customizable Bollinger Band/ATR filters can narrow the list, but do not rely on a proprietary indicator label as the definition. On the daily chart require:

- A prior advance of at least 8% over roughly 1–3 months.
- A 7–15 session box/triangle with at least two touches near resistance.
- The last five sessions’ average volume no more than roughly 70% of the 3-month average.
- Range width no more than 2.5 ATR and no close below the rising SMA50.
- No earnings within 5 trading days.

### Trigger and entry

1. Draw the exact range high before the next session; never redraw it to justify a trade.
2. Require an hourly close above that level and Relative Volume at least 1.8.
3. Prefer the breakout bar to close in its upper third and the sector ETF to be positive.
4. Enter on a retest of the range high or no more than 0.25 ATR above it.

### Risk and exits

- **Initial stop:** Below the retest/breakout-bar low minus 0.10 ATR. If that is not structurally meaningful, use the last contraction swing low. Skip risk wider than 1 ATR.
- **Failure:** Exit on an hourly close back inside the box with expanding sell volume, or a daily close below the breakout level.
- **Profit management:** Target the smaller of the measured move (box height added to breakout) or 3R. After +1R, trail beneath the prior day’s low.
- **Time stop:** Day 6. A valid expansion should work quickly; exit if price remains inside 0.5R of entry for two closes.

### Skip conditions

- Range formed after a sharp decline rather than after an advance.
- Volume is rising during the contraction, suggesting distribution rather than supply exhaustion.
- Breakout is entirely premarket/after-hours and regular-session volume does not confirm it.
- A broad-index selloff breaks the market-regime gate on trigger day.

---

## 6. Strategy 5 — Liquid ETF Oversold Snapback

### Thesis

Short-horizon reversals can follow temporary liquidity shocks. Restricting the trade to diversified, liquid, unlevered equity ETFs reduces the single-company information risk that makes “buy the biggest loser” dangerous. This is a conditional bull-regime strategy, not an attempt to catch a falling market in a new bear trend.

### Candidate preset: `C5_ETF_SNAPBACK`

Use Finviz’s ETF filters and save a curated portfolio of eligible broad-market, size/style, and sector ETFs.

| Finviz filter | Setting |
|---|---|
| Asset Type | Equity |
| Type | Passive, long-only; manually exclude leveraged/inverse |
| AUM | Over $1B |
| Price | Over $20 |
| Average Volume | Over 1M |
| SMA200 | Price above SMA200 |
| SMA20 | Price below SMA20 |
| Performance Week | Down 3–10% using a custom range |
| RSI | Daily RSI(2) at or below 10 using an advanced custom filter; fallback RSI(14) below 30 |
| Relative Volume | At least 1.0 on the selloff |
| Net Fund Flows | Prefer positive over 1 or 3 months; use only as a ranking aid |

Require SPY to remain above its 200-day average. Prefer a broad risk-off day with no new ETF-specific structural problem. Reject leveraged, inverse, single-stock, volatility, crypto, commodity, fixed-income, and ETN products even if they appear.

### Trigger and entry

Do not buy the oversold close blindly.

1. On the next session, require a 15-minute close above VWAP and above the first 30-minute high.
2. Prefer improving market breadth and SPY also above VWAP.
3. Enter with a marketable limit on the first VWAP/opening-range retest.
4. If the ETF gaps up more than 0.75 ATR, let it go; the favorable reversion may already be spent.

### Risk and exits

- **Initial stop:** 0.10 ATR below the shock low.
- **Profit management:** Exit at daily EMA5/EMA10, the SMA20, 2R, or the first strong rejection at prior support-turned-resistance—whichever comes first.
- **Failure:** Exit on a new low after the trigger or if SPY closes below its 200-day average.
- **Time stop:** Day 3. This is a snapback, not an investment.

### Skip conditions

- Persistent macro repricing after a surprise Fed, inflation, geopolitical, or credit event.
- The ETF’s underlying industry has a new fundamental shock and continues to underperform the market.
- Contango/decay or derivative exposure is central to the product.
- Spread above 0.08% or visibly poor depth.

---

## 7. Daily workflow

### After the close: 25–35 minutes

1. Check SPY/QQQ/IWM, New Highs vs. New Lows, Maps, and sector/industry Groups; assign the regime.
2. Run `C2_QHIGH_BASE`, `C3_PULLBACK_CANDIDATE`, `C4_COIL_CANDIDATE`, and `C5_ETF_SNAPBACK`.
3. Sort by Relative Volume, then use Charts view to remove messy structures.
4. Review earnings dates, news, SEC filings, peer performance, and sector ETF context.
5. Keep no more than 10 candidates total. Record entry, stop, 1R, target, time stop, catalyst, and invalidation before setting alerts.
6. Review Earnings After reports for `C1_PEAD_LONG`, but plan the regular-session opening range rather than committing to an extended-hours entry.

### Premarket and regular session

1. Review Earnings Before and update Strategy 1 candidates.
2. Cancel any plan invalidated by new filings/news, a large adverse index gap, or a gap beyond its chase limit.
3. From 9:30–10:00 ET, observe only. After 10:00, act only on a defined trigger.
4. Record planned and actual fill, spread, slippage, Relative Volume, and screenshot at entry.
5. Do not create a new thesis after entry. Manage against the prewritten stop, target, and time stop.

### Priority when several signals trigger

1. Higher evidence-ranked strategy.
2. Stronger sector/market alignment.
3. Better reward to the next real resistance, not a cosmetically tighter stop.
4. Lower correlation with current positions.
5. Lower spread and slippage.

## 8. Validation required before deployment

### 8.1 Why a separate backtest is mandatory

Finviz is suitable for discovery, monitoring, charts, alerts, exports, and real-time/intraday screening. It is not a point-in-time historical screener database. A test that downloads today’s Finviz universe and applies old prices would contain survivorship and look-ahead bias.

For this repository, any implementation should source price, calendar, fundamentals, and event history through `trading.marketdata`, then evaluate releases in `trading.lab`; Finviz should remain the research/execution interface, not an untracked second market-data source.

### 8.2 Test specification

- Reconstruct historical membership and all filters point-in-time, including delisted stocks.
- Timestamp earnings actuals, estimates, guidance/news availability, and entries so no after-the-fact data leaks into a signal.
- Use next-bar or next-session execution; never assume a fill at the bar that first revealed the signal.
- Model spreads, commissions, at least 5–10 bps one-way slippage for stocks, and gap-through-stop fills. Stress costs at 2× the base assumption.
- Test each strategy alone and then as a portfolio across bull, bear, high-volatility, low-volatility, and rate-shock regimes.
- Use rolling walk-forward or anchored out-of-sample periods; do not choose thresholds on the full sample.
- Compare against simple matched alternatives: SPY for the same holding window, sector ETF, and random liquid candidates with identical entry timing.

Track expectancy in R, win rate, average win/average loss, profit factor, exposure, turnover, maximum drawdown, worst gap loss, MAE/MFE, capacity, sector concentration, and results by year/regime. Dollar return alone is not enough.

Suggested promotion gates, set **before** viewing final out-of-sample results:

- Positive out-of-sample mean R with a confidence interval that does not depend on a handful of outliers.
- Out-of-sample profit factor at least 1.20 after base costs and above 1.05 at 2× costs.
- No single calendar year or ticker contributes more than 25% of total strategy profit.
- Stable results across reasonable nearby thresholds; reject a narrow parameter peak.
- Drawdown and overnight gap loss fit the intended account risk.
- Then paper-trade at least 60 signals or three months, whichever is longer, and reconcile every missed/partial fill.

Only the strategies that pass should be called “profitable,” and the ranking should then be replaced by out-of-sample expectancy and portfolio contribution.

## 9. What not to do

- Do not use the Finviz **Oversold**, **New High**, **Unusual Volume**, or chart-pattern label as an entry by itself.
- Do not substitute high Short Float for an edge. Short-interest data are periodic and squeezes can reverse violently.
- Do not hold routine stock setups through earnings just because the chart looks good.
- Do not optimize dozens of indicator combinations against Finviz’s legacy indicator tests. The reference’s 1995–2009 tests exclude current market structure and commissions and are not evidence for these exact strategies.
- Do not add fundamental filters to Strategy 5’s ETF signal as if ETF-level P/E or EPS growth were directly comparable to a company.
- Do not trade extended hours merely because Elite displays real-time extended-hours data; spreads and depth can be materially worse.
- Do not equate a high win rate with a good strategy. Expectancy after slippage and gap losses is the standard.

## 10. Evidence and platform sources

Platform details were checked against the local [Finviz Help Center reference](../finviz-help-center.md) and current official pages:

- [Finviz Screener Help](https://elite.finviz.com/help/screener) — field definitions, signals, Relative Volume, ATR, highs/lows, and filter behavior.
- [Finviz Elite](https://finviz.com/elite) — current real-time data, intraday charts, advanced/ETF filters, alerts, exports, and API capabilities.
- [Finviz: Intraday Timeframes & Advanced Indicators](https://finviz.com/blog/unlock-powerful-trading-insights-with-intraday-timeframes-advanced-indicators-in-finviz-screener/) — customizable technical filters across intraday through monthly timeframes.

Research motivating the hypotheses—not validating the exact rules above:

- Bernard & Thomas, [“Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?”](https://doi.org/10.2307/2491062) (1989), and Ng, Rusticus & Verdi, [“Implications of Transaction Costs for the Post-Earnings Announcement Drift”](https://doi.org/10.1111/j.1475-679X.2008.00290.x) (2008). PEAD motivates Strategy 1; the latter shows why costs and liquidity cannot be ignored.
- George & Hwang, [“The 52-Week High and Momentum Investing”](https://doi.org/10.1111/j.1540-6261.2004.00695.x) (2004). Nearness to the 52-week high motivates part of Strategy 2.
- Lee & Swaminathan, [“Price Momentum and Trading Volume”](https://doi.org/10.1111/0022-1082.00280) (2000), and Moskowitz & Grinblatt, [“Do Industries Explain Momentum?”](https://doi.org/10.1111/0022-1082.00146) (1999). These motivate volume and industry confirmation rather than isolated price chasing.
- Lehmann, [“Fads, Martingales, and Market Efficiency”](https://doi.org/10.3386/w2533) (1990), and Da, Liu & Schaumburg, [“Decomposing Short-Term Return Reversal”](https://doi.org/10.2139/ssrn.1551025) (2011). Short-horizon reversal motivates Strategy 5, while the residual/liquidity result supports excluding known fundamental shocks.
- McLean & Pontiff, [“Does Academic Research Destroy Stock Return Predictability?”](https://doi.org/10.1111/jofi.12365) (2016). Published predictors weakened out of sample and after publication, reinforcing the requirement for current validation.
- SEC Office of Investor Education, [“Understanding Order Types”](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-14) — stop prices are triggers, not guaranteed execution prices; stop-limit orders can remain unfilled.

## Bottom line

The best initial allocation is **zero live dollars** and equal research priority to the five candidates, with Strategies 1 and 2 first in the implementation queue. Use Finviz Elite to find and monitor the setups exactly as defined, use the monorepo’s point-in-time data and lab funnel to determine whether an edge survives current costs, and deploy only the survivors paper-first. That is the credible path from a persuasive screen to a potentially profitable long-swing system.
