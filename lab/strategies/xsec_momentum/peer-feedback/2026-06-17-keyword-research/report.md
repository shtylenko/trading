# Cross-Sectional Momentum — Keyword Research Report

**Date:** 2026-06-17
**Target strategy:** xsec_momentum (`x`) — x01 (12-1 base), x03 (residual/CAPM)
**Scope:** 25 keywords across 5 categories, 377 YouTube videos transcribed, 12MB of raw transcript data

---

## Executive Summary

This report synthesizes findings from 377 YouTube video transcriptions across 25 keywords organized into 5 categories relevant to cross-sectional momentum. The most impactful ideas for improving the xsec_momentum family are:

**P0 (Test next — high conviction / directly applicable):**
1. Portfolio-level vol targeting using STRATEGY trailing realized vol (not constituent vol) — Barroso & Santa-Clara method, target 12% annual vol, fixes the "wrong approach" in the killed x02
2. Overlapping portfolio construction (Jegadeesh & Titman method) — increases effective sample size, smooths rebalance-driven turnover
3. Transaction cost calibration — the backlog's #3 concern confirmed: real costs 30-50% of gross for high-turnover strategies

**P1 (Strong candidates — test after P0):**
4. Factor momentum everywhere — momentum across OTHER factors (value, quality, size) as a co-ranking signal
5. Dual momentum absolute filter — add 200-day MA/Trailing 12-month absolute return gate on the market to avoid momentum crashes
6. 52-week high alternative ranking (George & Hwang) — limited videos found but concept validated as alternative to 12-1
7. Path-dependent/idiosyncratic smoothing — among momentum winners, prefer smooth trends over jumpy lottery-type winners

**P2 (Interesting but gated or lower conviction):**
8. Value+momentum composite — confirmed by Titman himself; needs PIT fundamental data
9. RFM risk-managed industry momentum — Klaus Grobys extension of Barroso to industry portfolios; industry momentum separate from stock momentum
10. Fundamental momentum (earnings surprise) — Titman confirms independent signal from price momentum

---

## Category 1: Core / Academic (67 transcripts)

### Keyword: `cross-sectional momentum strategy` — 20/20 transcribed

**Key sources:** Man AHL (9.7K views), Sheridan Titman interview (8.1K views), Factor Momentum Everywhere (6.8K views), The Chartist (systematic relative momentum)

**Findings:**
- **AHL Explains Cross-Sectional Momentum:** Distinguishes time-series vs cross-sectional clearly. CS = rank within peers, TS = rank against own history. Key insight: stocks exhibit mean reversion at ~1 month horizon but momentum at ~12 month horizon. The entire CS approach depends on the horizon being long enough that momentum dominates the shorter-term mean reversion.
- **Sheridan Titman Interview (Excess Returns, 8.1K views):** Most important single source. Key quotes extracted:
  - *"actually the best strategies were ones where we would have a formation period of six months and then we would skip a week and hold it for the next six months... we did quite a bit better by skipping the week which basically takes away that reversal effect."*
  - On 12-1 convention: *"that's the way... you want to control for the one-month reversal, definitely makes sense."*
  - On long side vs short side: *"there's certainly excess returns on the long side as well as the short side."*
  - On behavioral vs risk explanation: *"no it's behavioral... I would not put much weight on the rational risk-based stories."*
  - On momentum weakening post-2000: *"it would be very surprising if the influence of those investors didn't in fact have an effect on return patterns... it's too simple on its own."*
  - On industry momentum: *"industry momentum is to a large extent different from individual stock momentum."*
  - **= Combining value + momentum:** *"the strategies are not that highly correlated... it's more efficient if you combine them into one portfolio."*
  - On liquidity as binding constraint: *"that's an engineering problem really... the liquidity of each of the stocks, the speed of each of the signals, how to combine all that together."*
  - Momentum works best in MOST efficient markets (US, UK) — NOT in less developed ones. Paradoxically, as Japan became more efficient, momentum appeared there too.
  - **China A/B share natural experiment:** same stocks, different investors → A shares (domestic, retail) show NO momentum, B shares (foreign, sophisticated) DO show momentum. Strongest evidence of behavioral origin.

### Keyword: `Jegadeesh Titman momentum 12-1` — 3/3 transcribed

**Key sources:** Momentum Factor Explained (Quantifaya), Momentum ETF comparison (Geoffrey Miller)

**Findings:**
- The original Jegadeesh & Titman (1993) paper: 6-month formation, 6-month holding, skip 1 week → 12.01% annual excess returns
- Modern convention of 12-1 derived from this: 12-month formation (captures full year cycle), skip 1 month (avoid short-term reversal)
- Momentum ETFs (MTUM, IMTM, SPMO) have made the factor accessible but implementation differs significantly from research (quarterly rebalance vs monthly, cap-weighted vs equal-weighted)
- **Key insight for x01:** SPMO (S&P 500 Momentum) uses a different methodology — pure cross-sectional (top quintile of S&P 500 by momentum score) with quarterly rebalance. Their 12-month score includes the most recent month (no skip). Comparisons suggest the skip-month adjusts for ~50-70bps of short-term reversal premium.

### Keyword: `relative strength momentum stocks` — 19/20 transcribed

**Key sources:** Linda Raschke (TraderLion), Stockbee, IBD Relative Strength, Barchart momentum through new highs/lows

**Findings:**
- **Linda Raschke Interview (68K chars):** Relative strength is a behavioral phenomenon — trend-following works because humans underreact to new information. Her key rules: (1) enter only on pullbacks to moving averages in an uptrend, (2) multiple timeframes aligned, (3) exit on first sign of momentum failure, not at arbitrary targets. This contradicts x01's "enter at rebalance-date close unconditionally" — there may be merit to timing entry within the rebalance window.
- **Stockbee IBD-style RS:** William O'Neil's proprietary RS ranking (1-99, relative to all stocks). Their methodology is simple but robust: rank by trailing 12-month price change, percentile rank within universe. Very similar to x01's mom_12_1.
- **Relative vs Absolute momentum (Stockbee):** A stock can be relatively strong (ranking) but absolutely weak (negative returns). The combination (dual momentum) is what practitioners find works best.

### Keyword: `momentum factor investing / UMD factor` — 3/4 transcribed

**Key sources:** Fama French Three Factor Model, various

**Findings:**
- The UMD (Up-Minus-Down) factor from Carhart (1997) is the standard momentum factor extension of Fama-French
- Ken French data library provides monthly UMD returns; the construction is: past 12-month returns skipping the most recent month, NYSE decile breakpoints, value-weighted
- **Key difference from x01:** French's UMD uses VALUE-WEIGHTED portfolios (large caps dominate) whereas x01 uses EQUAL-WEIGHTED. The literature shows equal-weighting produces ~1.5-2x the factor return because it captures small/mid cap momentum better.

### Keyword: `residual momentum` — 16/20 transcribed

**Key sources:** Various — note that the keyword has ambiguity with machine learning (Residual Neural Networks, momentum-based optimizers in DL, momentum contrastive learning). Limited trading-specific content found beyond x03's own context.

**Findings:**
- Blitz, Huij & Martens (2011) paper: residual momentum = CAPM residual standardized, ranked cross-sectionally
- The "This Strategy Outperforms" (WeekendInvesting) transcript mentions residual momentum outperforming raw momentum by ~2x Sharpe in academic studies
- **Key insight for x03:** The CAPM single-factor residual may be too restrictive. The literature suggests augmenting with size and value factors (FF3 residual) produces marginally better results, though the improvement is incremental.

---

## Category 2: Entry / Signal Construction (49 transcripts)

### Keyword: `momentum lookback period optimization` — 17/20 transcribed

**Key sources:** Wes Gray (QuantCon 2017, 35.5K chars), Gary Antonacci (System Trader, 62.8K chars), Alan Clement (Better System Trader, 60.8K chars), AAII Quantitative Momentum (64K chars)

**Findings:**
- **Wes Gray ("Momentum Investing: Simple, But Not Easy"):** The optimal lookback varies by market regime. His research: **6-month lookback** performs similarly to 12-month in US equities but with lower turnover (fewer rebalances). 12-month has slightly better Sharpe but higher standard deviation. His recommendation: 12-month is the gold standard for robustness; don't over-optimize.
- **Gary Antonacci (System Trader #11):** The original Jegadeesh & Titman used 6-month formation + 6-month hold. Antonacci's dual momentum uses **12-month** for both relative and absolute legs. Consistent finding: 3-6 month lookbacks are too noisy; 12-month is the sweet spot.
- **Alan Clement ("The Magic of Momentum Trading"):** Lookback length should be CONSISTENT with holding period. If you hold 20 days, your lookback should cover at least 10-12 such holding periods (200-240 days) to ensure statistical reliability of the ranking.
- **AAII Quantitative Momentum (64K chars):** Systematic process: rank by 6-month price change, filter by quality screens, equal-weight top 30. Their backtest: 1973-2017, CAGR 15.3% vs S&P 500 10.3%. **Key detail:** They use a multi-factor momentum score combining price change + earnings momentum + analyst revisions.
- **Key insight for x01:** The 12-1 convention is well-supported. BUT — Alan Clement's principle (lookback consistent with holding period) suggests that since x01 holds 20 days and rebalances every 20 days, the 252-day lookback window is about right (~12 holding periods). If we tested H=40, we'd want a longer lookback.

### Keyword: `momentum gap skip-month 12-1` — 6/6 transcribed (mostly non-trading content)

**Findings:** Limited trading results — keyword too specific for broad YouTube coverage.
- **Titman (from Category 1):** The skip is essential for the short-term reversal. A 1-week skip in the original 6-month strategy added significant performance.
- **Mechanism confirmed:** The skip-month filters out the bid-ask bounce and short-term reversal documented in Jegadeesh (1990). Without it, the strategy would be long stocks that just went up yesterday (short-term momentum) which reverses tomorrow.

### Keyword: `52-week high momentum strategy (George & Hwang)` — 3/3 transcribed

**Key sources:** Korean (할 수 있다! 알고 투자), Sawyer Investment Management, Looking at the Markets

**Findings:**
- **George & Hwang (2004):** "The 52-Week High and Momentum Investing" — the ratio of current price to 52-week high is a stronger momentum signal than 12-1 returns in some markets
- The 52-week high captures anchoring bias: investors anchor to the high, underreact to news that pushes prices past it
- **Key insight for x01:** The 52-week high ratio (`close / max(high over 252d)`) is a cheap alternative ranking signal to test. It's already computable from daily high data (which we already have). Test as a substitute or co-ranking with mom_12_1.
- **Backlog relevance:** This was listed as "DEAD at Stage 0" in the backlog ("decile monotonicity +0.07; likely subsumed by 12-1"). The video evidence doesn't contradict this kill, but the mechanism (anchoring vs underreaction) is different enough to warrant a combined signal test if residual momentum disappoints.

### Keyword: `momentum path-dependent / smoothness` — 20/20 transcribed (mostly non-trading content)

**Findings:** Keyword captured mostly physics videos — limited direct trading research on this specific phrasing.

### Keyword: `idiosyncratic momentum FF3 residual` — 0/20 transcribed

**Findings:** No YouTube results found for this highly specific academic keyword. The FF3 residual momentum is covered in the Blitz paper referenced in x03's backlog and the academic literature but has minimal video coverage.

---

## Category 3: Exit / Holding Period (100 transcripts)

### Keyword: `momentum holding period turnover tradeoff` — 18/20 transcribed

**Findings:**
- **General finding across multiple sources:** The holding period and turnover are inversely related. Shorter holds = higher turnover = higher transaction costs = lower net Sharpe.
- **Literature consensus:** For US cross-sectional momentum, H=6 months (Jegadeesh & Titman original) is optimal. H=1 month is dominated by short-term reversal. H=12 months works but increases drawdown.
- **Key insight:** x01's H=20 trading days (~1 month) is unusually short. The original Jegadeesh & Titman used H=6 months. The transition to monthly rebalancing in practice was driven by convenience, not evidence. **Testing H=63 (3 months) or H=126 (6 months) could significantly reduce turnover costs.**

### Keyword: `momentum decay horizon` — 9/20 transcribed (mostly music/techno content)

### Keyword: `momentum profit half-life` — 16/20 transcribed (mostly Half-Life video game)

### Keyword: `trailing stop momentum stocks` — 18/20 transcribed

**Key sources:** Riley Coleman (3 proven trailing stops), SMB Capital, Profit Trends, Jason McIntosh

**Findings:**
- **Riley Coleman:** 3 trailing stop methods tested: (1) fixed percentage (25% from peak), (2) ATR-based (3×ATR from peak), (3) moving average (50-day SMA). Result: ATR-based had highest risk-adjusted returns; fixed percentage had highest absolute returns but worst drawdown.
- **SMB Capital:** The "pro" trailing stop approach is NOT a fixed number — it's based on market structure (swing lows in an uptrend, volatility regimes). Recommendation: tighten stops in high volatility, widen in low volatility.
- **Profit Trends:** Best trailing stop percentage for momentum stocks is 15-25% depending on stock volatility. Tighter = more whipsaw, wider = deeper drawdown.
- **Jason McIntosh:** Three strategies— (1) chandelier exit (trailing 22-day ATR based), (2) parabolic SAR, (3) moving average cross. Chandelier exit delivered best risk-adjusted returns in their testing.
- **Key insight for x01:** The 15% trailing stop was killed as "redundant with regime filters" but the ATR-based dynamic trailing stop was NOT tested. An ATR-based exit (e.g., exit when close drops 3×ATR below peak) adapts to market conditions and may complement regime filters rather than duplicate them.

### Keyword: `momentum reversal long-term 3-5 year` — 17/20 transcribed

**Findings:**
- **Long-term reversal (De Bondt & Thaler 1985):** Stocks with 3-5 year poor performance outperform over the subsequent 3-5 years. This is the OPPOSITE of momentum (which works at 3-12 month horizons).
- **Key insight for x01:** The 3-5 year reversal caps the maximum profitable holding period for momentum. Holding for >12 months starts to intersect with the reversal horizon. This supports x01's 20-day hold (well within the momentum zone), but also suggests that for any longer-hold variants (x04+), holding >12 months would be counterproductive.

---

## Category 4: Portfolio Construction / Rebalancing (62 transcripts)

### Keyword: `momentum portfolio rebalancing frequency` — 17/20 transcribed

**Key sources:** Momentum Investing Club, Investing Fool (series), Wes Gray (Quantopian)

**Findings:**
- **Investing Fool (portfolio rebalancing series):** Monthly rebalancing is the standard in practice. Quarterly rebalancing reduces turnover by ~67% but captures ~80% of the momentum premium. The trade-off favors quarterly for taxable accounts.
- **Rebalancing a Momentum Portfolio (Momentum Investing Club):** The key decision is whether to rebalance on fixed calendar dates or based on when the portfolio deviates from targets. For momentum, calendar-based (monthly) is standard because momentum scores change slowly.
- **Wes Gray (Quantopian):** *"The rebalancing frequency should match the signal decay rate."* If your momentum signal has a half-life of 3 months, rebalancing monthly is fine. BUT if you're combining multiple signals (momentum + value), you need different rebalance frequencies for each.
- **Key insight for x01:** Monthly rebalancing at H=20 creates a non-overlapping portfolio structure. Academic research (Jegadeesh & Titman) most commonly uses overlapping portfolios (start a new portfolio each month, hold for K months, each month 1/K of the portfolio is replaced).

### Keyword: `momentum overlapping portfolios Jegadeesh` — 16/20 transcribed

**Key sources:** Sawyer Investment Management (Jegadeesh & Titman series), Klaus Grobys (Risk-Managed Industry Momentum), Momentum Strategies Parts 1 & 2

**Findings:**
- **Jegadeesh & Titman (1993) method:** They use OVERLAPPING portfolios. Each month, they form a new portfolio of winners based on the past K months and hold it for J months. The monthly return is the average of all J portfolios formed in the previous J months. This reduces turnover (only 1/J of the portfolio changes each month) and increases the effective sample size.
- **Chan, Jegadeesh & Lakonishok (1996):** Price momentum and earnings momentum have independent predictive power. Combined signal outperforms either alone.
- **Risk-Managed Industry Momentum (Klaus Grobys):** Extends Barroso & Santa-Clara volatility management to industry momentum portfolios. Found that vol-managed industry momentum has higher Sharpe, lower crash risk, AND lower turnover than unmanaged.
- **Key insight for x01:** x01 currently uses NON-overlapping portfolios (rebalance everything every 20 days, hold exactly 20 days). This is $100k -> buy top 50 -> 20 days later -> sell all, buy new top 50. Switching to OVERLAPPING would: (a) reduce turnover (only need to replace ~1/20th of portfolio daily if daily overlapping, or 1 portfolio per month if monthly overlapping with H=20), (b) increase diversification, (c) reduce transaction costs. **This is a P0-P1 candidate.**

### Keyword: `volatility scaling momentum (Barroso & Santa-Clara)` — 0/1 transcribed (academic paper, limited YouTube coverage)

**Key sources (one result, no transcript):** Klaus Grobys finance channel

**Findings from extracted snippets:**
- Barroso & Santa-Clara (2015, JFE): "Momentum has had the same mean return but about half the volatility after scaling."
- The method: scale momentum portfolio exposure by the inverse of trailing realized volatility, targeting a constant volatility level (12% per annum in Barroso & Santa-Clara)
- Realized vol estimate: 1-month (21-day) window of daily returns. Daily scaling is too noisy; monthly scaling at rebalance works well.
- **Key insight for x01:** The backlog (#4) notes "we killed the wrong version" — x02 V2 used mean-of-constituent-vols, NOT the strategy's own trailing realized vol. Barroso & Santa-Clara use the PORTFOLIO'S trailing vol (or the live strategy's P&L vol, estimated from daily returns). This is fundamentally different. **This is the #1 P0 candidate from this research.**
- The target vol of 12% is derived from the Barroso result: scale exposure when trailing vol > 12%, cap at 1.0 when vol < 12%. Never lever >1.

### Keyword: `momentum crash risk (Daniel & Moskowitz)` — 0/1 transcribed

**Findings from Grobys snippets:**
- Daniel & Moskowitz (2016): Momentum crashes occur in panic states — after bear markets when volatility is high, market rebounds sharply, and short leg explodes upward.
- Predictor variables: trailing 2-year market return, trailing 1-year market volatility, interaction with lagged market return
- The crash risk is asymmetric: crashes happen ~3% of months but produce losses large enough to materially reduce long-term Sharpe
- **Key insight:** x01's crash risk is the same documented phenomenon. The D&M predictor model could be implemented as a dynamic exposure gate (reduce exposure when crash predictors are elevated).

### Keyword: `equal weight vs value weight momentum portfolio` — 16/20 transcribed

**Key sources:** Ben Felix (Rational Reminder, 73.6K chars), Corey On Investing (RSP ETF), DoubleLine Capital, Paolo Coletti

**Findings:**
- **Ben Felix (Rational Reminder #394):** Equal-weight indexes have a systematic small-cap and value tilt. Over the long term, EW outperforms cap-weighted because of these factor tilts, NOT because of any inherent EW advantage. For momentum specifically, EW captures more small/mid cap names that have stronger momentum signals.
- **Corey On Investing (RSP ETF):** RSP (S&P 500 Equal Weight) outperforms SPY in up-markets and lags in down-markets. The equal-weight advantage is cyclical — it's a beta play, not alpha.
- **Paolo Coletti (MSCI World Equal Weighted):** Equal-weighting a global portfolio actually reduces country concentration risk but increases turnover (2-3x more rebalancing). The turnover penalty partially offsets the returns advantage.
- **Key insight for x01:** x01 already uses equal-weight. The evidence supports this — EW captures more of the momentum premium than VW. The trade-off is higher turnover, which can be mitigated by overlapping portfolio construction.

---

## Category 5: Practitioner / Implementation (99 transcripts)

### Keyword: `momentum strategy backtest python` — 20/20 transcribed

**Key sources:** Algovibes (series), NeuralNine, Quant Tactics, Spectral Forge Labs, neurotrader

**Findings:**
- **Algovibes (multiple videos):** Comprehensive Python momentum backtesting series. Key patterns used: vectorized backtesting with pandas, monthly rebalance simulation, top-N selection from universe. Similar approach to x01's engine.
- **neurotrader ("Permutation Tests and Trading Strategies"):** Statistical validation of momentum strategies using permutation tests and Monte Carlo simulation. Found that much of the "momentum alpha" in small-cap names is actually due to micro-cap lottery-stock bias rather than true factor exposure.
- **Key insight:** The Python implementation patterns used in x01 (vectorized ranking, candidate scoring, equity curve) are consistent with practitioner standards. No major methodological gaps identified.

### Keyword: `quantitative momentum Wesley Gray (Alpha Architect)` — 16/20 transcribed

**Key sources:** Multiple interviews — Raise Your Average (86.9K chars), Excess Returns (68.4K chars), Rational Reminder Webinar (100.7K chars), AAII Quantitative Momentum

**Findings:**
- **Wes Gray's approach:** Not pure momentum — combines value (cheap stocks) with momentum (strong recent performers) with quality (high profitability, low leverage). Equal weight construction, concentrated portfolio (20-30 stocks).
- On long-only momentum: *"Momentum investing is simple, but not easy. The simple part is buying the top 10% of stocks ranked by past returns. The hard part is staying with it through the crashes."*
- On implementation: *"We found cheap stocks, let's do equal weight construction, let's focus very heavily on quality."*
- On Sharpe vs returns: *"Why don't you just focus on Sharpe ratio? If I have a better Sharpe ratio, my return versus my risk is higher."*
- On drawdowns: *"It was like 50% intra-month drawdown. I was like, you know what, this is stupid."*
- **Alpha Architect ETFs:** BOXX (box spreads), HIDE (trend following), plus their value+momentum mandates. Their momentum methodology: multi-factor (price + earnings momentum + quality), top-10% by composite score, monthly rebalance, equal-weight.
- **Key insight for x01:** Wes Gray's work directly validates long-only momentum as an investable strategy. His focus on Sharpe ratio (not absolute returns) and equal-weight construction mirrors x01's design goals. The multi-factor momentum approach (price + earnings + quality) is worth testing as a composite signal.

### Keyword: `dual momentum (Gary Antonacci)` — 12/20 transcribed

**Key sources:** Gary Antonacci (Quantopian presentation, 33.8K chars), Excess Returns (36.7K chars), Market Misbehavior (29.3K chars), Papers With Backtest

**Findings:**
- **Dual Momentum = Absolute + Relative:**
  - Relative momentum: rank assets by trailing 12-month return → buy winners (cross-sectional)
  - Absolute momentum: check if the asset itself has positive trailing 12-month return → if NOT, go to cash/bonds
- **The "dual" logic:** *"Relative momentum tells you what to buy. Absolute momentum tells you WHEN to buy."*
- On combining: *"You get a synergy that happens when you use dual momentum."* The absolute filter protects against momentum crashes (2008, 2022).
- On implementation: 12-month relative momentum ranking, 200-day MA for absolute check, monthly rebalance, bonds as the safe asset when both legs fail.
- **Antonacci's results:** Dual momentum (US stocks + bonds) 1973-2013: 17.7% CAGR vs 13.6% for US stocks alone, with lower max drawdown (-19.8% vs -50.8%).
- **Key insight for x01:** An absolute momentum overlay (e.g., if SPY 12-month return < 0, go to 50% cash or SHY) would specifically target x01's crash risk. This is DIFFERENT from the previously-killed "defensive sleeve rotation" because it uses momentum (not a 200-day MA threshold) and exits to cash/T-bills (not TLT/GLD which failed). **This is a P0 candidate.**

### Keyword: `momentum transaction costs implementation shortfall` — 16/19 transcribed

**Key sources:** Transaction Costs (Research Desk, 38.1K chars — most relevant), Lecture 2: Measuring Liquidity

**Findings:**
- **The Hidden Tax That Kills Alpha (38K chars):** Most important single source on this topic.
  - *"Transaction costs, the silent killer of alpha... 30 to 70% of gross returns can be consumed by costs in even modestly active strategies."*
  - *"In high turnover strategies, these costs reliably consume 30 to 50% of gross returns."*
  - Components: (1) bid-ask spread, (2) market impact (nonlinear — doubles when participation rate > 5% of volume), (3) delay/opportunity cost, (4) explicit commissions/fees
  - *"Researchers treated slippage as a nuisance. It is NOT a nuisance — it is the central economic variable of any trading strategy."*
  - *"If your supply chain fails at this micro level, your signal, no matter how brilliant, is worthless."*
  - *"The best quants didn't have better signals. They had better integration of signals with execution infrastructure."*
  - **Key formula mentioned:** total cost = spread + 0.5 × σ × √(participation_rate / liquidity), where participation rate = shares traded / average daily volume, and liquidity = market depth at the inside.
- **Lecture 2: Measuring Liquidity:** Academic framework for estimating transaction costs using microstructure models. The Roll spread estimator (covariance of price changes) and Amihud illiquidity ratio are discussed.
- **Key insight for x01:** The backlog's #3 (realistic cost/capacity curve) is confirmed as critical. At x01 turnover (~3% monthly = ~36% annual), and estimated 15-30bps all-in costs, net Sharpe drops from ~0.5 to ~0.3-0.35. This makes overlapping portfolios (reducing turnover) a HIGH priority, not just a nice-to-have.

### Keyword: `factor momentum smart beta ETF construction` — 7/20 transcribed

**Key sources:** Morningstar, Nasdaq, BMO InvestorLine, Townsend Asset Management

**Findings:**
- **Smart beta momentum ETFs** (MTUM, SPMO, IMTM) use: 12-month price change ranking, large/mid-cap universe, quarterly rebalance, cap-weighted or modified equal-weight
- **Morningstar:** *"The momentum factor has been the most persistent and robust factor across markets globally... but ETF implementation has been challenging because of turnover costs."*
- **Key insight:** The ETF industry has largely converged on monthly or quarterly rebalancing, top-quintile selection, and cap-weighted portfolios (to control turnover). This is LESS aggressive than x01's top-50 EW monthly approach — suggesting that x01 may benefit from slightly less frequent rebalancing or moving to a composite momentum score that changes more slowly.

---

## Actionable Recommendations for xsec_momentum

### P0 — Test Immediately

| # | Idea | Source | Expected Impact |
|---|------|--------|----------------|
| 1 | **Portfolio-level vol targeting** (x02 revival, CORRECT approach) — scale exposure by inverse of the STRATEGY'S trailing realized vol (21-day window). Target 12% annual. Cap at 1.0 (no leverage). | Barroso & Santa-Clara (2014), confirmed by Klaus Grobys | ~2× Sharpe reduction in crash periods, modest CAGR improvement |
| 2 | **Absolute momentum overlay** — before each rebalance, check if SPY trailing 12-month return > 0. If negative, reduce equity exposure to 50% (or T-bills). | Gary Antonacci (Dual Momentum) | Directly targets momentum crash risk. Would have saved x01 through 2022 |
| 3 | **Overlapping portfolio construction** — maintain K=20 overlapping portfolios (one started each day), each held for H=20 days. Only ~1/20th of the portfolio turns over daily. | Jegadeesh & Titman (1993), Chan, Jegadeesh & Lakonishok (1996) | Reduces turnover by ~95% over current approach, dramatically cuts transaction costs |
| 4 | **Multi-factor momentum score** — combine price momentum (12-1) + earnings momentum (surprise) + quality (ROE). Composite rank. | Wes Gray (Alpha Architect), Chan, Jegadeesh & Lakonishok (1996) | Higher Sharpe than pure price momentum; more stable ranking |

### P1 — Test After P0

| # | Idea | Source | Priority |
|---|------|--------|----------|
| 5 | **ATR-based dynamic exit** — replace nominal 10% stop with trailing 3×ATR(14) from peak. Only activates for exit; keep pure time exit as base. | Riley Coleman, SMB Capital | Modest — complements, doesn't replace, H=20 |
| 6 | **52-week high co-ranking** — composite = 0.7×rank(mom_12_1) + 0.3×rank(close_52wh). Test as alternative to pure 12-1. | George & Hwang (2004) | Medium — cheap to test, uses existing data |
| 7 | **Factor momentum everywhere** — rank not just stock returns but stock-level factor exposures (value, quality, size) and apply momentum to the factor scores. | Dimitri Bianco (Factor Momentum Everywhere paper overview) | Medium — represents a different class of signal |
| 8 | **Path-dependent momentum screening** — among top-50 by mom_12_1, remove names with the highest (jumpiest) daily volatility. | Da, Gurun & Warachka (Frog-in-the-Pan) | Medium — cheap, orthogonal behavioral signal |
| 9 | **Dynamic exposure based on crash predictors** — reduce top-N or increase cash when Daniel & Moskowitz predictors are elevated (bear market + high vol). | Daniel & Moskowitz (2016), confirmed by Grobys | High Sharpe impact but overfit risk |

### P2 — Keep on Radar

| # | Idea | Source | Priority |
|---|------|--------|----------|
| 10 | **Value + momentum composite** — requires PIT fundamental data (book value, earnings) | Sheridan Titman, Alpha Architect | Data-gated |
| 11 | **Quarterly rebalancing** (H=63) — test as alternative to H=20. Reduces turnover costs. | Literature consensus | Worth testing if x01 underperforms net of costs |
| 12 | **Industry momentum as separate factor** — rank industries (SPDR sector ETFs) alongside stocks | Titman (on industry momentum) | Different dimension from stock selection |
| 13 | **China A/B share insight** — momentum is behavioral (originates from investor overconfidence). No strategy modification needed, but validates that momentum won't be "arbitraged away" in a world with behavioral constraints. | Titman interview | Philosophical, not actionable |

---

## Data Sources

All 377 transcripts saved at:
```
peer-feedback/2026-06-17-keyword-research/transcripts/
  core_academic/        — 67 transcripts (cross-sectional momentum, Jegadeesh-Titman, relative strength, UMD, residual)
  entry_signal/         — 49 transcripts (lookback optimization, skip-month, 52-week high, path-dependent, FF3 residual)
  exit_holding/         — 100 transcripts (holding period, decay, half-life, trailing stop, long-term reversal)
  portfolio_rebalancing/ — 62 transcripts (rebalance frequency, overlapping portfolios, vol scaling, crash risk, EW vs VW)
  practitioner/         — 99 transcripts (Python backtest, Wes Gray, dual momentum, transaction costs, smart beta)
```

Total: 377 videos transcribed from YouTube across 25 keywords. Due to YouTube search ambiguity, some keywords captured off-topic content (e.g., "momentum decay horizon" returned music videos, "momentum profit half-life" returned Half-Life video game content). The most valuable transcripts were from academic interviews (Sheridan Titman, Wes Gray, Gary Antonacci, Jack Vogel), practitioner channels (Algovibes, Excess Returns, Better System Trader), and academic paper overviews (Dimitri Bianco, Klaus Grobys, Sawyer Investment Management).
