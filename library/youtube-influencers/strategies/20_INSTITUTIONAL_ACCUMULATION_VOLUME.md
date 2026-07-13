# Institutional Accumulation (Volume Analysis) Strategy
## Used by: StockBee (Pradeep Bonde), Gaurav

### Overview
Track institutional buying using volume indicators to detect accumulation before price breaks out. Institutions make 70%+ of daily volume, and their footprint shows in volume data.

### Key Indicators

**On-Balance Volume (OBV):** Cumulative volume. Rising OBV = accumulation. OBV rising while price flat = bullish divergence.

**Chaikin Money Flow (CMF)(20):** > 0 = buying pressure. > 0.2 = strong accumulation. Best at confirming VCP/bull flag patterns.

**Money Flow Index (MFI)(14):** Volume-weighted RSI. < 20 = oversold. Divergence = potential reversal.

**Volume-by-Price:** Shows where most volume traded = institutional levels.

### Accumulation Patterns
- Rising OBV with flat price = stealth accumulation
- Volume dry-up during consolidation (40-60% below avg)
- Volume spike on bounce from support (institutions defending level)
- Quiet volume on up days, higher volume on down days = distribution (AVOID)

### Using with VCP Pattern
1. Identify VCP on chart
2. Check: OBV rising? CMF > 0?
3. Volume dry-up in final T = supply exhausted
4. Volume surge on breakout = institutional confirmation
5. If no volume surge on breakout = skip the trade

### Scanner Setup
```
OBV 20-day rising
CMF(20) > 0
Volume today < SMA(volume,20) [dry-up today]
Price within 15% of 52-week high
20 > 50 > 200 SMA
Price > $10
```

### Risk Management
- Use volume as confirmation, not standalone signal
- No volume confirmation = skip the trade
- Exit if volume indicators reverse (CMF turns negative)

### Resources
- StockBee blog: stockbee.blogspot.com
- Gaurav (Market Trend) YouTube
- StockCharts.com: Volume indicators
