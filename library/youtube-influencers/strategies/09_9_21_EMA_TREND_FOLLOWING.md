# 9/21 EMA Trend Following Strategy
## Used by: Rayner Teo, Martin Luk, SMB Capital

### Overview
Exponential Moving Averages (EMAs) are the most basic yet effective trend-following tool. The **9 and 21 EMA** combination provides the sweet spot: fast enough for swing trades, slow enough to filter noise. Buy on pullbacks to rising EMAs in a confirmed uptrend.

### EMA Hierarchy
**9 EMA:** Fastest — follows price closely, short-term trend
**21 EMA:** Intermediate — smoother trend line, main swing support
**50 EMA:** Medium-term — major support in uptrends
**200 EMA:** Long-term — line between bull and bear market

### Trend Identification
**Strong uptrend (Stage 2):** 9 > 21 > 50 > 200, all rising, price above all
**Weak uptrend:** EMAs aligned but flatter
**Choppy/Tangled:** EMAs crossing each other = avoid
**Downtrend:** EMAs stacked in reverse = no longs

### Entry Rules (Long Only)
1. **Trend confirmed:** 9 > 21 > 50, all rising, price above 200
2. **Pullback:** Price pulls back to 9 or 21 EMA
3. **Bounce confirmation:** A bullish candle (hammer, engulfing, or higher low) at the EMA
4. **Entry on close of confirmation candle**

**Alternative entry:** Buy when price closes above 9 EMA after touching 21 EMA

### Stop Loss Placement
- **Tight:** Below 21 EMA (1-2% risk for strong stocks)
- **Normal:** Below 50 EMA (3-5% risk)
- **Wide:** Below 200 EMA (last resort for major trends)

### Profit Taking
- **First target:** Prior high or next resistance zone
- **Primary exit:** Close below 9 EMA (swing trade) or 21 EMA (position trade)
- **Scale out:** 1/3 at first target, 1/3 at second, trail remainder with 9 EMA

### Multiple Timeframe Confluence
- **Weekly:** Determine overall trend direction
- **Daily:** Primary timeframe for entry
- **4-Hour/1-Hour:** Fine-tune entry timing

### Risk Management
- Risk 1% per trade (0.5% for aggressive)
- Max 8 open positions
- Don't trade when EMAs are tangled (ADX < 20)

### Scanner Setup (Finviz)
```
SMA_9 above SMA_21
SMA_21 above SMA_50
SMA_200 rising (slope up)
Price above SMA_50
Relative Strength > 70
Volume > 500K
Price > $10
```

### ETF Applications
**For QQQ, SPY, IWM:**
- 9/21 EMA cross on daily chart
- Buy on first pullback to 9 or 21 EMA after bullish cross
- Exit when price closes below 21 EMA
- Stop: below 50 EMA

### Common Mistakes
1. Buying into a downtrend (9 < 21 < 50)
2. Catching a falling knife (buying before price holds an EMA)
3. Using EMA cross alone without price action confirmation
4. Not checking higher timeframe (daily/weekly alignment)

### Resources
- Rayner Teo: "Moving Average Trading Secrets" (3M+ views)
- SMB Capital: "The Only Moving Average Guide"
- Martin Luk: 9 EMA trail exit strategy
