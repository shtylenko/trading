# Relative Strength Sector Rotation Strategy
## Used by: IBD (CANSLIM), Mark Minervini, SMB Capital

### Overview
Find the strongest sectors using RS, then find the strongest stocks within those sectors. This is the foundation of CANSLIM and most institutional money management.

### RS Calculation
- **Stock RS:** 12-month price performance vs S&P 500
- **Sector RS:** Sector ETF price / SPY price
- **RS Rating:** 1-99 ranking, 99 = top 1%

### Weekly Process
1. Check 11 sector ETFs: XLK, XLF, XLE, XLI, XLV, XLP, XLU, XLB, XLY, XLC, XLRE
2. Find the 3-5 with strongest RS (sector/SPY ratio rising)
3. Within top sectors, find stocks with RS > 80
4. Screen only those for VCP, breakout, or pullback setups
5. Buy only the best stock in each leading sector

### Sector Rotation Model
- **Early Bull:** Technology (XLK), Consumer Disc (XLY)
- **Mid Bull:** Industrials (XLI), Energy (XLE), Materials (XLB)
- **Late Bull:** Healthcare (XLV), Staples (XLP), Utilities (XLU)
- **Bear:** Cash, short-duration bonds, inverse ETFs

### Simple ETF Implementation
1. Buy top 3 RS sector ETFs each month
2. Rebalance quarterly
3. Hold for 1-3 months per sector
4. This alone beats most active managers over time

### Entry Timing
- Buy breakouts in top RS stocks within top RS sectors
- Buy pullbacks in same
- Exit when stock's RS rating falls below 70
- Exit when sector falls out of top 5 by RS

### Adapting for $25-100k
- Buy sector ETFs directly (XLK, XLF, etc.)
- Focus on 2-3 sectors maximum
- Check Finviz for sector performance weekly

### Resources
- IBD: investors.com
- Minervini: SEPA methodology
- Finviz: sector performance map
