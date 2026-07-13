# Bollinger Band Squeeze & Walk Strategy
## Used by: TradingLab (4M+ Views), Rayner Teo

### Overview
Bollinger Bands contract (squeeze) before explosive moves and expand (walk) during strong trends. Combine with RSI for timing. Popularized by TradingLab, John Bollinger.

### Settings
- Period: 20, StdDev: 2, Source: Close
- Upper band = 20 SMA + (2 × StdDev)
- Lower band = 20 SMA - (2 × StdDev)
- %b = (Close - Lower) / (Upper - Lower)

### Squeeze Identification
- Bands narrow to tightest in 3+ months
- %b oscillates in a narrow range
- **BandWidth** (Upper-Lower)/Middle reaches 6-month low
- Low volatility signals impending expansion

### Walk Identification (Strong Trend)
- Price closes above upper band
- Bands widen (bandwidth increasing)
- Price holds above middle band (20 SMA) on pullbacks
- RSI > 50 throughout (stays overbought in strong trends)

### Entry Rules

**Squeeze Breakout Entry:**
1. Bands at 6-month tightest
2. Price breaks above upper band with volume
3. RSI > 50
4. Enter at close of breakout candle
5. Stop: below squeeze low

**Walk Pullback Entry:**
1. Price has been walking upper band
2. Pulls back to middle band (20 SMA) on declining volume
3. Middle band is rising
4. Bullish reversal at middle band
5. RSI > 50 (not below 40)
6. Enter on confirmation

### RSI Filters
- RSI(14) > 50 = bullish bias, only take longs
- RSI < 30 in uptrend = oversold bounce opportunity
- RSI divergence (price up, RSI down) = warning

### Stop Loss
- Squeeze entry: below the squeeze low (2-4%)
- Walk entry: below middle band / 20 SMA (3-6%)
- Normal: below the recent swing low

### Targets
- First: prior resistance
- Second: 2× ATR from entry
- Trail: once up 2:1, move stop to breakeven

### Adapting for $25-100k
- QQQ/SPY daily for lower risk
- Individual stocks: liquid, tight bands
- Use BB + RSI combo on TradingView

### Resources
- TradingLab: "Bollinger Band + RSI Strategy" (1.7M views)
- John Bollinger: "Bollinger on Bollinger Bands"
