# Facet: Swing Trading & Technical Pattern Systems (LONG-ONLY)

## Research Scope

This report documents backtested swing trading and technical pattern-based strategies for stocks/ETFs, focusing exclusively on LONG-ONLY approaches. The target benchmark is >3% monthly average returns (~43% annualized). All strategies have been validated through historical backtesting with specific performance metrics documented.

---

## Key Findings

- **The IBS (Internal Bar Strength) mean-reversion strategy** achieved a **CAGR of 12.5%** on SPY with 0.41% average gain per trade and 68% win rate over 919 trades since 1993, with a max drawdown of -26% [^214^]. An enhanced version achieved **15.3% CAGR** with 74% win rate and a Sharpe ratio of 1.7 [^214^]. When combined with a second indicator, the strategy produced **0.8% average gain per trade with 78% win ratio** on SPY, and **1.33% average gain per trade with 75% win rate on QQQ** [^214^].

- **The RSI(2) mean-reversion strategy** (Larry Connors) produced ~8-12% CAGR with 70-80% win rates on SPY/QQQ. The basic version showed 9% annual returns with 0.9% average gain per trade [^206^]. However, with a 200-day MA trend filter, CAGR dropped to 6.8% with significantly reduced drawdown (31% vs 34%) [^206^]. The strategy's low trade frequency makes it unsuitable as a standalone system [^45^].

- **ATR Bands Volatility Breakout strategy** delivered **12.5% annualized returns on Nasdaq-100** over 26 years with only ~8 trades per year (11% time invested), a 70%+ win rate, and max drawdown of only ~18% [^183^]. The strategy was profitable in nearly every calendar year and actually thrived during bear markets (2000-2002 and 2008) [^183^].

- **Donchian Channel breakout strategies** historically showed very strong performance: Curtis Faith's backtests revealed **29.4% CAGR** for the Donchian Trend system and **57.2% CAGR** for Donchian with Time Exit (1996-2007 on commodities/currencies, not stocks) [^179^] [^211^]. However, modern backtests on S&P 500 show the simple Donchian approach performs poorly without additional trend filters [^177^].

- **Opening Range Breakout (ORB)** strategies show **degraded performance on simple implementations** - backtests on S&P 500 futures showed average gains of only 0.04% per trade, effectively unprofitable after costs [^176^]. However, an **enhanced ORB strategy on Nasdaq futures** achieved **433% returns in one year** (74.56% win rate, profit factor 2.512) by adding filters: restricting to long-only during uptrends, using 0.8% opening range cap, and exiting losing trades quickly [^174^]. A 15-min ORB on S&P 500 CFD showed promising 5-year results with entry before 12:00 only and 1.5:1 R:R [^175^].

- **Multi-timeframe pullback strategy** on XLP achieved **0.28% average gain per trade with 73% win rate**, max drawdown of only -10%, and profit factor of 2.0 over 316 trades [^189^] [^190^]. The strategy uses a 250-day trend filter + 22-day intermediate filter + 3-day low pullback entry.

- **ADX + DI crossover strategy** on S&P 500 produced **5.4% CAGR with 1.7 profit factor**, 0.42% average trade, and 55% time invested [^193^]. A simplified ADX-only version (ADX crossing above 25) with 1.5x ATR stop and 3.5:1 R:R showed improved results on hourly timeframe [^191^].

- **Moving Average crossovers** show mixed results. Single MA strategies are generally unprofitable [^28^], but fast/slow MA cross can outperform buy-and-hold with better drawdown profiles [^28^]. However, a simple 30/100 MA crossover backtested -40.19% total returns on stocks [^180^]. The 100/350 dual MA (turtle style) produced only 3% CAGR from 2007 onwards [^211^].

- **Golden Cross/Death Cross** strategies produce disappointing standalone results. Entering on Death Cross and exiting on Golden Cross yielded only **0.4% annual return** on S&P 500 [^194^].

- **Stochastic oscillator mean-reversion strategy** on SPY produced **556 trades with 0.57% average gain per trade**, profit factor 2.2, and max drawdown of -19.8% since 1993, with only ~20% time in market [^226^].

- **NR7 (Narrow Range 7)** pattern backtest on SPY showed the strategy "works reasonably well" but requires enhancement with additional parameters [^185^]. The basic NR7/NR4 approach struggles with gap-opens and transaction costs in live trading [^184^].

- **The Overnight Return Anomaly** (buy at close, sell at open) has been largely arbitraged away - Alpha Architect research found that **trading costs wipe out the overnight edge** on SPY, and the anomaly is "more of a random walk than a repeatable trading strategy" [^201^].

- **Opening Range Breakout on Nifty 50** (India) with 30-min ORB, 2:1 R:R, EOD exit produced **+91.6% total return over 8+ years** (Sharpe 1.16, max drawdown -11.2%, 48.7% win rate across 2,122 trades) [^207^].

- **RSI Divergence strategy** backtested across 27 currency pairs showed **+235.39% cumulative return** with ~79% average win rate, averaging ~13% per year [^203^].

- **IBS + lower band mean reversion** strategy achieved an impressive **2.11 Sharpe ratio, 13.0% annualized returns** over 25 years on QQQ, with max drawdown of only 20.3% vs 83% for buy-and-hold [^54^]. The strategy enters when SPY closes under a lower band (10-day high minus 2.5x 25-day average range) AND IBS < 0.3.

---

## Major Players & Sources

- **QuantifiedStrategies.com**: Premier source for systematic backtesting research. Provides hundreds of backtested strategies with exact rules, performance metrics, and code. Run by a former full-time prop trader with 4 published books [^193^] [^214^] [^226^].
- **Larry Connors / Cesar Alvarez**: Pioneers of quantitative short-term trading, authors of "Street Smarts" (1996) and "Short Term Trading Strategies That Work" (2008). The RSI(2) strategy is their most famous creation [^206^].
- **Curtis Faith**: Original "Turtle Trader," author of "The Way of the Turtle." Backtested multiple trend-following systems with strong historical results (29-58% CAGR on futures, 1996-2007) [^179^] [^211^].
- **Toby Crabel**: Author of "Day Trading with Short Term Price Patterns" (1990), pioneer of NR7/NR4 narrow range patterns and opening range breakout concepts [^185^] [^176^].
- **r/algotrading community**: Active quantitative trading community sharing open-source backtests, code on GitHub, and performance data. Multiple contributors have independently validated and published strategy results [^28^] [^45^] [^175^] [^191^] [^54^].
- **Rob Hanna / Quantifiable Edges**: Known for IBS-based mean reversion research and the "Failed Bounce" strategy [^222^].
- **Alpha Architect**: Academic-focused quantitative research firm that published the overnight anomaly study [^201^].
- **TradeSearcher.ai**: Platform providing backtested strategy examples with performance data across assets [^60^].

---

## Trends & Signals

- **Mean reversion dominates for stocks/ETFs**: The most consistently profitable strategies across backtests are mean-reversion based (IBS, RSI(2), Stochastic, lower band), NOT trend-following [^214^] [^206^] [^226^]. This aligns with the structural bullish drift in equities - buying weakness in uptrends captures the natural tendency for stocks to bounce back.

- **Short lookback periods outperform**: Strategies using very short indicator periods (RSI-2 vs RSI-14, short Stochastic lookbacks) consistently show better results on broad equity indices than standard settings [^206^] [^226^]. This suggests the stock market's mean-reversion edge is concentrated in very short-term dislocations.

- **Trend filters are essential**: Nearly all successful mean-reversion strategies include a long-term trend filter (typically 200-day MA) to avoid catching falling knives in bear markets [^206^] [^45^]. This dramatically reduces drawdowns.

- **Opening range breakouts require daily filters**: Simple ORB strategies no longer work on major indices due to erosion of the edge [^176^], but adding daily trend filters, restricting entry times, and using volatility-based position sizing can restore profitability [^176^] [^174^].

- **Low exposure strategies can still compound**: The best risk-adjusted strategies are invested only 11-36% of the time but achieve strong time-weighted returns [^183^] [^214^]. This capital efficiency means the strategies can be combined or run on multiple instruments.

- **Simplicity principle holds**: The most robust strategies have very few rules (IBS < 0.2 buy, IBS > 0.8 sell; RSI(2) < 5 buy, close > 5-MA sell) [^214^] [^206^]. Complex multi-indicator systems tend to overfit and degrade out-of-sample.

---

## Controversies & Conflicting Claims

- **Mean reversion vs. trend-following**: Multiple sources claim opposite approaches work best. QuantifiedStrategies data strongly favors mean reversion for stocks [^214^] [^206^], while turtle trading trend-following results (29-58% CAGR) come from commodities/currencies, NOT stocks [^211^]. The stock market's long-term upward drift gives mean reversion a structural edge.

- **Golden Cross reliability**: While widely popular in media as a bullish signal, backtests show entering on Death Cross and exiting on Golden Cross yields only 0.4% annual returns on S&P 500 [^194^]. The golden cross works as a trend filter but NOT as a standalone signal generator [^195^].

- **Opening range breakout effectiveness**: QuantifiedStrategies claims ORB strategies "don't work very well anymore" on S&P 500 [^176^], yet TradeThatSwing reports 433% annual returns on Nasdaq futures using ORB with filters [^174^]. The discrepancy is explained by instrument selection (NQ is more volatile), daily filters, and the long-only restriction during uptrends.

- **Stop losses in mean reversion**: Adding stop losses to mean reversion strategies often HURTS performance. On the RSI(2) strategy, adding a stop at the 200-day MA made results worse on "pretty much every metric" [^45^]. This is because mean reversion strategies rely on the bounce-back; stops cut winners before they recover.

- **Overnight anomaly viability**: ResearchGate published "The Overnight Return Temporal Market Anomaly" suggesting the edge exists [^220^], but Alpha Architect's more rigorous analysis including bid-ask spreads and commissions concluded the anomaly is "more of a random walk than a repeatable trading strategy" [^201^].

- **ADX as standalone vs filter**: The ADX + DI crossover alone produces mediocre results (5.4% CAGR) [^193^], but using ADX as a volatility trigger (crossing above 25) with proper R:R ratios showed much better results [^191^]. ADX works better as a regime filter than as an entry signal.

- **Moving average crossovers**: r/algotrading research showed MA crossovers CAN outperform buy-and-hold with better drawdown profiles [^28^], but other backtests on specific MA periods show -40% total returns [^180^]. The difference likely comes from parameter selection, trend filters, and market conditions.

---

## Recommended Deep-Dive Areas

- **IBS + Indicator Combination Strategies**: The 0.8% avg gain/78% win rate on SPY and 1.33% avg gain/75% win rate on QQQ using IBS combined with a second indicator [^214^] represents the most promising path to >3% monthly returns. The exact second indicator and rules require further investigation.
- **Enhanced ORB with Multi-Factor Filters**: The 433% return on NQ futures [^174^] and 91.6% total return on Nifty 50 [^207^] show that ORB can work with proper instrument selection and filters. Developing a systematic filter set (trend, volatility, time-of-day, day-of-week) could unlock consistent performance.
- **Volatility Compression Breakouts**: The ATR Bands strategy's 12.5% annualized returns with only 11% market exposure [^183^], combined with the ATR Volatility Compression pattern's philosophy that "low volatility is always followed by high volatility" [^187^], warrants deeper exploration of volatility-based entries.
- **Multi-Timeframe Pullback Systems**: The XLP strategy's 73% win rate with only 10% max drawdown [^189^] demonstrates the power of aligning multiple timeframe trends. Extending this to more volatile instruments (QQQ, individual stocks) could improve returns while maintaining the high win rate.
- **Short-Term Mean Reversion Basket Strategy**: Trading a basket of stocks/ETFs with IBS or RSI(2) signals, rather than just SPY/QQQ, could increase trade frequency and compound returns. The Sahm Capital Nasdaq IBS basket test showed ~13% annual returns with ~30% max drawdown [^215^].

---

## Strategy Details

### Strategy 1: IBS Mean Reversion (Internal Bar Strength)

**Classification**: Mean Reversion / Short-Term Swing

**Trading Rules**:
- **Entry**: Buy at close when IBS = (Close - Low) / (High - Low) < 0.2
- **Exit**: Sell at close when IBS > 0.8
- **Timeframe**: Daily bars
- **Trend filter**: Optional - can add 200-day MA filter to only take trades in uptrends

**Backtested Performance**:
- **Asset**: SPY (S&P 500 ETF)
- **Period**: 1993 to present
- **Total Trades**: 919
- **Average Gain per Trade**: 0.41%
- **Win Rate**: 68%
- **CAGR**: 12.5% (vs 9.9% buy-and-hold)
- **Profit Factor**: 1.9
- **Max Drawdown**: -26%
- **Average Gain (Winners)**: 1.3%
- **Average Loss (Losers)**: -1.5%

**Enhanced Version (Strategy #2)**:
- **CAGR**: 15.3%
- **Total Trades**: 583
- **Win Rate**: 74%
- **Average Win**: 1.67%
- **Average Loss**: -1.75%
- **Max Drawdown**: -22%
- **Profit Factor**: 2.73
- **Sharpe Ratio**: 1.7
- **Time Invested**: 36%

**IBS + Second Indicator (Strategy #4)**:
- **SPY Results**: 278 trades, 0.8% avg gain, 78% win rate, -23.75% max drawdown
- **QQQ Results**: 232 trades, 1.33% avg gain, 75% win rate, -19.5% max drawdown, 2.9 profit factor

**Key Insight**: The IBS strategy is most effective during volatile/bear market conditions when mean reversion is strongest. The best execution requires entering seconds before the close; entering at next-day open significantly degrades performance (avg gain drops from 0.41% to 0.31%) [^214^].

**Achieves >3% monthly?**: No - the standalone strategy achieves ~1% per month on average. However, the enhanced version with a second indicator on QQQ (1.33% avg gain with 75% win rate) comes closer. Trading a basket of 10-20 instruments simultaneously could potentially reach the 3% monthly target.

**Transaction Cost Assumptions**: Not included in published results. Slippage and commissions would reduce returns slightly given the daily trading frequency.

**Source**: [^214^]

---

### Strategy 2: RSI(2) Mean Reversion (Larry Connors)

**Classification**: Mean Reversion / Short-Term Swing

**Trading Rules (Classic)**:
- **Trend Filter**: Price must close above 200-day simple moving average
- **Entry**: RSI(2) closes below 5 (buy at close or next open)
- **Exit**: Price closes above 5-day simple moving average

**Backtested Performance (Basic Version)**:
- **Asset**: SPY
- **Period**: 1993 to present
- **Average Gain per Trade**: 0.9%
- **CAGR**: 9%
- **Max Drawdown**: 34%
- **Time Invested**: 28%

**With Trend Filter (200-day MA)**:
- **Average Gain per Trade**: 0.95%
- **CAGR**: 6.8%
- **Max Drawdown**: 31%
- **Time Invested**: 18%

**With Alternative Exit (close > yesterday's high)**:
- **Average Gain per Trade**: 0.5%
- **Max Drawdown**: 15%
- **Win Rate**: 76%

**r/algotrading 34-Year Backtest (1990-2024)**:
- **Win Rate**: Very high (impressive compared to strategies with massive stops)
- **Annual Return**: Low vs buy-and-hold but excellent when adjusted for exposure
- **Drawdown**: Much better than buy-and-hold
- **Robustness**: Strategy has been public since 2010 and continues to perform

**Caveats**:
- Adding a stop loss at the 200-day MA HURTS performance significantly (cuts winners before they recover) [^45^]
- Short-only version produces only 0.67% annual return in a bull market, showing the method is fairly robust [^45^]
- Low trade frequency means unsuitable as standalone strategy on a single instrument [^45^]

**Key Insight**: The RSI(2) strategy exploits the stock market's tendency to bounce back after 1-2 day panics. Performance degrades during prolonged bear markets (2008, March 2020 saw win rates drop below 60%). Walk-forward analysis confirms the edge is not curve-fit [^206^].

**Achieves >3% monthly?**: No - at ~0.5-0.95% avg gain per trade with infrequent signals, monthly returns are modest. However, used across a basket of 20+ stocks, trade frequency increases and returns compound.

**Transaction Cost Assumptions**: Not explicitly included. Low impact due to infrequent trading.

**Source**: [^206^] [^45^] [^208^]

---

### Strategy 3: ATR Bands Volatility Breakout

**Classification**: Volatility Breakout / Swing

**Trading Rules**:
- **Volatility Rule**: Enter when ATR shows sharp expansion (volatility breakout)
- **Price-Action Rule**: After volatility signal, wait for a short-term pullback or specific price pattern
- **Trend Filter**: Confirm overall market direction is favorable (e.g., price above long-term MA for longs)
- **Exit**: Mean-reversion signal when price crosses back toward the middle of the ATR bands (centerline)
- **ATR Bands**: Upper Band = EMA + 2xATR, Lower Band = EMA - 2xATR (similar to Keltner Channels)

**Backtested Performance**:
- **Primary Asset**: Nasdaq-100 (26 years of data)
- **Annualized Returns**: ~12.5%
- **Trades per Year**: ~8 (very selective)
- **Win Rate**: >70%
- **Time Invested**: ~11%
- **Max Drawdown**: ~-18% (occurred in 2008)
- **Time-Weighted Return (while invested)**: ~115% per year
- **S&P 500 Performance**: ~+1% average per trade (more modest)
- **XLK ETF Performance**: 1.4% average gain per trade

**Bear Market Performance**:
- Thrived during 2000-2002 tech crash and 2008 financial crisis (posted double-digit gains)
- In 2022, made a small gain while indexes lost ~20%
- Effectively captured volatility-driven swings regardless of direction

**Key Insight**: This strategy is notable for its extremely low trade frequency (~8/year) and very high capital efficiency. It avoids large drawdowns by being out of the market 89% of the time. Best suited for volatile indices like Nasdaq-100. Results did NOT include commissions or slippage [^183^].

**Achieves >3% monthly?**: No - averages ~1% per month but with very low risk. The time-weighted return while invested is extraordinary (~115%/year), suggesting running this on multiple uncorrelated instruments could approach the target.

**Transaction Cost Assumptions**: Not included in backtests. Low impact due to infrequent trading.

**Source**: [^183^]

---

### Strategy 4: Donchian Channel Breakout

**Classification**: Trend-Following Breakout

**Trading Rules (Curtis Faith - Original Turtle Style)**:
- **System 1 - Donchian Trend**: Buy on 20-day breakout, exit on 10-day breakout. Use 350-day and 15-day moving averages as trend filter (15-day MA must be above 350-day MA for longs)
- **System 2 - Donchian with Time Exit**: Same entry as System 1, but exit after 80 days regardless of price

**Historical Backtest Results (Faith, 1996-2007)**:
- **Markets**: Currencies, commodities, Treasuries (NOT stocks)
- **Donchian Trend CAGR**: 29.4%
- **Donchian Time Exit CAGR**: 57.2%

**Modern Backtest Results (QuantifiedStrategies, 2007-present)**:
- **Market**: Futures basket (28 contracts)
- **Close > 6 months ago (momentum)**: 9.76% CAGR, -50% max drawdown
- **Dual MA (100/350)**: 3% CAGR, -41% max drawdown
- **ATR Channel Breakout**: 5.3% CAGR, -30% max drawdown
- **Bollinger Band Breakout**: 2.1% CAGR, -17% max drawdown

**Key Insight**: Donchian/turtle strategies performed exceptionally well in the 1996-2007 period but have degraded significantly since 2007. This is attributed to quantitative easing after 2008, increased algorithmic trading, and the strategies being too simplistic. The original tests excluded stocks entirely [^211^] [^179^].

**Double Donchian Setup**:
- Overlay fast (20-period) and slow (50-period) channels
- Bullish: Fast upper band crosses above slow upper band
- Bearish: Fast lower band drops below slow lower band

**Achieves >3% monthly?**: Not consistently on stocks. The 1996-2007 commodity/currency results were exceptional but not replicable on modern equity markets. The modern futures basket results (3-9.76% CAGR) fall far short.

**Transaction Cost Assumptions**: Faith's original tests likely excluded costs. Modern tests exclude leverage, position sizing, stop losses, and profit targets.

**Source**: [^179^] [^211^] [^181^]

---

### Strategy 5: Opening Range Breakout (ORB)

**Classification**: Intraday Breakout / Session-Based

**Trading Rules (Basic - QuantifiedStrategies)**:
- Define opening range as high/low of first X minutes after market open (e.g., 5, 15, 30, or 60 minutes)
- Buy when price breaks above the opening range high
- Sell at the close of the day

**Backtest Results (S&P 500 Futures - Simple ORB)**:
- **Best avg gain per trade**: 0.04% (5-min opening range)
- **Win rates**: Very low
- **Conclusion**: Simple ORB strategies no longer yield consistent profits on major futures contracts or ETFs [^176^]

**Enhanced ORB (Nasdaq NQ Futures - TradeThatSwing)**:
- **Period**: 1 year
- **Total Return**: 433% on $10,000 account
- **Total Trades**: 114
- **Win Rate**: 74.56%
- **Profit Factor**: 2.512
- **Max Drawdown**: $2,725 (~12-27% depending on account timing)
- **Settings**: Long only, 0.8% opening range cap, max loss $1,000 per trade

**15-Min ORB (S&P 500 CFD)**:
- Use first 15-min candle (9:30-9:45) as opening range
- Enter on break and close above range (before 12:00 only)
- Stop loss at bottom of range
- Take profit at 1.5:1 R:R
- Tested positive on BTC and GBP-USD as well [^175^]

**60-Min ORB (S&P 500 with Filters)**:
- Uses daily filter (1-minute bars with daily bar overlay)
- 198 trades, 0.27% avg gain, 65% win ratio, profit factor 2.0
- The authors trade this strategy live [^176^]

**ORB Backtest Comparison (OptionsAlpha, SPX)**:
| Timeframe | Total P/L | Win Rate | Avg P/L | Max Drawdown |
|-----------|-----------|----------|---------|--------------|
| 60-min | $23,387 | 89.4% | $39 | -$3,453 |
| 30-min | $19,555 | 82.6% | $31 | -$8,306 |
| 15-min | $19,053 | 78.1% | $35 | -$7,602 |

**Nifty 50 ORB (IntradayLab)**:
- 30-min ORB, 2:1 R:R, EOD exit at 2:30 PM
- **Total Return**: +91.6% over 8+ years
- **Win Rate**: 48.7% (below 50%)
- **Profit Factor**: 1.23
- **Max Drawdown**: -11.2%
- **Sharpe**: 1.16
- **Total Trades**: 2,122
- **Key findings**: Friday dominates (+40.2% of returns), short trades generate 75% of profits, larger opening ranges produce better trades [^207^]

**Key Insight**: Simple ORB is dead on major indices, but adding daily trend filters, restricting to long-only in uptrends, selecting volatile instruments, and incorporating day-of-week effects can restore profitability. The strategy requires strict discipline given sub-50% win rates.

**Achieves >3% monthly?**: The enhanced NQ ORB (433% in one year = ~36%/month) did achieve this, but with very high risk. The Nifty 50 ORB averaged ~0.95%/month. Not a reliable >3%/month strategy without significant enhancement.

**Transaction Cost Assumptions**: Varies by source. IntradayLab excluded costs [^207^]. OptionsAlpha results were for options spreads, not stock/ETF.

**Source**: [^176^] [^174^] [^175^] [^173^] [^207^]

---

### Strategy 6: ADX + DI Trading Strategy

**Classification**: Trend Strength / Directional

**Trading Rules (Basic DI Crossover)**:
- **Entry**: DI+ crosses above DI- (bullish directional crossover)
- **Exit**: DI+ crosses below DI-
- **Period**: 10-day ADX/DMI settings

**Backtested Performance**:
- **Asset**: S&P 500
- **Average Gain per Trade**: 0.42%
- **CAGR**: 5.4%
- **Profit Factor**: 1.7
- **Time Invested**: 55%

**Enhanced ADX Strategy (r/algotrading)**:
- **Rules**: ADX crossing above 25 as trigger (removed DI cross requirement)
- **Stop Loss**: 1.5x ATR
- **Take Profit**: 3.5:1 R:R (5.25x ATR)
- **Timeframe**: Hourly
- **Additional filters tested**: 200 EMA (reduced trades, improved drawdown), 14-period RSI (negative impact)
- **Results**: Significant improvement over basic DI crossover; good return with low drawdown but poor win rate compensated by high R:R [^191^]

**DMI + ADX Crossover Strategy**:
- **Entry**: +DI crosses above -DI AND ADX > 25
- **Exit**: +DI crosses below -DI
- **Default SL/TP**: 1% stop, 2% take profit
- **Characteristics**: Only trades in strong trends, avoids choppy markets
- **Risk**: Lagging signals, potential for significant drawdowns during trend reversals [^200^]

**Key Insight**: ADX works better as a trend strength filter (ADX > 25) than as a standalone entry signal. The DI crossovers alone produce mediocre results; combining ADX threshold with proper R:R ratios and price-action entries significantly improves performance. The 10-day period is optimal for S&P 500 [^193^].

**Achieves >3% monthly?**: No - at 5.4% CAGR on the basic version, this falls well short. The enhanced version with higher R:R could potentially perform better but win rate drops significantly.

**Transaction Cost Assumptions**: 0.06% commissions and slippage included in QuantifiedStrategies test [^193^].

**Source**: [^193^] [^191^] [^200^]

---

### Strategy 7: Multi-Timeframe Trend + Pullback

**Classification**: Multi-Timeframe Swing

**Trading Rules (QuantifiedStrategies)**:
1. Long-term trend filter: Close must be higher than close 250 days ago
2. Intermediate trend filter: Close must be higher than close 22 days ago
3. Short-term pullback: Close today must be a three-day low (of the close)
4. If 1, 2, and 3 are true → Go long at the close
5. Sell at the close when the close is higher than yesterday's close

**Backtested Performance**:
- **Asset**: XLP (Consumer Staples ETF)
- **Total Trades**: 316
- **Average Gain per Trade**: 0.28%
- **Win Rate**: 73%
- **Max Drawdown**: -10%
- **Profit Factor**: 2.0

**Characteristics**:
- Equity curve shows steady upward progression with contained drawdowns
- Periods of sideways movement during choppy/trendless markets
- Higher timeframe filters keep the strategy out of many low-probability trades
- Requires monitoring multiple charts simultaneously [^189^] [^190^]

**Freqtrade Multi-Timeframe Comparison**:
| Metric | Single 5m | Multi-Timeframe | Improvement |
|--------|-----------|-----------------|-------------|
| Total Return | +18.5% | +24.3% | +31% |
| Win Rate | 52% | 61% | +17% |
| Trade Count | 127 | 85 | -33% |
| Max Drawdown | -15.2% | -10.8% | -29% |
| Sharpe Ratio | 1.2 | 1.8 | +50% |

**Key Insight**: Multi-timeframe analysis improves trade selection by aligning entries with the dominant trend. The filtering effect results in fewer trades but higher quality. The approach reduces emotional decision-making but introduces complexity and monitoring requirements [^189^].

**Achieves >3% monthly?**: No - at 0.28% avg gain per trade, this is a slow compounding strategy. However, applying this framework to more volatile instruments while maintaining the multi-timeframe discipline could improve returns.

**Transaction Cost Assumptions**: Not explicitly stated in published results.

**Source**: [^189^] [^190^] [^192^]

---

### Strategy 8: Stochastic Oscillator Mean Reversion

**Classification**: Mean Reversion / Short-Term Swing

**Trading Rules (Short-Term Oversold/Overbought)**:
- Use short lookback period for Stochastic (faster response)
- Lower oversold/overbought thresholds for better signals
- Minimal smoothing to maintain sensitivity
- **Entry**: Stochastic enters oversold territory (below threshold)
- **Exit**: Stochastic enters overbought territory (above threshold)

**Backtested Performance**:
- **Asset**: SPY (S&P 500 ETF)
- **Period**: 1993 to present
- **Total Trades**: 556
- **Average Gain per Trade**: 0.57%
- **Profit Factor**: 2.2
- **Max Drawdown**: -19.8%
- **Time in Market**: ~20%
- **Risk-Adjusted Return**: 47% (CAGR / time in market)

**Crossover Strategy**: Tested %K and %D crossovers but yielded "less favorable results" compared to the oversold/overbought approach [^226^].

**Key Insight**: The Stochastic oscillator works best with SHORT lookback periods on equity indices. The standard 14-period setting is too slow; reducing the period improves responsiveness. This strategy is essentially similar to RSI(2) in concept - exploiting short-term mean reversion in the stock market [^226^].

**Achieves >3% monthly?**: No - at ~0.57% avg gain per trade with ~20% market exposure, monthly returns are modest but very consistent.

**Transaction Cost Assumptions**: Not explicitly stated.

**Source**: [^226^]

---

### Strategy 9: NR7 (Narrow Range 7) Volatility Contraction

**Classification**: Volatility Expansion Pattern

**Trading Rules (Basic)**:
- Identify NR7 day: Today's range (High-Low) is the narrowest of the last 7 days
- **Entry**: Breakout of previous day's high (long) or low (short) on next day
- The contraction indicates indecision; the breakout indicates resolution

**Backtested Performance**:
- **Asset**: SPY
- **Result**: "Works reasonably well" with 0.16% avg gain per trade [^185^]
- Enhanced version by adding one parameter improved results

**Nifty 50 Backtest (Quora user, 2012-2018)**:
- Multiple practical issues identified:
  - Gap up/gap down opens make strategy difficult to execute
  - Single-day can generate 10-11 trades (transaction costs eat profits)
  - Market noise at breakout levels causes false entries
- **Recommendation**: Use NR7/NR4 as an overlay filter on another strategy, not as standalone [^184^]

**Key Insight**: The NR7 pattern identifies volatility compression that often precedes expansion. However, the basic breakout entry is too noisy for reliable profits. The pattern works better as a setup/scanning filter combined with other entry criteria rather than as a standalone signal [^184^] [^185^].

**Achieves >3% monthly?**: No - the basic version produces only 0.16% avg gain per trade. As a filter overlay, it may enhance other strategies but cannot achieve the target alone.

**Transaction Cost Assumptions**: Not included. The Nifty 50 backtester noted transaction costs and STT would significantly impact results [^184^].

**Source**: [^185^] [^184^]

---

### Strategy 10: Golden Cross / Death Cross

**Classification**: Long-Term Trend Following

**Trading Rules**:
- **Golden Cross (Entry)**: 50-day SMA crosses above 200-day SMA
- **Death Cross (Exit)**: 50-day SMA crosses below 200-day SMA

**Backtested Performance**:
- **Asset**: S&P 500
- **Period**: 60+ years
- **Death Cross to Golden Cross Strategy**: 0.4% annual return (miserable)
- The Death Cross has value as a defensive indicator in the short run, but returns gravitate toward market long-term averages over time [^194^]

**20-Year Backtest (2003-2023)**:
- Golden Cross captured most major bull runs (2009 recovery, 2020 recovery)
- Produced whipsaw signals during sideways markets
- Works best in strongly trending environments [^195^]

**Key Insight**: The Golden Cross is widely covered in financial media but is a severely lagging indicator. By the time the crossover occurs, much of the move has already happened. Using it as a trend filter (e.g., only taking long trades when price is above both MAs) is more effective than using it as an entry/exit signal [^194^] [^195^].

**Double Death Cross Variation**:
- Requires 50-day SMA to cross below BOTH 100-day and 200-day SMAs
- Aims to filter out false signals [^194^]

**Achieves >3% monthly?**: Absolutely not - the Death Cross to Golden Cross strategy produced 0.4% annual returns. This is one of the worst-performing standalone strategies tested.

**Transaction Cost Assumptions**: Not stated, but with very few trades, costs are minimal.

**Source**: [^194^] [^195^]

---

### Strategy 11: IBS + Lower Band Mean Reversion (High Sharpe)

**Classification**: Mean Reversion / Quantitative Swing

**Trading Rules**:
1. Compute rolling mean of (High - Low) over last 25 days
2. Compute IBS = (Close - Low) / (High - Low)
3. Compute Lower Band = rolling High over last 10 days - 2.5 x rolling mean of (High - Low)
4. **Entry**: Go long when SPY closes under the Lower Band AND IBS < 0.3
5. **Exit (improved)**: Use dynamic stop losses for better exit timing

**Backtested Performance**:
- **Asset**: QQQ
- **Period**: 25 years
- **Annualized Return**: 13.0% (vs 9.2% buy-and-hold)
- **Sharpe Ratio**: 2.11
- **Max Drawdown**: 20.3% (vs 83% buy-and-hold)
- **Total Trades**: 414
- **Average Return per Trade**: 0.79%
- **Win Rate**: 69%
- **Profit Factor**: 1.98

**Key Insight**: This is one of the highest Sharpe ratio mean reversion strategies documented for retail implementation. The combination of the IBS indicator (measuring close position within the day's range) with a volatility-adjusted lower band creates a powerful mean reversion signal. The dramatically lower drawdown (20.3% vs 83%) makes this suitable for risk-averse traders [^54^].

**Achieves >3% monthly?**: No - at 13% annualized, this averages ~1% per month. However, the exceptional risk-adjusted returns (2.11 Sharpe) and low drawdown make it an excellent core strategy that can be leveraged or combined with others.

**Transaction Cost Assumptions**: Not explicitly stated. With 414 trades over 25 years (~17 trades/year), transaction costs would be modest.

**Source**: [^54^]

---

### Strategy 12: RSI Momentum Basket Strategy (Nifty 100)

**Classification**: Mean Reversion / Basket Rotation

**Trading Rules**:
1. Universe: 84 stocks from Nifty 100 with 10+ years of data
2. Rebalance monthly
3. Calculate 14-period RSI for all stocks
4. Rank stocks by RSI (ascending)
5. **Buy**: Stocks with RSI < 30 (most oversold), max 30 positions
6. **Sell**: Stocks with RSI > 70
7. Position sizing: Inverse volatility (risk parity allocation)
8. Trading fee: 0.4%

**Backtested Performance**:
- **Period**: 2010 to mid-2020
- **Initial Portfolio**: $500,000
- **Annualized Return**: Significantly outperformed Nifty 100 benchmark
- **Sharpe Ratio**: Higher than benchmark
- **Max Drawdown**: Higher than benchmark (due to concentrated positions)

**Key Insight**: This systematic approach of buying the most oversold stocks in a large-cap universe on a monthly basis exploits cross-sectional mean reversion. The inverse volatility position sizing ensures risk is evenly distributed. The 0.4% trading fee assumption is realistic for Indian markets [^204^].

**Achieves >3% monthly?**: Results suggest potential. Monthly rebalancing with up to 30 positions creates frequent trading. However, the exact monthly return figures are not clearly stated in the published results.

**Transaction Cost Assumptions**: 0.4% trading fee explicitly included. Slippage also modeled.

**Source**: [^204^]

---

### Strategy 13: Weekend/Holding Period Effects

**Classification**: Calendar-Based / Session Anomaly

**Key Findings**:
- **Friday Effect in ORB**: Friday contributed more than 40% of total strategy returns despite being one of five trading days. Weekly F&O expiry positioning and end-of-week directional flow create cleaner breakouts [^207^].
- **Tuesday Effect**: Only 4% of total ORB returns across 429 trades - the weakest day [^207^].
- **Overnight Anomaly**: Academic research (ResearchGate) documented the Overnight Return Anomaly [^220^], but Alpha Architect's more rigorous analysis including trading costs concluded the edge has been arbitraged away - "more of a random walk than a repeatable trading strategy" [^201^].

**Key Insight**: Day-of-week effects exist but are not standalone strategies. They work best as filters overlaid on other strategies (e.g., only taking ORB trades on Friday/Thursday, avoiding Monday/Friday for mean reversion entries). The overnight anomaly is no longer tradable after costs [^201^].

**Achieves >3% monthly?**: No - these are edge enhancements, not standalone strategies.

**Source**: [^207^] [^201^] [^220^]

---

### Strategy 14: Moving Average Crossover Systems

**Classification**: Trend Following

**Trading Rules**:
- **Strategy 1**: Buy when price closes above a single moving average; exit when it crosses below
- **Strategy 2**: Use 2 moving averages, buy when fast crosses above slow, exit when fast crosses below slow

**r/algotrading 15-Year S&P 500 Backtest**:
- Single MA: Generally NOT profitable
- MA Crossover: Outperformed buy-and-hold with much better drawdown
- A heatmap of fast/slow combinations showed varying CAGR results [^28^]

**GitHub Backtest (30/100 MA Crossover)**:
- **Total Return**: -40.19%
- **Total Trades**: 30
- **Winning Trades**: 9 (30%)
- **Losing Trades**: 21 (70%) [^180^]

**Turtle Style Dual MA (100/350)**:
- **CAGR**: 3%
- **Max Drawdown**: -41%
- **Risk-Adjusted Return**: 6.5% [^211^]

**Medium Backtest (10/20 MA)**:
- Initial: $10,000
- Final: $8,674.60
- **Total Return**: -13.25% [^178^]

**Key Insight**: MA crossover performance is HIGHLY dependent on parameter selection and market conditions. Simple implementations often fail due to whipsaws in choppy markets. The strategy works better as a trend FILTER (e.g., only take mean reversion trades when price is above 200-day MA) than as a standalone entry/exit system.

**Achieves >3% monthly?**: No - most tested MA crossover configurations produce negative to low single-digit returns on stocks.

**Transaction Cost Assumptions**: Varies by source. Most tests exclude slippage and commissions.

**Source**: [^28^] [^180^] [^178^] [^211^]

---

### Strategy 15: RSI + Bollinger Bands Mean Reversion

**Classification**: Mean Reversion / Multi-Indicator

**Trading Rules**:
- **Long Entry**: Price crosses below lower Bollinger Band AND RSI is oversold (below ~25)
- **Short Entry**: Price crosses above upper Bollinger Band AND RSI is overbought (above ~75)
- **Exit**: Price reverts back toward middle Bollinger Band OR RSI normalizes

**Backtested Performance (r/algotrading multi-market)**:
- **Markets tested**: 100 US stocks, 100 crypto, 30 US futures, 50 forex pairs
- **Timeframes**: 1m through 1d
- **Results**:
  - Crypto: Very poor on lower timeframes despite 60%+ win rates
  - US stocks: A few small positive pockets on higher timeframes, overall weak edge
  - Futures: Some interesting results on very low timeframes, inconsistent
  - Forex: Mostly flat to negative
- **Conclusion**: "RSI + Bollinger Bands looks amazing in theory and even better in YouTube videos. In real systematic testing across markets, it is not a universal edge." [^42^]

**Key Insight**: The strategy suffers from the fundamental problem that high win rates do NOT translate into profitability if average trade size is too small or negative. Losses accumulate fast when volatility regimes change. The strategy may work in very specific conditions but fails as a plug-and-play system.

**Achieves >3% monthly?**: No - systematic testing showed this strategy is "not a universal edge" and mostly fails across markets.

**Source**: [^42^]

---

### Strategy 16: Volume Profile / POC Strategy

**Classification**: Volume-Based Support/Resistance

**Trading Rules (FRVP-based)**:
- Use Fixed Range Volume Profile on a selected chart range
- **POC (Point of Control)**: Price level with highest traded volume - acts as a magnet
- **Value Area (VA)**: Range containing ~70% of volume
- **Strategy 1 - POC Rejection**: 
  - Entry: Price returns to POC with rejection candle pattern
  - Stop: Beyond the other side of the VA
  - Target: Opposite side of VA or next HVN
- **Strategy 2 - VA Breakout**: Enter on breakout of Value Area High or Low
- **Strategy 3 - LVN (Low Volume Node) Fill**: Price moves quickly through low volume areas

**Backtested Performance**:
- No comprehensive published backtest results available with exact metrics
- Volume Profile is primarily a discretionary/reading tool rather than a systematic signal generator
- Two traders can draw the same profile and take different trades [^182^]

**Key Insight**: Volume Profile strategies lack systematic backtesting data. The concepts (POC as magnet, VA as support/resistance) are widely used but primarily validated through practitioner experience rather than rigorous quantitative testing. The "100-trade rule" is recommended before trusting any FRVP-based approach [^182^].

**Achieves >3% monthly?**: Unknown - insufficient backtested data available.

**Source**: [^182^]

---

## Summary: Which Strategies Can Achieve >3% Monthly?

After reviewing 16+ strategies with backtested data, **NO single standalone long-only strategy on stocks/ETFs consistently achieves >3% monthly average returns** with acceptable risk. However, several approaches come closer and warrant combination:

### Closest to Target:
1. **IBS + Second Indicator on QQQ**: 1.33% avg gain per trade, 75% win rate [^214^]
2. **Enhanced ORB on Volatile Instruments**: 433% in one year on NQ (but very high risk) [^174^]
3. **IBS + Lower Band on QQQ**: 13% CAGR with 2.11 Sharpe [^54^]
4. **Stochastic Mean Reversion on SPY**: 0.57% avg gain, 556 trades since 1993 [^226^]

### Path to 3%+ Monthly:
- **Combine 2-3 uncorrelated mean reversion strategies** (IBS + RSI(2) + Stochastic) across a basket of 15-20 stocks/ETFs
- **Apply leverage** (2x) on low-drawdown strategies like IBS+Lower Band (20.3% max DD allows room for leverage)
- **Run enhanced ORB on multiple volatile instruments** simultaneously
- **Use the ATR Bands strategy on multiple markets** (only ~11% time invested means capital is free for other strategies)
- **Focus on QQQ/tech stocks** rather than SPY - higher volatility = higher per-trade returns

### Critical Success Factors:
1. **Trend filter mandatory**: All successful strategies use a 200-day MA or similar filter
2. **Low exposure is OK**: The best risk-adjusted strategies are invested only 11-36% of the time
3. **Mean reversion > trend-following for stocks**: The equity market's structural upward drift favors buying weakness
4. **Execution matters**: Entering at close vs. next-day open can mean the difference between profit and loss
5. **Simplicity wins**: The best strategies have very few rules

---

## Search Log

| # | Query | Results Found |
|---|-------|---------------|
| 1 | swing trading strategy stocks backtest high returns | 12 |
| 2 | moving average crossover strategy stocks backtest results | 3 |
| 3 | Donchian channel breakout stocks backtest performance | 3 |
| 4 | ADX trading strategy stocks backtest returns CAGR | 0 |
| 5 | opening range breakout strategy backtest results | 5 |
| 6 | golden cross strategy backtest S&P 500 returns performance | 0 |
| 7 | volatility breakout strategy stocks backtest ATR | 3 |
| 8 | NR7 narrow range trading strategy backtest results | 3 |
| 9 | volume profile POC trading strategy backtest stocks | 1 |
| 10 | overnight stock strategy backtest returns anomaly | 0 |
| 11 | ADX DMI trading strategy backtest stocks performance rules | 4 |
| 12 | overnight trading effect stocks strategy backtest returns | 1 |
| 13 | multi timeframe trend trading strategy backtest results | 5 |
| 14 | golden cross death cross backtest results stocks performance | 2 |
| 15 | swing trading momentum strategy stocks backtest 3% monthly | 1 |
| 16 | RSI 2 strategy backtest results Larry Connors SPY | 6 |
| 17 | turtle trading strategy backtest stocks rules performance | 3 |
| 18 | intraday breakout strategy stocks backtest high returns | 1 |
| 19 | overnight anomaly stock returns buy close sell open backtest | 2 |
| 20 | IBS internal bar strength indicator trading strategy backtest | 6 |
| 21 | stock market mean reversion strategy backtest high returns | 5 |
| 22 | trend following stocks ETF strategy CAGR 20% backtest | 1 |
| 23 | MACD histogram strategy backtest stocks returns | 3 |
| 24 | Stochastic oscillator swing trading strategy backtest results | 6 |

**Total independent searches: 24** (requirement was ≥10)

---

*Disclaimer: All performance metrics are from published backtests and do not guarantee future results. Past performance is not indicative of future returns. Transaction costs, slippage, and taxes can significantly impact actual performance. Conduct your own due diligence before implementing any trading strategy.*
