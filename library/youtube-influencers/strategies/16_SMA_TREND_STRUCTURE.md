# 20/50/200 SMA Trend Structure Strategy
## Used by: SMB Capital, Stage Analysis

### Overview
Use 20, 50, and 200 period SMAs to define trend structure. Only buy when bullishly aligned (20 > 50 > 200, all rising). Foundation of Stan Weinstein's Stage Analysis and IBD's CANSLIM.

### The Hierarchy
- **20 SMA:** Short-term trend, provides occasional support
- **50 SMA:** Intermediate trend, main swing support in Stage 2
- **200 SMA:** Long-term line in the sand, defines bull/bear market

### Stage 2 (Active Bull) Confirmation
1. 20 > 50 > 200 SMA (all rising)
2. Price above all three
3. Higher highs and higher lows on weekly
4. Golden cross has occurred (50 crossed above 200)
5. 200 SMA rising for 4+ months

### Entry Rules (Long Only, Stage 2)
**At 20 SMA bounce (tight stop):**
- Price touches 20 SMA, volume dries up
- Bullish reversal candle at 20 SMA
- Stop: below 20 SMA
- Risk: 2-4%

**At 50 SMA bounce (normal swing):**
- Price touches 50 SMA, volume dries up
- Bullish reversal candle at 50 SMA
- Stop: below 50 SMA
- Risk: 5-8%

**At 200 SMA bounce (major trend):**
- Rare in strong Stage 2 trends
- Stop: below 200 SMA
- Risk: 8-12%

### ETF Implementation (Simplest)
Buy SPY/QQQ when 50 SMA > 200 SMA AND both rising. Exit when 50 SMA falls below 200 SMA. This captures the bulk of bull markets.

### Stop Loss Rules
- At 20 SMA entry: stop below 50 SMA
- At 50 SMA entry: stop below 200 SMA
- At 200 SMA entry: stop below the swing low

### Market Regimes
- **Stage 2 (20 > 50 > 200):** Long only, aggressive entries
- **Stage 3 (tangled MA):** Reduce size, be selective
- **Stage 4 (20 < 50 < 200):** Cash, no longs

### Adapting for $25-100k
- Works great on QQQ/SPY for lower risk
- Individual stocks: only in Stage 2
- Don't bottom fish in Stage 4

### Resources
- Stan Weinstein: "Secrets for Profiting..."
- SMB Capital: "The Only Moving Average Guide"
- IBD: investors.com
